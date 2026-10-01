Shader "InkDrift/Water"
{
    Properties
    {
        _ShallowColor ("Shallow", Color) = (0.25, 0.75, 0.8, 1)
        _DeepColor ("Deep", Color) = (0.05, 0.18, 0.35, 1)
        _FoamColor ("Foam", Color) = (1, 1, 1, 1)
        _DepthRange ("Depth Range", Float) = 3
        _FoamWidth ("Foam Width", Float) = 0.6
        _WaveScale ("Wave Scale", Float) = 0.35
        _WaveSpeed ("Wave Speed", Float) = 0.4
        _FlowDir ("Flow Dir", Vector) = (1, 0, 0.2, 0)
        _ReflectStrength ("Reflection", Range(0, 2)) = 0.8
    }
    SubShader
    {
        Tags { "Queue" = "Transparent-50" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite On
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"

            half4 _ShallowColor, _DeepColor, _FoamColor;
            float _DepthRange, _FoamWidth, _WaveScale, _WaveSpeed, _ReflectStrength;
            float4 _FlowDir;

            struct A { float4 p : POSITION; float3 n : NORMAL; };
            struct V { float4 p : SV_POSITION; float3 w : TEXCOORD0; float4 sp : TEXCOORD1; half fog : TEXCOORD2; };

            float hash(float2 p) { return frac(sin(dot(p, float2(41.3, 289.1))) * 45758.5); }
            float vnoise(float2 p) { float2 i = floor(p), f = frac(p); f = f * f * (3 - 2 * f);
                return lerp(lerp(hash(i), hash(i + float2(1, 0)), f.x), lerp(hash(i + float2(0, 1)), hash(i + 1), f.x), f.y); }

            V vert(A v)
            {
                V o;
                o.w = TransformObjectToWorld(v.p.xyz);
                o.p = TransformWorldToHClip(o.w);
                o.sp = ComputeScreenPos(o.p);
                o.fog = ComputeFogFactor(o.p.z);
                return o;
            }

            half4 frag(V i) : SV_Target
            {
                float2 uv = i.w.xz * _WaveScale;
                float2 flow = normalize(_FlowDir.xz + 1e-4) * _Time.y * _WaveSpeed;
                float h0 = vnoise(uv + flow) * 0.6 + vnoise(uv * 2.3 - flow * 1.4) * 0.4;
                float hx = vnoise(uv + float2(0.05, 0) + flow) * 0.6 + vnoise((uv + float2(0.05, 0)) * 2.3 - flow * 1.4) * 0.4;
                float hz = vnoise(uv + float2(0, 0.05) + flow) * 0.6 + vnoise((uv + float2(0, 0.05)) * 2.3 - flow * 1.4) * 0.4;
                float3 n = normalize(float3((h0 - hx) * 3.0, 1.0, (h0 - hz) * 3.0));

                float2 suv = i.sp.xy / i.sp.w;
                float sceneZ = LinearEyeDepth(SampleSceneDepth(suv), _ZBufferParams);
                float waterZ = LinearEyeDepth(i.p.z, _ZBufferParams);
                float depth = max(sceneZ - waterZ, 0);
                float d01 = saturate(depth / _DepthRange);
                half3 col = lerp(_ShallowColor.rgb, _DeepColor.rgb, floor(d01 * 3.0 + 0.5) / 3.0);

                Light sun = GetMainLight(TransformWorldToShadowCoord(i.w));
                half3 viewDir = GetWorldSpaceNormalizeViewDir(i.w);
                half3 H = normalize(sun.direction + viewDir);
                half spec = step(0.985, pow(saturate(dot(n, H)), 64.0));
                half3 R = reflect(-viewDir, n);
                half3 env = GlossyEnvironmentReflection(R, i.w, 0.1, 1.0, suv);
                half fres = smoothstep(0.4, 0.8, 1.0 - saturate(dot(n, viewDir)));
                col = lerp(col, env, fres * _ReflectStrength * 0.6);
                col *= lerp(0.65, 1.0, sun.shadowAttenuation);
                col += sun.color * spec * 1.5;

                float foamLine = step(depth, _FoamWidth * (0.6 + 0.4 * vnoise(uv * 6 + flow * 3)));
                float foamDots = step(0.8, vnoise(uv * 9.0 + flow * 2.0)) * step(depth, _FoamWidth * 3.0);
                col = lerp(col, _FoamColor.rgb, saturate(foamLine + foamDots * 0.6));
                col = MixFog(col, i.fog);
                return half4(col, lerp(0.75, 0.97, d01));
            }
            ENDHLSL
        }
    }
}
