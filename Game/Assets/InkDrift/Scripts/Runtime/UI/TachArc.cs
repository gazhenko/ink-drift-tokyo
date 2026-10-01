using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>Segmented tachometer / gauge arc. value01 lights segments; redline01 turns segments red.</summary>
    public class TachArc : MaskableGraphic
    {
        public int segments = 36;
        public float startAngle = 210f;
        public float endAngle = -30f;
        public float innerRadius = 150f;
        public float outerRadius = 190f;
        public float gapDeg = 1.6f;
        public float value01;
        public float redline01 = 0.88f;
        public Color off = new Color(1f, 1f, 1f, 0.12f);
        public Color low = new Color(0f, 0.9f, 1f, 1f);
        public Color mid = new Color(1f, 0.9f, 0f, 1f);
        public Color high = new Color(1f, 0.23f, 0.19f, 1f);
        public Color ink = new Color(0.043f, 0.043f, 0.07f, 1f);
        public bool flash;

        public void SetValue(float v)
        {
            if (Mathf.Abs(v - value01) > 0.002f) { value01 = v; SetVerticesDirty(); }
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Vector2 c = GetPixelAdjustedRect().center;
            float span = endAngle - startAngle;
            // ink backing arc
            Arc(vh, c, innerRadius - 8f, outerRadius + 8f, startAngle + Mathf.Sign(span) * -2f, endAngle - Mathf.Sign(span) * -2f, ink, 48);
            for (int i = 0; i < segments; i++)
            {
                float t0 = (float)i / segments, t1 = (float)(i + 1) / segments;
                float a0 = startAngle + span * t0 + gapDeg * 0.5f * Mathf.Sign(span);
                float a1 = startAngle + span * t1 - gapDeg * 0.5f * Mathf.Sign(span);
                bool lit = t1 <= value01 + 1e-4f;
                Color col = t0 >= redline01 ? high : (t0 > 0.6f ? mid : low);
                if (!lit) col = t0 >= redline01 ? new Color(high.r, high.g, high.b, 0.25f) : off;
                if (flash && lit) col = Color.white;
                float outer = outerRadius + (t0 >= redline01 ? 6f : 0f);
                Arc(vh, c, innerRadius, outer, a0, a1, col, 3);
            }
        }

        static void Arc(VertexHelper vh, Vector2 c, float r0, float r1, float a0, float a1, Color col, int steps)
        {
            int start = vh.currentVertCount;
            for (int s = 0; s <= steps; s++)
            {
                float a = Mathf.Lerp(a0, a1, (float)s / steps) * Mathf.Deg2Rad;
                Vector2 d = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                vh.AddVert(c + d * r0, col, Vector2.zero);
                vh.AddVert(c + d * r1, col, Vector2.one);
            }
            for (int s = 0; s < steps; s++)
            {
                int i = start + s * 2;
                vh.AddTriangle(i, i + 1, i + 3);
                vh.AddTriangle(i, i + 3, i + 2);
            }
        }
    }
}
