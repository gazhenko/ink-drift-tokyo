using UnityEngine;

namespace InkDrift
{
    public static class CarFactory
    {
        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");

        /// <summary>Instantiate a car prefab (Resources/Cars/&lt;prefabName&gt;) or a primitive stand-in, configure physics, paint and driver.</summary>
        public static CarController Spawn(CarSpec spec, int paintIndex, Pose pose, bool player, bool night)
        {
            var prefab = Resources.Load<GameObject>("Cars/" + spec.prefabName);
            GameObject go = prefab != null ? Object.Instantiate(prefab, pose.position, pose.rotation) : BuildStandIn(spec, pose);
            go.name = (player ? "Player_" : "Rival_") + spec.id;
            SetLayer(go.transform, CarController.CarLayer);

            var car = go.GetOrAdd<CarController>();
            car.spec = spec.Clone();
            car.Init();
            car.assistLevel = player ? GameSession.AssistLevel : 0;
            car.transmission = player ? GameSession.Gearbox : Transmission.Automatic;

            Color paint = spec.paints.Length > 0 ? spec.paints[Mathf.Clamp(paintIndex, 0, spec.paints.Length - 1)] : Color.white;
            ApplyPaint(go, paint);

            var fx = go.GetOrAdd<CarEffects>();
            fx.headlightsOn = night;
            fx.underglow = UnderglowFor(paint);

            var src = go.GetOrAdd<AudioSource>();
            src.spatialBlend = player ? 0.35f : 1f;
            src.minDistance = 6f; src.maxDistance = 140f; src.rolloffMode = AudioRolloffMode.Linear;
            var eng = go.GetOrAdd<EngineAudio>();
            eng.car = car;
            eng.volume = player ? 0.85f : 0.7f;

            if (player) go.AddComponent<PlayerDriver>();
            else go.AddComponent<AIDriver>();
            return car;
        }

        /// <summary>Static showroom car: no physics or drivers, wheels resting at their rest pose.</summary>
        public static GameObject SpawnDisplay(CarSpec spec, int paintIndex, Transform parent)
        {
            var prefab = Resources.Load<GameObject>("Cars/" + spec.prefabName);
            GameObject go = prefab != null ? Object.Instantiate(prefab, parent) : BuildStandIn(spec, new Pose(parent.position, parent.rotation));
            go.transform.SetParent(parent, false);
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            var car = go.GetComponent<CarController>();
            if (car != null)
            {
                car.spec = spec.Clone();
                car.Init();
                for (int i = 0; i < 4; i++)
                    if (car.wheelVisuals[i] != null)
                    {
                        var w = car.wheels[i];
                        car.wheelVisuals[i].localPosition = new Vector3(w.localMount.x, spec.wheelRadius, w.localMount.z);
                        car.wheelVisuals[i].localRotation = Quaternion.Euler(0, i < 2 ? 12f : 0f, 0);
                    }
            }
            // Immediate + reverse order: dependents (CarEffects/EngineAudio [RequireComponent]) must go before
            // CarController / Rigidbody / AudioSource, otherwise Unity refuses the removal and the car stays physical.
            var mbs = go.GetComponents<MonoBehaviour>();
            for (int i = mbs.Length - 1; i >= 0; i--) Object.DestroyImmediate(mbs[i]);
            var rb = go.GetComponent<Rigidbody>(); if (rb) Object.DestroyImmediate(rb);
            foreach (var a in go.GetComponentsInChildren<AudioSource>()) Object.DestroyImmediate(a);
            Color paint = spec.paints.Length > 0 ? spec.paints[Mathf.Clamp(paintIndex, 0, spec.paints.Length - 1)] : Color.white;
            ApplyPaint(go, paint);
            return go;
        }

        public static void ApplyPaint(GameObject go, Color paint)
        {
            var mpb = new MaterialPropertyBlock();
            foreach (var r in go.GetComponentsInChildren<Renderer>())
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (mats[i] == null) continue;
                    string n = mats[i].name;
                    if (n.Contains("Paint") && !n.Contains("Accent"))
                    {
                        r.GetPropertyBlock(mpb, i);
                        mpb.SetColor(BaseColorId, paint);
                        r.SetPropertyBlock(mpb, i);
                    }
                }
            }
        }

        static Color UnderglowFor(Color paint)
        {
            Color.RGBToHSV(paint, out float h, out float s, out float v);
            if (s < 0.25f) return new Color(0f, 0.9f, 1f);   // white/black cars get cyan
            return Color.HSVToRGB(Mathf.Repeat(h + 0.5f, 1f), 1f, 1f);
        }

        public static void SetLayer(Transform t, int layer)
        {
            t.gameObject.layer = layer;
            foreach (Transform c in t) SetLayer(c, layer);
        }

        /// <summary>Primitive car used before real models are imported (and as a fallback).</summary>
        static GameObject BuildStandIn(CarSpec spec, Pose pose)
        {
            var root = new GameObject("StandIn_" + spec.id);
            root.transform.SetPositionAndRotation(pose.position, pose.rotation);
            var rb = root.AddComponent<Rigidbody>();
            var toon = Resources.Load<Material>("Materials/CarPaint_Default");
            var dark = Resources.Load<Material>("Materials/Toon_DarkTrim");
            var tire = Resources.Load<Material>("Materials/Toon_Tire");

            float len = spec.wheelbase + 1.75f;
            float wid = Mathf.Max(spec.trackFront, spec.trackRear) + 0.28f;
            float zc = spec.frontAxleZ - spec.wheelbase * 0.5f;
            var body = Box(root.transform, "Body", new Vector3(0, 0.62f, zc), new Vector3(wid, 0.55f, len), toon);
            var cabin = Box(root.transform, "Cabin", new Vector3(0, 1.08f, zc - 0.25f), new Vector3(wid * 0.82f, 0.45f, len * 0.45f), dark);
            var wing = Box(root.transform, "Wing", new Vector3(0, 1.25f, zc - len * 0.46f), new Vector3(wid * 0.95f, 0.05f, 0.32f), dark);
            Object.Destroy(cabin.GetComponent<Collider>());
            Object.Destroy(wing.GetComponent<Collider>());
            var col = body.GetComponent<BoxCollider>();
            col.size = new Vector3(1f, 1.4f, 1f);
            col.center = new Vector3(0f, 0.1f, 0f);

            var car = root.AddComponent<CarController>();
            car.spec = spec.Clone();
            car.Init();
            for (int i = 0; i < 4; i++)
            {
                var w = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Object.Destroy(w.GetComponent<Collider>());
                var pivot = new GameObject(new[] { "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR" }[i]).transform;
                pivot.SetParent(root.transform, false);
                w.transform.SetParent(pivot, false);
                w.transform.localRotation = Quaternion.Euler(0, 0, 90);
                w.transform.localScale = new Vector3(spec.wheelRadius * 2f, spec.wheelWidth * 0.5f, spec.wheelRadius * 2f);
                if (tire) w.GetComponent<Renderer>().sharedMaterial = tire;
                car.wheelVisuals[i] = pivot;
                pivot.localPosition = car.wheels[i].localMount - Vector3.up * spec.restLength;
            }
            return root;
        }

        static GameObject Box(Transform parent, string name, Vector3 pos, Vector3 size, Material m)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
            g.name = name;
            g.transform.SetParent(parent, false);
            g.transform.localPosition = pos;
            g.transform.localScale = size;
            if (m) g.GetComponent<Renderer>().sharedMaterial = m;
            return g;
        }
    }
}
