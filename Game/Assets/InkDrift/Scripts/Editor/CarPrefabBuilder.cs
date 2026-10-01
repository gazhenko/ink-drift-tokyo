using System.IO;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Models/Cars/&lt;id&gt;/&lt;id&gt;.fbx → Resources/Cars/Car_&lt;id&gt;.prefab (+ traffic → Resources/Traffic). Copies dims JSON to Resources/CarDims.</summary>
    public static class CarPrefabBuilder
    {
        [MenuItem("InkDrift/Setup/Build Car Prefabs")]
        public static void BuildAll()
        {
            Directory.CreateDirectory("Assets/InkDrift/Resources/Cars");
            Directory.CreateDirectory("Assets/InkDrift/Resources/Traffic");
            Directory.CreateDirectory("Assets/InkDrift/Resources/CarDims");
            foreach (var spec in CarCatalog.All)
            {
                string dir = $"Assets/InkDrift/Models/Cars/{spec.id}";
                string fbx = $"{dir}/{spec.id}.fbx";
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
                if (model == null) { Debug.LogWarning("[Cars] missing " + fbx); continue; }
                string dims = $"{dir}/{spec.id}_dims.json";
                if (File.Exists(Path.GetFullPath(dims)))
                {
                    string dst = $"Assets/InkDrift/Resources/CarDims/{spec.id}.json";
                    File.Copy(Path.GetFullPath(dims), Path.GetFullPath(dst), true);
                    AssetDatabase.ImportAsset(dst);
                }
                BuildHero(model, spec);
            }
            CarCatalog.Reload();
            string tdir = "Assets/InkDrift/Models/Cars/Traffic";
            if (Directory.Exists(Path.GetFullPath(tdir)))
                foreach (var f in Directory.GetFiles(Path.GetFullPath(tdir), "*.fbx"))
                {
                    var model = AssetDatabase.LoadAssetAtPath<GameObject>($"{tdir}/{Path.GetFileName(f)}");
                    if (model != null) BuildTraffic(model);
                }
            AssetDatabase.SaveAssets();
        }

        static Transform Find(Transform root, string name)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name == name) return t;
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name.StartsWith(name)) return t;
            return null;
        }

        static void BuildHero(GameObject model, CarSpec spec)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            go.name = spec.prefabName;
            CarFactory.SetLayer(go.transform, CarController.CarLayer);

            var rb = go.AddComponent<Rigidbody>();
            rb.mass = spec.mass;
            var car = go.AddComponent<CarController>();
            car.spec = CarCatalog.Get(spec.id).Clone();
            string[] wn = { "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR" };
            string[] cn = { "Caliper_FL", "Caliper_FR", "Caliper_RL", "Caliper_RR" };
            for (int i = 0; i < 4; i++)
            {
                var w = Find(go.transform, wn[i]);
                if (w != null) { w.SetParent(go.transform, true); car.wheelVisuals[i] = w; }
                var c = Find(go.transform, cn[i]);
                if (c != null) { c.SetParent(go.transform, true); car.caliperVisuals[i] = c; }
            }

            // body collider: lower hull + cabin box from body renderer bounds
            var body = Find(go.transform, "Body");
            Bounds b = new Bounds(Vector3.zero, Vector3.zero); bool first = true;
            foreach (var r in (body != null ? body : go.transform).GetComponentsInChildren<MeshRenderer>())
            {
                if (r.name.StartsWith("Wheel") || r.name.StartsWith("Caliper")) continue;
                var bb = r.bounds;
                bb.center = go.transform.InverseTransformPoint(bb.center);
                if (first) { b = bb; first = false; } else b.Encapsulate(bb);
            }
            float clearance = 0.18f;
            var lower = go.AddComponent<BoxCollider>();
            float lowerTop = Mathf.Lerp(b.min.y, b.max.y, 0.55f);
            lower.center = new Vector3(b.center.x, (clearance + lowerTop) * 0.5f, b.center.z);
            lower.size = new Vector3(b.size.x * 0.96f, lowerTop - clearance, b.size.z * 0.97f);
            var cabin = go.AddComponent<BoxCollider>();
            cabin.center = new Vector3(b.center.x, (lowerTop + b.max.y) * 0.5f, b.center.z - b.size.z * 0.05f);
            cabin.size = new Vector3(b.size.x * 0.78f, b.max.y - lowerTop, b.size.z * 0.5f);
            var pm = new PhysicsMaterial("CarBody") { dynamicFriction = 0.25f, staticFriction = 0.25f, bounciness = 0.05f, frictionCombine = PhysicsMaterialCombine.Minimum };
            AssetDatabase.CreateAsset(pm, $"Assets/InkDrift/Resources/Cars/{spec.prefabName}_phys.physicMaterial");
            lower.sharedMaterial = pm; cabin.sharedMaterial = pm;

            // ricer rims: per-car wheel colors (FBX rim materials are read-only sub-assets, so swap in library materials)
            var rimCol = spec.id switch
            {
                "hachi" => new Color(0.72f, 0.45f, 0.18f), "kaiju" => new Color(0.86f, 0.68f, 0.18f), "zenkai" => new Color(0.82f, 0.84f, 0.88f),
                "raijin" => new Color(0.78f, 0.6f, 0.16f), _ => new Color(0.95f, 0.95f, 0.95f),
            };
            var rim = MaterialLibrary.Flat("Toon_Rim_" + spec.id, rimCol, 0.85f, 0.85f, null, 0.9f);
            rim.SetFloat("_SpecSize", 0.2f); rim.SetFloat("_SpecIntensity", 1.6f);
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++) if (mats[i] != null && mats[i].name.StartsWith("M_Rim")) { mats[i] = rim; changed = true; }
                if (changed) r.sharedMaterials = mats;
            }

            var fx = go.AddComponent<CarEffects>();
            var ex = new System.Collections.Generic.List<Transform>();
            foreach (var n in new[] { "Exhaust_L", "Exhaust_R" }) { var t = Find(go.transform, n); if (t) ex.Add(t); }
            fx.exhaustPoints = ex.ToArray();
            go.AddComponent<AudioSource>();
            go.AddComponent<EngineAudio>().car = car;

            // reflection probe that follows the car (refreshed by script) for neon/sunset reflections on paint
            var probeGo = new GameObject("PaintProbe");
            probeGo.transform.SetParent(go.transform, false);
            probeGo.transform.localPosition = new Vector3(0, 1.2f, 0);
            var probe = probeGo.AddComponent<ReflectionProbe>();
            probe.mode = UnityEngine.Rendering.ReflectionProbeMode.Realtime;
            probe.refreshMode = UnityEngine.Rendering.ReflectionProbeRefreshMode.ViaScripting;
            probe.timeSlicingMode = UnityEngine.Rendering.ReflectionProbeTimeSlicingMode.IndividualFaces;
            probe.resolution = 128; probe.size = new Vector3(14, 8, 14); probe.boxProjection = false; probe.importance = 2;
            probe.cullingMask = ~((1 << CarController.CarLayer) | (1 << 11));
            probe.farClipPlane = 300f; probe.hdr = true;
            probeGo.AddComponent<ProbeUpdater>();

            PrefabUtility.SaveAsPrefabAsset(go, $"Assets/InkDrift/Resources/Cars/{spec.prefabName}.prefab");
            Object.DestroyImmediate(go);
            Debug.Log("[Cars] built " + spec.prefabName);
        }

        static void BuildTraffic(GameObject model)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            string n = Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(model));
            string pname = "Traffic_" + n.Replace("traffic_", "");
            go.name = pname;
            Bounds b = new Bounds(Vector3.zero, Vector3.zero); bool first = true;
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                var bb = r.bounds;
                if (first) { b = bb; first = false; } else b.Encapsulate(bb);
            }
            var col = go.AddComponent<BoxCollider>();
            col.center = go.transform.InverseTransformPoint(b.center) + Vector3.up * 0.05f;
            col.size = new Vector3(b.size.x * 0.97f, b.size.y * 0.9f, b.size.z * 0.98f);
            var rb = go.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.mass = 1200f;
            PrefabUtility.SaveAsPrefabAsset(go, $"Assets/InkDrift/Resources/Traffic/{pname}.prefab");
            Object.DestroyImmediate(go);
        }
    }
}
