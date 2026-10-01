using UnityEngine;

namespace InkDrift
{
    /// <summary>One-shot 2D UI sounds loaded from Resources/Audio/UI.</summary>
    public static class UISfx
    {
        static AudioSource src;

        public static void Play(string name, float vol = 0.7f)
        {
            var clip = Resources.Load<AudioClip>("Audio/UI/" + name);
            if (clip == null) return;
            if (src == null)
            {
                var g = new GameObject("UISfx");
                Object.DontDestroyOnLoad(g);
                src = g.AddComponent<AudioSource>();
                src.spatialBlend = 0f; src.ignoreListenerPause = true;
            }
            src.PlayOneShot(clip, vol);
        }
    }
}
