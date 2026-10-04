using TMPro;
using UnityEngine;

namespace InkDrift
{
    /// <summary>A player's name floating above their car (online races), facing the camera and fading with distance.</summary>
    public class NameTag : MonoBehaviour
    {
        TextMeshPro text;

        public static void Attach(Transform car, string name)
        {
            var go = new GameObject("NameTag");
            go.transform.SetParent(car, false);
            go.transform.localPosition = new Vector3(0f, 2.1f, 0f);
            var tag = go.AddComponent<NameTag>();
            tag.text = go.AddComponent<TextMeshPro>();
            tag.text.text = name;
            tag.text.fontSize = 4.5f;
            tag.text.alignment = TextAlignmentOptions.Center;
            tag.text.color = Palette.Yellow;
            if (FontSet.I && FontSet.I.comic) tag.text.font = FontSet.I.comic;
            tag.text.outlineWidth = 0.25f;
            tag.text.outlineColor = Palette.Ink;
            tag.text.rectTransform.sizeDelta = new Vector2(12f, 2f);
        }

        void LateUpdate()
        {
            var cam = Camera.main;
            if (cam == null || text == null) return;
            Vector3 d = transform.position - cam.transform.position;
            transform.rotation = Quaternion.LookRotation(d, Vector3.up);
            float dist = d.magnitude;
            // bigger with distance so it stays readable, gone when very far or right on top of the camera
            transform.localScale = Vector3.one * Mathf.Clamp(dist / 14f, 0.6f, 3f);
            var c = text.color; c.a = Mathf.Clamp01((dist - 3f) / 3f) * Mathf.Clamp01((260f - dist) / 60f); text.color = c;
        }
    }
}
