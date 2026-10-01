"""INK DRIFT: TOKYO — fallback soundtrack, composed & synthesized procedurally (numpy).

usage: python Tools/audio/gen_music.py [menu|shibuya|shuto|okutama|trailer ...]

Loop tracks are rendered as exact periodic signals (notes, reverb/delay tails, compressor and
limiter state all wrap around the loop), so end->start is sample-continuous.
Outputs:
  Game/Assets/InkDrift/Audio/Music/{menu,shibuya,shuto,okutama}.wav   (16-bit loops)
  Game/Assets/InkDrift/Audio/Music/trailer.mp3 + trailer_cues.json
  Tools/audio/out/*.wav (+ .ogg q6 via libvorbis) lossless/reference masters
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import inkdsp as d  # noqa: E402
import music as M  # noqa: E402
from inkdsp import SR, secs  # noqa: E402
from music import Note, mel, prog, shift  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MUSIC = ROOT / "Game/Assets/InkDrift/Audio/Music"
OUT = Path(__file__).parent / "out"
FFMPEG = "/opt/homebrew/bin/ffmpeg"


# --------------------------------------------------------------------------- pattern helpers
def octave_bass(chords, octv=2, pattern="LH", step=0.5, vel=(0.95, 0.72), gate=0.78):
    out = []
    for (t, dur, sym) in chords:
        r = M.chord_root(sym, octv)
        k = 0
        tt = 0.0
        while tt < dur - 1e-9:
            c = pattern[k % len(pattern)]
            if c != ".":
                m = r + {"L": 0, "H": 12, "F": 7, "O": 24, "f": -5}[c]
                out.append(Note(t + tt, step * gate, m, vel[0] if c == "L" else vel[1]))
            tt += step
            k += 1
    return out


def arp(chords, lo=62, step=0.25, shape="up", octaves=2, vel=0.7, gate=0.55, accent=4):
    out = []
    for (t, dur, sym) in chords:
        v = M.voicing(sym, lo, lo + 12, None, 4)
        tones = []
        for o in range(octaves):
            tones += [m + 12 * o for m in v]
        if shape == "updown":
            seq = tones + tones[-2:0:-1]
        elif shape == "down":
            seq = tones[::-1]
        elif shape == "pingpong":
            seq = [tones[i // 2] if i % 2 == 0 else tones[-1 - i // 2] for i in range(len(tones))]
        else:
            seq = tones
        k = 0
        tt = 0.0
        while tt < dur - 1e-9:
            out.append(Note(t + tt, step * gate, seq[k % len(seq)], vel * (1.0 if k % accent == 0 else 0.78)))
            tt += step
            k += 1
    return out


def offbeat_stabs(dur):
    return [(o + 0.5, 0.32) for o in np.arange(0, dur, 1.0)]


def eighth_stabs(dur):
    return [(o, 0.3) for o in np.arange(0, dur, 0.5)]


def env_points(song, pts, n=None):
    """Piecewise log-linear curve from (beat, value) breakpoints -> per-sample array."""
    n = n or song.N
    xs = np.array([song.s(b) for b, _ in pts], dtype=float)
    ys = np.log(np.array([v for _, v in pts], dtype=float))
    return np.exp(np.interp(np.arange(n), xs, ys))


def auto_filter(song, pts, res=0.1, mode="lp"):
    fc = env_points(song, pts)

    def post(x):
        def f(xx, ff):
            if mode == "lp":
                return d.lp24(xx, ff, res)
            return d._apply_mono(lambda c: d.svf(c, ff, np.full(c.shape[0], 0.707), 2), xx)
        if song.loop:
            P = secs(1.0)
            return f(np.concatenate([x[-P:], x]), np.concatenate([fc[-P:], fc]))[P:]
        return f(x, fc)
    return post


def gain_curve(song, pts):
    g = np.interp(np.arange(song.N), [song.s(b) for b, _ in pts], [v for _, v in pts])

    def post(x):
        return x * g[:, None]
    return post


def fx_hits(song, stem, t, kind, rng, **kw):
    if kind == "crash":
        smp = d.crash(rng, **kw)
    elif kind == "rev":
        dur = kw.pop("dur", song.sec(4))
        smp = d.reverse_swell(rng, dur, **kw)
        song.add(stem, smp, song.s(t) - smp.shape[0])
        return
    elif kind == "riser":
        beats = kw.pop("beats", 16)
        smp = d.riser(rng, song.sec(beats), **kw)
        song.add(stem, smp, song.s(t))
        return
    elif kind == "boom":
        smp = d.boom(rng, **kw)
    elif kind == "sub":
        smp = d.sub_drop(rng, **kw)
    else:
        raise ValueError(kind)
    song.add(stem, smp, song.s(t))


def orch_hit(song, stem, t, chord_notes, rng, vel=1.0, dur=0.9):
    n = secs(dur)
    x = np.zeros((n, 2))
    for m in chord_notes:
        f = float(d.mtof(m))
        x += M.v_brass(rng, f, n - secs(0.12), vel, cut=1500, env_amt=6000, fdec=0.08, rel=0.12)[:n]
        x += 0.6 * M.v_supersaw(rng, f, n - secs(0.3), vel, dcy=0.15, sus=0.2, rel=0.3)[:n]
    nz = d.bp(d.noise(n, rng), 2500, 0.5) * d.perc(n, 0.001, 0.03)
    x += 0.4 * np.stack([nz, nz], -1)
    x *= d.perc(n, 0.001, dur / 3.0)[:, None]
    song.add(stem, x / len(chord_notes) ** 0.5, song.s(t))


# ------------------------------------------------------------------------------- drum styles
EURO = {
    "kick": "x...x...x...x...",
    "snare": "....x.......x...",
    "clap": "....x.......x...",
    "hat": "xoxgxoxgxoxgxoxg",
    "ohat": "..x...x...x...x.",
}


def drums(song, kit, t0, bars, style="full", fill=False, crash=True, vel=1.0):
    """Eurobeat drum layers for one section. `fill` puts a snare/tom fill in the last bar."""
    body = bars - 1 if fill else bars
    if style in ("full", "verse", "intro2", "half"):
        play = M.play_pattern
        if style == "half":
            play(song, "kick", kit.kick, "x.......x.......", t0, bars, is_kick=True, vel=vel)
            play(song, "snare", kit.snare, "........x.......", t0, body, vel=vel)
            play(song, "hat", kit.hat, "x.x.x.x.x.x.x.x.", t0, bars, vel=0.8 * vel)
        else:
            play(song, "kick", kit.kick, EURO["kick"], t0, bars, is_kick=True, vel=vel)
            play(song, "snare", kit.snare, EURO["snare"], t0, body, vel=vel)
            if style in ("full", "intro2"):
                play(song, "clap", kit.clap, EURO["clap"], t0, body, vel=vel)
            play(song, "hat", kit.hat, EURO["hat"] if style != "verse" else "x.xgx.xgx.xgx.xg", t0, bars, vel=vel)
            play(song, "ohat", kit.ohat, EURO["ohat"], t0, bars, vel=(1.0 if style == "full" else 0.7) * vel)
    elif style == "intro":
        M.play_pattern(song, "kick", kit.kick, EURO["kick"], t0, bars, is_kick=True, vel=vel)
        M.play_pattern(song, "hat", kit.hat, "x.x.x.x.x.x.x.x.", t0, bars, vel=0.8 * vel)
        M.play_pattern(song, "ohat", kit.ohat, EURO["ohat"], t0, bars, vel=0.6 * vel)
    elif style == "hats":
        M.play_pattern(song, "hat", kit.hat, "x.xgx.xgx.xgx.xg", t0, bars, vel=0.7 * vel)
    elif style == "kick":
        M.play_pattern(song, "kick", kit.kick, EURO["kick"], t0, bars, is_kick=True, vel=vel)
        M.play_pattern(song, "hat", kit.hat, "x.x.x.x.x.x.x.x.", t0, bars, vel=0.75 * vel)
    if fill:
        tf = t0 + (bars - 1) * 4
        M.play_pattern(song, "snare", kit.snare, "x.x.x.xxxxxxXXXX", tf, 1, vel=0.85 * vel)
        toms = sorted(kit.tom)
        for i, f in enumerate(reversed(toms)):
            song.add("perc", kit.tom[f] * 0.8 * vel, song.s(tf + 2 + i * 0.5))
    if crash:
        song.add("crash", kit.crash[0] * 0.9 * vel, song.s(t0))


# ===================================================================================== SHIBUYA
SHIBUYA_RIFF = ("A5:2 A5:1 D6:2 A5:2 G5:2 F5:2 G5:1 A5:4 | F5:2 F5:1 Bb5:2 F5:2 E5:2 D5:2 E5:1 F5:4 | "
                "G5:2 G5:1 C6:2 G5:2 F5:2 E5:2 F5:1 G5:4 | E5:2 E5:1 A5:2 C#6:2 E6:2 C#6:2 A5:1 E5:4")
SHIBUYA_RIFF_B = SHIBUYA_RIFF.rsplit("|", 1)[0] + "| A5:2 A5:1 C#6:2 E6:2 G6:2 F6:2 E6:1 C#6:4"
SHIBUYA_CHO_A = ("D5:2 F5:2 Bb5:4> A5:2 G5:2 F5:4 | E5:2 F5:2 G5:4 C6:4> Bb5:2 A5:2 | "
                 "A5:3 G5:1 A5:2 C6:2 E6:4> D6:2 C6:2 | D6:6 C6:2 A5:4 F5:4")
SHIBUYA_CHO_B = ("D5:2 F5:2 Bb5:4> A5:2 G5:2 F5:4 | E5:2 F5:2 G5:4 C6:4> D6:2 E6:2 | "
                 "F6:4> E6:4 C6:2 A5:2 C6:2 E6:2 | D6:12 r:4")


def shibuya():
    """SHIBUYA NEON — 155 BPM eurobeat in D minor, night-neon energy. 96 bars loop."""
    S = M.Song("shibuya", 155, bars=96, seed=155)
    rng = np.random.default_rng(1550)
    kit = M.Kit(seed=15, kick=dict(f0=300, f1=55, ptau=0.016, adec=0.095, click=0.65, drive=2.4, sub=0.04),
                snare=dict(tone=200, noise_dec=0.15, gated=0.65))
    sc = dict(att=0.003, hold=0.01, rel=0.17, shape=1.6)
    S.stem("kick", lufs=-17.0, eq=[("hp", 30, 0, 0.7)])
    S.stem("snare", lufs=-19.5, verb2=0.15, eq=[("hp", 120, 0, 0.7)])
    S.stem("clap", lufs=-21.5, verb2=0.2, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("hat", lufs=-26, pan=0.18, eq=[("hp", 4000, 0, 0.7)])
    S.stem("ohat", lufs=-27.5, pan=-0.15, eq=[("hp", 3500, 0, 0.7)])
    S.stem("crash", lufs=-26, width=1.2, eq=[("hp", 2000, 0, 0.7)])
    S.stem("perc", lufs=-24, verb2=0.2)
    S.stem("bass", lufs=-18.5, sc=0.5, eq=[("hp", 35, 0, 0.7), ("peak", 900, 1.5, 1.0)])
    S.stem("chords", lufs=-21.0, sc=0.55, verb=0.12, width=1.25, eq=[("hp", 180, 0, 0.7)])
    S.stem("pad", lufs=-24.0, sc=0.5, verb=0.3, width=1.4, eq=[("hp", 200, 0, 0.7)])
    S.stem("lead", lufs=-16.0, sc=0.12, verb=0.17, delay=0.12, eq=[("hp", 220, 0, 0.7), ("peak", 2800, 1.5, 1.0)])
    S.stem("lead2", lufs=-24.0, sc=0.2, verb=0.15, eq=[("hp", 150, 0, 0.7)])
    sweep = [(0, 500), (14, 900), (30, 9000), (32, 18000), (88 * 4, 18000), (92 * 4, 7000), (95 * 4, 700), (96 * 4, 500)]
    S.stem("riff", lufs=-16.5, sc=0.2, verb=0.1, delay=0.1, eq=[("hp", 200, 0, 0.7)],
           post=auto_filter(S, sweep, res=0.25))
    S.stem("ichords", lufs=-21.5, sc=0.55, verb=0.12, width=1.25, eq=[("hp", 180, 0, 0.7)],
           post=auto_filter(S, sweep, res=0.2))
    S.stem("riffhi", lufs=-16.5, sc=0.2, verb=0.12, delay=0.12, eq=[("hp", 220, 0, 0.7)])
    S.stem("bells", lufs=-22.5, sc=0.15, verb=0.3, delay=0.15, eq=[("hp", 400, 0, 0.7)])
    S.stem("arp", lufs=-24.0, sc=0.3, verb=0.15, delay=0.22, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("fx", lufs=-24.0, verb=0.25, width=1.3, eq=[("hp", 120, 0, 0.7)])

    B = lambda bar: bar * 4.0  # noqa: E731
    HOOK = "Dm Bb C A"
    VERSE = "Dm Bb Gm A"
    PRE = "Bb C Dm Dm Bb C A A"
    CHO = "Bb C Am Dm Bb C Am Dm Bb C Am Dm Bb C A Dm"
    BRK = "Bb C Am Dm Bb C A A"

    riff, riff_b = SHIBUYA_RIFF, SHIBUYA_RIFF_B
    verse_a = "D5:3 E5:1 F5:2 A5:2 G5:4 F5:2 E5:2 | D5:6 r:10"
    verse_b = "Bb4:3 C5:1 D5:2 G5:2 F5:4 E5:2 D5:2 | C#5:6 r:10"
    verse_b2 = "Bb4:3 C5:1 D5:2 G5:2 F5:4 E5:2 D5:2 | C#5:4 E5:4 G5:4 A5:4"
    bells_a = "r:16 | r:8 F6:1 G6:1 A6:2 Bb6:2 A6:2"
    bells_b = "r:16 | r:8 A6:1 G6:1 E6:2 C#6:2 E6:2"
    pre = ("D5:2 F5:2 Bb5:4 A5:4 F5:4 | E5:2 G5:2 C6:4 Bb5:4 G5:4 | F5:2 A5:2 D6:4 C6:4 A5:4 | D6:8 C6:4 A5:4 | "
           "Bb5:4 A5:4 G5:4 F5:4 | G5:4 A5:4 Bb5:4 C6:4 | C#6:8 E6:8 | E6:16")
    cho_a, cho_b = SHIBUYA_CHO_A, SHIBUYA_CHO_B
    cho_b2 = ("D5:2 F5:2 Bb5:4> A5:2 G5:2 F5:4 | E5:2 F5:2 G5:4 C6:4> D6:2 E6:2 | C#6:3 D6:1 E6:4> A5:4 C#6:4 | "
              "D6:12 r:4")

    # ---- harmony per section
    sec = {}
    sec["intro"] = prog(HOOK + " " + HOOK, B(0))
    sec["verse"] = prog(" ".join([VERSE] * 4), B(8))
    sec["pre"] = prog(PRE, B(24))
    sec["cho1"] = prog(CHO, B(32))
    sec["hook1"] = prog(HOOK + " " + HOOK, B(48))
    sec["brk"] = prog(BRK, B(56))
    sec["cho2"] = prog(CHO, B(64))
    sec["hook2"] = prog(HOOK + " " + HOOK, B(80))
    sec["outro"] = prog(HOOK + " " + HOOK, B(88))

    # ---- drums
    drums(S, kit, B(0), 4, "intro", crash=True, vel=0.85)
    drums(S, kit, B(4), 4, "intro2", fill=True, crash=False)
    drums(S, kit, B(8), 16, "verse", fill=True)
    drums(S, kit, B(24), 6, "verse")
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(30), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(30), 8, 4, 32, 0.25, 1.0)
    drums(S, kit, B(32), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(40)))
    drums(S, kit, B(48), 8, "full", fill=True)
    drums(S, kit, B(56), 4, "hats", crash=True, vel=0.8)
    drums(S, kit, B(60), 2, "kick", crash=False)
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(62), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(60), 16, 4, 32, 0.2, 1.0, curve=1.3)
    drums(S, kit, B(64), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(72)))
    drums(S, kit, B(80), 8, "full", fill=True)
    drums(S, kit, B(88), 4, "full", crash=True)
    drums(S, kit, B(92), 4, "intro", crash=False, fill=True)

    # ---- bass
    for k in ("intro", "verse", "cho1", "hook1", "cho2", "hook2", "outro"):
        M.play_poly(S, "bass", octave_bass(sec[k]), M.v_bass)
    M.play_poly(S, "bass", octave_bass(sec["pre"][:6], pattern="LL"), M.v_bass)
    M.play_poly(S, "bass", octave_bass(prog("A A", B(30)), pattern="L", step=0.25, vel=(0.8, 0.8)), M.v_bass,
                env_amt=3200)
    M.play_poly(S, "bass", [Note(B(56) + i * 4, 3.8, M.chord_root(c[2], 2), 0.7) for i, c in enumerate(sec["brk"][:4])],
                M.v_bass, cut=180, env_amt=600, sus=0.8, dcy=0.5, rel=0.3)
    M.play_poly(S, "bass", octave_bass(sec["brk"][4:], pattern="L", step=0.5), M.v_bass)

    # ---- chords: offbeat supersaw stabs in hooks/choruses, pads elsewhere
    stab = dict(a=0.002, dcy=0.12, sus=0.25, rel=0.12, cut=1800, env_amt=7000, fdec=0.09, cents=24)
    for k in ("cho1", "cho2"):
        M.play_chords(S, "chords", sec[k], M.v_supersaw, 57, 79, rhythm=offbeat_stabs, gate=1.0, vel=0.9, **stab)
    for k in ("hook1", "hook2"):
        M.play_chords(S, "chords", sec[k], M.v_supersaw, 55, 74, rhythm=offbeat_stabs, gate=1.0, vel=0.7, **stab)
    for k in ("intro", "outro"):
        M.play_chords(S, "ichords", sec[k], M.v_supersaw, 55, 74, rhythm=offbeat_stabs, gate=1.0, vel=0.7, **stab)
    M.play_chords(S, "chords", sec["verse"], M.v_brass, 55, 72, rhythm=offbeat_stabs, gate=1.0, vel=0.7,
                  cut=800, env_amt=2800, fdec=0.07, rel=0.08)
    for k in ("verse", "pre", "brk", "cho1", "cho2"):
        M.play_chords(S, "pad", sec[k], M.v_pad, 50, 74, vel=0.8)

    # ---- hook riff (bright saw + octave) and its filtered intro/outro version
    for b0, txt in ((0, riff), (4, riff_b), (88, riff), (92, riff_b)):
        M.play_mono(S, "riff", mel(txt, B(b0)), "saw", cut=1800, env_amt=5000, fdec=0.12, res=0.2,
                    gate_frac=0.75, vib_depth=0.0, octave=0.35, glide=0.03)
    for b0, txt in ((48, riff), (52, riff_b), (80, riff), (84, riff_b)):
        M.play_mono(S, "riffhi", mel(txt, B(b0)), "supersaw", cut=2500, env_amt=6000, fdec=0.15, res=0.15,
                    gate_frac=0.78, vib_depth=0.0, cents=20, mix=0.65, octave=0.25)
        M.play_mono(S, "lead2", mel(txt, B(b0), tr=-12), "square", cut=1200, env_amt=3000, gate_frac=0.75,
                    vib_depth=0.0)

    # ---- verse call (lead) & response (bells)
    v_lead = (mel(verse_a, B(8)) + mel(verse_b, B(10)) + mel(verse_a, B(12)) + mel(verse_b, B(14)) +
              mel(verse_a, B(16)) + mel(verse_b, B(18)) + mel(verse_a, B(20)) + mel(verse_b2, B(22)))
    M.play_mono(S, "lead", v_lead, "saw", cut=1400, env_amt=3500, fdec=0.25, res=0.18, vib_depth=0.2, amp=0.5)
    v_bells = []
    for b0 in (8, 12, 16, 20):
        v_bells += mel(bells_a, B(b0), vel=0.7) + mel(bells_b, B(b0 + 2), vel=0.7)
    M.play_poly(S, "bells", v_bells, M.v_bell, amp_decay=0.5)

    # ---- pre-chorus (rising), chorus 1/2 (supersaw lead + square octave-down double)
    M.play_mono(S, "lead", mel(pre, B(24)), "saw", cut=1600, env_amt=4000, fdec=0.3, res=0.2, vib_depth=0.25)
    for b0, alt in ((32, False), (64, True)):
        ch = mel(cho_a, B(b0)) + mel(cho_b, B(b0 + 4)) + mel(cho_a, B(b0 + 8)) + mel(cho_b2, B(b0 + 12))
        M.play_mono(S, "lead", ch, "supersaw", cut=2600, env_amt=5000, fdec=0.25, res=0.15, cents=18, mix=0.6,
                    vib_depth=0.25, glide=0.04, octave=0.2 if alt else 0.0)
        M.play_mono(S, "lead2", shift(ch, tr=-12), "square", cut=1100, env_amt=2500, vib_depth=0.15)
        # bell sparkle arps answering on the off-beats
        M.play_poly(S, "bells", arp(sec["cho1" if not alt else "cho2"], lo=79, step=0.5, shape="updown", octaves=1,
                                    vel=0.45, gate=0.4), M.v_bell, amp_decay=0.35, index=1.6)
        M.play_poly(S, "arp", arp(sec["cho1" if not alt else "cho2"], lo=67, step=0.25, shape="updown", octaves=2,
                                  vel=0.6), M.v_pluck, cut=900, env_amt=4500, fdec=0.06)

    # ---- breakdown: bells play the chorus hook softly, arps rise in the build
    bk = mel(cho_a, B(56), vel=0.75)
    M.play_poly(S, "bells", bk, M.v_bell, amp_decay=1.0, index=2.0)
    M.play_poly(S, "arp", arp(sec["brk"][4:], lo=62, step=0.25, shape="up", octaves=3, vel=0.6), M.v_pluck,
                cut=600, env_amt=5000, fdec=0.07)
    M.play_mono(S, "lead", mel("C#6:8 E6:8 | E6:16", B(60 + 2)), "saw", cut=1500, env_amt=3000, vib_depth=0.3)

    # ---- FX: crashes, risers, reverse swells
    fx_hits(S, "fx", B(24) + 16, "riser", rng, beats=16, f_lo=300, f_hi=10000)
    fx_hits(S, "fx", B(32), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(60), "riser", rng, beats=16, f_lo=250, f_hi=12000, tonal=(110, 880))
    fx_hits(S, "fx", B(64), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(32), "sub", rng, dur=1.4, f0=90, f1=36)
    fx_hits(S, "fx", B(64), "sub", rng, dur=1.4, f0=90, f1=36)
    fx_hits(S, "fx", B(0), "rev", rng, dur=S.sec(2))
    orch_hit(S, "fx", B(48), [50, 57, 62, 65, 69], rng)
    orch_hit(S, "fx", B(80), [50, 57, 62, 65, 69], rng)

    sections = [("intro", 0), ("verse", 8), ("pre_chorus", 24), ("chorus_1", 32), ("hook", 48),
                ("breakdown", 56), ("chorus_2", 64), ("hook_2", 80), ("outro", 88)]
    return S, sections


# ------------------------------------------------------------------------- more pattern helpers
def gate_post(song, pattern, regions, depth=1.0, smooth_ms=3.0, steps=16):
    """Trance gate: amplitude-chop a stem by a 16-step pattern inside beat regions."""
    pat = np.array([1.0 if c == "x" else (0.45 if c == "o" else 0.0) for c in pattern])
    g = np.ones(song.N)
    for (b0, b1) in regions:
        b = b0
        k = 0
        while b < b1 - 1e-9:
            i0, i1 = song.s(b), song.s(b + 4.0 / steps)
            lv = pat[k % steps]
            g[i0 % song.N if song.loop else i0: (i1 % song.N if song.loop else i1) or song.N] = 1 - depth * (1 - lv)
            b += 4.0 / steps
            k += 1
    if song.loop:
        g = d.circ(lambda z: d.smooth(z, smooth_ms), g, pre=secs(0.2), post=0)
    else:
        g = d.smooth(g, smooth_ms)

    def post(x):
        return x * g[:, None]
    return post


def comp_rhythm(hits):
    def r(dur):
        return [(o, ln) for (o, ln) in hits if o < dur - 1e-9]
    return r


def bars_of(chords):
    return chords


# ======================================================================================= SHUTO
def shuto():
    """SHUTO C1 LOOP — 150 BPM eurobeat/trance hybrid in A minor, sunset highway rush. 96 bars."""
    S = M.Song("shuto", 150, bars=96, seed=150)
    rng = np.random.default_rng(1500)
    kit = M.Kit(seed=33, kick=dict(f0=280, f1=54, ptau=0.017, adec=0.11, click=0.55, drive=2.3, sub=0.05),
                snare=dict(tone=210, noise_dec=0.13, gated=0.5), clap=dict(fc=1500, dec=0.13))
    B = lambda bar: bar * 4.0  # noqa: E731
    gate_regions = [(B(0), B(8)), (B(48), B(56)), (B(80), B(96))]
    S.stem("kick", lufs=-17.0, eq=[("hp", 30, 0, 0.7)])
    S.stem("snare", lufs=-21.0, verb2=0.18, eq=[("hp", 150, 0, 0.7)])
    S.stem("clap", lufs=-20.5, verb2=0.25, width=1.4, eq=[("hp", 300, 0, 0.7)])
    S.stem("hat", lufs=-25.5, pan=0.2, eq=[("hp", 5000, 0, 0.7)])
    S.stem("ohat", lufs=-26.0, pan=-0.12, eq=[("hp", 4000, 0, 0.7)])
    S.stem("crash", lufs=-26, width=1.3, eq=[("hp", 2500, 0, 0.7)])
    S.stem("perc", lufs=-25, verb2=0.2)
    S.stem("bass", lufs=-18.5, sc=0.6, eq=[("hp", 35, 0, 0.7), ("peak", 1000, 1.5, 1.0)])
    S.stem("chords", lufs=-21.0, sc=0.6, verb=0.18, width=1.35, eq=[("hp", 200, 0, 0.7)])
    sweep = [(0, 400), (12, 700), (30, 8000), (32, 16000), (88 * 4, 16000), (93 * 4, 3000), (96 * 4, 400)]
    S.stem("gated", lufs=-20.5, sc=0.3, verb=0.22, delay=0.08, width=1.4, eq=[("hp", 200, 0, 0.7)],
           post=lambda x: auto_filter(S, sweep, res=0.2)(gate_post(S, "x.xxx.x.xx.xx.xx", gate_regions, 0.9)(x)))
    S.stem("pad", lufs=-24.0, sc=0.5, verb=0.35, width=1.5, eq=[("hp", 220, 0, 0.7)])
    S.stem("lead", lufs=-16.0, sc=0.15, verb=0.2, delay=0.14, eq=[("hp", 250, 0, 0.7), ("peak", 3000, 1.5, 1.0)])
    S.stem("lead2", lufs=-23.5, sc=0.2, verb=0.18, eq=[("hp", 150, 0, 0.7)])
    S.stem("trance", lufs=-16.5, sc=0.25, verb=0.2, delay=0.16, width=1.2, eq=[("hp", 250, 0, 0.7)])
    S.stem("bells", lufs=-22.0, sc=0.15, verb=0.3, delay=0.2, eq=[("hp", 500, 0, 0.7)])
    S.stem("arp", lufs=-22.5, sc=0.35, verb=0.15, delay=0.25, width=1.4, eq=[("hp", 300, 0, 0.7)])
    S.stem("fx", lufs=-24.0, verb=0.3, width=1.3, eq=[("hp", 120, 0, 0.7)])

    HOOK = "Am F C G"
    VERSE = "Am F C G Am F C G F G Em Am Dm F G G"
    PRE = "F G Em Am F G E E"
    CHO = "F G Em Am F G Em Am F G Em Am F G E Am"
    BRK = "F G Em Am F G E E"
    sec = {
        "intro": prog(HOOK + " " + HOOK, B(0)), "verse": prog(VERSE, B(8)), "pre": prog(PRE, B(24)),
        "cho1": prog(CHO, B(32)), "hook1": prog(HOOK + " " + HOOK, B(48)), "brk": prog(BRK, B(56)),
        "cho2": prog(CHO, B(64)), "hook2": prog(HOOK + " " + HOOK, B(80)), "outro": prog(HOOK + " " + HOOK, B(88)),
    }
    hook = "A5:3 C6:3 E6:2 D6:3 C6:3 B5:2 | A5:3 C6:3 F6:2 E6:3 C6:3 A5:2 | G5:3 C6:3 E6:2 D6:3 C6:3 G5:2 | G5:3 B5:3 D6:2 E6:3 D6:3 B5:2"
    hook_b = hook.rsplit("|", 1)[0] + "| B5:3 D6:3 G6:2 A6:8"
    va = "E5:3 A5:3 C6:2 B5:4 A5:4 | A5:6 r:10 | G5:3 C6:3 E6:2 D6:4 C6:4 | B5:6 r:10"
    va2 = "E5:3 A5:3 C6:2 B5:4 A5:4 | A5:6 r:10 | G5:3 C6:3 E6:2 D6:4 C6:4 | B5:4 C6:4 D6:8"
    vb = "A5:3 C6:3 F6:2 E6:4 C6:4 | D6:6 r:10 | E6:3 D6:3 B5:2 G5:4 E5:4 | A5:6 r:10"
    vc = "F5:3 A5:3 D6:2 C6:4 A5:4 | C6:4 A5:4 F5:8 | G5:4 B5:4 D6:4 F6:4 | G6:16"
    bell_resp = {1: "r:8 C7:2 A6:2 F6:2 C6:2", 3: "r:8 D7:2 B6:2 G6:2 D6:2"}
    bell_resp_b = {1: "r:8 B6:2 G6:2 D6:2 B5:2", 3: "r:8 E7:2 C7:2 A6:2 E6:2"}
    pre = ("A5:4 C6:4 F6:8 | G6:4 F6:4 D6:8 | E6:4 D6:4 B5:8 | C6:4 B5:4 A5:8 | "
           "A5:2 C6:2 F6:4 A5:2 C6:2 F6:4 | B5:2 D6:2 G6:4 B5:2 D6:2 G6:4 | G#5:4 B5:4 E6:4 G#6:4 | B6:16")
    cho_a = "C6:4> A5:2 C6:2 F6:4> E6:2 C6:2 | D6:4> B5:2 D6:2 G6:4> F6:2 D6:2 | E6:3 D6:1 B5:2 G5:2 B5:4 E6:4 | C6:6 B5:2 A5:8"
    cho_b = "C6:4> A5:2 C6:2 F6:4> G6:2 A6:2 | G6:4> F6:2 E6:2 D6:4 B5:2 D6:2 | E6:3 F6:1 E6:2 D6:2 B5:4 G5:4 | A5:12 r:4"
    cho_b2 = "C6:4> A5:2 C6:2 F6:4> G6:2 A6:2 | G6:4> F6:2 E6:2 D6:4 B5:2 D6:2 | G#5:4 B5:4 E6:4 D6:2 B5:2 | A5:12 r:4"

    # drums
    drums(S, kit, B(0), 4, "intro", vel=0.85)
    drums(S, kit, B(4), 4, "intro2", fill=True, crash=False)
    drums(S, kit, B(8), 16, "verse", fill=True)
    drums(S, kit, B(24), 6, "verse")
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(30), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(30), 8, 4, 32, 0.25, 1.0)
    drums(S, kit, B(32), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(40)))
    drums(S, kit, B(48), 8, "full", fill=True)
    drums(S, kit, B(56), 4, "hats", vel=0.8)
    drums(S, kit, B(60), 2, "kick", crash=False)
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(62), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(60), 16, 4, 32, 0.2, 1.0, curve=1.3)
    drums(S, kit, B(64), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(72)))
    drums(S, kit, B(80), 8, "full", fill=True)
    drums(S, kit, B(88), 4, "full")
    drums(S, kit, B(92), 4, "intro", crash=False, fill=True)
    M.play_pattern(S, "perc", kit.shaker, "gxoxgxoxgxoxgxox", B(8), 16)
    M.play_pattern(S, "perc", kit.shaker, "gxoxgxoxgxoxgxox", B(64), 16)

    # bass: trance rolling in intro/hooks/outro, eurobeat octaves in verse/chorus
    for k in ("intro", "hook1", "hook2", "outro"):
        M.play_poly(S, "bass", octave_bass(sec[k], pattern=".LHL", step=0.25, gate=0.7, vel=(0.9, 0.75)), M.v_bass,
                    cut=300, env_amt=2000, fdec=0.05)
    for k in ("verse", "cho1", "cho2"):
        M.play_poly(S, "bass", octave_bass(sec[k]), M.v_bass)
    M.play_poly(S, "bass", octave_bass(sec["pre"][:6], pattern="LL"), M.v_bass)
    M.play_poly(S, "bass", octave_bass(prog("E E", B(30)), pattern="L", step=0.25, vel=(0.8, 0.8)), M.v_bass)
    M.play_poly(S, "bass", [Note(B(56) + i * 4, 3.8, M.chord_root(c[2], 2), 0.7) for i, c in enumerate(sec["brk"][:4])],
                M.v_bass, cut=180, env_amt=600, sus=0.8, dcy=0.5, rel=0.3)
    M.play_poly(S, "bass", octave_bass(sec["brk"][4:], pattern="L", step=0.5), M.v_bass)

    # chords: gated supersaw sustains (intro/hook/outro), offbeat stabs in choruses, pads
    for k in ("intro", "hook1", "hook2", "outro"):
        M.play_chords(S, "gated", sec[k], M.v_supersaw, 57, 81, vel=0.8, a=0.004, dcy=0.5, sus=0.85, rel=0.05,
                      cut=2500, env_amt=2000, cents=26, mix=0.8)
    stab = dict(a=0.002, dcy=0.12, sus=0.25, rel=0.12, cut=1900, env_amt=7000, fdec=0.09, cents=24)
    for k in ("cho1", "cho2"):
        M.play_chords(S, "chords", sec[k], M.v_supersaw, 57, 79, rhythm=offbeat_stabs, gate=1.0, vel=0.9, **stab)
    for k in ("verse", "pre", "brk", "cho1", "cho2"):
        M.play_chords(S, "pad", sec[k], M.v_pad, 52, 76, vel=0.8, cut=2600)

    # hook: trance supersaw lead (+ square double an octave down)
    for b0, txt in ((48, hook), (52, hook_b), (80, hook), (84, hook_b)):
        nts = mel(txt, B(b0))
        M.play_mono(S, "trance", nts, "supersaw", cut=2800, env_amt=6000, fdec=0.14, res=0.12, gate_frac=0.8,
                    vib_depth=0.0, cents=28, mix=0.8, glide=0.03)
        M.play_mono(S, "lead2", shift(nts, tr=-12), "square", cut=1200, env_amt=3000, gate_frac=0.75, vib_depth=0.0)
    for b0, txt in ((0, hook), (4, hook_b), (88, hook), (92, hook_b)):
        M.play_poly(S, "bells", mel(txt, B(b0), vel=0.55), M.v_bell, amp_decay=0.4, index=1.4)

    # verse lead + bell responses
    v_lead = mel(va, B(8)) + mel(va2, B(12)) + mel(vb, B(16)) + mel(vc, B(20))
    M.play_mono(S, "lead", v_lead, "saw", cut=1500, env_amt=3500, fdec=0.25, res=0.18, vib_depth=0.2)
    for b0, resp in ((8, bell_resp), (12, bell_resp), (16, bell_resp_b)):
        for k, txt in resp.items():
            M.play_poly(S, "bells", mel(txt, B(b0 + k), vel=0.7), M.v_bell, amp_decay=0.5)
    M.play_poly(S, "arp", arp(sec["verse"], lo=64, step=0.25, shape="updown", octaves=2, vel=0.55), M.v_pluck,
                cut=700, env_amt=3500, fdec=0.05)

    # pre + choruses
    M.play_mono(S, "lead", mel(pre, B(24)), "saw", cut=1700, env_amt=4000, fdec=0.3, res=0.2, vib_depth=0.25)
    for b0, alt in ((32, False), (64, True)):
        ch = mel(cho_a, B(b0)) + mel(cho_b, B(b0 + 4)) + mel(cho_a, B(b0 + 8)) + mel(cho_b2, B(b0 + 12))
        M.play_mono(S, "lead", ch, "supersaw", cut=2800, env_amt=5000, fdec=0.25, res=0.12, cents=24, mix=0.7,
                    vib_depth=0.25, glide=0.04, octave=0.22 if alt else 0.0)
        M.play_mono(S, "lead2", shift(ch, tr=-12), "square", cut=1100, env_amt=2500, vib_depth=0.15)
        M.play_poly(S, "arp", arp(sec["cho2" if alt else "cho1"], lo=69, step=0.25, shape="pingpong", octaves=2,
                                  vel=0.6), M.v_pluck, cut=1000, env_amt=5000, fdec=0.06)

    # breakdown: bells sing the chorus, rising arps and lead into chorus 2
    M.play_poly(S, "bells", mel(cho_a, B(56), vel=0.75), M.v_bell, amp_decay=1.0, index=2.0)
    M.play_poly(S, "arp", arp(sec["brk"][4:], lo=64, step=0.25, shape="up", octaves=3, vel=0.6), M.v_pluck,
                cut=600, env_amt=5000, fdec=0.07)
    M.play_mono(S, "lead", mel("G#6:8 B6:8 | B6:16", B(62)), "saw", cut=1500, env_amt=3000, vib_depth=0.3)

    fx_hits(S, "fx", B(28), "riser", rng, beats=16, f_lo=300, f_hi=10000)
    fx_hits(S, "fx", B(32), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(60), "riser", rng, beats=16, f_lo=250, f_hi=12000, tonal=(110, 880))
    fx_hits(S, "fx", B(64), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(32), "sub", rng, dur=1.4, f0=90, f1=40)
    fx_hits(S, "fx", B(64), "sub", rng, dur=1.4, f0=90, f1=40)
    fx_hits(S, "fx", B(0), "rev", rng, dur=S.sec(2))
    orch_hit(S, "fx", B(48), [45, 52, 57, 60, 64], rng)
    orch_hit(S, "fx", B(80), [45, 52, 57, 60, 64], rng)
    sections = [("intro", 0), ("verse", 8), ("pre_chorus", 24), ("chorus_1", 32), ("hook", 48),
                ("breakdown", 56), ("chorus_2", 64), ("hook_2", 80), ("outro", 88)]
    return S, sections


# ===================================================================================== OKUTAMA
def okutama():
    """OKUTAMA TOUGE — 160 BPM eurobeat in E minor with a distorted guitar-like lead. 100 bars."""
    S = M.Song("okutama", 160, bars=100, seed=160)
    rng = np.random.default_rng(1600)
    kit = M.Kit(seed=51, kick=dict(f0=310, f1=56, ptau=0.015, adec=0.09, click=0.7, drive=2.6, sub=0.04),
                snare=dict(tone=185, noise_dec=0.16, gated=0.75, snap=0.9))
    B = lambda bar: bar * 4.0  # noqa: E731
    S.stem("kick", lufs=-17.0, eq=[("hp", 30, 0, 0.7)])
    S.stem("snare", lufs=-19.0, verb2=0.15, eq=[("hp", 120, 0, 0.7)])
    S.stem("clap", lufs=-22.0, verb2=0.2, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("hat", lufs=-26.0, pan=0.18, eq=[("hp", 4500, 0, 0.7)])
    S.stem("ohat", lufs=-26.5, pan=-0.15, eq=[("hp", 3500, 0, 0.7)])
    S.stem("crash", lufs=-25.5, width=1.2, eq=[("hp", 2000, 0, 0.7)])
    S.stem("perc", lufs=-23.0, verb2=0.2)
    S.stem("bass", lufs=-18.5, sc=0.5, eq=[("hp", 35, 0, 0.7), ("peak", 900, 2.0, 1.0)])
    S.stem("chug", lufs=-21.5, sc=0.35, width=1.5, eq=[("hp", 120, 0, 0.7)])
    S.stem("chords", lufs=-21.5, sc=0.55, verb=0.12, width=1.3, eq=[("hp", 200, 0, 0.7)])
    S.stem("pad", lufs=-24.5, sc=0.5, verb=0.3, width=1.4, eq=[("hp", 200, 0, 0.7)])
    sweep = [(0, 600), (12, 1200), (30, 9000), (32, 18000), (96 * 4, 18000), (99 * 4, 1500), (100 * 4, 600)]
    S.stem("gtr", lufs=-15.5, sc=0.12, verb=0.14, delay=0.1, eq=[("hp", 150, 0, 0.7)],
           post=auto_filter(S, sweep, res=0.15))
    S.stem("lead", lufs=-16.5, sc=0.15, verb=0.16, delay=0.12, eq=[("hp", 220, 0, 0.7), ("peak", 2800, 1.5, 1.0)])
    S.stem("lead2", lufs=-24.0, sc=0.2, verb=0.15, eq=[("hp", 150, 0, 0.7)])
    S.stem("bells", lufs=-22.5, sc=0.15, verb=0.3, delay=0.15, eq=[("hp", 400, 0, 0.7)])
    S.stem("arp", lufs=-24.0, sc=0.3, verb=0.15, delay=0.22, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("fx", lufs=-24.0, verb=0.25, width=1.3, eq=[("hp", 120, 0, 0.7)])

    HOOK = "Em C D B"
    VERSE = "Em C D Bm Em C D Bm C D Em Em Am B Em B"
    PRE = "C D Bm Em C D B B"
    CHO = "C D Bm Em C D Bm Em C D Bm Em C D B Em"
    SOLO = "Am B Em Em C D B B"
    BRK = "C D Bm Em C D B B"
    sec = {
        "intro": prog(HOOK + " " + HOOK, B(0)), "verse": prog(VERSE, B(8)), "pre": prog(PRE, B(24)),
        "cho1": prog(CHO, B(32)), "hook1": prog(HOOK + " " + HOOK, B(48)), "solo": prog(SOLO, B(56)),
        "brk": prog(BRK, B(64)), "cho2": prog(CHO, B(72)), "hook2": prog(HOOK + " " + HOOK, B(88)),
        "outro": prog(HOOK, B(96)),
    }
    riff = ("E5:1 E5:1 G5:1 E5:1 A5:2 G5:2 ^B5:3 A5:1 G5:2 E5:2 | C5:1 C5:1 E5:1 C5:1 G5:2 E5:2 ^A5:3 G5:1 E5:2 C5:2 | "
            "D5:1 D5:1 F#5:1 D5:1 A5:2 F#5:2 ^B5:3 A5:1 F#5:2 D5:2 | B4:1 B4:1 D#5:1 B4:1 F#5:2 D#5:2 ^A5:3 G5:1 F#5:2 D#5:2")
    riff_b = riff.rsplit("|", 1)[0] + "| B4:1 D#5:1 F#5:1 A5:1 B5:2 A5:2 F#5:2 ^B5:6"
    v1 = "B4:3 D5:1 E5:2 G5:2 F#5:4 E5:2 D5:2 | E5:6 r:10 | A4:3 B4:1 D5:2 F#5:2 E5:4 D5:2 A4:2 | B4:6 r:10"
    v1b = "B4:3 D5:1 E5:2 G5:2 F#5:4 E5:2 D5:2 | E5:6 r:10 | A4:3 B4:1 D5:2 F#5:2 E5:4 D5:2 A4:2 | B4:4 D5:4 F#5:8"
    v2 = "E5:3 G5:1 C6:4 B5:2 A5:2 G5:4 | F#5:3 A5:1 D6:4 C6:2 B5:2 A5:4 | B5:4 G5:4 E5:8 | E5:16"
    v3 = "C5:2 E5:2 A5:4 G5:2 E5:2 C5:4 | D#5:4 F#5:4 B5:8 | G5:2 B5:2 E6:4 D6:2 B5:2 G5:4 | F#5:4 A5:4 B5:8"
    bells_r = {1: "r:8 G6:2 E6:2 C6:2 G5:2", 3: "r:8 F#6:2 D6:2 B5:2 F#5:2"}
    pre = ("E5:2 G5:2 C6:4 B5:4 G5:4 | F#5:2 A5:2 D6:4 C6:4 A5:4 | B5:4 D6:4 F#6:8 | E6:8 D6:4 B5:4 | "
           "C6:4 B5:4 A5:4 G5:4 | A5:4 B5:4 C6:4 D6:4 | D#6:8 F#6:8 | ^B6:16")
    cho_a = "E5:2 G5:2 C6:4> B5:2 A5:2 G5:4 | F#5:2 A5:2 D6:4> C6:2 B5:2 A5:4 | B5:3 A5:1 B5:2 D6:2 F#6:4> E6:2 D6:2 | E6:6 D6:2 B5:4 G5:4"
    cho_b = "E5:2 G5:2 C6:4> B5:2 A5:2 G5:4 | F#5:2 A5:2 D6:4> E6:2 F#6:2 G6:4 | F#6:4> E6:4 D6:2 B5:2 D6:2 F#6:2 | ^E6:12 r:4"
    cho_b2 = "E5:2 G5:2 C6:4> B5:2 A5:2 G5:4 | F#5:2 A5:2 D6:4> E6:2 F#6:2 G6:4 | D#6:3 E6:1 F#6:4> B5:4 D#6:4 | ^E6:12 r:4"
    solo = ("A5:2 C6:2 E6:2 A6:4 G6:2 E6:2 D6:2 | D#6:2 F#6:2 B6:4 A6:2 F#6:2 D#6:4 | "
            "E6:1 G6:1 B6:1 G6:1 E6:1 G6:1 B6:1 G6:1 E6:1 G6:1 B6:1 E7:5 | ^D7:4 B6:4 G6:4 E6:4 | "
            "G6:1 E6:1 C6:1 E6:1 G6:1 E6:1 C6:1 E6:1 G6:2 A6:2 G6:2 E6:2 | "
            "F#6:1 D6:1 A5:1 D6:1 F#6:1 D6:1 A5:1 D6:1 F#6:2 G6:2 A6:2 B6:2 | ^B6:8 A6:2 G6:2 F#6:2 D#6:2 | F#6:16")
    gtr = dict(style="guitar", vib_rate=6.2, vib_depth=0.35, vib_delay=0.16, a=0.003, dcy=0.4, sus=0.85, rel=0.1,
               gate_frac=0.92, cents=7, glide=0.035, bend_time=0.11, amp=0.55)

    # drums (a bit busier: 16th hats, ride in chorus)
    drums(S, kit, B(0), 4, "intro", vel=0.9)
    drums(S, kit, B(4), 4, "full", fill=True, crash=True)
    drums(S, kit, B(8), 16, "verse", fill=True)
    drums(S, kit, B(24), 6, "verse")
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(30), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(30), 8, 4, 32, 0.25, 1.0)
    drums(S, kit, B(32), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(40)))
    drums(S, kit, B(48), 8, "full", fill=True)
    drums(S, kit, B(56), 8, "full", fill=True)
    drums(S, kit, B(64), 4, "hats", vel=0.8)
    drums(S, kit, B(68), 2, "kick", crash=False)
    M.play_pattern(S, "kick", kit.kick, EURO["kick"], B(70), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(68), 16, 4, 32, 0.2, 1.0, curve=1.3)
    drums(S, kit, B(72), 16, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(80)))
    drums(S, kit, B(88), 8, "full", fill=True)
    drums(S, kit, B(96), 4, "intro", crash=True, fill=True)
    for b0, nb in ((32, 16), (72, 16), (56, 8)):
        M.play_pattern(S, "perc", kit.ride, "x.x.x.x.x.x.x.x.", B(b0), nb, vel=0.5)

    # bass + palm-muted guitar chugs (power chords) in hooks / solo / intro
    for k in ("intro", "verse", "cho1", "hook1", "solo", "cho2", "hook2", "outro"):
        M.play_poly(S, "bass", octave_bass(sec[k]), M.v_bass, cut=320, env_amt=2800)
    M.play_poly(S, "bass", octave_bass(sec["pre"][:6], pattern="LL"), M.v_bass)
    M.play_poly(S, "bass", octave_bass(prog("B B", B(30)), pattern="L", step=0.25, vel=(0.8, 0.8)), M.v_bass)
    M.play_poly(S, "bass", [Note(B(64) + i * 4, 3.8, M.chord_root(c[2], 2), 0.7) for i, c in enumerate(sec["brk"][:4])],
                M.v_bass, cut=180, env_amt=600, sus=0.8, dcy=0.5, rel=0.3)
    M.play_poly(S, "bass", octave_bass(sec["brk"][4:], pattern="L", step=0.5), M.v_bass)
    chug_notes = []
    for k in ("intro", "hook1", "solo", "hook2", "outro"):
        for (t, dur, sym) in sec[k]:
            r = M.chord_root(sym, 3)
            for i in range(int(dur * 4)):
                if i % 16 in (0, 1, 3, 4, 6, 8, 9, 11, 12, 14):
                    v = 0.95 if i % 4 == 0 else 0.7
                    chug_notes += [Note(t + i * 0.25, 0.16, r, v), Note(t + i * 0.25, 0.16, r + 7, v * 0.8)]
    M.play_poly(S, "chug", chug_notes, lambda rng_, f, g, v: np.stack([d.lp(
        M._guitar(np.full(g + secs(0.03), f), rng_, 5)[:, 0], 2200.0) * d.adsr(g, 0.002, 0.08, 0.3, 0.03), ] * 2, -1) * v)

    stab = dict(a=0.002, dcy=0.12, sus=0.25, rel=0.12, cut=1800, env_amt=7000, fdec=0.09, cents=22)
    for k in ("cho1", "cho2"):
        M.play_chords(S, "chords", sec[k], M.v_supersaw, 55, 76, rhythm=offbeat_stabs, gate=1.0, vel=0.9, **stab)
    M.play_chords(S, "chords", sec["verse"], M.v_brass, 52, 71, rhythm=offbeat_stabs, gate=1.0, vel=0.7,
                  cut=800, env_amt=2800, fdec=0.07, rel=0.08)
    for k in ("verse", "pre", "brk", "cho1", "cho2", "solo"):
        M.play_chords(S, "pad", sec[k], M.v_pad, 50, 72, vel=0.8)

    # guitar lead: riff (intro/hooks/outro), chorus melody, solo
    for b0, txt in ((0, riff), (4, riff_b), (48, riff), (52, riff_b), (88, riff), (92, riff_b), (96, riff)):
        M.play_mono(S, "gtr", mel(txt, B(b0)), **{**gtr, "gate_frac": 0.8, "vib_depth": 0.2})
    for b0 in (32, 72):
        ch = mel(cho_a, B(b0)) + mel(cho_b, B(b0 + 4)) + mel(cho_a, B(b0 + 8)) + mel(cho_b2, B(b0 + 12))
        M.play_mono(S, "gtr", ch, **gtr)
        M.play_mono(S, "lead", ch, "supersaw", cut=2000, env_amt=3000, fdec=0.25, res=0.1, cents=16, mix=0.5,
                    vib_depth=0.2, glide=0.035, amp=0.35)
        M.play_mono(S, "lead2", shift(ch, tr=-12), "square", cut=1000, env_amt=2000, vib_depth=0.15)
        M.play_poly(S, "bells", arp(prog(CHO, B(b0)), lo=76, step=0.5, shape="updown", octaves=1, vel=0.45,
                                    gate=0.4), M.v_bell, amp_decay=0.35, index=1.6)
    M.play_mono(S, "gtr", mel(solo, B(56)), **{**gtr, "vib_depth": 0.45})
    # verse: synth lead call, bell response; pre on lead
    vl = mel(v1, B(8)) + mel(v1b, B(12)) + mel(v2, B(16)) + mel(v3, B(20))
    M.play_mono(S, "lead", vl, "saw", cut=1300, env_amt=3500, fdec=0.25, res=0.2, vib_depth=0.22)
    for b0 in (8, 12):
        for k, txt in bells_r.items():
            M.play_poly(S, "bells", mel(txt, B(b0 + k), vel=0.7), M.v_bell, amp_decay=0.5)
    M.play_mono(S, "gtr", mel(pre, B(24)), **gtr)
    M.play_poly(S, "arp", arp(sec["pre"], lo=64, step=0.25, shape="up", octaves=2, vel=0.5), M.v_pluck,
                cut=700, env_amt=4000, fdec=0.05)
    # breakdown
    M.play_poly(S, "bells", mel(cho_a, B(64), vel=0.75), M.v_bell, amp_decay=1.0, index=2.0)
    M.play_poly(S, "arp", arp(sec["brk"][4:], lo=59, step=0.25, shape="up", octaves=3, vel=0.6), M.v_pluck,
                cut=600, env_amt=5000, fdec=0.07)
    M.play_mono(S, "gtr", mel("D#6:8 F#6:8 | ^B6:16", B(70)), **gtr)

    fx_hits(S, "fx", B(28), "riser", rng, beats=16, f_lo=300, f_hi=10000)
    fx_hits(S, "fx", B(32), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(68), "riser", rng, beats=16, f_lo=250, f_hi=12000, tonal=(82, 660))
    fx_hits(S, "fx", B(72), "rev", rng, dur=S.sec(4))
    fx_hits(S, "fx", B(32), "sub", rng, dur=1.3, f0=95, f1=41)
    fx_hits(S, "fx", B(72), "sub", rng, dur=1.3, f0=95, f1=41)
    fx_hits(S, "fx", B(0), "rev", rng, dur=S.sec(2))
    orch_hit(S, "fx", B(48), [40, 47, 52, 55, 59], rng)
    orch_hit(S, "fx", B(88), [40, 47, 52, 55, 59], rng)
    sections = [("intro", 0), ("verse", 8), ("pre_chorus", 24), ("chorus_1", 32), ("hook", 48), ("guitar_solo", 56),
                ("breakdown", 64), ("chorus_2", 72), ("hook_2", 88), ("outro", 96)]
    return S, sections


# ======================================================================================== MENU
def menu():
    """MENU — 120 BPM neon synthwave / city-pop groove in D minor / F major. 44-bar loop."""
    S = M.Song("menu", 120, bars=44, seed=120)
    rng = np.random.default_rng(1200)
    kit = M.Kit(seed=77, kick=dict(f0=170, f1=50, ptau=0.025, adec=0.16, click=0.35, drive=1.6, sub=0.05),
                snare=dict(tone=180, noise_dec=0.2, gated=1.1, body=0.5, snap=0.9),
                hat=dict(dur=0.07, dec=0.028, tone=0.35, bright=10000.0), clap=dict(fc=1200, dec=0.14))
    B = lambda bar: bar * 4.0  # noqa: E731
    S.stem("kick", lufs=-18.0, eq=[("hp", 30, 0, 0.7)])
    S.stem("snare", lufs=-19.5, verb=0.12, verb2=0.15, eq=[("hp", 140, 0, 0.7)])
    S.stem("clap", lufs=-24.0, verb2=0.25, width=1.4)
    S.stem("hat", lufs=-25.5, pan=0.22, eq=[("hp", 5000, 0, 0.7)])
    S.stem("perc", lufs=-27.0, pan=-0.3, verb2=0.15)
    S.stem("crash", lufs=-27, width=1.2, eq=[("hp", 2500, 0, 0.7)])
    S.stem("bass", lufs=-18.0, sc=0.3, eq=[("hp", 35, 0, 0.7), ("peak", 700, 2.0, 1.0)])
    S.stem("ep", lufs=-20.0, sc=0.25, verb=0.2, delay=0.06, width=1.3, eq=[("hp", 150, 0, 0.7)])
    S.stem("pad", lufs=-23.0, sc=0.35, verb=0.35, width=1.5, eq=[("hp", 200, 0, 0.7)])
    S.stem("lead", lufs=-17.0, sc=0.1, verb=0.22, delay=0.2, eq=[("hp", 250, 0, 0.7)])
    S.stem("brass", lufs=-21.0, sc=0.2, verb=0.15, width=1.3, eq=[("hp", 200, 0, 0.7)])
    sweep = [(0, 900), (14, 5000), (16, 9000), (40 * 4, 9000), (43 * 4, 1500), (44 * 4, 900)]
    S.stem("arp", lufs=-23.5, sc=0.25, verb=0.15, delay=0.3, width=1.5, eq=[("hp", 300, 0, 0.7)],
           post=auto_filter(S, sweep, res=0.2))
    S.stem("bells", lufs=-23.0, verb=0.3, delay=0.2, eq=[("hp", 500, 0, 0.7)])
    S.stem("fx", lufs=-26.0, verb=0.3, width=1.3)

    LOOP = "Bbmaj7 A7 Dm7 Cm7:0.5 F7:0.5"
    PRE = "Gm7 Am7 Bbmaj7 C7sus4:0.5 C7:0.5"
    CHO = "Bbmaj7 C7 Am7 Dm7 Gm7 C7 Fmaj7 A7"
    BRK = "Gm7 Am7 Bbmaj7 C7sus4"
    sec = {
        "intro": prog(LOOP, B(0)), "verse": prog(LOOP + " " + LOOP, B(4)), "pre": prog(PRE, B(12)),
        "cho1": prog(CHO, B(16)), "inter": prog(LOOP, B(24)), "brk": prog(BRK, B(28)),
        "cho2": prog(CHO, B(32)), "outro": prog(LOOP, B(40)),
    }
    verse = ("r:2 D5:2 F5:2 A5:4 G5:2 F5:2 D5:2 | E5:4 C#5:2 E5:2 G5:4 r:4 | F5:2 E5:2 D5:2 C5:2 D5:4 A4:4 | "
             "Bb4:4 C5:2 Eb5:2 F5:4 r:4")
    verse2 = ("r:2 D5:2 F5:2 A5:4 G5:2 F5:2 D5:2 | E5:4 C#5:2 E5:2 G5:4 r:4 | F5:2 E5:2 D5:2 C5:2 D5:4 A4:4 | "
              "Bb4:2 C5:2 Eb5:2 F5:2 A5:4 C6:4")
    pre = "Bb5:4 A5:4 G5:4 D5:4 | C6:4 Bb5:4 A5:4 E5:4 | D6:4 C6:4 A5:4 F5:4 | G5:4 A5:4 Bb5:4 C6:4"
    cho = ("F5:3 G5:3 A5:2> D6:4 C6:4 | Bb5:3 A5:3 G5:2> E5:4 C5:4 | C6:3 D6:1 C6:2 E6:2> A5:4 G5:4 | "
           "F5:6 E5:2 D5:8 | Bb5:3 A5:3 G5:2> D6:4 C6:4 | Bb5:4 A5:2 G5:2 E5:4 G5:4 | A5:6 C6:2 E6:4> F6:4 | "
           "E6:4 C#6:4 A5:8")
    solo = ("D6:2 F6:2 A6:4 G6:2 F6:2 D6:4 | C#6:2 E6:2 G6:4 F6:2 E6:2 C#6:4 | D6:2 C6:2 A5:2 F5:2 A5:4 D6:4 | "
            "C6:4 Bb5:2 A5:2 G5:4 F5:4")
    resp = {1: "r:12 A6:1 G6:1 E6:2", 3: "r:12 C6:1 D6:1 F6:2"}

    # drums: LinnDrum-ish groove, big gated snare, 16th hats with swing feel via velocities
    hatp = "xgoxxgoxxgoxxgox"
    for b0, nb in ((4, 8), (16, 8), (32, 8)):
        M.play_pattern(S, "kick", kit.kick, "x.....x...x.....", b0 * 4, nb, is_kick=True)
        M.play_pattern(S, "snare", kit.snare, "....x.......x...", b0 * 4, nb)
        M.play_pattern(S, "clap", kit.clap, "............x...", b0 * 4, nb, vel=0.7)
        M.play_pattern(S, "hat", kit.hat, hatp, b0 * 4, nb, humanize=0.08)
        S.add("crash", kit.crash[0] * 0.7, S.s(b0 * 4))
    M.play_pattern(S, "kick", kit.kick, "x.....x...x.....", B(12), 4, is_kick=True)
    M.play_pattern(S, "snare", kit.snare, "....x.......x...", B(12), 3)
    M.roll(S, "snare", kit.snare, B(15), 4, 8, 16, 0.3, 0.9)
    M.play_pattern(S, "hat", kit.hat, hatp, B(12), 4, humanize=0.08)
    M.play_pattern(S, "kick", kit.kick, "x.....x...x.....", B(24), 4, is_kick=True)
    M.play_pattern(S, "snare", kit.snare, "....x.......x...", B(24), 4)
    M.play_pattern(S, "hat", kit.hat, hatp, B(24), 4, humanize=0.08)
    for b0, nb in ((0, 4), (28, 4), (40, 4)):
        M.play_pattern(S, "hat", kit.hat, "x.o.x.o.x.o.x.o.", B(b0), nb, vel=0.7, humanize=0.08)
    M.play_pattern(S, "perc", kit.shaker, "goxogoxogoxogoxo", B(0), 44, vel=0.8, humanize=0.1)
    M.play_pattern(S, "perc", kit.rim, "...x......x..x..", B(4), 8, vel=0.6)
    M.play_pattern(S, "perc", kit.rim, "...x......x..x..", B(32), 8, vel=0.6)
    M.roll(S, "snare", kit.snare, B(31), 4, 8, 16, 0.25, 0.85)

    # funky synth bass (16th syncopation with octave pops)
    funk = "L..LH.L.L..LH.LH"
    for k in ("verse", "pre", "cho1", "inter", "cho2"):
        M.play_poly(S, "bass", octave_bass(sec[k], pattern=funk, step=0.25, gate=0.7, vel=(0.95, 0.7)), M.v_bass,
                    cut=220, env_amt=1800, fdec=0.06, res=0.38, sub=0.5)
    for k in ("intro", "brk", "outro"):
        M.play_poly(S, "bass", octave_bass(sec[k], pattern="L.......L.......", step=0.25, gate=7.2, vel=(0.7, 0.7)),
                    M.v_bass, cut=200, env_amt=500, sus=0.8, dcy=0.4, rel=0.2)

    # e-piano comping (anticipations), pads, brass stabs in the chorus
    ep_r = comp_rhythm([(0.0, 1.4), (1.5, 0.45), (2.5, 0.9), (3.5, 0.45)])
    for k in sec:
        M.play_chords(S, "ep", sec[k], M.v_epiano, 57, 76, rhythm=ep_r, gate=0.95, vel=0.7, max_notes=4)
        M.play_chords(S, "pad", sec[k], M.v_pad, 53, 74, vel=0.7, cut=1800, cents=12)
    for k in ("cho1", "cho2"):
        M.play_chords(S, "brass", sec[k], M.v_brass, 60, 79, rhythm=comp_rhythm([(1.5, 0.3), (3.5, 0.3)]),
                      gate=1.0, vel=0.8, cut=1100, env_amt=3500, fdec=0.08)

    # arps throughout (filtered open in the intro, closed into the outro -> loop)
    M.play_poly(S, "arp", arp(prog(" ".join([LOOP] * 3) + " " + PRE + " " + CHO + " " + LOOP + " " + BRK + " " + CHO +
                                   " " + LOOP, 0.0), lo=65, step=0.25, shape="updown", octaves=2, vel=0.55),
                M.v_pluck, wave="square", cut=900, env_amt=3000, fdec=0.05, cents=6)

    lead = dict(cut=1600, env_amt=2600, fdec=0.25, res=0.12, vib_depth=0.18, vib_rate=5.2, glide=0.06, cents=6,
                pw_lfo=0.12, amp=0.5)
    M.play_mono(S, "lead", mel(verse, B(4)) + mel(verse2, B(8)), "square", **lead)
    for b0 in (4, 8):
        for k, txt in resp.items():
            M.play_poly(S, "bells", mel(txt, B(b0 + k), vel=0.7), M.v_bell, amp_decay=0.6, index=1.5)
    M.play_mono(S, "lead", mel(pre, B(12)), "square", **lead)
    M.play_mono(S, "lead", mel(cho, B(16)), "saw", **{**lead, "cut": 2000})
    M.play_mono(S, "lead", mel(solo, B(24)), "saw", **{**lead, "cut": 2400, "vib_depth": 0.25})
    M.play_mono(S, "lead", mel(cho, B(32)), "saw", **{**lead, "cut": 2200, "octave": 0.15})
    M.play_poly(S, "bells", mel(cho, B(28), vel=0.6)[:10], M.v_bell, amp_decay=1.0, index=1.8)
    M.play_poly(S, "bells", shift(mel(cho, B(32), vel=0.5), tr=12), M.v_bell, amp_decay=0.5, index=1.2)

    fx_hits(S, "fx", B(12), "riser", rng, beats=16, f_lo=400, f_hi=8000)
    fx_hits(S, "fx", B(16), "rev", rng, dur=S.sec(2))
    fx_hits(S, "fx", B(32), "rev", rng, dur=S.sec(2))
    sections = [("intro", 0), ("verse", 4), ("pre_chorus", 12), ("chorus_1", 16), ("interlude", 24),
                ("breakdown", 28), ("chorus_2", 32), ("outro", 40)]
    return S, sections


menu.mix = dict(delay=dict(t_l=0.375, t_r=0.5, fb=0.4, lpf=4000, hpf=300), duck=dict(rel=0.14),
                verb=dict(rt60=2.6, size=1.2, damp=0.4, predelay=0.03, hpf=220, lpf=8000))
shuto.mix = dict(verb=dict(rt60=2.6, size=1.2, damp=0.3, predelay=0.03, hpf=220, lpf=10000))


# ===================================================================================== TRAILER
TR_BPM = 150.0
TR_BEAT = 60.0 / TR_BPM            # 0.4 s
TR_CUT = 24.0                      # hard cut to silence
TR_DROP = 24.5                     # impact #1 + drop downbeat
TR_HIT = 64.0                      # impact #2 (final hit)
TR_END = 75.0
TR_DROP_BEAT = 60                  # global beat index of the drop downbeat (bar 15)
TR_BRK_BEAT = 140                  # breakdown starts (bar 35) -> 56.5 s
TR_BREATH_BEAT = 156               # breakdown ends (bar 39) -> 62.9 s; final hit grid restarts here
TR_BREATH = TR_DROP + (TR_BREATH_BEAT - TR_DROP_BEAT) * TR_BEAT   # 62.9 s: last breakdown bar line


def tr_time(b):
    """Global trailer beat -> seconds. Grid restarts after the 0.5 s cut and before the final hit."""
    if b < TR_DROP_BEAT:
        return b * TR_BEAT
    if b < TR_BREATH_BEAT:
        return TR_DROP + (b - TR_DROP_BEAT) * TR_BEAT
    return TR_HIT + (b - TR_BREATH_BEAT) * TR_BEAT


def braam(rng, notes, dur, peak=0.35):
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros((n, 2))
    for m in notes:
        f = float(d.mtof(m))
        x += d.supersaw(np.full(n, f), rng, 14, 0.6, 0.8) + 0.6 * np.stack([d.saw(np.full(n, f * 0.5), rng.uniform())] * 2, -1)
    u = t / dur
    fc = 120 + 1600 * np.clip(u / peak, 0, 1) ** 1.5 * np.exp(-np.maximum(u - peak, 0) / 0.25)
    x = d.lp24(x, fc, 0.35, 2.5)
    env = np.clip(t / 0.25, 0, 1) * np.exp(-np.maximum(t - dur * peak, 0) / (dur * 0.35))
    return d.fade_edges(np.tanh(1.8 * x * env[:, None]) / len(notes) ** 0.5, 0.01, 0.2)


def drone(rng, f, dur, cut0=120.0, cut1=900.0):
    n = secs(dur)
    t = np.arange(n) / SR
    u = t / dur
    fr = np.full(n, f) * (1 + 0.002 * np.sin(2 * np.pi * 0.13 * t))
    x = 0.9 * np.sin(2 * np.pi * np.cumsum(fr) / SR)
    sw = np.stack([d.saw(fr * 2 * 2 ** (c / 1200), rng.uniform()) for c in (-7, 7)], -1)
    sw = d.lp24(sw, cut0 * (cut1 / cut0) ** u, 0.3)
    y = x[:, None] * 0.8 + sw * 0.5
    env = np.clip(t / 2.5, 0, 1)
    return d.fade_edges(y * env[:, None], 0.01, 0.5)


def trailer_part_a():
    """0 - 24.0 s: ominous intro (sub drones, ticking hats, reverse swells) + build."""
    S = M.Song("trailerA", TR_BPM, length_s=TR_CUT, loop=False, seed=751, tail_s=0.5)
    rng = np.random.default_rng(7510)
    kit = M.Kit(seed=75, kick=dict(f0=280, f1=52, ptau=0.018, adec=0.11, click=0.6, drive=2.4, sub=0.05),
                snare=dict(tone=200, noise_dec=0.15, gated=0.6), hat=dict(dur=0.05, dec=0.012, tone=0.6, bright=8000.0))
    S.stem("drone", lufs=-24.0, eq=[("hp", 28, 0, 0.7)])
    S.stem("braam", lufs=-22.5, verb=0.25, width=1.3)
    S.stem("tick", lufs=-29.5, verb2=0.3, delay=0.1)
    S.stem("kick", lufs=-18.0)
    S.stem("snare", lufs=-20.0, verb2=0.2)
    S.stem("bass", lufs=-20.0, sc=0.4, eq=[("hp", 35, 0, 0.7)])
    S.stem("arp", lufs=-21.0, sc=0.3, verb=0.2, delay=0.2, width=1.4, eq=[("hp", 250, 0, 0.7)])
    S.stem("pad", lufs=-25.0, sc=0.3, verb=0.35, width=1.5, eq=[("hp", 150, 0, 0.7)])
    S.stem("bells", lufs=-26.0, verb=0.45, delay=0.25)
    S.stem("lead", lufs=-19.0, verb=0.25, delay=0.15, eq=[("hp", 220, 0, 0.7)])
    S.stem("fx", lufs=-22.5, verb=0.3, width=1.4, eq=[("hp", 60, 0, 0.7)])
    B = lambda bar: bar * 4.0  # noqa: E731
    # --- intro 0-8 s (bars 0-5)
    S.add("drone", drone(rng, float(d.mtof(26)), TR_CUT + 0.3, 90, 1400), 0)
    S.add("braam", braam(rng, [38, 41, 45, 50], 4.6), S.s(0))
    S.add("braam", braam(rng, [38, 41, 45, 50, 53], 3.4), S.s(12))
    for i in range(40):  # ticking hats, 8ths, alternating sides, slowly growing
        v = 0.35 + 0.65 * i / 40
        h = kit.hat[i % 4] * v
        S.add("tick", d.pan_mono(h, -0.5 if i % 2 else 0.5) / 1.41, S.s(i * 0.5))
    for i in range(0, 20, 1):
        S.add("tick", kit.rim[0] * (0.25 + 0.3 * (i % 4 == 0)), S.s(i))
    for end_beat, dur in ((8, 2.4), (16, 2.4), (20, 3.2)):
        sw = d.reverse_swell(rng, dur, bright=6500.0)
        S.add("fx", sw, S.s(end_beat) - sw.shape[0])
    bell_frag = mel("A5:4 D6:4 A5:4 G5:2 F5:2 | G5:4 A5:12", B(2), vel=0.6)
    M.play_poly(S, "bells", bell_frag, M.v_bell, amp_decay=1.4, index=1.8)
    M.play_chords(S, "pad", prog("Dmadd9:5", 0.0), M.v_pad, 50, 69, vel=0.6, a=3.0, cut=900)
    # --- build 8-24 s (bars 5-15)
    BUILD = "Dm Dm Bb Bb C C Gm Gm A A"
    ch = prog(BUILD, B(5))
    S.add("fx", d.boom(rng, 2.2) * 0.6, S.s(B(5)))
    for i, c in enumerate(ch):
        lo = 50 + int(round(i * 2.2))
        nts = arp([c], lo=lo, step=0.25, shape="updown", octaves=2, vel=0.45 + 0.05 * i)
        M.play_poly(S, "arp", nts, M.v_pluck, cut=350 + 450 * i, env_amt=1500 + 500 * i, fdec=0.06)
    M.play_chords(S, "pad", ch, M.v_pad, 52, 72, vel=0.7, cut=1200)
    M.play_poly(S, "bass", [Note(c[0] + k, 0.9, M.chord_root(c[2], 2), 0.7) for c in ch[:4] for k in range(4)], M.v_bass,
                cut=180, env_amt=900)
    M.play_poly(S, "bass", octave_bass(ch[4:]), M.v_bass)
    M.play_pattern(S, "kick", kit.kick, "x.......x.......", B(7), 4, is_kick=True)
    M.play_pattern(S, "kick", kit.kick, "x...x...x...x...", B(11), 3, is_kick=True)
    M.play_pattern(S, "kick", kit.kick, "x.x.x.x.x.x.x.x.", B(14), 1, is_kick=True)
    M.roll(S, "snare", kit.snare, B(11), 16, 4, 32, 0.15, 1.0, curve=1.15)
    M.play_pattern(S, "tick", kit.hat, "x.x.x.x.x.x.x.x.", B(5), 6, vel=0.7)
    M.play_pattern(S, "tick", kit.hat, "xxxxxxxxxxxxxxxx", B(11), 4, vel=0.8)
    S.add("fx", d.riser(rng, 24.0 - 9.6, 250, 11000, 2.0, 2.2), S.s(B(6)))
    S.add("fx", d.riser(rng, 6.4, 300, 12000, 3.0, 1.6, tonal=(110, 1760)), S.s(B(11)))
    M.play_mono(S, "lead", mel("G5:8 Bb5:8 | D6:12 C6:4 | C#6:8 E6:8 | A6:16", B(11)), "saw", cut=900, env_amt=3000,
                fdec=0.4, vib_depth=0.25, amp=0.5)
    return S


def trailer_part_b():
    """24.5 - 75 s: drop (24.5-56.5), breakdown/rise (56.5-62.9), breath, final hit 64.0 + ring-out."""
    def tmap(b):
        return tr_time(b) - TR_DROP
    S = M.Song("trailerB", TR_BPM, length_s=TR_END - TR_DROP, loop=False, seed=752, time_map=tmap)
    rng = np.random.default_rng(7520)
    kit = M.Kit(seed=76, kick=dict(f0=300, f1=55, ptau=0.016, adec=0.1, click=0.65, drive=2.4, sub=0.04),
                snare=dict(tone=200, noise_dec=0.15, gated=0.65))
    S.stem("kick", lufs=-17.0, eq=[("hp", 30, 0, 0.7)])
    S.stem("snare", lufs=-19.5, verb2=0.15, eq=[("hp", 120, 0, 0.7)])
    S.stem("clap", lufs=-21.5, verb2=0.2, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("hat", lufs=-26.0, pan=0.18, eq=[("hp", 4000, 0, 0.7)])
    S.stem("ohat", lufs=-27.0, pan=-0.15, eq=[("hp", 3500, 0, 0.7)])
    S.stem("crash", lufs=-25.0, width=1.2, eq=[("hp", 2000, 0, 0.7)])
    S.stem("perc", lufs=-24.0, verb2=0.2)
    S.stem("bass", lufs=-18.5, sc=0.5, eq=[("hp", 35, 0, 0.7), ("peak", 900, 1.5, 1.0)])
    S.stem("chords", lufs=-21.0, sc=0.55, verb=0.12, width=1.25, eq=[("hp", 180, 0, 0.7)])
    S.stem("pad", lufs=-23.5, sc=0.5, verb=0.3, width=1.4, eq=[("hp", 200, 0, 0.7)])
    S.stem("lead", lufs=-16.0, sc=0.12, verb=0.17, delay=0.12, eq=[("hp", 220, 0, 0.7), ("peak", 2800, 1.5, 1.0)])
    S.stem("lead2", lufs=-24.0, sc=0.2, verb=0.15, eq=[("hp", 150, 0, 0.7)])
    S.stem("riff", lufs=-16.5, sc=0.2, verb=0.12, delay=0.12, eq=[("hp", 220, 0, 0.7)])
    S.stem("bells", lufs=-22.5, sc=0.15, verb=0.35, delay=0.15, eq=[("hp", 400, 0, 0.7)])
    S.stem("arp", lufs=-24.0, sc=0.3, verb=0.15, delay=0.22, width=1.3, eq=[("hp", 300, 0, 0.7)])
    S.stem("impact", lufs=-15.5, verb=0.3, width=1.2)
    S.stem("fx", lufs=-22.0, verb=0.3, width=1.3, eq=[("hp", 60, 0, 0.7)])
    S.stem("ring", lufs=-21.0, verb=0.5, width=1.5, eq=[("hp", 40, 0, 0.7)])
    B = lambda bar: bar * 4.0  # noqa: E731
    HOOK = "Dm Bb C A"
    CHO8 = "Bb C Am Dm Bb C A Dm"
    cho_b2 = ("D5:2 F5:2 Bb5:4> A5:2 G5:2 F5:4 | E5:2 F5:2 G5:4 C6:4> D6:2 E6:2 | "
              "C#6:3 D6:1 E6:4> A5:4 C#6:4 | D6:12 r:4")
    sec = {"hk1": prog(HOOK + " " + HOOK, B(15)), "cho": prog(CHO8, B(23)), "hk2": prog(HOOK, B(31)),
           "brk": prog("Bb C A A", B(35))}
    # impact #1 exactly at the drop downbeat
    S.add("impact", d.boom(rng, 3.0), S.s(B(15)))
    orch_hit(S, "impact", B(15), [38, 50, 57, 62, 65, 69], rng, dur=1.2)
    fx_hits(S, "fx", B(15), "sub", rng, dur=1.6, f0=100, f1=34)
    # drums
    drums(S, kit, B(15), 8, "full", fill=True)
    drums(S, kit, B(23), 8, "full", fill=True)
    drums(S, kit, B(31), 4, "full", fill=True)
    S.add("crash", kit.crash[1] * 0.8, S.s(B(19)))
    S.add("crash", kit.crash[1] * 0.8, S.s(B(27)))
    # bass/chords
    for k in ("hk1", "cho", "hk2"):
        M.play_poly(S, "bass", octave_bass(sec[k]), M.v_bass)
    stab = dict(a=0.002, dcy=0.12, sus=0.25, rel=0.12, cut=1800, env_amt=7000, fdec=0.09, cents=24)
    for k in ("hk1", "cho", "hk2"):
        M.play_chords(S, "chords", sec[k], M.v_supersaw, 57, 79, rhythm=offbeat_stabs, gate=1.0, vel=0.85, **stab)
    M.play_chords(S, "pad", sec["cho"], M.v_pad, 50, 74, vel=0.8)
    # hook riff -> chorus -> hook
    for b0, txt in ((15, SHIBUYA_RIFF), (19, SHIBUYA_RIFF_B), (31, SHIBUYA_RIFF)):
        nts = mel(txt, B(b0))
        M.play_mono(S, "riff", nts, "supersaw", cut=2500, env_amt=6000, fdec=0.15, res=0.15, gate_frac=0.78,
                    vib_depth=0.0, cents=20, mix=0.65, octave=0.25)
        M.play_mono(S, "lead2", shift(nts, tr=-12), "square", cut=1200, env_amt=3000, gate_frac=0.75, vib_depth=0.0)
    ch = mel(SHIBUYA_CHO_A, B(23)) + mel(cho_b2, B(27))
    M.play_mono(S, "lead", ch, "supersaw", cut=2600, env_amt=5000, fdec=0.25, res=0.15, cents=18, mix=0.6,
                vib_depth=0.25, glide=0.04, octave=0.2)
    M.play_mono(S, "lead2", shift(ch, tr=-12), "square", cut=1100, env_amt=2500, vib_depth=0.15)
    M.play_poly(S, "bells", arp(sec["cho"], lo=79, step=0.5, shape="updown", octaves=1, vel=0.45, gate=0.4),
                M.v_bell, amp_decay=0.35, index=1.6)
    M.play_poly(S, "arp", arp(sec["cho"] + sec["hk2"], lo=67, step=0.25, shape="updown", octaves=2, vel=0.6),
                M.v_pluck, cut=900, env_amt=4500, fdec=0.06)
    orch_hit(S, "impact", B(23), [46, 53, 58, 62, 65], rng, vel=0.8)
    # breakdown / rise 56.5-62.9 (bars 35-38)
    M.play_chords(S, "pad", sec["brk"], M.v_pad, 52, 74, vel=0.9)
    M.play_poly(S, "bells", mel(SHIBUYA_CHO_A.split("|")[0] + "|" + SHIBUYA_CHO_A.split("|")[1], B(35), vel=0.8),
                M.v_bell, amp_decay=1.0, index=2.0)
    M.play_poly(S, "bass", [Note(B(35), 3.8, 46, 0.7), Note(B(36), 3.8, 48, 0.7)], M.v_bass, cut=180, env_amt=600,
                sus=0.8, dcy=0.5, rel=0.3)
    M.play_poly(S, "bass", octave_bass(sec["brk"][2:], pattern="L", step=0.25), M.v_bass)
    M.play_pattern(S, "kick", kit.kick, "x...x...x...x...", B(37), 2, is_kick=True)
    M.roll(S, "snare", kit.snare, B(37), 8, 8, 32, 0.2, 0.8, curve=1.2)
    M.play_poly(S, "arp", arp(sec["brk"][2:], lo=62, step=0.25, shape="up", octaves=3, vel=0.5), M.v_pluck,
                cut=700, env_amt=5000, fdec=0.07)
    M.play_mono(S, "lead", mel("C#6:8 E6:8 | A6:16", B(37)), "saw", cut=1600, env_amt=3000, vib_depth=0.3)
    S.add("fx", 0.5 * d.riser(rng, 6.4, 220, 13000, 2.5, 1.8, tonal=(110, 1760)), S.s(B(35)))
    S.add("crash", kit.crash[0] * 0.7, S.s(B(35)))
    # the breath: 62.9 -> 64.0 reverse swell sucking into the final hit
    rs = d.reverse_swell(rng, TR_HIT - TR_BREATH, bright=7000.0)          # 1.1 s, ends exactly at 64.0
    S.add("fx", rs * 1.3, S.s(TR_BREATH_BEAT) - rs.shape[0])
    # impact #2 at exactly 64.0 s + ring-out to 75 s
    S.add("impact", d.boom(rng, 5.0) * 1.1, S.s(TR_BREATH_BEAT))
    orch_hit(S, "impact", TR_BREATH_BEAT, [38, 50, 57, 62, 65, 69, 74], rng, dur=1.6)
    S.add("kick", kit.kick[0], S.s(TR_BREATH_BEAT))
    S.kicks.append((S.s(TR_BREATH_BEAT), 1.0))
    S.add("snare", kit.snare[0], S.s(TR_BREATH_BEAT))
    S.add("crash", kit.crash[0], S.s(TR_BREATH_BEAT))
    fx_hits(S, "fx", TR_BREATH_BEAT, "sub", rng, dur=3.0, f0=110, f1=30, tau=0.5)
    ring = []
    for m in (38, 45, 50, 53, 57, 62):
        ring.append(Note(TR_BREATH_BEAT, 18.0, m, 0.7))
    M.play_poly(S, "ring", ring, M.v_pad, a=0.02, rel=4.0, cut=1600, cents=14)
    S.add("ring", drone(rng, float(d.mtof(26)), 10.5, 400, 90) * 0.8, S.s(TR_BREATH_BEAT))
    M.play_poly(S, "bells", mel("A5:4 D6:4 A5:4 G5:2 F5:2 | G5:4 A5:12", TR_BREATH_BEAT + 4, vel=0.55), M.v_bell,
                amp_decay=1.6, index=1.6)
    for i in range(14):  # ticking hats return, fading out
        S.add("perc", kit.hat[i % 4] * 0.5 * (1 - i / 14), S.s(TR_BREATH_BEAT + 6 + i * 0.5))
    return S


def trailer():
    SA = trailer_part_a()
    SB = trailer_part_b()
    print("[trailer] mixing part A (0-24.0s)...")
    vA = dict(rt60=2.8, size=1.3, damp=0.35, predelay=0.03, hpf=200, lpf=8500)
    a = M.mixdown(SA, verb=vA, premaster=True, report=False, fx_sc=0.2)
    print("[trailer] mixing part B (24.5-75s)...")
    vB = dict(rt60=2.6, size=1.25, damp=0.3, predelay=0.025, hpf=200, lpf=9000)
    b = M.mixdown(SB, verb=vB, premaster=True, report=False)
    # relative level: the build peaks a little under the drop
    la = M.stem_lufs(a[secs(16.0): secs(24.0)])
    lb = M.stem_lufs(b[: secs(32.0)])
    a = a * d.dbg((lb - 2.0) - la)
    nA, nGap = secs(TR_CUT), secs(TR_DROP - TR_CUT)
    a = a[:nA].copy()
    r = secs(0.004)
    a[-r:] *= np.linspace(1, 0, r)[:, None]          # hard (but click-free) cut at 24.0 s
    b = b[: secs(TR_END) - nA - nGap].copy()
    fo = secs(TR_END - 72.0)                          # final fade: 72 -> 75 s
    b[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo)))[:, None]
    mix = np.concatenate([a, np.zeros((nGap, 2)), b])
    assert mix.shape[0] == secs(TR_END)
    S = M.Song("trailer", TR_BPM, length_s=TR_END, loop=False)
    out = M.master(S, mix, -14.0, -1.6)
    # the master's DC removal/limiter must not leak into the silent gap / tail
    out[secs(TR_CUT): secs(TR_DROP)] = 0.0
    out = d.fade_edges(out, 0.0, 0.01)
    return S, out


def trailer_cues():
    bars_a = [{"bar": i, "time_s": round(i * 4 * TR_BEAT, 3), "section": "intro" if i < 5 else "build"}
              for i in range(0, 15)]
    bars_b = [{"bar": i, "time_s": round(tr_time(i * 4), 3), "section": "drop" if i < 35 else "breakdown_rise"}
              for i in range(15, 39)]
    bars_c = [{"bar": 39 + k, "time_s": round(TR_HIT + k * 4 * TR_BEAT, 3), "section": "final_hit_ringout"}
              for k in range(0, 7)]
    beats = [round(tr_time(b), 3) for b in range(0, TR_BREATH_BEAT)]
    beats += [round(TR_HIT + k * TR_BEAT, 3) for k in range(0, int((TR_END - TR_HIT) / TR_BEAT))]
    return {
        "file": "trailer.mp3",
        "master_wav": "Tools/audio/out/trailer.wav",
        "bpm": TR_BPM,
        "duration_s": TR_END,
        "sample_rate": SR,
        "beat_s": TR_BEAT,
        "bar_s": 4 * TR_BEAT,
        "key": "D minor",
        "impacts_s": [TR_DROP, TR_HIT],
        "hard_cut_s": TR_CUT,
        "silence_s": [TR_CUT, TR_DROP],
        "drop_start_s": TR_DROP,
        "sections": [
            {"name": "intro", "start_s": 0.0, "end_s": 8.0, "bars": "0-4",
             "notes": "sub drone, low braams at 0.0 and 4.8, ticking hats, reverse swells ending at 3.2, 6.4, 8.0"},
            {"name": "build", "start_s": 8.0, "end_s": TR_CUT, "bars": "5-14",
             "notes": "rising arps, half-time kick from 11.2, 4-on-floor from 17.6, snare roll accelerating 17.6-24.0, "
                      "noise riser 9.6-24.0, kick 8ths in the last bar (22.4-24.0)"},
            {"name": "silence", "start_s": TR_CUT, "end_s": TR_DROP, "notes": "hard cut, digital silence"},
            {"name": "drop", "start_s": TR_DROP, "end_s": tr_time(TR_BRK_BEAT), "bars": "15-34",
             "notes": "impact + full eurobeat: hook riff 24.5, hook B 30.9, chorus 37.3, hook 50.1 (fill 54.9-56.5)"},
            {"name": "breakdown_rise", "start_s": tr_time(TR_BRK_BEAT), "end_s": round(TR_BREATH, 3), "bars": "35-38",
             "notes": "pads + bells, kick and accelerating snare roll from 59.7, riser"},
            {"name": "breath", "start_s": round(TR_BREATH, 3), "end_s": TR_HIT,
             "notes": "drums stop; reverse swell sucks into the final hit"},
            {"name": "final_hit_ringout", "start_s": TR_HIT, "end_s": TR_END,
             "notes": "impact + orchestral stab at 64.0, sustained D minor ring-out, bells 65.6, ticking hats 66.4-71.6, "
                      "fade 72-75"},
        ],
        "accents_s": {
            "braams": [0.0, 4.8], "build_start_hit": 8.0, "crashes": [24.5, 30.9, 37.3, 43.7, 50.1, 56.5, 64.0],
            "chorus_start": tr_time(23 * 4), "hook_return": tr_time(31 * 4),
        },
        "bars": bars_a + bars_b + bars_c,
        "beats_s": beats,
        "grid_note": ("150 BPM throughout (beat 0.4 s, bar 1.6 s). Three grid anchors: 0.0 s (intro/build, bars 0-14), "
                      "24.5 s (drop + breakdown, bars 15-38; the grid restarts after the 0.5 s silence) and 64.0 s "
                      "(final hit + ring-out, bars 39-45). The final hit lands 1.1 s after the last breakdown bar "
                      "line (62.9 s), filled by the 'breath' reverse swell."),
    }


# ------------------------------------------------------------------------------------ output
def decode(path):
    """Decode with ffmpeg (honours the LAME gapless header) -> float array (n, 2)."""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(float)


def render_trailer():
    import soundfile as sf
    t0 = time.time()
    print("[trailer] composing...")
    S, out = trailer()
    OUT.mkdir(parents=True, exist_ok=True)
    MUSIC.mkdir(parents=True, exist_ok=True)
    wav = OUT / "trailer.wav"
    sf.write(str(wav), np.clip(out, -1, 1), SR, subtype="PCM_24")
    mp3 = MUSIC / "trailer.mp3"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "320k", "-ar", str(SR),
                    "-ac", "2", str(mp3)], check=True)
    dec = decode(mp3)
    # alignment check: cross-correlate the onset region of the decoded mp3 against the master
    k0, k1 = secs(24.3), secs(25.3)
    ref = out[k0:k1, 0]
    best = max(range(-3000, 3001, 1), key=lambda o: float(np.dot(ref, dec[k0 + o:k1 + o, 0])) if k0 + o >= 0 else -1e9)
    cues = trailer_cues()
    cues["mp3"] = {"bitrate": "320k CBR", "encoder": "LAME (ffmpeg libmp3lame)",
                   "decoded_samples": int(dec.shape[0]), "offset_vs_master_samples": int(best),
                   "note": "LAME adds encoder priming (~1105 samples, 25 ms) that gapless-aware decoders (ffmpeg, most "
                           "NLEs) strip via the LAME header; if a tool ignores it, everything lands ~25 ms late. "
                           "The 24-bit master WAV has no offset."}
    meta = {"name": "trailer", "bpm": TR_BPM, "samples": int(out.shape[0]), "seconds": out.shape[0] / SR,
            "loop": False, "lufs": round(d.lufs(out), 2), "true_peak_dbtp": round(d.true_peak_db(out), 2),
            "mp3_lufs": round(d.lufs(dec), 2), "mp3_true_peak_dbtp": round(d.true_peak_db(dec), 2)}
    cues["loudness"] = {"lufs_integrated": meta["mp3_lufs"], "true_peak_dbtp": meta["mp3_true_peak_dbtp"]}
    (MUSIC / "trailer_cues.json").write_text(json.dumps(cues, indent=2))
    print(f"[trailer] done in {time.time() - t0:.1f}s  LUFS {meta['lufs']}  TP {meta['true_peak_dbtp']}  "
          f"mp3: LUFS {meta['mp3_lufs']} TP {meta['mp3_true_peak_dbtp']} offset {best} samples, {dec.shape[0]} samples")
    return S, out, meta


def render(name, fn):
    if name == "trailer":
        return render_trailer()
    t0 = time.time()
    print(f"[{name}] composing...")
    S, sections = fn()
    print(f"[{name}] mixing ({S.L / SR:.2f}s, {len(S.stems)} stems)...")
    out = M.mixdown(S, **getattr(fn, "mix", {}))
    out16 = M.dither16(out, seed=len(name))
    OUT.mkdir(parents=True, exist_ok=True)
    MUSIC.mkdir(parents=True, exist_ok=True)
    meta = {"name": name, "bpm": S.bpm, "samples": int(S.L), "seconds": round(S.L / SR, 4), "loop": S.loop,
            "lufs": round(d.lufs(out16), 2), "true_peak_dbtp": round(d.true_peak_db(out16), 2)}
    if S.loop:
        meta["loop_start_sample"] = 0
        meta["loop_end_sample"] = int(S.L)
        meta["sections"] = {k: {"bar": b, "time_s": round(S.s(b * 4) / SR, 4)} for k, b in sections}
        d.write_wav(MUSIC / f"{name}.wav", out16)
        d.write_wav(OUT / f"{name}.wav", out16)
        # reference OGG (libvorbis q6): Vorbis overshoots a little, so trim until decoded TP <= -1 dBTP
        import soundfile as sf
        trim = 0.0
        for _ in range(3):
            d.write_ogg(OUT / f"{name}.ogg", out16 * d.dbg(trim), 0.6)
            tp = d.true_peak_db(sf.read(str(OUT / f"{name}.ogg"))[0])
            if tp <= -1.05:
                break
            trim -= tp + 1.1
        meta["ogg_reference"] = {"file": f"Tools/audio/out/{name}.ogg", "trim_db": round(trim, 2),
                                 "true_peak_dbtp": round(float(tp), 2)}
    print(f"[{name}] done in {time.time() - t0:.1f}s  LUFS {meta['lufs']}  TP {meta['true_peak_dbtp']}")
    return S, out16, meta


TRACKS = {"menu": menu, "shibuya": shibuya, "shuto": shuto, "okutama": okutama, "trailer": trailer}


def main(names):
    metas = {}
    for n in names or TRACKS:
        _, _, meta = render(n, TRACKS[n])
        metas[n] = meta
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "music_meta.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(metas)
    p.write_text(json.dumps(old, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
