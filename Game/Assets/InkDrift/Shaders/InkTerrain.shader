Shader "InkDrift/Terrain"
{
    Properties
    {
        _GrassMap ("Grass (R)", 2D) = "white" {}
        [Normal][NoScaleOffset] _GrassNormal ("Grass Normal", 2D) = "bump" {}
        _RockMap ("Rock (G)", 2D) = "white" {}
        [Normal][NoScaleOffset] _RockNormal ("Rock Normal", 2D) = "bump" {}
        _LeafMap ("Forest Floor (B)", 2D) = "white" {}
        [Normal][NoScaleOffset] _LeafNormal ("Forest Floor Normal", 2D) = "bump" {}
        _DirtMap ("Dirt / Gravel (A)", 2D) = "white" {}
        [Normal][NoScaleOffset] _DirtNormal ("Dirt Normal", 2D) = "bump" {}
        _Tiling ("Tiling (m per repeat) xyzw = grass rock leaf dirt", Vector) = (4, 8, 4, 3)
        _GrassTint ("Grass Tint", Color) = (1, 1, 1, 1)
        _BlendSharpness ("Blend Sharpness", Range(1, 16)) = 6
        _Smoothness ("Smoothness", Range(0, 1)) = 0.15
        _ShadowColor ("Shadow Color", Color) = (1,1,1,1)
        _ShadowThreshold ("Terminator", Range(-1,1)) = 0.0
        _HighlightThreshold ("Highlight Band", Range(0,1)) = 0.6
        _HighlightBoost ("Highlight Boost", Range(0,1)) = 0.1
        _SpecSize ("Spec Size", Range(0,1)) = 0.02
        _SpecIntensity ("Spec Intensity", Range(0,4)) = 0.2
        _RimAmount ("Rim", Range(0,2)) = 0.2
        _HalftoneAmount ("Halftone", Range(0,1)) = 0.8
        _ReceiveShadows ("Receive Shadows", Range(0,1)) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        TEXTURE2D(_GrassMap); SAMPLER(sampler_GrassMap); TEXTURE2D(_GrassNormal);
        TEXTURE2D(_RockMap); TEXTURE2D(_RockNormal);
        TEXTURE2D(_LeafMap); TEXTURE2D(_LeafNormal);
        TEXTURE2D(_DirtMap); TEXTURE2D(_DirtNormal);
        TEXTURE2D(_PlanarReflectionTex); SAMPLER(sampler_PlanarReflectionTex);
        CBUFFER_START(UnityPerMaterial)
            float4 _GrassMap_ST, _RockMap_ST, _LeafMap_ST, _DirtMap_ST;
            float4 _Tiling;
            half4 _GrassTint;
            half _BlendSharpness, _Smoothness;
            half4 _ShadowColor;
            half _ShadowThreshold, _HighlightThreshold, _HighlightBoost, _SpecSize, _SpecIntensity, _RimAmount, _HalftoneAmount;
            // unused toon inputs kept for the shared lighting include
            half _ReflectStrength, _ReflectBands, _OcclusionStrength, _ReceiveShadows;
        CBUFFER_END
        half4 _ToonShadowTint; half4 _ToonRimColor; float4 _ToonParams; float4 _ComicParams; float _ComicPulse; float _PlanarReflectionOn;
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #define INK_TERRAIN 1
            #include "InkToonLighting.hlsl"

            struct A { float4 positionOS : POSITION; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; half4 color : COLOR; };
            struct V { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; half3 normalWS : TEXCOORD1; half4 color : TEXCOORD2; half fog : TEXCOORD3; };

            V vert(A v)
            {
                V o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.color = v.color;
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half3 TriSample(TEXTURE2D_PARAM(tex, smp), float3 p, half3 w, float tile)
            {
                half3 x = SAMPLE_TEXTURE2D(tex, smp, p.zy / tile).rgb;
                half3 y = SAMPLE_TEXTURE2D(tex, smp, p.xz / tile).rgb;
                half3 z = SAMPLE_TEXTURE2D(tex, smp, p.xy / tile).rgb;
                return x * w.x + y * w.y + z * w.z;
            }

            half4 frag(V i) : SV_Target
            {
                half3 n = normalize(i.normalWS);
                half3 tw = pow(abs(n), 4.0); tw /= (tw.x + tw.y + tw.z);
                float2 top = i.positionWS.xz;
                half4 wv = max(i.color, 0.0001h);
                wv = pow(wv, _BlendSharpness * 0.25h);
                // height-ish modulation for crisper transitions
                half3 g = SAMPLE_TEXTURE2D(_GrassMap, sampler_GrassMap, top / _Tiling.x).rgb * _GrassTint.rgb;
                half3 r = TriSample(TEXTURE2D_ARGS(_RockMap, sampler_GrassMap), i.positionWS, tw, _Tiling.y);
                half3 l = SAMPLE_TEXTURE2D(_LeafMap, sampler_GrassMap, top / _Tiling.z).rgb;
                half3 d = SAMPLE_TEXTURE2D(_DirtMap, sampler_GrassMap, top / _Tiling.w).rgb;
                half lr = Luminance(r), lg = Luminance(g), ll = Luminance(l), ld = Luminance(d);
                half4 hw = wv * (half4(lg, lr, ll, ld) + 0.5h);
                hw = pow(hw, _BlendSharpness);
                hw /= max(dot(hw, 1.0h), 1e-4h);
                half3 albedo = g * hw.x + r * hw.y + l * hw.z + d * hw.w;

                // normal perturbation from the dominant layer (top projection), cheap whiteout blend
                half3 nTex = UnpackNormal(SAMPLE_TEXTURE2D(_GrassNormal, sampler_GrassMap, top / _Tiling.x)) * hw.x
                           + UnpackNormal(SAMPLE_TEXTURE2D(_RockNormal, sampler_GrassMap, top / _Tiling.y)) * hw.y
                           + UnpackNormal(SAMPLE_TEXTURE2D(_LeafNormal, sampler_GrassMap, top / _Tiling.z)) * hw.z
                           + UnpackNormal(SAMPLE_TEXTURE2D(_DirtNormal, sampler_GrassMap, top / _Tiling.w)) * hw.w;
                half3 nW = normalize(half3(n.x + nTex.x * 0.6h, n.y, n.z + nTex.y * 0.6h));

                InkSurface s = (InkSurface)0;
                s.albedo = albedo;
                s.normalWS = nW;
                s.viewDirWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                s.positionWS = i.positionWS;
                s.smoothness = _Smoothness;
                s.occlusion = 1;
                s.screenUV = GetNormalizedScreenSpaceUV(i.positionCS);
                s.positionCS = i.positionCS;
                s.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                half3 c = InkShade(s);
                return half4(MixFog(c, i.fog), 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On ColorMask 0
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"
            float3 _LightDirection; float3 _LightPosition;
            struct A { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            float4 vert(A v) : SV_POSITION
            {
                float3 p = TransformObjectToWorld(v.positionOS.xyz);
                float3 n = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 ld = normalize(_LightPosition - p);
            #else
                float3 ld = _LightDirection;
            #endif
                return ApplyShadowClamping(TransformWorldToHClip(ApplyShadowBias(p, n, ld)));
            }
            half4 frag() : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On ColorMask R
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            struct A { float4 positionOS : POSITION; };
            float4 vert(A v) : SV_POSITION { return TransformObjectToHClip(v.positionOS.xyz); }
            half frag(float4 p : SV_POSITION) : SV_Target { return p.z; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RenderingLayers.hlsl"
            struct A { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct V { float4 positionCS : SV_POSITION; half3 n : TEXCOORD0; };
            V vert(A v) { V o; o.positionCS = TransformObjectToHClip(v.positionOS.xyz); o.n = TransformObjectToWorldNormal(v.normalOS); return o; }
            void frag(V i, out half4 outNormalWS : SV_Target0
            #ifdef _WRITE_RENDERING_LAYERS
                , out uint outRenderingLayers : SV_Target1
            #endif
            )
            {
                float3 normalWS = normalize(i.n);
            #if defined(_GBUFFER_NORMALS_OCT)
                float2 oct = PackNormalOctQuadEncode(normalWS);
                outNormalWS = half4(PackFloat2To888(saturate(oct * 0.5 + 0.5)), 0.0);
            #else
                outNormalWS = half4(normalWS, 0.0);
            #endif
            #ifdef _WRITE_RENDERING_LAYERS
                outRenderingLayers = EncodeMeshRenderingLayer();
            #endif
            }
            ENDHLSL
        }
    }
}
