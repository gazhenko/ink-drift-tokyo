using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

namespace InkDrift.Net
{
    /// <summary>
    /// UDP socket with a receive thread, plus per-peer reliable ordered delivery (sequence numbers, acks and resends)
    /// on top of plain unreliable datagrams. Packet: 'I','K', protocol, kind, then for reliable packets a u16 sequence.
    /// Everything except Receive runs on the main thread; received datagrams queue up for Poll.
    /// </summary>
    public class NetTransport : IDisposable
    {
        public const byte Protocol = 3;
        const byte KindUnreliable = 1, KindReliable = 2, KindAck = 3, KindKeepAlive = 4;
        const float ResendInterval = 0.15f;
        const int MaxResends = 60;                 // ~9 s before a reliable message gives up (the peer times out first)

        public int LocalPort { get; private set; }
        public long BytesIn, BytesOut;

        readonly Socket socket;
        readonly Thread thread, heartbeat;
        // endpoints the heartbeat thread keeps warm (copied under the lock: peers itself is main-thread only)
        readonly List<IPEndPoint> heartbeatTargets = new List<IPEndPoint>();
        volatile bool running = true;
        readonly ConcurrentQueue<(byte[] data, int len, IPEndPoint from)> inbox = new ConcurrentQueue<(byte[], int, IPEndPoint)>();

        class Pending { public ushort seq; public byte[] packet; public float nextSend; public int tries; }
        public class Peer
        {
            public IPEndPoint ep;
            public ushort nextSendSeq = 1;
            public ushort nextRecvSeq = 1;
            public readonly List<object> pendingOut = new List<object>();
            public readonly Dictionary<ushort, byte[]> reorder = new Dictionary<ushort, byte[]>();
            public float lastHeard;
        }
        readonly Dictionary<string, Peer> peers = new Dictionary<string, Peer>();

        /// <summary>Raw unreliable/reliable payload delivered to the session (payload starts at offset 0).</summary>
        public event Action<IPEndPoint, byte[]> OnMessage;
        /// <summary>Datagram that isn't ours (STUN responses, discovery probes): full bytes.</summary>
        public event Action<IPEndPoint, byte[], int> OnForeign;

        public NetTransport(int port, bool broadcast = false)
        {
            socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            try { socket.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, false); } catch { }
            socket.Bind(new IPEndPoint(IPAddress.Any, port));
            if (broadcast) socket.EnableBroadcast = true;
            // Windows: an ICMP 'port unreachable' would otherwise make the next ReceiveFrom throw and kill the thread
            try { const int SIO_UDP_CONNRESET = -1744830452; socket.IOControl(SIO_UDP_CONNRESET, new byte[] { 0 }, null); } catch { }
            LocalPort = ((IPEndPoint)socket.LocalEndPoint).Port;
            thread = new Thread(ReceiveLoop) { IsBackground = true, Name = "InkNetRecv" };
            thread.Start();
            heartbeat = new Thread(HeartbeatLoop) { IsBackground = true, Name = "InkNetBeat" };
            heartbeat.Start();
        }

        /// <summary>
        /// Once a second, a tiny packet to every peer from its own thread: a frame that stalls for seconds (loading a
        /// track, compiling shaders on a slow GPU) must not look like a dropped connection to the others.
        /// </summary>
        void HeartbeatLoop()
        {
            var pkt = new byte[] { (byte)'I', (byte)'K', Protocol, KindKeepAlive };
            var targets = new List<IPEndPoint>();
            while (running)
            {
                Thread.Sleep(1000);
                targets.Clear();
                lock (heartbeatTargets) targets.AddRange(heartbeatTargets);
                foreach (var t in targets)
                {
                    try { socket.SendTo(pkt, 0, pkt.Length, SocketFlags.None, t); }
                    catch { if (!running) return; }
                }
            }
        }

        void ReceiveLoop()
        {
            var buf = new byte[2048];
            while (running)
            {
                try
                {
                    EndPoint from = new IPEndPoint(IPAddress.Any, 0);
                    int n = socket.ReceiveFrom(buf, ref from);
                    if (n <= 0) continue;
                    var copy = new byte[n];
                    Buffer.BlockCopy(buf, 0, copy, 0, n);
                    inbox.Enqueue((copy, n, (IPEndPoint)from));
                }
                catch (SocketException) { if (!running) return; }
                catch (ObjectDisposedException) { return; }
                catch (Exception e) { if (running) Debug.LogWarning("[Net] receive: " + e.Message); }
            }
        }

        public void Dispose()
        {
            running = false;
            try { socket.Close(); } catch { }
        }

        static string Key(IPEndPoint ep) => ep.Address + ":" + ep.Port;

        public Peer GetPeer(IPEndPoint ep, bool create = true)
        {
            string k = Key(ep);
            if (!peers.TryGetValue(k, out var p) && create)
            {
                p = new Peer { ep = ep, lastHeard = Time.realtimeSinceStartup };
                peers[k] = p;
                lock (heartbeatTargets) heartbeatTargets.Add(ep);
            }
            return p;
        }

        public void RemovePeer(IPEndPoint ep)
        {
            peers.Remove(Key(ep));
            lock (heartbeatTargets) heartbeatTargets.RemoveAll(e => e.Equals(ep));
        }

        /// <summary>Tests: drop this fraction of outgoing datagrams.</summary>
        public static float TestDropRate;
        static readonly System.Random dropRng = new System.Random(5);

        public void SendRaw(IPEndPoint to, byte[] data, int len)
        {
            if (TestDropRate > 0f && dropRng.NextDouble() < TestDropRate) return;
            try { socket.SendTo(data, 0, len, SocketFlags.None, to); BytesOut += len; }
            catch (Exception e) { Debug.LogWarning("[Net] send to " + to + ": " + e.Message); }
        }

        public void SendUnreliable(IPEndPoint to, byte[] payload, int len)
        {
            var pkt = new byte[len + 4];
            pkt[0] = (byte)'I'; pkt[1] = (byte)'K'; pkt[2] = Protocol; pkt[3] = KindUnreliable;
            Buffer.BlockCopy(payload, 0, pkt, 4, len);
            SendRaw(to, pkt, pkt.Length);
        }

        public void SendReliable(IPEndPoint to, byte[] payload, int len)
        {
            var peer = GetPeer(to);
            ushort seq = peer.nextSendSeq++;
            var pkt = new byte[len + 6];
            pkt[0] = (byte)'I'; pkt[1] = (byte)'K'; pkt[2] = Protocol; pkt[3] = KindReliable;
            pkt[4] = (byte)(seq & 0xFF); pkt[5] = (byte)(seq >> 8);
            Buffer.BlockCopy(payload, 0, pkt, 6, len);
            peer.pendingOut.Add(new Pending { seq = seq, packet = pkt, nextSend = Time.realtimeSinceStartup + ResendInterval });
            SendRaw(to, pkt, pkt.Length);
        }

        /// <summary>Main thread: deliver queued datagrams and resend unacknowledged reliable ones.</summary>
        public void Poll()
        {
            float now = Time.realtimeSinceStartup;
            while (inbox.TryDequeue(out var m))
            {
                BytesIn += m.len;
                var d = m.data;
                if (m.len < 4 || d[0] != 'I' || d[1] != 'K' || d[2] != Protocol) { OnForeign?.Invoke(m.from, d, m.len); continue; }
                var peer = GetPeer(m.from);
                peer.lastHeard = now;
                byte kind = d[3];
                if (kind == KindKeepAlive) continue;
                if (kind == KindUnreliable)
                {
                    var payload = new byte[m.len - 4];
                    Buffer.BlockCopy(d, 4, payload, 0, payload.Length);
                    OnMessage?.Invoke(m.from, payload);
                }
                else if (kind == KindAck && m.len >= 6)
                {
                    ushort seq = (ushort)(d[4] | (d[5] << 8));
                    peer.pendingOut.RemoveAll(o => ((Pending)o).seq == seq);
                }
                else if (kind == KindReliable && m.len >= 6)
                {
                    ushort seq = (ushort)(d[4] | (d[5] << 8));
                    SendRaw(m.from, new byte[] { (byte)'I', (byte)'K', Protocol, KindAck, d[4], d[5] }, 6);
                    short ahead = (short)(seq - peer.nextRecvSeq);
                    if (ahead < 0) continue;                  // duplicate of something already delivered
                    var payload = new byte[m.len - 6];
                    Buffer.BlockCopy(d, 6, payload, 0, payload.Length);
                    if (ahead > 0) { if (ahead < 512) peer.reorder[seq] = payload; continue; }
                    OnMessage?.Invoke(m.from, payload);
                    peer.nextRecvSeq++;
                    while (peer.reorder.TryGetValue(peer.nextRecvSeq, out var next))
                    {
                        peer.reorder.Remove(peer.nextRecvSeq);
                        OnMessage?.Invoke(m.from, next);
                        peer.nextRecvSeq++;
                    }
                }
            }
            foreach (var p in peers.Values)
                for (int i = p.pendingOut.Count - 1; i >= 0; i--)
                {
                    var o = (Pending)p.pendingOut[i];
                    if (now < o.nextSend) continue;
                    if (++o.tries > MaxResends) { p.pendingOut.RemoveAt(i); continue; }
                    o.nextSend = now + ResendInterval;
                    SendRaw(p.ep, o.packet, o.packet.Length);
                }
        }

        public static IPEndPoint Parse(string host, int defaultPort)
        {
            host = host.Trim();
            int port = defaultPort;
            int colon = host.LastIndexOf(':');
            if (colon > 0 && host.IndexOf(':') == colon && int.TryParse(host.Substring(colon + 1), out int p)) { port = p; host = host.Substring(0, colon); }
            if (!IPAddress.TryParse(host, out var ip))
            {
                foreach (var a in Dns.GetHostAddresses(host))
                    if (a.AddressFamily == AddressFamily.InterNetwork) { ip = a; break; }
            }
            return ip == null ? null : new IPEndPoint(ip, port);
        }

        /// <summary>This machine's IPv4 addresses on its local networks (for the host screen).</summary>
        public static List<string> LocalAddresses()
        {
            var list = new List<string>();
            try
            {
                foreach (var ni in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (ni.OperationalStatus != System.Net.NetworkInformation.OperationalStatus.Up) continue;
                    if (ni.NetworkInterfaceType == System.Net.NetworkInformation.NetworkInterfaceType.Loopback) continue;
                    foreach (var ua in ni.GetIPProperties().UnicastAddresses)
                        if (ua.Address.AddressFamily == AddressFamily.InterNetwork && !list.Contains(ua.Address.ToString()))
                            list.Add(ua.Address.ToString());
                }
            }
            catch { }
            return list;
        }
    }
}
