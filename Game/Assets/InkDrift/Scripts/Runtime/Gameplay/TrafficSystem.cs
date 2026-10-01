using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Kinematic lane traffic that flows along the TrackPath in the racing direction around the player.
    /// Near misses award bonus points + a callout. Cars are recycled ahead of / behind the player.
    /// </summary>
    public class TrafficSystem : MonoBehaviour
    {
        public CarController player;
        public DriftScorer scorer;
        public int count = 14;
        public float spawnAhead = 320f;
        public float despawnBehind = 120f;
        public Vector2 speedRange = new Vector2(13f, 24f);
        public float laneWidth = 3.5f;
        public string[] prefabNames = { "Traffic_kei", "Traffic_taxi", "Traffic_van", "Traffic_truck" };

        class TCar
        {
            public Transform t; public Rigidbody rb; public float d, speed, lane, laneTarget; public bool nearMissed; public float bump;
        }

        readonly List<TCar> cars = new List<TCar>();
        int playerHint = -1;
        float nearMissCooldown;

        void Start()
        {
            for (int i = 0; i < count; i++) cars.Add(Spawn(i));
        }

        TCar Spawn(int i)
        {
            GameObject go = null;
            var prefab = Resources.Load<GameObject>("Traffic/" + prefabNames[i % prefabNames.Length]);
            if (prefab != null) go = Instantiate(prefab);
            else
            {
                go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                go.transform.localScale = new Vector3(1.75f, 1.6f, 4.2f);
                var m = Resources.Load<Material>("Materials/Toon_Traffic");
                if (m) go.GetComponent<Renderer>().sharedMaterial = m;
            }
            go.name = "Traffic_" + i;
            CarFactory.SetLayer(go.transform, CarController.CarLayer);
            var rb = go.GetOrAdd<Rigidbody>();
            rb.isKinematic = true;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            var c = new TCar { t = go.transform, rb = rb, speed = Random.Range(speedRange.x, speedRange.y) };
            go.SetActive(false);
            return c;
        }

        void Place(TCar c, float d)
        {
            var path = TrackPath.Active;
            c.d = Mathf.Repeat(d, path.length);
            float hw = path.HalfWidthAt(c.d);
            int lanes = Mathf.Max(1, Mathf.FloorToInt(hw * 2f / laneWidth));
            int lane = Random.Range(0, lanes);
            c.lane = c.laneTarget = -hw + laneWidth * (lane + 0.5f);
            c.speed = Random.Range(speedRange.x, speedRange.y);
            c.nearMissed = false;
            c.t.gameObject.SetActive(true);
            Pose(c, true);
        }

        void Pose(TCar c, bool teleport)
        {
            var path = TrackPath.Active;
            Vector3 p = path.PointAt(c.d) + path.RightAt(c.d) * c.lane;
            Vector3 f = path.TangentAt(c.d + 2f);
            // stick to the road surface
            if (Physics.Raycast(p + Vector3.up * 4f, Vector3.down, out var hit, 10f, ~(1 << CarController.CarLayer), QueryTriggerInteraction.Ignore))
                p = hit.point;
            var rot = Quaternion.LookRotation(f, Vector3.up);
            if (teleport) { c.t.SetPositionAndRotation(p, rot); c.rb.position = p; c.rb.rotation = rot; }
            else { c.rb.MovePosition(p); c.rb.MoveRotation(rot); }
        }

        void FixedUpdate()
        {
            var path = TrackPath.Active;
            if (path == null || player == null) return;
            float dt = Time.fixedDeltaTime;
            float pd = path.Project(player.transform.position, ref playerHint, out _);
            nearMissCooldown -= dt;

            foreach (var c in cars)
            {
                if (!c.t.gameObject.activeSelf)
                {
                    Place(c, pd + Random.Range(spawnAhead * 0.35f, spawnAhead));
                    continue;
                }
                float rel = Mathf.DeltaAngle(pd / path.length * 360f, c.d / path.length * 360f) / 360f * path.length;
                if (rel < -despawnBehind || rel > spawnAhead * 1.3f)
                {
                    Place(c, pd + Random.Range(spawnAhead * 0.7f, spawnAhead));
                    continue;
                }
                // simple car-following: slow for anything right ahead in-lane
                float speed = c.speed;
                foreach (var o in cars)
                {
                    if (o == c || !o.t.gameObject.activeSelf) continue;
                    float gap = Mathf.Repeat(o.d - c.d, path.length);
                    if (gap > 0f && gap < 18f && Mathf.Abs(o.lane - c.lane) < 1.6f) speed = Mathf.Min(speed, o.speed * (gap / 18f));
                }
                c.d = Mathf.Repeat(c.d + speed * dt, path.length);
                c.lane = Mathf.MoveTowards(c.lane, c.laneTarget, dt * 1.2f);
                Pose(c, false);

                // near miss: fast pass within ~1.3 m of the traffic car's side
                if (!c.nearMissed && nearMissCooldown <= 0f)
                {
                    Vector3 local = c.t.InverseTransformPoint(player.transform.position);
                    float relSpeed = player.SpeedMs - speed;
                    if (Mathf.Abs(local.z) < 2.6f && Mathf.Abs(local.x) < 3.0f && Mathf.Abs(local.x) > 1.6f && relSpeed > 8f)
                    {
                        c.nearMissed = true;
                        nearMissCooldown = 1.2f;
                        scorer?.AddBonus(600f);
                        CalloutSystem.I?.Show(CalloutId.NearMiss, "+600");
                    }
                }
            }
        }
    }
}
