# INK DRIFT: TOKYO — v1.5.0: photo-scanned driver and cockpit

A comic-book cel-shaded drift racer through Tokyo. **Watch the trailer:** [INK-DRIFT-TOKYO-trailer.mp4](https://github.com/gazhenko/ink-drift-tokyo/releases/download/v1.0.0/INK-DRIFT-TOKYO-trailer.mp4).

## What's new in 1.5.0
- **Photo-scanned materials.** The driver's gloves and suit now use CC0 photo-scans from Poly Haven at their real-world scale:
  - full-grain leather for the glove backs and knuckle guards
  - scanned suede for the palms, with the silicone grip print on top
  - a scanned technical weave under the suit's quilting
  - scanned knit for the cuffs

  Each scan is tinted to the suit colours while keeping its own natural variation.
- **A realistic cockpit around the hands.** The whole interior now uses the same physically based, photo-scanned rendering as the driver, so the hands sit in a consistent realistic space. The game's comic ink filter stays off everything inside the car; the city outside keeps the comic style.
  - grain-embossed dash
  - Alcantara wheel rim, headliner and visors
  - stitched leather door cards
  - herringbone seat fabric and floor carpet
  - brushed metal and chrome fittings
  - a powder-coated roll cage
- **Real shadows across the cockpit:** the wheel, cage and pillars now cast shadows onto the dash and the driver's hands.
- **Interior lighting:** the cabin now blocks reflections of the street the way a real roof and doors do (specular occlusion), so the fabric reads as matte cloth and the leather as satin, even under Shibuya's neon. Cloth reflects almost nothing; metal fittings keep their reflections.
- **Verified on Linux:** the Linux build was run headless on Linux with OpenGL 4.5 software rendering and renders the same in-car view as macOS.

## 1.4.0: a realistic driver
- **Realistic driver shading.** The driver now has its own physically based shader:
  - Realistic lighting with soft shadows, cabin and street lights, and reflections.
  - Cloth sheen on the suit and satin leather on the gloves.
  - The game's comic ink outlines and grain are masked off the driver, so the gloves and sleeves sit in the comic cockpit like a photographed object.
- **Real shadows:** the hands cast shadows onto the wheel, dash and each other, and pick up the car's roof and pillar shadows.
- **Baked detail:**
  - Ambient occlusion, convexity and cavity are baked from the high-detail mesh, so the gaps between fingers, the seams, the cuff edges and the strap all darken naturally.
  - The leather is lightly scuffed on its high points.
- **A truer glove:** smoothed fingertips with no fingernail bumps, double flexion creases across the palm side of every finger joint, and fine wrinkles over the knuckles.
- **A real 9-and-3 grip:**
  - From the driver's seat you see the backs of the gloves, with the logo and red knuckle guards facing you.
  - The index finger is on top, the fingers wrap round the rim and the thumbs hook over it.
  - When a hand lets go to re-grab, it lifts off the rim instead of passing through it.
- **Instrument glow:** the gauges spill a faint warm light onto the gloves and rim at night.

## 1.3.0: the driver
- **A real driver in the in-car view.** The capsule arms are replaced by a fully rigged human model with anatomically correct arms and hands. It is built from the MakeHuman CC0 base mesh with that project's own skeleton and hand-painted skin weights, scaled to a 1.75 m adult.
- **Race suit and gloves, detailed to the stitch:**
  - The suit sleeves are quilted multi-layer Nomex with a contrasting stripe down the top of the arm, fabric folds at the elbow, and embroidered patches.
  - The leather gloves have a pebbled grain, a suede palm with a printed silicone grip, a padded knuckle guard and a flared gauntlet with a Velcro strap and pull tab. Every panel meets at a stitched seam groove.
- **Hands that actually hold things.**
  - Each finger joint curls about its anatomical axis, so the fingers wrap the wheel rim with the thumb over the top.
  - The left hand cups the shift knob and closes round the hydraulic handbrake. Hands open as they let go and close again on the next hold.
  - Two-bone arm IK keeps the elbows hinging the natural way, and the forearm's twist bone shares the wrist roll so the wrist never pinches.
- **Realistic shading for the driver:** a soft light-to-shadow transition and real leather sheen, while the rest of the game keeps its comic look.

## 1.2.0: in-car view
- **In-car camera from the driver's seat.** Press **C / Y / △** to cycle cameras: chase, near chase, **in-car**, roof, bumper. The game remembers your choice.
- **Right-hand drive, like the real Japanese cars.** Each car gets its own cockpit, sized from its windshield, roof and beltline. It includes a deep-dish wheel, an instrument pod with live tach, boost and water gauges, a digital gear and speed readout, a shift-light strip that flashes at the limiter, an H-pattern shifter, a hydraulic handbrake, bucket seats with harnesses, a roll cage in the car's colour, sun visors, door cards, and a rear-view mirror that shows the cars behind you.
- **The driver's arms are rendered and animated.**
  - The hands grip the rim and steer hand over hand.
  - When the wheel snaps back on its own in a drift, it spins through the palms.
  - The left hand moves the gear lever through the H-pattern on every shift and pulls the hydraulic handbrake.
- **The camera feels the car.** Your head moves with braking, acceleration and cornering forces, and turns to look where the car is sliding. Hold look-back to turn round over the seats.
- In the car the HUD drops its speedo and drift meter (the dash shows them) and moves the minimap out of the way.

## 1.1.0: controllers and remapping
- **Controllers work everywhere.** Xbox (360 / One / Series / any XInput pad), DualShock 4, DualSense and Switch Pro are recognised directly. Generic USB/Bluetooth pads that only show up as a joystick are turned into a standard gamepad automatically: DirectInput-mode pads, Xbox-style clones on macOS, and unrecognised pads on Linux.
- **Controller Setup** (Settings ▸ Controls) records any controller's layout one button at a time and remembers it per controller. Use it when a pad's buttons come out wrong, or to map a racing wheel and pedals.
- **Full remapping.** Every driving control has two keyboard keys and one controller input. You set one by pressing it. If that input was already used somewhere else, it's removed there. You can clear or reset a single slot, or reset everything. Bindings are saved between sessions.
- **Button prompts match your device.** Prompts switch between keyboard and controller as you play, and use your controller's own names: A/B/X/Y, ×/○/□/△ or B/A/Y/X.
- **Controller options:** stick dead zone, steering response (linear / smooth / soft), vibration, and button labels. The new **Input test** panel shows live input.
- **Vibration** on tyre slide, the rev limiter and wall hits.
- **Pause menu:** Controls are available mid-race, B / ○ backs out, and unplugging the controller pauses the game.
- Menus: selection no longer jumps between buttons on the car-select screen when changing car or paint with the d-pad. A gamepad user who clicked the mouse gets a selection back.

## Downloads
| Platform | File | Notes |
|---|---|---|
| macOS (Apple Silicon + Intel) | `InkDriftTokyo-v1.5.0-macOS-universal.zip` | Unsigned (ad-hoc). Right-click → Open, or run `xattr -dr com.apple.quarantine "INK DRIFT TOKYO.app"` |
| Windows 10/11 x64 | `InkDriftTokyo-v1.5.0-Windows-x64.zip` | Extract everything into a new folder, run `InkDriftTokyo.exe` (D3D11 default) |
| Linux x64 | `InkDriftTokyo-v1.5.0-Linux-x64.tar.gz` | Extract into a new folder, then `./InkDriftTokyo.x86_64` (Vulkan, OpenGL fallback) |

Checksums: `SHA256SUMS.txt`.

## What's in the demo
- **3 tracks:** SHIBUYA NEON (night, wet neon streets, sakura canal) · SHUTO C1 LOOP (sunset elevated expressway with traffic) · OKUTAMA TOUGE (autumn mountain switchbacks)
- **5 cars**, all fictional ricer-kitted look-alikes: HACHI GR8 · KAIJU SPR-X · ZENKAI Z · RAIJIN BX-R (AWD) · TSUBAME RS — 8 paints each
- **Modes:** Drift Attack · Rival Battle (5 drifting AI rivals) · Free Run
- **Drift physics** with combined-slip tires, clutch kicks, handbrake, weight transfer; assists from PRO (none) to EASY
- **Drift callouts:** graffiti comic pop-ups — ナイス！ 成功！ グレートドリフト！ すごい！ やばい！！ 完璧！ 神ドリフト！！ — with a Japanese announcer voice

## Default controls
| | Keyboard | Xbox | PlayStation |
|---|---|---|---|
| Throttle / Brake | W / S or ↑ / ↓ | RT / LT | R2 / L2 |
| Steer | A / D or ← / → | Left stick | Left stick |
| Handbrake | Space | A | × |
| Clutch | Left Shift | X | □ |
| Shift up / down | E / Q | RB / LB | R1 / L1 |
| Camera · Look back · Reset | C · B · R | Y · RS · View | △ · R3 · Create |
| Pause | Esc / P | Menu | Options |

## Known limitations
- Builds are unsigned; macOS/Windows will warn on first launch.
- Tested natively on macOS (Apple Silicon); the Linux build is verified rendering on Linux (OpenGL, software). The Windows build is produced by the same pipeline but hasn't been run on Windows hardware. Controller support is covered by automated tests with simulated devices.
- Wired third-party Xbox-protocol pads that macOS itself doesn't expose to apps can't be seen by any game on macOS; connect over Bluetooth or switch the pad to its DirectInput/Switch mode.
- The announcer voice is Japanese text-to-speech; the voice lines can be regenerated with `Tools/audio/elevenlabs_voices.py`.
