using TMPro;
using UnityEngine;

namespace InkDrift
{
    public class Blink : MonoBehaviour
    {
        TextMeshProUGUI t;
        void Awake() { t = GetComponent<TextMeshProUGUI>(); }
        void Update() { if (t) t.alpha = 0.55f + 0.45f * Mathf.Abs(Mathf.Sin(Time.unscaledTime * 2.4f)); }
    }
}
