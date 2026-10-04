using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Rain for tracks flagged TrackInfo.rain: streaks falling around the camera (stretched by their own and the
    /// camera's motion), splash rings on the ground, spray off every car's tyres, ripples on standing water
    /// (InkToon _WET, global _RainIntensity), heavier haze, a rain loop and the odd flash of lightning with thunder.
    /// </summary>
    public class RainWeather : MonoBehaviour
    {
        public float intensity = 1f;

        static readonly int RainIntensityId = Shader.PropertyToID("_RainIntensity");

        Camera cam;
        Transform emitter;
        ParticleSystem streaks, splashes;
        Material sprayMat;
        readonly Dictionary<CarController, ParticleSystem[]> spray = new Dictionary<CarController, ParticleSystem[]>();
        float scanTimer, groundY, groundTimer;
        Vector3 lastCamPos;
        Light sun;
        float sunBase, ambientBase, flash, nextFlash;
        RainAudio audioLoop;
        static readonly bool debugLog = CommandLine.Has("-rainDebug");
        float fogBase;

        public static void Ensure(float intensity)
        {
            var go = new GameObject("RainWeather");
            go.AddComponent<RainWeather>().intensity = intensity;
        }

        void Start()
        {
            int quality = QualitySettings.GetQualityLevel();
            float density = quality >= 2 ? 1f : quality == 1 ? 0.65f : 0.4f;
            var rainMat = Resources.Load<Material>("Materials/Rain");
            var ringMat = Resources.Load<Material>("Materials/RainRing");
            emitter = new GameObject("RainEmitter").transform;
            emitter.SetParent(transform, false);

            // ---- streaks: a 40 m box of drops above and around the camera, simulated in world space
            streaks = NewSystem("Streaks", emitter, rainMat);
            var main = streaks.main;
            main.loop = true; main.playOnAwake = true;
            main.startLifetime = 1.1f;
            main.startSpeed = 0f;
            main.startSize3D = false;
            main.startSize = new ParticleSystem.MinMaxCurve(0.035f, 0.055f);   // comic rain: bold streaks, not hairlines
            main.startColor = new Color(1f, 1f, 1f, 1f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.maxParticles = Mathf.RoundToInt(7000 * density);
            var em = streaks.emission; em.rateOverTime = 4200f * density * intensity;
            var sh = streaks.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(40f, 1f, 40f);
            sh.position = new Vector3(0f, 8f, 0f);
            var vel = streaks.velocityOverLifetime; vel.enabled = true; vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-0.6f, -0.2f);
            vel.y = new ParticleSystem.MinMaxCurve(-15f, -12.5f);
            vel.z = new ParticleSystem.MinMaxCurve(0.1f, 0.4f);
            var r = streaks.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.velocityScale = 0.075f;           // ~1 m streaks
            r.cameraVelocityScale = 0.02f;      // and slanted by our own speed through them
            r.lengthScale = 1f;
            r.sortMode = ParticleSystemSortMode.None;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;

            // ---- splash rings on the ground around the camera
            splashes = NewSystem("Splashes", emitter, ringMat);
            var sm = splashes.main;
            sm.loop = true;
            sm.startLifetime = new ParticleSystem.MinMaxCurve(0.18f, 0.3f);
            sm.startSpeed = 0f;
            sm.startSize = new ParticleSystem.MinMaxCurve(0.08f, 0.14f);
            sm.simulationSpace = ParticleSystemSimulationSpace.World;
            sm.maxParticles = Mathf.RoundToInt(1400 * density);
            var sem = splashes.emission; sem.rateOverTime = 2600f * density * intensity;
            var ssh = splashes.shape; ssh.shapeType = ParticleSystemShapeType.Box; ssh.scale = new Vector3(26f, 0.01f, 26f);
            var sol = splashes.sizeOverLifetime; sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0f, 0.3f), new Keyframe(1f, 2.6f)));
            var scol = splashes.colorOverLifetime; scol.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
            scol.color = g;
            var sr = splashes.GetComponent<ParticleSystemRenderer>();
            sr.renderMode = ParticleSystemRenderMode.HorizontalBillboard;
            sr.sortMode = ParticleSystemSortMode.None;
            sr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            sr.receiveShadows = false;

            // ---- spray off the tyres: the comic smoke puffs, made light and misty
            var smoke = Resources.Load<Material>("Materials/ToonSmoke");
            if (smoke != null)
            {
                sprayMat = new Material(smoke) { name = "RainSpray" };
                sprayMat.SetColor("_LitColor", new Color(0.86f, 0.9f, 1f));
                sprayMat.SetColor("_ShadeColor", new Color(0.55f, 0.6f, 0.75f));
            }

            Debug.Log($"[Rain] start: streaks mat={(rainMat ? rainMat.shader.name : "MISSING")} ring mat={(ringMat ? ringMat.shader.name : "MISSING")} spray={(sprayMat != null)} quality={quality} density={density}");
            Shader.SetGlobalFloat(RainIntensityId, intensity);
            fogBase = RenderSettings.fogDensity;
            RenderSettings.fogDensity = fogBase * (1f + 0.45f * intensity);
            foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None))
                if (l.type == LightType.Directional && (sun == null || l.intensity > sun.intensity)) sun = l;
            if (sun) sunBase = sun.intensity;
            ambientBase = RenderSettings.ambientIntensity;
            nextFlash = Time.time + Random.Range(14f, 26f);

            var a = new GameObject("RainAudio");
            a.transform.SetParent(transform, false);
            var src = a.AddComponent<AudioSource>();
            src.spatialBlend = 0f;
            src.volume = 0.32f * intensity;
            audioLoop = a.AddComponent<RainAudio>();
        }

        static ParticleSystem NewSystem(string name, Transform parent, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            // an empty system has empty bounds, so automatic culling would pause it before its first drop: always run
            var main = ps.main; main.cullingMode = ParticleSystemCullingMode.AlwaysSimulate;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.minParticleSize = 0f; r.maxParticleSize = 4f;
            return ps;
        }

        void OnDestroy()
        {
            Shader.SetGlobalFloat(RainIntensityId, 0f);
            if (fogBase > 0f) RenderSettings.fogDensity = fogBase;
            if (sun) sun.intensity = sunBase;
            RenderSettings.ambientIntensity = ambientBase;
        }

        void LateUpdate()
        {
            if (cam == null || !cam.isActiveAndEnabled) cam = Camera.main;
            if (cam == null) return;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            Vector3 cp = cam.transform.position;
            Vector3 cv = (cp - lastCamPos) / dt;
            if (cv.sqrMagnitude > 90f * 90f) cv = Vector3.zero;   // teleports, scene start
            lastCamPos = cp;

            // drops are emitted ahead of where the camera will be when they reach eye level
            Vector3 lead = Vector3.ProjectOnPlane(cv, Vector3.up) * 0.55f;
            emitter.position = new Vector3(cp.x, cp.y, cp.z) + lead;
            if (!streaks.isPlaying) { streaks.Play(); splashes.Play(); }

            // splashes sit on the ground under the camera (city streets are near enough flat over 26 m)
            groundTimer -= dt;
            if (groundTimer <= 0f)
            {
                groundTimer = 0.25f;
                if (Physics.Raycast(cp + lead + Vector3.up * 2f, Vector3.down, out var hit, 60f, ~((1 << CarController.CarLayer) | (1 << 2)), QueryTriggerInteraction.Ignore))
                    groundY = hit.point.y + 0.03f;
                else groundY = cp.y - 2f;
            }
            splashes.transform.position = new Vector3(cp.x + lead.x, groundY, cp.z + lead.z);

            UpdateSpray(dt);
            UpdateLightning(dt);
            if (debugLog && Time.frameCount % 120 == 0)
                Debug.Log($"[Rain] streaks {streaks.particleCount} (playing {streaks.isPlaying}) splashes {splashes.particleCount} spray systems {spray.Count} emitter {emitter.position} cam {cp}");
        }

        // ---------------------------------------------------------------- tyre spray
        void UpdateSpray(float dt)
        {
            scanTimer -= dt;
            if (scanTimer <= 0f && sprayMat != null)
            {
                scanTimer = 1f;
                foreach (var car in CarController.All)
                    if (car != null && !spray.ContainsKey(car)) spray[car] = MakeSpray(car);
            }
            foreach (var kv in spray)
            {
                var car = kv.Key;
                if (car == null) continue;
                for (int i = 0; i < 2; i++)
                {
                    var ps = kv.Value[i];
                    if (ps == null) continue;
                    var w = car.wheels[2 + i];
                    bool on = w != null && w.grounded && car.SpeedMs > 6f;
                    var em = ps.emission;
                    em.rateOverTime = on ? Mathf.Clamp(car.SpeedMs * 1.6f, 0f, 90f) * intensity : 0f;
                }
            }
        }

        ParticleSystem[] MakeSpray(CarController car)
        {
            var arr = new ParticleSystem[2];
            for (int i = 0; i < 2; i++)
            {
                var w = car.wheels[2 + i];
                if (w == null) continue;
                var ps = NewSystem("RainSpray" + i, car.transform, sprayMat);
                ps.transform.localPosition = new Vector3(w.localMount.x, 0.25f, w.localMount.z - car.spec.wheelRadius - 0.1f);
                ps.transform.localRotation = Quaternion.Euler(-12f, 180f, 0f);
                var m = ps.main;
                m.loop = true;
                m.startLifetime = new ParticleSystem.MinMaxCurve(0.35f, 0.7f);
                m.startSpeed = new ParticleSystem.MinMaxCurve(1.5f, 4f);
                m.startSize = new ParticleSystem.MinMaxCurve(0.5f, 1.1f);
                m.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
                m.startColor = new Color(1f, 1f, 1f, 0.55f);
                m.simulationSpace = ParticleSystemSimulationSpace.World;
                m.maxParticles = 120;
                m.gravityModifier = 0.15f;
                var em = ps.emission; em.rateOverTime = 0f;
                var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 18f; sh.radius = 0.15f;
                var sol = ps.sizeOverLifetime; sol.enabled = true;
                sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0f, 0.5f), new Keyframe(1f, 1.8f)));
                var col = ps.colorOverLifetime; col.enabled = true;
                var g = new Gradient();
                g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                          new[] { new GradientAlphaKey(0.55f, 0f), new GradientAlphaKey(0f, 1f) });
                col.color = g;
                var r = ps.GetComponent<ParticleSystemRenderer>();
                r.renderMode = ParticleSystemRenderMode.Billboard;
                r.sortMode = ParticleSystemSortMode.Distance;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                ps.Play();
                arr[i] = ps;
            }
            return arr;
        }

        // ---------------------------------------------------------------- lightning
        void UpdateLightning(float dt)
        {
            if (Time.time >= nextFlash)
            {
                nextFlash = Time.time + Random.Range(18f, 38f);
                StartCoroutine(Strike());
            }
            flash = Mathf.MoveTowards(flash, 0f, dt * 7f);
            if (sun) sun.intensity = sunBase + flash * 2.2f;
            RenderSettings.ambientIntensity = ambientBase * (1f + flash * 1.6f);
        }

        System.Collections.IEnumerator Strike()
        {
            flash = 1f;
            yield return new WaitForSeconds(Random.Range(0.08f, 0.14f));
            flash = 0.7f;
            yield return new WaitForSeconds(Random.Range(0.9f, 2.6f));
            if (audioLoop) audioLoop.Thunder();
        }
    }

    /// <summary>Procedural rain loop (dense filtered noise with a patter of drops) and thunder rumbles.</summary>
    [RequireComponent(typeof(AudioSource))]
    public class RainAudio : MonoBehaviour
    {
        System.Random rng = new System.Random(7);
        float lp1, lp2, hp, drop, rumble, rumbleLp, rumbleEnv;
        volatile float thunderRequest;
        int sr;

        void Start()
        {
            sr = AudioSettings.outputSampleRate;
            var a = GetComponent<AudioSource>();
            a.clip = AudioClip.Create("silence", sr, 1, sr, false);
            a.loop = true; a.Play();
        }

        public void Thunder() { thunderRequest = 1f; }

        void OnAudioFilterRead(float[] data, int channels)
        {
            if (thunderRequest > 0f) { rumbleEnv = 1f; thunderRequest = 0f; }
            float k1 = 0.35f, k2 = 0.08f;
            for (int i = 0; i < data.Length; i += channels)
            {
                float n = (float)(rng.NextDouble() * 2 - 1);
                // hiss: band-limited noise
                lp1 += (n - lp1) * k1;
                lp2 += (lp1 - lp2) * k2;
                float hiss = (lp1 - lp2) * 0.9f;
                // patter: sparse clicks of drops on the car and the road
                if (rng.NextDouble() < 0.0025) drop = (float)(rng.NextDouble() * 0.5 + 0.2);
                drop *= 0.985f;
                hp += (n * drop - hp) * 0.6f;
                // thunder: very low noise with a slow decaying envelope
                rumbleLp += (n - rumbleLp) * 0.004f;
                rumble = rumbleLp * 9f * rumbleEnv;
                rumbleEnv *= 0.99994f;
                float s = hiss * 0.55f + hp * 0.35f + rumble * 0.6f;
                for (int c = 0; c < channels; c++) data[i + c] += s;
            }
        }
    }
}
