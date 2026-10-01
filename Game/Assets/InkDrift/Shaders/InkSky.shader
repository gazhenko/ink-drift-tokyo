Shader "InkDrift/Sky"
{
    Properties
    {
        _ZenithColor ("Zenith", Color) = (0.12, 0.2, 0.55, 1)
        _HorizonColor ("Horizon", Color) = (1.0, 0.55, 0.45, 1)
        _GroundColor ("Ground", Color) = (0.2, 0.15, 0.25, 1)
        _HorizonGlow ("Horizon Glow Color", Color) = (1, 0.4, 0.6, 1)
        _GlowHeight ("Glow Height", Range(0.01, 1)) = 0.18
        _GlowStrength ("Glow Strength", Range(0, 4)) = 1
        _SunColor ("Sun Color", Color) = (1, 0.85, 0.6, 1)
        _SunSize ("Sun Size", Range(0.001, 0.2)) = 0.04
        _SunHalo ("Sun Halo", Range(0, 2)) = 0.6
        _CloudColor ("Cloud Lit", Color) = (1, 0.92, 0.85, 1)
        _CloudShadow ("Cloud Shadow", Color) = (0.55, 0.45, 0.7, 1)
        _CloudCover ("Cloud Cover", Range(0, 1)) = 0.45
        _CloudScale ("Cloud Scale", Float) = 1.6
        _CloudSpeed ("Cloud Speed", Float) = 0.004
        _CloudHeight ("Cloud Band Height", Range(0, 1)) = 0.35
        _StarDensity ("Stars", Range(0, 1)) = 0
        _MoonDir ("Moon Dir", Vector) = (0.3, 0.5, -0.8, 0)
        _MoonSize ("Moon Size", Range(0, 0.1)) = 0
        _Exposure ("Exposure", Float) = 1
    }
    SubShader
    {
        Tags { "Queue" = "Background" "RenderType" = "Background" "PreviewType" = "Skybox" "RenderPipeline" = "UniversalPipeline" }
        Cull Off ZWrite Off

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            half4 _ZenithColor, _HorizonColor, _GroundColor, _HorizonGlow, _SunColor, _CloudColor, _CloudShadow;
            float _GlowHeight, _GlowStrength, _SunSize, _SunHalo, _CloudCover, _CloudScale, _CloudSpeed, _CloudHeight, _StarDensity, _MoonSize, _Exposure;
            float4 _MoonDir;

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.dir = v.positionOS.xyz;
                return o;
            }

            float hash12(float2 p) { float3 p3 = frac(float3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return frac((p3.x + p3.y) * p3.z); }
            float vnoise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(hash12(i), hash12(i + float2(1, 0)), u.x), lerp(hash12(i + float2(0, 1)), hash12(i + float2(1, 1)), u.x), u.y);
            }
            float fbm(float2 p)
            {
                float a = 0.5, s = 0;
                for (int k = 0; k < 5; k++) { s += a * vnoise(p); p = p * 2.03 + 17.1; a *= 0.5; }
                return s;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float y = d.y;
                Light sun = GetMainLight();
                float3 L = sun.direction;

                half3 sky = lerp(_HorizonColor.rgb, _ZenithColor.rgb, smoothstep(0.0, 0.55, y));
                // banded gradient (posterized a little for the comic look)
                float band = floor(saturate(y) * 10.0) / 10.0;
                sky = lerp(sky, lerp(_HorizonColor.rgb, _ZenithColor.rgb, smoothstep(0.0, 0.55, band)), 0.35);
                half3 ground = lerp(_HorizonColor.rgb * 0.7, _GroundColor.rgb, smoothstep(0.0, -0.25, y));
                half3 c = y >= 0 ? sky : ground;

                // horizon glow (sunset / city light pollution), stronger toward the sun
                float sunFacing = saturate(dot(normalize(float3(d.x, 0, d.z)), normalize(float3(L.x, 0, L.z))) * 0.5 + 0.5);
                float glow = exp(-abs(y) / max(_GlowHeight, 0.01)) * _GlowStrength * (0.55 + 0.45 * sunFacing);
                c += _HorizonGlow.rgb * glow;

                // sun disc with hard comic halo rings
                float sd = dot(d, L);
                float sunDisc = smoothstep(1.0 - _SunSize, 1.0 - _SunSize * 0.85, sd);
                float halo1 = smoothstep(1.0 - _SunSize * 3.0, 1.0 - _SunSize * 2.8, sd) * 0.25;
                float halo2 = smoothstep(1.0 - _SunSize * 6.0, 1.0 - _SunSize * 5.7, sd) * 0.12;
                c += _SunColor.rgb * (sunDisc * 4.0 + (halo1 + halo2) * _SunHalo) * step(0.0, y + 0.02);

                // stylized clouds on a dome projection
                if (y > 0.0)
                {
                    float2 uv = d.xz / (y + 0.12) * _CloudScale * 0.25;
                    uv += _Time.y * _CloudSpeed * float2(1.0, 0.3);
                    float n = fbm(uv);
                    float heightMask = smoothstep(0.0, 0.08, y) * (1.0 - smoothstep(_CloudHeight, _CloudHeight + 0.45, y));
                    float cov = 1.0 - _CloudCover;
                    float cloud = smoothstep(cov, cov + 0.04, n) * heightMask;
                    // lit side: offset sample toward the sun
                    float n2 = fbm(uv + normalize(L.xz + 1e-4) * 0.06);
                    float litMask = smoothstep(-0.02, 0.02, n - n2 + 0.01);
                    half3 cc = lerp(_CloudShadow.rgb, _CloudColor.rgb, litMask);
                    // rim near the sun
                    cc += _SunColor.rgb * smoothstep(0.85, 1.0, sd) * (1.0 - litMask * 0.5) * 0.6;
                    float edge = smoothstep(cov, cov + 0.012, n) - smoothstep(cov + 0.012, cov + 0.03, n);
                    c = lerp(c, cc, cloud);
                    c = lerp(c, c * 0.55, edge * heightMask * 0.6);
                }

                // stars + moon for night skies
                if (_StarDensity > 0.0 && y > 0.0)
                {
                    float2 sp = d.xz / (y + 0.3) * 220.0;
                    float h = hash12(floor(sp));
                    float star = step(1.0 - _StarDensity * 0.02, h) * smoothstep(0.35, 0.1, length(frac(sp) - 0.5));
                    c += star * smoothstep(0.05, 0.4, y) * 1.5;
                }
                if (_MoonSize > 0.0)
                {
                    float md = dot(d, normalize(_MoonDir.xyz));
                    c += half3(1.0, 0.97, 0.88) * smoothstep(1.0 - _MoonSize, 1.0 - _MoonSize * 0.9, md) * 2.0;
                    c += half3(0.6, 0.7, 1.0) * smoothstep(1.0 - _MoonSize * 6.0, 1.0, md) * 0.15;
                }
                return half4(c * _Exposure, 1);
            }
            ENDHLSL
        }
    }
}
