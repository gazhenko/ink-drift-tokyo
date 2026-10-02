// Physically based shading for the driver (suit, gloves): URP PBR lighting (GGX, cascaded soft shadows, Forward+
// lights, reflection probes) with a tiling detail normal on UV0, baked AO / convexity / cavity on a unique UV1,
// fabric sheen and edge wear. Writes the InkMask pass so the comic post pass leaves these pixels clean.
Shader "InkDrift/Realistic"
{
    Properties
    {
        [MainColor] _BaseColor ("Color", Color) = (1, 1, 1, 1)
        [MainTexture] _BaseMap ("Albedo / Decal (UV0)", 2D) = "white" {}
        [Normal][NoScaleOffset] _BumpMap ("Detail Normal (UV0, tiling)", 2D) = "bump" {}
        _BumpScale ("Detail Normal Strength", Float) = 1
        [NoScaleOffset] _BakeMap ("Bake (UV1): R AO, G convexity, B cavity", 2D) = "white" {}
        _AOStrength ("AO Strength", Range(0, 1)) = 1
        _CavityStrength ("Cavity Strength", Range(0, 1)) = 0.6
        _Smoothness ("Smoothness", Range(0, 1)) = 0.3
        _Metallic ("Metallic", Range(0, 1)) = 0
        _Sheen ("Fabric Sheen", Range(0, 1)) = 0
        _SheenColor ("Sheen Color", Color) = (1, 1, 1, 1)
        _Wear ("Edge Wear", Range(0, 1)) = 0
        _WearColor ("Wear Color", Color) = (0.45, 0.45, 0.47, 1)
        _AmbientBoost ("Ambient Boost", Range(0, 4)) = 1
        _Cutoff ("Alpha Cutoff", Range(0, 1)) = 0.5
        [Toggle(_ALPHATEST_ON)] _AlphaClip ("Alpha Clip (decals)", Float) = 0
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        TEXTURE2D(_BaseMap);  SAMPLER(sampler_BaseMap);
        TEXTURE2D(_BumpMap);  SAMPLER(sampler_BumpMap);
        TEXTURE2D(_BakeMap);  SAMPLER(sampler_BakeMap);

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            half _BumpScale;
            half _AOStrength;
            half _CavityStrength;
            half _Smoothness;
            half _Metallic;
            half _Sheen;
            half4 _SheenColor;
            half _Wear;
            half4 _WearColor;
            half _AmbientBoost;
            half _Cutoff;
        CBUFFER_END

        half4 BaseSample(float2 uv)
        {
            return SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, TRANSFORM_TEX(uv, _BaseMap)) * _BaseColor;
        }
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

            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv : TEXCOORD0;
                float2 uv1 : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float4 uv : TEXCOORD0;          // xy tiling / decal, zw bake
                float3 positionWS : TEXCOORD1;
                half3 normalWS : TEXCOORD2;
                half4 tangentWS : TEXCOORD3;
                half fogFactor : TEXCOORD4;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings vert(Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                VertexNormalInputs n = GetVertexNormalInputs(v.normalOS, v.tangentOS);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = n.normalWS;
                o.tangentWS = half4(n.tangentWS, v.tangentOS.w * GetOddNegativeScale());
                o.uv = float4(v.uv, v.uv1);
                o.fogFactor = ComputeFogFactor(p.positionCS.z);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half4 base = BaseSample(i.uv.xy);
            #if defined(_ALPHATEST_ON)
                clip(base.a - _Cutoff);
            #endif
                half3 bake = SAMPLE_TEXTURE2D(_BakeMap, sampler_BakeMap, i.uv.zw).rgb;
                half ao = lerp(1.0h, bake.r, _AOStrength);
                half convex = bake.g;
                half cavity = lerp(1.0h, 1.0h - bake.b, _CavityStrength);

                // fine surface detail (weave / grain / print) in tangent space
                half3 nTS = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, i.uv.xy), _BumpScale);   // UV0 is laid out in tile units
                half3 nWS0 = normalize(i.normalWS);
                half3 bit = cross(nWS0, i.tangentWS.xyz) * i.tangentWS.w;
                half3 normalWS = normalize(TransformTangentToWorld(nTS, half3x3(i.tangentWS.xyz, bit, nWS0)));

                // edge wear on convex areas, grime in cavities
                half wear = saturate((convex - 0.56h) * 6.0h) * _Wear;
                half3 albedo = lerp(base.rgb, _WearColor.rgb, wear) * cavity;
                half smooth = _Smoothness * lerp(1.0h, 0.55h, wear) * lerp(0.75h, 1.0h, ao);
                // geometric specular anti-aliasing: widen the highlight where the normal changes faster than a pixel
                float3 dndx = ddx(normalWS), dndy = ddy(normalWS);
                float variance = 0.25 * (dot(dndx, dndx) + dot(dndy, dndy));
                float rough = 1.0 - smooth;
                smooth = (half)(1.0 - sqrt(saturate(rough * rough + min(2.0 * variance, 0.2))));

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = normalWS;
                input.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                input.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                input.fogCoord = i.fogFactor;
                input.bakedGI = SampleSH(normalWS) * _AmbientBoost;
                input.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                input.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo * lerp(1.0h, ao, 0.35h);   // a little occlusion on direct light too (contact darkening)
                s.metallic = _Metallic;
                s.smoothness = smooth;
                s.normalTS = nTS;
                s.occlusion = ao;
                s.alpha = 1.0h;

                half4 color = UniversalFragmentPBR(input, s);

                // fabric sheen: grazing-angle retro-reflection of the weave
                if (_Sheen > 0.001h)
                {
                    Light ml = GetMainLight(input.shadowCoord, input.positionWS, input.shadowMask);
                    half NdotV = saturate(dot(normalWS, input.viewDirectionWS));
                    half f = pow(1.0h - NdotV, 4.0h);
                    half wrap = saturate(dot(normalWS, ml.direction) * 0.5h + 0.5h);
                    half3 light = ml.color * ml.shadowAttenuation * ml.distanceAttenuation * wrap + input.bakedGI;
                    color.rgb += _SheenColor.rgb * _Sheen * f * light * ao;
                }
                color.rgb = MixFog(color.rgb, input.fogCoord);
                return half4(color.rgb, 1.0h);
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

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                float3 posWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 nWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - posWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                o.positionCS = ApplyShadowClamping(TransformWorldToHClip(ApplyShadowBias(posWS, nWS, lightDir)));
                o.uv = v.uv;
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
            #if defined(_ALPHATEST_ON)
                clip(BaseSample(i.uv).a - _Cutoff);
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

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = v.uv;
                return o;
            }

            half frag(Varyings i) : SV_Target
            {
            #if defined(_ALPHATEST_ON)
                clip(BaseSample(i.uv).a - _Cutoff);
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
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing
            #include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RenderingLayers.hlsl"

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half3 normalWS : TEXCOORD1; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = v.uv;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }

            void frag(Varyings i, out half4 outNormalWS : SV_Target0
            #ifdef _WRITE_RENDERING_LAYERS
                , out uint outRenderingLayers : SV_Target1
            #endif
            )
            {
            #if defined(_ALPHATEST_ON)
                clip(BaseSample(i.uv).a - _Cutoff);
            #endif
                float3 normalWS = normalize(i.normalWS);
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

        // drawn by InkMaskFeature into _InkMaskTex: the comic post skips ink lines and grain here
        Pass
        {
            Name "InkMask"
            Tags { "LightMode" = "InkMask" }
            ZWrite Off
            ZTest LEqual
            Cull [_Cull]
            ColorMask R

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma shader_feature_local _ALPHATEST_ON
            #pragma multi_compile_instancing

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };

            Varyings vert(Attributes v)
            {
                UNITY_SETUP_INSTANCE_ID(v);
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = v.uv;
                return o;
            }

            half frag(Varyings i) : SV_Target
            {
            #if defined(_ALPHATEST_ON)
                clip(BaseSample(i.uv).a - _Cutoff);
            #endif
                return 1.0h;
            }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
