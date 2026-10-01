using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>
    /// Procedural Japanese city buildings. Geometry goes into per-chunk MeshBuilders whose submeshes map to:
    /// facades[0..n-1], shop strip, roof, sign atlas, sign frame, billboard atlas, metal.
    /// </summary>
    public class BuildingKit
    {
        public class Lot { public Vector3 center; public Quaternion rot; public float w, d; public Vector2[] corners; }

        public readonly List<Material> facades = new List<Material>();
        public readonly List<string> facadeNames = new List<string>();
        public Material shop, roof, frame, metal, glassTower;
        public SignAtlas signs, billboards;
        public int SubFacade(int i) => i;
        public int SubShop => facades.Count;
        public int SubRoof => facades.Count + 1;
        public int SubSign => facades.Count + 2;
        public int SubFrame => facades.Count + 3;
        public int SubBillboard => facades.Count + 4;
        public int SubMetal => facades.Count + 5;
        public Material[] Materials;
        public float tileH = 14f;     // default metres per facade tile (overridden per set below)
        public float floorH = 3.5f;
        public float shopH = 4.5f;
        public float shopTileW = 9f;
        public readonly List<float> tileSize = new List<float>();
        static readonly Dictionary<string, float> KnownTile = new Dictionary<string, float>
        {
            { "glass_office", 15.2f }, { "zakkyo_tile", 12.8f }, { "concrete_apartment", 11.6f }, { "brick_mansion", 12f },
            { "dark_glass_tower", 16f }, { "parking_garage", 11.2f },
        };
        readonly List<Lot> lots = new List<Lot>();
        bool night;

        public BuildingKit(bool night, float emissionBoost = 1f)
        {
            this.night = night;
            string dir = "Assets/InkDrift/Art/Facades";
            string full = Path.GetFullPath(dir);
            if (Directory.Exists(full))
            {
                foreach (var f in Directory.GetFiles(full, "*_albedo.png"))
                {
                    string set = Path.GetFileName(f).Replace("_albedo.png", "");
                    var m = MaterialLibrary.Ensure($"Toon_Facade_{set}" + (night ? "_Night" : "_Day"));
                    MaterialLibrary.ApplyTextures(m,
                        AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{set}_albedo.png"),
                        AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{set}_normal.png"),
                        AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{set}_mask.png"),
                        AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{set}_emission.png"));
                    bool hasEm = File.Exists(Path.GetFullPath($"{dir}/{set}_emission.png"));
                    MaterialLibrary.SetKeyword(m, "_EMISSION", "_UseEmission", hasEm);
                    m.SetColor("_EmissionColor", (night ? new Color(2.2f, 2.0f, 1.8f) : new Color(0.0f, 0.0f, 0.0f)) * emissionBoost);
                    m.SetFloat("_Smoothness", 0.55f);
                    m.SetFloat("_ReflectStrength", 0.35f);
                    m.SetFloat("_Metallic", 0.2f);
                    EditorUtility.SetDirty(m);
                    if (set.Contains("shop") || set.Contains("ground") || set.Contains("street")) shop = m;
                    else { facades.Add(m); facadeNames.Add(set); tileSize.Add(KnownTile.TryGetValue(set, out var ts) ? ts : tileH); }
                }
            }
            if (facades.Count == 0)
            {
                facades.Add(MaterialLibrary.Flat("Toon_FacadeFallbackA", new Color(0.82f, 0.78f, 0.72f)));
                facades.Add(MaterialLibrary.Flat("Toon_FacadeFallbackB", new Color(0.45f, 0.55f, 0.7f), 0.8f, 0.3f, null, 0.5f));
                facadeNames.Add("fallback_a"); facadeNames.Add("fallback_b"); tileSize.Add(tileH); tileSize.Add(tileH);
            }
            if (shop == null)
            {
                shop = facades[0];
            }
            roof = MaterialLibrary.FromSet("concrete_weathered", "Toon_Roof", 6f, 0.2f);
            frame = MaterialLibrary.Flat("Toon_SignFrame", new Color(0.15f, 0.15f, 0.18f), 0.5f, 0.5f);
            metal = MaterialLibrary.FromSet("metal_galvanized", "Toon_Galvanized", 3f, 0.6f, 0.7f);
            signs = SignAtlas.Build("SignAtlas", "Assets/InkDrift/Art/Signs", n => !n.StartsWith("bb_") && !n.StartsWith("vending_"), 0.5f, night);
            billboards = SignAtlas.Build("BillboardAtlas", "Assets/InkDrift/Art/Signs", n => n.StartsWith("bb_"), 0.5f, night);
            var mats = new List<Material>(facades) { shop, roof, signs.material ?? frame, frame, billboards.material ?? frame, metal };
            Materials = mats.ToArray();
        }

        public int FacadeIndex(string contains, System.Random rng)
        {
            var idx = new List<int>();
            for (int i = 0; i < facadeNames.Count; i++) if (facadeNames[i].Contains(contains)) idx.Add(i);
            return idx.Count > 0 ? idx[rng.Next(idx.Count)] : rng.Next(facades.Count);
        }

        // ---------------------------------------------------------------- lot bookkeeping (OBB overlap)
        public static Vector2[] Corners(Vector3 c, Quaternion r, float w, float d)
        {
            Vector3 x = r * Vector3.right * (w * 0.5f), z = r * Vector3.forward * (d * 0.5f);
            Vector3[] p = { c - x - z, c + x - z, c + x + z, c - x + z };
            var o = new Vector2[4];
            for (int i = 0; i < 4; i++) o[i] = new Vector2(p[i].x, p[i].z);
            return o;
        }

        static bool Overlap(Vector2[] a, Vector2[] b)
        {
            foreach (var poly in new[] { a, b })
                for (int i = 0; i < 4; i++)
                {
                    Vector2 e = poly[(i + 1) % 4] - poly[i];
                    Vector2 axis = new Vector2(-e.y, e.x).normalized;
                    float amin = float.MaxValue, amax = float.MinValue, bmin = float.MaxValue, bmax = float.MinValue;
                    foreach (var p in a) { float d = Vector2.Dot(p, axis); amin = Mathf.Min(amin, d); amax = Mathf.Max(amax, d); }
                    foreach (var p in b) { float d = Vector2.Dot(p, axis); bmin = Mathf.Min(bmin, d); bmax = Mathf.Max(bmax, d); }
                    if (amax < bmin + 0.05f || bmax < amin + 0.05f) return false;
                }
            return true;
        }

        readonly Dictionary<Vector2Int, List<Lot>> grid = new Dictionary<Vector2Int, List<Lot>>();
        static Vector2Int Cell(Vector2 p) => new Vector2Int(Mathf.FloorToInt(p.x / 40f), Mathf.FloorToInt(p.y / 40f));

        public bool TryReserve(Vector3 center, Quaternion rot, float w, float d, out Lot lot)
        {
            var c = Corners(center, rot, w, d);
            lot = null;
            var cc = Cell(new Vector2(center.x, center.z));
            for (int x = -1; x <= 1; x++)
                for (int y = -1; y <= 1; y++)
                    if (grid.TryGetValue(new Vector2Int(cc.x + x, cc.y + y), out var list))
                        foreach (var o in list) if (Overlap(c, o.corners)) return false;
            lot = new Lot { center = center, rot = rot, w = w, d = d, corners = c };
            if (!grid.TryGetValue(cc, out var l)) grid[cc] = l = new List<Lot>();
            l.Add(lot);
            lots.Add(lot);
            return true;
        }

        public void ReserveKeepOut(Vector3 center, Quaternion rot, float w, float d)
        {
            var lot = new Lot { center = center, rot = rot, w = w, d = d, corners = Corners(center, rot, w, d) };
            var cc = Cell(new Vector2(center.x, center.z));
            // keep-outs may be large: register in all covered cells
            float r = Mathf.Max(w, d) * 0.5f;
            int span = Mathf.CeilToInt(r / 40f);
            for (int x = -span; x <= span; x++)
                for (int y = -span; y <= span; y++)
                {
                    var k = new Vector2Int(cc.x + x, cc.y + y);
                    if (!grid.TryGetValue(k, out var l)) grid[k] = l = new List<Lot>();
                    l.Add(lot);
                }
        }

        // ---------------------------------------------------------------- building geometry
        /// <summary>Building on a lot. Front face = lot's -Z side (toward the street). groundY = base height.</summary>
        public void AddBuilding(MeshBuilder mb, PropKit kit, Lot lot, float height, int facade, bool shopFront, bool details, Color tint, List<Vector3> neonLights, float groundY)
        {
            var r = lot.rot;
            Vector3 X = r * Vector3.right, Z = r * Vector3.forward;
            Vector3 c = new Vector3(lot.center.x, groundY, lot.center.z);
            float w = lot.w, d = lot.d;
            float h = height;
            int fs = SubFacade(facade);
            float tile = facade < tileSize.Count ? tileSize[facade] : tileH;
            float u0 = kit.R(0f, 1f);   // random facade phase so neighbors differ

            // walls: front(-Z), right(+X), back(+Z), left(-X)
            Vector3[] wallOrigin = { c - Z * d / 2 - X * w / 2, c + X * w / 2 - Z * d / 2, c + Z * d / 2 + X * w / 2, c - X * w / 2 + Z * d / 2 };
            Vector3[] wallDir = { X, Z, -X, -Z };
            float[] wallLen = { w, d, w, d };
            for (int k = 0; k < 4; k++)
            {
                Vector3 o = wallOrigin[k], dir = wallDir[k];
                float len = wallLen[k];
                float yStart = 0f;
                if (shopFront && k == 0)
                {
                    // ground-floor shop strip, 1 texture repeat per ~shopH*2 meters
                    float su = len / shopTileW;
                    mb.Quad(SubShop, o, o + Vector3.up * shopH, o + dir * len + Vector3.up * shopH, o + dir * len, new Vector2(u0, 0), new Vector2(u0 + su, 1), tint);
                    yStart = shopH;
                }
                float vs = yStart / tile, ve = h / tile;
                mb.Quad(fs, o + Vector3.up * yStart, o + Vector3.up * h, o + dir * len + Vector3.up * h, o + dir * len + Vector3.up * yStart,
                    new Vector2(u0, vs), new Vector2(u0 + len / tile, ve), tint);
            }
            // roof + parapet
            Vector3 top = c + Vector3.up * h;
            mb.Quad(SubRoof, top - X * w / 2 - Z * d / 2, top - X * w / 2 + Z * d / 2, top + X * w / 2 + Z * d / 2, top + X * w / 2 - Z * d / 2, Vector2.zero, new Vector2(w / 6f, d / 6f), Color.white);
            float pt = 0.25f, ph = 0.9f;
            mb.Box(SubRoof, top + Vector3.up * ph / 2 - Z * (d / 2 - pt / 2), r, new Vector3(w, ph, pt), 3f, Color.white);
            mb.Box(SubRoof, top + Vector3.up * ph / 2 + Z * (d / 2 - pt / 2), r, new Vector3(w, ph, pt), 3f, Color.white);
            mb.Box(SubRoof, top + Vector3.up * ph / 2 - X * (w / 2 - pt / 2), r, new Vector3(pt, ph, d - pt * 2), 3f, Color.white);
            mb.Box(SubRoof, top + Vector3.up * ph / 2 + X * (w / 2 - pt / 2), r, new Vector3(pt, ph, d - pt * 2), 3f, Color.white);

            if (!details) return;

            // rooftop clutter: stair/elevator housing, water tank, AC units
            if (kit.Chance(0.8f))
            {
                float hw2 = kit.R(2.5f, 4f), hd2 = kit.R(2.5f, 4f), hh = kit.R(2.6f, 3.6f);
                mb.Box(SubRoof, top + X * kit.R(-w / 4, w / 4) + Z * kit.R(0, d / 4) + Vector3.up * hh / 2, r, new Vector3(hw2, hh, hd2), 3f, Color.white);
            }
            if (kit.Chance(0.45f))
            {
                Vector3 tp = top + X * kit.R(-w / 3, w / 3) + Z * kit.R(-d / 4, d / 3);
                // water tank on legs
                mb.Box(SubMetal, tp + Vector3.up * 2.8f, r, new Vector3(2.4f, 1.8f, 2.4f), 2f, new Color(0.85f, 0.88f, 0.9f));
                for (int k = 0; k < 4; k++) mb.Box(SubMetal, tp + X * ((k % 2) * 2 - 1) * 1.0f + Z * ((k / 2) * 2 - 1) * 1.0f + Vector3.up * 0.95f, r, new Vector3(0.12f, 1.9f, 0.12f), 1f, Color.white);
            }
            int acs = kit.RI(0, 5);
            for (int k = 0; k < acs; k++)
            {
                Vector3 ap = top + X * kit.R(-w / 2 + 1, w / 2 - 1) + Z * kit.R(-d / 2 + 1, d / 2 - 1) + Vector3.up * 0.45f;
                mb.Box(SubMetal, ap, r * Quaternion.Euler(0, kit.RI(0, 4) * 90, 0), new Vector3(0.9f, 0.7f, 0.35f), 1f, new Color(0.9f, 0.9f, 0.86f));
            }
            // side-wall AC units (the classic Tokyo look)
            int sideAcs = kit.RI(0, (int)(h / floorH));
            for (int k = 0; k < sideAcs; k++)
            {
                bool right = kit.Chance(0.5f);
                Vector3 wallC = c + X * (right ? w / 2 + 0.2f : -w / 2 - 0.2f);
                Vector3 ap = wallC + Z * kit.R(-d / 2 + 1, d / 2 - 1) + Vector3.up * (shopFront ? shopH : 0f) + Vector3.up * floorH * kit.RI(0, Mathf.Max(1, (int)((h - shopH) / floorH))) + Vector3.up * 0.5f;
                mb.Box(SubMetal, ap, r, new Vector3(0.35f, 0.65f, 0.85f), 1f, new Color(0.9f, 0.9f, 0.86f));
            }

            // projecting vertical signs stacked on the front corner (perpendicular to the street)
            if (signs.entries.Count > 0 && shopFront && kit.Chance(0.85f))
            {
                int stack = kit.RI(1, 4);
                float y = shopH + 0.6f;
                bool leftCorner = kit.Chance(0.5f);
                Vector3 anchor = c - Z * (d / 2) + X * (leftCorner ? -w / 2 + 0.9f : w / 2 - 0.9f);
                for (int s = 0; s < stack && y < h - 1.5f; s++)
                {
                    var e = signs.Pick(kit.rng, true);
                    float sh = Mathf.Min(kit.R(3.5f, 8f), h - y - 0.8f);
                    if (sh < 2.5f) break;
                    float sw = Mathf.Clamp(sh * e.aspect, 0.8f, 1.6f);
                    Vector3 sc = anchor - Z * (sw / 2 + 0.25f) + Vector3.up * (y + sh / 2);
                    signs.AddSign(mb, SubSign, SubFrame, e, sc, X, Vector3.up, sw, sh, 0.3f, Color.white);
                    if (night && neonLights != null && kit.Chance(0.5f)) neonLights.Add(sc - Z * 1.2f);
                    y += sh + 0.4f;
                }
            }
            // flush horizontal sign above the shop strip
            if (signs.entries.Count > 0 && shopFront && kit.Chance(0.7f))
            {
                var e = signs.Pick(kit.rng, false);
                float sh = 1.1f, sw = Mathf.Min(w - 1f, sh * Mathf.Max(e.aspect, 1f));
                Vector3 sc = c - Z * (d / 2 + 0.2f) + Vector3.up * (shopH + 0.75f) + X * kit.R(-(w - sw) / 2, (w - sw) / 2);
                signs.AddSign(mb, SubSign, SubFrame, e, sc, -Z, Vector3.up, sw, sh, 0.2f, Color.white);
            }
            // rooftop billboard
            if (billboards.entries.Count > 0 && kit.Chance(h > 18f ? 0.35f : 0.15f))
            {
                var e = billboards.Pick(kit.rng);
                float bw = Mathf.Min(w * 0.9f, 14f), bh = bw / Mathf.Max(1.2f, e.aspect);
                Vector3 bc = top - Z * (d / 2 - 1.5f) + Vector3.up * (bh / 2 + 2.2f);
                billboards.AddSign(mb, SubBillboard, SubFrame, e, bc, -Z, Vector3.up, bw, bh, 0.4f, Color.white);
                // lattice legs
                for (int k = -1; k <= 1; k += 2)
                    mb.Box(SubMetal, top - Z * (d / 2 - 1.5f) + X * k * bw * 0.35f + Vector3.up * 1.1f, r, new Vector3(0.2f, 2.2f, 0.2f), 1f, Color.white);
                if (night && neonLights != null) neonLights.Add(bc - Z * 3f - Vector3.up * bh * 0.4f);
            }
        }

        /// <summary>Tall background tower with setbacks (no shop strip).</summary>
        public void AddTower(MeshBuilder mb, PropKit kit, Lot lot, float height, int facade, Color tint, float groundY)
        {
            float h1 = height * kit.R(0.55f, 0.8f);
            AddBuilding(mb, kit, lot, h1, facade, false, false, tint, null, groundY);
            var top = new Lot { center = lot.center, rot = lot.rot, w = lot.w * kit.R(0.6f, 0.85f), d = lot.d * kit.R(0.6f, 0.85f) };
            top.corners = Corners(top.center, top.rot, top.w, top.d);
            // second tier built from h1 upward: shift by building at groundY+h1
            AddBuilding(mb, kit, top, height - h1, facade, false, false, tint, null, groundY + h1);
            // aircraft warning light / crown
            Vector3 c = new Vector3(lot.center.x, groundY + height, lot.center.z);
            mb.Box(SubMetal, c + Vector3.up * 1.5f, lot.rot, new Vector3(top.w * 0.5f, 3f, top.d * 0.5f), 2f, Color.white);
        }
    }
}
