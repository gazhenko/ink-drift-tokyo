#ifndef INK_TOON_INPUT_INCLUDED
#define INK_TOON_INPUT_INCLUDED

#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

TEXTURE2D(_BaseMap);      SAMPLER(sampler_BaseMap);
TEXTURE2D(_BumpMap);      SAMPLER(sampler_BumpMap);
TEXTURE2D(_MaskMap);      SAMPLER(sampler_MaskMap);
TEXTURE2D(_EmissionMap);  SAMPLER(sampler_EmissionMap);
TEXTURE2D(_PlanarReflectionTex); SAMPLER(sampler_PlanarReflectionTex);

CBUFFER_START(UnityPerMaterial)
    float4 _BaseMap_ST;
    half4 _BaseColor;
    half _BumpScale;
    half _Metallic;
    half _Smoothness;
    half _OcclusionStrength;
    half4 _EmissionColor;
    half4 _ShadowColor;
    half _ShadowThreshold;
    half _HighlightThreshold;
    half _HighlightBoost;
    half _SpecSize;
    half _SpecIntensity;
    half _RimAmount;
    half _ReflectStrength;
    half _ReflectBands;
    half _HalftoneAmount;
    half _VertexAO;
    half _WindStrength;
    half _HueVariation;
    half _VertexTint;
    half _BackfaceFlip;
    half _ReceiveShadows;
    half _Cutoff;
    float _WorldUVScale;
    half _WetAmount;
    half _MaskHeightPuddles;
CBUFFER_END

// Globals from ComicPostFX
half4 _ToonShadowTint;
half4 _ToonRimColor;
float4 _ToonParams;      // x band softness
float4 _ComicParams;     // x halftone strength, y halftone scale (px), z paper grain, w vignette
float _ComicPulse;
float4 _WindParams;      // xyz dir, w time scale
float _PlanarReflectionOn;

float3 InkWind(float3 positionWS, half weight)
{
    if (_WindStrength <= 0.0h || weight <= 0.0h) return positionWS;
    float t = _Time.y * (_WindParams.w > 0 ? _WindParams.w : 1.0);
    float phase = dot(positionWS.xz, float2(0.13, 0.17));
    float3 dir = any(_WindParams.xyz) ? _WindParams.xyz : float3(1, 0, 0.4);
    float sway = sin(t * 1.3 + phase) * 0.6 + sin(t * 2.7 + phase * 2.3) * 0.25 + sin(t * 6.1 + phase * 5.0) * 0.08;
    positionWS += dir * sway * _WindStrength * weight * 0.25;
    positionWS.y += sin(t * 3.1 + phase * 3.0) * _WindStrength * weight * 0.03;
    return positionWS;
}

float2 InkUV(float2 uv, float3 positionWS, float3 normalWS)
{
#if defined(_WORLD_UV)
    float3 n = abs(normalWS);
    if (n.y > n.x && n.y > n.z) return positionWS.xz * _WorldUVScale;
    if (n.x > n.z) return positionWS.zy * _WorldUVScale;
    return positionWS.xy * _WorldUVScale;
#else
    return TRANSFORM_TEX(uv, _BaseMap);
#endif
}

#endif
