using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Runtime mesh builder for the procedural cockpit: boxes, rounded boxes, tubes, capsules, spheres, tori,
    /// discs, profile extrusions and tube sweeps. Geometry is added in the space given by <see cref="M"/>.
    /// Flat faces get hard normals (the ink outline pass reads them); round parts are smooth.
    /// </summary>
    public class ProcMesh
    {
        readonly List<Vector3> v = new List<Vector3>();
        readonly List<Vector3> n = new List<Vector3>();
        readonly List<Vector2> uv = new List<Vector2>();
        readonly List<int> t = new List<int>();
        public Matrix4x4 M = Matrix4x4.identity;

        public int VertexCount => v.Count;

        int V(Vector3 p, Vector3 nn, Vector2 u)
        {
            v.Add(M.MultiplyPoint3x4(p));
            n.Add(M.MultiplyVector(nn).normalized);
            uv.Add(u);
            return v.Count - 1;
        }

        /// <summary>Triangle whose winding is fixed up so its front faces <paramref name="outward"/>.</summary>
        void Tri(int a, int b, int c, Vector3 outward)
        {
            Vector3 geo = Vector3.Cross(v[b] - v[a], v[c] - v[a]);
            if (Vector3.Dot(geo, M.MultiplyVector(outward)) < 0f) { int s = b; b = c; c = s; }
            t.Add(a); t.Add(b); t.Add(c);
        }

        void TriRaw(int a, int b, int c) { t.Add(a); t.Add(b); t.Add(c); }

        /// <summary>Flat quad p0..p3 (any winding) facing <paramref name="normal"/>.</summary>
        public void Quad(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, Vector3 normal)
        {
            normal = normal.normalized;
            int a = V(p0, normal, new Vector2(0, 0)), b = V(p1, normal, new Vector2(1, 0)), c = V(p2, normal, new Vector2(1, 1)), d = V(p3, normal, new Vector2(0, 1));
            Tri(a, b, c, normal); Tri(a, c, d, normal);
        }

        /// <summary>Quad whose normal comes from its own corners (p0,p1,p2 clockwise seen from the front).</summary>
        public void QuadAuto(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, bool flip = false)
        {
            Vector3 nn = Vector3.Cross(p1 - p0, p3 - p0);
            if (nn.sqrMagnitude < 1e-12f) nn = Vector3.Cross(p2 - p1, p3 - p1);
            Quad(p0, p1, p2, p3, flip ? -nn : nn);
        }

        public void Box(Vector3 c, Vector3 size, Quaternion r)
        {
            Vector3 h = size * 0.5f;
            Vector3 X = r * Vector3.right, Y = r * Vector3.up, Z = r * Vector3.forward;
            Vector3 P(float sx, float sy, float sz) => c + X * (h.x * sx) + Y * (h.y * sy) + Z * (h.z * sz);
            Quad(P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1), X);
            Quad(P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1), -X);
            Quad(P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1), Y);
            Quad(P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1), -Y);
            Quad(P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1), Z);
            Quad(P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1), -Z);
        }

        public void Box(Vector3 c, Vector3 size) => Box(c, size, Quaternion.identity);

        /// <summary>Box spanning two points (a beam), with a cross-section of w x h; <paramref name="up"/> orients h.</summary>
        public void Beam(Vector3 a, Vector3 b, float w, float h, Vector3 up)
        {
            Vector3 d = b - a;
            Box((a + b) * 0.5f, new Vector3(w, h, d.magnitude), Quaternion.LookRotation(d, up));
        }

        /// <summary>Superellipsoid "rounded box": e≈0.15 boxy with soft edges, 1 = ellipsoid.</summary>
        public void RoundBox(Vector3 c, Vector3 size, Quaternion r, float e = 0.2f, int seg = 10)
        {
            Vector3 h = size * 0.5f;
            int baseIdx = v.Count;
            for (int i = 0; i <= seg; i++)
            {
                float th = -Mathf.PI / 2 + Mathf.PI * i / seg;
                for (int j = 0; j <= seg * 2; j++)
                {
                    float ph = -Mathf.PI + 2f * Mathf.PI * j / (seg * 2);
                    float ct = SPow(Mathf.Cos(th), e), st = SPow(Mathf.Sin(th), e);
                    float cp = SPow(Mathf.Cos(ph), e), sp = SPow(Mathf.Sin(ph), e);
                    var p = new Vector3(h.x * ct * cp, h.y * st, h.z * ct * sp);
                    // normal of the superellipsoid: gradient of |x/a|^(2/e) + ...
                    float k = 2f - e;
                    var nn = new Vector3(SPow(Mathf.Cos(th), k) * SPow(Mathf.Cos(ph), k) / h.x, SPow(Mathf.Sin(th), k) / h.y, SPow(Mathf.Cos(th), k) * SPow(Mathf.Sin(ph), k) / h.z);
                    if (nn.sqrMagnitude < 1e-10f) nn = p;
                    V(c + r * p, r * nn, new Vector2((float)j / (seg * 2), (float)i / seg));
                }
            }
            int row = seg * 2 + 1;
            for (int i = 0; i < seg; i++)
                for (int j = 0; j < seg * 2; j++)
                {
                    int a = baseIdx + i * row + j, b = a + 1, cc = a + row, d = cc + 1;
                    Vector3 mid = (v[a] + v[d]) * 0.5f - M.MultiplyPoint3x4(c);
                    Tri(a, cc, d, M.inverse.MultiplyVector(mid)); Tri(a, d, b, M.inverse.MultiplyVector(mid));
                }
        }

        static float SPow(float x, float p) => Mathf.Sign(x) * Mathf.Pow(Mathf.Abs(x), p);

        /// <summary>Tapered tube from a (radius ra) to b (radius rb); caps optional.</summary>
        public void Tube(Vector3 a, Vector3 b, float ra, float rb, int seg = 12, bool capA = true, bool capB = true, float uvLen = 1f)
        {
            Vector3 d = b - a;
            if (d.sqrMagnitude < 1e-10f) return;
            Quaternion q = Quaternion.LookRotation(d, Mathf.Abs(Vector3.Dot(d.normalized, Vector3.up)) > 0.95f ? Vector3.forward : Vector3.up);
            Vector3 X = q * Vector3.right, Y = q * Vector3.up, Z = d.normalized;
            float slope = (ra - rb) / d.magnitude;
            int i0 = v.Count;
            for (int i = 0; i <= seg; i++)
            {
                float ang = 2f * Mathf.PI * i / seg;
                Vector3 radial = X * Mathf.Cos(ang) + Y * Mathf.Sin(ang);
                Vector3 nn = (radial + Z * slope).normalized;
                V(a + radial * ra, nn, new Vector2((float)i / seg, 0));
                V(b + radial * rb, nn, new Vector2((float)i / seg, uvLen));
            }
            for (int i = 0; i < seg; i++)
            {
                int p0 = i0 + i * 2, p1 = p0 + 1, p2 = p0 + 2, p3 = p0 + 3;
                Vector3 outw = (v[p0] + v[p3]) * 0.5f - (M.MultiplyPoint3x4(a) + M.MultiplyPoint3x4(b)) * 0.5f;
                Vector3 o = M.inverse.MultiplyVector(outw);
                Tri(p0, p1, p3, o); Tri(p0, p3, p2, o);
            }
            if (capA) Disc(a, -Z, ra, seg);
            if (capB) Disc(b, Z, rb, seg);
        }

        public void Capsule(Vector3 a, Vector3 b, float r, int seg = 10)
        {
            Tube(a, b, r, r, seg, false, false);
            Sphere(a, r, seg);
            Sphere(b, r, seg);
        }

        public void Sphere(Vector3 c, float r, int seg = 12) => Ellipsoid(c, new Vector3(r, r, r), Quaternion.identity, seg);

        public void Ellipsoid(Vector3 c, Vector3 radii, Quaternion rot, int seg = 12)
        {
            int i0 = v.Count, rows = seg / 2 + 1;
            for (int i = 0; i <= rows; i++)
            {
                float th = Mathf.PI * i / rows;
                for (int j = 0; j <= seg; j++)
                {
                    float ph = 2f * Mathf.PI * j / seg;
                    Vector3 unit = new Vector3(Mathf.Sin(th) * Mathf.Cos(ph), Mathf.Cos(th), Mathf.Sin(th) * Mathf.Sin(ph));
                    Vector3 p = Vector3.Scale(unit, radii);
                    Vector3 nn = new Vector3(unit.x / radii.x, unit.y / radii.y, unit.z / radii.z);
                    V(c + rot * p, rot * nn, new Vector2((float)j / seg, (float)i / rows));
                }
            }
            for (int i = 0; i < rows; i++)
                for (int j = 0; j < seg; j++)
                {
                    int a = i0 + i * (seg + 1) + j, b = a + 1, cc = a + seg + 1, d = cc + 1;
                    Vector3 o = M.inverse.MultiplyVector((v[a] + v[d]) * 0.5f - M.MultiplyPoint3x4(c));
                    Tri(a, b, d, o); Tri(a, d, cc, o);
                }
        }

        /// <summary>Flat disc (UV mapped 0..1 across its diameter, u along <paramref name="uAxis"/>).</summary>
        public void Disc(Vector3 c, Vector3 normal, float r, int seg = 24, Vector3? uAxis = null)
        {
            normal = normal.normalized;
            Vector3 U = uAxis ?? Vector3.Cross(normal, Mathf.Abs(normal.y) > 0.9f ? Vector3.forward : Vector3.up).normalized;
            U = Vector3.ProjectOnPlane(U, normal).normalized;
            Vector3 W = Vector3.Cross(U, normal).normalized;   // v runs 'up' for a viewer facing the disc (textures read correctly)
            int ci = V(c, normal, new Vector2(0.5f, 0.5f));
            int i0 = v.Count;
            for (int i = 0; i <= seg; i++)
            {
                float a = 2f * Mathf.PI * i / seg;
                float cu = Mathf.Cos(a), su = Mathf.Sin(a);
                V(c + (U * cu + W * su) * r, normal, new Vector2(0.5f + 0.5f * cu, 0.5f + 0.5f * su));
            }
            for (int i = 0; i < seg; i++) Tri(ci, i0 + i, i0 + i + 1, normal);
        }

        /// <summary>Torus around <paramref name="axis"/> through c; arc in degrees measured from <paramref name="zeroDir"/>.</summary>
        public void Torus(Vector3 c, Vector3 axis, Vector3 zeroDir, float R, float r, float arc0 = 0f, float arc1 = 360f, int segU = 48, int segV = 12)
        {
            axis = axis.normalized;
            Vector3 X = Vector3.ProjectOnPlane(zeroDir, axis).normalized, Y = Vector3.Cross(axis, X);
            int i0 = v.Count;
            for (int i = 0; i <= segU; i++)
            {
                float a = Mathf.Deg2Rad * Mathf.Lerp(arc0, arc1, (float)i / segU);
                Vector3 radial = X * Mathf.Cos(a) + Y * Mathf.Sin(a);
                Vector3 ring = c + radial * R;
                for (int j = 0; j <= segV; j++)
                {
                    float b = 2f * Mathf.PI * j / segV;
                    Vector3 nn = radial * Mathf.Cos(b) + axis * Mathf.Sin(b);
                    V(ring + nn * r, nn, new Vector2((float)i / segU, (float)j / segV));
                }
            }
            for (int i = 0; i < segU; i++)
                for (int j = 0; j < segV; j++)
                {
                    int a = i0 + i * (segV + 1) + j, b = a + 1, cc = a + segV + 1, d = cc + 1;
                    Vector3 o = n[a] + n[d];
                    Tri(a, b, d, M.inverse.MultiplyVector(o)); Tri(a, d, cc, M.inverse.MultiplyVector(o));
                }
        }

        /// <summary>Extrudes a closed (z, y) profile along x from x0 to x1 (flat shaded, optional end caps for convex profiles).</summary>
        public void ExtrudeX(IList<Vector2> zy, float x0, float x1, bool caps = false)
        {
            int count = zy.Count;
            Vector2 centroid = Vector2.zero;
            foreach (var p in zy) centroid += p;
            centroid /= count;
            for (int i = 0; i < count; i++)
            {
                Vector2 p = zy[i], q = zy[(i + 1) % count];
                Vector2 edge = q - p;
                Vector2 nrm = new Vector2(edge.y, -edge.x);   // outward if the profile is clockwise in (z, y)
                Vector2 mid = (p + q) * 0.5f;
                if (Vector2.Dot(nrm, mid - centroid) < 0f) nrm = -nrm;
                Vector3 N = new Vector3(0f, nrm.y, nrm.x);
                Quad(new Vector3(x0, p.y, p.x), new Vector3(x1, p.y, p.x), new Vector3(x1, q.y, q.x), new Vector3(x0, q.y, q.x), N);
            }
            if (!caps) return;
            foreach (float x in new[] { x0, x1 })
            {
                Vector3 N = x == x0 ? Vector3.left : Vector3.right;
                int ci = V(new Vector3(x, centroid.y, centroid.x), N, Vector2.zero);
                int i0 = v.Count;
                for (int i = 0; i < count; i++) V(new Vector3(x, zy[i].y, zy[i].x), N, Vector2.zero);
                for (int i = 0; i < count; i++) Tri(ci, i0 + i, i0 + (i + 1) % count, N);
            }
        }

        /// <summary>Round tube swept through points with sphere joints (roll cage, harness edges).</summary>
        public void Sweep(IList<Vector3> pts, float r, int seg = 10)
        {
            for (int i = 0; i + 1 < pts.Count; i++)
            {
                Tube(pts[i], pts[i + 1], r, r, seg, false, false);
                if (i > 0) Sphere(pts[i], r, seg);
            }
        }

        /// <summary>Grid surface f(u,v) with smooth normals (headliner, seat backs), facing <paramref name="towards"/> roughly.</summary>
        public void Surface(System.Func<float, float, Vector3> f, int nu, int nv, Vector3 towards)
        {
            int i0 = v.Count;
            for (int j = 0; j <= nv; j++)
                for (int i = 0; i <= nu; i++)
                {
                    float uu = (float)i / nu, vv = (float)j / nv;
                    Vector3 p = f(uu, vv);
                    Vector3 du = f(Mathf.Min(1f, uu + 0.01f), vv) - f(Mathf.Max(0f, uu - 0.01f), vv);
                    Vector3 dv = f(uu, Mathf.Min(1f, vv + 0.01f)) - f(uu, Mathf.Max(0f, vv - 0.01f));
                    Vector3 nn = Vector3.Cross(du, dv).normalized;
                    if (Vector3.Dot(nn, towards) < 0f) nn = -nn;
                    V(p, nn, new Vector2(uu, vv));
                }
            for (int j = 0; j < nv; j++)
                for (int i = 0; i < nu; i++)
                {
                    int a = i0 + j * (nu + 1) + i, b = a + 1, c = a + nu + 1, d = c + 1;
                    Vector3 o = M.inverse.MultiplyVector(n[a] + n[d]);
                    Tri(a, b, d, o); Tri(a, d, c, o);
                }
        }

        /// <summary>Appends another builder's geometry (already in this space).</summary>
        public void Append(ProcMesh o)
        {
            int off = v.Count;
            v.AddRange(o.v); n.AddRange(o.n); uv.AddRange(o.uv);
            foreach (int i in o.t) t.Add(i + off);
        }

        /// <summary>Mirrors the geometry across x = 0 (left hand from the right hand).</summary>
        public ProcMesh MirroredX()
        {
            var m = new ProcMesh();
            for (int i = 0; i < v.Count; i++)
            {
                m.v.Add(new Vector3(-v[i].x, v[i].y, v[i].z));
                m.n.Add(new Vector3(-n[i].x, n[i].y, n[i].z));
                m.uv.Add(uv[i]);
            }
            for (int i = 0; i < t.Count; i += 3) { m.t.Add(t[i]); m.t.Add(t[i + 2]); m.t.Add(t[i + 1]); }
            return m;
        }

        public Mesh ToMesh(string name)
        {
            var mesh = new Mesh { name = name };
            if (v.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(v);
            mesh.SetNormals(n);
            mesh.SetUVs(0, uv);
            mesh.SetTriangles(t, 0);
            var colors = new Color[v.Count];
            for (int i = 0; i < colors.Length; i++) colors[i] = new Color(1f, 0f, 0.5f, 1f);   // toon shader: R AO = 1, G wind = 0, B hue variation neutral
            mesh.colors = colors;
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
