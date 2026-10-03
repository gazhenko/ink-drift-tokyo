using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift
{
    /// <summary>
    /// The driver's arms in a racing suit with gloves: shoulder anchors under the eye point, a two-bone IK per arm,
    /// and gloves posed around a grip axis. Hands are placed by <see cref="CockpitRig"/> (wheel, shifter, handbrake).
    /// Index 0 = right arm, 1 = left arm. All positions are local to the cockpit root (= car space).
    /// </summary>
    public class DriverArms : IDriverArms
    {
        /// <summary>Procedural fallback (used if the rigged driver model is missing): holds are all the same fist.</summary>
        public void Pose(int i, Vector3 gripPos, Quaternion gripRot, Grip grip, float open) => Pose(i, gripPos, gripRot);
        public void SetThumbTarget(int i, Vector3? carLocal) { }
        public void SetEffort(int i, float effort) { }
        public void SetBodyOffset(Vector3 carLocal) { }

        public const float UpperLen = 0.30f, ForeLen = 0.285f;
        /// <summary>Wrist point in glove space (the glove origin is the centre of whatever it grips).</summary>
        public static readonly Vector3 WristLocal = new Vector3(0f, 0.004f, -0.112f);

        public readonly Transform[] upper = new Transform[2], fore = new Transform[2], elbow = new Transform[2], hand = new Transform[2];
        public readonly Vector3[] shoulder = new Vector3[2];

        public static DriverArms Create(Transform root, Vector3 eye, Material suit, Material stripe, Material glove, Material cuff)
        {
            var a = new DriverArms();
            var parent = new GameObject("DriverArms").transform;
            parent.SetParent(root, false);

            var upperMesh = new ProcMesh();
            upperMesh.Tube(Vector3.zero, Vector3.forward, 0.052f, 0.043f, 18);
            var foreMesh = new ProcMesh();
            foreMesh.Tube(Vector3.zero, Vector3.forward, 0.043f, 0.033f, 18);
            var stripeMesh = new ProcMesh();
            stripeMesh.Tube(new Vector3(0, 0, 0.30f), new Vector3(0, 0, 0.36f), 0.0405f, 0.0395f, 18, false, false);
            var elbowMesh = new ProcMesh();
            elbowMesh.Sphere(Vector3.zero, 0.045f, 16);
            var right = GloveMesh(out var rightCuff);
            var gloveMeshes = new[] { right, right.MirroredX() };
            var cuffMeshes = new[] { rightCuff, rightCuff.MirroredX() };

            for (int i = 0; i < 2; i++)
            {
                string side = i == 0 ? "R" : "L";
                a.upper[i] = Node(parent, "UpperArm" + side, upperMesh, suit);
                a.fore[i] = Node(parent, "Forearm" + side, foreMesh, suit);
                Node(a.fore[i], "Stripe", stripeMesh, stripe);
                a.elbow[i] = Node(parent, "Elbow" + side, elbowMesh, suit);
                a.hand[i] = Node(parent, "Glove" + side, gloveMeshes[i], glove);
                Node(a.hand[i], "Cuff", cuffMeshes[i], cuff);
                float sx = i == 0 ? 0.19f : -0.19f;
                a.shoulder[i] = eye + new Vector3(sx, -0.25f, -0.07f);
            }
            return a;
        }

        static Transform Node(Transform parent, string name, ProcMesh pm, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = pm.ToMesh("Driver_" + name);
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.lightProbeUsage = LightProbeUsage.Off;
            mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            return go.transform;
        }

        /// <summary>
        /// Right racing glove closed around a grip axis along x (thumb toward -x), back of the hand +y, fingers
        /// wrapping forward (+z) over the grip and back underneath. Origin = centre of the gripped bar.
        /// </summary>
        static ProcMesh GloveMesh(out ProcMesh cuff)
        {
            var g = new ProcMesh();
            g.RoundBox(new Vector3(0f, 0.006f, -0.058f), new Vector3(0.084f, 0.031f, 0.08f), Quaternion.Euler(8f, 0f, 0f), 0.35f, 10);
            float[] fx = { -0.0275f, -0.0092f, 0.0092f, 0.0265f };
            float[] fr = { 0.0098f, 0.0102f, 0.0097f, 0.0086f };
            float[] fl = { 1f, 1.06f, 1f, 0.84f };
            for (int i = 0; i < 4; i++)
            {
                Vector3 k = new Vector3(fx[i], 0.019f, -0.02f);
                Vector3 P(float y, float z) => k + (new Vector3(fx[i], y, z) - k) * fl[i];
                Vector3 p1 = P(0.031f, 0.012f), p2 = P(0.013f, 0.035f), p3 = P(-0.015f, 0.029f);
                g.Capsule(k, p1, fr[i], 10);
                g.Capsule(p1, p2, fr[i] * 0.97f, 10);
                g.Capsule(p2, p3, fr[i] * 0.92f, 10);
                g.Ellipsoid(k + new Vector3(0f, 0.004f, -0.002f), new Vector3(fr[i] * 1.15f, fr[i] * 0.9f, fr[i] * 1.2f), Quaternion.identity, 10);   // knuckle
            }
            var t0 = new Vector3(-0.039f, -0.004f, -0.07f);
            var t1 = new Vector3(-0.047f, -0.013f, -0.036f);
            var t2 = new Vector3(-0.033f, -0.023f, -0.009f);
            var t3 = new Vector3(-0.017f, -0.027f, 0.007f);
            g.Capsule(t0, t1, 0.0125f, 10);
            g.Capsule(t1, t2, 0.0108f, 10);
            g.Capsule(t2, t3, 0.0098f, 10);
            g.Tube(new Vector3(0f, 0.004f, -0.09f), new Vector3(0f, 0.004f, -0.105f), 0.031f, 0.033f, 16, false, false);   // wrist
            cuff = new ProcMesh();
            cuff.Tube(new Vector3(0f, 0.004f, -0.100f), new Vector3(0f, 0.004f, -0.138f), 0.034f, 0.039f, 18, false, false);   // open gauntlet over the sleeve
            return g;
        }

        /// <summary>Places the glove (car space) and solves the arm to its wrist.</summary>
        public void Pose(int i, Vector3 handPos, Quaternion handRot)
        {
            hand[i].localPosition = handPos;
            hand[i].localRotation = handRot;
            Vector3 w = handPos + handRot * WristLocal;
            Vector3 s = shoulder[i];
            // elbows hang outward and down, slightly behind the shoulder line
            Vector3 pole = s + new Vector3(i == 0 ? 0.55f : -0.55f, -0.75f, -0.2f);
            Vector3 e = SolveElbow(s, ref w, pole);
            Place(upper[i], s, e);
            Place(fore[i], e, w);
            elbow[i].localPosition = e;
        }

        /// <summary>Two-bone IK: returns the elbow; pulls the wrist in if the target is out of reach.</summary>
        static Vector3 SolveElbow(Vector3 s, ref Vector3 w, Vector3 pole)
        {
            const float a = UpperLen, b = ForeLen;
            Vector3 d = w - s;
            float len = d.magnitude;
            Vector3 dir = len > 1e-5f ? d / len : Vector3.forward;
            float L = Mathf.Clamp(len, Mathf.Abs(a - b) + 0.01f, a + b - 0.002f);
            if (len > L) w = s + dir * L;
            float x = (a * a - b * b + L * L) / (2f * L);
            float h = Mathf.Sqrt(Mathf.Max(0f, a * a - x * x));
            Vector3 bend = Vector3.ProjectOnPlane(pole - s, dir);
            if (bend.sqrMagnitude < 1e-8f) bend = Vector3.down;
            return s + dir * x + bend.normalized * h;
        }

        static void Place(Transform t, Vector3 from, Vector3 to)
        {
            Vector3 d = to - from;
            float len = Mathf.Max(d.magnitude, 1e-4f);
            t.localPosition = from;
            t.localRotation = Quaternion.LookRotation(d / len, Mathf.Abs(Vector3.Dot(d / len, Vector3.up)) > 0.98f ? Vector3.forward : Vector3.up);
            t.localScale = new Vector3(1f, 1f, len);
        }
    }
}
