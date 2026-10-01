using UnityEngine;

namespace InkDrift
{
    /// <summary>Ring-buffer skidmark mesh (one draw call for every car).</summary>
    [RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
    public class Skidmarks : MonoBehaviour
    {
        public static Skidmarks I { get; private set; }
        const int MaxMarks = 4096;
        const float MinDistance = 0.25f;

        struct Mark { public Vector3 pos, normal, right; public float alpha; public int last; }

        readonly Mark[] marks = new Mark[MaxMarks];
        int index;
        bool dirty;
        Mesh mesh;
        Vector3[] verts; Vector3[] normals; Vector4[] tangents; Color32[] colors; Vector2[] uvs; int[] tris;

        void Awake()
        {
            I = this;
            transform.position = Vector3.zero;
            transform.rotation = Quaternion.identity;
            verts = new Vector3[MaxMarks * 4]; normals = new Vector3[MaxMarks * 4]; tangents = new Vector4[MaxMarks * 4];
            colors = new Color32[MaxMarks * 4]; uvs = new Vector2[MaxMarks * 4]; tris = new int[MaxMarks * 6];
            for (int i = 0; i < MaxMarks; i++) marks[i].last = -1;
            mesh = new Mesh { name = "Skidmarks" };
            mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.MarkDynamic();
            GetComponent<MeshFilter>().sharedMesh = mesh;
            var mr = GetComponent<MeshRenderer>();
            if (mr.sharedMaterial == null) mr.sharedMaterial = Resources.Load<Material>("Materials/Skidmark");
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        /// <returns>index to pass back next frame to continue the strip</returns>
        public int Add(Vector3 pos, Vector3 normal, float intensity, int last, float width)
        {
            if (intensity <= 0f) return -1;
            if (last >= 0)
            {
                float d = (pos - marks[last].pos).sqrMagnitude;
                if (d < MinDistance * MinDistance) return last;
                if (d > 4f) last = -1;
            }
            int i = index;
            index = (index + 1) % MaxMarks;
            ref var m = ref marks[i];
            m.pos = pos; m.normal = normal; m.alpha = Mathf.Clamp01(intensity); m.last = last;
            Vector3 dir = last >= 0 ? (pos - marks[last].pos) : Vector3.forward;
            m.right = Vector3.Cross(dir, normal).normalized * (width * 0.5f);
            if (last >= 0)
            {
                ref var p = ref marks[last];
                int v = i * 4;
                verts[v + 0] = p.pos - p.right; verts[v + 1] = p.pos + p.right;
                verts[v + 2] = m.pos - m.right; verts[v + 3] = m.pos + m.right;
                for (int k = 0; k < 4; k++) { normals[v + k] = normal; tangents[v + k] = new Vector4(1, 0, 0, 1); }
                byte a0 = (byte)(p.alpha * 200), a1 = (byte)(m.alpha * 200);
                colors[v + 0] = colors[v + 1] = new Color32(0, 0, 0, a0);
                colors[v + 2] = colors[v + 3] = new Color32(0, 0, 0, a1);
                uvs[v + 0] = new Vector2(0, 0); uvs[v + 1] = new Vector2(1, 0); uvs[v + 2] = new Vector2(0, 1); uvs[v + 3] = new Vector2(1, 1);
                int t = i * 6;
                tris[t + 0] = v; tris[t + 1] = v + 2; tris[t + 2] = v + 1;
                tris[t + 3] = v + 2; tris[t + 4] = v + 3; tris[t + 5] = v + 1;
            }
            else
            {
                int t = i * 6;
                for (int k = 0; k < 6; k++) tris[t + k] = 0;
            }
            dirty = true;
            return i;
        }

        void LateUpdate()
        {
            if (!dirty) return;
            dirty = false;
            mesh.vertices = verts; mesh.normals = normals; mesh.tangents = tangents; mesh.colors32 = colors; mesh.uv = uvs;
            mesh.SetTriangles(tris, 0, false);
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 100000f);
        }
    }
}
