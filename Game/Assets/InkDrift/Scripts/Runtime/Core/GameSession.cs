using UnityEngine;

namespace InkDrift
{
    public enum GameMode { DriftAttack, Battle, FreeRun }

    public class TrackInfo
    {
        public string id, name, jp, scene, timeOfDay, blurb;
        public int laps;
        public float lengthKm;
        public Color accent;
    }

    public static class TrackCatalog
    {
        public static readonly TrackInfo[] All =
        {
            new TrackInfo { id = "shibuya", name = "SHIBUYA NEON", jp = "渋谷ネオン", scene = "Track_shibuya", timeOfDay = "NIGHT · WET",
                blurb = "Rain-slick neon canyons, tight 90s and a sakura-lined canal. Clip the walls, chase the glow.", laps = 3, accent = Palette.Magenta },
            new TrackInfo { id = "shuto", name = "SHUTO C1 LOOP", jp = "首都高C1", scene = "Track_shuto", timeOfDay = "SUNSET",
                blurb = "Elevated expressway sweepers at 200 km/h between towers, tunnels and late-shift traffic.", laps = 2, accent = Palette.Yellow },
            new TrackInfo { id = "okutama", name = "OKUTAMA TOUGE", jp = "奥多摩峠", scene = "Track_okutama", timeOfDay = "AUTUMN · GOLDEN HOUR",
                blurb = "Western Tokyo's mountain pass: hairpins, cedar forest, burning momiji and a long drop to the gorge.", laps = 2, accent = Palette.Red },
        };

        public static TrackInfo Get(string id)
        {
            foreach (var t in All) if (t.id == id) return t;
            return All[0];
        }
    }

    /// <summary>Selections and settings carried between scenes; settings persisted with PlayerPrefs.</summary>
    public static class GameSession
    {
        public static string CarId = "hachi";
        public static int PaintIndex = 0;
        public static string TrackId = "shibuya";
        public static GameMode Mode = GameMode.DriftAttack;
        public static int Rivals = 5;
        public static bool Traffic = true;

        public static int AssistLevel
        {
            get => PlayerPrefs.GetInt("assist", 1);
            set => PlayerPrefs.SetInt("assist", value);
        }
        public static Transmission Gearbox
        {
            get => (Transmission)PlayerPrefs.GetInt("gearbox", 0);
            set => PlayerPrefs.SetInt("gearbox", (int)value);
        }
        public static float MasterVolume
        {
            get => PlayerPrefs.GetFloat("vol_master", 0.9f);
            set { PlayerPrefs.SetFloat("vol_master", value); AudioListener.volume = value; }
        }
        public static float MusicVolume
        {
            get => PlayerPrefs.GetFloat("vol_music", 0.7f);
            set => PlayerPrefs.SetFloat("vol_music", value);
        }
        public static float VoiceVolume
        {
            get => PlayerPrefs.GetFloat("vol_voice", 1f);
            set => PlayerPrefs.SetFloat("vol_voice", value);
        }
        public static int Quality
        {
            get => PlayerPrefs.GetInt("quality", Mathf.Max(0, QualitySettings.names.Length - 1));
            set { PlayerPrefs.SetInt("quality", value); QualitySettings.SetQualityLevel(value, true); }
        }

        public static long BestScore(string track) => long.Parse(PlayerPrefs.GetString("best_" + track, "0"));
        public static void SetBestScore(string track, long s) => PlayerPrefs.SetString("best_" + track, s.ToString());
        public static float BestLap(string track) => PlayerPrefs.GetFloat("lap_" + track, 0f);
        public static void SetBestLap(string track, float t) => PlayerPrefs.SetFloat("lap_" + track, t);
    }
}
