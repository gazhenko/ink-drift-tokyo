using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift
{
    /// <summary>What a hand is holding (sets the finger pose and where the held object sits in the fist).</summary>
    public enum Grip { Wheel, Lever, Knob, Open }

    /// <summary>Driver arms the cockpit can pose. Index 0 = right arm, 1 = left. Positions/rotations are car-local.</summary>
    public interface IDriverArms
    {
        /// <param name="gripPos">centre of the object being held</param>
        /// <param name="gripRot">forward = where the fingers point past the grip, up = back of the hand</param>
        /// <param name="open">0 = holding, 1 = hand relaxed open (travelling between holds)</param>
        void Pose(int i, Vector3 gripPos, Quaternion gripRot, Grip grip, float open);

        /// <summary>Car-local point the thumb should rest on (a wheel spoke), or null for the normal grip.</summary>
        void SetThumbTarget(int i, Vector3? carLocal);
    }

    /// <summary>
    /// The rigged driver (Tools/driver/build_driver.py: MakeHuman CC0 anatomy in a quilted race suit and leather
    /// gloves, MakeHuman skeleton + skin weights). Two-bone arm IK that keeps the elbow a hinge, forearm roll split
    /// onto the twist bone, and per-joint finger curl about each finger's anatomical axis. The grip centre for each
    /// hold is measured from the posed fingers, so a rim, knob or lever sits inside the closed hand.
    /// </summary>
    public class DriverModel : IDriverArms
    {
        class Arm
        {
            public Transform up1, up2, low1, low2, wrist;
            public readonly Transform[,] fing = new Transform[5, 3];
            public Quaternion up1Rest, up2Rest, low1Rest, low2Rest, wristRest;
            public readonly Quaternion[,] fingRest = new Quaternion[5, 3];
            public readonly Vector3[,] curlAxis = new Vector3[5, 3];     // in each bone's own space
            public Quaternion frameToWrist;                              // wrist rotation relative to the (fingers, back) hand frame
            public Vector3 backLocal;                                    // back of the hand, wrist space
            public readonly Vector3[] gripLocal = new Vector3[4];        // grip centre per Grip, wrist space
            public readonly float[,] curl = new float[5, 3];             // current (smoothed) curl, degrees
            public Vector3 pole;                                         // elbow pole offset from the shoulder, car space
            public Vector3 foreFrame;                                    // elbow -> wrist at rest, in the hand frame
            public float roll, slant;                                    // current settle of the fist on the rim, degrees
            public float settleRoll, settleSlant; public bool settled;   // last solved settle (search warm start)
        }

        // degrees at the knuckle, middle and end joint: thumb, index, middle, ring, little
        static readonly float[][,] Poses =
        {
            // finger joints arc at ~26 mm radius: a 35 mm rim or lever fills the fist without passing through the fingers
            new float[,] { { 30, 34, 38 }, { 58, 70, 44 }, { 62, 72, 46 }, { 66, 74, 46 }, { 70, 74, 44 } },   // Wheel
            new float[,] { { 38, 38, 40 }, { 60, 72, 44 }, { 64, 74, 46 }, { 68, 76, 46 }, { 72, 76, 44 } },   // Lever
            new float[,] { { 14, 18, 22 }, { 34, 46, 28 }, { 38, 50, 30 }, { 42, 52, 30 }, { 46, 52, 28 } },   // Knob
            new float[,] { { 6, 8, 8 }, { 14, 20, 10 }, { 16, 22, 12 }, { 18, 24, 12 }, { 20, 24, 12 } },       // Open
        };

        readonly Arm[] arms = new Arm[2];
        Transform root;
        readonly Vector3?[] thumbTarget = new Vector3?[2];
        readonly float[] thumbHook = new float[2];
        // a hooked thumb lies almost straight along the spoke
        static readonly float[] HookCurl = { 4f, 6f, 10f };

        public void SetThumbTarget(int i, Vector3? carLocal) { thumbTarget[i] = carLocal; }

        public static DriverModel Create(Transform cockpitRoot, Vector3 eye)
        {
            var prefab = Resources.Load<GameObject>("Driver/driver_arms");
            if (prefab == null) return null;
            var go = Object.Instantiate(prefab, cockpitRoot, false);
            go.name = "Driver";
            var m = new DriverModel { root = cockpitRoot };
            string[] sides = { "R", "L" };
            for (int i = 0; i < 2; i++)
            {
                string s = sides[i];
                var a = new Arm
                {
                    up1 = Find(go.transform, "upperarm01." + s), up2 = Find(go.transform, "upperarm02." + s),
                    low1 = Find(go.transform, "lowerarm01." + s), low2 = Find(go.transform, "lowerarm02." + s),
                    wrist = Find(go.transform, "wrist." + s),
                };
                if (a.up1 == null || a.low1 == null || a.wrist == null) { Object.Destroy(go); return null; }
                for (int f = 0; f < 5; f++)
                    for (int j = 0; j < 3; j++)
                        a.fing[f, j] = Find(go.transform, $"finger{f + 1}-{j + 1}.{s}");
                m.arms[i] = a;
            }
            // shoulders under the driver's eye point
            Vector3 mid = (cockpitRoot.InverseTransformPoint(m.arms[0].up1.position) + cockpitRoot.InverseTransformPoint(m.arms[1].up1.position)) * 0.5f;
            go.transform.localPosition += eye + new Vector3(0f, -0.25f, -0.06f) - mid;
            foreach (var r in go.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                r.updateWhenOffscreen = true;            // bones move far from the bind pose
                ApplyLook(r);
                r.shadowCastingMode = ShadowCastingMode.On;   // hands shade the wheel, dash and each other
                r.lightProbeUsage = LightProbeUsage.Off;
                r.reflectionProbeUsage = ReflectionProbeUsage.Off;
                r.skinnedMotionVectors = false;
            }
            var logo = LogoCentres(go);
            for (int i = 0; i < 2; i++) m.Calibrate(m.arms[i], i, logo);
            return m;
        }

        // ---------------------------------------------------------------- materials (sRGB colours)
        struct Look
        {
            public Color color; public string scan; public float desat, unit, bump, smooth, sheen, wear; public Color sheenColor, wearColor;
            public string normal, decal; public float quilt;
        }

        // sRGB target colours; scans are tinted to them at real-world scale (UV0: glove 4 cm, suit 8 cm, trim 4 cm per unit)
        static readonly Dictionary<string, Look> Looks = new Dictionary<string, Look>
        {
            // multi-layer Nomex: scanned technical weave, quilted, deep racing blue with a cloth sheen
            { "M_DrvSuit", new Look { color = new Color(0.12f, 0.2f, 0.48f), scan = "nomex_weave", desat = 1f, unit = 0.08f, bump = 1.0f, smooth = 0.12f, quilt = 0.9f, sheen = 0.1f, sheenColor = new Color(0.55f, 0.7f, 1f) } },
            { "M_DrvStripe", new Look { color = new Color(0.84f, 0.84f, 0.86f), scan = "nomex_weave", desat = 1f, unit = 0.04f, bump = 1.0f, smooth = 0.13f, quilt = 0.5f, sheen = 0.1f, sheenColor = Color.white } },
            { "M_DrvStretch", new Look { color = new Color(0.1f, 0.12f, 0.2f), scan = "nomex_weave", desat = 1f, unit = 0.04f, bump = 1.0f, smooth = 0.12f, sheen = 0.1f, sheenColor = new Color(0.5f, 0.6f, 0.9f) } },
            { "M_DrvKnit", new Look { color = new Color(0.075f, 0.075f, 0.085f), scan = "knit", desat = 1f, unit = 0.04f, bump = 1.0f, smooth = 0.09f, sheen = 0.1f, sheenColor = new Color(0.5f, 0.5f, 0.55f) } },
            // scanned full-grain leather: black, satin, scuffed lighter on the knuckles and edges. The scan is upholstery
            // hide, so its grain is scaled 2.5x finer and softened toward the thin nappa of a driving glove
            { "M_DrvGloveBack", new Look { color = new Color(0.075f, 0.075f, 0.08f), scan = "leather_grain", desat = 1f, unit = 0.1f, bump = 0.5f, smooth = 0.21f, wear = 0.45f, wearColor = new Color(0.22f, 0.22f, 0.24f) } },
            { "M_DrvKnuckle", new Look { color = new Color(0.5f, 0.05f, 0.075f), scan = "leather_grain", desat = 1f, unit = 0.1f, bump = 0.5f, smooth = 0.2f, wear = 0.35f, wearColor = new Color(0.66f, 0.28f, 0.3f) } },
            // scanned suede palm (grip print from the procedural map rides on top as the macro layer)
            { "M_DrvGlovePalm", new Look { color = new Color(0.12f, 0.12f, 0.13f), scan = "suede", desat = 1f, unit = 0.04f, bump = 1.0f, smooth = 0.14f, normal = "suede_n", quilt = 0.5f, sheen = 0.1f, sheenColor = new Color(0.6f, 0.6f, 0.65f) } },
            { "M_DrvStrap", new Look { color = new Color(0.1f, 0.1f, 0.11f), normal = "velcro_n", bump = 0.9f, smooth = 0.1f, sheen = 0.08f, sheenColor = new Color(0.5f, 0.5f, 0.5f) } },
            { "M_DrvLogo", new Look { color = Color.white, smooth = 0.4f, decal = "glove_logo" } },
            { "M_DrvPatchInk", new Look { color = Color.white, smooth = 0.3f, sheen = 0.08f, sheenColor = Color.white, decal = "patch_ink" } },
            { "M_DrvPatchFlag", new Look { color = Color.white, smooth = 0.3f, sheen = 0.08f, sheenColor = Color.white, decal = "patch_flag" } },
            { "M_DrvPatchClass", new Look { color = Color.white, smooth = 0.3f, decal = "patch_class" } },
            // thread beads: glove contrast stitching (red) and suit stitching (light grey)
            { "M_DrvGusset", new Look { color = new Color(0.015f, 0.015f, 0.017f), smooth = 0.05f } },   // vent holes
            { "M_DrvStitchSuit", new Look { color = new Color(0.78f, 0.78f, 0.8f), smooth = 0.3f, sheen = 0.1f, sheenColor = Color.white } },
            { "M_DrvStitch", new Look { color = new Color(0.62f, 0.05f, 0.06f), smooth = 0.32f, sheen = 0.1f, sheenColor = new Color(1f, 0.5f, 0.5f) } },
        };

        static void ApplyLook(Renderer r)
        {
            var bake = Resources.Load<Texture2D>("Driver/" + r.name.ToLowerInvariant() + "_bake_mask");
            var mats = r.materials;   // instances
            foreach (var m in mats)
            {
                if (m == null || m.shader == null || m.shader.name != "InkDrift/Realistic") continue;
                string key = null;
                foreach (var k in Looks.Keys) if (m.name.StartsWith(k) && (key == null || k.Length > key.Length)) key = k;
                if (key == null) continue;
                var l = Looks[key];
                if (l.scan != null) ScanLibrary.Apply(m, l.scan, l.color, l.desat, l.smooth, l.bump, l.unit);
                else
                {
                    m.SetColor("_BaseColor", l.color);
                    m.SetFloat("_Smoothness", l.smooth);
                    m.SetFloat("_MaskStrength", 0f);
                    if (l.normal != null) { m.SetTexture("_BumpMap", Resources.Load<Texture2D>("Driver/" + l.normal)); m.SetFloat("_BumpScale", l.bump); }
                }
                if (l.decal != null) m.SetTexture("_BaseMap", Resources.Load<Texture2D>("Driver/" + l.decal));
                // macro layer: suit quilting / palm grip print from the procedural maps, at UV0 tile size
                if (l.quilt > 0f)
                {
                    m.SetTexture("_DetailNormal", Resources.Load<Texture2D>("Driver/" + (l.normal ?? "suit_n")));
                    m.SetFloat("_DetailTiling", key == "M_DrvStripe" ? 0.5f : 1f);
                    m.SetFloat("_DetailScale", l.quilt);
                }
                if (bake != null) m.SetTexture("_BakeMap", bake);
                m.SetFloat("_Sheen", l.sheen);
                m.SetColor("_SheenColor", l.sheenColor);
                m.SetFloat("_Wear", l.wear);
                m.SetColor("_WearColor", l.wearColor);
                m.SetFloat("_AOStrength", 1f);
                m.SetFloat("_CavityStrength", 0.6f);
                m.SetFloat("_AmbientBoost", AmbientBoost);
                // cloth barely reflects its surroundings; leather keeps a little sheen of the cabin
                bool leather = key == "M_DrvGloveBack" || key == "M_DrvKnuckle" || key == "M_DrvLogo";
                m.SetFloat("_EnvSpecular", leather ? InteriorEnvSpecular : ClothEnvSpecular);
            }
            r.materials = mats;
        }

        /// <summary>Cockpit ambient: the toon interior is lit "anime bright"; the driver needs a little more fill to sit in it.</summary>
        public static float AmbientBoost = 1.3f;

        /// <summary>Share of the environment reflection that reaches surfaces inside the cabin (roof/doors block the rest).</summary>
        public static float InteriorEnvSpecular = 0.15f;
        public static float ClothEnvSpecular = 0.04f;

        static Transform Find(Transform t, string name)
        {
            if (t.name == name) return t;
            foreach (Transform c in t) { var r = Find(c, name); if (r != null) return r; }
            return null;
        }

        /// <summary>Rest-pose world positions of the glove logo vertices (the logo sits on the back of each hand).</summary>
        static List<Vector3> LogoCentres(GameObject go)
        {
            var pts = new List<Vector3>();
            foreach (var r in go.GetComponentsInChildren<SkinnedMeshRenderer>())
            {
                var mats = r.sharedMaterials;
                for (int sm = 0; sm < mats.Length && sm < r.sharedMesh.subMeshCount; sm++)
                {
                    if (mats[sm] == null || !mats[sm].name.StartsWith("M_DrvLogo")) continue;
                    var baked = new Mesh();
                    r.BakeMesh(baked, false);   // unscaled: TransformPoint applies the scale
                    var v = baked.vertices;
                    // the baked copy is CPU-readable; the imported mesh isn't in player builds
                    if (sm < baked.subMeshCount)
                        foreach (int idx in baked.GetTriangles(sm)) pts.Add(r.transform.TransformPoint(v[idx]));
                    Object.Destroy(baked);
                }
            }
            return pts;
        }

        /// <summary>Rest-pose measurements: hand frame, finger curl axes and the grip centre of every hold.</summary>
        void Calibrate(Arm a, int i, List<Vector3> logo)
        {
            a.up1Rest = a.up1.localRotation; a.up2Rest = a.up2 ? a.up2.localRotation : Quaternion.identity;
            a.low1Rest = a.low1.localRotation; a.low2Rest = a.low2 ? a.low2.localRotation : Quaternion.identity;
            a.wristRest = a.wrist.localRotation;
            for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.fing[f, j]) a.fingRest[f, j] = a.fing[f, j].localRotation;

            Vector3 wr = a.wrist.position;
            Vector3 fingers = (a.fing[2, 0].position - wr).normalized;
            Vector3 across = (a.fing[1, 0].position - a.fing[4, 0].position).normalized;   // index -> little reversed
            Vector3 n = Vector3.Cross(fingers, across).normalized;
            // the back of the hand is where its logo is (nearest logo vertices to this wrist); fall back to the thumb side test
            Vector3 lc = Vector3.zero; int ln = 0;
            foreach (var p in logo) if ((p - wr).sqrMagnitude < 0.12f * 0.12f) { lc += p; ln++; }
            Vector3 palm;
            if (ln > 0) palm = Vector3.Dot(lc / ln - wr, n) > 0f ? -n : n;
            else
            {
                Vector3 tip = a.fing[0, 2].position + (a.fing[0, 2].position - a.fing[0, 1].position) * 0.9f;
                palm = Vector3.Dot(tip - wr, n) > 0f ? n : -n;
            }
            Vector3 back = -palm;
            back = Vector3.ProjectOnPlane(back, fingers).normalized;
            a.backLocal = Quaternion.Inverse(a.wrist.rotation) * back;
            a.frameToWrist = Quaternion.Inverse(Quaternion.LookRotation(fingers, back)) * a.wrist.rotation;
            a.foreFrame = Quaternion.Inverse(Quaternion.LookRotation(fingers, back)) * (wr - a.low1.position).normalized;
            Vector3 toLittle = (a.fing[4, 0].position - a.fing[1, 0].position).normalized;

            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                {
                    var b = a.fing[f, j];
                    if (b == null) continue;
                    Vector3 next = j < 2 && a.fing[f, j + 1] ? a.fing[f, j + 1].position : b.position + (b.position - a.fing[f, j - 1 >= 0 ? j - 1 : 0].position);
                    Vector3 d = (next - b.position).normalized;
                    // fingers fold toward the palm; the thumb folds across it toward the little finger
                    Vector3 toward = f == 0 ? (palm * 0.75f + toLittle * 0.55f).normalized : palm;
                    Vector3 axis = Vector3.Cross(d, toward).normalized;
                    a.curlAxis[f, j] = Quaternion.Inverse(b.rotation) * axis;
                }

            // grip centres: pose each hold, fit a circle through the middle finger's knuckle, middle and end joints
            for (int g = 0; g < 4; g++)
            {
                SetCurl(a, Poses[g], 1f);
                Vector3 p0 = a.fing[2, 0].position, p1 = a.fing[2, 1].position, p2 = a.fing[2, 2].position;
                Vector3 c = Circumcentre(p0, p1, p2, out bool ok);
                if (!ok || g == (int)Grip.Open) c = p0 + palm * 0.03f;
                // a shift knob is cupped under the palm rather than wrapped by the fingers
                if (g == (int)Grip.Knob) c = Vector3.Lerp(wr, a.fing[2, 0].position, 0.72f) + palm * 0.04f;
                a.gripLocal[g] = a.wrist.InverseTransformPoint(c);
            }
            SetCurl(a, Poses[(int)Grip.Open], 1f);
            for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) a.curl[f, j] = Poses[(int)Grip.Open][f, j];
            a.pole = new Vector3(i == 0 ? 0.55f : -0.55f, -0.75f, -0.2f);
        }

        /// <summary>Two-bone IK elbow for a wrist target (pulled in to arm's reach if needed).</summary>
        Vector3 Elbow(Arm a, Vector3 S, float la, float lb, ref Vector3 wt)
        {
            Vector3 d = wt - S;
            float len = d.magnitude;
            Vector3 dir = len > 1e-5f ? d / len : Vector3.forward;
            float L = Mathf.Clamp(len, Mathf.Abs(la - lb) + 0.01f, la + lb - 0.002f);
            if (len > L) wt = S + dir * L;
            float x = (la * la - lb * lb + L * L) / (2f * L);
            float h = Mathf.Sqrt(Mathf.Max(0f, la * la - x * x));
            Vector3 pole = root.TransformPoint(root.InverseTransformPoint(S) + a.pole);
            Vector3 bend = Vector3.ProjectOnPlane(pole - S, dir);
            if (bend.sqrMagnitude < 1e-8f) bend = -root.up;
            return S + dir * x + bend.normalized * h;
        }

        const float RollMax = 100f, SlantMax = 35f, ComfortBend = 40f;

        /// <summary>
        /// The fist's settle on the rim: a roll about the rim (the fist slides round its cross-section) and a slant about
        /// the back of the hand (the rim crosses the palm diagonally, as in a real grip). Both keep the rim inside the
        /// hand; this picks the pair closest to the designed grip that keeps the wrist within a comfortable bend.
        /// </summary>
        void WristSettle(Arm a, Vector3 S, float la, float lb, Vector3 gripPos, Quaternion gripRot, Vector3 gl, out float roll, out float slant)
        {
            Vector3 P = root.TransformPoint(gripPos);
            // a wrist bends ~40 degrees comfortably (extension with some ulnar deviation); beyond that it costs a lot
            float Cost(float r, float t)
            {
                float b = Bend(a, S, la, lb, P, gripRot, gl, r, t);
                return Mathf.Max(0f, b - ComfortBend) * 4f + b * 0.05f + Mathf.Abs(r) * 0.2f + Mathf.Abs(t) * 0.3f;
            }
            float best;
            if (!a.settled)
            {
                // first hold: coarse global search
                best = float.MaxValue; roll = 0f; slant = 0f;
                for (float r = -RollMax; r <= RollMax + 0.1f; r += 10f)
                    for (float t = -SlantMax; t <= SlantMax + 0.1f; t += 5f)
                    {
                        float c = Cost(r, t);
                        if (c < best) { best = c; roll = r; slant = t; }
                    }
                a.settled = true;
            }
            else { roll = a.settleRoll; slant = a.settleSlant; best = Cost(roll, slant); }
            // then a pattern search from the last answer: the cost changes smoothly as the wheel turns
            for (float step = 8f; step >= 0.99f; step *= 0.5f)
                for (int it = 0; it < 4; it++)
                {
                    bool moved = false;
                    for (int k = 0; k < 4; k++)
                    {
                        float r = Mathf.Clamp(roll + (k == 0 ? step : k == 1 ? -step : 0f), -RollMax, RollMax);
                        float t = Mathf.Clamp(slant + (k == 2 ? step : k == 3 ? -step : 0f), -SlantMax, SlantMax);
                        float c = Cost(r, t);
                        if (c < best - 1e-4f) { best = c; roll = r; slant = t; moved = true; }
                    }
                    if (!moved) break;
                }
            a.settleRoll = roll; a.settleSlant = slant;
            if (devWrist && Time.frameCount % 120 == 0)
                Debug.Log($"[Driver] arm {(a == arms[0] ? 0 : 1)} roll {roll:0} slant {slant:0} wrist bend {Bend(a, S, la, lb, P, gripRot, gl, 0f, 0f):0}->{Bend(a, S, la, lb, P, gripRot, gl, roll, slant):0}");
        }

        static readonly bool devWrist = CommandLine.Has("-dbgWrist");

        static Quaternion Settle(float roll, float slant) => Quaternion.AngleAxis(roll, Vector3.right) * Quaternion.AngleAxis(slant, Vector3.up);

        /// <summary>Angle between the forearm and the hand (0 = straight wrist) for a settle of the fist on the rim.</summary>
        float Bend(Arm a, Vector3 S, float la, float lb, Vector3 P, Quaternion gripRot, Vector3 gl, float roll, float slant)
        {
            Quaternion frame = root.rotation * gripRot * Settle(roll, slant);
            Vector3 wt = P - frame * a.frameToWrist * gl;
            return Vector3.Angle(wt - Elbow(a, S, la, lb, ref wt), frame * a.foreFrame);
        }

        static Vector3 Circumcentre(Vector3 a, Vector3 b, Vector3 c, out bool ok)
        {
            Vector3 ab = b - a, ac = c - a, n = Vector3.Cross(ab, ac);
            float d = 2f * n.sqrMagnitude;
            ok = d > 1e-10f;
            if (!ok) return a;
            return a + (Vector3.Cross(n, ab) * ac.sqrMagnitude + Vector3.Cross(ac, n) * ab.sqrMagnitude) / d;
        }

        static void SetCurl(Arm a, float[,] deg, float k)
        {
            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                    if (a.fing[f, j]) a.fing[f, j].localRotation = a.fingRest[f, j] * Quaternion.AngleAxis(deg[f, j] * k, a.curlAxis[f, j]);
        }

        public void Pose(int i, Vector3 gripPos, Quaternion gripRot, Grip grip, float open)
        {
            var a = arms[i];
            float dt = Mathf.Min(Time.deltaTime, 0.05f);
            open = Mathf.Clamp01(open);

            // fingers: hold pose blended toward a relaxed hand while travelling
            var hold = Poses[(int)grip];
            var rel = Poses[(int)Grip.Open];
            float k = 1f - Mathf.Exp(-18f * dt);
            bool hookWanted = thumbTarget[i].HasValue && grip == Grip.Wheel && open < 0.2f;
            thumbHook[i] = Mathf.MoveTowards(thumbHook[i], hookWanted ? 1f : 0f, dt / 0.12f);
            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                {
                    float want = Mathf.Lerp(hold[f, j], rel[f, j], open);
                    if (f == 0) want = Mathf.Lerp(want, HookCurl[j], thumbHook[i]);
                    a.curl[f, j] = Mathf.Lerp(a.curl[f, j], want, k);
                    if (a.fing[f, j]) a.fing[f, j].localRotation = a.fingRest[f, j] * Quaternion.AngleAxis(a.curl[f, j], a.curlAxis[f, j]);
                }

            Vector3 gl = Vector3.Lerp(a.gripLocal[(int)grip], a.gripLocal[(int)Grip.Open], open);
            // two-bone IK from the rest pose
            a.up1.localRotation = a.up1Rest; if (a.up2) a.up2.localRotation = a.up2Rest;
            a.low1.localRotation = a.low1Rest; if (a.low2) a.low2.localRotation = a.low2Rest;
            a.wrist.localRotation = a.wristRest;
            Vector3 S = a.up1.position, e0 = a.low1.position, w0 = a.wrist.position;
            float la = (e0 - S).magnitude, lb = (w0 - e0).magnitude;

            // a fist can roll round the rim and still hold it: settle at the roll that leaves the wrist straightest,
            // as a real driver's does, instead of bending it to whatever angle the grip frame dictates
            float rollWant = 0f, slantWant = 0f;
            if (grip == Grip.Wheel) WristSettle(a, S, la, lb, gripPos, gripRot, gl, out rollWant, out slantWant);
            float ks = 1f - Mathf.Exp(-8f * dt);
            a.roll = Mathf.Lerp(a.roll, rollWant * (1f - open), ks);
            a.slant = Mathf.Lerp(a.slant, slantWant * (1f - open), ks);
            gripRot *= Settle(a.roll, a.slant);   // local x runs along the rim (index to little), y out of the back of the hand

            // letting go: the hand comes off the object toward the back of the hand before it travels
            gripPos += gripRot * Vector3.up * (0.045f * Mathf.SmoothStep(0f, 1f, open));
            // where the wrist must be for the held object to sit at the grip centre
            Quaternion rw = root.rotation * gripRot * a.frameToWrist;
            Vector3 wt = root.TransformPoint(gripPos) - rw * gl;
            Vector3 E = Elbow(a, S, la, lb, ref wt);

            // upper arm: carry the elbow hinge with it so the forearm folds the anatomical way
            Vector3 h0 = Vector3.Cross(e0 - S, w0 - e0), h1 = Vector3.Cross(E - S, wt - E);
            if (h0.sqrMagnitude > 1e-10f && h1.sqrMagnitude > 1e-10f)
                a.up1.rotation = Quaternion.LookRotation((E - S).normalized, h1.normalized) * Quaternion.Inverse(Quaternion.LookRotation((e0 - S).normalized, h0.normalized)) * a.up1.rotation;
            else
                a.up1.rotation = Quaternion.FromToRotation(e0 - S, E - S) * a.up1.rotation;
            Vector3 ec = a.low1.position;
            a.low1.rotation = Quaternion.FromToRotation(a.wrist.position - ec, wt - ec) * a.low1.rotation;

            // forearm roll: the second forearm bone takes half of the hand's twist (no candy-wrapper wrist)
            if (a.low2)
            {
                Vector3 axis = (wt - ec).normalized;
                Vector3 now = Vector3.ProjectOnPlane(a.wrist.rotation * a.backLocal, axis);
                Vector3 want = Vector3.ProjectOnPlane(rw * a.backLocal, axis);
                float tw = Vector3.SignedAngle(now, want, axis);
                a.low2.rotation = Quaternion.AngleAxis(tw * 0.55f, axis) * a.low2.rotation;
            }
            a.wrist.rotation = rw;

            // thumb over the spoke: swing the thumb from its base so its tip rests on the target
            if (thumbHook[i] > 0.001f && thumbTarget[i].HasValue && a.fing[0, 0] && a.fing[0, 2])
            {
                Vector3 b0 = a.fing[0, 0].position;
                Vector3 tip = a.fing[0, 2].position + (a.fing[0, 2].position - a.fing[0, 1].position) * 0.9f;
                Vector3 tgt = root.TransformPoint(thumbTarget[i].Value);
                Quaternion q = Quaternion.FromToRotation(tip - b0, tgt - b0);
                q.ToAngleAxis(out float ang, out Vector3 ax);
                if (ang > 180f) ang -= 360f;
                ang = Mathf.Clamp(ang, -65f, 65f) * thumbHook[i];
                if (ax.sqrMagnitude > 1e-6f) a.fing[0, 0].rotation = Quaternion.AngleAxis(ang, ax) * a.fing[0, 0].rotation;
            }
        }
    }
}
