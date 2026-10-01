using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>SHIBUYA NEON: wet neon city circuit with intersections, side streets, a sakura canal and dense blocks.</summary>
    public static class CityBuilder
    {
        class Stub { public Vector3 mouth, dir; public float length, hw; }

        public static void Build(PropKit kit, TrackLayout t, TrackDef def, Transform root)
        {
            bool night = def.look.night;
            float hw = def.roadHalfWidth, sw = def.sidewalk;
            neon = new List<Vector3>();
            chunks.Clear();
            var gRoad = PropKit.Group("Road", root);
            var gCity = PropKit.Group("City", root);
            var gProps = PropKit.Group("Props", root);
            var gLights = PropKit.Group("Lights", root);
            var gCol = PropKit.Group("Colliders", root);

            // ------------------------------------------------ materials
            var road = MaterialLibrary.FromSet("road_asphalt_worn", "Toon_Road_Wet", 5f, 0.45f);
            MaterialLibrary.SetKeyword(road, "_WET", "_Wet", def.wet);
            road.SetFloat("_WetAmount", 0.8f); road.SetFloat("_MaskHeightPuddles", 0.7f); road.SetFloat("_HalftoneAmount", 0.6f);
            road.SetTextureScale("_BaseMap", Vector2.one);
            road.SetColor("_BaseColor", new Color(1.35f, 1.35f, 1.45f));
            var curb = MaterialLibrary.FromSet("sidewalk_curb_granite", "Toon_Curb", 1f, 0.35f);
            curb.SetTextureScale("_BaseMap", Vector2.one);
            var walk = MaterialLibrary.FromSet("sidewalk_pavers_interlock", "Toon_Sidewalk_Wet", 1f, 0.4f);
            walk.SetTextureScale("_BaseMap", Vector2.one);
            MaterialLibrary.SetKeyword(walk, "_WET", "_Wet", def.wet); walk.SetFloat("_WetAmount", 0.45f); walk.SetFloat("_MaskHeightPuddles", 0.5f);
            var white = MaterialLibrary.Flat("Toon_PaintWhite", new Color(0.92f, 0.92f, 0.88f), 0.45f);
            var yellow = MaterialLibrary.Flat("Toon_PaintYellow", new Color(1f, 0.78f, 0.1f), 0.45f);
            var concreteWall = MaterialLibrary.FromSet("concrete_formwork", "Toon_CanalWall", 1f, 0.25f);
            concreteWall.SetTextureScale("_BaseMap", Vector2.one);
            var ground = MaterialLibrary.FromSet("road_asphalt_fresh", "Toon_Ground", 1f, 0.3f);
            MaterialLibrary.SetKeyword(ground, "_WORLD_UV", "_WorldUV", true); ground.SetFloat("_WorldUVScale", 0.2f);
            var water = AssetDatabase.LoadAssetAtPath<Material>(MaterialLibrary.Dir + "/Water_Canal.mat") ?? MaterialLibrary.Ensure("Water_Canal", Shader.Find("InkDrift/Water"));
            water.SetColor("_ShallowColor", new Color(0.12f, 0.35f, 0.42f)); water.SetColor("_DeepColor", new Color(0.03f, 0.06f, 0.14f));
            var wetPhys = new PhysicsMaterial("Wet") { dynamicFriction = 0.6f, staticFriction = 0.6f };
            kit.SaveObject(wetPhys, "Wet");

            // ------------------------------------------------ special ranges
            var corners = new List<int>();
            for (int s = 0; s < t.segments.Count; s++)
                if (t.segments[s].kind != 'S' && t.segments[s].a >= 80f && t.segments[s].r <= 25f) corners.Add(s);
            int canalSeg = 10;
            float canalA = t.segStart[canalSeg] + 6f, canalB = t.segEnd[canalSeg] - 6f;
            bool InCanal(float d) => d > canalA && d < canalB;
            bool InCorner(float d, float pad)
            {
                foreach (var s in corners) if (d > t.segStart[s] - pad && d < t.segEnd[s] + pad) return true;
                return false;
            }

            // ------------------------------------------------ road, curbs, sidewalks (chunks of 60 samples)
            int chunk = 60;
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var mb = new MeshBuilder();
                var crown = new[] { new Vector2(-hw - 0.05f, -0.02f), new Vector2(-hw * 0.5f, 0.04f), new Vector2(0, 0.07f), new Vector2(hw * 0.5f, 0.04f), new Vector2(hw + 0.05f, -0.02f) };
                mb.Sweep(0, t, i0, cnt, crown, 5f, 5f, Color.white);
                kit.MeshObject($"Road_{i0}", gRoad, mb, new[] { road }, true, false, 9, wetPhys);

                var cb = new MeshBuilder();
                // right curb + sidewalk
                cb.Sweep(0, t, i0, cnt, new[] { new Vector2(hw, -0.05f), new Vector2(hw, 0.15f), new Vector2(hw + 0.3f, 0.15f) }, 1f, 1f, Color.white);
                cb.Sweep(1, t, i0, cnt, new[] { new Vector2(hw + 0.3f, 0.15f), new Vector2(hw + sw, 0.15f) }, 1f, 1f, Color.white);
                // left: canal range gets a narrow walk
                cb.Sweep(0, t, i0, cnt, new[] { new Vector2(-hw - 0.3f, 0.15f), new Vector2(-hw, 0.15f), new Vector2(-hw, -0.05f) }, 1f, 1f, Color.white);
                float leftWalk = sw;
                bool canalChunk = InCanal(t.dist[i0]) || InCanal(t.dist[t.Wrap(i0 + cnt)]);
                cb.Sweep(1, t, i0, cnt, new[] { new Vector2(-hw - leftWalk, 0.15f), new Vector2(-hw - 0.3f, 0.15f) }, 1f, 1f, Color.white,
                    i => InCanal(t.dist[i]) ? 0f : 0f);
                kit.MeshObject($"Curb_{i0}", gRoad, cb, new[] { curb, walk }, true, false);
            }

            // ------------------------------------------------ lane markings
            var mk = new MeshBuilder();
            void Strip(int sub, float x, float w, float d0, float d1)
            {
                int a = t.IndexAt(d0), b = t.IndexAt(d1);
                int n = t.Wrap(b - a); if (n < 1) return;
                mk.Sweep(sub, t, a, n, new[] { new Vector2(x - w / 2, 0.075f), new Vector2(x + w / 2, 0.075f) }, 1f, 1f, Color.white);
            }
            for (float d = 0; d < t.length; d += 6f)
            {
                if (InCorner(d, 14f)) continue;
                float e = Mathf.Min(d + 6f, t.length - 0.1f);
                Strip(0, hw - 0.35f, 0.15f, d, e);
                Strip(0, -hw + 0.35f, 0.15f, d, e);
                Strip(1, -0.13f, 0.12f, d, e);
                Strip(1, 0.13f, 0.12f, d, e);
            }
            for (float d = 0; d < t.length; d += 12f)
            {
                if (InCorner(d, 14f)) continue;
                Strip(0, hw * 0.5f, 0.12f, d, d + 5f);
                Strip(0, -hw * 0.5f, 0.12f, d, d + 5f);
            }
            // crosswalks before/after each corner
            foreach (var s in corners)
            {
                foreach (float dc in new[] { t.segStart[s] - 9f, t.segEnd[s] + 9f })
                {
                    int i = t.IndexAt(dc);
                    for (float x = -hw + 0.6f; x < hw - 0.4f; x += 0.9f)
                    {
                        Vector3 c = t.pts[i] + t.right[i] * (x + 0.225f) + Vector3.up * 0.08f;
                        Vector3 f = t.tan[i] * 2f, r = t.right[i] * 0.225f;
                        mk.Quad(0, c - r - f, c - r + f, c + r + f, c + r - f, Vector2.zero, Vector2.one, Color.white);
                    }
                }
            }
            kit.MeshObject("Markings", gRoad, mk, new[] { white, yellow }, false, false);

            // painted road text/arrows (Japan drives on the left: forward lanes are on the left of the centerline)
            {
                var dm = new MeshBuilder();
                string[] decals = { "road_speed_40_white", "road_arrow_straight", "road_arrow_straight_left", "road_diamond_crosswalk_ahead", "road_tomare", "road_arrow_left" };
                var dmats = new Material[decals.Length];
                for (int k = 0; k < decals.Length; k++)
                {
                    var dmat = MaterialLibrary.Ensure("Toon_Decal_" + decals[k]);
                    var tex = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/InkDrift/Art/Decals/{decals[k]}.png");
                    if (tex) dmat.SetTexture("_BaseMap", tex);
                    dmat.SetColor("_BaseColor", new Color(0.92f, 0.92f, 0.88f));
                    dmat.EnableKeyword("_ALPHATEST_ON"); dmat.SetFloat("_AlphaClip", 1); dmat.SetFloat("_Cutoff", 0.35f);
                    dmat.SetFloat("_Smoothness", 0.5f); dmat.SetFloat("_HalftoneAmount", 0.4f);
                    dmats[k] = dmat;
                }
                void Decal(int sub, Vector3 c, Vector3 fwd, float w, float len)
                {
                    fwd.y = 0; fwd.Normalize();
                    Vector3 rgt = Vector3.Cross(Vector3.up, fwd);
                    c += Vector3.up * 0.082f;
                    Vector3 hx = rgt * w * 0.5f, hz = fwd * len * 0.5f;
                    dm.Quad(sub, c - hx - hz, c - hx + hz, c + hx + hz, c + hx - hz, Vector2.zero, Vector2.one, Color.white);
                }
                float lane = hw * 0.5f;
                for (float d = 30f; d < t.length; d += 130f)
                {
                    if (InCorner(d, 30f)) continue;
                    int i = t.IndexAt(d);
                    foreach (float off in new[] { -lane * 0.5f, -lane * 1.5f }) Decal(0, t.pts[i] + t.right[i] * off, t.tan[i], 1.4f, 4.6f);
                    foreach (float off in new[] { lane * 0.5f, lane * 1.5f }) Decal(0, t.pts[t.IndexAt(d + 20f)] + t.right[t.IndexAt(d + 20f)] * off, -t.tan[t.IndexAt(d + 20f)], 1.4f, 4.6f);
                }
                foreach (var s in corners)
                {
                    bool leftTurn = t.segments[s].kind == 'L';
                    int ia = t.IndexAt(t.segStart[s] - 24f), ib = t.IndexAt(t.segStart[s] - 48f);
                    Decal(leftTurn ? 5 : 1, t.pts[ia] + t.right[ia] * -lane * 0.5f, t.tan[ia], 1.3f, 5f);
                    Decal(2, t.pts[ia] + t.right[ia] * -lane * 1.5f, t.tan[ia], 1.3f, 5f);
                    Decal(3, t.pts[ib] + t.right[ib] * -lane * 0.5f, t.tan[ib], 1.6f, 3.2f);
                    Decal(3, t.pts[ib] + t.right[ib] * -lane * 1.5f, t.tan[ib], 1.6f, 3.2f);
                }
                kit.MeshObject("RoadText", gRoad, dm, dmats, false, false);
            }

            // ------------------------------------------------ track-distance acceleration
            var grid = new Dictionary<Vector2Int, List<int>>();
            for (int i = 0; i < t.Count; i++)
            {
                var k = new Vector2Int(Mathf.FloorToInt(t.pts[i].x / 20f), Mathf.FloorToInt(t.pts[i].z / 20f));
                if (!grid.TryGetValue(k, out var l)) grid[k] = l = new List<int>();
                l.Add(i);
            }
            float TrackDist(Vector3 p)
            {
                var k = new Vector2Int(Mathf.FloorToInt(p.x / 20f), Mathf.FloorToInt(p.z / 20f));
                float best = 1e9f;
                for (int x = -3; x <= 3; x++)
                    for (int y = -3; y <= 3; y++)
                        if (grid.TryGetValue(new Vector2Int(k.x + x, k.y + y), out var l))
                            foreach (var i in l) { float d = new Vector2(p.x - t.pts[i].x, p.z - t.pts[i].z).magnitude; if (d < best) best = d; }
                return best;
            }

            var bk = new BuildingKit(night);
            foreach (var m in bk.facades) { m.SetFloat("_VertexTint", 1f); }
            bk.shop.SetFloat("_VertexTint", 1f);

            // ------------------------------------------------ intersections + side-street stubs
            var stubs = new List<Stub>();
            var patch = new MeshBuilder();
            foreach (var s in corners)
            {
                int ia = t.IndexAt(t.segStart[s]), ib = t.IndexAt(t.segEnd[s]);
                Vector3 A = t.pts[ia], B = t.pts[ib];
                Vector3 dIn = t.tan[t.Wrap(ia - 2)], dOut = t.tan[t.Wrap(ib + 2)];
                dIn.y = 0; dOut.y = 0; dIn.Normalize(); dOut.Normalize();
                // intersection of the straights' lines
                Vector2 a2 = new Vector2(A.x, A.z), b2 = new Vector2(B.x, B.z), u = new Vector2(dIn.x, dIn.z), v = new Vector2(dOut.x, dOut.z);
                float den = u.x * v.y - u.y * v.x;
                if (Mathf.Abs(den) < 1e-3f) continue;
                Vector2 ba = b2 - a2;
                float sParam = (ba.x * v.y - ba.y * v.x) / den;
                Vector3 X = new Vector3(a2.x + u.x * sParam, 0f, a2.y + u.y * sParam);
                // intersection square
                var q = Quaternion.LookRotation(dIn);
                float half = hw + 0.3f;
                Vector3 r = q * Vector3.right * half, f = q * Vector3.forward * half;
                patch.Quad(0, X - r - f + Vector3.up * 0.02f, X - r + f + Vector3.up * 0.02f, X + r + f + Vector3.up * 0.02f, X + r - f + Vector3.up * 0.02f, new Vector2(X.x, X.z) / 5f, new Vector2(X.x, X.z) / 5f + Vector2.one * (half * 2 / 5f), Color.white);
                bk.ReserveKeepOut(X, q, half * 2 + sw * 2 + 2f, half * 2 + sw * 2 + 2f);
                foreach (var (mouthDir, label) in new[] { (dIn, "in"), (-dOut, "out") })
                {
                    var st = new Stub { mouth = X + mouthDir * half, dir = mouthDir, hw = hw * 0.85f };
                    float len = 0f;
                    for (float l = 8f; l <= 70f; l += 4f)
                    {
                        if (TrackDist(st.mouth + mouthDir * l) < hw + sw + st.hw + 6f) break;
                        len = l;
                    }
                    if (len < 24f) continue;
                    st.length = len;
                    stubs.Add(st);
                }
            }
            kit.MeshObject("IntersectionPatches", gRoad, patch, new[] { road }, true, false, 9, wetPhys);

            foreach (var st in stubs)
            {
                var mb = new MeshBuilder();
                var q = Quaternion.LookRotation(st.dir);
                Vector3 r = q * Vector3.right;
                Vector3 m0 = st.mouth, m1 = st.mouth + st.dir * st.length;
                // road
                mb.Quad(0, m0 - r * st.hw, m1 - r * st.hw, m1 + r * st.hw, m0 + r * st.hw, new Vector2(0, 0), new Vector2(st.hw * 2 / 5f, st.length / 5f), Color.white);
                // sidewalks + curbs
                foreach (int side in new[] { -1, 1 })
                {
                    Vector3 e0 = m0 + r * side * st.hw, e1 = m1 + r * side * st.hw;
                    Vector3 o0 = m0 + r * side * (st.hw + sw), o1 = m1 + r * side * (st.hw + sw);
                    Vector3 up = Vector3.up * 0.15f;
                    if (side > 0) mb.Quad(1, e0 + up, e1 + up, o1 + up, o0 + up, Vector2.zero, new Vector2(sw, st.length), Color.white);
                    else mb.Quad(1, o0 + up, o1 + up, e1 + up, e0 + up, Vector2.zero, new Vector2(sw, st.length), Color.white);
                }
                kit.MeshObject("SideStreet", gRoad, mb, new[] { road, walk }, false, false);
                // markings on the stub: 止まれ-style stop line near the mouth
                var stop = new MeshBuilder();
                Vector3 sl = m0 + st.dir * 3f + Vector3.up * 0.03f;
                stop.Quad(0, sl - r * st.hw, sl - r * st.hw + st.dir * 0.45f, sl + r * st.hw + st.dir * 0.45f, sl + r * st.hw, Vector2.zero, Vector2.one, Color.white);
                {
                    // 止まれ painted in the lane heading toward the main road (reads for drivers exiting the side street)
                    Vector3 fwd = -st.dir, rgt = Vector3.Cross(Vector3.up, fwd);
                    Vector3 c = m0 + st.dir * 6.5f - rgt * (st.hw * 0.5f) + Vector3.up * 0.04f;
                    Vector3 hx = rgt * 1.2f, hz = fwd * 1.8f;
                    stop.Quad(1, c - hx - hz, c - hx + hz, c + hx + hz, c + hx - hz, Vector2.zero, Vector2.one, Color.white);
                }
                kit.MeshObject("StopLine", gRoad, stop, new[] { white, MaterialLibrary.Get("Toon_Decal_road_tomare") ?? white }, false, false);
                bk.ReserveKeepOut(st.mouth + st.dir * st.length * 0.5f, q, (st.hw + sw) * 2f, st.length + 6f);
                // dead-end building + barricade
                if (bk.TryReserve(m1 + st.dir * 12f, q, (st.hw + sw) * 2f + 6f, 20f, out var endLot))
                {
                    var bmb = new MeshBuilder();
                    bk.AddBuilding(bmb, kit, endLot, kit.R(18, 40), kit.RI(0, bk.facades.Count), true, true, Tint(kit), null, 0f);
                    kit.MeshObject("DeadEnd", gCity, bmb, bk.Materials, false);
                }
                // stub-side frontage buildings
                foreach (int side in new[] { -1, 1 })
                    for (float l = 2f; l < st.length - 4f;)
                    {
                        float w = kit.R(8f, 16f), dep = kit.R(14f, 22f);
                        Vector3 front = m0 + st.dir * (l + w / 2) + r * side * (st.hw + sw + 0.2f);
                        Vector3 outward = r * side;
                        if (bk.TryReserve(front + outward * dep / 2, Quaternion.LookRotation(outward), w, dep, out var lot) && TrackDist(front) > hw + sw + 1f)
                        {
                            var bmb = Chunk(lot.center);
                            bk.AddBuilding(bmb, kit, lot, kit.R(12f, 34f), kit.RI(0, bk.facades.Count), true, true, Tint(kit), neon, 0f);
                        }
                        l += w + kit.R(0f, 1.5f);
                    }
            }

            // ------------------------------------------------ canal
            {
                int ia = t.IndexAt(canalA), ib = t.IndexAt(canalB);
                int n = t.Wrap(ib - ia);
                float nearX = hw + 2.6f, farX = hw + 16.5f, promX = hw + 21f, bedY = -3.6f;
                var cm = new MeshBuilder();
                cm.Sweep(0, t, ia, n, new[] { new Vector2(-farX, 0.15f), new Vector2(-farX, bedY) }, 2f, 2f, Color.white, null, true);
                cm.Sweep(0, t, ia, n, new[] { new Vector2(-nearX, bedY), new Vector2(-nearX, 0.15f) }, 2f, 2f, Color.white, null, true);
                cm.Sweep(0, t, ia, n, new[] { new Vector2(-farX, bedY), new Vector2(-nearX, bedY) }, 2f, 2f, Color.white, null, true);
                cm.Sweep(1, t, ia, n, new[] { new Vector2(-promX, 0.15f), new Vector2(-farX, 0.15f) }, 1f, 1f, Color.white, null, true);
                // end caps
                foreach (int idx in new[] { ia, ib })
                {
                    Vector3 o = t.pts[idx]; Vector3 rr = t.right[idx];
                    Vector3 p0 = o - rr * farX + Vector3.up * bedY, p1 = o - rr * farX + Vector3.up * 0.15f, p2 = o - rr * nearX + Vector3.up * 0.15f, p3 = o - rr * nearX + Vector3.up * bedY;
                    if (idx == ia) cm.Quad(0, p3, p2, p1, p0, Vector2.zero, new Vector2(7, 2), Color.white);
                    else cm.Quad(0, p0, p1, p2, p3, Vector2.zero, new Vector2(7, 2), Color.white);
                }
                kit.MeshObject("Canal", gRoad, cm, new[] { concreteWall, walk }, true, true);
                var wm = new MeshBuilder();
                wm.Sweep(0, t, ia, n, new[] { new Vector2(-farX, -2.9f), new Vector2(-nearX, -2.9f) }, 4f, 4f, Color.white, null, true);
                kit.MeshObject("CanalWater", gRoad, wm, new[] { water }, false, false);
                Vector3 cc = (t.pts[ia] + t.pts[ib]) * 0.5f - t.right[t.IndexAt((canalA + canalB) / 2)] * (nearX + farX) * 0.5f;
                bk.ReserveKeepOut(cc, Quaternion.LookRotation(t.tan[t.IndexAt((canalA + canalB) / 2)]), (promX - nearX) + 4f, Vector3.Distance(t.pts[ia], t.pts[ib]) + 4f);

                // sakura over both banks, lanterns along the railing
                var sakura = kit.FindPrefabs("sakura");
                var lantern = kit.FindPrefab("chochin_string_4m", "chochin");
                var railing = kit.FindPrefab("pedestrian_railing_2m_pipe_white", "pedestrian_railing");
                for (float d = canalA + 3f; d < canalB - 3f; d += 7.5f)
                {
                    int i = t.IndexAt(d);
                    Vector3 o = t.pts[i]; Vector3 rr = t.right[i]; Quaternion face = Quaternion.LookRotation(rr);
                    if (sakura.Count > 0)
                    {
                        kit.Place(kit.Pick(sakura), o - rr * (hw + 1.6f) + Vector3.up * 0.15f, Quaternion.Euler(kit.R(-3, 3), kit.R(0, 360), 0) , gProps, kit.R(0.85f, 1.1f));
                        kit.Place(kit.Pick(sakura), o - rr * (farX + 2.2f) + Vector3.up * 0.15f, Quaternion.Euler(0, kit.R(0, 360), 0), gProps, kit.R(0.9f, 1.15f));
                    }
                    if (railing) for (int rk = 0; rk < 4; rk++) { int ip = t.IndexAt(d + 2f + rk * 2f); kit.Place(railing, t.pts[ip] - t.right[ip] * (nearX - 0.25f) + Vector3.up * 0.15f, Quaternion.LookRotation(t.right[ip]), gProps); }
                }
                if (lantern)
                    for (float d = canalA + 2f; d < canalB - 6f; d += 6f)
                    {
                        int i = t.IndexAt(d); Vector3 o = t.pts[i]; Vector3 rr = t.right[i];
                        kit.Place(lantern, o - rr * (nearX - 0.6f) + Vector3.up * 3.2f, Quaternion.LookRotation(t.tan[i]), gProps);
                    }
                else
                {
                    // procedural lantern string: red emissive paper lanterns on a catenary
                    var lm = new MeshBuilder();
                    var red = MaterialLibrary.Flat("Toon_Chochin", new Color(0.9f, 0.15f, 0.1f), 0.2f, 0f, new Color(2.4f, 0.5f, 0.2f) * (night ? 1f : 0.1f));
                    var cable = MaterialLibrary.Flat("Toon_Cable", new Color(0.05f, 0.05f, 0.06f), 0.2f);
                    for (float d = canalA + 2f; d < canalB - 8f; d += 8f)
                    {
                        int i0 = t.IndexAt(d), i1 = t.IndexAt(d + 8f);
                        Vector3 a = t.pts[i0] - t.right[i0] * (nearX - 0.5f) + Vector3.up * 3.6f;
                        Vector3 b = t.pts[i1] - t.right[i1] * (nearX - 0.5f) + Vector3.up * 3.6f;
                        var pts = new List<Vector3>();
                        for (int k = 0; k <= 10; k++) { float u2 = k / 10f; pts.Add(Vector3.Lerp(a, b, u2) - Vector3.up * 0.5f * 4f * u2 * (1 - u2)); }
                        lm.Tube(1, pts, 0.012f, 4, Color.white);
                        for (int k = 1; k < 8; k++)
                        {
                            float u2 = k / 8f;
                            Vector3 p = Vector3.Lerp(a, b, u2) - Vector3.up * (0.5f * 4f * u2 * (1 - u2) + 0.3f);
                            lm.Box(0, p, Quaternion.LookRotation(t.tan[i0]), new Vector3(0.28f, 0.42f, 0.28f), 1f, Color.white);
                        }
                    }
                    kit.MeshObject("Lanterns", gProps, lm, new[] { red, cable }, false, false);
                }
            }

            // ------------------------------------------------ buildings: frontage rows, second rows, infill grid
            for (int side = -1; side <= 1; side += 2)
                for (int row = 0; row < 2; row++)
                {
                    float d = kit.R(0, 6);
                    while (d < t.length)
                    {
                        float w = kit.R(7f, 18f), dep = kit.R(12f, 22f);
                        int i = t.IndexAt(d + w / 2);
                        bool canalHere = side < 0 && InCanal(d + w / 2);
                        Vector3 outward = t.right[i] * side;
                        float frontOff = hw + sw + 0.15f + (canalHere ? 18f : 0f) + row * kit.R(22f, 30f);
                        Vector3 front = t.pts[i] + outward * frontOff; front.y = 0f;
                        Vector3 center = front + outward * dep / 2;
                        var corners2 = BuildingKit.Corners(center, Quaternion.LookRotation(outward), w, dep);
                        bool clear = true;
                        foreach (var cpt in corners2) if (TrackDist(new Vector3(cpt.x, 0, cpt.y)) < hw + sw + 0.1f) clear = false;
                        if (clear && bk.TryReserve(center, Quaternion.LookRotation(outward), w, dep, out var lot))
                        {
                            bool startZone = d < 260f;
                            float h = row == 0 ? kit.R(14f, startZone ? 46f : 34f) : kit.R(20f, 60f);
                            int fac = row == 0 ? bk.FacadeIndex(kit.Chance(0.6f) ? "tile" : "mixed", kit.rng) : kit.RI(0, bk.facades.Count);
                            var bmb = Chunk(center);
                            bk.AddBuilding(bmb, kit, lot, h, fac, row == 0, row == 0, Tint(kit), neon, 0f);
                            if (row == 0 && startZone && bk.billboards.entries.Count > 0 && kit.Chance(0.35f) && h > 24f)
                            {
                                // giant facade screen (Shibuya crossing vibe)
                                var e = bk.billboards.Pick(kit.rng);
                                float bw = Mathf.Min(w - 1.5f, 14f), bh = bw / Mathf.Max(1.3f, e.aspect);
                                Vector3 sc = front - outward * 0.35f + Vector3.up * Mathf.Min(h - bh / 2 - 2f, 17f);
                                bk.billboards.AddSign(bmb, bk.SubBillboard, bk.SubFrame, e, sc, -outward, Vector3.up, bw, bh, 0.5f, Color.white);
                                if (night) neon.Add(sc - outward * 5f - Vector3.up * 4f);
                            }
                        }
                        d += w + (kit.Chance(0.15f) ? kit.R(2f, 4f) : kit.R(0.1f, 0.8f));
                    }
                }
            // infill grid: dense blocks with occasional streets, towers further out
            Vector3 mn = new Vector3(1e9f, 0, 1e9f), mx = new Vector3(-1e9f, 0, -1e9f);
            foreach (var p in t.pts) { mn = Vector3.Min(mn, p); mx = Vector3.Max(mx, p); }
            float pad = 420f;
            for (float x = mn.x - pad; x < mx.x + pad; x += 24f)
                for (float z = mn.z - pad; z < mx.z + pad; z += 24f)
                {
                    if (Mathf.Repeat(x - mn.x, 24f * 5f) < 1f || Mathf.Repeat(z - mn.z, 24f * 4f) < 1f) continue;   // grid streets
                    Vector3 c = new Vector3(x + kit.R(-2f, 2f), 0, z + kit.R(-2f, 2f));
                    float td = TrackDist(c);
                    if (td < hw + sw + 14f) continue;
                    float w = kit.R(14f, 21f), dep = kit.R(14f, 21f);
                    if (!bk.TryReserve(c, Quaternion.identity, w, dep, out var lot)) continue;
                    float far01 = Mathf.InverseLerp(40f, 380f, td);
                    float cluster = Mathf.PerlinNoise(x * 0.004f + 3.1f, z * 0.004f + 7.7f);
                    float h = Mathf.Lerp(kit.R(12f, 40f), kit.R(30f, 150f) * (0.4f + cluster), far01 * (0.4f + 0.6f * cluster));
                    var bmb = Chunk(c);
                    if (h > 70f) bk.AddTower(bmb, kit, lot, h, bk.FacadeIndex(kit.Chance(0.5f) ? "glass" : "dark", kit.rng), Tint(kit), 0f);
                    else bk.AddBuilding(bmb, kit, lot, h, kit.RI(0, bk.facades.Count), td < 60f, td < 60f, Tint(kit), td < 60f ? neon : null, 0f);
                }
            foreach (var kv in chunks) kit.MeshObject($"Block_{kv.Key.x}_{kv.Key.y}", gCity, kv.Value, bk.Materials, false);

            // ground plane under everything
            {
                var gm = new MeshBuilder();
                Vector3 a = new Vector3(mn.x - pad - 40, -0.03f, mn.z - pad - 40), b = new Vector3(mx.x + pad + 40, -0.03f, mx.z + pad + 40);
                gm.Quad(0, new Vector3(a.x, a.y, a.z), new Vector3(a.x, a.y, b.z), new Vector3(b.x, a.y, b.z), new Vector3(b.x, a.y, a.z), Vector2.zero, Vector2.one, Color.white);
                kit.MeshObject("Ground", gRoad, gm, new[] { ground }, true, false);
            }

            // ------------------------------------------------ street furniture
            var lamp = kit.FindPrefab("street_lamp_classic", "street_lamp");
            var pole = kit.FindPrefab("utility_pole_transformer", "utility_pole");
            var pole2 = kit.FindPrefab("utility_pole_plain", "utility_pole");
            var vend = kit.FindPrefabs("vending_machine");
            var rail = kit.FindPrefab("pedestrian_railing_2m_bars_green", "pedestrian_railing");
            var keyaki = kit.FindPrefabs("keyaki");
            var bike = kit.FindPrefab("bicycle");
            var cone = kit.FindPrefab("traffic_cone");
            var barrier = kit.FindPrefab("construction_barrier");
            var signal = kit.FindPrefab("traffic_signal_vehicle");
            var pedSignal = kit.FindPrefab("traffic_signal_pedestrian");
            var bollard = kit.FindPrefab("bollard_steel", "bollard");
            var postbox = kit.FindPrefab("post_box_round", "post_box");
            var lampColor = new Color(1f, 0.78f, 0.55f);
            var poleTops = new List<(Vector3 basePos, Quaternion rot, GameObject inst)>();

            for (float d = 4f; d < t.length; d += 30f)
            {
                int i = t.IndexAt(d);
                int side = ((int)(d / 30f) % 2 == 0) ? 1 : -1;
                if (side < 0 && InCanal(d)) side = 1;
                Vector3 o = t.pts[i], rr = t.right[i] * side;
                var lp = kit.Place(lamp, o + rr * (hw + 0.7f) + Vector3.up * 0.15f, Quaternion.LookRotation(-rr), gProps);
                if (lp == null && lamp == null)
                {
                    // fallback lamp: pole + head box
                    var lmb = new MeshBuilder();
                    lmb.Box(0, o + rr * (hw + 0.7f) + Vector3.up * 3.7f, Quaternion.LookRotation(rr), new Vector3(0.16f, 7.4f, 0.16f), 1f, Color.white);
                    lmb.Box(0, o + rr * (hw - 0.4f) + Vector3.up * 7.3f, Quaternion.LookRotation(rr), new Vector3(0.3f, 0.15f, 2.4f), 1f, Color.white);
                    kit.MeshObject("Lamp", gProps, lmb, new[] { bk.metal }, false);
                }
                if (night) AddPointLight(gLights, o + rr * (hw - 0.9f) + Vector3.up * 7f, lampColor, 22f, 110f);
            }
            for (float d = 12f; d < t.length; d += 34f)
            {
                if (InCorner(d, 12f) || d < 250f) continue;
                int i = t.IndexAt(d);
                int side = InCanal(d) ? 1 : -1;
                Vector3 o = t.pts[i], rr = t.right[i] * side;
                var prefab = kit.Chance(0.5f) ? pole : pole2;
                var inst = kit.Place(prefab, o + rr * (hw + sw - 0.5f) + Vector3.up * 0.15f, Quaternion.LookRotation(-rr), gProps);
                poleTops.Add((o + rr * (hw + sw - 0.5f), Quaternion.LookRotation(-rr), inst));
            }
            Wires(kit, gProps, poleTops);

            for (float d = 20f; d < t.length; d += kit.R(30f, 60f))
            {
                if (InCorner(d, 10f)) continue;
                int i = t.IndexAt(d);
                int side = kit.Chance(0.5f) ? 1 : -1;
                if (side < 0 && InCanal(d)) side = 1;
                Vector3 o = t.pts[i], rr = t.right[i] * side;
                int n = kit.RI(1, 4);
                for (int k = 0; k < n && vend.Count > 0; k++)
                {
                    var vm = kit.Place(kit.Pick(vend), o + rr * (hw + sw - 0.55f) + t.tan[i] * (k * 1.15f) + Vector3.up * 0.15f, Quaternion.LookRotation(-rr), gProps);
                    if (night && k == 0) AddPointLight(gLights, o + rr * (hw + sw - 1.8f) + Vector3.up * 1.5f, new Color(0.85f, 0.95f, 1f), 6f, 4f);
                }
                if (bike && kit.Chance(0.5f))
                    for (int k = 0; k < kit.RI(1, 5); k++)
                        kit.Place(bike, o + rr * (hw + 1.2f) + t.tan[i] * (3f + k * 0.7f) + Vector3.up * 0.15f, Quaternion.LookRotation(rr) * Quaternion.Euler(0, kit.R(-8, 8), 0), gProps);
                if (postbox && kit.Chance(0.15f)) kit.Place(postbox, o + rr * (hw + 1f) - t.tan[i] * 4f + Vector3.up * 0.15f, Quaternion.LookRotation(-rr), gProps);
            }
            // railings along curbs with gaps
            if (rail)
                for (float d = 0; d < t.length; d += 2f)
                {
                    if (InCorner(d, 16f) || Mathf.Repeat(d, 40f) > 30f) continue;
                    int i = t.IndexAt(d);
                    foreach (int side in new[] { -1, 1 })
                    {
                        if (side < 0 && InCanal(d)) continue;
                        int ip = side > 0 ? i : t.IndexAt(d + 2f);
                        kit.Place(rail, t.pts[ip] + t.right[ip] * side * (hw + 0.45f) + Vector3.up * 0.15f, Quaternion.LookRotation(-t.right[ip] * side), gProps);
                    }
                }
            // keyaki avenue on the start straight
            if (keyaki.Count > 0)
                for (float d = 10f; d < t.segEnd[0] - 10f; d += 14f)
                {
                    int i = t.IndexAt(d);
                    foreach (int side in new[] { -1, 1 })
                        kit.Place(kit.Pick(keyaki), t.pts[i] + t.right[i] * side * (hw + 2.0f) + Vector3.up * 0.15f, Quaternion.Euler(0, kit.R(0, 360), 0), gProps, kit.R(0.85f, 1.05f));
                }
            // intersections: signals + bollards
            foreach (var s in corners)
            {
                foreach (float dc in new[] { t.segStart[s] - 12f, t.segEnd[s] + 12f })
                {
                    int i = t.IndexAt(dc);
                    foreach (int side in new[] { -1, 1 })
                    {
                        Vector3 p = t.pts[i] + t.right[i] * side * (hw + 0.8f) + Vector3.up * 0.15f;
                        if (signal && side < 0) kit.Place(signal, p, Quaternion.LookRotation(-t.tan[i]), gProps);
                        if (pedSignal && side > 0) kit.Place(pedSignal, p, Quaternion.LookRotation(-t.right[i]), gProps);
                        if (bollard) for (int k = 0; k < 3; k++) kit.Place(bollard, p + t.tan[i] * (k * 1.2f + 1.5f), Quaternion.identity, gProps);
                    }
                }
            }
            // stub barricades (visible boundary + collider)
            foreach (var st in stubs)
            {
                var q = Quaternion.LookRotation(st.dir);
                Vector3 r = q * Vector3.right;
                Vector3 p = st.mouth + st.dir * 4f;
                for (float x = -st.hw - 1f; x <= st.hw + 1f; x += 1.6f)
                {
                    if (barrier) kit.Place(barrier, p + r * x + Vector3.up * 0.0f, q, gProps);
                    else if (cone) kit.Place(cone, p + r * x, q, gProps);
                }
                if (night) AddPointLight(gLights, p + Vector3.up * 2.5f, new Color(1f, 0.55f, 0.1f), 8f, 6f);
            }

            // neon spill lights (colored, on the wet road)
            if (night)
            {
                var cols = new[] { new Color(1f, 0.18f, 0.5f), new Color(0f, 0.85f, 1f), new Color(1f, 0.85f, 0.1f), new Color(0.6f, 0.3f, 1f), new Color(1f, 0.35f, 0.15f) };
                var used = new List<Vector3>();
                foreach (var p in neon)
                {
                    if (TrackDist(p) > hw + sw + 8f) continue;
                    bool close = false;
                    foreach (var u in used) if ((u - p).sqrMagnitude < 14f * 14f) { close = true; break; }
                    if (close) continue;
                    used.Add(p);
                    AddPointLight(gLights, p, cols[kit.RI(0, cols.Length)], 18f, 45f);
                }
            }

            // ------------------------------------------------ boundary colliders (building line) + visible barriers where open
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var wmb = new MeshBuilder();
                wmb.Sweep(0, t, i0, cnt, new[] { new Vector2(hw + sw, 0f), new Vector2(hw + sw, 4f) }, 1f, 1f, Color.white, null, true);
                wmb.Sweep(0, t, i0, cnt, new[] { new Vector2(-hw - sw, 4f), new Vector2(-hw - sw, 0f) }, 1f, 1f, Color.white,
                    i => InCanal(t.dist[i]) ? sw - 2.4f : 0f, true);
                kit.ColliderOnly($"Wall_{i0}", gCol, wmb);
            }
        }

        static List<Vector3> neon = new List<Vector3>();
        static readonly Dictionary<Vector2Int, MeshBuilder> chunks = new Dictionary<Vector2Int, MeshBuilder>();

        static MeshBuilder Chunk(Vector3 p)
        {
            var k = new Vector2Int(Mathf.FloorToInt(p.x / 120f), Mathf.FloorToInt(p.z / 120f));
            if (!chunks.TryGetValue(k, out var mb)) chunks[k] = mb = new MeshBuilder();
            return mb;
        }

        public static Color Tint(PropKit kit)
        {
            float v = kit.R(0.82f, 1.05f);
            return new Color(v * kit.R(0.95f, 1.05f), v * kit.R(0.95f, 1.03f), v * kit.R(0.95f, 1.08f), 1f);
        }

        public static void AddPointLight(Transform parent, Vector3 pos, Color c, float range, float intensity)
        {
            var g = new GameObject("PL");
            g.transform.SetParent(parent, false);
            g.transform.position = pos;
            var l = g.AddComponent<Light>();
            l.type = LightType.Point; l.color = c; l.range = range; l.intensity = intensity; l.shadows = LightShadows.None;
            l.renderMode = LightRenderMode.ForcePixel;
        }

        /// <summary>Catenary wires between consecutive utility poles (uses WireAnchor_* children when present).</summary>
        public static void Wires(PropKit kit, Transform parent, List<(Vector3 basePos, Quaternion rot, GameObject inst)> poles)
        {
            var wm = new MeshBuilder();
            List<Vector3> Anchors((Vector3 basePos, Quaternion rot, GameObject inst) p)
            {
                var list = new List<Vector3>();
                if (p.inst != null)
                    foreach (var tr in p.inst.GetComponentsInChildren<Transform>())
                        if (tr.name.StartsWith("WireAnchor")) list.Add(tr.position);
                if (list.Count == 0)
                {
                    Vector3 r = p.rot * Vector3.right;
                    foreach (float h in new[] { 10.6f, 10.6f, 9.6f, 9.6f, 8.2f })
                        list.Add(p.basePos + Vector3.up * h + r * (list.Count % 2 == 0 ? -0.6f : 0.6f));
                }
                return list;
            }
            for (int k = 0; k + 1 < poles.Count; k++)
            {
                if ((poles[k].basePos - poles[k + 1].basePos).magnitude > 60f) continue;
                var a = Anchors(poles[k]); var b = Anchors(poles[k + 1]);
                int n = Mathf.Min(a.Count, b.Count);
                for (int w = 0; w < n; w++)
                {
                    var pts = new List<Vector3>();
                    float sag = 0.5f + 0.15f * w;
                    for (int s = 0; s <= 12; s++) { float u = s / 12f; pts.Add(Vector3.Lerp(a[w], b[w], u) - Vector3.up * sag * 4f * u * (1 - u)); }
                    wm.Tube(0, pts, w < 2 ? 0.025f : 0.016f, 4, Color.white);
                }
            }
            kit.MeshObject("Wires", parent, wm, new[] { MaterialLibrary.Flat("Toon_Cable", new Color(0.05f, 0.05f, 0.06f), 0.2f) }, false, false);
        }
    }
}
