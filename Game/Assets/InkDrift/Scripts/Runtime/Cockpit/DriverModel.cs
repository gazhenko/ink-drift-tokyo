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
            public Color color; public string normal; public float bump, smooth, sheen, wear; public Color sheenColor, wearColor; public string decal;
        }

        static readonly Dictionary<string, Look> Looks = new Dictionary<string, Look>
        {
            // quilted Nomex: deep racing blue with a soft cloth sheen
            { "M_DrvSuit", new Look { color = new Color(0.12f, 0.21f, 0.5f), normal = "suit_n", bump = 0.8f, smooth = 0.2f, sheen = 0.35f, sheenColor = new Color(0.55f, 0.7f, 1f) } },
            { "M_DrvStripe", new Look { color = new Color(0.86f, 0.86f, 0.88f), normal = "twill_n", bump = 0.7f, smooth = 0.26f, sheen = 0.35f, sheenColor = Color.white } },
            { "M_DrvStretch", new Look { color = new Color(0.11f, 0.13f, 0.22f), normal = "twill_n", bump = 0.9f, smooth = 0.2f, sheen = 0.4f, sheenColor = new Color(0.5f, 0.6f, 0.9f) } },
            { "M_DrvKnit", new Look { color = new Color(0.085f, 0.085f, 0.095f), normal = "knit_n", bump = 1.0f, smooth = 0.14f, sheen = 0.3f, sheenColor = new Color(0.5f, 0.5f, 0.55f) } },
            // full-grain leather: dark, glossy, scuffed lighter on the knuckles and edges
            { "M_DrvGloveBack", new Look { color = new Color(0.085f, 0.085f, 0.09f), normal = "leather_n", bump = 0.28f, smooth = 0.33f, wear = 0.5f, wearColor = new Color(0.24f, 0.24f, 0.26f) } },
            { "M_DrvKnuckle", new Look { color = new Color(0.55f, 0.06f, 0.09f), normal = "leather_n", bump = 0.28f, smooth = 0.3f, wear = 0.4f, wearColor = new Color(0.7f, 0.3f, 0.32f) } },
            // suede palm with silicone grip print
            { "M_DrvGlovePalm", new Look { color = new Color(0.13f, 0.13f, 0.14f), normal = "suede_n", bump = 0.6f, smooth = 0.15f, sheen = 0.3f, sheenColor = new Color(0.6f, 0.6f, 0.65f) } },
            { "M_DrvStrap", new Look { color = new Color(0.1f, 0.1f, 0.11f), normal = "velcro_n", bump = 0.9f, smooth = 0.1f, sheen = 0.2f, sheenColor = new Color(0.5f, 0.5f, 0.5f) } },
            { "M_DrvLogo", new Look { color = Color.white, smooth = 0.4f, decal = "glove_logo" } },
            { "M_DrvPatchInk", new Look { color = Color.white, smooth = 0.3f, sheen = 0.2f, sheenColor = Color.white, decal = "patch_ink" } },
            { "M_DrvPatchFlag", new Look { color = Color.white, smooth = 0.3f, sheen = 0.2f, sheenColor = Color.white, decal = "patch_flag" } },
            { "M_DrvPatchClass", new Look { color = Color.white, smooth = 0.3f, decal = "patch_class" } },
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
                m.SetColor("_BaseColor", l.color);
                if (l.decal != null) m.SetTexture("_BaseMap", Resources.Load<Texture2D>("Driver/" + l.decal));
                if (l.normal != null) m.SetTexture("_BumpMap", Resources.Load<Texture2D>("Driver/" + l.normal));
                m.SetFloat("_BumpScale", l.bump);
                if (bake != null) m.SetTexture("_BakeMap", bake);
                m.SetFloat("_Smoothness", l.smooth);
                m.SetFloat("_Sheen", l.sheen);
                m.SetColor("_SheenColor", l.sheenColor);
                m.SetFloat("_Wear", l.wear);
                m.SetColor("_WearColor", l.wearColor);
                m.SetFloat("_AOStrength", 1f);
                m.SetFloat("_CavityStrength", 0.6f);
                m.SetFloat("_AmbientBoost", AmbientBoost);
            }
            r.materials = mats;
        }

        /// <summary>Cockpit ambient: the toon interior is lit "anime bright"; the driver needs a little more fill to sit in it.</summary>
        public static float AmbientBoost = 1.3f;

        static Transform Find(Transform t, string name)
        {
            if (t.name == name) return t;
            foreach (Transform c in t) { var r = Find(c, name); if (r != null) return r; }
            return null;
        }

        /// <summary>Rest-pose measurements: hand frame, finger curl axes and the grip centre of every hold.</summary>
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
                    foreach (int idx in r.sharedMesh.GetTriangles(sm)) pts.Add(r.transform.TransformPoint(v[idx]));
                    Object.Destroy(baked);
                }
            }
            return pts;
        }

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
            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                {
                    float want = Mathf.Lerp(hold[f, j], rel[f, j], open);
                    a.curl[f, j] = Mathf.Lerp(a.curl[f, j], want, k);
                    if (a.fing[f, j]) a.fing[f, j].localRotation = a.fingRest[f, j] * Quaternion.AngleAxis(a.curl[f, j], a.curlAxis[f, j]);
                }

            // letting go: the hand comes off the object toward the back of the hand before it travels
            gripPos += gripRot * Vector3.up * (0.045f * Mathf.SmoothStep(0f, 1f, open));
            // where the wrist must be for the held object to sit at the grip centre
            Quaternion rw = root.rotation * gripRot * a.frameToWrist;
            Vector3 gl = Vector3.Lerp(a.gripLocal[(int)grip], a.gripLocal[(int)Grip.Open], open);
            Vector3 wt = root.TransformPoint(gripPos) - rw * gl;

            // two-bone IK from the rest pose
            a.up1.localRotation = a.up1Rest; if (a.up2) a.up2.localRotation = a.up2Rest;
            a.low1.localRotation = a.low1Rest; if (a.low2) a.low2.localRotation = a.low2Rest;
            a.wrist.localRotation = a.wristRest;
            Vector3 S = a.up1.position, e0 = a.low1.position, w0 = a.wrist.position;
            float la = (e0 - S).magnitude, lb = (w0 - e0).magnitude;
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
            Vector3 E = S + dir * x + bend.normalized * h;

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
        }
    }
}
