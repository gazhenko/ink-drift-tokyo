using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace InkDrift.EditorTools
{
    /// <summary>Builds Resources: CalloutLibrary (sprites + voices), FontSet (dynamic TMP fonts), UI sprites, audio.</summary>
    public static class ResourcesBuilder
    {
        const string Res = "Assets/InkDrift/Resources";

        [MenuItem("InkDrift/Setup/Build Resources")]
        public static void BuildAll()
        {
            Directory.CreateDirectory(Res);
            Directory.CreateDirectory(Res + "/UI");
            Directory.CreateDirectory(Res + "/Audio/UI");
            Directory.CreateDirectory(Res + "/Music");
            Directory.CreateDirectory(Res + "/Cars");
            Directory.CreateDirectory(Res + "/Traffic");
            AssetDatabase.Refresh();
            CopyUISprites();
            CopyAudio();
            BuildFonts();
            BuildCallouts();
            AssetDatabase.SaveAssets();
            Debug.Log("[Resources] built");
        }

        static void CopyIfExists(string src, string dst)
        {
            if (!File.Exists(Path.GetFullPath(src))) return;
            if (File.Exists(Path.GetFullPath(dst))) AssetDatabase.DeleteAsset(dst);
            AssetDatabase.CopyAsset(src, dst);
        }

        static void CopyUISprites()
        {
            string ui = "Assets/InkDrift/Art/UI";
            foreach (var n in new[] { "logo_inkdrift", "rank_S", "rank_A", "rank_B", "rank_C", "rank_D", "speedlines_radial", "icon" })
                CopyIfExists($"{ui}/{n}.png", $"{Res}/UI/{n}.png");
            // track previews (screenshots captured from builds)
            if (Directory.Exists(Path.GetFullPath("Assets/InkDrift/Art/Previews")))
                foreach (var f in Directory.GetFiles(Path.GetFullPath("Assets/InkDrift/Art/Previews"), "track_*.png", SearchOption.TopDirectoryOnly).Select(Path.GetFileName))
                    CopyIfExists($"Assets/InkDrift/Art/Previews/{f}", $"{Res}/UI/{f}");
            AssetDatabase.Refresh();
            foreach (var p in Directory.GetFiles(Path.GetFullPath(Res + "/UI"), "*.png"))
            {
                string ap = Res + "/UI/" + Path.GetFileName(p);
                var ti = (TextureImporter)AssetImporter.GetAtPath(ap);
                if (ti == null) continue;
                ti.textureType = TextureImporterType.Sprite; ti.mipmapEnabled = false; ti.alphaIsTransparency = true; ti.maxTextureSize = 4096;
                ti.SaveAndReimport();
            }
        }

        static void CopyAudio()
        {
            // voice + sfx live under Art/../Audio; music + ui sounds are copied into Resources for runtime loading
            string a = "Assets/InkDrift/Audio";
            if (Directory.Exists(Path.GetFullPath(a + "/Music")))
                foreach (var f in Directory.GetFiles(Path.GetFullPath(a + "/Music")).Where(f => f.EndsWith(".ogg") || f.EndsWith(".wav") || f.EndsWith(".mp3")))
                    CopyIfExists($"{a}/Music/{Path.GetFileName(f)}", $"{Res}/Music/{Path.GetFileName(f)}");
            if (Directory.Exists(Path.GetFullPath(a + "/SFX")))
                foreach (var f in Directory.GetFiles(Path.GetFullPath(a + "/SFX")).Where(f => f.EndsWith(".ogg") || f.EndsWith(".wav") || f.EndsWith(".mp3")))
                {
                    string n = Path.GetFileName(f);
                    string dst = n.StartsWith("ui_") ? $"{Res}/Audio/UI/{n}" : $"{Res}/Audio/{n}";
                    CopyIfExists($"{a}/SFX/{n}", dst);
                }
        }

        static TMP_FontAsset Font(string ttf, string name, int size = 90)
        {
            string fontPath = $"Assets/InkDrift/Art/Fonts/{ttf}";
            var font = AssetDatabase.LoadAssetAtPath<Font>(fontPath);
            if (font == null) { Debug.LogWarning("missing font " + ttf); return null; }
            string outPath = $"{Res}/Fonts/{name}.asset";
            Directory.CreateDirectory(Res + "/Fonts");
            var existing = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(outPath);
            if (existing != null) return existing;
            var fa = TMP_FontAsset.CreateFontAsset(font, size, 9, GlyphRenderMode.SDFAA, 2048, 2048, AtlasPopulationMode.Dynamic, true);
            fa.name = name;
            AssetDatabase.CreateAsset(fa, outPath);
            // persist the generated atlas texture + material as sub-assets
            if (fa.atlasTextures != null)
                foreach (var tex in fa.atlasTextures) if (tex != null) { tex.name = name + " Atlas"; AssetDatabase.AddObjectToAsset(tex, fa); }
            if (fa.material != null) { fa.material.name = name + " Material"; AssetDatabase.AddObjectToAsset(fa.material, fa); }
            EditorUtility.SetDirty(fa);
            return fa;
        }

        static void BuildFonts()
        {
            var set = AssetDatabase.LoadAssetAtPath<FontSet>($"{Res}/FontSet.asset");
            if (set == null) { set = ScriptableObject.CreateInstance<FontSet>(); AssetDatabase.CreateAsset(set, $"{Res}/FontSet.asset"); }
            set.comic = Font("Bangers-Regular.ttf", "Bangers SDF");
            set.hud = Font("ChakraPetch-Bold.ttf", "ChakraPetch Bold SDF");
            set.hudRegular = Font("ChakraPetch-Regular.ttf", "ChakraPetch SDF");
            set.jpHeavy = Font("DelaGothicOne-Regular.ttf", "DelaGothicOne SDF");
            set.jpOutline = Font("RampartOne-Regular.ttf", "RampartOne SDF");
            set.jpGraffiti = Font("ReggaeOne-Regular.ttf", "ReggaeOne SDF");
            set.jpBody = Font("NotoSansJP-Bold.ttf", "NotoSansJP SDF");
            // JP fallback for every latin font so mixed strings render
            foreach (var f in new[] { set.comic, set.hud, set.hudRegular })
            {
                if (f == null) continue;
                f.fallbackFontAssetTable ??= new System.Collections.Generic.List<TMP_FontAsset>();
                if (set.jpBody != null && !f.fallbackFontAssetTable.Contains(set.jpBody)) f.fallbackFontAssetTable.Add(set.jpBody);
                EditorUtility.SetDirty(f);
            }
            foreach (var f in new[] { set.jpHeavy, set.jpOutline, set.jpGraffiti })
            {
                if (f == null || set.jpBody == null) continue;
                f.fallbackFontAssetTable ??= new System.Collections.Generic.List<TMP_FontAsset>();
                if (!f.fallbackFontAssetTable.Contains(set.jpBody)) f.fallbackFontAssetTable.Add(set.jpBody);
                EditorUtility.SetDirty(f);
            }
            EditorUtility.SetDirty(set);
            // make Bangers the TMP default so stray texts are on-style
            var settings = Resources.Load<TMP_Settings>("TMP Settings");
            if (settings != null && set.comic != null)
            {
                var so = new SerializedObject(settings);
                so.FindProperty("m_defaultFontAsset").objectReferenceValue = set.comic;
                so.ApplyModifiedPropertiesWithoutUndo();
            }
        }

        static void BuildCallouts()
        {
            var lib = AssetDatabase.LoadAssetAtPath<CalloutLibrary>($"{Res}/CalloutLibrary.asset");
            if (lib == null) { lib = ScriptableObject.CreateInstance<CalloutLibrary>(); AssetDatabase.CreateAsset(lib, $"{Res}/CalloutLibrary.asset"); }
            lib.entries.Clear();
            string dir = "Assets/InkDrift/Art/Callouts";
            string voiceDir = "Assets/InkDrift/Audio/Voice";
            Sprite S(string p) => AssetDatabase.LoadAssetAtPath<Sprite>(p);
            foreach (var d in CalloutLibrary.Defaults)
            {
                string id = CalloutLibrary.FileId(d.id);
                ColorUtility.TryParseHtmlString(d.hex, out var col);
                var e = new CalloutLibrary.Entry
                {
                    id = d.id, jp = d.jp, en = d.en, color = col,
                    composite = S($"{dir}/callout_{id}.png"),
                    text = null,   // the composite already contains burst + text; animated as one piece
                    burst = null,
                };
                var voices = Directory.Exists(Path.GetFullPath(voiceDir))
                    ? Directory.GetFiles(Path.GetFullPath(voiceDir), $"vo_{id}_*.*").Where(f => !f.EndsWith(".meta")).Select(f => AssetDatabase.LoadAssetAtPath<AudioClip>($"{voiceDir}/{Path.GetFileName(f)}")).Where(c => c != null).ToArray()
                    : new AudioClip[0];
                e.voices = voices;
                lib.entries.Add(e);
            }
            lib.splats = Directory.Exists(Path.GetFullPath("Assets/InkDrift/Art/UI"))
                ? Directory.GetFiles(Path.GetFullPath("Assets/InkDrift/Art/UI"), "splat_*.png").Select(f => S("Assets/InkDrift/Art/UI/" + Path.GetFileName(f))).Where(s => s != null).ToArray()
                : new Sprite[0];
            lib.speedLines = S("Assets/InkDrift/Art/UI/speedlines_radial.png");
            lib.popSfx = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/InkDrift/Audio/SFX/callout_pop.wav");
            lib.bigPopSfx = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/InkDrift/Audio/SFX/callout_bigpop.wav");
            lib.failSfx = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/InkDrift/Audio/SFX/callout_fail.wav");
            EditorUtility.SetDirty(lib);
        }
    }
}
