using UnityEngine;

namespace InkDrift
{
    public static class Extensions
    {
        /// <summary>Unity-null-safe "get or add" (avoid ?? on UnityEngine.Object).</summary>
        public static T GetOrAdd<T>(this GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            return c != null ? c : go.AddComponent<T>();
        }
    }
}
