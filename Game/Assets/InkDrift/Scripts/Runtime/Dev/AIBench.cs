using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Dev: lap-time benchmark for the CPU drivers. -aiBench [laps] runs a Battle with every car (the player's too)
    /// on AI, logs "[AIBench]" lines with each car's lap times and quits when the leader has done that many laps.
    /// Combine with -scene, -car, -rivals n, -timeScale k (faster than real time) and -aiLegacy (the pre-1.29 AI).
    /// </summary>
    public class AIBench : MonoBehaviour
    {
        class Entry { public CarController car; public AIDriver ai; public int lap; public float lapStart; public readonly List<float> laps = new List<float>(); public float bestLap = float.MaxValue; }

        readonly List<Entry> entries = new List<Entry>();
        int lapsWanted;
        float t0;
        bool started;

        public static bool Active => CommandLine.Has("-aiBench");

        void Start()
        {
            lapsWanted = Mathf.Max(1, (int)CommandLine.GetFloat("-aiBench", 3));
            float ts = CommandLine.GetFloat("-timeScale", 1f);
            if (ts > 0.1f) Time.timeScale = ts;
            Debug.Log($"[AIBench] start laps={lapsWanted} timeScale={Time.timeScale} legacy={AIDriver.Legacy} difficulty={GameSession.Difficulty}");
        }

        void Update()
        {
            var rb = RaceBootstrap.I;
            var race = RaceManager.I;
            var path = TrackPath.Active;
            if (rb == null || race == null || path == null) return;
            if (!started)
            {
                if (race.state != RaceManager.State.Racing) return;
                started = true;
                t0 = Time.time;
                var cars = new List<CarController> { rb.Player };
                cars.AddRange(rb.Rivals);
                foreach (var c in cars)
                {
                    if (c == null) continue;
                    var ai = c.GetComponent<AIDriver>();
                    if (ai == null) continue;
                    entries.Add(new Entry { car = c, ai = ai, lapStart = Time.time });
                }
                return;
            }
            float L = path.length;
            int leader = 0;
            foreach (var e in entries)
            {
                if (e.car == null) continue;
                // laps counted from the start line (the AI's progress starts behind it on the grid)
                int lap = Mathf.FloorToInt((e.ai.Progress - path.startDistance) / L + 1f);
                if (lap > e.lap)
                {
                    if (e.lap >= 1)
                    {
                        float lt = Time.time - e.lapStart;
                        e.laps.Add(lt);
                        e.bestLap = Mathf.Min(e.bestLap, lt);
                        Debug.Log($"[AIBench] {e.car.name} lap {e.lap} {lt:0.000}s");
                    }
                    e.lap = lap;
                    e.lapStart = Time.time;
                }
                leader = Mathf.Max(leader, e.laps.Count);
            }
            if (leader >= lapsWanted || Time.time - t0 > 60f * 12f) Report();
        }

        void Report()
        {
            var sb = new StringBuilder();
            float sumBest = 0f; int n = 0;
            foreach (var e in entries)
            {
                if (e.car == null) continue;
                sb.Append($"[AIBench] RESULT {e.car.name} resets={e.ai.Resets} laps={e.laps.Count} best={(e.laps.Count > 0 ? e.bestLap : 0f):0.000}");
                foreach (var l in e.laps) sb.Append($" {l:0.000}");
                sb.AppendLine();
                if (e.laps.Count > 0) { sumBest += e.bestLap; n++; }
            }
            sb.Append($"[AIBench] MEAN_BEST {(n > 0 ? sumBest / n : 0f):0.000} cars={n} track={GameSession.TrackId}");
            Debug.Log(sb.ToString());
            Application.Quit();
            enabled = false;
        }
    }
}
