using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.XInput;
using UnityEngine.SceneManagement;

namespace InkDrift
{
    /// <summary>
    /// Command-line driven verification captures for builds:
    ///   -scene Track_shibuya   load a scene directly
    ///   -car kaiju -mode battle  session overrides
    ///   -autopilot             AI drives the player car
    ///   -shots dir -shotTimes 4,8,12  write screenshots at those seconds then quit
    ///   -telemetry file.csv    log player telemetry each physics step
    ///   -fakePad [-padLabels 0..3]  add a simulated Xbox pad and switch prompts to it (UI screenshots without hardware)
    /// </summary>
    public class DevCapture : MonoBehaviour
    {
        static DevCapture _i;
        StreamWriter telemetry;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (_i != null) return;
            bool any = CommandLine.Has("-shots") || CommandLine.Has("-scene") || CommandLine.Has("-autopilot") || CommandLine.Has("-telemetry") || CommandLine.Has("-record") || CommandLine.Has("-fakePad");
            if (!any) return;
            var g = new GameObject("DevCapture");
            DontDestroyOnLoad(g);
            _i = g.AddComponent<DevCapture>();
        }

        /// <summary>Adds a simulated pad and taps R3 so menus switch to controller prompts.</summary>
        static IEnumerator FakePad()
        {
            var pad = InputSystem.AddDevice<XInputController>("FakePad");
            yield return new WaitForSecondsRealtime(0.5f);
            InputSystem.QueueStateEvent(pad, new GamepadState().WithButton(GamepadButton.RightStick));
            yield return null; yield return null;
            InputSystem.QueueStateEvent(pad, new GamepadState());
        }

        static IEnumerator DevPause(float at)
        {
            yield return new WaitForSeconds(at);
            RaceManager.I?.DevPause(CommandLine.Has("-pauseControls"));
        }

        IEnumerator Start()
        {
            float maxRun = CommandLine.GetFloat("-quitAfter", 180f);
            Invoke(nameof(Bail), maxRun);
            string car = CommandLine.Get("-car");
            if (car != null) GameSession.CarId = car;
            string mode = CommandLine.Get("-mode");
            if (mode != null) GameSession.Mode = mode == "battle" ? GameMode.Battle : mode == "free" ? GameMode.FreeRun : GameMode.DriftAttack;
            GameSession.PaintIndex = (int)CommandLine.GetFloat("-paint", GameSession.PaintIndex);
            if (CommandLine.Has("-padLabels")) GameSession.PadLabels = (int)CommandLine.GetFloat("-padLabels", 0);
            if (CommandLine.Has("-fakePad")) StartCoroutine(FakePad());
            string scene = CommandLine.Get("-scene");
            if (scene != null && SceneManager.GetActiveScene().name != scene)
            {
                SceneManager.LoadScene(scene);
                yield return null; yield return null;
            }
            ApplyDebugFlags();
            if (CommandLine.Has("-autopilot"))
            {
                yield return new WaitForSeconds(0.2f);
                var rb = RaceBootstrap.I;
                if (rb != null && rb.Player != null)
                {
                    var pd = rb.Player.GetComponent<PlayerDriver>();
                    if (pd) Destroy(pd);
                    var ai = rb.Player.gameObject.AddComponent<AIDriver>();
                    ai.rubberBand = false; ai.driftStyle = true; ai.skill = 1f;
                    rb.Player.assistLevel = 0;
                }
            }
            if (CommandLine.Has("-pause")) StartCoroutine(DevPause(CommandLine.GetFloat("-pause", 6f)));
            string tel = CommandLine.Get("-telemetry");
            if (tel != null)
            {
                try { telemetry = new StreamWriter(Path.GetFullPath(tel)); }
                catch (System.Exception e) { Debug.LogError("[DevCapture] telemetry: " + e.Message); }
                telemetry?.WriteLine("t,x,y,z,speed_kmh,rpm,gear,drift_angle,yaw_rate,throttle,brake,steer,hb,grounded,score");
            }
            string rec = CommandLine.Get("-record");
            if (rec != null)
            {
                // generic fixed-timestep frame recorder for any scene (menu showcase etc.)
                Directory.CreateDirectory(rec);
                int fps = (int)CommandLine.GetFloat("-recordFps", 60);
                float secs = CommandLine.GetFloat("-recordSec", 6f);
                yield return new WaitForSeconds(CommandLine.GetFloat("-recordDelay", 1.5f));
                Time.captureDeltaTime = 1f / fps;
                int frames = Mathf.RoundToInt(secs * fps);
                for (int f = 0; f < frames; f++)
                {
                    yield return new WaitForEndOfFrame();
                    var tex = ScreenCapture.CaptureScreenshotAsTexture();
                    File.WriteAllBytes(Path.Combine(rec, $"f_{f:00000}.jpg"), tex.EncodeToJPG(93));
                    Destroy(tex);
                }
                Time.captureDeltaTime = 0f;
                Application.Quit();
                yield break;
            }
            string dir = TrailerDirector.Requested ? null : CommandLine.Get("-shots");   // -trailer reuses -shots for its shot list
            if (dir != null)
            {
                Directory.CreateDirectory(dir);
                string times = CommandLine.Get("-shotTimes", "3,6,9");
                float start = Time.unscaledTime;   // real time: shots also work while paused
                int n = 0;
                foreach (var s in times.Split(','))
                {
                    float t = float.Parse(s, System.Globalization.CultureInfo.InvariantCulture);
                    while (Time.unscaledTime - start < t) yield return null;
                    yield return new WaitForEndOfFrame();
                    var cam = Camera.main;
                    string path = Path.Combine(dir, $"shot_{n++:00}_{SceneManager.GetActiveScene().name}.png");
                    ScreenCapture.CaptureScreenshot(path);
                    yield return null;
                }
                yield return new WaitForSecondsRealtime(0.5f);
                telemetry?.Close();
                Application.Quit();
            }
        }

        /// <summary>Feature toggles for render debugging: -dbgNoPost -dbgNoBloom -dbgNoLights -dbgNoReflect -dbgNoInk -dbgNoHud</summary>
        static void ApplyDebugFlags()
        {
            if (CommandLine.Has("-dbgNoPost"))
                foreach (var v in FindObjectsByType<UnityEngine.Rendering.Volume>(FindObjectsSortMode.None)) v.weight = 0f;
            if (CommandLine.Has("-dbgNoBloom"))
                foreach (var v in FindObjectsByType<UnityEngine.Rendering.Volume>(FindObjectsSortMode.None))
                    if (v.sharedProfile != null && v.sharedProfile.TryGet<UnityEngine.Rendering.Universal.Bloom>(out var b)) b.active = false;
            if (CommandLine.Has("-dbgNoLights"))
                foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None)) if (l.type != LightType.Directional) l.enabled = false;
            if (CommandLine.Has("-dbgNoReflect"))
                foreach (var p in FindObjectsByType<PlanarReflection>(FindObjectsSortMode.None)) p.enabled = false;
            if (CommandLine.Has("-dbgNoInk")) Shader.SetGlobalColor("_InkColor", new Color(0, 0, 0, 0));
            if (CommandLine.Has("-dbgNoHud"))
                foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None)) c.enabled = false;
        }

        // -dbgCam "d,height,lateral,lookAhead[,fov]" : fixed camera at a track distance (for scenery review)
        bool camApplied;
        void FixedCam()
        {
            string spec = CommandLine.Get("-dbgCam");
            if (spec == null || TrackPath.Active == null || Camera.main == null) return;
            var f = System.Array.ConvertAll(spec.Split(','), x => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture));
            var path = TrackPath.Active;
            float d = f[0], h = f.Length > 1 ? f[1] : 3f, lat = f.Length > 2 ? f[2] : 0f, ahead = f.Length > 3 ? f[3] : 25f;
            var cam = Camera.main;
            var chase = cam.GetComponent<ChaseCamera>(); if (chase) chase.enabled = false;
            Vector3 p = path.PointAt(d) + path.RightAt(d) * lat + Vector3.up * h;
            Vector3 look = path.PointAt(d + ahead) + Vector3.up * 1.5f;
            cam.transform.SetPositionAndRotation(p, Quaternion.LookRotation(look - p));
            if (f.Length > 4) cam.fieldOfView = f[4];
        }

        void LateUpdate()
        {
            if (CommandLine.Has("-dbgCam")) FixedCam();
            if (CommandLine.Has("-dbgNoInk")) Shader.SetGlobalColor("_InkColor", new Color(0, 0, 0, 0));
            if (CommandLine.Has("-dbgNoEnvRefl")) RenderSettings.reflectionIntensity = 0f;   // dev: isolate environment reflections
            if (CommandLine.Has("-dbgNoAddLights") && Time.frameCount % 30 == 0)               // dev: isolate point/spot lights
                foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None)) if (l.type != LightType.Directional) l.enabled = false;
            if (CommandLine.Has("-dbgNoHud") && Time.frameCount % 30 == 0)
                foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None)) c.enabled = false;
        }

        void FixedUpdate()
        {
            if (telemetry == null) return;
            var rb = RaceBootstrap.I;
            if (rb == null || rb.Player == null) return;
            var c = rb.Player;
            var p = c.transform.position;
            telemetry.WriteLine(string.Format(System.Globalization.CultureInfo.InvariantCulture,
                "{0:F3},{1:F2},{2:F2},{3:F2},{4:F1},{5:F0},{6},{7:F1},{8:F3},{9:F2},{10:F2},{11:F2},{12},{13},{14}",
                Time.time, p.x, p.y, p.z, c.SpeedKmh, c.EngineRpm, c.Gear, c.DriftAngle, c.YawRate, c.input.throttle, c.input.brake, c.input.steer,
                c.input.handbrake ? 1 : 0, c.GroundedWheels, rb.Scorer != null ? rb.Scorer.TotalScore : 0));
        }

        void Bail() { Debug.LogWarning("[DevCapture] -quitAfter reached"); telemetry?.Close(); Application.Quit(); }

        void OnApplicationQuit() { telemetry?.Close(); }
    }
}
