using UnityEngine;
using UnityEngine.InputSystem;

namespace InkDrift
{
    /// <summary>Keyboard + gamepad driving input. Digital keys are smoothed so keyboard drifting is possible.</summary>
    [RequireComponent(typeof(CarController))]
    public class PlayerDriver : MonoBehaviour
    {
        CarController car;
        InputAction steer, throttle, brake, handbrake, clutch, shiftUp, shiftDown, resetCar, cameraCycle, pause, lookBack;
        float kbSteer, kbThrottle, kbBrake;

        public static bool LookBackHeld { get; private set; }
        public static event System.Action CameraCyclePressed;
        public static event System.Action PausePressed;
        public static event System.Action ResetPressed;

        void Awake() { car = GetComponent<CarController>(); }

        void OnEnable()
        {
            steer = new InputAction("Steer", InputActionType.Value);
            steer.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/a").With("Positive", "<Keyboard>/d");
            steer.AddCompositeBinding("1DAxis").With("Negative", "<Keyboard>/leftArrow").With("Positive", "<Keyboard>/rightArrow");
            steer.AddBinding("<Gamepad>/leftStick/x");

            throttle = Make("Throttle", "<Keyboard>/w", "<Keyboard>/upArrow", "<Gamepad>/rightTrigger");
            brake = Make("Brake", "<Keyboard>/s", "<Keyboard>/downArrow", "<Gamepad>/leftTrigger");
            handbrake = Make("Handbrake", "<Keyboard>/space", "<Gamepad>/buttonSouth");
            clutch = Make("Clutch", "<Keyboard>/leftShift", "<Gamepad>/buttonWest");
            shiftUp = Make("ShiftUp", "<Keyboard>/e", "<Gamepad>/rightShoulder");
            shiftDown = Make("ShiftDown", "<Keyboard>/q", "<Gamepad>/leftShoulder");
            resetCar = Make("Reset", "<Keyboard>/r", "<Gamepad>/select");
            cameraCycle = Make("Camera", "<Keyboard>/c", "<Gamepad>/buttonNorth");
            pause = Make("Pause", "<Keyboard>/escape", "<Gamepad>/start");
            lookBack = Make("LookBack", "<Keyboard>/b", "<Gamepad>/rightStickPress");

            foreach (var a in All()) a.Enable();
            shiftUp.performed += _ => car.ShiftUp();
            shiftDown.performed += _ => car.ShiftDown();
            resetCar.performed += _ => ResetPressed?.Invoke();
            cameraCycle.performed += _ => CameraCyclePressed?.Invoke();
            pause.performed += _ => PausePressed?.Invoke();
        }

        void OnDisable()
        {
            foreach (var a in All()) { a.Disable(); a.Dispose(); }
        }

        InputAction[] All() => new[] { steer, throttle, brake, handbrake, clutch, shiftUp, shiftDown, resetCar, cameraCycle, pause, lookBack };

        static InputAction Make(string name, params string[] bindings)
        {
            var a = new InputAction(name, InputActionType.Value);
            foreach (var b in bindings) a.AddBinding(b);
            return a;
        }

        bool GamepadActive()
        {
            var g = Gamepad.current;
            if (g == null) return false;
            return Mathf.Abs(g.leftStick.x.ReadValue()) > 0.08f || g.rightTrigger.ReadValue() > 0.05f || g.leftTrigger.ReadValue() > 0.05f;
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            float rawSteer = steer.ReadValue<float>();
            float rawThrottle = throttle.ReadValue<float>();
            float rawBrake = brake.ReadValue<float>();
            bool pad = GamepadActive();

            CarInputState s = car.input;
            if (pad)
            {
                float x = rawSteer;
                float dead = 0.06f;
                x = Mathf.Sign(x) * Mathf.Clamp01((Mathf.Abs(x) - dead) / (1f - dead));
                x = Mathf.Sign(x) * Mathf.Pow(Mathf.Abs(x), 1.35f);
                s.steer = x;
                s.throttle = rawThrottle;
                s.brake = rawBrake;
                kbSteer = x; kbThrottle = rawThrottle; kbBrake = rawBrake;
            }
            else
            {
                // Keyboard: ramp toward the target, return to center faster, and counter-steer snaps quickly.
                float target = rawSteer;
                bool reversing = Mathf.Abs(target) > 0.01f && Mathf.Sign(target) != Mathf.Sign(kbSteer) && Mathf.Abs(kbSteer) > 0.05f;
                float rate = Mathf.Abs(target) < 0.01f ? 5.5f : (reversing ? 9f : 3.4f);
                kbSteer = Mathf.MoveTowards(kbSteer, target, rate * dt);
                kbThrottle = Mathf.MoveTowards(kbThrottle, rawThrottle, (rawThrottle > kbThrottle ? 7f : 10f) * dt);
                kbBrake = Mathf.MoveTowards(kbBrake, rawBrake, 8f * dt);
                s.steer = kbSteer;
                s.throttle = kbThrottle;
                s.brake = kbBrake;
            }
            s.handbrake = handbrake.ReadValue<float>() > 0.5f;
            s.clutch = clutch.ReadValue<float>();
            car.input.steer = s.steer;
            car.input.throttle = s.throttle;
            car.input.brake = s.brake;
            car.input.handbrake = s.handbrake;
            car.input.clutch = s.clutch;
            LookBackHeld = lookBack.ReadValue<float>() > 0.5f;
        }
    }
}
