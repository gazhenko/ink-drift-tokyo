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

            if (AIBench.Active)
            {
                mode = GameMode.Battle;
                GameSession.Rivals = (int)CommandLine.GetFloat("-rivals", 5);
                if (CommandLine.Has("-difficulty")) GameSession.Difficulty = (int)CommandLine.GetFloat("-difficulty", 2);
            }
            bool online = Net.NetSession.InRace;
            if (online) mode = GameMode.Battle;
            int rivalsCount = online ? 0 : mode == GameMode.Battle ? Mathf.Clamp(GameSession.Rivals, AIBench.Active ? 0 : 1, 7) : 0;
            var playerSpec = CarCatalog.Get(GameSession.CarId);
            int mySlot = online ? Mathf.Max(0, Net.NetSession.I.Grid.IndexOf(Net.NetSession.I.LocalId)) : rivalsCount;
            Player = CarFactory.Spawn(playerSpec, GameSession.PaintIndex, path.GridPose(mySlot), true, night);
            if (online)
            {
                Player.gameObject.AddComponent<Net.NetCarSender>();
                var ns = Net.NetSession.I;
                for (int slot = 0; slot < ns.Grid.Count; slot++)
                {
                    var np = ns.Find(ns.Grid[slot]);
                    if (np == null || np.id == ns.LocalId) continue;
                    var spec = CarCatalog.Get(np.carId);
                    var rc = CarFactory.Spawn(spec, np.paint, path.GridPose(slot), false, night);
                    var ai = rc.GetComponent<AIDriver>();
                    if (ai) DestroyImmediate(ai);
                    rc.name = "Net_" + np.name;
                    var nd = rc.gameObject.AddComponent<Net.NetCarDriver>();
                    nd.playerId = np.id; nd.playerName = np.name;
                    NameTag.Attach(rc.transform, np.name);
                    Rivals.Add(rc);
                }
            }

            var all = CarCatalog.All;
            for (int i = 0; i < rivalsCount; i++)
            {
                var spec = all[(i + 1 + System.Array.IndexOf(new List<CarSpec>(all).ToArray(), playerSpec)) % all.Count];
                var r = CarFactory.Spawn(spec, (i * 3 + 1) % spec.paints.Length, path.GridPose(i), false, night);
                var ai = r.GetComponent<AIDriver>();
                if (AIDriver.Legacy)
                {
                    ai.skill = Random.Range(0.93f, 1.0f);
                    ai.aggression = Random.Range(0.4f, 0.9f);
                    ai.lateralOffset = Random.Range(-1.2f, 1.2f);
                    ai.driftStyle = true;
                }
                // a small spread so the field races as a pack instead of a train: the front-runner uses the full limit
                else ai.ApplyDifficulty(GameSession.Difficulty, Mathf.Min(i, 5) * 0.006f);
                ai.rubberTarget = Player;
                Rivals.Add(r);
            }

            if (AIBench.Active)
            {
                // every car on AI, the player's car at the same difficulty without catch-up
                var pd = Player.GetComponent<PlayerDriver>();
                if (pd) Destroy(pd);
                var pai = Player.gameObject.AddComponent<AIDriver>();
                if (AIDriver.Legacy) { pai.skill = 1f; pai.driftStyle = true; }
                else pai.ApplyDifficulty(GameSession.Difficulty, 0f);
                pai.rubberBand = false;
                Player.assistLevel = 0;
                Player.transmission = Transmission.Automatic;
                gameObject.AddComponent<AIBench>();
            }
            if (mainCamera == null) mainCamera = Camera.main;
            var chase = mainCamera.gameObject.GetOrAdd<ChaseCamera>();
            chase.target = Player;
            chase.mode = ChaseCamera.Sanitize(GameSession.CameraMode);
            string camArg = CommandLine.Get("-camMode");   // dev: -camMode chase|near|hood|bumper
            if (camArg != null && System.Enum.TryParse(camArg == "near" ? "ChaseNear" : camArg, true, out ChaseCamera.Mode cm)) chase.mode = ChaseCamera.Sanitize((int)cm);
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
            Race.TotalLaps = online ? Net.NetSession.I.Laps : mode == GameMode.FreeRun ? 999 : TrackCatalog.Get(trackId).laps;
            Race.Online = online;

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
                traffic.enabled = (GameSession.Traffic && mode != GameMode.Battle || trackId == "shuto") && !AIBench.Active && !online;
                traffic.player = Player;
                traffic.scorer = Scorer;
            }

            if (TrackCatalog.Get(trackId).rain && !CommandLine.Has("-noRain")) RainWeather.Ensure(1f);
            MusicPlayer.Ensure().PlayTrackMusic(trackId);
            if (CommandLine.Has("-autopilot") && !AIBench.Active)
            {
                // dev: the AI drives the player's car (any race, including online ones)
                var pd = Player.GetComponent<PlayerDriver>();
                if (pd) Destroy(pd);
                var pai = Player.gameObject.AddComponent<AIDriver>();
                pai.ApplyDifficulty(2, 0f);
                pai.rubberBand = false;
                Player.assistLevel = 0;
            }
            if (online) { Race.BeginOnline(); Net.NetSession.I.LocalLoaded(); }
            else Race.Begin(0.6f);
        }

        void CalloutPopScore(long pts)
        {
            // Small banked chains: no voice, just a quick score stamp.
            CalloutSystem.I.Show(CalloutId.Nice, "+" + pts.ToString("N0"));
        }
    }
}
