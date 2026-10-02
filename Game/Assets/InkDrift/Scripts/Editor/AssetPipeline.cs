using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Import rules by folder + suffix so every asset lands with the right settings automatically.</summary>
    public class AssetPipeline : AssetPostprocessor
    {
        static bool In(string path, string folder) => path.Replace('\\', '/').Contains(folder);

        void OnPreprocessTexture()
        {
            var ti = (TextureImporter)assetImporter;
            string p = assetPath.Replace('\\', '/');
            string lower = p.ToLowerInvariant();
            string file = System.IO.Path.GetFileNameWithoutExtension(lower);

            if (In(p, "/Art/HDRI/"))
            {
                ti.textureShape = TextureImporterShape.TextureCube;
                ti.generateCubemap = TextureImporterGenerateCubemap.Cylindrical;
                ti.sRGBTexture = false;
                ti.maxTextureSize = 2048;
                ti.textureCompression = TextureImporterCompression.CompressedHQ;
                ti.mipmapEnabled = true;
                return;
            }

            bool ui = In(p, "/Art/Callouts/") || In(p, "/Art/UI/") || In(p, "/Resources/UI/");
            if (ui)
            {
                ti.textureType = TextureImporterType.Sprite;
                ti.spriteImportMode = SpriteImportMode.Single;
                ti.alphaIsTransparency = true;
                ti.mipmapEnabled = false;
                ti.maxTextureSize = 4096;
                ti.textureCompression = TextureImporterCompression.CompressedHQ;
                ti.wrapMode = file.Contains("tile") || file.Contains("grain") || file.Contains("screentone") ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
                if (file.Contains("halftone_tile") || file.Contains("paper_grain") || file.Contains("screentone")) ti.textureType = TextureImporterType.Default;
                return;
            }

            ti.textureType = TextureImporterType.Default;
            ti.mipmapEnabled = true;
            ti.streamingMipmaps = true;
            ti.anisoLevel = 8;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            ti.maxTextureSize = In(p, "/Art/Facades/") || In(p, "/Art/Textures/") ? 2048 : 2048;

            if (file.EndsWith("_normal") || file.EndsWith("_nrm") || file.EndsWith("_n"))
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.sRGBTexture = false;
            }
            else if (file.EndsWith("_mask") || file.EndsWith("_height") || file.EndsWith("_rough") || file.EndsWith("_ao") || file.Contains("noise"))
            {
                ti.sRGBTexture = false;
            }
            else
            {
                ti.sRGBTexture = true;
                ti.alphaIsTransparency = In(p, "/Decals/") || In(p, "/Signs/") || lower.Contains("leaves") || lower.Contains("leaf") || lower.Contains("atlas") || lower.Contains("grass") || lower.Contains("fern");
            }
            if (In(p, "/Models/Driver/") && (file.StartsWith("patch_") || file.Contains("logo")))
            {
                ti.alphaIsTransparency = true;          // suit patches / glove logo are alpha-clipped decals
                ti.wrapMode = TextureWrapMode.Clamp;
            }
            if (In(p, "/Art/Signs/") || In(p, "/Art/Decals/")) ti.wrapMode = TextureWrapMode.Clamp;
        }

        void OnPreprocessModel()
        {
            var mi = (ModelImporter)assetImporter;
            mi.globalScale = 1f;
            mi.useFileScale = true;
            mi.importCameras = false;
            mi.importLights = false;
            mi.importAnimation = false;
            mi.animationType = ModelImporterAnimationType.None;
            mi.importBlendShapes = false;
            mi.importNormals = ModelImporterNormals.Import;
            mi.importTangents = ModelImporterTangents.CalculateMikk;
            mi.meshCompression = ModelImporterMeshCompression.Off;
            mi.optimizeMeshPolygons = true;
            mi.optimizeMeshVertices = true;
            mi.weldVertices = true;
            mi.isReadable = In(assetPath, "/Models/Cars/") || In(assetPath, "/Models/Track/");
            mi.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
            mi.addCollider = false;
            if (In(assetPath, "/Models/Driver/"))
            {
                // skinned driver arms: keep the bones as transforms for the runtime IK
                mi.animationType = ModelImporterAnimationType.Generic;
                mi.avatarSetup = ModelImporterAvatarSetup.NoAvatar;
                mi.optimizeGameObjects = false;
                mi.skinWeights = ModelImporterSkinWeights.Standard;
            }
        }

        /// <summary>FBX materials from Blender become InkDrift/Toon materials, keeping base color, textures and emission.</summary>
        void OnPreprocessMaterialDescription(MaterialDescription d, Material m, AnimationClip[] clips)
        {
            if (!In(assetPath, "/Models/")) return;
            var shader = Shader.Find("InkDrift/Toon");
            if (shader == null) return;
            m.shader = shader;
            string n = d.materialName ?? m.name;
            string ln = n.ToLowerInvariant();
            Color baseCol = Color.white;
            if (d.TryGetProperty("DiffuseColor", out Vector4 c)) baseCol = new Color(c.x, c.y, c.z, 1f);
            bool hasTex = d.TryGetProperty("DiffuseColor", out TexturePropertyDescription td) && td.texture != null;
            if (hasTex) { m.SetTexture("_BaseMap", td.texture); m.SetColor("_BaseColor", Color.white); }
            else m.SetColor("_BaseColor", baseCol);
            if (d.TryGetProperty("NormalMap", out TexturePropertyDescription nt) && nt.texture != null)
            { m.SetTexture("_BumpMap", nt.texture); m.EnableKeyword("_NORMALMAP"); m.SetFloat("_UseNormalMap", 1); }
            else if (d.TryGetProperty("Bump", out TexturePropertyDescription bt) && bt.texture != null)
            { m.SetTexture("_BumpMap", bt.texture); m.EnableKeyword("_NORMALMAP"); m.SetFloat("_UseNormalMap", 1); }

            Color em = Color.black;
            if (d.TryGetProperty("EmissiveColor", out Vector4 e))
            {
                float f = d.TryGetProperty("EmissiveFactor", out float ef) ? ef : 1f;
                em = new Color(e.x, e.y, e.z) * f;
            }
            if (ln.Contains("emissive") || ln.Contains("lamp") && ln.Contains("emiss"))
            {
                if (em.maxColorComponent < 0.05f) em = baseCol;
                float k = ln.Contains("signal") ? 3.5f : ln.Contains("lantern") || ln.Contains("akachochin") ? 2.5f : 4f;
                m.SetColor("_EmissionColor", em * k);
                if (hasTex) { m.SetTexture("_EmissionMap", td.texture); m.EnableKeyword("_EMISSION"); m.SetFloat("_UseEmission", 1); }
            }

            // surface response by name
            float smooth = 0.35f, metal = 0f, refl = 0f;
            if (ln.Contains("chrome") || ln.Contains("mirror")) { smooth = 0.95f; metal = 1f; refl = 1.2f; }
            else if (ln.Contains("stainless") || ln.Contains("aluminum") || ln.Contains("brass")) { smooth = 0.7f; metal = 0.9f; refl = 0.8f; }
            else if (ln.Contains("galvanized") || ln.Contains("steel")) { smooth = 0.55f; metal = 0.7f; refl = 0.4f; }
            else if (ln.Contains("glass")) { smooth = 0.95f; refl = 0.9f; }
            else if (ln.Contains("paintedmetal") || ln.Contains("vendingbody") || ln.Contains("bikeframe")) { smooth = 0.6f; metal = 0.2f; refl = 0.25f; }
            else if (ln.Contains("plastic") || ln.Contains("porcelain") || ln.Contains("frp")) { smooth = 0.65f; refl = 0.15f; }
            else if (ln.Contains("concrete") || ln.Contains("stone") || ln.Contains("shotcrete")) { smooth = 0.12f; }
            else if (ln.Contains("rubber") || ln.Contains("cable") || ln.Contains("rope")) { smooth = 0.2f; }
            else if (ln.Contains("reflector")) { smooth = 0.8f; m.SetColor("_EmissionColor", baseCol * 0.35f); }
            m.SetFloat("_Smoothness", smooth); m.SetFloat("_Metallic", metal); m.SetFloat("_ReflectStrength", refl);

            bool foliage = ln.Contains("leaves") || ln.Contains("leaf") || ln.Contains("needle") || ln.Contains("grass") || ln.Contains("fern")
                           || ln.Contains("susuki") || ln.Contains("blossom") || ln.Contains("petal") || ln.Contains("bamboo_leaf") || ln.Contains("cutout") || ln.Contains("wiremesh");
            bool tree = In(assetPath, "/Models/Trees/");
            if (foliage)
            {
                m.EnableKeyword("_ALPHATEST_ON"); m.SetFloat("_AlphaClip", 1); m.SetFloat("_Cutoff", 0.45f);
                m.SetFloat("_Cull", 0);
                m.SetFloat("_HalftoneAmount", 0.55f);
                m.SetFloat("_SpecIntensity", 0f);
                m.SetFloat("_RimAmount", 0.35f);
                m.SetFloat("_BackfaceFlip", 0f);
                m.SetFloat("_ReceiveShadows", 0.35f);
            }
            if (tree)
            {
                m.SetFloat("_VertexAO", 0.85f);
                m.SetFloat("_WindStrength", foliage ? 1.0f : 0.25f);
                m.SetFloat("_HueVariation", foliage ? 0.35f : 0.1f);
                m.SetFloat("_ShadowThreshold", foliage ? -0.15f : 0f);
            }
            if (In(assetPath, "/Models/Cars/")) CarMaterial(m, n, baseCol, hasTex);
            if (In(assetPath, "/Models/Driver/")) DriverMaterial(m, n);
            m.enableInstancing = true;
        }

        /// <summary>Realistic shading for the driver's suit and gloves: soft terminator, real highlights, fine normal detail.</summary>
        static void DriverMaterial(Material m, string name)
        {
            // realistic path (physically based, excluded from the comic ink pass); DriverModel sets the look at runtime
            var real = Shader.Find("InkDrift/Realistic");
            if (real != null)
            {
                m.shader = real;
                bool decal = name.Contains("Logo") || name.Contains("Patch");
                m.SetFloat("_AlphaClip", decal ? 1f : 0f);
                if (decal) m.EnableKeyword("_ALPHATEST_ON"); else m.DisableKeyword("_ALPHATEST_ON");
                m.SetFloat("_Cutoff", 0.5f);
                return;
            }
            void P(float smooth, float spec, float specSize, float specSoft, float bump)
            {
                m.SetFloat("_Smoothness", smooth); m.SetFloat("_SpecIntensity", spec); m.SetFloat("_SpecSize", specSize);
                m.SetFloat("_SpecSoftness", specSoft); m.SetFloat("_BumpScale", bump);
            }
            m.SetFloat("_BandSoftness", 0.32f);
            m.SetFloat("_ShadowThreshold", -0.12f);
            m.SetFloat("_HalftoneAmount", 0.12f);
            m.SetFloat("_HighlightBoost", 0.05f);
            m.SetFloat("_RimAmount", 0.3f);
            m.SetFloat("_ReceiveShadows", 0.35f);
            m.SetFloat("_Metallic", 0f);
            m.SetFloat("_ReflectStrength", 0f);
            if (name.Contains("GloveBack") || name.Contains("Knuckle")) P(0.55f, 0.55f, 0.3f, 0.35f, 1.1f);        // full-grain leather sheen
            else if (name.Contains("GlovePalm")) P(0.12f, 0.15f, 0.1f, 0.5f, 1.3f);                              // suede + silicone print
            else if (name.Contains("Strap") || name.Contains("Knit")) P(0.05f, 0.05f, 0.05f, 0.5f, 1.2f);
            else if (name.Contains("Stripe") || name.Contains("Stretch")) P(0.22f, 0.2f, 0.15f, 0.45f, 0.9f);
            else if (name.Contains("Suit")) P(0.18f, 0.18f, 0.15f, 0.5f, 1.0f);                                   // quilted Nomex
            if (name.Contains("Logo") || name.Contains("Patch"))
            {
                m.EnableKeyword("_ALPHATEST_ON"); m.SetFloat("_AlphaClip", 1f); m.SetFloat("_Cutoff", 0.5f);
                P(0.35f, 0.3f, 0.15f, 0.35f, 1f);
            }
        }

        static void CarMaterial(Material m, string name, Color baseCol, bool hasTex)
        {
            void P(float smooth, float metal, float refl, float spec, float specSize, float rim)
            {
                m.SetFloat("_Smoothness", smooth); m.SetFloat("_Metallic", metal); m.SetFloat("_ReflectStrength", refl);
                m.SetFloat("_SpecIntensity", spec); m.SetFloat("_SpecSize", specSize); m.SetFloat("_RimAmount", rim);
            }
            if (name.StartsWith("M_Paint"))
            {
                P(0.9f, 0.35f, 1.0f, 1.8f, 0.2f, 0.9f);
                m.SetFloat("_ReflectBands", 5f);
                m.SetFloat("_HalftoneAmount", 0.7f);
                if (!hasTex) m.SetColor("_BaseColor", name.Contains("Accent") ? new Color(0.06f, 0.06f, 0.07f) : Color.white);
            }
            else if (name.StartsWith("M_Glass")) { m.SetColor("_BaseColor", new Color(0.03f, 0.035f, 0.05f)); P(0.97f, 0.2f, 1.4f, 2.2f, 0.25f, 0.4f); }
            else if (name.StartsWith("M_Chrome")) { m.SetColor("_BaseColor", new Color(0.8f, 0.82f, 0.86f)); P(0.95f, 1f, 1.3f, 2f, 0.2f, 0.6f); }
            else if (name.StartsWith("M_Rim")) { if (!hasTex) m.SetColor("_BaseColor", new Color(0.12f, 0.12f, 0.14f)); P(0.8f, 0.8f, 0.8f, 1.6f, 0.18f, 0.6f); }
            else if (name.StartsWith("M_Tire")) { if (!hasTex) m.SetColor("_BaseColor", new Color(0.05f, 0.05f, 0.055f)); P(0.2f, 0f, 0f, 0.2f, 0.05f, 0.2f); }
            else if (name.StartsWith("M_Carbon"))
            {
                var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Art/Textures/misc_carbon_fiber/misc_carbon_fiber_albedo.jpg");
                if (!hasTex && tex) { m.SetTexture("_BaseMap", tex); m.SetTextureScale("_BaseMap", Vector2.one * 4f); }
                m.SetColor("_BaseColor", new Color(0.55f, 0.55f, 0.6f)); P(0.85f, 0.3f, 0.7f, 1.4f, 0.15f, 0.6f);
            }
            else if (name.StartsWith("M_Trim") || name.StartsWith("M_Grille") || name.StartsWith("M_Underbody")) { if (!hasTex) m.SetColor("_BaseColor", new Color(0.05f, 0.05f, 0.06f)); P(0.45f, 0f, 0.2f, 0.5f, 0.1f, 0.3f); }
            else if (name.StartsWith("M_HeadLight")) { P(0.95f, 0.5f, 1.2f, 2f, 0.3f, 0.5f); m.SetColor("_EmissionColor", new Color(0.6f, 0.6f, 0.6f)); }
            else if (name.StartsWith("M_TailLight")) { if (!hasTex) m.SetColor("_BaseColor", new Color(0.7f, 0.05f, 0.06f)); P(0.9f, 0.1f, 0.8f, 1.5f, 0.2f, 0.4f); m.SetColor("_EmissionColor", new Color(0.6f, 0.03f, 0.05f)); }
            else if (name.StartsWith("M_Decal") || name.StartsWith("M_Plate"))
            {
                if (name.StartsWith("M_Decal")) { m.EnableKeyword("_ALPHATEST_ON"); m.SetFloat("_AlphaClip", 1); m.SetFloat("_Cutoff", 0.5f); }
                P(0.85f, 0f, 0.6f, 1.2f, 0.15f, 0.6f);
            }
            else if (name.StartsWith("M_Brake")) P(0.6f, 0.8f, 0.4f, 1f, 0.1f, 0.3f);
            else if (name.StartsWith("M_Interior")) P(0.3f, 0f, 0f, 0.3f, 0.05f, 0.2f);
        }

        void OnPreprocessAudio()
        {
            var ai = (AudioImporter)assetImporter;
            var s = ai.defaultSampleSettings;
            if (In(assetPath, "/Music/"))
            {
                s.loadType = AudioClipLoadType.Streaming;
                s.compressionFormat = AudioCompressionFormat.Vorbis;
                s.quality = 0.8f;
            }
            else
            {
                s.loadType = AudioClipLoadType.DecompressOnLoad;
                s.compressionFormat = AudioCompressionFormat.Vorbis;
                s.quality = 0.85f;
            }
            ai.defaultSampleSettings = s;
            ai.loadInBackground = In(assetPath, "/Music/");
            ai.forceToMono = In(assetPath, "/Voice/") ? false : ai.forceToMono;
        }
    }
}
