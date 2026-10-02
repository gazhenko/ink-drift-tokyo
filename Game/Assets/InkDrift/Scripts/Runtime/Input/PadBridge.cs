using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.Layouts;
using UnityEngine.InputSystem.LowLevel;

namespace InkDrift
{
    /// <summary>Standard gamepad inputs (Xbox positions) that a raw controller can be mapped onto.</summary>
    public enum PadTarget
    {
        South, East, West, North, LeftShoulder, RightShoulder, LeftTrigger, RightTrigger, Select, Start,
        LeftStickPress, RightStickPress, DpadUp, DpadDown, DpadLeft, DpadRight, LeftStickX, LeftStickY, RightStickX, RightStickY
    }

    /// <summary>One mapped input: output = (value - rest) / (full - rest). Buttons use rest 0 / full 1.</summary>
    [Serializable]
    public class PadMapEntry
    {
        public PadTarget target;
        public string control;
        public float rest;
        public float full = 1f;
    }

    [Serializable]
    public class PadMapping
    {
        public string key;
        public string name;
        public bool custom;
        public List<PadMapEntry> entries = new List<PadMapEntry>();
    }

    /// <summary>
    /// Turns controllers that Unity only sees as generic joysticks (third-party/DirectInput pads on macOS and
    /// Windows, unrecognised pads on Linux, wheels) into virtual gamepads, using a default layout guess or a
    /// layout the player recorded in Controller Setup. A recognised gamepad can be remapped the same way.
    /// The raw device is then masked out of the game's actions so it isn't read twice.
    /// </summary>
    public static class PadBridge
    {
        public const string VirtualInterface = "InkDriftVirtual";
        const string VirtualLayout = "InkDriftVirtualGamepad";
        const string PrefsPrefix = "ink_padmap_";

        class Link
        {
            public InputDevice source;
            public Gamepad pad;
            public PadMapping map;
            public InputControl[] controls;
            public GamepadState last;
            public bool paused;
        }

        static readonly List<Link> links = new List<Link>();
        public static readonly HashSet<InputDevice> MaskedSources = new HashSet<InputDevice>();
        static bool inited;

        public static void Init()
        {
            if (inited) return;
            inited = true;
            InputSystem.RegisterLayout("{ \"name\": \"" + VirtualLayout + "\", \"extend\": \"Gamepad\", \"displayName\": \"Mapped Controller\" }",
                VirtualLayout, new InputDeviceMatcher().WithInterface(VirtualInterface));
            InputSystem.onEvent += (ev, d) => OnEvent(ev, d);
            foreach (var d in InputSystem.devices.ToArray()) Consider(d);
        }

        public static bool IsVirtual(InputDevice d) => d != null && d.description.interfaceName == VirtualInterface;
        public static bool IsMasked(InputDevice d) => d != null && MaskedSources.Contains(d);
        public static bool IsBridged(InputDevice source) => Find(source) != null;
        public static bool HasCustomMapping(InputDevice source) { var l = Find(source); return l != null && l.map.custom; }
        public static PadMapping MappingFor(InputDevice source) => Find(source)?.map;

        public static InputDevice SourceOf(InputDevice virtualPad)
        {
            foreach (var l in links) if (l.pad == virtualPad) return l.source;
            return null;
        }

        public static Gamepad VirtualFor(InputDevice source) => Find(source)?.pad;

        static Link Find(InputDevice source)
        {
            foreach (var l in links) if (l.source == source) return l;
            return null;
        }

        /// <summary>Generic controller-like devices that aren't already gamepads (HID joysticks, Linux SDL devices).</summary>
        public static bool LooksLikeController(InputDevice d)
        {
            if (d == null || d is Gamepad || d is Keyboard || d is Pointer || d is Sensor || IsVirtual(d)) return false;
            if (d is Joystick) return true;
            if (d.description.interfaceName != "Linux") return false;
            int buttons = 0;
            foreach (var c in d.allControls) if (c is ButtonControl && !c.synthetic) buttons++;
            return buttons >= 4;
        }

        /// <summary>Physical controllers the player could set up (recognised gamepads and generic ones).</summary>
        public static List<InputDevice> PhysicalControllers()
        {
            var list = new List<InputDevice>();
            foreach (var d in InputSystem.devices)
                if (d.enabled && !IsVirtual(d) && (d is Gamepad || LooksLikeController(d))) list.Add(d);
            return list;
        }

        public static void OnDeviceChange(InputDevice d, InputDeviceChange change)
        {
            switch (change)
            {
                case InputDeviceChange.Added:
                case InputDeviceChange.Reconnected:
                    Consider(d);
                    break;
                case InputDeviceChange.Removed:
                case InputDeviceChange.Disconnected:
                    Detach(d);
                    break;
            }
        }

        static void Consider(InputDevice d)
        {
            if (d == null || IsVirtual(d) || Find(d) != null) return;
            var saved = Load(KeyOf(d));
            if (d is Gamepad) { if (saved != null) Attach(d, saved); return; }   // recognised pads are only bridged when remapped
            if (!LooksLikeController(d)) return;
            Attach(d, saved ?? Guess(d));
        }

        static void Attach(InputDevice src, PadMapping map)
        {
            var desc = new InputDeviceDescription
            {
                interfaceName = VirtualInterface,
                product = string.IsNullOrEmpty(src.displayName) ? src.name : src.displayName,
                manufacturer = src.description.manufacturer,
            };
            Gamepad pad;
            try { pad = InputSystem.AddDevice(desc) as Gamepad; }
            catch (Exception e) { Debug.LogWarning("[Input] could not create a virtual gamepad: " + e.Message); return; }
            if (pad == null) return;
            var link = new Link { source = src, pad = pad, map = map };
            Resolve(link);
            links.Add(link);
            MaskedSources.Add(src);
            GameInput.RefreshDeviceMask();
            Debug.Log($"[Input] {src.displayName} [{src.layout}] → virtual gamepad ({(map.custom ? "player mapping" : "default layout guess")}, {map.entries.Count} inputs)");
        }

        static void Detach(InputDevice src)
        {
            var l = Find(src);
            if (l == null) return;
            links.Remove(l);
            MaskedSources.Remove(src);
            if (l.pad.added) InputSystem.RemoveDevice(l.pad);
            GameInput.RefreshDeviceMask();
        }

        static void Resolve(Link l)
        {
            l.controls = new InputControl[l.map.entries.Count];
            for (int i = 0; i < l.controls.Length; i++)
                l.controls[i] = l.source.TryGetChildControl(l.map.entries[i].control);
        }

        /// <summary>Stops forwarding a device's input (while Controller Setup records it).</summary>
        public static void SetPaused(InputDevice source, bool paused)
        {
            var l = Find(source);
            if (l == null) return;
            l.paused = paused;
            if (paused && l.pad.added) { l.last = default; InputSystem.QueueStateEvent(l.pad, l.last); }
        }

        /// <summary>Saves a player-recorded mapping and (re)bridges the device with it.</summary>
        public static void SaveCustom(InputDevice source, PadMapping map)
        {
            map.key = KeyOf(source);
            map.custom = true;
            PlayerPrefs.SetString(PrefsPrefix + Hash(map.key), JsonUtility.ToJson(map));
            PlayerPrefs.Save();
            Detach(source);
            Attach(source, map);
        }

        /// <summary>Deletes a player mapping: recognised gamepads go back to Unity's layout, others to the default guess.</summary>
        public static void Forget(InputDevice source)
        {
            PlayerPrefs.DeleteKey(PrefsPrefix + Hash(KeyOf(source)));
            PlayerPrefs.Save();
            Detach(source);
            Consider(source);
        }

        static PadMapping Load(string key)
        {
            string json = PlayerPrefs.GetString(PrefsPrefix + Hash(key), "");
            if (string.IsNullOrEmpty(json)) return null;
            try { var m = JsonUtility.FromJson<PadMapping>(json); return m != null && m.key == key ? m : null; }
            catch { return null; }
        }

        // ------------------------------------------------------------------ forwarding
        // Input is forwarded as real state events so the virtual pad behaves like hardware (press detection,
        // interactive rebinding). Events queued while the Input System is processing are handled in the same update,
        // so forwarding from onEvent adds no latency; Pump() after the update catches anything the event didn't carry.

        static void OnEvent(InputEventPtr ev, InputDevice device)
        {
            if (links.Count == 0 || IsVirtual(device)) return;
            if (!ev.IsA<StateEvent>() && !ev.IsA<DeltaStateEvent>()) return;
            var l = Find(device);
            if (l == null || l.paused || !l.pad.added) return;
            Forward(l, ev);
        }

        public static void Pump()
        {
            for (int i = 0; i < links.Count; i++)
            {
                var l = links[i];
                if (!l.paused && l.pad.added && l.source.added) Forward(l, default);
            }
        }

        static void Forward(Link l, InputEventPtr ev)
        {
            var s = Compute(l, ev);
            if (Same(s, l.last)) return;
            l.last = s;
            InputSystem.QueueStateEvent(l.pad, s);
        }

        public static float Read(InputControl c) => c is InputControl<float> f ? f.ReadValue() : 0f;

        static float Read(InputControl c, InputEventPtr ev)
        {
            if (c is InputControl<float> f)
            {
                if (ev.valid && f.ReadValueFromEvent(ev, out float v)) return v;
                return f.ReadValue();
            }
            return 0f;
        }

        static GamepadState Compute(Link l, InputEventPtr ev)
        {
            var st = new GamepadState();
            float lx = 0, ly = 0, rx = 0, ry = 0, lt = 0, rt = 0;
            var entries = l.map.entries;
            for (int i = 0; i < entries.Count; i++)
            {
                var c = l.controls[i];
                if (c == null) continue;
                var e = entries[i];
                float v = Read(c, ev);
                float span = e.full - e.rest;
                if (Mathf.Abs(span) < 1e-4f) continue;
                float t = (v - e.rest) / span;
                // default guesses learn the real range of axes they haven't seen at full travel yet
                if (!l.map.custom && t > 1.02f && IsAnalog(e.target)) { e.full = v; t = 1f; }
                switch (e.target)
                {
                    case PadTarget.LeftStickX: lx += t; break;
                    case PadTarget.LeftStickY: ly += t; break;
                    case PadTarget.RightStickX: rx += t; break;
                    case PadTarget.RightStickY: ry += t; break;
                    case PadTarget.LeftTrigger: lt = Mathf.Max(lt, Mathf.Clamp01(t)); break;
                    case PadTarget.RightTrigger: rt = Mathf.Max(rt, Mathf.Clamp01(t)); break;
                    default:
                        if (t > 0.5f) st = st.WithButton(ButtonOf(e.target));
                        break;
                }
            }
            st.leftStick = Vector2.ClampMagnitude(new Vector2(Mathf.Clamp(lx, -1f, 1f), Mathf.Clamp(ly, -1f, 1f)), 1f);
            st.rightStick = Vector2.ClampMagnitude(new Vector2(Mathf.Clamp(rx, -1f, 1f), Mathf.Clamp(ry, -1f, 1f)), 1f);
            st.leftTrigger = lt;
            st.rightTrigger = rt;
            return st;
        }

        static bool Same(in GamepadState a, in GamepadState b) =>
            a.buttons == b.buttons && a.leftStick == b.leftStick && a.rightStick == b.rightStick && a.leftTrigger == b.leftTrigger && a.rightTrigger == b.rightTrigger;

        public static bool IsAnalog(PadTarget t) =>
            t == PadTarget.LeftStickX || t == PadTarget.LeftStickY || t == PadTarget.RightStickX || t == PadTarget.RightStickY ||
            t == PadTarget.LeftTrigger || t == PadTarget.RightTrigger;

        public static bool IsStick(PadTarget t) =>
            t == PadTarget.LeftStickX || t == PadTarget.LeftStickY || t == PadTarget.RightStickX || t == PadTarget.RightStickY;

        static GamepadButton ButtonOf(PadTarget t)
        {
            switch (t)
            {
                case PadTarget.South: return GamepadButton.South;
                case PadTarget.East: return GamepadButton.East;
                case PadTarget.West: return GamepadButton.West;
                case PadTarget.North: return GamepadButton.North;
                case PadTarget.LeftShoulder: return GamepadButton.LeftShoulder;
                case PadTarget.RightShoulder: return GamepadButton.RightShoulder;
                case PadTarget.Select: return GamepadButton.Select;
                case PadTarget.Start: return GamepadButton.Start;
                case PadTarget.LeftStickPress: return GamepadButton.LeftStick;
                case PadTarget.RightStickPress: return GamepadButton.RightStick;
                case PadTarget.DpadUp: return GamepadButton.DpadUp;
                case PadTarget.DpadDown: return GamepadButton.DpadDown;
                case PadTarget.DpadLeft: return GamepadButton.DpadLeft;
                default: return GamepadButton.DpadRight;
            }
        }

        // ------------------------------------------------------------------ default layouts

        /// <summary>
        /// Best guess for a controller Unity only knows as a joystick:
        /// Linux evdev names follow the kernel gamepad spec (xpad reports X/Y swapped, Sony/Nintendo don't);
        /// HID and generic Linux joysticks use the common DirectInput order (1 □/X, 2 ×/A, 3 ○/B, 4 △/Y, 5 LB, 6 RB,
        /// 7 LT, 8 RT, 9 select, 10 start, 11 LS, 12 RS; right stick on Z/Rz, analog triggers on Rx/Ry).
        /// Anything else gets fixed in Controller Setup.
        /// </summary>
        public static PadMapping Guess(InputDevice d)
        {
            var m = new PadMapping { key = KeyOf(d), name = d.displayName };
            if (Has(d, "A") && Has(d, "B") && (Has(d, "Start") || Has(d, "TriggerLeft")))
            {
                bool spec = GameInput.GuessStyle(d.description, d.displayName) != PadStyle.Xbox;
                Btn(m, d, PadTarget.South, "A");
                Btn(m, d, PadTarget.East, "B");
                Btn(m, d, PadTarget.West, spec ? "Y" : "X");
                Btn(m, d, PadTarget.North, spec ? "X" : "Y");
                Btn(m, d, PadTarget.LeftShoulder, "TriggerLeft");
                Btn(m, d, PadTarget.RightShoulder, "TriggerRight");
                Btn(m, d, PadTarget.Select, "Select");
                Btn(m, d, PadTarget.Start, "Start");
                Btn(m, d, PadTarget.LeftStickPress, "ThumbLeft");
                Btn(m, d, PadTarget.RightStickPress, "ThumbRight");
                if (Has(d, "Z")) Trigger(m, d, PadTarget.LeftTrigger, "Z"); else Btn(m, d, PadTarget.LeftTrigger, "TriggerLeft2");
                if (Has(d, "RotateZ")) Trigger(m, d, PadTarget.RightTrigger, "RotateZ"); else Btn(m, d, PadTarget.RightTrigger, "TriggerRight2");
                Axis(m, d, PadTarget.RightStickX, "RotateX", 1f);
                Axis(m, d, PadTarget.RightStickY, "RotateY", -1f);
            }
            else
            {
                bool lnx = Has(d, "Thumb");
                string[] names = lnx
                    ? new[] { "Trigger", "Thumb", "Thumb2", "Top", "Top2", "Pinkie", "Base", "Base2", "Base3", "Base4", "Base5", "Base6" }
                    : new[] { "trigger", "button2", "button3", "button4", "button5", "button6", "button7", "button8", "button9", "button10", "button11", "button12" };
                PadTarget[] order =
                {
                    PadTarget.West, PadTarget.South, PadTarget.East, PadTarget.North, PadTarget.LeftShoulder, PadTarget.RightShoulder,
                    PadTarget.LeftTrigger, PadTarget.RightTrigger, PadTarget.Select, PadTarget.Start, PadTarget.LeftStickPress, PadTarget.RightStickPress,
                };
                for (int i = 0; i < order.Length; i++) Btn(m, d, order[i], names[i]);
                string z = lnx ? "Z" : "z", rz = lnx ? "RotateZ" : "rz", rxn = lnx ? "RotateX" : "rx", ryn = lnx ? "RotateY" : "ry";
                if (Has(d, z) && Has(d, rz))
                {
                    Axis(m, d, PadTarget.RightStickX, z, 1f);
                    Axis(m, d, PadTarget.RightStickY, rz, -1f);
                    if (Has(d, rxn) && Has(d, ryn)) { Trigger(m, d, PadTarget.LeftTrigger, rxn); Trigger(m, d, PadTarget.RightTrigger, ryn); }
                }
                else if (Has(d, rxn) && Has(d, ryn))
                {
                    Axis(m, d, PadTarget.RightStickX, rxn, 1f);
                    Axis(m, d, PadTarget.RightStickY, ryn, lnx ? -1f : 1f);
                }
            }
            // left stick (Unity already flips Y to up-positive) and hat switch
            string stick = Has(d, "stick") ? "stick" : null;
            if (stick != null) { Axis(m, d, PadTarget.LeftStickX, stick + "/x", 1f); Axis(m, d, PadTarget.LeftStickY, stick + "/y", 1f); }
            string hat = Has(d, "hat") ? "hat" : null;
            if (hat != null)
            {
                Btn(m, d, PadTarget.DpadUp, hat + "/up"); Btn(m, d, PadTarget.DpadDown, hat + "/down");
                Btn(m, d, PadTarget.DpadLeft, hat + "/left"); Btn(m, d, PadTarget.DpadRight, hat + "/right");
            }
            return m;
        }

        static bool Has(InputDevice d, string path) => d.TryGetChildControl(path) != null;

        static void Btn(PadMapping m, InputDevice d, PadTarget t, string path)
        {
            if (Has(d, path)) m.entries.Add(new PadMapEntry { target = t, control = path, rest = 0f, full = 1f });
        }

        static void Axis(PadMapping m, InputDevice d, PadTarget t, string path, float full)
        {
            if (Has(d, path)) m.entries.Add(new PadMapEntry { target = t, control = path, rest = 0f, full = full });
        }

        /// <summary>Analog trigger: drivers park triggers at the bottom of a centred axis (-1) or at 0; assume a symmetric range.</summary>
        static void Trigger(PadMapping m, InputDevice d, PadTarget t, string path)
        {
            var c = d.TryGetChildControl(path);
            if (c == null) return;
            float now = Read(c);
            float rest = now < -0.2f ? now : 0f;
            m.entries.Add(new PadMapEntry { target = t, control = path, rest = rest, full = rest < 0f ? -rest : 1f });
        }

        // ------------------------------------------------------------------ identity

        public static string KeyOf(InputDevice d)
        {
            var desc = d.description;
            return $"{desc.interfaceName}|{desc.manufacturer}|{desc.product}|{VendorId(desc):X4}:{ProductId(desc):X4}|{d.layout}";
        }

        public static int VendorId(InputDeviceDescription desc) => CapInt(desc.capabilities, "vendorId");
        public static int ProductId(InputDeviceDescription desc) => CapInt(desc.capabilities, "productId");

        static int CapInt(string caps, string field)
        {
            if (string.IsNullOrEmpty(caps)) return 0;
            var mt = Regex.Match(caps, "\"" + field + "\"\\s*:\\s*(\\d+)");
            return mt.Success && int.TryParse(mt.Groups[1].Value, out int v) ? v : 0;
        }

        static string Hash(string s)
        {
            uint h = 2166136261;
            foreach (char ch in s) { h ^= ch; h *= 16777619; }
            return h.ToString("x8");
        }
    }
}
