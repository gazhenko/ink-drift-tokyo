using System;
using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Photo-scanned CC0 materials (Tools/driver/fetch_scans.py -> Resources/Scan) applied to InkDrift/Realistic
    /// materials at their real-world size: a scan is tinted to a target colour by normalising it with its own mean,
    /// so it keeps its natural variation (fibres, grain, wear) at any colour.
    /// </summary>
    public static class ScanLibrary
    {
        [Serializable] class Entry { public string name; public float size_m; public float[] mean_srgb; public float mean_smooth; }
        [Serializable] class Root { public Entry[] sets; }

        static Dictionary<string, Entry> sets;
        static Shader shader;

        public static Shader Realistic => shader != null ? shader : (shader = Shader.Find("InkDrift/Realistic"));

        static Entry Get(string name)
        {
            if (sets == null)
            {
                sets = new Dictionary<string, Entry>();
                var ta = Resources.Load<TextAsset>("Scan/scans");
                if (ta != null)
                    foreach (var e in JsonUtility.FromJson<Root>(ta.text).sets) sets[e.name] = e;
            }
            return name != null && sets.TryGetValue(name, out var v) ? v : null;
        }

        /// <param name="uvUnitMeters">metres per UV0 unit (skinned driver meshes); 0 = object-space triplanar</param>
        public static void Apply(Material m, string scan, Color tint, float desaturate, float smooth, float bump, float uvUnitMeters)
        {
            m.SetColor("_BaseColor", tint);
            m.SetFloat("_Smoothness", smooth);
            var e = Get(scan);
            if (e == null) { m.SetFloat("_MaskStrength", 0f); m.SetFloat("_Triplanar", 0f); return; }
            m.SetTexture("_BaseMap", Resources.Load<Texture2D>($"Scan/{scan}_albedo"));
            m.SetTexture("_BumpMap", Resources.Load<Texture2D>($"Scan/{scan}_n"));
            m.SetTexture("_MaskMap", Resources.Load<Texture2D>($"Scan/{scan}_mask"));
            m.SetColor("_TexMean", new Color(e.mean_srgb[0], e.mean_srgb[1], e.mean_srgb[2]));
            m.SetFloat("_Desaturate", desaturate);
            m.SetFloat("_BumpScale", bump);
            m.SetFloat("_MaskStrength", 1f);
            m.SetFloat("_MaskSmoothMean", Mathf.Max(0.05f, e.mean_smooth));
            if (uvUnitMeters > 0f)
            {
                float k = uvUnitMeters / Mathf.Max(0.01f, e.size_m);
                m.SetTextureScale("_BaseMap", new Vector2(k, k));
                m.SetFloat("_Triplanar", 0f);
            }
            else m.SetFloat("_Triplanar", 1f / Mathf.Max(0.01f, e.size_m));
        }

        /// <summary>A new realistic material (null if the shader isn't in the build).</summary>
        public static Material Create(string name, string scan, Color tint, float desaturate, float smooth, float bump,
                                      float metallic = 0f, float sheen = 0f, Color? emission = null)
        {
            if (Realistic == null) return null;
            var m = new Material(Realistic) { name = "Real_" + name };
            if (scan != null) Apply(m, scan, tint, desaturate, smooth, bump, 0f);
            else { m.SetColor("_BaseColor", tint); m.SetFloat("_Smoothness", smooth); m.SetFloat("_Triplanar", 0f); }
            m.SetFloat("_Metallic", metallic);
            m.SetFloat("_Sheen", sheen);
            m.SetColor("_SheenColor", Color.Lerp(tint, Color.white, 0.6f));
            m.SetFloat("_AOStrength", 0f);
            m.SetFloat("_CavityStrength", 0f);
            m.SetFloat("_AmbientBoost", DriverModel.AmbientBoost);
            bool cloth = scan == "suede" || scan == "seat_fabric" || scan == "carpet" || scan == "nomex_weave" || scan == "knit";
            m.SetFloat("_EnvSpecular", metallic > 0.5f ? 0.45f : cloth ? DriverModel.ClothEnvSpecular : DriverModel.InteriorEnvSpecular);   // metal needs its reflections
            if (emission.HasValue) m.SetColor("_EmissionColor", emission.Value);
            return m;
        }
    }
}
