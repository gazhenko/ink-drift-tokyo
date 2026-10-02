// Physically based shading for the driver (suit, gloves): URP PBR lighting (GGX, cascaded soft shadows, Forward+
// lights, reflection probes) with a tiling detail normal on UV0, baked AO / convexity / cavity on a unique UV1,
// fabric sheen and edge wear. Writes the InkMask pass so the comic post pass leaves these pixels clean.
Shader "InkDrift/Realistic"
{
    Properties
    {
        [MainColor] _BaseColor ("Color", Color) = (1, 1, 1, 1)
        [MainTexture] _BaseMap ("Albedo scan / decal (UV0 x tiling, or triplanar)", 2D) = "white" {}
        _TexMean ("Scan mean colour (albedo is normalised by it)", Color) = (1, 1, 1, 1)
        _Desaturate ("Desaturate scan", Range(0, 1)) = 0
        [Normal][NoScaleOffset] _BumpMap ("Scan normal", 2D) = "bump" {}
        _BumpScale ("Scan normal strength", Float) = 1
        [NoScaleOffset] _MaskMap ("Scan mask (G AO, A smoothness)", 2D) = "white" {}
        _MaskStrength ("Scan mask strength", Range(0, 1)) = 0
        _MaskSmoothMean ("Scan mean smoothness", Range(0.01, 1)) = 0.5
        [Normal][NoScaleOffset] _DetailNormal ("Macro normal (UV0, e.g. quilting)", 2D) = "bump" {}
        _DetailTiling ("Macro normal tiling", Float) = 1
        _DetailScale ("Macro normal strength", Float) = 0
        _Triplanar ("Triplanar (1 / tile metres, 0 = UV0)", Float) = 0
        [HDR] _EmissionColor ("Emission", Color) = (0, 0, 0, 0)
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
        _EnvSpecular ("Environment Reflection (interior specular occlusion)", Range(0, 1)) = 1
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
        TEXTURE2D(_MaskMap);  SAMPLER(sampler_MaskMap);
        TEXTURE2D(_DetailNormal);  SAMPLER(sampler_DetailNormal);

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
            half4 _TexMean;
            half _Desaturate;
            half _MaskStrength;
            half _MaskSmoothMean;
            float _DetailTiling;
            half _DetailScale;
            float _Triplanar;
            half4 _EmissionColor;
            half _EnvSpecular;
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
                float4 uv : TEXCOORD0;          // xy UV0, zw bake UV1
                float3 positionWS : TEXCOORD1;
                half3 normalWS : TEXCOORD2;
                half4 tangentWS : TEXCOORD3;
                half fogFactor : TEXCOORD4;
                float3 positionOS : TEXCOORD5;  // triplanar (moves with the part: wheel, levers)
                half3 normalOS : TEXCOORD6;
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
                o.positionOS = v.positionOS.xyz;
                o.normalOS = v.normalOS;
                o.fogFactor = ComputeFogFactor(p.positionCS.z);
                return o;
            }

            // scan albedo tinted to _BaseColor while keeping the scan's own variation
            half3 Tint(half3 tex)
            {
                half3 t = lerp(tex, Luminance(tex).xxx, _Desaturate);
                half3 m = lerp(_TexMean.rgb, Luminance(_TexMean.rgb).xxx, _Desaturate);
                return _BaseColor.rgb * t / max(m, 0.02h);
            }

            half4 frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half3 nWS0 = normalize(i.normalWS);
                half3 normalWS;
                half4 tex, mask;
                if (_Triplanar > 0.0)
                {
                    // object-space triplanar with whiteout normal blending (procedural cockpit parts have no real UVs)
                    float3 p = i.positionOS * _Triplanar;
                    half3 nOS = normalize(i.normalOS);
                    half3 w = pow(abs(nOS), 4.0h); w /= (w.x + w.y + w.z);
                    float2 ux = p.zy, uy = p.xz, uz = p.xy;
                    tex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, ux) * w.x + SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uy) * w.y + SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uz) * w.z;
                    mask = SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, ux) * w.x + SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, uy) * w.y + SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, uz) * w.z;
                    half3 tx = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, ux), _BumpScale);
                    half3 ty = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uy), _BumpScale);
                    half3 tz = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uz), _BumpScale);
                    tx = half3(tx.xy + nOS.zy, abs(tx.z) * nOS.x);
                    ty = half3(ty.xy + nOS.xz, abs(ty.z) * nOS.y);
                    tz = half3(tz.xy + nOS.xy, abs(tz.z) * nOS.z);
                    half3 nb = normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
                    normalWS = normalize(TransformObjectToWorldNormal(nb));
                }
                else
                {
                    float2 uv = TRANSFORM_TEX(i.uv.xy, _BaseMap);
                    tex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uv);
                    mask = SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, uv);
                    half3 nTS = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uv), _BumpScale);
                    half3 mTS = UnpackNormalScale(SAMPLE_TEXTURE2D(_DetailNormal, sampler_DetailNormal, i.uv.xy * _DetailTiling), _DetailScale);
                    nTS = normalize(half3(nTS.xy + mTS.xy, nTS.z * mTS.z));   // whiteout: fine scan detail over macro shape
                    half3 bit = cross(nWS0, i.tangentWS.xyz) * i.tangentWS.w;
                    normalWS = normalize(TransformTangentToWorld(nTS, half3x3(i.tangentWS.xyz, bit, nWS0)));
                }
            #if defined(_ALPHATEST_ON)
                clip(tex.a * _BaseColor.a - _Cutoff);
            #endif
                half3 bake = SAMPLE_TEXTURE2D(_BakeMap, sampler_BakeMap, i.uv.zw).rgb;
                half ao = lerp(1.0h, bake.r, _AOStrength) * lerp(1.0h, mask.g, _MaskStrength);
                half convex = bake.g;
                half cavity = lerp(1.0h, 1.0h - bake.b, _CavityStrength);

                // edge wear on convex areas, grime in cavities
                half wear = saturate((convex - 0.56h) * 6.0h) * _Wear;
                half3 albedo = lerp(Tint(tex.rgb), _WearColor.rgb, wear) * cavity;
                half smooth = lerp(_Smoothness, saturate(mask.a / _MaskSmoothMean * _Smoothness), _MaskStrength);
                smooth *= lerp(1.0h, 0.55h, wear) * lerp(0.75h, 1.0h, ao);
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
                s.normalTS = half3(0, 0, 1);
                // indirect light is done here rather than by URP (occlusion 0 switches its GI off), so the reflection
                // can use the smooth normal's Fresnel and horizon occlusion
                s.occlusion = 0.0h;
                s.emission = _EmissionColor.rgb;
                s.alpha = 1.0h;

                half4 color = UniversalFragmentPBR(input, s);
                // ambient fill
                color.rgb += input.bakedGI * s.albedo * (1.0h - _Metallic) * 0.96h * ao;
                // environment reflection. Interior: the cabin blocks most of the outside world (_EnvSpecular). Fresnel
                // comes from the smooth normal, and reflections the bumpy normal sends back into the surface are dropped
                // (horizon occlusion); otherwise every grazing grain of leather or suede sparkles with the sky.
                {
                    BRDFData brdf;
                    SurfaceData sb = s;
                    InitializeBRDFData(sb, brdf);
                    half3 V = input.viewDirectionWS;
                    half3 R = reflect(-V, normalWS);
                    half horizon = saturate(1.0h + 1.3h * dot(R, nWS0));
                    half fresnel = Pow4(1.0h - saturate(dot(nWS0, V)));
                    half3 env = GlossyEnvironmentReflection(R, input.positionWS, brdf.perceptualRoughness, 1.0h, input.normalizedScreenSpaceUV);
                    env = min(env, 4.0h);   // no single sun-lit texel of the probe as a hot speck
                    color.rgb += env * EnvironmentBRDFSpecular(brdf, fresnel) * ao * _EnvSpecular * horizon * horizon;
                }

                // fabric sheen: grazing-angle retro-reflection of the weave
                if (_Sheen > 0.001h)
                {
                    Light ml = GetMainLight(input.shadowCoord, input.positionWS, input.shadowMask);
                    // grazing factor from the smooth surface normal: with the bumpy detail normal it spikes to 1 on
                    // every fibre that tips past the silhouette, sparkling with the ambient colour
                    half NdotV = saturate(dot(nWS0, input.viewDirectionWS));
                    half f = pow(1.0h - NdotV, 4.0h) * lerp(0.7h, 1.0h, saturate(dot(normalWS, input.viewDirectionWS) * 4.0h));
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
