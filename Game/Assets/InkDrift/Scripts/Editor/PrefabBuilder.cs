using System.IO;
using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Wraps every prop/tree FBX into a prefab: colliders, physics for knock-over props, layers, special face materials.</summary>
    public static class PrefabBuilder
    {
        const string PropOut = "Assets/InkDrift/Prefabs/Props";
        const string TreeOut = "Assets/InkDrift/Prefabs/Trees";

        [MenuItem("InkDrift/Setup/Build Prefabs")]
        public static void BuildAll()
        {
            Directory.CreateDirectory(PropOut);
            Directory.CreateDirectory(TreeOut);
            int n = 0;
            foreach (var guid in AssetDatabase.FindAssets("t:Model", new[] { "Assets/InkDrift/Models/Props", "Assets/InkDrift/Models/Trees" }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (model == null) continue;
                bool tree = path.Contains("/Models/Trees/");
                string name = Path.GetFileNameWithoutExtension(path);
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
                inst.name = name;
                Configure(inst, name.ToLowerInvariant(), tree);
                PrefabUtility.SaveAsPrefabAsset(inst, $"{(tree ? TreeOut : PropOut)}/{name}.prefab");
                Object.DestroyImmediate(inst);
                n++;
            }
            AssetDatabase.SaveAssets();
            Debug.Log($"[PrefabBuilder] built {n} prefabs");
        }

        static void SetLayerRecursive(Transform t, int layer)
        {
            t.gameObject.layer = layer;
            foreach (Transform c in t) SetLayerRecursive(c, layer);
        }

        static Bounds LocalBounds(GameObject go)
        {
            var b = new Bounds(Vector3.zero, Vector3.zero);
            bool first = true;
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mb = mf.sharedMesh.bounds;
                var m = go.transform.worldToLocalMatrix * r.transform.localToWorldMatrix;
                for (int i = 0; i < 8; i++)
                {
                    var c = mb.center + Vector3.Scale(mb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    var p = m.MultiplyPoint3x4(c);
                    if (first) { b = new Bounds(p, Vector3.zero); first = false; } else b.Encapsulate(p);
                }
            }
            return b;
        }

        static void Configure(GameObject go, string n, bool tree)
        {
            SetLayerRecursive(go.transform, tree ? 11 : 10);
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                ApplyFaceMaterials(r, n);
                if (tree && (n.Contains("grass") || n.Contains("fern") || n.Contains("litter") || n.Contains("weeds") || n.Contains("susuki")))
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            var b = LocalBounds(go);
            if (tree)
            {
                // trunk collider for street trees placed as GameObjects
                if (n.StartsWith("sakura") || n.StartsWith("keyaki") || n.StartsWith("ginkgo") || n.StartsWith("momiji") || n.StartsWith("kuromatsu"))
                {
                    var cc = go.AddComponent<CapsuleCollider>();
                    cc.radius = 0.28f; cc.height = 4f; cc.center = new Vector3(0, 2f, 0);
                }
                else if (n.StartsWith("rock") || n.StartsWith("cliff"))
                {
                    var mc = go.AddComponent<BoxCollider>();
                    mc.center = b.center; mc.size = b.size * 0.85f;
                }
                foreach (var t in go.GetComponentsInChildren<Transform>()) t.gameObject.isStatic = true;
                return;
            }

            // ---- props
            bool knock = n.Contains("cone") || n.Contains("construction_barrier") || n.Contains("recycle_bin") || n.Contains("garbage") || n.Contains("bicycle") || n.Contains("bench") || n.Contains("post_cone");
            bool none = n.Contains("manhole") || n.Contains("drain") || n.Contains("noren") || n.Contains("awning") || n.Contains("chochin") || n.Contains("akachochin")
                        || n.Contains("tunnel_lamp") || n.Contains("billboard_frame") || n.Contains("water_tank") || n.Contains("ac_outdoor") || n.Contains("kerb") || n.Contains("slope_protection");
            if (none) { foreach (var t in go.GetComponentsInChildren<Transform>()) t.gameObject.isStatic = true; return; }

            if (n.Contains("guardrail") || n.Contains("railing") || n.Contains("parapet") || n.Contains("jersey") || n.Contains("stone_retaining") || n.Contains("bridge_railing") || n.Contains("cone_bar"))
            {
                var bc = go.AddComponent<BoxCollider>();
                bc.center = new Vector3(b.center.x, Mathf.Max(0.5f, b.center.y), b.center.z);
                bc.size = new Vector3(b.size.x, Mathf.Max(1.0f, b.size.y), Mathf.Max(0.3f, b.size.z));
            }
            else if (n.Contains("pole") || n.Contains("lamp") || n.Contains("signal") || n.Contains("sign_post") || n.Contains("mirror") || n.Contains("delineator") || n.Contains("snow_pole") || n.Contains("bollard") || n.Contains("hydrant") || n.Contains("bus_stop") || n.Contains("parking_sign") || n.Contains("chevron"))
            {
                var cc = go.AddComponent<CapsuleCollider>();
                cc.radius = n.Contains("utility_pole") ? 0.2f : 0.12f;
                cc.height = Mathf.Min(b.size.y, 6f);
                cc.center = new Vector3(0, cc.height * 0.5f, 0);
            }
            else
            {
                var bc = go.AddComponent<BoxCollider>();
                bc.center = b.center; bc.size = b.size;
            }

            if (knock)
            {
                var rb = go.AddComponent<Rigidbody>();
                rb.mass = n.Contains("cone") ? 3f : n.Contains("bicycle") ? 16f : n.Contains("bench") ? 25f : 9f;
                rb.linearDamping = 0.2f; rb.angularDamping = 0.3f;
                rb.interpolation = RigidbodyInterpolation.Interpolate;
                rb.sleepThreshold = 0.05f;
            }
            else foreach (var t in go.GetComponentsInChildren<Transform>()) t.gameObject.isStatic = true;
        }

        /// <summary>Assign 2D-art faces (signs, vending fronts, billboards) to the dedicated material slots.</summary>
        static void ApplyFaceMaterials(MeshRenderer r, string n)
        {
            var mats = r.sharedMaterials;
            bool changed = false;
            for (int i = 0; i < mats.Length; i++)
            {
                if (mats[i] == null) continue;
                string mn = mats[i].name;
                Material repl = null;
                if (mn.StartsWith("M_VendingFront"))
                    repl = FaceMat(n.Contains("slim") ? "vending_front_icecream" : "vending_front_drinks", "Vending", 1.6f);
                else if (mn.StartsWith("M_BillboardFace"))
                    repl = FaceMat("bb_", "Billboard", 1.2f);
                else if (mn.StartsWith("M_SignFace"))
                {
                    string key = n.Contains("round") ? "roadsign_speed40" : n.Contains("triangle") ? "roadsign_tomare" : n.Contains("diamond") ? "roadsign_curve" : n.Contains("rect") ? "roadsign_oneway" : n.Contains("gantry") ? "gantry" : "roadsign_speed40";
                    repl = RoadSignMat(key);
                }
                else if (mn.StartsWith("M_BannerFace"))
                    repl = FaceMat("banner_", "Banner", 0.3f);
                if (repl != null) { mats[i] = repl; changed = true; }
            }
            if (changed) r.sharedMaterials = mats;
        }

        static Material FaceMat(string contains, string label, float emission)
        {
            string dir = "Assets/InkDrift/Art/Signs";
            string full = Path.GetFullPath(dir);
            if (!Directory.Exists(full)) return null;
            string pick = null;
            foreach (var f in Directory.GetFiles(full, "*_albedo.png"))
                if (Path.GetFileName(f).Contains(contains)) { pick = Path.GetFileName(f).Replace("_albedo.png", ""); break; }
            if (pick == null) return null;
            var m = MaterialLibrary.Ensure($"Toon_{label}_{pick}");
            MaterialLibrary.ApplyTextures(m, AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{pick}_albedo.png"), null, null, AssetDatabase.LoadAssetAtPath<Texture2D>($"{dir}/{pick}_emission.png"));
            MaterialLibrary.SetKeyword(m, "_EMISSION", "_UseEmission", File.Exists(Path.GetFullPath($"{dir}/{pick}_emission.png")));
            m.SetColor("_EmissionColor", Color.white * emission);
            m.SetFloat("_Smoothness", 0.7f); m.SetFloat("_ReflectStrength", 0.3f);
            return m;
        }

        static Material RoadSignMat(string key)
        {
            string p = $"Assets/InkDrift/Generated/Common/{key}.png";
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(p);
            if (tex == null) return null;
            var m = MaterialLibrary.Ensure("Toon_" + key);
            MaterialLibrary.ApplyTextures(m, tex, null, null, null);
            m.SetColor("_BaseColor", Color.white);
            m.SetFloat("_Smoothness", 0.6f);
            m.SetColor("_EmissionColor", new Color(0.08f, 0.08f, 0.08f));
            return m;
        }
    }
}
