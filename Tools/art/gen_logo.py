"""gen_logo.py — INK DRIFT: TOKYO title logo (4096x1536, transparent).

Usage:
    python gen_logo.py              # final render (ss=2) -> Art/UI/logo_inkdrift.png (+ _mono) + previews
    python gen_logo.py --preview    # fast low-res render to the scratch/preview folder (ss=0.5)

Layers (back to front):
  1. sumi ink brush swipe + ink splat backdrop (with magenta / cyan paint swipes peeking out)
  2. speed-streaks + tire-smoke puffs trailing the wordmark
  3. 3D extruded wordmark  INK | DRIFT  (paper inner stroke, heavy ink stroke, indigo extrusion,
     gradient fill, halftone, gloss streak), ink drips
  4. ": TOKYO" Persona-style slashed banner and インクドリフト東京 tape
  5. splatter flecks + sparkles
"""
from __future__ import annotations

import gc
import math
import os
import sys

import numpy as np
import skia
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uilib import *  # noqa: E402,F403
import inklib  # noqa: E402

W, H = 4096, 1536
INK, PAPER = C("ink"), C("paper")
MAG, CYAN, YEL, RED, IND = C("magenta"), C("cyan"), C("yellow"), C("red"), C("indigo")
OUT = os.path.join(inklib.ART, "UI")


def wordmark_paths(box=(380, 150, 3700, 900)):
    """Returns (ink_path, drift_path) — sheared/rotated Bangers wordmark fitted into box."""
    size = 1000
    ink = text_path("INK", "bangers", size, tracking=0.02)
    gap = size * 0.20
    adv_ink = text_advance("INK", "bangers", size, tracking=0.02)
    drift = text_path("DRIFT", "bangers", size, tracking=0.02, x=adv_ink + gap)
    both = combine(ink, drift)
    l, t, r_, b = bounds(both)
    piv = ((l + r_) / 2, (t + b) / 2)
    ink = transformed(ink, rotate=-5.5, skew_x=-0.16, pivot=piv)
    drift = transformed(drift, rotate=-5.5, skew_x=-0.16, pivot=piv)
    both = combine(ink, drift)
    l, t, r_, b = bounds(both)
    s = min((box[2] - box[0]) / (r_ - l), (box[3] - box[1]) / (b - t))
    m = skia.Matrix()
    m.setTranslate(-l, -t)
    m.postScale(s, s)
    m.postTranslate(box[0] + ((box[2] - box[0]) - (r_ - l) * s) / 2, box[1] + ((box[3] - box[1]) - (b - t) * s) / 2)
    ink.transform(m); drift.transform(m)
    return ink, drift


def smoke_puffs(cv, cx, cy, n, size, r, color=None, shade=None):
    """Manga tire-smoke: overlapping puffs (paper) with halftone shading + ink outline."""
    color = PAPER if color is None else color
    shade = C("#C9C1EA") if shade is None else shade
    paths = []
    for i in range(n):
        t = i / max(1, n - 1)
        x = cx - t * size * 2.4 + r.uniform(-0.15, 0.15) * size
        y = cy + r.uniform(-0.35, 0.25) * size - t * size * 0.2
        rr = size * (1.0 - 0.55 * t) * r.uniform(0.75, 1.05)
        paths += scallop_cloud(x, y, rr, rr * 0.8, bumps=9, bump=0.32, r=r)
    m = np.zeros((cv.H, cv.W), f32)
    for q in paths:
        np.maximum(m, cv.mask(q), out=m)
    cv.paint(cv.dilate(m, 12), INK)
    cv.paint(m, color)
    # halftone shading toward the bottom-left of the cloud mass
    ramp = cv.ramp((cx - size, cy - size * 0.8), (cx - size * 2.2, cy + size * 0.9))
    dots = cv.halftone(smoothstep(0.35, 1.0, ramp) * 0.40, 16, 45)
    cv.paint(m * dots, shade)
    return m


def render(ss=2.0, out_path=None, mono_path=None):
    cv = FCanvas(W, H, ss=ss)
    r = rng("logo_inkdrift")

    ink_p, drift_p = wordmark_paths()
    l_i, t_i, r_i, b_i = bounds(ink_p)
    l_d, t_d, r_d, b_d = bounds(drift_p)

    # ---------------------------------------------------------------- 1. backdrop
    # magenta paint swipe peeking out above, cyan swipe below (JSR graffiti layering)
    sw_m = brush_mask(cv, [(520, 570), (1400, 460), (2400, 350), (3350, 280), (3880, 255)], 440, rng("swm"),
                      bristles=120, press=0.05, taper=0.30, dry=0.8, dry_start=0.55)
    cv.paint(sw_m, MAG)
    del sw_m
    sw_c = brush_mask(cv, [(820, 1250), (1800, 1170), (2800, 1080), (3700, 990), (3990, 960)], 330, rng("swc"),
                      bristles=100, press=0.05, taper=0.35, dry=0.85, dry_start=0.5)
    cv.paint(sw_c, CYAN)
    del sw_c
    # flecks behind everything
    cv.paint(cv.mask(flecks_in(2050, 700, 1850, 260, (2, 15), rng("flb"), (60, 50, W - 60, H - 50), sigma=0.5, elong=0.4)), INK)
    # main sumi swipe (loaded head lower-left, dry splayed tail upper-right)
    sumi = brush_mask(cv, [(330, 880), (1100, 815), (2000, 720), (2950, 610), (3650, 540), (3960, 510)], 950,
                      rng("sumi"), bristles=180, press=0.06, taper=0.30, dry=0.9, dry_start=0.6, splay=0.30)
    for p in organic_splat(470, 880, 330, rng("sumisplat"), arms=20, blob=0.62, wob=0.22, arm_len=(0.2, 0.7)):
        np.maximum(sumi, cv.mask(p), out=sumi)
    cv.paint(sumi, INK)
    sheen = cv.halftone(smoothstep(0.0, 1.0, 1 - cv.ramp((0, 300), (0, 1300))) * 0.28, 22, 45)
    cv.paint(sumi * sheen, IND, 0.9)
    del sheen
    xs = [600, 860, 1300, 1700, 2150, 2540, 2950, 3300]
    drips_clean(cv, sumi, xs, [r.uniform(26, 46) for _ in xs], [r.uniform(80, 240) for _ in xs], INK, r, overlap=26)
    del sumi
    gc.collect()

    # ---------------------------------------------------------------- 2. smoke + speed streaks
    # bold comic motion streaks trailing the wordmark (paper with ink outline + a few cyan/magenta)
    streaks = []
    ys = np.linspace(t_i + 120, b_i - 90, 7)
    for i, y in enumerate(ys):
        y = y + r.uniform(-25, 25)
        # left edge of the sheared wordmark at this height (bangers skew + rotation)
        x1 = l_i + (b_i - y) * 0.27 + r.uniform(30, 120)
        L = r.uniform(380, 820)
        x0 = max(110, x1 - L)
        w = r.uniform(26, 52)
        streaks.append((poly([(x0, y), (x1, y - w / 2), (x1, y + w / 2)]), i))
    for pth, i in streaks:
        m = cv.mask(pth)
        cv.paint(cv.dilate(m, 8), INK)
        cv.paint(m, (PAPER, CYAN, PAPER, MAG, PAPER, PAPER, CYAN)[i % 7])
    thin = skia.Path()
    for i in range(14):
        y = r.uniform(t_i + 60, b_i - 60)
        x1 = l_i + (b_i - y) * 0.27 + r.uniform(0, 80)
        L = r.uniform(200, 600)
        thin.addPath(poly([(max(110, x1 - L), y), (x1, y - 5), (x1, y + 5)]))
    cv.paint(cv.mask(thin), PAPER, 0.9)

    # ---------------------------------------------------------------- 3. wordmark
    F_i = cv.mask(ink_p)
    F_d = cv.mask(drift_p)
    # paint drips hanging from the letters themselves (graffiti) — only from stems that reach
    # the (tilted) baseline, so nothing drips out of the middle of a glyph
    rd = rng("letterdrips")
    slope = math.tan(math.radians(5.5))
    for Fm, (lo, hi), n in ((F_i, (l_i + 60, r_i - 60), 3), (F_d, (l_d + 60, r_d - 60), 5)):
        cand = np.linspace(lo, hi, 160)
        ys = bottom_edges(Fm, cv.ss, cand)
        ok = [(x, y) for x, y in zip(cand, ys) if y is not None]
        c = max(y + slope * x for x, y in ok)
        ok = [(x, y) for x, y in ok if y + slope * x > c - 14]
        picks = []
        order = rd.permutation(len(ok))
        for k in order:
            x, y = ok[k]
            if all(abs(x - px) > 170 for px, _ in picks):
                picks.append((x, y))
            if len(picks) >= n:
                break
        for x, y in picks:
            for dp in drip_paths(x, y - 8, rd.uniform(24, 34), rd.uniform(70, 200), rd, bulb=1.35):
                np.maximum(Fm, cv.mask(dp), out=Fm)
    F = np.maximum(F_i, F_d)
    P = cv.dilate(F, 20)
    K = cv.dilate(P, 28)
    del F
    E, depth = depth_extrude(cv, K, 30, 52)
    cv.paint(cv.dilate(E, 12), INK)
    col = gradient_map(depth, [(0, C("#5B34C9")), (0.35, C("#3A2390")), (1, C("#140E33"))])
    inner = cv.erode(E, 5)
    cv.paint(inner, col)
    # ridge hatch on the extrusion (manga speed-hatch along the extrude direction)
    hatch = cv.halftone(0.18, 26, math.degrees(math.atan2(52, 30)) + 90, shape="line")
    cv.paint(inner * hatch * smoothstep(0.15, 0.6, depth), INK, 0.35)
    del col, depth, inner, hatch
    del E
    cv.paint(K, INK)
    cv.paint(P, PAPER)
    del P, K
    gc.collect()
    gl, gt, gr, gb = l_i, min(t_i, t_d), r_d, max(b_i, b_d)
    for Fm, col, (t, b), dark, dot in ((F_i, MAG, (t_i, b_i), C("#B0124F"), C("#7A0B3A")),
                                       (F_d, CYAN, (t_d, b_d), C("#0A6FE0"), C("#0B3F8C"))):
        top = lighten(col, 0.6)
        cv.paint(Fm, cv.vgrad(t, b, [(0, top), (0.40, col), (1, dark)]))
        dots = cv.halftone(cv.ramp((0, t + (b - t) * 0.42), (0, b)) * 0.6, 17, 45)
        cv.paint(Fm * dots, dot, 0.8)
        del dots
        # gloss streak (follows the wordmark's tilt)
        ang = math.tan(math.radians(-5.5))
        y0 = gt + (gb - gt) * 0.30
        band = poly([(gl - 100, y0 - (gl - 100 - gl) * ang * -1), (gr + 100, y0 + (gr + 100 - gl) * ang),
                     (gr + 100, y0 + (gr + 100 - gl) * ang + 70), (gl - 100, y0 + 70)])
        band2 = poly([(gl - 100, y0 + 105), (gr + 100, y0 + (gr + 100 - gl) * ang + 105),
                      (gr + 100, y0 + (gr + 100 - gl) * ang + 128), (gl - 100, y0 + 128)])
        cv.paint(Fm * cv.mask(combine(band, band2)), PAPER, 0.45)
        # inner top highlight edge (rim light) — thin paper line inside the top of each glyph
        rim = Fm * (1 - cv.shift(Fm, 0, 10))
        cv.paint(rim, PAPER, 0.55)
        del rim
    del F_i, F_d
    gc.collect()

    # ---------------------------------------------------------------- 4. TOKYO banner + JP tape
    bx0, by0, bx1, by1 = 2280, 960, 3760, 1210
    slab = poly([(bx0 + 30, by0 - 34), (bx1 + 110, by0 - 80), (bx1 + 40, by1 - 50), (bx0 - 40, by1 - 4)])
    cv.paint(cv.shift(cv.dilate(cv.mask(slab), 10), 14, 16), INK)
    cv.paint(cv.dilate(cv.mask(slab), 10), INK)
    cv.paint(cv.mask(slab), RED)
    band = poly([(bx0 + 70, by0), (bx1 + 50, by0 - 40), (bx1 - 10, by1 - 56), (bx0, by1 - 14)])
    mb = cv.mask(band)
    cv.paint(cv.dilate(mb, 9), PAPER)
    cv.paint(mb, INK)
    cv.paint(mb * cv.halftone(cv.ramp((bx0, 0), (bx1, 0)) * 0.25, 12, 45), IND)
    tk = text_path("TOKYO", "dela", 300, tracking=0.03)
    tk = fit_path(tk, (bx0 + 300, by0 + 40, bx1 - 70, by1 - 70))
    tk = transformed(tk, rotate=-1.6, skew_x=-0.2)
    mt = cv.mask(tk)
    cv.paint(cv.shift(mt, 8, 8), RED)
    cv.paint(mt, PAPER)
    tl, tt, tr, tb = bounds(tk)
    # colon: two slanted squares right before TOKYO
    cx0 = tl - 150
    cl = combine(para(cx0, tt + 6, cx0 + 66, tt + 66, 12), para(cx0 - 14, tb - 62, cx0 + 52, tb - 2, 12))
    cv.paint(cv.dilate(cv.mask(cl), 5), INK)
    cv.paint(cv.mask(cl), YEL)

    # JP tape (acid yellow, slight tilt, torn ends)
    tx0, ty0, tx1, ty1 = 560, 1010, 2160, 1190
    pts = [(tx0, ty0 + 26)]
    rt = rng("tape")
    pts += [(tx1, ty0 - 8)]
    for k in range(1, 6):  # torn right end
        pts.append((tx1 + rt.uniform(-14, 14), ty0 - 8 + (ty1 - 30 - ty0 + 8) * k / 6))
    pts += [(tx1 + 10, ty1 - 30), (tx0 + 10, ty1)]
    for k in range(5, 0, -1):  # torn left end
        pts.append((tx0 + 5 + rt.uniform(-14, 14), ty0 + 26 + (ty1 - ty0 - 26) * k / 6))
    tape = poly(pts)
    mt = cv.mask(tape)
    cv.paint(cv.shift(cv.dilate(mt, 8), 14, 16), INK)
    cv.paint(cv.dilate(mt, 8), INK)
    cv.paint(mt, YEL)
    cv.paint(mt * cv.halftone(cv.ramp((0, ty0), (0, ty1)) * 0.35, 12, 45), C("#FFB000"))
    jp = text_path("インクドリフト東京", "dela", 200, tracking=0.02)
    jp = fit_path(jp, (tx0 + 70, ty0 + 34, tx1 - 60, ty1 - 34))
    jp = transformed(jp, rotate=-1.2, skew_x=-0.1)
    cv.paint(cv.mask(jp), INK)

    # ---------------------------------------------------------------- 5. flecks + sparkles
    cv.paint(cv.mask(flecks_in(3880, 330, 160, 40, (2, 10), rng("fl2"), (60, 50, W - 60, H - 50), sigma=0.6, elong=0.5)), INK)
    for (sx, sy, sr, c) in ((3880, 250, 74, YEL), (3740, 130, 36, PAPER), (300, 330, 52, PAPER),
                            (1900, 1300, 30, PAPER)):
        sp = sparkle(sx, sy, sr, 0.14)
        cv.paint(cv.dilate(cv.mask(sp), 8), INK)
        cv.paint(cv.mask(sp), c)

    if out_path:
        cv.save(out_path)
    return cv


def night_bg(w, h):
    """Night-Tokyo-ish backdrop for previews: indigo sky, magenta haze, skyline with windows."""
    cv = FCanvas(w, h, ss=1)
    cv.paint(np.ones((cv.H, cv.W), f32), cv.vgrad(0, h, [(0, C("#07061A")), (0.55, C("#1B1340")),
                                                          (0.85, C("#5A1A5E")), (1, C("#FF2D7A"))]))
    r = rng("skyline")
    x = 0
    sky = skia.Path(); win = skia.Path()
    while x < w:
        bw = r.uniform(40, 140); bh = r.uniform(h * 0.12, h * 0.45)
        sky.addRect(skia.Rect.MakeLTRB(x, h - bh, x + bw, h))
        for yy in np.arange(h - bh + 10, h - 6, 14):
            for xx in np.arange(x + 6, x + bw - 8, 12):
                if r.random() < 0.35:
                    win.addRect(skia.Rect.MakeLTRB(xx, yy, xx + 5, yy + 6))
        x += bw + r.uniform(-6, 10)
    cv.paint(cv.mask(sky), C("#0B0B12"))
    cv.paint(cv.mask(win), C("#FFE6A8"), 0.8)
    return cv.image().convert("RGB")


def previews(logo_path):
    logo = Image.open(logo_path).convert("RGBA")
    pw, ph = 2048, 768
    small = logo.resize((pw, ph), Image.LANCZOS)
    top = night_bg(pw, ph).convert("RGBA")
    top.alpha_composite(small)
    paper = Image.open(os.path.join(OUT, "paper_grain.png")).convert("RGBA") if os.path.exists(
        os.path.join(OUT, "paper_grain.png")) else Image.new("RGBA", (1024, 1024), (255, 248, 231, 255))
    bot = tile_preview(paper, 2, 1, 99999).resize((pw, ph)).convert("RGBA")
    bot.alpha_composite(small)
    sheet = Image.new("RGB", (pw, ph * 2 + 12), (0, 0, 0))
    sheet.paste(top.convert("RGB"), (0, 0))
    sheet.paste(bot.convert("RGB"), (0, ph + 12))
    sheet.save(os.path.join(inklib.PREVIEWS, "logo_on_bg.png"))


def make_mono(src_path, dst_path):
    """Single-colour white overlay version: bright parts -> white, ink -> transparent,
    extrusion -> partial alpha (fades with depth)."""
    a = np.asarray(Image.open(src_path).convert("RGBA")).astype(np.float32) / 255.0
    v = a[..., :3].max(-1)
    k = smoothstep(0.30, 0.85, v)
    out = np.zeros_like(a)
    out[..., :3] = 1.0
    out[..., 3] = a[..., 3] * k
    save_image(out, dst_path)


def main(argv):
    preview = "--preview" in argv
    SP = os.environ.get("LOGO_PREVIEW_DIR", inklib.PREVIEWS)
    if preview:
        img = render(0.5).image()
        img.save(os.path.join(SP, "logo_preview.png"))
        a = np.asarray(img)[..., 3]
        ys, xs = np.nonzero(a > 0)
        print("bbox (design px)", xs.min() * 2, ys.min() * 2, xs.max() * 2, ys.max() * 2)
        return
    p = os.path.join(OUT, "logo_inkdrift.png")
    if "--post" not in argv:
        render(2.0, p)
    make_mono(p, os.path.join(OUT, "logo_inkdrift_mono.png"))
    previews(p)


if __name__ == "__main__":
    main(sys.argv[1:])
