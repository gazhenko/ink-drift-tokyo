using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>
    /// Pops comic/graffiti callouts on screen with a shouted Japanese voice line, a flash, camera shake and a
    /// post-FX pulse. Higher tiers are bigger, louder and longer.
    /// </summary>
    public class CalloutSystem : MonoBehaviour
    {
        public static CalloutSystem I { get; private set; }

        Canvas canvas;
        RectTransform root;
        Image flash;
        AudioSource voice, sfx;
        readonly List<GameObject> live = new List<GameObject>();
        float lastVoiceTime = -10f;
        int slot;
        public static event System.Action<float> OnDuck;   // music ducking request (seconds)

        static readonly Vector2[] Slots =
        {
            new Vector2(0f, 230f), new Vector2(-470f, 170f), new Vector2(470f, 170f), new Vector2(0f, 300f),
        };

        void Awake()
        {
            I = this;
            canvas = UIKit.MakeCanvas("CalloutCanvas", 50, transform);
            root = UIKit.Stretch("Root", canvas.transform);
            flash = UIKit.Img("Flash", root, null, new Color(1, 1, 1, 0), new Vector2(0.5f, 0.5f), Vector2.zero, Vector2.zero);
            var frt = flash.rectTransform; frt.anchorMin = Vector2.zero; frt.anchorMax = Vector2.one; frt.sizeDelta = Vector2.zero;

            voice = gameObject.AddComponent<AudioSource>();
            voice.playOnAwake = false; voice.spatialBlend = 0f; voice.priority = 0; voice.volume = 1f;
            sfx = gameObject.AddComponent<AudioSource>();
            sfx.playOnAwake = false; sfx.spatialBlend = 0f; sfx.priority = 1; sfx.volume = 0.8f;
        }

        public float VoiceVolume { get => voice.volume; set => voice.volume = value; }

        public void Show(CalloutId id, string scoreLine = null)
        {
            var lib = CalloutLibrary.Instance;
            var e = lib != null ? lib.Get(id) : null;
            int tierPower = TierPower(id);
            StartCoroutine(Animate(id, e, tierPower, scoreLine));

            // voice + sfx
            if (e != null && e.voices != null && e.voices.Length > 0)
            {
                if (Time.unscaledTime - lastVoiceTime > 0.35f || tierPower >= 4)
                {
                    voice.Stop();
                    voice.pitch = 1f;
                    voice.PlayOneShot(e.voices[Random.Range(0, e.voices.Length)], 1f);
                    lastVoiceTime = Time.unscaledTime;
                    OnDuck?.Invoke(1.2f);
                }
            }
            if (lib != null)
            {
                var pop = id == CalloutId.Fail ? lib.failSfx : (tierPower >= 4 ? lib.bigPopSfx : lib.popSfx);
                if (pop != null) sfx.PlayOneShot(pop, 0.9f);
            }

            if (ChaseCamera.Main != null) { ChaseCamera.Main.AddShake(0.15f + tierPower * 0.08f); ChaseCamera.Main.KickFov(2f + tierPower); }
            ComicPostFX.Pulse(0.25f + tierPower * 0.12f);
        }

        static int TierPower(CalloutId id) => id switch
        {
            CalloutId.Nice => 1, CalloutId.Good => 2, CalloutId.Great => 3, CalloutId.Awesome => 4, CalloutId.Insane => 5,
            CalloutId.Perfect => 6, CalloutId.God => 8, CalloutId.DriftKing => 7, CalloutId.NewRecord => 5,
            CalloutId.Go => 4, CalloutId.Goal => 5, CalloutId.Fail => 2, _ => 2
        };

        bool IsCountdown(CalloutId id) => id == CalloutId.Count3 || id == CalloutId.Count2 || id == CalloutId.Count1 || id == CalloutId.Go || id == CalloutId.Start;

        IEnumerator Animate(CalloutId id, CalloutLibrary.Entry e, int power, string scoreLine)
        {
            // Clear older callouts quickly so screen doesn't clutter.
            foreach (var g in live) if (g != null) StartCoroutine(Kill(g));
            live.Clear();

            Vector2 pos = IsCountdown(id) ? new Vector2(0f, 60f) : Slots[(slot++) % Slots.Length];
            if (power >= 6) pos = new Vector2(0f, 120f);
            float s = Mathf.Lerp(0.62f, 1.05f, power / 8f) * (e != null ? e.scale : 1f);
            if (IsCountdown(id)) s = 0.95f;

            var holder = UIKit.Rect("Callout_" + id, root, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), pos, new Vector2(1024, 512));
            live.Add(holder.gameObject);
            Color col = e != null ? e.color : Palette.Yellow;

            Image burst = null, text = null;
            TextMeshProUGUI fallbackJp = null, fallbackEn = null;
            var lib = CalloutLibrary.Instance;
            if (lib != null && lib.splats.Length > 0 && power >= 3)
            {
                var sp = UIKit.Img("Splat", holder, lib.splats[Random.Range(0, lib.splats.Length)], col.WithA(0.9f), new Vector2(0.5f, 0.5f), new Vector2(Random.Range(-60, 60), Random.Range(-30, 30)), new Vector2(1100, 700));
                sp.rectTransform.localRotation = Quaternion.Euler(0, 0, Random.Range(0, 360));
            }
            if (e != null && e.burst != null)
            {
                burst = UIKit.Img("Burst", holder, e.burst, e.tintBurst ? col : Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1024, 512));
            }
            if (e != null && e.text != null)
                text = UIKit.Img("Text", holder, e.text, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1024, 512));
            else if (e != null && e.composite != null)
                text = UIKit.Img("Composite", holder, e.composite, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1024, 512));
            else
            {
                // Fallback: TMP text in the comic style.
                var fs = FontSet.I;
                string jp = e != null ? e.jp : id.ToString();
                string en = e != null ? e.en : id.ToString();
                fallbackJp = UIKit.Text("JP", holder, jp, fs ? fs.jpHeavy : null, 150, col, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 30), new Vector2(1400, 220));
                UIKit.Inked(fallbackJp, 0.3f, Palette.Ink, new Vector2(0.9f, -0.9f));
                fallbackEn = UIKit.Text("EN", holder, en, fs ? fs.comic : null, 70, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -105), new Vector2(1000, 100));
                UIKit.Inked(fallbackEn, 0.3f);
            }
            TextMeshProUGUI score = null;
            if (!string.IsNullOrEmpty(scoreLine))
            {
                var fs = FontSet.I;
                score = UIKit.Text("Score", holder, scoreLine, fs ? fs.comic : null, 84, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -230), new Vector2(900, 110));
                UIKit.Inked(score, 0.32f, Palette.Ink, new Vector2(1f, -1f));
            }

            float rot0 = Random.Range(-28f, 28f);
            float rot1 = Random.Range(-7f, 7f);
            float dur = IsCountdown(id) ? 0.85f : Mathf.Lerp(1.15f, 2.1f, power / 8f);
            if (power >= 4) StartCoroutine(Flash(power >= 6 ? 0.55f : 0.3f));

            float t = 0f;
            while (t < dur && holder != null)
            {
                t += Time.unscaledDeltaTime;
                float pop = UIKit.EaseOutBack(t / 0.22f, 2.6f);
                float k = s * pop;
                float wobble = Mathf.Sin(t * 38f) * Mathf.Exp(-t * 6f) * 0.06f;
                holder.localScale = Vector3.one * (k + wobble);
                holder.localRotation = Quaternion.Euler(0, 0, Mathf.Lerp(rot0, rot1, UIKit.EaseOutCubic(t / 0.25f)));
                holder.anchoredPosition = pos + new Vector2(0f, t * 18f) + (power >= 5 ? Random.insideUnitCircle * Mathf.Exp(-t * 4f) * 10f : Vector2.zero);
                if (burst != null)
                {
                    burst.rectTransform.localRotation = Quaternion.Euler(0, 0, -t * 25f);
                    burst.rectTransform.localScale = Vector3.one * (1f + 0.05f * Mathf.Sin(t * 20f) + t * 0.08f);
                }
                if (score != null) score.rectTransform.localScale = Vector3.one * UIKit.EaseOutBack(Mathf.Clamp01((t - 0.12f) / 0.2f), 3f);
                yield return null;
            }
            if (holder != null) yield return Kill(holder.gameObject);
        }

        IEnumerator Kill(GameObject g)
        {
            if (g == null) yield break;
            var rt = (RectTransform)g.transform;
            var cg = g.GetOrAdd<CanvasGroup>();
            float t = 0f;
            Vector3 s0 = rt.localScale;
            while (t < 0.16f && g != null)
            {
                t += Time.unscaledDeltaTime;
                float k = t / 0.16f;
                rt.localScale = s0 * (1f + 0.45f * k);
                cg.alpha = 1f - k;
                yield return null;
            }
            if (g != null) Destroy(g);
        }

        IEnumerator Flash(float a)
        {
            float t = 0f;
            while (t < 0.18f)
            {
                t += Time.unscaledDeltaTime;
                flash.color = new Color(1f, 1f, 1f, a * (1f - t / 0.18f));
                yield return null;
            }
            flash.color = new Color(1, 1, 1, 0);
        }
    }
}
