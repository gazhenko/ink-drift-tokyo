using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>The five playable cars. All fictional look-alikes; no OEM names or logos.</summary>
    public static class CarCatalog
    {
        static List<CarSpec> _all;

        public static IReadOnlyList<CarSpec> All => _all ??= ApplyDims(Build());

        public static void Reload() { _all = null; }

        /// <summary>Override chassis geometry with dimensions measured from the actual car model (Resources/CarDims/&lt;id&gt;.json).</summary>
        static List<CarSpec> ApplyDims(List<CarSpec> list)
        {
            foreach (var c in list)
            {
                var ta = Resources.Load<TextAsset>("CarDims/" + c.id);
                if (ta == null) continue;
                var kv = new Dictionary<string, float>();
                foreach (System.Text.RegularExpressions.Match m in System.Text.RegularExpressions.Regex.Matches(ta.text, "\"([A-Za-z0-9_ ]+)\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?)"))
                    kv[m.Groups[1].Value.ToLowerInvariant()] = float.Parse(m.Groups[2].Value, System.Globalization.CultureInfo.InvariantCulture);
                float Find(float fallback, params string[][] keys)
                {
                    foreach (var need in keys)
                        foreach (var p in kv)
                        {
                            bool ok = true;
                            foreach (var n in need) if (!p.Key.Contains(n)) { ok = false; break; }
                            if (ok) return p.Value;
                        }
                    return fallback;
                }
                float wb = Find(c.wheelbase, new[] { "wheelbase" });
                float fz = Find(wb * 0.5f, new[] { "front", "axle", "z" }, new[] { "front_axle" });
                float rz = Find(fz - wb, new[] { "rear", "axle", "z" }, new[] { "rear_axle" });
                c.wheelbase = Mathf.Abs(fz - rz) > 1.5f ? Mathf.Abs(fz - rz) : wb;
                c.frontAxleZ = fz;
                c.trackFront = Find(c.trackFront, new[] { "front", "track" });
                c.trackRear = Find(c.trackRear, new[] { "rear", "track" });
                c.wheelRadius = Find(c.wheelRadius, new[] { "wheel", "radius" }, new[] { "tire", "radius" }, new[] { "radius" });
                c.wheelWidth = Find(c.wheelWidth, new[] { "wheel", "width" }, new[] { "tire", "width" });
                float com = Find(-1f, new[] { "com" }, new[] { "center", "mass" });
                if (com > 0.2f && com < 0.8f) c.centerOfMass = new Vector3(0f, com, c.frontAxleZ - c.wheelbase * 0.5f + 0.04f);
                else c.centerOfMass = new Vector3(0f, c.centerOfMass.y, c.frontAxleZ - c.wheelbase * 0.5f + c.centerOfMass.z);
            }
            return list;
        }

        public static CarSpec Get(string id)
        {
            foreach (var c in All) if (c.id == id) return c;
            return All[0];
        }

        static Color Hex(string h) { ColorUtility.TryParseHtmlString(h, out var c); return c; }

        static List<CarSpec> Build()
        {
            var list = new List<CarSpec>();

            list.Add(new CarSpec
            {
                id = "hachi", displayName = "HACHI GR8", jpName = "ハチ・ジーアールエイト", prefabName = "Car_hachi",
                tagline = "Featherweight boxer. The purest drift teacher in Tokyo.",
                inspiredBy = "2020s Japanese 2+2 boxer coupe",
                drive = DriveType.RWD, mass = 1275f,
                centerOfMass = new Vector3(0f, 0.40f, 0.04f),
                wheelbase = 2.575f, trackFront = 1.52f, trackRear = 1.55f, frontAxleZ = 1.30f,
                wheelRadius = 0.325f, mountHeight = 0.60f,
                springFront = 46000f, springRear = 42000f, antiRollFront = 13000f, antiRollRear = 8000f,
                gripFront = 1.16f, gripRear = 1.02f, slideGripRear = 0.80f,
                idleRpm = 950f, redlineRpm = 7400f, revLimitRpm = 7600f,
                torqueRpm = new float[] { 1000, 2000, 3000, 4000, 5000, 6000, 7000, 7600 },
                torqueNm = new float[] { 190, 228, 252, 268, 290, 300, 288, 262 },
                cylinders = 4, exhaustCharacter = 0.75f,
                gears = new[] { 3.626f, 2.188f, 1.541f, 1.213f, 1.000f, 0.767f }, finalDrive = 4.30f,
                clutchCapacity = 560f, maxSteerDeg = 56f,
                statPower = 0.48f, statWeight = 0.78f, statGrip = 0.62f, statDrift = 0.86f, horsepower = 310,
                paints = new[] { Hex("#FF2D7A"), Hex("#00E5FF"), Hex("#FFE600"), Hex("#F2F2F2"), Hex("#111116"), Hex("#2F6BFF"), Hex("#FF6A00"), Hex("#B6FF3B") },
            });

            list.Add(new CarSpec
            {
                id = "kaiju", displayName = "KAIJU SPR-X", jpName = "カイジュウ・エスピーアールエックス", prefabName = "Car_kaiju",
                tagline = "Inline-six monster. Snaps sideways the instant you ask.",
                inspiredBy = "2020s Japanese turbo inline-six grand tourer",
                drive = DriveType.RWD, mass = 1505f,
                centerOfMass = new Vector3(0f, 0.43f, 0.06f),
                wheelbase = 2.47f, trackFront = 1.594f, trackRear = 1.589f, frontAxleZ = 1.24f,
                wheelRadius = 0.345f, mountHeight = 0.62f,
                springFront = 62000f, springRear = 58000f, antiRollFront = 17000f, antiRollRear = 10000f,
                gripFront = 1.20f, gripRear = 1.10f, slideGripRear = 0.78f,
                idleRpm = 850f, redlineRpm = 7000f, revLimitRpm = 7200f,
                torqueRpm = new float[] { 1000, 2000, 3000, 4000, 5000, 6000, 6800, 7200 },
                torqueNm = new float[] { 260, 320, 345, 352, 350, 336, 305, 280 },
                turboBoostGain = 0.95f, turboSpool = 0.55f,
                cylinders = 6, exhaustCharacter = 0.45f,
                gears = new[] { 3.727f, 2.048f, 1.371f, 1.000f, 0.819f, 0.637f }, finalDrive = 3.69f,
                clutchCapacity = 980f, maxSteerDeg = 52f,
                brakeTorque = 2900f,
                statPower = 0.95f, statWeight = 0.45f, statGrip = 0.74f, statDrift = 0.72f, horsepower = 580,
                paints = new[] { Hex("#FFE600"), Hex("#FF3B30"), Hex("#111116"), Hex("#E8E8EA"), Hex("#00E5FF"), Hex("#7A2BFF"), Hex("#FF2D7A"), Hex("#3BFF9A") },
            });

            list.Add(new CarSpec
            {
                id = "zenkai", displayName = "ZENKAI Z", jpName = "ゼンカイ・ゼット", prefabName = "Car_zenkai",
                tagline = "Twin-turbo V6 torque wall. Long, lazy, enormous angle.",
                inspiredBy = "2020s Japanese twin-turbo V6 sports coupe",
                drive = DriveType.RWD, mass = 1590f,
                centerOfMass = new Vector3(0f, 0.44f, 0.08f),
                wheelbase = 2.55f, trackFront = 1.56f, trackRear = 1.59f, frontAxleZ = 1.30f,
                wheelRadius = 0.345f, mountHeight = 0.62f,
                springFront = 60000f, springRear = 56000f, antiRollFront = 16000f, antiRollRear = 9500f,
                gripFront = 1.18f, gripRear = 1.08f, slideGripRear = 0.82f,
                idleRpm = 800f, redlineRpm = 6800f, revLimitRpm = 7000f,
                torqueRpm = new float[] { 1000, 1800, 2800, 3800, 4800, 5800, 6500, 7000 },
                torqueNm = new float[] { 270, 330, 360, 362, 355, 330, 300, 270 },
                turboBoostGain = 0.75f, turboSpool = 0.40f,
                cylinders = 6, exhaustCharacter = 0.62f,
                gears = new[] { 3.794f, 2.324f, 1.624f, 1.271f, 1.000f, 0.794f }, finalDrive = 3.69f,
                clutchCapacity = 900f, maxSteerDeg = 58f,
                brakeTorque = 2900f,
                statPower = 0.82f, statWeight = 0.40f, statGrip = 0.70f, statDrift = 0.90f, horsepower = 480,
                paints = new[] { Hex("#2F6BFF"), Hex("#FF6A00"), Hex("#FFE600"), Hex("#F2F2F2"), Hex("#111116"), Hex("#FF2D7A"), Hex("#00E5FF"), Hex("#9B9BA3") },
            });

            list.Add(new CarSpec
            {
                id = "raijin", displayName = "RAIJIN BX-R", jpName = "ライジン・ビーエックスアール", prefabName = "Car_raijin",
                tagline = "Turbo boxer, symmetrical AWD. Throw it in, pin it, pray.",
                inspiredBy = "2020s Japanese AWD turbo sports sedan",
                drive = DriveType.AWD, frontTorqueSplit = 0.32f, mass = 1560f,
                centerOfMass = new Vector3(0f, 0.47f, 0.12f),
                wheelbase = 2.67f, trackFront = 1.57f, trackRear = 1.58f, frontAxleZ = 1.38f,
                wheelRadius = 0.33f, mountHeight = 0.64f,
                springFront = 54000f, springRear = 50000f, antiRollFront = 12000f, antiRollRear = 11000f,
                gripFront = 1.16f, gripRear = 1.10f, slideGripFront = 0.86f, slideGripRear = 0.84f,
                idleRpm = 850f, redlineRpm = 6600f, revLimitRpm = 6900f,
                torqueRpm = new float[] { 1000, 2000, 3000, 4000, 5000, 5800, 6400, 6900 },
                torqueNm = new float[] { 230, 300, 330, 335, 330, 315, 290, 260 },
                turboBoostGain = 0.65f, turboSpool = 0.42f,
                cylinders = 4, exhaustCharacter = 0.8f,
                gears = new[] { 3.454f, 1.947f, 1.296f, 0.972f, 0.780f, 0.666f }, finalDrive = 4.11f,
                clutchCapacity = 820f, maxSteerDeg = 50f,
                statPower = 0.70f, statWeight = 0.52f, statGrip = 0.92f, statDrift = 0.58f, horsepower = 380,
                paints = new[] { Hex("#F2F2F2"), Hex("#FF3B30"), Hex("#111116"), Hex("#00E5FF"), Hex("#FFE600"), Hex("#3BFF9A"), Hex("#FF2D7A"), Hex("#7A2BFF") },
            });

            list.Add(new CarSpec
            {
                id = "tsubame", displayName = "TSUBAME RS", jpName = "ツバメ・アールエス", prefabName = "Car_tsubame",
                tagline = "One tonne of roadster. Twitchy, honest, savage on the touge.",
                inspiredBy = "2020s Japanese lightweight roadster",
                drive = DriveType.RWD, mass = 1065f,
                centerOfMass = new Vector3(0f, 0.38f, 0.02f),
                wheelbase = 2.31f, trackFront = 1.495f, trackRear = 1.505f, frontAxleZ = 1.18f,
                wheelRadius = 0.31f, mountHeight = 0.58f,
                springFront = 40000f, springRear = 36000f, antiRollFront = 11000f, antiRollRear = 6500f,
                gripFront = 1.14f, gripRear = 1.02f, slideGripRear = 0.78f,
                idleRpm = 900f, redlineRpm = 7500f, revLimitRpm = 7700f,
                torqueRpm = new float[] { 1000, 2000, 3000, 4000, 5000, 6000, 7000, 7700 },
                torqueNm = new float[] { 150, 182, 200, 212, 222, 228, 214, 190 },
                cylinders = 4, exhaustCharacter = 0.65f,
                gears = new[] { 3.709f, 2.190f, 1.536f, 1.177f, 1.000f, 0.832f }, finalDrive = 3.90f,
                clutchCapacity = 420f, maxSteerDeg = 55f,
                brakeTorque = 2100f,
                statPower = 0.32f, statWeight = 0.95f, statGrip = 0.58f, statDrift = 0.80f, horsepower = 240,
                paints = new[] { Hex("#FF3B30"), Hex("#FFB7D5"), Hex("#00E5FF"), Hex("#F2F2F2"), Hex("#111116"), Hex("#FFE600"), Hex("#3BFF9A"), Hex("#2F6BFF") },
            });

            return list;
        }
    }
}
