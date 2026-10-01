using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>Parallelogram comic panel with a thick ink border and a hard offset shadow.</summary>
    public class SlantPanel : MaskableGraphic
    {
        public float slant = 24f;
        public float border = 6f;
        public Color borderColor = new Color(0.043f, 0.043f, 0.07f, 1f);
        public Vector2 shadowOffset = new Vector2(10f, -10f);
        public Color shadowColor = new Color(0.043f, 0.043f, 0.07f, 0.85f);

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            if (shadowOffset != Vector2.zero) Quad(vh, r, slant, shadowOffset, 0f, shadowColor);
            Quad(vh, r, slant, Vector2.zero, 0f, borderColor);
            Quad(vh, r, slant, Vector2.zero, border, color);
        }

        static void Quad(VertexHelper vh, Rect r, float s, Vector2 off, float inset, Color c)
        {
            int i = vh.currentVertCount;
            float x0 = r.xMin + inset, x1 = r.xMax - inset, y0 = r.yMin + inset, y1 = r.yMax - inset;
            float k = s * (y1 - y0) / Mathf.Max(1f, r.height);
            vh.AddVert(new Vector3(x0 + off.x, y0 + off.y), c, Vector2.zero);
            vh.AddVert(new Vector3(x0 + k + off.x, y1 + off.y), c, Vector2.up);
            vh.AddVert(new Vector3(x1 + k + off.x, y1 + off.y), c, Vector2.one);
            vh.AddVert(new Vector3(x1 + off.x, y0 + off.y), c, Vector2.right);
            vh.AddTriangle(i, i + 1, i + 2);
            vh.AddTriangle(i + 2, i + 3, i);
        }
    }
}
