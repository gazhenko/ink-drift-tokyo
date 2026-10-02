using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>
    /// Controller Setup: records which physical button/axis of a controller is which standard gamepad input
    /// (Xbox positions), then hands the layout to <see cref="PadBridge"/>. Works for any controller Unity can see,
    /// including generic DirectInput pads, unrecognised Bluetooth pads and wheels. Keyboard: TAB skip, BACKSPACE back, ESC cancel.
    /// </summary>
    public class PadSetupWizard : MonoBehaviour
    {
        struct Step { public PadTarget target; public string text; public string glyph; }

        enum Phase { ChooseDevice, WaitRelease, WaitPress, Hold, Done }

        Action<bool> done;
        Phase phase;
        List<InputDevice> candidates;
        InputDevice device;
        List<InputControl> controls;
        float[] rest;
        List<List<InputControl>> candControls;
        List<float[]> candRest;
        Step[] steps;
        int step;
        InputControl hit;
        float hitBase, peak, holdT, doneT;
        readonly Dictionary<int, PadMapEntry> recorded = new Dictionary<int, PadMapEntry>();
        TextMeshProUGUI deviceText, prompt, glyph, progress, status;
        RectTransform progressFill;
        PadStyle style;

        static FontSet F => FontSet.I;

        public static PadSetupWizard Open(Transform parent, Action<bool> done)
        {
            var rt = UIKit.Stretch("PadSetup", parent);
            var w = rt.gameObject.AddComponent<PadSetupWizard>();
            w.done = done;
            w.Build();
            return w;
        }

        void Build()
        {
            var dim = gameObject.AddComponent<Image>();
            dim.color = Palette.Ink.WithA(0.86f);
            var p = UIKit.Rect("Panel", transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, 10), new Vector2(1240, 660));
            var sp = p.gameObject.AddComponent<SlantPanel>(); sp.color = Palette.Indigo; sp.borderColor = Palette.Paper; sp.border = 8; sp.slant = 30; sp.raycastTarget = false;
            var title = UIKit.Text("Title", p, "CONTROLLER SETUP · コントローラー設定", F ? F.comic : null, 64, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -70), new Vector2(1150, 80));
            UIKit.Inked(title, 0.25f, Palette.Ink, new Vector2(1, -1));
            deviceText = UIKit.Text("Device", p, "", F ? F.hud : null, 28, Palette.Cyan, TextAlignmentOptions.Center, new Vector2(0.5f, 1), new Vector2(0, -130), new Vector2(1150, 40));
            prompt = UIKit.Text("Prompt", p, "", F ? F.comic : null, 56, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 110), new Vector2(1150, 70));
            UIKit.Inked(prompt, 0.25f);
            glyph = UIKit.Text("Glyph", p, "", F ? F.comic : null, 130, Palette.Magenta, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -15), new Vector2(1150, 150));
            glyph.richText = true;
            UIKit.Inked(glyph, 0.2f, Palette.Ink, new Vector2(1.5f, -1.5f));
            status = UIKit.Text("Status", p, "", F ? F.hud : null, 28, Palette.Lime, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -120), new Vector2(1150, 40));
            var bg = UIKit.Img("ProgBg", p, null, Palette.Paper.WithA(0.15f), new Vector2(0.5f, 0), new Vector2(0, 130), new Vector2(900, 14));
            var fill = UIKit.Img("Fill", bg.transform, null, Palette.Yellow, new Vector2(0, 0.5f), Vector2.zero, new Vector2(0, 14));
            fill.rectTransform.pivot = new Vector2(0, 0.5f);
            progressFill = fill.rectTransform;
            progress = UIKit.Text("Progress", p, "", F ? F.hud : null, 24, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 165), new Vector2(900, 34));
            UIKit.Text("Keys", p, "KEYBOARD:  TAB  SKIP (NOT ON THIS CONTROLLER)   ·   BACKSPACE  PREVIOUS   ·   ESC  CANCEL", F ? F.hudRegular : null, 22, Palette.Paper.WithA(0.75f), TextAlignmentOptions.Center, new Vector2(0.5f, 0), new Vector2(0, 70), new Vector2(1150, 34));

            GameInput.BeginCapture();
            candidates = PadBridge.PhysicalControllers();
            if (candidates.Count == 0)
            {
                prompt.text = "NO CONTROLLER FOUND";
                glyph.text = "";
                status.text = "Connect a controller (USB or Bluetooth), then try again.";
                status.color = Palette.Red;
                phase = Phase.Done; doneT = 2.5f;
                return;
            }
            if (candidates.Count == 1) SelectDevice(candidates[0]);
            else
            {
                phase = Phase.ChooseDevice;
                candControls = new List<List<InputControl>>();
                candRest = new List<float[]>();
                foreach (var d in candidates) { var cs = Leaves(d); candControls.Add(cs); candRest.Add(Snapshot(cs)); }
                deviceText.text = candidates.Count + " CONTROLLERS CONNECTED";
                prompt.text = "PRESS ANY BUTTON ON THE CONTROLLER TO SET UP";
                glyph.text = "?";
            }
        }

        static List<InputControl> Leaves(InputDevice d)
        {
            var list = new List<InputControl>();
            foreach (var c in d.allControls)
                if (!c.synthetic && !c.noisy && c is InputControl<float> && c.children.Count == 0) list.Add(c);
            return list;
        }

        static float[] Snapshot(List<InputControl> cs)
        {
            var r = new float[cs.Count];
            for (int i = 0; i < r.Length; i++) r[i] = PadBridge.Read(cs[i]);
            return r;
        }

        void SelectDevice(InputDevice d)
        {
            device = d;
            PadBridge.SetPaused(d, true);
            controls = Leaves(d);
            rest = Snapshot(controls);
            style = GameInput.StyleOf(d);
            deviceText.text = d.displayName.ToUpperInvariant() + "  ·  " + GameInput.StyleName(style) + " LABELS";
            string L(string c) => GameInput.PadLabel(c, style);
            steps = new[]
            {
                new Step { target = PadTarget.South, text = "PRESS THE BOTTOM FACE BUTTON", glyph = L("buttonSouth") },
                new Step { target = PadTarget.East, text = "PRESS THE RIGHT FACE BUTTON", glyph = L("buttonEast") },
                new Step { target = PadTarget.West, text = "PRESS THE LEFT FACE BUTTON", glyph = L("buttonWest") },
                new Step { target = PadTarget.North, text = "PRESS THE TOP FACE BUTTON", glyph = L("buttonNorth") },
                new Step { target = PadTarget.LeftShoulder, text = "PRESS THE LEFT BUMPER", glyph = L("leftShoulder") },
                new Step { target = PadTarget.RightShoulder, text = "PRESS THE RIGHT BUMPER", glyph = L("rightShoulder") },
                new Step { target = PadTarget.LeftTrigger, text = "PULL THE LEFT TRIGGER ALL THE WAY", glyph = L("leftTrigger") },
                new Step { target = PadTarget.RightTrigger, text = "PULL THE RIGHT TRIGGER ALL THE WAY", glyph = L("rightTrigger") },
                new Step { target = PadTarget.Select, text = "PRESS THE SMALL LEFT CENTRE BUTTON", glyph = L("select") },
                new Step { target = PadTarget.Start, text = "PRESS THE SMALL RIGHT CENTRE BUTTON", glyph = L("start") },
                new Step { target = PadTarget.LeftStickPress, text = "CLICK THE LEFT STICK IN", glyph = L("leftStickPress") },
                new Step { target = PadTarget.RightStickPress, text = "CLICK THE RIGHT STICK IN", glyph = L("rightStickPress") },
                new Step { target = PadTarget.DpadUp, text = "PRESS D-PAD UP", glyph = "↑" },
                new Step { target = PadTarget.DpadDown, text = "PRESS D-PAD DOWN", glyph = "↓" },
                new Step { target = PadTarget.DpadLeft, text = "PRESS D-PAD LEFT", glyph = "←" },
                new Step { target = PadTarget.DpadRight, text = "PRESS D-PAD RIGHT", glyph = "→" },
                new Step { target = PadTarget.LeftStickX, text = "PUSH THE LEFT STICK (OR WHEEL) FULLY RIGHT", glyph = "L →" },
                new Step { target = PadTarget.LeftStickY, text = "PUSH THE LEFT STICK FULLY UP", glyph = "L ↑" },
                new Step { target = PadTarget.RightStickX, text = "PUSH THE RIGHT STICK FULLY RIGHT", glyph = "R →" },
                new Step { target = PadTarget.RightStickY, text = "PUSH THE RIGHT STICK FULLY UP", glyph = "R ↑" },
            };
            step = 0;
            Enter(Phase.WaitRelease);
        }

        void Enter(Phase ph)
        {
            phase = ph;
            if (steps == null || step >= steps.Length) return;
            var s = steps[step];
            prompt.text = s.text;
            glyph.text = s.glyph;
            progress.text = $"STEP {step + 1} / {steps.Length}";
            progressFill.sizeDelta = new Vector2(900f * step / steps.Length, 14f);
            if (ph == Phase.WaitRelease) holdT = 0f;
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            if (phase == Phase.Done)
            {
                if ((doneT -= dt) <= 0f) Finish(recorded.Count > 0 && device != null);
                return;
            }
            var kb = Keyboard.current;
            if (kb != null && kb.escapeKey.wasPressedThisFrame) { Cancel(); return; }
            if (device != null && !device.added) { status.text = "Controller disconnected"; Cancel(); return; }

            if (phase == Phase.ChooseDevice)
            {
                for (int k = 0; k < candidates.Count; k++)
                    if (Strongest(candControls[k], candRest[k], 0.6f, false, out _, out _) >= 0) { SelectDevice(candidates[k]); return; }
                return;
            }

            if (kb != null && kb.tabKey.wasPressedThisFrame) { recorded.Remove(step); Next("Skipped", Palette.Paper); return; }
            if (kb != null && kb.backspaceKey.wasPressedThisFrame && step > 0) { step--; recorded.Remove(step); status.text = ""; Enter(Phase.WaitRelease); return; }

            var s = steps[step];
            switch (phase)
            {
                case Phase.WaitRelease:
                    // everything back at rest for a moment before listening
                    if (Strongest(controls, rest, 0.3f, false, out _, out _) < 0) { if ((holdT += dt) > 0.15f) Enter(Phase.WaitPress); }
                    else holdT = 0f;
                    break;
                case Phase.WaitPress:
                {
                    int i = Strongest(controls, rest, 0.55f, PadBridge.IsStick(s.target), out float v, out float delta);
                    if (i < 0) break;
                    int used = UsedBy(controls[i], Mathf.Sign(delta));
                    if (used >= 0 && used != step)
                    {
                        status.text = $"That's already {steps[used].glyph} — press a different one";
                        status.color = Palette.Red;
                        Enter(Phase.WaitRelease);
                        break;
                    }
                    hit = controls[i]; hitBase = rest[i]; peak = v; holdT = 0f;
                    phase = Phase.Hold;
                    break;
                }
                case Phase.Hold:
                {
                    float v = PadBridge.Read(hit);
                    if (Mathf.Abs(v - hitBase) > Mathf.Abs(peak - hitBase) && Mathf.Sign(v - hitBase) == Mathf.Sign(peak - hitBase)) peak = v;
                    holdT += dt;
                    bool released = Mathf.Abs(v - hitBase) < 0.3f;
                    if (holdT > 0.4f || released)
                    {
                        string rel = hit.path.Substring(device.path.Length + 1);
                        recorded[step] = new PadMapEntry { target = s.target, control = rel, rest = hitBase, full = peak };
                        Next($"Got it: {hit.displayName}", Palette.Lime);
                    }
                    break;
                }
            }
        }

        /// <summary>Index of the control furthest from rest (above threshold), or -1.</summary>
        static int Strongest(List<InputControl> cs, float[] baseVals, float threshold, bool centredAxesOnly, out float value, out float delta)
        {
            int best = -1; float bestD = threshold; value = 0f; delta = 0f;
            for (int i = 0; i < cs.Count; i++)
            {
                if (centredAxesOnly && (Mathf.Abs(baseVals[i]) > 0.35f || IsDigital(cs[i]))) continue;
                float v = PadBridge.Read(cs[i]);
                float d = v - baseVals[i];
                if (Mathf.Abs(d) > bestD) { bestD = Mathf.Abs(d); best = i; value = v; delta = d; }
            }
            return best;
        }

        /// <summary>Plain on/off buttons (not analog triggers or hat directions) can't be stick axes.</summary>
        static bool IsDigital(InputControl c) => c is UnityEngine.InputSystem.Controls.ButtonControl && c.stateBlock.sizeInBits == 1;

        int UsedBy(InputControl c, float sign)
        {
            string rel = c.path.Substring(device.path.Length + 1);
            foreach (var kv in recorded)
                if (kv.Value.control == rel && Mathf.Sign(kv.Value.full - kv.Value.rest) == sign) return kv.Key;
            return -1;
        }

        void Next(string msg, Color col)
        {
            status.text = msg;
            status.color = col;
            UISfx.Play("ui_move");
            step++;
            if (step >= steps.Length)
            {
                progressFill.sizeDelta = new Vector2(900f, 14f);
                progress.text = "DONE";
                prompt.text = "ALL SET! · 設定完了";
                glyph.text = "OK";
                phase = Phase.Done;
                doneT = 1.2f;
                return;
            }
            Enter(Phase.WaitRelease);
        }

        void Cancel()
        {
            recorded.Clear();
            Finish(false);
        }

        void Finish(bool save)
        {
            if (device != null)
            {
                if (save)
                {
                    var map = new PadMapping { name = device.displayName };
                    foreach (var kv in recorded) map.entries.Add(kv.Value);
                    PadBridge.SaveCustom(device, map);
                }
                else PadBridge.SetPaused(device, false);
            }
            GameInput.EndCapture();
            var cb = done;
            done = null;
            Destroy(gameObject);
            cb?.Invoke(save);
        }

        void OnDestroy()
        {
            // closed by a scene change mid-setup
            if (done != null) { if (device != null) PadBridge.SetPaused(device, false); GameInput.EndCapture(); }
        }
    }
}
