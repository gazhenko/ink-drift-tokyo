using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace InkDrift.EditorTools
{
    /// <summary>Generates the three track scenes from layouts + theme builders. Batch: -executeMethod InkDrift.EditorTools.TrackGenerator.GenerateAll</summary>
    public static class TrackGenerator
    {
        public const string SceneDir = "Assets/InkDrift/Scenes";

        [MenuItem("InkDrift/Tracks/Generate All")]
        public static void GenerateAll()
        {
            foreach (var id in new[] { "shibuya", "shuto", "okutama" }) Generate(id);
        }

        [MenuItem("InkDrift/Tracks/Generate Shibuya")] public static void GenShibuya() => Generate("shibuya");
        [MenuItem("InkDrift/Tracks/Generate Shuto")] public static void GenShuto() => Generate("shuto");
        [MenuItem("InkDrift/Tracks/Generate Okutama")] public static void GenOkutama() => Generate("okutama");

        public static void GenerateFromCommandLine()
        {
            string ids = CommandLine.Get("-tracks", "shibuya,shuto,okutama");
            foreach (var id in ids.Split(',')) Generate(id.Trim());
        }

        public static void Generate(string id)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var def = TrackDef.Get(id);
            var layout = TrackLayout.Build(id, 2f, def.elevation, def.bankPerCurv, def.maxBank);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var kit = new PropKit(id, def.seed);
            var root = PropKit.Group("Track_" + id);

            var path = BuildPathData(layout, def, root);
            switch (def.theme)
            {
                case TrackTheme.City: CityBuilder.Build(kit, layout, def, root); break;
                case TrackTheme.Expressway: ExpresswayBuilder.Build(kit, layout, def, root); break;
                case TrackTheme.Mountain: MountainBuilder.Build(kit, layout, def, root); break;
            }
            StartGantry(kit, layout, def, root);
            ApplyLook(kit, def, root);
            SetupGameplay(def, root);

            kit.Report();
            System.IO.Directory.CreateDirectory(SceneDir);
            string scenePath = $"{SceneDir}/Track_{id}.unity";
            EditorSceneManager.SaveScene(scene, scenePath);
            AddToBuild(scenePath);
            AssetDatabase.SaveAssets();
            Debug.Log($"[TrackGen] {id}: {layout.length:0} m, {layout.Count} samples, generated in {sw.Elapsed.TotalSeconds:0.0}s");
        }

        public static void AddToBuild(string scenePath)
        {
            var list = EditorBuildSettings.scenes.ToList();
            if (!list.Any(s => s.path == scenePath)) list.Add(new EditorBuildSettingsScene(scenePath, true));
            // keep MainMenu first
            list = list.OrderBy(s => s.path.Contains("MainMenu") ? 0 : 1).ThenBy(s => s.path).ToList();
            EditorBuildSettings.scenes = list.ToArray();
        }

        // ------------------------------------------------------------------ path data, racing line, speed profile
        static TrackPath BuildPathData(TrackLayout t, TrackDef def, Transform root)
        {
            var go = new GameObject("TrackPath");
            go.transform.SetParent(root, false);
            var tp = go.AddComponent<TrackPath>();
            int n = t.Count;
            tp.trackId = def.id;
            tp.points = new Vector3[n];
            tp.rights = new Vector3[n];
            tp.halfWidths = new float[n];
            tp.dist = new float[n];
            for (int i = 0; i < n; i++)
            {
                tp.points[i] = t.pts[i] + Vector3.up * 0.05f;
                tp.rights[i] = t.right[i];
                tp.halfWidths[i] = def.roadHalfWidth;
                tp.dist[i] = t.dist[i];
            }
            tp.length = t.length;
            tp.startDistance = def.startDistance;

            // racing line: iterative lateral smoothing inside the road
            float[] off = new float[n];
            float margin = def.theme == TrackTheme.Mountain ? 1.3f : 1.8f;
            float lim = def.roadHalfWidth - margin;
            for (int it = 0; it < 400; it++)
            {
                for (int i = 0; i < n; i++)
                {
                    Vector3 a = t.pts[t.Wrap(i - 3)] + t.right[t.Wrap(i - 3)] * off[t.Wrap(i - 3)];
                    Vector3 b = t.pts[t.Wrap(i + 3)] + t.right[t.Wrap(i + 3)] * off[t.Wrap(i + 3)];
                    Vector3 mid = (a + b) * 0.5f;
                    float target = Vector3.Dot(mid - t.pts[i], t.right[i]);
                    off[i] = Mathf.Clamp(Mathf.Lerp(off[i], target, 0.5f), -lim, lim);
                }
            }
            tp.racingLine = new Vector3[n];
            for (int i = 0; i < n; i++) tp.racingLine[i] = tp.points[i] + t.right[i] * off[i];

            // speed profile from racing-line curvature
            float[] v = new float[n];
            for (int i = 0; i < n; i++)
            {
                Vector3 a = tp.racingLine[t.Wrap(i - 4)], b = tp.racingLine[i], c = tp.racingLine[t.Wrap(i + 4)];
                float k = Curvature(a, b, c);
                float mu = 1.18f;
                v[i] = Mathf.Clamp(Mathf.Sqrt(mu * 9.81f / Mathf.Max(k, 1e-4f)), 11f, def.theme == TrackTheme.Expressway ? 72f : 58f);
            }
            float ds = t.length / n;
            for (int pass = 0; pass < 3; pass++)
            {
                for (int i = n - 1; i >= 0; i--) v[i] = Mathf.Min(v[i], Mathf.Sqrt(v[t.Wrap(i + 1)] * v[t.Wrap(i + 1)] + 2f * 8f * ds));
                for (int i = 0; i < n; i++) v[i] = Mathf.Min(v[i], Mathf.Sqrt(v[t.Wrap(i - 1)] * v[t.Wrap(i - 1)] + 2f * 5f * ds));
            }
            tp.targetSpeed = v;
            return tp;
        }

        static float Curvature(Vector3 a, Vector3 b, Vector3 c)
        {
            a.y = b.y = c.y = 0;
            float ab = Vector3.Distance(a, b), bc = Vector3.Distance(b, c), ca = Vector3.Distance(c, a);
            float area2 = Vector3.Cross(b - a, c - a).magnitude;
            if (ab * bc * ca < 1e-4f) return 0f;
            return 2f * area2 / (ab * bc * ca);
        }

        // ------------------------------------------------------------------ start gantry with comic banner
        static void StartGantry(PropKit kit, TrackLayout t, TrackDef def, Transform root)
        {
            int i = t.IndexAt(def.startDistance);
            Vector3 p = t.pts[i];
            Vector3 r = t.right[i];
            Vector3 fwd = t.tan[i];
            var g = PropKit.Group("StartGantry", root);
            float hw = def.roadHalfWidth + 0.8f;
            var mb = new MeshBuilder();
            var rot = Quaternion.LookRotation(fwd, Vector3.up);
            // two legs + crossbeam
            mb.Box(0, p + r * hw + Vector3.up * 3.6f, rot, new Vector3(0.45f, 7.2f, 0.45f), 1f, Color.white);
            mb.Box(0, p - r * hw + Vector3.up * 3.6f, rot, new Vector3(0.45f, 7.2f, 0.45f), 1f, Color.white);
            mb.Box(0, p + Vector3.up * 7.0f, rot, new Vector3(hw * 2f + 0.6f, 0.5f, 0.5f), 1f, Color.white);
            // banner (both faces)
            float bw = hw * 1.6f, bh = bw / 2.6f;
            Vector3 c = p + Vector3.up * (6.75f - bh * 0.5f);
            Vector3 hx = r * bw * 0.5f, hy = Vector3.up * bh * 0.5f, fz = fwd * 0.06f;
            mb.Quad(1, c - hx - hy - fz, c - hx + hy - fz, c + hx + hy - fz, c + hx - hy - fz, Vector2.zero, Vector2.one, Color.white);
            mb.Quad(1, c + hx - hy + fz, c + hx + hy + fz, c - hx + hy + fz, c - hx - hy + fz, new Vector2(0, 0), Vector2.one, Color.white);
            var steel = MaterialLibrary.Flat("Toon_GantrySteel", new Color(0.12f, 0.12f, 0.16f), 0.5f, 0.6f, null, 0.4f);
            var banner = MaterialLibrary.Ensure("Toon_StartBanner");
            var logo = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Art/UI/logo_inkdrift.png");
            if (logo) banner.SetTexture("_BaseMap", logo);
            banner.SetColor("_BaseColor", Color.white);
            banner.SetFloat("_AlphaClip", 1); banner.EnableKeyword("_ALPHATEST_ON"); banner.SetFloat("_Cutoff", 0.4f);
            banner.SetFloat("_Cull", 0);
            banner.SetColor("_EmissionColor", def.look.night ? new Color(0.6f, 0.6f, 0.6f) : Color.black);
            if (logo) { banner.SetTexture("_EmissionMap", logo); MaterialLibrary.SetKeyword(banner, "_EMISSION", "_UseEmission", def.look.night); }
            kit.MeshObject("Gantry", g, mb, new[] { steel, banner }, false);

            // checkered start line
            var line = new MeshBuilder();
            for (int k = 0; k < 2; k++)
            {
                int j = t.Wrap(i + k);
                int cells = Mathf.RoundToInt(def.roadHalfWidth * 2f / 0.75f);
                for (int s = 0; s < cells; s++)
                {
                    if ((s + k) % 2 == 1) continue;
                    float x0 = -def.roadHalfWidth + s * 0.75f, x1 = x0 + 0.75f;
                    Vector3 o0 = t.pts[j] + Vector3.up * 0.03f, o1 = t.pts[t.Wrap(j + 1)] + Vector3.up * 0.03f;
                    Vector3 rr0 = t.BankedRight(j), rr1 = t.BankedRight(t.Wrap(j + 1));
                    Vector3 a = o0 + rr0 * x0, b = o1 + rr1 * x0;
                    Vector3 cc = o1 + rr1 * x1, d = o0 + rr0 * x1;
                    line.Quad(0, a, b, cc, d, Vector2.zero, Vector2.one, Color.white);
                }
            }
            kit.MeshObject("StartLine", g, line, new[] { MaterialLibrary.Flat("Toon_PaintWhite", new Color(0.95f, 0.95f, 0.92f), 0.4f) }, false, false);
        }

        // ------------------------------------------------------------------ lighting / sky / post / comic settings
        static void ApplyLook(PropKit kit, TrackDef def, Transform root)
        {
            var L = def.look;
            var sunGo = new GameObject("Sun");
            sunGo.transform.SetParent(root, false);
            sunGo.transform.rotation = Quaternion.Euler(L.sunElevation, L.sunAzimuth, 0f);
            var sun = sunGo.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = L.sunColor;
            sun.intensity = L.sunIntensity;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 1f;
            sun.shadowBias = 0.05f; sun.shadowNormalBias = 0.4f;
            RenderSettings.sun = sun;

            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = L.ambSky;
            RenderSettings.ambientEquatorColor = L.ambEquator;
            RenderSettings.ambientGroundColor = L.ambGround;

            var sky = new Material(Shader.Find("InkDrift/Sky"));
            sky.SetColor("_ZenithColor", L.zenith); sky.SetColor("_HorizonColor", L.horizon); sky.SetColor("_GroundColor", L.skyGround);
            sky.SetColor("_HorizonGlow", L.glow); sky.SetFloat("_GlowHeight", L.glowHeight); sky.SetFloat("_GlowStrength", L.glowStrength);
            sky.SetColor("_SunColor", L.skySun); sky.SetFloat("_SunSize", Mathf.Max(0.0005f, L.sunSize)); sky.SetFloat("_SunHalo", L.sunSize > 0 ? 0.6f : 0f);
            sky.SetColor("_CloudColor", L.cloudLit); sky.SetColor("_CloudShadow", L.cloudShadow); sky.SetFloat("_CloudCover", L.cloudCover); sky.SetFloat("_CloudScale", L.cloudScale);
            sky.SetFloat("_StarDensity", L.stars); sky.SetFloat("_MoonSize", L.moonSize); sky.SetFloat("_Exposure", L.skyExposure);
            kit.SaveObject(sky, "Sky");
            RenderSettings.skybox = sky;

            var hdri = AssetDatabase.FindAssets(L.hdri + " t:Cubemap").Select(AssetDatabase.GUIDToAssetPath).Select(AssetDatabase.LoadAssetAtPath<Cubemap>).FirstOrDefault();
            if (hdri != null)
            {
                RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
                RenderSettings.customReflectionTexture = hdri;
            }
            RenderSettings.reflectionIntensity = L.reflectionIntensity;

            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = L.fogColor;
            RenderSettings.fogStartDistance = L.fogStart;
            RenderSettings.fogEndDistance = L.fogEnd;

            var fxGo = new GameObject("ComicPostFX");
            fxGo.transform.SetParent(root, false);
            var fx = fxGo.AddComponent<ComicPostFX>();
            fx.fogColor = L.fogColor; fx.fogStart = L.fogStart; fx.fogEnd = L.fogEnd;
            fx.shadowTint = L.shadowTint; fx.rimColor = L.rimColor; fx.outlineWidth = L.outlineWidth; fx.halftoneStrength = L.halftone;

            // post volume
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            kit.SaveObject(profile, "PostProfile");
            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(L.bloomIntensity); bloom.threshold.Override(L.bloomThreshold); bloom.scatter.Override(L.bloomScatter);
            bloom.highQualityFiltering.Override(true);
            var tone = profile.Add<Tonemapping>(true); tone.mode.Override(TonemappingMode.Neutral);
            var ca = profile.Add<ColorAdjustments>(true);
            ca.saturation.Override(L.saturation); ca.contrast.Override(L.contrast); ca.postExposure.Override(L.exposure);
            var wb = profile.Add<WhiteBalance>(true); wb.temperature.Override(L.temperature); wb.tint.Override(L.tint);
            var vig = profile.Add<Vignette>(true); vig.intensity.Override(L.vignette); vig.smoothness.Override(0.45f); vig.color.Override(new Color(0.06f, 0.02f, 0.1f));
            var chrom = profile.Add<ChromaticAberration>(true); chrom.intensity.Override(0.06f);
            var mb = profile.Add<MotionBlur>(true); mb.intensity.Override(0.22f); mb.quality.Override(MotionBlurQuality.Medium);
            var smh = profile.Add<ShadowsMidtonesHighlights>(true);
            smh.shadows.Override(new Vector4(0.95f, 0.92f, 1.08f, 0f));
            foreach (var comp in profile.components) { comp.name = comp.GetType().Name; AssetDatabase.AddObjectToAsset(comp, profile); }
            var volGo = new GameObject("PostVolume");
            volGo.transform.SetParent(root, false);
            var vol = volGo.AddComponent<Volume>();
            vol.isGlobal = true; vol.priority = 0; vol.sharedProfile = profile;
            EditorUtility.SetDirty(profile);
        }

        static void SetupGameplay(TrackDef def, Transform root)
        {
            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.nearClipPlane = 0.15f; cam.farClipPlane = def.theme == TrackTheme.City ? 1600f : 3000f;
            cam.fieldOfView = 60f; cam.allowHDR = true; cam.allowMSAA = false;
            var data = camGo.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            data.antialiasingQuality = AntialiasingQuality.High;
            data.dithering = true;
            data.renderShadows = true;
            data.requiresDepthOption = CameraOverrideOption.On;
            camGo.AddComponent<AudioListener>();
            if (def.wet) camGo.AddComponent<PlanarReflection>();
            var t = Object.FindAnyObjectByType<TrackPath>();
            if (t != null)
            {
                var pose = t.GridPose(0);
                camGo.transform.position = pose.position - pose.rotation * Vector3.forward * 7f + Vector3.up * 2.5f;
                camGo.transform.rotation = Quaternion.LookRotation(pose.position - camGo.transform.position);
            }

            var race = new GameObject("RaceBootstrap");
            var rb = race.AddComponent<RaceBootstrap>();
            rb.trackId = def.id;
            rb.night = def.look.night;
            rb.mainCamera = cam;

            if (def.theme == TrackTheme.Expressway)
            {
                var traffic = new GameObject("Traffic").AddComponent<TrafficSystem>();
                traffic.count = 16;
            }
        }
    }
}
