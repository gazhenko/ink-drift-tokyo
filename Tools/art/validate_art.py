"""Sanity checks for generated art: sizes (power-of-two), modes, pairing of albedo/emission,
facade map completeness, tileability (edge-continuity ratio) and margins. Prints a summary.
usage: python validate_art.py"""
import glob
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import ART  # noqa

PO2 = {2 ** i for i in range(4, 14)}


def info(p):
    im = Image.open(p)
    return im.size, im.mode


def seam_ratio(a, axis):
    a = a.astype(np.float32)
    if axis == 1:
        edge = np.abs(a[:, 0] - a[:, -1]).mean()
        inner = np.abs(a[:, 1:] - a[:, :-1]).mean()
    else:
        edge = np.abs(a[0] - a[-1]).mean()
        inner = np.abs(a[1:] - a[:-1]).mean()
    return edge / max(inner, 1e-6)


def main():
    problems = []
    counts = {}
    for sub in ("Fonts", "Callouts", "Signs", "Facades", "Decals", "UI"):
        files = sorted(glob.glob(os.path.join(ART, sub, "*")))
        files = [f for f in files if not f.endswith(".meta")]
        pngs = [f for f in files if f.endswith(".png")]
        counts[sub] = (len(files), len(pngs))
        for p in pngs:
            (w, h), mode = info(p)
            if w not in PO2 or h not in PO2:
                problems.append(f"non-power-of-two {w}x{h}: {os.path.relpath(p, ART)}")
    # pairing albedo/emission
    for sub in ("Signs", "Facades"):
        for a in glob.glob(os.path.join(ART, sub, "*_albedo.png")):
            e = a.replace("_albedo.png", "_emission.png")
            if not os.path.exists(e):
                problems.append(f"missing emission for {os.path.basename(a)}")
            elif info(a)[0] != info(e)[0]:
                problems.append(f"albedo/emission size mismatch {os.path.basename(a)}")
    # facade maps
    for a in glob.glob(os.path.join(ART, "Facades", "*_albedo.png")):
        base = a[:-len("_albedo.png")]
        for suf in ("_normal.png", "_emission.png", "_mask.png"):
            if not os.path.exists(base + suf):
                problems.append(f"missing {os.path.basename(base + suf)}")
        m = base + "_mask.png"
        if os.path.exists(m) and info(m)[1] != "RGBA":
            problems.append(f"mask not RGBA: {os.path.basename(m)}")
        arr = np.asarray(Image.open(a).convert("RGB"))
        rx, ry = seam_ratio(arr, 1), seam_ratio(arr, 0)
        name = os.path.basename(base)
        print(f"  facade {name:22s} {arr.shape[1]}x{arr.shape[0]}  seam x {rx:4.2f}  y {ry:4.2f}")
    sign_alb = glob.glob(os.path.join(ART, "Signs", "*_albedo.png"))
    bb = [p for p in sign_alb if os.path.basename(p).startswith("bb_")]
    vend = [p for p in sign_alb if os.path.basename(p).startswith("vending_")]
    shop = [p for p in sign_alb if p not in bb and p not in vend]
    print("counts (files, pngs):", counts)
    print(f"signs: {len(shop)} storefront, {len(bb)} billboards, {len(vend)} vending fronts")
    liv = glob.glob(os.path.join(ART, "Decals", "livery_*.png"))
    road = glob.glob(os.path.join(ART, "Decals", "road_*.png"))
    print(f"decals: {len(road)} road, {len(liv)} livery")
    for p in liv:
        a = np.asarray(Image.open(p).convert("RGBA"))[..., 3] > 8
        ys, xs = np.nonzero(a)
        if len(xs):
            mg = min(xs.min(), ys.min(), a.shape[1] - 1 - xs.max(), a.shape[0] - 1 - ys.max())
            if mg < 8:
                problems.append(f"livery near edge ({mg}px): {os.path.basename(p)}")
    print("problems:" if problems else "no problems found")
    for q in problems:
        print("  -", q)


if __name__ == "__main__":
    main()
