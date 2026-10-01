using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>Title → main menu → car select → track select → loading. Built entirely in code over a 3D showroom.</summary>
    public class MenuController : MonoBehaviour
    {
        public Transform turntable;
        public Camera cam;
        public Light[] accentLights = new Light[0];

        enum Screen { Title, Main, Car, Track, Settings, Loading }
        Screen screen;
        Canvas canvas;
        RectTransform root;
        GameObject current;
        GameObject displayCar;
        int carIndex, paintIndex, trackIndex;
        GameMode pendingMode = GameMode.DriftAttack;
        InputAction left, right, up, down, back, any;
        float camT;
        TextMeshProUGUI carName, carJp, carTag, carSpecs, paintLabel;
        Image[] statFill;
        readonly List<Image> swatches = new List<Image>();

        void Start()
        {
            Time.timeScale = 1f;
            AudioListener.pause = false;
            AudioListener.volume = GameSession.MasterVolume;
            QualitySettings.SetQualityLevel(GameSession.Quality, true);
            canvas = UIKit.MakeCanvas("Menu", 10, transform);
            root = UIKit.Stretch("Root", canvas.transform);
            if (FindAnyObjectByType<EventSystem>() == null)
                new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
            left = Act("<Keyboard>/leftArrow", "<Keyboard>/a", "<Gamepad>/dpad/left", "<Gamepad>/leftStick/left");
            right = Act("<Keyboard>/rightArrow", "<Keyboard>/d", "<Gamepad>/dpad/right", "<Gamepad>/leftStick/right");
            up = Act("<Keyboard>/upArrow", "<Keyboard>/w", "<Gamepad>/dpad/up");
            down = Act("<Keyboard>/downArrow", "<Keyboard>/s", "<Gamepad>/dpad/down");
            back = Act("<Keyboard>/escape", "<Keyboard>/backspace", "<Gamepad>/buttonEast");
            any = Act("<Keyboard>/anyKey", "<Gamepad>/start", "<Gamepad>/buttonSouth", "<Mouse>/leftButton");
            carIndex = Mathf.Max(0, IndexOfCar(GameSession.CarId));
            if (CommandLine.Has("-menuCar")) carIndex = Mathf.Clamp((int)CommandLine.GetFloat("-menuCar", 0), 0, CarCatalog.All.Count - 1);
            paintIndex = GameSession.PaintIndex;
            MusicPlayer.Ensure().PlayMenuMusic();
            ShowDisplayCar();
            string dbg = CommandLine.Get("-menuScreen");
            Go(dbg == "main" ? Screen.Main : dbg == "car" ? Screen.Car : dbg == "track" ? Screen.Track : dbg == "settings" ? Screen.Settings : Screen.Title);
            if (CommandLine.Has("-autoFlow")) StartCoroutine(AutoFlow());
        }

        /// <summary>Smoke test: title → main → Battle → car → track → race (-autoFlow [-flowTrack n] [-flowCar n]).</summary>
        IEnumerator AutoFlow()
        {
            yield return new WaitForSeconds(1.5f);
            Go(Screen.Main); yield return new WaitForSeconds(0.8f);
            MainPick(1); yield return new WaitForSeconds(0.8f);
            carIndex = (int)CommandLine.GetFloat("-flowCar", 2); ShowDisplayCar(); Go(Screen.Car); yield return new WaitForSeconds(0.8f);
            GameSession.CarId = CarCatalog.All[carIndex].id; GameSession.PaintIndex = 3;
            trackIndex = (int)CommandLine.GetFloat("-flowTrack", 1); Go(Screen.Track); yield return new WaitForSeconds(0.8f);
            StartRace();
        }

        void OnDestroy() { foreach (var a in new[] { left, right, up, down, back, any }) { a?.Disable(); a?.Dispose(); } }

        static InputAction Act(params string[] b)
        {
            var a = new InputAction(type: InputActionType.Button);
            foreach (var x in b) a.AddBinding(x);
            a.Enable();
            return a;
        }

        static int IndexOfCar(string id)
        {
            var all = CarCatalog.All;
            for (int i = 0; i < all.Count; i++) if (all[i].id == id) return i;
            return 0;
        }

        void Update()
        {
            if (turntable) turntable.Rotate(0f, 14f * Time.deltaTime, 0f, Space.World);
            camT += Time.deltaTime;
            if (cam)
            {
                float a = Mathf.Sin(camT * 0.15f) * 12f;
                Vector3 target = turntable ? turntable.position + Vector3.up * 0.7f : Vector3.zero;
                Vector3 offset = Quaternion.Euler(0, 215f + a, 0) * new Vector3(0, 2.3f, 10.5f);
                if (screen == Screen.Car) offset = Quaternion.Euler(0, 210f + a * 0.5f, 0) * new Vector3(0, 1.3f, 6.4f);
                cam.transform.position = Vector3.Lerp(cam.transform.position, target + offset, 1f - Mathf.Exp(-3f * Time.deltaTime));
                cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(target + (screen == Screen.Car ? cam.transform.right * 1.7f : Vector3.zero) - cam.transform.position), 1f - Mathf.Exp(-4f * Time.deltaTime));
            }
            foreach (var l in accentLights) if (l && l.type == LightType.Spot) l.intensity = 30f + Mathf.Sin(Time.time * 2.3f + l.GetInstanceID()) * 6f;

            switch (screen)
            {
                case Screen.Title:
                    if (any.WasPressedThisFrame()) { UISfx.Play("ui_confirm"); Go(Screen.Main); }
                    break;
                case Screen.Car:
                    if (left.WasPressedThisFrame()) ChangeCar(-1);
                    if (right.WasPressedThisFrame()) ChangeCar(1);
                    if (up.WasPressedThisFrame()) ChangePaint(-1);
                    if (down.WasPressedThisFrame()) ChangePaint(1);
                    if (back.WasPressedThisFrame()) Go(Screen.Main);
                    break;
                case Screen.Track:
                    if (left.WasPressedThisFrame()) { trackIndex = (trackIndex + TrackCatalog.All.Length - 1) % TrackCatalog.All.Length; Go(Screen.Track); }
                    if (right.WasPressedThisFrame()) { trackIndex = (trackIndex + 1) % TrackCatalog.All.Length; Go(Screen.Track); }
                    if (back.WasPressedThisFrame()) Go(Screen.Car);
                    break;
                case Screen.Settings:
                case Screen.Main:
                    if (back.WasPressedThisFrame()) Go(screen == Screen.Settings ? Screen.Main : Screen.Title);
                    break;
            }
        }

        void Go(Screen s)
        {
            screen = s;
            if (current) Destroy(current);
            current = UIKit.Stretch(s.ToString(), root).gameObject;
            statFill = null; swatches.Clear();
            switch (s)
            {
                case Screen.Title: BuildTitle(); break;
                case Screen.Main: BuildMain(); break;
                case Screen.Car: BuildCar(); break;
                case Screen.Track: BuildTrack(); break;
                case Screen.Settings: BuildSettings(); break;
            }
            StartCoroutine(PopIn(current.transform as RectTransform));
        }

        IEnumerator PopIn(RectTransform rt)
        {
            var cg = rt.gameObject.AddComponent<CanvasGroup>();
            float t = 0f;
            while (t < 0.25f && rt)
            {
                t += Time.unscaledDeltaTime;
                cg.alpha = t / 0.25f;
                rt.localScale = Vector3.one * Mathf.Lerp(1.06f, 1f, UIKit.EaseOutCubic(t / 0.25f));
                yield return null;
            }
        }

        Transform C => current.transform;
        FontSet F => FontSet.I;

        void Header(string en, string jp, Color col)
        {
            var p = UIKit.Rect("Header", C, new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(60, -40), new Vector2(900, 130));
            var sp = p.gameObject.AddComponent<SlantPanel>(); sp.color = col; sp.slant = 30; sp.raycastTarget = false;
            var t = UIKit.Text("EN", p, en, F ? F.comic : null, 84, Palette.Ink, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(460, 14), new Vector2(820, 100));
            var j = UIKit.Text("JP", p, jp, F ? F.jpHeavy : null, 30, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(460, -42), new Vector2(820, 40));
            UIKit.Inked(j, 0.25f);
        }

        void Hint(string text)
        {
            var t = UIKit.Text("Hint", C, text, F ? F.comic : null, 30, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 40), new Vector2(1600, 50));
            UIKit.Inked(t, 0.3f);
        }

        void BuildTitle()
        {
            var logo = Resources.Load<Sprite>("UI/logo_inkdrift");
            if (logo) UIKit.Img("Logo", C, logo, Color.white, new Vector2(0.5f, 0.77f), Vector2.zero, new Vector2(1080, 405));
            else
            {
                var t = UIKit.Text("Logo", C, "INK DRIFT", F ? F.comic : null, 220, Palette.Magenta, TextAlignmentOptions.Center, new Vector2(0.5f, 0.66f), Vector2.zero, new Vector2(1600, 260));
                UIKit.Inked(t, 0.3f, Palette.Ink, new Vector2(1.5f, -1.5f));
                var t2 = UIKit.Text("Sub", C, "TOKYO · インクドリフト東京", F ? F.jpHeavy : null, 72, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0.52f), Vector2.zero, new Vector2(1600, 100));
                UIKit.Inked(t2, 0.3f);
            }
            var press = UIKit.Text("Press", C, "PRESS ANY BUTTON · ボタンを押してね", F ? F.comic : null, 50, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.09f), Vector2.zero, new Vector2(1600, 80));
            UIKit.Inked(press, 0.3f, Palette.Ink, new Vector2(1, -1));
            press.gameObject.AddComponent<Blink>();
            UIKit.Text("Ver", C, "v" + Application.version + "  ·  a comic-book drift demo", F ? F.hudRegular : null, 22, Palette.Paper.WithA(0.6f), TextAlignmentOptions.Right, new Vector2(1, 0), new Vector2(-260, 24), new Vector2(500, 30));
        }

        void BuildMain()
        {
            Header("MAIN MENU", "メインメニュー", Palette.Yellow);
            string[] en = { "DRIFT ATTACK", "RIVAL BATTLE", "FREE RUN", "SETTINGS", "QUIT" };
            string[] jp = { "ドリフトアタック", "ライバルバトル", "フリーラン", "設定", "終了" };
            Color[] cols = { Palette.Magenta, Palette.Cyan, Palette.Lime, Palette.Paper, Palette.Paper };
            UnityEngine.UI.Button first = null;
            for (int i = 0; i < en.Length; i++)
            {
                int k = i;
                var b = UIKit.Button(en[i], C, en[i], jp[i], new Vector2(0, 0.5f), new Vector2(330 + i * 18, 230 - i * 125), new Vector2(560, 104), () => MainPick(k), cols[i]);
                if (i == 0) first = b;
            }
            var desc = UIKit.Text("Desc", C, "Chain drifts for points. Angle × speed × combo.\nClip the walls. Don't touch them.", F ? F.comic : null, 34, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(560, 150), new Vector2(900, 100));
            UIKit.Inked(desc, 0.3f);
            EventSystem.current.SetSelectedGameObject(first.gameObject);
            Hint("↑↓ SELECT   ·   ENTER / A  CONFIRM   ·   ESC / B  BACK");
        }

        void MainPick(int k)
        {
            UISfx.Play("ui_confirm");
            switch (k)
            {
                case 0: pendingMode = GameMode.DriftAttack; Go(Screen.Car); break;
                case 1: pendingMode = GameMode.Battle; Go(Screen.Car); break;
                case 2: pendingMode = GameMode.FreeRun; Go(Screen.Car); break;
                case 3: Go(Screen.Settings); break;
                case 4: Application.Quit(); break;
            }
        }

        void BuildCar()
        {
            Header("SELECT CAR", "車を選んでね", Palette.Magenta);
            var spec = CarCatalog.All[carIndex];
            var panel = UIKit.Rect("Info", C, new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(-60, -10), new Vector2(720, 760));
            var sp = panel.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Ink.WithA(0.88f); sp.borderColor = Palette.Paper; sp.border = 5; sp.slant = 20; sp.raycastTarget = false;
            carName = UIKit.Text("Name", panel, spec.displayName, F ? F.comic : null, 92, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(360, -70), new Vector2(660, 110));
            UIKit.Inked(carName, 0.25f, Palette.Ink, new Vector2(1, -1));
            carJp = UIKit.Text("JP", panel, spec.jpName, F ? F.jpHeavy : null, 30, Palette.Magenta, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(360, -138), new Vector2(660, 40));
            carTag = UIKit.Text("Tag", panel, spec.tagline, F ? F.comic : null, 32, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(360, -205), new Vector2(640, 90));
            carTag.textWrappingMode = TextWrappingModes.Normal;
            string[] labels = { "POWER", "WEIGHT", "GRIP", "DRIFT" };
            statFill = new Image[4];
            for (int i = 0; i < 4; i++)
            {
                UIKit.Text("L" + i, panel, labels[i], F ? F.comic : null, 34, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(150, -300 - i * 58), new Vector2(220, 50));
                var bg = UIKit.Img("Bg" + i, panel, null, Palette.Paper.WithA(0.15f), new Vector2(0, 1), new Vector2(470, -300 - i * 58), new Vector2(420, 26));
                statFill[i] = UIKit.Img("Fill" + i, bg.transform, null, i == 3 ? Palette.Magenta : Palette.Yellow, new Vector2(0, 0.5f), Vector2.zero, new Vector2(420, 26));
                statFill[i].rectTransform.pivot = new Vector2(0, 0.5f);
            }
            carSpecs = UIKit.Text("Specs", panel, "", F ? F.hudRegular : null, 26, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(360, 190), new Vector2(640, 90));
            carSpecs.textWrappingMode = TextWrappingModes.Normal;
            paintLabel = UIKit.Text("PaintL", panel, "PAINT ↑↓", F ? F.comic : null, 30, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(150, 120), new Vector2(220, 40));
            for (int i = 0; i < spec.paints.Length; i++)
            {
                var s = UIKit.Img("Sw" + i, panel, null, spec.paints[i], new Vector2(0, 0), new Vector2(300 + i * 52, 120), new Vector2(40, 40));
                swatches.Add(s);
            }
            var go = UIKit.Button("Go", C, "SELECT", "決定", new Vector2(1, 0), new Vector2(-300, 90), new Vector2(380, 104), () => { UISfx.Play("ui_confirm"); GameSession.CarId = CarCatalog.All[carIndex].id; GameSession.PaintIndex = paintIndex; Go(Screen.Track); }, Palette.Yellow);
            UIKit.Button("Prev", C, "◀", null, new Vector2(0, 0.5f), new Vector2(110, -40), new Vector2(110, 110), () => ChangeCar(-1), Palette.Paper);
            UIKit.Button("Next", C, "▶", null, new Vector2(0.5f, 0.5f), new Vector2(60, -40), new Vector2(110, 110), () => ChangeCar(1), Palette.Paper);
            EventSystem.current.SetSelectedGameObject(go.gameObject);
            Hint("◀ ▶ CAR   ·   ↑↓ PAINT   ·   ENTER / A  SELECT   ·   ESC / B  BACK");
            RefreshCarInfo();
        }

        void RefreshCarInfo()
        {
            var spec = CarCatalog.All[carIndex];
            if (carName) carName.text = spec.displayName;
            if (carJp) carJp.text = spec.jpName;
            if (carTag) carTag.text = spec.tagline;
            if (statFill != null)
            {
                float[] v = { spec.statPower, spec.statWeight, spec.statGrip, spec.statDrift };
                for (int i = 0; i < 4; i++) StartCoroutine(Fill(statFill[i], v[i]));
            }
            if (carSpecs) carSpecs.text = $"{spec.horsepower:0} PS  ·  {spec.mass:0} kg  ·  {(spec.drive == DriveType.AWD ? "AWD" : "FR")}  ·  {spec.cylinders}-cyl{(spec.turboBoostGain > 0 ? " turbo" : "")}\n<size=80%><color=#9BE7FF>Inspired by: {spec.inspiredBy}</color></size>";
            for (int i = 0; i < swatches.Count; i++)
                swatches[i].rectTransform.localScale = Vector3.one * (i == paintIndex ? 1.35f : 1f);
        }

        IEnumerator Fill(Image img, float v)
        {
            float t = 0f;
            float from = img.rectTransform.sizeDelta.x / 420f;
            while (t < 0.3f && img)
            {
                t += Time.unscaledDeltaTime;
                img.rectTransform.sizeDelta = new Vector2(420f * Mathf.Lerp(from, v, UIKit.EaseOutCubic(t / 0.3f)), 26f);
                yield return null;
            }
        }

        void ChangeCar(int d)
        {
            UISfx.Play("ui_move");
            carIndex = (carIndex + d + CarCatalog.All.Count) % CarCatalog.All.Count;
            paintIndex = 0;
            ShowDisplayCar();
            Go(Screen.Car);
        }

        void ChangePaint(int d)
        {
            var spec = CarCatalog.All[carIndex];
            paintIndex = (paintIndex + d + spec.paints.Length) % spec.paints.Length;
            if (displayCar) CarFactory.ApplyPaint(displayCar, spec.paints[paintIndex]);
            UISfx.Play("ui_move");
            RefreshCarInfo();
        }

        void ShowDisplayCar()
        {
            if (displayCar) Destroy(displayCar);
            if (turntable == null) return;
            var spec = CarCatalog.All[carIndex];
            displayCar = CarFactory.SpawnDisplay(spec, paintIndex, turntable);
        }

        void BuildTrack()
        {
            Header("SELECT TRACK", "コースを選んでね", Palette.Cyan);
            var tracks = TrackCatalog.All;
            UnityEngine.UI.Button sel = null;
            for (int i = 0; i < tracks.Length; i++)
            {
                var tr = tracks[i];
                bool on = i == trackIndex;
                var card = UIKit.Rect("Card" + i, C, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2((i - 1) * 580, on ? 10 : -10), new Vector2(540, 640));
                var sp = card.gameObject.AddComponent<SlantPanel>(); sp.color = on ? tr.accent : Palette.Ink.WithA(0.85f); sp.border = 8; sp.slant = 26; sp.raycastTarget = false;
                var prev = Resources.Load<Sprite>("UI/track_" + tr.id);
                if (prev) { var img = UIKit.Img("Preview", card, prev, Color.white, new Vector2(0.5f, 1), new Vector2(10, -170), new Vector2(480, 270)); img.preserveAspect = false; }
                var n = UIKit.Text("Name", card, tr.name, F ? F.comic : null, 58, on ? Palette.Ink : Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(10, -40), new Vector2(520, 70));
                var j = UIKit.Text("JP", card, tr.jp, F ? F.jpHeavy : null, 40, on ? Palette.Paper : tr.accent, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(10, -95), new Vector2(520, 50));
                UIKit.Inked(j, 0.3f);
                UIKit.Text("Time", card, tr.timeOfDay, F ? F.hud : null, 28, on ? Palette.Ink : Palette.Cyan, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(10, -140), new Vector2(520, 40));
                var b = UIKit.Text("Blurb", card, tr.blurb, F ? F.comic : null, 26, on ? Palette.Ink : Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(10, 100), new Vector2(470, 130));
                b.textWrappingMode = TextWrappingModes.Normal;
                long best = GameSession.BestScore(tr.id);
                UIKit.Text("Best", card, best > 0 ? $"BEST {best:N0}" : "NO RECORD", F ? F.hud : null, 26, on ? Palette.Ink : Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(10, 30), new Vector2(470, 40));
            }
            sel = UIKit.Button("Race", C, "RACE!", "スタート", new Vector2(0.5f, 0), new Vector2(0, 120), new Vector2(420, 110), StartRace, Palette.Yellow);
            EventSystem.current.SetSelectedGameObject(sel.gameObject);
            Hint("◀ ▶ TRACK   ·   ENTER / A  RACE   ·   ESC / B  BACK");
        }

        void BuildSettings()
        {
            Header("SETTINGS", "設定", Palette.Lime);
            float y = 250;
            UnityEngine.UI.Button first = null;
            UnityEngine.UI.Button Row(string label, System.Func<string> value, System.Action cycle)
            {
                var b = UIKit.Button(label, C, label, null, new Vector2(0.5f, 0.5f), new Vector2(-260, y), new Vector2(520, 88), null, Palette.Paper);
                var v = UIKit.Text("Val", C, value(), F ? F.comic : null, 46, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(380, y), new Vector2(700, 80));
                UIKit.Inked(v, 0.3f);
                b.onClick.AddListener(() => { cycle(); v.text = value(); UISfx.Play("ui_move"); });
                y -= 110;
                first ??= b;
                return b;
            }
            string[] assist = { "PRO (no assists)", "STANDARD (counter-steer)", "EASY (counter-steer + stability)" };
            Row("ASSIST", () => assist[GameSession.AssistLevel], () => GameSession.AssistLevel = (GameSession.AssistLevel + 1) % 3);
            Row("GEARBOX", () => GameSession.Gearbox == Transmission.Automatic ? "AUTOMATIC" : "MANUAL (E/Q · RB/LB)", () => GameSession.Gearbox = GameSession.Gearbox == Transmission.Automatic ? Transmission.Manual : Transmission.Automatic);
            Row("QUALITY", () => QualitySettings.names[Mathf.Clamp(GameSession.Quality, 0, QualitySettings.names.Length - 1)].ToUpperInvariant(), () => GameSession.Quality = (GameSession.Quality + 1) % QualitySettings.names.Length);
            Row("MUSIC", () => Mathf.RoundToInt(GameSession.MusicVolume * 10) + " / 10", () => GameSession.MusicVolume = Mathf.Repeat(GameSession.MusicVolume + 0.1f, 1.05f));
            Row("VOICE", () => Mathf.RoundToInt(GameSession.VoiceVolume * 10) + " / 10", () => GameSession.VoiceVolume = Mathf.Repeat(GameSession.VoiceVolume + 0.1f, 1.05f));
            Row("FULLSCREEN", () => UnityEngine.Screen.fullScreen ? "ON" : "OFF", () => UnityEngine.Screen.fullScreen = !UnityEngine.Screen.fullScreen);
            var controls = UIKit.Text("Controls", C,
                "KEYBOARD  W/S throttle·brake  A/D steer  SPACE handbrake  SHIFT clutch  E/Q shift  C camera  R reset\nGAMEPAD  RT/LT throttle·brake  L-stick steer  A handbrake  X clutch  RB/LB shift  Y camera  View reset",
                F ? F.hudRegular : null, 24, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 120), new Vector2(1700, 80));
            controls.textWrappingMode = TextWrappingModes.Normal;
            EventSystem.current.SetSelectedGameObject(first.gameObject);
            Hint("ENTER / A  CHANGE   ·   ESC / B  BACK");
        }

        void StartRace()
        {
            UISfx.Play("ui_start");
            GameSession.Mode = pendingMode;
            GameSession.TrackId = TrackCatalog.All[trackIndex].id;
            PlayerPrefs.Save();
            screen = Screen.Loading;
            if (current) Destroy(current);
            current = UIKit.Stretch("Loading", root).gameObject;
            StartCoroutine(Load(TrackCatalog.All[trackIndex]));
        }

        static readonly string[] Tips =
        {
            "CLUTCH KICK: hold SHIFT/X, rev it, release mid-corner to snap the rear loose.",
            "Switching drift direction (manji / feint) bumps your multiplier.",
            "Within ~2 m of a wall while sliding = CLOSE! ×1.6. Touching it = 失敗.",
            "Lift the throttle to reduce angle, feed it to add angle. Steer where you want to GO.",
            "The handbrake kills rear grip instantly — tap it, don't hold it.",
            "Near-miss traffic on the Shuto for bonus points.",
        };

        IEnumerator Load(TrackInfo t)
        {
            var dim = current.AddComponent<Image>(); dim.color = Palette.Ink;
            var title = UIKit.Text("T", current.transform, t.name, F ? F.comic : null, 140, t.accent, TextAlignmentOptions.Center, new Vector2(0.5f, 0.62f), Vector2.zero, new Vector2(1700, 170));
            UIKit.Inked(title, 0.25f, Palette.Paper, new Vector2(1.5f, -1.5f));
            var jp = UIKit.Text("J", current.transform, t.jp, F ? F.jpHeavy : null, 80, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.48f), Vector2.zero, new Vector2(1600, 110));
            var tip = UIKit.Text("Tip", current.transform, "TIP · " + Tips[Random.Range(0, Tips.Length)], F ? F.comic : null, 38, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0.25f), Vector2.zero, new Vector2(1600, 120));
            tip.textWrappingMode = TextWrappingModes.Normal;
            var bar = UIKit.Img("Bar", current.transform, null, t.accent, new Vector2(0.5f, 0.15f), new Vector2(-600, 0), new Vector2(0, 20));
            bar.rectTransform.pivot = new Vector2(0, 0.5f);
            yield return null;
            var op = SceneManager.LoadSceneAsync(t.scene);
            while (!op.isDone)
            {
                bar.rectTransform.sizeDelta = new Vector2(1200f * Mathf.Clamp01(op.progress / 0.9f), 20);
                yield return null;
            }
        }
    }
}
