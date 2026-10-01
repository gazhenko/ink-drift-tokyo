using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace InkDrift
{
    /// <summary>In-race comic HUD: speedo/tach/gear, drift chain + multiplier, score, laps/time/position, minimap.</summary>
    public class HUD : MonoBehaviour
    {
        public CarController car;
        public DriftScorer scorer;
        public RaceManager race;

        Canvas canvas;
        TextMeshProUGUI speed, speedUnit, gear, chain, mult, total, lapText, timeText, bestText, posText, angleText, closeText, modeText;
        TachArc tach, angleArc;
        Image chainBar, speedLines;
        SlantPanel chainPanel, gearPanel;
        CanvasGroup chainGroup;
        MiniMap map;
        float chainShown, chainPunch, multPunch;
        int lastMult = 1;
        float flashT;

        public void Build()
        {
            var fs = FontSet.I;
            canvas = UIKit.MakeCanvas("HUD", 20, transform);
            var root = UIKit.Stretch("Root", canvas.transform);

            // speed lines overlay (behind everything else in the HUD)
            var lib = CalloutLibrary.Instance;
            if (lib != null && lib.speedLines != null)
            {
                speedLines = UIKit.Img("SpeedLines", root, lib.speedLines, new Color(1, 1, 1, 0), new Vector2(0.5f, 0.5f), Vector2.zero, Vector2.zero);
                speedLines.preserveAspect = false;
                var rt = speedLines.rectTransform; rt.anchorMin = Vector2.zero; rt.anchorMax = Vector2.one; rt.sizeDelta = new Vector2(400, 400);
            }

            // ---------------- speedo (bottom-right)
            var speedo = UIKit.Rect("Speedo", root, new Vector2(1, 0), new Vector2(1, 0), new Vector2(1, 0), new Vector2(-40, 30), new Vector2(460, 420));
            tach = speedo.gameObject.AddComponent<TachArc>();
            tach.innerRadius = 158; tach.outerRadius = 196; tach.raycastTarget = false;
            speed = UIKit.Text("Speed", speedo, "0", fs ? fs.hud : null, 150, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(-6, 18), new Vector2(380, 170));
            UIKit.Inked(speed, 0.22f, Palette.Ink, new Vector2(0.8f, -0.8f));
            speed.characterSpacing = -4;
            speedUnit = UIKit.Text("Unit", speedo, "km/h", fs ? fs.comic : null, 44, Palette.Cyan, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -62), new Vector2(200, 60));
            UIKit.Inked(speedUnit, 0.3f);
            var gp = UIKit.Rect("GearPanel", speedo, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0, -150), new Vector2(120, 96));
            gearPanel = gp.gameObject.AddComponent<SlantPanel>(); gearPanel.color = Palette.Yellow; gearPanel.slant = 18; gearPanel.raycastTarget = false;
            gear = UIKit.Text("Gear", gp, "1", fs ? fs.hud : null, 84, Palette.Ink, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(8, 2), new Vector2(120, 96));

            // drift angle mini-arc (bottom-center)
            var ang = UIKit.Rect("Angle", root, new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0.5f, 0), new Vector2(0, 10), new Vector2(320, 180));
            angleArc = ang.gameObject.AddComponent<TachArc>();
            angleArc.segments = 24; angleArc.startAngle = 180; angleArc.endAngle = 0; angleArc.innerRadius = 110; angleArc.outerRadius = 128; angleArc.redline01 = 0.75f;
            angleArc.low = Palette.Lime; angleArc.mid = Palette.Yellow; angleArc.high = Palette.Magenta; angleArc.raycastTarget = false;
            angleText = UIKit.Text("AngleText", ang, "0°", fs ? fs.hud : null, 46, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, -38), new Vector2(200, 60));
            UIKit.Inked(angleText, 0.3f);
            closeText = UIKit.Text("Close", ang, "CLOSE! ×1.6", fs ? fs.comic : null, 46, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(0, 70), new Vector2(400, 60));
            UIKit.Inked(closeText, 0.32f); closeText.gameObject.SetActive(false);

            // ---------------- drift chain (top-center)
            var cp = UIKit.Rect("Chain", root, new Vector2(0.5f, 1), new Vector2(0.5f, 1), new Vector2(0.5f, 1), new Vector2(0, -26), new Vector2(560, 130));
            chainGroup = cp.gameObject.AddComponent<CanvasGroup>();
            chainPanel = cp.gameObject.AddComponent<SlantPanel>(); chainPanel.color = Palette.Magenta; chainPanel.raycastTarget = false;
            chain = UIKit.Text("ChainScore", cp, "0", fs ? fs.comic : null, 96, Palette.Paper, TextAlignmentOptions.Center, new Vector2(0.5f, 0.5f), new Vector2(-30, 8), new Vector2(460, 120));
            UIKit.Inked(chain, 0.3f, Palette.Ink, new Vector2(1f, -1f));
            mult = UIKit.Text("Mult", cp, "×1", fs ? fs.comic : null, 76, Palette.Yellow, TextAlignmentOptions.Center, new Vector2(1f, 0.5f), new Vector2(-40, 14), new Vector2(160, 100));
            UIKit.Inked(mult, 0.34f, Palette.Ink, new Vector2(1f, -1f));
            var barBg = UIKit.Img("BarBg", cp, null, Palette.Ink, new Vector2(0.5f, 0f), new Vector2(10, -6), new Vector2(470, 16));
            chainBar = UIKit.Img("Bar", barBg.transform, null, Palette.Yellow, new Vector2(0f, 0.5f), Vector2.zero, new Vector2(470, 10));
            chainBar.rectTransform.pivot = new Vector2(0, 0.5f);
            chainBar.rectTransform.anchoredPosition = new Vector2(0, 0);

            // ---------------- total score (top-right)
            var tp = UIKit.Rect("Total", root, new Vector2(1, 1), new Vector2(1, 1), new Vector2(1, 1), new Vector2(-40, -26), new Vector2(430, 110));
            var tpp = tp.gameObject.AddComponent<SlantPanel>(); tpp.color = Palette.Ink.WithA(0.85f); tpp.borderColor = Palette.Paper; tpp.border = 4; tpp.raycastTarget = false;
            var tl = UIKit.Text("Label", tp, "DRIFT SCORE · ドリフト", fs ? fs.jpBody : null, 24, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(205, -22), new Vector2(380, 30));
            total = UIKit.Text("Value", tp, "0", fs ? fs.hud : null, 62, Palette.Paper, TextAlignmentOptions.Right, new Vector2(1, 0), new Vector2(-180, 40), new Vector2(380, 70));

            // ---------------- race info (top-left)
            var rp = UIKit.Rect("Race", root, new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1), new Vector2(40, -26), new Vector2(440, 170));
            var rpp = rp.gameObject.AddComponent<SlantPanel>(); rpp.color = Palette.Ink.WithA(0.85f); rpp.borderColor = Palette.Paper; rpp.border = 4; rpp.raycastTarget = false;
            lapText = UIKit.Text("Lap", rp, "LAP 1/3", fs ? fs.comic : null, 56, Palette.Yellow, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(200, -40), new Vector2(360, 64));
            posText = UIKit.Text("Pos", rp, "", fs ? fs.comic : null, 64, Palette.Magenta, TextAlignmentOptions.Right, new Vector2(1, 1), new Vector2(-90, -40), new Vector2(160, 70));
            UIKit.Inked(posText, 0.3f);
            timeText = UIKit.Text("Time", rp, "0:00.000", fs ? fs.hud : null, 44, Palette.Paper, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(200, -96), new Vector2(360, 50));
            bestText = UIKit.Text("Best", rp, "BEST --:--.---", fs ? fs.hudRegular : null, 28, Palette.Cyan, TextAlignmentOptions.Left, new Vector2(0, 1), new Vector2(200, -138), new Vector2(360, 36));
            modeText = UIKit.Text("Mode", rp, "", fs ? fs.comic : null, 26, Palette.Paper.WithA(0.7f), TextAlignmentOptions.Left, new Vector2(0, 0), new Vector2(200, -18), new Vector2(360, 30));

            // ---------------- minimap (bottom-left)
            var mm = UIKit.Rect("MiniMap", root, new Vector2(0, 0), new Vector2(0, 0), new Vector2(0, 0), new Vector2(40, 40), new Vector2(300, 300));
            var mmBg = mm.gameObject.AddComponent<SlantPanel>(); mmBg.color = Palette.Indigo.WithA(0.75f); mmBg.slant = 0; mmBg.border = 5; mmBg.raycastTarget = false;
            var mmc = UIKit.Rect("Map", mm, Vector2.zero, Vector2.one, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(-14, -14));
            mmc.gameObject.AddComponent<RectMask2D>();
            var mmInner = UIKit.Rect("Lines", mmc, Vector2.zero, Vector2.one, new Vector2(0.5f, 0.5f), Vector2.zero, Vector2.zero);
            map = mmInner.gameObject.AddComponent<MiniMap>();
            map.raycastTarget = false;
            map.path = TrackPath.Active;
            map.player = car != null ? car.transform : null;

            if (scorer != null)
            {
                scorer.OnMultiplier += m => multPunch = 1f;
            }
        }

        public void AddRival(Transform t) { if (map != null) map.others.Add(t); }

        static string Fmt(float t)
        {
            if (t <= 0f) return "--:--.---";
            int m = (int)(t / 60f); float s = t - m * 60f;
            return $"{m}:{s:00.000}";
        }

        static string Ordinal(int p) => p switch { 1 => "1ST", 2 => "2ND", 3 => "3RD", _ => p + "TH" };

        void Update()
        {
            if (car == null || canvas == null) return;
            float dt = Time.unscaledDeltaTime;
            float kmh = Mathf.Abs(car.ForwardSpeed) * 3.6f;
            speed.text = Mathf.RoundToInt(kmh).ToString();
            float rpm01 = Mathf.Clamp01(car.EngineRpm / car.spec.revLimitRpm);
            tach.redline01 = car.spec.redlineRpm / car.spec.revLimitRpm;
            tach.SetValue(rpm01);
            bool shiftLight = car.EngineRpm > car.spec.redlineRpm * 0.96f;
            flashT += dt;
            bool f = shiftLight && Mathf.Repeat(flashT, 0.12f) < 0.06f;
            if (f != tach.flash) { tach.flash = f; tach.SetVerticesDirty(); }
            gear.text = car.Gear < 0 ? "R" : car.Gear == 0 ? "N" : car.Gear.ToString();
            gearPanel.color = car.OnLimiter ? Palette.Red : Palette.Yellow;

            float a = scorer != null ? scorer.CurrentAngle : Mathf.Abs(car.DriftAngle);
            angleArc.SetValue(Mathf.Clamp01(a / 90f));
            angleText.text = Mathf.RoundToInt(a) + "°";

            if (scorer != null)
            {
                bool active = scorer.ChainActive;
                chainGroup.alpha = Mathf.MoveTowards(chainGroup.alpha, active ? 1f : 0f, dt * (active ? 10f : 3f));
                if (active) chainShown = Mathf.Lerp(chainShown, scorer.ChainScore, 1f - Mathf.Exp(-18f * dt));
                chain.text = Mathf.RoundToInt(chainShown).ToString("N0");
                int tier = DriftScorer.TierFor(scorer.ChainScore);
                chainPanel.color = tier switch { >= 6 => Palette.Red, >= 3 => Palette.Magenta, >= 2 => Palette.Yellow, >= 1 => Palette.Cyan, _ => Palette.Indigo };
                chain.color = tier == 2 ? Palette.Ink : Palette.Paper;
                if (scorer.Multiplier != lastMult) { lastMult = scorer.Multiplier; multPunch = 1f; }
                mult.text = "×" + scorer.Multiplier;
                multPunch = Mathf.MoveTowards(multPunch, 0f, dt * 4f);
                mult.rectTransform.localScale = Vector3.one * (1f + multPunch * 0.6f);
                mult.rectTransform.localRotation = Quaternion.Euler(0, 0, Mathf.Sin(multPunch * 20f) * 10f * multPunch);
                chainBar.rectTransform.sizeDelta = new Vector2(470f * scorer.ChainTimeLeft01, 10f);
                total.text = scorer.TotalScore.ToString("N0");
                closeText.gameObject.SetActive(scorer.Drifting && scorer.CloseToWall);
                if (closeText.gameObject.activeSelf) closeText.rectTransform.localScale = Vector3.one * (1f + Mathf.Sin(Time.time * 30f) * 0.06f);
            }

            if (race != null)
            {
                lapText.text = race.Mode == GameMode.FreeRun ? "FREE RUN" : $"LAP {Mathf.Min(race.PlayerLap, race.TotalLaps)}/{race.TotalLaps}";
                timeText.text = Fmt(race.CurrentLapTime);
                bestText.text = "BEST " + Fmt(race.BestLapTime);
                posText.text = race.Mode == GameMode.Battle ? Ordinal(race.PlayerPosition) : "";
                modeText.text = race.Mode switch { GameMode.DriftAttack => "DRIFT ATTACK · ドリフトアタック", GameMode.Battle => "RIVAL BATTLE · バトル", _ => "FREE RUN · フリー" };
            }

            if (speedLines != null)
            {
                float s = Mathf.InverseLerp(110f, 230f, kmh) * 0.55f + car.Boost * 0.15f;
                var c = speedLines.color; c.a = Mathf.Lerp(c.a, s, 1f - Mathf.Exp(-6f * dt)); speedLines.color = c;
                speedLines.rectTransform.localScale = Vector3.one * (1f + Mathf.Repeat(Time.time * 3f, 1f) * 0.04f);
                speedLines.rectTransform.localRotation = Quaternion.Euler(0, 0, Mathf.Floor(Time.time * 24f) * 7f);
            }
        }

        public void SetVisible(bool v) { if (canvas) canvas.enabled = v; }
    }
}
