// Toon smoke (lit, dissolve-edged puffs), additive glow particles, and skidmarks.
Shader "InkDrift/ToonSmoke"
{
    Properties
    {
        _MainTex ("Puff (R shape, G noise)", 2D) = "white" {}
        _LitColor ("Lit", Color) = (1, 1, 1, 1)
        _ShadeColor ("Shade", Color) = (0.8, 0.8, 0.9, 1)
        _InkEdge ("Ink Edge", Range(0, 0.2)) = 0.06
        _Softness ("Edge Softness", Range(0.001, 0.2)) = 0.02
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            half4 _LitColor, _ShadeColor, _InkColor;
            half _InkEdge, _Softness;

            struct Attributes { float4 positionOS : POSITION; half4 color : COLOR; float2 uv : TEXCOORD0; };
            struct Varyings { float4 positionCS : SV_POSITION; half4 color : COLOR; float2 uv : TEXCOORD0; float3 positionWS : TEXCOORD1; half fog : TEXCOORD2; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.color = v.color; o.uv = v.uv;
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half4 t = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                float2 c = i.uv * 2.0 - 1.0;
                float r2 = dot(c, c);
                // fake sphere normal in view space -> world
                float3 nV = float3(c.x, c.y, sqrt(saturate(1.0 - r2)));
                float3 nW = normalize(mul((float3x3)UNITY_MATRIX_I_V, nV));
                Light sun = GetMainLight();
                half ndl = dot(nW, sun.direction);
                half lit = smoothstep(-0.05, 0.05, ndl);
                half shape = t.r * (0.75 + 0.25 * t.g);
                // dissolve: particle alpha raises the threshold, giving crisp anime puffs that erode away
                half thr = 1.0 - i.color.a;
                half a = smoothstep(thr, thr + _Softness, shape);
                half edge = a - smoothstep(thr + _InkEdge, thr + _InkEdge + _Softness, shape);
                half3 amb = SampleSH(half3(0, 1, 0));
                half3 col = lerp(_ShadeColor.rgb * (amb * 0.8 + 0.42), _LitColor.rgb * (sun.color * 0.7 + amb * 0.5 + 0.3), lit) * i.color.rgb;
                col = lerp(col, col * 0.55, saturate(edge) * 0.7);
                col = MixFog(col, i.fog);
                return half4(col, a);
            }
            ENDHLSL
        }
    }
}
