using UnityEngine;

namespace InkDrift
{
    /// <summary>Sampled centerline of a closed circuit (written by the track generator). Used for laps, AI, resets, minimap.</summary>
    public class TrackPath : MonoBehaviour
    {
        public Vector3[] points = new Vector3[0];
        public Vector3[] rights = new Vector3[0];
        public float[] halfWidths = new float[0];
        public float[] dist = new float[0];
        public Vector3[] racingLine = new Vector3[0];
        public float[] targetSpeed = new float[0];   // m/s hint for AI
        public int[] lanesCount = new int[0];
        public float length;
        public float startDistance = 0f;
        public string trackId;

        public static TrackPath Active { get; private set; }

        void Awake() { Active = this; }
        void OnEnable() { Active = this; }

        public int Count => points.Length;

        public int Wrap(int i) { int n = points.Length; return ((i % n) + n) % n; }

        public int ClosestIndex(Vector3 p, int hint = -1, int window = 40)
        {
            int n = points.Length;
            if (n == 0) return 0;
            int best = 0; float bestD = float.MaxValue;
            if (hint >= 0)
            {
                for (int k = -window; k <= window; k++)
                {
                    int i = Wrap(hint + k);
                    float d = (points[i] - p).sqrMagnitude;
                    if (d < bestD) { bestD = d; best = i; }
                }
                if (bestD < 30f * 30f) return best;
            }
            for (int i = 0; i < n; i++)
            {
                float d = (points[i] - p).sqrMagnitude;
                if (d < bestD) { bestD = d; best = i; }
            }
            return best;
        }

        /// <summary>Continuous distance along the centerline for position p (projects onto the nearest segment).</summary>
        public float Project(Vector3 p, ref int hint, out float lateral)
        {
            int i = ClosestIndex(p, hint);
            hint = i;
            int j = Wrap(i + 1), h = Wrap(i - 1);
            // choose the segment (i->j or h->i) whose projection parameter is within range
            Vector3 a = points[i], b = points[j];
            Vector3 ab = b - a;
            float t = Vector3.Dot(p - a, ab) / Mathf.Max(1e-4f, ab.sqrMagnitude);
            float baseD = dist[i];
            if (t < 0f)
            {
                a = points[h]; b = points[i]; ab = b - a;
                t = Mathf.Clamp01(Vector3.Dot(p - a, ab) / Mathf.Max(1e-4f, ab.sqrMagnitude));
                baseD = dist[h];
                float segLen = ab.magnitude;
                lateral = Vector3.Dot(p - (a + ab * t), rights[h]);
                float d = baseD + segLen * t;
                return d >= length ? d - length : d;
            }
            t = Mathf.Clamp01(t);
            lateral = Vector3.Dot(p - (a + ab * t), rights[i]);
            float dd = baseD + ab.magnitude * t;
            return dd >= length ? dd - length : dd;
        }

        public int IndexAt(float d)
        {
            d = Mathf.Repeat(d, length);
            int lo = 0, hi = dist.Length - 1;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) >> 1;
                if (dist[mid] <= d) lo = mid; else hi = mid - 1;
            }
            return lo;
        }

        public Vector3 PointAt(float d, Vector3[] line = null)
        {
            line ??= points;
            d = Mathf.Repeat(d, length);
            int i = IndexAt(d);
            int j = Wrap(i + 1);
            float segStart = dist[i];
            float segEnd = j == 0 ? length : dist[j];
            float t = Mathf.InverseLerp(segStart, segEnd, d);
            return Vector3.Lerp(line[i], line[j], t);
        }

        public Vector3 TangentAt(float d)
        {
            int i = IndexAt(d);
            return (points[Wrap(i + 1)] - points[i]).normalized;
        }

        public Vector3 RightAt(float d) => rights[IndexAt(d)];
        public float HalfWidthAt(float d) => halfWidths[IndexAt(d)];
        public float TargetSpeedAt(float d) => targetSpeed.Length > 0 ? targetSpeed[IndexAt(d)] : 30f;

        /// <summary>Grid slot pose behind the start line: two columns, staggered.</summary>
        public Pose GridPose(int slot)
        {
            float back = 10f + slot * 7.5f;
            float d = Mathf.Repeat(startDistance - back, length);
            Vector3 p = PointAt(d);
            Vector3 fwd = TangentAt(d);
            Vector3 right = RightAt(d);
            float hw = HalfWidthAt(d);
            float side = (slot % 2 == 0 ? -1f : 1f) * Mathf.Min(2.4f, hw * 0.4f);
            p += right * side + Vector3.up * 0.3f;
            return new Pose(p, Quaternion.LookRotation(fwd, Vector3.up));
        }

        public Pose ResetPose(Vector3 near, ref int hint)
        {
            float d = Project(near, ref hint, out _);
            d = Mathf.Repeat(d - 4f, length);
            Vector3 p = PointAt(d) + Vector3.up * 0.6f;
            Vector3 fwd = TangentAt(d);
            return new Pose(p, Quaternion.LookRotation(fwd, Vector3.up));
        }

#if UNITY_EDITOR
        void OnDrawGizmosSelected()
        {
            if (points == null || points.Length < 2) return;
            Gizmos.color = Color.cyan;
            for (int i = 0; i < points.Length; i++) Gizmos.DrawLine(points[i], points[Wrap(i + 1)]);
            if (racingLine != null && racingLine.Length == points.Length)
            {
                Gizmos.color = Color.magenta;
                for (int i = 0; i < racingLine.Length; i++) Gizmos.DrawLine(racingLine[i], racingLine[Wrap(i + 1)]);
            }
        }
#endif
    }
}
