using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace InkDrift.Net
{
    /// <summary>Finds games hosted on the local network: broadcasts Discover to the game ports, hosts answer HostInfo.</summary>
    public class LanDiscovery : IDisposable
    {
        public class Found { public IPEndPoint ep; public string host, track, version; public int players, max, phase; public float seen; }

        public readonly List<Found> Games = new List<Found>();
        readonly NetTransport net;
        float timer;

        public LanDiscovery()
        {
            try { net = new NetTransport(0, true); net.OnMessage += OnMessage; }
            catch (Exception e) { Debug.LogWarning("[Net] discovery: " + e.Message); }
        }

        public void Dispose() { net?.Dispose(); }

        public void Poll()
        {
            if (net == null) return;
            net.Poll();
            timer -= Time.unscaledDeltaTime;
            if (timer > 0f) return;
            timer = 1.2f;
            var probe = new NetWriter(Msg.Discover).Bytes;
            var targets = new List<IPAddress> { IPAddress.Broadcast, IPAddress.Loopback };
            foreach (var b in SubnetBroadcasts()) if (!targets.Contains(b)) targets.Add(b);
            foreach (var ip in targets)
                for (int port = NetSession.DefaultPort; port < NetSession.DefaultPort + 4; port++)
                    net.SendUnreliable(new IPEndPoint(ip, port), probe, probe.Length);
            Games.RemoveAll(g => Time.realtimeSinceStartup - g.seen > 4f);
        }

        void OnMessage(IPEndPoint from, byte[] data)
        {
            var r = new NetReader(data);
            if (r.Type != Msg.HostInfo) return;
            var f = Games.Find(g => g.ep.Equals(from));
            if (f == null) { f = new Found { ep = from }; Games.Add(f); }
            f.host = r.Str(); f.players = r.U8(); f.max = r.U8(); f.phase = r.U8(); f.track = r.Str(); f.version = r.Str();
            f.seen = Time.realtimeSinceStartup;
            // one host answers on every address it has (loopback, Wi-Fi, a VPN): keep one, preferring the home network
            var same = Games.FindAll(g => g.host == f.host && g.ep.Port == f.ep.Port && g.track == f.track);
            if (same.Count > 1)
            {
                same.Sort((a, b) => Rank(a.ep.Address).CompareTo(Rank(b.ep.Address)));
                for (int i = 1; i < same.Count; i++) Games.Remove(same[i]);
                same[0].seen = f.seen;
            }
        }

        /// <summary>Lower = better address to show: home/office LAN, then other private, then loopback, then the rest.</summary>
        static int Rank(IPAddress a)
        {
            var b = a.GetAddressBytes();
            if (b[0] == 192 && b[1] == 168) return 0;
            if (b[0] == 10 || (b[0] == 172 && b[1] >= 16 && b[1] < 32)) return 1;
            if (b[0] == 127) return 3;
            return 2;
        }

        static IEnumerable<IPAddress> SubnetBroadcasts()
        {
            var list = new List<IPAddress>();
            try
            {
                foreach (var ni in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (ni.OperationalStatus != System.Net.NetworkInformation.OperationalStatus.Up) continue;
                    foreach (var ua in ni.GetIPProperties().UnicastAddresses)
                    {
                        if (ua.Address.AddressFamily != AddressFamily.InterNetwork || ua.IPv4Mask == null) continue;
                        var a = ua.Address.GetAddressBytes(); var m = ua.IPv4Mask.GetAddressBytes();
                        if (m.Length != 4 || m[0] == 0) continue;
                        var b = new byte[4];
                        for (int i = 0; i < 4; i++) b[i] = (byte)(a[i] | ~m[i]);
                        list.Add(new IPAddress(b));
                    }
                }
            }
            catch { }
            return list;
        }
    }

    /// <summary>
    /// UPnP IGD port mapping: find the router (SSDP), then ask it to forward a UDP port to this computer and tell us the
    /// public address. Many home routers allow this; when they don't, the host has to forward the port by hand.
    /// </summary>
    public static class UPnP
    {
        static string controlUrl, serviceType;
        static readonly HttpClient http = new HttpClient { Timeout = TimeSpan.FromSeconds(4) };

        public struct Result { public bool ok; public string externalIp, error; }

        public static async Task<Result> AddMappingAsync(int port, string description)
        {
            try
            {
                if (!await DiscoverAsync()) return new Result { error = "no UPnP router found" };
                string local = LocalAddressToward(new Uri(controlUrl).Host);
                string args = $"<NewRemoteHost></NewRemoteHost><NewExternalPort>{port}</NewExternalPort><NewProtocol>UDP</NewProtocol>" +
                              $"<NewInternalPort>{port}</NewInternalPort><NewInternalClient>{local}</NewInternalClient><NewEnabled>1</NewEnabled>" +
                              $"<NewPortMappingDescription>{description}</NewPortMappingDescription><NewLeaseDuration>0</NewLeaseDuration>";
                var resp = await SoapAsync("AddPortMapping", args);
                if (resp == null || resp.Contains("UPnPError")) return new Result { error = "the router refused the mapping" };
                var ipResp = await SoapAsync("GetExternalIPAddress", "");
                var m = ipResp != null ? Regex.Match(ipResp, "<NewExternalIPAddress>([^<]+)</NewExternalIPAddress>") : null;
                string ext = m != null && m.Success ? m.Groups[1].Value : null;
                // a private external address means another NAT sits in front of this router (no inbound path)
                if (ext == null || IsPrivate(ext)) return new Result { error = "the router is behind another network (no public address)", externalIp = ext };
                Debug.Log($"[Net] UPnP mapped UDP {port} -> {local}, public address {ext}");
                return new Result { ok = true, externalIp = ext };
            }
            catch (Exception e) { return new Result { error = e.Message }; }
        }

        public static async void RemoveMappingAsync(int port)
        {
            try { if (controlUrl != null) await SoapAsync("DeletePortMapping", $"<NewRemoteHost></NewRemoteHost><NewExternalPort>{port}</NewExternalPort><NewProtocol>UDP</NewProtocol>"); }
            catch { }
        }

        static bool IsPrivate(string ip)
        {
            if (!IPAddress.TryParse(ip, out var a)) return true;
            var b = a.GetAddressBytes();
            return b[0] == 10 || (b[0] == 172 && b[1] >= 16 && b[1] < 32) || (b[0] == 192 && b[1] == 168) || (b[0] == 100 && b[1] >= 64 && b[1] < 128) || b[0] == 127 || b[0] == 0;
        }

        static string LocalAddressToward(string host)
        {
            try
            {
                using (var s = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp))
                {
                    s.Connect(host, 1900);
                    return ((IPEndPoint)s.LocalEndPoint).Address.ToString();
                }
            }
            catch { return NetTransport.LocalAddresses().Count > 0 ? NetTransport.LocalAddresses()[0] : "0.0.0.0"; }
        }

        static async Task<bool> DiscoverAsync()
        {
            if (controlUrl != null) return true;
            using (var udp = new UdpClient(AddressFamily.InterNetwork))
            {
                udp.Client.ReceiveTimeout = 2500;
                foreach (var st in new[] { "urn:schemas-upnp-org:device:InternetGatewayDevice:1", "urn:schemas-upnp-org:service:WANIPConnection:1" })
                {
                    string req = "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nST: " + st + "\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n\r\n";
                    var b = Encoding.ASCII.GetBytes(req);
                    await udp.SendAsync(b, b.Length, new IPEndPoint(IPAddress.Parse("239.255.255.250"), 1900));
                }
                var deadline = DateTime.UtcNow.AddSeconds(3);
                while (DateTime.UtcNow < deadline)
                {
                    var recv = udp.ReceiveAsync();
                    var done = await Task.WhenAny(recv, Task.Delay(Math.Max(1, (int)(deadline - DateTime.UtcNow).TotalMilliseconds)));
                    if (done != recv) break;
                    string text = Encoding.ASCII.GetString(recv.Result.Buffer);
                    var loc = Regex.Match(text, @"(?im)^location:\s*(\S+)");
                    if (!loc.Success) continue;
                    if (await ReadDescriptionAsync(loc.Groups[1].Value)) return true;
                }
            }
            return false;
        }

        static async Task<bool> ReadDescriptionAsync(string location)
        {
            string xml;
            try { xml = await http.GetStringAsync(location); } catch { return false; }
            foreach (var type in new[] { "urn:schemas-upnp-org:service:WANIPConnection:2", "urn:schemas-upnp-org:service:WANIPConnection:1", "urn:schemas-upnp-org:service:WANPPPConnection:1" })
            {
                int i = xml.IndexOf("<serviceType>" + type + "</serviceType>", StringComparison.Ordinal);
                if (i < 0) continue;
                var m = Regex.Match(xml.Substring(i), "<controlURL>([^<]+)</controlURL>");
                if (!m.Success) continue;
                var baseUri = new Uri(location);
                var bm = Regex.Match(xml, "<URLBase>([^<]+)</URLBase>");
                if (bm.Success) baseUri = new Uri(bm.Groups[1].Value);
                controlUrl = new Uri(baseUri, m.Groups[1].Value.Trim()).ToString();
                serviceType = type;
                return true;
            }
            return false;
        }

        static async Task<string> SoapAsync(string action, string args)
        {
            string body = "<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\">" +
                          $"<s:Body><u:{action} xmlns:u=\"{serviceType}\">{args}</u:{action}></s:Body></s:Envelope>";
            var req = new HttpRequestMessage(HttpMethod.Post, controlUrl) { Content = new StringContent(body, Encoding.UTF8, "text/xml") };
            req.Headers.Add("SOAPAction", $"\"{serviceType}#{action}\"");
            try
            {
                var resp = await http.SendAsync(req);
                return await resp.Content.ReadAsStringAsync();
            }
            catch { return null; }
        }
    }

    /// <summary>
    /// STUN (RFC 5389) binding request from the game's own socket: the public address and port the internet sees for
    /// it, which goes into the invite code when the router can't be asked to open the port.
    /// </summary>
    public static class Stun
    {
        static TaskCompletionSource<IPEndPoint> pending;
        static byte[] txId;

        public static async Task<IPEndPoint> QueryAsync(NetTransport net)
        {
            if (net == null) return null;
            foreach (var server in new[] { "stun.l.google.com", "stun.cloudflare.com" })
            {
                IPEndPoint ep;
                try
                {
                    var addrs = await Dns.GetHostAddressesAsync(server);
                    var a = Array.Find(addrs, x => x.AddressFamily == AddressFamily.InterNetwork);
                    if (a == null) continue;
                    ep = new IPEndPoint(a, server.Contains("google") ? 19302 : 3478);
                }
                catch { continue; }
                pending = new TaskCompletionSource<IPEndPoint>();
                txId = new byte[12]; new System.Random().NextBytes(txId);
                var req = new byte[20];
                req[0] = 0x00; req[1] = 0x01;                       // binding request, no attributes
                req[4] = 0x21; req[5] = 0x12; req[6] = 0xA4; req[7] = 0x42;   // magic cookie
                Buffer.BlockCopy(txId, 0, req, 8, 12);
                for (int attempt = 0; attempt < 3; attempt++)
                {
                    net.SendRaw(ep, req, req.Length);
                    var done = await Task.WhenAny(pending.Task, Task.Delay(700));
                    if (done == pending.Task) return pending.Task.Result;
                }
            }
            return null;
        }

        /// <summary>Called by the session for datagrams that aren't game packets.</summary>
        public static void OnDatagram(IPEndPoint from, byte[] d, int len)
        {
            if (pending == null || len < 20 || d[0] != 0x01 || d[1] != 0x01) return;
            for (int i = 0; i < 12; i++) if (d[8 + i] != txId[i]) return;
            int p = 20;
            while (p + 4 <= len)
            {
                int type = (d[p] << 8) | d[p + 1], alen = (d[p + 2] << 8) | d[p + 3];
                if ((type == 0x0020 || type == 0x0001) && alen >= 8 && d[p + 5] == 0x01)
                {
                    int port = (d[p + 6] << 8) | d[p + 7];
                    var ip = new byte[] { d[p + 8], d[p + 9], d[p + 10], d[p + 11] };
                    if (type == 0x0020)
                    {
                        port ^= 0x2112;
                        ip[0] ^= 0x21; ip[1] ^= 0x12; ip[2] ^= 0xA4; ip[3] ^= 0x42;
                    }
                    pending.TrySetResult(new IPEndPoint(new IPAddress(ip), port));
                    return;
                }
                p += 4 + ((alen + 3) & ~3);
            }
        }
    }
}
