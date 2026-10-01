"""Music inspection plots: short-term loudness, long-term spectrum vs pink slope, zoomed
piano-roll-like spectrograms. usage: python musicviz.py FILE OUT.png [t0 t1] [t0 t1] ..."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as sps

sys.path.insert(0, str(Path(__file__).parent))


def short_term_lufs(x, sr, win=3.0, hop=0.5):
    import pyloudnorm as pyln
    meter = pyln.Meter(sr)
    # K-weight once, then windowed mean-square
    xf = x.copy()
    for _, f in meter._filters.items():
        xf = sps.lfilter(f.b, f.a, xf, axis=0)
    p = (xf ** 2).sum(axis=1)
    w = int(win * sr)
    h = int(hop * sr)
    c = np.cumsum(np.concatenate([[0], p]))
    idx = np.arange(0, len(p) - w, h)
    ms = (c[idx + w] - c[idx]) / w
    return (idx + w / 2) / sr, -0.691 + 10 * np.log10(ms + 1e-12)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fp, out = sys.argv[1], sys.argv[2]
    ranges = [(float(a), float(b)) for a, b in zip(sys.argv[3::2], sys.argv[4::2])]
    x, sr = sf.read(fp, always_2d=True)
    mono = x.mean(axis=1)
    rows = 2 + len(ranges)
    fig = plt.figure(figsize=(13, 2.6 * rows + 0.5), dpi=85)
    ax1 = fig.add_subplot(rows, 2, 1)
    t, st = short_term_lufs(x, sr)
    ax1.plot(t, st, color="#FF2D7A")
    ax1.set_ylim(-40, -5)
    ax1.grid(alpha=0.3)
    ax1.set_title("short-term loudness (3 s)")
    ax2 = fig.add_subplot(rows, 2, 2)
    f, P = sps.welch(mono, sr, nperseg=8192)
    P = 10 * np.log10(P + 1e-20)
    # 1/6-octave smoothing
    lf = np.log2(np.maximum(f, 1))
    Ps = np.array([P[(lf > l - 1 / 12) & (lf < l + 1 / 12)].mean() if ((lf > l - 1 / 12) & (lf < l + 1 / 12)).any() else np.nan for l in lf])
    ax2.semilogx(f[1:], Ps[1:], color="#00B8CC")
    ref = Ps[np.argmin(abs(f - 1000))]
    for slope, ls in ((-3, ":"), (-4.5, "--")):
        ax2.semilogx(f[1:], ref + slope * np.log2(f[1:] / 1000), "k", ls=ls, lw=0.7)
    ax2.set_xlim(20, 20000)
    ax2.set_ylim(ref - 45, ref + 35)
    ax2.grid(alpha=0.3, which="both")
    ax2.set_title("avg spectrum (dotted -3 dB/oct, dashed -4.5)")
    ax3 = fig.add_subplot(rows, 1, 2)
    ff, tt, S = sps.spectrogram(mono, sr, nperseg=4096, noverlap=3072)
    S = 10 * np.log10(S + 1e-14)
    ax3.pcolormesh(tt, ff[1:], S[1:], shading="auto", cmap="magma", vmin=S.max() - 80, vmax=S.max())
    ax3.set_yscale("log")
    ax3.set_ylim(30, 16000)
    for i, (a, b) in enumerate(ranges):
        ax = fig.add_subplot(rows, 1, 3 + i)
        seg = mono[int(a * sr): int(b * sr)]
        ff, tt, S = sps.spectrogram(seg, sr, nperseg=8192, noverlap=8192 - 512)
        S = 10 * np.log10(S + 1e-14)
        sel = (ff > 40) & (ff < 5000)
        ax.pcolormesh(tt + a, ff[sel], S[sel], shading="auto", cmap="magma", vmin=S.max() - 70, vmax=S.max())
        ax.set_yscale("log")
        ax.set_ylim(40, 5000)
        ax.set_title(f"{a:.1f}-{b:.1f}s")
    fig.tight_layout()
    fig.savefig(out)


if __name__ == "__main__":
    main()
