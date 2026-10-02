using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>
    /// Controls screen (main menu Settings and the pause menu): rebind every driving control for keyboard (two keys)
    /// and controller, live input test, controller options, and Controller Setup for unrecognised controllers.
    /// </summary>
    public class ControlsScreen : MonoBehaviour
    {
        public static bool IsOpen => openCount > 0;
        static int openCount;

        Action onClose;
        readonly Dictionary<GameObject, (Bind bind, Slot slot)> cells = new Dictionary<GameObject, (Bind, Slot)>();
        readonly Dictionary<(Bind, Slot), TextMeshProUGUI> cellText = new Dictionary<(Bind, Slot), TextMeshProUGUI>();
        TextMeshProUGUI deviceName, deviceNote, notice, hint, labelsVal, rumbleVal, deadVal, curveVal;
        RectTransform steerFill, throttleFill, brakeFill, clutchFill;
        readonly List<(Image img, Func<bool> on)> lights = new List<(Image, Func<bool>)>();
        GameObject undoSetup;
        PadSetupWizard wizard;
        float noticeUntil, refreshT;
        bool rebinding;

        static FontSet F => FontSet.I;

        public static ControlsScreen Open(Transform parent, Action onClose)
        {
            GameInput.EnsureEventSystem();
            var rt = UIKit.Stretch("Controls", parent);
            var cs = rt.gameObject.AddComponent<ControlsScreen>();
            cs.onClose = onClose;
            cs.Build();
            return cs;
        }

        void OnEnable() { openCount++; GameInput.DeviceChanged += OnDevice; GameInput.BindingsChanged += RefreshCells; }
        void OnDisable() { openCount--; GameInput.DeviceChanged -= OnDevice; GameInput.BindingsChanged -= RefreshCells; }

        void OnDevice() { RefreshCells(); RefreshDevice(); RefreshHint(); }

        // ------------------------------------------------------------------ layout

        void Build()
        {
            var dim = gameObject.AddComponent<Image>();
            dim.color = Palette.Ink.WithA(0.78f);

            var head = UIKit.Rect("Header", transform, new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(60, -40), new Vector2(900, 130));
            var hp = head.gameObject.AddComponent<SlantPanel>(); hp.color = Palette.Lime; hp.slant = 30; hp.raycastTarget = false;
            UIKit.Text("EN", head, "CONTROLS", F ? F.comic : null, 84, Palette.Ink, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(460, 14), new Vector2(820, 100));
            var jp = UIKit.Text("JP", head, "操作設定 · キーとボタンの割り当て", F ? F.jpHeavy : null, 30, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 0.5f), new Vector2(460, -42), new Vector2(820, 40));
            UIKit.Inked(jp, 0.25f);

            BuildTable();
            BuildSidePanel();

            notice = UIKit.Text("Notice", transform, "", F ? F.comic : null, 32, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(-250, 100), new Vector2(1250, 44));
            UIKit.Inked(notice, 0.3f);
            hint = UIKit.Text("Hint", transform, "", F ? F.comic : null, 30, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 40), new Vector2(1800, 50));
            UIKit.Inked(hint, 0.3f);

            RefreshCells();
            RefreshDevice();
            RefreshOptions();
            RefreshHint();
            var first = cellText[(Bind.Throttle, GameInput.UsingGamepad ? Slot.Pad : Slot.Key1)].transform.parent.gameObject;
            EventSystem.current?.SetSelectedGameObject(first);
            if (CommandLine.Has("-openSetup")) Invoke(nameof(OpenWizard), 1.5f);   // dev: screenshot the setup overlay
        }

        void BuildTable()
        {
            var p = UIKit.Rect("Table", transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-250, -48), new Vector2(1250, 770));
            var sp = p.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Ink.WithA(0.9f); sp.borderColor = Palette.Paper; sp.border = 5; sp.slant = 16; sp.raycastTarget = false;
            float[] colX = { -95, 145, 425 };
            string[] colName = { "KEY 1", "KEY 2", "CONTROLLER" };
            for (int c = 0; c < 3; c++)
                UIKit.Text("Col" + c, p, colName[c], F ? F.hud : null, 26, Palette.Cyan, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(colX[c], 335), new Vector2(260, 36));
            UIKit.Text("ColL", p, "CONTROL", F ? F.hud : null, 26, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(-370, 335), new Vector2(380, 36));

            for (int i = 0; i < GameInput.BindNames.Length; i++)
            {
                var b = (Bind)i;
                float y = 282 - i * 53;
                UIKit.Text("L" + i, p, GameInput.BindNames[i], F ? F.comic : null, 31, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(-370, y + 7), new Vector2(380, 34));
                UIKit.Text("J" + i, p, GameInput.BindJp[i], F ? F.jpBody : null, 15, Palette.Paper.WithA(0.6f), TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(-370, y - 16), new Vector2(380, 20));
                for (int c = 0; c < 3; c++)
                {
                    var slot = (Slot)c;
                    var btn = UIKit.Button($"Cell{i}_{c}", p, "", null, new Vector2(0.5f, 0.5f), new Vector2(colX[c], y), new Vector2(c == 2 ? 300 : 230, 46),
                        () => Rebind(b, slot), c == 2 ? Palette.Cyan : Palette.Paper);
                    cells[btn.gameObject] = (b, slot);
                    var t = btn.transform.Find("Label").GetComponent<TextMeshProUGUI>();
                    t.richText = true;
                    t.font = F ? F.hud : t.font;
                    t.fontSize = 24;
                    cellText[(b, slot)] = t;
                }
            }
        }

        void BuildSidePanel()
        {
            var p = UIKit.Rect("Side", transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(660, -48), new Vector2(540, 770));
            var sp = p.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Ink.WithA(0.9f); sp.borderColor = Palette.Paper; sp.border = 5; sp.slant = 16; sp.raycastTarget = false;

            UIKit.Text("DevT", p, "CONTROLLER · コントローラー", F ? F.hud : null, 24, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(0, 345), new Vector2(460, 32));
            deviceName = UIKit.Text("Dev", p, "", F ? F.comic : null, 34, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(0, 308), new Vector2(460, 40));
            deviceName.overflowMode = TextOverflowModes.Ellipsis;
            deviceNote = UIKit.Text("DevN", p, "", F ? F.hudRegular : null, 18, Palette.Paper.WithA(0.75f), TextAlignmentOptions.TopLeft, new Vector2(0.5f, 0.5f), new Vector2(0, 248), new Vector2(460, 66));
            deviceNote.textWrappingMode = TextWrappingModes.Normal;

            UIKit.Text("TestT", p, "INPUT TEST · 入力テスト", F ? F.hud : null, 24, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(0, 190), new Vector2(460, 32));
            steerFill = Bar(p, "STEER", 152, true);
            throttleFill = Bar(p, "THROTTLE", 122, false);
            brakeFill = Bar(p, "BRAKE", 92, false);
            clutchFill = Bar(p, "CLUTCH", 62, false);
            string[] names = { "HB", "▲", "▼", "CAM", "LOOK", "RESET", "PAUSE" };
            Func<bool>[] tests =
            {
                () => GameInput.Handbrake.ReadValue<float>() > 0.5f, () => GameInput.ShiftUp.IsPressed(), () => GameInput.ShiftDown.IsPressed(),
                () => GameInput.CameraCycle.IsPressed(), () => GameInput.LookBack.ReadValue<float>() > 0.5f, () => GameInput.ResetCar.IsPressed(), () => GameInput.Pause.IsPressed(),
            };
            for (int i = 0; i < names.Length; i++)
            {
                var img = UIKit.Img("Light" + i, p, null, Palette.Paper.WithA(0.15f), new Vector2(0.5f, 0.5f), new Vector2(-198 + i * 66, 20), new Vector2(60, 34));
                UIKit.Text("T", img.transform, names[i], F ? F.hud : null, 17, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(60, 34));
                lights.Add((img, tests[i]));
            }

            labelsVal = Option(p, "BUTTON LABELS", -38, () => { GameSession.PadLabels = (GameSession.PadLabels + 1) % 4; RefreshCells(); RefreshHint(); RefreshDevice(); });
            rumbleVal = Option(p, "VIBRATION", -96, () => { GameSession.Vibration = !GameSession.Vibration; if (GameSession.Vibration) GameInput.Impulse(0.6f, 0.6f, 0.25f); });
            deadVal = Option(p, "STICK DEAD ZONE", -154, () =>
            {
                float[] z = { 0.05f, 0.1f, 0.15f, 0.2f, 0.25f };
                GameSession.StickDeadzone = z[(Array.IndexOf(z, Nearest(z, GameSession.StickDeadzone)) + 1) % z.Length];
            });
            curveVal = Option(p, "STEER RESPONSE", -212, () =>
            {
                float[] c = { 1f, 1.35f, 1.7f };
                GameSession.SteerResponse = c[(Array.IndexOf(c, Nearest(c, GameSession.SteerResponse)) + 1) % c.Length];
            });

            UIKit.Button("Setup", p, "SET UP CONTROLLER", null, new Vector2(0.5f, 0.5f), new Vector2(-70, -282), new Vector2(330, 60), OpenWizard, Palette.Magenta);
            undoSetup = UIKit.Button("Undo", p, "UNDO SETUP", null, new Vector2(0.5f, 0.5f), new Vector2(170, -282), new Vector2(150, 60), UndoSetup, Palette.Paper).gameObject;
            UIKit.Button("ResetAll", p, "RESET ALL", null, new Vector2(0.5f, 0.5f), new Vector2(-115, -347), new Vector2(240, 60), () =>
            {
                GameInput.ResetAllBindings();
                Notice("All controls reset to default · 初期設定に戻しました");
                UISfx.Play("ui_confirm");
            }, Palette.Paper);
            UIKit.Button("Back", p, "BACK", "戻る", new Vector2(0.5f, 0.5f), new Vector2(125, -347), new Vector2(220, 60), Close, Palette.Yellow);
        }

        RectTransform Bar(Transform p, string label, float y, bool centered)
        {
            UIKit.Text("BL" + label, p, label, F ? F.hud : null, 19, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0.5f, 0.5f), new Vector2(-150, y), new Vector2(160, 26));
            var bg = UIKit.Img("Bg" + label, p, null, Palette.Paper.WithA(0.15f), new Vector2(0.5f, 0.5f), new Vector2(75, y), new Vector2(310, 16));
            var fill = UIKit.Img("Fill", bg.transform, null, centered ? Palette.Cyan : Palette.Yellow, new Vector2(centered ? 0.5f : 0f, 0.5f), Vector2.zero, new Vector2(0, 16));
            fill.rectTransform.pivot = new Vector2(centered ? 0.5f : 0f, 0.5f);
            if (centered) UIKit.Img("Mid", bg.transform, null, Palette.Paper, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(2, 22));
            return fill.rectTransform;
        }

        TextMeshProUGUI Option(Transform p, string label, float y, Action change)
        {
            TextMeshProUGUI val = null;
            UIKit.Button("Opt" + label, p, "", null, new Vector2(0.5f, 0.5f), new Vector2(0, y), new Vector2(470, 52), () => { change(); RefreshOptions(); UISfx.Play("ui_move"); }, Palette.Paper);
            var btn = p.Find("Opt" + label);
            var l = btn.Find("Label").GetComponent<TextMeshProUGUI>();
            l.text = label; l.fontSize = 26; l.alignment = TextAlignmentOptions.Left;
            l.rectTransform.sizeDelta = new Vector2(420, 52);
            val = UIKit.Text("Val", btn, "", F ? F.hud : null, 24, Palette.Magenta, TextAlignmentOptions.Right, new Vector2(0.5f, 0.5f), new Vector2(-8, 0), new Vector2(420, 52));
            return val;
        }

        static float Nearest(float[] arr, float v)
        {
            float best = arr[0];
            foreach (var a in arr) if (Mathf.Abs(a - v) < Mathf.Abs(best - v)) best = a;
            return best;
        }

        // ------------------------------------------------------------------ refresh

        void RefreshCells()
        {
            foreach (var kv in cellText)
            {
                if (rebinding && kv.Value.text.StartsWith("PRESS")) continue;
                kv.Value.text = GameInput.Label(kv.Key.Item1, kv.Key.Item2, color: false);
            }
        }

        void RefreshOptions()
        {
            string auto = $"AUTO ({GameInput.StyleName(GameInput.StyleOf(GameInput.ActivePad == null ? null : GameInput.ActivePad))})";
            labelsVal.text = GameSession.PadLabels == 0 ? auto : GameInput.StyleName((PadStyle)(GameSession.PadLabels - 1));
            rumbleVal.text = GameSession.Vibration ? "ON" : "OFF";
            deadVal.text = Mathf.RoundToInt(GameSession.StickDeadzone * 100f) + "%";
            float c = GameSession.SteerResponse;
            curveVal.text = c < 1.1f ? "LINEAR" : c < 1.5f ? "SMOOTH" : "SOFT";
        }

        void RefreshDevice()
        {
            var pad = GameInput.ActivePad;
            var all = PadBridge.PhysicalControllers();
            bool anyCustom = false;
            foreach (var d in all) if (PadBridge.HasCustomMapping(d)) anyCustom = true;
            if (undoSetup) undoSetup.SetActive(anyCustom);
            if (pad != null)
            {
                var src = PadBridge.SourceOf(pad);
                deviceName.text = (src ?? pad).displayName.ToUpperInvariant();
                string labels = GameInput.StyleName(GameInput.Style);
                if (src == null) deviceNote.text = $"Recognised gamepad · {labels} buttons" + (GameInput.UsingGamepad ? "" : " · press a button to switch to it");
                else if (PadBridge.HasCustomMapping(src)) deviceNote.text = $"Using your Controller Setup · {labels} buttons";
                else deviceNote.text = $"Generic controller, default layout · {labels} buttons. Buttons wrong? Use SET UP CONTROLLER.";
            }
            else if (all.Count > 0)
            {
                deviceName.text = all[0].displayName.ToUpperInvariant();
                deviceNote.text = "Connected. Press a button or move a stick on it to use it.";
            }
            else
            {
                deviceName.text = "KEYBOARD";
                deviceNote.text = "No controller detected. Connect any Xbox, PlayStation, Switch Pro or generic USB / Bluetooth pad.";
            }
            RefreshOptions();
        }

        void RefreshHint()
        {
            if (hint == null) return;
            if (GameInput.UsingGamepad)
            {
                var st = GameInput.Style;
                hint.text = $"{GameInput.PadLabel("buttonSouth", st)} CHANGE   ·   {GameInput.PadLabel("buttonWest", st)} CLEAR   ·   {GameInput.PadLabel("buttonNorth", st)} DEFAULT   ·   {GameInput.PadLabel("buttonEast", st)} BACK";
            }
            else hint.text = "ENTER / CLICK  CHANGE   ·   DEL  CLEAR   ·   HOME  DEFAULT   ·   ESC  BACK";
        }

        void Notice(string text, float seconds = 3.5f)
        {
            notice.text = text;
            noticeUntil = Time.unscaledTime + seconds;
        }

        // ------------------------------------------------------------------ actions

        void Rebind(Bind b, Slot s)
        {
            if (GameInput.Capturing || wizard != null) return;
            rebinding = true;
            UISfx.Play("ui_confirm");
            var t = cellText[(b, s)];
            t.text = "PRESS…";
            Notice(s == Slot.Pad
                ? $"PRESS A BUTTON, TRIGGER OR STICK FOR {GameInput.BindNames[(int)b]}  ·  wait 8 s to cancel"
                : $"PRESS A KEY FOR {GameInput.BindNames[(int)b]}  ·  ESC cancels", 9f);
            GameInput.StartRebind(b, s, ok =>
            {
                rebinding = false;
                RefreshCells();
                if (!ok) Notice("Cancelled · キャンセル", 1.5f);
                else if (GameInput.LastConflict != null) Notice($"{GameInput.Label(b, s)} was also on {GameInput.LastConflict} — removed it there");
                else { Notice($"{GameInput.BindNames[(int)b]} → {GameInput.Label(b, s)}", 2f); UISfx.Play("ui_confirm"); }
            });
        }

        void OpenWizard()
        {
            if (GameInput.Capturing || wizard != null) return;
            UISfx.Play("ui_confirm");
            wizard = PadSetupWizard.Open(transform, ok =>
            {
                wizard = null;
                RefreshDevice(); RefreshCells(); RefreshHint();
                Notice(ok ? "Controller set up! Try it in INPUT TEST · 設定完了" : "Controller setup cancelled", 3f);
                var setup = transform.Find("Side/Setup");
                if (setup) EventSystem.current?.SetSelectedGameObject(setup.gameObject);
            });
        }

        void UndoSetup()
        {
            foreach (var d in PadBridge.PhysicalControllers()) if (PadBridge.HasCustomMapping(d)) PadBridge.Forget(d);
            RefreshDevice();
            Notice("Controller setup removed — back to the default layout");
            var setup = transform.Find("Side/Setup");
            if (setup) EventSystem.current?.SetSelectedGameObject(setup.gameObject);
        }

        void Close()
        {
            if (GameInput.Capturing || wizard != null) return;
            UISfx.Play("ui_move");
            PlayerPrefs.Save();
            var cb = onClose;
            Destroy(gameObject);
            cb?.Invoke();
        }

        void Update()
        {
            // live input test
            float steer = GameInput.Steer.ReadValue<float>();
            steerFill.anchoredPosition = new Vector2(steer * 155f * 0.5f, 0f);
            steerFill.sizeDelta = new Vector2(Mathf.Abs(steer) * 155f, 16f);
            throttleFill.sizeDelta = new Vector2(310f * GameInput.Throttle.ReadValue<float>(), 16f);
            brakeFill.sizeDelta = new Vector2(310f * GameInput.Brake.ReadValue<float>(), 16f);
            clutchFill.sizeDelta = new Vector2(310f * GameInput.Clutch.ReadValue<float>(), 16f);
            foreach (var (img, on) in lights) img.color = on() ? Palette.Yellow : Palette.Paper.WithA(0.15f);

            if (Time.unscaledTime > noticeUntil && notice.text.Length > 0 && !rebinding) notice.text = "";
            if ((refreshT += Time.unscaledDeltaTime) > 0.5f) { refreshT = 0f; RefreshDevice(); }

            if (GameInput.Capturing || wizard != null) return;
            if (GameInput.Back.WasPressedThisFrame()) { Close(); return; }
            var sel = EventSystem.current ? EventSystem.current.currentSelectedGameObject : null;
            if (sel != null && cells.TryGetValue(sel, out var cell))
            {
                if (GameInput.Clear.WasPressedThisFrame()) { GameInput.ClearBinding(cell.bind, cell.slot); UISfx.Play("ui_move"); }
                else if (GameInput.Default.WasPressedThisFrame())
                {
                    GameInput.ResetBinding(cell.bind, cell.slot);
                    UISfx.Play("ui_move");
                    if (GameInput.LastConflict != null) Notice($"Default restored — removed it from {GameInput.LastConflict}");
                }
            }
        }
    }
}
