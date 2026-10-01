<p align="center"><img src="Docs/media/logo.png" alt="INK DRIFT: TOKYO" width="820"></p>

<p align="center"><b>A comic-book cel-shaded drift racer through Tokyo.</b><br>
Neon canyons, elevated expressways and autumn mountain passes — rendered like a manga panel, driven like a sim.</p>

<p align="center">
<a href="../../releases/latest"><b>⬇ Download for macOS · Windows · Linux</b></a> ·
<a href="https://github.com/gazhenko/ink-drift-tokyo/releases/download/v1.0.0/INK-DRIFT-TOKYO-trailer.mp4"><b>▶ Watch the trailer</b></a>
</p>

<p align="center"><a href="https://github.com/gazhenko/ink-drift-tokyo/releases/download/v1.0.0/INK-DRIFT-TOKYO-trailer.mp4"><img src="Docs/media/teaser.gif" alt="gameplay teaser — click for the full trailer" width="900"></a></p>

| SHIBUYA NEON · 渋谷ネオン | SHUTO C1 LOOP · 首都高C1 | OKUTAMA TOUGE · 奥多摩峠 |
|---|---|---|
| <img src="Docs/media/shibuya.png" width="300"> | <img src="Docs/media/shuto.png" width="300"> | <img src="Docs/media/okutama.png" width="300"> |

---

## What it is

**INK DRIFT: TOKYO** is a playable demo built in Unity 6 (URP). Every pixel goes through a custom toon pipeline —
banded light, screen-space ink outlines, halftone screentone in the shadows, aggressive color grading — on top of
PBR-textured, densely dressed environments. Drifting is physical and hard: rear tires have to be *broken loose*
with weight transfer, handbrake or a clutch kick, then balanced with throttle and counter-steer.

Pop a good drift and Tokyo shouts at you: graffiti comic callouts burst onto the screen — **ナイス！ 成功！
グレートドリフト！ すごい！ やばい！！ 完璧！ 神ドリフト！！** — with a Japanese announcer voice.

### Features
- **3 tracks**
  - **SHIBUYA NEON 渋谷ネオン** — night, rain-soaked streets with real-time planar reflections of the neon, 90° intersections with side streets, a sakura-lined canal.
  - **SHUTO C1 LOOP 首都高C1** — elevated expressway at sunset over a dense city, sweepers, a sodium-lit tunnel, live traffic for near-misses.
  - **OKUTAMA TOUGE 奥多摩峠** — western Tokyo's mountain pass in autumn: stacked switchback hairpins, cedar forest, burning momiji, a river gorge.
- **5 cars** — fictional look-alikes of current Japanese sports cars with loud "ricer" kits (GT wings, splitters, canards, livery):
  HACHI GR8 · KAIJU SPR-X · ZENKAI Z · RAIJIN BX-R (AWD) · TSUBAME RS. 8 paints each.
- **Drift physics** — raycast suspension with anti-roll bars, combined-slip tire model (wheelspin eats lateral grip → real
  power oversteer), two-inertia clutch (clutch kicks work), locked drift diff, turbo spool + blow-off, rev limiter, auto/manual gearbox.
  Three assist levels from PRO (none) to EASY.
- **Drift scoring** — angle × speed × combo multiplier; multiplier grows with sustained drifts and direction switches;
  wall-proximity "CLOSE!" bonus; touch a wall and the chain is lost (失敗…).
- **Modes** — Drift Attack (score), Rival Battle (5 AI rivals who drift too), Free Run.
- **Procedural engine audio** per car (boxer rumble, inline-six scream, V6 growl), turbo whistle, blow-off flutter, pops & bangs;
  original synthesized eurobeat/city-pop soundtrack. The announcer is Japanese TTS (regenerate with ElevenLabs via
  `Tools/audio/elevenlabs_voices.py`).
- Keyboard and gamepad.

## Controls

| | Keyboard | Gamepad |
|---|---|---|
| Throttle / Brake | W / S (or ↑ / ↓) | RT / LT |
| Steer | A / D (or ← / →) | Left stick |
| Handbrake | Space | A / Cross |
| Clutch (kick!) | Left Shift | X / Square |
| Shift up / down (manual) | E / Q | RB / LB |
| Camera | C | Y / Triangle |
| Look back | B | R-stick click |
| Reset car | R | View / Select |
| Pause | Esc | Start |

**Drifting 101:** brake into the corner to load the nose → flick or tap the handbrake → throttle to keep the rear
spinning → counter-steer and *steer where you want the car to go* → modulate throttle to hold the angle.
Clutch-kick (hold Shift with throttle, release) to snap the rear loose mid-corner.

## Running the builds
- **macOS** (Apple Silicon + Intel): unzip, right-click `INK DRIFT TOKYO.app` → Open (the build is unsigned).
  If macOS says it's damaged: `xattr -dr com.apple.quarantine "INK DRIFT TOKYO.app"`.
- **Windows** (x64): unzip and run `InkDriftTokyo.exe`.
- **Linux** (x64): unzip, `chmod +x InkDriftTokyo.x86_64 && ./InkDriftTokyo.x86_64` (Vulkan or OpenGL 4.5).

## Building from source
Requirements: Unity **6000.3.25f1** (6.3 LTS) with Windows/Linux build support, Blender 5.2 (only to regenerate models), Python 3.12+.

```bash
Tools/pipeline.sh setup     # configure URP, input, quality, layers
Tools/pipeline.sh content   # import → prefabs → resources → generate the 3 track scenes + menu
Tools/pipeline.sh build     # macOS / Windows / Linux players into Builds/
```
Everything in the world is generated from code: `Game/Assets/InkDrift/Scripts/Editor/Track/*` builds the tracks from
`Tools/tracks/layouts.json`; props and foliage are built in Blender by `Tools/blender/**`; textures/signs/callouts by
`Tools/art/**`.

## Tech notes
- URP Forward+, custom HLSL toon shader (`InkDrift/Toon`) with banded main + additional lights, screen-space halftone,
  banded reflections, rim light, wind, vertex AO; full-screen ink outline pass (depth + normals); custom sky, water and terrain shaders.
- GPU-instanced foliage renderer (thousands of cedars with LODs), procedural city blocks with sign atlases, real-time planar reflections.
- Trailer captured in-engine by `TrailerDirector` (fixed-timestep frame capture + `AudioRenderer`) and cut with ffmpeg.

## Credits
All third-party assets are CC0 / OFL — see [CREDITS.md](CREDITS.md). The five hero cars and four traffic vehicles are
original procedural models built in Blender for this project (fictional look-alikes; no manufacturer names, badges or
logos). All brands, shops and billboards in the game are fictional.

Code: MIT (see [LICENSE](LICENSE)).
