using UnityEditor;
using UnityEngine;

namespace InkDrift.EditorTools
{
    /// <summary>Headless content pipeline entry points (see Tools/pipeline.sh).</summary>
    public static class Pipeline
    {
        [MenuItem("InkDrift/Pipeline/Build Content")]
        public static void Content()
        {
            Step("Core materials", MaterialLibrary.BuildCore);
            Step("Prefabs", PrefabBuilder.BuildAll);
            Step("Car prefabs", CarPrefabBuilder.BuildAll);
            Step("Resources", ResourcesBuilder.BuildAll);
            if (!CommandLine.Has("-skipTracks")) Step("Tracks", TrackGenerator.GenerateFromCommandLine);
            Step("Menu", MenuSceneBuilder.Build);
            Step("TestPad", TestPadBuilder.Build);
            AssetDatabase.SaveAssets();
            if (Application.isBatchMode) EditorApplication.Exit(0);
        }

        static void Step(string name, System.Action a)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            try { a(); Debug.Log($"[Pipeline] {name} OK ({sw.Elapsed.TotalSeconds:0.0}s)"); }
            catch (System.Exception e)
            {
                Debug.LogError($"[Pipeline] {name} FAILED: {e}");
                if (Application.isBatchMode) EditorApplication.Exit(2);
                throw;
            }
        }
    }
}
