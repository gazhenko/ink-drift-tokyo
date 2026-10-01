using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;

namespace InkDrift
{
    /// <summary>
    /// Scripted vehicle-dynamics checks on the flat test pad (scene TestPad, `-physicsTest out.txt [-car id]`).
    /// Reports: 0-100 km/h, top speed in 2nd, skidpad lateral g, handbrake drift initiation, sustained drift with a
    /// closed-loop counter-steer controller, clutch-kick yaw response, spin-outs.
    /// </summary>
    public class PhysicsTest : MonoBehaviour
    {
        readonly StringBuilder report = new StringBuilder();
        CarController car;

        void Start()
        {
            if (!CommandLine.Has("-physicsTest")) { enabled = false; return; }
            Time.fixedDeltaTime = 1f / 120f;
            StartCoroutine(RunAll());
        }

        CarController Spawn(string id)
        {
            if (car) Destroy(car.gameObject);
            var spec = CarCatalog.Get(id);
            car = CarFactory.Spawn(spec, 0, new Pose(new Vector3(0, 0.5f, -250f), Quaternion.identity), false, false);
            var ai = car.GetComponent<AIDriver>(); if (ai) Destroy(ai);
            var fx = car.GetComponent<CarEffects>(); if (fx) fx.enabled = true;
            car.assistLevel = (int)CommandLine.GetFloat("-assist", 0);
            car.transmission = Transmission.Automatic;
            var cam = Camera.main;
            if (cam) { var ch = cam.gameObject.GetOrAdd<ChaseCamera>(); ch.target = car; ch.Snap(); }
            return car;
        }

        void Set(float steer, float thr, float brake, bool hb, float clutch = 0f)
        {
            car.input.steer = steer; car.input.throttle = thr; car.input.brake = brake; car.input.handbrake = hb; car.input.clutch = clutch;
        }

        IEnumerator RunAll()
        {
            yield return new WaitForSeconds(0.5f);
            string ids = CommandLine.Get("-car", "hachi,kaiju,zenkai,raijin,tsubame");
            foreach (var id in ids.Split(','))
            {
                report.AppendLine($"=== {id} ===");
                yield return Accel(id);
                yield return Skidpad(id);
                yield return DriftHold(id, false);
                yield return DriftHold(id, true);
            }
            string outPath = CommandLine.Get("-physicsTest", "physics_report.txt");
            File.WriteAllText(outPath, report.ToString());
            Debug.Log(report.ToString());
            Application.Quit();
        }

        IEnumerator Settle()
        {
            Set(0, 0, 1, true);
            for (int i = 0; i < 60; i++) yield return new WaitForFixedUpdate();
        }

        IEnumerator Accel(string id)
        {
            Spawn(id);
            yield return Settle();
            float t = 0f, t100 = -1f, t60 = -1f;
            Set(0, 1, 0, false);
            while (t < 14f)
            {
                yield return new WaitForFixedUpdate();
                t += Time.fixedDeltaTime;
                float k = car.ForwardSpeed * 3.6f;
                if (t60 < 0 && k >= 60) t60 = t;
                if (t100 < 0 && k >= 100) t100 = t;
                // keep straight
                car.input.steer = Mathf.Clamp(-car.YawRate * 0.8f - car.transform.position.x * 0.02f, -0.3f, 0.3f);
            }
            report.AppendLine($"accel: 0-60 {t60:0.00}s  0-100 {t100:0.00}s  speed@14s {car.ForwardSpeed * 3.6f:0} km/h gear {car.Gear}");
        }

        IEnumerator Skidpad(string id)
        {
            Spawn(id);
            yield return Settle();
            // accelerate to 60 km/h, then hold a constant-radius circle with speed control, measure lateral accel
            float t = 0f, maxLat = 0f, spinT = 0f;
            Set(0, 0.6f, 0, false);
            while (car.ForwardSpeed < 16.7f && t < 8f) { yield return new WaitForFixedUpdate(); t += Time.fixedDeltaTime; }
            float target = 16.7f;
            t = 0f;
            while (t < 10f)
            {
                yield return new WaitForFixedUpdate();
                t += Time.fixedDeltaTime;
                target += Time.fixedDeltaTime * 0.6f;   // slowly increase speed until grip runs out
                float err = target - car.ForwardSpeed;
                Set(0.55f, Mathf.Clamp01(0.3f + err * 0.3f), Mathf.Clamp01(-err * 0.2f), false);
                Vector3 lv = car.transform.InverseTransformDirection(car.Body.linearVelocity);
                float lat = Mathf.Abs(car.YawRate * lv.z) / 9.81f;
                if (Mathf.Abs(car.DriftAngle) < 12f) maxLat = Mathf.Max(maxLat, lat);
                if (Mathf.Abs(car.DriftAngle) > 90f) spinT += Time.fixedDeltaTime;
            }
            report.AppendLine($"skidpad: max lateral {maxLat:0.00} g (grip regime), spun {(spinT > 0.2f ? "YES" : "no")}");
        }

        /// <summary>Handbrake entry at ~70 km/h, then hold a target drift angle using throttle + counter-steer feedback.</summary>
        IEnumerator DriftHold(string id, bool clutchKick)
        {
            Spawn(id);
            yield return Settle();
            Set(0, 1, 0, false);
            float t = 0f;
            while (car.ForwardSpeed < 19.5f && t < 10f) { yield return new WaitForFixedUpdate(); t += Time.fixedDeltaTime; car.input.steer = Mathf.Clamp(-car.YawRate * 0.8f, -0.3f, 0.3f); }
            // initiation
            t = 0f;
            float maxAngle = 0f;
            while (t < 0.55f)
            {
                yield return new WaitForFixedUpdate(); t += Time.fixedDeltaTime;
                if (clutchKick)
                {
                    // clutch in + rev, release at 0.3 s while steering in
                    bool held = t < 0.3f;
                    Set(-0.85f, 1f, 0, false, held ? 1f : 0f);
                }
                else Set(-0.9f, 0.4f, 0, t < 0.35f);
                maxAngle = Mathf.Max(maxAngle, Mathf.Abs(car.DriftAngle));
            }
            float initAngle = Mathf.Abs(car.DriftAngle);
            // hold: PD on drift angle using throttle; steer = counter-steer (beta) + path term
            float target = 35f, R = 28f;
            float hold = 0f, sum = 0f, n = 0f, spun = 0f;
            t = 0f;
            float prevA = Mathf.Abs(car.DriftAngle);
            while (t < 8f)
            {
                yield return new WaitForFixedUpdate(); t += Time.fixedDeltaTime;
                // expert driver (same law as Tools/physics/sim.py): fronts track velocity + yaw-rate correction; throttle holds angle
                float beta = car.DriftAngle;
                float a = Mathf.Abs(beta);
                float sgn = beta >= 0 ? 1f : -1f;
                float rTarget = -sgn * Mathf.Max(car.SpeedMs, 1f) / R;
                float steerDeg = beta + (rTarget - car.YawRate) * 9f;
                float dA = (a - prevA) / Time.fixedDeltaTime; prevA = a;
                float thr = Mathf.Clamp01(0.55f + (target - a) * 0.035f - dA * 0.006f);
                Set(Mathf.Clamp(steerDeg / car.spec.maxSteerDeg, -1, 1), thr, 0, false);
                if (a > 15f && a < 70f && car.SpeedKmh > 25f) hold += Time.fixedDeltaTime;
                if (a > 100f) spun += Time.fixedDeltaTime;
                if (a > 10f) { sum += a; n++; }
            }
            report.AppendLine($"drift({(clutchKick ? "clutch-kick" : "handbrake")}): peak entry {maxAngle:0}°, after-entry {initAngle:0}°, sustained {hold:0.0}/8.0 s, mean angle {(n > 0 ? sum / n : 0):0}°, spin {(spun > 0.3f ? "YES" : "no")}, end speed {car.SpeedKmh:0} km/h");
        }
    }
}
