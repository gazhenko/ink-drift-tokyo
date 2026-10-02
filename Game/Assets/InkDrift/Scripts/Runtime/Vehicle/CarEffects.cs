using UnityEngine;

namespace InkDrift
{
    /// <summary>Tire smoke, skidmarks, backfire flames, sparks, lights (brake/reverse/head/underglow) and tire/wind audio.</summary>
    [RequireComponent(typeof(CarController))]
    public class CarEffects : MonoBehaviour
    {
        public Color underglow = new Color(1f, 0.18f, 0.48f);
        public bool headlightsOn;
        public Transform[] exhaustPoints = new Transform[0];
        readonly System.Collections.Generic.List<(Renderer r, int idx)> tailLights = new System.Collections.Generic.List<(Renderer, int)>();
        readonly System.Collections.Generic.List<(Renderer r, int idx)> headLights = new System.Collections.Generic.List<(Renderer, int)>();

        CarController car;
        ParticleSystem[] smoke = new ParticleSystem[4];
        ParticleSystem sparks, flames;
        Light underLight, flameLight;
        Light[] headSpots = new Light[0];
        int[] skidIds = { -1, -1, -1, -1 };
        AudioSource tireSrc, windSrc, impactSrc;
        float flameTimer;
        MaterialPropertyBlock mpb;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Start()
        {
            car = GetComponent<CarController>();
            mpb = new MaterialPropertyBlock();
            foreach (var r in GetComponentsInChildren<Renderer>())
            {
                if (r is ParticleSystemRenderer) continue;
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (mats[i] == null) continue;
                    if (mats[i].name.Contains("TailLight")) tailLights.Add((r, i));
                    else if (mats[i].name.Contains("HeadLight")) headLights.Add((r, i));
                }
            }
            var smokeMat = Resources.Load<Material>("Materials/ToonSmoke");
            var sparkMat = Resources.Load<Material>("Materials/Spark");
            var flameMat = Resources.Load<Material>("Materials/Flame");
            for (int i = 2; i < 4; i++) smoke[i] = MakeSmoke(i, smokeMat);
            if (car.spec.drive == DriveType.AWD) for (int i = 0; i < 2; i++) smoke[i] = MakeSmoke(i, smokeMat);
            sparks = MakeSparks(sparkMat);
            flames = MakeFlames(flameMat);

            var ul = new GameObject("Underglow");
            ul.transform.SetParent(transform, false);
            ul.transform.localPosition = new Vector3(0, 0.12f, car.spec.frontAxleZ - car.spec.wheelbase * 0.5f);
            underLight = ul.AddComponent<Light>();
            underLight.type = LightType.Point; underLight.range = 3.5f; underLight.intensity = 1.2f; underLight.color = underglow;
            underLight.shadows = LightShadows.None;

            var fl = new GameObject("FlameLight");
            fl.transform.SetParent(transform, false);
            fl.transform.localPosition = new Vector3(0, 0.4f, car.spec.frontAxleZ - car.spec.wheelbase - 1.2f);
            flameLight = fl.AddComponent<Light>();
            flameLight.type = LightType.Point; flameLight.range = 5f; flameLight.intensity = 0f; flameLight.color = new Color(1f, 0.55f, 0.15f);

            car.OnBackfire += Backfire;
            car.OnImpact += Impact;

            tireSrc = MakeAudioSource("Tires", Resources.Load<AudioClip>("Audio/tire_squeal_loop"), true);
            windSrc = MakeAudioSource("Wind", Resources.Load<AudioClip>("Audio/wind_loop"), true);
            impactSrc = MakeAudioSource("Impact", null, false);
            if (tireSrc.clip == null) tireSrc.gameObject.AddComponent<ProceduralNoise>().mode = ProceduralNoise.Mode.Squeal;
            if (windSrc.clip == null) windSrc.gameObject.AddComponent<ProceduralNoise>().mode = ProceduralNoise.Mode.Wind;
            SetHeadlights(headlightsOn);
        }

        void OnDestroy()
        {
            if (car != null) { car.OnBackfire -= Backfire; car.OnImpact -= Impact; }
        }

        public void SetHeadlights(bool on)
        {
            headlightsOn = on;
            if (on && headSpots.Length == 0)
            {
                headSpots = new Light[2];
                for (int i = 0; i < 2; i++)
                {
                    var g = new GameObject("HeadSpot" + i);
                    g.transform.SetParent(transform, false);
                    g.transform.localPosition = new Vector3(i == 0 ? -0.6f : 0.6f, 0.7f, car.spec.frontAxleZ + 0.8f);
                    g.transform.localRotation = Quaternion.Euler(6f, 0, 0);
                    var l = g.AddComponent<Light>();
                    l.type = LightType.Spot; l.range = 45f; l.spotAngle = 62f; l.innerSpotAngle = 30f; l.intensity = 40f;
                    l.color = new Color(0.92f, 0.96f, 1f);
                    l.shadows = LightShadows.None;
                    headSpots[i] = l;
                }
            }
            foreach (var l in headSpots) if (l) l.enabled = on;
            foreach (var (r, i) in headLights) if (r) SetEmission(r, i, on ? new Color(4f, 4.2f, 4.5f) : new Color(0.6f, 0.6f, 0.6f));
        }

        AudioSource MakeAudioSource(string n, AudioClip clip, bool loop)
        {
            var g = new GameObject(n);
            g.transform.SetParent(transform, false);
            var a = g.AddComponent<AudioSource>();
            a.clip = clip; a.loop = loop; a.spatialBlend = 0.6f; a.volume = 0f; a.dopplerLevel = 0.2f;
            if (loop && clip != null) a.Play();
            return a;
        }

        ParticleSystem MakeSmoke(int wheel, Material mat)
        {
            var g = new GameObject("Smoke" + wheel);
            g.transform.SetParent(transform, false);
            var ps = g.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true; main.playOnAwake = false;
            main.duration = 1f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(1.1f, 2.2f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.4f, 1.6f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.9f, 1.8f);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = 420;
            main.gravityModifier = -0.035f;
            main.startColor = new Color(1f, 1f, 1f, 0.95f);
            var em = ps.emission; em.rateOverTime = 0f;
            var shape = ps.shape; shape.shapeType = ParticleSystemShapeType.Sphere; shape.radius = 0.25f;
            var sol = ps.sizeOverLifetime; sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0, 0.45f), new Keyframe(0.3f, 1.25f), new Keyframe(1f, 2.6f)));
            var col = ps.colorOverLifetime; col.enabled = true;
            var grad = new Gradient();
            grad.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(new Color(0.9f, 0.92f, 1f), 1f) },
                         new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.85f, 0.06f), new GradientAlphaKey(0.55f, 0.45f), new GradientAlphaKey(0f, 1f) });
            col.color = grad;
            var rol = ps.rotationOverLifetime; rol.enabled = true; rol.z = new ParticleSystem.MinMaxCurve(-0.6f, 0.6f);
            var vel = ps.velocityOverLifetime; vel.enabled = true; vel.space = ParticleSystemSimulationSpace.World;
            vel.y = new ParticleSystem.MinMaxCurve(0.3f, 0.9f);
            vel.x = new ParticleSystem.MinMaxCurve(0f, 0f); vel.z = new ParticleSystem.MinMaxCurve(0f, 0f);
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.6f; noise.frequency = 0.35f; noise.scrollSpeed = 0.3f;
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.sortMode = ParticleSystemSortMode.Distance;
            r.minParticleSize = 0f; r.maxParticleSize = 4f;
            ps.Play();
            return ps;
        }

        ParticleSystem MakeSparks(Material mat)
        {
            var g = new GameObject("Sparks");
            g.transform.SetParent(transform, false);
            var ps = g.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main; main.loop = false; main.playOnAwake = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.25f, 0.6f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(4f, 14f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.09f);
            main.gravityModifier = 1.4f;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startColor = new Color(1f, 0.8f, 0.3f);
            var em = ps.emission; em.rateOverTime = 0;
            var shape = ps.shape; shape.shapeType = ParticleSystemShapeType.Hemisphere; shape.radius = 0.1f;
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat; r.renderMode = ParticleSystemRenderMode.Stretch; r.velocityScale = 0.06f; r.lengthScale = 1f;
            return ps;
        }

        ParticleSystem MakeFlames(Material mat)
        {
            var g = new GameObject("Flames");
            g.transform.SetParent(transform, false);
            g.transform.localPosition = exhaustPoints.Length > 0 && exhaustPoints[0] != null ? transform.InverseTransformPoint(exhaustPoints[0].position) : new Vector3(0.45f, 0.33f, car.spec.frontAxleZ - car.spec.wheelbase - 1.05f);
            g.transform.localRotation = Quaternion.Euler(0, 180, 0);
            var ps = g.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main; main.loop = false; main.playOnAwake = false;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.06f, 0.14f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(3f, 7f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.55f);
            main.simulationSpace = ParticleSystemSimulationSpace.Local;
            main.startColor = new Color(1f, 0.6f, 0.2f);
            var em = ps.emission; em.rateOverTime = 0;
            var shape = ps.shape; shape.shapeType = ParticleSystemShapeType.Cone; shape.angle = 8f; shape.radius = 0.03f;
            var sol = ps.sizeOverLifetime; sol.enabled = true; sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 1, 1, 0.2f));
            var r = ps.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat; r.renderMode = ParticleSystemRenderMode.Stretch; r.velocityScale = 0.05f; r.lengthScale = 1.8f;
            return ps;
        }

        void Backfire()
        {
            if (flames == null) return;
            flames.Emit(Random.Range(4, 9));
            flameTimer = 0.07f;
        }

        void Impact(float dv, Vector3 p, Collision c)
        {
            if (dv < 1.2f) return;
            sparks.transform.position = p;
            sparks.transform.rotation = Quaternion.LookRotation(c.contactCount > 0 ? c.GetContact(0).normal : Vector3.up);
            sparks.Emit(Mathf.RoundToInt(Mathf.Clamp(dv * 12f, 8, 90)));
            if (GetComponent<PlayerDriver>() != null)
            {
                if (ChaseCamera.Main != null) ChaseCamera.Main.AddShake(Mathf.Clamp(dv * 0.12f, 0.1f, 1f));
                GameInput.Impulse(Mathf.Clamp01(dv / 7f), Mathf.Clamp01(dv / 5f), Mathf.Lerp(0.12f, 0.35f, Mathf.Clamp01(dv / 10f)));
            }
            var clip = Resources.Load<AudioClip>("Audio/impact");
            if (clip != null) impactSrc.PlayOneShot(clip, Mathf.Clamp01(dv / 8f));
        }

        void Update()
        {
            float dt = Time.deltaTime;
            float maxSlide = 0f;
            for (int i = 0; i < 4; i++)
            {
                var w = car.wheels[i];
                if (w == null) continue;
                float slip = w.grounded ? w.slipSpeed : 0f;
                float smokeAmt = Mathf.Clamp01((slip - 3.5f) / 10f) * (w.offroad ? 0.4f : 1f);
                maxSlide = Mathf.Max(maxSlide, Mathf.Clamp01((slip - 2.5f) / 8f));
                var ps = smoke[i];
                if (ps != null)
                {
                    ps.transform.position = w.point + Vector3.up * 0.25f;
                    var em = ps.emission;
                    em.rateOverTime = smokeAmt * 38f * Mathf.Clamp01(car.SpeedMs / 6f + 0.25f);
                }
                // skidmarks
                if (Skidmarks.I != null)
                {
                    if (w.grounded && slip > 4f && !w.offroad)
                        skidIds[i] = Skidmarks.I.Add(w.point + w.normal * 0.02f, w.normal, Mathf.Clamp01((slip - 4f) / 8f), skidIds[i], car.spec.wheelWidth);
                    else skidIds[i] = -1;
                }
            }

            // brake / reverse lights
            float brake = car.Gear < 0 ? car.input.throttle : car.input.brake;
            Color tail = new Color(1f, 0.05f, 0.08f) * (headlightsOn ? 1.6f : 0.6f);
            if (brake > 0.05f || car.input.handbrake) tail = new Color(1f, 0.05f, 0.08f) * 6f;
            foreach (var (r, i) in tailLights) if (r) SetEmission(r, i, tail);

            // underglow pulses with the bass of the engine
            underLight.color = underglow;
            underLight.intensity = 1.1f + Mathf.Sin(Time.time * 3f) * 0.12f;

            flameTimer -= dt;
            flameLight.intensity = flameTimer > 0f ? 3f : Mathf.MoveTowards(flameLight.intensity, 0f, dt * 80f);

            if (tireSrc != null)
            {
                tireSrc.volume = Mathf.Lerp(tireSrc.volume, maxSlide * 0.75f, 1f - Mathf.Exp(-12f * dt));
                tireSrc.pitch = 0.85f + maxSlide * 0.25f + car.SpeedMs * 0.002f;
            }
            if (windSrc != null)
            {
                windSrc.volume = Mathf.Clamp01((car.SpeedMs - 8f) / 60f) * 0.45f;
                windSrc.pitch = 0.8f + car.SpeedMs * 0.006f;
            }
        }

        void SetEmission(Renderer r, int index, Color c)
        {
            r.GetPropertyBlock(mpb, index);
            mpb.SetColor(EmissionId, c);
            r.SetPropertyBlock(mpb, index);
        }
    }
}
