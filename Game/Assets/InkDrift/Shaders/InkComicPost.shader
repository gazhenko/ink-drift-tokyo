Shader "InkDrift/ComicPost"
{
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" }
        ZWrite Off ZTest Always Blend Off Cull Off

        Pass
        {
            Name "InkOutline"
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma target 3.5
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareNormalsTexture.hlsl"

            half4 _InkColor;
            float4 _InkParams;   // x width px, y depth sens, z normal sens
            float4 _InkFade;     // x start m, y end m
            float4 _ComicParams; // x halftone, y scale, z grain, w vignette
            float _ComicPulse;
            TEXTURE2D(_InkMaskTex);   // 1 where realistic objects (the driver) are visible: no ink, no grain

            float Hash(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }

            float LinearDepth(float2 uv)
            {
                float raw = SampleSceneDepth(uv);
                return LinearEyeDepth(raw, _ZBufferParams);
            }

            half4 Frag(Varyings input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                float2 uv = input.texcoord;
                half4 col = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, uv);

                float scale = _ScreenParams.y / 1080.0;
                float w = max(_InkParams.x * scale, 0.75);
                float2 px = w / _ScreenParams.xy;

                float d0 = LinearDepth(uv);
                float d1 = LinearDepth(uv + float2(px.x, px.y));
                float d2 = LinearDepth(uv + float2(-px.x, -px.y));
                float d3 = LinearDepth(uv + float2(px.x, -px.y));
                float d4 = LinearDepth(uv + float2(-px.x, px.y));

                // relative depth discontinuity (scale-invariant)
                float dd = (abs(d1 - d2) + abs(d3 - d4)) / max(d0, 0.1);
                float depthEdge = smoothstep(0.035, 0.09, dd * _InkParams.y);

                float3 n1 = SampleSceneNormals(uv + float2(px.x, px.y));
                float3 n2 = SampleSceneNormals(uv + float2(-px.x, -px.y));
                float3 n3 = SampleSceneNormals(uv + float2(px.x, -px.y));
                float3 n4 = SampleSceneNormals(uv + float2(-px.x, px.y));
                float nd = length(n1 - n2) + length(n3 - n4);
                float normalEdge = smoothstep(0.55, 0.95, nd * _InkParams.z);

                float edge = saturate(max(depthEdge, normalEdge));
                // keep realistic surfaces clean, including the outline that would hug their silhouette
                float m0 = SAMPLE_TEXTURE2D(_InkMaskTex, sampler_PointClamp, uv).r;
                float2 mp = px * 1.5;
                float mn = max(max(SAMPLE_TEXTURE2D(_InkMaskTex, sampler_PointClamp, uv + mp).r, SAMPLE_TEXTURE2D(_InkMaskTex, sampler_PointClamp, uv - mp).r),
                               max(SAMPLE_TEXTURE2D(_InkMaskTex, sampler_PointClamp, uv + float2(mp.x, -mp.y)).r, SAMPLE_TEXTURE2D(_InkMaskTex, sampler_PointClamp, uv + float2(-mp.x, mp.y)).r));
                edge *= 1.0 - max(m0, mn);
                // fade with distance so far geometry doesn't turn to mush; skybox has no outline interior
                float fade = 1.0 - smoothstep(_InkFade.x, _InkFade.y, d0);
                fade = max(fade, depthEdge * 0.5 * (1.0 - smoothstep(_InkFade.y, _InkFade.y * 2.5, d0)));
                edge *= fade;

                half3 c = lerp(col.rgb, _InkColor.rgb, edge * _InkColor.a);

                // paper grain + ink vignette
                float g = Hash(floor(uv * _ScreenParams.xy * 0.5) + floor(_Time.y * 12.0)) - 0.5;
                c += g * _ComicParams.z * 0.25 * (1.0 - m0);
                float2 v = uv - 0.5;
                float vig = smoothstep(0.35, 0.85, length(v * float2(_ScreenParams.x / _ScreenParams.y, 1.0)) * 0.9);
                c = lerp(c, c * _InkColor.rgb * 2.0, vig * _ComicParams.w);

                // callout pulse: saturation punch + slight chromatic split
                if (_ComicPulse > 0.001)
                {
                    float2 dir = v * 0.012 * _ComicPulse;
                    half r = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, uv + dir).r;
                    half b = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, uv - dir).b;
                    c.r = lerp(c.r, r * (1.0 - edge) + _InkColor.r * edge, 0.6);
                    c.b = lerp(c.b, b * (1.0 - edge) + _InkColor.b * edge, 0.6);
                    half l = Luminance(c);
                    c = lerp(l.xxx, c, 1.0 + _ComicPulse * 0.6);
                }
                return half4(c, col.a);
            }
            ENDHLSL
        }
    }
}
