using TMPro;
using UnityEngine;

namespace InkDrift
{
    /// <summary>Font assets + small helpers to build comic-styled uGUI in code.</summary>
    [CreateAssetMenu(menuName = "InkDrift/Font Set")]
    public class FontSet : ScriptableObject
    {
        public TMP_FontAsset comic;      // Bangers
        public TMP_FontAsset hud;        // Chakra Petch Bold
        public TMP_FontAsset hudRegular; // Chakra Petch Regular
        public TMP_FontAsset jpHeavy;    // Dela Gothic One
        public TMP_FontAsset jpOutline;  // Rampart One
        public TMP_FontAsset jpGraffiti; // Reggae One
        public TMP_FontAsset jpBody;     // Noto Sans JP

        static FontSet _i;
        public static FontSet I => _i ??= Resources.Load<FontSet>("FontSet");
    }
}
