using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace InkDrift
{
    /// <summary>
    /// Animates a car's cockpit (built by <see cref="CockpitBuilder"/>) while the in-car camera is active:
    /// steering wheel with hand-over-hand grips (hands slide when the wheel snaps back on its own), H-pattern
    /// shifts with the left hand, hydraulic handbrake pulls, live tach/boost/water gauges, shift lights, and a
    /// rendered rear-view mirror. Right-hand drive: the driver sits on the right, the left hand works the console.
    /// </summary>
    public class CockpitRig : MonoBehaviour
    {
        public CarController car;
        public CabinDims dims;
        public Transform wheel, shifter, handbrake, tachNeedle, boostNeedle, waterNeedle;
        public TextMeshPro gearText, speedText;
        public Renderer[] shiftLights;
        public Material[] ledOn;
        public Material ledOff;
        public Renderer mirrorRenderer;
        public Vector3 mirrorPos, knobLocal, handbrakeGripLocal;
        public float wheelRadius = 0.172f;
        public IDriverArms arms;

        /// <summary>Steering-wheel turn at full lock (degrees each way).</summary>
        public const float WheelLockDeg = 300f;
        const float HbPullDeg = 26f;

        static readonly Dictionary<CarController, CockpitRig> rigs = new Dictionary<CarController, CockpitRig>();

        Quaternion wheelBase, shifterBase, hbBase, tachBase, boostBase, waterBase;
        float lastWheel, wheelVel, tachT, boostT, waterT = 0.47f, hbT;
        int shownGear = int.MinValue, shownSpeed = -1;
        int[] ledState;

        // hands: 0 right, 1 left
        class Hand
        {
            public float gripW;        // grip angle in wheel space (deg, CCW from 3 o'clock as the driver sees it)
            public bool regrab;
            public float regrabT;
            public Vector3 fromPos;
            public Quaternion fromRot;
        }
        readonly Hand[] hands = { new Hand(), new Hand() };
        static readonly float[] Home = { 10f, 170f };

        enum Task { None, Shifter, Handbrake }
        Task task, lastTask;
        float taskBlend;
        Vector3 taskPos;
        Quaternion taskRot = Quaternion.identity;

        // shifter
        Vector2 knobGate;
        readonly List<Vector2> path = new List<Vector2>();
        float pathT = 1f, shiftStart, shiftLinger;
        int animGear = 1;

        // mirror
        Camera mirrorCam;
        RenderTexture mirrorRT;

        public Vector3 EyeLocal => dims.Eye;

        /// <summary>The cockpit for a car (built on first use).</summary>
        public static CockpitRig For(CarController car)
        {
            if (car == null) return null;
            if (rigs.TryGetValue(car, out var rig) && rig != null) return rig;
            rig = CockpitBuilder.Build(car);
            if (rig != null) { rigs[car] = rig; rig.gameObject.SetActive(false); }
            return rig;
        }

        public void Init()
        {
            wheelBase = wheel.localRotation;
            shifterBase = shifter.localRotation;
            hbBase = handbrake.localRotation;
            tachBase = tachNeedle.localRotation;
            boostBase = boostNeedle.localRotation;
            waterBase = waterNeedle.localRotation;
            ledState = new int[shiftLights.Length];
            knobGate = GatePos(car.Gear);
            animGear = car.Gear;
            for (int i = 0; i < 2; i++) hands[i].gripW = Home[i];
        }

        public void SetActive(bool on)
        {
            if (gameObject.activeSelf == on) return;
            gameObject.SetActive(on);
            var fx = car.GetComponent<CarEffects>();
            if (fx != null) fx.InteriorView = on;
            if (on) { EnsureMirror(); Snap(); }
            else if (mirrorCam != null) mirrorCam.enabled = false;
        }

        void OnDestroy()
        {
            rigs.Remove(car);
            if (mirrorCam != null) Destroy(mirrorCam.gameObject);
            if (mirrorRT != null) mirrorRT.Release();
        }

        void Snap()
        {
            lastWheel = WheelAngle();
            for (int i = 0; i < 2; i++) { hands[i].gripW = Home[i] + lastWheel; hands[i].regrab = false; }
            taskBlend = 0f; task = Task.None;
            knobGate = GatePos(car.Gear); animGear = car.Gear; pathT = 1f;
            LateUpdate();
        }

        /// <summary>Dev captures: -dbgHandbrake pulls the (visual) handbrake for 1.2 s every 4 s.</summary>
        static bool DevHandbrake() => devHb && Mathf.Repeat(Time.time, 4f) < 1.2f;
        static readonly bool devHb = CommandLine.Has("-dbgHandbrake");
        static readonly string devTask = CommandLine.Get("-dbgTask");

        float WheelAngle() => car.SteerAngle / Mathf.Max(1f, car.spec.maxSteerDeg) * WheelLockDeg;

        void LateUpdate()
        {
            if (car == null) return;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);

            // ---------------------------------------------------------------- wheel
            float w = WheelAngle();
            wheelVel = Mathf.Lerp(wheelVel, (w - lastWheel) / dt, 1f - Mathf.Exp(-20f * dt));
            lastWheel = w;
            wheel.localRotation = wheelBase * Quaternion.Euler(0f, 0f, -w);

            // ---------------------------------------------------------------- shifter path (H pattern via the neutral rail)
            int target = car.IsShifting ? car.PendingGear : car.Gear;
            if (target != animGear)
            {
                animGear = target;
                path.Clear();
                Vector2 to = GatePos(target);
                path.Add(knobGate); path.Add(new Vector2(knobGate.x, 0f)); path.Add(new Vector2(to.x, 0f)); path.Add(to);
                pathT = 0f;
                shiftStart = Time.time;
                shiftLinger = Time.time + 0.55f;
            }
            if (pathT < 1f && (taskBlend > 0.75f || task == Task.Handbrake || Time.time - shiftStart > 0.12f))
            {
                pathT = Mathf.Min(1f, pathT + dt / 0.12f);
                knobGate = AlongPath(path, Smooth(pathT));
            }
            const float lever = 0.155f;
            shifter.localRotation = shifterBase * Quaternion.Euler(Mathf.Atan2(knobGate.y, lever) * Mathf.Rad2Deg, 0f, -Mathf.Atan2(knobGate.x, lever) * Mathf.Rad2Deg);

            // ---------------------------------------------------------------- left-hand task
            bool hbWanted = (car.input.handbrake || DevHandbrake()) && !car.frozen;
            Task want = hbWanted ? Task.Handbrake : (pathT < 1f || Time.time < shiftLinger) ? Task.Shifter : Task.None;
            if (devTask != null) want = devTask == "lever" ? Task.Handbrake : Task.Shifter;   // dev: -dbgTask knob|lever
            if (want != Task.None) task = want;
            if (want != Task.None && lastTask == Task.None) hands[1].gripW = Home[1] + w;   // come back to the home grip
            lastTask = want;
            taskBlend = Mathf.MoveTowards(taskBlend, want != Task.None ? 1f : 0f, dt / (want != Task.None ? 0.09f : 0.17f));
            if (taskBlend <= 0f) task = Task.None;

            // handbrake lever follows the hand (or the input when the hand is already there)
            float hbTarget = hbWanted && taskBlend > 0.7f ? 1f : 0f;
            hbT = Mathf.MoveTowards(hbT, hbTarget, dt / 0.07f);
            handbrake.localRotation = hbBase * Quaternion.Euler(-HbPullDeg * Smooth(hbT), 0f, 0f);

            // ---------------------------------------------------------------- hands
            bool oneHanded = taskBlend > 0.5f;
            for (int i = 0; i < 2; i++)
            {
                WheelHand(i, w, dt, oneHanded && i == 0, out Vector3 pos, out Quaternion rot);
                var hand = hands[i];
                Grip grip = Grip.Wheel;
                float open = hand.regrab ? Mathf.Sin(Mathf.PI * hand.regrabT) : 0f;    // let go, move, take hold again
                if (i == 1 && taskBlend > 0f && task != Task.None)
                {
                    TaskPose(task, out Vector3 tp, out Quaternion tr);
                    float k = 1f - Mathf.Exp(-30f * dt);
                    if (taskBlend < 0.05f || taskPos == Vector3.zero) { taskPos = tp; taskRot = tr; }
                    else { taskPos = Vector3.Lerp(taskPos, tp, k); taskRot = Quaternion.Slerp(taskRot, tr, k); }
                    float b = Smooth(taskBlend);
                    Vector3 lift = (Vector3.up * 0.6f - ColumnDir() * 0.4f) * 0.06f * Mathf.Sin(Mathf.PI * b);
                    pos = Vector3.Lerp(pos, taskPos, b) + lift;
                    rot = Quaternion.Slerp(rot, taskRot, b);
                    if (b > 0.5f) grip = task == Task.Handbrake ? Grip.Lever : Grip.Knob;
                    open = Mathf.Max(open, Mathf.Sin(Mathf.PI * b));
                }
                arms.SetThumbTarget(i, grip == Grip.Wheel && !hand.regrab ? SpokeThumbPoint(i, w) : (Vector3?)null);
                arms.Pose(i, pos, rot, grip, open);
            }

            UpdateGauges(dt);
            UpdateMirror();
        }

        // ---------------------------------------------------------------- wheel grips

        Vector3 ColumnDir() => wheelBase * Vector3.forward;

        /// <summary>
        /// Hand frame on the rim (forward = wrist-to-knuckles, up = back of the hand): the back of the glove faces the
        /// driver and a little outward, the index finger leads along the rim toward 12 o'clock, the knuckles point
        /// outward and forward round the rim -- the real 9-and-3 grip.
        /// </summary>
        void RimPose(int hand, float carAngle, out Vector3 pos, out Quaternion rot)
        {
            float a = carAngle * Mathf.Deg2Rad;
            Vector3 radial = wheelBase * new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0f);
            Vector3 ccw = wheelBase * new Vector3(-Mathf.Sin(a), Mathf.Cos(a), 0f);
            Vector3 col = ColumnDir();
            pos = wheel.localPosition + radial * wheelRadius;
            Vector3 index = hand == 0 ? ccw : -ccw;                       // index finger side of the fist
            Vector3 back = Vector3.ProjectOnPlane(-col * 0.8f + radial * 0.45f, index).normalized;
            Vector3 fingers = Vector3.Cross(back, index).normalized;
            if (Vector3.Dot(fingers, radial) < 0f) fingers = -fingers;
            rot = Quaternion.LookRotation(fingers, back);
        }

        void WheelHand(int i, float w, float dt, bool oneHanded, out Vector3 pos, out Quaternion rot)
        {
            var h = hands[i];
            float home = Home[i];
            float carAng = h.gripW - w;
            if (!h.regrab)
            {
                if (Mathf.Abs(wheelVel) > 540f)
                {
                    // the wheel is spinning back through the palms: hands slide toward their home grip
                    carAng = Mathf.MoveTowardsAngle(carAng, home, 300f * dt);
                    h.gripW = carAng + w;
                }
                else
                {
                    float rel = Mathf.DeltaAngle(home, carAng);
                    float lo = i == 0 ? -80f : -120f, hi = i == 0 ? 120f : 80f;
                    if (oneHanded) { lo -= 35f; hi += 35f; }
                    if (rel < lo || rel > hi)
                    {
                        RimPose(i, carAng, out h.fromPos, out h.fromRot);
                        h.regrab = true;
                        h.regrabT = 0f;
                        // re-grab at the home position, or past it in the turning direction for big inputs
                        float lead = Mathf.Clamp(wheelVel * 0.06f, -40f, 40f);
                        h.gripW = home - lead + w;
                    }
                }
            }
            if (h.regrab)
            {
                h.regrabT = Mathf.Min(1f, h.regrabT + dt / 0.14f);
                RimPose(i, h.gripW - w, out Vector3 tp, out Quaternion tr);
                float s = Smooth(h.regrabT);
                Vector3 lift = -ColumnDir() * 0.07f * Mathf.Sin(Mathf.PI * s);
                pos = Vector3.Lerp(h.fromPos, tp, s) + lift;
                rot = Quaternion.Slerp(h.fromRot, tr, s);
                if (h.regrabT >= 1f) h.regrab = false;
                return;
            }
            RimPose(i, h.gripW - w, out pos, out rot);
        }

        /// <summary>
        /// Where a thumb rests when the hand holds the rim next to a spoke (9-and-3): on the driver's face of the
        /// 3 o'clock (right hand) or 9 o'clock (left hand) spoke, just inside the rim. Null when the hand is elsewhere.
        /// </summary>
        Vector3? SpokeThumbPoint(int i, float w)
        {
            float spoke = i == 0 ? 0f : 180f;                 // wheel-local angle of the spoke next to this hand
            if (Mathf.Abs(Mathf.DeltaAngle(hands[i].gripW, spoke)) > 32f) return null;
            float a = (spoke - w) * Mathf.Deg2Rad;            // where that spoke is now, in car space
            Vector3 radial = wheelBase * new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0f);
            float r = wheelRadius - 0.032f;
            // the spokes dish about 12 mm toward the dash this far out; the thumb lies on their driver-side face, 6 mm nearer
            return wheel.localPosition + radial * r + ColumnDir() * 0.006f;
        }

        void TaskPose(Task t, out Vector3 pos, out Quaternion rot)
        {
            if (t == Task.Handbrake)
            {
                Vector3 axis = (handbrake.localRotation * handbrakeGripLocal).normalized;
                pos = handbrake.localPosition + handbrake.localRotation * handbrakeGripLocal;
                Vector3 fingers = Vector3.ProjectOnPlane(Vector3.forward, axis).normalized;
                Vector3 back = Vector3.ProjectOnPlane(Vector3.left, fingers);
                rot = Quaternion.LookRotation(fingers, back);
                return;
            }
            Vector3 knob = shifter.localPosition + shifter.localRotation * knobLocal;
            pos = knob + Vector3.up * 0.006f;
            rot = Quaternion.LookRotation(new Vector3(0f, -0.62f, 0.78f), Vector3.up);
        }

        // ---------------------------------------------------------------- shifter gate

        /// <summary>Knob offset (x right, y forward) in the gate for a gear: 1-2 left, 3-4 middle, 5-6 right, R far left up.</summary>
        Vector2 GatePos(int g)
        {
            const float col = 0.045f, row = 0.052f;
            if (g == 0) return Vector2.zero;
            if (g < 0) return new Vector2(-2f * col, row);
            int c = (g - 1) / 2;
            int cols = (car.spec.gears.Length + 1) / 2;
            float x = (c - (cols - 1) * 0.5f) * col;
            return new Vector2(x, (g % 2 == 1) ? row : -row);
        }

        static Vector2 AlongPath(List<Vector2> p, float t)
        {
            float total = 0f;
            for (int i = 1; i < p.Count; i++) total += Vector2.Distance(p[i - 1], p[i]);
            if (total < 1e-5f) return p[p.Count - 1];
            float d = t * total;
            for (int i = 1; i < p.Count; i++)
            {
                float seg = Vector2.Distance(p[i - 1], p[i]);
                if (d <= seg) return Vector2.Lerp(p[i - 1], p[i], seg > 1e-6f ? d / seg : 1f);
                d -= seg;
            }
            return p[p.Count - 1];
        }

        static float Smooth(float t) { t = Mathf.Clamp01(t); return t * t * (3f - 2f * t); }

        // ---------------------------------------------------------------- gauges

        void UpdateGauges(float dt)
        {
            float k = 1f - Mathf.Exp(-22f * dt);
            float rpmT = Mathf.Clamp01(car.EngineRpm / Mathf.Max(1000f, dims.dialMaxRpm));
            tachT = Mathf.Lerp(tachT, rpmT, k);
            tachNeedle.localRotation = tachBase * Quaternion.Euler(0f, 0f, 225f - 270f * tachT);

            float gain = car.spec.turboBoostGain;
            float bar = gain > 0f && car.Boost > 0.02f ? car.Boost * (0.8f + gain) : Mathf.Lerp(-0.72f, -0.08f, car.Throttle);
            boostT = Mathf.Lerp(boostT, Mathf.Clamp01((bar + 1f) / 3f), k);
            boostNeedle.localRotation = boostBase * Quaternion.Euler(0f, 0f, 225f - 270f * boostT);
            float temp = 86f + Mathf.Sin(Time.time * 0.05f) * 1.5f + car.EngineLoad * 4f;
            waterT = Mathf.Lerp(waterT, Mathf.Clamp01((temp - 50f) / 80f), dt * 0.5f);
            waterNeedle.localRotation = waterBase * Quaternion.Euler(0f, 0f, 225f - 270f * waterT);

            int g = car.Gear;
            if (g != shownGear) { shownGear = g; gearText.text = g < 0 ? "R" : g == 0 ? "N" : g.ToString(); }
            int spd = Mathf.RoundToInt(car.SpeedKmh);
            if (spd != shownSpeed) { shownSpeed = spd; speedText.text = spd + " km/h"; }

            // shift lights: green, green, yellow, yellow, red, red, red; flash blue at the limiter
            float red = dims.redline > 0f ? dims.redline : car.spec.redlineRpm;
            float start = red * 0.78f;
            int lit = Mathf.Clamp(Mathf.FloorToInt((car.EngineRpm - start) / (red - start) * shiftLights.Length + 0.5f), 0, shiftLights.Length);
            bool flash = car.OnLimiter || car.EngineRpm >= red;
            bool flashOn = ((int)(Time.time * 14f) & 1) == 0;
            for (int i = 0; i < shiftLights.Length; i++)
            {
                int s = flash ? (flashOn ? 4 : 0) : i < lit ? (i < 2 ? 1 : i < 4 ? 2 : 3) : 0;
                if (s == ledState[i]) continue;
                ledState[i] = s;
                shiftLights[i].sharedMaterial = s == 0 ? ledOff : ledOn[s - 1];
            }
        }

        // ---------------------------------------------------------------- mirror

        void EnsureMirror()
        {
            if (mirrorCam != null || mirrorRenderer == null) return;
            mirrorRT = new RenderTexture(384, 128, 16, RenderTextureFormat.ARGB32) { name = "RearMirror", antiAliasing = 1 };
            var go = new GameObject("MirrorCamera");
            go.transform.SetParent(car.transform, false);
            // just behind the rear bumper: our own car stays out of shot while rivals and traffic behind still show
            go.transform.localPosition = new Vector3(0f, mirrorPos.y - 0.12f, -(car.spec.wheelbase * 0.5f + 1.45f));
            go.transform.localRotation = Quaternion.Euler(2f, 180f, 0f);
            mirrorCam = go.AddComponent<Camera>();
            mirrorCam.targetTexture = mirrorRT;
            mirrorCam.fieldOfView = 19f;
            mirrorCam.nearClipPlane = 0.25f;
            mirrorCam.farClipPlane = 450f;
            mirrorCam.cullingMask = ~(1 << 5);
            mirrorCam.depth = -10f;
            mirrorCam.allowMSAA = false;
            mirrorCam.allowHDR = false;
            var data = mirrorCam.GetUniversalAdditionalCameraData();
            data.renderShadows = false;
            data.renderPostProcessing = false;
            data.requiresDepthTexture = false;
            data.requiresColorTexture = false;
            data.antialiasing = AntialiasingMode.None;
            var mat = new Material(Shader.Find("UI/Default")) { mainTexture = mirrorRT, color = new Color(0.92f, 0.92f, 0.95f) };
            mat.mainTextureScale = new Vector2(-1f, 1f);    // mirror image
            mat.mainTextureOffset = new Vector2(1f, 0f);
            mat.renderQueue = 3000;
            mirrorRenderer.sharedMaterial = mat;
        }

        void UpdateMirror()
        {
            if (mirrorCam == null) return;
            mirrorCam.enabled = (Time.frameCount & 1) == 0;   // 30 Hz at 60 fps is plenty for a mirror
        }
    }
}
