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
    /// (message round trips, invite codes, and reliable ordered delivery between two real sockets with packet loss).
    /// </summary>
    public static class NetSelfTest
    {
        static int pass, fail;

        static void Check(bool ok, string what)
        {
            if (ok) pass++; else fail++;
            Debug.Log($"[NetTest] {(ok ? "PASS" : "FAIL")} {what}");
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

            Debug.Log($"[NetTest] {pass} passed, {fail} failed");
            if (Application.isBatchMode) EditorApplication.Exit(fail == 0 ? 0 : 1);
        }
    }
}
