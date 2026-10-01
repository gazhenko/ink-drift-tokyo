# Audio credits — INK DRIFT: TOKYO

**All sound effects and music are original and made for this project by procedural synthesis.**
No samples, loops, sample packs, recordings, third-party audio or AI-generated audio were used.
Every waveform is computed from scratch in Python/NumPy by the scripts in `Tools/audio/`:
oscillators, noise, filters, envelopes, FM operators, a sequencer and a mixer.
The scripts are deterministic and seeded, so re-running them on the same toolchain reproduces
byte-identical files.

```
Tools/.venv/bin/python Tools/audio/gen_sfx.py      # all SFX (+ Resources copies)
Tools/.venv/bin/python Tools/audio/gen_music.py    # all music (or: gen_music.py shibuya trailer ...)
Tools/.venv/bin/python Tools/audio/analyze.py --loop --png <dir> <files>   # objective checks
```

| Script | Contents |
|--------|----------|
| `Tools/audio/inkdsp.py` | DSP core: PolyBLEP saw/pulse, 7-voice stereo supersaw, TPT state-variable filters (time-varying), RBJ EQ, ADSR, FM bell / DX-style e-piano, synthesized drums (kick with pitch envelope + click, gated snare, clap, 808-style metallic hats, crash, toms), risers, reverse swells, impacts, Schroeder-diffused 8-line FDN reverb, ping-pong delay, compressor, soft clipper, true-peak lookahead limiter, loop-safe (circular) processing |
| `Tools/audio/music.py` | Sequencer: melody/chord notation, voice-led chord voicings, instrument voices, mono lead with glide, vibrato and bends, guitar-style waveshaped lead, drum patterns and rolls, sidechain ducking, stem auto-levelling, FX sends, mastering |
| `Tools/audio/gen_sfx.py` | All SFX |
| `Tools/audio/gen_music.py` | The compositions (arrangements, chord progressions, melodies) and the trailer cue sheet |
| `Tools/audio/analyze.py`, `musicviz.py` | Measurement: LUFS, true peak, DC, NaN, click and loop-seam checks, spectrograms |

## Sound effects — `Game/Assets/InkDrift/Audio/SFX/` (44.1 kHz, 16-bit PCM WAV)

| File | Length | Ch | True peak | What it is |
|------|--------|----|-----------|------------|
| `ui_move.wav` | 0.060 s | 2 | −3.0 dBTP | bright E6 blip with downward chirp + tick |
| `ui_confirm.wav` | 0.250 s | 2 | −2.0 dBTP | two-tone FM chime E6→B6 (+E7 sparkle) with a light upward whoosh |
| `ui_start.wav` | 1.200 s | 2 | −1.2 dBTP | whoosh-in → kick/sub/crack impact + D-minor supersaw stab → bell/glitter shimmer |
| `callout_pop.wav` | 0.350 s | 2 | −1.5 dBTP | comic "POP!": transient + upward pitched sweep + spray-can hiss |
| `callout_bigpop.wav` | 0.900 s | 2 | −1.2 dBTP | big pop + sub drop + crash + rising pentatonic bell sparkle |
| `callout_fail.wav` | 0.700 s | 2 | −1.5 dBTP | bit-crushed crunch, then a descending muted-brass "wah-wah" |
| `impact.wav` | 0.600 s | 1 | −1.2 dBTP | car crunch: low thump, modal metal resonances, plastic cracks, debris rattle |
| `tire_squeal_loop.wav` | 4.000 s (176 400 smp) | 1 | −1.5 dBTP | seamless loop: three jittering 0.9–1.5 kHz squeal tones with harmonics, phase noise, stick-slip chatter AM and hiss |
| `wind_loop.wav` | 6.000 s (264 600 smp) | 1 | −1.5 dBTP | seamless loop: gusting band-passed pink noise, rumble, hiss and a faint whistle |
| `countdown_beep.wav` | 0.360 s | 2 | −2.0 dBTP | A5 (880 Hz) countdown beep |
| `countdown_go.wav` | 1.000 s | 2 | −1.5 dBTP | A6 + E7 + A5 "GO" tone with a punchy transient |

The runtime copies are byte-identical to the files above:
- `Resources/Audio/`: `tire_squeal_loop.wav`, `wind_loop.wav`, `impact.wav`
- `Resources/Audio/UI/`: `ui_move.wav`, `ui_confirm.wav`, `ui_start.wav`

The loops are built from FFT-periodic noise and integer-cycle oscillators, and their filters run in
steady state around the loop, so end→start is sample-continuous.

## Music — `Game/Assets/InkDrift/Audio/Music/`

The four loop tracks are 44.1 kHz, 16-bit stereo WAVs (TPDF-dithered). Each loops end→start on the
whole file (loop start sample 0, loop end = file length). Notes, reverb/delay tails and
compressor/limiter state wrap around the seam, so the loop point is sample-continuous.
Musically, each outro closes back down into the intro, and the intro reopens into the track.
All tracks are mastered to −14 LUFS integrated with true peak ≤ −1.5 dBTP.

| File | Title | Tempo / key | Length | Sections (bar → time) |
|------|-------|-------------|--------|-----------------------|
| `menu.wav` | Neon Garage | 120 BPM, D minor/F major city-pop | 44 bars, 88.000 s | intro 0 → 0.0 · verse 4 → 8.0 · pre 12 → 24.0 · chorus 16 → 32.0 · interlude 24 → 48.0 · breakdown 28 → 56.0 · chorus 2 32 → 64.0 · outro 40 → 80.0 |
| `shibuya.wav` | Shibuya Neon Rush | 155 BPM, D minor eurobeat | 96 bars, 148.645 s | intro 0 → 0.0 · verse 8 → 12.39 · pre 24 → 37.16 · chorus 32 → 49.55 · hook 48 → 74.32 · breakdown 56 → 86.71 · chorus 2 64 → 99.10 · hook 2 80 → 123.87 · outro 88 → 136.26 |
| `shuto.wav` | C1 Sunset Loop | 150 BPM, A minor eurobeat/trance | 96 bars, 153.600 s | intro 0 → 0.0 · verse 8 → 12.8 · pre 24 → 38.4 · chorus 32 → 51.2 · hook 48 → 76.8 · breakdown 56 → 89.6 · chorus 2 64 → 102.4 · hook 2 80 → 128.0 · outro 88 → 140.8 |
| `okutama.wav` | Okutama Touge Fire | 160 BPM, E minor eurobeat, guitar-style lead | 100 bars, 150.000 s | intro 0 → 0.0 · verse 8 → 12.0 · pre 24 → 36.0 · chorus 32 → 48.0 · hook 48 → 72.0 · guitar solo 56 → 84.0 · breakdown 64 → 96.0 · chorus 2 72 → 108.0 · hook 2 88 → 132.0 · outro 96 → 144.0 |
| `trailer.mp3` | Ink Drift Trailer Cue | 150 BPM, D minor | 75.000 s, not looped | intro 0–8 · build 8–24 · silence 24.0–24.5 · drop 24.5–56.5 · breakdown/rise 56.5–62.9 · breath 62.9–64.0 · final hit + ring-out 64–75 |

`trailer.mp3` is 320 kbps CBR LAME. Impacts land at exactly 24.5 s and 64.0 s. The full cue sheet,
with sections, bar and beat times, accents and MP3 priming notes, is in `trailer_cues.json` next to it.
The drop quotes the Shibuya hook riff and chorus, so the trailer and the game share a theme.

Lossless masters are written to `Tools/audio/out/` (gitignored), including `trailer.wav` (24-bit)
and libvorbis q6 `.ogg` versions of the loops.

## Tooling (not shipped)

NumPy, SciPy (BSD-3-Clause); Numba (BSD-2-Clause); soundfile (BSD-3-Clause) with libsndfile
(LGPL-2.1) and libvorbis (BSD-3-Clause); pyloudnorm (MIT); Matplotlib (PSF-style, analysis plots
only); FFmpeg with libmp3lame/LAME (LGPL) for the trailer MP3. None of these contribute audio
content.
