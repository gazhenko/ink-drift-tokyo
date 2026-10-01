using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift.EditorTools
{
    /// <summary>Multi-submesh mesh builder with sweep/box/tube primitives (hard-edged normals for toon shading).</summary>
    public class MeshBuilder
    {
        public readonly List<Vector3> v = new List<Vector3>();
        public readonly List<Vector3> n = new List<Vector3>();
        public readonly List<Vector2> uv = new List<Vector2>();
        public readonly List<Color> c = new List<Color>();
        public readonly List<List<int>> subs = new List<List<int>>();

        public int VertexCount => v.Count;

        public List<int> Sub(int i)
        {
            while (subs.Count <= i) subs.Add(new List<int>());
            return subs[i];
        }

        public int Vert(Vector3 p, Vector3 nrm, Vector2 t, Color col)
        {
            v.Add(p); n.Add(nrm); uv.Add(t); c.Add(col);
            return v.Count - 1;
        }

        public void Tri(int sub, int a, int b, int d) { var s = Sub(sub); s.Add(a); s.Add(b); s.Add(d); }
        public void Quad(int sub, int a, int b, int d, int e) { Tri(sub, a, b, d); Tri(sub, a, d, e); }

        /// <summary>Flat quad p0..p3 (counter-clockwise when viewed from the front), UV rect.</summary>
        public void Quad(int sub, Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, Vector2 uv0, Vector2 uv1, Color col)
        {
            Vector3 nrm = Vector3.Cross(p1 - p0, p3 - p0).normalized;
            int a = Vert(p0, nrm, new Vector2(uv0.x, uv0.y), col);
            int b = Vert(p1, nrm, new Vector2(uv0.x, uv1.y), col);
            int d = Vert(p2, nrm, new Vector2(uv1.x, uv1.y), col);
            int e = Vert(p3, nrm, new Vector2(uv1.x, uv0.y), col);
            Quad(sub, a, b, d, e);
        }

        /// <summary>Oriented box with per-face UVs in meters / uvScale. Faces: 0 front(+z),1 back,2 right(+x),3 left,4 top,5 bottom.</summary>
        public void Box(int sub, Vector3 center, Quaternion rot, Vector3 size, float uvScale, Color col, bool top = true, bool bottom = false, int[] faceSubs = null)
        {
            Vector3 h = size * 0.5f;
            Vector3 P(float x, float y, float z) => center + rot * new Vector3(x * h.x, y * h.y, z * h.z);
            int S(int f) => faceSubs != null && faceSubs.Length > f && faceSubs[f] >= 0 ? faceSubs[f] : sub;
            // front +z (seen from +z): bottom-left is +x
            Quad(S(0), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1), P(-1, -1, 1), Vector2.zero, new Vector2(size.x / uvScale, size.y / uvScale), col);
            Quad(S(1), P(-1, -1, -1), P(-1, 1, -1), P(1, 1, -1), P(1, -1, -1), Vector2.zero, new Vector2(size.x / uvScale, size.y / uvScale), col);
            Quad(S(2), P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1), Vector2.zero, new Vector2(size.z / uvScale, size.y / uvScale), col);
            Quad(S(3), P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1), P(-1, -1, -1), Vector2.zero, new Vector2(size.z / uvScale, size.y / uvScale), col);
            if (top) Quad(S(4), P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1), Vector2.zero, new Vector2(size.x / uvScale, size.z / uvScale), col);
            if (bottom) Quad(S(5), P(-1, -1, 1), P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), Vector2.zero, new Vector2(size.x / uvScale, size.z / uvScale), col);
        }

        /// <summary>Tube along a polyline (wires, rails, pipes).</summary>
        public void Tube(int sub, IList<Vector3> path, float radius, int sides, Color col, float uvScale = 1f)
        {
            if (path.Count < 2) return;
            int start = v.Count;
            float dist = 0f;
            Vector3 prevUp = Vector3.up;
            for (int i = 0; i < path.Count; i++)
            {
                Vector3 t = i == 0 ? path[1] - path[0] : i == path.Count - 1 ? path[i] - path[i - 1] : path[i + 1] - path[i - 1];
                t.Normalize();
                if (i > 0) dist += Vector3.Distance(path[i], path[i - 1]);
                Vector3 side = Vector3.Cross(t, Mathf.Abs(Vector3.Dot(t, prevUp)) > 0.95f ? Vector3.right : prevUp).normalized;
                Vector3 up = Vector3.Cross(side, t).normalized;
                prevUp = up;
                for (int s = 0; s <= sides; s++)
                {
                    float a = s / (float)sides * Mathf.PI * 2f;
                    Vector3 dir = side * Mathf.Cos(a) + up * Mathf.Sin(a);
                    Vert(path[i] + dir * radius, dir, new Vector2(s / (float)sides, dist / uvScale), col);
                }
            }
            int ring = sides + 1;
            for (int i = 0; i < path.Count - 1; i++)
                for (int s = 0; s < sides; s++)
                {
                    int a = start + i * ring + s, b = a + 1, d = a + ring + 1, e = a + ring;
                    Quad(sub, a, e, d, b);
                }
        }

        /// <summary>
        /// Sweep a 2D profile (x = lateral offset from the centerline along banked right, y = up) along samples [i0..i1]
        /// of a layout. Hard edges between profile segments. UV.x = profile length / uScale, UV.y = distance / vScale.
        /// </summary>
        public void Sweep(int sub, TrackLayout t, int i0, int count, Vector2[] profile, float uScale, float vScale, Color col, System.Func<int, float> lateralOffset = null, bool flatBank = false)
        {
            if (count < 1 || profile.Length < 2) return;
            int segs = profile.Length - 1;
            float[] ulen = new float[profile.Length];
            for (int k = 1; k < profile.Length; k++) ulen[k] = ulen[k - 1] + Vector2.Distance(profile[k], profile[k - 1]);
            int start = v.Count;
            for (int s = 0; s <= count; s++)
            {
                int i = t.Wrap(i0 + s);
                Vector3 o = t.pts[i];
                Vector3 r = flatBank ? t.right[i] : t.BankedRight(i);
                Vector3 u = flatBank ? Vector3.up : t.BankedUp(i);
                float off = lateralOffset != null ? lateralOffset(i) : 0f;
                float vv = (t.dist[t.Wrap(i0)] + s * t.length / t.Count) / vScale;
                for (int k = 0; k < segs; k++)
                {
                    Vector2 a = profile[k], b = profile[k + 1];
                    Vector2 d = (b - a).normalized;
                    Vector2 pn = new Vector2(-d.y, d.x);   // left normal in profile space
                    Vector3 nrm = (r * pn.x + u * pn.y).normalized;
                    Vert(o + r * (a.x + off) + u * a.y, nrm, new Vector2(ulen[k] / uScale, vv), col);
                    Vert(o + r * (b.x + off) + u * b.y, nrm, new Vector2(ulen[k + 1] / uScale, vv), col);
                }
            }
            int stride = segs * 2;
            for (int s = 0; s < count; s++)
                for (int k = 0; k < segs; k++)
                {
                    int a = start + s * stride + k * 2;
                    int b = a + 1;
                    int a2 = a + stride, b2 = b + stride;
                    // profile goes left->right in x; with the normal on the left of travel this winding faces outward
                    Quad(sub, a, a2, b2, b);
                }
        }

        public Mesh ToMesh(string name, bool recalcNormals = false)
        {
            var m = new Mesh { name = name, indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
            m.SetVertices(v);
            m.SetNormals(n);
            m.SetUVs(0, uv);
            m.SetColors(c);
            int used = 0;
            foreach (var s in subs) if (s.Count > 0) used++;
            m.subMeshCount = subs.Count;
            for (int i = 0; i < subs.Count; i++) m.SetTriangles(subs[i], i, false);
            m.RecalculateBounds();
            if (recalcNormals) m.RecalculateNormals();
            m.RecalculateTangents();
            return m;
        }

        public void Append(MeshBuilder o)
        {
            int baseV = v.Count;
            v.AddRange(o.v); n.AddRange(o.n); uv.AddRange(o.uv); c.AddRange(o.c);
            for (int i = 0; i < o.subs.Count; i++)
                foreach (var idx in o.subs[i]) Sub(i).Add(idx + baseV);
        }
    }
}
