using System;
using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    [CreateAssetMenu(menuName = "InkDrift/Callout Library")]
    public class CalloutLibrary : ScriptableObject
    {
        [Serializable]
        public class Entry
        {
            public CalloutId id;
            public string jp;
            public string en;
            public Color color = Color.white;
            public Sprite composite;
            public Sprite text;
            public Sprite burst;
            public bool tintBurst;
            public AudioClip[] voices = Array.Empty<AudioClip>();
            public float scale = 1f;
        }

        public List<Entry> entries = new List<Entry>();
        public Sprite[] splats = Array.Empty<Sprite>();
        public Sprite speedLines;
        public Sprite halftone;
        public AudioClip popSfx;
        public AudioClip bigPopSfx;
        public AudioClip failSfx;

        Dictionary<CalloutId, Entry> map;

        public Entry Get(CalloutId id)
        {
            if (map == null)
            {
                map = new Dictionary<CalloutId, Entry>();
                foreach (var e in entries) map[e.id] = e;
            }
            map.TryGetValue(id, out var r);
            return r;
        }

        static CalloutLibrary _instance;
        public static CalloutLibrary Instance => _instance ??= Resources.Load<CalloutLibrary>("CalloutLibrary");

        public static readonly (CalloutId id, string jp, string en, string hex)[] Defaults =
        {
            (CalloutId.Nice, "ナイス！", "NICE!", "#B6FF3B"),
            (CalloutId.Good, "成功！", "SUCCESS!", "#00E5FF"),
            (CalloutId.Great, "グレートドリフト！", "GREAT DRIFT!", "#FFE600"),
            (CalloutId.Awesome, "すごい！", "AWESOME!", "#FF2D7A"),
            (CalloutId.Insane, "やばい！！", "INSANE!!", "#FF2D7A"),
            (CalloutId.Perfect, "完璧！", "PERFECT!", "#FFE600"),
            (CalloutId.God, "神ドリフト！！", "GOD DRIFT!!", "#FF3B30"),
            (CalloutId.Fail, "失敗…", "FAIL...", "#FF3B30"),
            (CalloutId.BestLap, "最高！", "BEST LAP!", "#FFE600"),
            (CalloutId.NewRecord, "新記録！", "NEW RECORD!", "#FF2D7A"),
            (CalloutId.Start, "スタート！", "START!", "#00E5FF"),
            (CalloutId.Count3, "さん！", "3", "#FF3B30"),
            (CalloutId.Count2, "に！", "2", "#FFE600"),
            (CalloutId.Count1, "いち！", "1", "#00E5FF"),
            (CalloutId.Go, "ゴー！！", "GO!!", "#B6FF3B"),
            (CalloutId.FinalLap, "ファイナルラップ！", "FINAL LAP!", "#FF2D7A"),
            (CalloutId.Goal, "ゴール！", "GOAL!", "#FFE600"),
            (CalloutId.DriftKing, "ドリフトキング！", "DRIFT KING!", "#FF3B30"),
            (CalloutId.Ikee, "いけー！", "GO GO GO!", "#B6FF3B"),
            (CalloutId.NearMiss, "ニアミス！", "NEAR MISS!", "#00E5FF"),
            (CalloutId.Overtake, "オーバーテイク！", "OVERTAKE!", "#FFE600"),
        };

        public static string FileId(CalloutId id) => id switch
        {
            CalloutId.Nice => "nice", CalloutId.Good => "good", CalloutId.Great => "great", CalloutId.Awesome => "awesome",
            CalloutId.Insane => "insane", CalloutId.Perfect => "perfect", CalloutId.God => "god", CalloutId.Fail => "fail",
            CalloutId.BestLap => "best_lap", CalloutId.NewRecord => "new_record", CalloutId.Start => "start",
            CalloutId.Count3 => "count_3", CalloutId.Count2 => "count_2", CalloutId.Count1 => "count_1", CalloutId.Go => "go",
            CalloutId.FinalLap => "final_lap", CalloutId.Goal => "goal", CalloutId.DriftKing => "drift_king",
            CalloutId.Ikee => "ikee", CalloutId.NearMiss => "near_miss", CalloutId.Overtake => "overtake",
            _ => id.ToString().ToLowerInvariant()
        };
    }
}
