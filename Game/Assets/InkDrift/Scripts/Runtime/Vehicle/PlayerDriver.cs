using UnityEngine;

namespace InkDrift
{
    /// <summary>Feeds <see cref="GameInput"/> into the car. Keys are smoothed so keyboard drifting is possible; analog input is shaped by the player's response curve.</summary>
    [RequireComponent(typeof(CarController))]
    public class PlayerDriver : MonoBehaviour
    {
        CarController car;
        float kbSteer, kbThrottle, kbBrake;
        bool steerAnalog, throttleAnalog, brakeAnalog;

        public static bool LookBackHeld { get; private set; }
        public static event System.Action CameraCyclePressed;
        public static event System.Action PausePressed;
        public static event System.Action ResetPressed;

        void Awake()
        {
            car = GetComponent<CarController>();
            GameInput.Init();
        }

        void OnDisable()
        {
            LookBackHeld = false;
            GameInput.SetEngineRumble(0f, 0f);
        }

        void Update()
        {
            if (GameInput.Pause.WasPressedThisFrame()) PausePressed?.Invoke();
            if (Time.timeScale <= 0f) { GameInput.SetEngineRumble(0f, 0f); return; }

            if (GameInput.ShiftUp.WasPressedThisFrame()) car.ShiftUp();
            if (GameInput.ShiftDown.WasPressedThisFrame()) car.ShiftDown();
            if (GameInput.ResetCar.WasPressedThisFrame()) ResetPressed?.Invoke();
            if (GameInput.CameraCycle.WasPressedThisFrame()) CameraCyclePressed?.Invoke();

            float dt = Time.unscaledDeltaTime;
            float rawSteer = GameInput.Steer.ReadValue<float>();
            float rawThrottle = GameInput.Throttle.ReadValue<float>();
            float rawBrake = GameInput.Brake.ReadValue<float>();

            if (GameInput.FromController(GameInput.Steer, ref steerAnalog))
            {
                // dead zone is applied by the Input System (Settings ▸ Controls ▸ dead zone); shape the rest
                kbSteer = Mathf.Sign(rawSteer) * Mathf.Pow(Mathf.Abs(rawSteer), GameSession.SteerResponse);
            }
            else
            {
                // keyboard: ramp toward the target, return to center faster, and counter-steer snaps quickly
                float target = rawSteer;
                bool reversing = Mathf.Abs(target) > 0.01f && Mathf.Sign(target) != Mathf.Sign(kbSteer) && Mathf.Abs(kbSteer) > 0.05f;
                float rate = Mathf.Abs(target) < 0.01f ? 5.5f : (reversing ? 9f : 3.4f);
                kbSteer = Mathf.MoveTowards(kbSteer, target, rate * dt);
            }
            kbThrottle = GameInput.FromController(GameInput.Throttle, ref throttleAnalog)
                ? Pedal(rawThrottle)
                : Mathf.MoveTowards(kbThrottle, rawThrottle, (rawThrottle > kbThrottle ? 7f : 10f) * dt);
            kbBrake = GameInput.FromController(GameInput.Brake, ref brakeAnalog)
                ? Pedal(rawBrake)
                : Mathf.MoveTowards(kbBrake, rawBrake, 8f * dt);

            car.input.steer = kbSteer;
            car.input.throttle = kbThrottle;
            car.input.brake = kbBrake;
            car.input.handbrake = GameInput.Handbrake.ReadValue<float>() > 0.5f;
            car.input.clutch = GameInput.Clutch.ReadValue<float>();
            LookBackHeld = GameInput.LookBack.ReadValue<float>() > 0.5f;

            UpdateRumble();
        }

        /// <summary>Small trigger dead zone so a resting trigger never creeps the throttle.</summary>
        static float Pedal(float v) => Mathf.Clamp01((v - 0.03f) / 0.97f);

        void UpdateRumble()
        {
            if (!GameInput.UsingGamepad || car.frozen) { GameInput.SetEngineRumble(0f, 0f); return; }
            // low motor: tyres sliding / scrubbing; high motor: rev limiter buzz and big wheelspin
            float slide = car.GroundedWheels > 0 ? Mathf.InverseLerp(8f, 40f, Mathf.Abs(car.DriftAngle)) * Mathf.InverseLerp(4f, 18f, car.SpeedMs) : 0f;
            float low = slide * 0.32f;
            float high = (car.OnLimiter ? 0.18f : 0f) + (car.input.handbrake && car.SpeedMs > 3f ? 0.1f : 0f);
            GameInput.SetEngineRumble(low, high);
        }
    }
}
