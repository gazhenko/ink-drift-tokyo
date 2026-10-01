using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Racing-line follower that can also hold a drift: it steers the *velocity* vector toward the target
    /// (pure pursuit) and regulates the slide angle with throttle, kicking the handbrake on corner entry.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class AIDriver : MonoBehaviour
    {
        public float skill = 1f;              // speed multiplier on the target profile
        public float aggression = 0.6f;
        public bool driftStyle = true;
        public float desiredDriftAngle = 32f;
        public float lateralOffset;           // personal line offset in meters
        public bool rubberBand = true;
        public CarController rubberTarget;
        public float Progress { get; private set; }   // total distance including laps
        public bool cinematic;                // trailer: always drift where possible

        CarController car;
        int hint = -1;
        float lastD;
        int laps;
        float handbrakeTimer;
        float stuckTimer;
        float avoidOffset;
        float integ;
        float prevAngle;

        void Awake() { car = GetComponent<CarController>(); car.assistLevel = 0; car.stabilityControl = true; }

        public void ResetProgress() { laps = 0; hint = -1; lastD = 0f; Progress = 0f; }

        void FixedUpdate()
        {
            var path = TrackPath.Active;
            if (path == null || path.Count < 4) return;
            float dt = Time.fixedDeltaTime;
            Vector3 pos = car.transform.position;
            float d = path.Project(pos, ref hint, out float lateral);
            if (lastD > path.length * 0.8f && d < path.length * 0.2f) laps++;
            else if (d > path.length * 0.8f && lastD < path.length * 0.2f) laps--;
            lastD = d;
            Progress = laps * path.length + d;

            float speed = car.SpeedMs;
            float look = 7f + speed * 0.55f;
            float targetD = d + look;
            Vector3 target = path.PointAt(targetD, path.racingLine.Length == path.Count ? path.racingLine : null);
            Vector3 right = path.RightAt(targetD);
            float hw = path.HalfWidthAt(targetD);
            float off = Mathf.Clamp(lateralOffset + avoidOffset, -hw * 0.7f, hw * 0.7f);
            target += right * off;

            // --- speed profile (min over the braking horizon)
            float vt = float.MaxValue;
            for (float a = 0f; a < 90f; a += 6f)
            {
                float v = path.TargetSpeedAt(d + a);
                // allow for braking distance at ~8 m/s^2
                float vAllowed = Mathf.Sqrt(v * v + 2f * 8.5f * a);
                vt = Mathf.Min(vt, vAllowed);
            }
            vt *= skill;
            if (rubberBand && rubberTarget != null)
            {
                float gap = 0f;
                var other = rubberTarget.GetComponent<AIDriver>();
                // approximate gap using the player's projected distance
                int h2 = -1;
                float pd = path.Project(rubberTarget.transform.position, ref h2, out _);
                gap = Mathf.DeltaAngle(pd / path.length * 360f, d / path.length * 360f) / 360f * path.length;
                vt *= Mathf.Clamp(1f - gap * 0.0025f, 0.88f, 1.10f);
            }

            // --- corner sharpness ahead → decide drift
            Vector3 tNow = path.TangentAt(d);
            Vector3 tAhead = path.TangentAt(d + 25f + speed * 0.4f);
            float turn = Vector3.SignedAngle(tNow, tAhead, Vector3.up);
            bool corner = Mathf.Abs(turn) > 20f;
            bool wantDrift = (driftStyle || cinematic) && corner && speed > 13f;

            // --- steering: aim the velocity vector at the target, then add counter-steer (beta) so front wheels follow it
            Vector3 vel = car.Body.linearVelocity;
            Vector3 heading = car.transform.forward;
            Vector3 vdir = vel.magnitude > 4f ? vel.normalized : heading;
            Vector3 toT = target - pos; toT.y = 0f;
            float errVel = Vector3.SignedAngle(Vector3.ProjectOnPlane(vdir, Vector3.up), toT, Vector3.up);
            float beta = car.DriftAngle;  // + = velocity right of heading
            float steerDeg;
            bool sliding = Mathf.Abs(beta) > 8f;
            if (sliding)
            {
                // Drift: front wheels track the velocity vector (beta) + yaw-rate correction toward the path curvature
                // (pure pursuit on the velocity heading) — validated in Tools/physics/sim.py.
                float dist = Mathf.Max(5f, toT.magnitude);
                float kappa = 2f * Mathf.Sin(errVel * Mathf.Deg2Rad) / dist;
                float rTarget = speed * kappa;                     // Unity sign: + = turning right
                steerDeg = beta + (rTarget - car.YawRate) * 9f;
            }
            else steerDeg = errVel * 1.6f;
            float steer = Mathf.Clamp(steerDeg / Mathf.Max(1f, car.spec.maxSteerDeg), -1f, 1f);

            // --- throttle / brake
            float throttle, brake = 0f;
            float speedErr = vt - speed;
            if (speedErr < -2.5f && !(wantDrift && Mathf.Abs(beta) > 12f))
            {
                throttle = 0f;
                brake = Mathf.Clamp01(-speedErr * 0.12f);
            }
            else
            {
                throttle = Mathf.Clamp01(0.7f + speedErr * 0.15f);
            }

            {
                float a = Mathf.Abs(beta);
                float dA = (a - prevAngle) / dt;
                if (a > 8f)
                {
                    // Sliding: hold the drift angle on drift corners, otherwise catch the slide (~6°).
                    // high-speed drifts run shallower angles (expressway style)
                    float angleTarget = wantDrift ? Mathf.Lerp(desiredDriftAngle, 20f, Mathf.InverseLerp(18f, 38f, speed)) : 6f;
                    float angleErr = angleTarget - a;
                    integ = Mathf.Clamp(integ + angleErr * dt, -10f, 10f);
                    throttle = Mathf.Clamp01((wantDrift ? 0.62f : 0.35f) + angleErr * 0.035f - dA * 0.006f + integ * 0.01f);
                    if (wantDrift && speed < vt * 0.75f) throttle = Mathf.Max(throttle, 0.5f);
                    if (a > 75f) throttle = 0f;
                    brake = 0f;
                }
                else
                {
                    integ = 0f;
                    if (wantDrift && handbrakeTimer <= 0f && speed > 15f && speed < 25f)
                    {
                        handbrakeTimer = 0.28f + aggression * 0.1f;   // initiate
                        steer = Mathf.Clamp(Mathf.Sign(turn) * 1f, -1f, 1f);
                    }
                    else if (!wantDrift)
                    {
                        // traction control in grip mode: back off when the driven wheels spin up
                        var rl = car.wheels[2];
                        if (rl != null && rl.grounded && rl.slipRatio > 0.45f) throttle *= 0.75f;
                    }
                }
            }

            bool hb = false;
            if (handbrakeTimer > 0f) { handbrakeTimer -= dt; hb = handbrakeTimer > 0.05f; throttle = Mathf.Max(throttle, 0.5f); }

            // --- simple avoidance of cars directly ahead
            avoidOffset = Mathf.MoveTowards(avoidOffset, 0f, dt * 0.8f);
            int mask = 1 << CarController.CarLayer;
            if (Physics.SphereCast(pos + Vector3.up * 0.6f, 1.0f, heading, out var hit, 10f + speed * 0.4f, mask, QueryTriggerInteraction.Ignore)
                && hit.rigidbody != car.Body)
            {
                float side = Vector3.Dot(hit.point - pos, car.transform.right) > 0f ? -1f : 1f;
                avoidOffset = Mathf.Clamp(avoidOffset + side * dt * 6f * aggression, -4f, 4f);
                if (hit.distance < 6f && speed > 8f) { throttle *= 0.6f; }
            }

            // --- stuck recovery
            if (speed < 1.5f && !car.frozen) stuckTimer += dt; else stuckTimer = 0f;
            if (stuckTimer > 3f)
            {
                stuckTimer = 0f;
                var pose = path.ResetPose(pos, ref hint);
                car.ResetTo(pose.position, pose.rotation);
            }

            prevAngle = Mathf.Abs(beta);
            car.input.steer = steer;
            car.input.throttle = throttle;
            car.input.brake = brake;
            car.input.handbrake = hb;
            car.input.clutch = 0f;
        }
    }
}
