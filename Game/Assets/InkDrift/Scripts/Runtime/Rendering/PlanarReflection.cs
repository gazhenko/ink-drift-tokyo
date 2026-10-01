using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace InkDrift
{
    /// <summary>
    /// Mirror-camera planar reflection for the flat, rain-soaked Shibuya streets. Renders with renderer index 1
    /// (no comic post) into _PlanarReflectionTex, sampled by the toon shader's _WET path.
    /// </summary>
    [DefaultExecutionOrder(1000)]
    [RequireComponent(typeof(Camera))]
    public class PlanarReflection : MonoBehaviour
    {
        public float planeHeight = 0.02f;
        [Range(0.25f, 1f)] public float resolutionScale = 0.5f;
        public LayerMask cullingMask = ~0;
        public float farClip = 400f;

        Camera main, refl;
        bool warned;
        RenderTexture rt;
        static readonly int TexId = Shader.PropertyToID("_PlanarReflectionTex");
        static readonly int OnId = Shader.PropertyToID("_PlanarReflectionOn");

        void OnEnable()
        {
            main = GetComponent<Camera>();
            var go = new GameObject("PlanarReflectionCamera") { hideFlags = HideFlags.HideAndDontSave };
            refl = go.AddComponent<Camera>();
            refl.enabled = false;
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = false;
            data.renderShadows = false;
            data.requiresDepthOption = CameraOverrideOption.Off;
            data.requiresColorOption = CameraOverrideOption.Off;
            data.SetRenderer(1);
        }

        void OnDisable()
        {
            Shader.SetGlobalFloat(OnId, 0f);
            if (refl) DestroyImmediate(refl.gameObject);
            if (rt) { rt.Release(); DestroyImmediate(rt); }
        }

        void EnsureRT()
        {
            int w = Mathf.Max(64, (int)(main.pixelWidth * resolutionScale));
            int h = Mathf.Max(64, (int)(main.pixelHeight * resolutionScale));
            if (rt != null && rt.width == w && rt.height == h) return;
            if (rt) { rt.Release(); DestroyImmediate(rt); }
            rt = new RenderTexture(w, h, 24, RenderTextureFormat.DefaultHDR) { name = "PlanarReflection", useMipMap = false };
            rt.Create();
            // new GPU memory is undefined on Metal: clear so a missed frame can't feed garbage/NaNs to bloom
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            GL.Clear(true, true, Color.black);
            RenderTexture.active = prev;
        }

        void LateUpdate()
        {
            if (main == null || refl == null || !main.isActiveAndEnabled) return;
            EnsureRT();
            refl.CopyFrom(main);
            refl.enabled = false;
            refl.cullingMask = cullingMask;
            refl.farClipPlane = farClip;
            refl.targetTexture = rt;
            refl.clearFlags = CameraClearFlags.Skybox;

            Vector3 n = Vector3.up;
            Vector3 p = new Vector3(0f, planeHeight, 0f);
            float d = -Vector3.Dot(n, p);
            Vector4 plane = new Vector4(n.x, n.y, n.z, d);
            Matrix4x4 R = Reflection(plane);
            refl.worldToCameraMatrix = main.worldToCameraMatrix * R;
            Vector3 camPos = R.MultiplyPoint(main.transform.position);
            refl.transform.position = camPos;
            Vector4 clip = CameraSpacePlane(refl, p, n);
            refl.projectionMatrix = main.CalculateObliqueMatrix(clip);

            GL.invertCulling = true;
            var req = new UniversalRenderPipeline.SingleCameraRequest { destination = rt };
            bool ok = RenderPipeline.SupportsRenderRequest(refl, req);
            if (ok) RenderPipeline.SubmitRenderRequest(refl, req);
            GL.invertCulling = false;
            if (!ok)
            {
                if (!warned) { Debug.LogWarning("[PlanarReflection] render request unsupported; disabling"); warned = true; }
                Shader.SetGlobalFloat(OnId, 0f);
                return;
            }

            Shader.SetGlobalTexture(TexId, rt);
            Shader.SetGlobalFloat(OnId, 1f);
        }

        static Vector4 CameraSpacePlane(Camera cam, Vector3 pos, Vector3 normal)
        {
            Matrix4x4 m = cam.worldToCameraMatrix;
            Vector3 cpos = m.MultiplyPoint(pos + normal * 0.05f);
            Vector3 cnormal = m.MultiplyVector(normal).normalized;
            return new Vector4(cnormal.x, cnormal.y, cnormal.z, -Vector3.Dot(cpos, cnormal));
        }

        static Matrix4x4 Reflection(Vector4 p)
        {
            Matrix4x4 r = Matrix4x4.identity;
            r.m00 = 1f - 2f * p[0] * p[0]; r.m01 = -2f * p[0] * p[1]; r.m02 = -2f * p[0] * p[2]; r.m03 = -2f * p[3] * p[0];
            r.m10 = -2f * p[1] * p[0]; r.m11 = 1f - 2f * p[1] * p[1]; r.m12 = -2f * p[1] * p[2]; r.m13 = -2f * p[3] * p[1];
            r.m20 = -2f * p[2] * p[0]; r.m21 = -2f * p[2] * p[1]; r.m22 = 1f - 2f * p[2] * p[2]; r.m23 = -2f * p[3] * p[2];
            r.m30 = 0f; r.m31 = 0f; r.m32 = 0f; r.m33 = 1f;
            return r;
        }
    }
}
