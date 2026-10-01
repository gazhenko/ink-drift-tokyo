using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>Heading-up minimap drawn from the TrackPath centerline, with car markers.</summary>
    public class MiniMap : MaskableGraphic
    {
        public TrackPath path;
        public Transform player;
        public readonly List<Transform> others = new List<Transform>();
        public float metersVisible = 520f;
        public float lineWidth = 9f;
        public Color roadColor = new Color(1f, 0.97f, 0.9f, 1f);
        public Color inkColor = new Color(0.043f, 0.043f, 0.07f, 1f);
        public Color playerColor = new Color(1f, 0.18f, 0.48f, 1f);
        public Color otherColor = new Color(0f, 0.9f, 1f, 1f);
        public Color startColor = new Color(1f, 0.9f, 0f, 1f);

        void Update() { SetVerticesDirty(); }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            if (path == null || path.Count < 2 || player == null) return;
            Rect r = GetPixelAdjustedRect();
            float scale = r.width / metersVisible;
            Vector3 center = player.position;
            float yaw = player.eulerAngles.y;
            Quaternion rot = Quaternion.Euler(0, 0, yaw);

            Vector2 Map(Vector3 w)
            {
                Vector2 p = new Vector2(w.x - center.x, w.z - center.z) * scale;
                return (Vector2)(rot * p) + r.center;
            }

            int n = path.Count;
            int step = Mathf.Max(1, n / 400);
            for (int pass = 0; pass < 2; pass++)
            {
                float w = pass == 0 ? lineWidth + 7f : lineWidth;
                Color col = pass == 0 ? inkColor : roadColor;
                for (int i = 0; i < n; i += step)
                {
                    int j = (i + step) % n;
                    Segment(vh, Map(path.points[i]), Map(path.points[j]), w, col, r);
                }
            }
            // start line
            Vector3 sp = path.PointAt(path.startDistance);
            Vector3 sr = path.RightAt(path.startDistance) * 9f;
            Segment(vh, Map(sp - sr), Map(sp + sr), 6f, startColor, r);

            foreach (var o in others) if (o) Dot(vh, Map(o.position), 9f, otherColor, r);
            // player arrow
            Vector2 pc = Map(player.position);
            int k = vh.currentVertCount;
            vh.AddVert(pc + new Vector2(0, 16), playerColor, Vector2.zero);
            vh.AddVert(pc + new Vector2(11, -11), playerColor, Vector2.zero);
            vh.AddVert(pc + new Vector2(-11, -11), playerColor, Vector2.zero);
            vh.AddTriangle(k, k + 1, k + 2);
        }

        static bool Inside(Rect r, Vector2 p) => r.Contains(p);

        static void Segment(VertexHelper vh, Vector2 a, Vector2 b, float w, Color c, Rect clip)
        {
            if (!Inside(clip, a) && !Inside(clip, b)) return;
            a = new Vector2(Mathf.Clamp(a.x, clip.xMin, clip.xMax), Mathf.Clamp(a.y, clip.yMin, clip.yMax));
            b = new Vector2(Mathf.Clamp(b.x, clip.xMin, clip.xMax), Mathf.Clamp(b.y, clip.yMin, clip.yMax));
            Vector2 d = (b - a);
            if (d.sqrMagnitude < 1e-4f) return;
            Vector2 nrm = new Vector2(-d.y, d.x).normalized * (w * 0.5f);
            Vector2 ext = d.normalized * (w * 0.5f);
            int i = vh.currentVertCount;
            vh.AddVert(a - nrm - ext, c, Vector2.zero);
            vh.AddVert(a + nrm - ext, c, Vector2.zero);
            vh.AddVert(b + nrm + ext, c, Vector2.zero);
            vh.AddVert(b - nrm + ext, c, Vector2.zero);
            vh.AddTriangle(i, i + 1, i + 2);
            vh.AddTriangle(i + 2, i + 3, i);
        }

        static void Dot(VertexHelper vh, Vector2 p, float rad, Color c, Rect clip)
        {
            if (!Inside(clip, p)) return;
            int i = vh.currentVertCount;
            vh.AddVert(p, c, Vector2.zero);
            for (int s = 0; s <= 12; s++)
            {
                float a = s / 12f * Mathf.PI * 2f;
                vh.AddVert(p + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * rad, c, Vector2.zero);
                if (s > 0) vh.AddTriangle(i, i + s, i + s + 1);
            }
        }
    }
}
