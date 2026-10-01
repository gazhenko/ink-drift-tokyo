"""Generate all INK DRIFT sound effects from scratch (deterministic, seeded).

usage: python Tools/audio/gen_sfx.py
Writes 44.1 kHz / 16-bit WAVs to Game/Assets/InkDrift/Audio/SFX/ and the copies the runtime
loads from Resources (Audio/tire_squeal_loop, Audio/wind_loop, Audio/impact, Audio/UI/ui_*).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import inkdsp as d  # noqa: E402
from inkdsp import SR, TAU, secs, tvec  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SFX = ROOT / "Game/Assets/InkDrift/Audio/SFX"
RES = ROOT / "Game/Assets/InkDrift/Resources/Audio"


def place(buf, sig, t0):
    i = secs(t0)
    n = min(sig.shape[0], buf.shape[0] - i)
    buf[i: i + n] += sig[:n]
    return buf


def st(x, pan=0.0):
    return d.pan_mono(x, pan) if x.ndim == 1 else x


def finish(x, total_s, fade_s=0.03, fade_in=0.0003):
    n = secs(total_s)
    x = x[:n] if x.shape[0] >= n else np.concatenate([x, np.zeros((n - x.shape[0],) + x.shape[1:])])
    x = d.remove_dc(x)
    return d.fade_edges(x, fade_in, fade_s)


def tail_fade(x, start_s):
    """Smooth multiplicative fade from start_s to the end (cosine)."""
    n = x.shape[0]
    i = secs(start_s)
    w = np.ones(n)
    w[i:] = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n - i))
    return x * (w[:, None] if x.ndim == 2 else w)


# ------------------------------------------------------------------------------- UI sounds
def ui_move():
    rng = np.random.default_rng(101)
    n = secs(0.06)
    t = tvec(n)
    f = 1318.5 * 2 ** ((5 / 12) * np.exp(-t / 0.006))  # E6 with a quick downward chirp
    sq = d.hp(d.lp(d.pulse(f, np.full(n, 0.5)), 6500.0), 300.0)
    body = (0.45 * sq + 0.8 * np.sin(TAU * np.cumsum(f) / SR) + 0.25 * np.sin(TAU * 2 * np.cumsum(f) / SR))
    body *= d.perc(n, 0.0008, 0.016)
    tick = d.hp(d.noise(n, rng), 5000.0) * np.exp(-t / 0.0018) * 0.6
    x = np.stack([body + tick, body + np.roll(tick, 12)], axis=-1)
    return finish(x, 0.06, 0.008)


def chime(f, n, dec=0.08, bright=1.0):
    t = tvec(n)
    m = np.sin(TAU * f * 2.0 * t) * 1.6 * bright * np.exp(-t / 0.03)
    c = np.sin(TAU * f * t + m)
    c += 0.25 * np.sin(TAU * f * 3.01 * t) * np.exp(-t / 0.02)
    return c * d.perc(n, 0.001, dec)


def ui_confirm():
    rng = np.random.default_rng(102)
    total = 0.25
    n = secs(total + 0.3)
    x = np.zeros((n, 2))
    place(x, st(chime(1318.5, secs(0.16), 0.045), -0.15), 0.0)  # E6
    place(x, st(chime(1975.5, secs(0.3), 0.085), 0.15), 0.07)   # B6 (a fifth up)
    place(x, st(0.25 * chime(2637.0, secs(0.25), 0.06, 0.6), 0.3), 0.075)  # E7 sparkle
    # slight whoosh: upward band-pass sweep, decorrelated L/R
    m = secs(0.22)
    u = np.linspace(0, 1, m)
    fc = 1200 * (9000 / 1200) ** u
    env = np.sin(np.pi * u) ** 1.5
    wl = d.svf(d.noise(m, rng), fc, np.full(m, 1.4), 1) * env
    wr = d.svf(d.noise(m, rng), fc * 1.05, np.full(m, 1.4), 1) * env
    place(x, 0.16 * np.stack([wl, wr], -1), 0.0)
    wet = d.reverb(np.concatenate([x, np.zeros((secs(0.3), 2))]), rt60=0.45, size=0.5, damp=0.2, predelay=0.005)
    x = x + 0.22 * wet[: n]
    x = tail_fade(x[: secs(total)], 0.17)
    return finish(x, total, 0.01)


def ui_start():
    rng = np.random.default_rng(103)
    total = 1.2
    t0 = 0.30  # impact time
    n = secs(total + 1.0)
    x = np.zeros((n, 2))
    # whoosh in: rising band-pass noise + reverse swell, auto-panned L->R
    m = secs(t0)
    u = np.linspace(0, 1, m)
    fc = 350 * (7000 / 350) ** (u ** 1.4)
    wz = d.svf(d.noise(m, rng), fc, np.full(m, 1.8), 1) * u ** 2.2
    pan = -0.6 + 1.2 * u
    th = (pan + 1) * np.pi / 4
    x[:m, 0] += 0.55 * wz * np.cos(th) * 1.41
    x[:m, 1] += 0.55 * wz * np.sin(th) * 1.41
    rs = d.reverse_swell(rng, t0, bright=7000.0)
    place(x, st(0.35 * rs), 0.0)
    # impact
    k = d.kick(rng, 0.6, f0=210, f1=44, ptau=0.04, adec=0.2, click=0.8, drive=3.0)
    place(x, st(0.95 * k), t0)
    place(x, st(0.42 * d.sub_drop(rng, 0.55, 90, 45, 0.12)), t0)
    crk = d.hp(d.noise(secs(0.12), rng), 1400) * np.exp(-tvec(secs(0.12)) / 0.03)
    place(x, np.stack([crk, np.roll(crk, 30)], -1) * 0.45, t0)
    sn = d.snare(rng, 0.5, tone=170, gated=0.8)
    place(x, st(0.5 * sn), t0)
    # supersaw stab: D minor (D3 A3 D4 F4 A4 D5)
    ns = secs(0.75)
    tt = tvec(ns)
    stab = np.zeros((ns, 2))
    for mnote in (50, 57, 62, 65, 69, 74):
        stab += d.supersaw(np.full(ns, d.mtof(mnote)), rng, cents=25, mix=0.8)
    fenv = 900 + 9000 * np.exp(-tt / 0.09)
    stab = d.lp24(stab, fenv, 0.25) * d.perc(ns, 0.002, 0.25)[:, None] * 0.3
    place(x, stab, t0)
    # shimmer: fast rising FM bell arpeggio + glitter pings
    for i, mnote in enumerate((86, 89, 93, 98, 101, 105)):
        b = d.fm_bell(d.mtof(mnote), secs(0.7), ratio=3.5, index=1.6, idx_decay=0.08, amp_decay=0.28)
        place(x, st(0.22 * b, (-0.5 + 0.2 * i)), t0 + 0.03 + 0.045 * i)
    for _ in range(28):
        tp = t0 + 0.05 + rng.uniform(0, 0.6) ** 1.5
        fp = rng.uniform(4500, 11000)
        nn = secs(0.05)
        ping = np.sin(TAU * fp * tvec(nn)) * d.perc(nn, 0.0005, 0.012)
        place(x, st(0.08 * ping, rng.uniform(-0.9, 0.9)), tp)
    sh = d.hp(d.noise(secs(0.8), rng), 6000) * d.perc(secs(0.8), 0.02, 0.18)
    place(x, np.stack([sh, d.hp(d.noise(secs(0.8), rng), 6000) * d.perc(secs(0.8), 0.02, 0.18)], -1) * 0.08, t0)
    wet = d.reverb(x, rt60=1.5, size=1.1, damp=0.3, predelay=0.012)
    x = x + 0.28 * wet
    x, _ = d.compress(x, thr_db=-14, ratio=3, att=0.003, rel=0.12, rms_ms=2)
    x = tail_fade(x[: secs(total)], 0.75)
    return finish(x, total, 0.02)


# --------------------------------------------------------------------------- comic callouts
def pop_core(rng, f_lo=330, f_hi=1450, sweep=0.035, dec=0.05, thump_f=(190, 85)):
    n = secs(0.25)
    t = tvec(n)
    f = f_lo * (f_hi / f_lo) ** np.clip(t / sweep, 0, 1) ** 0.6
    ph = TAU * np.cumsum(f) / SR
    body = (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)) * d.perc(n, 0.0006, dec)
    tf = thump_f[1] + (thump_f[0] - thump_f[1]) * np.exp(-t / 0.015)
    thump = np.sin(TAU * np.cumsum(tf) / SR) * d.perc(n, 0.0008, 0.035)
    click = d.hp(d.noise(n, rng), 1200) * np.exp(-t / 0.0015)
    return np.tanh(1.3 * (0.95 * body + 0.5 * thump + 0.55 * click))


def spray(rng, dur, flutter=32.0):
    n = secs(dur)
    t = tvec(n)
    u = t / dur
    nz = d.noise(n, rng)
    h = d.bp(d.hp(nz, 3500), 7500, 0.7) + 0.4 * d.hp(nz, 9000)
    env = np.clip(u / 0.06, 0, 1) * (1 - u) ** 1.3
    am = 1 + 0.25 * np.sin(TAU * flutter * t) * u
    return h * env * am


def callout_pop():
    rng = np.random.default_rng(201)
    total = 0.35
    x = np.zeros((secs(total + 0.3), 2))
    place(x, st(pop_core(rng)), 0.0)
    s1 = spray(rng, 0.27)
    s2 = spray(rng, 0.27)
    place(x, 0.4 * np.stack([s1, s2], -1), 0.04)
    wet = d.reverb(x, rt60=0.35, size=0.45, damp=0.25, predelay=0.004)
    x = x + 0.15 * wet
    x = tail_fade(x[: secs(total)], 0.26)
    return finish(x, total, 0.01)


def callout_bigpop():
    rng = np.random.default_rng(202)
    total = 0.9
    x = np.zeros((secs(total + 1.0), 2))
    place(x, st(1.0 * pop_core(rng, 220, 1000, 0.045, 0.07, (150, 60))), 0.0)
    place(x, st(0.5 * d.sub_drop(rng, 0.6, 140, 40, 0.1)), 0.0)
    cr = d.crash(rng, 0.9, dec=0.32, bright=8000)
    cr2 = d.crash(rng, 0.9, dec=0.32, bright=8500)
    place(x, 0.42 * np.stack([cr, cr2], -1), 0.004)
    # rising sparkle: A-major pentatonic bells going up, alternating sides
    notes = (81, 85, 88, 93, 97, 100, 105, 109)
    for i, mnote in enumerate(notes):
        b = d.fm_bell(d.mtof(mnote), secs(0.45), ratio=3.5, index=1.4, idx_decay=0.05, amp_decay=0.16)
        place(x, st((0.2 + 0.02 * i) * b, 0.55 if i % 2 else -0.55), 0.09 + 0.075 * i)
    m = secs(0.75)
    u = np.linspace(0, 1, m)
    fc = 2500 * (14000 / 2500) ** u
    sw = np.stack([d.svf(d.noise(m, rng), fc, np.full(m, 2.0), 1), d.svf(d.noise(m, rng), fc, np.full(m, 2.0), 1)], -1)
    place(x, sw * (np.sin(np.pi * u) ** 1.2 * 0.3)[:, None], 0.1)
    for _ in range(40):
        tp = 0.1 + rng.uniform(0, 0.7)
        fp = 3500 + 9000 * ((tp - 0.1) / 0.7) + rng.uniform(-800, 800)
        nn = secs(0.04)
        ping = np.sin(TAU * fp * tvec(nn)) * d.perc(nn, 0.0005, 0.01)
        place(x, st(0.08 * ping, rng.uniform(-1, 1)), tp)
    wet = d.reverb(x, rt60=0.9, size=0.8, damp=0.3, predelay=0.01)
    x = x + 0.22 * wet
    x, _ = d.compress(x, thr_db=-12, ratio=3, att=0.002, rel=0.1, rms_ms=2)
    x = tail_fade(x[: secs(total)], 0.62)
    return finish(x, total, 0.02)


def callout_fail():
    rng = np.random.default_rng(203)
    total = 0.7
    n = secs(total + 0.4)
    x = np.zeros((n, 2))
    # crunch: distorted, sample-held noise burst + crumple clicks + thud
    m = secs(0.16)
    t = tvec(m)
    cz = d.lp(d.noise(m, rng), 3800) * 4.0
    cz = np.clip(cz, -0.6, 0.6)
    cz = np.repeat(cz[::5], 5)[:m]  # crude sample-rate reduction -> crunchy
    cz = np.round(cz * 12) / 12     # bit crush
    cz *= d.perc(m, 0.0005, 0.04)
    thud = d.kick(rng, 0.25, f0=150, f1=55, ptau=0.02, adec=0.06, click=0.3, drive=2.5)
    place(x, st(0.65 * cz), 0.0)
    place(x, st(0.4 * thud), 0.0)
    for _ in range(9):
        cl = d.bp(d.noise(secs(0.006), rng), rng.uniform(1500, 5000), 3) * d.perc(secs(0.006), 0.0002, 0.0015)
        place(x, st(0.5 * cl, rng.uniform(-0.6, 0.6)), rng.uniform(0.0, 0.11))
    # wah-wah: muted-trombone-ish saw through a moving formant
    def wah(t_on, dur, f_start, f_end, vib_depth, wahs):
        k = secs(dur)
        tt = tvec(k)
        u = tt / dur
        bend = f_start * (f_end / f_start) ** np.clip((u - 0.25) / 0.75, 0, 1) ** 1.2
        vib = 1 + vib_depth * np.sin(TAU * 6.0 * tt) * np.clip((u - 0.3) / 0.3, 0, 1)
        f = bend * vib
        src = d.saw(f, 0.0) + 0.7 * d.saw(f * 1.004, 0.3) + 0.3 * d.pulse(f * 0.5, np.full(k, 0.3))
        # wah = cutoff "opening" per syllable
        ph = np.clip(tt * wahs / dur, 0, wahs)
        syl = np.sin(np.pi * np.mod(ph, 1.0)) ** 0.7
        fc = 380 + 1500 * syl * (1 - 0.35 * u)
        y = d.svf(src, fc, np.full(k, 3.2), 0) * 0.6 + 0.25 * d.svf(src, fc * 2.2, np.full(k, 4.0), 1)
        env = d.adsr(k - secs(0.06), 0.02, 0.1, 0.85, 0.06, n_total=k)
        return y * env
    w1 = wah(0.07, 0.24, d.mtof(55), d.mtof(55), 0.0, 1)       # G3
    w2 = wah(0.31, 0.39, d.mtof(54), d.mtof(51.5), 0.022, 3)    # F#3 sagging down, wobbling
    place(x, st(0.6 * w1, -0.1), 0.07)
    place(x, st(0.6 * w2, 0.1), 0.30)
    wet = d.reverb(x, rt60=0.5, size=0.6, damp=0.35, predelay=0.006)
    x = x + 0.14 * wet
    x = tail_fade(x[: secs(total)], 0.6)
    return finish(x, total, 0.01)


# ----------------------------------------------------------------------------------- impact
def impact():
    rng = np.random.default_rng(301)
    total = 0.6
    n = secs(total + 0.3)
    y = np.zeros(n)
    t = tvec(n)
    # low thump
    tf = 42 + 50 * np.exp(-t / 0.02)
    th = np.sin(TAU * np.cumsum(tf) / SR) * d.perc(n, 0.001, 0.055)
    y += 0.6 * np.tanh(2.0 * th)
    # metal: modal resonator bank excited by a few noise bursts (crunch)
    modes = np.exp(rng.uniform(np.log(350), np.log(5500), 26))
    decs = rng.uniform(0.02, 0.16, 26)
    amps = rng.uniform(0.3, 1.0, 26) / np.sqrt(modes / 350)
    mi = secs(0.5)
    ti = tvec(mi)
    ir = np.zeros(mi)
    for f, dc, a in zip(modes, decs, amps):
        ir += a * np.sin(TAU * f * ti + rng.uniform(0, TAU)) * np.exp(-ti / dc)
    exc = np.zeros(n)
    for t0, a in ((0.0, 1.0), (0.017, 0.7), (0.041, 0.55), (0.075, 0.35)):
        k = secs(0.012)
        place(exc, d.noise(k, rng) * d.perc(k, 0.0003, 0.003) * a, t0)
    metal = np.convolve(exc, ir)[:n]
    metal /= np.abs(metal).max() + 1e-9
    y += 0.85 * np.tanh(1.8 * metal)
    # plastic cracks: short bright noise ticks clustered early
    for _ in range(14):
        k = secs(rng.uniform(0.0008, 0.003))
        ck = d.bp(d.noise(k, rng), rng.uniform(2200, 7000), 1.5) * d.perc(k, 0.0001, 0.0008)
        place(y, 0.6 * ck, rng.uniform(0, 0.12) ** 1.3)
    # broadband crunch burst
    m = secs(0.14)
    cb = d.bp(d.noise(m, rng), 1800, 0.5) * d.perc(m, 0.0005, 0.03)
    place(y, 0.45 * cb, 0.0)
    # debris rattle tail
    for _ in range(26):
        tp = 0.06 + rng.uniform(0, 1) ** 1.8 * 0.48
        k = secs(0.02)
        f = rng.uniform(1800, 6500)
        rt = np.sin(TAU * f * tvec(k)) * d.perc(k, 0.0002, rng.uniform(0.002, 0.006))
        place(y, 0.18 * (1 - (tp - 0.06) / 0.5) * rt, tp)
    y = d.eq(y, [("hp", 35, 0, 0.7), ("peak", 2800, 2.5, 1.0)])
    y = d.softclip(y / (np.abs(y).max() + 1e-9) * 1.3, 0.6)
    y = tail_fade(y[: secs(total)], 0.35)
    return finish(y, total, 0.02)


# ------------------------------------------------------------------------------------ loops
def make_periodic_freq(f, n):
    """Scale an instantaneous-frequency curve so it completes an integer number of cycles."""
    cyc = f.sum() / SR
    return f * (np.round(cyc) / cyc)


def periodic_phase(f):
    return TAU * (np.cumsum(f) / SR - f[0] / SR)


def tire_squeal_loop():
    rng = np.random.default_rng(401)
    dur = 4.0
    n = secs(dur)
    out = np.zeros(n)
    bases = (880.0, 1140.0, 1510.0)
    levels = (1.0, 0.75, 0.45)
    xf = [d.periodic_lfnoise(n, rng, 0.35) for _ in bases]  # slow cross-fade between squealers
    for k, (b, lvl) in enumerate(zip(bases, levels)):
        wander = d.periodic_lfnoise(n, rng, 0.9)
        jitter = d.periodic_lfnoise(n, rng, 28.0)
        f = b * (1 + 0.032 * wander + 0.011 * jitter)
        f = make_periodic_freq(f, n)
        ph = periodic_phase(f)
        # phase noise (narrow-band spread around each partial) -> "noisy" tone, not a sine
        pn = 0.45 * d.periodic_lfnoise(n, rng, 160.0)
        p = ph + pn
        tone = np.sin(p) + 0.42 * np.sin(2 * p + 0.7) + 0.2 * np.sin(3 * p + 1.9) + 0.08 * np.sin(4 * p + 0.4)
        tone = np.tanh(1.4 * tone)  # rubbery, slightly squared-off
        # stick-slip chatter: pulse-train AM at ~38-55 Hz (integer cycles per loop)
        cr = make_periodic_freq(46 * (1 + 0.15 * d.periodic_lfnoise(n, rng, 2.0)), n)
        chat = 0.72 + 0.28 * np.abs(np.sin(0.5 * periodic_phase(cr))) ** 0.5
        am = np.clip(0.62 + 0.38 * d.periodic_lfnoise(n, rng, 7.0), 0.05, None) * chat
        presence = np.clip(0.55 + 0.45 * xf[k], 0.0, None) ** 1.3
        out += lvl * tone * am * presence
    # noisy sidebands/hiss around the squeal band and asphalt scrub underneath
    hiss = d.bandnoise_fft(n, rng, 700, 4200)
    hiss_am = np.clip(0.6 + 0.4 * d.periodic_lfnoise(n, rng, 12.0), 0, None)
    scrub = d.bandnoise_fft(n, rng, 180, 650)
    out = out / np.std(out)
    out += 0.22 * hiss * hiss_am + 0.10 * scrub * hiss_am
    # band shaping (IIR) in steady state around the loop
    out = d.circ(lambda z: d.eq(z, [("hp", 420, 0, 0.7), ("peak", 1150, 3.0, 0.8), ("lp", 6500, 0, 0.7),
                                    ("highshelf", 3500, -4.0, 0.7)]), out, pre=n, post=0)
    out = d.circ(lambda z: d.compress(z, thr_db=-10, ratio=2.5, att=0.005, rel=0.08)[0], out / np.abs(out).max(),
                 pre=n, post=secs(0.01))
    return out - out.mean()


def wind_loop():
    rng = np.random.default_rng(402)
    dur = 6.0
    n = secs(dur)
    gust = d.periodic_lfnoise(n, rng, 0.28)
    gust = gust / np.abs(gust).max()
    flutter = d.periodic_lfnoise(n, rng, 3.0)
    pink = d.colored_noise(n, rng, -3.0)
    brown = d.colored_noise(n, rng, -6.0)
    white = d.colored_noise(n, rng, 0.0)
    fc = 520 * 2 ** (1.1 * gust + 0.12 * flutter)
    fcw = 760 * 2 ** (0.35 * gust)

    def proc(z):
        L = z.shape[0] // 2
        def ext(a):
            return np.concatenate([a, a])
        body = d.svf(ext(pink), ext(fc), np.full(2 * L, 0.8), 4)
        rumble = d.svf(ext(brown), np.full(2 * L, 140.0), np.full(2 * L, 0.7), 0)
        hiss = d.svf(ext(white), np.full(2 * L, 3200.0), np.full(2 * L, 0.7), 2)
        whistle = d.svf(ext(pink), ext(fcw), np.full(2 * L, 22.0), 1)
        g = ext(gust)
        lvl = 0.55 + 0.45 * g
        y = (body * lvl * 0.9 + rumble * (0.7 + 0.3 * g) * 0.9 + hiss * np.clip(0.3 + 0.7 * g, 0, None) ** 2 * 0.09
             + whistle * np.clip(g, 0, None) ** 1.5 * 0.5)
        return y[L:]

    y = proc(np.zeros(2 * n))
    y = d.circ(lambda z: d.eq(z, [("hp", 40, 0, 0.7), ("lp", 9000, 0, 0.7)]), y, pre=n, post=0)
    return y - y.mean()


# -------------------------------------------------------------------------------- countdown
def beep_tone(f, gate, rel, bright=0.45):
    n = gate + secs(rel)
    t = tvec(n)
    ff = f * 2 ** ((25 / 1200) * np.exp(-t / 0.008))
    sq = d.lp(d.pulse(ff, np.full(n, 0.5)), 5200.0)
    s = np.sin(TAU * np.cumsum(ff) / SR)
    s2 = np.sin(TAU * 2 * np.cumsum(ff) / SR)
    y = bright * sq + 0.8 * s + 0.15 * s2
    return y * d.adsr(gate, 0.002, 0.15, 0.82, rel, n_total=n)


def countdown_beep():
    rng = np.random.default_rng(501)
    total = 0.36
    x = np.zeros((secs(total + 0.4), 2))
    place(x, st(0.6 * beep_tone(880.0, secs(0.19), 0.07)), 0.0)
    wet = d.reverb(x, rt60=0.35, size=0.5, damp=0.3, predelay=0.006)
    x = x + 0.12 * wet
    x = tail_fade(x[: secs(total)], 0.28)
    return finish(x, total, 0.01)


def countdown_go():
    rng = np.random.default_rng(502)
    total = 1.0
    x = np.zeros((secs(total + 0.6), 2))
    g = secs(0.55)
    tone = beep_tone(1760.0, g, 0.32, 0.55) + 0.35 * beep_tone(2637.0, g, 0.32, 0.3) + 0.45 * beep_tone(880.0, g, 0.32, 0.25)
    place(x, st(0.42 * tone), 0.0)
    place(x, st(0.55 * d.kick(rng, 0.35, f0=240, f1=60, ptau=0.02, adec=0.08, click=0.6)), 0.0)
    ch = d.hp(d.noise(secs(0.25), rng), 4500) * d.perc(secs(0.25), 0.001, 0.06)
    place(x, np.stack([ch, d.hp(d.noise(secs(0.25), rng), 4500) * d.perc(secs(0.25), 0.001, 0.06)], -1) * 0.16, 0.0)
    wet = d.reverb(x, rt60=0.8, size=0.8, damp=0.3, predelay=0.01)
    x = x + 0.16 * wet
    x = tail_fade(x[: secs(total)], 0.62)
    return finish(x, total, 0.02)


# ------------------------------------------------------------------------------------- main
# name -> (fn, target sample peak dBFS, is_loop)
SOUNDS = {
    "ui_move": (ui_move, -3.0, False),
    "ui_confirm": (ui_confirm, -2.0, False),
    "ui_start": (ui_start, -1.2, False),
    "callout_pop": (callout_pop, -1.5, False),
    "callout_bigpop": (callout_bigpop, -1.2, False),
    "callout_fail": (callout_fail, -1.5, False),
    "impact": (impact, -1.2, False),
    "tire_squeal_loop": (tire_squeal_loop, -1.5, True),
    "wind_loop": (wind_loop, -1.5, True),
    "countdown_beep": (countdown_beep, -2.0, False),
    "countdown_go": (countdown_go, -1.5, False),
}

RES_COPIES = {
    "tire_squeal_loop": RES / "tire_squeal_loop.wav",
    "wind_loop": RES / "wind_loop.wav",
    "impact": RES / "impact.wav",
    "ui_move": RES / "UI/ui_move.wav",
    "ui_confirm": RES / "UI/ui_confirm.wav",
    "ui_start": RES / "UI/ui_start.wav",
}


def main(only=None):
    SFX.mkdir(parents=True, exist_ok=True)
    (RES / "UI").mkdir(parents=True, exist_ok=True)
    for name, (fn, pk, loop) in SOUNDS.items():
        if only and name not in only:
            continue
        x = fn()
        x = x * d.dbg(pk) / d.dbg(d.true_peak_db(x))
        x = d.write_wav(SFX / f"{name}.wav", x)
        print(f"{name:18s} {x.shape[0] / SR:6.3f}s  ch={1 if x.ndim == 1 else x.shape[1]}  peak={d.peak_db(x):6.2f} dBFS")
        if name in RES_COPIES:
            shutil.copyfile(SFX / f"{name}.wav", RES_COPIES[name])


if __name__ == "__main__":
    main(sys.argv[1:] or None)
