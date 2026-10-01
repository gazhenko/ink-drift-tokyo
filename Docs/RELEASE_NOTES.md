# INK DRIFT: TOKYO — v1.0.0 demo

A comic-book cel-shaded drift racer through Tokyo. **Watch the trailer:** `INK-DRIFT-TOKYO-trailer.mp4` (below).

## Downloads
| Platform | File | Notes |
|---|---|---|
| macOS (Apple Silicon + Intel) | `InkDriftTokyo-v1.0.0-macOS-universal.zip` | Unsigned (ad-hoc). Right-click → Open, or run `xattr -dr com.apple.quarantine "INK DRIFT TOKYO.app"` |
| Windows 10/11 x64 | `InkDriftTokyo-v1.0.0-Windows-x64.zip` | Extract everything, run `InkDriftTokyo.exe` (D3D11 default) |
| Linux x64 | `InkDriftTokyo-v1.0.0-Linux-x64.tar.gz` | `tar -xzf …`, then `./InkDriftTokyo.x86_64` (Vulkan, OpenGL fallback) |

Checksums: `SHA256SUMS.txt`.

## What's in the demo
- **3 tracks:** SHIBUYA NEON (night, wet neon streets, sakura canal) · SHUTO C1 LOOP (sunset elevated expressway with traffic) · OKUTAMA TOUGE (autumn mountain switchbacks)
- **5 cars**, all fictional ricer-kitted look-alikes: HACHI GR8 · KAIJU SPR-X · ZENKAI Z · RAIJIN BX-R (AWD) · TSUBAME RS — 8 paints each
- **Modes:** Drift Attack · Rival Battle (5 drifting AI rivals) · Free Run
- **Drift physics** with combined-slip tires, clutch kicks, handbrake, weight transfer; assists from PRO (none) to EASY
- **Drift callouts:** graffiti comic pop-ups — ナイス！ 成功！ グレートドリフト！ すごい！ やばい！！ 完璧！ 神ドリフト！！ — with a Japanese announcer voice
- Keyboard and gamepad

## Controls
W/S or RT/LT throttle·brake · A/D or left stick steer · Space / A handbrake · Shift / X clutch · E/Q or RB/LB shift (manual) · C / Y camera · R / View reset · Esc / Start pause

## Known limitations
- Builds are unsigned; macOS/Windows will warn on first launch.
- Tested natively on macOS (Apple Silicon). Windows and Linux builds are produced by the same pipeline but were not hand-tested on hardware.
- The announcer voice is Japanese text-to-speech; the voice lines can be regenerated with `Tools/audio/elevenlabs_voices.py`.
