using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Drift-aware chase camera. The orbit follows a blend of heading and velocity so a sideways car is shown
    /// side-on (the classic drift-cam), FOV and shake scale with speed, impulses come from impacts/callouts.
    /// </summary>
    [RequireComponent(typeof(Camera))]
    public class ChaseCamera : MonoBehaviour
    {
        public enum Mode { Chase, ChaseNear, Cockpit, Hood, Bumper }

        public CarController target;
        public Mode mode = Mode.Chase;
        public float distance = 5.6f;
        public float height = 1.75f;
        public float lookHeight = 0.95f;
        public float velocityFollow = 0.55f;
        public float baseFov = 60f;
        public float maxFov = 84f;
        public float positionLag = 9f;
        public float rotationLag = 10f;

        public static ChaseCamera Main { get; private set; }

        Camera cam;
        Vector3 smoothedDir;
        Vector3 vel;
        float shake;
        float fovKick;
        float yawOffset;
        Vector3 shakeSeed;
        float baseNear;
        CockpitRig rig;
        Vector3 lastVel, smoothAcc;
        float lookYaw;
        readonly System.Collections.Generic.List<(UnityEngine.Rendering.Universal.MotionBlur mb, float intensity)> blurs = new System.Collections.Generic.List<(UnityEngine.Rendering.Universal.MotionBlur, float)>();
        bool blurOff;

        void Awake()
        {
            cam = GetComponent<Camera>();
            baseNear = cam.nearClipPlane;
            Main = this;
            shakeSeed = new Vector3(Random.value * 100f, Random.value * 100f, Random.value * 100f);
            PlayerDriver.CameraCyclePressed += Cycle;
        }

        void OnDestroy() { PlayerDriver.CameraCyclePressed -= Cycle; }

        void Cycle()
        {
            mode = (Mode)(((int)mode + 1) % 5);
            GameSession.CameraMode = (int)mode;
        }

        public void AddShake(float amount) { shake = Mathf.Min(1.5f, shake + amount); }
        public void KickFov(float amount) { fovKick = Mathf.Max(fovKick, amount); }

        public void Snap()
        {
            if (target == null) return;
            lastVel = target.Body.linearVelocity;
            smoothAcc = Vector3.zero;
            lookYaw = 0f;
            smoothedDir = target.transform.forward;
            transform.position = DesiredPosition(smoothedDir);
            transform.rotation = Quaternion.LookRotation(LookPoint() - transform.position);
        }

        Vector3 LookPoint()
        {
            Transform t = target.transform;
            Vector3 v = target.Body.linearVelocity;
            return t.position + Vector3.up * lookHeight + Vector3.ClampMagnitude(v * 0.06f, 2f);
        }

        Vector3 DesiredPosition(Vector3 dir)
        {
            float d = mode == Mode.ChaseNear ? distance * 0.72f : distance;
            float h = mode == Mode.ChaseNear ? height * 0.8f : height;
            Vector3 p = target.transform.position - dir * d + Vector3.up * h;
            return p;
        }

        void LateUpdate()
        {
            if (target == null) return;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            Transform t = target.transform;
            float speed = target.SpeedMs;

            // the interior only exists while we're sitting in it
            if (rig != null && (mode != Mode.Cockpit || rig.car != target)) { rig.SetActive(false); rig = null; }
            SetMotionBlur(mode != Mode.Cockpit);
            if (mode == Mode.Cockpit && CockpitView(t, speed, dt)) return;
            cam.nearClipPlane = baseNear;

            if (mode == Mode.Bumper || mode == Mode.Hood)
            {
                Vector3 local = mode == Mode.Bumper ? new Vector3(0f, 0.55f, target.spec.frontAxleZ + 0.9f) : new Vector3(0f, 1.22f, 0.2f);
                transform.position = t.TransformPoint(local);
                Quaternion lookRot = t.rotation;
                if (PlayerDriver.LookBackHeld) lookRot = lookRot * Quaternion.Euler(0, 180, 0);
                transform.rotation = lookRot;
                ApplyFov(speed, dt);
                ApplyShake(speed, dt, 0.35f);
                return;
            }

            Vector3 fwd = Vector3.ProjectOnPlane(t.forward, Vector3.up).normalized;
            Vector3 v = Vector3.ProjectOnPlane(target.Body.linearVelocity, Vector3.up);
            Vector3 vdir = v.magnitude > 3f ? v.normalized : fwd;
            if (Vector3.Dot(vdir, fwd) < -0.2f) vdir = fwd;   // reversing / spun: stay behind the car
            Vector3 want = Vector3.Slerp(fwd, vdir, velocityFollow).normalized;
            if (smoothedDir.sqrMagnitude < 0.5f) smoothedDir = want;
            smoothedDir = Vector3.Slerp(smoothedDir, want, 1f - Mathf.Exp(-rotationLag * 0.45f * dt)).normalized;

            Vector3 dir = smoothedDir;
            if (PlayerDriver.LookBackHeld) dir = -fwd;
            Vector3 desired = DesiredPosition(dir);

            // Keep the camera out of walls.
            Vector3 pivot = t.position + Vector3.up * 1.2f;
            Vector3 toCam = desired - pivot;
            int mask = ~((1 << CarController.CarLayer) | (1 << 2));
            if (Physics.SphereCast(pivot, 0.3f, toCam.normalized, out var hit, toCam.magnitude, mask, QueryTriggerInteraction.Ignore))
                desired = pivot + toCam.normalized * Mathf.Max(1.2f, hit.distance - 0.1f);

            // Spring toward desired; tighter at speed so the car stays framed.
            float lag = positionLag * Mathf.Lerp(1f, 1.6f, Mathf.InverseLerp(10f, 60f, speed));
            transform.position = Vector3.SmoothDamp(transform.position, desired, ref vel, 1f / lag, Mathf.Infinity, dt);
            Vector3 look = LookPoint();
            Quaternion rot = Quaternion.LookRotation(look - transform.position, Vector3.up);
            // A touch of roll into the drift for drama.
            rot *= Quaternion.Euler(0f, 0f, -target.DriftAngle * 0.05f);
            transform.rotation = Quaternion.Slerp(transform.rotation, rot, 1f - Mathf.Exp(-rotationLag * 2f * dt));

            ApplyFov(speed, dt);
            ApplyShake(speed, dt, 1f);
        }

        void SetMotionBlur(bool on)
        {
            if (on != blurOff) return;
            blurOff = !on;
            if (!on)
            {
                blurs.Clear();
                foreach (var v in FindObjectsByType<UnityEngine.Rendering.Volume>(FindObjectsSortMode.None))
                    if (v.sharedProfile != null && v.sharedProfile.TryGet(out UnityEngine.Rendering.Universal.MotionBlur mb))
                    { blurs.Add((mb, mb.intensity.value)); mb.intensity.value = 0f; }
            }
            else
            {
                foreach (var (mb, i) in blurs) if (mb != null) mb.intensity.value = i;
                blurs.Clear();
            }
        }

        void OnDisable() { SetMotionBlur(true); }

        /// <summary>Driver's-eye view from the right-hand seat; head moves with g-forces and looks into the slide.</summary>
        bool CockpitView(Transform t, float speed, float dt)
        {
            var r = CockpitRig.For(target);
            if (r == null) { mode = Mode.Hood; return false; }
            rig = r;
            rig.SetActive(true);

            Vector3 v = target.Body.linearVelocity;
            Vector3 acc = t.InverseTransformDirection((v - lastVel) / dt);
            lastVel = v;
            smoothAcc = Vector3.Lerp(smoothAcc, Vector3.ClampMagnitude(acc, 40f), 1f - Mathf.Exp(-6f * dt));
            Vector3 head = new Vector3(Mathf.Clamp(-smoothAcc.x * 0.0028f, -0.045f, 0.045f),
                                       Mathf.Clamp(-smoothAcc.y * 0.0015f, -0.02f, 0.02f),
                                       Mathf.Clamp(-smoothAcc.z * 0.0035f, -0.04f, 0.04f));
            // look where the car is going: into the slide when drifting, a little into the turn otherwise
            float yawWant = speed < 3f ? 0f : Mathf.Clamp(target.DriftAngle * 0.55f + target.input.steer * 4f, -38f, 38f);
            lookYaw = Mathf.Lerp(lookYaw, yawWant, 1f - Mathf.Exp(-3.2f * dt));
            float pitch = 6.5f + Mathf.Clamp(-smoothAcc.z * 0.15f, -2.5f, 2.5f);
            float roll = Mathf.Clamp(smoothAcc.x * 0.10f, -2.5f, 2.5f);
            Vector3 eye = rig.EyeLocal + head;
            rig.HeadOffset = head;
            Quaternion look = Quaternion.Euler(pitch, lookYaw, roll);
            if (PlayerDriver.LookBackHeld || (CommandLine.Has("-dbgLookBack") && Mathf.Repeat(Time.time, 10f) > 8f))
            {
                // over-the-shoulder view out of the rear window, from up under the headliner
                float lz = Mathf.Min(rig.EyeLocal.z - 0.5f, rig.dims.backTopZ + 0.10f);   // behind the front seats
                eye = new Vector3(0.05f, rig.dims.Roof(lz) - 0.15f, lz);
                look = Quaternion.Euler(7f, 180f, 0f);
            }
            transform.position = t.TransformPoint(eye);
            transform.rotation = t.rotation * look;
            cam.nearClipPlane = 0.03f;

            float f = Mathf.Lerp(70f, 76f, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(10f, 75f, speed)));
            fovKick = Mathf.MoveTowards(fovKick, 0f, dt * 18f);
            cam.fieldOfView = Mathf.Lerp(cam.fieldOfView, f + fovKick * 0.4f + target.Boost * 1.5f, 1f - Mathf.Exp(-5f * dt));
            ApplyShake(speed, dt, 0.25f);
            // dev: "-dbgCockpitCam px,py,pz,tx,ty,tz,fov" -- eye-relative camera position and look target (close-up review)
            string dc = CommandLine.Get("-dbgCockpitCam");
            if (dc != null)
            {
                var dcv = System.Array.ConvertAll(dc.Split(','), x => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture));
                Vector3 p = rig.EyeLocal + new Vector3(dcv[0], dcv[1], dcv[2]), tgt = rig.EyeLocal + new Vector3(dcv[3], dcv[4], dcv[5]);
                transform.position = t.TransformPoint(p);
                transform.rotation = t.rotation * Quaternion.LookRotation(tgt - p);
                cam.fieldOfView = dcv.Length > 6 ? dcv[6] : 40f;
            }
            return true;
        }

        void ApplyFov(float speed, float dt)
        {
            float f = Mathf.Lerp(baseFov, maxFov, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(8f, 75f, speed)));
            if (mode == Mode.Bumper || mode == Mode.Hood) f += 6f;
            fovKick = Mathf.MoveTowards(fovKick, 0f, dt * 18f);
            float boost = target.Boost * 3f;
            cam.fieldOfView = Mathf.Lerp(cam.fieldOfView, f + fovKick + boost, 1f - Mathf.Exp(-5f * dt));
        }

        void ApplyShake(float speed, float dt, float scale)
        {
            shake = Mathf.MoveTowards(shake, 0f, dt * 1.8f);
            float ambient = Mathf.InverseLerp(20f, 80f, speed) * 0.06f + (target.OnLimiter ? 0.05f : 0f);
            float drift = Mathf.InverseLerp(15f, 60f, Mathf.Abs(target.DriftAngle)) * 0.05f;
            float amp = (ambient + drift + shake * shake * 0.6f) * scale;
            if (amp < 1e-4f) return;
            float tt = Time.time * 22f;
            Vector3 n = new Vector3(Mathf.PerlinNoise(shakeSeed.x, tt) - 0.5f, Mathf.PerlinNoise(shakeSeed.y, tt) - 0.5f, Mathf.PerlinNoise(shakeSeed.z, tt * 0.7f) - 0.5f);
            transform.position += transform.rotation * new Vector3(n.x, n.y, 0f) * amp * 0.6f;
            transform.rotation *= Quaternion.Euler(n.y * amp * 8f, n.x * amp * 8f, n.z * amp * 14f);
        }
    }
}
