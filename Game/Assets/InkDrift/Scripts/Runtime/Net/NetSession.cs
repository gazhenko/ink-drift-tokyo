using System;
using System.Collections.Generic;
using System.Net;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace InkDrift.Net
{
    public class NetPlayer
    {
        public int id;
        public string name = "DRIVER";
        public string carId = "hachi";
        public int paint;
        public bool ready, inLobby = true, loaded, finished;
        public float finishTime;
        public int ping;
        public IPEndPoint ep;          // host side: where this player's packets come from
        public float lastHeard;
        public bool hasState;
        public CarSnapshot state;      // latest snapshot of this player's car
        public float stateReceived;    // local realtime when it arrived
    }

    /// <summary>
    /// A multiplayer session (survives scene loads). One player hosts: the host keeps the lobby, starts races, syncs the
    /// green light and collects finishing times; every game simulates its own car and sends its state to the host,
    /// which relays it to the others. Friends join with the host's room code (through the online relay, so no router
    /// setup), by LAN discovery, or by address; if the relay can't be reached the host falls back to a direct invite
    /// code and opens its router port with UPnP where the router allows it.
    /// </summary>
    public class NetSession : MonoBehaviour
    {
        public const int DefaultPort = 7777;
        public const int MaxPlayers = 8;
        public const float Timeout = 15f;
        static readonly bool netLog = CommandLine.Has("-netLog");

        public enum Phase { Connecting, Lobby, Loading, Countdown, Racing, Results }

        public static NetSession I { get; private set; }
        /// <summary>In an online session (connected).</summary>
        public static bool Online => I != null && I.Connected;
        /// <summary>The current race is an online race.</summary>
        public static bool InRace => Online && (I.phase == Phase.Loading || I.phase == Phase.Countdown || I.phase == Phase.Racing || I.phase == Phase.Results);

        public bool IsHost { get; private set; }
        public bool Connected { get; private set; }
        public int LocalId { get; private set; } = -1;
        public Phase phase = Phase.Connecting;
        public string TrackId = "shibuya";
        public int Laps = 3;
        public readonly List<NetPlayer> Players = new List<NetPlayer>();
        public readonly List<int> Grid = new List<int>();
        public string Status = "";
        public string InviteCode, PublicAddress, PortStatus;
        /// <summary>Host: the online room code ("K7Q-4MZ") once the relay has given one; RelayStatus says why not.</summary>
        public string RoomCode, RelayStatus;
        /// <summary>Client: connected through the online relay rather than directly.</summary>
        public bool ViaRelay { get; private set; }
        /// <summary>Host: still waiting for the relay's room code.</summary>
        public bool RelayPending => IsHost && net != null && net.Relay != null && !net.Relay.IsOpen;
        public List<string> LanAddresses = new List<string>();
        public int Port => net != null ? net.LocalPort : 0;
        /// <summary>Host clock time of the green light (Countdown/Racing).</summary>
        public double GoTime;
        /// <summary>Final or running standings: player ids in order, with their finish times (-1 = still racing / DNF).</summary>
        public readonly List<(int id, float time)> Standings = new List<(int, float)>();
        public bool ResultsFinal;

        public event Action Changed;              // lobby/players/status changed (UI refresh)
        public event Action<string> Disconnected; // session over, with a reason
        public event Action<NetPlayer> PlayerLeft;

        NetTransport net;
        IPEndPoint hostEp;
        uint token;
        float helloTimer, helloDeadline, pingTimer, lobbyTimer;
        double clockOffset;
        float bestRtt = 999f;
        float relayRetryAt = -1f;
        int relayRetries, hellosSent;
        bool fallbackStarted;
        float firstFinish = -1f;
        float loadDeadline = -1f;
        LanDiscovery discovery;

        public NetPlayer Local => Find(LocalId);
        public NetPlayer Find(int id) { foreach (var p in Players) if (p.id == id) return p; return null; }

        static double Now => Time.realtimeSinceStartupAsDouble;
        /// <summary>The host's clock (seconds).</summary>
        public double HostTime => IsHost ? Now : Now + clockOffset;
        /// <summary>Local realtime at which the host clock reads t.</summary>
        public float LocalTimeOf(double hostT) => (float)(IsHost ? hostT : hostT - clockOffset);

        public static string PlayerName
        {
            get
            {
                var n = PlayerPrefs.GetString("mp_name", "");
                if (string.IsNullOrEmpty(n)) { n = "DRIVER-" + UnityEngine.Random.Range(100, 999); PlayerPrefs.SetString("mp_name", n); }
                return n;
            }
            set => PlayerPrefs.SetString("mp_name", string.IsNullOrWhiteSpace(value) ? "DRIVER" : value.Trim().ToUpperInvariant().Substring(0, Mathf.Min(16, value.Trim().Length)));
        }

        // ---------------------------------------------------------------- start / stop
        static NetSession Create()
        {
            if (I != null) I.Shutdown(null);
            var go = new GameObject("NetSession");
            DontDestroyOnLoad(go);
            I = go.AddComponent<NetSession>();
            return I;
        }

        /// <summary>Host a game on the default port (or the next free one).</summary>
        public static NetSession Host()
        {
            var s = Create();
            s.IsHost = true;
            for (int p = DefaultPort; p < DefaultPort + 10 && s.net == null; p++)
            {
                try { s.net = new NetTransport(p, true); }
                catch (Exception e) { Debug.Log($"[Net] port {p} busy: {e.Message}"); }
            }
            if (s.net == null) { s.Fail("Couldn't open a network port (7777-7786 are all in use)."); return s; }
            s.Hook();
            s.Connected = true;
            s.LocalId = 0;
            s.phase = Phase.Lobby;
            s.TrackId = GameSession.TrackId;
            s.Laps = TrackCatalog.Get(s.TrackId).laps;
            s.Players.Add(new NetPlayer { id = 0, name = PlayerName, carId = GameSession.CarId, paint = GameSession.PaintIndex, ready = true });
            s.LanAddresses = NetTransport.LocalAddresses();
            if (s.LanAddresses.Count > 0 && IPAddress.TryParse(s.LanAddresses[0], out var lan)) s.InviteCode = InviteCodec.Encode(lan, s.Port);
            s.Status = "Hosting on port " + s.Port;
            Debug.Log("[Net] hosting on port " + s.Port);
            if (CommandLine.Has("-noRelay")) s.StartFallback();
            else s.StartRelay();
            return s;
        }

        /// <summary>Join a host by room code, invite code, address, host name or ip:port.</summary>
        public static NetSession Join(string address)
        {
            var s = Create();
            IPEndPoint ep = null;
            bool viaRelay = RelayLink.TryParseCode(address, out string room);
            if (!viaRelay)
            {
                try { if (!InviteCodec.TryDecode(address, out ep)) ep = NetTransport.Parse(address, DefaultPort); }
                catch (Exception e) { Debug.Log("[Net] parse: " + e.Message); }
                if (ep == null) { s.Fail("Couldn't find \"" + address + "\". Check the code or address."); return s; }
            }
            try { s.net = new NetTransport(0, true); }
            catch (Exception e) { s.Fail("Couldn't open a network port: " + e.Message); return s; }
            s.Hook();
            if (viaRelay)
            {
                try { s.net.AttachRelay(RelayLink.Join(room)); }
                catch (Exception e) { s.Fail("Couldn't reach the online service: " + e.Message); return s; }
                s.ViaRelay = true;
                ep = NetTransport.RelayEndpoint(0);
            }
            s.hostEp = ep;
            s.net.GetPeer(ep);          // keep-alives to the host start now, so a stalled frame here doesn't look like we left
            s.token = (uint)UnityEngine.Random.Range(1, int.MaxValue);
            s.phase = Phase.Connecting;
            s.helloDeadline = Time.realtimeSinceStartup + 60f;      // until the first hello goes out; then 25 s from it
            s.Status = viaRelay ? "Joining room " + RelayLink.Format(room) + "…" : "Connecting to " + ep + "…";
            Debug.Log("[Net] joining " + (viaRelay ? "room " + room : ep.ToString()));
            return s;
        }

        void Hook()
        {
            net.OnMessage += OnMessage;
            net.OnForeign += OnForeign;
        }

        /// <summary>Leave the session (tells the others).</summary>
        public void Leave()
        {
            var bye = new NetWriter(Msg.Leave).U8(Math.Max(0, LocalId)).Bytes;
            if (IsHost) { foreach (var p in Players) if (p.ep != null) net?.SendUnreliable(p.ep, bye, bye.Length); }
            else if (hostEp != null) net?.SendUnreliable(hostEp, bye, bye.Length);
            Shutdown(null);
        }

        void Fail(string reason) { Debug.Log("[Net] session ended: " + reason); Status = reason; Shutdown(reason); }

        void Shutdown(string reason)
        {
            Connected = false;
            net?.Dispose(); net = null;
            if (upnpMapped) UPnP.RemoveMappingAsync(upnpPort);
            if (I == this) I = null;
            if (reason != null) Disconnected?.Invoke(reason);
            LastDisconnectReason = reason;
            Destroy(gameObject);
        }

        /// <summary>Why the last session ended (shown by the menu after it returns).</summary>
        public static string LastDisconnectReason;

        void OnDestroy() { net?.Dispose(); if (I == this) I = null; }
        void OnApplicationQuit() { if (Connected) Leave(); }

        // ---------------------------------------------------------------- internet access (host)
        bool upnpMapped;
        int upnpPort;

        /// <summary>Ask the relay for a room code (friends anywhere join with it; nobody touches their router).</summary>
        void StartRelay()
        {
            RelayStatus = "Getting a room code…";
            try { net.AttachRelay(RelayLink.Host()); }
            catch (Exception e) { HostRelayLost("Couldn't reach the online service: " + e.Message); }
        }

        /// <summary>The relay is unreachable or dropped: retry in the background, and offer a direct invite code meanwhile.</summary>
        void HostRelayLost(string why)
        {
            bool hadRoom = RoomCode != null;
            net.DetachRelay();
            RoomCode = null;
            for (int i = Players.Count - 1; i >= 0; i--)
                if (NetTransport.IsRelay(Players[i].ep)) DropPlayer(Players[i], "lost the connection");
            relayRetries++;
            relayRetryAt = Time.realtimeSinceStartup + Mathf.Min(60f, 5f * relayRetries);
            RelayStatus = hadRoom ? "Lost the connection to the online service. Getting a new room code…"
                : (why ?? "Couldn't reach the online service.") + " Trying again…";
            Debug.Log("[Net] relay lost: " + (why ?? "closed"));
            StartFallback();
            Changed?.Invoke();
        }

        /// <summary>Direct connections: open the router port (UPnP) or find the public address (STUN) for an invite code.</summary>
        void StartFallback()
        {
            if (fallbackStarted) return;
            fallbackStarted = true;
            PortStatus = "Opening the port on your router…";
            OpenInternetAccess();
        }

        void PollRelay()
        {
            var link = net?.Relay;
            if (link == null) return;
            while (link.Events.TryDequeue(out var e))
            {
                if (netLog) Debug.Log($"[Net] relay {e.kind} {e.id} {e.text}");
                switch (e.kind)
                {
                    case RelayLink.EventKind.Open:
                        if (IsHost)
                        {
                            RoomCode = RelayLink.Format(e.text); RelayStatus = null; relayRetries = 0;
                            Debug.Log("[Net] online room " + RoomCode);
                            if (CommandLine.Has("-mpCodeFile")) try { System.IO.File.WriteAllText(CommandLine.Get("-mpCodeFile"), RoomCode); } catch { }
                            Changed?.Invoke();
                        }
                        else { Status = "In the room, waiting for the host…"; Changed?.Invoke(); }
                        break;
                    case RelayLink.EventKind.Left:
                        if (IsHost) { var p = ByEndpoint(NetTransport.RelayEndpoint(e.id)); if (p != null) DropPlayer(p, "left"); }
                        break;
                    case RelayLink.EventKind.Error:
                    case RelayLink.EventKind.Closed:
                        if (!IsHost) Fail(e.text ?? (Connected ? "Lost the connection to the online room." : "Couldn't join the room."));
                        else HostRelayLost(e.text);
                        return;
                }
            }
        }

        async void OpenInternetAccess()
        {
            int port = Port;
            try
            {
                var r = await UPnP.AddMappingAsync(port, "INK DRIFT TOKYO");
                if (this == null) return;
                if (r.ok)
                {
                    upnpMapped = true; upnpPort = port;
                    PublicAddress = r.externalIp;
                    if (IPAddress.TryParse(r.externalIp, out var ext)) InviteCode = InviteCodec.Encode(ext, port);
                    PortStatus = "Router port opened: friends can join over the internet with your invite code.";
                }
                else
                {
                    var stun = await Stun.QueryAsync(net);
                    if (this == null) return;
                    if (stun != null)
                    {
                        PublicAddress = stun.Address.ToString();
                        if (InviteCode == null || !string.IsNullOrEmpty(PublicAddress)) InviteCode = InviteCodec.Encode(stun.Address, port);
                    }
                    PortStatus = "Your router didn't open the port automatically. Friends on your network can join; over the internet, forward UDP " + port + " to this computer (or use a virtual LAN such as Tailscale or ZeroTier).";
                }
            }
            catch (Exception e) { PortStatus = "Couldn't check the router: " + e.Message; }
            Changed?.Invoke();
        }

        // ---------------------------------------------------------------- loop
        void Update()
        {
            if (net == null) return;
            net.Poll();
            if (net == null) return;
            PollRelay();
            if (net == null) return;
            float now = Time.realtimeSinceStartup;
            if (IsHost) HostUpdate(now); else ClientUpdate(now);
        }

        void HostUpdate(float now)
        {
            for (int i = Players.Count - 1; i >= 0; i--)
            {
                var p = Players[i];
                if (p.id == LocalId || p.ep == null) continue;
                var peer = net.GetPeer(p.ep, false);           // keep-alives count: they're seen by the transport
                float heard = Mathf.Max(p.lastHeard, peer != null ? peer.lastHeard : 0f);
                if (now - heard > Timeout) { Debug.Log($"[Net] {p.name} timed out"); DropPlayer(p, "timed out"); }
            }
            if (relayRetryAt > 0f && now > relayRetryAt && net.Relay == null) { relayRetryAt = -1f; StartRelay(); }
            lobbyTimer -= Time.unscaledDeltaTime;
            if (lobbyTimer <= 0f) { lobbyTimer = 1f; BroadcastLobby(false); }   // keeps pings shown and peers warm
            if (phase == Phase.Loading && (AllLoaded() || (loadDeadline > 0f && now > loadDeadline))) SendGo();
            if (phase == Phase.Racing && !ResultsFinal)
            {
                bool all = true;
                foreach (var p in Players) if (!p.finished) all = false;
                if (all || (firstFinish > 0f && now - firstFinish > 45f)) { ResultsFinal = true; BroadcastResults(); }
            }
        }

        void ClientUpdate(float now)
        {
            if (!Connected)
            {
                helloTimer -= Time.unscaledDeltaTime;
                bool canSend = !ViaRelay || (net.Relay != null && net.Relay.IsOpen);
                if (helloTimer <= 0f && canSend)
                {
                    helloTimer = 0.3f;
                    var w = new NetWriter(Msg.Hello).U32(token).U16(NetTransport.Protocol).Str(Application.version)
                        .Str(PlayerName).Str(GameSession.CarId).U8(GameSession.PaintIndex);
                    var b = w.Bytes; net.SendUnreliable(hostEp, b, b.Length);
                    // the wait counts from the first hello actually sent and needs several unanswered ones: a game that
                    // stalls for seconds (loading, compiling shaders on a slow GPU) mustn't give up before it has asked
                    if (hellosSent++ == 0) helloDeadline = now + 25f;
                }
                if (now > helloDeadline && (hellosSent == 0 || hellosSent >= 8))
                    Fail(!ViaRelay ? "No answer from the host. Check the code or address, and that the host's port is open."
                        : net.Relay != null && net.Relay.IsOpen ? "The host didn't answer. Ask them to check their game is still in the lobby."
                        : "The online service didn't answer. Check your internet connection and try again.");
                return;
            }
            var host = net.GetPeer(hostEp, false);
            if (host != null && now - host.lastHeard > Timeout) { Fail("Lost connection to the host."); return; }
            pingTimer -= Time.unscaledDeltaTime;
            if (pingTimer <= 0f)
            {
                pingTimer = 0.5f;
                var b = new NetWriter(Msg.Ping).F64(Now).U16(Local != null ? Local.ping : 0).Bytes;
                net.SendUnreliable(hostEp, b, b.Length);
            }
        }

        // ---------------------------------------------------------------- receive
        void OnForeign(IPEndPoint from, byte[] data, int len) { Stun.OnDatagram(from, data, len); }

        void OnMessage(IPEndPoint from, byte[] data)
        {
            NetReader r;
            try { r = new NetReader(data); } catch { return; }
            if (netLog && r.Type != Msg.CarState && r.Type != Msg.Ping && r.Type != Msg.Pong) Debug.Log($"[Net] <- {r.Type} from {from}");
            try { if (IsHost) HostReceive(from, r); else ClientReceive(from, r); }
            catch (Exception e) { Debug.LogWarning($"[Net] bad {r.Type} from {from}: {e.Message}"); }
        }

        NetPlayer ByEndpoint(IPEndPoint ep)
        {
            foreach (var p in Players) if (p.ep != null && p.ep.Equals(ep)) return p;
            return null;
        }

        void HostReceive(IPEndPoint from, NetReader r)
        {
            float now = Time.realtimeSinceStartup;
            var p = ByEndpoint(from);
            if (p != null) p.lastHeard = now;
            switch (r.Type)
            {
                case Msg.Discover:
                {
                    var b = new NetWriter(Msg.HostInfo).Str(Local?.name ?? "HOST").U8(Players.Count).U8(MaxPlayers).U8((int)phase)
                        .Str(TrackId).Str(Application.version).Bytes;
                    net.SendUnreliable(from, b, b.Length);
                    break;
                }
                case Msg.Hello:
                {
                    r.U32(); int proto = r.U16(); string ver = r.Str();
                    string name = r.Str(), car = r.Str(); int paint = r.U8();
                    if (p != null) { SendWelcome(p); break; }        // a resend: it missed our welcome
                    string why = proto != NetTransport.Protocol || ver != Application.version ? $"Version mismatch: the host has v{Application.version}, you have v{ver}."
                        : phase != Phase.Lobby ? "That race has already started. Try again when it's back in the lobby."
                        : Players.Count >= MaxPlayers ? "That game is full." : null;
                    if (why != null) { var rej = new NetWriter(Msg.Reject).Str(why).Bytes; net.SendUnreliable(from, rej, rej.Length); break; }
                    int id = 1;
                    while (Find(id) != null) id++;
                    p = new NetPlayer { id = id, name = Unique(name), carId = CarCatalog.Get(car).id, paint = paint, ep = from, lastHeard = now };
                    Players.Add(p);
                    Debug.Log($"[Net] {p.name} joined from {(NetTransport.IsRelay(from) ? "the online room" : from.ToString())}");
                    SendWelcome(p);
                    BroadcastLobby(true);
                    break;
                }
                case Msg.LobbyUpdate when p != null:
                    p.name = Unique(r.Str(), p); p.carId = CarCatalog.Get(r.Str()).id; p.paint = r.U8(); p.ready = r.Bool(); p.inLobby = r.Bool();
                    BroadcastLobby(true);
                    break;
                case Msg.Ping when p != null:
                {
                    double ct = r.F64(); p.ping = r.U16();
                    var b = new NetWriter(Msg.Pong).F64(ct).F64(HostTime).Bytes;
                    net.SendUnreliable(from, b, b.Length);
                    break;
                }
                case Msg.Loaded when p != null:
                    p.loaded = true;
                    break;
                case Msg.CarState when p != null:
                {
                    var s = CarSnapshot.Read(r);
                    if (s.id != p.id) break;
                    StoreState(p, s);
                    var raw = Relay(s);
                    foreach (var o in Players) if (o.ep != null && o != p) net.SendUnreliable(o.ep, raw, raw.Length);
                    break;
                }
                case Msg.Finish when p != null:
                    RecordFinish(p, r.F32());
                    break;
                case Msg.Leave when p != null:
                    DropPlayer(p, "left");
                    break;
            }
        }

        string Unique(string name, NetPlayer self = null)
        {
            name = string.IsNullOrWhiteSpace(name) ? "DRIVER" : name.Trim().ToUpperInvariant();
            if (name.Length > 16) name = name.Substring(0, 16);
            string n = name; int k = 2;
            bool Taken(string s) { foreach (var q in Players) if (q != self && q.name == s) return true; return false; }
            while (Taken(n)) n = name + " " + k++;
            return n;
        }

        void SendWelcome(NetPlayer p)
        {
            var b = new NetWriter(Msg.Welcome).U8(p.id).Str(p.name).Bytes;
            net.SendReliable(p.ep, b, b.Length);
        }

        void DropPlayer(NetPlayer p, string why)
        {
            Players.Remove(p);
            net.RemovePeer(p.ep);
            Grid.Remove(p.id);
            Status = $"{p.name} {why}.";
            PlayerLeft?.Invoke(p);
            BroadcastLobby(true);
            if (phase == Phase.Racing && !ResultsFinal) BroadcastResults();
            Changed?.Invoke();
        }

        void ClientReceive(IPEndPoint from, NetReader r)
        {
            if (!from.Equals(hostEp)) return;
            switch (r.Type)
            {
                case Msg.Welcome:
                    if (Connected) break;
                    LocalId = r.U8();
                    PlayerName = r.Str();
                    Connected = true;
                    phase = Phase.Lobby;
                    Status = "Connected.";
                    Debug.Log("[Net] joined as player " + LocalId);
                    SendLobbyUpdate();
                    Changed?.Invoke();
                    break;
                case Msg.Reject:
                    Fail(r.Str());
                    break;
                case Msg.Lobby:
                    ReadLobby(r);
                    break;
                case Msg.Pong:
                {
                    double sent = r.F64(), hostT = r.F64();
                    double now = Now;
                    float rtt = (float)(now - sent);
                    // keep the offset from the quickest exchanges (least queueing): best within 20% of the best seen
                    if (rtt < bestRtt * 1.2f || rtt < 0.03f)
                    {
                        double off = hostT + rtt * 0.5 - now;
                        clockOffset = bestRtt >= 999f ? off : clockOffset + (off - clockOffset) * 0.3;
                        bestRtt = Mathf.Min(bestRtt, rtt);
                    }
                    else bestRtt *= 1.01f;     // drift back up slowly if the link gets slower
                    if (Local != null) Local.ping = Mathf.RoundToInt(rtt * 1000f);
                    break;
                }
                case Msg.StartRace:
                    ReadStart(r);
                    break;
                case Msg.Go:
                    GoTime = r.F64();
                    phase = Phase.Countdown;
                    Changed?.Invoke();
                    break;
                case Msg.CarState:
                {
                    var s = CarSnapshot.Read(r);
                    var p = Find(s.id);
                    if (p != null && s.id != LocalId) StoreState(p, s);
                    break;
                }
                case Msg.Results:
                    ReadResults(r);
                    break;
                case Msg.ToLobby:
                    phase = Phase.Lobby;
                    foreach (var p in Players) { p.finished = false; p.loaded = false; p.hasState = false; }
                    Changed?.Invoke();
                    break;
                case Msg.Leave:
                    Fail("The host closed the game.");
                    break;
            }
        }

        static byte[] Relay(CarSnapshot s) { var w = new NetWriter(Msg.CarState); s.Write(w); return w.Bytes; }

        void StoreState(NetPlayer p, CarSnapshot s)
        {
            if (p.hasState && s.time <= p.state.time) return;     // out of order
            p.state = s; p.hasState = true; p.stateReceived = Time.realtimeSinceStartup;
        }

        // ---------------------------------------------------------------- lobby
        void BroadcastLobby(bool reliable)
        {
            if (!IsHost || net == null) return;
            var w = new NetWriter(Msg.Lobby).Str(TrackId).U8(Laps).U8((int)phase).U8(Players.Count);
            foreach (var p in Players) w.U8(p.id).Str(p.name).Str(p.carId).U8(p.paint).Bool(p.ready).Bool(p.inLobby).U16(Mathf.Clamp(p.ping, 0, 9999));
            var b = w.Bytes;
            foreach (var p in Players)
                if (p.ep != null) { if (reliable) net.SendReliable(p.ep, b, b.Length); else net.SendUnreliable(p.ep, b, b.Length); }
            Changed?.Invoke();
        }

        void ReadLobby(NetReader r)
        {
            TrackId = r.Str(); Laps = r.U8(); r.U8();
            int n = r.U8();
            var seen = new HashSet<int>();
            for (int i = 0; i < n; i++)
            {
                int id = r.U8();
                var p = Find(id);
                if (p == null) { p = new NetPlayer { id = id }; Players.Add(p); }
                p.name = r.Str(); p.carId = r.Str(); p.paint = r.U8(); p.ready = r.Bool(); p.inLobby = r.Bool();
                int ping = r.U16();
                if (id != LocalId) p.ping = ping;
                seen.Add(id);
            }
            for (int i = Players.Count - 1; i >= 0; i--)
                if (!seen.Contains(Players[i].id)) { var gone = Players[i]; Players.RemoveAt(i); PlayerLeft?.Invoke(gone); }
            Changed?.Invoke();
        }

        /// <summary>Send this player's lobby choices (name, car, paint, ready, whether they're in the lobby).</summary>
        public void SendLobbyUpdate()
        {
            var me = Local;
            if (me != null) { me.name = PlayerName; me.carId = GameSession.CarId; me.paint = GameSession.PaintIndex; }
            if (IsHost) { BroadcastLobby(true); return; }
            if (!Connected || me == null) return;
            var b = new NetWriter(Msg.LobbyUpdate).Str(PlayerName).Str(GameSession.CarId).U8(GameSession.PaintIndex).Bool(me.ready).Bool(me.inLobby).Bytes;
            net.SendReliable(hostEp, b, b.Length);
        }

        public void SetReady(bool ready) { var me = Local; if (me == null) return; me.ready = ready; SendLobbyUpdate(); }

        /// <summary>Host: choose the track (resets laps to the track's default).</summary>
        public void SetTrack(string id) { if (!IsHost) return; TrackId = id; Laps = TrackCatalog.Get(id).laps; BroadcastLobby(true); }
        public void SetLaps(int laps) { if (!IsHost) return; Laps = Mathf.Clamp(laps, 1, 9); BroadcastLobby(true); }

        public bool CanStart(out string why)
        {
            why = null;
            if (!IsHost) { why = "Waiting for the host to start."; return false; }
            foreach (var p in Players) if (!p.inLobby) { why = p.name + " is still on the results screen."; return false; }
            return true;
        }

        // ---------------------------------------------------------------- race
        /// <summary>Host: start the race for everyone in the lobby.</summary>
        public void StartRace()
        {
            if (!IsHost || !CanStart(out _)) return;
            Grid.Clear();
            // the host starts at the back; everyone else in join order
            foreach (var p in Players) if (p.id != LocalId) Grid.Add(p.id);
            Grid.Add(LocalId);
            var w = new NetWriter(Msg.StartRace).Str(TrackId).U8(Laps).U8(Grid.Count);
            foreach (int id in Grid) w.U8(id);
            var b = w.Bytes;
            foreach (var p in Players) if (p.ep != null) net.SendReliable(p.ep, b, b.Length);
            BeginLoading();
        }

        void ReadStart(NetReader r)
        {
            TrackId = r.Str(); Laps = r.U8();
            int n = r.U8();
            Grid.Clear();
            for (int i = 0; i < n; i++) Grid.Add(r.U8());
            BeginLoading();
        }

        void BeginLoading()
        {
            phase = Phase.Loading;
            Standings.Clear(); ResultsFinal = false; firstFinish = -1f;
            foreach (var p in Players) { p.loaded = false; p.finished = false; p.finishTime = 0f; p.hasState = false; p.inLobby = false; }
            loadDeadline = Time.realtimeSinceStartup + 40f;
            GameSession.TrackId = TrackId;
            GameSession.Mode = GameMode.Battle;
            Changed?.Invoke();
            var track = TrackCatalog.Get(TrackId);
            Debug.Log("[Net] loading " + track.scene);
            SceneManager.LoadScene(track.scene);
        }

        /// <summary>The race scene is ready (called by RaceBootstrap).</summary>
        public void LocalLoaded()
        {
            var me = Local;
            if (me != null) me.loaded = true;
            if (!IsHost) { var b = new NetWriter(Msg.Loaded).Bytes; net.SendReliable(hostEp, b, b.Length); }
        }

        bool AllLoaded() { foreach (var p in Players) if (!p.loaded) return false; return true; }

        void SendGo()
        {
            // green light 4.5 s from now: time for the Go message to arrive and everyone's countdown
            GoTime = HostTime + 4.5;
            phase = Phase.Countdown;
            var b = new NetWriter(Msg.Go).F64(GoTime).Bytes;
            foreach (var p in Players) if (p.ep != null) net.SendReliable(p.ep, b, b.Length);
            Debug.Log("[Net] go at host time " + GoTime.ToString("0.00"));
            Changed?.Invoke();
        }

        /// <summary>The race is on (RaceManager at the green light).</summary>
        public void RaceStarted() { if (phase == Phase.Countdown) phase = Phase.Racing; }

        /// <summary>Send this car's state (owner -> host -> others).</summary>
        public void SendState(CarSnapshot s)
        {
            if (net == null || !Connected) return;
            s.id = LocalId; s.time = HostTime;
            var me = Local; if (me != null) { me.state = s; me.hasState = true; }
            var b = Relay(s);
            if (IsHost) { foreach (var p in Players) if (p.ep != null) net.SendUnreliable(p.ep, b, b.Length); }
            else net.SendUnreliable(hostEp, b, b.Length);
        }

        /// <summary>This player crossed the line.</summary>
        public void LocalFinished(float raceTime)
        {
            var me = Local;
            if (me == null || me.finished) return;
            if (IsHost) RecordFinish(me, raceTime);
            else { me.finished = true; me.finishTime = raceTime; var b = new NetWriter(Msg.Finish).F32(raceTime).Bytes; net.SendReliable(hostEp, b, b.Length); }
        }

        void RecordFinish(NetPlayer p, float time)
        {
            if (p.finished) return;
            p.finished = true; p.finishTime = time;
            if (firstFinish < 0f) firstFinish = Time.realtimeSinceStartup;
            BroadcastResults();
        }

        void BroadcastResults()
        {
            BuildStandings();
            var w = new NetWriter(Msg.Results).Bool(ResultsFinal).U8(Standings.Count);
            foreach (var s in Standings) w.U8(s.id).F32(s.time);
            var b = w.Bytes;
            foreach (var p in Players) if (p.ep != null) net.SendReliable(p.ep, b, b.Length);
            if (ResultsFinal) phase = Phase.Results;
            Changed?.Invoke();
        }

        void BuildStandings()
        {
            Standings.Clear();
            var fin = new List<NetPlayer>(); var rest = new List<NetPlayer>();
            foreach (var p in Players) (p.finished ? fin : rest).Add(p);
            fin.Sort((a, b) => a.finishTime.CompareTo(b.finishTime));
            rest.Sort((a, b) => (b.hasState ? b.state.progress : 0f).CompareTo(a.hasState ? a.state.progress : 0f));
            foreach (var p in fin) Standings.Add((p.id, p.finishTime));
            foreach (var p in rest) Standings.Add((p.id, -1f));
        }

        void ReadResults(NetReader r)
        {
            ResultsFinal = r.Bool();
            int n = r.U8();
            Standings.Clear();
            for (int i = 0; i < n; i++)
            {
                int id = r.U8(); float t = r.F32();
                Standings.Add((id, t));
                var p = Find(id); if (p != null && t >= 0f) { p.finished = true; p.finishTime = t; }
            }
            if (ResultsFinal) phase = Phase.Results;
            Changed?.Invoke();
        }

        /// <summary>Back to the lobby after a race (host takes everyone; a client just goes back itself).</summary>
        public void ReturnToLobby()
        {
            var me = Local;
            if (me != null) { me.inLobby = true; me.ready = IsHost; }
            if (IsHost)
            {
                phase = Phase.Lobby;
                foreach (var p in Players) { p.finished = false; p.loaded = false; p.hasState = false; }
                var b = new NetWriter(Msg.ToLobby).Bytes;
                foreach (var p in Players) if (p.ep != null) net.SendReliable(p.ep, b, b.Length);
                BroadcastLobby(true);
            }
            else SendLobbyUpdate();
            SceneManager.LoadScene("MainMenu");
        }

        // ---------------------------------------------------------------- dev automation
        /// <summary>
        /// -mpHost / -mpJoin addr|code|@file [-mpName n] [-mpAutoStart players] [-mpTrack id] [-mpLaps n] [-mpCodeFile path]:
        /// scripted sessions for tests (-relay url picks the relay, -noRelay hosts without it).
        /// </summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void DevAuto()
        {
            if (!CommandLine.Has("-mpHost") && !CommandLine.Has("-mpJoin")) return;
            var go = new GameObject("NetDev"); DontDestroyOnLoad(go);
            go.AddComponent<NetDev>();
        }

        class NetDev : MonoBehaviour
        {
            System.Collections.IEnumerator Start()
            {
                yield return new WaitForSecondsRealtime(1.5f);
                if (CommandLine.Has("-mpName")) PlayerName = CommandLine.Get("-mpName");
                if (CommandLine.Has("-car")) GameSession.CarId = CommandLine.Get("-car");
                if (CommandLine.Has("-mpHost"))
                {
                    var s = Host();
                    if (CommandLine.Has("-mpTrack")) s.SetTrack(CommandLine.Get("-mpTrack"));
                    if (CommandLine.Has("-mpLaps")) s.SetLaps((int)CommandLine.GetFloat("-mpLaps", 1));
                    int want = (int)CommandLine.GetFloat("-mpAutoStart", 0);
                    if (want > 0)
                    {
                        float deadline = Time.realtimeSinceStartup + 120f;
                        while (I != null && I.Players.Count < want && Time.realtimeSinceStartup < deadline) yield return null;
                        yield return new WaitForSecondsRealtime(1f);
                        I?.StartRace();
                    }
                }
                else
                {
                    // -mpJoin @file: wait for the host's -mpCodeFile and join that room
                    string target = CommandLine.Get("-mpJoin");
                    if (target.StartsWith("@"))
                    {
                        string path = target.Substring(1);
                        float deadline = Time.realtimeSinceStartup + 120f;
                        while (!System.IO.File.Exists(path) && Time.realtimeSinceStartup < deadline) yield return new WaitForSecondsRealtime(0.5f);
                        target = System.IO.File.Exists(path) ? System.IO.File.ReadAllText(path).Trim() : "";
                        Debug.Log("[Net] dev join: room " + target);
                    }
                    Join(target);
                }
            }
        }
    }
}
