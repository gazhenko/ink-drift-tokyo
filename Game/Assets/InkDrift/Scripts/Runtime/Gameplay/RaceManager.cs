using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>Countdown, laps, positions, callouts for race events, pause menu and the results screen.</summary>
    public class RaceManager : MonoBehaviour
    {
        public enum State { Intro, Countdown, Racing, Finished }

        public GameMode Mode = GameMode.DriftAttack;
        public int TotalLaps = 3;
        public CarController player;
        public DriftScorer scorer;
        public readonly List<CarController> rivals = new List<CarController>();
        public State state = State.Intro;

        public int PlayerLap { get; private set; } = 1;
        public int PlayerPosition { get; private set; } = 1;
        public float CurrentLapTime { get; private set; }
        public float BestLapTime { get; private set; }
        public float RaceTime { get; private set; }

        public static RaceManager I { get; private set; }

        int hint = -1;
        float lastD;
        bool halfway;
        bool paused;
        GameObject pauseRoot, resultsRoot;
        Canvas menuCanvas;
        string pauseNote;
        float sessionBest;

        void Awake() { I = this; }

        void OnEnable()
        {
            PlayerDriver.PausePressed += TogglePause;
            PlayerDriver.ResetPressed += ResetPlayer;
            GameInput.PadDisconnected += OnPadLost;
        }

        void OnDisable()
        {
            PlayerDriver.PausePressed -= TogglePause;
            PlayerDriver.ResetPressed -= ResetPlayer;
            GameInput.PadDisconnected -= OnPadLost;
            Time.timeScale = 1f;
        }

        public void Begin(float introSeconds = 0f) { StartCoroutine(Run(introSeconds)); }

        IEnumerator Run(float intro)
        {
            SetFrozen(true);
            BestLapTime = GameSession.BestLap(GameSession.TrackId);
            if (intro > 0f) yield return new WaitForSeconds(intro);
            state = State.Countdown;
            var cs = CalloutSystem.I;
            yield return new WaitForSeconds(0.4f);
            cs?.Show(CalloutId.Count3); yield return new WaitForSeconds(1f);
            cs?.Show(CalloutId.Count2); yield return new WaitForSeconds(1f);
            cs?.Show(CalloutId.Count1); yield return new WaitForSeconds(1f);
            cs?.Show(CalloutId.Go);
            SetFrozen(false);
            state = State.Racing;
            var path = TrackPath.Active;
            if (path != null) lastD = path.Project(player.transform.position, ref hint, out _);
        }

        void SetFrozen(bool f)
        {
            if (player) player.frozen = f;
            foreach (var r in rivals) if (r) r.frozen = f;
        }

        void Update()
        {
            // B / Circle backs out of the pause menu (Esc and Start are the Pause binding itself)
            if (paused && !ControlsScreen.IsOpen && !GameInput.Capturing && GameInput.Back.WasPressedThisFrame() && !GameInput.Pause.WasPressedThisFrame())
                TogglePause();
            if (state != State.Racing || player == null) return;
            var path = TrackPath.Active;
            if (path == null) return;
            float dt = Time.deltaTime;
            RaceTime += dt;
            CurrentLapTime += dt;

            float d = path.Project(player.transform.position, ref hint, out _);
            float L = path.length;
            float rel = Mathf.Repeat(d - path.startDistance, L);
            float relLast = Mathf.Repeat(lastD - path.startDistance, L);
            if (rel > L * 0.4f && rel < L * 0.6f) halfway = true;
            if (relLast > L * 0.85f && rel < L * 0.15f && halfway)
            {
                halfway = false;
                CompleteLap();
            }
            lastD = d;

            if (Mode == GameMode.Battle && rivals.Count > 0)
            {
                float myProg = (PlayerLap - 1) * L + rel;
                int pos = 1;
                foreach (var r in rivals)
                {
                    var ai = r ? r.GetComponent<AIDriver>() : null;
                    if (ai == null) continue;
                    float theirs = ai.Progress - path.startDistance;
                    if (theirs > myProg) pos++;
                }
                if (pos < PlayerPosition && RaceTime > 5f) CalloutSystem.I?.Show(CalloutId.Overtake);
                PlayerPosition = pos;
            }
        }

        void CompleteLap()
        {
            float lap = CurrentLapTime;
            CurrentLapTime = 0f;
            bool best = BestLapTime <= 0f || lap < BestLapTime;
            if (best)
            {
                BestLapTime = lap;
                GameSession.SetBestLap(GameSession.TrackId, lap);
            }
            if (Mode == GameMode.FreeRun) { if (best) CalloutSystem.I?.Show(CalloutId.BestLap); return; }
            PlayerLap++;
            if (PlayerLap > TotalLaps) { Finish(); return; }
            if (PlayerLap == TotalLaps) CalloutSystem.I?.Show(CalloutId.FinalLap);
            else if (best && sessionBest > 0f) CalloutSystem.I?.Show(CalloutId.BestLap);
            sessionBest = sessionBest <= 0f ? lap : Mathf.Min(sessionBest, lap);
        }

        void Finish()
        {
            state = State.Finished;
            StartCoroutine(FinishRoutine());
        }

        public static string RankFor(long score, string track)
        {
            float k = track == "shuto" ? 1.3f : 1f;
            if (score >= 180000 * k) return "S";
            if (score >= 110000 * k) return "A";
            if (score >= 60000 * k) return "B";
            if (score >= 25000 * k) return "C";
            return "D";
        }

        IEnumerator FinishRoutine()
        {
            CalloutSystem.I?.Show(CalloutId.Goal);
            // hand the car to the AI for a cool-down lap
            var ai = player.gameObject.AddComponent<AIDriver>();
            ai.skill = 0.7f; ai.driftStyle = true; ai.rubberBand = false;
            var pd = player.GetComponent<PlayerDriver>();
            if (pd) pd.enabled = false;
            yield return new WaitForSeconds(2.2f);

            long score = scorer ? scorer.TotalScore : 0;
            string rank = Mode == GameMode.Battle ? (PlayerPosition == 1 ? "S" : PlayerPosition == 2 ? "A" : PlayerPosition <= 4 ? "B" : "C") : RankFor(score, GameSession.TrackId);
            bool record = Mode == GameMode.DriftAttack && score > GameSession.BestScore(GameSession.TrackId);
            if (record) GameSession.SetBestScore(GameSession.TrackId, score);
            PlayerPrefs.Save();

            if (rank == "S") CalloutSystem.I?.Show(CalloutId.DriftKing);
            else if (record) CalloutSystem.I?.Show(CalloutId.NewRecord);
            yield return new WaitForSeconds(1.0f);
            ShowResults(score, rank, record);
        }

        Canvas EnsureCanvas()
        {
            if (menuCanvas == null)
            {
                menuCanvas = UIKit.MakeCanvas("RaceMenus", 80, transform);
                GameInput.EnsureEventSystem(transform);
            }
            return menuCanvas;
        }

        void ShowResults(long score, string rank, bool record)
        {
            var c = EnsureCanvas();
            var fs = FontSet.I;
            resultsRoot = UIKit.Stretch("Results", c.transform).gameObject;
            var dim = resultsRoot.AddComponent<Image>(); dim.color = Palette.Indigo.WithA(0.72f);
            var panel = UIKit.Rect("Panel", resultsRoot.transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 20), new Vector2(1100, 640));
            var sp = panel.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Paper; sp.slant = 40; sp.border = 10; sp.shadowOffset = new Vector2(22, -22);
            var title = UIKit.Text("Title", panel, "RESULTS · リザルト", fs ? fs.jpHeavy : null, 64, Palette.Magenta, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(420, -70), new Vector2(760, 90));
            UIKit.Inked(title, 0.25f, Palette.Ink, new Vector2(1, -1));
            var track = TrackCatalog.Get(GameSession.TrackId);
            UIKit.Text("Track", panel, $"{track.name}  {track.jp}  ·  {CarCatalog.Get(GameSession.CarId).displayName}", fs ? fs.comic : null, 34, Palette.Ink, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(440, -130), new Vector2(800, 50));

            string[] rows =
            {
                Mode == GameMode.Battle ? $"POSITION   {PlayerPosition} / {rivals.Count + 1}" : $"DRIFT SCORE   {score:N0}",
                $"BEST CHAIN   {(scorer ? scorer.BestChain : 0):N0}",
                $"LONGEST DRIFT   {(scorer ? scorer.LongestDrift : 0):0.0}s",
                $"BEST LAP   {FormatTime(BestLapTime)}",
                $"TOTAL TIME   {FormatTime(RaceTime)}",
            };
            for (int i = 0; i < rows.Length; i++)
            {
                var t = UIKit.Text("Row" + i, panel, rows[i], fs ? fs.hud : null, i == 0 ? 52 : 38, Palette.Ink, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(430, -210 - i * 62 - (i > 0 ? 14 : 0)), new Vector2(760, 64));
            }
            if (record)
            {
                var nr = UIKit.Text("Record", panel, "NEW RECORD! 新記録！", fs ? fs.jpHeavy : null, 40, Palette.Red, TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(430, 120), new Vector2(760, 60));
                UIKit.Inked(nr, 0.2f);
            }
            var lib = Resources.Load<Sprite>("UI/rank_" + rank);
            if (lib != null) UIKit.Img("Rank", panel, lib, Color.white, new Vector2(1, 0.5f), new Vector2(-220, 40), new Vector2(380, 380));
            else
            {
                var r = UIKit.Text("Rank", panel, rank, fs ? fs.comic : null, 360, rank == "S" ? Palette.Red : Palette.Magenta, TextAlignmentOptions.Center, new Vector2(1, 0.5f), new Vector2(-220, 40), new Vector2(380, 380));
                UIKit.Inked(r, 0.3f, Palette.Ink, new Vector2(1.5f, -1.5f));
            }

            var retry = UIKit.Button("Retry", resultsRoot.transform, "RETRY", "もう一回", new Vector2(0.5f, 0.5f), new Vector2(-170, -380), new Vector2(300, 100), Restart, Palette.Yellow);
            UIKit.Button("Menu", resultsRoot.transform, "MENU", "メニュー", new Vector2(0.5f, 0.5f), new Vector2(170, -380), new Vector2(300, 100), QuitToMenu, Palette.Cyan);
            EventSystem.current?.SetSelectedGameObject(retry.gameObject);
            StartCoroutine(PopIn(panel));
        }

        IEnumerator PopIn(RectTransform rt)
        {
            float t = 0f;
            while (t < 0.35f)
            {
                t += Time.unscaledDeltaTime;
                rt.localScale = Vector3.one * UIKit.EaseOutBack(t / 0.35f, 2f);
                rt.localRotation = Quaternion.Euler(0, 0, (1f - t / 0.35f) * -8f);
                yield return null;
            }
        }

        static string FormatTime(float t)
        {
            if (t <= 0f) return "--:--.---";
            int m = (int)(t / 60f); float s = t - m * 60f;
            return $"{m}:{s:00.000}";
        }

        void OnPadLost(UnityEngine.InputSystem.InputDevice pad)
        {
            if (paused || state == State.Finished) return;
            pauseNote = "CONTROLLER DISCONNECTED · コントローラーが切断されました";
            TogglePause();
        }

        /// <summary>Dev captures: open the pause menu (and optionally its Controls screen).</summary>
        public void DevPause(bool controls)
        {
            if (!paused) TogglePause();
            if (controls) OpenControls();
        }

        void OpenControls()
        {
            if (pauseRoot) pauseRoot.SetActive(false);
            ControlsScreen.Open(EnsureCanvas().transform, () =>
            {
                if (!pauseRoot) return;
                pauseRoot.SetActive(true);
                var b = pauseRoot.transform.Find("Controls");
                if (b) EventSystem.current?.SetSelectedGameObject(b.gameObject);
            });
        }

        void TogglePause()
        {
            if (state == State.Finished || ControlsScreen.IsOpen || GameInput.Capturing) return;
            paused = !paused;
            Time.timeScale = paused ? 0f : 1f;
            AudioListener.pause = paused;
            if (paused)
            {
                var c = EnsureCanvas();
                pauseRoot = UIKit.Stretch("Pause", c.transform).gameObject;
                var dim = pauseRoot.AddComponent<Image>(); dim.color = Palette.Ink.WithA(0.7f);
                var fs = FontSet.I;
                var t = UIKit.Text("Title", pauseRoot.transform, "PAUSE · 一時停止", fs ? fs.jpHeavy : null, 96, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 260), new Vector2(1200, 140));
                UIKit.Inked(t, 0.25f, Palette.Ink, new Vector2(1.2f, -1.2f));
                var resume = UIKit.Button("Resume", pauseRoot.transform, "RESUME", "再開", new Vector2(0.5f, 0.5f), new Vector2(0, 80), new Vector2(420, 100), TogglePause, Palette.Yellow);
                UIKit.Button("Restart", pauseRoot.transform, "RESTART", "リスタート", new Vector2(0.5f, 0.5f), new Vector2(0, -50), new Vector2(420, 100), Restart, Palette.Paper);
                UIKit.Button("Controls", pauseRoot.transform, "CONTROLS", "操作設定", new Vector2(0.5f, 0.5f), new Vector2(0, -180), new Vector2(420, 100), OpenControls, Palette.Lime);
                UIKit.Button("Quit", pauseRoot.transform, "QUIT TO MENU", "メニューへ", new Vector2(0.5f, 0.5f), new Vector2(0, -310), new Vector2(420, 100), QuitToMenu, Palette.Cyan);
                if (pauseNote != null)
                {
                    var n = UIKit.Text("Note", pauseRoot.transform, pauseNote, fs ? fs.jpHeavy : null, 34, Palette.Red, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 175), new Vector2(1400, 50));
                    UIKit.Inked(n, 0.25f);
                    pauseNote = null;
                }
                EventSystem.current?.SetSelectedGameObject(resume.gameObject);
            }
            else if (pauseRoot != null) Destroy(pauseRoot);
        }

        void ResetPlayer()
        {
            if (state != State.Racing || player == null || TrackPath.Active == null) return;
            int h = -1;
            var pose = TrackPath.Active.ResetPose(player.transform.position, ref h);
            player.ResetTo(pose.position, pose.rotation);
            ChaseCamera.Main?.Snap();
        }

        public void Restart()
        {
            Time.timeScale = 1f; AudioListener.pause = false;
            SceneManager.LoadScene(SceneManager.GetActiveScene().name);
        }

        public void QuitToMenu()
        {
            Time.timeScale = 1f; AudioListener.pause = false;
            SceneManager.LoadScene("MainMenu");
        }
    }
}
