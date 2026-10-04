// Rain for the wet tracks (RainWeather): thin streaks that pick up the city's light, and expanding splash rings.
Shader "InkDrift/Rain"
{
    Properties
    {
        _Tint ("Tint", Color) = (0.75, 0.85, 1, 0.45)
        [Toggle] _Ring ("Splash ring (else streak)", Float) = 0
        _Glow ("Light pickup", Range(0, 4)) = 1.6
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

            half4 _Tint;
            half _Ring, _Glow;

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
                half a;
                if (_Ring > 0.5h)
                {
                    float r = length(i.uv * 2.0 - 1.0);
                    a = saturate(1.0 - abs(r - 0.8) * 7.0) * step(r, 1.0);
                }
                else
                {
                    // streak: thin across, tapered along
                    float x = abs(i.uv.x * 2.0 - 1.0), y = i.uv.y;
                    a = saturate(1.4 - x * 1.4) * smoothstep(0.0, 0.2, y) * smoothstep(1.0, 0.7, y);
                }
                // the drops catch whatever light is around: sky/neon ambient and the nearest street lights
                half3 light = SampleSH(half3(0, 1, 0)) * 0.6 + 0.12;
                Light sun = GetMainLight();
                light += sun.color * 0.15;
                half3 col = _Tint.rgb * light * _Glow * i.color.rgb;
                // fade out right in front of the lens
                float camD = length(i.positionWS - _WorldSpaceCameraPos);
                a *= _Tint.a * i.color.a * saturate((camD - 0.6) / 1.2);
                col = MixFog(col, i.fog);
                return half4(col, a);
            }
            ENDHLSL
        }
    }
}
