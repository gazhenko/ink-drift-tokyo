using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift.EditorTools
{
    /// <summary>Generator helpers: prefab lookup (fuzzy), instancing into scenes, mesh asset storage.</summary>
    public class PropKit
    {
        public readonly string trackId;
        public readonly string genDir;
        Mesh container;
        int meshCounter;
        readonly Dictionary<string, GameObject> prefabCache = new Dictionary<string, GameObject>();
        static string[] allPrefabs;
        public readonly HashSet<string> missing = new HashSet<string>();
        public System.Random rng;

        public PropKit(string id, int seed)
        {
            trackId = id;
            genDir = $"Assets/InkDrift/Generated/{id}";
            if (AssetDatabase.IsValidFolder(genDir)) AssetDatabase.DeleteAsset(genDir);
            Directory.CreateDirectory(genDir);
            AssetDatabase.Refresh();
            rng = new System.Random(seed);
            allPrefabs = null;
        }

        public float R(float a, float b) => a + (float)rng.NextDouble() * (b - a);
        public int RI(int a, int bExclusive) => rng.Next(a, bExclusive);
        public bool Chance(float p) => rng.NextDouble() < p;
        public T Pick<T>(IList<T> list) => list[rng.Next(list.Count)];

        public Mesh SaveMesh(Mesh m)
        {
            m.name = $"{trackId}_{meshCounter++:0000}_{m.name}";
            if (container == null)
            {
                container = m;
                AssetDatabase.CreateAsset(m, $"{genDir}/{trackId}_meshes.asset");
            }
            else AssetDatabase.AddObjectToAsset(m, container);
            return m;
        }

        public void SaveObject(Object o, string name)
        {
            AssetDatabase.CreateAsset(o, $"{genDir}/{name}.asset");
        }

        /// <summary>Create a GameObject with mesh + materials (+ optional collider).</summary>
        public GameObject MeshObject(string name, Transform parent, MeshBuilder mb, Material[] mats, bool collider = false, bool shadows = true, int layer = 9, PhysicsMaterial physMat = null)
        {
            if (mb.VertexCount == 0) return null;
            var mesh = SaveMesh(mb.ToMesh(name));
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.layer = layer;
            go.isStatic = true;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            var use = new Material[mesh.subMeshCount];
            for (int i = 0; i < use.Length; i++) use[i] = mats[Mathf.Min(i, mats.Length - 1)];
            mr.sharedMaterials = use;
            mr.shadowCastingMode = shadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
            if (collider)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = mesh;
                if (physMat != null) mc.sharedMaterial = physMat;
            }
            return go;
        }

        public GameObject ColliderOnly(string name, Transform parent, MeshBuilder mb, PhysicsMaterial physMat = null)
        {
            if (mb.VertexCount == 0) return null;
            var mesh = SaveMesh(mb.ToMesh(name));
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.layer = 9;
            go.isStatic = true;
            var mc = go.AddComponent<MeshCollider>();
            mc.sharedMesh = mesh;
            if (physMat != null) mc.sharedMaterial = physMat;
            return go;
        }

        public GameObject FindPrefab(params string[] names)
        {
            string key = string.Join("|", names);
            if (prefabCache.TryGetValue(key, out var cached)) return cached;
            allPrefabs ??= AssetDatabase.FindAssets("t:Prefab", new[] { "Assets/InkDrift/Prefabs" });
            GameObject found = null;
            foreach (var n in names)
            {
                foreach (var g in allPrefabs)
                {
                    string p = AssetDatabase.GUIDToAssetPath(g);
                    string f = Path.GetFileNameWithoutExtension(p).ToLowerInvariant();
                    if (f == n.ToLowerInvariant()) { found = AssetDatabase.LoadAssetAtPath<GameObject>(p); break; }
                }
                if (found) break;
            }
            if (!found)
                foreach (var n in names)
                {
                    foreach (var g in allPrefabs)
                    {
                        string p = AssetDatabase.GUIDToAssetPath(g);
                        string f = Path.GetFileNameWithoutExtension(p).ToLowerInvariant();
                        if (f.Contains(n.ToLowerInvariant())) { found = AssetDatabase.LoadAssetAtPath<GameObject>(p); break; }
                    }
                    if (found) break;
                }
            if (!found) missing.Add(names[0]);
            prefabCache[key] = found;
            return found;
        }

        public List<GameObject> FindPrefabs(string contains, string folder = null)
        {
            allPrefabs ??= AssetDatabase.FindAssets("t:Prefab", new[] { "Assets/InkDrift/Prefabs" });
            var list = new List<GameObject>();
            foreach (var g in allPrefabs)
            {
                string p = AssetDatabase.GUIDToAssetPath(g);
                if (folder != null && !p.Contains("/" + folder + "/")) continue;
                if (Path.GetFileNameWithoutExtension(p).ToLowerInvariant().Contains(contains.ToLowerInvariant()))
                    list.Add(AssetDatabase.LoadAssetAtPath<GameObject>(p));
            }
            return list;
        }

        public GameObject Place(GameObject prefab, Vector3 pos, Quaternion rot, Transform parent, float scale = 1f)
        {
            if (prefab == null) return null;
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            go.transform.SetPositionAndRotation(pos, rot);
            if (scale != 1f) go.transform.localScale *= scale;
            return go;
        }

        public GameObject Place(string name, Vector3 pos, Quaternion rot, Transform parent, float scale = 1f)
            => Place(FindPrefab(name), pos, rot, parent, scale);

        public static Transform Group(string name, Transform parent = null)
        {
            var g = new GameObject(name);
            if (parent) g.transform.SetParent(parent, false);
            return g.transform;
        }

        public void Report()
        {
            if (missing.Count > 0) Debug.LogWarning($"[TrackGen:{trackId}] missing prefabs: {string.Join(", ", missing)}");
        }
    }
}
