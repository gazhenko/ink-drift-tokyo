using System;
using System.Threading;
using UnityEditor;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.DualShock;
using UnityEngine.InputSystem.Layouts;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.Switch;
using UnityEngine.InputSystem.UI;
using UnityEngine.InputSystem.XInput;

namespace InkDrift.EditorTools
{
    /// <summary>
    /// Headless checks for GameInput / PadBridge with simulated devices (Xbox, PlayStation, Switch, an unrecognised
    /// HID pad, a Linux evdev pad): bindings, labels, rebinding, conflicts, persistence, remapping, disconnects.
    ///   Unity -batchmode -nographics -executeMethod InkDrift.EditorTools.InputSelfTest.Run   (exit code = failures)
    /// </summary>
    public static class InputSelfTest
    {
        static int fails, passes;

        static void Check(bool ok, string what)
        {
            if (ok) passes++; else fails++;
            Debug.Log($"[InputTest] {(ok ? "PASS" : "FAIL")} {what}");
        }

        static void Tick(int n = 1) { for (int i = 0; i < n; i++) InputSystem.Update(); }

        static void Set(InputDevice d, params (string path, float v)[] vals)
        {
            using (StateEvent.From(d, out var ev))
            {
                foreach (var (path, v) in vals) d[path].WriteValueIntoEvent(v, ev);
                InputSystem.QueueEvent(ev);
            }
            Tick();
        }

        static void Pad(Gamepad g, GamepadState s) { InputSystem.QueueStateEvent(g, s); Tick(); }

        [MenuItem("InkDrift/Tests/Input Self Test")]
        public static void Run()
        {
            int code = 99;
            var oldMode = InputSystem.settings.updateMode;
            try { code = RunAll(); }
            catch (Exception e) { Debug.LogError("[InputTest] exception " + e); }
            finally { InputSystem.settings.updateMode = oldMode; Cleanup(); }
            Debug.Log($"[InputTest] {passes} passed, {fails} failed");
            if (Application.isBatchMode) EditorApplication.Exit(code);
        }

        static void Cleanup()
        {
            PlayerPrefs.DeleteKey("ink_bindings_v1");
            PlayerPrefs.DeleteKey("pad_labels");
            foreach (var d in InputSystem.devices.ToArray())
                if (d.description.interfaceName == "TestHID" || d.description.interfaceName == "Linux" || d is XInputController) PadBridge.Forget(d);
        }

        /// <summary>Edit-mode updates normally go to editor-only state; route them like player updates (as play mode would).</summary>
        static void PlayerUpdatesInEditMode(bool on)
        {
            var mgr = typeof(InputSystem).GetField("s_Manager", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static).GetValue(null);
            mgr.GetType().GetProperty("runPlayerUpdatesInEditMode").SetValue(mgr, on);
        }

        static int RunAll()
        {
            InputSystem.settings.updateMode = InputSettings.UpdateMode.ProcessEventsManually;
            PlayerUpdatesInEditMode(true);
            PlayerPrefs.DeleteKey("ink_bindings_v1");
            GameSession.PadLabels = 0;
            GameInput.Init();
            GameInput.ResetAllBindings();
            var kb = InputSystem.GetDevice<Keyboard>() ?? InputSystem.AddDevice<Keyboard>();
            if (InputSystem.GetDevice<Mouse>() == null) InputSystem.AddDevice<Mouse>();
            Tick();

            // ---------------------------------------------------------- Xbox (XInput) pad
            var x = InputSystem.AddDevice<XInputController>();
            Tick();
            Pad(x, new GamepadState { leftStick = new Vector2(-0.8f, 0f), rightTrigger = 1f }.WithButton(GamepadButton.South));
            Check(GameInput.Throttle.ReadValue<float>() > 0.95f, "Xbox RT → throttle");
            Check(GameInput.Steer.ReadValue<float>() < -0.6f, $"Xbox left stick → steer left ({GameInput.Steer.ReadValue<float>():0.00})");
            Check(GameInput.Handbrake.ReadValue<float>() > 0.5f, "Xbox A → handbrake");
            Check(GameInput.UsingGamepad && GameInput.ActivePad == x, "Xbox pad becomes the active device");
            Check(GameInput.Style == PadStyle.Xbox, "Xbox button labels");
            Check(GameInput.Label(Bind.Handbrake, Slot.Pad, false) == "A" && GameInput.Label(Bind.Throttle, Slot.Pad, false) == "RT", "labels A / RT");
            Pad(x, new GamepadState().WithButton(GamepadButton.Start));
            Check(GameInput.Pause.WasPressedThisFrame(), "Xbox Menu → pause");
            Pad(x, new GamepadState().WithButton(GamepadButton.DpadDown));
            Check(GameInput.NavDown.WasPressedThisFrame(), "Xbox d-pad → menu navigation");
            Pad(x, new GamepadState { leftStick = new Vector2(0f, -0.9f) });
            Check(GameInput.NavDown.IsPressed(), "Xbox left stick → menu navigation");
            Pad(x, new GamepadState().WithButton(GamepadButton.East));
            Check(GameInput.Back.WasPressedThisFrame(), "Xbox B → back");
            Pad(x, new GamepadState());

            // ---------------------------------------------------------- keyboard
            InputSystem.QueueStateEvent(kb, new KeyboardState(Key.W, Key.A)); Tick();
            Check(GameInput.Throttle.ReadValue<float>() > 0.95f && GameInput.Steer.ReadValue<float>() < -0.95f, "keyboard W/A → throttle/steer");
            Check(!GameInput.UsingGamepad && GameInput.Label(Bind.Throttle) == "W", "keyboard use switches labels to keys");
            InputSystem.QueueStateEvent(kb, new KeyboardState(Key.UpArrow, Key.RightArrow)); Tick();
            Check(GameInput.Throttle.ReadValue<float>() > 0.95f && GameInput.Steer.ReadValue<float>() > 0.95f, "arrow keys (second key column)");
            InputSystem.QueueStateEvent(kb, new KeyboardState()); Tick();

            // ---------------------------------------------------------- PlayStation / Switch detection
            try
            {
                var ds = InputSystem.AddDevice<DualSenseGamepadHID>();
                var ds4 = InputSystem.AddDevice<DualShock4GamepadHID>();
                var sw = InputSystem.AddDevice<SwitchProControllerHID>();
                Check(GameInput.StyleOf(ds) == PadStyle.PlayStation && GameInput.StyleOf(ds4) == PadStyle.PlayStation, "DualSense / DualShock 4 → PlayStation labels");
                Check(GameInput.StyleOf(sw) == PadStyle.Nintendo, "Switch Pro → Nintendo labels");
                Check(PadBridge.VirtualFor(ds) == null && PadBridge.VirtualFor(sw) == null, "recognised pads are not bridged");
                InputSystem.RemoveDevice(ds); InputSystem.RemoveDevice(ds4); InputSystem.RemoveDevice(sw);
            }
            catch (Exception e) { Check(false, "PlayStation/Switch devices: " + e.Message); }
            Check(GameInput.PadLabel("<Gamepad>/buttonSouth", PadStyle.PlayStation, false) == "×" && GameInput.PadLabel("<Gamepad>/buttonSouth", PadStyle.Nintendo, false) == "B"
                  && GameInput.PadLabel("<Gamepad>/rightTrigger", PadStyle.PlayStation, false) == "R2" && GameInput.PadLabel("<Gamepad>/leftTrigger", PadStyle.Nintendo, false) == "ZL", "PlayStation / Nintendo button names");
            var dsDesc = new InputDeviceDescription { interfaceName = "HID", manufacturer = "Sony Interactive Entertainment", product = "Wireless Controller" };
            Check(GameInput.GuessStyle(dsDesc, "Wireless Controller") == PadStyle.PlayStation, "generic Sony pad → PlayStation labels");

            // ---------------------------------------------------------- unrecognised HID pad (generic Xbox-layout pad on macOS/Windows)
            InputSystem.RegisterLayout(@"{
                ""name"": ""TestHIDPad"", ""extend"": ""Joystick"", ""format"": ""TPAD"",
                ""controls"": [
                    { ""name"": ""button2"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 1, ""format"": ""BIT"" },
                    { ""name"": ""button3"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 2, ""format"": ""BIT"" },
                    { ""name"": ""button4"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 3, ""format"": ""BIT"" },
                    { ""name"": ""button5"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 4, ""format"": ""BIT"" },
                    { ""name"": ""button6"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 5, ""format"": ""BIT"" },
                    { ""name"": ""button7"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 6, ""format"": ""BIT"" },
                    { ""name"": ""button8"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 7, ""format"": ""BIT"" },
                    { ""name"": ""button9"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 8, ""format"": ""BIT"" },
                    { ""name"": ""button10"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 9, ""format"": ""BIT"" },
                    { ""name"": ""button11"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 10, ""format"": ""BIT"" },
                    { ""name"": ""button12"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 11, ""format"": ""BIT"" },
                    { ""name"": ""z"", ""layout"": ""Axis"", ""offset"": 12, ""format"": ""FLT"" },
                    { ""name"": ""rz"", ""layout"": ""Axis"", ""offset"": 16, ""format"": ""FLT"" },
                    { ""name"": ""rx"", ""layout"": ""Axis"", ""offset"": 20, ""format"": ""FLT"" },
                    { ""name"": ""ry"", ""layout"": ""Axis"", ""offset"": 24, ""format"": ""FLT"" },
                    { ""name"": ""hat"", ""layout"": ""Dpad"", ""offset"": 28, ""format"": ""BIT"", ""sizeInBits"": 4 }
                ] }", "TestHIDPad", new InputDeviceMatcher().WithInterface("TestHID"));
            var joy = InputSystem.AddDevice(new InputDeviceDescription { interfaceName = "TestHID", manufacturer = "ACME", product = "USB Gamepad" });
            Tick();
            var vjoy = PadBridge.VirtualFor(joy);
            Check(joy is Joystick, "test HID pad is only a Joystick to Unity");
            Check(vjoy != null && PadBridge.IsMasked(joy), "unrecognised pad → virtual gamepad, raw device masked");
            Set(joy, ("button2", 1f));
            Check(GameInput.Handbrake.ReadValue<float>() > 0.5f, "HID button 2 (A/×) → handbrake");
            Check(GameInput.ActivePad == vjoy && GameInput.UsingGamepad, "bridged pad becomes the active device");
            Set(joy, ("button2", 0f), ("trigger", 1f));
            Check(GameInput.Clutch.ReadValue<float>() > 0.5f, "HID button 1 (X/□) → clutch");
            Set(joy, ("trigger", 0f), ("ry", 1f), ("stick/x", -1f));
            Check(GameInput.Throttle.ReadValue<float>() > 0.9f, "HID Ry analog trigger → throttle");
            Check(GameInput.Steer.ReadValue<float>() < -0.9f, "HID stick → steer");
            Set(joy, ("ry", 0f), ("stick/x", 0f), ("button10", 1f));
            Check(GameInput.Pause.WasPressedThisFrame(), "HID button 10 (start) → pause");
            Set(joy, ("button10", 0f), ("hat/right", 1f));
            Check(GameInput.NavRight.WasPressedThisFrame(), "HID hat → menu navigation");
            Set(joy, ("hat/right", 0f));
            Check(GameInput.StyleOf(vjoy) == PadStyle.Xbox, "unknown pad defaults to Xbox labels");

            // ---------------------------------------------------------- Linux evdev-named pad (xpad naming)
            InputSystem.RegisterLayout(@"{
                ""name"": ""TestSDLPad"", ""format"": ""LJOY"",
                ""controls"": [
                    { ""name"": ""A"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 0, ""format"": ""BIT"" },
                    { ""name"": ""B"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 1, ""format"": ""BIT"" },
                    { ""name"": ""X"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 2, ""format"": ""BIT"" },
                    { ""name"": ""Y"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 3, ""format"": ""BIT"" },
                    { ""name"": ""TriggerLeft"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 4, ""format"": ""BIT"" },
                    { ""name"": ""TriggerRight"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 5, ""format"": ""BIT"" },
                    { ""name"": ""Select"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 6, ""format"": ""BIT"" },
                    { ""name"": ""Start"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 7, ""format"": ""BIT"" },
                    { ""name"": ""ThumbLeft"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 8, ""format"": ""BIT"" },
                    { ""name"": ""ThumbRight"", ""layout"": ""Button"", ""offset"": 0, ""bit"": 9, ""format"": ""BIT"" },
                    { ""name"": ""Stick"", ""layout"": ""Stick"", ""offset"": 4, ""format"": ""VEC2"" },
                    { ""name"": ""Z"", ""layout"": ""Axis"", ""offset"": 12, ""format"": ""FLT"", ""defaultState"": ""-1"" },
                    { ""name"": ""RotateZ"", ""layout"": ""Axis"", ""offset"": 16, ""format"": ""FLT"", ""defaultState"": ""-1"" },
                    { ""name"": ""RotateX"", ""layout"": ""Axis"", ""offset"": 20, ""format"": ""FLT"" },
                    { ""name"": ""RotateY"", ""layout"": ""Axis"", ""offset"": 24, ""format"": ""FLT"" },
                    { ""name"": ""Hat"", ""layout"": ""Dpad"", ""offset"": 28, ""format"": ""BIT"", ""sizeInBits"": 4 }
                ] }", "TestSDLPad", new InputDeviceMatcher().WithInterface("Linux").WithProduct("Test.*"));
            var lnx = InputSystem.AddDevice(new InputDeviceDescription { interfaceName = "Linux", manufacturer = "Microsoft", product = "Test X-Box 360 pad" });
            Tick();
            Check(PadBridge.VirtualFor(lnx) != null, "Linux evdev pad → virtual gamepad");
            Set(lnx, ("X", 1f));
            Check(GameInput.Clutch.ReadValue<float>() > 0.5f, "xpad X (west) → clutch");
            Set(lnx, ("X", 0f), ("Y", 1f));
            Check(GameInput.CameraCycle.WasPressedThisFrame(), "xpad Y (north) → camera");
            Set(lnx, ("Y", 0f));
            Check(GameInput.Brake.ReadValue<float>() < 0.05f, "evdev trigger resting at -1 reads as released");
            Set(lnx, ("Z", 1f), ("Stick/x", 1f));
            Check(GameInput.Brake.ReadValue<float>() > 0.9f && GameInput.Steer.ReadValue<float>() > 0.9f, "evdev Z → brake, stick → steer");
            Set(lnx, ("Z", -1f), ("Stick/x", 0f));
            var sony = InputSystem.AddDevice(new InputDeviceDescription { interfaceName = "Linux", manufacturer = "Sony Interactive Entertainment", product = "Test Wireless Controller" });
            Tick();
            Set(sony, ("Y", 1f));
            Check(GameInput.Clutch.ReadValue<float>() > 0.5f, "hid-playstation BTN_WEST (□) → clutch");
            Set(sony, ("Y", 0f));
            InputSystem.RemoveDevice(sony);

            // ---------------------------------------------------------- rebinding
            bool? result = null;
            GameInput.StartRebind(Bind.Throttle, Slot.Pad, ok => result = ok);
            Check(GameInput.Capturing, "gameplay/menu actions paused while listening");
            Pad(x, new GamepadState().WithButton(GamepadButton.North));
            Wait(() => result.HasValue);
            Pad(x, new GamepadState());
            Check(result == true && GameInput.PathOf(Bind.Throttle, Slot.Pad) == "<Gamepad>/buttonNorth", $"rebind throttle → Y ({GameInput.PathOf(Bind.Throttle, Slot.Pad)})");
            Check(GameInput.PathOf(Bind.Camera, Slot.Pad) == "" && GameInput.LastConflict == "CAMERA", "duplicate removed from CAMERA");
            Check(!GameInput.Capturing, "actions resume after rebinding");
            Pad(x, new GamepadState().WithButton(GamepadButton.North));
            Check(GameInput.Throttle.ReadValue<float>() > 0.9f && !GameInput.CameraCycle.IsPressed(), "Y now drives throttle only");
            Pad(x, new GamepadState());

            result = null;
            GameInput.StartRebind(Bind.SteerLeft, Slot.Pad, ok => result = ok);
            Pad(x, new GamepadState { rightStick = new Vector2(-1f, 0f) });
            Wait(() => result.HasValue);
            Pad(x, new GamepadState());
            Check(GameInput.PathOf(Bind.SteerLeft, Slot.Pad) == "<Gamepad>/rightStick/left", $"steer left → right stick ({GameInput.PathOf(Bind.SteerLeft, Slot.Pad)})");
            Pad(x, new GamepadState { rightStick = new Vector2(-0.7f, 0f) });
            Check(GameInput.Steer.ReadValue<float>() < -0.4f, $"analog steering from a rebound stick half ({GameInput.Steer.ReadValue<float>():0.00})");
            Pad(x, new GamepadState());

            result = null;
            GameInput.StartRebind(Bind.Handbrake, Slot.Key1, ok => result = ok);
            InputSystem.QueueStateEvent(kb, new KeyboardState(Key.H)); Tick();
            Wait(() => result.HasValue);
            InputSystem.QueueStateEvent(kb, new KeyboardState()); Tick();
            Check(GameInput.PathOf(Bind.Handbrake, Slot.Key1) == "<Keyboard>/h", $"rebind handbrake key → H ({GameInput.PathOf(Bind.Handbrake, Slot.Key1)})");

            result = null;
            GameInput.StartRebind(Bind.Brake, Slot.Key1, ok => result = ok);
            InputSystem.QueueStateEvent(kb, new KeyboardState(Key.Escape)); Tick();
            Wait(() => result.HasValue);
            InputSystem.QueueStateEvent(kb, new KeyboardState()); Tick();
            Check(result == false && GameInput.PathOf(Bind.Brake, Slot.Key1) == "<Keyboard>/s", "ESC cancels a key rebind");

            result = null;
            GameInput.StartRebind(Bind.ShiftUp, Slot.Pad, ok => result = ok);
            Set(joy, ("button6", 1f));
            Wait(() => result.HasValue);
            Set(joy, ("button6", 0f));
            Check(GameInput.PathOf(Bind.ShiftUp, Slot.Pad) == "<Gamepad>/rightShoulder", $"rebind with a bridged pad stores a gamepad path ({GameInput.PathOf(Bind.ShiftUp, Slot.Pad)})");

            // ---------------------------------------------------------- persistence
            GameInput.Asset.FindActionMap("Drive").RemoveAllBindingOverrides();
            typeof(GameInput).GetMethod("LoadOverrides", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static).Invoke(null, null);
            Check(GameInput.PathOf(Bind.Throttle, Slot.Pad) == "<Gamepad>/buttonNorth" && GameInput.PathOf(Bind.Handbrake, Slot.Key1) == "<Keyboard>/h"
                  && GameInput.PathOf(Bind.Camera, Slot.Pad) == "" && GameInput.PathOf(Bind.SteerLeft, Slot.Pad) == "<Gamepad>/rightStick/left", "saved bindings (incl. cleared ones) reload");
            GameInput.ResetBinding(Bind.Throttle, Slot.Pad);
            GameInput.ResetBinding(Bind.Camera, Slot.Pad);
            Check(GameInput.PathOf(Bind.Throttle, Slot.Pad) == "<Gamepad>/rightTrigger" && GameInput.PathOf(Bind.Camera, Slot.Pad) == "<Gamepad>/buttonNorth", "per-slot reset to default");
            GameInput.ClearBinding(Bind.Pause, Slot.Key2);
            Check(GameInput.PathOf(Bind.Pause, Slot.Key2) == "" && GameInput.Label(Bind.Pause, Slot.Key2) == "—", "clear a key slot");
            GameInput.ResetAllBindings();
            Check(GameInput.PathOf(Bind.SteerLeft, Slot.Pad) == "<Gamepad>/leftStick/left" && GameInput.PathOf(Bind.Handbrake, Slot.Key1) == "<Keyboard>/space", "reset all");

            // ---------------------------------------------------------- remapping a recognised pad (Controller Setup result)
            var map = new PadMapping();
            map.entries.Add(new PadMapEntry { target = PadTarget.South, control = "buttonEast", rest = 0, full = 1 });
            map.entries.Add(new PadMapEntry { target = PadTarget.East, control = "buttonSouth", rest = 0, full = 1 });
            map.entries.Add(new PadMapEntry { target = PadTarget.LeftStickX, control = "leftStick/x", rest = 0, full = -1 });
            map.entries.Add(new PadMapEntry { target = PadTarget.RightTrigger, control = "rightTrigger", rest = 0, full = 1 });
            PadBridge.SaveCustom(x, map);
            Tick();
            Check(PadBridge.IsMasked(x) && PadBridge.HasCustomMapping(x), "custom layout bridges a recognised pad and masks it");
            Pad(x, new GamepadState().WithButton(GamepadButton.East));
            Check(GameInput.Handbrake.ReadValue<float>() > 0.5f, "remapped: physical B now acts as A (handbrake)");
            Pad(x, new GamepadState().WithButton(GamepadButton.South));
            Check(GameInput.Handbrake.ReadValue<float>() < 0.5f, "remapped: physical A no longer handbrake (raw pad masked)");
            Pad(x, new GamepadState { leftStick = new Vector2(1f, 0f) });
            Check(GameInput.Steer.ReadValue<float>() < -0.9f, "remapped: inverted steering axis");
            Pad(x, new GamepadState());
            PadBridge.Forget(x);
            Tick();
            Pad(x, new GamepadState().WithButton(GamepadButton.South));
            Check(!PadBridge.IsMasked(x) && GameInput.Handbrake.ReadValue<float>() > 0.5f, "undo setup restores Unity's layout");
            Pad(x, new GamepadState());

            // ---------------------------------------------------------- UI module + disconnect
            var es = GameInput.EnsureEventSystem();
            var module = es.GetComponent<InputSystemUIInputModule>();
            bool noJoystick = true;
            foreach (var b in module.submit.action.bindings) if (b.path.Contains("Joystick")) noJoystick = false;
            Check(module.actionsAsset == GameInput.Asset && module.submit.action.bindings.Count >= 4 && noJoystick, "UI module uses game UI actions (no raw-joystick bindings)");
            UnityEngine.Object.DestroyImmediate(es.gameObject);

            InputDevice lost = null;
            void OnLost(InputDevice d) => lost = d;
            GameInput.PadDisconnected += OnLost;
            Pad(x, new GamepadState().WithButton(GamepadButton.South));
            Pad(x, new GamepadState());
            InputSystem.RemoveDevice(x);
            Tick();
            Check(lost == x && !GameInput.UsingGamepad, "unplugging the active pad raises PadDisconnected");
            GameInput.PadDisconnected -= OnLost;
            InputSystem.RemoveDevice(joy);
            Tick();
            Check(vjoy != null && !vjoy.added, "unplugging a bridged pad removes its virtual gamepad");
            InputSystem.RemoveDevice(lnx);
            return fails;
        }

        static void Wait(Func<bool> done, float seconds = 3f)
        {
            var t0 = DateTime.Now;
            while (!done() && (DateTime.Now - t0).TotalSeconds < seconds) { Thread.Sleep(15); Tick(); }
        }
    }
}
