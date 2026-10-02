using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace InkDrift.EditorTools
{
    /// <summary>One-shot project configuration (URP assets, renderer features, player/quality/input/layers). Batch: -executeMethod InkDrift.EditorTools.ProjectSetup.Run</summary>
    public static class ProjectSetup
    {
        public const string SettingsDir = "Assets/InkDrift/Settings";

        [MenuItem("InkDrift/Setup/Configure Project")]
        public static void Run()
        {
            Directory.CreateDirectory(SettingsDir);
            ConfigureLayers();
            ConfigurePlayer();
            var post = EnsurePostMaterial();
            var high = EnsurePipeline("High", post, 1.0f, 200f, 4096, 4);
            var med = EnsurePipeline("Medium", post, 0.9f, 140f, 2048, 3);
            var low = EnsurePipeline("Low", post, 0.75f, 90f, 1024, 2);
            GraphicsSettings.defaultRenderPipeline = high;
            ConfigureQuality(low, med, high);
            ConfigureTimeAndPhysics();
            ImportTmpEssentials();
            AssetDatabase.SaveAssets();
            Debug.Log("[InkDrift] Project configured.");
        }

        static void ConfigureLayers()
        {
            var tm = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0];
            var so = new SerializedObject(tm);
            var layers = so.FindProperty("layers");
            void Set(int i, string n) { var p = layers.GetArrayElementAtIndex(i); if (string.IsNullOrEmpty(p.stringValue)) p.stringValue = n; }
            Set(8, "Car"); Set(9, "Track"); Set(10, "Props"); Set(11, "Foliage"); Set(12, "Reflection");
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Gazhenko";
            PlayerSettings.productName = "INK DRIFT TOKYO";
            PlayerSettings.SetApplicationIdentifier(UnityEditor.Build.NamedBuildTarget.Standalone, "com.gazhenko.inkdrift");
            PlayerSettings.bundleVersion = "1.8.0";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.defaultScreenWidth = 1920;
            PlayerSettings.defaultScreenHeight = 1080;
            PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.SplashScreen.show = false;
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.SetApiCompatibilityLevel(UnityEditor.Build.NamedBuildTarget.Standalone, ApiCompatibilityLevel.NET_Standard);
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneOSX, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneOSX, new[] { GraphicsDeviceType.Metal });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneLinux64, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneLinux64, new[] { GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLCore });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[] { GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Direct3D12, GraphicsDeviceType.Vulkan });

            var ps = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0];
            var so = new SerializedObject(ps);
            var input = so.FindProperty("activeInputHandler");
            if (input != null) input.intValue = 2;   // Both
            var icon = so.FindProperty("macOSURLSchemes");
            so.ApplyModifiedPropertiesWithoutUndo();

            var iconTex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Art/UI/icon.png");
            if (iconTex != null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, new[] { iconTex }, IconKind.Any);
        }

        static Material EnsurePostMaterial()
        {
            string path = SettingsDir + "/InkComicPost.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null)
            {
                m = new Material(Shader.Find("InkDrift/ComicPost"));
                AssetDatabase.CreateAsset(m, path);
            }
            return m;
        }

        static UniversalRenderPipelineAsset EnsurePipeline(string tier, Material post, float renderScale, float shadowDistance, int shadowRes, int cascades)
        {
            string rendererPath = $"{SettingsDir}/URP_{tier}_Renderer.asset";
            string reflPath = $"{SettingsDir}/URP_{tier}_ReflectionRenderer.asset";
            string assetPath = $"{SettingsDir}/URP_{tier}.asset";

            var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(rendererPath);
            if (renderer == null)
            {
                renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(renderer, rendererPath);
            }
            var reflRenderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(reflPath);
            if (reflRenderer == null)
            {
                reflRenderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(reflRenderer, reflPath);
            }
            foreach (var r in new[] { renderer, reflRenderer })
            {
                r.postProcessData ??= AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
                r.renderingMode = RenderingMode.ForwardPlus;
                r.depthPrimingMode = DepthPrimingMode.Disabled;
                r.copyDepthMode = CopyDepthMode.AfterOpaques;
                EditorUtility.SetDirty(r);
            }
            EnsureFullscreenFeature(renderer, post);
            EnsureFeature<InkMaskFeature>(renderer, "InkMask");

            var asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(assetPath);
            if (asset == null)
            {
                asset = UniversalRenderPipelineAsset.Create(renderer);
                AssetDatabase.CreateAsset(asset, assetPath);
            }
            var so = new SerializedObject(asset);
            void SetF(string n, float v) { var p = so.FindProperty(n); if (p != null) p.floatValue = v; else Debug.LogWarning("URP prop missing " + n); }
            void SetI(string n, int v) { var p = so.FindProperty(n); if (p != null) p.intValue = v; else Debug.LogWarning("URP prop missing " + n); }
            void SetB(string n, bool v) { var p = so.FindProperty(n); if (p != null) p.boolValue = v; else Debug.LogWarning("URP prop missing " + n); }
            // renderer list: 0 = main, 1 = reflections (no comic post)
            var list = so.FindProperty("m_RendererDataList");
            list.arraySize = 2;
            list.GetArrayElementAtIndex(0).objectReferenceValue = renderer;
            list.GetArrayElementAtIndex(1).objectReferenceValue = reflRenderer;
            SetI("m_DefaultRendererIndex", 0);
            SetB("m_RequireDepthTexture", true);
            SetB("m_RequireOpaqueTexture", false);
            SetB("m_SupportsHDR", true);
            SetI("m_MSAA", 1);
            SetF("m_RenderScale", renderScale);
            SetI("m_MainLightRenderingMode", 1);
            SetB("m_MainLightShadowsSupported", true);
            SetI("m_MainLightShadowmapResolution", shadowRes);
            SetI("m_AdditionalLightsRenderingMode", 1);
            SetI("m_AdditionalLightsPerObjectLimit", 8);
            SetB("m_AdditionalLightShadowsSupported", tier == "High");
            SetI("m_AdditionalLightsShadowmapResolution", 2048);
            SetF("m_ShadowDistance", shadowDistance);
            SetI("m_ShadowCascadeCount", cascades);
            SetB("m_SoftShadowsSupported", true);
            SetB("m_SupportsTerrainHoles", false);
            SetI("m_ColorGradingMode", 1); // HDR grading
            SetI("m_ColorGradingLutSize", 32);
            SetB("m_UseSRPBatcher", true);
            SetB("m_SupportsDynamicBatching", false);
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(asset);
            return asset;
        }

        /// <summary>Renderer features only (no other project changes): -executeMethod InkDrift.EditorTools.ProjectSetup.EnsureRenderFeatures</summary>
        public static void EnsureRenderFeatures()
        {
            foreach (var tier in new[] { "High", "Medium", "Low" })
            {
                var r = AssetDatabase.LoadAssetAtPath<UniversalRendererData>($"{SettingsDir}/URP_{tier}_Renderer.asset");
                if (r != null) EnsureFeature<InkMaskFeature>(r, "InkMask");
            }
            AssetDatabase.SaveAssets();
            Debug.Log("[InkDrift] render features ensured");
            if (Application.isBatchMode) EditorApplication.Exit(0);
        }

        static void EnsureFeature<T>(UniversalRendererData data, string name) where T : ScriptableRendererFeature
        {
            foreach (var f in data.rendererFeatures) if (f is T) return;
            var feature = ScriptableObject.CreateInstance<T>();
            feature.name = name;
            AssetDatabase.AddObjectToAsset(feature, data);
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(feature, out _, out long localId);
            var so = new SerializedObject(data);
            var feats = so.FindProperty("m_RendererFeatures");
            var map = so.FindProperty("m_RendererFeatureMap");
            feats.arraySize++;
            feats.GetArrayElementAtIndex(feats.arraySize - 1).objectReferenceValue = feature;
            map.arraySize++;
            map.GetArrayElementAtIndex(map.arraySize - 1).longValue = localId;
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(data);
        }

        static void EnsureFullscreenFeature(UniversalRendererData data, Material post)
        {
            foreach (var f in data.rendererFeatures) if (f is FullScreenPassRendererFeature) return;
            var feature = ScriptableObject.CreateInstance<FullScreenPassRendererFeature>();
            feature.name = "InkComicPost";
            feature.passMaterial = post;
            feature.passIndex = 0;
            feature.injectionPoint = FullScreenPassRendererFeature.InjectionPoint.BeforeRenderingPostProcessing;
            feature.fetchColorBuffer = true;
            feature.requirements = ScriptableRenderPassInput.Depth | ScriptableRenderPassInput.Normal;
            AssetDatabase.AddObjectToAsset(feature, data);
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(feature, out _, out long localId);
            var so = new SerializedObject(data);
            var feats = so.FindProperty("m_RendererFeatures");
            var map = so.FindProperty("m_RendererFeatureMap");
            feats.arraySize++;
            feats.GetArrayElementAtIndex(feats.arraySize - 1).objectReferenceValue = feature;
            map.arraySize++;
            map.GetArrayElementAtIndex(map.arraySize - 1).longValue = localId;
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(data);
        }

        static void ConfigureQuality(RenderPipelineAsset low, RenderPipelineAsset med, RenderPipelineAsset high)
        {
            var qs = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/QualitySettings.asset")[0];
            var so = new SerializedObject(qs);
            var levels = so.FindProperty("m_QualitySettings");
            levels.arraySize = 3;
            string[] names = { "Low", "Medium", "High" };
            RenderPipelineAsset[] assets = { low, med, high };
            for (int i = 0; i < 3; i++)
            {
                var l = levels.GetArrayElementAtIndex(i);
                l.FindPropertyRelative("name").stringValue = names[i];
                l.FindPropertyRelative("customRenderPipeline").objectReferenceValue = assets[i];
                var vs = l.FindPropertyRelative("vSyncCount"); if (vs != null) vs.intValue = 1;
                var af = l.FindPropertyRelative("anisotropicTextures"); if (af != null) af.intValue = 2;
                var lb = l.FindPropertyRelative("lodBias"); if (lb != null) lb.floatValue = i == 2 ? 2.0f : i == 1 ? 1.4f : 1.0f;
                var tq = l.FindPropertyRelative("globalTextureMipmapLimit"); if (tq != null) tq.intValue = i == 0 ? 1 : 0;
                var pl = l.FindPropertyRelative("pixelLightCount"); if (pl != null) pl.intValue = 8;
                var sb = l.FindPropertyRelative("skinWeights"); if (sb != null) sb.intValue = 4;
            }
            so.FindProperty("m_CurrentQuality").intValue = 2;
            var per = so.FindProperty("m_PerPlatformDefaultQuality");
            if (per != null)
                for (int i = 0; i < per.arraySize; i++) per.GetArrayElementAtIndex(i).FindPropertyRelative("second").intValue = 2;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ConfigureTimeAndPhysics()
        {
            var tm = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TimeManager.asset")[0];
            var so = new SerializedObject(tm);
            // Unity 6 serializes Fixed Timestep as RationalTime { m_Count, m_Rate { m_Numerator, m_Denominator } }
            var cnt = so.FindProperty("Fixed Timestep.m_Count");
            if (cnt != null)
            {
                var num = so.FindProperty("Fixed Timestep.m_Rate.m_Numerator"); var den = so.FindProperty("Fixed Timestep.m_Rate.m_Denominator");
                double rate = num != null && den != null && den.longValue > 0 ? num.longValue / (double)den.longValue : 141120000.0;
                cnt.longValue = (long)System.Math.Round(rate / 120.0);
            }
            else so.FindProperty("Fixed Timestep").floatValue = 1f / 120f;
            var mx = so.FindProperty("Maximum Allowed Timestep"); if (mx != null) mx.floatValue = 0.05f;
            so.ApplyModifiedPropertiesWithoutUndo();
            Physics.defaultContactOffset = 0.01f;
            Physics.defaultSolverIterations = 8;
            Physics.defaultSolverVelocityIterations = 2;
        }

        static void ImportTmpEssentials()
        {
            if (AssetDatabase.FindAssets("t:TMP_Settings").Length > 0) return;
            string[] candidates =
            {
                "Packages/com.unity.ugui/Package Resources/TMP Essential Resources.unitypackage",
                "Packages/com.unity.textmeshpro/Package Resources/TMP Essential Resources.unitypackage",
            };
            foreach (var c in candidates)
            {
                string full = Path.GetFullPath(c);
                if (File.Exists(full)) { AssetDatabase.ImportPackage(full, false); Debug.Log("[InkDrift] Imported TMP essentials"); return; }
            }
            Debug.LogWarning("[InkDrift] TMP essentials package not found");
        }
    }
}
