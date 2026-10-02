#ifndef INK_TOON_LIGHTING_INCLUDED
#define INK_TOON_LIGHTING_INCLUDED

#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

// Screen-space comic halftone: returns 1 inside a dot. size01 = dot coverage (0..1).
half InkHalftone(float2 screenPx, half size01, float cellPx)
{
    const float s = 0.70710678;
    float2 p = float2(screenPx.x * s - screenPx.y * s, screenPx.x * s + screenPx.y * s) / max(cellPx, 1.0);
    float2 cell = frac(p) - 0.5;
    float d = length(cell);
    float aa = fwidth(d) * 0.75; // derivative before any divergent early-out
    if (size01 <= 0.001h) return 0.0h;
    float r = sqrt(saturate(size01)) * 0.62;
    return smoothstep(r + aa, r - aa, d);
}

half InkBand(half x, half threshold, half softness)
{
    return smoothstep(threshold - softness, threshold + softness, x);
}

struct InkSurface
{
    half3 albedo;
    half3 normalWS;
    half3 viewDirWS;
    float3 positionWS;
    half metallic;
    half smoothness;
    half occlusion;
    half3 emission;
    half alpha;
    float2 screenUV;
    float4 positionCS;
    float4 shadowCoord;
    half fogFactor;
    half wet;
};

half3 InkShade(InkSurface s)
{
#if defined(INK_HAS_SOFTNESS)
    // per-material override: realistic surfaces (the driver) shade with a soft terminator and highlight
    half soft = _BandSoftness > 0.0h ? _BandSoftness : max(_ToonParams.x, 0.005h);
    half specSoft = max(_SpecSoftness, 0.02h);
#else
    half soft = max(_ToonParams.x, 0.005h);
    half specSoft = 0.02h;
#endif
    half3 N = s.normalWS;
    half3 V = s.viewDirWS;
    half NdotV = saturate(dot(N, V));

    // ---------------- main light
    half4 shadowMask = half4(1, 1, 1, 1);
    Light mainLight = GetMainLight(s.shadowCoord, s.positionWS, shadowMask);
    half NdotL = dot(N, mainLight.direction);
    half shadowAtten = lerp(1.0h, mainLight.shadowAttenuation, _ReceiveShadows);
    half lit = InkBand(NdotL, _ShadowThreshold, soft) * InkBand(shadowAtten, 0.5h, 0.08h);
    half hi = InkBand(NdotL, _HighlightThreshold, soft) * lit;

    // Flattened ambient: blend directional SH toward the up-facing sample so shading stays graphic.
    half3 ambN = SampleSH(N);
    half3 ambUp = SampleSH(half3(0, 1, 0));
    half3 ambient = lerp(ambN, ambUp, 0.5h);

    half3 tint = _ToonShadowTint.rgb * _ShadowColor.rgb;
    half3 lightCol = mainLight.color;
    half ambLum = Luminance(ambient);
    // anime-style shadows: hue-shifted and readable (not crushed), contrast carried by the band edge
    half3 diffuseLit = s.albedo * (lightCol + ambient * 0.6h);
    half3 diffuseShadow = s.albedo * tint * (ambLum * 1.1h + 0.12h + Luminance(lightCol) * 0.08h);
    half3 color = lerp(diffuseShadow, diffuseLit, lit);
    color += s.albedo * lightCol * hi * _HighlightBoost;

    // halftone dots on the shadow side of the terminator + in cast shadows
    half dotsTone = (1.0h - lit) * (0.30h + 0.70h * smoothstep(-0.65h, 0.05h, NdotL));
    half dots = InkHalftone(s.screenUV * _ScreenParams.xy, dotsTone * 0.9h, _ComicParams.y * (_ScreenParams.y / 1080.0));
    color *= 1.0h - dots * _ComicParams.x * _HalftoneAmount * 0.55h;

    // ---------------- specular (hard comic highlight)
    half3 H = SafeNormalize(mainLight.direction + V);
    half NdotH = saturate(dot(N, H));
    half specPow = exp2(10.0h * s.smoothness + 1.0h);
    half spec = pow(NdotH, specPow) * s.smoothness;
    half specMask = InkBand(spec, 1.0h - _SpecSize, specSoft) * lit;
    half3 specCol = lerp(half3(1, 1, 1), s.albedo, s.metallic * 0.6h);
    color += specCol * lightCol * specMask * _SpecIntensity;

    // ---------------- reflections (banded) for glossy/metal/wet
    half reflAmt = _ReflectStrength + s.wet;
    if (reflAmt > 0.001h)
    {
        half3 R = reflect(-V, N);
        half perceptualRoughness = 1.0h - s.smoothness;
        half3 env = GlossyEnvironmentReflection(R, s.positionWS, perceptualRoughness, s.occlusion, s.screenUV);
        half lum = max(Luminance(env), 1e-4h);
        half bands = max(_ReflectBands, 2.0h);
        half q = floor(lum * bands + 0.5h) / bands;
        env *= q / lum;
        half fres = InkBand(1.0h - NdotV, 0.55h, 0.06h) * 0.8h + 0.2h;
        half3 refl = env * lerp(fres * 0.5h, 1.0h, s.metallic) * lerp(half3(1, 1, 1), s.albedo, s.metallic);
#if defined(_WET)
        if (_PlanarReflectionOn > 0.5)
        {
            float2 uvR = s.screenUV + N.xz * 0.03;
            half3 planar = SAMPLE_TEXTURE2D_LOD(_PlanarReflectionTex, sampler_PlanarReflectionTex, uvR, 0).rgb;
            planar = clamp(planar, 0.0h, 6.0h);
            if (any(isnan(planar)) || any(isinf(planar))) planar = 0.0h;
            half wf = s.wet * (0.35h + 0.65h * pow(1.0h - NdotV, 3.0h));
            color = lerp(color, color * 0.45h + planar, saturate(wf));
        }
#endif
        color += refl * _ReflectStrength;
    }

    // ---------------- rim light (backlit edges)
    half rim = InkBand(1.0h - NdotV, 0.72h, 0.03h) * saturate(NdotL * 0.6h + 0.55h);
    color += _ToonRimColor.rgb * rim * _RimAmount * (0.6h + 0.4h * lit);

    // ---------------- additional lights (banded pools)
#if defined(_ADDITIONAL_LIGHTS)
    uint pixelLightCount = GetAdditionalLightsCount();
    InputData inputData = (InputData)0;
    inputData.positionWS = s.positionWS;
    inputData.normalizedScreenSpaceUV = s.screenUV;
    inputData.normalWS = N;
    inputData.viewDirectionWS = V;

    #if USE_CLUSTER_LIGHT_LOOP
    UNITY_LOOP for (uint lightIndex = 0; lightIndex < min(URP_FP_DIRECTIONAL_LIGHTS_COUNT, MAX_VISIBLE_LIGHTS); lightIndex++)
    {
        Light light = GetAdditionalLight(lightIndex, s.positionWS, shadowMask);
        half nl = InkBand(dot(N, light.direction), 0.0h, soft);
        color += s.albedo * light.color * nl * light.shadowAttenuation;
    }
    #endif

    LIGHT_LOOP_BEGIN(pixelLightCount)
        Light light = GetAdditionalLight(lightIndex, s.positionWS, shadowMask);
        // Physical inverse-square attenuation snapped to powers of 4 -> crisp comic pools that keep real energy.
        half a = light.distanceAttenuation * light.shadowAttenuation;
        half aq = (a > 0.004h) ? min(exp2(round(log2(max(a, 1e-4h)) * 0.5h) * 2.0h), 1.0h) : 0.0h;
        aq *= smoothstep(0.004h, 0.008h, a);
        half nl = InkBand(dot(N, light.direction), -0.05h, soft);
        half3 add = s.albedo * light.color * nl * aq;
        half3 Hl = SafeNormalize(light.direction + V);
        half sl = InkBand(pow(saturate(dot(N, Hl)), specPow) * s.smoothness, 1.0h - _SpecSize, 0.03h);
        color += add + light.color * sl * aq * 0.5h * _SpecIntensity;
    LIGHT_LOOP_END
#endif

    color *= lerp(1.0h, s.occlusion, _OcclusionStrength);
    color += s.emission;
    return color;
}

#endif
