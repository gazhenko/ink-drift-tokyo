using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>
    /// Turtle-defined closed circuit ("S len", "R/L angle radius"), solved for closure (two straights flagged adjA/adjB),
    /// resampled at uniform spacing, with elevation from a keyframe profile. Mirrors Tools/tracks/layout.py.
    /// </summary>
    public class TrackLayout
    {
        public struct Seg { public char kind; public float a, r; public string flag; }

        public readonly List<Vector3> pts = new List<Vector3>();      // y = elevation
        public readonly List<Vector3> tan = new List<Vector3>();
        public readonly List<Vector3> right = new List<Vector3>();
        public readonly List<float> dist = new List<float>();
        public readonly List<float> curvature = new List<float>();    // signed 1/m, + = right turn
        public readonly List<float> bank = new List<float>();         // degrees
        public float length;
        public float spacing;
        public List<Seg> segments;
        public float[] segStart;      // distance where each segment begins
        public float[] segEnd;

        public static List<Seg> Load(string id)
        {
            string path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../Tools/tracks/layouts.json"));
            string json = File.ReadAllText(path);
            // tiny parser for {"id": [["S",240,"adjA"],["R",90,16], ...], ...}
            int k = json.IndexOf("\"" + id + "\"", StringComparison.Ordinal);
            if (k < 0) throw new Exception("layout not found " + id);
            int start = json.IndexOf('[', k);
            int depth = 0, end = start;
            for (int i = start; i < json.Length; i++)
            {
                if (json[i] == '[') depth++;
                else if (json[i] == ']') { depth--; if (depth == 0) { end = i; break; } }
            }
            string body = json.Substring(start + 1, end - start - 1);
            var segs = new List<Seg>();
            int p = 0;
            while (true)
            {
                int a = body.IndexOf('[', p);
                if (a < 0) break;
                int b = body.IndexOf(']', a);
                var parts = body.Substring(a + 1, b - a - 1).Split(',');
                var s = new Seg { kind = parts[0].Trim().Trim('"')[0], a = float.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture) };
                if (s.kind == 'S') s.flag = parts.Length > 2 ? parts[2].Trim().Trim('"') : null;
                else s.r = float.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);
                segs.Add(s);
                p = b + 1;
            }
            return segs;
        }

        static List<Vector2> Walk(List<Seg> segs, Dictionary<int, float> overrides, float step = 1f)
        {
            var o = new List<Vector2>();
            double x = 0, z = 0, h = 0;
            o.Add(Vector2.zero);
            for (int i = 0; i < segs.Count; i++)
            {
                var s = segs[i];
                if (s.kind == 'S')
                {
                    double L = overrides != null && overrides.TryGetValue(i, out var ov) ? ov : s.a;
                    int n = Math.Max(1, (int)(L / step));
                    for (int k = 0; k < n; k++)
                    {
                        x += Math.Sin(h * Math.PI / 180) * L / n;
                        z += Math.Cos(h * Math.PI / 180) * L / n;
                        o.Add(new Vector2((float)x, (float)z));
                    }
                }
                else
                {
                    double ang = s.a * (s.kind == 'R' ? 1 : -1);
                    double arc = Math.Abs(ang * Math.PI / 180) * s.r;
                    int n = Math.Max(2, (int)(arc / step));
                    for (int k = 0; k < n; k++)
                    {
                        h += ang / n;
                        double mid = h - ang / n / 2;
                        x += Math.Sin(mid * Math.PI / 180) * arc / n;
                        z += Math.Cos(mid * Math.PI / 180) * arc / n;
                        o.Add(new Vector2((float)x, (float)z));
                    }
                }
            }
            return o;
        }

        public static List<Vector2> Solve(List<Seg> segs) => Solve(segs, out _);

        public static List<Vector2> Solve(List<Seg> segs, out float[] segLengths)
        {
            int ia = segs.FindIndex(s => s.kind == 'S' && s.flag == "adjA");
            int ib = segs.FindIndex(s => s.kind == 'S' && s.flag == "adjB");
            double la = segs[ia].a, lb = segs[ib].a;
            Vector2 End(double a, double b) { var w = Walk(segs, new Dictionary<int, float> { { ia, (float)a }, { ib, (float)b } }, 2f); return w[w.Count - 1]; }
            for (int it = 0; it < 30; it++)
            {
                var e = End(la, lb);
                if (e.magnitude < 0.01f) break;
                var ea = End(la + 1, lb) - e;
                var eb = End(la, lb + 1) - e;
                double det = ea.x * eb.y - eb.x * ea.y;
                double da = (-e.x * eb.y + eb.x * e.y) / det;
                double db = (-ea.x * e.y + e.x * ea.y) / det;
                la += da; lb += db;
            }
            segLengths = new float[segs.Count];
            for (int i = 0; i < segs.Count; i++)
                segLengths[i] = segs[i].kind == 'S' ? (i == ia ? (float)la : i == ib ? (float)lb : segs[i].a) : Mathf.Abs(segs[i].a) * Mathf.Deg2Rad * segs[i].r;
            var final = Walk(segs, new Dictionary<int, float> { { ia, (float)la }, { ib, (float)lb } }, 0.5f);
            // distribute any residual closure error
            Vector2 err = final[final.Count - 1];
            for (int i = 0; i < final.Count; i++) final[i] -= err * (i / (float)(final.Count - 1));
            final.RemoveAt(final.Count - 1);
            return final;
        }

        /// <param name="elev">elevation keyframes: (fraction 0..1, height m), looped</param>
        public static TrackLayout Build(string id, float spacing, Vector2[] elev, float bankPerCurv = 0f, float maxBank = 0f)
        {
            var segs = Load(id);
            var raw = Solve(segs, out var segLen);
            var t = new TrackLayout { spacing = spacing, segments = segs };
            // arc-length param of raw
            var cum = new List<float> { 0f };
            for (int i = 1; i <= raw.Count; i++) cum.Add(cum[i - 1] + Vector2.Distance(raw[i - 1], raw[i % raw.Count]));
            float total = cum[cum.Count - 1];
            int n = Mathf.RoundToInt(total / spacing);
            float ds = total / n;
            int j = 0;
            var p2 = new List<Vector2>();
            for (int i = 0; i < n; i++)
            {
                float d = i * ds;
                while (j < raw.Count - 1 && cum[j + 1] < d) j++;
                float u = Mathf.InverseLerp(cum[j], cum[j + 1], d);
                p2.Add(Vector2.Lerp(raw[j], raw[(j + 1) % raw.Count], u));
            }
            // smooth tiny kinks (1 pass)
            var sm = new List<Vector2>(p2);
            for (int i = 0; i < n; i++) sm[i] = (p2[(i - 1 + n) % n] + p2[i] * 2f + p2[(i + 1) % n]) * 0.25f;

            t.length = total;
            float sumLen = 0f; foreach (var l in segLen) sumLen += l;
            t.segStart = new float[segs.Count]; t.segEnd = new float[segs.Count];
            float acc = 0f;
            for (int i = 0; i < segs.Count; i++) { t.segStart[i] = acc * total / sumLen; acc += segLen[i]; t.segEnd[i] = acc * total / sumLen; }
            for (int i = 0; i < n; i++)
            {
                float d = i * ds;
                float y = SampleElev(elev, d / total);
                t.pts.Add(new Vector3(sm[i].x, y, sm[i].y));
                t.dist.Add(d);
            }
            for (int i = 0; i < n; i++)
            {
                Vector3 a = t.pts[(i - 1 + n) % n], b = t.pts[(i + 1) % n];
                Vector3 tg = (b - a).normalized;
                t.tan.Add(tg);
                Vector3 flat = new Vector3(tg.x, 0, tg.z).normalized;
                t.right.Add(Vector3.Cross(Vector3.up, flat).normalized);
            }
            for (int i = 0; i < n; i++)
            {
                Vector3 t0 = t.tan[(i - 2 + n) % n], t1 = t.tan[(i + 2) % n];
                float ang = Vector3.SignedAngle(new Vector3(t0.x, 0, t0.z), new Vector3(t1.x, 0, t1.z), Vector3.up) * Mathf.Deg2Rad;
                t.curvature.Add(ang / (4f * ds));
            }
            // banking from smoothed curvature
            for (int i = 0; i < n; i++)
            {
                float c = 0; int w = 6;
                for (int k = -w; k <= w; k++) c += t.curvature[(i + k + n) % n];
                c /= (2 * w + 1);
                t.bank.Add(Mathf.Clamp(c * bankPerCurv, -maxBank, maxBank));
            }
            return t;
        }

        static float SampleElev(Vector2[] k, float f)
        {
            if (k == null || k.Length == 0) return 0f;
            if (k.Length == 1) return k[0].y;
            for (int i = 0; i < k.Length; i++)
            {
                var a = k[i];
                var b = i + 1 < k.Length ? k[i + 1] : new Vector2(k[0].x + 1f, k[0].y);
                if (f >= a.x && f <= b.x)
                {
                    float u = Mathf.InverseLerp(a.x, b.x, f);
                    return Mathf.Lerp(a.y, b.y, Mathf.SmoothStep(0f, 1f, u));
                }
            }
            // before first key: wrap from last
            var last = k[k.Length - 1];
            float uu = Mathf.InverseLerp(last.x - 1f, k[0].x, f);
            return Mathf.Lerp(last.y, k[0].y, Mathf.SmoothStep(0f, 1f, uu));
        }

        public int Count => pts.Count;
        public int Wrap(int i) => ((i % Count) + Count) % Count;
        public float DistAtIndex(int i) => dist[Wrap(i)];
        public int IndexAt(float d) => Wrap(Mathf.RoundToInt(Mathf.Repeat(d, length) / (length / Count)));

        /// <summary>Banked right vector at sample i.</summary>
        public Vector3 BankedRight(int i)
        {
            return Quaternion.AngleAxis(-bank[Wrap(i)], tan[Wrap(i)]) * right[Wrap(i)];
        }
        public Vector3 BankedUp(int i) => Vector3.Cross(tan[Wrap(i)], BankedRight(i)).normalized;
    }
}
