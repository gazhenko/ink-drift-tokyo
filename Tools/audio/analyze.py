"""Objective checks for generated audio (we can't listen, so we measure).

usage: python analyze.py [--png DIR] [--loop] FILE...
Reports duration, sample peak, true peak (4x oversampled), integrated LUFS (BS.1770 via
pyloudnorm), DC offset, NaN/Inf, a click detector (2nd-difference outliers vs local RMS),
and for loops the seam: the junction end->start is checked with the same detector, plus
level continuity across the boundary. Optionally renders waveform + spectrogram PNGs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal as sps
from scipy.ndimage import uniform_filter1d

sys.path.insert(0, str(Path(__file__).parent))
import inkdsp as d  # noqa: E402


def load(path):
    x, sr = sf.read(str(path), always_2d=True)
    return x.astype(float), sr


def click_scan(x, win_ms=8.0, ratio=14.0, abs_thr=0.08, sr=44100):
    """Flag isolated sample-level discontinuities: |2nd diff| far above its local RMS."""
    hits = []
    worst = 0.0
    for c in range(x.shape[1]):
        d2 = np.zeros(x.shape[0])
        d2[1:-1] = x[2:, c] - 2 * x[1:-1, c] + x[:-2, c]
        w = max(3, int(win_ms * 1e-3 * sr))
        loc = np.sqrt(uniform_filter1d(d2 * d2, w) + 1e-12)
        # exclude the sample's own contribution from the local RMS estimate
        loc_ex = np.sqrt(np.maximum(loc ** 2 - d2 * d2 / w, 0) + 1e-12)
        r = np.abs(d2) / loc_ex
        bad = np.where((r > ratio) & (np.abs(d2) > abs_thr))[0]
        if bad.size:
            hits += [(int(i), c, float(r[i])) for i in bad[:20]]
        mask = np.abs(d2) > abs_thr
        if mask.any():
            worst = max(worst, float(r[mask].max()))
    return hits, worst


def seam_report(x, sr=44100):
    k = int(0.05 * sr)
    j = np.concatenate([x[-k:], x[:k]])
    hits, worst = click_scan(j)
    seam_hits = [h for h in hits if abs(h[0] - k) < 64]
    jump = float(np.abs(x[0] - x[-1]).max())
    d1 = np.abs(np.diff(x, axis=0))
    p999 = float(np.percentile(d1, 99.9))
    # derivative continuity: compare slope across seam with typical slopes
    slope_end = x[-1] - x[-2]
    slope_start = x[1] - x[0]
    slope_jump = float(np.abs(slope_start - slope_end).max())
    rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-12)
    m = int(0.1 * sr)
    return {
        "seam_sample_jump": round(jump, 5),
        "typical_step_p99.9": round(p999, 5),
        "seam_slope_change": round(slope_jump, 5),
        "seam_click_flags": len(seam_hits),
        "seam_worst_d2_ratio": round(worst, 2),
        "rms_last100ms_db": round(rms(x[-m:]), 2),
        "rms_first100ms_db": round(rms(x[:m]), 2),
    }


def report(path, loop=False):
    x, sr = load(path)
    rep = {"file": str(path), "sr": sr, "channels": x.shape[1], "samples": x.shape[0],
           "duration_s": round(x.shape[0] / sr, 4)}
    rep["finite"] = bool(np.all(np.isfinite(x)))
    rep["peak_dbfs"] = round(float(d.peak_db(x)), 2)
    rep["true_peak_dbtp"] = round(float(d.true_peak_db(x)), 2)
    try:
        rep["lufs_i"] = round(float(d.lufs(x)), 2)
    except Exception as e:  # noqa: BLE001
        rep["lufs_i"] = None
    rep["dc_offset"] = [float(f"{v:.2e}") for v in x.mean(axis=0)]
    hits, worst = click_scan(x)
    rep["click_flags"] = len(hits)
    rep["click_examples_s"] = [round(h[0] / sr, 4) for h in hits[:6]]
    rep["first_last_sample"] = [round(float(np.abs(x[0]).max()), 5), round(float(np.abs(x[-1]).max()), 5)]
    if loop:
        rep["seam"] = seam_report(x, sr)
    return rep


def plot(path, out_png, loop=False, title=None, fmax=20000):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x, sr = load(path)
    mono = x.mean(axis=1)
    rows = 3 if loop else 2
    fig, ax = plt.subplots(rows, 1, figsize=(12, 2.4 * rows + 1.2), dpi=90)
    t = np.arange(len(mono)) / sr
    ax[0].plot(t, x[:, 0], lw=0.4, color="#FF2D7A")
    if x.shape[1] > 1:
        ax[0].plot(t, x[:, 1], lw=0.4, color="#00B8CC", alpha=0.6)
    ax[0].set_xlim(0, t[-1])
    ax[0].set_ylim(-1, 1)
    ax[0].axhline(10 ** (-1 / 20), color="k", lw=0.5, ls=":")
    ax[0].axhline(-(10 ** (-1 / 20)), color="k", lw=0.5, ls=":")
    ax[0].set_title(title or Path(path).name)
    nper = 2048 if len(mono) > 2048 * 8 else 512
    f, tt, S = sps.spectrogram(mono, sr, nperseg=nper, noverlap=nper * 3 // 4)
    S = 10 * np.log10(S + 1e-14)
    ax[1].pcolormesh(tt, f[1:], S[1:], shading="auto", cmap="magma", vmin=S.max() - 90, vmax=S.max())
    ax[1].set_yscale("log")
    ax[1].set_ylim(30, fmax)
    ax[1].set_ylabel("Hz")
    if loop:
        k = int(0.03 * sr)
        j = np.concatenate([x[-k:], x[:k]])
        tj = (np.arange(len(j)) - k) / sr * 1000
        ax[2].plot(tj, j[:, 0], lw=0.6, color="#FF2D7A")
        if x.shape[1] > 1:
            ax[2].plot(tj, j[:, 1], lw=0.6, color="#00B8CC", alpha=0.7)
        ax[2].axvline(0, color="k", lw=0.6)
        ax[2].set_xlabel("ms around loop seam (end | start)")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--png", default=None)
    a = ap.parse_args()
    for fp in a.files:
        r = report(fp, a.loop)
        print(json.dumps(r))
        if a.png:
            Path(a.png).mkdir(parents=True, exist_ok=True)
            plot(fp, Path(a.png) / (Path(fp).stem + ".png"), a.loop)


if __name__ == "__main__":
    main()
