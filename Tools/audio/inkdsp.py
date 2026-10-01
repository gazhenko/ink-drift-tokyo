"""INK DRIFT: TOKYO — procedural audio DSP core.

Everything here is synthesized from scratch (no samples). Deterministic: all randomness comes
from explicit numpy Generators seeded by the callers.

Contents
  oscillators   PolyBLEP saw / pulse, sine, supersaw (7 detuned voices, stereo spread)
  filters       TPT state-variable filter (time-varying cutoff/Q), RBJ biquads, one-poles
  envelopes     vectorized ADSR, per-sample gate-driven ADSR state machine
  FM            2/3-operator FM bell and DX-style electric piano
  drums         kick, snare (gated), clap, closed/open hats, crash, tom, impacts, risers
  effects       FDN reverb (Schroeder allpass diffusers + 8-line Householder FDN),
                ping-pong stereo delay, compressor, soft clipper, true-peak lookahead limiter
  utilities     circular (loop-safe) processing, loudness, I/O
"""
from __future__ import annotations

import numpy as np
import numba as nb
from scipy import signal as sps
from scipy.ndimage import minimum_filter1d

SR = 44100
TAU = 2.0 * np.pi


# ----------------------------------------------------------------------------------- basics
def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def dbg(db):
    return 10.0 ** (np.asarray(db, dtype=float) / 20.0)


def todb(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def secs(n):
    return int(round(n * SR))


def tvec(n):
    return np.arange(n) / SR


def fade_edges(x, fin=0.0005, fout=0.003):
    """Short raised-cosine fades so a one-shot starts/ends exactly at zero."""
    x = np.array(x, dtype=float, copy=True)
    n = x.shape[0]
    a, b = max(1, secs(fin)), max(1, secs(fout))
    a, b = min(a, n // 2), min(b, n // 2)
    wa = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    wb = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, b))
    if x.ndim == 1:
        x[:a] *= wa
        x[-b:] *= wb
    else:
        x[:a] *= wa[:, None]
        x[-b:] *= wb[:, None]
    return x


def pan_mono(x, pan=0.0):
    """Equal-power pan, pan in [-1, 1] -> (n, 2)."""
    th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=-1) * np.sqrt(2)


def width(st, w):
    m = 0.5 * (st[:, 0] + st[:, 1])
    s = 0.5 * (st[:, 0] - st[:, 1]) * w
    return np.stack([m + s, m - s], axis=-1)


def noise(n, rng):
    return rng.uniform(-1.0, 1.0, n)


def colored_noise(n, rng, slope_db_oct=-3.0, circular=True):
    """Noise with a spectral tilt, made in the frequency domain (periodic over n)."""
    w = rng.standard_normal(n)
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    W *= (f / 1000.0) ** (slope_db_oct / 6.0206)
    y = np.fft.irfft(W, n)
    return y / (np.std(y) + 1e-12)


def periodic_lfnoise(n, rng, cutoff_hz, order=4):
    """Smooth random modulation signal (zero mean, unit std) that is exactly periodic over n."""
    w = rng.standard_normal(n)
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = 1.0 / np.sqrt(1.0 + (f / cutoff_hz) ** (2 * order))
    H[0] = 0.0
    y = np.fft.irfft(W * H, n)
    return y / (np.std(y) + 1e-12)


def bandnoise_fft(n, rng, lo, hi, circular=True):
    w = rng.standard_normal(n)
    W = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = ((f >= lo) & (f <= hi)).astype(float)
    # soften edges a little
    H = np.convolve(H, np.hanning(9) / np.hanning(9).sum(), mode="same")
    y = np.fft.irfft(W * H, n)
    return y / (np.std(y) + 1e-12)


# ------------------------------------------------------------------------------ oscillators
@nb.njit(cache=True, fastmath=True)
def _blep(t, dt):
    if t < dt:
        t = t / dt
        return t + t - t * t - 1.0
    elif t > 1.0 - dt:
        t = (t - 1.0) / dt
        return t * t + t + t + 1.0
    return 0.0


@nb.njit(cache=True, fastmath=True)
def saw(freq, phase0=0.0):
    n = freq.shape[0]
    out = np.empty(n)
    ph = phase0
    for i in range(n):
        dt = freq[i] / 44100.0
        if dt > 0.45:
            dt = 0.45
        out[i] = 2.0 * ph - 1.0 - _blep(ph, dt)
        ph += dt
        if ph >= 1.0:
            ph -= 1.0
    return out


@nb.njit(cache=True, fastmath=True)
def pulse(freq, pw, phase0=0.0):
    n = freq.shape[0]
    out = np.empty(n)
    ph = phase0
    for i in range(n):
        dt = freq[i] / 44100.0
        if dt > 0.45:
            dt = 0.45
        w = pw[i]
        v = 1.0 if ph < w else -1.0
        v += _blep(ph, dt)
        t2 = ph - w
        if t2 < 0.0:
            t2 += 1.0
        v -= _blep(t2, dt)
        out[i] = v
        ph += dt
        if ph >= 1.0:
            ph -= 1.0
    return out


def sine(freq, phase0=0.0):
    freq = np.broadcast_to(np.asarray(freq, float), np.shape(freq))
    ph = np.cumsum(freq) / SR + phase0
    return np.sin(TAU * (ph - freq / SR))


def phase_of(freq, phase0=0.0):
    return np.cumsum(freq) / SR + phase0 - np.asarray(freq) / SR


def tri(freq, phase0=0.0):
    ph = np.mod(phase_of(freq, phase0), 1.0)
    return 4.0 * np.abs(ph - 0.5) - 1.0


SUPERSAW_OFFS = np.array([-0.11002313, -0.06288439, -0.01952356, 0.0, 0.01991221, 0.06216538, 0.10745242])
SUPERSAW_PANS = np.array([-0.9, 0.62, -0.32, 0.0, 0.34, -0.6, 0.92])


def supersaw(freq, rng, cents=22.0, mix=0.75, spread=1.0, voices=7):
    """JP-8000 style supersaw. freq: per-sample array. Returns (n, 2)."""
    offs = SUPERSAW_OFFS / 0.11 * (cents / 1200.0)
    n = freq.shape[0]
    L = np.zeros(n)
    R = np.zeros(n)
    idx = range(7) if voices == 7 else [3, 1, 5][:voices]
    for k in idx:
        f = freq * (2.0 ** offs[k])
        v = saw(f, rng.uniform(0, 1))
        g = (1.0 - 0.55 * mix) if k == 3 else mix * 0.42
        th = (SUPERSAW_PANS[k] * spread + 1) * np.pi / 4
        L += v * g * np.cos(th) * 1.4142
        R += v * g * np.sin(th) * 1.4142
    return np.stack([L, R], axis=-1)


# ---------------------------------------------------------------------------------- filters
@nb.njit(cache=True, fastmath=True)
def svf(x, fc, q, mode):
    """Zavalishin/Cytomic TPT SVF with per-sample cutoff & Q.
    mode 0=LP 1=BP(unity peak) 2=HP 3=notch 4=BP(skirt, gain Q) 5=peak/bell-ish"""
    n = x.shape[0]
    y = np.empty(n)
    ic1 = 0.0
    ic2 = 0.0
    for i in range(n):
        f = fc[i]
        if f > 20000.0:
            f = 20000.0
        if f < 10.0:
            f = 10.0
        g = np.tan(np.pi * f / 44100.0)
        k = 1.0 / q[i]
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if mode == 0:
            y[i] = v2
        elif mode == 1:
            y[i] = k * v1
        elif mode == 2:
            y[i] = x[i] - k * v1 - v2
        elif mode == 3:
            y[i] = x[i] - k * v1
        elif mode == 4:
            y[i] = v1
        else:
            y[i] = x[i] - k * v1 - 2.0 * v2
    return y


def _arr(v, n):
    a = np.asarray(v, dtype=float)
    return np.full(n, float(a)) if a.ndim == 0 else a


def lp(x, fc, q=0.707):
    return _apply_mono(lambda c: svf(c, _arr(fc, c.shape[0]), _arr(q, c.shape[0]), 0), x)


def bp(x, fc, q=1.0):
    return _apply_mono(lambda c: svf(c, _arr(fc, c.shape[0]), _arr(q, c.shape[0]), 1), x)


def hp(x, fc, q=0.707):
    return _apply_mono(lambda c: svf(c, _arr(fc, c.shape[0]), _arr(q, c.shape[0]), 2), x)


def lp24(x, fc, res=0.0, drive=1.0):
    """Two cascaded SVF lowpasses (24 dB/oct). res 0..1 -> resonance on the 2nd stage."""
    def f(c):
        n = c.shape[0]
        fca = _arr(fc, n)
        if drive != 1.0:
            c = np.tanh(c * drive) / np.tanh(drive)
        y = svf(c, fca, np.full(n, 0.54), 0)
        return svf(y, fca, np.full(n, 0.6 + 9.0 * res ** 2), 0)
    return _apply_mono(f, x)


def _apply_mono(f, x):
    if x.ndim == 1:
        return f(np.ascontiguousarray(x))
    return np.stack([f(np.ascontiguousarray(x[:, c])) for c in range(x.shape[1])], axis=-1)


def sos_filter(x, sos, axis=0):
    return sps.sosfilt(sos, x, axis=axis)


def butter(x, kind, fc, order=2):
    sos = sps.butter(order, fc, btype=kind, fs=SR, output="sos")
    return sps.sosfilt(sos, x, axis=0)


def rbj(kind, f0, gain_db=0.0, q=0.707):
    A = 10 ** (gain_db / 40)
    w0 = TAU * f0 / SR
    al = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    if kind == "peak":
        b = [1 + al * A, -2 * c, 1 - al * A]
        a = [1 + al / A, -2 * c, 1 - al / A]
    elif kind == "lowshelf":
        sA = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * c + sA), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sA)]
        a = [(A + 1) + (A - 1) * c + sA, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sA]
    elif kind == "highshelf":
        sA = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * c + sA), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sA)]
        a = [(A + 1) - (A - 1) * c + sA, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sA]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return np.concatenate([b, a])[None, :]


def eq(x, bands):
    """bands: list of (kind, f0, gain_db, q). kind in peak/lowshelf/highshelf/hp/lp."""
    y = x
    for kind, f0, g, q in bands:
        if kind in ("hp", "lp"):
            sos = sps.butter(2, f0, btype="high" if kind == "hp" else "low", fs=SR, output="sos")
        else:
            sos = rbj(kind, f0, g, q)
        y = sps.sosfilt(sos, y, axis=0)
    return y


@nb.njit(cache=True, fastmath=True)
def onepole_var(x, coef):
    """y += (x - y) * coef[i]  (per-sample smoothing coefficient)."""
    n = x.shape[0]
    y = np.empty(n)
    s = 0.0
    for i in range(n):
        s += (x[i] - s) * coef[i]
        y[i] = s
    return y


def smooth(x, ms):
    a = 1.0 - np.exp(-1.0 / (ms * 0.001 * SR))
    return sps.lfilter([a], [1, -(1 - a)], x, axis=0)


# -------------------------------------------------------------------------------- envelopes
def adsr(n_gate, a=0.005, d=0.2, s=0.7, r=0.15, curve=1.0, n_total=None):
    """Vectorized ADSR. Gate length n_gate samples; returns array of n_gate + release samples.
    Attack linear(ish), decay/release exponential, and the final sample reaches exactly 0."""
    nr = max(8, secs(r))
    n = n_total if n_total is not None else n_gate + nr
    t = np.arange(n) / SR
    a = max(a, 1.0 / SR)
    att = np.clip(t / a, 0.0, 1.0) ** curve
    dec = s + (1 - s) * np.exp(-np.maximum(t - a, 0.0) / max(d / 4.0, 1e-4))
    env = np.where(t < a, att, dec)
    tg = n_gate / SR
    if n_gate < n:
        vg = env[min(n_gate, n - 1)]
        rel = vg * np.exp(-np.maximum(t - tg, 0.0) / max(r / 5.0, 1e-4))
        env = np.where(t >= tg, rel, env)
    # guarantee a clean ending
    k = min(n // 2, max(4, secs(0.004)))
    env[-k:] *= np.linspace(1, 0, k)
    return env


def perc(n, a=0.001, decay=0.2, curve_exp=1.0):
    """Percussive env: attack then exponential decay with time-constant `decay` (seconds)."""
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1 / SR), 0, 1)
    env = att * np.exp(-np.maximum(t - a, 0) / decay) ** curve_exp
    k = min(n // 2, max(4, secs(0.003)))
    env[-k:] *= np.linspace(1, 0, k)
    return env


@nb.njit(cache=True, fastmath=True)
def adsr_sm(gate, trig, a, d, s, r, retrig_from_zero):
    """Gate-driven ADSR state machine (for mono/legato lines). trig[i]=1 restarts attack."""
    n = gate.shape[0]
    out = np.empty(n)
    v = 0.0
    stage = 0  # 0 idle,1 att,2 dec/sus,3 rel
    ainc = 1.0 / max(a * 44100.0, 1.0)
    dc = 1.0 - np.exp(-1.0 / max(d * 44100.0 / 4.0, 1.0))
    rc = 1.0 - np.exp(-1.0 / max(r * 44100.0 / 5.0, 1.0))
    for i in range(n):
        if trig[i] > 0.5:
            stage = 1
            if retrig_from_zero:
                v = 0.0
        if gate[i] < 0.5 and stage != 0:
            stage = 3
        if stage == 1:
            v += ainc
            if v >= 1.0:
                v = 1.0
                stage = 2
        elif stage == 2:
            v += (s - v) * dc
        elif stage == 3:
            v += (0.0 - v) * rc
            if v < 1e-6:
                v = 0.0
                stage = 0
        out[i] = v
    return out


# ------------------------------------------------------------------------------------- FM
def fm_bell(f, n, rng=None, ratio=3.5, index=3.0, idx_decay=0.35, amp_decay=1.2, a=0.002,
            ratio2=1.0, index2=0.6, detune=0.0):
    t = np.arange(n) / SR
    ienv = np.exp(-t / idx_decay)
    m = np.sin(TAU * f * ratio * t) * index * ienv
    c1 = np.sin(TAU * f * t + m)
    m2 = np.sin(TAU * f * ratio2 * t * (1 + detune)) * index2 * ienv
    c2 = np.sin(TAU * f * (1 + detune) * t + m2)
    env = perc(n, a, amp_decay)
    return (0.7 * c1 + 0.4 * c2) * env


def fm_epiano(f, n_gate, vel=0.8, r=0.35, rng=None):
    """DX7 E.Piano-ish: 1:1 body pair + 14:1 tine pair."""
    nr = secs(r)
    n = n_gate + nr
    t = np.arange(n) / SR
    det = 0.6  # Hz
    i_body = (0.4 + 1.5 * vel) * np.exp(-t / 0.9)
    body = np.sin(TAU * f * t + i_body * np.sin(TAU * f * t))
    body2 = np.sin(TAU * (f + det) * t + i_body * 0.8 * np.sin(TAU * (f + det) * t))
    i_tine = (0.6 + 2.2 * vel) * np.exp(-t / 0.018)
    tine = np.sin(TAU * f * t + i_tine * np.sin(TAU * f * 14.0 * t)) * np.exp(-t / 0.25)
    env = adsr(n_gate, 0.002, 2.5, 0.0, r, n_total=n)
    amp_body = np.exp(-t / (1.6 * (440 / max(f, 60)) ** 0.25))
    return (0.55 * (body + body2) * amp_body + 0.35 * tine) * env


# ------------------------------------------------------------------------------------ drums
def kick(rng, dur=0.42, f0=260.0, f1=50.0, ptau=0.03, adec=0.24, click=0.5, drive=2.0, sub=0.25):
    n = secs(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / ptau)
    ph = np.cumsum(f) / SR
    hold = 0.035
    env = np.where(t < hold, 1.0, np.exp(-(t - hold) / adec))
    body = np.sin(TAU * ph) * env
    body = np.tanh(drive * body) / np.tanh(drive)
    subw = np.sin(TAU * np.cumsum(np.full(n, f1)) / SR) * np.exp(-t / (adec * 1.4)) * np.clip((t - 0.01) / 0.03, 0, 1)
    cl = hp(noise(n, rng), 1800.0) * np.exp(-t / 0.0035)
    cl += np.sin(TAU * 3200 * t) * np.exp(-t / 0.002) * 0.5
    y = body + sub * subw + click * cl
    return fade_edges(y, 0.0003, 0.02)


def snare(rng, dur=0.5, tone=190.0, noise_dec=0.16, body=0.6, snap=0.8, gated=0.0):
    n = secs(dur)
    t = tvec(n)
    f = tone * (1 + 0.5 * np.exp(-t / 0.012))
    b = (np.sin(TAU * np.cumsum(f) / SR) + 0.55 * np.sin(TAU * np.cumsum(f * 1.72) / SR)) * np.exp(-t / 0.07)
    nz = noise(n, rng)
    nz = bp(nz, 2600.0, 0.6) * 0.8 + hp(nz, 5500.0) * 0.5
    nenv = np.exp(-t / noise_dec)
    y = body * b + snap * nz * nenv
    y = np.tanh(1.4 * y)
    if gated > 0:
        # 80s gated room: dense noise IR, flat for ~180 ms then hard-ish close
        ni = secs(0.26)
        ti = tvec(ni)
        ir = rng.standard_normal(ni) * np.where(ti < 0.17, np.exp(-ti / 0.4), np.exp(-0.17 / 0.4) * np.exp(-(ti - 0.17) / 0.015))
        ir = lp(ir, 7000.0)
        ir = hp(ir, 250.0)
        ir /= np.sqrt(np.sum(ir ** 2))
        wet = sps.fftconvolve(y, ir)[:n]
        y = y + gated * wet
    return fade_edges(y, 0.0003, 0.02)


def clap(rng, dur=0.45, fc=1300.0, dec=0.11, spread_ms=(0, 9, 19, 30)):
    n = secs(dur)
    t = tvec(n)
    nz = noise(n, rng)
    nz = bp(nz, fc, 0.9) + 0.3 * bp(nz, fc * 2.6, 1.2)
    env = np.zeros(n)
    for i, ms in enumerate(spread_ms):
        s0 = ms / 1000.0
        tt = t - s0
        last = i == len(spread_ms) - 1
        env += np.where(tt >= 0, np.exp(-np.maximum(tt, 0) / (dec if last else 0.006)), 0) * (1.0 if last else 0.8)
    y = nz * env
    return fade_edges(np.tanh(1.5 * y), 0.0002, 0.02)


HAT_FREQS = np.array([205.3, 304.4, 369.6, 522.7, 800.0, 540.0])


def metal(n, rng, base=1.0):
    t = tvec(n)
    m = np.zeros(n)
    for f in HAT_FREQS * base * 1.62:
        m += np.sign(np.sin(TAU * f * t + rng.uniform(0, TAU)))
    return m / 6.0


def hat(rng, dur=0.06, dec=0.022, open_=False, tone=0.5, bright=9000.0):
    n = secs(dur)
    t = tvec(n)
    m = metal(n, rng)
    nz = noise(n, rng)
    x = tone * m + (1 - tone) * nz
    x = bp(x, bright, 0.9) + 0.6 * hp(x, bright * 0.8)
    env = perc(n, 0.0004, dec)
    return fade_edges(x * env, 0.0002, 0.004 if not open_ else 0.02)


def crash(rng, dur=2.6, dec=0.75, bright=7000.0):
    n = secs(dur)
    t = tvec(n)
    m = metal(n, rng, 1.0) + 0.7 * metal(n, rng, 1.37)
    nz = noise(n, rng)
    x = 0.35 * m + nz
    x = hp(x, 3000.0) * 0.7 + bp(x, bright, 0.7)
    env = perc(n, 0.001, dec) * (0.4 + 0.6 * np.exp(-t / 0.08))
    # slow brightness decay
    y = x * env
    y = lp(y, 16000.0 * np.exp(-t / 1.5) + 3000.0)
    return fade_edges(y, 0.0003, 0.2)


def ride(rng, dur=1.4):
    n = secs(dur)
    t = tvec(n)
    x = 0.6 * metal(n, rng, 2.1) + 0.4 * noise(n, rng)
    x = bp(x, 8500.0, 1.4)
    bell = sum(np.sin(TAU * f * t) for f in (2650, 3720, 5010)) * np.exp(-t / 0.35) * 0.15
    return fade_edges((x * perc(n, 0.0005, 0.42)) + bell, 0.0003, 0.1)


def tom(rng, f=110.0, dur=0.45):
    n = secs(dur)
    t = tvec(n)
    ff = f * (1 + 0.6 * np.exp(-t / 0.03))
    y = np.sin(TAU * np.cumsum(ff) / SR) * np.exp(-t / 0.16)
    y += 0.15 * bp(noise(n, rng), 2500, 0.7) * np.exp(-t / 0.03)
    return fade_edges(np.tanh(1.3 * y), 0.0003, 0.02)


def riser(rng, dur, f_lo=300.0, f_hi=9000.0, q=2.5, curve=2.0, tonal=None):
    """Noise riser with sweeping band-pass + optional saw sweep; amplitude swells in."""
    n = secs(dur)
    x = np.linspace(0, 1, n)
    fc = f_lo * (f_hi / f_lo) ** (x ** curve)
    nz = noise(n, rng)
    y = svf(nz, fc, np.full(n, q), 1) * 0.9 + 0.25 * hp(nz, 6000.0) * x ** 3
    if tonal is not None:
        f0, f1 = tonal
        fr = f0 * (f1 / f0) ** (x ** 1.6)
        sw = sum(saw(fr * 2 ** (c / 1200), rng.uniform()) for c in (-12, 0, 13))
        y += 0.18 * svf(sw, fc * 0.8 + 400, np.full(n, 1.0), 0)
    env = x ** 1.8
    return fade_edges(y * env, 0.01, 0.002)


def reverse_swell(rng, dur=1.5, bright=6000.0):
    c = crash(rng, dur + 0.6, dec=0.9, bright=bright)[: secs(dur)]
    y = c[::-1].copy()
    return fade_edges(y, 0.05, 0.003)


def sub_drop(rng, dur=1.6, f0=110.0, f1=28.0, tau=0.35):
    n = secs(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    y = np.sin(TAU * np.cumsum(f) / SR) * perc(n, 0.003, dur / 2.8)
    return fade_edges(np.tanh(1.6 * y), 0.001, 0.05)


def boom(rng, dur=2.5):
    """Cinematic impact: sub drop + body thump + noise crack + metallic ring."""
    n = secs(dur)
    t = tvec(n)
    s = sub_drop(rng, dur, 95.0, 30.0, 0.25)
    thump = kick(rng, 0.6, f0=180, f1=42, ptau=0.05, adec=0.22, click=0.9, drive=3.0)
    crack = hp(noise(n, rng), 1500.0) * np.exp(-t / 0.05)
    crack = np.tanh(3 * crack) * 0.5
    rng2 = rng
    ring = crash(rng2, dur, dec=0.9, bright=5000.0) * 0.5
    y = 1.0 * s
    y[: thump.shape[0]] += 0.9 * thump
    y += crack + ring
    return fade_edges(y, 0.0003, 0.3)


# ----------------------------------------------------------------------------------- effects
@nb.njit(cache=True, fastmath=True)
def _allpass(x, d, g):
    n = x.shape[0]
    buf = np.zeros(d)
    y = np.empty(n)
    w = 0
    for i in range(n):
        b = buf[w]
        v = x[i] + g * b
        y[i] = b - g * v
        buf[w] = v
        w += 1
        if w >= d:
            w = 0
    return y


@nb.njit(cache=True, fastmath=True)
def _fdn8(xl, xr, dl, gains, damp, mod_depth):
    n = xl.shape[0]
    N = 8
    maxd = 0
    for i in range(N):
        if dl[i] > maxd:
            maxd = dl[i]
    maxd += 64
    buf = np.zeros((N, maxd))
    wp = np.zeros(N, np.int64)
    lpst = np.zeros(N)
    s = np.zeros(N)
    yl = np.empty(n)
    yr = np.empty(n)
    inl = np.array([1.0, -1.0, 1.0, -1.0, 1.0, 1.0, -1.0, -1.0])
    inr = np.array([1.0, 1.0, -1.0, -1.0, -1.0, 1.0, 1.0, -1.0])
    ol = np.array([1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0])
    orr = np.array([1.0, -1.0, 1.0, 1.0, 1.0, -1.0, -1.0, 1.0])
    for i in range(n):
        tot = 0.0
        for j in range(N):
            # gentle modulation of read position (chorus in the tail) -> fractional read
            md = mod_depth * np.sin(6.2831853 * (0.11 + 0.07 * j) * i / 44100.0 + j)
            rp = wp[j] - dl[j] - md
            while rp < 0:
                rp += maxd
            i0 = int(rp)
            fr = rp - i0
            i1 = i0 + 1
            if i1 >= maxd:
                i1 -= maxd
            v = buf[j, i0] * (1 - fr) + buf[j, i1] * fr
            lpst[j] += (v - lpst[j]) * (1.0 - damp)
            s[j] = lpst[j] * gains[j]
            tot += s[j]
        hh = tot * (2.0 / N)
        ol_ = 0.0
        or_ = 0.0
        for j in range(N):
            ol_ += s[j] * ol[j]
            or_ += s[j] * orr[j]
            buf[j, wp[j]] = s[j] - hh + 0.35 * (xl[i] * inl[j] + xr[i] * inr[j])
            wp[j] += 1
            if wp[j] >= maxd:
                wp[j] = 0
        yl[i] = ol_ * 0.35
        yr[i] = or_ * 0.35
    return yl, yr


def reverb(x, rt60=2.0, size=1.0, damp=0.35, predelay=0.02, hpf=180.0, lpf=11000.0, mod=4.0, seed=0):
    """Stereo FDN reverb (Schroeder allpass input diffusion + 8-line Householder FDN).
    Returns the wet signal only, same length as x (caller pads for tails)."""
    if x.ndim == 1:
        x = np.stack([x, x], axis=-1)
    base = np.array([1013, 1187, 1361, 1499, 1693, 1871, 2053, 2273], dtype=float)
    dl = np.round(base * size * 1.6).astype(np.int64)
    gains = 10 ** (-3.0 * dl / (rt60 * SR))
    pre = secs(predelay)
    xl = np.concatenate([np.zeros(pre), x[:, 0]])[: x.shape[0]]
    xr = np.concatenate([np.zeros(pre), x[:, 1]])[: x.shape[0]]
    for d, g in ((142, 0.7), (107, 0.7), (379, 0.6), (277, 0.6)):
        xl = _allpass(np.ascontiguousarray(xl), int(d * size + 0.5), g)
        xr = _allpass(np.ascontiguousarray(xr), int(d * size * 1.13 + 0.5), g)
    yl, yr = _fdn8(xl, xr, dl, gains, damp, mod)
    y = np.stack([yl, yr], axis=-1)
    y = eq(y, [("hp", hpf, 0, 0.7), ("lp", lpf, 0, 0.7)])
    return y


@nb.njit(cache=True, fastmath=True)
def _pingpong(xm, dl, dr, fb, lpc, hpc):
    n = xm.shape[0]
    M = max(dl, dr) + 8
    bl = np.zeros(M)
    br = np.zeros(M)
    yl = np.empty(n)
    yr = np.empty(n)
    w = 0
    sl = 0.0
    sr = 0.0
    hl = 0.0
    hr = 0.0
    for i in range(n):
        rl = bl[(w - dl) % M]
        rr = br[(w - dr) % M]
        sl += (rl - sl) * lpc
        sr += (rr - sr) * lpc
        hl += (sl - hl) * hpc
        hr += (sr - hr) * hpc
        fl = sl - hl
        fr = sr - hr
        bl[w] = xm[i] + fb * fr
        br[w] = fb * fl
        yl[i] = rl
        yr[i] = rr
        w += 1
        if w >= M:
            w = 0
    return yl, yr


def pingpong(x, t_l, t_r=None, fb=0.4, lpf=5000.0, hpf=250.0):
    xm = x.mean(axis=1) if x.ndim == 2 else x
    t_r = t_l if t_r is None else t_r
    lpc = 1 - np.exp(-TAU * lpf / SR)
    hpc = 1 - np.exp(-TAU * hpf / SR)
    yl, yr = _pingpong(np.ascontiguousarray(xm), secs(t_l), secs(t_r), fb, lpc, hpc)
    return np.stack([yl, yr], axis=-1)


@nb.njit(cache=True, fastmath=True)
def _comp_gain(det_db, thr, ratio, knee, att, rel):
    n = det_db.shape[0]
    g = np.empty(n)
    ac = 1.0 - np.exp(-1.0 / max(att * 44100.0, 1.0))
    rc = 1.0 - np.exp(-1.0 / max(rel * 44100.0, 1.0))
    st = 0.0
    for i in range(n):
        x = det_db[i]
        over = x - thr
        if 2 * over < -knee:
            gr = 0.0
        elif 2 * abs(over) <= knee:
            gr = (1.0 / ratio - 1.0) * (over + knee / 2) ** 2 / (2 * knee)
        else:
            gr = (1.0 / ratio - 1.0) * over
        if gr < st:
            st += (gr - st) * ac
        else:
            st += (gr - st) * rc
        g[i] = st
    return g


def compress(x, thr_db=-18.0, ratio=3.0, att=0.01, rel=0.12, knee=6.0, makeup_db=0.0, sidechain=None,
             rms_ms=5.0):
    sc = x if sidechain is None else sidechain
    m = np.abs(sc).max(axis=1) if sc.ndim == 2 else np.abs(sc)
    if rms_ms > 0:
        m = np.sqrt(np.maximum(smooth(m * m, rms_ms), 0)) * 1.414
    det = todb(m)
    gdb = _comp_gain(np.ascontiguousarray(det), thr_db, ratio, knee, att, rel)
    g = dbg(gdb + makeup_db)
    return x * (g[:, None] if x.ndim == 2 else g), gdb


def softclip(x, thresh=0.7):
    """Smooth knee saturator: linear below thresh, tanh into ceiling 1.0 above."""
    a = np.abs(x)
    over = a > thresh
    y = np.array(x, copy=True)
    k = 1 - thresh
    y[over] = np.sign(x[over]) * (thresh + k * np.tanh((a[over] - thresh) / k))
    return y


def true_peak_env(x, os=4):
    if x.ndim == 1:
        x = x[:, None]
    up = sps.resample_poly(x, os, 1, axis=0)
    p = np.abs(up).max(axis=1)
    n = x.shape[0]
    p = p[: n * os].reshape(n, os).max(axis=1)
    return np.maximum(p, np.abs(x).max(axis=1))


@nb.njit(cache=True, fastmath=True)
def _release(s, rc):
    n = s.shape[0]
    g = np.empty(n)
    v = s[0]
    for i in range(n):
        if s[i] < v:
            v = s[i]
        else:
            v += (s[i] - v) * rc
        g[i] = v
    return g


def limiter(x, ceiling_db=-1.2, look_ms=3.0, rel_ms=80.0):
    """True-peak-aware lookahead brickwall limiter (no added latency: gain looks ahead)."""
    c = dbg(ceiling_db)
    p = true_peak_env(x)
    gt = np.minimum(1.0, c / np.maximum(p, 1e-9))
    W = max(2, secs(look_ms / 1000))
    # h[n] = min(gt[n .. n+W-1]) ; s = moving average over h[n-W+1 .. n]
    h = minimum_filter1d(gt, size=W, origin=-(W // 2), mode="nearest")
    s = np.convolve(h, np.ones(W) / W, mode="full")[: len(h)]
    s[: W] = np.minimum(s[:W], h[:W])
    s = np.minimum(s, gt)
    g = _release(np.ascontiguousarray(s), 1 - np.exp(-1.0 / (rel_ms / 1000 * SR)))
    g = np.minimum(g, s)
    y = x * (g[:, None] if x.ndim == 2 else g)
    return y, g


# ------------------------------------------------------------------------- circular helpers
def circ(fn, x, pre=None, post=None):
    """Run fn on a loop-periodic signal so that its internal state at the loop seam is the
    steady state: process [tail | x | head] and keep the middle."""
    n = x.shape[0]
    pre = min(n, secs(3.0)) if pre is None else min(pre, n)
    post = min(n, secs(0.05)) if post is None else min(post, n)
    ext = np.concatenate([x[n - pre:], x, x[:post]], axis=0)
    y = fn(ext)
    if isinstance(y, tuple):
        y = y[0]
    return y[pre: pre + n]


def wrap_tail(y, n):
    """Fold everything past n back onto the start (steady-state of a periodic input)."""
    out = np.array(y[:n], copy=True)
    k = n
    while k < y.shape[0]:
        seg = y[k: k + n]
        out[: seg.shape[0]] += seg
        k += n
    return out


def circ_lti(fn, x, tail_s):
    """For linear time-invariant effects (reverb/delay): pad, process, fold tail onto start."""
    n = x.shape[0]
    pad = np.zeros((secs(tail_s),) + x.shape[1:])
    y = fn(np.concatenate([x, pad], axis=0))
    return wrap_tail(y, n)


# ------------------------------------------------------------------------------- loudness/io
def lufs(x):
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)
    xx = x if x.ndim == 2 else x[:, None]
    if xx.shape[0] < secs(0.45):
        xx = np.concatenate([xx, np.zeros((secs(0.45) - xx.shape[0], xx.shape[1]))])
    return meter.integrated_loudness(xx)


def true_peak_db(x):
    xx = x if x.ndim == 2 else x[:, None]
    up = sps.resample_poly(xx, 4, 1, axis=0)
    return todb(max(np.abs(up).max(), np.abs(xx).max()))


def peak_db(x):
    return todb(np.abs(x).max())


def normalize_peak(x, peak_db_target=-1.5):
    return x * dbg(peak_db_target) / (np.abs(x).max() + 1e-12)


def remove_dc(x, circular=False):
    return x - x.mean(axis=0)


def write_wav(path, x, peak_db_target=None):
    import soundfile as sf
    x = np.asarray(x, dtype=float)
    assert np.all(np.isfinite(x)), f"non-finite samples in {path}"
    if peak_db_target is not None:
        x = normalize_peak(x, peak_db_target)
    xi = np.clip(np.round(x * 32768.0), -32768, 32767).astype(np.int16)  # explicit, unbiased rounding
    sf.write(str(path), xi, SR, subtype="PCM_16")
    return xi.astype(float) / 32768.0


def write_ogg(path, x, quality=0.6):
    """OGG Vorbis via libsndfile/libvorbis. quality 0.6 == oggenc -q6."""
    import soundfile as sf
    x = np.asarray(x, dtype=float)
    assert np.all(np.isfinite(x)), f"non-finite samples in {path}"
    x = np.clip(x, -1, 1)
    ch = 1 if x.ndim == 1 else x.shape[1]
    # write in small blocks: one huge write crashes libvorbis (_preextrapolate_helper)
    with sf.SoundFile(str(path), "w", SR, ch, format="OGG", subtype="VORBIS",
                      compression_level=1.0 - quality) as f:
        for i in range(0, x.shape[0], 4096):
            f.write(x[i: i + 4096])
