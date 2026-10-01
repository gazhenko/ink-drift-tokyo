"""gen_ui.py — UI textures for INK DRIFT: TOKYO (everything in Art/UI except the logo).

Usage:
    python gen_ui.py            # render everything + contact sheet
    python gen_ui.py rank_S     # render a single item (name prefix match)
    python gen_ui.py --sheet    # only rebuild the contact sheet

Deterministic: all randomness from seeded generators.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uilib import *  # noqa: E402,F403
import inklib  # noqa: E402

UI = os.path.join(inklib.ART, "UI")
os.makedirs(UI, exist_ok=True)
ITEMS = {}


def item(name):
    def deco(fn):
        ITEMS[name] = fn
        return fn
    return deco


def P(name):
    return os.path.join(UI, name)


INK, PAPER = C("ink"), C("paper")
MAG, CYAN, YEL, RED, IND, LIME, SAK = C("magenta"), C("cyan"), C("yellow"), C("red"), C("indigo"), C("lime"), C("sakura")


# ======================================================================================
# Tileables
# ======================================================================================
@item("halftone_tile")
def halftone_tile():
    # 45deg dot screen; horizontal repeat of the rotated lattice = 16 px -> 16 cells / tile
    cv = FCanvas(256, 256, ss=4)
    per = 16 / math.sqrt(2)
    m = cv.halftone(0.38, per, 45, offset=(0.0, 0.0))
    g = 1 - m
    out = cv2.resize(g, (256, 256), interpolation=cv2.INTER_AREA)
    save_l(out, P("halftone_tile.png"))
    # extra: gradient strip (dot size ramps 0 -> merged), tileable horizontally
    cv = FCanvas(1024, 256, ss=4)
    ramp = cv.ramp((0, 0), (1024, 0))
    m = cv.halftone(ramp ** 1.1 * 0.95, per, 45)
    out = cv2.resize(1 - m, (1024, 256), interpolation=cv2.INTER_AREA)
    save_l(out, P("halftone_gradient.png"))


@item("screentone_lines")
def screentone_lines():
    cv = FCanvas(256, 256, ss=4)
    d = 8 / math.sqrt(2)  # perpendicular spacing so the horizontal repeat is exactly 8 px
    m = cv.halftone(0.42, d, 45, shape="line")
    out = cv2.resize(1 - m, (256, 256), interpolation=cv2.INTER_AREA)
    save_l(out, P("screentone_lines.png"))
    # extra: cross-hatch variant
    m2 = cv.halftone(0.30, d, -45, shape="line")
    out2 = cv2.resize(1 - np.maximum(m * 0.0 + cv.halftone(0.30, d, 45, shape="line"), m2), (256, 256),
                      interpolation=cv2.INTER_AREA)
    save_l(out2, P("screentone_crosshatch.png"))


@item("speedlines_radial")
def speedlines_radial():
    S = 2048
    cv = FCanvas(S, S, ss=2)
    r = rng("speedlines")
    cx = cy = S / 2
    path = skia.Path()
    # stratified angles so there are no big gaps, irregular widths + inner radii
    n = 300
    for i in range(n):
        a = 2 * math.pi * (i + r.uniform(0.0, 1.0)) / n
        k = r.random()
        rin = S * (0.25 + 0.17 * r.random() ** 0.7)
        if k < 0.12:
            rin *= 0.82  # a few long stabbing lines
        w = 4 + 34 * r.random() ** 2.2
        if k > 0.93:
            w *= 2.0  # occasional fat wedge
        path.addPath(wedge(cx, cy, a, rin, S * 0.75, 0.0, w))
    # very thin hairlines between
    for i in range(220):
        a = r.uniform(0, 2 * math.pi)
        rin = S * (0.30 + 0.15 * r.random())
        path.addPath(wedge(cx, cy, a, rin, S * 0.75, 0.0, 1.5 + 2.5 * r.random()))
    m = cv.mask(path)
    # soften the very tips into the clear centre (radius normalised to the half-size)
    rr = cv.radial(cx, cy, S / 2)
    fade = smoothstep(0.42, 0.62, rr)
    cv.paint(m * fade, C("white"))
    cv.save(P("speedlines_radial.png"))


@item("paper_grain")
def paper_grain():
    S = 1024
    r = rng("paper")
    # tileable multi-scale noise (spectral -> periodic)
    mott = noise(S, S, 140, seed=11, beta=2.2)
    mid = noise(S, S, 18, seed=12, beta=1.6)
    fine = noise(S, S, 1.5, seed=13, beta=0.6)
    tone = 0.5 * (mott - 0.5) * 0.10 + (mid - 0.5) * 0.05 + (fine - 0.5) * 0.09
    # fibres: short curved strands drawn with wrap-around copies
    dark = skia.Path()
    light = skia.Path()
    for i in range(2600):
        x, y = r.uniform(0, S), r.uniform(0, S)
        L = 6 + 46 * r.random() ** 2
        a = r.uniform(0, math.pi)
        bend = r.uniform(-0.6, 0.6)
        pts = []
        for t in np.linspace(0, 1, 5):
            aa = a + bend * (t - 0.5)
            pts.append((x + math.cos(aa) * L * (t - 0.5), y + math.sin(aa) * L * (t - 0.5)))
        q = smooth_open(pts)
        (dark if r.random() < 0.55 else light).addPath(q)
    ss = 2
    md = raster(wrap_copies(dark, S, S), S * ss, S * ss, scale=ss, stroke=0.9, fill=False)
    ml = raster(wrap_copies(light, S, S), S * ss, S * ss, scale=ss, stroke=1.3, fill=False)
    md = cv2.resize(md, (S, S), interpolation=cv2.INTER_AREA)
    ml = cv2.resize(ml, (S, S), interpolation=cv2.INTER_AREA)
    tone = tone - md * 0.06 + ml * 0.035
    base = np.asarray(PAPER, f32)
    shade_col = np.array([0.80, 0.74, 0.62], f32)  # warm fibre brown
    t = np.clip(-tone * 6, 0, 1)[..., None]
    rgb = base * (1 + np.clip(tone, -1, 1)[..., None] * 0.9)
    rgb = rgb * (1 - t * 0.25) + shade_col * t * 0.25
    save_image(np.clip(rgb, 0, 1), P("paper_grain.png"), "RGB")
    # neutral grayscale overlay version (0.5 = no change) for multiply/overlay use
    g = np.clip(0.5 + tone * 2.2, 0, 1)
    save_l(g, P("paper_grain_overlay.png"))


# ======================================================================================
# Frames
# ======================================================================================
@item("panel_frame")
def panel_frame():
    """512x512 9-slice comic panel. Slice borders: 80 px all sides (L=T=R=B=80)."""
    S = 512
    cv = FCanvas(S, S, ss=2)
    sh = 14           # drop shadow offset
    o = 8             # outer margin
    x0, y0, x1, y1 = o, o, S - o - sh, S - o - sh
    outer = rect(x0, y0, x1, y1)
    m_out = cv.mask(outer)
    bw = 34           # total border thickness (paper rim + ink)
    inner = rect(x0 + bw, y0 + bw, x1 - bw, y1 - bw)
    m_in = cv.mask(inner)
    # ink drop shadow (solid, offset down-right), window punched out
    cv.paint(cv.shift(m_out, sh, sh) * (1 - m_out), INK, 0.9)
    # paper rim then the heavy ink border
    cv.paint(m_out * (1 - m_in), PAPER)
    k0 = cv.mask(rect(x0 + 5, y0 + 5, x1 - 5, y1 - 5))
    cv.paint(k0 * (1 - m_in), INK)
    # inner paper gap + ink hairline (double-ruled panel look)
    g0 = cv.mask(rect(x0 + bw - 9, y0 + bw - 9, x1 - bw + 9, y1 - bw + 9))
    g1 = cv.mask(rect(x0 + bw - 5, y0 + bw - 5, x1 - bw + 5, y1 - bw + 5))
    cv.paint(g0 * (1 - g1), PAPER)
    # corner accents (confined to the 80 px corner slices, clipped to the frame)
    tl = poly([(x0 + 5, y0 + 5), (x0 + 70, y0 + 5), (x0 + 5, y0 + 70)])
    br = poly([(x1 - 5, y1 - 5), (x1 - 70, y1 - 5), (x1 - 5, y1 - 70)])
    for p, col in ((tl, MAG), (br, CYAN)):
        mp = cv.mask(p) * k0
        cv.paint(mp, col)
        cv.paint(cv.mask(p, stroke=4, fill=False, join="miter") * k0, INK)
    cv.save(P("panel_frame.png"))


def _button(hover: bool):
    W, H = 640, 192
    cv = FCanvas(W, H, ss=2)
    sl = 34                  # slant
    x0, x1, y0, y1 = 26, W - 64 - sl, 42, H - 34
    shape = para(x0, y0, x1, y1, sl)
    sh_off = (12, 10) if hover else (9, 8)
    shadow = para(x0 + sh_off[0], y0 + sh_off[1], x1 + sh_off[0], y1 + sh_off[1], sl)
    m = cv.mask(shape)
    if hover:
        # cyan offset slab + ink shadow (two-tone offset, Persona style)
        cv.paint(cv.mask(shadow), INK)
        slab = para(x0 - 16, y0 - 10, x1 - 16, y1 - 10, sl)
        cv.paint(cv.dilate(cv.mask(slab), 5), INK)
        cv.paint(cv.mask(slab), CYAN)
        cv.paint(cv.dilate(m, 6), INK)
        fill = cv.vgrad(y0, y1, [(0, lighten(MAG, 0.15)), (0.55, MAG), (1, darken(MAG, 0.25))])
        cv.paint(m, fill)
        # halftone shading at the bottom
        # horizontal line-tone (x-invariant, so the 9-slice centre can stretch without distortion)
        tone = cv.halftone(cv.ramp((0, y0 + (y1 - y0) * 0.40), (0, y1)) * 0.7, 6, 0, shape="line")
        cv.paint(m * tone, darken(MAG, 0.55), 0.75)
        # paper inner keyline
        inner = para(x0 + 9, y0 + 8, x1 - 9, y1 - 8, sl)
        cv.paint(cv.mask(inner, stroke=3.5, fill=False, join="miter"), PAPER)
        # spark accent at top-right cap
        sp = sparkle(x1 + sl - 6, y0 + 4, 30, 0.14)
        cv.paint(cv.dilate(cv.mask(sp), 5), INK)
        cv.paint(cv.mask(sp), YEL)
        sp2 = sparkle(x1 + sl - 44, y0 - 10, 13, 0.14)
        cv.paint(cv.dilate(cv.mask(sp2), 3.5), INK)
        cv.paint(cv.mask(sp2), PAPER)
        # left cap: paper slash stripes
        for i, dx in enumerate((22, 46)):
            s = para(x0 + dx, y0 + 8, x0 + dx + 12, y1 - 8, sl * (y1 - y0 - 16) / (y1 - y0))
            cv.paint(cv.mask(s), PAPER if i == 0 else INK)
    else:
        cv.paint(cv.mask(shadow), MAG)
        cv.paint(cv.dilate(m, 6), PAPER)
        cv.paint(cv.dilate(m, 2), INK)
        fill = cv.vgrad(y0, y1, [(0, lighten(INK, 0.10)), (1, INK)])
        cv.paint(m, fill)
        tone = cv.halftone(cv.ramp((0, y1), (0, y0)) * 0.45, 6, 0, shape="line")
        cv.paint(m * tone, IND, 0.9)
        # left cap accent slashes
        for i, (dx, col) in enumerate(((20, MAG), (40, CYAN))):
            s = para(x0 + dx, y0 + 10, x0 + dx + 10, y1 - 10, sl * (y1 - y0 - 20) / (y1 - y0))
            cv.paint(cv.mask(s), col)
    cv.save(P("button_frame_hover.png" if hover else "button_frame.png"))


@item("button_frame")
def button_frame():
    """640x192, horizontal 3-slice: L=136, R=136, T=B=0 (stretch width only)."""
    _button(False)
    _button(True)


# ======================================================================================
# Rank badges
# ======================================================================================
RANKS = {
    "S": dict(col=YEL, col2=lighten(YEL, 0.55), burst=MAG, burst2=CYAN, seed=11),
    "A": dict(col=MAG, col2=lighten(MAG, 0.45), burst=CYAN, burst2=YEL, seed=12),
    "B": dict(col=CYAN, col2=lighten(CYAN, 0.55), burst=MAG, burst2=YEL, seed=13),
    "C": dict(col=LIME, col2=lighten(LIME, 0.5), burst=IND, burst2=MAG, seed=14),
    "D": dict(col=np.array([0.62, 0.60, 0.72], f32), col2=np.array([0.86, 0.85, 0.92], f32),
              burst=IND, burst2=np.array([0.42, 0.40, 0.52], f32), seed=15),
}


def _rank(letter):
    spec = RANKS[letter]
    S = 512
    cv = FCanvas(S, S, ss=2)
    r = rng(spec["seed"])
    cx, cy = 256, 238
    if letter == "S":
        # radiating action lines behind (paper/yellow)
        lines = action_lines(cx, cy, 165, 226, 40, 22, r, len_jitter=0.2)
        cv.paint(cv.dilate(cv.mask(lines), 3), INK)
        cv.paint(cv.mask(lines), YEL)
    if letter == "D":
        base = jagged_ellipse(cx, cy, 182, 182, teeth=26, depth=0.035, r=r, jitter=0.4)
    else:
        n = {"S": 22, "A": 18, "B": 16, "C": 14}[letter]
        base = starburst(cx, cy, 210, 210, n=n, inner=0.80, jitter=0.22, r=r, rot=r.uniform(0, 1),
                         curve=0.18 if letter in "SA" else 0.0)
    mb = cv.mask(base)
    # offset ink drop
    cv.paint(cv.shift(cv.dilate(mb, 8), 10, 12), INK)
    cv.paint(cv.dilate(mb, 8), INK)
    cv.paint(mb, spec["burst"])
    # halftone ring of the second colour
    ring = cv.radial(cx, cy, 210)
    dots = cv.halftone(smoothstep(0.35, 1.0, ring) * 0.55, 11, 45)
    cv.paint(mb * dots, spec["burst2"], 0.9)
    # inner disc (stamp)
    disc = circle(cx, cy, 138)
    md = cv.mask(disc)
    cv.paint(cv.dilate(md, 9), INK)
    cv.paint(cv.dilate(md, 4), PAPER)
    cv.paint(md, INK)
    cv.paint(md * cv.halftone(cv.ramp((cx, cy - 138), (cx, cy + 138)) * 0.35, 9, 45), IND, 1.0)
    # big letter
    tp = text_path(letter, "dela", 300)
    tp = fit_path(tp, (cx - 105, cy - 120, cx + 105, cy + 112))
    tp = transformed(tp, rotate=-6, skew_x=-0.14)
    F = cv.mask(tp)
    l, t, rr, b = bounds(tp)
    comic_text(cv, F, [(0, spec["col2"]), (0.45, spec["col"]), (1, spec["d1"])],
               paper_w=7, ink_w=9, ext=(9, 11), ext_near=spec["d2"],
               ext_far=spec["d3"], ht_color=spec["d2"], ht_period=8,
               ht_amt=0.5, grad_box=(t, b),
               shine=(l - 20, t + (b - t) * 0.30, rr + 20, t + (b - t) * 0.08, (b - t) * 0.09))
    # RANK ribbon
    rb = ribbon(cx, 420, 250, 56, angle=-4, tail=0.14, notch=0.5, fold=0.06)
    for k in ("tails", "folds", "band"):
        mk = cv.mask(rb[k])
        if k == "tails":
            cv.paint(cv.dilate(mk, 5), INK)
            cv.paint(mk, darken(spec["burst"], 0.4) if letter != "D" else darken(IND, 0.3))
        elif k == "folds":
            cv.paint(mk, INK)
        else:
            cv.paint(cv.dilate(mk, 5), INK)
            cv.paint(mk, INK if letter != "S" else MAG)
    rt = text_path("RANK", "bangers", 60, tracking=0.08)
    rt = fit_path(rt, (cx - 70, 400, cx + 70, 440))
    rt = transformed(rt, rotate=-4)
    mt = cv.mask(rt)
    cv.paint(mt, PAPER if letter != "S" else YEL)
    if letter == "S":
        cr = crown(cx, 62, 116, 66)
        cr = transformed(cr, rotate=-6)
        mc = cv.mask(cr)
        cv.paint(cv.shift(cv.dilate(mc, 7), 5, 6), INK)
        cv.paint(cv.dilate(mc, 7), INK)
        cv.paint(mc, cv.vgrad(30, 96, [(0, lighten(YEL, 0.5)), (0.6, YEL), (1, C("#FFB000"))]))
        for (sx, sy) in ((cx - 32, 46), (cx, 40), (cx + 32, 34)):
            pass
        gem = circle(cx, 76, 9)
        cv.paint(cv.dilate(cv.mask(gem), 3), INK)
        cv.paint(cv.mask(gem), MAG)
        for (sx, sy, sr, col) in ((70, 120, 34, PAPER), (446, 96, 26, YEL), (438, 330, 30, PAPER),
                                  (78, 352, 22, YEL), (404, 40, 14, PAPER)):
            sp = sparkle(sx, sy, sr, 0.13)
            ms = cv.mask(sp)
            cv.paint(cv.dilate(ms, 4), INK)
            cv.paint(ms, col)
    if letter == "D":
        # sweat drop
        drop = skia.Path()
        drop.moveTo(380, 120)
        drop.cubicTo(400, 150, 412, 170, 400, 186)
        drop.cubicTo(388, 200, 360, 196, 360, 176)
        drop.cubicTo(360, 160, 372, 140, 380, 120)
        drop.close()
        m = cv.mask(drop)
        cv.paint(cv.dilate(m, 5), INK)
        cv.paint(m, C("#9FE8FF"))
        cv.paint(cv.mask(ellipse(377, 172, 5, 9)), PAPER)
    cv.save(P(f"rank_{letter}.png"))


for _k, _s in RANKS.items():
    _c = _s["col"]
    if _k == "S":  # yellow must deepen toward orange/red, never olive
        _s.update(d1=C("#FFB000"), d2=C("#F06A00"), d3=C("#8A1C3C"))
    else:
        _s.update(d1=darken(_c, 0.25), d2=darken(_c, 0.55), d3=darken(_c, 0.85))

for _L in "SABCD":
    ITEMS[f"rank_{_L}"] = (lambda L: (lambda: _rank(L)))(_L)


# ======================================================================================
# Splats (white, tintable)
# ======================================================================================
def _splat(idx):
    S = 1024
    cv = FCanvas(S, S, ss=2)
    r = rng(f"splat{idx}")
    W = C("white")
    if idx == 1:  # round splat with arms + droplets
        m = np.zeros((cv.H, cv.W), f32)
        for p in organic_splat(512, 470, 330, r, arms=22, blob=0.55, wob=0.25):
            np.maximum(m, cv.mask(p), out=m)
        cv.paint(m, W)
        cv.paint(cv.mask(flecks(512, 470, 300, 110, (1.5, 8), r, sigma=0.5, elong=0.4)), W)
        drips_clean(cv, m, [440, 520, 600], [24, 30, 20], [150, 230, 110], W, r, overlap=16)
    elif idx == 2:  # directional splash (thrown paint, travelling right)
        m = np.zeros((cv.H, cv.W), f32)
        # impact blob, squashed along travel direction
        for p in organic_splat(330, 520, 260, r, arms=10, blob=0.62, wob=0.2, arm_len=(0.1, 0.35)):
            q = skia.Path(p)
            q.transform(skia.Matrix.Scale(1.25, 0.8))
            q.offset(-330 * 0.25, 520 * 0.2)
            np.maximum(m, cv.mask(q), out=m)
        # forward streaks: tapered, ending in elongated drops
        for i in range(24):
            ang = r.normal(0, 0.22)
            y0 = 520 + r.uniform(-90, 90)
            x0 = 380
            L = r.uniform(180, 520) * (1 - abs(ang))
            w0 = r.uniform(14, 44)
            left, right = [], []
            for j in range(13):
                t = j / 12
                x = x0 + math.cos(ang) * L * t
                y = y0 + math.sin(ang) * L * t
                w = w0 * ((1 - t) ** 1.4 * 0.9 + 0.18)
                left.append((x - math.sin(ang) * w / 2, y + math.cos(ang) * w / 2))
                right.append((x + math.sin(ang) * w / 2, y - math.cos(ang) * w / 2))
            np.maximum(m, cv.mask(poly(left + right[::-1])), out=m)
            ex, ey = x0 + math.cos(ang) * L, y0 + math.sin(ang) * L
            br = w0 * r.uniform(0.3, 0.45)
            d = ellipse(0, 0, br * 2.2, br)
            d.transform(skia.Matrix.RotateRad(ang))
            d.offset(ex + br, ey)
            np.maximum(m, cv.mask(d), out=m)
        # flying droplets ahead (elongated along travel)
        fp = skia.Path()
        for i in range(120):
            ang = r.normal(0, 0.3)
            dist = r.uniform(420, 600)
            s = 2 + 10 * r.random() ** 3
            q = ellipse(0, 0, s * r.uniform(1.6, 3.2), s * 0.65)
            q.transform(skia.Matrix.RotateRad(ang))
            x = 380 + math.cos(ang) * dist * r.uniform(0.75, 1.0)
            y = 520 + math.sin(ang) * dist
            if x < 980 and 60 < y < 960:
                q.offset(x, y)
                fp.addPath(q)
        np.maximum(m, cv.mask(fp), out=m)
        cv.paint(m, W)
    elif idx == 3:  # drip-heavy graffiti blob
        pts = []
        for i in range(30):
            a = 2 * math.pi * i / 30
            k = 1 + 0.18 * math.sin(a * 3 + 2) + r.uniform(-0.08, 0.08)
            pts.append((512 + math.cos(a) * 330 * k, 330 + math.sin(a) * 210 * k))
        m = cv.mask(smooth_closed(pts, 0.9))
        cv.paint(m, W)
        xs = np.linspace(230, 800, 11) + r.uniform(-20, 20, 11)
        drips_clean(cv, m, list(xs), [r.uniform(16, 34) for _ in xs], [r.uniform(80, 520) for _ in xs], W, r,
                    overlap=14)
        cv.paint(cv.mask(flecks(512, 330, 360, 90, (2, 9), r, sigma=0.45)), W)
    else:  # dry brush swipe (bristle simulation)
        spine = [(110, 650), (300, 540), (520, 470), (760, 420), (930, 360)]
        m = brush_mask(cv, spine, 210, r, bristles=110, press=0.08, taper=0.4, dry=0.75, dry_start=0.25)
        cv.paint(m, W)
        cv.paint(cv.mask(flecks(905, 375, 110, 60, (1.5, 6), r, sigma=0.6, elong=0.6)), W)
        cv.paint(cv.mask(flecks(140, 640, 120, 40, (1.5, 7), r, sigma=0.5, elong=0.3)), W)
    cv.save(P(f"splat_{idx}.png"))


for _i in range(1, 5):
    ITEMS[f"splat_{_i}"] = (lambda i: (lambda: _splat(i)))(_i)


# ======================================================================================
# Arrows
# ======================================================================================
def _arrow_canvas(path, fname, fill_col=MAG, shadow=(7, 8)):
    S = 256
    cv = FCanvas(S, S, ss=2)
    m = cv.mask(path)
    K = cv.dilate(cv.dilate(m, 7), 7)
    cv.paint(cv.shift(K, *shadow), INK)
    cv.paint(K, INK)
    cv.paint(cv.dilate(m, 7), PAPER)
    l, t, r_, b = bounds(path)
    cv.paint(m, cv.vgrad(t, b, [(0, lighten(fill_col, 0.4)), (0.5, fill_col), (1, darken(fill_col, 0.3))]))
    dots = cv.halftone(cv.ramp((0, t + (b - t) * 0.4), (0, b)) * 0.5, 7, 45)
    cv.paint(m * dots, darken(fill_col, 0.5), 0.8)
    # shine streak
    band = poly([(l, t + (b - t) * 0.30), (r_, t + (b - t) * 0.12), (r_, t + (b - t) * 0.22), (l, t + (b - t) * 0.40)])
    cv.paint(m * cv.mask(band), PAPER, 0.55)
    cv.save(P(fname))


def _arrow_shape():
    # chunky right-pointing arrow, sheared forward
    pts = [(40, 104), (128, 104), (128, 52), (214, 128), (128, 204), (128, 152), (40, 152)]
    return transformed(poly(pts), skew_x=-0.18)


@item("arrows")
def arrows():
    base = _arrow_shape()
    for name, rot in (("right", 0), ("down", 90), ("left", 180), ("up", -90)):
        p = transformed(base, rotate=rot, pivot=(128, 128))
        p = fit_path(p, (34, 34, 222, 222))
        sh = {"right": (7, 8), "left": (7, 8), "up": (7, 8), "down": (7, 8)}[name]
        _arrow_canvas(p, f"arrow_{name}.png", MAG, sh)
    # double chevrons
    ch = skia.Path()
    for dx in (0, 62):
        ch.addPath(poly([(48 + dx, 52), (96 + dx, 52), (158 + dx, 128), (96 + dx, 204), (48 + dx, 204), (110 + dx, 128)]))
    ch = transformed(ch, skew_x=-0.12)
    for name, rot in (("right", 0), ("left", 180)):
        p = transformed(ch, rotate=rot, pivot=(128, 128))
        p = fit_path(p, (30, 40, 226, 216))
        _arrow_canvas(p, f"arrow_chevron_{name}.png", CYAN)


# ======================================================================================
# Card frames
# ======================================================================================
def _halftone_corner(cv, cx, cy, rad, col, period=10, opacity=1.0, clip=None):
    ramp = 1 - cv.radial(cx, cy, rad)
    dots = cv.halftone(ramp ** 1.3 * 0.75, period, 45)
    if clip is not None:
        dots = dots * clip
    cv.paint(dots, col, opacity)


def _card(kind):
    """kind = 'car' | 'track'. 1024x768 card frame with transparent render window."""
    W, H = 1024, 768
    cv = FCanvas(W, H, ss=2)
    r = rng("card_" + kind)
    acc, acc2 = (MAG, CYAN) if kind == "car" else (CYAN, MAG)
    cut = 70
    o = 26
    x0, y0, x1, y1 = o, o, W - o - 16, H - o - 18
    outline = poly([(x0 + cut, y0), (x1, y0), (x1, y1 - cut), (x1 - cut, y1), (x0, y1), (x0, y0 + cut)])
    mo = cv.mask(outline)
    # offset shadow + accent slab
    cv.paint(cv.shift(cv.dilate(mo, 6), 16, 18), INK)
    slab = cv.shift(mo, -12, -12)
    cv.paint(cv.dilate(slab, 6), INK)
    cv.paint(slab, acc)
    cv.paint(cv.dilate(mo, 6), INK)
    # card body: paper with halftone corner accents
    cv.paint(mo, PAPER)
    _halftone_corner(cv, x0, y0, 330, acc, 12, 0.95, clip=mo)
    _halftone_corner(cv, x1, y1, 300, acc2, 12, 0.95, clip=mo)
    # diagonal speed slashes on the paper
    for i in range(5 if kind == "car" else 0):
        xx = x1 - 260 + i * 34
        s = para(xx, y0 + 18, xx + 12, y0 + 70, 18)
        cv.paint(cv.mask(s), INK)
    if kind == "car":
        win = (x0 + 34, y0 + 92, x1 - 34, y1 - 170)
        wcut = 44
        wpath = poly([(win[0] + wcut, win[1]), (win[2], win[1]), (win[2], win[3] - wcut), (win[2] - wcut, win[3]),
                      (win[0], win[3]), (win[0], win[1] + wcut)])
        # nameplate strip (ink, slanted) bottom
        npl = para(x0 + 26, y1 - 140, x1 - 120, y1 - 40, 30)
        mn = cv.mask(npl)
        cv.paint(cv.shift(mn, 8, 8), acc)
        cv.paint(cv.dilate(mn, 5), PAPER)
        cv.paint(cv.dilate(mn, 1), INK)
        cv.paint(mn, cv.vgrad(y1 - 140, y1 - 40, [(0, lighten(INK, 0.12)), (1, INK)]))
        cv.paint(mn * cv.halftone(cv.ramp((x0, 0), (x1, 0)) * 0.30, 8, 45), IND)
        # number tab top-left in the cut corner region
        tab = para(x0 + cut + 10, y0 + 18, x0 + cut + 170, y0 + 74, 16)
        mt = cv.mask(tab)
        cv.paint(cv.dilate(mt, 5), INK)
        cv.paint(mt, acc)
        # little "CAR" label
        lab = fit_path(text_path("MACHINE", "bangers", 60, tracking=0.06), (x0 + cut + 32, y0 + 28, x0 + cut + 160, y0 + 66))
        cv.paint(cv.mask(lab), PAPER)
        # stat tick strip on right of nameplate
        for i in range(6):
            s = para(x1 - 104 + i * 14, y1 - 132, x1 - 98 + i * 14, y1 - 48, 12)
            cv.paint(cv.mask(s), INK if i % 2 == 0 else acc)
    else:
        win = (x0 + 150, y0 + 40, x1 - 36, y1 - 150)
        wcut = 40
        wpath = poly([(win[0], win[1]), (win[2] - wcut, win[1]), (win[2], win[1] + wcut), (win[2], win[3]),
                      (win[0] + wcut, win[3]), (win[0], win[3] - wcut)])
        # vertical JP strip (tategaki name area) on the left
        vs = poly([(x0 + 30, y0 + cut + 10), (x0 + 120, y0 + cut - 14), (x0 + 120, y1 - 30), (x0 + 30, y1 - 30)])
        mv = cv.mask(vs)
        cv.paint(cv.shift(mv, 8, 8), acc2)
        cv.paint(cv.dilate(mv, 5), PAPER)
        cv.paint(cv.dilate(mv, 1), INK)
        cv.paint(mv, INK)
        cv.paint(mv * cv.halftone(cv.ramp((0, y1), (0, y0)) * 0.3, 8, 45), IND)
        # bottom nameplate
        npl = para(x0 + 150, y1 - 124, x1 - 36, y1 - 36, 26)
        mn = cv.mask(npl)
        cv.paint(cv.shift(mn, 8, 8), acc)
        cv.paint(cv.dilate(mn, 5), PAPER)
        cv.paint(cv.dilate(mn, 1), INK)
        cv.paint(mn, cv.vgrad(y1 - 124, y1 - 36, [(0, lighten(INK, 0.12)), (1, INK)]))
        # map-pin / flag icon in the top-left corner
        pin = skia.Path()
        pin.addCircle(x0 + 76, y0 + 116, 22)
        pin.addPath(poly([(x0 + 56, y0 + 124), (x0 + 96, y0 + 124), (x0 + 76, y0 + 160)]))
        mp = cv.mask(pin)
        cv.paint(cv.dilate(mp, 5), INK)
        cv.paint(mp, YEL)
        cv.paint(cv.mask(circle(x0 + 76, y0 + 116, 8)), PAPER)
    mw = cv.mask(wpath)
    # window: ink frame, then punch out
    cv.paint(cv.dilate(mw, 12), INK)
    cv.paint(cv.dilate(mw, 6) * (1 - cv.erode(cv.dilate(mw, 6), 3)), acc)
    cv.erase(mw)
    # hand-inked flecks on the frame
    cv.save(P(f"card_{kind}_frame.png"))
    return win


@item("cards")
def cards():
    w1 = _card("car")
    w2 = _card("track")
    print("car window", w1, "track window", w2)


# ======================================================================================
# extras
# ======================================================================================
@item("tag_new")
def tag_new():
    S = 512
    cv = FCanvas(S, S, ss=2)
    r = rng("tagnew")
    b = starburst(250, 256, 196, 160, n=16, inner=0.74, jitter=0.22, r=r, curve=0.2)
    mb = cv.mask(b)
    cv.paint(cv.shift(cv.dilate(mb, 8), 10, 10), INK)
    cv.paint(cv.dilate(mb, 8), INK)
    cv.paint(mb, YEL)
    cv.paint(mb * cv.halftone(cv.radial(256, 256, 220) * 0.5, 10, 45), MAG, 0.8)
    t = fit_path(text_path("NEW!", "bangers", 200), (120, 180, 400, 320))
    t = transformed(t, rotate=-8)
    F = cv.mask(t)
    l, tt, rr, bb = bounds(t)
    comic_text(cv, F, [(0, lighten(MAG, 0.4)), (1, MAG)], 6, 8, ext=(6, 8), ext_near=darken(MAG, 0.5),
               ext_far=darken(MAG, 0.8), grad_box=(tt, bb))
    cv.save(P("tag_new.png"))


# ======================================================================================
def sheet():
    names = ["halftone_tile.png", "halftone_gradient.png", "screentone_lines.png", "screentone_crosshatch.png",
             "speedlines_radial.png", "paper_grain.png", "paper_grain_overlay.png", "panel_frame.png",
             "button_frame.png", "button_frame_hover.png", "rank_S.png", "rank_A.png", "rank_B.png",
             "rank_C.png", "rank_D.png", "splat_1.png", "splat_2.png", "splat_3.png", "splat_4.png",
             "arrow_left.png", "arrow_right.png", "arrow_up.png", "arrow_down.png", "arrow_chevron_left.png",
             "arrow_chevron_right.png", "card_car_frame.png", "card_track_frame.png", "tag_new.png",
             "logo_inkdrift.png", "logo_inkdrift_mono.png"]
    paths = [P(n) for n in names if os.path.exists(P(n))]
    contact_sheet(paths, os.path.join(inklib.PREVIEWS, "ui.png"), cell=(300, 220), cols=6, bg="checker",
                  title="INK DRIFT: TOKYO — UI")


def main(argv):
    if "--sheet" in argv:
        sheet(); return
    sel = [a for a in argv if not a.startswith("-")]
    for name, fn in ITEMS.items():
        if sel and not any(name.startswith(s) for s in sel):
            continue
        print("render", name, flush=True)
        fn()
    sheet()


if __name__ == "__main__":
    main(sys.argv[1:])
