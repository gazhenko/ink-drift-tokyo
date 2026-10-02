using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>Lives in every track scene: spawns the player/rivals and wires camera, scoring, callouts, HUD, race logic and music.</summary>
    public class RaceBootstrap : MonoBehaviour
    {
        public string trackId = "shibuya";
        public bool night;
        public Camera mainCamera;
        public bool spawnOnStart = true;

        public CarController Player { get; private set; }
        public DriftScorer Scorer { get; private set; }
        public RaceManager Race { get; private set; }
        public HUD Hud { get; private set; }
        public readonly List<CarController> Rivals = new List<CarController>();

        public static RaceBootstrap I { get; private set; }

        void Awake()
        {
            I = this;
            Time.fixedDeltaTime = 1f / 120f;
            Physics.defaultSolverIterations = 8;
            GameSession.TrackId = trackId;
        }

        void Start()
        {
            if (!spawnOnStart) return;
            if (TrailerDirector.Requested) { gameObject.AddComponent<TrailerDirector>(); return; }
            SetupRace(GameSession.Mode);
        }

        public void SetupRace(GameMode mode)
        {
            var path = TrackPath.Active;
            if (path == null) { Debug.LogError("No TrackPath in scene"); return; }
            if (FindAnyObjectByType<Skidmarks>() == null) new GameObject("Skidmarks", typeof(MeshFilter), typeof(MeshRenderer), typeof(Skidmarks));

            int rivalsCount = mode == GameMode.Battle ? Mathf.Clamp(GameSession.Rivals, 1, 7) : 0;
            var playerSpec = CarCatalog.Get(GameSession.CarId);
            Player = CarFactory.Spawn(playerSpec, GameSession.PaintIndex, path.GridPose(rivalsCount), true, night);

            var all = CarCatalog.All;
            for (int i = 0; i < rivalsCount; i++)
            {
                var spec = all[(i + 1 + System.Array.IndexOf(new List<CarSpec>(all).ToArray(), playerSpec)) % all.Count];
                var r = CarFactory.Spawn(spec, (i * 3 + 1) % spec.paints.Length, path.GridPose(i), false, night);
                var ai = r.GetComponent<AIDriver>();
                ai.skill = Random.Range(0.93f, 1.0f);
                ai.aggression = Random.Range(0.4f, 0.9f);
                ai.lateralOffset = Random.Range(-1.2f, 1.2f);
                ai.rubberTarget = Player;
                ai.driftStyle = true;
                Rivals.Add(r);
            }

            if (mainCamera == null) mainCamera = Camera.main;
            var chase = mainCamera.gameObject.GetOrAdd<ChaseCamera>();
            chase.target = Player;
            chase.mode = (ChaseCamera.Mode)Mathf.Clamp(GameSession.CameraMode, 0, 4);
            string camArg = CommandLine.Get("-camMode");   // dev: -camMode cockpit|chase|near|hood|bumper
            if (camArg != null && System.Enum.TryParse(camArg == "near" ? "ChaseNear" : camArg, true, out ChaseCamera.Mode cm)) chase.mode = cm;
            chase.Snap();
            if (mainCamera.GetComponent<AudioListener>() == null) mainCamera.gameObject.AddComponent<AudioListener>();

            var sys = new GameObject("RaceSystems");
            Scorer = sys.AddComponent<DriftScorer>();
            Scorer.Bind(Player);
            sys.AddComponent<CalloutSystem>();
            CalloutSystem.I.VoiceVolume = GameSession.VoiceVolume;
            Race = sys.AddComponent<RaceManager>();
            Race.Mode = mode;
            Race.player = Player;
            Race.scorer = Scorer;
            Race.rivals.AddRange(Rivals);
            Race.TotalLaps = mode == GameMode.FreeRun ? 999 : TrackCatalog.Get(trackId).laps;

            Hud = sys.AddComponent<HUD>();
            Hud.car = Player; Hud.scorer = Scorer; Hud.race = Race;
            Hud.Build();
            foreach (var r in Rivals) Hud.AddRival(r.transform);

            Scorer.OnTier += id => CalloutSystem.I.Show(id);
            Scorer.OnChainBanked += (pts, tier) =>
            {
                if (tier.HasValue) CalloutSystem.I.Show(tier.Value, "+" + pts.ToString("N0"));
                else if (pts > 500) CalloutPopScore(pts);
            };
            Scorer.OnChainFailed += lost => CalloutSystem.I.Show(CalloutId.Fail, "-" + ((long)lost).ToString("N0"));
            Scorer.OnMultiplier += m => { if (m == 5 || m == 8) CalloutSystem.I.Show(CalloutId.Ikee); };

            var traffic = FindAnyObjectByType<TrafficSystem>();
            if (traffic != null)
            {
                traffic.enabled = GameSession.Traffic && mode != GameMode.Battle || trackId == "shuto";
                traffic.player = Player;
                traffic.scorer = Scorer;
            }

            MusicPlayer.Ensure().PlayTrackMusic(trackId);
            Race.Begin(0.6f);
        }

        void CalloutPopScore(long pts)
        {
            // Small banked chains: no voice, just a quick score stamp.
            CalloutSystem.I.Show(CalloutId.Nice, "+" + pts.ToString("N0"));
        }
    }
}
