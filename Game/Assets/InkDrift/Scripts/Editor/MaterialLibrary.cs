using System.IO;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Creates/updates toon materials from texture sets and named presets. All live in Assets/InkDrift/Materials.</summary>
    public static class MaterialLibrary
    {
        public const string Dir = "Assets/InkDrift/Materials";
        const string TexDir = "Assets/InkDrift/Art/Textures";
        static Shader toon;

        static Shader Toon => toon ??= Shader.Find("InkDrift/Toon");

        public static Material Get(string name)
        {
            return AssetDatabase.LoadAssetAtPath<Material>($"{Dir}/{name}.mat");
        }

        public static Material Ensure(string name, Shader shader = null)
        {
            Directory.CreateDirectory(Dir);
            string path = $"{Dir}/{name}.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(shader ?? Toon) { name = name };
                AssetDatabase.CreateAsset(m, path);
            }
            else if (shader != null && m.shader != shader) m.shader = shader;
            m.enableInstancing = true;
            return m;
        }

        static Texture2D Tex(string path) => AssetDatabase.LoadAssetAtPath<Texture2D>(path);

        static Texture2D FindTex(string dir, string set, string suffix)
        {
            foreach (var ext in new[] { ".png", ".jpg", ".tga" })
            {
                var t = Tex($"{dir}/{set}{suffix}{ext}");
                if (t != null) return t;
            }
            return null;
        }

        /// <summary>Toon material from Art/Textures/&lt;set&gt;/ (albedo, normal, mask).</summary>
        public static Material FromSet(string set, string matName = null, float tilingMeters = 4f, float smooth = 0.4f, float metallic = 0f, Color? tint = null)
        {
            var m = Ensure(matName ?? "Toon_" + set);
            string dir = $"{TexDir}/{set}";
            ApplyTextures(m, FindTex(dir, set, "_albedo"), FindTex(dir, set, "_normal"), FindTex(dir, set, "_mask"), null);
            m.SetColor("_BaseColor", tint ?? Color.white);
            m.SetFloat("_Smoothness", smooth);
            m.SetFloat("_Metallic", metallic);
            m.SetTextureScale("_BaseMap", Vector2.one * (1f / Mathf.Max(0.01f, tilingMeters)));
            EditorUtility.SetDirty(m);
            return m;
        }

        public static void ApplyTextures(Material m, Texture albedo, Texture normal, Texture mask, Texture emission)
        {
            if (albedo) m.SetTexture("_BaseMap", albedo);
            if (normal) { m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP"); m.SetFloat("_UseNormalMap", 1); }
            else { m.DisableKeyword("_NORMALMAP"); m.SetFloat("_UseNormalMap", 0); }
            if (mask) { m.SetTexture("_MaskMap", mask); m.EnableKeyword("_MASKMAP"); m.SetFloat("_UseMaskMap", 1); }
            else { m.DisableKeyword("_MASKMAP"); m.SetFloat("_UseMaskMap", 0); }
            if (emission) { m.SetTexture("_EmissionMap", emission); m.EnableKeyword("_EMISSION"); m.SetFloat("_UseEmission", 1); }
        }

        public static Material Flat(string name, Color color, float smooth = 0.3f, float metallic = 0f, Color? emission = null, float reflect = 0f)
        {
            var m = Ensure(name);
            m.SetColor("_BaseColor", color);
            m.SetFloat("_Smoothness", smooth);
            m.SetFloat("_Metallic", metallic);
            m.SetFloat("_ReflectStrength", reflect);
            m.SetColor("_EmissionColor", emission ?? Color.black);
            m.DisableKeyword("_NORMALMAP"); m.DisableKeyword("_MASKMAP"); m.DisableKeyword("_EMISSION");
            EditorUtility.SetDirty(m);
            return m;
        }

        public static void SetKeyword(Material m, string kw, string prop, bool on)
        {
            if (on) m.EnableKeyword(kw); else m.DisableKeyword(kw);
            m.SetFloat(prop, on ? 1 : 0);
        }

        /// <summary>Core runtime materials loaded by scripts via Resources/Materials.</summary>
        [MenuItem("InkDrift/Setup/Build Core Materials")]
        public static void BuildCore()
        {
            string res = "Assets/InkDrift/Resources/Materials";
            Directory.CreateDirectory(res);
            Material R(string n, Shader s)
            {
                string p = $"{res}/{n}.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(p);
                if (m == null) { m = new Material(s) { name = n }; AssetDatabase.CreateAsset(m, p); }
                m.shader = s;
                return m;
            }

            var paint = R("CarPaint_Default", Toon);
            paint.SetColor("_BaseColor", new Color(1f, 0.18f, 0.48f));
            paint.SetFloat("_Smoothness", 0.88f); paint.SetFloat("_Metallic", 0.35f); paint.SetFloat("_ReflectStrength", 0.9f);
            paint.SetFloat("_SpecSize", 0.18f); paint.SetFloat("_SpecIntensity", 1.6f); paint.SetFloat("_RimAmount", 0.8f);
            var trim = R("Toon_DarkTrim", Toon);
            trim.SetColor("_BaseColor", new Color(0.06f, 0.06f, 0.08f)); trim.SetFloat("_Smoothness", 0.7f); trim.SetFloat("_ReflectStrength", 0.6f);
            var tire = R("Toon_Tire", Toon);
            tire.SetColor("_BaseColor", new Color(0.05f, 0.05f, 0.06f)); tire.SetFloat("_Smoothness", 0.15f);
            var traffic = R("Toon_Traffic", Toon);
            traffic.SetColor("_BaseColor", new Color(0.9f, 0.9f, 0.88f)); traffic.SetFloat("_Smoothness", 0.7f); traffic.SetFloat("_ReflectStrength", 0.5f);

            var smoke = R("ToonSmoke", Shader.Find("InkDrift/ToonSmoke"));
            var puff = Tex("Assets/InkDrift/Art/Generated/smoke_puff.png");
            if (puff) smoke.SetTexture("_MainTex", puff);
            var spark = R("Spark", Shader.Find("InkDrift/Additive"));
            spark.SetColor("_Color", new Color(6f, 3.2f, 0.8f, 1f));
            var glow = Tex("Assets/InkDrift/Art/Generated/glow_dot.png");
            if (glow) spark.SetTexture("_MainTex", glow);
            var flame = R("Flame", Shader.Find("InkDrift/Additive"));
            flame.SetColor("_Color", new Color(8f, 3f, 0.6f, 1f));
            var flameTex = Tex("Assets/InkDrift/Art/Generated/flame.png");
            if (flameTex) flame.SetTexture("_MainTex", flameTex); else if (glow) flame.SetTexture("_MainTex", glow);
            var skid = R("Skidmark", Shader.Find("InkDrift/Skidmark"));
            var tread = Tex("Assets/InkDrift/Art/Generated/tread.png");
            if (tread) skid.SetTexture("_MainTex", tread);
            foreach (var m in new[] { paint, trim, tire, traffic, smoke, spark, flame, skid }) { m.enableInstancing = true; EditorUtility.SetDirty(m); }
            AssetDatabase.SaveAssets();
        }
    }
}
