using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace InkDrift.EditorTools
{
    /// <summary>Main menu: rooftop showroom over night Shibuya, neon turntable, graffiti wall, city ring.</summary>
    public static class MenuSceneBuilder
    {
        [MenuItem("InkDrift/Setup/Build Menu Scene")]
        public static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var kit = new PropKit("menu", 777);
            var root = PropKit.Group("Showroom");
            var def = TrackDef.Get("shibuya");

            // floor: wet rooftop deck
            var deck = MaterialLibrary.FromSet("concrete_smooth", "Toon_RooftopWet", 1f, 0.6f);
            MaterialLibrary.SetKeyword(deck, "_WET", "_Wet", true); deck.SetFloat("_WetAmount", 0.7f);
            deck.SetTextureScale("_BaseMap", Vector2.one * 0.25f);
            MaterialLibrary.SetKeyword(deck, "_WORLD_UV", "_WorldUV", true); deck.SetFloat("_WorldUVScale", 0.25f);
            var mb = new MeshBuilder();
            mb.Quad(0, new Vector3(-60, 0, -60), new Vector3(-60, 0, 60), new Vector3(60, 0, 60), new Vector3(60, 0, -60), Vector2.zero, Vector2.one * 30, Color.white);
            kit.MeshObject("Deck", root, mb, new[] { deck }, true, false);

            // turntable: dark disc + emissive neon ring
            var tt = new MeshBuilder();
            int seg = 64;
            for (int i = 0; i < seg; i++)
            {
                float a0 = i / (float)seg * Mathf.PI * 2, a1 = (i + 1) / (float)seg * Mathf.PI * 2;
                Vector3 p0 = new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0)), p1 = new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1));
                tt.Quad(0, p0 * 0.2f + Vector3.up * 0.12f, p1 * 0.2f + Vector3.up * 0.12f, p1 * 3.6f + Vector3.up * 0.12f, p0 * 3.6f + Vector3.up * 0.12f, Vector2.zero, Vector2.one, Color.white);
                tt.Quad(1, p0 * 3.6f, p0 * 3.6f + Vector3.up * 0.12f, p1 * 3.6f + Vector3.up * 0.12f, p1 * 3.6f, Vector2.zero, Vector2.one, Color.white);
            }
            var disc = MaterialLibrary.Flat("Toon_Turntable", new Color(0.08f, 0.08f, 0.1f), 0.85f, 0.6f, null, 0.8f);
            var neon = MaterialLibrary.Flat("Toon_NeonMagenta", new Color(1f, 0.2f, 0.5f), 0.5f, 0f, new Color(8f, 1.2f, 3.5f));
            var neonC = MaterialLibrary.Flat("Toon_NeonCyan", new Color(0.1f, 0.9f, 1f), 0.5f, 0f, new Color(0.6f, 6f, 8f));
            var turn = kit.MeshObject("TurntableMesh", root, tt, new[] { disc, neon }, true, true);
            var turntable = new GameObject("Turntable").transform;
            turntable.position = new Vector3(0, 0.12f, 0);
            turn.transform.SetParent(turntable, true);
            turn.isStatic = false;

            // graffiti wall + neon tubes behind the car
            var wall = new MeshBuilder();
            wall.Quad(0, new Vector3(-14, 0, 9), new Vector3(-14, 7, 9), new Vector3(14, 7, 9), new Vector3(14, 0, 9), Vector2.zero, new Vector2(1, 1), Color.white);
            var wallMat = MaterialLibrary.Ensure("Toon_GraffitiWall");
            var logo = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Art/UI/logo_inkdrift.png");
            var brick = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/InkDrift/Art/Textures/concrete_formwork/concrete_formwork_albedo.jpg");
            wallMat.SetTexture("_BaseMap", brick); wallMat.SetColor("_BaseColor", new Color(0.35f, 0.33f, 0.45f));
            kit.MeshObject("Wall", root, wall, new[] { wallMat }, false, true);
            if (logo)
            {
                var lm = new MeshBuilder();
                lm.Quad(0, new Vector3(-9, 1.6f, 8.9f), new Vector3(-9, 6.6f, 8.9f), new Vector3(9, 6.6f, 8.9f), new Vector3(9, 1.6f, 8.9f), new Vector2(0, 0), new Vector2(1, 1), Color.white);
                var logoMat = MaterialLibrary.Ensure("Toon_WallLogo");
                MaterialLibrary.ApplyTextures(logoMat, logo, null, null, logo);
                MaterialLibrary.SetKeyword(logoMat, "_EMISSION", "_UseEmission", true);
                logoMat.SetColor("_EmissionColor", Color.white * 0.9f);
                logoMat.EnableKeyword("_ALPHATEST_ON"); logoMat.SetFloat("_AlphaClip", 1); logoMat.SetFloat("_Cutoff", 0.35f);
                kit.MeshObject("WallLogo", root, lm, new[] { logoMat }, false, false);
            }
            var tubes = new MeshBuilder();
            tubes.Tube(0, new[] { new Vector3(-13, 0.3f, 8.7f), new Vector3(-13, 7.2f, 8.7f) }, 0.07f, 8, Color.white);
            tubes.Tube(1, new[] { new Vector3(13, 0.3f, 8.7f), new Vector3(13, 7.2f, 8.7f) }, 0.07f, 8, Color.white);
            tubes.Tube(0, new[] { new Vector3(-12, 7.4f, 8.7f), new Vector3(12, 7.4f, 8.7f) }, 0.07f, 8, Color.white);
            kit.MeshObject("NeonTubes", root, tubes, new[] { neon, neonC }, false, false);

            var lights = new System.Collections.Generic.List<Light>();
            Light L(Vector3 p, Color c, float range, float inten, LightType type = LightType.Point, Vector3? look = null)
            {
                var g = new GameObject("Light");
                g.transform.SetParent(root, false);
                g.transform.position = p;
                if (look.HasValue) g.transform.rotation = Quaternion.LookRotation(look.Value - p);
                var l = g.AddComponent<Light>();
                l.type = type; l.color = c; l.range = range; l.intensity = inten;
                if (type == LightType.Spot) { l.spotAngle = 55; l.innerSpotAngle = 25; l.shadows = LightShadows.Soft; }
                lights.Add(l);
                return l;
            }
            L(new Vector3(-6, 5, -3), new Color(1f, 0.25f, 0.6f), 16, 30f, LightType.Spot, Vector3.up * 0.5f);
            L(new Vector3(6, 5, -3), new Color(0.2f, 0.9f, 1f), 16, 30f, LightType.Spot, Vector3.up * 0.5f);
            L(new Vector3(0, 7, 2), new Color(1f, 0.95f, 0.9f), 14, 40f, LightType.Spot, Vector3.zero);
            L(new Vector3(0, 0.4f, 0), new Color(1f, 0.2f, 0.55f), 4, 1.2f);

            // city ring for depth
            var bk = new BuildingKit(true);
            foreach (var m in bk.facades) m.SetFloat("_VertexTint", 1f);
            var city = new MeshBuilder();
            var rng = kit;
            for (int i = 0; i < 140; i++)
            {
                float a = kit.R(0, Mathf.PI * 2), r = kit.R(90, 420);
                Vector3 c = new Vector3(Mathf.Cos(a) * r, -40f, Mathf.Sin(a) * r);
                if (bk.TryReserve(c, Quaternion.Euler(0, kit.R(0, 90), 0), kit.R(18, 32), kit.R(18, 32), out var lot))
                {
                    float h = kit.R(40f, 190f);
                    if (h > 110f) bk.AddTower(city, kit, lot, h, kit.RI(0, bk.facades.Count), CityBuilder.Tint(kit), -40f);
                    else bk.AddBuilding(city, kit, lot, h, kit.RI(0, bk.facades.Count), false, true, CityBuilder.Tint(kit), null, -40f);
                }
            }
            kit.MeshObject("CityRing", root, city, bk.Materials, false, false);

            // look + post (reuse Shibuya night grading)
            var sunGo = new GameObject("Moon");
            sunGo.transform.rotation = Quaternion.Euler(40, 150, 0);
            var sun = sunGo.AddComponent<Light>(); sun.type = LightType.Directional; sun.intensity = 0.35f; sun.color = new Color(0.55f, 0.65f, 1f); sun.shadows = LightShadows.Soft;
            RenderSettings.sun = sun;
            var shib = AssetDatabase.LoadAssetAtPath<Material>("Assets/InkDrift/Generated/shibuya/Sky.asset");
            var sky = new Material(Shader.Find("InkDrift/Sky"));
            var Ld = def.look;
            sky.SetColor("_ZenithColor", Ld.zenith); sky.SetColor("_HorizonColor", Ld.horizon); sky.SetColor("_HorizonGlow", Ld.glow);
            sky.SetFloat("_GlowStrength", 1.1f); sky.SetFloat("_GlowHeight", 0.15f); sky.SetFloat("_StarDensity", 0.6f); sky.SetFloat("_MoonSize", 0.012f);
            sky.SetFloat("_SunSize", 0.0005f); sky.SetFloat("_CloudCover", 0.35f); sky.SetColor("_CloudColor", Ld.cloudLit); sky.SetColor("_CloudShadow", Ld.cloudShadow);
            kit.SaveObject(sky, "MenuSky");
            RenderSettings.skybox = sky;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = Ld.ambSky; RenderSettings.ambientEquatorColor = Ld.ambEquator; RenderSettings.ambientGroundColor = Ld.ambGround;
            RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Linear; RenderSettings.fogColor = Ld.fogColor; RenderSettings.fogStartDistance = 60; RenderSettings.fogEndDistance = 700;
            var fx = new GameObject("ComicPostFX").AddComponent<ComicPostFX>();
            fx.fogColor = Ld.fogColor; fx.fogStart = 60; fx.fogEnd = 700; fx.shadowTint = Ld.shadowTint; fx.rimColor = Ld.rimColor;
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>("Assets/InkDrift/Generated/shibuya/PostProfile.asset");
            var vol = new GameObject("PostVolume").AddComponent<Volume>();
            vol.isGlobal = true; vol.sharedProfile = profile;

            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            camGo.transform.position = new Vector3(-4, 1.6f, -6.5f);
            camGo.transform.LookAt(new Vector3(0, 0.7f, 0));
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 38f; cam.nearClipPlane = 0.1f; cam.farClipPlane = 1500f; cam.allowHDR = true;
            var data = camGo.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true; data.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing; data.antialiasingQuality = AntialiasingQuality.High;
            camGo.AddComponent<AudioListener>();
            camGo.AddComponent<PlanarReflection>();

            var mc = new GameObject("Menu").AddComponent<MenuController>();
            mc.turntable = turntable;
            mc.cam = cam;
            mc.accentLights = lights.ToArray();

            System.IO.Directory.CreateDirectory(TrackGenerator.SceneDir);
            string path = TrackGenerator.SceneDir + "/MainMenu.unity";
            EditorSceneManager.SaveScene(scene, path);
            TrackGenerator.AddToBuild(path);
            AssetDatabase.SaveAssets();
        }
    }
}
