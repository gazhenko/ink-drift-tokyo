using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift
{
    /// <summary>Draws FoliageData with Graphics.RenderMeshInstanced: per-cell frustum + distance culling, 2-level LOD.</summary>
    [ExecuteAlways]
    public class FoliageRenderer : MonoBehaviour
    {
        public FoliageData data;
        [Range(0.2f, 1.5f)] public float distanceScale = 1f;

        readonly Plane[] planes = new Plane[6];
        Matrix4x4[] scratch = new Matrix4x4[1023];
        readonly System.Collections.Generic.List<Matrix4x4> near = new System.Collections.Generic.List<Matrix4x4>(1024);
        readonly System.Collections.Generic.List<Matrix4x4> far = new System.Collections.Generic.List<Matrix4x4>(1024);

        void Update()
        {
            if (data == null) return;
            var cam = Camera.main;
#if UNITY_EDITOR
            if (!Application.isPlaying && UnityEditor.SceneView.lastActiveSceneView != null) cam = UnityEditor.SceneView.lastActiveSceneView.camera;
#endif
            if (cam == null) return;
            DrawFor(cam);
        }

        void DrawFor(Camera cam)
        {
            GeometryUtility.CalculateFrustumPlanes(cam, planes);
            Vector3 cp = cam.transform.position;
            float q = QualitySettings.GetQualityLevel() == 0 ? 0.6f : 1f;
            foreach (var layer in data.layers)
            {
                if (layer.mesh == null || layer.materials == null || layer.materials.Length == 0) continue;
                float cull = layer.cullDistance * distanceScale * q;
                float lod = layer.lodDistance * distanceScale * q;
                for (int c = 0; c < layer.cellBounds.Length; c++)
                {
                    var b = layer.cellBounds[c];
                    float dist = Mathf.Sqrt(b.SqrDistance(cp));
                    if (dist > cull) continue;
                    if (!GeometryUtility.TestPlanesAABB(planes, b)) continue;
                    bool useLod = layer.lodMesh != null && dist > lod;
                    // cells that straddle the LOD boundary: draw near half with LOD0 by per-instance check
                    if (layer.lodMesh != null && dist < lod && Vector3.Distance(b.center, cp) + b.extents.magnitude > lod)
                        DrawSplit(layer, c, cp, lod);
                    else
                        Draw(layer, useLod, layer.cellStart[c], layer.cellCount[c], null);
                }
            }
        }

        void DrawSplit(FoliageData.Layer layer, int c, Vector3 cp, float lod)
        {
            int start = layer.cellStart[c], count = layer.cellCount[c];
            near.Clear(); far.Clear();
            for (int i = start; i < start + count; i++)
            {
                var m = layer.instances[i];
                Vector3 p = new Vector3(m.m03, m.m13, m.m23);
                if ((p - cp).sqrMagnitude < lod * lod) near.Add(m); else far.Add(m);
            }
            Draw(layer, false, 0, near.Count, near);
            Draw(layer, true, 0, far.Count, far);
        }

        void Draw(FoliageData.Layer layer, bool lod, int start, int count, System.Collections.Generic.List<Matrix4x4> list)
        {
            if (count <= 0) return;
            Mesh mesh = lod ? layer.lodMesh : layer.mesh;
            Material[] mats = lod && layer.lodMaterials != null && layer.lodMaterials.Length > 0 ? layer.lodMaterials : layer.materials;
            Matrix4x4 offset = lod ? layer.lodOffset : layer.meshOffset;
            for (int done = 0; done < count; done += 1023)
            {
                int n = Mathf.Min(1023, count - done);
                for (int i = 0; i < n; i++)
                    scratch[i] = (list != null ? list[done + i] : layer.instances[start + done + i]) * offset;
                for (int s = 0; s < mesh.subMeshCount; s++)
                {
                    var mat = mats[Mathf.Min(s, mats.Length - 1)];
                    if (mat == null) continue;
                    var rp = new RenderParams(mat)
                    {
                        shadowCastingMode = layer.castShadows && !lod ? ShadowCastingMode.On : (layer.castShadows ? ShadowCastingMode.On : ShadowCastingMode.Off),
                        receiveShadows = true,
                        layer = 11,
                        worldBounds = new Bounds(Vector3.zero, Vector3.one * 100000f),
                    };
                    Graphics.RenderMeshInstanced(rp, mesh, s, scratch, n);
                }
            }
        }
    }
}
