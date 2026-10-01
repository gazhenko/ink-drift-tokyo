using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>OKUTAMA TOUGE: autumn mountain pass with carved terrain, switchback walls, guardrails, dense instanced forest and a gorge.</summary>
    public static class MountainBuilder
    {
        const float Cell = 5f;

        public static void Build(PropKit kit, TrackLayout t, TrackDef def, Transform root)
        {
            float hw = def.roadHalfWidth, sh = def.sidewalk;     // sidewalk = paved shoulder width here
            float edge = hw + sh;
            var gRoad = PropKit.Group("Road", root);
            var gTerrain = PropKit.Group("Terrain", root);
            var gProps = PropKit.Group("Props", root);
            var gCol = PropKit.Group("Colliders", root);

            // ---------------- materials
            var road = MaterialLibrary.FromSet("road_asphalt_fresh", "Toon_MountainRoad", 5f, 0.3f);
            road.SetTextureScale("_BaseMap", Vector2.one);
            road.SetColor("_BaseColor", new Color(1.3f, 1.3f, 1.35f));
            var gravel = MaterialLibrary.FromSet("nature_dirt_shoulder", "Toon_Shoulder", 1f, 0.15f);
            gravel.SetTextureScale("_BaseMap", Vector2.one * 0.5f);
            var white = MaterialLibrary.Flat("Toon_PaintWhite", new Color(0.92f, 0.92f, 0.88f), 0.45f);
            var yellow = MaterialLibrary.Flat("Toon_PaintYellow", new Color(1f, 0.78f, 0.1f), 0.45f);
            var wallMat = MaterialLibrary.FromSet("concrete_weathered", "Toon_RetainingWall", 1f, 0.2f);
            var grid = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Generated/Common/slope_grid_albedo.png");
            if (grid) { wallMat.SetTexture("_BaseMap", grid); wallMat.SetTextureScale("_BaseMap", Vector2.one); }
            var terrainMat = MaterialLibrary.Ensure("Terrain_Okutama", Shader.Find("InkDrift/Terrain"));
            void T(string prop, string set, string suffix)
            {
                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/InkDrift/Art/Textures/{set}/{set}{suffix}.png")
                          ?? AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/InkDrift/Art/Textures/{set}/{set}{suffix}.jpg");
                if (tex) terrainMat.SetTexture(prop, tex);
            }
            T("_GrassMap", "nature_grass", "_albedo"); T("_GrassNormal", "nature_grass", "_normal");
            T("_RockMap", "nature_rock_cliff", "_albedo"); T("_RockNormal", "nature_rock_cliff", "_normal");
            T("_LeafMap", "nature_forest_floor_autumn", "_albedo"); T("_LeafNormal", "nature_forest_floor_autumn", "_normal");
            T("_DirtMap", "nature_gravel", "_albedo"); T("_DirtNormal", "nature_gravel", "_normal");
            terrainMat.SetVector("_Tiling", new Vector4(5f, 9f, 5f, 3f));
            terrainMat.SetColor("_GrassTint", new Color(0.78f, 0.82f, 0.55f));
            var water = MaterialLibrary.Ensure("Water_River", Shader.Find("InkDrift/Water"));
            water.SetColor("_ShallowColor", new Color(0.3f, 0.75f, 0.7f)); water.SetColor("_DeepColor", new Color(0.05f, 0.25f, 0.35f));
            water.SetVector("_FlowDir", new Vector4(1, 0, 0.1f, 0)); water.SetFloat("_WaveSpeed", 0.9f);
            var asphaltPhys = new PhysicsMaterial("Asphalt") { dynamicFriction = 0.8f, staticFriction = 0.8f }; kit.SaveObject(asphaltPhys, "Asphalt");
            var grassPhys = new PhysicsMaterial("Grass") { dynamicFriction = 0.5f, staticFriction = 0.5f }; kit.SaveObject(grassPhys, "Grass");
            var dirtPhys = new PhysicsMaterial("Dirt") { dynamicFriction = 0.6f, staticFriction = 0.6f }; kit.SaveObject(dirtPhys, "Dirt");

            // ---------------- spatial index of road samples
            var idx = new Dictionary<Vector2Int, List<int>>();
            for (int i = 0; i < t.Count; i++)
            {
                var k = new Vector2Int(Mathf.FloorToInt(t.pts[i].x / 20f), Mathf.FloorToInt(t.pts[i].z / 20f));
                if (!idx.TryGetValue(k, out var l)) idx[k] = l = new List<int>();
                l.Add(i);
            }
            float Nearest(float x, float z, out int best)
            {
                var k = new Vector2Int(Mathf.FloorToInt(x / 20f), Mathf.FloorToInt(z / 20f));
                float bd = 1e9f; best = 0;
                for (int a = -2; a <= 2; a++)
                    for (int b = -2; b <= 2; b++)
                        if (idx.TryGetValue(new Vector2Int(k.x + a, k.y + b), out var l))
                            foreach (var i in l) { float dx = x - t.pts[i].x, dz = z - t.pts[i].z; float d = dx * dx + dz * dz; if (d < bd) { bd = d; best = i; } }
                if (bd > 1e8f)
                {
                    for (int i = 0; i < t.Count; i += 4) { float dx = x - t.pts[i].x, dz = z - t.pts[i].z; float d = dx * dx + dz * dz; if (d < bd) { bd = d; best = i; } }
                }
                return Mathf.Sqrt(bd);
            }

            // IDW base surface from a subset of road samples
            var basePts = new List<Vector3>();
            for (int i = 0; i < t.Count; i += 3) basePts.Add(t.pts[i]);
            float Base(float x, float z)
            {
                double ws = 0, hs = 0;
                foreach (var p in basePts)
                {
                    double dx = x - p.x, dz = z - p.z;
                    double d2 = dx * dx + dz * dz + 25.0;
                    double w = 1.0 / (d2 * d2);
                    ws += w; hs += w * p.y;
                }
                return (float)(hs / ws);
            }

            Vector3 mn = new Vector3(1e9f, 0, 1e9f), mx = new Vector3(-1e9f, 0, -1e9f);
            foreach (var p in t.pts) { mn = Vector3.Min(mn, p); mx = Vector3.Max(mx, p); }
            Vector3 center = (mn + mx) * 0.5f;

            // river: runs west-east south of the track
            var river = new List<Vector3>();
            for (float x = mn.x - 900f; x <= mx.x + 900f; x += 20f)
                river.Add(new Vector3(x, -22f, mn.z - 115f + Mathf.Sin(x / 170f) * 45f + Mathf.Sin(x / 63f) * 12f));
            float RiverDist(float x, float z)
            {
                float best = 1e9f;
                for (int i = 0; i < river.Count - 1; i++)
                {
                    Vector2 a = new Vector2(river[i].x, river[i].z), b = new Vector2(river[i + 1].x, river[i + 1].z), p = new Vector2(x, z);
                    Vector2 ab = b - a; float u = Mathf.Clamp01(Vector2.Dot(p - a, ab) / ab.sqrMagnitude);
                    best = Mathf.Min(best, Vector2.Distance(p, a + ab * u));
                }
                return best;
            }

            float Ridge(float x, float z)
            {
                float s = 0f, a = 1f, f = 1f / 420f;
                for (int o = 0; o < 5; o++)
                {
                    float n = 1f - Mathf.Abs(Mathf.PerlinNoise(x * f + 31.7f + o * 7.1f, z * f + 11.3f + o * 3.7f) * 2f - 1f);
                    s += n * n * a; a *= 0.5f; f *= 2.1f;
                }
                return s;
            }

            // ---------------- terrain heightfield
            float x0 = mn.x - 700f, z0 = mn.z - 520f, x1 = mx.x + 700f, z1 = mx.z + 700f;
            int nx = Mathf.CeilToInt((x1 - x0) / Cell) + 1, nz = Mathf.CeilToInt((z1 - z0) / Cell) + 1;
            var H = new float[nx, nz];
            var D = new float[nx, nz];
            for (int ix = 0; ix < nx; ix++)
                for (int iz = 0; iz < nz; iz++)
                {
                    float x = x0 + ix * Cell, z = z0 + iz * Cell;
                    float dRoad = Nearest(x, z, out int ni);
                    D[ix, iz] = dRoad;
                    float baseH = Base(x, z);
                    float rise = (z - center.z) * 0.10f;
                    float amp = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(12f, 320f, dRoad));
                    float h = baseH + Ridge(x, z) * 190f * amp + rise * amp + (Mathf.PerlinNoise(x * 0.05f, z * 0.05f) - 0.5f) * 3f * Mathf.InverseLerp(6f, 30f, dRoad);
                    // river gorge
                    float dr = RiverDist(x, z);
                    float gorge = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(95f, 14f, dr));
                    h = Mathf.Lerp(h, -24f + Mathf.Min(dr, 14f) * 0.15f, gorge);
                    // blend toward nearby road heights (weighted over samples within 20 m)
                    if (dRoad < 22f)
                    {
                        float wsum = 0f, ysum = 0f, wmax = 0f;
                        var k = new Vector2Int(Mathf.FloorToInt(x / 20f), Mathf.FloorToInt(z / 20f));
                        for (int a = -1; a <= 1; a++)
                            for (int b = -1; b <= 1; b++)
                                if (idx.TryGetValue(new Vector2Int(k.x + a, k.y + b), out var l))
                                    foreach (var i in l)
                                    {
                                        float d = new Vector2(x - t.pts[i].x, z - t.pts[i].z).magnitude;
                                        float w = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(edge + 13f, edge + 1.5f, d));
                                        if (w <= 0f) continue;
                                        wsum += w; ysum += w * (t.pts[i].y - 0.35f); wmax = Mathf.Max(wmax, w);
                                    }
                        if (wsum > 0f) h = Mathf.Lerp(h, ysum / wsum, wmax);
                    }
                    H[ix, iz] = h;
                }

            float HeightAt(float x, float z)
            {
                float fx = (x - x0) / Cell, fz = (z - z0) / Cell;
                int ix = Mathf.Clamp((int)fx, 0, nx - 2), iz = Mathf.Clamp((int)fz, 0, nz - 2);
                float u = fx - ix, v = fz - iz;
                return Mathf.Lerp(Mathf.Lerp(H[ix, iz], H[ix + 1, iz], u), Mathf.Lerp(H[ix, iz + 1], H[ix + 1, iz + 1], u), v);
            }
            Vector3 NormalAt(int ix, int iz)
            {
                float hl = H[Mathf.Max(ix - 1, 0), iz], hr = H[Mathf.Min(ix + 1, nx - 1), iz];
                float hd = H[ix, Mathf.Max(iz - 1, 0)], hu = H[ix, Mathf.Min(iz + 1, nz - 1)];
                return new Vector3(hl - hr, 2f * Cell, hd - hu).normalized;
            }

            // chunked terrain meshes with splat vertex colors
            int cq = 60;
            for (int cx = 0; cx < nx - 1; cx += cq)
                for (int cz = 0; cz < nz - 1; cz += cq)
                {
                    int ex = Mathf.Min(cx + cq, nx - 1), ez = Mathf.Min(cz + cq, nz - 1);
                    var mb = new MeshBuilder();
                    int w = ex - cx + 1;
                    for (int iz = cz; iz <= ez; iz++)
                        for (int ix = cx; ix <= ex; ix++)
                        {
                            float x = x0 + ix * Cell, z = z0 + iz * Cell;
                            Vector3 n = NormalAt(ix, iz);
                            float slope = 1f - n.y;
                            float dRoad = D[ix, iz];
                            float rock = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.22f, 0.42f, slope));
                            float dirt = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(edge + 6f, edge + 1f, dRoad)) * (1f - rock);
                            float forest = Mathf.PerlinNoise(x * 0.012f + 5f, z * 0.012f + 9f);
                            float leaf = Mathf.Clamp01((forest - 0.35f) * 3f) * (1f - rock) * (1f - dirt);
                            float grassW = Mathf.Clamp01(1f - rock - dirt - leaf);
                            float dr = RiverDist(x, z);
                            if (dr < 18f) { rock = Mathf.Max(rock, 0.7f); grassW *= 0.3f; }
                            mb.Vert(new Vector3(x, H[ix, iz], z), n, new Vector2(x, z) / 10f, new Color(grassW, rock, leaf, dirt));
                        }
                    for (int iz = 0; iz < ez - cz; iz++)
                        for (int ix = 0; ix < ex - cx; ix++)
                        {
                            int a = iz * w + ix, b = a + 1, c = a + w, d = c + 1;
                            mb.Tri(0, a, c, d); mb.Tri(0, a, d, b);
                        }
                    var go = kit.MeshObject($"Terrain_{cx}_{cz}", gTerrain, mb, new[] { terrainMat }, true, true, 9, grassPhys);
                }

            // river water
            {
                var wm = new MeshBuilder();
                for (int i = 0; i < river.Count - 1; i++)
                {
                    Vector3 a = river[i], b = river[i + 1];
                    Vector3 dir = (b - a).normalized; Vector3 r = Vector3.Cross(Vector3.up, dir) * 13f;
                    a.y = b.y = -20.5f;
                    wm.Quad(0, a - r, b - r, b + r, a + r, new Vector2(0, i), new Vector2(1, i + 1), Color.white);
                }
                kit.MeshObject("River", gTerrain, wm, new[] { water }, false, false);
            }

            // distant mountain ring (silhouettes in the haze)
            {
                var rm = new MeshBuilder();
                int seg = 160, rings = 6;
                float r0 = 1700f, r1 = 4800f;
                var ringMat = MaterialLibrary.Flat("Toon_FarMountains", Color.white, 0.1f);
                ringMat.SetFloat("_VertexTint", 1f); ringMat.SetFloat("_HalftoneAmount", 0.2f); ringMat.SetFloat("_RimAmount", 0f);
                for (int rI = 0; rI <= rings; rI++)
                    for (int s = 0; s <= seg; s++)
                    {
                        float ang = s / (float)seg * Mathf.PI * 2f;
                        float rad = Mathf.Lerp(r0, r1, rI / (float)rings);
                        float x = center.x + Mathf.Cos(ang) * rad, z = center.z + Mathf.Sin(ang) * rad;
                        float h = rI == 0 ? -30f : Ridge(x * 0.5f, z * 0.5f) * Mathf.Lerp(250f, 900f, rI / (float)rings) - 60f;
                        float haze = rI / (float)rings;
                        Color c = Color.Lerp(new Color(0.45f, 0.5f, 0.38f), new Color(0.55f, 0.6f, 0.82f), haze);
                        rm.Vert(new Vector3(x, h, z), Vector3.up, Vector2.zero, c);
                    }
                for (int rI = 0; rI < rings; rI++)
                    for (int s = 0; s < seg; s++)
                    {
                        int a = rI * (seg + 1) + s, b = a + 1, c = a + seg + 1, d = c + 1;
                        rm.Tri(0, a, d, c); rm.Tri(0, a, b, d);
                    }
                var m = rm.ToMesh("FarMountains", true);
                var go = new GameObject("FarMountains");
                go.transform.SetParent(gTerrain, false);
                go.AddComponent<MeshFilter>().sharedMesh = kit.SaveMesh(m);
                go.AddComponent<MeshRenderer>().sharedMaterial = ringMat;
            }

            // ---------------- road surface + shoulders + skirts
            int chunk = 50;
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var mb = new MeshBuilder();
                mb.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge, 0f), new Vector2(0f, 0.06f), new Vector2(edge, 0f) }, 5f, 5f, Color.white);
                kit.MeshObject($"Road_{i0}", gRoad, mb, new[] { road }, true, false, 9, asphaltPhys);
                var sk = new MeshBuilder();
                sk.Sweep(0, t, i0, cnt, new[] { new Vector2(edge, 0f), new Vector2(edge + 1.4f, -0.2f), new Vector2(edge + 2.6f, -1.6f) }, 2f, 2f, Color.white);
                sk.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge - 2.6f, -1.6f), new Vector2(-edge - 1.4f, -0.2f), new Vector2(-edge, 0f) }, 2f, 2f, Color.white);
                kit.MeshObject($"Shoulder_{i0}", gRoad, sk, new[] { gravel }, true, false, 9, dirtPhys);
            }
            var mk = new MeshBuilder();
            void Strip(int sub, float x, float w, float d0, float d1)
            {
                int a = t.IndexAt(d0), b = t.IndexAt(d1);
                int n = t.Wrap(b - a); if (n < 1) return;
                mk.Sweep(sub, t, a, n, new[] { new Vector2(x - w / 2, 0.065f), new Vector2(x + w / 2, 0.065f) }, 1f, 1f, Color.white);
            }
            for (float d = 0; d < t.length; d += 6f)
            {
                float e = Mathf.Min(d + 6f, t.length - 0.1f);
                Strip(0, hw - 0.2f, 0.15f, d, e); Strip(0, -hw + 0.2f, 0.15f, d, e);
                Strip(1, 0f, 0.15f, d, e);
            }
            kit.MeshObject("Markings", gRoad, mk, new[] { white, yellow }, false, false);

            // ---------------- retaining walls (uphill) + guardrails (downhill)
            var walls = new MeshBuilder();
            var gr = kit.FindPrefab("guardrail_wbeam_4m", "guardrail");
            var cable = kit.FindPrefab("mountain_guardrail_cable");
            var grDown = new bool[t.Count, 2];
            for (int side = -1; side <= 1; side += 2)
            {
                int s01 = side < 0 ? 0 : 1;
                Vector3? prevBot = null, prevTop = null; float prevV = 0f;
                for (int i = 0; i <= t.Count; i++)
                {
                    int ii = t.Wrap(i);
                    Vector3 o = t.pts[ii]; Vector3 r = t.right[ii] * side;
                    Vector3 probe = o + r * (edge + 4f);
                    float th = HeightAt(probe.x, probe.z);
                    float diff = th - o.y;
                    grDown[ii, s01] = diff < -1.2f;
                    if (diff > 2.0f)
                    {
                        float wallH = Mathf.Clamp(diff + 0.6f, 0f, 14f);
                        Vector3 bot = o + r * (edge + 0.5f) + Vector3.up * -0.3f;
                        Vector3 top = bot + r * (wallH * 0.32f) + Vector3.up * wallH;
                        float v = t.dist[ii] / 6f;
                        if (prevBot.HasValue)
                        {
                            if (side > 0) walls.Quad(0, prevBot.Value, prevTop.Value, top, bot, new Vector2(prevV, 0), new Vector2(v, wallH / 6f), Color.white);
                            else walls.Quad(0, bot, top, prevTop.Value, prevBot.Value, new Vector2(v, 0), new Vector2(prevV, wallH / 6f), Color.white);
                        }
                        prevBot = bot; prevTop = top; prevV = v;
                    }
                    else { prevBot = null; prevTop = null; }
                }
            }
            kit.MeshObject("RetainingWalls", gRoad, walls, new[] { wallMat }, true, true);

            for (int side = -1; side <= 1; side += 2)
            {
                int s01 = side < 0 ? 0 : 1;
                for (float d = 0; d < t.length; d += 4f)
                {
                    int i = t.IndexAt(d);
                    bool hairpin = Mathf.Abs(t.curvature[i]) > 1f / 30f && Mathf.Sign(t.curvature[i]) == -side;  // outside of the turn
                    if (!grDown[i, s01] && !hairpin) continue;
                    // 4 m tiles run along local +X from the origin, front (+Z) faces the road
                    int ip = side > 0 ? i : t.IndexAt(d + 4f);
                    Vector3 p = t.pts[ip] + t.right[ip] * side * (edge - 0.1f);
                    var prefab = (cable != null && kit.Chance(0.15f)) ? cable : gr;
                    if (prefab) kit.Place(prefab, p, Quaternion.LookRotation(-t.right[ip] * side), gProps);
                }
            }
            // containment colliders on both sides everywhere
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var w = new MeshBuilder();
                w.Sweep(0, t, i0, cnt, new[] { new Vector2(edge + 0.2f, -1f), new Vector2(edge + 0.2f, 2.5f) }, 1f, 1f, Color.white);
                w.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge - 0.2f, 2.5f), new Vector2(-edge - 0.2f, -1f) }, 1f, 1f, Color.white);
                kit.ColliderOnly($"Containment_{i0}", gCol, w);
            }

            // ---------------- hairpin furniture: convex mirrors + chevrons; delineators; signs
            var mirror = kit.FindPrefab("convex_traffic_mirror", "mirror");
            var chevron = kit.FindPrefab("chevron_curve_sign", "chevron");
            var delin = kit.FindPrefab("delineator_post", "delineator");
            for (int s = 0; s < t.segments.Count; s++)
            {
                var seg = t.segments[s];
                if (seg.kind == 'S' || seg.a < 100f) continue;
                int side = seg.kind == 'R' ? -1 : 1;   // outside of the turn
                float mid = (t.segStart[s] + t.segEnd[s]) * 0.5f;
                int im = t.IndexAt(mid);
                if (mirror) kit.Place(mirror, t.pts[im] + t.right[im] * side * (edge + 1.0f), Quaternion.LookRotation(-t.right[im] * side), gProps);
                for (float d = t.segStart[s]; d < t.segEnd[s]; d += 6f)
                {
                    int i = t.IndexAt(d);
                    if (chevron) kit.Place(chevron, t.pts[i] + t.right[i] * side * (edge + 0.6f), Quaternion.LookRotation(-t.tan[i]), gProps);
                }
            }
            if (delin)
                for (float d = 0; d < t.length; d += 22f)
                {
                    int i = t.IndexAt(d);
                    foreach (int side in new[] { -1, 1 })
                        kit.Place(delin, t.pts[i] + t.right[i] * side * (edge + 0.35f), Quaternion.LookRotation(-t.tan[i]), gProps);
                }

            // shrine + vending machine by the start
            {
                int i = t.IndexAt(def.startDistance - 70f);
                Vector3 o = t.pts[i], r = -t.right[i];
                Vector3 sp = o + r * (edge + 9f); sp.y = HeightAt(sp.x, sp.z);
                var torii = kit.FindPrefab("torii_stone", "torii");
                var toro = kit.FindPrefab("toro_stone_lantern", "toro");
                if (torii) kit.Place(torii, sp, Quaternion.LookRotation(-r), gProps);
                if (toro) { kit.Place(toro, sp + t.tan[i] * 2.6f + r * 2f, Quaternion.LookRotation(-r), gProps); kit.Place(toro, sp - t.tan[i] * 2.6f + r * 2f, Quaternion.LookRotation(-r), gProps); }
                var offering = kit.FindPrefab("hokora_small", "saisen_box");
                if (offering) kit.Place(offering, sp + r * 6f, Quaternion.LookRotation(-r), gProps);
                var vend = kit.FindPrefabs("vending_machine");
                int j = t.IndexAt(def.startDistance - 25f);
                Vector3 vp = t.pts[j] + t.right[j] * (edge + 1.1f);
                if (vend.Count > 0) kit.Place(vend[0], vp, Quaternion.LookRotation(-t.right[j]), gProps);
            }

            // ---------------- foliage (instanced)
            var fd = ScriptableObject.CreateInstance<FoliageData>();
            fd.cellSize = 96f;
            var sugi = kit.FindPrefabs("sugi", "Trees");
            var momiji = kit.FindPrefabs("momiji", "Trees");
            var ginkgo = kit.FindPrefabs("ginkgo", "Trees");
            var bamboo = kit.FindPrefabs("bamboo", "Trees");
            var shrubs = kit.FindPrefabs("bush", "Trees").Concat(kit.FindPrefabs("hedge_azalea", "Trees")).ToList();
            var grass = kit.FindPrefabs("grass", "Trees").Concat(kit.FindPrefabs("susuki", "Trees")).Concat(kit.FindPrefabs("weeds", "Trees")).ToList();
            var ferns = kit.FindPrefabs("fern", "Trees");
            var rocks = kit.FindPrefabs("rock_mossy", "Trees");
            var cliffs = kit.FindPrefabs("cliff", "Trees");
            var litter = kit.FindPrefabs("litter_autumn", "Trees");

            var scatter = new Dictionary<GameObject, List<Matrix4x4>>();
            void Add(GameObject prefab, Vector3 p, float scale, float yaw, float tilt = 0f)
            {
                if (prefab == null) return;
                if (!scatter.TryGetValue(prefab, out var l)) scatter[prefab] = l = new List<Matrix4x4>();
                l.Add(Matrix4x4.TRS(p, Quaternion.Euler(tilt * kit.R(-1f, 1f), yaw, tilt * kit.R(-1f, 1f)), Vector3.one * scale));
            }
            bool GoodGround(float x, float z, out float y, out float slope)
            {
                float fx = (x - x0) / Cell, fz = (z - z0) / Cell;
                int ix = Mathf.Clamp(Mathf.RoundToInt(fx), 1, nx - 2), iz = Mathf.Clamp(Mathf.RoundToInt(fz), 1, nz - 2);
                y = HeightAt(x, z);
                slope = 1f - NormalAt(ix, iz).y;
                return RiverDist(x, z) > 20f;
            }
            // cedar forest: dense near the road, sparse far
            for (float x = x0 + 10; x < x1 - 10; x += 8f)
                for (float z = z0 + 10; z < z1 - 10; z += 8f)
                {
                    float px = x + kit.R(-3.5f, 3.5f), pz = z + kit.R(-3.5f, 3.5f);
                    float dRoad = Nearest(px, pz, out _);
                    if (dRoad < edge + 6.5f) continue;
                    bool far = dRoad > 230f;
                    if (far && kit.Chance(0.72f)) continue;
                    if (!GoodGround(px, pz, out float y, out float slope) || slope > 0.42f) continue;
                    float forest = Mathf.PerlinNoise(px * 0.012f + 5f, pz * 0.012f + 9f);
                    if (forest < 0.32f && kit.Chance(0.8f)) continue;
                    if (sugi.Count > 0) Add(kit.Pick(sugi), new Vector3(px, y - 0.3f, pz), kit.R(0.75f, 1.25f), kit.R(0, 360), 2f);
                }
            // momiji + ginkgo lining the road
            for (float d = 0; d < t.length; d += 5.5f)
            {
                int i = t.IndexAt(d);
                foreach (int side in new[] { -1, 1 })
                {
                    if (!kit.Chance(0.8f)) continue;
                    float off = edge + kit.R(4.0f, 22f);
                    Vector3 p = t.pts[i] + t.right[i] * side * off;
                    if (Nearest(p.x, p.z, out _) < edge + 4f) continue;
                    if (!GoodGround(p.x, p.z, out float y, out float slope) || slope > 0.5f) continue;
                    var list = kit.Chance(0.82f) ? momiji : ginkgo;
                    if (list.Count > 0) Add(kit.Pick(list), new Vector3(p.x, y - 0.2f, p.z), kit.R(0.8f, 1.2f), kit.R(0, 360), 3f);
                }
            }
            // momiji groves on the visible slopes (the autumn fire)
            for (int k = 0; k < 1400 && momiji.Count > 0; k++)
            {
                float px = kit.R(mn.x - 260, mx.x + 260), pz = kit.R(mn.z - 260, mx.z + 260);
                float dRoad = Nearest(px, pz, out _);
                if (dRoad < edge + 8f || dRoad > 260f) continue;
                if (Mathf.PerlinNoise(px * 0.02f + 40f, pz * 0.02f + 11f) < 0.45f) continue;
                if (!GoodGround(px, pz, out float y, out float slope) || slope > 0.5f) continue;
                Add(kit.Pick(momiji), new Vector3(px, y - 0.2f, pz), kit.R(0.9f, 1.35f), kit.R(0, 360), 3f);
            }
            // fallen-leaf patches along the shoulders
            for (float d = 0; d < t.length && litter.Count > 0; d += 3f)
            {
                int i = t.IndexAt(d);
                foreach (int side in new[] { -1, 1 })
                {
                    Vector3 p = t.pts[i] + t.right[i] * side * (edge + kit.R(1.6f, 4f));
                    if (!GoodGround(p.x, p.z, out float y, out _)) continue;
                    Add(kit.Pick(litter), new Vector3(p.x, y + 0.03f, p.z), kit.R(0.8f, 1.3f), kit.R(0, 360));
                }
            }
            // cliff faces in the gorge
            for (int k = 0; k < 120 && cliffs.Count > 0; k++)
            {
                var rp = river[kit.RI(0, river.Count)];
                Vector3 p = rp + new Vector3(kit.R(-1, 1), 0, kit.R(-1, 1)).normalized * kit.R(18f, 40f);
                if (Nearest(p.x, p.z, out _) < edge + 10f) continue;
                Add(kit.Pick(cliffs), new Vector3(p.x, HeightAt(p.x, p.z) - 2f, p.z), kit.R(0.9f, 1.8f), kit.R(0, 360), 6f);
            }
            // bamboo patches in the low valley
            for (int k = 0; k < 160 && bamboo.Count > 0; k++)
            {
                float px = kit.R(x0 + 200, x1 - 200), pz = kit.R(mn.z - 100, mn.z + 60);
                float dRoad = Nearest(px, pz, out _);
                if (dRoad < edge + 5f || dRoad > 120f) continue;
                if (!GoodGround(px, pz, out float y, out float slope) || slope > 0.45f) continue;
                Add(kit.Pick(bamboo), new Vector3(px, y, pz), kit.R(0.9f, 1.2f), kit.R(0, 360));
            }
            // undergrowth along the road edges
            for (float d = 0; d < t.length; d += 1.6f)
            {
                int i = t.IndexAt(d);
                foreach (int side in new[] { -1, 1 })
                {
                    float off = edge + kit.R(2.8f, 11f);
                    Vector3 p = t.pts[i] + t.right[i] * side * off + t.tan[i] * kit.R(-0.8f, 0.8f);
                    if (Nearest(p.x, p.z, out _) < edge + 2.6f) continue;
                    if (!GoodGround(p.x, p.z, out float y, out float slope) || slope > 0.55f) continue;
                    float rr = (float)kit.rng.NextDouble();
                    if (rr < 0.55f && grass.Count > 0) Add(kit.Pick(grass), new Vector3(p.x, y, p.z), kit.R(0.8f, 1.4f), kit.R(0, 360));
                    else if (rr < 0.75f && ferns.Count > 0) Add(kit.Pick(ferns), new Vector3(p.x, y, p.z), kit.R(0.8f, 1.3f), kit.R(0, 360));
                    else if (rr < 0.85f && shrubs.Count > 0) Add(kit.Pick(shrubs), new Vector3(p.x, y - 0.1f, p.z), kit.R(0.7f, 1.2f), kit.R(0, 360));
                }
            }
            // rocks on steep ground + boulders in the gorge
            for (int k = 0; k < 900 && rocks.Count > 0; k++)
            {
                float px = kit.R(x0 + 20, x1 - 20), pz = kit.R(z0 + 20, z1 - 20);
                if (Nearest(px, pz, out _) < edge + 4f) continue;
                float y = HeightAt(px, pz);
                float fx = (px - x0) / Cell, fz = (pz - z0) / Cell;
                float slope = 1f - NormalAt(Mathf.Clamp((int)fx, 1, nx - 2), Mathf.Clamp((int)fz, 1, nz - 2)).y;
                bool gorge = RiverDist(px, pz) < 30f;
                if (slope < 0.25f && !gorge) continue;
                Add(kit.Pick(rocks), new Vector3(px, y - 0.4f, pz), gorge ? kit.R(1.2f, 3.5f) : kit.R(0.8f, 2.2f), kit.R(0, 360), 10f);
            }

            foreach (var kv in scatter) AddLayer(fd, kv.Key, kv.Value);
            kit.SaveObject(fd, "Foliage");
            foreach (var l in fd.layers) EditorUtility.SetDirty(fd);
            var fr = new GameObject("Foliage").AddComponent<FoliageRenderer>();
            fr.transform.SetParent(root, false);
            fr.data = fd;
            Debug.Log($"[Mountain] foliage instances: {string.Join(", ", fd.layers.Select(l => l.name + "=" + l.instances.Length))}");
        }

        /// <summary>Turn a prefab + world matrices into a FoliageData layer (LOD0/LOD1 from the prefab's renderers).</summary>
        public static void AddLayer(FoliageData fd, GameObject prefab, List<Matrix4x4> mats)
        {
            var renderers = prefab.GetComponentsInChildren<MeshRenderer>(true);
            MeshRenderer lod0 = null, lod1 = null;
            foreach (var r in renderers)
            {
                if (r.name.ToLowerInvariant().Contains("lod1")) lod1 = r;
                else if (lod0 == null) lod0 = r;
            }
            if (lod0 == null) return;
            var mf0 = lod0.GetComponent<MeshFilter>();
            var layer = new FoliageData.Layer
            {
                name = prefab.name,
                mesh = mf0.sharedMesh,
                materials = lod0.sharedMaterials,
                meshOffset = prefab.transform.worldToLocalMatrix * lod0.transform.localToWorldMatrix,
                castShadows = !prefab.name.Contains("grass") && !prefab.name.Contains("fern") && !prefab.name.Contains("susuki"),
            };
            string n = prefab.name.ToLowerInvariant();
            layer.lodDistance = n.Contains("sugi") ? 120f : 70f;
            layer.cullDistance = n.Contains("sugi") ? 1100f : n.Contains("grass") || n.Contains("fern") || n.Contains("susuki") ? 110f : n.Contains("rock") || n.Contains("boulder") ? 500f : 650f;
            if (lod1 != null)
            {
                layer.lodMesh = lod1.GetComponent<MeshFilter>().sharedMesh;
                layer.lodMaterials = lod1.sharedMaterials;
                layer.lodOffset = prefab.transform.worldToLocalMatrix * lod1.transform.localToWorldMatrix;
            }
            // bucket into cells
            var cells = new Dictionary<Vector2Int, List<Matrix4x4>>();
            foreach (var m in mats)
            {
                var k = new Vector2Int(Mathf.FloorToInt(m.m03 / fd.cellSize), Mathf.FloorToInt(m.m23 / fd.cellSize));
                if (!cells.TryGetValue(k, out var l)) cells[k] = l = new List<Matrix4x4>();
                l.Add(m);
            }
            var all = new List<Matrix4x4>();
            var starts = new List<int>(); var counts = new List<int>(); var bounds = new List<Bounds>();
            var mb = mf0.sharedMesh.bounds;
            float rad = mb.extents.magnitude * 1.3f;
            foreach (var kv in cells)
            {
                starts.Add(all.Count); counts.Add(kv.Value.Count);
                var b = new Bounds(new Vector3(kv.Value[0].m03, kv.Value[0].m13, kv.Value[0].m23), Vector3.zero);
                foreach (var m in kv.Value) b.Encapsulate(new Vector3(m.m03, m.m13 + mb.center.y, m.m23));
                b.Expand(rad * 2f);
                bounds.Add(b);
                all.AddRange(kv.Value);
            }
            layer.instances = all.ToArray(); layer.cellStart = starts.ToArray(); layer.cellCount = counts.ToArray(); layer.cellBounds = bounds.ToArray();
            fd.layers.Add(layer);
        }
    }
}
