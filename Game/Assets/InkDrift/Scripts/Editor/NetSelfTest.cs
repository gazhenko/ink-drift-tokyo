using System.Collections.Generic;
using System.Net;
using System.Threading;
using InkDrift.Net;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>
    /// Headless checks for the multiplayer layer: -executeMethod InkDrift.EditorTools.NetSelfTest.Run
    /// (message round trips, invite and room codes, reliable ordered delivery between two real sockets with packet loss,
    /// and a host and guest talking through the online relay).
    /// </summary>
    public static class NetSelfTest
    {
        static int pass, fail;

        static void Check(bool ok, string what)
        {
            if (ok) pass++; else fail++;
            Debug.Log($"[NetTest] {(ok ? "PASS" : "FAIL")} {what}");
        }

        /// <summary>Host and guest transports talking through the real relay (or -relay url): room code, reliable order, leaving.</summary>
        static void RelayRoundTrip()
        {
            var h = new NetTransport(0); var g = new NetTransport(0);
            var hostLink = RelayLink.Host();
            h.AttachRelay(hostLink);
            var clock = System.Diagnostics.Stopwatch.StartNew();
            bool Wait(System.Func<bool> done, int ms)
            {
                var until = clock.ElapsedMilliseconds + ms;
                while (!done() && clock.ElapsedMilliseconds < until) { Thread.Sleep(5); h.Poll(); g.Poll(); }
                return done();
            }
            var hostEvents = new List<RelayLink.Event>();
            void Drain(RelayLink l, List<RelayLink.Event> into) { while (l.Events.TryDequeue(out var e)) into.Add(e); }
            bool open = Wait(() => { Drain(hostLink, hostEvents); return hostLink.IsOpen || hostEvents.Exists(e => e.kind == RelayLink.EventKind.Error); }, 15000);
            Check(open && hostLink.IsOpen && hostLink.LocalId == 0, $"relay gives the host a room code ({RelayLink.Format(hostLink.RoomCode)}) via {RelayLink.Url} in {clock.ElapsedMilliseconds} ms"
                  + (hostEvents.Exists(e => e.kind == RelayLink.EventKind.Error) ? ": " + hostEvents.Find(e => e.kind == RelayLink.EventKind.Error).text : ""));
            if (!hostLink.IsOpen) { h.Dispose(); g.Dispose(); return; }

            var guestLink = RelayLink.Join(hostLink.RoomCode.ToLowerInvariant());
            g.AttachRelay(guestLink);
            var guestEvents = new List<RelayLink.Event>();
            Wait(() => guestLink.IsOpen, 10000);
            Check(guestLink.IsOpen && guestLink.LocalId > 0, $"guest joins the room as peer {guestLink.LocalId}");
            Check(Wait(() => { Drain(hostLink, hostEvents); return hostEvents.Exists(e => e.kind == RelayLink.EventKind.Joined && e.id == guestLink.LocalId); }, 5000), "host hears the guest join");

            var gotH = new List<int>(); var gotG = new List<int>();
            h.OnMessage += (from, data) => { var rr = new NetReader(data); if (rr.Type == Msg.Results && from.Equals(NetTransport.RelayEndpoint(guestLink.LocalId))) gotH.Add(rr.I32()); };
            g.OnMessage += (from, data) => { var rr = new NetReader(data); if (rr.Type == Msg.Results && from.Equals(NetTransport.RelayEndpoint(0))) gotG.Add(rr.I32()); };
            const int N = 300;
            var t0 = clock.ElapsedMilliseconds;
            for (int i = 0; i < N; i++)
            {
                var m = new NetWriter(Msg.Results).I32(i).Bytes;
                g.SendReliable(NetTransport.RelayEndpoint(0), m, m.Length);
                h.SendReliable(NetTransport.RelayEndpoint(guestLink.LocalId), m, m.Length);
            }
            Wait(() => gotH.Count >= N && gotG.Count >= N, 15000);
            bool inOrder = true;
            for (int i = 0; i < gotH.Count; i++) if (gotH[i] != i) inOrder = false;
            for (int i = 0; i < gotG.Count; i++) if (gotG[i] != i) inOrder = false;
            Check(gotH.Count == N && gotG.Count == N && inOrder, $"reliable traffic both ways through the relay ({gotH.Count}/{N}, {gotG.Count}/{N} in order, {clock.ElapsedMilliseconds - t0} ms, {guestLink.FramesOut} frames for {N} packets)");

            g.Dispose();
            Check(Wait(() => { Drain(hostLink, hostEvents); return hostEvents.Exists(e => e.kind == RelayLink.EventKind.Left && e.id == guestLink.LocalId); }, 8000), "host hears the guest leave");

            var lost = RelayLink.Join("ZZZZZZ");
            var lostEvents = new List<RelayLink.Event>();
            Wait(() => { Drain(lost, lostEvents); return lostEvents.Exists(e => e.kind == RelayLink.EventKind.Error); }, 10000);
            var err = lostEvents.Find(e => e.kind == RelayLink.EventKind.Error);
            Check(err.text != null && err.text.Contains("No game found"), "joining an unknown room explains why: " + err.text);
            lost.Dispose();
            h.Dispose();
        }

        public static void Run()
        {
            pass = fail = 0;
            // ---- invite codes
            foreach (var (ip, port) in new[] { ("192.168.1.20", 7777), ("203.0.113.254", 7786), ("10.0.0.1", 7777), ("255.255.255.255", 8032) })
            {
                string code = InviteCodec.Encode(IPAddress.Parse(ip), port);
                bool ok = InviteCodec.TryDecode(code, out var ep) && ep.Address.ToString() == ip && ep.Port == port;
                Check(ok, $"invite {ip}:{port} -> {code}");
                Check(InviteCodec.TryDecode(code.ToLowerInvariant().Replace("-", " "), out var ep2) && ep2.Equals(ep), "invite code is case/separator tolerant");
            }
            Check(!InviteCodec.TryDecode("hello", out _), "garbage is not an invite code");

            // ---- car snapshot round trip
            var s = new CarSnapshot { id = 3, time = 1234.5678, pos = new Vector3(1, 2, 3), rot = Quaternion.Euler(10, 20, 30), vel = new Vector3(-4, 5, 6),
                                      angVel = new Vector3(0.1f, 0.2f, 0.3f), steer = -0.5f, throttle = 0.75f, brake = 0.2f, handbrake = true, finished = true,
                                      gear = -1, progress = 4321.5f, lap = 2, resetCount = 7 };
            var w = new NetWriter(Msg.CarState); s.Write(w);
            var r = new NetReader(w.Bytes);
            var t = CarSnapshot.Read(r);
            Check(r.Type == Msg.CarState && t.id == 3 && t.time == s.time && t.pos == s.pos && Quaternion.Angle(t.rot, s.rot) < 0.01f && t.vel == s.vel
                  && Mathf.Abs(t.steer + 0.5f) < 0.01f && Mathf.Abs(t.throttle - 0.75f) < 0.01f && t.handbrake && t.finished && t.gear == -1
                  && t.progress == s.progress && t.lap == 2 && t.resetCount == 7, "car snapshot round trip");
            var sw = new NetWriter(Msg.Lobby).Str("渋谷ネオン · DRIVER").U8(200).F64(-1.5);
            var sr = new NetReader(sw.Bytes);
            Check(sr.Str() == "渋谷ネオン · DRIVER" && sr.U8() == 200 && sr.F64() == -1.5, "strings and numbers round trip (UTF-8)");

            // ---- reliable ordered delivery with 30% loss, both directions
            var a = new NetTransport(0); var b = new NetTransport(0);
            var aEp = new IPEndPoint(IPAddress.Loopback, a.LocalPort); var bEp = new IPEndPoint(IPAddress.Loopback, b.LocalPort);
            var gotB = new List<int>(); var gotA = new List<int>();
            b.OnMessage += (from, data) => { var rr = new NetReader(data); if (rr.Type == Msg.Results) gotB.Add(rr.I32()); };
            a.OnMessage += (from, data) => { var rr = new NetReader(data); if (rr.Type == Msg.Results) gotA.Add(rr.I32()); };
            NetTransport.TestDropRate = 0.3f;
            const int N = 200;
            for (int i = 0; i < N; i++)
            {
                var m = new NetWriter(Msg.Results).I32(i).Bytes;
                a.SendReliable(bEp, m, m.Length);
                b.SendReliable(aEp, m, m.Length);
            }
            var start = System.Diagnostics.Stopwatch.StartNew();
            while ((gotA.Count < N || gotB.Count < N) && start.ElapsedMilliseconds < 20000)
            {
                Thread.Sleep(5);
                a.Poll(); b.Poll();
            }
            NetTransport.TestDropRate = 0f;
            bool ordered = true;
            for (int i = 0; i < gotB.Count; i++) if (gotB[i] != i) ordered = false;
            for (int i = 0; i < gotA.Count; i++) if (gotA[i] != i) ordered = false;
            Check(gotA.Count == N && gotB.Count == N, $"reliable delivery under 30% loss ({gotB.Count}/{N} and {gotA.Count}/{N} in {start.ElapsedMilliseconds} ms)");
            Check(ordered, "reliable delivery is in order and without duplicates");
            a.Dispose(); b.Dispose();

            // ---- room codes and relay endpoints
            Check(RelayLink.TryParseCode(" k7q-4mz ", out var rc) && rc == "K7Q4MZ" && RelayLink.Format(rc) == "K7Q-4MZ", "room code is case/separator tolerant");
            Check(!RelayLink.TryParseCode("192.168.1.20", out _) && !RelayLink.TryParseCode("INK-ABCD-EFGH", out _) && !RelayLink.TryParseCode("K7Q-4M0", out _)
                  && !RelayLink.TryParseCode("laptop:7777", out _), "addresses and invite codes aren't room codes");
            var rep = NetTransport.RelayEndpoint(5);
            Check(NetTransport.IsRelay(rep) && rep.Equals(NetTransport.RelayEndpoint(5)) && !NetTransport.IsRelay(new IPEndPoint(IPAddress.Parse("10.0.1.5"), 0))
                  && !NetTransport.IsRelay(new IPEndPoint(IPAddress.Loopback, 7777)), "relay stand-in endpoints");

            RelayRoundTrip();

            Debug.Log($"[NetTest] {pass} passed, {fail} failed");
            if (Application.isBatchMode) EditorApplication.Exit(fail == 0 ? 0 : 1);
        }
    }
}
