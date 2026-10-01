Shader "InkDrift/Skidmark"
{
    Properties
    {
        _MainTex ("Tread", 2D) = "white" {}
        _Color ("Color", Color) = (0.05, 0.05, 0.07, 1)
    }
    SubShader
    {
        Tags { "Queue" = "Transparent-100" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Offset -2, -2
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            half4 _Color;
            struct A { float4 p : POSITION; half4 c : COLOR; float2 uv : TEXCOORD0; };
            struct V { float4 p : SV_POSITION; half4 c : COLOR; float2 uv : TEXCOORD0; half fog : TEXCOORD1; };
            V vert(A v) { V o; o.p = TransformObjectToHClip(v.p.xyz); o.c = v.c; o.uv = v.uv; o.fog = ComputeFogFactor(o.p.z); return o; }
            half4 frag(V i) : SV_Target
            {
                half t = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv).r;
                half edge = smoothstep(0.0, 0.12, i.uv.x) * smoothstep(1.0, 0.88, i.uv.x);
                half a = i.c.a * edge * (0.7 + 0.3 * t) * _Color.a;
                return half4(MixFog(_Color.rgb, i.fog), a);
            }
            ENDHLSL
        }
    }
}
