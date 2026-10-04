Shader "InkDrift/Toon"
{
    Properties
    {
        [MainTexture] _BaseMap ("Albedo", 2D) = "white" {}
        [MainColor] _BaseColor ("Color", Color) = (1,1,1,1)
        [Normal][NoScaleOffset] _BumpMap ("Normal", 2D) = "bump" {}
        _BumpScale ("Normal Scale", Float) = 1
        [NoScaleOffset] _MaskMap ("Mask (R metal, G AO, B height, A smooth)", 2D) = "white" {}
        _Metallic ("Metallic", Range(0,1)) = 0
        _Smoothness ("Smoothness", Range(0,1)) = 0.3
        _OcclusionStrength ("AO Strength", Range(0,1)) = 1
        [NoScaleOffset] _EmissionMap ("Emission", 2D) = "white" {}
        [HDR] _EmissionColor ("Emission", Color) = (0,0,0,0)
        _ShadowColor ("Shadow Color (x global tint)", Color) = (1,1,1,1)
        _ShadowThreshold ("Terminator", Range(-1,1)) = 0.0
        _BandSoftness ("Band Softness (0 = global comic band)", Range(0,1)) = 0
        _SpecSoftness ("Highlight Softness", Range(0.02,1)) = 0.02
        _HighlightThreshold ("Highlight Band", Range(0,1)) = 0.6
        _HighlightBoost ("Highlight Boost", Range(0,1)) = 0.12
        _SpecSize ("Spec Size", Range(0,1)) = 0.12
        _SpecIntensity ("Spec Intensity", Range(0,4)) = 1
        _RimAmount ("Rim", Range(0,2)) = 0.6
        _ReflectStrength ("Reflection", Range(0,2)) = 0
        _ReflectBands ("Reflection Bands", Float) = 4
        _HalftoneAmount ("Halftone", Range(0,1)) = 1
        _VertexAO ("Vertex Color AO (R)", Range(0,1)) = 0
        _WindStrength ("Wind (vertex G)", Range(0,3)) = 0
        _HueVariation ("Variation (vertex B)", Range(0,1)) = 0
        _VertexTint ("Vertex Color Tint (RGB)", Range(0,1)) = 0
        _BackfaceFlip ("Flip Normal On Backfaces", Range(0,1)) = 1
        _ReceiveShadows ("Receive Shadows", Range(0,1)) = 1
        _Cutoff ("Alpha Cutoff", Range(0,1)) = 0.5
        _WorldUVScale ("World UV Scale", Float) = 0.25
        _WetAmount ("Wetness", Range(0,1)) = 0
        _MaskHeightPuddles ("Puddles from mask B", Range(0,1)) = 0
        [Toggle(_ALPHATEST_ON)] _AlphaClip ("Alpha Clip", Float) = 0
        [Toggle(_NORMALMAP)] _UseNormalMap ("Use Normal Map", Float) = 0
        [Toggle(_MASKMAP)] _UseMaskMap ("Use Mask Map", Float) = 0
        [Toggle(_EMISSION)] _UseEmission ("Use Emission", Float) = 0
        [Toggle(_WORLD_UV)] _WorldUV ("World UV (triplanar-ish)", Float) = 0
        [Toggle(_WET)] _Wet ("Wet / Planar Reflection", Float) = 0
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" "UniversalMaterialType" = "Lit" }
        LOD 300

        HLSLINCLUDE
        #include "InkToonInput.hlsl"
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma shader_feature_local _NORMALMAP
            #pragma shader_feature_local _MASKMAP
            #pragma shader_feature_local _EMISSION
            #pragma shader_feature_local _WORLD_UV
            #pragma shader_feature_local _WET

            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "InkToonLighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                half3 normalWS : TEXCOORD2;
                half4 tangentWS : TEXCOORD3;
                half4 color : TEXCOORD4;
                half fogFactor : TEXCOORD5;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 posWS = TransformObjectToWorld(v.positionOS.xyz);
                posWS = InkWind(posWS, v.color.g);
                VertexNormalInputs n = GetVertexNormalInputs(v.normalOS, v.tangentOS);
                o.positionWS = posWS;
                o.positionCS = TransformWorldToHClip(posWS);
                o.normalWS = n.normalWS;
                o.tangentWS = half4(n.tangentWS, v.tangentOS.w * GetOddNegativeScale());
                o.uv = v.uv;
                o.color = v.color;
                o.fogFactor = ComputeFogFactor(o.positionCS.z);
                return o;
            }

        #if defined(_WET)
            float _RainIntensity;   // global (RainWeather): 0 dry .. 1 pouring

            float2 InkHash2(float2 p)
            {
                p = float2(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)));
                return frac(sin(p) * 43758.5453);
            }

            // raindrop rings on standing water: one drop per ~0.5 m cell, expanding and fading on its own clock;
            // returns the slope (xz) of the ripple height field
            float2 RainRipples(float2 p)
            {
                float2 grad = 0;
                [unroll] for (int layer = 0; layer < 2; layer++)
                {
                    float2 q = p * (layer == 0 ? 2.1 : 2.9) + layer * 17.3;
                    float2 cell = floor(q), f = frac(q);
                    float2 h = InkHash2(cell);
                    float t = frac(_Time.y * (1.1 + h.y * 0.6) + h.x);
                    float2 d = f - (0.25 + h * 0.5);
                    float r = length(d);
                    float rr = t * 0.45;
                    float band = saturate(1.0 - abs(r - rr) * 14.0);
                    float wave = sin((r - rr) * 60.0) * band * (1.0 - t) * (1.0 - t);
                    grad += d / max(r, 1e-3) * wave;
                }
                return grad;
            }
        #endif

            half4 frag(Varyings i, bool isFrontFace : SV_IsFrontFace) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half3 normalWS = normalize(i.normalWS);
                if (!isFrontFace && _BackfaceFlip > 0.5h) normalWS = -normalWS;
                float2 uv = InkUV(i.uv, i.positionWS, normalWS);
                half4 baseTex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uv);
                half alpha = baseTex.a * _BaseColor.a;
            #if defined(_ALPHATEST_ON)
                clip(alpha - _Cutoff);
            #endif
                half3 albedo = baseTex.rgb * _BaseColor.rgb;
                albedo *= 1.0h + (i.color.b - 0.5h) * _HueVariation;
                albedo *= lerp(half3(1, 1, 1), i.color.rgb, _VertexTint);

            #if defined(_NORMALMAP)
                half3 nTS = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uv), _BumpScale);
                half3 bitangent = i.tangentWS.w * cross(normalWS, i.tangentWS.xyz);
                normalWS = normalize(TransformTangentToWorld(nTS, half3x3(i.tangentWS.xyz, bitangent, normalWS)));
            #endif

                half metallic = _Metallic, smooth = _Smoothness, ao = 1.0h, height = 0.5h;
            #if defined(_MASKMAP)
                half4 m = SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, uv);
                metallic *= m.r; ao = m.g; height = m.b; smooth *= m.a;
            #endif
                ao *= lerp(1.0h, i.color.r, _VertexAO);

                InkSurface s = (InkSurface)0;
                s.albedo = albedo;
                s.normalWS = normalWS;
                s.viewDirWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                s.positionWS = i.positionWS;
                s.metallic = metallic;
                s.smoothness = smooth;
                s.occlusion = ao;
                s.screenUV = GetNormalizedScreenSpaceUV(i.positionCS);
                s.positionCS = i.positionCS;
                s.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
            #if defined(_EMISSION)
                s.emission = SAMPLE_TEXTURE2D(_EmissionMap, sampler_EmissionMap, uv).rgb * _EmissionColor.rgb;
            #else
                s.emission = _EmissionColor.rgb;
            #endif
            #if defined(_WET)
                half puddle = lerp(1.0h, smoothstep(0.55h, 0.35h, height), _MaskHeightPuddles);
                s.wet = _WetAmount * puddle;
                s.smoothness = lerp(s.smoothness, 0.92h, s.wet);
                if (_RainIntensity > 0.001 && normalWS.y > 0.7h)
                {
                    // rain on the water: ripples tilt the normal, which ripples the reflections too
                    float2 g = RainRipples(i.positionWS.xz) * (_RainIntensity * 0.35 * s.wet);
                    s.normalWS = normalize(normalWS + half3(g.x, 0, g.y));
                }
            #endif
                half3 c = InkShade(s);
                c = MixFog(c, i.fogFactor);
                return half4(c, 1.0h);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; half4 color : COLOR; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                float3 posWS = InkWind(TransformObjectToWorld(v.positionOS.xyz), v.color.g);
                float3 nWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - posWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(posWS, nWS, lightDir));
                cs = ApplyShadowClamping(cs);
                o.positionCS = cs;
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
            #if defined(_ALPHATEST_ON)
                clip(SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).a * _BaseColor.a - _Cutoff);
            #endif
                return 0;
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_instancing

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                o.positionCS = TransformWorldToHClip(InkWind(TransformObjectToWorld(v.positionOS.xyz), v.color.g));
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                return o;
            }

            half frag(Varyings i) : SV_Target
            {
            #if defined(_ALPHATEST_ON)
                clip(SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).a * _BaseColor.a - _Cutoff);
            #endif
                return i.positionCS.z;
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma shader_feature_local _NORMALMAP
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RenderingLayers.hlsl"

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float4 tangentOS : TANGENT; float2 uv : TEXCOORD0; half4 color : COLOR; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half3 normalWS : TEXCOORD1; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                o.positionCS = TransformWorldToHClip(InkWind(TransformObjectToWorld(v.positionOS.xyz), v.color.g));
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }

            void frag(Varyings i, bool isFrontFace : SV_IsFrontFace, out half4 outNormalWS : SV_Target0
            #ifdef _WRITE_RENDERING_LAYERS
                , out uint outRenderingLayers : SV_Target1
            #endif
            )
            {
            #if defined(_ALPHATEST_ON)
                clip(SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).a * _BaseColor.a - _Cutoff);
            #endif
                float3 normalWS = normalize(i.normalWS);
                if (!isFrontFace && _BackfaceFlip > 0.5h) normalWS = -normalWS;
            #if defined(_GBUFFER_NORMALS_OCT)
                float2 octNormalWS = PackNormalOctQuadEncode(normalWS);
                float2 remapped = saturate(octNormalWS * 0.5 + 0.5);
                outNormalWS = half4(PackFloat2To888(remapped), 0.0);
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
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
