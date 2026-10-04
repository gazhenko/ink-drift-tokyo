using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Racing-line follower that can also hold a drift: it steers the *velocity* vector toward the target
    /// (pure pursuit) and regulates the slide angle with throttle, kicking the handbrake on corner entry.
    ///
    /// Speed comes from a per-car profile built from the racing line's curvature and the car's own grip (and the
    /// track's wet surface), with braking points from the braking distance at the current speed. Difficulty sets how
    /// much of the grip it uses, whether it drifts or grips through corners, and how hard it catches up from behind;
    /// it never eases off when it's ahead of the player.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class AIDriver : MonoBehaviour
    {
        public float skill = 1f;              // legacy: speed multiplier on the baked profile; else a fine speed trim
        public float aggression = 0.6f;
        public bool driftStyle = true;
        public float desiredDriftAngle = 32f;
        public float lateralOffset;           // personal line offset in meters
        public bool rubberBand = true;
        public CarController rubberTarget;
        public float Progress { get; private set; }   // total distance including laps
        public bool cinematic;                // trailer: always drift where possible
        /// <summary>Fraction of the calibrated cornering limit the speed profile uses (difficulty).</summary>
        public float gripUse = 0.98f;
        /// <summary>Largest speed bonus when behind the rubber-band target (never slows down when ahead).</summary>
        public float catchUp = 0.04f;
        /// <summary>Drift only through hairpins (turns sharper than this, degrees over the look-ahead); 999 = never.</summary>
        public float driftTurnMin = 999f;
        public int Resets { get; private set; }

        /// <summary>Dev: the pre-1.29 AI (baked speed profile, eases off when ahead, drifts everywhere) for benchmarks.</summary>
        public static readonly bool Legacy = CommandLine.Has("-aiLegacy");
        /// <summary>
        /// Dev: the drift controller (baked speed profile, drifts through every corner) instead of the grip racer. It's
        /// what the CPU used to be: fine in the 4WD car, but it takes the rear-drive cars round Shuto at half the pace.
        /// </summary>
        public static readonly bool ClassicMode = CommandLine.Has("-aiClassic");
        /// <summary>
        /// The style this car is driven in: the drift controller suits the 4WD car (it pulls itself out of every
        /// slide), the grip racer is far quicker in the rear-drive ones (benchmarked with -aiBench).
        /// </summary>
        bool Classic => Legacy || ClassicMode || driftCar;
        bool driftCar;

        /// <summary>
        /// Lateral acceleration the cars actually hold through corners, as a multiple of their nominal rear grip, at
        /// gripUse 1 (calibrated with -aiBench: the fastest value that still keeps every car on the road).
        /// </summary>
        public static float LimitScale = CommandLine.Has("-aiGrip") ? CommandLine.GetFloat("-aiGrip", 1f) : 1.0f;
        // dev tuning (benchmarks): closed-loop corner cap margin (0 = off), drift threshold override, speed trim
        static readonly float GovMargin = CommandLine.Has("-aiGov") ? CommandLine.GetFloat("-aiGov", 0f) : 1.15f;
        static readonly float DriftOverride = CommandLine.Has("-aiDrift") ? CommandLine.GetFloat("-aiDrift", 999f) : -1f;
        static readonly float SpeedTrim = CommandLine.Has("-aiTrim") ? CommandLine.GetFloat("-aiTrim", 1f) : 1f;
        static readonly float SkillOverride = CommandLine.Has("-aiSkill") ? CommandLine.GetFloat("-aiSkill", 1f) : 0f;
        static readonly bool EdgeGuard = !CommandLine.Has("-aiNoEdge");

        /// <summary>Difficulty presets: 0 EASY, 1 NORMAL, 2 HARD, 3 EXPERT.</summary>
        public void ApplyDifficulty(int level, float spread)
        {
            level = Mathf.Clamp(level, 0, 3);
            float[] grip = { 0.86f, 0.93f, 0.975f, 1.0f };
            float[] catchUps = { 0f, 0.02f, 0.035f, 0.05f };
            float[] lateral = { 1.0f, 0.6f, 0.35f, 0.2f };
            float[] driftMin = { 20f, 60f, 999f, 999f };
            // the drift controller's speed on its profile (the old field ran 0.93-1.00 and backed off when ahead)
            if (car == null) car = GetComponent<CarController>();
            driftCar = car != null && car.spec.drive == DriveType.AWD && !CommandLine.Has("-aiGripMode");
            float[] skills = { 0.93f, 1.0f, 1.03f, 1.06f };
            gripUse = grip[level] * (1f - spread);
            catchUp = catchUps[level];
            lateralOffset = Random.Range(-lateral[level], lateral[level]) * (Classic ? 0.6f : 1f);
            driftTurnMin = DriftOverride >= 0f ? DriftOverride : driftMin[level];
            driftStyle = Classic || level == 0;
            aggression = Mathf.Lerp(0.5f, 1f, level / 3f) * Random.Range(0.85f, 1f);
            skill = Classic ? (SkillOverride > 0f ? SkillOverride : skills[level]) * (1f - spread) : 1f;
        }

        CarController car;
        int hint = -1;
        float lastD;
        int laps;
        float handbrakeTimer;
        float stuckTimer;
        float avoidOffset;
        float integ;
        float prevAngle;

        void Awake()
        {
            car = GetComponent<CarController>(); car.assistLevel = 0; car.stabilityControl = true;
            if (DebugLog) car.OnImpact += (imp, point, col) =>
            {
                if (imp < 2.5f || col.rigidbody != null) return;
                Debug.Log($"[AI] {name} impact {imp:0.0} m/s at d={lastD:0} lat={lastLat:0.0} hw={lastHw:0.0} v={car.SpeedKmh:0} steer={car.input.steer:0.00} thr={car.input.throttle:0.00} drift={car.DriftAngle:0} hit={col.collider.name}");
            };
        }

        static readonly bool DebugLog = CommandLine.Has("-aiLog");
        float lastLat, lastHw;

        // ---------------------------------------------------------------- per-car speed profile
        static readonly Dictionary<(int path, int mu, int vmax, int brake), float[]> profiles = new Dictionary<(int, int, int, int), float[]>();
        float[] profile;
        float brakeDecel = 8.5f;

        /// <summary>Cornering speed from the racing line's curvature at mu, then braking-limited backwards.</summary>
        /// <summary>The line this AI actually drives: the baked racing line pulled a little toward the centre.</summary>
        const float SafeLine = 0.82f;

        static float[] BuildProfile(TrackPath path, float mu, float vmax, float decel)
        {
            int n = path.Count;
            var line = new Vector3[n];
            for (int i = 0; i < n; i++) line[i] = path.points[i] + path.rights[i] * RacingLat(path, path.dist[i]) * SafeLine;
            var v = new float[n];
            for (int i = 0; i < n; i++)
            {
                Vector3 a = line[path.Wrap(i - 4)], b = line[i], c = line[path.Wrap(i + 4)];
                float k = Curvature(a, b, c);
                v[i] = Mathf.Clamp(Mathf.Sqrt(mu * 9.81f / Mathf.Max(k, 1e-4f)), 9f, vmax);
            }
            for (int pass = 0; pass < 3; pass++)
                for (int i = n - 1; i >= 0; i--)
                {
                    int j = path.Wrap(i + 1);
                    float ds = j == 0 ? path.length - path.dist[i] : path.dist[j] - path.dist[i];
                    v[i] = Mathf.Min(v[i], Mathf.Sqrt(v[j] * v[j] + 2f * decel * Mathf.Max(0.1f, ds)));
                }
            return v;
        }

        static float Curvature(Vector3 a, Vector3 b, Vector3 c)
        {
            a.y = b.y = c.y = 0f;
            float ab = (b - a).magnitude, bc = (c - b).magnitude, ca = (a - c).magnitude;
            float area2 = Mathf.Abs(Vector3.Cross(b - a, c - a).y);
            float den = ab * bc * ca;
            return den < 1e-5f ? 0f : 2f * area2 / den;
        }

        void EnsureProfile(TrackPath path)
        {
            // the cars hold about their rear axle's grip (the weaker end, which decides the limit), less on wet tarmac
            float wet = TrackCatalog.Get(path.trackId ?? GameSession.TrackId).wet ? 0.86f : 1f;
            float mu = Mathf.Min(car.spec.gripFront, car.spec.gripRear) * wet * LimitScale * gripUse;
            float vmax = car.MaxSpeedInGear(car.spec.gears.Length) * 0.97f;
            brakeDecel = Mathf.Clamp(mu * 9.81f * 0.82f, 5f, 11f);
            var key = (path.GetInstanceID(), Mathf.RoundToInt(mu * 1000f), Mathf.RoundToInt(vmax), Mathf.RoundToInt(brakeDecel * 10f));
            if (!profiles.TryGetValue(key, out profile))
            {
                profile = BuildProfile(path, mu, vmax, brakeDecel);
                profiles[key] = profile;
            }
        }

        float ProfileAt(TrackPath path, float d) => profile != null ? profile[path.IndexAt(d)] : path.TargetSpeedAt(d);

        // ---------------------------------------------------------------- racecraft
        readonly Dictionary<CarController, int> otherHints = new Dictionary<CarController, int>();
        float followCap = float.MaxValue;

        /// <summary>Racing line's offset from the centreline at d (+ = right).</summary>
        static float RacingLat(TrackPath path, float d)
        {
            if (path.racingLine.Length != path.Count) return 0f;
            int i = path.IndexAt(d);
            return Vector3.Dot(path.racingLine[i] - path.points[i], path.rights[i]);
        }

        /// <summary>
        /// Positions of the other cars along the track decide the line: keep a car's width from anyone alongside, and
        /// for a slower car ahead pass on the side with room (or, with no room, sit behind it instead of hitting it).
        /// </summary>
        void Racecraft(TrackPath path, float d, float myLat, float speed, float lineD)
        {
            float L = path.length;
            float hw = path.HalfWidthAt(d);
            float lineLat = RacingLat(path, lineD) + lateralOffset;     // where this car would be without traffic
            float avoidTarget = 0f, bestTtc = float.MaxValue;
            followCap = float.MaxValue;
            Vector3 me = car.transform.position;
            foreach (var o in CarController.All)
            {
                if (o == null || o == car) continue;
                Vector3 op = o.transform.position;
                if ((op - me).sqrMagnitude > 60f * 60f) continue;
                if (!otherHints.TryGetValue(o, out int h)) h = -1;
                float od = path.Project(op, ref h, out float oLat);
                otherHints[o] = h;
                float along = Mathf.DeltaAngle(d / L * 360f, od / L * 360f) / 360f * L;   // + = it's ahead
                float dl = oLat - myLat;
                float closing = speed - o.SpeedMs;
                if (Mathf.Abs(along) < 5.5f)
                {
                    if (Mathf.Abs(dl) < 2.5f) avoidTarget += -(dl >= 0f ? 1f : -1f) * (2.6f - Mathf.Abs(dl));
                }
                else if (along > 0f && along < 45f && Mathf.Abs(dl) < 2.6f && closing > 0.5f)
                {
                    float ttc = (along - 4.8f) / closing;
                    if (ttc >= 2.8f || ttc >= bestTtc) continue;
                    bestTtc = ttc;
                    float roomL = (oLat - 2.7f) - (-hw + 1.1f);
                    float roomR = (hw - 1.1f) - (oLat + 2.7f);
                    if (Mathf.Max(roomL, roomR) > 0.2f)
                    {
                        bool left = Mathf.Abs(roomL - roomR) > 1.5f ? roomL > roomR : myLat < oLat;
                        if (left && roomL <= 0.2f) left = false;
                        else if (!left && roomR <= 0.2f) left = true;
                        avoidTarget = (left ? oLat - 2.8f : oLat + 2.8f) - lineLat;
                    }
                    if (Mathf.Max(roomL, roomR) <= 0.2f || ttc < 0.8f)
                        followCap = Mathf.Min(followCap, o.SpeedMs + Mathf.Max(0f, along - 7f) * 0.6f);
                }
            }
            avoidOffset = Mathf.MoveTowards(avoidOffset, avoidTarget, Time.fixedDeltaTime * (avoidTarget == 0f ? 1.2f : 3.5f));
        }

        public void ResetProgress() { laps = 0; hint = -1; lastD = 0f; Progress = 0f; }

        void FixedUpdate()
        {
            var path = TrackPath.Active;
            if (path == null || path.Count < 4) return;
            float dt = Time.fixedDeltaTime;
            Vector3 pos = car.transform.position;
            float d = path.Project(pos, ref hint, out float lateral);
            lastLat = lateral; lastHw = path.HalfWidthAt(d);
            if (lastD > path.length * 0.8f && d < path.length * 0.2f) laps++;
            else if (d > path.length * 0.8f && lastD < path.length * 0.2f) laps--;
            lastD = d;
            Progress = laps * path.length + d;

            float speed = car.SpeedMs;
            float look = 7f + speed * 0.55f;
            float targetD = d + look;
            if (!Legacy) Racecraft(path, d, lateral, speed, targetD);
            Vector3 target = path.PointAt(targetD, path.racingLine.Length == path.Count ? path.racingLine : null);
            Vector3 right = path.RightAt(targetD);
            float hw = path.HalfWidthAt(targetD);
            float off;
            if (Classic) off = Mathf.Clamp(lateralOffset + avoidOffset, -hw * 0.7f, hw * 0.7f);
            else
            {
                // keep the final line a metre inside the road edges, wherever the racing line runs
                // the baked line runs within 1.8 m of the edge; tracking errors put the car on the kerb from there,
                // so it's kept a little further in
                float rl = RacingLat(path, targetD);
                float rlSafe = rl * SafeLine;
                // railings, signal poles and guardrails stand a little inside the nominal road edge
                off = Mathf.Clamp(rlSafe + lateralOffset + avoidOffset, -hw + 2.0f, hw - 2.0f) - rl;
            }
            target += right * off;

            // --- speed profile (min over the braking horizon)
            float vt = float.MaxValue;
            if (Classic)
            {
                for (float a = 0f; a < 90f; a += 6f)
                {
                    float v = path.TargetSpeedAt(d + a);
                    // allow for braking distance at ~8 m/s^2
                    float vAllowed = Mathf.Sqrt(v * v + 2f * 8.5f * a);
                    vt = Mathf.Min(vt, vAllowed);
                }
                vt *= skill * (Legacy ? 1f : SpeedTrim);
            }
            else
            {
                // the profile already has its braking ramps; look ahead by the reaction distance (and a bit) so the
                // brakes come on at the braking point rather than after it
                EnsureProfile(path);
                float horizon = 6f + speed * 0.35f;
                for (float a = 0f; a <= horizon; a += 3f)
                {
                    float v = ProfileAt(path, d + a);
                    vt = Mathf.Min(vt, Mathf.Sqrt(v * v + 2f * brakeDecel * a));
                }
                vt *= skill * SpeedTrim;
            }
            if (rubberBand && rubberTarget != null)
            {
                // gap along the track to the rubber-band target (+ = this car is ahead)
                int h2 = -1;
                float pd = path.Project(rubberTarget.transform.position, ref h2, out _);
                float gap = Mathf.DeltaAngle(pd / path.length * 360f, d / path.length * 360f) / 360f * path.length;
                if (Legacy) vt *= Mathf.Clamp(1f - gap * 0.0025f, 0.88f, 1.10f);
                else if (gap < 0f) vt *= 1f + catchUp * Mathf.Clamp01(-gap / 120f);   // catch up from behind, never back off
            }
            if (!Legacy) vt = Mathf.Min(vt, followCap);

            // --- corner sharpness ahead → decide drift
            Vector3 tNow = path.TangentAt(d);
            Vector3 tAhead = path.TangentAt(d + 25f + speed * 0.4f);
            float turn = Vector3.SignedAngle(tNow, tAhead, Vector3.up);
            bool corner = Mathf.Abs(turn) > 20f;
            bool wantDrift = (driftStyle || cinematic) && corner && speed > 13f;
            if (!Classic && !cinematic && !driftStyle) wantDrift = Mathf.Abs(turn) > driftTurnMin && speed > 13f;

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
            else if (Classic) steerDeg = errVel * 1.6f;
            else
            {
                // Grip: the bicycle-model steer angle for the pure-pursuit curvature, a yaw-rate correction, and a cap
                // that keeps the front tyres near their peak slip angle (beyond it they plough on: full lock in a
                // tight corner ran the old controller straight into the wall).
                float dist = Mathf.Max(5f, toT.magnitude);
                float kappa = 2f * Mathf.Sin(errVel * Mathf.Deg2Rad) / dist;
                float wb = car.spec.wheelbase;
                float kin = Mathf.Atan(wb * kappa) * Mathf.Rad2Deg;
                steerDeg = kin + (speed * kappa - car.YawRate) * 8f;
                float vv = Mathf.Max(speed, 5f);
                float muNow = Mathf.Min(car.spec.gripFront, car.spec.gripRear);
                float cap = Mathf.Atan(wb * muNow * 9.81f / (vv * vv)) * Mathf.Rad2Deg + car.spec.peakSlipAngleDeg * 1.15f;
                steerDeg = Mathf.Clamp(steerDeg, -cap, cap);
            }
            float steer = Mathf.Clamp(steerDeg / Mathf.Max(1f, car.spec.maxSteerDeg), -1f, 1f);

            // --- throttle / brake
            float throttle, brake = 0f;
            float speedErr = vt - speed;
            if (!Classic && !sliding)
            {
                // closed-loop corner speed: the curvature it needs to reach its aim point, against what the tyres hold
                float distT = Mathf.Max(5f, toT.magnitude);
                float kReq = Mathf.Abs(2f * Mathf.Sin(errVel * Mathf.Deg2Rad) / distT);
                float wetK = TrackCatalog.Get(path.trackId ?? GameSession.TrackId).wet ? 0.86f : 1f;
                float muC = Mathf.Min(car.spec.gripFront, car.spec.gripRear) * wetK * LimitScale * gripUse;
                // only in slow, tight corners (city 90s, hairpins): on fast sweepers it reads every small heading
                // error as a corner and lifts for nothing
                float govW = Mathf.InverseLerp(30f, 22f, speed);
                if (kReq > 1e-3f && GovMargin > 0f && govW > 0f)
                {
                    float cap = Mathf.Sqrt(muC * 9.81f / kReq) * GovMargin;
                    vt = Mathf.Min(vt, Mathf.Lerp(vt, cap, govW));
                    speedErr = vt - speed;
                }
            }
            float brakeAt = Classic ? -2.5f : -0.6f;
            if (speedErr < brakeAt && !(wantDrift && Mathf.Abs(beta) > 12f))
            {
                throttle = 0f;
                brake = Classic ? Mathf.Clamp01(-speedErr * 0.12f) : Mathf.Clamp(-speedErr * 0.45f, 0f, Mathf.Abs(steer) > 0.5f ? 0.8f : 1f);
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
                        if (Classic) { if (rl != null && rl.grounded && rl.slipRatio > 0.45f) throttle *= 0.75f; }
                        else
                        {
                            // hold the rears near peak slip, and lift as the rear starts to step out
                            float slip = 0f;
                            for (int w = 2; w < 4; w++) if (car.wheels[w] != null && car.wheels[w].grounded) slip = Mathf.Max(slip, car.wheels[w].slipRatio);
                            throttle *= Mathf.Clamp(1f - (slip - 0.12f) * 4f, 0.2f, 1f);
                            throttle *= Mathf.Clamp(1f - (a - 3f) * 0.18f, 0.15f, 1f);
                        }
                    }
                }
            }

            bool hb = false;
            if (handbrakeTimer > 0f) { handbrakeTimer -= dt; hb = handbrakeTimer > 0.05f; throttle = Mathf.Max(throttle, 0.5f); }

            // --- simple avoidance of cars directly ahead (legacy: all cars; now: traffic, the field is handled by Racecraft)
            if (Legacy) avoidOffset = Mathf.MoveTowards(avoidOffset, 0f, dt * 0.8f);
            int mask = 1 << CarController.CarLayer;
            if (Physics.SphereCast(pos + Vector3.up * 0.6f, 1.0f, heading, out var hit, 10f + speed * 0.4f, mask, QueryTriggerInteraction.Ignore)
                && hit.rigidbody != car.Body && (Legacy || hit.rigidbody == null || hit.rigidbody.GetComponent<CarController>() == null))
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
                Resets++;
                if (DebugLog) Debug.Log($"[AI] {name} reset at d={d:0} lat={lateral:0.0} hw={path.HalfWidthAt(d):0.0}");
                var pose = path.ResetPose(pos, ref hint);
                car.ResetTo(pose.position, pose.rotation);
            }

            // edge guard: near the road edge and heading further out, steer back in and lift
            if (!Legacy && EdgeGuard && !car.frozen)
            {
                float hwHere = path.HalfWidthAt(d);
                float outward = Vector3.Dot(vdir, path.RightAt(d)) * Mathf.Sign(lateral);   // + = moving toward that edge
                float over = Mathf.Abs(lateral) - (hwHere - Mathf.Max(1.8f, hwHere * 0.36f));
                if (over > 0f && outward > 0f)
                {
                    float k = Mathf.Clamp01(over / 1.2f);
                    steer = Mathf.Clamp(steer - Mathf.Sign(lateral) * k * 0.6f, -1f, 1f);
                    throttle *= 1f - 0.7f * k;
                }
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
