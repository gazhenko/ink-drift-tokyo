using System;

namespace InkDrift
{
    /// <summary>Tiny command-line reader for dev/trailer/screenshot modes (e.g. -trailer, -shot out.png).</summary>
    public static class CommandLine
    {
        static string[] args;
        static string[] Args => args ??= Environment.GetCommandLineArgs();

        public static bool Has(string flag)
        {
            foreach (var a in Args) if (string.Equals(a, flag, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public static string Get(string flag, string fallback = null)
        {
            var a = Args;
            for (int i = 0; i < a.Length - 1; i++)
                if (string.Equals(a[i], flag, StringComparison.OrdinalIgnoreCase)) return a[i + 1];
            return fallback;
        }

        public static float GetFloat(string flag, float fallback)
        {
            var s = Get(flag);
            return s != null && float.TryParse(s, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var f) ? f : fallback;
        }
    }
}
