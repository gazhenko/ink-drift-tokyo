using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace InkDrift.EditorTools
{
    /// <summary>Flat asphalt test pad for physics validation (-scene TestPad -physicsTest out.txt).</summary>
    public static class TestPadBuilder
    {
        [MenuItem("InkDrift/Setup/Build Test Pad")]
        public static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var kit = new PropKit("testpad", 1);
            var root = PropKit.Group("TestPad");
            var mat = MaterialLibrary.FromSet("road_asphalt_highway", "Toon_TestPad", 1f, 0.3f);
            MaterialLibrary.SetKeyword(mat, "_WORLD_UV", "_WorldUV", true); mat.SetFloat("_WorldUVScale", 0.2f);
            var mb = new MeshBuilder();
            float s = 700f;
            mb.Quad(0, new Vector3(-s, 0, -s), new Vector3(-s, 0, s), new Vector3(s, 0, s), new Vector3(s, 0, -s), Vector2.zero, Vector2.one, Color.white);
            var phys = new PhysicsMaterial("Asphalt") { dynamicFriction = 0.8f, staticFriction = 0.8f };
            kit.SaveObject(phys, "Asphalt");
            kit.MeshObject("Pad", root, mb, new[] { mat }, true, false, 9, phys);
            var cone = kit.FindPrefab("traffic_cone");
            for (int i = 0; i < 40; i++)
            {
                float a = i / 40f * Mathf.PI * 2f;
                kit.Place(cone, new Vector3(Mathf.Cos(a) * 30f, 0, Mathf.Sin(a) * 30f + 60f), Quaternion.identity, root);
            }
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional; sun.transform.rotation = Quaternion.Euler(40, 200, 0); sun.intensity = 1.4f; sun.shadows = LightShadows.Soft;
            RenderSettings.sun = sun;
            var sky = new Material(Shader.Find("InkDrift/Sky"));
            kit.SaveObject(sky, "Sky");
            RenderSettings.skybox = sky;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            new GameObject("ComicPostFX").AddComponent<ComicPostFX>();
            var camGo = new GameObject("Main Camera"); camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>(); cam.farClipPlane = 2000;
            var d = camGo.AddComponent<UniversalAdditionalCameraData>(); d.renderPostProcessing = true;
            camGo.AddComponent<AudioListener>();
            new GameObject("PhysicsTest").AddComponent<PhysicsTest>();
            string path = TrackGenerator.SceneDir + "/TestPad.unity";
            EditorSceneManager.SaveScene(scene, path);
            TrackGenerator.AddToBuild(path);
        }
    }
}
