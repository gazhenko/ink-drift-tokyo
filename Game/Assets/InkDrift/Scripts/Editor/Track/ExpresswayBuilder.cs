using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>SHUTO C1 LOOP: elevated expressway at sunset through a dense city, with tunnels, gantries and landmark towers.</summary>
    public static class ExpresswayBuilder
    {
        public static void Build(PropKit kit, TrackLayout t, TrackDef def, Transform root)
        {
            float hw = def.roadHalfWidth;
            float gutter = 0.9f;
            float edge = hw + gutter;
            var gRoad = PropKit.Group("Expressway", root);
            var gCity = PropKit.Group("City", root);
            var gProps = PropKit.Group("Props", root);
            var gLights = PropKit.Group("Lights", root);

            var asphalt = MaterialLibrary.FromSet("road_asphalt_highway", "Toon_Highway", 5f, 0.35f);
            asphalt.SetTextureScale("_BaseMap", Vector2.one);
            asphalt.SetColor("_BaseColor", new Color(1.3f, 1.3f, 1.35f));
            var concrete = MaterialLibrary.FromSet("concrete_smooth", "Toon_ConcreteSmooth", 1f, 0.25f);
            concrete.SetTextureScale("_BaseMap", Vector2.one);
            var girder = MaterialLibrary.FromSet("metal_painted", "Toon_Girder", 1f, 0.35f);
            girder.SetTextureScale("_BaseMap", Vector2.one);
            var barrierGlass = MaterialLibrary.Flat("Toon_SoundBarrier", new Color(0.55f, 0.8f, 0.72f), 0.85f, 0.1f, null, 0.7f);
            var white = MaterialLibrary.Flat("Toon_PaintWhite", new Color(0.92f, 0.92f, 0.88f), 0.45f);
            var yellow = MaterialLibrary.Flat("Toon_PaintYellow", new Color(1f, 0.78f, 0.1f), 0.45f);
            var sodium = MaterialLibrary.Flat("Toon_SodiumLamp", new Color(1f, 0.6f, 0.2f), 0.5f, 0f, new Color(6f, 3f, 0.8f));
            var signGreen = MaterialLibrary.Flat("Toon_SignGreen", new Color(0.05f, 0.42f, 0.25f), 0.4f);
            var ground = MaterialLibrary.FromSet("road_asphalt_fresh", "Toon_Ground", 1f, 0.3f);
            MaterialLibrary.SetKeyword(ground, "_WORLD_UV", "_WorldUV", true); ground.SetFloat("_WorldUVScale", 0.2f);
            var phys = new PhysicsMaterial("Asphalt") { dynamicFriction = 0.8f, staticFriction = 0.8f };
            kit.SaveObject(phys, "Asphalt");

            // tunnel ranges (fractions of the lap)
            var tunnels = new List<Vector2> { new Vector2(0.44f, 0.53f) };
            bool InTunnel(float d) { float f = d / t.length; foreach (var r in tunnels) if (f > r.x && f < r.y) return true; return false; }

            int chunk = 50;
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var road = new MeshBuilder();
                road.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge, 0f), new Vector2(0, 0.05f), new Vector2(edge, 0f) }, 5f, 5f, Color.white);
                kit.MeshObject($"Deck_{i0}", gRoad, road, new[] { asphalt }, true, true, 9, phys);

                var st = new MeshBuilder();
                // deck slab underside + edge fascia
                st.Sweep(0, t, i0, cnt, new[] { new Vector2(edge + 0.6f, -0.05f), new Vector2(edge + 0.6f, -1.6f), new Vector2(-edge - 0.6f, -1.6f), new Vector2(-edge - 0.6f, -0.05f) }, 2f, 2f, Color.white);
                // parapets (inside on the left: right wall goes bottom->top, left wall top->bottom)
                st.Sweep(0, t, i0, cnt, new[] { new Vector2(edge, 0f), new Vector2(edge, 0.85f), new Vector2(edge + 0.25f, 1.05f), new Vector2(edge + 0.6f, 1.05f), new Vector2(edge + 0.6f, -0.05f) }, 1f, 2f, Color.white);
                st.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge - 0.6f, -0.05f), new Vector2(-edge - 0.6f, 1.05f), new Vector2(-edge - 0.25f, 1.05f), new Vector2(-edge, 0.85f), new Vector2(-edge, 0f) }, 1f, 2f, Color.white);
                kit.MeshObject($"Parapet_{i0}", gRoad, st, new[] { concrete }, true, true);

                // sound barriers on stretches near buildings (both faces)
                float dm = t.dist[t.Wrap(i0 + cnt / 2)];
                if (!InTunnel(dm) && Mathf.PerlinNoise(dm * 0.003f, 1.7f) > 0.45f)
                {
                    var sb = new MeshBuilder();
                    foreach (int side in new[] { -1, 1 })
                    {
                        float x = side * (edge + 0.42f);
                        sb.Sweep(0, t, i0, cnt, side > 0 ? new[] { new Vector2(x, 1.05f), new Vector2(x, 3.6f) } : new[] { new Vector2(x, 3.6f), new Vector2(x, 1.05f) }, 2f, 2f, Color.white);
                        sb.Sweep(0, t, i0, cnt, side > 0 ? new[] { new Vector2(x + 0.05f, 3.6f), new Vector2(x + 0.05f, 1.05f) } : new[] { new Vector2(x - 0.05f, 1.05f), new Vector2(x - 0.05f, 3.6f) }, 2f, 2f, Color.white);
                    }
                    kit.MeshObject($"Barrier_{i0}", gRoad, sb, new[] { barrierGlass }, false, false);
                }
            }

            // markings: edge lines, dashed lane split, chevrons near tunnel mouths
            var mk = new MeshBuilder();
            void Strip(int sub, float x, float w, float d0, float d1)
            {
                int a = t.IndexAt(d0), b = t.IndexAt(d1);
                int n = t.Wrap(b - a); if (n < 1) return;
                mk.Sweep(sub, t, a, n, new[] { new Vector2(x - w / 2, 0.055f), new Vector2(x + w / 2, 0.055f) }, 1f, 1f, Color.white);
            }
            for (float d = 0; d < t.length; d += 8f) { Strip(0, hw - 0.2f, 0.18f, d, Mathf.Min(d + 8f, t.length - 0.1f)); Strip(1, -hw + 0.2f, 0.18f, d, Mathf.Min(d + 8f, t.length - 0.1f)); }
            for (float d = 0; d < t.length; d += 20f) Strip(0, 0f, 0.15f, d, d + 8f);
            kit.MeshObject("Markings", gRoad, mk, new[] { white, yellow }, false, false);

            // piers every ~32 m (skip in tunnels)
            var pierPrefab = kit.FindPrefab("shuto_pier");
            var pm = new MeshBuilder();
            for (float d = 6f; d < t.length; d += 32f)
            {
                if (InTunnel(d)) continue;
                int i = t.IndexAt(d);
                Vector3 p = t.pts[i];
                float h = p.y - 1.6f;
                var rot = Quaternion.LookRotation(t.right[i]);
                if (pierPrefab != null)
                {
                    // cap spans Unity Z (16 m) -> align Z across the road
                    var inst = kit.Place(pierPrefab, new Vector3(p.x, 0f, p.z), Quaternion.LookRotation(t.right[i]), gRoad);
                    inst.transform.localScale = new Vector3(1f, h / 12.55f, (edge * 2f + 1.6f) / 16f);
                }
                else
                {
                    pm.Box(0, new Vector3(p.x, h * 0.5f - 0.6f, p.z), rot, new Vector3(2.2f, h - 1.2f, 2.2f), 2f, Color.white);
                    pm.Box(0, new Vector3(p.x, h - 0.6f, p.z), rot, new Vector3(edge * 2f + 1.4f, 1.3f, 2.4f), 2f, Color.white);
                }
            }
            kit.MeshObject("Piers", gRoad, pm, new[] { concrete }, true, true);

            // twin-arm lights every 45 m
            var lightPole = kit.FindPrefab("shuto_light_pole");
            var lp = new MeshBuilder();
            for (float d = 12f; d < t.length; d += 45f)
            {
                if (InTunnel(d)) continue;
                int i = t.IndexAt(d);
                Vector3 c = t.pts[i];
                if (lightPole) kit.Place(lightPole, c + t.right[i] * (edge + 0.42f) + Vector3.up * 1.05f, Quaternion.LookRotation(-t.right[i]), gProps);
                else
                {
                    var q = Quaternion.LookRotation(t.tan[i]);
                    Vector3 b = c + t.right[i] * (edge + 0.42f);
                    lp.Box(0, b + Vector3.up * 6f, q, new Vector3(0.22f, 10f, 0.22f), 1f, Color.white);
                    lp.Box(0, b + Vector3.up * 10.8f - t.right[i] * 1.8f, q, new Vector3(3.6f, 0.15f, 0.15f), 1f, Color.white);
                    lp.Box(1, b + Vector3.up * 10.6f - t.right[i] * 3.4f, q, new Vector3(0.7f, 0.12f, 0.35f), 1f, Color.white);
                }
                CityBuilder.AddPointLight(gLights, c + t.right[i] * (edge - 3.2f) + Vector3.up * 10f, new Color(1f, 0.75f, 0.45f), 24f, 30f);
            }
            kit.MeshObject("LightPoles", gProps, lp, new[] { girder, sodium }, false, true);

            // overhead sign gantries with route names
            var gantryTex = MakeGantryTextures(kit);
            var gm = new MeshBuilder();
            float[] gantries = { 0.12f, 0.36f, 0.62f, 0.83f };
            for (int gi = 0; gi < gantries.Length; gi++)
            {
                int i = t.IndexAt(gantries[gi] * t.length);
                Vector3 c = t.pts[i]; var q = Quaternion.LookRotation(t.tan[i]); Vector3 r = t.right[i];
                gm.Box(0, c + r * (edge + 0.9f) + Vector3.up * 3.6f, q, new Vector3(0.4f, 7.2f, 0.4f), 1f, Color.white);
                gm.Box(0, c - r * (edge + 0.9f) + Vector3.up * 3.6f, q, new Vector3(0.4f, 7.2f, 0.4f), 1f, Color.white);
                gm.Box(0, c + Vector3.up * 7.1f, q, new Vector3(edge * 2f + 2.4f, 0.5f, 0.5f), 1f, Color.white);
                // sign faces (front toward oncoming car = -tan)
                float w = edge * 1.7f, h = 2.6f;
                Vector3 sc = c + Vector3.up * 5.4f - t.tan[i] * 0.3f;
                Vector3 hx = r * w * 0.5f, hy = Vector3.up * h * 0.5f;
                float v0 = gi / 4f, v1 = (gi + 1) / 4f;
                gm.Quad(1, sc + hx - hy, sc + hx + hy, sc - hx + hy, sc - hx - hy, new Vector2(0, v0), new Vector2(1, v1), Color.white);
                gm.Box(0, sc + t.tan[i] * 0.08f, q, new Vector3(w + 0.2f, h + 0.2f, 0.12f), 1f, Color.white);
            }
            var signMat = MaterialLibrary.Ensure("Toon_GantrySigns");
            if (gantryTex) signMat.SetTexture("_BaseMap", gantryTex);
            signMat.SetColor("_BaseColor", Color.white); signMat.SetFloat("_Smoothness", 0.5f);
            if (gantryTex) { signMat.SetTexture("_EmissionMap", gantryTex); MaterialLibrary.SetKeyword(signMat, "_EMISSION", "_UseEmission", true); signMat.SetColor("_EmissionColor", new Color(0.25f, 0.25f, 0.25f)); }
            kit.MeshObject("Gantries", gProps, gm, new[] { girder, signMat }, false, true);

            // tunnels: box section with lamp strips and orange light every 10 m
            foreach (var r in tunnels)
            {
                int ia = t.IndexAt(r.x * t.length), ib = t.IndexAt(r.y * t.length);
                int n = t.Wrap(ib - ia);
                var tm = new MeshBuilder();
                float wx = edge + 0.6f, roof = 6.2f;
                tm.Sweep(0, t, ia, n, new[] { new Vector2(wx, 1.0f), new Vector2(wx, roof), new Vector2(-wx, roof), new Vector2(-wx, 1.0f) }, 2f, 2f, Color.white);
                // outer shell (seen from outside)
                tm.Sweep(0, t, ia, n, new[] { new Vector2(-wx - 0.8f, -1.6f), new Vector2(-wx - 0.8f, roof + 0.8f), new Vector2(wx + 0.8f, roof + 0.8f), new Vector2(wx + 0.8f, -1.6f) }, 2f, 2f, Color.white);
                tm.Sweep(1, t, ia, n, new[] { new Vector2(wx - 0.05f, 4.4f), new Vector2(wx - 0.05f, 4.65f) }, 1f, 1f, Color.white);
                tm.Sweep(1, t, ia, n, new[] { new Vector2(-wx + 0.05f, 4.65f), new Vector2(-wx + 0.05f, 4.4f) }, 1f, 1f, Color.white);
                kit.MeshObject("Tunnel", gRoad, tm, new[] { concrete, sodium }, true, true);
                for (int k = 0; k < n; k += 5)
                {
                    int i = t.Wrap(ia + k);
                    CityBuilder.AddPointLight(gLights, t.pts[i] + Vector3.up * 4.8f, new Color(1f, 0.55f, 0.18f), 10f, 14f);
                }
            }

            // ---------------- city below and around
            var bk = new BuildingKit(false, 1f);
            foreach (var m in bk.facades) m.SetFloat("_VertexTint", 1f);
            // sunset: windows start to glow a bit
            foreach (var m in bk.facades) m.SetColor("_EmissionColor", new Color(0.7f, 0.55f, 0.4f));
            var grid = new Dictionary<Vector2Int, List<int>>();
            for (int i = 0; i < t.Count; i++)
            {
                var k = new Vector2Int(Mathf.FloorToInt(t.pts[i].x / 25f), Mathf.FloorToInt(t.pts[i].z / 25f));
                if (!grid.TryGetValue(k, out var l)) grid[k] = l = new List<int>();
                l.Add(i);
            }
            float TrackDist(Vector3 p, out float roadY)
            {
                var k = new Vector2Int(Mathf.FloorToInt(p.x / 25f), Mathf.FloorToInt(p.z / 25f));
                float best = 1e9f; roadY = 0f;
                for (int x = -3; x <= 3; x++)
                    for (int y = -3; y <= 3; y++)
                        if (grid.TryGetValue(new Vector2Int(k.x + x, k.y + y), out var l))
                            foreach (var i in l) { float d = new Vector2(p.x - t.pts[i].x, p.z - t.pts[i].z).magnitude; if (d < best) { best = d; roadY = t.pts[i].y; } }
                return best;
            }
            var chunks = new Dictionary<Vector2Int, MeshBuilder>();
            MeshBuilder Chunk(Vector3 p)
            {
                var k = new Vector2Int(Mathf.FloorToInt(p.x / 160f), Mathf.FloorToInt(p.z / 160f));
                if (!chunks.TryGetValue(k, out var mb)) chunks[k] = mb = new MeshBuilder();
                return mb;
            }
            Vector3 mn = new Vector3(1e9f, 0, 1e9f), mx = new Vector3(-1e9f, 0, -1e9f);
            foreach (var p in t.pts) { mn = Vector3.Min(mn, p); mx = Vector3.Max(mx, p); }
            float pad = 650f;
            // ground-level streets under the expressway (simple grid)
            for (float x = mn.x - pad; x < mx.x + pad; x += 26f)
                for (float z = mn.z - pad; z < mx.z + pad; z += 26f)
                {
                    if (Mathf.Repeat(x - mn.x, 26f * 4f) < 1f || Mathf.Repeat(z - mn.z, 26f * 5f) < 1f) continue;
                    Vector3 c = new Vector3(x + kit.R(-2, 2), 0, z + kit.R(-2, 2));
                    float td = TrackDist(c, out float ry);
                    float w = kit.R(15f, 22f), dep = kit.R(15f, 22f);
                    float clearance = edge + 3f + Mathf.Max(w, dep) * 0.72f;
                    float h;
                    if (td < clearance)
                    {
                        // under the deck: only low buildings that stay below the slab
                        float under = ry - 3.5f;
                        if (under < 6f || td < edge + 2f) continue;
                        h = kit.R(4f, Mathf.Max(5f, under));
                    }
                    else
                    {
                        float far01 = Mathf.InverseLerp(30f, 600f, td);
                        float cluster = Mathf.PerlinNoise(x * 0.003f + 11f, z * 0.003f + 5f);
                        h = Mathf.Lerp(kit.R(12f, 45f), kit.R(40f, 210f) * (0.35f + cluster), far01 * (0.5f + 0.5f * cluster));
                        if (td < 60f) h = Mathf.Max(h, ry + kit.R(-6f, 25f));
                    }
                    if (!bk.TryReserve(c, Quaternion.identity, w, dep, out var lot)) continue;
                    var mb = Chunk(c);
                    if (h > 80f) bk.AddTower(mb, kit, lot, h, bk.FacadeIndex(kit.Chance(0.6f) ? "glass" : "dark", kit.rng), CityBuilder.Tint(kit), 0f);
                    else bk.AddBuilding(mb, kit, lot, h, kit.RI(0, bk.facades.Count), true, td < 120f && td > clearance, CityBuilder.Tint(kit), null, 0f);
                }
            foreach (var kv in chunks) kit.MeshObject($"Block_{kv.Key.x}_{kv.Key.y}", gCity, kv.Value, bk.Materials, false);
            {
                var gmb = new MeshBuilder();
                Vector3 a = new Vector3(mn.x - pad - 60, -0.03f, mn.z - pad - 60), b = new Vector3(mx.x + pad + 60, -0.03f, mx.z + pad + 60);
                gmb.Quad(0, new Vector3(a.x, a.y, a.z), new Vector3(a.x, a.y, b.z), new Vector3(b.x, a.y, b.z), new Vector3(b.x, a.y, a.z), Vector2.zero, Vector2.one, Color.white);
                kit.MeshObject("Ground", gCity, gmb, new[] { ground }, true, false);
            }

            // ---------------- landmarks: red/white lattice tower + a tall slender broadcast tower
            Vector3 center = (mn + mx) * 0.5f; center.y = 0;
            LatticeTower(kit, gCity, center + new Vector3(-(mx.x - mn.x) * 0.5f - 380f, 0, (mx.z - mn.z) * 0.15f), 333f, 80f, true);
            LatticeTower(kit, gCity, center + new Vector3((mx.x - mn.x) * 0.5f + 900f, 0, (mx.z - mn.z) * 0.6f + 400f), 634f, 68f, false);

            // ---------------- invisible containment above parapets
            for (int i0 = 0; i0 < t.Count; i0 += chunk)
            {
                int cnt = Mathf.Min(chunk, t.Count - i0);
                var w = new MeshBuilder();
                w.Sweep(0, t, i0, cnt, new[] { new Vector2(edge, 0f), new Vector2(edge, 5f) }, 1f, 1f, Color.white);
                w.Sweep(0, t, i0, cnt, new[] { new Vector2(-edge, 5f), new Vector2(-edge, 0f) }, 1f, 1f, Color.white);
                kit.ColliderOnly($"Containment_{i0}", gRoad, w);
            }
        }

        static void LatticeTower(PropKit kit, Transform parent, Vector3 basePos, float height, float baseWidth, bool redWhite)
        {
            var mb = new MeshBuilder();
            int levels = 26;
            Vector3[] Corners(float y)
            {
                float f = y / height;
                float w = Mathf.Lerp(baseWidth, baseWidth * 0.08f, Mathf.Pow(f, 0.62f)) * 0.5f;
                return new[] { new Vector3(-w, y, -w), new Vector3(w, y, -w), new Vector3(w, y, w), new Vector3(-w, y, w) };
            }
            float r0 = baseWidth * 0.018f;
            for (int l = 0; l < levels; l++)
            {
                float y0 = height * 0.82f * l / levels, y1 = height * 0.82f * (l + 1) / levels;
                var a = Corners(y0); var b = Corners(y1);
                int sub = redWhite ? ((l / 3) % 2) : 0;
                float rr = r0 * Mathf.Lerp(1f, 0.25f, (float)l / levels);
                for (int k = 0; k < 4; k++)
                {
                    mb.Tube(sub, new[] { basePos + a[k], basePos + b[k] }, rr, 5, Color.white);
                    mb.Tube(sub, new[] { basePos + a[k], basePos + b[(k + 1) % 4] }, rr * 0.45f, 4, Color.white);
                    mb.Tube(sub, new[] { basePos + a[(k + 1) % 4], basePos + b[k] }, rr * 0.45f, 4, Color.white);
                    if (l % 4 == 0) mb.Tube(sub, new[] { basePos + a[k], basePos + a[(k + 1) % 4] }, rr * 0.6f, 4, Color.white);
                }
                if (l == levels / 3 || l == levels * 2 / 3)
                {
                    float w = Mathf.Abs(a[0].x) * 2.4f;
                    mb.Box(2, basePos + Vector3.up * y0, Quaternion.identity, new Vector3(w, height * 0.03f, w), 4f, Color.white);
                }
            }
            // antenna mast
            mb.Tube(redWhite ? 0 : 2, new[] { basePos + Vector3.up * height * 0.82f, basePos + Vector3.up * height }, r0 * 0.35f, 6, Color.white);
            var red = MaterialLibrary.Flat("Toon_TowerRed", new Color(0.95f, 0.25f, 0.12f), 0.45f, 0.3f);
            var whiteM = MaterialLibrary.Flat("Toon_TowerWhite", new Color(0.95f, 0.95f, 0.92f), 0.45f, 0.3f);
            var deck = MaterialLibrary.Flat("Toon_TowerDeck", new Color(0.7f, 0.75f, 0.8f), 0.8f, 0.4f, new Color(0.6f, 0.5f, 0.3f), 0.6f);
            kit.MeshObject(redWhite ? "Tower_Red" : "Tower_Tall", parent, mb, redWhite ? new[] { red, whiteM, deck } : new[] { whiteM, whiteM, deck }, false, true);
        }

        static Texture2D MakeGantryTextures(PropKit kit)
        {
            // 4 stacked sign faces: green with white Japanese/English place names (generated with the HUD font if available)
            string path = "Assets/InkDrift/Generated/Common/gantry_signs.png";
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            return tex;   // produced by Tools/art/gantry_signs.py
        }
    }
}
