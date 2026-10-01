using UnityEngine;

namespace InkDrift
{
    /// <summary>Time-sliced realtime reflection probe refresh (one face per frame) so the paint reflects the live scene.</summary>
    [RequireComponent(typeof(ReflectionProbe))]
    public class ProbeUpdater : MonoBehaviour
    {
        ReflectionProbe probe;
        int renderId = -1;

        void Start()
        {
            probe = GetComponent<ReflectionProbe>();
            // only the player's car keeps a live probe (cost); rivals fall back to the scene reflection
            if (GetComponentInParent<PlayerDriver>() == null && !TrailerDirector.Requested) { probe.enabled = false; enabled = false; }
        }

        void Update()
        {
            if (probe == null) return;
            if (renderId < 0 || probe.IsFinishedRendering(renderId))
                renderId = probe.RenderProbe();
        }
    }
}
