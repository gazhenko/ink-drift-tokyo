using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
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

        enum Screen { Title, Main, Car, Track, Settings, Controls, Loading, Online, Lobby }
        Screen screen;
        Canvas canvas;
        RectTransform root;
        GameObject current;
        GameObject displayCar;
        int carIndex, paintIndex, trackIndex;
        bool carForLobby;                      // the car screen was opened from the online lobby
        Net.LanDiscovery discovery;
        string onlineMessage;
        TMP_InputField joinField, nameField;
        float lanRefresh;
        int lanShown = -1;
        GameMode pendingMode = GameMode.DriftAttack;
        float camT;
        int screenFrame;
        TextMeshProUGUI hintText;
        System.Func<string> hintBuild;
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
            GameInput.EnsureEventSystem();
            GameInput.DeviceChanged += RefreshHint;
            carIndex = Mathf.Max(0, IndexOfCar(GameSession.CarId));
            if (CommandLine.Has("-menuCar")) carIndex = Mathf.Clamp((int)CommandLine.GetFloat("-menuCar", 0), 0, CarCatalog.All.Count - 1);
            paintIndex = GameSession.PaintIndex;
            MusicPlayer.Ensure().PlayMenuMusic();
            ShowDisplayCar();
            string dbg = CommandLine.Get("-menuScreen");
            // back from an online race: straight to the lobby; dropped from a session: the online screen with the reason
            if (Net.NetSession.Online) { Hook(); Go(Screen.Lobby); }
            else if (Net.NetSession.LastDisconnectReason != null) { onlineMessage = Net.NetSession.LastDisconnectReason; Net.NetSession.LastDisconnectReason = null; Go(Screen.Online); }
            else Go(dbg == "main" ? Screen.Main : dbg == "car" ? Screen.Car : dbg == "track" ? Screen.Track : dbg == "settings" ? Screen.Settings : dbg == "controls" ? Screen.Controls
                : dbg == "online" ? Screen.Online : dbg == "lobby" ? Screen.Lobby : Screen.Title);
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

        void OnDestroy()
        {
            GameInput.DeviceChanged -= RefreshHint;
            Unhook();
            discovery?.Dispose();
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

            // a session that started without this menu (or came back connected): show its lobby
            if (Net.NetSession.Online && (screen == Screen.Title || screen == Screen.Main || screen == Screen.Online) && Time.frameCount != screenFrame)
            { Hook(); Go(Screen.Lobby); return; }

            // one screen change per frame: a press that closed one screen must not also act on the next
            if (Time.frameCount == screenFrame || GameInput.Capturing) return;
            switch (screen)
            {
                case Screen.Title:
                    if (GameInput.Any.WasPressedThisFrame()) { UISfx.Play("ui_confirm"); Go(Screen.Main); }
                    break;
                case Screen.Car:
                    if (GameInput.NavLeft.WasPressedThisFrame()) ChangeCar(-1);
                    else if (GameInput.NavRight.WasPressedThisFrame()) ChangeCar(1);
                    else if (GameInput.NavUp.WasPressedThisFrame()) ChangePaint(-1);
                    else if (GameInput.NavDown.WasPressedThisFrame()) ChangePaint(1);
                    else if (GameInput.Back.WasPressedThisFrame()) Go(carForLobby && Net.NetSession.Online ? Screen.Lobby : Screen.Main);
                    break;
                case Screen.Track:
                    if (GameInput.NavLeft.WasPressedThisFrame()) { trackIndex = (trackIndex + TrackCatalog.All.Length - 1) % TrackCatalog.All.Length; Go(Screen.Track); }
                    else if (GameInput.NavRight.WasPressedThisFrame()) { trackIndex = (trackIndex + 1) % TrackCatalog.All.Length; Go(Screen.Track); }
                    else if (GameInput.Back.WasPressedThisFrame()) Go(Screen.Car);
                    break;
                case Screen.Settings:
                case Screen.Main:
                    if (GameInput.Back.WasPressedThisFrame()) Go(screen == Screen.Settings ? Screen.Main : Screen.Title);
                    break;
                case Screen.Online:
                    discovery?.Poll();
                    lanRefresh -= Time.unscaledDeltaTime;
                    if (lanRefresh <= 0f && discovery != null && discovery.Games.Count != lanShown && !Typing()) { lanRefresh = 0.5f; Go(Screen.Online); }
                    if (GameInput.Back.WasPressedThisFrame() && !Typing()) Go(Screen.Main);
                    break;
                case Screen.Lobby:
                    if (GameInput.Back.WasPressedThisFrame() && !Typing()) LeaveSession();
                    break;
            }
        }

        void Go(Screen s)
        {
            var from = screen;
            screen = s;
            screenFrame = Time.frameCount;
            hintText = null; hintBuild = null;
            if (current) Destroy(current);
            current = UIKit.Stretch(s.ToString(), root).gameObject;
            statFill = null; swatches.Clear();
            switch (s)
            {
                case Screen.Title: BuildTitle(); break;
                case Screen.Main: BuildMain(); break;
                case Screen.Car: BuildCar(); break;
                case Screen.Track: BuildTrack(); break;
                case Screen.Settings: BuildSettings(from == Screen.Controls); break;
                case Screen.Controls: ControlsScreen.Open(C, () => Go(Screen.Settings)); break;
                case Screen.Online: BuildOnline(); break;
                case Screen.Lobby: BuildLobby(); break;
            }
            if (s != Screen.Online && s != Screen.Lobby && s != Screen.Car) { discovery?.Dispose(); discovery = null; }
            if (s != Screen.Car && s != Screen.Lobby) carForLobby = false;
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

        /// <summary>Footer hint that re-labels itself when the player switches between keyboard and controller.</summary>
        void Hint(System.Func<string> build)
        {
            hintBuild = build;
            hintText = UIKit.Text("Hint", C, build(), F ? F.comic : null, 30, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 40), new Vector2(1600, 50));
            hintText.richText = true;
            UIKit.Inked(hintText, 0.3f);
        }

        void RefreshHint() { if (hintText && hintBuild != null) hintText.text = hintBuild(); }

        static string Pick => GameInput.UsingGamepad ? "D-PAD" : "↑↓";
        static string Ok => GameInput.ConfirmLabel;
        static string No => GameInput.BackLabel;

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
            string[] en = { "DRIFT ATTACK", "RIVAL BATTLE", "FREE RUN", "ONLINE", "SETTINGS", "QUIT" };
            string[] jp = { "ドリフトアタック", "ライバルバトル", "フリーラン", "オンライン", "設定", "終了" };
            Color[] cols = { Palette.Magenta, Palette.Cyan, Palette.Lime, Palette.Yellow, Palette.Paper, Palette.Paper };
            UnityEngine.UI.Button first = null;
            for (int i = 0; i < en.Length; i++)
            {
                int k = i;
                var b = UIKit.Button(en[i], C, en[i], jp[i], new Vector2(0, 0.5f), new Vector2(330 + i * 16, 280 - i * 108), new Vector2(560, 96), () => MainPick(k), cols[i]);
                if (i == 0) first = b;
            }
            var desc = UIKit.Text("Desc", C, "Chain drifts for points. Angle × speed × combo.\nClip the walls. Don't touch them.", F ? F.comic : null, 34, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(560, 150), new Vector2(900, 100));
            UIKit.Inked(desc, 0.3f);
            EventSystem.current.SetSelectedGameObject(first.gameObject);
            Hint(() => $"{Pick}  SELECT   ·   {Ok}  CONFIRM   ·   {No}  BACK");
        }

        void MainPick(int k)
        {
            UISfx.Play("ui_confirm");
            switch (k)
            {
                case 0: pendingMode = GameMode.DriftAttack; Go(Screen.Car); break;
                case 1: pendingMode = GameMode.Battle; Go(Screen.Car); break;
                case 2: pendingMode = GameMode.FreeRun; Go(Screen.Car); break;
                case 3: Go(Screen.Online); break;
                case 4: Go(Screen.Settings); break;
                case 5: Application.Quit(); break;
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
            var go = UIKit.Button("Go", C, "SELECT", "決定", new Vector2(1, 0), new Vector2(-300, 90), new Vector2(380, 104), () =>
            {
                UISfx.Play("ui_confirm");
                GameSession.CarId = CarCatalog.All[carIndex].id; GameSession.PaintIndex = paintIndex;
                if (carForLobby && Net.NetSession.Online) { PlayerPrefs.Save(); Net.NetSession.I.SendLobbyUpdate(); Go(Screen.Lobby); }
                else Go(Screen.Track);
            }, Palette.Yellow);
            var prev = UIKit.Button("Prev", C, "◀", null, new Vector2(0, 0.5f), new Vector2(110, -40), new Vector2(110, 110), () => ChangeCar(-1), Palette.Paper);
            var next = UIKit.Button("Next", C, "▶", null, new Vector2(0.5f, 0.5f), new Vector2(60, -40), new Vector2(110, 110), () => ChangeCar(1), Palette.Paper);
            // directions change car/paint here, so keep the selection on SELECT (arrows are for the mouse)
            foreach (var b in new[] { go, prev, next }) b.navigation = new Navigation { mode = Navigation.Mode.None };
            EventSystem.current.SetSelectedGameObject(go.gameObject);
            Hint(() => $"◀ ▶  CAR   ·   {(GameInput.UsingGamepad ? "▲▼" : "↑↓")}  PAINT   ·   {Ok}  SELECT   ·   {No}  BACK");
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
            Hint(() => $"◀ ▶  TRACK   ·   {Ok}  RACE   ·   {No}  BACK");
        }

        void BuildSettings(bool fromControls = false)
        {
            Header("SETTINGS", "設定", Palette.Lime);
            float y = 300;
            UnityEngine.UI.Button first = null;
            UnityEngine.UI.Button Row(string label, System.Func<string> value, System.Action cycle)
            {
                var b = UIKit.Button(label, C, label, null, new Vector2(0.5f, 0.5f), new Vector2(-260, y), new Vector2(520, 88), null, Palette.Paper);
                var v = UIKit.Text("Val", C, value(), F ? F.comic : null, 46, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(380, y), new Vector2(700, 80));
                UIKit.Inked(v, 0.3f);
                b.onClick.AddListener(() => { cycle(); if (v) v.text = value(); UISfx.Play("ui_move"); });
                y -= 92;
                first ??= b;
                return b;
            }
            var controlsRow = Row("CONTROLS", () => "KEYS · CONTROLLER  ▶", () => Go(Screen.Controls));
            string[] assist = { "PRO (no assists)", "STANDARD (counter-steer)", "EASY (counter-steer + stability)" };
            Row("ASSIST", () => assist[GameSession.AssistLevel], () => GameSession.AssistLevel = (GameSession.AssistLevel + 1) % 3);
            Row("CPU RIVALS", () => GameSession.DifficultyNames[GameSession.Difficulty], () => GameSession.Difficulty = (GameSession.Difficulty + 1) % 4);
            Row("GEARBOX", () => GameSession.Gearbox == Transmission.Automatic ? "AUTOMATIC" : $"MANUAL ({GameInput.Label(Bind.ShiftUp)} / {GameInput.Label(Bind.ShiftDown)})", () => GameSession.Gearbox = GameSession.Gearbox == Transmission.Automatic ? Transmission.Manual : Transmission.Automatic);
            Row("QUALITY", () => QualitySettings.names[Mathf.Clamp(GameSession.Quality, 0, QualitySettings.names.Length - 1)].ToUpperInvariant(), () => GameSession.Quality = (GameSession.Quality + 1) % QualitySettings.names.Length);
            Row("MUSIC", () => Mathf.RoundToInt(GameSession.MusicVolume * 10) + " / 10", () => GameSession.MusicVolume = Mathf.Repeat(GameSession.MusicVolume + 0.1f, 1.05f));
            Row("VOICE", () => Mathf.RoundToInt(GameSession.VoiceVolume * 10) + " / 10", () => GameSession.VoiceVolume = Mathf.Repeat(GameSession.VoiceVolume + 0.1f, 1.05f));
            Row("FULLSCREEN", () => UnityEngine.Screen.fullScreen ? "ON" : "OFF", () => UnityEngine.Screen.fullScreen = !UnityEngine.Screen.fullScreen);
            EventSystem.current.SetSelectedGameObject((fromControls ? controlsRow : first).gameObject);
            Hint(() => $"{Ok}  CHANGE   ·   {No}  BACK");
        }

        // ---------------------------------------------------------------- online
        bool Typing() => (joinField && joinField.isFocused) || (nameField && nameField.isFocused);

        void Hook()
        {
            var ns = Net.NetSession.I;
            if (ns == null) return;
            ns.Changed -= OnNetChanged; ns.Changed += OnNetChanged;
            ns.Disconnected -= OnNetDisconnected; ns.Disconnected += OnNetDisconnected;
        }

        void Unhook()
        {
            var ns = Net.NetSession.I;
            if (ns == null) return;
            ns.Changed -= OnNetChanged; ns.Disconnected -= OnNetDisconnected;
        }

        void OnNetChanged()
        {
            var ns = Net.NetSession.I;
            if (ns == null) return;
            if (ns.phase == Net.NetSession.Phase.Loading) { ShowLoadingFor(ns.TrackId); return; }
            if (screen == Screen.Online && ns.Connected) { Go(Screen.Lobby); return; }
            if (screen == Screen.Lobby && !Typing()) Go(Screen.Lobby);
        }

        void OnNetDisconnected(string reason)
        {
            onlineMessage = reason;
            if (screen == Screen.Lobby || screen == Screen.Online || screen == Screen.Car) Go(Screen.Online);
        }

        void LeaveSession()
        {
            Unhook();
            Net.NetSession.I?.Leave();
            onlineMessage = null;
            Go(Screen.Online);
        }

        void HostGame()
        {
            UISfx.Play("ui_confirm");
            SaveName();
            var ns = Net.NetSession.Host();
            if (ns == null || !ns.Connected) { onlineMessage = Net.NetSession.LastDisconnectReason ?? "Couldn't host a game."; Go(Screen.Online); return; }
            Hook();
            Go(Screen.Lobby);
        }

        void JoinGame(string address)
        {
            if (string.IsNullOrWhiteSpace(address)) { onlineMessage = "Type your friend's room code first."; Go(Screen.Online); return; }
            UISfx.Play("ui_confirm");
            SaveName();
            PlayerPrefs.SetString("mp_last_join", address.Trim());
            var ns = Net.NetSession.Join(address);
            if (ns != null && ns) { Hook(); onlineMessage = null; }
            else onlineMessage = Net.NetSession.LastDisconnectReason;
            Go(Screen.Online);
        }

        void SaveName() { if (nameField) Net.NetSession.PlayerName = nameField.text; PlayerPrefs.Save(); }

        void BuildOnline()
        {
            Header("ONLINE", "オンライン · 友達とレース", Palette.Yellow);
            discovery ??= new Net.LanDiscovery();
            var ns = Net.NetSession.I;
            bool connecting = ns != null && !ns.Connected && !ns.IsHost;

            UIKit.Text("NameL", C, "YOUR NAME", F ? F.comic : null, 36, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(330, 250), new Vector2(560, 50));
            nameField = UIKit.InputField("Name", C, Net.NetSession.PlayerName, "DRIVER", new Vector2(0, 0.5f), new Vector2(390, 190), new Vector2(620, 80), 16);
            nameField.onEndEdit.AddListener(v => { Net.NetSession.PlayerName = v; PlayerPrefs.Save(); });

            var host = UIKit.Button("Host", C, "HOST GAME", "ホスト", new Vector2(0, 0.5f), new Vector2(390, 60), new Vector2(620, 104), HostGame, Palette.Magenta);

            UIKit.Text("JoinL", C, "JOIN A FRIEND · their room code", F ? F.comic : null, 32, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(430, -60), new Vector2(640, 50));
            joinField = UIKit.InputField("JoinCode", C, PlayerPrefs.GetString("mp_last_join", ""), "K7Q-4MZ", new Vector2(0, 0.5f), new Vector2(390, -125), new Vector2(620, 80), 64);
            joinField.onSubmit.AddListener(JoinGame);
            UIKit.Button("Paste", C, "PASTE", null, new Vector2(0, 0.5f), new Vector2(235, -230), new Vector2(300, 84), () => { joinField.text = GUIUtility.systemCopyBuffer?.Trim() ?? ""; }, Palette.Paper);
            UIKit.Button("Join", C, connecting ? "JOINING…" : "JOIN", "参加", new Vector2(0, 0.5f), new Vector2(550, -230), new Vector2(300, 84), () => JoinGame(joinField.text), Palette.Cyan);
            UIKit.Button("Back", C, "BACK", "戻る", new Vector2(0, 0.5f), new Vector2(390, -340), new Vector2(620, 84), () => { if (connecting) Net.NetSession.I?.Leave(); Go(Screen.Main); }, Palette.Paper);

            // games on this network
            var panel = UIKit.Rect("Lan", C, new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(-60, 20), new Vector2(760, 640));
            var sp = panel.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Ink.WithA(0.88f); sp.borderColor = Palette.Paper; sp.border = 5; sp.slant = 20; sp.raycastTarget = false;
            UIKit.Text("LanT", panel, "GAMES ON YOUR NETWORK", F ? F.comic : null, 44, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -55), new Vector2(720, 60));
            var games = discovery.Games;
            lanShown = games.Count;
            UnityEngine.UI.Button firstGame = null;
            if (games.Count == 0)
                UIKit.Text("None", panel, "Looking for games…\nWhen a friend on the same Wi-Fi hosts, it shows up here.", F ? F.comic : null, 30, Palette.Paper.WithA(0.75f), TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 20), new Vector2(680, 200)).textWrappingMode = TextWrappingModes.Normal;
            for (int i = 0; i < games.Count && i < 4; i++)
            {
                var g = games[i];
                string addr = g.ep.Address.Equals(System.Net.IPAddress.Loopback) ? "this computer" : g.ep.Address.ToString();
                string label = $"{g.host}  ·  {g.players}/{g.max}";
                var ep = g.ep;
                var b = UIKit.Button("Game" + i, panel, label, $"{TrackCatalog.Get(g.track).name}  ·  {(g.phase > 1 ? "racing now" : addr)}", new Vector2(0.5f, 1), new Vector2(0, -160 - i * 112), new Vector2(680, 100), () => JoinGame(ep.Address + ":" + ep.Port), Palette.Lime);
                firstGame ??= b;
            }
            if (!string.IsNullOrEmpty(onlineMessage) || connecting)
            {
                var msg = UIKit.Text("Msg", C, connecting ? ns.Status : onlineMessage, F ? F.comic : null, 32, connecting ? Palette.Cyan : Palette.Red, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 120), new Vector2(1700, 90));
                msg.textWrappingMode = TextWrappingModes.Normal;
                UIKit.Inked(msg, 0.3f);
            }
            var cur = EventSystem.current.currentSelectedGameObject;
            if (cur == null || !cur.activeInHierarchy) EventSystem.current.SetSelectedGameObject((firstGame ? firstGame : host).gameObject);
            Hint(() => $"{Ok}  SELECT   ·   {No}  BACK   ·   type a code with the keyboard");
        }

        void BuildLobby()
        {
            var ns = Net.NetSession.I;
            if (ns == null || !ns.Connected) { onlineMessage = Net.NetSession.LastDisconnectReason; BuildOnline(); screen = Screen.Online; return; }
            Hook();
            Header("LOBBY", ns.IsHost ? "ロビー · あなたがホスト" : "ロビー", Palette.Cyan);

            // players
            var list = UIKit.Rect("Players", C, new Vector2(0, 0.5f), new Vector2(0, 0.5f), new Vector2(0, 0.5f), new Vector2(60, 40), new Vector2(820, 600));
            var sp = list.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Ink.WithA(0.88f); sp.borderColor = Palette.Paper; sp.border = 5; sp.slant = 20; sp.raycastTarget = false;
            UIKit.Text("PT", list, $"DRIVERS  {ns.Players.Count}/{Net.NetSession.MaxPlayers}", F ? F.comic : null, 44, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(330, -55), new Vector2(560, 60));
            for (int i = 0; i < ns.Players.Count; i++)
            {
                var p = ns.Players[i];
                bool me = p.id == ns.LocalId;
                string status = p.id == 0 ? "HOST" : !p.inLobby ? "RESULTS" : p.ready ? "READY" : "…";
                UIKit.Text("P" + i, list, $"{p.name}{(me ? "  (YOU)" : "")}", F ? F.hud : null, 36, me ? Palette.Magenta : Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(330, -125 - i * 60), new Vector2(560, 50));
                UIKit.Text("C" + i, list, CarCatalog.Get(p.carId).displayName, F ? F.hudRegular : null, 26, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(690, -125 - i * 60), new Vector2(300, 50));
                UIKit.Text("S" + i, list, me || p.id == 0 ? status : $"{status}  {p.ping}ms", F ? F.hudRegular : null, 26, p.ready || p.id == 0 ? Palette.Lime : Palette.Paper.WithA(0.6f), TextAlignmentOptions.Right, new Vector2(1, 1), new Vector2(-150, -125 - i * 60), new Vector2(260, 50));
            }

            // race settings + invite
            var info = UIKit.Rect("Info", C, new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(1, 0.5f), new Vector2(-60, 40), new Vector2(880, 600));
            var ip = info.gameObject.AddComponent<SlantPanel>(); ip.color = Palette.Ink.WithA(0.88f); ip.borderColor = Palette.Paper; ip.border = 5; ip.slant = 20; ip.raycastTarget = false;
            var track = TrackCatalog.Get(ns.TrackId);
            UIKit.Text("TrackL", info, "TRACK", F ? F.comic : null, 30, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(330, -50), new Vector2(560, 44));
            var tn = UIKit.Text("Track", info, $"{track.name}  {track.jp}", F ? F.comic : null, 46, track.accent, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(390, -100), new Vector2(680, 60));
            UIKit.Inked(tn, 0.25f);
            UIKit.Text("Laps", info, $"{ns.Laps} LAPS  ·  {track.timeOfDay}", F ? F.hud : null, 30, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(390, -150), new Vector2(680, 44));
            if (ns.IsHost)
            {
                int ti = System.Array.FindIndex(TrackCatalog.All, t => t.id == ns.TrackId);
                UIKit.Button("TrackPrev", info, "◀", null, new Vector2(1, 1), new Vector2(-170, -100), new Vector2(80, 70), () => ns.SetTrack(TrackCatalog.All[(ti + TrackCatalog.All.Length - 1) % TrackCatalog.All.Length].id), Palette.Paper);
                UIKit.Button("TrackNext", info, "▶", null, new Vector2(1, 1), new Vector2(-80, -100), new Vector2(80, 70), () => ns.SetTrack(TrackCatalog.All[(ti + 1) % TrackCatalog.All.Length].id), Palette.Paper);
                UIKit.Button("LapsDown", info, "−", null, new Vector2(1, 1), new Vector2(-170, -175), new Vector2(80, 60), () => ns.SetLaps(ns.Laps - 1), Palette.Paper);
                UIKit.Button("LapsUp", info, "+", null, new Vector2(1, 1), new Vector2(-80, -175), new Vector2(80, 60), () => ns.SetLaps(ns.Laps + 1), Palette.Paper);

                // the room code works from anywhere; the direct invite code is only the fallback when the relay is unreachable
                bool room = ns.RoomCode != null, pending = !room && ns.RelayPending;
                string shown = room ? ns.RoomCode : pending ? "…" : ns.InviteCode ?? "…";
                string lan = ns.LanAddresses.Count > 0 ? string.Join("  ", ns.LanAddresses) : "-";
                string label = room || pending ? "ROOM CODE · send it to your friends" : "INVITE CODE · direct connection";
                string detail = room ? "Friends type it under ONLINE → JOIN, from any network. No router setup needed.\nFriends on your Wi-Fi also see your game in their list."
                    : pending ? "Getting a room code from the online service…"
                    : $"{ns.RelayStatus}\nSame network: {lan}  ·  port {ns.Port}\n{ns.PortStatus}";
                UIKit.Text("InvL", info, label, F ? F.comic : null, 28, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(390, -240), new Vector2(680, 44));
                var code = UIKit.Text("Code", info, shown, F ? F.hud : null, room ? 80 : 64, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(390, -305), new Vector2(680, 90));
                UIKit.Inked(code, 0.25f);
                if (room || !pending)
                    UIKit.Button("Copy", info, "COPY", null, new Vector2(1, 1), new Vector2(-125, -305), new Vector2(170, 70), () => { GUIUtility.systemCopyBuffer = shown; UISfx.Play("ui_confirm"); }, Palette.Yellow);
                var det = UIKit.Text("Det", info, detail, F ? F.hudRegular : null, 24, Palette.Paper.WithA(0.85f), TextAlignmentOptions.TopLeft, new Vector2(0, 1), new Vector2(430, -420), new Vector2(780, 160));
                det.textWrappingMode = TextWrappingModes.Normal;
            }
            else
            {
                var w = UIKit.Text("Wait", info, "The host picks the track and starts the race.\nPick your car and press READY.", F ? F.comic : null, 32, Palette.Paper.WithA(0.85f), TextAlignmentOptions.TopLeft, new Vector2(0, 1), new Vector2(430, -260), new Vector2(780, 160));
                w.textWrappingMode = TextWrappingModes.Normal;
            }

            // actions
            var me2 = ns.Local;
            UnityEngine.UI.Button main;
            if (ns.IsHost)
            {
                bool can = ns.CanStart(out string why);
                main = UIKit.Button("Start", C, "START RACE", "スタート", new Vector2(0.5f, 0), new Vector2(330, 110), new Vector2(460, 110), () => { if (ns.CanStart(out _)) { UISfx.Play("ui_start"); ns.StartRace(); } }, can ? Palette.Yellow : Palette.Paper.WithA(0.5f));
                if (!can) UIKit.Text("Why", C, why, F ? F.comic : null, 28, Palette.Red, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(330, 185), new Vector2(800, 40));
            }
            else
            {
                bool ready = me2 != null && me2.ready;
                main = UIKit.Button("Ready", C, ready ? "READY ✓" : "READY", "準備OK", new Vector2(0.5f, 0), new Vector2(330, 110), new Vector2(460, 110), () => ns.SetReady(!(ns.Local != null && ns.Local.ready)), ready ? Palette.Lime : Palette.Yellow);
            }
            UIKit.Button("Car", C, "CHANGE CAR", "車を変更", new Vector2(0.5f, 0), new Vector2(-170, 110), new Vector2(460, 110), () => { carForLobby = true; carIndex = Mathf.Max(0, IndexOfCar(GameSession.CarId)); paintIndex = GameSession.PaintIndex; ShowDisplayCar(); Go(Screen.Car); }, Palette.Magenta);
            UIKit.Button("LeaveL", C, "LEAVE", "退出", new Vector2(0.5f, 0), new Vector2(-620, 110), new Vector2(340, 110), LeaveSession, Palette.Paper);
            if (!string.IsNullOrEmpty(ns.Status) && (ns.Status.Contains(" left") || ns.Status.Contains("timed out")))
                UIKit.Text("Status", C, ns.Status, F ? F.comic : null, 28, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(-400, 190), new Vector2(900, 40));
            EventSystem.current.SetSelectedGameObject(main.gameObject);
            Hint(() => $"{Ok}  SELECT   ·   {No}  LEAVE");
        }

        void ShowLoadingFor(string trackId)
        {
            if (screen == Screen.Loading) return;
            screen = Screen.Loading;
            if (current) Destroy(current);
            current = UIKit.Stretch("Loading", root).gameObject;
            var t = TrackCatalog.Get(trackId);
            var dim = current.AddComponent<Image>(); dim.color = Palette.Ink;
            var title = UIKit.Text("T", current.transform, t.name, F ? F.comic : null, 140, t.accent, TextAlignmentOptions.Center, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(1700, 170));
            UIKit.Inked(title, 0.25f, Palette.Paper, new Vector2(1.5f, -1.5f));
            UIKit.Text("J", current.transform, "ONLINE RACE · " + t.jp, F ? F.jpHeavy : null, 64, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.46f), Vector2.zero, new Vector2(1600, 100));
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
            "CLUTCH KICK: hold {clutch}, rev it, release mid-corner to snap the rear loose.",
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
            string tipText = Tips[Random.Range(0, Tips.Length)].Replace("{clutch}", GameInput.Label(Bind.Clutch)).Replace("{handbrake}", GameInput.Label(Bind.Handbrake));
            var tip = UIKit.Text("Tip", current.transform, "TIP · " + tipText, F ? F.comic : null, 38, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0.25f), Vector2.zero, new Vector2(1600, 120));
            tip.richText = true;
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
