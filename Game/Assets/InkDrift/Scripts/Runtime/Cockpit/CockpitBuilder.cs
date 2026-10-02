using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Rendering;

namespace InkDrift
{
    /// <summary>Cabin measurements of a car, from Tools/cars/cockpit_assets.py (Unity car-local frame, metres).</summary>
    [Serializable]
    public class CabinDims
    {
        public string id;
        public float[] eye;
        public float cowlZ, cowlY, cowlHalfW, headerZ, headerY, headerHalfW, sideFrontZ, sideRearZ, backTopZ, backBottomZ, floorY;
        public float[] z, roofY, beltY, beltHalfW, roofHalfW;
        public float redline, revLimit, dialMaxRpm;

        public Vector3 Eye => new Vector3(eye[0], eye[1], eye[2]);

        public static CabinDims Load(string id)
        {
            var ta = Resources.Load<TextAsset>("Cockpit/" + id);
            if (ta == null) return null;
            var d = JsonUtility.FromJson<CabinDims>(ta.text);
            return d != null && d.z != null && d.z.Length > 1 ? d : null;
        }

        float At(float[] arr, float zz)
        {
            // stations run from the header backwards (descending z)
            if (zz >= z[0]) return arr[0];
            for (int i = 1; i < z.Length; i++)
                if (zz >= z[i]) return Mathf.Lerp(arr[i - 1], arr[i], Mathf.InverseLerp(z[i - 1], z[i], zz));
            return arr[arr.Length - 1];
        }

        public float Roof(float zz) => At(roofY, zz);
        public float Belt(float zz) => At(beltY, zz);
        public float BeltW(float zz) => At(beltHalfW, zz);
        public float RoofW(float zz) => At(roofHalfW, zz);
    }

    /// <summary>
    /// Builds a right-hand-drive interior for a car from its <see cref="CabinDims"/>: dash, binnacle and live gauges,
    /// steering wheel, H-pattern shifter, hydraulic handbrake, pillars, headliner, doors, bucket seats, roll cage,
    /// rear-view mirror, and the driver's arms. Materials are cloned from the car's own (so their shader variants ship).
    /// </summary>
    public static class CockpitBuilder
    {
        static readonly Dictionary<string, Color> CageColors = new Dictionary<string, Color>
        {
            { "hachi", new Color(1f, 0.42f, 0.06f) }, { "kaiju", new Color(0.92f, 0.12f, 0.15f) }, { "zenkai", new Color(0.78f, 0.8f, 0.84f) },
            { "raijin", new Color(0.15f, 0.42f, 0.95f) }, { "tsubame", new Color(0.95f, 0.1f, 0.12f) },
        };

        class Mats
        {
            public Material dark, dash, soft, trim, metal, accent, cage, seat, insert, harness, marker, suit, suitStripe, glove, cuff, needle, ledOff, screen, chrome;
            public Material[] ledOn;
            public Material gaugeFace(Texture t) { var m = new Material(Shader.Find("UI/Default")); m.mainTexture = t; m.color = Color.white; m.renderQueue = 3000; return m; }   // after the opaque binnacle (the UI shader doesn't write depth)
        }

        public static CockpitRig Build(CarController car)
        {
            var dims = CabinDims.Load(car.spec.id);
            if (dims == null) { Debug.LogWarning("[Cockpit] no cabin data for " + car.spec.id); return null; }
            var root = new GameObject("Cockpit");
            root.transform.SetParent(car.transform, false);
            root.layer = CarController.CarLayer;
            var mats = MakeMaterials(car);
            var rig = root.AddComponent<CockpitRig>();
            rig.car = car;
            rig.dims = dims;

            var e = dims.Eye;
            float ex = e.x, ey = e.y, ez = e.z;
            float floor = dims.floorY;
            Vector3 wheelC = new Vector3(ex, ey - 0.25f, ez + 0.39f);
            Vector3 col = new Vector3(0f, -0.40f, 1f).normalized;          // steering column, toward the dash
            float dashEdgeZ = wheelC.z + 0.10f;
            float cz = dims.cowlZ, cy = dims.cowlY, hz = dims.headerZ, hy = dims.headerY;
            float yEdge = cy;
            float dashW = dims.BeltW(dashEdgeZ) - 0.05f;
            float consoleTop = floor + 0.33f;
            float gz = dashEdgeZ - 0.03f;   // instrument pod stands proud of the dash face
            Vector3 gaugeC = new Vector3(ex, ey - Mathf.Tan(20f * Mathf.Deg2Rad) * (gz - ez), gz);
            Vector3 gaugeN = (e - gaugeC).normalized;                       // gauge faces look at the driver

            var dark = new ProcMesh(); var dash = new ProcMesh(); var soft = new ProcMesh(); var trim = new ProcMesh();
            var metal = new ProcMesh(); var accent = new ProcMesh(); var seat = new ProcMesh(); var insert = new ProcMesh();
            var harness = new ProcMesh(); var chrome = new ProcMesh(); var screen = new ProcMesh();

            // ---------------------------------------------------------------- dash
            var prof = new List<Vector2>
            {
                new Vector2(cz + 0.05f, cy - 0.07f), new Vector2(cz - 0.02f, cy - 0.012f), new Vector2(dashEdgeZ + 0.07f, yEdge),
                new Vector2(dashEdgeZ, yEdge - 0.035f), new Vector2(dashEdgeZ + 0.025f, yEdge - 0.15f),
                new Vector2(dashEdgeZ + 0.11f, floor + 0.30f), new Vector2(cz - 0.08f, floor + 0.24f),
            };
            dash.ExtrudeX(prof, -dashW, dashW);
            // trim strip across the dash face and the passenger-side glovebox outline
            accent.Box(new Vector3(-0.08f, yEdge - 0.075f, dashEdgeZ + 0.012f), new Vector3(dashW * 2f - 0.5f, 0.012f, 0.012f));
            trim.Box(new Vector3(-ex, yEdge - 0.16f, dashEdgeZ + 0.045f), new Vector3(0.36f, 0.11f, 0.02f), Quaternion.Euler(-12f, 0f, 0f));
            // round "eyeball" vents at both dash ends and two in the centre
            foreach (float vx in new[] { dashW - 0.09f, -dashW + 0.09f, 0.07f, -0.07f })
            {
                Vector3 vc = new Vector3(vx, yEdge - 0.08f, dashEdgeZ + 0.008f);
                trim.Tube(vc + Vector3.forward * 0.02f, vc - Vector3.forward * 0.004f, 0.034f, 0.034f, 16, false, true);
                dark.Disc(vc - Vector3.forward * 0.006f, Vector3.back, 0.026f, 16);
                metal.Box(vc - Vector3.forward * 0.008f, new Vector3(0.05f, 0.004f, 0.004f));
            }

            // ---------------------------------------------------------------- binnacle + gauges
            Vector3 bc = gaugeC + new Vector3(0f, 0.01f, 0.02f);
            float ba = 0.175f, bb = 0.105f, b0 = gaugeC.z - 0.05f, b1 = dashEdgeZ + 0.08f;
            dash.Surface((u, vv) => new Vector3(bc.x + ba * Mathf.Cos(u * Mathf.PI), bc.y + bb * Mathf.Sin(u * Mathf.PI), Mathf.Lerp(b0, b1, vv)), 16, 2, Vector3.up);
            dark.Surface((u, vv) => new Vector3(bc.x + (ba - 0.012f) * Mathf.Cos(u * Mathf.PI), bc.y + (bb - 0.012f) * Mathf.Sin(u * Mathf.PI), Mathf.Lerp(b0 + 0.004f, b1, vv)), 16, 2, Vector3.down);
            trim.Torus(new Vector3(bc.x, bc.y, b0), Vector3.forward, Vector3.right, ba - 0.006f, 0.008f, 0f, 180f, 24, 8);
            // back plate in the plane of the dials, and the pod body under them down into the dash face
            {
                Quaternion gr = Quaternion.LookRotation(-gaugeN, Vector3.up);
                Vector3 gu = gr * Vector3.right, gv = gr * Vector3.up, back = gaugeC - gaugeN * 0.008f;
                dark.Quad(back - gu * ba - gv * 0.07f, back + gu * ba - gv * 0.07f, back + gu * ba + gv * 0.11f, back - gu * ba + gv * 0.11f, gaugeN);
                dash.Box(new Vector3(bc.x, gaugeC.y - 0.075f, (gaugeC.z + dashEdgeZ) * 0.5f + 0.01f), new Vector3(ba * 2f, 0.05f, dashEdgeZ - gaugeC.z + 0.05f));
            }

            var gauges = new GameObject("Gauges");
            gauges.transform.SetParent(root.transform, false);
            var tach = Gauge(gauges.transform, "Tach", Resources.Load<Texture2D>("Cockpit/tach_" + dims.id), gaugeC, gaugeN, 0.058f, mats, chrome, 0.045f);
            var boost = Gauge(gauges.transform, "Boost", Resources.Load<Texture2D>("Cockpit/gauge_boost"), gaugeC + new Vector3(-0.108f, -0.018f, 0.006f), gaugeN, 0.037f, mats, chrome, 0.028f);
            var water = Gauge(gauges.transform, "Water", Resources.Load<Texture2D>("Cockpit/gauge_water"), gaugeC + new Vector3(0.108f, -0.018f, 0.006f), gaugeN, 0.037f, mats, chrome, 0.028f);
            rig.tachNeedle = tach; rig.boostNeedle = boost; rig.waterNeedle = water;
            Quaternion gaugeRot = Quaternion.LookRotation(-gaugeN, Vector3.up);
            rig.gearText = Label(gauges.transform, "Gear", "N", gaugeC + gaugeRot * new Vector3(0f, 0.012f, -0.003f), gaugeRot, 0.024f, new Color(1f, 0.9f, 0.2f));
            rig.speedText = Label(gauges.transform, "Speed", "0", gaugeC + gaugeRot * new Vector3(0f, -0.016f, -0.003f), gaugeRot, 0.011f, Color.white);

            // shift lights along the binnacle lip
            rig.shiftLights = new Renderer[7];
            for (int i = 0; i < 7; i++)
            {
                var led = new ProcMesh();
                float lx = (i - 3) * 0.02f;
                led.RoundBox(new Vector3(bc.x + lx, bc.y + bb - 0.02f, b0 + 0.012f), new Vector3(0.013f, 0.009f, 0.006f), Quaternion.identity, 0.3f, 6);
                rig.shiftLights[i] = Part(root.transform, "ShiftLight" + i, led, mats.ledOff);
            }
            rig.ledOn = mats.ledOn;
            rig.ledOff = mats.ledOff;

            // ---------------------------------------------------------------- centre stack + console
            float stackZ = dashEdgeZ + 0.03f;
            dash.Box(new Vector3(0f, (yEdge - 0.11f + floor + 0.30f) * 0.5f, stackZ - 0.01f), new Vector3(0.30f, yEdge - 0.11f - floor - 0.30f, 0.06f), Quaternion.Euler(-8f, 0f, 0f));
            screen.Box(new Vector3(0f, yEdge - 0.16f, stackZ - 0.045f), new Vector3(0.20f, 0.08f, 0.006f), Quaternion.Euler(-10f, 0f, 0f));
            for (int k = -1; k <= 1; k++) metal.Tube(new Vector3(k * 0.07f, yEdge - 0.26f, stackZ - 0.035f), new Vector3(k * 0.07f, yEdge - 0.26f, stackZ - 0.06f), 0.017f, 0.015f, 14);
            float conRear = ez - 0.22f;
            dash.Box(new Vector3(0f, (floor + consoleTop) * 0.5f, (stackZ + conRear) * 0.5f), new Vector3(0.26f, consoleTop - floor, stackZ - conRear));
            soft.RoundBox(new Vector3(0f, consoleTop + 0.03f, conRear + 0.12f), new Vector3(0.22f, 0.07f, 0.26f), Quaternion.identity, 0.3f);   // armrest

            // H-pattern shifter (pivot at the base of the lever)
            var shifter = new GameObject("Shifter").transform;
            shifter.SetParent(root.transform, false);
            Vector3 shiftBase = new Vector3(0f, consoleTop + 0.005f, ez + 0.43f);
            soft.Tube(shiftBase, shiftBase + Vector3.up * 0.055f, 0.065f, 0.018f, 16, false, false);   // boot
            trim.Box(shiftBase, new Vector3(0.16f, 0.012f, 0.16f));
            shifter.localPosition = shiftBase + Vector3.up * 0.045f;   // short-shift extension: the pivot sits up in the boot
            var lever = new ProcMesh();
            lever.Tube(new Vector3(0f, -0.045f, 0f), new Vector3(0f, 0.135f, -0.01f), 0.0085f, 0.0075f, 10);
            Part(shifter, "Lever", lever, mats.metal);
            var knob = new ProcMesh();
            knob.Ellipsoid(new Vector3(0f, 0.155f, -0.012f), new Vector3(0.024f, 0.028f, 0.024f), Quaternion.identity, 16);
            Part(shifter, "Knob", knob, mats.accent);
            rig.shifter = shifter;
            rig.knobLocal = new Vector3(0f, 0.158f, -0.012f);

            // hydraulic handbrake on the driver side of the console (pivot at its base)
            var hb = new GameObject("Handbrake").transform;
            hb.SetParent(root.transform, false);
            hb.localPosition = new Vector3(0.105f, consoleTop - 0.02f, ez + 0.47f);
            metal.Box(hb.localPosition + new Vector3(0f, 0.02f, 0f), new Vector3(0.03f, 0.06f, 0.07f));
            var hbm = new ProcMesh();
            Vector3 hbTop = Quaternion.Euler(-18f, 0f, 0f) * new Vector3(0f, 0.30f, 0f);
            hbm.Tube(Vector3.zero, hbTop * 0.62f, 0.011f, 0.010f, 10);
            var hbGrip = new ProcMesh();
            hbGrip.Tube(hbTop * 0.6f, hbTop, 0.017f, 0.016f, 12);
            hbGrip.Sphere(hbTop, 0.016f, 12);
            Part(hb, "Lever", hbm, mats.metal);
            Part(hb, "Grip", hbGrip, mats.accent);
            rig.handbrake = hb;
            rig.handbrakeGripLocal = hbTop * 0.82f;

            // ---------------------------------------------------------------- steering wheel (pivot on the column axis)
            var wheel = new GameObject("SteeringWheel").transform;
            wheel.SetParent(root.transform, false);
            wheel.localPosition = wheelC;
            wheel.localRotation = Quaternion.LookRotation(col, Vector3.up);
            const float R = 0.172f;
            var rim = new ProcMesh();
            rim.Torus(Vector3.zero, Vector3.forward, Vector3.right, R, 0.0175f, 98f, 442f, 64, 12);   // leaves 82..98° for the marker
            Part(wheel, "Rim", rim, mats.soft);
            var mark = new ProcMesh();
            mark.Torus(Vector3.zero, Vector3.forward, Vector3.right, R, 0.0182f, 82f, 98f, 8, 12);
            Part(wheel, "Marker", mark, mats.marker);
            var spokes = new ProcMesh();
            float dish = 0.065f;   // deep dish: hub sits toward the dash
            foreach (float a in new[] { 0f, 180f, 270f })
            {
                Vector3 dir = new Vector3(Mathf.Cos(a * Mathf.Deg2Rad), Mathf.Sin(a * Mathf.Deg2Rad), 0f);
                spokes.Beam(new Vector3(0f, 0f, dish) + dir * 0.03f, dir * (R - 0.012f), 0.042f, 0.007f, Vector3.forward);
            }
            spokes.Tube(new Vector3(0f, 0f, dish + 0.02f), new Vector3(0f, 0f, dish - 0.012f), 0.045f, 0.042f, 24);
            Part(wheel, "Spokes", spokes, mats.metal);
            var hub = new ProcMesh();
            hub.Disc(new Vector3(0f, 0f, dish - 0.014f), Vector3.back, 0.03f, 24);
            hub.Tube(new Vector3(0f, 0f, dish + 0.02f), new Vector3(0f, 0f, 0.30f), 0.03f, 0.035f, 16, false, false);   // column + quick release
            Part(wheel, "Hub", hub, mats.dark);
            var horn = new ProcMesh();
            horn.Torus(new Vector3(0f, 0f, dish - 0.015f), Vector3.forward, Vector3.right, 0.022f, 0.004f, 0f, 360f, 24, 6);
            Part(wheel, "HornRing", horn, mats.accent);
            rig.wheel = wheel;
            rig.wheelRadius = R;
            // column shroud (does not turn)
            dash.Tube(wheelC + col * 0.10f, wheelC + col * 0.32f, 0.055f, 0.07f, 16, true, false);

            // ---------------------------------------------------------------- pillars, header, headliner, mirror
            foreach (int s in new[] { 1, -1 })
            {
                Vector3 a0 = new Vector3(s * (dims.cowlHalfW - 0.015f), cy - 0.02f, cz - 0.03f);
                Vector3 a1 = new Vector3(s * (dims.headerHalfW - 0.01f), hy - 0.035f, hz + 0.01f);
                trim.Beam(a0, a1, 0.095f, 0.05f, new Vector3(-s, 0.3f, 0f));
                // B-pillar / quarter post behind the doors
                float bz = ez - 0.62f;
                trim.Beam(new Vector3(s * (dims.BeltW(bz) - 0.07f), dims.Belt(bz) - 0.02f, bz), new Vector3(s * (dims.RoofW(bz) - 0.02f), dims.Roof(bz) - 0.05f, bz - 0.06f), 0.10f, 0.04f, new Vector3(-s, 0f, 0f));
                // C-pillar trim behind the side glass
                float c0 = dims.sideRearZ - 0.02f, c1 = dims.backBottomZ + 0.05f;
                if (c0 > c1)
                    trim.Surface((u, vv) =>
                    {
                        float zz = Mathf.Lerp(c0, c1, u);
                        float yy = Mathf.Lerp(dims.Belt(zz) - 0.03f, dims.Roof(zz) - 0.05f, vv);
                        float xx = Mathf.Lerp(dims.BeltW(zz) - 0.07f, dims.RoofW(zz) - 0.03f, vv);
                        return new Vector3(s * xx, yy, zz);
                    }, 6, 4, new Vector3(-s, 0f, 0f));
            }
            trim.Beam(new Vector3(-dims.headerHalfW, hy - 0.04f, hz), new Vector3(dims.headerHalfW, hy - 0.04f, hz), 0.06f, 0.05f, Vector3.up);
            float hl0 = hz - 0.02f, hl1 = dims.backTopZ;
            soft.Surface((u, vv) =>
            {
                float zz = Mathf.Lerp(hl0, hl1, vv);
                float w = dims.RoofW(zz) + 0.01f;
                float xx = Mathf.Lerp(-w, w, u);
                float k = 2f * u - 1f;
                return new Vector3(xx, dims.Roof(zz) - 0.045f - 0.035f * k * k, zz);
            }, 10, 12, Vector3.down);
            foreach (int s in new[] { 1, -1 })   // roof rails above the side windows
            {
                var pts = new List<Vector3>();
                for (float zz = hz; zz >= dims.backTopZ - 0.001f; zz -= 0.1f) pts.Add(new Vector3(s * (dims.RoofW(zz) - 0.01f), dims.Roof(zz) - 0.075f, zz));
                soft.Sweep(pts, 0.035f, 10);
            }
            // sun visors folded up
            foreach (float vx in new[] { 0.31f, -0.31f })
                soft.RoundBox(new Vector3(vx, hy - 0.075f, hz - 0.12f), new Vector3(0.36f, 0.016f, 0.16f), Quaternion.Euler(10f, 0f, 0f), 0.25f, 8);
            // rear-view mirror, angled to the driver
            Vector3 mc = new Vector3(0.02f, hy - 0.088f, hz - 0.075f);
            dark.Tube(new Vector3(0.02f, hy - 0.05f, hz - 0.04f), mc + new Vector3(0f, 0.02f, 0.01f), 0.008f, 0.006f, 8);
            Quaternion mRot = Quaternion.LookRotation(e - mc + new Vector3(0f, 0f, -0.0f), Vector3.up);   // +z faces the driver
            dark.RoundBox(mc, new Vector3(0.23f, 0.066f, 0.03f), mRot, 0.25f, 8);
            var mirrorFace = new ProcMesh();
            Vector3 mr = mRot * Vector3.right, mu = mRot * Vector3.up, mf = mRot * Vector3.forward;
            Vector3 fc = mc + mf * 0.0155f;
            mirrorFace.Quad(fc - mr * 0.105f - mu * 0.027f, fc + mr * 0.105f - mu * 0.027f, fc + mr * 0.105f + mu * 0.027f, fc - mr * 0.105f + mu * 0.027f, mf);
            rig.mirrorRenderer = Part(root.transform, "MirrorGlass", mirrorFace, mats.dark);
            rig.mirrorPos = mc;

            // ---------------------------------------------------------------- doors, sills, floor, rear
            float doorFront = dashEdgeZ + 0.12f, doorRear = ez - 0.60f;
            foreach (int s in new[] { 1, -1 })
            {
                dash.Surface((u, vv) =>
                {
                    float zz = Mathf.Lerp(doorFront, dims.backBottomZ + 0.05f, u);
                    float top = dims.Belt(zz) - 0.012f;
                    return new Vector3(s * (dims.BeltW(zz) - 0.065f - 0.02f * (1f - vv)), Mathf.Lerp(floor, top, vv), zz);
                }, 10, 3, new Vector3(-s, 0f, 0f));
                var sill = new List<Vector3>();
                for (float zz = doorFront; zz >= dims.backBottomZ; zz -= 0.1f) sill.Add(new Vector3(s * (dims.BeltW(zz) - 0.05f), dims.Belt(zz) - 0.006f, zz));
                trim.Sweep(sill, 0.022f, 8);
                float az = (doorFront + doorRear) * 0.5f - 0.05f;
                soft.RoundBox(new Vector3(s * (dims.BeltW(az) - 0.12f), floor + 0.45f, az), new Vector3(0.09f, 0.05f, 0.42f), Quaternion.identity, 0.3f);
                chrome.Box(new Vector3(s * (dims.BeltW(ez + 0.15f) - 0.083f), dims.Belt(ez + 0.15f) - 0.10f, ez + 0.15f), new Vector3(0.012f, 0.022f, 0.10f));
                dark.Disc(new Vector3(s * (dims.BeltW(doorFront - 0.25f) - 0.087f), floor + 0.17f, doorFront - 0.25f), new Vector3(-s, 0f, 0f), 0.07f, 20);
            }
            dark.Quad(new Vector3(-dashW, floor, cz), new Vector3(dashW, floor, cz), new Vector3(dashW, floor, dims.backBottomZ), new Vector3(-dashW, floor, dims.backBottomZ), Vector3.up);
            float shelfZ = ez - 1.0f;
            if (dims.backBottomZ < shelfZ)
                dark.Quad(new Vector3(-dashW, dims.Belt(shelfZ) - 0.02f, shelfZ), new Vector3(dashW, dims.Belt(shelfZ) - 0.02f, shelfZ),
                    new Vector3(dashW, dims.Belt(dims.backBottomZ) - 0.02f, dims.backBottomZ), new Vector3(-dashW, dims.Belt(dims.backBottomZ) - 0.02f, dims.backBottomZ), Vector3.up);
            foreach (float sx in new[] { 0.32f, -0.32f })   // rear bench
            {
                seat.RoundBox(new Vector3(sx, floor + 0.2f, ez - 0.85f), new Vector3(0.48f, 0.12f, 0.45f), Quaternion.identity, 0.3f);
                seat.RoundBox(new Vector3(sx, floor + 0.48f, Mathf.Max(ez - 1.08f, dims.backBottomZ + 0.15f)), new Vector3(0.48f, 0.5f, 0.12f), Quaternion.Euler(-14f, 0f, 0f), 0.3f);
            }

            // ---------------------------------------------------------------- bucket seats
            foreach (float sx in new[] { ex, -ex })
            {
                bool driver = sx > 0f;
                float sz = ez - 0.21f;
                Quaternion tilt = Quaternion.Euler(-17f, 0f, 0f);
                Vector3 backC = new Vector3(sx, floor + 0.60f, sz);
                seat.RoundBox(backC, new Vector3(0.50f, 0.84f, 0.09f), tilt, 0.22f);
                seat.RoundBox(new Vector3(sx, floor + 0.22f, ez + 0.08f), new Vector3(0.48f, 0.13f, 0.52f), Quaternion.Euler(6f, 0f, 0f), 0.25f);
                foreach (int s in new[] { 1, -1 })
                {
                    seat.RoundBox(backC + tilt * new Vector3(s * 0.23f, -0.12f, 0.07f), new Vector3(0.08f, 0.52f, 0.20f), tilt * Quaternion.Euler(0f, -s * 12f, 0f), 0.3f);
                    seat.RoundBox(new Vector3(sx + s * 0.22f, floor + 0.29f, ez + 0.08f), new Vector3(0.08f, 0.10f, 0.46f), Quaternion.identity, 0.3f);
                }
                insert.RoundBox(backC + tilt * new Vector3(0f, -0.05f, 0.05f), new Vector3(0.26f, 0.54f, 0.02f), tilt, 0.25f);
                if (!driver)
                    foreach (int s in new[] { 1, -1 })
                    {
                        Vector3 top = backC + tilt * new Vector3(s * 0.08f, 0.40f, 0.06f);
                        Vector3 bot = backC + tilt * new Vector3(s * 0.06f, -0.20f, 0.08f);
                        harness.Beam(top, bot, 0.05f, 0.006f, tilt * Vector3.forward);
                        chrome.Box(bot + tilt * new Vector3(0f, 0.06f, 0.006f), new Vector3(0.04f, 0.03f, 0.008f), tilt);
                    }
            }

            // ---------------------------------------------------------------- roll cage
            float hoopZ = ez - 0.42f;
            const float cr = 0.019f;
            var hoop = new List<Vector3>();
            foreach (int s in new[] { -1, 1 })
            {
                var leg = new[]
                {
                    new Vector3(s * (dims.BeltW(hoopZ) - 0.09f), floor + 0.02f, hoopZ),
                    new Vector3(s * (dims.BeltW(hoopZ) - 0.10f), dims.Belt(hoopZ), hoopZ),
                    new Vector3(s * (dims.RoofW(hoopZ) - 0.07f), dims.Roof(hoopZ) - 0.10f, hoopZ),
                };
                if (s < 0) hoop.AddRange(leg); else { Array.Reverse(leg); hoop.AddRange(leg); }
            }
            accent.Sweep(hoop, cr);
            accent.Tube(hoop[2], hoop[5], cr, cr, 10, false, false);   // diagonal
            foreach (int s in new[] { -1, 1 })
            {
                Vector3 top = new Vector3(s * (dims.RoofW(hoopZ) - 0.07f), dims.Roof(hoopZ) - 0.10f, hoopZ);
                Vector3 hdr = new Vector3(s * (dims.headerHalfW - 0.06f), hy - 0.085f, hz - 0.04f);
                Vector3 foot = new Vector3(s * (dims.cowlHalfW - 0.075f), cy - 0.015f, cz - 0.10f);
                accent.Sweep(new[] { top, hdr, foot }, cr);
                Vector3 hb0 = new Vector3(s * (dims.BeltW(hoopZ) - 0.12f), floor + 0.48f, hoopZ);
                Vector3 hb1 = new Vector3(s * (dims.BeltW(doorFront) - 0.13f), floor + 0.14f, doorFront - 0.05f);
                Vector3 hb2 = new Vector3(s * (dims.BeltW(hoopZ) - 0.12f), floor + 0.14f, hoopZ);
                Vector3 hb3 = new Vector3(s * (dims.BeltW(doorFront) - 0.13f), floor + 0.48f, doorFront - 0.05f);
                accent.Tube(hb0, hb1, cr, cr, 10, false, false);
                accent.Tube(hb2, hb3, cr, cr, 10, false, false);
            }

            Part(root.transform, "Dark", dark, mats.dark);
            Part(root.transform, "Dash", dash, mats.dash);
            Part(root.transform, "Soft", soft, mats.soft);
            Part(root.transform, "Trim", trim, mats.trim);
            Part(root.transform, "Metal", metal, mats.metal);
            Part(root.transform, "Cage", accent, mats.cage);
            Part(root.transform, "Seats", seat, mats.seat);
            Part(root.transform, "Inserts", insert, mats.insert);
            Part(root.transform, "Harness", harness, mats.harness);
            Part(root.transform, "Chrome", chrome, mats.chrome);
            Part(root.transform, "Screen", screen, mats.screen);

            var lamp = new GameObject("CabinLight").AddComponent<Light>();
            lamp.transform.SetParent(root.transform, false);
            lamp.transform.localPosition = new Vector3(0.05f, dims.Roof(ez + 0.05f) - 0.12f, ez + 0.05f);   // dome light
            lamp.type = LightType.Point;
            lamp.range = 1.7f;
            lamp.intensity = 0.5f;
            lamp.color = new Color(1f, 0.82f, 0.9f);
            lamp.shadows = LightShadows.None;
            lamp.renderMode = LightRenderMode.ForcePixel;

            // ---------------------------------------------------------------- driver's arms
            rig.arms = (IDriverArms)DriverModel.Create(root.transform, e) ?? DriverArms.Create(root.transform, e, mats.suit, mats.suitStripe, mats.glove, mats.cuff);
            rig.Init();
            SetLayerRecursive(root.transform, CarController.CarLayer);
            return rig;
        }

        /// <summary>Gauge dial: textured face (unlit), bezel ring and a needle pivot (returned).</summary>
        static Transform Gauge(Transform parent, string name, Texture2D face, Vector3 c, Vector3 n, float r, Mats mats, ProcMesh bezel, float needleLen)
        {
            Quaternion rot = Quaternion.LookRotation(-n, Vector3.up);
            var faceMesh = new ProcMesh();
            faceMesh.Disc(c, n, r, 40, rot * Vector3.right);
            Part(parent, name + "Face", faceMesh, face != null ? mats.gaugeFace(face) : mats.dark);
            bezel.Torus(c + n * 0.002f, n, rot * Vector3.right, r + 0.003f, 0.0035f, 0f, 360f, 40, 8);
            var pivot = new GameObject(name + "Needle").transform;
            pivot.SetParent(parent, false);
            pivot.localPosition = c + n * 0.004f;
            pivot.localRotation = rot;
            var needle = new ProcMesh();
            needle.Box(new Vector3(needleLen * 0.4f, 0f, 0f), new Vector3(needleLen * 1.15f, 0.0035f, 0.0015f));
            needle.Tube(new Vector3(0, 0, 0.001f), new Vector3(0, 0, -0.002f), 0.006f, 0.006f, 16);
            Part(pivot, "Needle", needle, mats.needle);
            return pivot;
        }

        static TextMeshPro Label(Transform parent, string name, string text, Vector3 pos, Quaternion rot, float height, Color color)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot;
            var t = go.AddComponent<TextMeshPro>();
            var fs = FontSet.I;
            if (fs != null && fs.hud != null) t.font = fs.hud;
            t.text = text;
            t.fontSize = 10f;
            t.alignment = TextAlignmentOptions.Center;
            t.color = color;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            t.rectTransform.sizeDelta = new Vector2(20f, 10f);
            t.ForceMeshUpdate();
            float h = Mathf.Max(0.01f, t.GetPreferredValues("8").y);
            go.transform.localScale = Vector3.one * (height / h);
            return t;
        }

        static Renderer Part(Transform parent, string name, ProcMesh pm, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = pm.ToMesh("Cockpit_" + name);
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = true;
            mr.lightProbeUsage = LightProbeUsage.Off;
            mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            return mr;
        }

        public static void SetLayerRecursive(Transform t, int layer)
        {
            t.gameObject.layer = layer;
            foreach (Transform c in t) SetLayerRecursive(c, layer);
        }

        // ---------------------------------------------------------------- materials

        static Material FindMat(CarController car, string prefix)
        {
            foreach (var r in car.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null && m.name.StartsWith(prefix)) return m;
            return null;
        }

        static Material Clone(Material template, string name, Color color, float smooth = 0.3f, float metal = 0f, float spec = 0.3f, Color? emission = null)
        {
            var m = new Material(template) { name = "Cockpit_" + name };
            void F(string p, float v) { if (m.HasProperty(p)) m.SetFloat(p, v); }
            m.SetColor("_BaseColor", color);
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", null);
            F("_Smoothness", smooth); F("_Metallic", metal); F("_ReflectStrength", metal > 0.5f ? 0.25f : 0f);
            F("_SpecIntensity", spec); F("_SpecSize", 0.15f); F("_RimAmount", 0.25f); F("_HalftoneAmount", 0.6f);
            F("_ReceiveShadows", 0.2f); F("_WindStrength", 0f); F("_VertexAO", 0f); F("_HueVariation", 0f); F("_VertexTint", 0f);
            if (m.HasProperty("_EmissionColor")) m.SetColor("_EmissionColor", emission ?? Color.black);
            return m;
        }

        static Mats MakeMaterials(CarController car)
        {
            var baseMat = FindMat(car, "M_Trim") ?? FindMat(car, "M_Interior") ?? FindMat(car, "M_Paint");
            var chromeT = FindMat(car, "M_Chrome") ?? baseMat;
            if (baseMat == null)
            {
                var sh = Shader.Find("InkDrift/Toon");
                baseMat = new Material(sh);
                chromeT = baseMat;
            }
            Color accent = CageColors.TryGetValue(car.spec.id, out var c) ? c : Palette.Magenta;
            var m = new Mats
            {
                dark = Clone(baseMat, "Dark", new Color(0.04f, 0.04f, 0.047f), 0.2f),
                dash = Clone(baseMat, "Dash", new Color(0.10f, 0.10f, 0.112f), 0.25f, 0f, 0.25f),
                soft = Clone(baseMat, "Alcantara", new Color(0.14f, 0.135f, 0.145f), 0.08f, 0f, 0.05f),
                trim = Clone(baseMat, "Trim", new Color(0.17f, 0.17f, 0.19f), 0.45f, 0f, 0.4f),
                metal = Clone(chromeT, "Metal", new Color(0.32f, 0.33f, 0.35f), 0.6f, 0.8f, 0.8f),
                chrome = Clone(chromeT, "Chrome", new Color(0.75f, 0.77f, 0.8f), 0.9f, 1f, 1.4f),
                accent = Clone(baseMat, "Accent", accent, 0.7f, 0.2f, 1.2f),
                cage = Clone(chromeT, "Cage", Color.Lerp(accent, new Color(0.05f, 0.05f, 0.06f), 0.62f), 0.55f, 0.5f, 0.7f),
                seat = Clone(baseMat, "Seat", new Color(0.09f, 0.09f, 0.1f), 0.15f, 0f, 0.1f),
                insert = Clone(baseMat, "SeatInsert", Color.Lerp(accent, Color.black, 0.25f), 0.2f, 0f, 0.15f),
                harness = Clone(baseMat, "Harness", accent, 0.3f),
                marker = Clone(baseMat, "Marker", new Color(1f, 0.85f, 0.1f), 0.3f),
                suit = Clone(baseMat, "Suit", new Color(0.13f, 0.27f, 0.7f), 0.3f, 0f, 0.25f),
                suitStripe = Clone(baseMat, "SuitStripe", new Color(0.95f, 0.95f, 0.96f), 0.3f),
                glove = Clone(baseMat, "Glove", new Color(0.05f, 0.05f, 0.055f), 0.25f, 0f, 0.3f),
                cuff = Clone(baseMat, "GloveCuff", accent, 0.3f),
                needle = Clone(baseMat, "Needle", new Color(1f, 0.35f, 0.1f), 0.5f, 0f, 0.5f, new Color(1.6f, 0.45f, 0.1f)),
                ledOff = Clone(baseMat, "LedOff", new Color(0.05f, 0.05f, 0.06f), 0.8f, 0f, 0.8f),
                screen = Clone(baseMat, "Screen", new Color(0.02f, 0.02f, 0.04f), 0.9f, 0f, 1f, new Color(0.25f, 0.05f, 0.35f)),
            };
            m.ledOn = new[]
            {
                Clone(baseMat, "LedGreen", new Color(0.2f, 1f, 0.3f), 0.8f, 0f, 0.5f, new Color(0.4f, 3f, 0.6f)),
                Clone(baseMat, "LedYellow", new Color(1f, 0.85f, 0.1f), 0.8f, 0f, 0.5f, new Color(3f, 2.4f, 0.3f)),
                Clone(baseMat, "LedRed", new Color(1f, 0.1f, 0.1f), 0.8f, 0f, 0.5f, new Color(3.5f, 0.3f, 0.3f)),
                Clone(baseMat, "LedBlue", new Color(0.2f, 0.5f, 1f), 0.8f, 0f, 0.5f, new Color(0.5f, 1.4f, 3.5f)),
            };
            return m;
        }
    }
}
