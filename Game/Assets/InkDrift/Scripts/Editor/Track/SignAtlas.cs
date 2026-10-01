using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Packs sign/billboard albedo + emission textures into matching atlases and exposes UV rects + aspect.</summary>
    public class SignAtlas
    {
        public class Entry { public string name; public Rect uv; public float aspect; public bool vertical; }

        public readonly List<Entry> entries = new List<Entry>();
        public Material material;
        public string Name;

        const string OutDir = "Assets/InkDrift/Generated/Common";

        public static SignAtlas Build(string atlasName, string srcDir, System.Func<string, bool> filter, float downscale, bool night)
        {
            var atlas = new SignAtlas { Name = atlasName };
            Directory.CreateDirectory(OutDir);
            string full = Path.GetFullPath(srcDir);
            if (!Directory.Exists(full)) { Debug.LogWarning("[SignAtlas] missing " + srcDir); return atlas; }
            var albedos = new List<Texture2D>();
            var emissions = new List<Texture2D>();
            foreach (var f in Directory.GetFiles(full, "*_albedo.png"))
            {
                string baseName = Path.GetFileName(f).Replace("_albedo.png", "");
                if (filter != null && !filter(baseName)) continue;
                var a = Load(f, downscale);
                string ef = f.Replace("_albedo.png", "_emission.png");
                var e = File.Exists(ef) ? Load(ef, downscale) : Black(a.width, a.height);
                if (e.width != a.width || e.height != a.height) e = Resize(e, a.width, a.height);
                albedos.Add(a); emissions.Add(e);
                atlas.entries.Add(new Entry { name = baseName, aspect = a.width / (float)a.height, vertical = a.height > a.width * 1.5f });
            }
            if (albedos.Count == 0) return atlas;
            var A = new Texture2D(2, 2, TextureFormat.RGBA32, true);
            var rects = A.PackTextures(albedos.ToArray(), 4, 4096, false);
            var E = new Texture2D(2, 2, TextureFormat.RGBA32, true);
            E.PackTextures(emissions.ToArray(), 4, 4096, false);
            for (int i = 0; i < rects.Length; i++) atlas.entries[i].uv = rects[i];
            string ap = $"{OutDir}/{atlasName}_albedo.png", ep = $"{OutDir}/{atlasName}_emission.png";
            File.WriteAllBytes(Path.GetFullPath(ap), A.EncodeToPNG());
            File.WriteAllBytes(Path.GetFullPath(ep), E.EncodeToPNG());
            AssetDatabase.ImportAsset(ap); AssetDatabase.ImportAsset(ep);
            foreach (var p in new[] { ap, ep })
            {
                var ti = (TextureImporter)AssetImporter.GetAtPath(p);
                ti.maxTextureSize = 4096; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true; ti.sRGBTexture = true;
                ti.textureCompression = TextureImporterCompression.CompressedHQ;
                ti.SaveAndReimport();
            }
            var m = MaterialLibrary.Ensure($"Toon_{atlasName}" + (night ? "_Night" : "_Day"));
            MaterialLibrary.ApplyTextures(m, AssetDatabase.LoadAssetAtPath<Texture2D>(ap), null, null, AssetDatabase.LoadAssetAtPath<Texture2D>(ep));
            m.SetColor("_BaseColor", Color.white);
            m.SetColor("_EmissionColor", night ? new Color(3.2f, 3.2f, 3.2f) : new Color(0.25f, 0.25f, 0.25f));
            MaterialLibrary.SetKeyword(m, "_EMISSION", "_UseEmission", true);
            m.SetFloat("_Smoothness", 0.6f);
            m.SetFloat("_Cull", 0);
            m.SetFloat("_HalftoneAmount", 0.3f);
            EditorUtility.SetDirty(m);
            atlas.material = m;
            return atlas;
        }

        static Texture2D Load(string file, float scale)
        {
            var t = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            t.LoadImage(File.ReadAllBytes(file));
            if (scale < 0.999f) t = Resize(t, Mathf.Max(16, (int)(t.width * scale)), Mathf.Max(16, (int)(t.height * scale)));
            return t;
        }

        static Texture2D Black(int w, int h)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var px = new Color32[w * h];
            for (int i = 0; i < px.Length; i++) px[i] = new Color32(0, 0, 0, 255);
            t.SetPixels32(px); t.Apply();
            return t;
        }

        static Texture2D Resize(Texture2D src, int w, int h)
        {
            // CPU bilinear resize (works in -nographics batch mode on GPU-less build machines)
            var dst = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5f) / h;
                for (int x = 0; x < w; x++)
                    px[y * w + x] = src.GetPixelBilinear((x + 0.5f) / w, v);
            }
            dst.SetPixels32(px);
            dst.Apply();
            return dst;
        }

        public Entry Pick(System.Random rng, bool? vertical = null)
        {
            if (entries.Count == 0) return null;
            for (int tries = 0; tries < 20; tries++)
            {
                var e = entries[rng.Next(entries.Count)];
                if (vertical == null || e.vertical == vertical.Value) return e;
            }
            return entries[rng.Next(entries.Count)];
        }

        /// <summary>Double-sided sign slab: center, facing normal (front), up, width/height, thickness.</summary>
        public void AddSign(MeshBuilder mb, int sub, int frameSub, Entry e, Vector3 center, Vector3 normal, Vector3 up, float width, float height, float thick, Color col)
        {
            Vector3 right = Vector3.Cross(up, normal).normalized;
            Vector3 hx = right * width * 0.5f, hy = up * height * 0.5f, hz = normal * thick * 0.5f;
            Vector2 u0 = e.uv.min, u1 = e.uv.max;
            // front
            Vector3 c = center + hz;
            mb.Quad(sub, c - hx - hy, c - hx + hy, c + hx + hy, c + hx - hy, u0, u1, col);
            // back (mirrored so text reads correctly from behind too)
            c = center - hz;
            mb.Quad(sub, c + hx - hy, c + hx + hy, c - hx + hy, c - hx - hy, u0, u1, col);
            // frame edges
            mb.Box(frameSub, center + hy + up * 0.04f, Quaternion.LookRotation(normal, up), new Vector3(width + 0.08f, 0.08f, thick + 0.04f), 1f, col);
            mb.Box(frameSub, center - hy - up * 0.04f, Quaternion.LookRotation(normal, up), new Vector3(width + 0.08f, 0.08f, thick + 0.04f), 1f, col);
            mb.Box(frameSub, center + hx + right * 0.04f, Quaternion.LookRotation(normal, up), new Vector3(0.08f, height, thick + 0.04f), 1f, col);
            mb.Box(frameSub, center - hx - right * 0.04f, Quaternion.LookRotation(normal, up), new Vector3(0.08f, height, thick + 0.04f), 1f, col);
        }
    }
}
