using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    public static class Palette
    {
        public static readonly Color Ink = Hex("#0B0B12");
        public static readonly Color Paper = Hex("#FFF8E7");
        public static readonly Color Magenta = Hex("#FF2D7A");
        public static readonly Color Cyan = Hex("#00E5FF");
        public static readonly Color Yellow = Hex("#FFE600");
        public static readonly Color Red = Hex("#FF3B30");
        public static readonly Color Indigo = Hex("#1B1340");
        public static readonly Color Sakura = Hex("#FFB7D5");
        public static readonly Color Lime = Hex("#B6FF3B");

        public static Color Hex(string h) { ColorUtility.TryParseHtmlString(h, out var c); return c; }
        public static Color WithA(this Color c, float a) { c.a = a; return c; }
    }

    public static class UIKit
    {
        public static Canvas MakeCanvas(string name, int order, Transform parent = null)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            if (parent) go.transform.SetParent(parent, false);
            var c = go.GetComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            c.sortingOrder = order;
            var s = go.GetComponent<CanvasScaler>();
            s.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            s.referenceResolution = new Vector2(1920, 1080);
            s.matchWidthOrHeight = 0.5f;
            return c;
        }

        public static RectTransform Rect(string name, Transform parent, Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot, Vector2 pos, Vector2 size)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = anchorMin; rt.anchorMax = anchorMax; rt.pivot = pivot;
            rt.anchoredPosition = pos; rt.sizeDelta = size;
            return rt;
        }

        /// <summary>A single-line text box (TextMeshPro input field) on a paper panel.</summary>
        public static TMP_InputField InputField(string name, Transform parent, string value, string placeholder, Vector2 anchor, Vector2 pos, Vector2 size, int maxChars = 64)
        {
            var rt = Rect(name, parent, anchor, anchor, new Vector2(0.5f, 0.5f), pos, size);
            var panel = rt.gameObject.AddComponent<SlantPanel>();
            panel.color = Palette.Paper; panel.slant = 12; panel.border = 4; panel.borderColor = Palette.Ink;
            var area = Stretch("TextArea", rt);
            area.offsetMin = new Vector2(28, 6); area.offsetMax = new Vector2(-28, -6);
            area.gameObject.AddComponent<RectMask2D>();
            var fs = FontSet.I;
            TextMeshProUGUI Make(string n, string text, Color c)
            {
                var t = Stretch(n, area).gameObject.AddComponent<TextMeshProUGUI>();
                if (fs && fs.hud) t.font = fs.hud;
                t.text = text; t.fontSize = size.y * 0.46f; t.color = c;
                t.alignment = TextAlignmentOptions.MidlineLeft;
                t.textWrappingMode = TextWrappingModes.NoWrap;
                t.raycastTarget = false;
                return t;
            }
            var ph = Make("Placeholder", placeholder, Palette.Ink.WithA(0.4f));
            var txt = Make("Text", "", Palette.Ink);
            var field = rt.gameObject.AddComponent<TMP_InputField>();
            field.targetGraphic = panel;
            field.textViewport = area;
            field.textComponent = txt;
            field.placeholder = ph;
            field.characterLimit = maxChars;
            field.lineType = TMP_InputField.LineType.SingleLine;
            field.caretColor = Palette.Magenta;
            field.customCaretColor = true;
            field.selectionColor = Palette.Cyan.WithA(0.5f);
            if (fs && fs.hud) field.fontAsset = fs.hud;
            field.pointSize = size.y * 0.46f;
            field.text = value ?? "";
            return field;
        }

        public static RectTransform Stretch(string name, Transform parent)
        {
            var rt = Rect(name, parent, Vector2.zero, Vector2.one, new Vector2(0.5f, 0.5f), Vector2.zero, Vector2.zero);
            return rt;
        }

        public static Image Img(string name, Transform parent, Sprite sprite, Color color, Vector2 anchor, Vector2 pos, Vector2 size)
        {
            var rt = Rect(name, parent, anchor, anchor, new Vector2(0.5f, 0.5f), pos, size);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite; img.color = color; img.raycastTarget = false;
            if (sprite != null) img.preserveAspect = true;
            return img;
        }

        public static TextMeshProUGUI Text(string name, Transform parent, string text, TMP_FontAsset font, float size, Color color,
            TextAlignmentOptions align, Vector2 anchor, Vector2 pos, Vector2 box)
        {
            var rt = Rect(name, parent, anchor, anchor, new Vector2(0.5f, 0.5f), pos, box);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            if (font != null) t.font = font;
            t.text = text; t.fontSize = size; t.color = color; t.alignment = align;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            t.overflowMode = TextOverflowModes.Overflow;
            return t;
        }

        /// <summary>Thick ink outline + hard drop shadow via the TMP SDF material (instanced per text).</summary>
        public static void Inked(TextMeshProUGUI t, float outline = 0.28f, Color? outlineColor = null, Vector2? shadow = null)
        {
            var m = t.fontMaterial; // instanced
            m.EnableKeyword("OUTLINE_ON");
            m.SetFloat(ShaderUtilities.ID_OutlineWidth, outline);
            m.SetColor(ShaderUtilities.ID_OutlineColor, outlineColor ?? Palette.Ink);
            m.SetFloat(ShaderUtilities.ID_FaceDilate, outline * 0.6f);
            if (shadow.HasValue)
            {
                m.EnableKeyword("UNDERLAY_ON");
                m.SetColor(ShaderUtilities.ID_UnderlayColor, Palette.Ink);
                m.SetFloat(ShaderUtilities.ID_UnderlayOffsetX, shadow.Value.x);
                m.SetFloat(ShaderUtilities.ID_UnderlayOffsetY, shadow.Value.y);
                m.SetFloat(ShaderUtilities.ID_UnderlayDilate, outline * 1.6f);
                m.SetFloat(ShaderUtilities.ID_UnderlaySoftness, 0f);
            }
            t.fontMaterial = m;
        }

        public static UnityEngine.UI.Button Button(string name, Transform parent, string label, string jp, Vector2 anchor, Vector2 pos, Vector2 size, System.Action onClick, Color? fill = null)
        {
            var rt = Rect(name, parent, anchor, anchor, new Vector2(0.5f, 0.5f), pos, size);
            var panel = rt.gameObject.AddComponent<SlantPanel>();
            panel.color = fill ?? Palette.Paper;
            var btn = rt.gameObject.AddComponent<UnityEngine.UI.Button>();
            btn.targetGraphic = panel;
            var colors = btn.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1f, 0.85f, 0.2f);
            colors.selectedColor = new Color(1f, 0.85f, 0.2f);
            colors.pressedColor = new Color(1f, 0.4f, 0.6f);
            colors.colorMultiplier = 1f;
            colors.fadeDuration = 0.05f;
            btn.colors = colors;
            var fs = FontSet.I;
            var t = Text("Label", rt, label, fs ? fs.comic : null, size.y * 0.5f, Palette.Ink, TMPro.TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(8, jp != null ? 8 : 0), size);
            if (jp != null)
            {
                var j = Text("JP", rt, jp, fs ? fs.jpBody : null, size.y * 0.2f, Palette.Ink.WithA(0.75f), TMPro.TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(8, -size.y * 0.3f), size);
            }
            btn.onClick.AddListener(() => onClick?.Invoke());
            rt.gameObject.AddComponent<ButtonPunch>();
            return btn;
        }

        public static float EaseOutBack(float t, float s = 2.2f)
        {
            t = Mathf.Clamp01(t) - 1f;
            return t * t * ((s + 1f) * t + s) + 1f;
        }

        public static float EaseOutCubic(float t) { t = 1f - Mathf.Clamp01(t); return 1f - t * t * t; }
        public static float EaseInCubic(float t) { t = Mathf.Clamp01(t); return t * t * t; }
    }
}
