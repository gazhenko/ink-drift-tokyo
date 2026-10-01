using System;
using UnityEngine;

namespace InkDrift
{
    public enum DriveType { RWD, AWD }

    /// <summary>Full physical + presentation description of a car. Presets live in CarCatalog.</summary>
    [Serializable]
    public class CarSpec
    {
        [Header("Identity")]
        public string id = "hachi";
        public string displayName = "HACHI GR8";
        public string jpName = "ハチ";
        public string tagline = "";
        public string inspiredBy = "";
        public string prefabName = "Car_hachi";

        [Header("Chassis")]
        public DriveType drive = DriveType.RWD;
        public float mass = 1270f;
        public Vector3 centerOfMass = new Vector3(0f, 0.42f, 0.02f);
        public Vector3 inertiaScale = new Vector3(1.0f, 1.05f, 1.0f);
        public float wheelbase = 2.575f;
        public float trackFront = 1.52f;
        public float trackRear = 1.55f;
        public float frontAxleZ = 1.30f;            // distance forward of origin to front axle

        [Header("Wheels / Suspension")]
        public float wheelRadius = 0.33f;
        public float wheelWidth = 0.255f;
        public float wheelInertia = 1.2f;           // kg m^2, per wheel incl. brake rotor
        public float mountHeight = 0.62f;           // suspension top, above ground origin
        public float restLength = 0.30f;
        public float springFront = 52000f;
        public float springRear = 48000f;
        public float damperBump = 3400f;
        public float damperRebound = 4600f;
        public float antiRollFront = 14000f;
        public float antiRollRear = 9000f;

        [Header("Tires")]
        public float gripFront = 1.18f;
        public float gripRear = 1.08f;
        public float peakSlipAngleDeg = 7.5f;
        public float peakSlipRatio = 0.11f;
        public float slideGripFront = 0.88f;        // fraction of peak when fully sliding
        public float slideGripRear = 0.80f;
        public float slideFalloff = 0.85f;          // how fast grip decays past the peak
        public float loadSensitivity = 0.10f;

        [Header("Engine")]
        public float idleRpm = 950f;
        public float redlineRpm = 7400f;
        public float revLimitRpm = 7600f;
        public float[] torqueRpm = { 1000, 2000, 3000, 4000, 5000, 6000, 7000, 7600 };
        public float[] torqueNm = { 170, 205, 225, 245, 258, 252, 232, 210 };
        public float engineInertia = 0.20f;
        public float engineFriction = 28f;
        public float engineBrake = 0.018f;          // Nm per rad/s
        public float turboBoostGain = 0f;           // 0 = NA. torque multiplier at full boost
        public float turboSpool = 0.45f;            // seconds
        public int cylinders = 4;
        public float exhaustCharacter = 0.5f;       // 0 smooth .. 1 raspy (audio)

        [Header("Drivetrain")]
        public float[] gears = { 3.626f, 2.188f, 1.541f, 1.213f, 1.000f, 0.767f };
        public float reverseRatio = 3.437f;
        public float finalDrive = 4.30f;
        public float drivetrainEfficiency = 0.88f;
        public float clutchCapacity = 520f;         // Nm
        public float frontTorqueSplit = 0f;         // AWD only
        public float shiftTime = 0.11f;

        [Header("Brakes / Steering")]
        public float brakeTorque = 2500f;   // per-wheel (scaled by bias)
        public float brakeBias = 0.64f;
        public float handbrakeTorque = 4200f;
        public float maxSteerDeg = 54f;             // angle-kit drift lock
        public float steerSpeed = 3.2f;             // full-lock per second (keyboard)

        [Header("Aero")]
        public float dragCoefficient = 0.33f;
        public float frontalArea = 2.05f;
        public float downforceFront = 0.25f;
        public float downforceRear = 0.45f;         // big ricer wing

        [Header("Presentation (0..1 stat bars)")]
        public float statPower = 0.5f;
        public float statWeight = 0.5f;
        public float statGrip = 0.5f;
        public float statDrift = 0.5f;
        public float horsepower = 300f;
        public Color[] paints = { };

        public float TorqueAt(float rpm)
        {
            if (rpm <= torqueRpm[0]) return torqueNm[0] * Mathf.Clamp01(rpm / torqueRpm[0] + 0.3f);
            for (int i = 1; i < torqueRpm.Length; i++)
            {
                if (rpm <= torqueRpm[i])
                {
                    float t = Mathf.InverseLerp(torqueRpm[i - 1], torqueRpm[i], rpm);
                    return Mathf.Lerp(torqueNm[i - 1], torqueNm[i], t);
                }
            }
            return torqueNm[torqueNm.Length - 1];
        }

        public float PeakTorque
        {
            get { float m = 0; foreach (var t in torqueNm) m = Mathf.Max(m, t); return m * (1f + turboBoostGain); }
        }

        public CarSpec Clone() => (CarSpec)MemberwiseClone();
    }
}
