using UnityEngine;

namespace InkDrift.EditorTools
{
    public enum TrackTheme { City, Expressway, Mountain }

    public class LookDef
    {
        public float sunElevation = 35f, sunAzimuth = 210f, sunIntensity = 1.4f;
        public Color sunColor = Color.white;
        public Color ambSky = new Color(0.5f, 0.55f, 0.75f), ambEquator = new Color(0.45f, 0.4f, 0.5f), ambGround = new Color(0.2f, 0.18f, 0.22f);
        public Color fogColor = new Color(0.55f, 0.5f, 0.7f);
        public float fogStart = 80f, fogEnd = 1200f;
        // sky
        public Color zenith = new Color(0.15f, 0.25f, 0.6f), horizon = new Color(1f, 0.6f, 0.5f), skyGround = new Color(0.15f, 0.12f, 0.2f), glow = new Color(1f, 0.4f, 0.5f);
        public float glowHeight = 0.18f, glowStrength = 0.8f, sunSize = 0.035f, cloudCover = 0.45f, cloudScale = 1.6f, stars = 0f, moonSize = 0f, skyExposure = 1f;
        public Color cloudLit = new Color(1f, 0.9f, 0.85f), cloudShadow = new Color(0.55f, 0.45f, 0.7f), skySun = new Color(1f, 0.85f, 0.6f);
        // post
        public float bloomIntensity = 0.7f, bloomThreshold = 1.0f, bloomScatter = 0.7f;
        public float saturation = 25f, contrast = 12f, exposure = 0f, temperature = 0f, tint = 0f, vignette = 0.28f;
        public Color shadowTint = new Color(0.42f, 0.36f, 0.62f), rimColor = new Color(0.75f, 0.95f, 1f);
        public float outlineWidth = 1.6f, halftone = 0.35f;
        public string hdri = "";
        public float reflectionIntensity = 1f;
        public bool night;
    }

    public class TrackDef
    {
        public string id;
        public int seed;
        public TrackTheme theme;
        public float roadHalfWidth = 6f;
        public float sidewalk = 4f;
        public float startDistance = 120f;
        public Vector2[] elevation = { new Vector2(0, 0) };
        public float bankPerCurv = 0f, maxBank = 0f;
        public bool wet;
        public LookDef look = new LookDef();

        public static TrackDef Get(string id)
        {
            switch (id)
            {
                case "shibuya":
                    return new TrackDef
                    {
                        id = id, seed = 1101, theme = TrackTheme.City, roadHalfWidth = 6.5f, sidewalk = 4.5f, startDistance = 125f, wet = true,
                        look = new LookDef
                        {
                            night = true, sunElevation = 38f, sunAzimuth = 140f, sunIntensity = 0.6f, sunColor = new Color(0.6f, 0.7f, 1f),
                            ambSky = new Color(0.3f, 0.26f, 0.5f), ambEquator = new Color(0.34f, 0.22f, 0.42f), ambGround = new Color(0.12f, 0.1f, 0.18f),
                            fogColor = new Color(0.16f, 0.09f, 0.24f), fogStart = 40f, fogEnd = 520f,
                            zenith = new Color(0.02f, 0.02f, 0.08f), horizon = new Color(0.22f, 0.08f, 0.3f), skyGround = new Color(0.04f, 0.03f, 0.07f),
                            glow = new Color(0.85f, 0.2f, 0.55f), glowHeight = 0.12f, glowStrength = 0.9f, sunSize = 0.0f, cloudCover = 0.35f,
                            cloudLit = new Color(0.45f, 0.25f, 0.55f), cloudShadow = new Color(0.08f, 0.05f, 0.14f), stars = 0.6f, moonSize = 0.012f, skySun = new Color(0.6f, 0.7f, 1f),
                            bloomIntensity = 0.8f, bloomThreshold = 1.0f, bloomScatter = 0.7f, saturation = 32f, contrast = 16f, exposure = 0.25f, temperature = -8f, tint = 6f, vignette = 0.32f,
                            shadowTint = new Color(0.66f, 0.58f, 1.0f), rimColor = new Color(1f, 0.35f, 0.75f), outlineWidth = 1.5f, halftone = 0.4f,
                            hdri = "shanghai_bund_4k", reflectionIntensity = 1.2f,
                        },
                    };
                case "shuto":
                    return new TrackDef
                    {
                        id = id, seed = 2202, theme = TrackTheme.Expressway, roadHalfWidth = 5.5f, sidewalk = 0f, startDistance = 150f,
                        elevation = new[] { new Vector2(0f, 16f), new Vector2(0.14f, 19f), new Vector2(0.3f, 26f), new Vector2(0.42f, 14f), new Vector2(0.52f, 11f), new Vector2(0.64f, 17f), new Vector2(0.78f, 24f), new Vector2(0.9f, 18f) },
                        bankPerCurv = 260f, maxBank = 4f,
                        look = new LookDef
                        {
                            sunElevation = 11f, sunAzimuth = 250f, sunIntensity = 1.8f, sunColor = new Color(1f, 0.62f, 0.38f),
                            ambSky = new Color(0.55f, 0.45f, 0.7f), ambEquator = new Color(0.75f, 0.45f, 0.45f), ambGround = new Color(0.22f, 0.15f, 0.2f),
                            fogColor = new Color(0.85f, 0.5f, 0.5f), fogStart = 150f, fogEnd = 1900f,
                            zenith = new Color(0.16f, 0.17f, 0.45f), horizon = new Color(1f, 0.55f, 0.35f), glow = new Color(1f, 0.35f, 0.3f), glowHeight = 0.22f, glowStrength = 1.1f,
                            sunSize = 0.045f, cloudCover = 0.5f, cloudScale = 1.3f, cloudLit = new Color(1f, 0.72f, 0.55f), cloudShadow = new Color(0.5f, 0.3f, 0.55f), skySun = new Color(1f, 0.75f, 0.45f),
                            bloomIntensity = 0.9f, bloomThreshold = 0.95f, saturation = 28f, contrast = 14f, exposure = 0.1f, temperature = 12f, vignette = 0.25f,
                            shadowTint = new Color(0.82f, 0.66f, 0.92f), rimColor = new Color(1f, 0.75f, 0.45f), outlineWidth = 1.6f,
                            hdri = "the_sky_is_on_fire_4k",
                        },
                    };
                default:
                    return new TrackDef
                    {
                        id = "okutama", seed = 3303, theme = TrackTheme.Mountain, roadHalfWidth = 4.2f, sidewalk = 1.2f, startDistance = 150f,
                        elevation = new[] { new Vector2(0f, 0f), new Vector2(0.06f, 4f), new Vector2(0.14f, 16f), new Vector2(0.23f, 29f), new Vector2(0.33f, 43f), new Vector2(0.43f, 57f),
                                            new Vector2(0.52f, 64f), new Vector2(0.6f, 60f), new Vector2(0.72f, 40f), new Vector2(0.85f, 18f), new Vector2(0.95f, 4f) },
                        bankPerCurv = 120f, maxBank = 3f,
                        look = new LookDef
                        {
                            sunElevation = 14f, sunAzimuth = 235f, sunIntensity = 1.55f, sunColor = new Color(1f, 0.78f, 0.52f),
                            ambSky = new Color(0.5f, 0.6f, 0.85f), ambEquator = new Color(0.65f, 0.5f, 0.4f), ambGround = new Color(0.22f, 0.17f, 0.12f),
                            fogColor = new Color(0.78f, 0.7f, 0.68f), fogStart = 120f, fogEnd = 1500f,
                            zenith = new Color(0.2f, 0.38f, 0.78f), horizon = new Color(1f, 0.82f, 0.6f), glow = new Color(1f, 0.6f, 0.35f), glowHeight = 0.2f, glowStrength = 0.6f,
                            sunSize = 0.04f, cloudCover = 0.42f, cloudScale = 1.8f, cloudLit = new Color(1f, 0.93f, 0.82f), cloudShadow = new Color(0.55f, 0.55f, 0.75f), skySun = new Color(1f, 0.85f, 0.6f),
                            bloomIntensity = 0.65f, bloomThreshold = 1.05f, saturation = 30f, contrast = 12f, exposure = 0.05f, temperature = 10f, vignette = 0.24f,
                            shadowTint = new Color(0.74f, 0.72f, 0.95f), rimColor = new Color(1f, 0.85f, 0.55f), outlineWidth = 1.6f,
                            hdri = "autumn_forest_04_4k",
                        },
                    };
            }
        }
    }
}
