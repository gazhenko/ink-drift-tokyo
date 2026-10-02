using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.DualShock;
using UnityEngine.InputSystem.Layouts;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.UI;
using UnityEngine.InputSystem.XInput;
#if UNITY_EDITOR || UNITY_STANDALONE_WIN || UNITY_STANDALONE_OSX || UNITY_STANDALONE_LINUX
using UnityEngine.InputSystem.Switch;
#endif

namespace InkDrift
{
    public enum PadStyle { Xbox, PlayStation, Nintendo }

    /// <summary>The rebindable driving controls, in the order the Controls screen lists them.</summary>
    public enum Bind { SteerLeft, SteerRight, Throttle, Brake, Handbrake, Clutch, ShiftUp, ShiftDown, Camera, LookBack, Reset, Pause }

    /// <summary>Binding columns: two keyboard keys and one controller input per control.</summary>
    public enum Slot { Key1, Key2, Pad }

    /// <summary>
    /// All game input in one place: a code-built action asset (keyboard + any gamepad), saved binding overrides,
    /// last-used device tracking for button labels, menu/UI actions and rumble. Controllers Unity doesn't recognise
    /// as gamepads are turned into virtual gamepads by <see cref="PadBridge"/>, so every binding here is written
    /// against &lt;Gamepad&gt; and &lt;Keyboard&gt; only.
    /// </summary>
    public static class GameInput
    {
        public const string KeyboardGroup = "Keyboard";
        public const string PadGroup = "Gamepad";
        const string PrefsKey = "ink_bindings_v1";

        public static InputActionAsset Asset { get; private set; }
        public static InputAction Steer, Throttle, Brake, Handbrake, Clutch, ShiftUp, ShiftDown, CameraCycle, LookBack, ResetCar, Pause;
        public static InputAction NavLeft, NavRight, NavUp, NavDown, Back, Any, Clear, Default;
        static InputActionMap driveMap, menuMap, uiMap;

        /// <summary>True while the player is using a controller (drives button labels and rumble).</summary>
        public static bool UsingGamepad { get; private set; }
        /// <summary>The gamepad (physical or bridged) that most recently produced input.</summary>
        public static Gamepad ActivePad { get; private set; }
        public static PadStyle Style => StyleOf(ActivePad);
        public static event Action DeviceChanged;
        public static event Action BindingsChanged;
        public static event Action<InputDevice> PadDisconnected;
        /// <summary>Name of the control that lost its binding during the last rebind (duplicate removed), or null.</summary>
        public static string LastConflict { get; private set; }

        static int captureDepth;
        static readonly bool[] mapWasEnabled = new bool[3];
        /// <summary>True while a rebind or controller setup is listening for raw input; menus ignore input meanwhile.</summary>
        public static bool Capturing => captureDepth > 0;

        struct Row { public InputAction action; public int key1, key2, pad; }
        static readonly Row[] rows = new Row[12];

        public static readonly string[] BindNames = { "STEER LEFT", "STEER RIGHT", "THROTTLE", "BRAKE / REVERSE", "HANDBRAKE", "CLUTCH", "SHIFT UP", "SHIFT DOWN", "CAMERA", "LOOK BACK", "RESET CAR", "PAUSE" };
        public static readonly string[] BindJp = { "左ステア", "右ステア", "アクセル", "ブレーキ・バック", "サイドブレーキ", "クラッチ", "シフトアップ", "シフトダウン", "カメラ", "後方確認", "リセット", "ポーズ" };

        static bool inited;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void AutoInit() => Init();

        public static void Init()
        {
            if (inited) return;
            inited = true;
            Build();
            LoadOverrides();
            ApplyDeadzone();
            driveMap.Enable();
            menuMap.Enable();
            uiMap.Enable();
            PadBridge.Init();
            InputSystem.onAfterUpdate += AfterUpdate;
            InputSystem.onDeviceChange += OnDeviceChange;
            Application.quitting += () => InputSystem.ResetHaptics();
            var pads = new List<string>();
            foreach (var d in InputSystem.devices) if (d is Gamepad || PadBridge.LooksLikeController(d)) pads.Add($"{d.displayName} [{d.layout}]");
            Debug.Log("[Input] controllers at startup: " + (pads.Count > 0 ? string.Join(", ", pads) : "none"));
        }

        // ------------------------------------------------------------------ actions

        static void Build()
        {
            Asset = ScriptableObject.CreateInstance<InputActionAsset>();
            Asset.name = "InkDriftControls";

            driveMap = Asset.AddActionMap("Drive");
            Steer = driveMap.AddAction("Steer", InputActionType.Value, expectedControlLayout: "Axis");
            AddAxis(Steer, "<Keyboard>/a", "<Keyboard>/d", KeyboardGroup);
            AddAxis(Steer, "<Keyboard>/leftArrow", "<Keyboard>/rightArrow", KeyboardGroup);
            AddAxis(Steer, "<Gamepad>/leftStick/left", "<Gamepad>/leftStick/right", PadGroup);
            rows[(int)Bind.SteerLeft] = new Row { action = Steer, key1 = 1, key2 = 4, pad = 7 };
            rows[(int)Bind.SteerRight] = new Row { action = Steer, key1 = 2, key2 = 5, pad = 8 };

            Throttle = Simple(Bind.Throttle, "Throttle", InputActionType.Value, "<Keyboard>/w", "<Keyboard>/upArrow", "<Gamepad>/rightTrigger");
            Brake = Simple(Bind.Brake, "Brake", InputActionType.Value, "<Keyboard>/s", "<Keyboard>/downArrow", "<Gamepad>/leftTrigger");
            Handbrake = Simple(Bind.Handbrake, "Handbrake", InputActionType.Value, "<Keyboard>/space", "", "<Gamepad>/buttonSouth");
            Clutch = Simple(Bind.Clutch, "Clutch", InputActionType.Value, "<Keyboard>/leftShift", "<Keyboard>/rightShift", "<Gamepad>/buttonWest");
            ShiftUp = Simple(Bind.ShiftUp, "ShiftUp", InputActionType.Button, "<Keyboard>/e", "", "<Gamepad>/rightShoulder");
            ShiftDown = Simple(Bind.ShiftDown, "ShiftDown", InputActionType.Button, "<Keyboard>/q", "", "<Gamepad>/leftShoulder");
            CameraCycle = Simple(Bind.Camera, "Camera", InputActionType.Button, "<Keyboard>/c", "", "<Gamepad>/buttonNorth");
            LookBack = Simple(Bind.LookBack, "LookBack", InputActionType.Value, "<Keyboard>/b", "", "<Gamepad>/rightStickPress");
            ResetCar = Simple(Bind.Reset, "Reset", InputActionType.Button, "<Keyboard>/r", "", "<Gamepad>/select");
            Pause = Simple(Bind.Pause, "Pause", InputActionType.Button, "<Keyboard>/escape", "<Keyboard>/p", "<Gamepad>/start");

            // Fixed menu controls (not rebindable, so menus always work even with a broken custom layout).
            menuMap = Asset.AddActionMap("Menu");
            NavLeft = Buttons(menuMap, "Left", "<Keyboard>/leftArrow", "<Keyboard>/a", "<Gamepad>/dpad/left", "<Gamepad>/leftStick/left");
            NavRight = Buttons(menuMap, "Right", "<Keyboard>/rightArrow", "<Keyboard>/d", "<Gamepad>/dpad/right", "<Gamepad>/leftStick/right");
            NavUp = Buttons(menuMap, "Up", "<Keyboard>/upArrow", "<Keyboard>/w", "<Gamepad>/dpad/up", "<Gamepad>/leftStick/up");
            NavDown = Buttons(menuMap, "Down", "<Keyboard>/downArrow", "<Keyboard>/s", "<Gamepad>/dpad/down", "<Gamepad>/leftStick/down");
            Back = Buttons(menuMap, "Back", "<Keyboard>/escape", "<Keyboard>/backspace", "<Gamepad>/buttonEast");
            Any = Buttons(menuMap, "Any", "<Keyboard>/anyKey", "<Mouse>/leftButton", "<Gamepad>/buttonSouth", "<Gamepad>/buttonEast",
                "<Gamepad>/buttonWest", "<Gamepad>/buttonNorth", "<Gamepad>/start", "<Gamepad>/select", "<Gamepad>/leftShoulder",
                "<Gamepad>/rightShoulder", "<Gamepad>/leftTrigger", "<Gamepad>/rightTrigger");
            Clear = Buttons(menuMap, "Clear", "<Keyboard>/delete", "<Gamepad>/buttonWest");
            Default = Buttons(menuMap, "Default", "<Keyboard>/home", "<Gamepad>/buttonNorth");

            // uGUI navigation/pointer actions for InputSystemUIInputModule (same names as the package defaults).
            uiMap = Asset.AddActionMap("UI");
            var nav = uiMap.AddAction("Navigate", InputActionType.PassThrough, expectedControlLayout: "Vector2");
            nav.AddBinding("<Gamepad>/leftStick");
            nav.AddBinding("<Gamepad>/dpad");
            nav.AddCompositeBinding("2DVector").With("Up", "<Keyboard>/upArrow").With("Down", "<Keyboard>/downArrow").With("Left", "<Keyboard>/leftArrow").With("Right", "<Keyboard>/rightArrow");
            nav.AddCompositeBinding("2DVector").With("Up", "<Keyboard>/w").With("Down", "<Keyboard>/s").With("Left", "<Keyboard>/a").With("Right", "<Keyboard>/d");
            Buttons(uiMap, "Submit", "<Keyboard>/enter", "<Keyboard>/numpadEnter", "<Keyboard>/space", "<Gamepad>/buttonSouth");
            Buttons(uiMap, "Cancel", "<Keyboard>/escape", "<Gamepad>/buttonEast");
            var point = uiMap.AddAction("Point", InputActionType.PassThrough, expectedControlLayout: "Vector2");
            point.AddBinding("<Mouse>/position"); point.AddBinding("<Pen>/position"); point.AddBinding("<Touchscreen>/touch*/position");
            var click = uiMap.AddAction("Click", InputActionType.PassThrough, expectedControlLayout: "Button");
            click.AddBinding("<Mouse>/leftButton"); click.AddBinding("<Pen>/tip"); click.AddBinding("<Touchscreen>/touch*/press");
            uiMap.AddAction("ScrollWheel", InputActionType.PassThrough, "<Mouse>/scroll", expectedControlLayout: "Vector2");
            uiMap.AddAction("RightClick", InputActionType.PassThrough, "<Mouse>/rightButton", expectedControlLayout: "Button");
            uiMap.AddAction("MiddleClick", InputActionType.PassThrough, "<Mouse>/middleButton", expectedControlLayout: "Button");
        }

        static void AddAxis(InputAction a, string neg, string pos, string group)
        {
            a.AddCompositeBinding("1DAxis").With("Negative", neg, group).With("Positive", pos, group);
        }

        static InputAction Simple(Bind b, string name, InputActionType type, string key1, string key2, string pad)
        {
            var a = driveMap.AddAction(name, type, expectedControlLayout: type == InputActionType.Value ? "Axis" : "Button");
            a.AddBinding(key1, groups: KeyboardGroup);
            a.AddBinding(key2, groups: KeyboardGroup);
            a.AddBinding(pad, groups: PadGroup);
            rows[(int)b] = new Row { action = a, key1 = 0, key2 = 1, pad = 2 };
            return a;
        }

        static InputAction Buttons(InputActionMap map, string name, params string[] paths)
        {
            var a = map.AddAction(name, InputActionType.Button);
            foreach (var p in paths) a.AddBinding(p);
            return a;
        }

        /// <summary>Creates the EventSystem if needed and points its UI module at our UI actions.</summary>
        public static EventSystem EnsureEventSystem(Transform parent = null)
        {
            Init();
            var es = EventSystem.current != null ? EventSystem.current : UnityEngine.Object.FindAnyObjectByType<EventSystem>();
            if (es == null)
            {
                var go = new GameObject("EventSystem", typeof(EventSystem));
                if (parent) go.transform.SetParent(parent);
                es = go.GetComponent<EventSystem>();
            }
            var m = es.GetComponent<InputSystemUIInputModule>();
            if (m == null) m = es.gameObject.AddComponent<InputSystemUIInputModule>();
            if (m.actionsAsset != Asset)
            {
                m.actionsAsset = Asset;
                m.move = InputActionReference.Create(uiMap["Navigate"]);
                m.submit = InputActionReference.Create(uiMap["Submit"]);
                m.cancel = InputActionReference.Create(uiMap["Cancel"]);
                m.point = InputActionReference.Create(uiMap["Point"]);
                m.leftClick = InputActionReference.Create(uiMap["Click"]);
                m.rightClick = InputActionReference.Create(uiMap["RightClick"]);
                m.middleClick = InputActionReference.Create(uiMap["MiddleClick"]);
                m.scrollWheel = InputActionReference.Create(uiMap["ScrollWheel"]);
                m.trackedDevicePosition = null;
                m.trackedDeviceOrientation = null;
                m.deselectOnBackgroundClick = false;
            }
            if (es.GetComponent<SelectionKeeper>() == null) es.gameObject.AddComponent<SelectionKeeper>();
            return es;
        }

        // ------------------------------------------------------------------ per-update work

        static void AfterUpdate()
        {
            if (Application.isPlaying && InputState.currentUpdateType == InputUpdateType.Editor) return;
            PadBridge.Pump();
            DetectActivity();
            UpdateRumble();
        }

        static void DetectActivity()
        {
            Gamepad hit = null;
            var pads = Gamepad.all;
            for (int i = 0; i < pads.Count && hit == null; i++)
                if (!PadBridge.IsMasked(pads[i]) && Actuated(pads[i])) hit = pads[i];
            if (hit != null) { SetActive(hit, true); return; }
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            bool keys = (kb != null && kb.anyKey.wasPressedThisFrame)
                        || (mouse != null && (mouse.leftButton.wasPressedThisFrame || mouse.rightButton.wasPressedThisFrame || mouse.delta.ReadValue().sqrMagnitude > 100f));
            if (keys && UsingGamepad) SetActive(ActivePad, false);
        }

        static bool Actuated(Gamepad g)
        {
            if (g.leftStick.ReadValue().sqrMagnitude > 0.36f || g.rightStick.ReadValue().sqrMagnitude > 0.36f) return true;
            if (g.leftTrigger.ReadValue() > 0.4f || g.rightTrigger.ReadValue() > 0.4f) return true;
            var all = g.allControls;
            for (int i = 0; i < all.Count; i++)
                if (all[i] is ButtonControl b && !b.synthetic && !b.noisy && b != g.leftTrigger && b != g.rightTrigger && b.isPressed) return true;
            return false;
        }

        static void SetActive(Gamepad pad, bool usingPad)
        {
            bool changed = usingPad != UsingGamepad || (pad != null && pad != ActivePad);
            if (pad != null) ActivePad = pad;
            UsingGamepad = usingPad && pad != null;
            if (changed) DeviceChanged?.Invoke();
        }

        static void OnDeviceChange(InputDevice d, InputDeviceChange change)
        {
            bool lost = (change == InputDeviceChange.Removed || change == InputDeviceChange.Disconnected)
                        && ActivePad != null && (d == ActivePad || PadBridge.VirtualFor(d) == ActivePad);
            PadBridge.OnDeviceChange(d, change);
            if (change == InputDeviceChange.Added || change == InputDeviceChange.Removed ||
                change == InputDeviceChange.Reconnected || change == InputDeviceChange.Disconnected)
            {
                RefreshDeviceMask();
                Debug.Log($"[Input] {change}: {d.displayName} [{d.layout}]");
            }
            if (lost)
            {
                var pad = ActivePad;
                ActivePad = null;
                UsingGamepad = false;
                PadDisconnected?.Invoke(pad);
                DeviceChanged?.Invoke();
            }
        }

        /// <summary>Keeps raw devices that are replaced by a virtual gamepad out of our actions.</summary>
        internal static void RefreshDeviceMask()
        {
            if (Asset == null) return;
            if (PadBridge.MaskedSources.Count == 0) { Asset.devices = null; return; }
            var list = new List<InputDevice>();
            foreach (var d in InputSystem.devices) if (!PadBridge.IsMasked(d)) list.Add(d);
            Asset.devices = list.ToArray();
        }

        /// <summary>Pauses gameplay/menu actions while raw input is being captured (rebinding, controller setup).</summary>
        public static void BeginCapture()
        {
            if (captureDepth++ > 0) return;
            var maps = new[] { driveMap, menuMap, uiMap };
            for (int i = 0; i < maps.Length; i++) { mapWasEnabled[i] = maps[i].enabled; maps[i].Disable(); }
        }

        public static void EndCapture()
        {
            if (captureDepth == 0 || --captureDepth > 0) return;
            var maps = new[] { driveMap, menuMap, uiMap };
            for (int i = 0; i < maps.Length; i++) if (mapWasEnabled[i]) maps[i].Enable();
        }

        // ------------------------------------------------------------------ bindings

        static int IndexOf(Bind b, Slot s)
        {
            var r = rows[(int)b];
            return s == Slot.Key1 ? r.key1 : s == Slot.Key2 ? r.key2 : r.pad;
        }

        public static string PathOf(Bind b, Slot s) => rows[(int)b].action.bindings[IndexOf(b, s)].effectivePath ?? "";

        /// <summary>Listens for the next key (keyboard slots) or controller input (pad slot) and binds it.</summary>
        public static InputActionRebindingExtensions.RebindingOperation StartRebind(Bind b, Slot s, Action<bool> done)
        {
            var a = rows[(int)b].action;
            int index = IndexOf(b, s);
            bool pad = s == Slot.Pad;
            BeginCapture();
            InputActionRebindingExtensions.RebindingOperation op = null;
            void Finish(bool ok)
            {
                op.Dispose();
                if (ok)
                {
                    ResolveConflicts(b, s);
                    SaveOverrides();
                    BindingsChanged?.Invoke();
                }
                EndCapture();
                done?.Invoke(ok);
            }
            op = a.PerformInteractiveRebinding(index)
                .WithExpectedControlType("Button")
                .WithControlsHavingToMatchPath(pad ? "<Gamepad>" : "<Keyboard>")
                .WithControlsExcluding("<Keyboard>/anyKey")
                .WithCancelingThrough("<Keyboard>/escape")
                .WithMagnitudeHavingToBeGreaterThan(0.6f)
                .WithTimeout(8f)
                .OnMatchWaitForAnother(0.08f)
                .OnPotentialMatch(o =>
                {
                    for (int i = o.candidates.Count - 1; i >= 0; i--)
                        if (PadBridge.IsMasked(o.candidates[i].device)) o.RemoveCandidate(o.candidates[i]);
                })
                .OnComplete(_ => Finish(true))
                .OnCancel(_ => Finish(false));
            op.Start();
            return op;
        }

        /// <summary>A control can only drive one function per column group: remove the binding elsewhere.</summary>
        static void ResolveConflicts(Bind b, Slot s)
        {
            LastConflict = null;
            string path = PathOf(b, s);
            if (string.IsNullOrEmpty(path)) return;
            var slots = s == Slot.Pad ? new[] { Slot.Pad } : new[] { Slot.Key1, Slot.Key2 };
            for (int i = 0; i < rows.Length; i++)
                foreach (var t in slots)
                {
                    if (i == (int)b && t == s) continue;
                    if (string.Equals(PathOf((Bind)i, t), path, StringComparison.OrdinalIgnoreCase))
                    {
                        rows[i].action.ApplyBindingOverride(IndexOf((Bind)i, t), "");
                        LastConflict = BindNames[i];
                    }
                }
        }

        public static void ClearBinding(Bind b, Slot s)
        {
            rows[(int)b].action.ApplyBindingOverride(IndexOf(b, s), "");
            SaveOverrides();
            BindingsChanged?.Invoke();
        }

        public static void ResetBinding(Bind b, Slot s)
        {
            rows[(int)b].action.RemoveBindingOverride(IndexOf(b, s));
            ResolveConflicts(b, s);
            SaveOverrides();
            BindingsChanged?.Invoke();
        }

        public static void ResetAllBindings()
        {
            driveMap.RemoveAllBindingOverrides();
            LastConflict = null;
            SaveOverrides();
            BindingsChanged?.Invoke();
        }

        // Overrides are stored by action name + binding index (binding GUIDs change every launch for code-built assets).
        [Serializable] class SavedBinding { public string action; public int index; public string path; }
        [Serializable] class SavedBindings { public List<SavedBinding> items = new List<SavedBinding>(); }

        static void SaveOverrides()
        {
            var s = new SavedBindings();
            foreach (var a in driveMap.actions)
                for (int i = 0; i < a.bindings.Count; i++)
                    if (a.bindings[i].overridePath != null)
                        s.items.Add(new SavedBinding { action = a.name, index = i, path = a.bindings[i].overridePath });
            PlayerPrefs.SetString(PrefsKey, JsonUtility.ToJson(s));
            PlayerPrefs.Save();
        }

        static void LoadOverrides()
        {
            string json = PlayerPrefs.GetString(PrefsKey, "");
            if (string.IsNullOrEmpty(json)) return;
            try
            {
                var s = JsonUtility.FromJson<SavedBindings>(json);
                foreach (var it in s.items)
                {
                    var a = driveMap.FindAction(it.action);
                    if (a != null && it.index >= 0 && it.index < a.bindings.Count && !a.bindings[it.index].isComposite)
                        a.ApplyBindingOverride(it.index, it.path ?? "");
                }
            }
            catch (Exception e) { Debug.LogWarning("[Input] ignoring saved bindings: " + e.Message); }
        }

        public static void ApplyDeadzone()
        {
            InputSystem.settings.defaultDeadzoneMin = Mathf.Clamp(GameSession.StickDeadzone, 0.02f, 0.4f);
        }

        // ------------------------------------------------------------------ labels

        public static PadStyle StyleOf(InputDevice d)
        {
            int forced = GameSession.PadLabels;
            if (forced > 0 && forced <= 3) return (PadStyle)(forced - 1);
            if (d == null) return PadStyle.Xbox;
            var src = PadBridge.SourceOf(d);
            if (src != null) d = src;
            if (d is DualShockGamepad) return PadStyle.PlayStation;
#if UNITY_EDITOR || UNITY_STANDALONE_WIN || UNITY_STANDALONE_OSX || UNITY_STANDALONE_LINUX
            if (d is SwitchProControllerHID) return PadStyle.Nintendo;
#endif
            if (d is XInputController) return PadStyle.Xbox;
            return GuessStyle(d.description, d.displayName);
        }

        public static PadStyle GuessStyle(InputDeviceDescription desc, string displayName)
        {
            string s = $"{desc.manufacturer} {desc.product} {displayName}".ToLowerInvariant();
            int vid = PadBridge.VendorId(desc);
            if (vid == 0x054C || s.Contains("sony") || s.Contains("playstation") || s.Contains("dualsense") || s.Contains("dualshock")) return PadStyle.PlayStation;
            if (vid == 0x057E || s.Contains("nintendo") || s.Contains("pro controller") || s.Contains("joy-con")) return PadStyle.Nintendo;
            return PadStyle.Xbox;
        }

        public static string StyleName(PadStyle s) => s == PadStyle.PlayStation ? "PLAYSTATION" : s == PadStyle.Nintendo ? "NINTENDO" : "XBOX";

        static string Tint(string t, string hex, bool color) => color ? $"<color={hex}>{t}</color>" : t;

        /// <summary>Button name as printed on the controller, for a &lt;Gamepad&gt; control path.</summary>
        public static string PadLabel(string path, PadStyle st, bool color = true)
        {
            if (string.IsNullOrEmpty(path)) return "—";
            string c = path;
            int k = c.IndexOf('>');
            if (k >= 0) c = c.Substring(k + 1);
            c = c.TrimStart('/').ToLowerInvariant();
            bool ps = st == PadStyle.PlayStation, nin = st == PadStyle.Nintendo;
            switch (c)
            {
                case "buttonsouth": return ps ? Tint(color ? "<size=135%>×</size>" : "×", "#8CB4FF", color) : nin ? "B" : Tint("A", "#6CC24A", color);
                case "buttoneast": return ps ? Tint("○", "#FF6B6B", color) : nin ? "A" : Tint("B", "#F0544F", color);
                case "buttonwest": return ps ? Tint("□", "#F49AC2", color) : nin ? "Y" : Tint("X", "#3E8EDE", color);
                case "buttonnorth": return ps ? Tint("△", "#4FD1B5", color) : nin ? "X" : Tint("Y", "#F5C518", color);
                case "leftshoulder": return ps ? "L1" : nin ? "L" : "LB";
                case "rightshoulder": return ps ? "R1" : nin ? "R" : "RB";
                case "lefttrigger": return ps ? "L2" : nin ? "ZL" : "LT";
                case "righttrigger": return ps ? "R2" : nin ? "ZR" : "RT";
                case "select": return ps ? "CREATE" : nin ? "−" : "VIEW";
                case "start": return ps ? "OPTIONS" : nin ? "+" : "MENU";
                case "leftstickpress": return ps ? "L3" : "LS";
                case "rightstickpress": return ps ? "R3" : "RS";
                case "dpad/up": return "D-PAD ↑";
                case "dpad/down": return "D-PAD ↓";
                case "dpad/left": return "D-PAD ←";
                case "dpad/right": return "D-PAD →";
                case "dpad": return "D-PAD";
                case "leftstick/up": return "L-STICK ↑";
                case "leftstick/down": return "L-STICK ↓";
                case "leftstick/left": return "L-STICK ←";
                case "leftstick/right": return "L-STICK →";
                case "leftstick": return "L-STICK";
                case "rightstick/up": return "R-STICK ↑";
                case "rightstick/down": return "R-STICK ↓";
                case "rightstick/left": return "R-STICK ←";
                case "rightstick/right": return "R-STICK →";
                case "rightstick": return "R-STICK";
            }
            return InputControlPath.ToHumanReadableString(path, InputControlPath.HumanReadableStringOptions.OmitDevice).ToUpperInvariant();
        }

        static string KeyLabel(InputAction a, int index)
        {
            if (string.IsNullOrEmpty(a.bindings[index].effectivePath)) return "—";
            string s = a.GetBindingDisplayString(index, InputBinding.DisplayStringOptions.DontIncludeInteractions).ToUpperInvariant();
            switch (s)
            {
                case "UP ARROW": return "↑";
                case "DOWN ARROW": return "↓";
                case "LEFT ARROW": return "←";
                case "RIGHT ARROW": return "→";
                case "": return "—";
            }
            return s;
        }

        public static string Label(Bind b, Slot s, bool color = true)
        {
            var r = rows[(int)b];
            int i = IndexOf(b, s);
            return s == Slot.Pad ? PadLabel(r.action.bindings[i].effectivePath, Style, color) : KeyLabel(r.action, i);
        }

        /// <summary>Label for whatever the player is holding right now (controller button or first key).</summary>
        public static string Label(Bind b)
        {
            if (UsingGamepad) return Label(b, Slot.Pad);
            string k = Label(b, Slot.Key1);
            return k != "—" ? k : Label(b, Slot.Key2);
        }

        public static string ConfirmLabel => UsingGamepad ? PadLabel("buttonSouth", Style) : "ENTER";
        public static string BackLabel => UsingGamepad ? PadLabel("buttonEast", Style) : "ESC";
        public static string NavLabel => UsingGamepad ? "D-PAD" : "↑↓";

        /// <summary>True if the action's current value comes from an analog controller rather than a key.</summary>
        public static bool FromController(InputAction a, ref bool last)
        {
            var c = a.activeControl;
            if (c != null) last = !(c.device is Keyboard);
            return last;
        }

        // ------------------------------------------------------------------ rumble

        static float engineLow, engineHigh, impulseLow, impulseHigh, impulseUntil, sentLow = -1f, sentHigh = -1f;
        static Gamepad rumbling;

        /// <summary>Continuous vibration (set every frame while driving; 0,0 to stop).</summary>
        public static void SetEngineRumble(float low, float high) { engineLow = low; engineHigh = high; }

        /// <summary>Short vibration burst (impacts, gear kicks).</summary>
        public static void Impulse(float low, float high, float seconds)
        {
            impulseLow = Mathf.Max(impulseLow, low);
            impulseHigh = Mathf.Max(impulseHigh, high);
            impulseUntil = Mathf.Max(impulseUntil, Time.unscaledTime + seconds);
        }

        static void UpdateRumble()
        {
            Gamepad target = null;
            if (UsingGamepad && GameSession.Vibration && Time.timeScale > 0f && ActivePad != null && !PadBridge.IsVirtual(ActivePad)) target = ActivePad;
            float lo = 0f, hi = 0f;
            if (Time.unscaledTime >= impulseUntil) impulseLow = impulseHigh = 0f;
            if (target != null) { lo = Mathf.Max(engineLow, impulseLow); hi = Mathf.Max(engineHigh, impulseHigh); }
            if (rumbling != null && rumbling != target)
            {
                if (rumbling.added) rumbling.SetMotorSpeeds(0f, 0f);
                rumbling = null; sentLow = sentHigh = -1f;
            }
            if (target == null) return;
            lo = Mathf.Clamp01(lo); hi = Mathf.Clamp01(hi);
            if (Mathf.Abs(lo - sentLow) < 0.02f && Mathf.Abs(hi - sentHigh) < 0.02f) return;
            target.SetMotorSpeeds(lo, hi);
            sentLow = lo; sentHigh = hi;
            rumbling = target;
        }
    }

    /// <summary>Gives a controller/keyboard user a selected button again after the mouse deselected everything.</summary>
    public class SelectionKeeper : MonoBehaviour
    {
        GameObject last;

        void Update()
        {
            var es = EventSystem.current;
            if (es == null || GameInput.Capturing) return;
            var cur = es.currentSelectedGameObject;
            if (cur != null && cur.activeInHierarchy) { last = cur; return; }
            bool nav = GameInput.NavUp.WasPressedThisFrame() || GameInput.NavDown.WasPressedThisFrame() || GameInput.NavLeft.WasPressedThisFrame() || GameInput.NavRight.WasPressedThisFrame();
            if (!nav) return;
            if (last != null && last.activeInHierarchy) { es.SetSelectedGameObject(last); return; }
            foreach (var s in UnityEngine.UI.Selectable.allSelectablesArray)
                if (s != null && s.IsInteractable() && s.navigation.mode != UnityEngine.UI.Navigation.Mode.None) { es.SetSelectedGameObject(s.gameObject); return; }
        }
    }
}
