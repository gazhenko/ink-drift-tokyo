# INK DRIFT: TOKYO — Design Contract

Shared spec for everyone (human or agent) producing code/assets for this repo.
Paths are relative to repo root. Unity project lives in `Game/`.

## Pillars
1. **Comic-book cel shading over realistic content.** Real-world proportions, PBR-grade textures and
   dense detail, rendered through a toon pipeline: 2–3 hard light bands, thick ink outlines,
   halftone dots in shadow, saturated grading, bloom on neon.
2. **Intense, difficult drifting.** Sim-leaning RWD/AWD tire model; drifting must be *earned*
   (clutch kick, handbrake, weight transfer, counter-steer). Assists are optional.
3. **Loud reward.** Good drifts trigger pop-out graffiti/comic callouts (Japanese + English
   subtitle) with an energetic Japanese female voice shouting the line.

## Palette (sRGB hex)
| Token        | Hex       | Use |
|--------------|-----------|-----|
| ink          | `#0B0B12` | outlines, text stroke |
| paper        | `#FFF8E7` | comic paper white, inner stroke |
| hot-magenta  | `#FF2D7A` | primary accent, callouts |
| electric-cyan| `#00E5FF` | secondary accent, neon |
| acid-yellow  | `#FFE600` | highlights, "GREAT" tier |
| signal-red   | `#FF3B30` | danger, "GOD" tier, fail |
| deep-indigo  | `#1B1340` | night shadow tint |
| sakura       | `#FFB7D5` | foliage accent |
| lime         | `#B6FF3B` | "NICE" tier |

## Typography (all SIL OFL, from google/fonts)
- **Dela Gothic One** – heavy Japanese display (callouts, titles)
- **Rampart One** – 3D-outlined Japanese (secondary callouts)
- **Reggae One** – graffiti-ish Japanese (signs, decals)
- **Bangers** – comic English (subtitles under callouts, menus)
- **Chakra Petch** (Bold) – HUD numerals / telemetry
- **Noto Sans JP** (Black/Bold) – fallback for UI and signage
Fonts live in `Game/Assets/InkDrift/Art/Fonts/` with their OFL.txt.

## Drift callout tiers
Triggered at end of a drift chain (or mid-chain when crossing a threshold).
| Tier | Score ≥ | JP | Romaji | EN subtitle | Color |
|------|---------|----|--------|-------------|-------|
| NICE    | 1 500  | ナイス！         | naisu!         | NICE!          | lime |
| GOOD    | 4 000  | 成功！           | seikō!         | SUCCESS!       | electric-cyan |
| GREAT   | 8 000  | グレートドリフト！| gurēto dorifuto| GREAT DRIFT!   | acid-yellow |
| AWESOME | 15 000 | すごい！         | sugoi!         | AWESOME!       | hot-magenta |
| INSANE  | 25 000 | やばい！！       | yabai!!        | INSANE!!       | hot-magenta |
| PERFECT | 40 000 | 完璧！           | kanpeki!       | PERFECT!       | acid-yellow |
| GOD     | 60 000 | 神ドリフト！！   | kami dorifuto  | GOD DRIFT!!    | signal-red |
Event callouts: 失敗… (shippai… / FAIL — wall hit), 最高！ (saikō / BEST LAP), 新記録！ (shin kiroku /
NEW RECORD), スタート！/ さん・に・いち・ゴー！ (countdown), ファイナルラップ！ (FINAL LAP),
ゴール！ (GOAL), ドリフトキング！ (DRIFT KING — results S rank), いけー！ (GO!! — combo x5),
ニアミス！ (NEAR MISS — traffic), オーバーテイク！ (OVERTAKE).

## Cars (fictional look-alikes, no OEM names/logos anywhere)
| ID | Display name | Inspired by | Drive | Character |
|----|--------------|-------------|-------|-----------|
| hachi    | HACHI GR8      | Toyota GR86 (ZN8)       | FR  | light, balanced, beginner drift |
| kaiju    | KAIJU SPR-X    | Toyota GR Supra (A90)   | FR  | big turbo I6, snappy |
| zenkai   | ZENKAI Z       | Nissan Z (RZ34)         | FR  | twin-turbo V6, torquey |
| raijin   | RAIJIN BX-R    | Subaru WRX (VB)         | AWD | turbo boxer, rally power-slides |
| tsubame  | TSUBAME RS     | Mazda MX-5 (ND)         | FR  | featherweight, twitchy |
"Ricer" kit per car: GT wing, front splitter, canards, side skirts, wide wheels with stretched
tires, underglow, a livery with Japanese graffiti decals.

## Tracks
| ID | Name | JP | Time of day | Character |
|----|------|----|-------------|-----------|
| shibuya | SHIBUYA NEON     | 渋谷ネオン   | night, wet    | tight 90s, neon canyon, sakura canal |
| shuto   | SHUTO C1 LOOP    | 首都高C1     | sunset        | elevated expressway, sweepers, tunnels, traffic |
| okutama | OKUTAMA TOUGE    | 奥多摩峠     | autumn golden hour | mountain pass, hairpins, cedar forest, momiji |

## Asset conventions
- Units: meters, Y-up in Unity (Blender exports FBX with `-Z forward, Y up`, apply transforms).
- Textures: power-of-two, albedo as sRGB PNG/JPG, normal maps OpenGL-style (+Y), names
  `<name>_albedo`, `_normal`, `_mask` (R=metal, G=AO, B=unused, A=smoothness), `_emission`.
- Car FBX hierarchy: `CarRoot/Body`, `CarRoot/Wheel_FL|FR|RL|RR` (pivot at hub center),
  `CarRoot/Caliper_*`, `CarRoot/Light_Head_L|R`, `CarRoot/Light_Tail_L|R`, `CarRoot/Wing`.
  Car faces +Z (forward) in Unity, origin on ground plane at car center.
- Every third-party asset is listed in `CREDITS.md` with author, source URL, and license.
  Only CC0 / CC-BY / OFL assets are allowed.
