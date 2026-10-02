using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;
using UnityEngine.Rendering.RenderGraphModule;
using UnityEngine.Rendering.Universal;

namespace InkDrift
{
    /// <summary>
    /// Renders every visible material with an "InkMask" pass (InkDrift/Realistic: the driver) into _InkMaskTex after
    /// opaques, depth-tested against the scene so only the visible pixels are marked. The comic post pass reads it and
    /// leaves those pixels — and the outline around them — free of ink lines and paper grain.
    /// </summary>
    public class InkMaskFeature : ScriptableRendererFeature
    {
        class MaskPass : ScriptableRenderPass
        {
            static readonly ShaderTagId Tag = new ShaderTagId("InkMask");
            static readonly int MaskId = Shader.PropertyToID("_InkMaskTex");

            class PassData { public RendererListHandle list; }

            public MaskPass() { renderPassEvent = RenderPassEvent.AfterRenderingOpaques; }

            public override void RecordRenderGraph(RenderGraph rg, ContextContainer frame)
            {
                var res = frame.Get<UniversalResourceData>();
                var cam = frame.Get<UniversalCameraData>();
                var rendering = frame.Get<UniversalRenderingData>();
                var lights = frame.Get<UniversalLightData>();

                var desc = cam.cameraTargetDescriptor;
                desc.graphicsFormat = GraphicsFormat.R8_UNorm;
                desc.depthStencilFormat = GraphicsFormat.None;
                desc.depthBufferBits = 0;
                desc.msaaSamples = 1;
                var mask = UniversalRenderer.CreateRenderGraphTexture(rg, desc, "_InkMaskTex", true, FilterMode.Point);

                using (var b = rg.AddRasterRenderPass<PassData>("Ink Mask", out var data))
                {
                    var draw = RenderingUtils.CreateDrawingSettings(Tag, rendering, cam, lights, SortingCriteria.CommonOpaque);
                    var filter = new FilteringSettings(RenderQueueRange.opaque);
                    data.list = rg.CreateRendererList(new RendererListParams(rendering.cullResults, draw, filter));
                    b.UseRendererList(data.list);
                    b.SetRenderAttachment(mask, 0, AccessFlags.Write);
                    b.SetRenderAttachmentDepth(res.activeDepthTexture, AccessFlags.Read);
                    b.SetGlobalTextureAfterPass(mask, MaskId);
                    b.AllowGlobalStateModification(true);
                    b.SetRenderFunc((PassData d, RasterGraphContext ctx) => ctx.cmd.DrawRendererList(d.list));
                }
            }
        }

        MaskPass pass;

        public override void Create() { pass = new MaskPass(); }

        public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
        {
            var type = renderingData.cameraData.cameraType;
            if (type == CameraType.Preview || type == CameraType.Reflection) return;
            renderer.EnqueuePass(pass);
        }
    }
}
