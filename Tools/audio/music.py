"""Tiny sequencer + instrument rack + mixer for INK DRIFT procedural music.

Song      timeline (beats -> samples), stems, circular (loop-seamless) note placement
mel()     compact melody notation:  "D5:2 F5:2 ~Bb5:4> r:2 _:2"
            NOTE:len   len in 16th notes (default 2 = an 8th)      r:len  rest
            _:len      tie (extend previous note)                 ~      glide into note
            >          accent                                     ^      bend up 2 semis into note
prog()    chord progressions "Dm Bb C A" (1 bar each) or "Dm:2 Bb:0.5" (bars)
voicing() voice-led chord voicings
voices    supersaw, bass, pluck, brass, pad, bell, e-piano, guitar(mono lead)...
mixdown() auto-levels stems to loudness targets, sidechain, FX sends (FDN reverb, ping-pong
          delay) processed circularly for loops, master bus (EQ, glue comp, soft clip,
          true-peak limiter) and loudness normalisation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

import inkdsp as d
from inkdsp import SR, TAU, secs, tvec

# ------------------------------------------------------------------------------ notation
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nn(name: str) -> int:
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d)", name)
    if not m:
        raise ValueError(name)
    pc = _PC[m.group(1).upper()] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc


@dataclass
class Note:
    t: float           # beats
    dur: float         # beats
    m: float           # midi
    vel: float = 0.85
    slide: bool = False
    bend: bool = False


def mel(s: str, t0: float = 0.0, unit: float = 0.25, vel: float = 0.85, tr: int = 0):
    notes: list[Note] = []
    t = t0
    for tok in s.split():
        if tok == "|":
            continue
        acc = ">" in tok
        name, _, ln = tok.replace(">", "").partition(":")
        L = float(ln) * unit if ln else 2 * unit
        if name == "r":
            t += L
            continue
        if name == "_":
            notes[-1].dur += L
            t += L
            continue
        slide = name.startswith("~")
        name = name.lstrip("~")
        bend = name.startswith("^")
        name = name.lstrip("^")
        notes.append(Note(t, L, nn(name) + tr, min(1.2, vel * (1.2 if acc else 1.0)), slide, bend))
        t += L
    return notes


def shift(notes, dt=0.0, tr=0, vel=1.0):
    return [Note(n.t + dt, n.dur, n.m + tr, n.vel * vel, n.slide, n.bend) for n in notes]


def span(notes):
    return max(n.t + n.dur for n in notes) if notes else 0.0


QUAL = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
    "sus4": (0, 5, 7), "sus2": (0, 2, 7), "dim": (0, 3, 6), "aug": (0, 4, 8), "add9": (0, 4, 7, 14),
    "madd9": (0, 3, 7, 14), "9": (0, 4, 7, 10, 14), "m9": (0, 3, 7, 10, 14), "maj9": (0, 4, 7, 11, 14),
    "5": (0, 7), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "7sus4": (0, 5, 7, 10), "13": (0, 4, 10, 14, 21),
    "m11": (0, 3, 7, 10, 17), "7b9": (0, 4, 7, 10, 13),
}


def parse_chord(sym: str):
    m = re.fullmatch(r"([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?", sym)
    if not m:
        raise ValueError(sym)
    root = nn(m.group(1) + "0") % 12
    ivs = QUAL[m.group(2)]
    bass = nn(m.group(3) + "0") % 12 if m.group(3) else root
    return root, ivs, bass


def chord_root(sym, octave=2):
    _, _, bass = parse_chord(sym)
    return 12 * (octave + 1) + bass


def voicing(sym, lo=55, hi=79, prev=None, max_notes=4):
    root, ivs, _ = parse_chord(sym)
    pcs = []
    for iv in ivs:
        pc = (root + iv) % 12
        if pc not in pcs:
            pcs.append(pc)
    if len(pcs) > max_notes:  # drop the fifth first
        fifth = (root + 7) % 12
        if fifth in pcs:
            pcs.remove(fifth)
        pcs = pcs[:max_notes]
    cands = []
    for k in range(len(pcs)):
        order = pcs[k:] + pcs[:k]
        for base_oct in range(2, 7):
            notes = []
            cur = 12 * base_oct + order[0]
            if cur < lo:
                continue
            notes.append(cur)
            for pc in order[1:]:
                nxt = notes[-1] + ((pc - notes[-1]) % 12 or 12)
                notes.append(nxt)
            if notes[-1] <= hi:
                cands.append(notes)
            break
    if not cands:
        cands = [[12 * 4 + pc for pc in sorted(pcs)]]
    if prev is None:
        mid = (lo + hi) / 2
        return min(cands, key=lambda c: abs(np.mean(c) - mid))
    return min(cands, key=lambda c: sum(abs(a - b) for a, b in zip(sorted(c), sorted(prev))) + abs(len(c) - len(prev)))


def prog(spec: str, t0: float = 0.0, bar_beats: float = 4.0):
    out = []
    t = t0
    for tok in spec.split():
        sym, _, ln = tok.partition(":")
        bars = float(ln) if ln else 1.0
        out.append((t, bars * bar_beats, sym))
        t += bars * bar_beats
    return out


def chord_at(chords, t):
    for c in chords:
        if c[0] <= t < c[0] + c[1]:
            return c[2]
    return chords[-1][2]


# -------------------------------------------------------------------------------- the song
class Stem:
    def __init__(self, name, n, lufs=None, gain_db=0.0, pan=0.0, width=1.0, eq=None, sc=0.0,
                 verb=0.0, verb2=0.0, delay=0.0, post=None):
        self.name = name
        self.buf = np.zeros((n, 2))
        self.lufs = lufs
        self.gain_db = gain_db
        self.pan = pan
        self.width = width
        self.eq = eq or []
        self.sc = sc
        self.verb = verb
        self.verb2 = verb2
        self.delay = delay
        self.post = post


class Song:
    def __init__(self, name, bpm, bars=None, length_s=None, loop=True, seed=1, tail_s=0.0, time_map=None):
        self.name = name
        self.bpm = bpm
        self.spb = SR * 60.0 / bpm
        self.loop = loop
        self.L = int(round(bars * 4 * self.spb)) if bars is not None else secs(length_s)
        self.N = self.L if loop else self.L + secs(tail_s)
        self.time_map = time_map
        self.stems: dict[str, Stem] = {}
        self.rng = np.random.default_rng(seed)
        self.kicks: list[tuple[int, float]] = []
        self.markers: dict[str, float] = {}

    def s(self, beat):
        if self.time_map is not None:
            return secs(self.time_map(beat))
        return int(round(beat * self.spb))

    def sec(self, beats):
        return beats * 60.0 / self.bpm

    def stem(self, name, **kw):
        if name not in self.stems:
            self.stems[name] = Stem(name, self.N, **kw)
        return self.stems[name]

    def add(self, name, sig, pos):
        buf = self.stems[name].buf
        if sig.ndim == 1:
            sig = np.stack([sig, sig], axis=-1)
        n = sig.shape[0]
        if self.loop:
            p = pos % self.L
            k = 0
            while k < n:
                seg = min(n - k, self.L - p)
                buf[p: p + seg] += sig[k: k + seg]
                k += seg
                p = 0
        else:
            if pos < 0:
                sig = sig[-pos:]
                n = sig.shape[0]
                pos = 0
            e = min(self.N, pos + n)
            if e > pos:
                buf[pos:e] += sig[: e - pos]


# ----------------------------------------------------------------------------------- voices
def v_supersaw(rng, f, gate, vel, a=0.004, dcy=0.35, sus=0.75, rel=0.3, cut=3500.0, env_amt=5000.0,
               fdec=0.22, res=0.12, cents=22.0, mix=0.75, spread=1.0, keytrack=0.4):
    n = gate + secs(rel)
    x = d.supersaw(np.full(n, f), rng, cents, mix, spread)
    t = tvec(n)
    fc = cut * (f / 440.0) ** keytrack + env_amt * vel * np.exp(-t / fdec)
    x = d.lp24(x, fc, res)
    env = d.adsr(gate, a, dcy, sus, rel, n_total=n)
    return x * (env * vel)[:, None] * 0.5


def v_pad(rng, f, gate, vel, a=0.35, rel=0.9, cut=2200.0, cents=16.0, mix=0.55, lfo=0.25):
    n = gate + secs(rel)
    t = tvec(n)
    x = d.supersaw(np.full(n, f), rng, cents, mix, 1.0)
    fc = cut * (1 + 0.25 * np.sin(TAU * lfo * t + rng.uniform(0, TAU)))
    x = d.lp24(x, fc, 0.1)
    env = d.adsr(gate, a, 0.5, 0.85, rel, n_total=n)
    return x * (env * vel)[:, None] * 0.4


def v_bass(rng, f, gate, vel, cut=260.0, env_amt=2400.0, fdec=0.075, res=0.32, sub=0.4, rel=0.035,
           dcy=0.16, sus=0.55, drive=1.6, pw=0.5):
    n = gate + secs(rel)
    t = tvec(n)
    fr = np.full(n, f)
    x = 0.7 * d.saw(fr, 0.0) + 0.45 * d.pulse(fr * 1.003, np.full(n, pw), 0.25)
    fc = cut + env_amt * vel * np.exp(-t / fdec)
    x = d.lp24(x, fc, res, drive)
    x += sub * np.sin(TAU * f * t)
    env = d.adsr(gate, 0.0015, dcy, sus, rel, n_total=n)
    return x * env * vel


def v_pluck(rng, f, gate, vel, cut=700.0, env_amt=6000.0, fdec=0.07, res=0.25, wave="saw", rel=0.08,
            cents=9.0, sus=0.0, dcy=0.25, pan=0.0):
    n = gate + secs(rel)
    t = tvec(n)
    fr = np.full(n, f)
    if wave == "saw":
        a = d.saw(fr * 2 ** (cents / 1200), rng.uniform())
        b = d.saw(fr * 2 ** (-cents / 1200), rng.uniform())
    else:
        a = d.pulse(fr * 2 ** (cents / 1200), np.full(n, 0.5), rng.uniform())
        b = d.pulse(fr * 2 ** (-cents / 1200), np.full(n, 0.5), rng.uniform())
    fc = cut + env_amt * vel * np.exp(-t / fdec)
    x = d.lp24(np.stack([a, b], -1), fc, res)
    env = d.adsr(gate, 0.001, dcy, sus, rel, n_total=n)
    return x * (env * vel)[:, None] * 0.6


def v_brass(rng, f, gate, vel, cut=900.0, env_amt=3500.0, fdec=0.12, res=0.15, rel=0.12, a=0.012):
    n = gate + secs(rel)
    t = tvec(n)
    fr = np.full(n, f)
    att = np.clip(t / 0.03, 0, 1)
    x = sum(d.saw(fr * 2 ** (c / 1200), rng.uniform()) for c in (-11, 0, 9))
    y = d.saw(fr * 2 ** (6 / 1200), rng.uniform())
    st = np.stack([x + 0.5 * y, x - 0.3 * y], -1) / 3
    fc = cut + env_amt * vel * att * np.exp(-t / fdec)
    st = d.lp24(st, fc, res)
    env = d.adsr(gate, a, 0.25, 0.7, rel, n_total=n)
    return st * (env * vel)[:, None]


def v_bell(rng, f, gate, vel, ratio=3.5, index=2.2, idx_decay=0.25, amp_decay=0.9, ring=4.0):
    n = max(gate, secs(amp_decay * ring))
    x = d.fm_bell(f, n, ratio=ratio, index=index * (0.6 + 0.5 * vel), idx_decay=idx_decay,
                  amp_decay=amp_decay, detune=0.0015)
    return x * vel * 0.6


def v_epiano(rng, f, gate, vel, r=0.4):
    x = d.fm_epiano(f, gate, vel, r)
    t = tvec(x.shape[0])
    trem = 0.12 * np.sin(TAU * 4.2 * t)
    return np.stack([x * (1 + trem), x * (1 - trem)], -1) * vel * 0.55


def v_sine_sub(rng, f, gate, vel, rel=0.08, a=0.01):
    n = gate + secs(rel)
    return np.sin(TAU * f * tvec(n)) * d.adsr(gate, a, 0.3, 0.9, rel, n_total=n) * vel


# ----------------------------------------------------------------------------------- players
def play_poly(song, stem, notes, voice, **kw):
    for n in notes:
        p0 = song.s(n.t)
        gate = max(32, song.s(n.t + n.dur) - p0)
        sig = voice(song.rng, float(d.mtof(n.m)), gate, n.vel, **kw)
        song.add(stem, sig, p0)


def play_chords(song, stem, chords, voice, lo=55, hi=79, rhythm=None, gate=0.9, vel=0.8, max_notes=4,
                add_bass=False, **kw):
    """rhythm: list of (offset_beats, dur_beats) within each chord, default: whole chord length."""
    prev = None
    for (t, dur, sym) in chords:
        v = voicing(sym, lo, hi, prev, max_notes)
        prev = v
        hits = rhythm(dur) if callable(rhythm) else (rhythm or [(0.0, dur)])
        for (o, ln) in hits:
            if o >= dur:
                continue
            for m in v:
                p0 = song.s(t + o)
                g = max(32, song.s(t + o + ln * gate) - p0)
                song.add(stem, voice(song.rng, float(d.mtof(m)), g, vel, **kw), p0)


def _phrases(notes, tol=1e-3):
    notes = sorted(notes, key=lambda n: n.t)
    out = []
    cur = []
    for n in notes:
        if cur and n.t - (cur[-1].t + cur[-1].dur) > 0.26:
            out.append(cur)
            cur = []
        cur.append(n)
    if cur:
        out.append(cur)
    return out


def play_mono(song, stem, notes, style="saw", glide=0.05, vib_rate=5.6, vib_depth=0.22, vib_delay=0.22,
              a=0.006, dcy=0.3, sus=0.8, rel=0.14, cut=2200.0, env_amt=4500.0, fdec=0.18, res=0.2,
              gate_frac=0.88, cents=9.0, octave=0.0, sub=0.0, drive=1.0, mix=0.7, keytrack=0.6,
              amp=0.5, bend_time=0.09, pw_lfo=0.0):
    """Monophonic lead with legato/glide, delayed vibrato, bends and filter envelope."""
    for ph in _phrases(notes):
        p0 = song.s(ph[0].t)
        pend = song.s(ph[-1].t + ph[-1].dur)
        n = pend - p0 + secs(rel) + secs(0.02)
        semis = np.full(n, float(ph[0].m))
        gate = np.zeros(n)
        trig = np.zeros(n)
        vel = np.zeros(n)
        vibenv = np.zeros(n)
        bendarr = np.zeros(n)
        glide_mask = np.zeros(n)
        for i, nt in enumerate(ph):
            a0 = song.s(nt.t) - p0
            b0 = song.s(nt.t + nt.dur) - p0
            nxt = ph[i + 1] if i + 1 < len(ph) else None
            legato_next = nxt is not None and nxt.slide
            gl = b0 if legato_next else a0 + max(int((b0 - a0) * gate_frac), secs(0.03))
            semis[a0:] = nt.m
            gate[a0:gl] = 1.0
            if not nt.slide:
                trig[a0] = 1.0
            else:
                glide_mask[a0: a0 + secs(glide * 4)] = 1.0
            vel[a0:] = nt.vel
            tt = np.arange(n - a0) / SR
            vibenv[a0:] = np.clip((tt - vib_delay) / 0.25, 0, 1)
            if nt.bend:
                k = min(secs(bend_time), n - a0)
                bendarr[a0: a0 + k] = -2.0 * (1 - np.linspace(0, 1, k)) ** 2
        # pitch smoothing: glide where slides happen, ~3 ms elsewhere
        coef = np.where(glide_mask > 0, 1 - np.exp(-1 / (glide * SR / 2.5)), 1 - np.exp(-1 / (0.003 * SR)))
        sm = d.onepole_var(semis - semis[0], coef) + semis[0]
        t = tvec(n)
        vib = vib_depth * vibenv * np.sin(TAU * vib_rate * t)
        f = d.mtof(sm + vib + bendarr)
        vel = d.smooth(vel, 4.0)
        aenv = d.adsr_sm(gate, trig, a, dcy, sus, rel, False)
        fenv = d.adsr_sm(gate, trig, 0.002, fdec, 0.0, 0.2, True)
        rng = song.rng
        if style == "saw":
            l = d.saw(f * 2 ** (cents / 1200), rng.uniform()) + 0.5 * d.pulse(f, np.full(n, 0.42), rng.uniform())
            r = d.saw(f * 2 ** (-cents / 1200), rng.uniform()) + 0.5 * d.pulse(f, np.full(n, 0.42), rng.uniform())
            x = np.stack([l, r], -1)
        elif style == "square":
            pw = 0.5 + pw_lfo * np.sin(TAU * 0.7 * t)
            l = d.pulse(f * 2 ** (cents / 1200), pw, rng.uniform())
            r = d.pulse(f * 2 ** (-cents / 1200), 1 - pw, rng.uniform())
            x = np.stack([l, r], -1) * 0.8
        elif style == "supersaw":
            x = d.supersaw(f, rng, cents, mix, 1.0)
        elif style == "guitar":
            x = _guitar(f, rng, cents)
        else:
            raise ValueError(style)
        if octave:
            x = x + octave * np.stack([d.saw(f * 2.0, rng.uniform())] * 2, -1)
        if style != "guitar":
            fc = (cut * (f / 440.0) ** keytrack + env_amt * fenv * vel)
            x = d.lp24(x, fc, res, drive)
        if sub:
            x = x + sub * np.sin(TAU * np.cumsum(f * 0.5) / SR)[:, None]
        song.add(stem, x * (aenv * vel)[:, None] * amp, p0)


def _guitar(f, rng, cents):
    """Distorted 'guitar-like' lead: detuned saws -> pre-EQ -> 2x oversampled asymmetric
    waveshaper -> cabinet-ish EQ. Returns stereo (n, 2)."""
    from scipy import signal as sps
    n = f.shape[0]
    src = d.saw(f * 2 ** (cents / 1200), rng.uniform()) + d.saw(f * 2 ** (-cents / 1200), rng.uniform())
    src += 0.35 * d.pulse(f * 0.5, np.full(n, 0.5), rng.uniform())
    src = d.eq(src, [("hp", 180, 0, 0.7), ("peak", 900, 4.0, 0.9)])
    up = sps.resample_poly(src, 2, 1)
    k = 9.0
    bias = 0.18
    y = np.tanh(k * (up + bias)) - np.tanh(k * bias)
    y = sps.resample_poly(y, 1, 2)[:n]
    y = d.eq(y, [("hp", 110, 0, 0.7), ("peak", 420, -4.0, 1.2), ("peak", 1900, 5.0, 1.0),
                 ("lp", 4800, 0, 0.7), ("lp", 5600, 0, 0.7), ("peak", 3200, 2.0, 2.0)])
    yl = y
    yr = np.concatenate([np.zeros(secs(0.011)), y])[:n] * 0.92  # double-tracked feel
    return np.stack([yl + 0.35 * yr, yr + 0.35 * yl], -1) * 0.5


# ------------------------------------------------------------------------------------ drums
class Kit:
    def __init__(self, seed=7, kick=None, snare=None, clap=None, hat=None, ohat=None):
        r = np.random.default_rng(seed)
        self.kick = [d.kick(r, **(kick or {})) for _ in range(2)]
        self.snare = [d.snare(r, **(snare or {"gated": 0.7})) for _ in range(3)]
        self.clap = [d.clap(r, **(clap or {})) for _ in range(3)]
        self.hat = [d.hat(r, **(hat or {})) for _ in range(4)]
        self.ohat = [d.hat(r, **(ohat or {"dur": 0.4, "dec": 0.12, "open_": True})) for _ in range(2)]
        self.crash = [d.crash(r) for _ in range(2)]
        self.ride = [d.ride(r)]
        self.tom = {f: d.tom(r, f) for f in (82.0, 110.0, 147.0, 196.0)}
        self.rim = [d.hp(d.bp(d.noise(secs(0.05), r), 1700, 4), 400) * d.perc(secs(0.05), 0.0003, 0.01)]
        self.shaker = [d.hp(d.noise(secs(0.07), r), 6000) * d.perc(secs(0.07), 0.008, 0.02) for _ in range(4)]


VEL = {"x": 0.85, "X": 1.0, "o": 0.55, "g": 0.3, "1": 0.2, "2": 0.35, "3": 0.5, "4": 0.65, "5": 0.8}


def play_pattern(song, stem, samples, pattern, t0, bars, steps=16, beats_per_bar=4.0, is_kick=False,
                 humanize=0.0, vel=1.0):
    """pattern: string of step characters (len multiple of `steps`, cycled per bar)."""
    pat = pattern.replace(" ", "").replace("|", "")
    nb = len(pat) // steps
    step = beats_per_bar / steps
    rng = song.rng
    k = 0
    for b in range(int(np.ceil(bars))):
        seg = pat[(b % nb) * steps: (b % nb + 1) * steps]
        for i, ch in enumerate(seg):
            tb = t0 + b * beats_per_bar + i * step
            if tb >= t0 + bars * beats_per_bar - 1e-9:
                break
            if ch in VEL:
                v = VEL[ch] * vel * (1 + humanize * rng.uniform(-1, 1))
                smp = samples[k % len(samples)]
                k += 1
                p = song.s(tb)
                song.add(stem, smp * v, p)
                if is_kick:
                    song.kicks.append((p, v))


def roll(song, stem, samples, t0, beats, start_div=4, end_div=32, v0=0.3, v1=1.0, curve=1.0):
    """Accelerating snare roll from start_div to end_div notes per bar (beats_per_bar=4)."""
    t = 0.0
    k = 0
    while t < beats - 1e-6:
        x = t / beats
        div = start_div * (end_div / start_div) ** (x ** curve)
        stepb = 4.0 / div
        v = v0 + (v1 - v0) * x ** 1.3
        song.add(stem, samples[k % len(samples)] * v, song.s(t0 + t))
        k += 1
        t += stepb


# ------------------------------------------------------------------------------------ mixing
import os  # noqa: E402

STEM_DUMP = os.environ.get("INK_STEMS")  # dump post-fader stems for inspection
def duck_env(song, depth=0.5, att=0.004, hold=0.012, rel=0.2, shape=1.8):
    if not song.kicks or depth <= 0:
        return np.ones(song.N)
    imp = np.zeros(song.N)
    for p, v in song.kicks:
        if song.loop:
            imp[p % song.L] = max(imp[p % song.L], min(1.0, v / 0.85))
        elif 0 <= p < song.N:
            imp[p] = max(imp[p], min(1.0, v / 0.85))
    na, nh, nr = secs(att), secs(hold), secs(rel)
    ker = np.concatenate([np.linspace(0, 1, na, endpoint=False), np.ones(nh), (1 - np.linspace(0, 1, nr)) ** shape])
    # the kernel attack is placed *before* the kick so the duck is fully down on the hit
    nfft = song.N if song.loop else song.N + ker.shape[0]
    K = np.zeros(nfft)
    K[: ker.shape[0]] = ker
    K = np.roll(K, -na)
    I = np.zeros(nfft)
    I[: song.N] = imp
    env = np.fft.irfft(np.fft.rfft(I) * np.fft.rfft(K), nfft)[: song.N]
    env = np.clip(env, 0, 1)
    return 1 - depth * env


def _proc(song, x, fn, tail=0.0):
    """Apply fn to a full-length stereo buffer in a loop-safe way."""
    if song.loop:
        if tail > 0:
            return d.circ_lti(fn, x, tail)
        return d.circ(fn, x, pre=secs(2.0), post=secs(0.05))
    if tail > 0:
        y = fn(np.concatenate([x, np.zeros((secs(tail), x.shape[1]))]))
        return y[: x.shape[0]]
    return fn(x)


def stem_lufs(x):
    try:
        v = d.lufs(x)
    except Exception:  # noqa: BLE001
        return -70.0
    return v if np.isfinite(v) else -70.0


def mixdown(song, verb=None, verb2=None, delay=None, master_lufs=-14.0, ceiling=-1.5, report=True,
            master_eq=None, glue=None, duck=None, fx_sc=0.35, mutes=None, post_mix=None,
            premaster=False):
    verb = verb or dict(rt60=2.2, size=1.1, damp=0.35, predelay=0.025, hpf=220, lpf=9000)
    verb2 = verb2 or dict(rt60=0.9, size=0.6, damp=0.3, predelay=0.008, hpf=200, lpf=8000)
    delay = delay or dict(t_l=song.sec(0.75), t_r=song.sec(0.5), fb=0.38, lpf=4500, hpf=300)
    N = song.N
    dry = np.zeros((N, 2))
    vin = np.zeros((N, 2))
    v2in = np.zeros((N, 2))
    din = np.zeros((N, 2))
    duck = duck or {}
    envs = {}
    info = {}
    for name, st in song.stems.items():
        x = st.buf
        if not np.any(x):
            continue
        if st.eq:
            x = _proc(song, x, lambda z, e=st.eq: d.eq(z, e))
        if st.post is not None:
            x = st.post(x)
        if st.lufs is not None:
            lv = stem_lufs(x)
            g = st.lufs - lv
            x = x * d.dbg(g)
            info[name] = (round(lv, 1), round(g, 1))
        x = x * d.dbg(st.gain_db)
        if st.pan:
            th = (st.pan + 1) * np.pi / 4
            x = np.stack([x[:, 0] * np.cos(th) * 1.414, x[:, 1] * np.sin(th) * 1.414], -1)
        if st.width != 1.0:
            x = d.width(x, st.width)
        if st.sc > 0:
            key = round(st.sc, 3)
            if key not in envs:
                envs[key] = duck_env(song, st.sc, **duck)
            x = x * envs[key][:, None]
        dry += x
        if STEM_DUMP:
            import soundfile as sf
            from pathlib import Path
            pth = Path(STEM_DUMP) / song.name
            pth.mkdir(parents=True, exist_ok=True)
            sf.write(str(pth / f"{name}.wav"), np.clip(x, -1, 1), SR, subtype="FLOAT")
        if st.verb:
            vin += x * st.verb
        if st.verb2:
            v2in += x * st.verb2
        if st.delay:
            din += x * st.delay
    fx = np.zeros((N, 2))
    if np.any(vin):
        fx += _proc(song, vin, lambda z: d.reverb(z, **verb), tail=verb["rt60"] * 1.8)
    if np.any(v2in):
        fx += _proc(song, v2in, lambda z: d.reverb(z, **verb2), tail=verb2["rt60"] * 2.0)
    if np.any(din):
        fx += _proc(song, din, lambda z: d.pingpong(z, **delay), tail=6.0)
    if fx_sc > 0:
        fx *= duck_env(song, fx_sc, **duck)[:, None]
    mix = dry + fx
    if mutes:
        g = np.ones(N)
        r = secs(0.003)
        for (a0, a1) in mutes:
            i0, i1 = secs(a0), secs(a1)
            g[i0:i1] = 0.0
            g[max(0, i0 - r):i0] = np.linspace(1, 0, min(r, i0))
        mix = mix * g[:, None]
    if post_mix is not None:
        mix = post_mix(mix)
    if premaster:
        if report:
            for k, v in info.items():
                print(f"    stem {k:10s} measured {v[0]:6.1f} LUFS  gain {v[1]:+6.1f} dB")
        return mix
    out = master(song, mix, master_lufs, ceiling, master_eq, glue)
    if report:
        for k, v in info.items():
            print(f"    stem {k:10s} measured {v[0]:6.1f} LUFS  gain {v[1]:+6.1f} dB")
    return out


def master(song, mix, target=-14.0, ceiling=-1.5, master_eq=None, glue=None):
    meq = master_eq or [("hp", 30, 0, 0.7), ("lowshelf", 80, -1.5, 0.7), ("peak", 280, -1.5, 0.9),
                        ("highshelf", 9500, 1.5, 0.7)]
    glue = glue or dict(thr_db=-15.0, ratio=2.0, att=0.015, rel=0.18, knee=8.0, rms_ms=15.0)
    ref = mix * d.dbg(-18.0 - stem_lufs(mix))
    pre = _proc(song, ref, lambda z: d.compress(d.eq(z, meq), **glue)[0])
    g = 0.0
    out = None
    for _ in range(6):
        def chain(z, gg=g):
            z = d.softclip(z * d.dbg(gg), 0.88)
            return d.limiter(z, ceiling, 2.5, 90.0)[0]
        out = _proc(song, pre, chain)
        lv = stem_lufs(out)
        if abs(lv - target) < 0.05:
            break
        g += target - lv
    # diagnostics: how hard are the glue comp and limiter working?
    _, gr = d.compress(d.eq(ref, meq), **glue)
    _, lg = d.limiter(d.softclip(pre * d.dbg(g), 0.88), ceiling, 2.5, 90.0)
    lg = d.todb(lg)
    print(f"    master: glue GR mean {gr.mean():.2f} dB (max {gr.min():.1f}); limiter GR mean {lg.mean():.2f} dB, "
          f"p99 {np.percentile(lg, 1):.2f} dB; makeup {g:+.1f} dB")
    out = out - out.mean(axis=0)
    return out


def dither16(x, seed=0):
    r = np.random.default_rng(seed)
    lsb = 1.0 / 32768
    return x + (r.uniform(-0.5, 0.5, x.shape) + r.uniform(-0.5, 0.5, x.shape)) * lsb
