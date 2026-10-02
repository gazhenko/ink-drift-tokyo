using System;
using UnityEngine;

namespace InkDrift
{
    public struct CarInputState
    {
        public float steer;      // -1 left .. +1 right
        public float throttle;   // 0..1
        public float brake;      // 0..1
        public float clutch;     // 0 engaged .. 1 pedal to floor
        public bool handbrake;
        public bool shiftUp, shiftDown;   // edge-triggered, consumed by the controller
    }

    public enum Transmission { Automatic, Manual }

    /// <summary>
    /// Raycast-suspension car with a combined-slip tire model, a two-inertia clutch (so clutch kicks are
    /// physically real), locked drift diff, turbo spool, rev limiter and an auto/manual gearbox.
    /// Wheel order everywhere: 0 FL, 1 FR, 2 RL, 3 RR.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class CarController : MonoBehaviour
    {
        public const int CarLayer = 8;
        const float RadToRpm = 60f / (2f * Mathf.PI);
        const int SubSteps = 8;

        public CarSpec spec = new CarSpec();
        public CarInputState input;
        public Transmission transmission = Transmission.Automatic;
        [Range(0, 2)] public int assistLevel = 1;   // 0 = PRO, 1 = counter-steer help, 2 = + yaw damping
        public bool frozen;
        public bool stabilityControl;   // yaw damping without steering assist (AI)
        public Transform[] wheelVisuals = new Transform[4];
        public Transform[] caliperVisuals = new Transform[4];

        public class Wheel
        {
            public Vector3 localMount;
            public bool front, left, driven;
            public bool grounded;
            public RaycastHit hit;
            public float compression, prevCompression, load;
            public float omega, spinAngle, steerAngle;
            public Vector3 fwd, side, point, normal;
            public float vLong, vLat;
            public float fx, fy;
            public float slipRatio, slipAngleDeg, slipSpeed, slideAmount;
            public float surfaceGrip = 1f, surfaceDrag;
            public bool offroad;
            public float visualOffset;   // suspension displacement of the wheel center below the mount
        }

        public readonly Wheel[] wheels = new Wheel[4];

        // ---- public telemetry ----
        public float EngineRpm => engineOmega * RadToRpm;
        public int Gear => gear;               // -1 R, 0 N, 1..n
        public float SpeedMs { get; private set; }
        public float SpeedKmh => SpeedMs * 3.6f;
        public float ForwardSpeed { get; private set; }
        public float DriftAngle { get; private set; }     // signed degrees, + = velocity to the right of heading
        public float YawRate { get; private set; }
        public float Throttle { get; private set; }
        public float Boost { get; private set; }
        public bool OnLimiter => limiterCut;
        public bool IsShifting => shiftTimer > 0f;
        /// <summary>The gear being shifted into (the current gear when not shifting).</summary>
        public int PendingGear => shiftTimer > 0f ? pendingGear : gear;
        public int GroundedWheels { get; private set; }
        public float SteerAngle => steerAngle;
        public float EngineLoad { get; private set; }
        public Rigidbody Body => rb;

        public event Action<int> OnGearChanged;
        public event Action OnBackfire;
        public event Action OnBlowOff;
        public event Action<float, Vector3, Collision> OnImpact;

        Rigidbody rb;
        float engineOmega;
        int gear = 1;
        float shiftTimer;
        int pendingGear;
        bool limiterCut;
        float limiterTimer;
        float steerAngle;
        float reverseHold;
        float prevThrottle;
        float overrunTimer;
        float axleInertiaRear, axleInertiaFront;
        int groundMask;
        readonly float[] fxAcc = new float[4], fyAcc = new float[4];

        public float MaxSpeedInGear(int g)
        {
            float r = RatioFor(g);
            return r == 0 ? 0 : spec.revLimitRpm / RadToRpm / Mathf.Abs(r) * spec.wheelRadius;
        }

        void Awake()
        {
            rb = GetComponent<Rigidbody>();
            Init();
        }

        public void Init()
        {
            rb = GetComponent<Rigidbody>();
            rb.mass = spec.mass;
            rb.centerOfMass = spec.centerOfMass;
            float L = spec.wheelbase + 1.7f, W = Mathf.Max(spec.trackFront, spec.trackRear) + 0.3f, H = 1.25f;
            rb.inertiaTensor = new Vector3(
                spec.mass * (H * H + L * L) / 12f * spec.inertiaScale.x * 0.85f,
                spec.mass * (W * W + L * L) / 12f * spec.inertiaScale.y * 0.85f,
                spec.mass * (H * H + W * W) / 12f * spec.inertiaScale.z * 0.85f);
            rb.inertiaTensorRotation = Quaternion.identity;
            rb.maxAngularVelocity = 25f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.ContinuousDynamic;
            rb.linearDamping = 0f;
            rb.angularDamping = 0.05f;

            groundMask = ~((1 << CarLayer) | (1 << 2)); // ignore cars and IgnoreRaycast

            float zf = spec.frontAxleZ, zr = spec.frontAxleZ - spec.wheelbase;
            float rearWeightFrac = Mathf.Clamp01((zf - spec.centerOfMass.z) / spec.wheelbase);
            for (int i = 0; i < 4; i++)
            {
                bool front = i < 2, left = (i % 2) == 0;
                float track = front ? spec.trackFront : spec.trackRear;
                float axleLoad = spec.mass * 9.81f * (front ? 1f - rearWeightFrac : rearWeightFrac) * 0.5f;
                float k = front ? spec.springFront : spec.springRear;
                float staticComp = Mathf.Clamp(axleLoad / k, 0.01f, spec.restLength * 0.6f);
                float mount = spec.restLength + spec.wheelRadius - staticComp; // so the origin sits on the ground at rest
                wheels[i] = new Wheel
                {
                    front = front, left = left,
                    localMount = new Vector3(left ? -track * 0.5f : track * 0.5f, mount, front ? zf : zr),
                    driven = spec.drive == DriveType.AWD || !front,
                    compression = staticComp, prevCompression = staticComp,
                };
            }
            axleInertiaRear = spec.wheelInertia * 2f + 0.15f;
            axleInertiaFront = spec.wheelInertia * 2f + 0.10f;
            engineOmega = spec.idleRpm / RadToRpm;
            gear = 1;
        }

        public void ResetTo(Vector3 position, Quaternion rotation)
        {
            rb.position = position;
            rb.rotation = rotation;
            transform.SetPositionAndRotation(position, rotation);
            rb.linearVelocity = Vector3.zero;
            rb.angularVelocity = Vector3.zero;
            foreach (var w in wheels) { w.omega = 0f; w.compression = w.prevCompression = 0.05f; }
            engineOmega = spec.idleRpm / RadToRpm;
            gear = 1; shiftTimer = 0f; steerAngle = 0f;
        }

        float RatioFor(int g)
        {
            if (g == 0) return 0f;
            if (g < 0) return -spec.reverseRatio * spec.finalDrive;
            return spec.gears[Mathf.Clamp(g - 1, 0, spec.gears.Length - 1)] * spec.finalDrive;
        }

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            Vector3 vel = rb.linearVelocity;
            Vector3 localVel = transform.InverseTransformDirection(vel);
            SpeedMs = vel.magnitude;
            ForwardSpeed = localVel.z;
            YawRate = transform.InverseTransformDirection(rb.angularVelocity).y;
            float planar = new Vector2(localVel.x, localVel.z).magnitude;
            DriftAngle = planar > 1.5f ? Mathf.Atan2(localVel.x, localVel.z) * Mathf.Rad2Deg : 0f;

            CarInputState inp = frozen ? new CarInputState { brake = 1f, handbrake = true, throttle = input.throttle, clutch = 1f } : input;

            UpdateGearbox(dt, ref inp, localVel);
            UpdateSteering(dt, inp, localVel);
            UpdateSuspension(dt);
            UpdateContactFrames();
            SimulateDrivetrain(dt, inp);
            ApplyTireForces();
            ApplyAero(vel);
            ApplyAssists(dt, inp, localVel);

            input.shiftUp = input.shiftDown = false;
        }

        // ------------------------------------------------------------------ steering
        void UpdateSteering(float dt, CarInputState inp, Vector3 localVel)
        {
            float speed = Mathf.Abs(localVel.z);
            // Grip-limited lock: the angle that puts the fronts just past their peak at this speed (+60% margin),
            // so full input turns hard without instantly spinning; sliding opens up full lock for counter-steer.
            float v = Mathf.Max(speed, 1f);
            float gripDeg = spec.wheelbase * 1.1f * 9.81f / (v * v) * Mathf.Rad2Deg + spec.peakSlipAngleDeg;
            float lockAtSpeed = Mathf.Min(spec.maxSteerDeg, gripDeg * 1.6f);
            float beta = localVel.z > 1f ? Mathf.Atan2(localVel.x, localVel.z) * Mathf.Rad2Deg : 0f;
            // Drifting opens up full lock so you can actually catch the slide.
            float lockLimit = Mathf.Max(lockAtSpeed, Mathf.Min(spec.maxSteerDeg, Mathf.Abs(beta) + 14f));
            float target = inp.steer * lockLimit;

            if (assistLevel > 0 && localVel.z > 3f)
            {
                float gain = assistLevel == 1 ? 0.5f : 0.85f;
                float userWeight = 1f - Mathf.Abs(inp.steer) * 0.6f;
                target += beta * gain * userWeight;
            }
            target = Mathf.Clamp(target, -spec.maxSteerDeg, spec.maxSteerDeg);
            steerAngle = Mathf.MoveTowards(steerAngle, target, spec.maxSteerDeg * 7f * dt);

            // ~50% Ackermann
            float a = Mathf.Abs(steerAngle);
            float inner = a, outer = a;
            if (a > 0.5f)
            {
                float R = spec.wheelbase / Mathf.Tan(a * Mathf.Deg2Rad);
                float half = spec.trackFront * 0.5f;
                float ackIn = Mathf.Atan(spec.wheelbase / Mathf.Max(0.5f, R - half)) * Mathf.Rad2Deg;
                float ackOut = Mathf.Atan(spec.wheelbase / (R + half)) * Mathf.Rad2Deg;
                inner = Mathf.Lerp(a, ackIn, 0.5f);
                outer = Mathf.Lerp(a, ackOut, 0.5f);
            }
            float s = Mathf.Sign(steerAngle);
            // Turning right (s>0): right wheel is inner.
            wheels[0].steerAngle = s * (s > 0 ? outer : inner);
            wheels[1].steerAngle = s * (s > 0 ? inner : outer);
            wheels[2].steerAngle = wheels[3].steerAngle = 0f;
        }

        // ------------------------------------------------------------------ suspension
        void UpdateSuspension(float dt)
        {
            Vector3 up = transform.up;
            int grounded = 0;
            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                Vector3 mountWS = transform.TransformPoint(w.localMount);
                float maxDist = spec.restLength + spec.wheelRadius;
                w.prevCompression = w.compression;
                if (Physics.Raycast(mountWS, -up, out w.hit, maxDist, groundMask, QueryTriggerInteraction.Ignore))
                {
                    w.grounded = true;
                    w.compression = maxDist - w.hit.distance;
                    w.point = w.hit.point;
                    w.normal = w.hit.normal;
                    ReadSurface(w);
                    grounded++;
                }
                else
                {
                    w.grounded = false;
                    w.compression = 0f;
                }
                w.visualOffset = spec.restLength - w.compression;
            }
            GroundedWheels = grounded;

            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                if (!w.grounded) { w.load = 0f; continue; }
                float k = w.front ? spec.springFront : spec.springRear;
                float cv = (w.compression - w.prevCompression) / dt;
                float damp = cv > 0f ? spec.damperBump : spec.damperRebound;
                float f = k * w.compression + damp * cv;
                float stop = spec.restLength * 0.85f;
                if (w.compression > stop) f += (w.compression - stop) * k * 10f;
                w.load = Mathf.Max(0f, f);
            }
            AntiRoll(0, 1, spec.antiRollFront);
            AntiRoll(2, 3, spec.antiRollRear);

            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                if (w.grounded && w.load > 0f) rb.AddForceAtPosition(up * w.load, w.point);
            }
        }

        void AntiRoll(int l, int r, float stiffness)
        {
            var wl = wheels[l]; var wr = wheels[r];
            if (!wl.grounded && !wr.grounded) return;
            float diff = (wl.compression - wr.compression) * stiffness;
            if (wl.grounded) wl.load = Mathf.Max(0f, wl.load + diff);
            if (wr.grounded) wr.load = Mathf.Max(0f, wr.load - diff);
        }

        void ReadSurface(Wheel w)
        {
            var mat = w.hit.collider.sharedMaterial;
            w.offroad = false; w.surfaceGrip = 1f; w.surfaceDrag = 0f;
            if (mat != null)
            {
                string n = mat.name;
                if (n.StartsWith("Grass")) { w.surfaceGrip = 0.62f; w.surfaceDrag = 0.06f; w.offroad = true; }
                else if (n.StartsWith("Dirt") || n.StartsWith("Gravel")) { w.surfaceGrip = 0.72f; w.surfaceDrag = 0.04f; w.offroad = true; }
                else if (n.StartsWith("Wet")) { w.surfaceGrip = 0.86f; }
                else if (n.StartsWith("Paint")) { w.surfaceGrip = 0.9f; }
            }
        }

        void UpdateContactFrames()
        {
            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                if (!w.grounded) { w.vLong = w.vLat = 0f; continue; }
                Vector3 heading = Quaternion.AngleAxis(w.steerAngle, transform.up) * transform.forward;
                w.fwd = Vector3.ProjectOnPlane(heading, w.normal).normalized;
                w.side = Vector3.Cross(w.normal, w.fwd);
                Vector3 pv = rb.GetPointVelocity(w.point);
                w.vLong = Vector3.Dot(pv, w.fwd);
                w.vLat = Vector3.Dot(pv, w.side);
            }
        }

        // ------------------------------------------------------------------ drivetrain + tires
        void SimulateDrivetrain(float dt, CarInputState inp)
        {
            float h = dt / SubSteps;
            float ratio = shiftTimer > 0f ? 0f : RatioFor(gear);
            float Ie = spec.engineInertia;

            // throttle (rev limiter / shift cut / downshift blip)
            float throttle = inp.throttle;
            if (gear < 0) throttle = inp.brake;  // reverse uses the brake pedal as throttle
            if (shiftTimer > 0f) throttle = pendingGear < gear ? 0.55f : 0f;
            if (limiterCut) throttle = 0f;
            Throttle = throttle;

            float rpm = EngineRpm;
            float targetBoost = spec.turboBoostGain > 0f ? throttle * Mathf.Clamp01((rpm - 2000f) / 2600f) : 0f;
            float prevBoost = Boost;
            Boost = Mathf.MoveTowards(Boost, targetBoost, dt / (targetBoost > Boost ? spec.turboSpool : 0.12f));
            if (prevBoost > 0.55f && throttle < 0.1f && prevThrottle > 0.6f) OnBlowOff?.Invoke();

            // overrun backfires when lifting at high rpm
            if (prevThrottle > 0.7f && throttle < 0.1f && rpm > spec.redlineRpm * 0.6f) overrunTimer = 0.6f;
            if (overrunTimer > 0f)
            {
                overrunTimer -= dt;
                if (UnityEngine.Random.value < dt * 9f) OnBackfire?.Invoke();
            }
            if (limiterCut && UnityEngine.Random.value < dt * 6f) OnBackfire?.Invoke();
            prevThrottle = throttle;

            float userClutch = inp.clutch;
            if (inp.handbrake && assistLevel > 0) userClutch = Mathf.Max(userClutch, 0.85f);

            float frontSplit = spec.drive == DriveType.AWD ? spec.frontTorqueSplit : 0f;
            float rearSplit = 1f - frontSplit;

            for (int i = 0; i < 4; i++) { wheels[i].fx = 0f; wheels[i].fy = 0f; }
            for (int i = 0; i < 4; i++) { fxAcc[i] = 0f; fyAcc[i] = 0f; }
            float loadAcc = 0f;

            for (int s = 0; s < SubSteps; s++)
            {
                rpm = EngineRpm;
                float torque = spec.TorqueAt(Mathf.Max(rpm, spec.idleRpm)) * (1f + Boost * spec.turboBoostGain) * throttle;
                float friction = spec.engineFriction * Mathf.Clamp01(rpm / 2000f) + spec.engineBrake * engineOmega * (1f - throttle);
                float Te = torque - friction;
                if (rpm < spec.idleRpm) Te += (spec.idleRpm - rpm) * 0.35f;  // idle governor

                // clutch: engine <-> transmission output (axle-speed weighted by split)
                float driveOmega = DrivenOmega(rearSplit, frontSplit);
                float rpmMatched = Mathf.Abs(driveOmega * ratio) * RadToRpm;
                float autoClutch = Mathf.Clamp01(Mathf.Max((rpm - spec.idleRpm * 1.05f) / 900f, (rpmMatched - spec.idleRpm * 1.1f) / 300f));
                float cap = spec.clutchCapacity * (1f - userClutch) * autoClutch;
                float Tc = 0f;
                if (ratio != 0f && cap > 0f)
                {
                    float Id = axleInertiaRear * rearSplit + axleInertiaFront * frontSplit;
                    float rel = engineOmega - driveOmega * ratio;
                    float Ieff = 1f / (1f / Ie + ratio * ratio / Mathf.Max(0.05f, Id));
                    Tc = Mathf.Clamp(rel * Ieff / h, -cap, cap);
                }
                engineOmega += (Te - Tc) / Ie * h;
                engineOmega = Mathf.Max(engineOmega, spec.idleRpm * 0.6f / RadToRpm);
                float driveTorque = Tc * ratio * spec.drivetrainEfficiency;
                loadAcc += Mathf.Abs(Tc) / Mathf.Max(1f, spec.PeakTorque);

                // tire forces at current wheel speeds
                for (int i = 0; i < 4; i++) TireForces(wheels[i]);

                // integrate wheel speeds (driven axles are locked-diff, so both sides share omega)
                if (spec.drive == DriveType.AWD)
                    IntegrateAxle(0, 1, driveTorque * frontSplit, axleInertiaFront, inp, h);
                else { IntegrateWheel(0, inp, h); IntegrateWheel(1, inp, h); }
                IntegrateAxle(2, 3, driveTorque * rearSplit, axleInertiaRear, inp, h);

                for (int i = 0; i < 4; i++) { fxAcc[i] += wheels[i].fx; fyAcc[i] += wheels[i].fy; }
            }
            for (int i = 0; i < 4; i++) { wheels[i].fx = fxAcc[i] / SubSteps; wheels[i].fy = fyAcc[i] / SubSteps; }
            EngineLoad = Mathf.Clamp01(loadAcc / SubSteps);

            // rev limiter (bouncing)
            rpm = EngineRpm;
            if (limiterCut) { limiterTimer -= dt; if (limiterTimer <= 0f && rpm < spec.revLimitRpm - 150f) limiterCut = false; }
            else if (rpm > spec.revLimitRpm) { limiterCut = true; limiterTimer = 0.055f; }
        }

        float DrivenOmega(float rearSplit, float frontSplit)
        {
            float rear = wheels[2].omega;   // locked diff: wheels 2 and 3 share omega
            float front = wheels[0].omega;
            return rear * rearSplit + front * frontSplit;
        }

        void TireForces(Wheel w)
        {
            if (!w.grounded || w.load <= 0f) { w.fx = w.fy = 0f; w.slipSpeed = 0f; w.slideAmount = 0f; return; }
            float r = spec.wheelRadius;
            float den = Mathf.Max(Mathf.Abs(w.vLong), 3.0f);
            float slipLong = w.omega * r - w.vLong;
            float sx = slipLong / den;
            float ty = w.vLat / den;
            float peakAngle = spec.peakSlipAngleDeg * Mathf.Deg2Rad;
            float sxn = sx / spec.peakSlipRatio;
            float syn = ty / Mathf.Tan(peakAngle);
            float sN = Mathf.Sqrt(sxn * sxn + syn * syn);

            float fz = Mathf.Min(w.load, spec.mass * 9.81f * 1.6f);
            float fz0 = spec.mass * 9.81f * 0.25f;
            float mu = (w.front ? spec.gripFront : spec.gripRear) * w.surfaceGrip
                       * (1f - spec.loadSensitivity * (fz / fz0 - 1f));
            float slide = w.front ? spec.slideGripFront : spec.slideGripRear;
            float f;
            if (sN < 1f) f = sN * (2f - sN);
            else f = slide + (1f - slide) * Mathf.Exp(-(sN - 1f) * spec.slideFalloff);
            float F = mu * fz * f;
            if (sN > 1e-5f)
            {
                w.fx = F * sxn / sN;
                w.fy = -F * syn / sN;
            }
            else { w.fx = w.fy = 0f; }
            // rolling resistance + offroad drag
            w.fx -= Mathf.Sign(w.vLong) * fz * (0.012f + w.surfaceDrag) * Mathf.Clamp01(Mathf.Abs(w.vLong));

            w.slipRatio = sx;
            w.slipAngleDeg = Mathf.Atan(ty) * Mathf.Rad2Deg;
            w.slipSpeed = Mathf.Sqrt(slipLong * slipLong + w.vLat * w.vLat);
            w.slideAmount = Mathf.Clamp01((sN - 1.2f) / 3f);
        }

        float BrakeTorqueFor(int i, CarInputState inp)
        {
            bool front = i < 2;
            float pedal = gear < 0 ? inp.throttle : inp.brake;
            float t = pedal * spec.brakeTorque * (front ? spec.brakeBias : 1f - spec.brakeBias);
            // simple ABS for assisted levels: back off service brakes when the wheel starts to lock
            if (assistLevel > 0 && t > 0f && wheels[i].grounded && wheels[i].slipRatio < -0.16f && Mathf.Abs(wheels[i].vLong) > 3f) t *= 0.3f;
            if (!front && inp.handbrake) t += spec.handbrakeTorque;
            if (frozen) t += 20000f;
            return t;
        }

        void IntegrateWheel(int i, CarInputState inp, float h)
        {
            var w = wheels[i];
            float I = spec.wheelInertia;
            float net = -w.fx * spec.wheelRadius;
            float omega = w.omega + net / I * h;
            w.omega = ApplyBrake(omega, BrakeTorqueFor(i, inp) / I * h);
            if (!w.grounded) w.omega *= 0.999f;
        }

        void IntegrateAxle(int a, int b, float driveTorque, float I, CarInputState inp, float h)
        {
            var wa = wheels[a]; var wb = wheels[b];
            float net = driveTorque - (wa.fx + wb.fx) * spec.wheelRadius;
            float omega = wa.omega + net / I * h;
            float brake = (BrakeTorqueFor(a, inp) + BrakeTorqueFor(b, inp)) / I * h;
            omega = ApplyBrake(omega, brake);
            wa.omega = wb.omega = omega;
        }

        static float ApplyBrake(float omega, float delta)
        {
            if (Mathf.Abs(omega) <= delta) return 0f;
            return omega - Mathf.Sign(omega) * delta;
        }

        void ApplyTireForces()
        {
            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                if (!w.grounded) continue;
                Vector3 force = w.fwd * w.fx + w.side * w.fy;
                // Apply slightly above the contact patch to tame body roll (classic arcade-sim compromise).
                Vector3 p = w.point + transform.up * (spec.centerOfMass.y * 0.35f);
                rb.AddForceAtPosition(force, p);
            }
        }

        void ApplyAero(Vector3 vel)
        {
            float v2 = vel.sqrMagnitude;
            if (v2 < 0.01f) return;
            float q = 0.5f * 1.225f * v2;
            rb.AddForce(-vel.normalized * q * spec.dragCoefficient * spec.frontalArea);
            Vector3 down = -transform.up;
            float zf = spec.frontAxleZ, zr = spec.frontAxleZ - spec.wheelbase;
            rb.AddForceAtPosition(down * q * spec.downforceFront, transform.TransformPoint(new Vector3(0, 0.5f, zf)));
            rb.AddForceAtPosition(down * q * spec.downforceRear, transform.TransformPoint(new Vector3(0, 0.9f, zr)));
        }

        void ApplyAssists(float dt, CarInputState inp, Vector3 localVel)
        {
            if ((assistLevel < 2 && !stabilityControl) || GroundedWheels < 3) return;
            // Yaw damping only beyond a generous drift angle, so assist-2 players still drift but rarely spin.
            float beta = Mathf.Abs(DriftAngle);
            if (beta > 55f && localVel.z > 4f)
            {
                float excess = Mathf.InverseLerp(55f, 95f, beta);
                rb.AddRelativeTorque(Vector3.up * -YawRate * rb.inertiaTensor.y * 2.5f * excess, ForceMode.Force);
            }
        }

        // ------------------------------------------------------------------ gearbox
        void UpdateGearbox(float dt, ref CarInputState inp, Vector3 localVel)
        {
            // held on the grid: never let the countdown brake select reverse
            if (frozen) { reverseHold = 0f; if (gear < 1 && shiftTimer <= 0f) { gear = 1; OnGearChanged?.Invoke(gear); } return; }
            if (shiftTimer > 0f)
            {
                shiftTimer -= dt;
                if (shiftTimer <= 0f) { gear = pendingGear; OnGearChanged?.Invoke(gear); }
                return;
            }
            int top = spec.gears.Length;
            if (transmission == Transmission.Manual)
            {
                if (inp.shiftUp && gear < top) StartShift(gear == -1 ? 0 : gear + 1);
                else if (inp.shiftDown && gear > -1) StartShift(gear - 1);
                if (gear == 0 && inp.shiftUp) StartShift(1);
                return;
            }

            // automatic
            float rpm = EngineRpm;
            float fwd = localVel.z;
            if (gear >= 1)
            {
                if (rpm > spec.redlineRpm * 0.985f && gear < top && inp.throttle > 0.2f && GroundedWheels >= 2 && !frozen && inp.clutch < 0.5f && ForwardSpeed > 4f)
                    StartShift(gear + 1);
                else if (gear > 1)
                {
                    float rpmBelow = rpm * RatioFor(gear - 1) / RatioFor(gear);
                    if (rpmBelow < spec.redlineRpm * 0.80f && rpm < spec.redlineRpm * 0.52f) StartShift(gear - 1);
                }
                if (fwd < 1.2f && inp.brake > 0.5f && inp.throttle < 0.1f)
                {
                    reverseHold += dt;
                    if (reverseHold > 0.35f) { gear = -1; reverseHold = 0f; OnGearChanged?.Invoke(gear); }
                }
                else reverseHold = 0f;
            }
            else
            {
                if (gear == 0) gear = 1;
                if (fwd > -1.2f && inp.throttle > 0.3f) { gear = 1; OnGearChanged?.Invoke(gear); }
            }
        }

        void StartShift(int target)
        {
            pendingGear = target;
            shiftTimer = spec.shiftTime;
        }

        public void ShiftUp() { input.shiftUp = true; }
        public void ShiftDown() { input.shiftDown = true; }

        // ------------------------------------------------------------------ visuals
        void LateUpdate()
        {
            float dt = Time.deltaTime;
            for (int i = 0; i < 4; i++)
            {
                var w = wheels[i];
                if (w == null) continue;
                w.spinAngle = Mathf.Repeat(w.spinAngle + w.omega * Mathf.Rad2Deg * dt, 360f);
                var vis = wheelVisuals[i];
                if (vis == null) continue;
                // mount y includes the radius; wheel center is mount - (rest - compression)
                vis.localPosition = new Vector3(w.localMount.x, w.localMount.y - (w.grounded ? (spec.restLength - w.compression) : spec.restLength), w.localMount.z);
                vis.localRotation = Quaternion.Euler(0f, w.steerAngle, 0f) * Quaternion.Euler(w.spinAngle, 0f, 0f);
                var cal = caliperVisuals[i];
                if (cal != null)
                {
                    cal.localPosition = vis.localPosition;
                    cal.localRotation = Quaternion.Euler(0f, w.steerAngle, 0f);
                }
            }
        }

        void OnCollisionEnter(Collision c)
        {
            float impulse = c.impulse.magnitude / Mathf.Max(1f, rb.mass);
            Vector3 p = c.contactCount > 0 ? c.GetContact(0).point : transform.position;
            OnImpact?.Invoke(impulse, p, c);
        }
    }
}
