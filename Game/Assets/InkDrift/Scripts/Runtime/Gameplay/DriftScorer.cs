using System;
using UnityEngine;

namespace InkDrift
{
    public enum CalloutId
    {
        Nice, Good, Great, Awesome, Insane, Perfect, God,
        Fail, BestLap, NewRecord, Start, Count3, Count2, Count1, Go, FinalLap, Goal, DriftKing, Ikee, NearMiss, Overtake
    }

    /// <summary>
    /// Drift chains: angle x speed x multiplier, multiplier grows with sustained drift and direction switches
    /// (manji / feint transitions), bonus for wall proximity. A wall hit loses the chain.
    /// </summary>
    public class DriftScorer : MonoBehaviour
    {
        public static readonly int[] TierThresholds = { 1500, 4000, 8000, 15000, 25000, 40000, 60000 };

        public CarController car;
        public float minSpeedKmh = 32f;
        public float minAngle = 11f;
        public float maxAngle = 118f;
        public float chainTimeout = 1.6f;
        public float impactFail = 2.2f;   // delta-v (m/s) that kills a chain

        public long TotalScore { get; private set; }
        public float ChainScore { get; private set; }
        public int Multiplier { get; private set; } = 1;
        public bool ChainActive { get; private set; }
        public bool Drifting { get; private set; }
        public float ChainTimeLeft01 => ChainActive ? Mathf.Clamp01(chainTimer / chainTimeout) : 0f;
        public float CurrentAngle { get; private set; }
        public bool CloseToWall { get; private set; }
        public long BestChain { get; private set; }
        public float LongestDrift { get; private set; }

        public event Action<CalloutId> OnTier;                 // mid-chain tier crossings
        public event Action<long, CalloutId?> OnChainBanked;   // final points, final tier (if any)
        public event Action<float> OnChainFailed;
        public event Action<int> OnMultiplier;
        public event Action OnTransition;

        float chainTimer, driftTime, multTimer, chainDuration;
        int lastDir;
        int announcedTier = -1;
        float lastImpactTime = -10f;

        public static int TierFor(float score)
        {
            int t = -1;
            for (int i = 0; i < TierThresholds.Length; i++) if (score >= TierThresholds[i]) t = i;
            return t;
        }

        void OnEnable() { if (car != null) car.OnImpact += HandleImpact; }
        void OnDisable() { if (car != null) car.OnImpact -= HandleImpact; }

        public void Bind(CarController c)
        {
            if (car != null) car.OnImpact -= HandleImpact;
            car = c;
            if (isActiveAndEnabled && car != null) car.OnImpact += HandleImpact;
        }

        public void ResetScore()
        {
            TotalScore = 0; ChainScore = 0; Multiplier = 1; ChainActive = false; announcedTier = -1;
            BestChain = 0; LongestDrift = 0;
        }

        void FixedUpdate()
        {
            if (car == null) return;
            float dt = Time.fixedDeltaTime;
            float angle = Mathf.Abs(car.DriftAngle);
            CurrentAngle = angle;
            float kmh = car.SpeedKmh;
            bool drifting = !car.frozen && car.GroundedWheels >= 3 && kmh > minSpeedKmh && angle > minAngle && angle < maxAngle && car.ForwardSpeed > 2f;
            Drifting = drifting;

            if (drifting)
            {
                int dir = car.DriftAngle > 0 ? 1 : -1;
                if (!ChainActive)
                {
                    ChainActive = true; ChainScore = 0; Multiplier = 1; announcedTier = -1; driftTime = 0; multTimer = 0; chainDuration = 0;
                    lastDir = dir;
                }
                else if (dir != lastDir && driftTime > 0.25f)
                {
                    BumpMultiplier();
                    OnTransition?.Invoke();
                    driftTime = 0f;
                }
                lastDir = dir;
                driftTime += dt;
                chainDuration += dt;
                multTimer += dt;
                if (multTimer > 3.0f) { multTimer = 0f; BumpMultiplier(); }

                float angleF = Mathf.Clamp01((angle - minAngle) / 28f);
                if (angle > 75f) angleF *= Mathf.Lerp(1f, 0.55f, (angle - 75f) / 43f);
                float speedF = Mathf.Pow(kmh / 100f, 1.15f);
                CloseToWall = ProbeWalls();
                float prox = CloseToWall ? 1.6f : 1f;
                ChainScore += 1000f * angleF * speedF * Multiplier * prox * dt;
                chainTimer = chainTimeout;
                LongestDrift = Mathf.Max(LongestDrift, chainDuration);

                int tier = TierFor(ChainScore);
                if (tier > announcedTier && tier >= 1)
                {
                    announcedTier = tier;
                    OnTier?.Invoke((CalloutId)tier);
                }
            }
            else if (ChainActive)
            {
                CloseToWall = false;
                chainTimer -= dt;
                if (chainTimer <= 0f) Bank();
            }
        }

        void BumpMultiplier()
        {
            if (Multiplier >= 10) return;
            Multiplier++;
            OnMultiplier?.Invoke(Multiplier);
        }

        void Bank()
        {
            ChainActive = false;
            long pts = (long)ChainScore;
            TotalScore += pts;
            BestChain = Math.Max(BestChain, pts);
            int tier = TierFor(pts);
            CalloutId? final = null;
            if (tier >= 0 && tier > announcedTier) final = (CalloutId)tier;
            else if (tier == 0 && announcedTier < 0) final = CalloutId.Nice;
            OnChainBanked?.Invoke(pts, final);
            ChainScore = 0; Multiplier = 1;
        }

        bool ProbeWalls()
        {
            // Rear-quarter feelers: being within ~1.6 m of a wall while sliding is the "clip" bonus.
            Transform t = car.transform;
            Vector3 origin = t.TransformPoint(0f, 0.6f, -1.6f);
            int mask = ~((1 << CarController.CarLayer) | (1 << 2));
            Vector3[] dirs = { -t.right, t.right, -t.forward, (-t.forward - t.right).normalized, (-t.forward + t.right).normalized };
            foreach (var d in dirs)
                if (Physics.Raycast(origin, d, out var hit, 2.4f, mask, QueryTriggerInteraction.Ignore) && Vector3.Dot(hit.normal, Vector3.up) < 0.5f)
                    return true;
            return false;
        }

        void HandleImpact(float dv, Vector3 p, Collision c)
        {
            if (dv < impactFail || Time.time - lastImpactTime < 0.8f) return;
            lastImpactTime = Time.time;
            if (!ChainActive || ChainScore < 300f) return;
            float lost = ChainScore;
            ChainActive = false; ChainScore = 0; Multiplier = 1; announcedTier = -1;
            OnChainFailed?.Invoke(lost);
        }

        /// <summary>External bonus (near-miss with traffic, etc.)</summary>
        public void AddBonus(float pts)
        {
            if (ChainActive) ChainScore += pts * Multiplier;
            else TotalScore += (long)pts;
        }
    }
}
