using UnityEngine;

namespace InkDrift.Net
{
    /// <summary>
    /// Another player's car: a full CarController (so its wheels, smoke, skids and engine behave like any car) fed with
    /// that player's inputs, and steered toward where they report it is. The reported pose is extrapolated by its age
    /// (dead reckoning), then velocity and spin are blended toward it; a big gap (a reset) teleports.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class NetCarDriver : MonoBehaviour
    {
        public int playerId;
        public string playerName;
        CarController car;
        uint lastReset;
        bool placed;

        /// <summary>Race distance as the owner reported it, extrapolated to now (for positions).</summary>
        public float Progress { get; private set; }
        public bool Finished { get; private set; }

        void Awake() { car = GetComponent<CarController>(); car.assistLevel = 0; }

        void FixedUpdate()
        {
            var s = NetSession.I;
            var p = s != null ? s.Find(playerId) : null;
            if (p == null || !p.hasState) return;
            var st = p.state;
            var rb = car.Body;

            // inputs drive wheel spin, steering, smoke and sound
            car.input.steer = st.steer;
            car.input.throttle = st.throttle;
            car.input.brake = st.brake;
            car.input.handbrake = st.handbrake;
            car.frozen = false;

            float age = Mathf.Clamp((float)(s.HostTime - st.time), 0f, 0.5f);
            Vector3 targetPos = st.pos + st.vel * age;
            Quaternion targetRot = Quaternion.AngleAxis(st.angVel.magnitude * Mathf.Rad2Deg * age, st.angVel.sqrMagnitude > 1e-6f ? st.angVel.normalized : Vector3.up) * st.rot;
            Progress = st.progress + st.vel.magnitude * age;
            Finished = st.finished;

            Vector3 err = targetPos - rb.position;
            if (!placed || st.resetCount != lastReset || err.sqrMagnitude > 7f * 7f)
            {
                placed = true; lastReset = st.resetCount;
                rb.position = targetPos; rb.rotation = targetRot;
                transform.SetPositionAndRotation(targetPos, targetRot);
                rb.linearVelocity = st.vel; rb.angularVelocity = st.angVel;
                return;
            }
            // position: aim the velocity at the reported motion plus a pull that closes the gap in ~0.3 s
            Vector3 wantVel = st.vel + err * 3.5f;
            rb.linearVelocity = Vector3.Lerp(rb.linearVelocity, wantVel, 0.3f);
            // orientation: same idea with the spin
            Quaternion dq = targetRot * Quaternion.Inverse(rb.rotation);
            dq.ToAngleAxis(out float ang, out Vector3 axis);
            if (ang > 180f) ang -= 360f;
            Vector3 wantSpin = st.angVel + (float.IsNaN(axis.x) ? Vector3.zero : axis * (ang * Mathf.Deg2Rad * 5f));
            rb.angularVelocity = Vector3.Lerp(rb.angularVelocity, wantSpin, 0.3f);
        }
    }

    /// <summary>Sends the local player's car state to the session ~30 times a second.</summary>
    [RequireComponent(typeof(CarController))]
    public class NetCarSender : MonoBehaviour
    {
        CarController car;
        float timer;
        public uint resetCount;

        void Awake() { car = GetComponent<CarController>(); }

        void FixedUpdate()
        {
            var s = NetSession.I;
            if (s == null || !s.Connected) return;
            timer -= Time.fixedDeltaTime;
            if (timer > 0f) return;
            timer = 1f / 30f;
            var rm = RaceManager.I;
            var rb = car.Body;
            s.SendState(new CarSnapshot
            {
                pos = rb.position, rot = rb.rotation, vel = rb.linearVelocity, angVel = rb.angularVelocity,
                steer = car.input.steer, throttle = car.input.throttle, brake = car.input.brake, handbrake = car.input.handbrake,
                gear = car.Gear,
                progress = rm != null ? rm.PlayerProgress : 0f,
                lap = rm != null ? rm.PlayerLap : 1,
                finished = rm != null && rm.state == RaceManager.State.Finished,
                resetCount = resetCount,
            });
        }
    }
}
