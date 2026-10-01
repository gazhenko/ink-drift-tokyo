using UnityEngine;
using UnityEngine.EventSystems;

namespace InkDrift
{
    /// <summary>Selected buttons pop and wobble a little, comic style.</summary>
    public class ButtonPunch : MonoBehaviour, ISelectHandler, IDeselectHandler, IPointerEnterHandler
    {
        float punch;
        bool selected;

        public void OnSelect(BaseEventData e) { selected = true; punch = 1f; UISfx.Play("ui_move"); }
        public void OnDeselect(BaseEventData e) { selected = false; }
        public void OnPointerEnter(PointerEventData e) { EventSystem.current?.SetSelectedGameObject(gameObject); }

        void Update()
        {
            punch = Mathf.MoveTowards(punch, 0f, Time.unscaledDeltaTime * 5f);
            float s = (selected ? 1.08f : 1f) + punch * 0.12f;
            transform.localScale = Vector3.one * s;
            transform.localRotation = Quaternion.Euler(0, 0, Mathf.Sin(punch * 18f) * punch * 4f + (selected ? -1.5f : 0f));
        }
    }
}
