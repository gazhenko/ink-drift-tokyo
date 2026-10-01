using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Real-time engine synthesizer (no samples): exhaust pulse train at the firing frequency with per-cylinder
    /// irregularity, two resonant exhaust formants, order harmonics, intake/induction noise, turbo whistle,
    /// blow-off flutter and overrun pops. Drives an AudioSource via OnAudioFilterRead.
    /// </summary>
    [RequireComponent(typeof(AudioSource))]
    public class EngineAudio : MonoBehaviour
    {
        public CarController car;
        [Range(0, 2)] public float volume = 0.9f;

        // shared state (written on main thread, read on audio thread)
        volatile float targetRpm = 900f, targetLoad, targetThrottle, targetBoost;
        volatile int popRequests, blowOffRequests;
        int cylinders = 4;
        float character = 0.5f;
        bool turbo;
        int sampleRate = 48000;

        // audio-thread state
        float rpm = 900f, load, throttle, boost;
        double phase;          // in firing events
        int cylIndex;
        float pulseEnv;
        readonly float[] cylAmp = new float[8];
        readonly float[] cylOffset = new float[8];
        Biquad f1L, f2L, lowL, f1R, f2R, lowR, intake, whistle, bovFilter;
        System.Random rng = new System.Random(1234);
        float popEnv, popTone, bovEnv, bovT;
        double harmPhase;
        float limiterEnv;

        struct Biquad
        {
            float a0, a1, a2, b1, b2, z1, z2;
            public void BandPass(float fc, float q, float sr)
            {
                float w = 2f * Mathf.PI * Mathf.Clamp(fc, 20f, sr * 0.45f) / sr;
                float alpha = Mathf.Sin(w) / (2f * q);
                float cs = Mathf.Cos(w);
                float n = 1f + alpha;
                a0 = alpha / n; a1 = 0f; a2 = -alpha / n; b1 = -2f * cs / n; b2 = (1f - alpha) / n;
            }
            public void LowPass(float fc, float q, float sr)
            {
                float w = 2f * Mathf.PI * Mathf.Clamp(fc, 20f, sr * 0.45f) / sr;
                float alpha = Mathf.Sin(w) / (2f * q);
                float cs = Mathf.Cos(w);
                float n = 1f + alpha;
                a0 = (1f - cs) * 0.5f / n; a1 = (1f - cs) / n; a2 = a0; b1 = -2f * cs / n; b2 = (1f - alpha) / n;
            }
            public float Process(float x)
            {
                float y = a0 * x + z1;
                z1 = a1 * x - b1 * y + z2;
                z2 = a2 * x - b2 * y;
                return y;
            }
        }

        void Start()
        {
            sampleRate = AudioSettings.outputSampleRate;
            var src = GetComponent<AudioSource>();
            src.clip = AudioClip.Create("engine_silence", sampleRate, 2, sampleRate, false);
            src.loop = true;
            src.playOnAwake = true;
            src.dopplerLevel = 0.3f;
            src.Play();
            Bind(car);
        }

        public void Bind(CarController c)
        {
            if (car != null) { car.OnBackfire -= Pop; car.OnBlowOff -= BlowOff; }
            car = c;
            if (car == null) return;
            cylinders = Mathf.Clamp(car.spec.cylinders, 3, 8);
            character = car.spec.exhaustCharacter;
            turbo = car.spec.turboBoostGain > 0f;
            var r = new System.Random(car.spec.id.GetHashCode());
            for (int i = 0; i < 8; i++)
            {
                cylAmp[i] = 0.75f + (float)r.NextDouble() * 0.5f;
                // Boxer-style unequal-length headers / odd-fire feel: larger timing offsets for low cylinder counts
                cylOffset[i] = ((float)r.NextDouble() - 0.5f) * (cylinders <= 4 ? 0.22f : 0.08f);
            }
            car.OnBackfire += Pop;
            car.OnBlowOff += BlowOff;
        }

        void OnDestroy() { if (car != null) { car.OnBackfire -= Pop; car.OnBlowOff -= BlowOff; } }

        void Pop() { popRequests++; }
        void BlowOff() { if (turbo) blowOffRequests++; }

        void Update()
        {
            if (car == null) return;
            targetRpm = car.EngineRpm;
            targetThrottle = car.Throttle;
            targetLoad = Mathf.Max(car.EngineLoad, car.Throttle * 0.6f);
            targetBoost = car.Boost;
        }

        float Noise() => (float)(rng.NextDouble() * 2.0 - 1.0);

        void OnAudioFilterRead(float[] data, int channels)
        {
            float sr = sampleRate;
            float tRpm = targetRpm, tLoad = targetLoad, tThr = targetThrottle, tBoost = targetBoost;
            int frames = data.Length / channels;

            // Per-block filter setup (formants move with rpm & throttle)
            float baseF = rpm / 60f * cylinders * 0.5f;
            float form1 = Mathf.Lerp(140f, 420f, character) + baseF * 0.9f;
            float form2 = Mathf.Lerp(900f, 2300f, character) + throttle * 600f;
            f1L.BandPass(form1, 1.6f, sr); f1R = f1L;
            f2L.BandPass(form2, 2.4f, sr); f2R = f2L;
            lowL.LowPass(Mathf.Lerp(1800f, 6500f, throttle * 0.6f + character * 0.4f), 0.7f, sr); lowR = lowL;
            intake.BandPass(1200f + rpm * 0.35f, 1.2f, sr);
            whistle.BandPass(2400f + boost * 5200f + rpm * 0.3f, 18f, sr);

            if (popRequests > 0) { popRequests = 0; popEnv = 1f; popTone = 60f + (float)rng.NextDouble() * 50f; }
            if (blowOffRequests > 0) { blowOffRequests = 0; bovEnv = 1f; bovT = 0f; }

            for (int i = 0; i < frames; i++)
            {
                // Smooth control params
                rpm += (tRpm - rpm) * 0.0025f;
                load += (tLoad - load) * 0.002f;
                throttle += (tThr - throttle) * 0.003f;
                boost += (tBoost - boost) * 0.002f;

                float fire = rpm / 60f * cylinders * 0.5f; // firing events / second
                double dPhase = fire / sr;
                phase += dPhase;
                if (phase >= 1.0 + cylOffset[cylIndex])
                {
                    phase -= 1.0 + cylOffset[cylIndex];
                    cylIndex = (cylIndex + 1) % cylinders;
                    pulseEnv = cylAmp[cylIndex] * (0.35f + load * 0.9f + throttle * 0.25f);
                }
                // exhaust pulse: sharp attack, fast decay (decay scales with firing period)
                float decay = Mathf.Exp(-fire * 3.2f / sr * 6f);
                pulseEnv *= decay;
                float pulse = pulseEnv * (1f + Noise() * (0.18f + character * 0.35f));

                // order harmonics give the tonal body
                harmPhase += fire / sr * 2.0 * Mathf.PI;
                if (harmPhase > 1e6) harmPhase -= 2.0 * Mathf.PI * 1e5;
                float hp = (float)harmPhase;
                float harm = Mathf.Sin(hp * 0.5f) * 0.35f + Mathf.Sin(hp) * 0.5f + Mathf.Sin(hp * 2f) * 0.18f * (0.5f + throttle);

                float exh = f1L.Process(pulse) * 2.2f + f2L.Process(pulse) * (0.6f + character * 0.8f) + harm * (0.18f + load * 0.25f) + pulse * 0.25f;
                float ind = intake.Process(Noise()) * (0.04f + throttle * 0.12f) * Mathf.Clamp01(rpm / 6000f);
                float s = exh + ind;

                // turbo whistle + blow-off flutter
                if (turbo)
                {
                    s += whistle.Process(Noise()) * boost * 0.9f;
                    if (bovEnv > 0.001f)
                    {
                        bovT += 1f / sr;
                        float flutter = 0.5f + 0.5f * Mathf.Sin(bovT * 2f * Mathf.PI * 22f);
                        s += Noise() * bovEnv * flutter * 0.55f;
                        bovEnv *= 1f - 3.2f / sr;
                    }
                }
                // overrun pop / backfire
                if (popEnv > 0.001f)
                {
                    float thump = Mathf.Sin(popEnv * popTone) * popEnv;
                    s += (Noise() * 0.9f + thump) * popEnv * 1.3f;
                    popEnv *= 1f - 40f / sr;
                }

                s = lowL.Process(s);
                // soft-clip for rasp
                s = (float)System.Math.Tanh(s * (1.2f + character * 1.5f)) * 0.65f * volume;

                for (int c = 0; c < channels; c++) data[i * channels + c] += s;
            }
        }
    }
}
