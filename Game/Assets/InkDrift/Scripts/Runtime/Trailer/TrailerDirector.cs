using System.Collections;
using System.Collections.Generic;
using System.IO;
using Unity.Collections;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Cinematic capture mode: `-trailer -capture &lt;dir&gt; [-shots chase:6,lowside:5,...] [-fps 60] [-car kaiju] [-slowmo]`.
    /// Spawns a hero + wingmen drifting under AI, runs a shot list with cinematic camera rigs and writes
    /// frames (fixed timestep) + game audio (AudioRenderer) + a JSON log of callouts per shot.
    /// </summary>
    public class TrailerDirector : MonoBehaviour
    {
        public static bool Requested => CommandLine.Has("-trailer");

        public enum Rig { Chase, LowSide, Front, Orbit, Flyby, Heli, Wheel, Hood, Scenic, Pack }

        class Shot { public Rig rig; public float duration; public float slowmo = 1f; public float side = 1f; }

        Camera cam;
        CarController hero;
        readonly List<CarController> pack = new List<CarController>();
        DriftScorer scorer;
        string outDir;
        int fps;
        int frame;
        float shotTime;
        Vector3 flybyPos;
        Vector3 camVel;
        readonly List<string> log = new List<string>();
        int currentShot;
        bool forceCallouts;
        int escalate;
        static readonly CalloutId[] Escalation = { CalloutId.Nice, CalloutId.Good, CalloutId.Great, CalloutId.Awesome, CalloutId.Insane, CalloutId.Perfect, CalloutId.God, CalloutId.Ikee, CalloutId.NearMiss, CalloutId.DriftKing };

        void Start() { StartCoroutine(Run()); }

        List<Shot> ParseShots()
        {
            var list = new List<Shot>();
            string spec = CommandLine.Get("-shots", "chase:6,lowside:5,front:4,orbit:5,flyby:4,wheel:4,heli:4,pack:6,scenic:5");
            foreach (var part in spec.Split(','))
            {
                var kv = part.Split(':');
                if (kv.Length < 2) continue;
                var s = new Shot { duration = float.Parse(kv[1], System.Globalization.CultureInfo.InvariantCulture) };
                string r = kv[0].ToLowerInvariant();
                if (r.EndsWith("_slow")) { s.slowmo = 0.35f; r = r.Replace("_slow", ""); }
                if (r.EndsWith("_l")) { s.side = -1f; r = r.Replace("_l", ""); }
                s.rig = r switch
                {
                    "lowside" => Rig.LowSide, "front" => Rig.Front, "orbit" => Rig.Orbit, "flyby" => Rig.Flyby, "heli" => Rig.Heli,
                    "wheel" => Rig.Wheel, "hood" => Rig.Hood, "scenic" => Rig.Scenic, "pack" => Rig.Pack, _ => Rig.Chase
                };
                list.Add(s);
            }
            return list;
        }

        IEnumerator Run()
        {
            fps = (int)CommandLine.GetFloat("-fps", 60);
            forceCallouts = CommandLine.Has("-forceCallouts");
            escalate = (int)CommandLine.GetFloat("-calloutStart", 0);
            outDir = CommandLine.Get("-capture", Path.Combine(Application.persistentDataPath, "trailer"));
            Directory.CreateDirectory(outDir);
            int w = (int)CommandLine.GetFloat("-w", 1920), h = (int)CommandLine.GetFloat("-h", 1080);
            Screen.SetResolution(w, h, FullScreenMode.Windowed);
            Application.targetFrameRate = -1;
            QualitySettings.vSyncCount = 0;
            yield return null; yield return null;

            var path = TrackPath.Active;
            var bootstrap = RaceBootstrap.I;
            cam = bootstrap != null && bootstrap.mainCamera != null ? bootstrap.mainCamera : Camera.main;
            if (FindAnyObjectByType<Skidmarks>() == null) new GameObject("Skidmarks", typeof(MeshFilter), typeof(MeshRenderer), typeof(Skidmarks));
            bool night = bootstrap != null && bootstrap.night;

            // hero + wingmen
            var heroSpec = CarCatalog.Get(CommandLine.Get("-car", "kaiju"));
            float startD = CommandLine.GetFloat("-startD", path.startDistance + 40f);
            hero = SpawnAI(heroSpec, (int)CommandLine.GetFloat("-paint", 0), path, startD, 0f, night);
            int wing = (int)CommandLine.GetFloat("-wingmen", 2);
            var all = CarCatalog.All;
            for (int i = 0; i < wing; i++)
            {
                var spec = all[(System.Array.IndexOf(new List<CarSpec>(all).ToArray(), heroSpec) + 1 + i) % all.Count];
                var c = SpawnAI(spec, (i * 3 + 2) % spec.paints.Length, path, startD - 14f - i * 12f, (i % 2 == 0 ? -2.2f : 2.2f), night);
                pack.Add(c);
            }
            var sys = new GameObject("TrailerSystems");
            scorer = sys.AddComponent<DriftScorer>();
            scorer.Bind(hero);
            sys.AddComponent<CalloutSystem>();
            scorer.OnTier += id => { CalloutSystem.I.Show(id); Log("callout", id.ToString()); };
            scorer.OnChainBanked += (pts, tier) => { if (tier.HasValue) { CalloutSystem.I.Show(tier.Value, "+" + pts.ToString("N0")); Log("callout", tier.Value.ToString()); } };
            var traffic = FindAnyObjectByType<TrafficSystem>();
            if (traffic) { traffic.player = hero; traffic.scorer = scorer; }

            // warm-up so cars are up to speed and drifting before capture starts
            float warm = CommandLine.GetFloat("-warmup", 7f);
            var chase = cam.gameObject.GetOrAdd<ChaseCamera>();
            chase.target = hero; chase.Snap();
            float t0 = Time.time;
            while (Time.time - t0 < warm) yield return null;
            chase.enabled = false;

            // capture
            Time.captureDeltaTime = 1f / fps;
            var shots = ParseShots();
            AudioRenderer.Start();
            var audioBuf = new List<float>();
            for (currentShot = 0; currentShot < shots.Count; currentShot++)
            {
                var s = shots[currentShot];
                Time.timeScale = s.slowmo;
                Time.captureDeltaTime = 1f / fps * s.slowmo;
                string dir = Path.Combine(outDir, $"shot_{currentShot:00}_{s.rig}");
                Directory.CreateDirectory(dir);
                Log("shot", $"{currentShot}:{s.rig}:{s.duration}");
                shotTime = 0f;
                frame = 0;
                SetupShot(s);
                int frames = Mathf.RoundToInt(s.duration * fps);
                int calloutFrame = forceCallouts && s.rig != Rig.Scenic && s.rig != Rig.Heli ? Mathf.RoundToInt(frames * 0.35f) : -1;
                for (int f = 0; f < frames; f++)
                {
                    shotTime = f / (float)fps;
                    if (f == calloutFrame)
                    {
                        var id = Escalation[escalate++ % Escalation.Length];
                        CalloutSystem.I.Show(id, "+" + (DriftScorer.TierThresholds[Mathf.Clamp((int)id, 0, 6)] + Random.Range(120, 900)).ToString("N0"));
                        Log("callout", id.ToString());
                    }
                    UpdateRig(s, 1f / fps);
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    File.WriteAllBytes(Path.Combine(dir, $"f_{f:00000}.jpg"), tex.EncodeToJPG(93));
                    Destroy(tex);
                    CollectAudio(audioBuf);
                }
                WriteWav(Path.Combine(dir, "audio.wav"), audioBuf, AudioSettings.outputSampleRate, 2);
                audioBuf.Clear();
            }
            AudioRenderer.Stop();
            File.WriteAllLines(Path.Combine(outDir, "log.txt"), log);
            Time.captureDeltaTime = 0f;
            Time.timeScale = 1f;
            Application.Quit();
        }

        void Log(string kind, string msg) => log.Add($"{currentShot}\t{shotTime:0.000}\t{kind}\t{msg}");

        CarController SpawnAI(CarSpec spec, int paint, TrackPath path, float d, float lateral, bool night)
        {
            Vector3 p = path.PointAt(d) + path.RightAt(d) * lateral + Vector3.up * 0.4f;
            var rot = Quaternion.LookRotation(path.TangentAt(d), Vector3.up);
            var car = CarFactory.Spawn(spec, paint, new Pose(p, rot), false, night);
            var ai = car.GetComponent<AIDriver>();
            ai.cinematic = true; ai.driftStyle = true; ai.rubberBand = false; ai.skill = 0.97f; ai.aggression = 0.8f;
            ai.desiredDriftAngle = 38f;
            car.Body.linearVelocity = rot * Vector3.forward * 22f;
            return car;
        }

        void CollectAudio(List<float> buf)
        {
            int n = AudioRenderer.GetSampleCountForCaptureFrame();
            if (n <= 0) return;
            var na = new NativeArray<float>(n * 2, Allocator.Temp);
            if (AudioRenderer.Render(na)) buf.AddRange(na.ToArray());
            na.Dispose();
        }

        static void WriteWav(string path, List<float> data, int rate, int ch)
        {
            using var fs = new FileStream(path, FileMode.Create);
            using var bw = new BinaryWriter(fs);
            int bytes = data.Count * 2;
            bw.Write(System.Text.Encoding.ASCII.GetBytes("RIFF")); bw.Write(36 + bytes); bw.Write(System.Text.Encoding.ASCII.GetBytes("WAVE"));
            bw.Write(System.Text.Encoding.ASCII.GetBytes("fmt ")); bw.Write(16); bw.Write((short)1); bw.Write((short)ch); bw.Write(rate); bw.Write(rate * ch * 2); bw.Write((short)(ch * 2)); bw.Write((short)16);
            bw.Write(System.Text.Encoding.ASCII.GetBytes("data")); bw.Write(bytes);
            foreach (var f in data) bw.Write((short)Mathf.Clamp(f * 32767f, -32768f, 32767f));
        }

        // ---------------------------------------------------------------- camera rigs
        void SetupShot(Shot s)
        {
            cam.fieldOfView = 55f;
            if (s.rig == Rig.Flyby)
            {
                var path = TrackPath.Active;
                int hint = -1;
                float d = path.Project(hero.transform.position, ref hint, out _);
                float ahead = hero.SpeedMs * s.duration * 0.55f;
                Vector3 p = path.PointAt(d + ahead);
                Vector3 r = path.RightAt(d + ahead);
                float hw = path.HalfWidthAt(d + ahead);
                flybyPos = p + r * (hw + 2.5f) * s.side + Vector3.up * 1.1f;
                cam.transform.position = flybyPos;
                cam.fieldOfView = 30f;
            }
            if (s.rig == Rig.Hood || s.rig == Rig.Chase)
            {
                var chase = cam.GetComponent<ChaseCamera>();
                chase.enabled = true;
                chase.target = hero;
                chase.mode = s.rig == Rig.Hood ? ChaseCamera.Mode.Bumper : ChaseCamera.Mode.ChaseNear;
                chase.Snap();
            }
            else cam.GetComponent<ChaseCamera>().enabled = false;
        }

        void UpdateRig(Shot s, float dt)
        {
            if (hero == null) return;
            Transform t = hero.transform;
            Vector3 v = hero.Body.linearVelocity; v.y = 0;
            Vector3 vdir = v.sqrMagnitude > 4f ? v.normalized : t.forward;
            Vector3 right = Vector3.Cross(Vector3.up, vdir);
            Vector3 target = t.position + Vector3.up * 0.7f;
            Vector3 want;
            switch (s.rig)
            {
                case Rig.LowSide:
                    want = t.position + right * 4.2f * s.side + vdir * 0.8f + Vector3.up * 0.55f;
                    Move(want, target, 0.06f, 42f);
                    break;
                case Rig.Front:
                    want = t.position + vdir * 7.5f + right * 1.2f * s.side + Vector3.up * 0.9f;
                    Move(want, target, 0.08f, 48f);
                    break;
                case Rig.Orbit:
                {
                    float a = shotTime * 40f * s.side;
                    want = t.position + Quaternion.Euler(0, a, 0) * (-vdir * 6f) + Vector3.up * 1.4f;
                    Move(want, target, 0.04f, 45f);
                    break;
                }
                case Rig.Flyby:
                    cam.transform.position = flybyPos;
                    cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(target - flybyPos), 1f - Mathf.Exp(-12f * dt));
                    break;
                case Rig.Heli:
                    want = t.position - vdir * 10f + Vector3.up * 16f;
                    Move(want, t.position + vdir * 6f, 0.2f, 50f);
                    break;
                case Rig.Wheel:
                    want = t.TransformPoint(new Vector3(1.6f * s.side, 0.35f, -hero.spec.wheelbase * 0.5f - 1.4f));
                    cam.transform.position = want;
                    cam.transform.rotation = Quaternion.LookRotation(t.TransformPoint(new Vector3(0.7f * s.side, 0.4f, 1.5f)) - want);
                    cam.fieldOfView = 70f;
                    break;
                case Rig.Pack:
                {
                    Vector3 c = t.position; int n = 1;
                    foreach (var p in pack) if (p) { c += p.transform.position; n++; }
                    c /= n;
                    want = c - vdir * 12f + right * 6f * s.side + Vector3.up * 4.5f;
                    Move(want, c + Vector3.up * 0.8f, 0.15f, 50f);
                    break;
                }
                case Rig.Scenic:
                {
                    // slow crane past the city/landscape, car passing through frame
                    want = t.position + right * 18f * s.side + Vector3.up * (6f + shotTime * 1.5f) - vdir * 10f;
                    Move(want, target + vdir * 10f, 0.6f, 40f);
                    break;
                }
            }
        }

        Vector3 Safe(Vector3 from, Vector3 want)
        {
            Vector3 d = want - from;
            int mask = ~((1 << CarController.CarLayer) | (1 << 2) | (1 << 11));
            if (Physics.SphereCast(from, 0.4f, d.normalized, out var hit, d.magnitude, mask, QueryTriggerInteraction.Ignore))
                return from + d.normalized * Mathf.Max(1.5f, hit.distance - 0.3f);
            return want;
        }

        void Move(Vector3 want, Vector3 look, float smooth, float fov)
        {
            if (hero != null) want = Safe(hero.transform.position + Vector3.up * 1.2f, want);
            if (shotTime < 0.0001f) { cam.transform.position = want; camVel = Vector3.zero; }
            cam.transform.position = Vector3.SmoothDamp(cam.transform.position, want, ref camVel, smooth, Mathf.Infinity, 1f / fps);
            cam.transform.rotation = Quaternion.LookRotation(look - cam.transform.position, Vector3.up);
            cam.fieldOfView = fov;
        }
    }
}
