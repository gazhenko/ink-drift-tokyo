using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Drives the global parameters of the comic post pass (ink outlines, halftone, paper grain, pulse) and the
    /// global toon lighting parameters. Lives in each scene; per-track look values are set by the track generator.
    /// </summary>
    [ExecuteAlways]
    public class ComicPostFX : MonoBehaviour
    {
        [Header("Ink outlines")]
        public Color inkColor = new Color(0.043f, 0.043f, 0.07f, 1f);
        [Range(0.5f, 4f)] public float outlineWidth = 1.6f;
        [Range(0f, 4f)] public float depthSensitivity = 1.2f;
        [Range(0f, 4f)] public float normalSensitivity = 1.0f;
        public float outlineFadeStart = 60f;
        public float outlineFadeEnd = 420f;

        [Header("Comic finish")]
        [Range(0f, 1f)] public float halftoneStrength = 0.35f;
        public float halftoneScale = 7f;
        [Range(0f, 1f)] public float paperGrain = 0.06f;
        [Range(0f, 1f)] public float vignetteInk = 0.25f;
        public Color shadowTint = new Color(0.72f, 0.66f, 0.95f, 1f);
        [Range(0f, 1f)] public float rimStrength = 0.6f;
        public Color rimColor = new Color(0.75f, 0.95f, 1f, 1f);
        [Range(0f, 1f)] public float bandSoftness = 0.04f;

        [Header("Atmosphere")]
        public Color fogColor = new Color(0.55f, 0.5f, 0.75f);
        public float fogStart = 60f;
        public float fogEnd = 900f;
        public Color skyTint = Color.white;

        static float pulse;
        static readonly int InkColorId = Shader.PropertyToID("_InkColor");
        static readonly int InkParamsId = Shader.PropertyToID("_InkParams");
        static readonly int InkFadeId = Shader.PropertyToID("_InkFade");
        static readonly int ComicParamsId = Shader.PropertyToID("_ComicParams");
        static readonly int ToonShadowTintId = Shader.PropertyToID("_ToonShadowTint");
        static readonly int ToonRimId = Shader.PropertyToID("_ToonRimColor");
        static readonly int ToonParamsId = Shader.PropertyToID("_ToonParams");
        static readonly int PulseId = Shader.PropertyToID("_ComicPulse");

        public static void Pulse(float amount) { pulse = Mathf.Max(pulse, Mathf.Clamp01(amount)); }

        void OnEnable() { Apply(); }
        void OnValidate() { Apply(); }

        void Update()
        {
            pulse = Mathf.MoveTowards(pulse, 0f, Time.unscaledDeltaTime * 2.2f);
            Apply();
        }

        void Apply()
        {
            Shader.SetGlobalColor(InkColorId, inkColor);
            Shader.SetGlobalVector(InkParamsId, new Vector4(outlineWidth, depthSensitivity, normalSensitivity, 0f));
            Shader.SetGlobalVector(InkFadeId, new Vector4(outlineFadeStart, outlineFadeEnd, 0f, 0f));
            Shader.SetGlobalVector(ComicParamsId, new Vector4(halftoneStrength, halftoneScale, paperGrain, vignetteInk));
            Shader.SetGlobalColor(ToonShadowTintId, shadowTint);
            Shader.SetGlobalColor(ToonRimId, rimColor * rimStrength);
            Shader.SetGlobalVector(ToonParamsId, new Vector4(bandSoftness, 0f, 0f, 0f));
            Shader.SetGlobalFloat(PulseId, pulse);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = fogColor;
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
        }
    }
}
