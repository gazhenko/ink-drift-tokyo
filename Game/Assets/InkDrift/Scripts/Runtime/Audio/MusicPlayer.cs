using System.Collections;
using UnityEngine;

namespace InkDrift
{
    /// <summary>Persistent music player with crossfades and ducking under voice callouts.</summary>
    public class MusicPlayer : MonoBehaviour
    {
        static MusicPlayer _i;
        AudioSource a, b;
        bool useA = true;
        float duck = 1f, duckTimer;
        string current;
        bool fading;

        public static MusicPlayer Ensure()
        {
            if (_i != null) return _i;
            var g = new GameObject("MusicPlayer");
            DontDestroyOnLoad(g);
            _i = g.AddComponent<MusicPlayer>();
            _i.a = _i.Make(); _i.b = _i.Make();
            CalloutSystem.OnDuck += _i.Duck;
            return _i;
        }

        AudioSource Make()
        {
            var s = gameObject.AddComponent<AudioSource>();
            s.loop = true; s.spatialBlend = 0f; s.volume = 0f; s.priority = 2; s.ignoreListenerPause = false;
            return s;
        }

        void Duck(float seconds) { duckTimer = Mathf.Max(duckTimer, seconds); }

        public void PlayMenuMusic() => Play("Music/menu");
        public void PlayTrackMusic(string trackId) => Play("Music/" + trackId);

        public void Play(string resource)
        {
            if (current == resource) return;
            var clip = Resources.Load<AudioClip>(resource);
            if (clip == null) clip = Resources.Load<AudioClip>("Music/menu");
            if (clip == null) return;
            current = resource;
            StopAllCoroutines();
            StartCoroutine(Crossfade(clip));
        }

        IEnumerator Crossfade(AudioClip clip)
        {
            var from = useA ? a : b;
            var to = useA ? b : a;
            useA = !useA;
            fading = true;
            to.clip = clip; to.time = 0f; to.Play();
            float t = 0f;
            while (t < 1.5f)
            {
                t += Time.unscaledDeltaTime;
                float k = t / 1.5f;
                to.volume = k * Target; from.volume = (1f - k) * Target;
                yield return null;
            }
            from.Stop();
            fading = false;
        }

        float Target => GameSession.MusicVolume * 0.6f * duck;

        void Update()
        {
            duckTimer -= Time.unscaledDeltaTime;
            duck = Mathf.MoveTowards(duck, duckTimer > 0f ? 0.45f : 1f, Time.unscaledDeltaTime * 3f);
            var active = useA ? a : b;   // the last crossfade target
            if (!fading && active.isPlaying) active.volume = Mathf.MoveTowards(active.volume, Target, Time.unscaledDeltaTime);
        }
    }
}
