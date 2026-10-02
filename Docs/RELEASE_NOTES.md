# INK DRIFT: TOKYO — v1.2.0: in-car view

A comic-book cel-shaded drift racer through Tokyo. **Watch the trailer:** [INK-DRIFT-TOKYO-trailer.mp4](https://github.com/gazhenko/ink-drift-tokyo/releases/download/v1.0.0/INK-DRIFT-TOKYO-trailer.mp4).

## What's new in 1.2.0
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
| macOS (Apple Silicon + Intel) | `InkDriftTokyo-v1.2.0-macOS-universal.zip` | Unsigned (ad-hoc). Right-click → Open, or run `xattr -dr com.apple.quarantine "INK DRIFT TOKYO.app"` |
| Windows 10/11 x64 | `InkDriftTokyo-v1.2.0-Windows-x64.zip` | Extract everything into a new folder, run `InkDriftTokyo.exe` (D3D11 default) |
| Linux x64 | `InkDriftTokyo-v1.2.0-Linux-x64.tar.gz` | Extract into a new folder, then `./InkDriftTokyo.x86_64` (Vulkan, OpenGL fallback) |

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
- Tested natively on macOS (Apple Silicon). The controller support is covered by automated tests with simulated Xbox, PlayStation, Switch, generic HID and Linux devices, but hasn't been tried with physical controllers on Windows or Linux.
- Wired third-party Xbox-protocol pads that macOS itself doesn't expose to apps can't be seen by any game on macOS; connect over Bluetooth or switch the pad to its DirectInput/Switch mode.
- The announcer voice is Japanese text-to-speech; the voice lines can be regenerated with `Tools/audio/elevenlabs_voices.py`.
