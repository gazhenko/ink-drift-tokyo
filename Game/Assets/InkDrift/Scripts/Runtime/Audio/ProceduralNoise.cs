using UnityEngine;

namespace InkDrift
{
    /// <summary>Fallback procedural loops for tire squeal and wind when no recorded clip is present.</summary>
    [RequireComponent(typeof(AudioSource))]
    public class ProceduralNoise : MonoBehaviour
    {
        public enum Mode { Squeal, Wind }
        public Mode mode;
        System.Random rng = new System.Random();
        float b0, b1, ph1, ph2, lp;
        int sr;

        void Start()
        {
            sr = AudioSettings.outputSampleRate;
            var a = GetComponent<AudioSource>();
            a.clip = AudioClip.Create("silence", sr, 1, sr, false);
            a.loop = true; a.Play();
        }

        void OnAudioFilterRead(float[] data, int channels)
        {
            for (int i = 0; i < data.Length; i += channels)
            {
                float n = (float)(rng.NextDouble() * 2 - 1);
                float s;
                if (mode == Mode.Squeal)
                {
                    // tonal squeal: two detuned resonances with noisy FM
                    ph1 += (950f + n * 120f) / sr; ph2 += (1430f + n * 160f) / sr;
                    if (ph1 > 1) ph1 -= 1; if (ph2 > 1) ph2 -= 1;
                    s = Mathf.Sin(ph1 * 6.2831f) * 0.35f + Mathf.Sin(ph2 * 6.2831f) * 0.2f + n * 0.08f;
                }
                else
                {
                    b0 = 0.995f * b0 + n * 0.05f; b1 = 0.97f * b1 + n * 0.03f;
                    s = b0 * 0.7f + b1 * 0.4f;
                }
                lp += (s - lp) * 0.5f;
                for (int c = 0; c < channels; c++) data[i + c] += lp * 0.5f;
            }
        }
    }
}
