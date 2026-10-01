// Additive HDR particles (sparks, flames, glows) — uses vertex color * _Color * texture.
Shader "InkDrift/Additive"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
        [HDR] _Color ("Color", Color) = (4, 2, 0.6, 1)
    }
    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
        Blend One One
        ZWrite Off
        Cull Off
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            half4 _Color;
            struct A { float4 p : POSITION; half4 c : COLOR; float2 uv : TEXCOORD0; };
            struct V { float4 p : SV_POSITION; half4 c : COLOR; float2 uv : TEXCOORD0; };
            V vert(A v) { V o; o.p = TransformObjectToHClip(v.p.xyz); o.c = v.c; o.uv = v.uv; return o; }
            half4 frag(V i) : SV_Target
            {
                half4 t = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, i.uv);
                half3 c = t.rgb * t.a * i.c.rgb * i.c.a * _Color.rgb;
                return half4(c, 0);
            }
            ENDHLSL
        }
    }
}
