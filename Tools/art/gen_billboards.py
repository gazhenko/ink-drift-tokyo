"""Rooftop billboards for INK DRIFT: TOKYO — 2048x1024, fictional brands, manga-poster style.

Usage:
  python gen_billboards.py                 # all + contact sheet
  python gen_billboards.py bb_voltz_energy # selected

Outputs: Art/Signs/bb_<name>_albedo.png (printed vinyl by day) and bb_<name>_emission.png
(poster lit by floodlights from the top edge + neon/LED accents at full strength).
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signlib import *  # noqa
from signlib import col, WHITE, _h

REG = {}


def bb(fn):
    REG[fn.__name__] = fn
    return fn


INK = C("ink"); PAPER = C("paper"); MAG = C("magenta"); CYAN = C("cyan"); YEL = C("yellow")
RED = C("red"); IND = C("indigo"); SAK = C("sakura"); LIME = C("lime")
W_, H_ = 2048, 1024


def B(name):
    s = Sign(name, W_, H_, bg=PAPER)
    s.accents = []  # (mask, colour, k) emitted at full strength
    return s


# --------------------------------------------------------------------------------------
# comic poster toolkit
# --------------------------------------------------------------------------------------
def comic_text(s, path, fill, y0=None, y1=None, paper=10.0, ink=9.0, ext=(10, 12), ext_col=None,
               ht=0.35, ht_col=None, shine=True, ink_col=INK, paper_col=PAPER):
    """Callout-style lettering: extrusion -> ink -> paper -> gradient fill (+halftone & shine)."""
    F = s.m(path)
    l, t, r_, b = bounds(path)
    y0 = t if y0 is None else y0
    y1 = b if y1 is None else y1
    P = s.A.dilate(F, paper) if paper else F
    K = s.A.dilate(P, ink) if ink else P
    if ext:
        E = s.A.extrude(K, ext[0], ext[1])
        s.A.paint(s.A.dilate(E, 2), ink_col)
        ec = ext_col if ext_col is not None else darken(fill if np.ndim(fill) == 1 else np.asarray(fill[-1][1]), 0.55)
        s.A.paint(s.A.erode(E, ink * 0.5) * (1 - K), ec)
    s.A.paint(K, ink_col)
    if paper:
        s.A.paint(P, paper_col)
    if isinstance(fill, list):
        g = s.A.vgrad(y0, y1, fill)
        s.A.paint(F, g)
        base = np.asarray(fill[-1][1], f32)
    else:
        s.A.paint(F, col(fill))
        base = col(fill)
    if ht:
        rr = s.A.ramp((0, y0 + (y1 - y0) * 0.35), (0, y1))
        dots = s.A.halftone(rr * ht, 9, 45)
        s.A.paint(F * dots, ht_col if ht_col is not None else darken(base, 0.45), 0.55)
    if shine:
        # glossy highlight band across the upper third
        band = s.A.mask(poly([(l - 50, t + (b - t) * 0.12), (r_ + 50, t + (b - t) * 0.02),
                              (r_ + 50, t + (b - t) * 0.16), (l - 50, t + (b - t) * 0.26)]))
        s.A.paint(F * band, WHITE, 0.35)
    return F


def diag_split(s, pts, color, opacity=1.0):
    m = s.m(poly(pts))
    s.A.paint(m, col(color), opacity)
    return m


def ht_field(s, mask, color, period, value, angle=45, opacity=1.0):
    dots = s.A.halftone(value, period, angle)
    s.A.paint(mask * dots, col(color), opacity)


def speed_burst(s, cx, cy, r_in, r_out, count, width, color, seed=1, opacity=1.0, clip=None, aspect=1.0):
    p = action_lines(cx, cy, r_in, r_out, count, width, r=rng(seed), aspect=aspect)
    m = s.m(p)
    if clip is not None:
        m = m * clip
    s.A.paint(m, col(color), opacity)
    return m


def hspeed(s, box, count, color, seed=2, thick=(2, 10), opacity=1.0, clip=None):
    """horizontal speed streaks within box"""
    x0, y0, x1, y1 = box
    r = rng(seed)
    p = skia.Path()
    for _ in range(count):
        y = r.uniform(y0, y1); L = r.uniform(0.2, 0.7) * (x1 - x0); x = r.uniform(x0, x1 - L)
        w = r.uniform(*thick)
        p.addPath(poly([(x, y), (x + L, y - w / 2), (x + L, y + w / 2)]))
    m = s.m(p)
    if clip is not None:
        m = m * clip
    s.A.paint(m, col(color), opacity)


def badge(s, cx, cy, rx, ry, fill, lines, tcol, font="dela", seed=3, n=18, rot=0.0, ink=8, emit=0.0):
    p = starburst(cx, cy, rx, ry, n=n, inner=0.8, jitter=0.1, r=rng(seed))
    p = transformed(p, rotate=rot, pivot=(cx, cy))
    m = s.m(p)
    s.A.paint(s.A.shift(s.A.dilate(m, ink), 8, 10), INK)
    s.A.paint(s.A.dilate(m, ink), INK)
    s.A.paint(m, col(fill))
    k = len(lines)
    hh = ry * 1.0 / k
    tm = None
    for i, ln in enumerate(lines):
        y0 = cy - ry * 0.5 + i * hh
        tp = T(ln, font, (cx - rx * 0.6, y0 + hh * 0.08, cx + rx * 0.6, y0 + hh * 0.92))
        tp = transformed(tp, rotate=rot, pivot=(cx, cy))
        mm = s.m(tp)
        s.A.paint(mm, col(tcol))
        tm = mm if tm is None else np.maximum(tm, mm)
    if emit:
        s.accents.append((m, col(fill), emit))
    return m


def panel_border(s, box, w=10):
    s.A.paint(s.m(rect(*box), stroke=w, fill=False, join="miter"), INK)


def cylinder_shade(s, mask, x0, x1, base, hl=0.55, dark=0.55):
    """Horizontal cylinder shading for cans/bottles: dark edges, bright highlight stripe."""
    t = s.A.ramp((x0, 0), (x1, 0))
    k = 1 - dark * (np.abs(t - 0.42) / 0.58) ** 1.6
    rgb = col(base)[None, None, :] * k[..., None]
    s.A.paint(mask, rgb)
    hlm = np.clip(1 - np.abs(t - 0.3) / 0.05, 0, 1) + 0.5 * np.clip(1 - np.abs(t - 0.78) / 0.025, 0, 1)
    s.A.paint(mask * hlm, WHITE, hl)


def finish_bb(s, lamps=4, gain=0.95, floor=0.18, seams=True, frame=12):
    """frame, vinyl seams, weathering, floodlight emission"""
    H, W = s.H, s.W
    clean = s.A.px[..., :3].copy()
    if seams:
        for x in (512, 1024, 1536):
            sm = s.m(rect(x - 1.2, 0, x + 1.2, H_))
            s.A.paint(sm, INK, 0.15)
            s.A.paint(s.A.shift(sm, 2, 0), WHITE, 0.1)
        # vinyl wrinkles (subtle large-scale shading)
        wr = noise(H, W, 180 * s.ss, seed=_h(s.name, "wr"), beta=2.0, aniso=(1.0, 3.0))
        s.A.multiply(np.ones((H, W), f32), (0.94 + 0.12 * wr)[..., None] * WHITE)
    s.weather(0.55, streak=0.7, fade=0.04, top_band=frame)
    # steel frame
    s.frame(0, 0, W_, H_, frame, hexc("#3C3F46"), bolts=0)
    # floodlights from lamps above the top edge
    xx = np.linspace(0, W_, W, dtype=f32)[None, :]
    yy = np.linspace(0, H_, H, dtype=f32)[:, None]
    I = np.zeros((H, W), f32)
    for i in range(lamps):
        lx = (i + 0.5) * W_ / lamps
        d2 = ((xx - lx) / (W_ / lamps * 0.62)) ** 2 + ((yy + 80) / (H_ * 1.05)) ** 2
        I += np.exp(-d2 * 1.6) * 1.15
    I = floor + (1 - floor) * np.clip(I, 0, 1.25)
    inner = s.m(rect(frame, frame, W_ - frame, H_ - frame))
    s.E += clean * (I * inner * gain)[..., None]
    for (m, c, k) in s.accents:
        s.E += m[..., None] * (c * k)[None, None, :]
        s.E += blur(m, 10 * s.ss)[..., None] * (c * k * 0.5)[None, None, :]


def neon_accent(s, path, color, r=4.0):
    """thin neon tube on the poster (both albedo glass + emission)."""
    s.neon(path, color, r=r, shadow=0.35, clips=0.4)


# ======================================================================================
# 1. energy drink
# ======================================================================================
def draw_can(s, cx, cy, w, h, angle, body, accent, logo_text, sub_text, seed=1):
    cv = Sign.__new__(Sign)
    # draw upright can into its own masks, then rotate via path transforms
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    def R(p):
        return transformed(p, rotate=angle, pivot=(cx, cy))
    body_p = R(rect(x0, y0 + h * 0.06, x1, y1 - h * 0.04, w * 0.08))
    top_p = R(ellipse(cx, y0 + h * 0.06, w / 2 * 0.92, w * 0.09))
    neck_p = R(poly([(x0, y0 + h * 0.09), (x0 + w * 0.06, y0 + h * 0.03), (x1 - w * 0.06, y0 + h * 0.03), (x1, y0 + h * 0.09)]))
    bot_p = R(ellipse(cx, y1 - h * 0.04, w / 2, w * 0.08))
    sil = union(body_p, top_p, neck_p, bot_p)
    S_ = s.m(sil)
    s.A.paint(s.A.shift(s.A.dilate(S_, 10), 18, 22), INK, 0.9)
    s.A.paint(s.A.dilate(S_, 10), INK)
    # rotated shading ramp: compute in rotated frame by drawing ramp along rotated x axis
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    t = s.A.ramp((cx - ux * w / 2, cy - uy * w / 2), (cx + ux * w / 2, cy + uy * w / 2))
    k = 1 - 0.6 * (np.abs(t - 0.4) / 0.6) ** 1.5
    bm = s.m(body_p)
    s.A.paint(bm, col(body)[None, None, :] * k[..., None])
    # metallic neck/top
    met = s.m(union(top_p, neck_p, bot_p)) * (1 - bm * 0.0)
    s.A.paint(s.m(union(neck_p, bot_p)), hexc("#B9BEC6")[None, None, :] * (0.6 + 0.5 * k)[..., None])
    s.A.paint(s.m(top_p), hexc("#D8DCE2"))
    s.A.paint(s.m(R(ellipse(cx, y0 + h * 0.06, w / 2 * 0.7, w * 0.06))), hexc("#9CA2AA"))
    s.A.paint(s.m(R(rect(cx - w * 0.12, y0 + h * 0.045, cx + w * 0.16, y0 + h * 0.07, 6))), hexc("#E9ECEF"))
    # label graphics: diagonal accent stripe + lightning + text (vertical on can)
    stripe = R(poly([(x0, y0 + h * 0.55), (x1, y0 + h * 0.38), (x1, y0 + h * 0.5), (x0, y0 + h * 0.67)]))
    s.A.paint(s.m(stripe) * bm, col(accent)[None, None, :] * k[..., None])
    lt = R(picto_lightning((cx - w * 0.3, y0 + h * 0.12, cx + w * 0.3, y0 + h * 0.4)))
    lm = s.m(lt) * bm
    s.A.paint(s.A.dilate(lm, 5) * bm, INK)
    s.A.paint(lm, col(accent))
    tp = R(transformed(VT(logo_text, "bangers", (cx - w * 0.32, y0 + h * 0.42, cx + w * 0.32, y1 - h * 0.14)), rotate=0))
    # logo set vertically reading top->bottom rotated 90 deg (like real cans)
    tp = fit_path(transformed(text_path(logo_text, "bangers", 200), rotate=90), (cx - w * 0.36, y0 + h * 0.36, cx + w * 0.36, y1 - h * 0.1))
    tp = R(tp)
    tm = s.m(tp)
    s.A.paint(s.A.dilate(tm, 6) * bm, INK)
    s.A.paint(tm, PAPER)
    # cylinder highlight
    hl = np.clip(1 - np.abs(t - 0.28) / 0.04, 0, 1) + 0.4 * np.clip(1 - np.abs(t - 0.8) / 0.02, 0, 1)
    s.A.paint(S_ * hl, WHITE, 0.6)
    return S_


@bb
def bb_voltz_energy():
    s = B("bb_voltz_energy")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, hexc("#120A22"))
    # diagonal yellow field
    ym = diag_split(s, [(0, 0), (1180, 0), (760, 1024), (0, 1024)], YEL)
    ht_field(s, ym, hexc("#FFB000"), 22, A.ramp((0, 1024), (1100, 0)) * 0.6)
    # magenta slash
    diag_split(s, [(1180, 0), (1290, 0), (870, 1024), (760, 1024)], MAG)
    diag_split(s, [(1290, 0), (1320, 0), (900, 1024), (870, 1024)], INK)
    # speed lines on dark side
    speed_burst(s, 1550, 480, 380, 1500, 140, 22, hexc("#3A1E7A"), seed=4, clip=1 - ym)
    # lightning bolts
    for (x0_, y0_, x1_, y1_, w) in [(1950, 0, 1700, 420, 70), (1450, 0, 1350, 260, 40), (2048, 520, 1800, 980, 60)]:
        p = lightning(x0_, y0_, x1_, y1_, w, segs=5, r=rng(int(x0_ + y0_)))
        m = s.m(p)
        A.paint(A.dilate(m, 6), INK); A.paint(m, CYAN)
        s.accents.append((m, CYAN, 0.9))
    # title
    title = transformed(T("VOLTZ", "bangers", (90, 70, 1050, 520)), rotate=-6, skew_x=-0.12)
    comic_text(s, title, [(0, PAPER), (0.25, hexc("#FFFFFF")), (0.6, MAG), (1, hexc("#A0004A"))], paper=14, ink=12,
               ext=(16, 20), ext_col=hexc("#4A0026"))
    kana = transformed(T("ボルツ", "dela", (120, 560, 560, 700)), rotate=-6)
    comic_text(s, kana, INK, paper=8, ink=0, ext=None, ht=0, shine=False, paper_col=PAPER)
    copy = transformed(T("限界突破！", "dela", (90, 700, 860, 930)), rotate=-6)
    comic_text(s, copy, [(0, hexc("#FFFFFF")), (1, CYAN)], paper=6, ink=8, ext=(9, 11), ext_col=hexc("#003C55"), ht=0.0, shine=False)
    # cans
    draw_can(s, 1500, 560, 330, 700, 10, hexc("#2B0A5E"), MAG, "VOLTZ", "", seed=1)
    draw_can(s, 1830, 640, 260, 560, -8, hexc("#0A3A5E"), CYAN, "VOLTZ", "", seed=2)
    badge(s, 1140, 820, 170, 150, RED, ["新発売", "NEW!"], PAPER, seed=7, rot=-8, emit=0.0)
    txt = T("カフェイン増量・炭酸強め", "noto", (40, 960, 600, 1000), align=(0, 0.5))
    A.paint(s.m(txt), PAPER)
    finish_bb(s)
    return s


# ======================================================================================
# 2. mecha film
# ======================================================================================
def mecha_head(cx, cy, sc):
    """Original angular mecha helmet (single blade crest, swept-back fins, wrap visor)."""
    def P(pts):
        return poly([(cx + x * sc, cy + y * sc) for x, y in pts])
    helm = P([(0, -130), (46, -110), (84, -60), (96, 0), (84, 60), (52, 96), (0, 116), (-52, 96), (-84, 60),
              (-96, 0), (-84, -60), (-46, -110)])
    crest = P([(0, -260), (16, -130), (8, -96), (-8, -96), (-16, -130)])
    finL = P([(-90, -40), (-170, -70), (-200, -40), (-110, 10)])
    finR = P([(90, -40), (170, -70), (200, -40), (110, 10)])
    finL2 = P([(-96, 10), (-160, 20), (-150, 50), (-92, 44)])
    finR2 = P([(96, 10), (160, 20), (150, 50), (92, 44)])
    visor = P([(-92, -26), (0, -6), (92, -26), (84, 6), (0, 26), (-84, 6)])
    eyes = P([(-80, -18), (0, 0), (80, -18), (74, -2), (0, 16), (-74, -2)])
    face = P([(-46, 40), (46, 40), (34, 100), (0, 114), (-34, 100)])
    vents = skia.Path()
    for i in range(3):
        vents.addPath(P([(-6 - i * 14, 52 + i * 8), (-2 - i * 14, 52 + i * 8), (-10 - i * 14, 96 - i * 4), (-14 - i * 14, 96 - i * 4)]))
        vents.addPath(P([(6 + i * 14, 52 + i * 8), (2 + i * 14, 52 + i * 8), (10 + i * 14, 96 - i * 4), (14 + i * 14, 96 - i * 4)]))
    plate = P([(-30, -116), (30, -116), (22, -60), (0, -48), (-22, -60)])
    brow = P([(-84, -60), (-20, -40), (0, -46), (20, -40), (84, -60), (90, -34), (0, -14), (-90, -34)])
    return dict(helm=helm, crest=crest, horns=union(finL, finR), cheeks=union(finL2, finR2), visor=visor, eyes=eyes,
                face=face, vents=vents, plate=plate, brow=brow)


@bb
def bb_mecha_garvarion():
    s = B("bb_mecha_garvarion")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    g = A.vgrad(0, 1024, [(0, hexc("#060A1E")), (0.6, hexc("#1B1340")), (1, hexc("#3A0E3A"))])
    A.paint(full, g)
    # perspective grid floor
    grid = skia.Path()
    for i in range(-20, 21):
        grid.addPath(poly([(1024 + i * 12, 640), (1024 + i * 12 + 1.5, 640), (1024 + i * 260 + 4, 1024), (1024 + i * 260 - 4, 1024)]))
    for j in range(12):
        y = 640 + (j / 12) ** 2 * 384
        grid.addPath(rect(0, y, 2048, y + 1 + j * 0.4))
    gm = s.m(grid) * A.ramp((0, 640), (0, 1024))
    A.paint(gm, CYAN, 0.6)
    s.accents.append((gm * 0.5, CYAN, 0.6))
    # beams + speed lines behind the head
    speed_burst(s, 1400, 430, 260, 1500, 220, 18, hexc("#2C2F7A"), seed=9)
    speed_burst(s, 1400, 430, 420, 1500, 60, 10, CYAN, seed=10, opacity=0.5)
    # explosion glow
    glow = np.clip(1 - A.radial(1400, 430, 520), 0, 1) ** 2
    A.paint(glow, hexc("#FF7A2E"), 0.55)
    # head
    hd = mecha_head(1400, 470, 3.0)
    allm = s.m(union(*hd.values()))
    A.paint(A.dilate(allm, 12), INK)
    def shade(m, base, k=0.4):
        t = A.ramp((1100, 150), (1700, 800))
        A.paint(m, col(base)[None, None, :] * (1.15 - k * t)[..., None])
    shade(s.m(hd["helm"]), hexc("#4A5170"))
    shade(s.m(hd["cheeks"]), hexc("#2A2E44"))
    shade(s.m(hd["horns"]), hexc("#8A93B8"))
    shade(s.m(hd["crest"]), hexc("#F2B705"))
    shade(s.m(hd["plate"]), MAG)
    shade(s.m(hd["brow"]), hexc("#2A2E44"))
    shade(s.m(hd["face"]), hexc("#8A93B8"))
    A.paint(s.m(hd["vents"]), INK)
    A.paint(s.m(hd["visor"]), INK)
    hm_ = s.m(union(hd["helm"], hd["horns"], hd["cheeks"]))
    rim = hm_ * (1 - A.shift(hm_, 14, 6))
    A.paint(rim, CYAN, 0.85)
    s.accents.append((rim, CYAN, 0.35))
    eyes = s.m(hd["eyes"])
    A.paint(eyes, hexc("#FF7AB6"))
    s.accents.append((eyes, hexc("#FF4FA0"), 1.6))
    s.accents.append((A.blur(eyes, 30), MAG, 1.2))
    # ink panel lines on helmet
    for seg in [[(1400, 130), (1400, 300)], [(1180, 470), (1270, 530)], [(1620, 470), (1530, 530)]]:
        A.paint(s.m(poly(seg, close=False), stroke=6, fill=False), INK)
    # titles
    sub = T("劇場版", "noto", (90, 70, 420, 160), align=(0, 0.5))
    comic_text(s, sub, PAPER, paper=0, ink=0, ext=None, ht=0, shine=False)
    title = transformed(T("鋼鉄機神", "dela", (80, 170, 1000, 400)), skew_x=-0.08)
    comic_text(s, title, [(0, hexc("#FFFFFF")), (0.55, hexc("#DDE4F2")), (1, hexc("#8E9AC0"))],
               paper=5, ink=9, ext=(9, 12), ext_col=hexc("#0B1030"), ht=0.0, shine=True)
    title2 = transformed(T("ガルヴァリオン", "dela", (80, 410, 1000, 580)), skew_x=-0.08)
    comic_text(s, title2, [(0, YEL), (1, hexc("#FF7A00"))], paper=8, ink=10, ext=(8, 10), ext_col=hexc("#5A1A00"))
    copy = T("魂が、燃える。", "noto", (100, 640, 760, 740), align=(0, 0.5))
    A.paint(s.m(copy), PAPER)
    # date box
    A.paint(s.m(rect(100, 790, 820, 940)), RED)
    A.paint(s.m(rect(100, 790, 820, 940), stroke=8, fill=False), INK)
    A.paint(s.m(T("12.24 ROADSHOW", "bangers", (130, 805, 790, 925))), PAPER)
    s.accents.append((s.m(rect(100, 790, 820, 940)), RED, 0.35))
    A.paint(s.m(T("全国ロードショー", "noto", (860, 840, 1200, 900), align=(0, 0.5))), PAPER)
    finish_bb(s, gain=0.9)
    return s


# ======================================================================================
# 3. idol group
# ======================================================================================
def heart(cx, cy, r_):
    p = skia.Path()
    p.moveTo(cx, cy + r_ * 0.95)
    p.cubicTo(cx - r_ * 1.3, cy + r_ * 0.1, cx - r_ * 1.0, cy - r_ * 0.95, cx, cy - r_ * 0.4)
    p.cubicTo(cx + r_ * 1.0, cy - r_ * 0.95, cx + r_ * 1.3, cy + r_ * 0.1, cx, cy + r_ * 0.95)
    p.close()
    return p


@bb
def bb_idol_starprism():
    s = B("bb_idol_starprism")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    g = gradient_map(A.ramp((0, 0), (2048, 1024)), [(0, hexc("#FFB7D5")), (0.5, hexc("#FFE3F0")), (1, hexc("#9EEBFF"))])
    A.paint(full, g)
    ht_field(s, full, hexc("#FF7AB6"), 26, A.radial(0, 0, 1500) * 0.45, angle=30, opacity=0.6)
    ht_field(s, full, hexc("#3ACBF2"), 26, (1 - A.radial(2048, 1024, 1300)) * 0.45, angle=60, opacity=0.6)
    # big heart
    hm = s.m(heart(1450, 470, 430))
    A.paint(A.shift(A.dilate(hm, 14), 20, 24), INK)
    A.paint(A.dilate(hm, 14), INK)
    A.paint(A.dilate(hm, 6), PAPER)
    A.paint(hm, A.vgrad(80, 900, [(0, hexc("#FF7AB6")), (1, MAG)]))
    ht_field(s, hm, hexc("#C2005A"), 14, A.ramp((0, 450), (0, 900)) * 0.5, opacity=0.6)
    hl = s.m(poly([(1180, 200), (1330, 150), (1260, 260), (1150, 330)]))
    A.paint(hl * hm, WHITE, 0.6)
    neon_accent(s, heart(1450, 470, 470), hexc("#FF4FB0"), r=4.5)
    mic = picto_mic((1370, 230, 1530, 560))
    mm = s.m(mic)
    A.paint(A.dilate(mm, 8), INK); A.paint(mm, PAPER)
    A.paint(s.m(picto_mic_grille((1370, 230, 1530, 560))), hexc("#C2005A"))
    for (x, y, rr) in [(1290, 330, 40), (1610, 290, 30), (1600, 520, 24), (1300, 560, 22)]:
        sp_ = s.m(picto_star((x - rr, y - rr, x + rr, y + rr), n=4, inner=0.25))
        A.paint(sp_, PAPER)
    # member stars
    members = [("ヒカリ", YEL), ("ユメ", CYAN), ("ルナ", hexc("#B04BFF")), ("アオイ", LIME), ("サクラ", hexc("#FF9AC8"))]
    for i, (nm, c) in enumerate(members):
        a = math.radians(-160 + i * 35)
        cx = 1450 + math.cos(a) * 330 * 1.25; cy = 470 + math.sin(a) * 300 + 220
        cx = 1050 + i * 200; cy = 820 - (i % 2) * 60
        st = s.m(picto_star((cx - 95, cy - 95, cx + 95, cy + 95)))
        s.occlude(A.dilate(st, 8))
        A.paint(A.dilate(st, 8), INK)
        A.paint(st, c)
        tm = s.m(T(nm, "noto", (cx - 48, cy - 8, cx + 48, cy + 34)))
        A.paint(A.dilate(tm, 5), INK); A.paint(tm, PAPER)
    # title
    t1 = transformed(T("STAR PRISM", "bangers", (80, 80, 900, 300)), rotate=-4)
    comic_text(s, t1, [(0, YEL), (0.5, hexc("#FF9A00")), (1, MAG)], paper=12, ink=10, ext=(12, 14), ext_col=hexc("#5A0030"))
    st = s.m(picto_star((880, 40, 1010, 170)))
    A.paint(A.dilate(st, 6), INK); A.paint(st, CYAN)
    kana = transformed(T("スタプリ", "dela", (100, 340, 560, 460)), rotate=-4)
    comic_text(s, kana, MAG, paper=8, ink=8, ext=None, ht=0, shine=False)
    A.paint(s.m(rect(90, 520, 960, 600)), INK)
    A.paint(s.m(T("NEW SINGLE", "bangers", (110, 530, 520, 592), align=(0, 0.5))), YEL)
    A.paint(s.m(T("『恋はドリフト』", "noto", (90, 620, 980, 760))), INK)
    badge(s, 820, 420, 120, 105, YEL, ["OUT", "NOW!"], INK, font="bangers", seed=11, rot=10)
    A.paint(s.m(T("全国ツアー 2026 決定！", "noto", (100, 800, 760, 870), align=(0, 0.5))), hexc("#5A0030"))
    finish_bb(s)
    return s


# ======================================================================================
# 4. ramen chain
# ======================================================================================
def ramen_bowl(s, cx, cy, rx, ry):
    A = s.A
    # bowl body
    body = skia.Path()
    body.moveTo(cx - rx, cy)
    body.cubicTo(cx - rx * 0.95, cy + ry * 2.4, cx + rx * 0.95, cy + ry * 2.4, cx + rx, cy)
    body.close()
    foot = rect(cx - rx * 0.35, cy + ry * 1.75, cx + rx * 0.35, cy + ry * 2.0, 8)
    bm = s.m(union(body, foot))
    rim = s.m(ellipse(cx, cy, rx, ry))
    allm = np.maximum(bm, rim)
    A.paint(A.shift(A.dilate(allm, 12), 18, 22), INK)
    A.paint(A.dilate(allm, 12), INK)
    t = A.ramp((cx - rx, 0), (cx + rx, 0))
    A.paint(bm, hexc("#C8161D")[None, None, :] * (1.1 - 0.5 * np.abs(t - 0.35))[..., None])
    # pattern band on bowl (raimon / thunder meander simplified)
    band = skia.Path()
    for i in range(14):
        x = cx - rx * 0.9 + i * rx * 0.13
        band.addPath(rect(x, cy + ry * 0.55, x + rx * 0.07, cy + ry * 0.62))
        band.addPath(rect(x + rx * 0.05, cy + ry * 0.55, x + rx * 0.07, cy + ry * 0.75))
    A.paint(s.m(band) * bm, PAPER, 0.9)
    A.paint(np.clip(1 - np.abs(t - 0.25) / 0.04, 0, 1) * bm, WHITE, 0.4)
    # rim & soup
    A.paint(rim, PAPER)
    soup = s.m(ellipse(cx, cy + ry * 0.06, rx * 0.92, ry * 0.8))
    A.paint(soup, A.vgrad(cy - ry, cy + ry, [(0, hexc("#E8B060")), (1, hexc("#B06A20"))]))
    # noodles
    nd = skia.Path()
    r = rng(5)
    for i in range(26):
        y = cy + r.uniform(-0.5, 0.6) * ry
        xs = cx - rx * 0.8 + r.uniform(0, 0.2) * rx
        pts = [(xs + k * rx * 0.2, y + math.sin(k * 1.7 + i) * ry * 0.1) for k in range(9)]
        nd.addPath(smooth_open(pts))
    ndm = s.m(nd, stroke=9, fill=False) * soup
    A.paint(A.dilate(ndm, 2) * soup, hexc("#8A5A1A"))
    A.paint(ndm, hexc("#FFE08A"))
    # toppings: chashu, egg, naruto, nori, negi
    ch = s.m(ellipse(cx + rx * 0.35, cy - ry * 0.05, rx * 0.26, ry * 0.42))
    A.paint(A.dilate(ch, 6), INK); A.paint(ch, hexc("#B4693A"))
    A.paint(s.m(ellipse(cx + rx * 0.35, cy - ry * 0.05, rx * 0.17, ry * 0.26)), hexc("#E8A57A"))
    A.paint(s.m(ellipse(cx + rx * 0.35, cy - ry * 0.05, rx * 0.17, ry * 0.26), stroke=4, fill=False), hexc("#8A3E1A"))
    for (ex, ey) in [(cx - rx * 0.32, cy + ry * 0.12)]:
        e = s.m(ellipse(ex, ey, rx * 0.16, ry * 0.36))
        A.paint(A.dilate(e, 6), INK); A.paint(e, PAPER)
        A.paint(s.m(ellipse(ex + rx * 0.01, ey + ry * 0.04, rx * 0.09, ry * 0.2)), hexc("#FF9A1E"))
    nr = s.m(ellipse(cx - rx * 0.02, cy - ry * 0.45, rx * 0.15, ry * 0.3))
    A.paint(A.dilate(nr, 6), INK); A.paint(nr, PAPER)
    sp = skia.Path()
    sp.addPath(smooth_open([(cx - rx * 0.02 + math.cos(a) * rx * 0.1 * a / 12, cy - ry * 0.45 + math.sin(a) * ry * 0.2 * a / 12)
                            for a in np.linspace(0, 12, 30)]))
    A.paint(s.m(sp, stroke=7, fill=False) * nr, hexc("#FF4F8B"))
    nori = s.m(transformed(rect(cx - rx * 0.75, cy - ry * 1.3, cx - rx * 0.45, cy - ry * 0.05, 4), rotate=-12))
    A.paint(A.dilate(nori, 5), INK); A.paint(nori, hexc("#1F2A1E"))
    neg = skia.Path()
    for i in range(18):
        x = cx + r.uniform(-0.5, 0.6) * rx; y = cy + r.uniform(-0.2, 0.55) * ry
        neg.addCircle(x, y, 9)
    A.paint(s.m(neg) * soup, hexc("#5FCB3A"))
    # steam
    for i, x in enumerate((cx - rx * 0.4, cx, cx + rx * 0.4)):
        p = smooth_open([(x, cy - ry * 1.1), (x - 40, cy - ry * 1.6), (x + 40, cy - ry * 2.1), (x - 30, cy - ry * 2.6)])
        A.paint(s.m(p, stroke=22, fill=False), PAPER, 0.8)


@bb
def bb_ramen_dragon():
    s = B("bb_ramen_dragon")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, hexc("#D21F1F"))
    speed_burst(s, 1350, 560, 300, 1700, 160, 30, hexc("#FF5A2A"), seed=12)
    ht_field(s, full, hexc("#FFD21E"), 24, (1 - A.radial(1350, 560, 900)) * 0.55, opacity=0.8)
    ramen_bowl(s, 1350, 560, 520, 170)
    # chopsticks lifting noodles
    lift = skia.Path()
    rr_ = rng(55)
    for i in range(9):
        x0_ = 1440 + i * 7
        pts = [(x0_, 300)]
        for k in range(1, 6):
            pts.append((x0_ - k * 12 + i * k * 2.5 + rr_.uniform(-8, 8), 300 + k * 46))
        lift.addPath(smooth_open(pts))
    lm = s.m(lift, stroke=11, fill=False)
    A.paint(A.dilate(lm, 3), INK); A.paint(lm, hexc("#FFE08A"))
    A.paint(A.erode(lm, 3) * A.ramp((1400, 0), (1520, 0)), WHITE, 0.25)
    for dx in (0, 46):
        p = poly([(1560 + dx, 40), (1574 + dx, 40), (1452 + dx, 330), (1440 + dx, 330)])
        A.paint(A.dilate(s.m(p), 5), INK); A.paint(s.m(p), hexc("#F2D7A0"))
    # title
    t0 = T("麺屋", "noto", (90, 60, 330, 170), align=(0, 0.5))
    comic_text(s, t0, PAPER, paper=0, ink=8, ext=None, ht=0, shine=False)
    t1 = transformed(T("ドラゴン", "dela", (80, 170, 860, 420)), rotate=-5)
    comic_text(s, t1, [(0, hexc("#FFF6A0")), (0.4, YEL), (1, hexc("#FF9A00"))], paper=12, ink=12, ext=(14, 16), ext_col=hexc("#5A1400"))
    t2 = transformed(VT("濃厚", "dela", (90, 470, 260, 820)), rotate=0)
    comic_text(s, t2, PAPER, paper=0, ink=10, ext=(8, 8), ext_col=INK, ht=0, shine=False)
    t3 = T("豚骨醤油", "dela", (290, 520, 830, 690))
    comic_text(s, t3, INK, paper=10, ink=0, ext=None, ht=0, shine=False, paper_col=PAPER)
    A.paint(s.m(rect(290, 730, 830, 820)), INK)
    A.paint(s.m(T("全国200店舗突破！", "noto", (310, 742, 810, 808))), YEL)
    badge(s, 1880, 180, 150, 130, YEL, ["一杯", "¥790"], INK, font="dela", seed=13, rot=8)
    A.paint(s.m(T("RAMEN DRAGON", "bangers", (90, 880, 600, 980), align=(0, 0.5))), PAPER)
    finish_bb(s)
    return s


# ======================================================================================
# 5. camera
# ======================================================================================
@bb
def bb_kagami_camera():
    s = B("bb_kagami_camera")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#05060C")), (1, hexc("#1B1340"))]))
    # night skyline silhouette w/ windows (halftone)
    r = rng(14)
    sky = skia.Path(); win = skia.Path()
    x = 0
    while x < 2048:
        w = r.uniform(70, 180); h = r.uniform(150, 420)
        sky.addPath(rect(x, 1024 - h, x + w, 1024))
        for wy in np.arange(1024 - h + 20, 1010, 26):
            for wx in np.arange(x + 12, x + w - 12, 22):
                if r.random() < 0.35:
                    win.addPath(rect(wx, wy, wx + 10, wy + 12))
        x += w + r.uniform(0, 12)
    A.paint(s.m(sky), hexc("#0E0B22"))
    wm = s.m(win)
    A.paint(wm, hexc("#FFD27A"))
    s.accents.append((wm, hexc("#FFC060"), 0.7))
    # bokeh circles
    for i in range(26):
        cx_, cy_, rr = r.uniform(900, 2048), r.uniform(80, 600), r.uniform(20, 70)
        c = [MAG, CYAN, YEL, hexc("#FF7A2E")][i % 4]
        m = s.m(circle(cx_, cy_, rr))
        A.paint(m, c, 0.25)
        A.paint(s.m(circle(cx_, cy_, rr), stroke=3, fill=False), c, 0.5)
    # camera body
    cx, cy = 1420, 470
    body = rect(cx - 420, cy - 180, cx + 420, cy + 230, 50)
    hump = poly([(cx - 150, cy - 180), (cx - 100, cy - 290), (cx + 100, cy - 290), (cx + 150, cy - 180)])
    grip = rect(cx - 440, cy - 170, cx - 250, cy + 230, 60)
    allm = s.m(union(body, hump, grip))
    occ = A.dilate(np.maximum(allm, s.m(circle(cx + 40, cy + 40, 262))), 14)
    s.accents = [(m_ * (1 - occ), c_, k_) for (m_, c_, k_) in s.accents]
    A.paint(A.shift(A.dilate(allm, 12), 20, 24), INK, 0.8)
    A.paint(A.dilate(allm, 12), INK)
    t = A.ramp((cx, cy - 290), (cx, cy + 230))
    A.paint(allm, hexc("#2A2C33")[None, None, :] * (1.4 - 0.7 * t)[..., None])
    # leatherette texture
    lt = A.noise(2.5, seed=15, beta=0.6)
    A.paint(s.m(rect(cx - 400, cy - 60, cx + 400, cy + 200, 20)) * (lt > 0.55), hexc("#16171C"), 0.8)
    A.paint(s.m(grip), hexc("#16171C"), 0.7)
    # top plate highlight
    A.paint(s.m(rect(cx - 410, cy - 175, cx + 410, cy - 150, 20)), WHITE, 0.25)
    # dials
    for dx in (-330, 280):
        d = s.m(rect(cx + dx, cy - 230, cx + dx + 100, cy - 175, 8))
        A.paint(A.dilate(d, 5), INK); A.paint(d, hexc("#8A8F99"))
        for k in range(8):
            A.paint(s.m(rect(cx + dx + 8 + k * 11, cy - 226, cx + dx + 12 + k * 11, cy - 180)), hexc("#5A5E66"))
    # lens
    for (rr, c) in [(260, hexc("#111216")), (232, hexc("#5C606A")), (214, hexc("#1A1B20")), (180, hexc("#2C2F38")),
                    (150, hexc("#0B0C10")), (120, hexc("#1A2A5A")), (78, hexc("#2A1A5A"))]:
        A.paint(s.m(circle(cx + 40, cy + 40, rr)), c)
    A.paint(s.m(circle(cx + 40, cy + 40, 232), stroke=6, fill=False), INK)
    # knurl ring
    kn = skia.Path()
    for k in range(90):
        a = 2 * math.pi * k / 90
        kn.addPath(wedge(cx + 40, cy + 40, a, 214, 232, 4, 4))
    A.paint(s.m(kn), hexc("#3A3D45"))
    # lens reflections
    A.paint(s.m(ellipse(cx - 10, cy - 10, 60, 34)), MAG, 0.55)
    A.paint(s.m(ellipse(cx + 90, cy + 90, 30, 18)), CYAN, 0.5)
    A.paint(s.m(circle(cx - 30, cy - 30, 16)), WHITE, 0.9)
    A.paint(s.m(T("KAGAMI", "chakra", (cx + 180, cy - 140, cx + 380, cy - 90))), hexc("#D9B45A"))
    A.paint(s.m(circle(cx + 360, cy - 120, 12)), RED)
    # title
    t1 = T("夜を、撮れ。", "dela", (90, 120, 880, 330), align=(0, 0.5))
    comic_text(s, t1, PAPER, paper=0, ink=10, ext=(8, 10), ext_col=hexc("#2A1A5A"), ht=0.25, ht_col=hexc("#9AA0B5"))
    A.paint(s.m(T("KAGAMI α-ZERO", "chakra", (90, 380, 820, 500), align=(0, 0.5))), hexc("#D9B45A"))
    A.paint(s.m(T("鏡光学 フルサイズミラーレス", "noto", (90, 530, 820, 590), align=(0, 0.5))), PAPER)
    A.paint(s.m(rect(90, 640, 560, 720)), hexc("#D9B45A"))
    A.paint(s.m(T("ISO 409600", "chakra", (110, 650, 540, 710))), INK)
    neon_accent(s, poly([(90, 760), (820, 760)], close=False), MAG, r=3.0)
    finish_bb(s, gain=0.9)
    return s


# ======================================================================================
# 6. soda
# ======================================================================================
def bottle_path(cx, top, h, w):
    """500ml PET soda bottle silhouette with shoulder + grip waist."""
    nw = w * 0.4
    pts_r = [(nw / 2, 0), (nw / 2, h * 0.07), (nw * 0.62, h * 0.09), (w * 0.48, h * 0.24), (w / 2, h * 0.32),
             (w / 2, h * 0.5), (w * 0.44, h * 0.58), (w / 2, h * 0.66), (w / 2, h * 0.94), (w * 0.4, h)]
    p = skia.Path()
    p.moveTo(cx - nw / 2, top)
    for (x, y) in pts_r:
        p.lineTo(cx + x, top + y)
    for (x, y) in reversed(pts_r):
        p.lineTo(cx - x, top + y)
    p.close()
    sm = skia.Path()
    stroke_paint = skia.Paint(PathEffect=skia.CornerPathEffect.Make(w * 0.12))
    stroke_paint.getFillPath(p, sm)
    return sm


@bb
def bb_puchi_soda():
    s = B("bb_puchi_soda")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#7FF0FF")), (1, hexc("#00A8D8"))]))
    ht_field(s, full, PAPER, 20, A.ramp((0, 0), (0, 1024)) * 0.4, opacity=0.5)
    # lime splash wave
    wave = skia.Path()
    pts = [(0, 700)] + [(x, 700 + math.sin(x / 160) * 60) for x in range(0, 2100, 60)] + [(2048, 1024), (0, 1024)]
    wm = s.m(poly(pts))
    A.paint(A.shift(A.dilate(wm, 10), 0, -12), INK)
    A.paint(wm, LIME)
    ht_field(s, wm, hexc("#5FC81E"), 16, A.ramp((0, 700), (0, 1024)) * 0.6)
    # bubbles
    r = rng(16)
    bub = skia.Path(); bubh = skia.Path()
    for i in range(70):
        x, y, rr = r.uniform(0, 2048), r.uniform(0, 1000), r.uniform(6, 40)
        c = skia.Path(); c.addCircle(x, y, rr)
        bub.addPath(stroke_path(c, max(3, rr * 0.18)))
        bubh.addCircle(x - rr * 0.35, y - rr * 0.35, rr * 0.22)
    A.paint(s.m(bub), PAPER, 0.85); A.paint(s.m(bubh), WHITE, 0.9)
    # bottles
    for (cx, top, h, w, liquid, rot) in [(1350, 120, 820, 300, hexc("#B6FF3B"), -6), (1700, 200, 760, 280, hexc("#FF7AB6"), 7)]:
        bp = transformed(bottle_path(cx, top, h, w), rotate=rot, pivot=(cx, top + h / 2))
        m = s.m(bp)
        A.paint(A.shift(A.dilate(m, 11), 16, 20), INK, 0.8)
        A.paint(A.dilate(m, 11), INK)
        a = math.radians(rot)
        t = A.ramp((cx - math.cos(a) * w / 2, top + h / 2 - math.sin(a) * w / 2), (cx + math.cos(a) * w / 2, top + h / 2 + math.sin(a) * w / 2))
        A.paint(m, col(liquid)[None, None, :] * (1.05 - 0.45 * np.abs(t - 0.4))[..., None])
        cap = s.m(transformed(rect(cx - w * 0.23, top - 46, cx + w * 0.23, top + 8, 8), rotate=rot, pivot=(cx, top + h / 2)))
        A.paint(A.dilate(cap, 8), INK); A.paint(cap, YEL if liquid[0] > 0.8 else CYAN)
        ribs = skia.Path()
        for k in range(7):
            x_ = cx - w * 0.2 + k * w * 0.066
            ribs.addPath(rect(x_, top - 40, x_ + w * 0.02, top + 2))
        A.paint(s.m(transformed(ribs, rotate=rot, pivot=(cx, top + h / 2))) * cap, INK, 0.35)
        label = s.m(transformed(rect(cx - w / 2, top + h * 0.45, cx + w / 2, top + h * 0.78), rotate=rot, pivot=(cx, top + h / 2))) * m
        A.paint(label, PAPER)
        lt = transformed(T("PUCHI", "bangers", (cx - w * 0.4, top + h * 0.48, cx + w * 0.4, top + h * 0.62)), rotate=rot, pivot=(cx, top + h / 2))
        A.paint(s.m(lt), MAG)
        lt2 = transformed(T("プチソーダ", "dela", (cx - w * 0.42, top + h * 0.64, cx + w * 0.42, top + h * 0.75)), rotate=rot, pivot=(cx, top + h / 2))
        A.paint(s.m(lt2), hexc("#0070A8"))
        A.paint(np.clip(1 - np.abs(t - 0.25) / 0.05, 0, 1) * m, WHITE, 0.55)
    # copy
    t1 = transformed(T("シュワッと", "dela", (80, 90, 960, 330)), rotate=-5)
    comic_text(s, t1, [(0, PAPER), (1, hexc("#BFF4FF"))], paper=10, ink=12, ext=(12, 14), ext_col=hexc("#004A6A"))
    t2 = transformed(T("夏！", "dela", (300, 330, 900, 640)), rotate=-5)
    comic_text(s, t2, [(0, YEL), (1, hexc("#FF8A00"))], paper=12, ink=12, ext=(14, 16), ext_col=hexc("#6A2A00"))
    badge(s, 170, 520, 125, 110, MAG, ["新発売"], PAPER, seed=17, rot=-12)
    A.paint(s.m(T("PUCHI SODA  ラムネ味・白桃味", "noto", (90, 900, 900, 960), align=(0, 0.5))), INK)
    finish_bb(s)
    return s


# ======================================================================================
# 7. game console
# ======================================================================================
@bb
def bb_nexa_gear():
    s = B("bb_nexa_gear")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#0B0B12")), (1, hexc("#22104A"))]))
    # perspective grid wall
    grid = skia.Path()
    for i in range(-30, 31):
        grid.addPath(poly([(1400 + i * 10, 520), (1400 + i * 10 + 1.2, 520), (1400 + i * 220 + 3, 1024), (1400 + i * 220 - 3, 1024)]))
        grid.addPath(poly([(1400 + i * 10, 520), (1400 + i * 10 + 1.2, 520), (1400 + i * 220 + 3, 0), (1400 + i * 220 - 3, 0)]))
    gm = s.m(grid)
    A.paint(gm, MAG, 0.35)
    # dimension rings (behind the hardware)
    for k, rr in enumerate((190, 270, 345)):
        neon_accent(s, ellipse(1480, 570, rr * 1.55, rr * 0.5), [CYAN, MAG, CYAN][k], r=2.6 + k * 0.4)
    # console box
    cx, cy = 1400, 520
    box = s.m(rect(cx - 330, cy - 120, cx + 330, cy + 60, 30))
    A.paint(A.shift(A.dilate(box, 10), 18, 22), INK, 0.8)
    A.paint(A.dilate(box, 10), INK)
    A.paint(box, A.vgrad(cy - 120, cy + 60, [(0, hexc("#F4F5FA")), (1, hexc("#A8ACBA"))]))
    stripe = s.m(rect(cx - 330, cy - 40, cx + 330, cy - 20))
    A.paint(stripe * box, MAG)
    s.accents.append((stripe * box, MAG, 0.9))
    A.paint(s.m(T("NEXA", "chakra", (cx - 300, cy + 0, cx - 120, cy + 45))), hexc("#2A2C38"))
    # controller
    pad = picto_gamepad((cx - 260, cy + 90, cx + 260, cy + 430))
    pm = s.m(pad)
    A.paint(A.shift(A.dilate(pm, 10), 18, 22), INK, 0.8)
    A.paint(A.dilate(pm, 10), INK)
    A.paint(pm, A.vgrad(cy + 90, cy + 430, [(0, hexc("#2C2F3A")), (1, hexc("#14151B"))]))
    # buttons glow
    for (bx, by, c) in [(cx + 95, cy + 175, MAG), (cx + 130, cy + 210, CYAN), (cx + 60, cy + 210, YEL), (cx + 95, cy + 245, LIME)]:
        bmm = s.m(circle(bx, by, 16))
        A.paint(bmm, c)
        s.accents.append((bmm, c, 1.0))
    # titles
    t1 = transformed(T("NEXA GEAR", "chakra", (80, 100, 860, 290), align=(0, 0.5)), skew_x=-0.15)
    comic_text(s, t1, [(0, PAPER), (0.5, CYAN), (1, hexc("#006A8A"))], paper=8, ink=10, ext=(10, 12), ext_col=hexc("#00303F"), ht=0.25)
    r1 = bounds(t1)[2]
    t2 = transformed(T("2", "dela", (r1 + 30, 60, r1 + 230, 360)), skew_x=-0.15)
    comic_text(s, t2, [(0, YEL), (1, MAG)], paper=10, ink=12, ext=(12, 14), ext_col=hexc("#4A0026"))
    t3 = T("次元を超えろ。", "dela", (90, 400, 900, 560), align=(0, 0.5))
    comic_text(s, t3, PAPER, paper=0, ink=0, ext=None, ht=0, shine=False)
    A.paint(s.m(rect(90, 620, 640, 720)), MAG)
    A.paint(s.m(T("11.11 発売", "noto", (110, 630, 620, 710))), PAPER)
    A.paint(s.m(T("ネクサギア2  希望小売価格 ¥49,980", "noto", (90, 760, 900, 820), align=(0, 0.5))), hexc("#B9B3D8"))
    badge(s, 1880, 160, 140, 120, YEL, ["予約", "受付中"], INK, font="noto", seed=19, rot=-10)
    occ = A.dilate(np.maximum(np.maximum(box, pm), np.maximum(s.m(t1), s.m(t3))), 12)
    s.occlude(occ)
    s.accents = [(m_ * (1 - occ), c_, k_) for (m_, c_, k_) in s.accents]
    # re-add button glows (they sit on the controller)
    for (bx, by, c) in [(cx + 95, cy + 175, MAG), (cx + 130, cy + 210, CYAN), (cx + 60, cy + 210, YEL), (cx + 95, cy + 245, LIME)]:
        s.accents.append((s.m(circle(bx, by, 16)), c, 1.0))
    s.accents.append((stripe * box, MAG, 0.9))
    finish_bb(s, gain=0.85)
    return s


# ======================================================================================
# 8. sneaker
# ======================================================================================
def sneaker_paths(cx, cy, L):
    """Side-view sneaker, toe to the right. Returns dict of paths (unit design * L)."""
    def U(x, y):
        return (cx + x * L, cy + y * L)
    up = skia.Path()
    up.moveTo(*U(-0.47, 0.06))
    up.cubicTo(*U(-0.50, -0.05), *U(-0.49, -0.17), *U(-0.44, -0.23))
    up.lineTo(*U(-0.40, -0.25))
    up.cubicTo(*U(-0.36, -0.20), *U(-0.30, -0.17), *U(-0.24, -0.19))
    up.lineTo(*U(-0.21, -0.29))
    up.cubicTo(*U(-0.17, -0.31), *U(-0.12, -0.30), *U(-0.10, -0.25))
    up.cubicTo(*U(0.05, -0.16), *U(0.25, -0.09), *U(0.40, -0.05))
    up.cubicTo(*U(0.50, -0.02), *U(0.54, 0.03), *U(0.50, 0.06))
    up.close()
    sole = skia.Path()
    sole.moveTo(*U(-0.50, 0.03)); sole.lineTo(*U(0.50, 0.03))
    sole.quadTo(*U(0.57, 0.05), *U(0.52, 0.10))
    sole.lineTo(*U(-0.42, 0.14))
    sole.quadTo(*U(-0.52, 0.14), *U(-0.50, 0.03))
    sole.close()
    big = rect(cx - L, cy - L, cx + L, cy + L)
    toe = skia.Op(up, rect(cx + 0.30 * L, cy - L, cx + L, cy + L), skia.PathOp.kIntersect_PathOp)
    heel = skia.Op(up, rect(cx - L, cy - L, cx - 0.36 * L, cy + L), skia.PathOp.kIntersect_PathOp)
    eyestay = stroke_path(smooth_open([U(-0.15, -0.235), U(0.05, -0.15), U(0.26, -0.075)]), 0.05 * L, cap="round")
    laces = skia.Path()
    for i in range(6):
        t = i / 5
        x = -0.14 + t * 0.38
        y = -0.235 + t * 0.16
        laces.addPath(poly([U(x - 0.012, y - 0.035), U(x + 0.02, y - 0.04), U(x + 0.03, y + 0.02), U(x - 0.002, y + 0.025)]))
    collar = smooth_closed([U(-0.40, -0.235), U(-0.33, -0.195), U(-0.25, -0.19), U(-0.22, -0.26), U(-0.33, -0.25)], 0.5)
    stripe = stroke_path(smooth_open([U(-0.42, -0.03), U(-0.22, -0.08), U(0.02, -0.01), U(0.30, -0.04)]), 0.035 * L)
    stripe = skia.Op(stripe, up, skia.PathOp.kIntersect_PathOp)
    return dict(sole=sole, upper=up, toe=toe, heel=heel, swirl=stripe, collar=collar, laces=laces, eyestay=eyestay)


@bb
def bb_kaze_runner():
    s = B("bb_kaze_runner")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, PAPER)
    # diagonal split: lime/ink
    dm = diag_split(s, [(820, 0), (2048, 0), (2048, 1024), (520, 1024)], INK)
    speed_burst(s, 1420, 520, 300, 1400, 200, 16, hexc("#2A2A3A"), seed=21, clip=dm)
    hspeed(s, (520, 100, 2048, 950), 90, LIME, seed=22, thick=(2, 9), opacity=0.8, clip=dm)
    ht_field(s, 1 - dm, hexc("#C8C1AE"), 18, A.ramp((0, 0), (800, 1024)) * 0.5)
    # wind swirls on left
    for k in range(3):
        p = smooth_open([(60, 700 + k * 70), (300, 640 + k * 70), (520, 700 + k * 70), (700, 640 + k * 70)])
        A.paint(s.m(p, stroke=8, fill=False), CYAN, 0.9)
    # sneaker
    sp = sneaker_paths(1440, 600, 1100)
    allm = s.m(union(sp["sole"], sp["upper"]))
    A.paint(A.shift(A.dilate(allm, 12), 22, 26), MAG)
    A.paint(A.dilate(allm, 12), PAPER)
    A.paint(A.dilate(allm, 6), INK)
    A.paint(s.m(sp["upper"]), A.vgrad(200, 640, [(0, hexc("#FFFFFF")), (1, hexc("#C9CFDA"))]))
    A.paint(s.m(sp["toe"]), hexc("#E7EAF0"))
    A.paint(s.m(sp["heel"]), MAG)
    A.paint(s.m(sp["swirl"]), CYAN)
    A.paint(s.m(sp["swirl"], stroke=6, fill=False), INK)
    A.paint(s.m(sp["eyestay"]) * s.m(sp["upper"]), hexc("#2A2C38"))
    A.paint(s.m(sp["collar"]), INK)
    A.paint(s.m(sp["laces"]), PAPER)
    A.paint(s.m(sp["laces"], stroke=3, fill=False), INK)
    A.paint(s.m(sp["sole"]), A.vgrad(630, 760, [(0, PAPER), (0.35, LIME), (1, hexc("#5FA81E"))]))
    for i in range(11):
        x = 1420 - 480 + i * 92
        A.paint(s.m(rect(x, 610 + 0.11 * 1100 - 22, x + 36, 610 + 0.11 * 1100 - 8, 5)), hexc("#3E7A12"))
    for k in ("upper", "toe", "heel", "sole"):
        A.paint(s.m(sp[k], stroke=5, fill=False), INK)
    # 風 badge on shoe
    kb = s.m(circle(1180, 500, 58))
    A.paint(A.dilate(kb, 6), PAPER); A.paint(kb, INK); A.paint(s.m(T("風", "dela", (1142, 462, 1218, 538))), PAPER)
    # copy
    t1 = transformed(VT("風になれ。", "dela", (110, 60, 360, 960)), skew_x=0.0)
    comic_text(s, t1, INK, paper=0, ink=0, ext=None, ht=0, shine=False)
    t2 = transformed(T("KAZE", "bangers", (390, 80, 860, 330)), rotate=-6, skew_x=-0.1)
    comic_text(s, t2, [(0, MAG), (1, hexc("#A0004A"))], paper=10, ink=10, ext=(12, 14), ext_col=INK)
    t3 = transformed(T("RUNNER", "bangers", (390, 320, 880, 470)), rotate=-6, skew_x=-0.1)
    comic_text(s, t3, [(0, CYAN), (1, hexc("#007A9A"))], paper=8, ink=10, ext=(10, 12), ext_col=INK)
    A.paint(s.m(T("走れ、東京。", "noto", (400, 545, 640, 600), align=(0, 0.5))), INK)
    badge(s, 640, 820, 150, 120, YEL, ["NEW", "MODEL"], INK, font="bangers", seed=23, rot=-8)
    finish_bb(s)
    return s


# ======================================================================================
# 9. lager
# ======================================================================================
def fox_mask(cx, cy, sc):
    def P(pts):
        return poly([(cx + x * sc, cy + y * sc) for x, y in pts])
    face = P([(0, 90), (-60, 20), (-80, -40), (-90, -110), (-40, -60), (0, -70), (40, -60), (90, -110), (80, -40), (60, 20)])
    eyeL = P([(-56, -20), (-18, -10), (-24, 0), (-50, -8)])
    eyeR = P([(56, -20), (18, -10), (24, 0), (50, -8)])
    markL = P([(-70, -70), (-48, -50), (-60, -30)])
    markR = P([(70, -70), (48, -50), (60, -30)])
    nose = P([(-8, 74), (8, 74), (0, 90)])
    return face, union(eyeL, eyeR), union(markL, markR), nose


@bb
def bb_kurokitsune_lager():
    s = B("bb_kurokitsune_lager")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#0B0B12")), (1, hexc("#2A1A0A"))]))
    speed_burst(s, 1450, 520, 260, 1500, 120, 26, hexc("#3A2A12"), seed=24)
    glow = np.clip(1 - A.radial(1450, 520, 700), 0, 1) ** 1.5
    A.paint(glow, hexc("#FFB020"), 0.45)
    # beer glass
    cx, top, h = 1450, 160, 760
    glass = poly([(cx - 200, top), (cx + 200, top), (cx + 160, top + h), (cx - 160, top + h)])
    gm = s.m(glass)
    A.paint(A.shift(A.dilate(gm, 12), 20, 24), INK, 0.8)
    A.paint(A.dilate(gm, 12), INK)
    A.paint(gm, A.vgrad(top, top + h, [(0, hexc("#FFD65A")), (0.5, hexc("#F2A11E")), (1, hexc("#B05A08"))]))
    # bubbles in beer
    r = rng(25)
    bb_ = skia.Path()
    for i in range(80):
        bb_.addCircle(cx + r.uniform(-170, 170), r.uniform(top + 160, top + h - 20), r.uniform(2, 7))
    A.paint(s.m(bb_) * gm, hexc("#FFF0B0"), 0.8)
    # foam
    foam = skia.Path()
    for (x, y, rr) in [(-170, 0, 70), (-90, -30, 90), (10, -40, 95), (110, -30, 85), (180, 0, 60), (-40, 10, 80), (70, 10, 80)]:
        foam.addCircle(cx + x, top + 40 + y, rr)
    fm = s.m(foam)
    A.paint(A.dilate(fm, 10), INK)
    A.paint(fm, A.vgrad(top - 60, top + 120, [(0, hexc("#FFFFFF")), (1, hexc("#EADFC6"))]))
    A.paint(np.clip(1 - np.abs(A.ramp((cx - 200, 0), (cx + 200, 0)) - 0.22) / 0.04, 0, 1) * gm, WHITE, 0.45)
    # fox mask emblem on glass
    face, eyes, marks, nose = fox_mask(cx, top + 470, 1.4)
    A.paint(A.dilate(s.m(face), 6), INK)
    A.paint(s.m(face), PAPER)
    A.paint(s.m(eyes), INK); A.paint(s.m(marks), RED); A.paint(s.m(nose), INK)
    # copy
    t1 = T("黒狐", "dela", (90, 80, 700, 420), align=(0, 0.5))
    comic_text(s, t1, [(0, hexc("#FFE9A8")), (0.5, hexc("#F2B705")), (1, hexc("#9A6A00"))], paper=8, ink=12, ext=(12, 14), ext_col=hexc("#2A1A00"))
    A.paint(s.m(T("KUROKITSUNE LAGER", "chakra", (90, 450, 900, 520), align=(0, 0.5), tracking=0.08)), hexc("#F2B705"))
    t2 = VT("キレ、極まる。", "noto", (975, 110, 1065, 760))
    A.paint(s.m(t2), PAPER)
    badge(s, 760, 800, 140, 115, RED, ["キンキン", "冷え"], PAPER, font="noto", seed=35, rot=8)
    A.paint(s.m(rect(90, 600, 640, 690)), hexc("#F2B705"))
    A.paint(s.m(T("超辛口 ・ 生", "noto", (110, 610, 620, 680))), INK)
    A.paint(s.m(T("お酒は20歳になってから。", "noto", (90, 930, 600, 975), align=(0, 0.5))), hexc("#9A8A6A"))
    neon_accent(s, rect(70, 60, 920, 560, 20), hexc("#FFB020"), r=3.2)
    finish_bb(s, gain=0.9)
    return s


# ======================================================================================
# 10. mobile carrier
# ======================================================================================
@bb
def bb_sora_mobile():
    s = B("bb_sora_mobile")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#2E8BFF")), (0.7, hexc("#9EE6FF")), (1, hexc("#FFFFFF"))]))
    # clouds
    r = rng(26)
    for i in range(7):
        cx_, cy_ = r.uniform(0, 2048), r.uniform(560, 960)
        cl = skia.Path()
        for k in range(6):
            cl.addCircle(cx_ + r.uniform(-160, 160), cy_ + r.uniform(-40, 30), r.uniform(60, 110))
        m = s.m(cl)
        A.paint(A.dilate(m, 6), hexc("#6FB6FF"), 0.6); A.paint(m, WHITE)
    # phone
    cx, cy = 1500, 500
    ph = s.m(transformed(rect(cx - 210, cy - 420, cx + 210, cy + 420, 60), rotate=12))
    A.paint(A.shift(A.dilate(ph, 12), 22, 26), INK, 0.7)
    A.paint(A.dilate(ph, 12), INK)
    A.paint(ph, hexc("#1A1C24"))
    scr = s.m(transformed(rect(cx - 185, cy - 390, cx + 185, cy + 390, 42), rotate=12, pivot=(cx, cy)))
    A.paint(scr, gradient_map(A.ramp((cx - 200, cy - 400), (cx + 200, cy + 400)), [(0, MAG), (0.5, hexc("#7A3BFF")), (1, CYAN)]))
    s.accents.append((scr, hexc("#B07AFF"), 0.45))
    t5 = transformed(T("5G", "chakra", (cx - 140, cy - 160, cx + 140, cy + 80)), rotate=12, pivot=(cx, cy))
    A.paint(s.m(t5), WHITE)
    s.accents.append((s.m(t5), WHITE, 0.6))
    # speed swoosh behind phone
    for k in range(3):
        p = smooth_open([(900, 300 + k * 80), (1200, 260 + k * 70), (1700, 340 + k * 60), (2100, 260 + k * 70)])
        A.paint(s.m(p, stroke=14 - k * 3, fill=False), YEL, 0.9)
    # copy
    t1 = transformed(T("SORA", "bangers", (80, 80, 640, 330)), rotate=-4)
    comic_text(s, t1, [(0, WHITE), (1, hexc("#BFE6FF"))], paper=0, ink=10, ext=(10, 12), ext_col=hexc("#0A3A8A"))
    t2 = transformed(T("MOBILE", "bangers", (600, 140, 1060, 330)), rotate=-4)
    comic_text(s, t2, [(0, YEL), (1, hexc("#FF9A00"))], paper=0, ink=10, ext=(10, 12), ext_col=hexc("#6A3A00"))
    A.paint(s.m(T("ソラモバイル", "dela", (90, 360, 700, 470), align=(0, 0.5))), hexc("#0A2A6A"))
    t3 = T("ギガ無制限", "dela", (90, 520, 900, 690), align=(0, 0.5))
    comic_text(s, t3, MAG, paper=10, ink=10, ext=(8, 10), ext_col=INK, ht=0.3)
    A.paint(s.m(rect(90, 730, 760, 860)), INK)
    A.paint(s.m(T("月額 ¥2,980", "noto", (110, 742, 740, 848))), YEL)
    A.paint(s.m(T("※税込・条件あり", "noto", (90, 880, 400, 920), align=(0, 0.5))), hexc("#2A4A7A"))
    finish_bb(s)
    return s


# ======================================================================================
# 11. weekly shonen magazine
# ======================================================================================
@bb
def bb_shonen_boost():
    s = B("bb_shonen_boost")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, PAPER)
    # manga panel collage on right
    panels = [poly([(860, 40), (1440, 40), (1380, 500), (860, 500)]),
              poly([(1470, 40), (2008, 40), (2008, 420), (1415, 420)]),
              poly([(860, 530), (1300, 530), (1250, 984), (860, 984)]),
              poly([(1330, 530), (2008, 450), (2008, 984), (1280, 984)])]
    r = rng(27)
    for i, pp in enumerate(panels):
        pm = s.m(pp)
        l, t, r_, b = bounds(pp)
        cx_, cy_ = (l + r_) / 2, (t + b) / 2
        if i == 0:
            A.paint(pm, PAPER)
            speed_burst(s, cx_, cy_, 60, 700, 220, 9, INK, seed=28, clip=pm)
            em = s.m(starburst(cx_, cy_, 140, 110, n=16, inner=0.6, r=rng(29)))
            A.paint(em * pm, YEL)
            A.paint(s.m(T("ドン!!", "dela", (cx_ - 110, cy_ - 50, cx_ + 110, cy_ + 50))) * pm, INK)
        elif i == 1:
            A.paint(pm, hexc("#FFE600"))
            ht_field(s, pm, hexc("#FF9A00"), 14, A.ramp((l, t), (r_, b)) * 0.6)
            hspeed(s, (l, t, r_, b), 60, INK, seed=30, thick=(2, 8), clip=pm)
            car = s.m(transformed(union(rect(cx_ - 200, cy_ - 30, cx_ + 200, cy_ + 50, 20),
                                        poly([(cx_ - 110, cy_ - 30), (cx_ - 60, cy_ - 90), (cx_ + 80, cy_ - 90), (cx_ + 130, cy_ - 30)])), rotate=-8)) * pm
            A.paint(A.dilate(car, 6) * pm, INK); A.paint(car, MAG)
            for wx in (-120, 120):
                A.paint(s.m(transformed(circle(cx_ + wx, cy_ + 55, 42), rotate=-8, pivot=(cx_, cy_))) * pm, INK)
        elif i == 2:
            A.paint(pm, hexc("#1B1340"))
            speed_burst(s, cx_, cy_, 40, 600, 160, 10, CYAN, seed=31, clip=pm)
            A.paint(s.m(T("ゴゴゴ", "dela", (l + 30, t + 40, r_ - 30, t + 200))) * pm, PAPER)
            ht_field(s, pm, MAG, 12, A.ramp((0, t), (0, b)) * 0.5)
        else:
            A.paint(pm, PAPER)
            ht_field(s, pm, hexc("#9A9AA6"), 10, 0.35, angle=30)
            sm = s.m(T("ドリフト番長", "dela", (l + 60, t + 140, r_ - 40, t + 330)))
            A.paint(A.dilate(sm, 10) * pm, INK); A.paint(sm * pm, YEL)
            A.paint(s.m(T("新連載!!", "dela", (l + 120, t + 360, r_ - 120, t + 470))) * pm, RED)
        A.paint(s.m(pp, stroke=12, fill=False, join="miter"), INK)
    # masthead
    A.paint(s.m(rect(0, 0, 820, 1024)), RED)
    ht_field(s, s.m(rect(0, 0, 820, 1024)), hexc("#B0101A"), 18, A.ramp((0, 0), (0, 1024)) * 0.5)
    A.paint(s.m(T("週刊少年", "dela", (60, 50, 760, 180))), PAPER)
    t1 = transformed(T("ブースト", "dela", (40, 190, 790, 420)), rotate=-3)
    comic_text(s, t1, [(0, YEL), (1, hexc("#FFA000"))], paper=10, ink=14, ext=(14, 16), ext_col=INK)
    A.paint(s.m(T("WEEKLY SHONEN BOOST", "bangers", (60, 440, 760, 510))), PAPER)
    A.paint(s.m(rect(60, 560, 760, 700)), INK)
    A.paint(s.m(T("最新号 好評発売中！", "noto", (80, 576, 740, 684))), YEL)
    A.paint(s.m(T("No.42", "chakra", (60, 740, 380, 860), align=(0, 0.5))), PAPER)
    A.paint(s.m(T("毎週月曜発売 ¥290", "noto", (60, 890, 700, 960), align=(0, 0.5))), PAPER)
    badge(s, 640, 800, 120, 100, YEL, ["特大", "付録"], INK, font="noto", seed=32, rot=8)
    finish_bb(s)
    return s


# ======================================================================================
# 12. drift league event
# ======================================================================================
def coupe_side(cx, cy, L):
    def P(pts):
        return [(cx + x * L, cy + y * L) for x, y in pts]
    body = smooth_closed(P([(-0.5, 0.05), (-0.5, -0.06), (-0.42, -0.1), (-0.2, -0.12), (-0.08, -0.24), (0.14, -0.25),
                            (0.28, -0.13), (0.48, -0.09), (0.52, 0.0), (0.5, 0.07), (-0.45, 0.08)]), 0.25)
    glass = smooth_closed(P([(-0.16, -0.12), (-0.06, -0.21), (0.12, -0.22), (0.24, -0.12)]), 0.25)
    wing = poly(P([(-0.52, -0.2), (-0.36, -0.2), (-0.37, -0.17), (-0.42, -0.17), (-0.42, -0.1), (-0.45, -0.1), (-0.45, -0.17), (-0.52, -0.17)]))
    return body, glass, wing, [(cx - 0.3 * L, cy + 0.07 * L), (cx + 0.32 * L, cy + 0.07 * L)]


@bb
def bb_drift_league():
    s = B("bb_drift_league")
    A = s.A
    full = np.ones((s.H, s.W), f32)
    A.paint(full, A.vgrad(0, 1024, [(0, hexc("#1B1340")), (1, hexc("#0B0B12"))]))
    # checkered band
    chk = skia.Path()
    for j in range(3):
        for i in range(70):
            if (i + j) % 2 == 0:
                x = i * 32; y = 880 + j * 32
                chk.addPath(rect(x, y, x + 32, y + 32))
    A.paint(s.m(rect(0, 880, 2048, 976)), PAPER)
    A.paint(s.m(chk), INK)
    # smoke clouds
    r = rng(33)
    smoke = skia.Path()
    for i in range(40):
        x = r.uniform(1000, 2048) ; y = r.uniform(420, 860)
        smoke.addCircle(x, y, r.uniform(50, 140) * (0.6 + 0.6 * (x - 1000) / 1000))
    sm = s.m(smoke)
    A.paint(A.dilate(sm, 8), hexc("#6A6A80"))
    A.paint(sm, A.vgrad(400, 900, [(0, hexc("#E8E6F0")), (1, hexc("#A8A6B8"))]))
    ht_field(s, sm, hexc("#8A88A0"), 12, A.ramp((0, 500), (0, 900)) * 0.5)
    # car drifting (rotated)
    CX = 1330
    body, glass, wing, wheels = coupe_side(CX, 640, 820)
    rot = -8
    def R(p):
        return transformed(p, rotate=rot, pivot=(CX, 640))
    bm = s.m(R(union(body, wing)))
    A.paint(A.shift(A.dilate(bm, 12), 16, 20), INK, 0.6)
    A.paint(A.dilate(bm, 12), INK)
    A.paint(bm, A.vgrad(440, 720, [(0, hexc("#FF6FA8")), (1, hexc("#B0004A"))]))
    A.paint(s.m(R(glass)), hexc("#1A2A4A"))
    A.paint(s.m(R(poly([(CX - 350, 600), (CX + 350, 560), (CX + 350, 575), (CX - 350, 615)]))) * bm, CYAN)
    for (wx, wy) in wheels:
        wp = transformed(circle(wx, wy, 78), rotate=rot, pivot=(CX, 640))
        wm = s.m(wp)
        A.paint(A.dilate(wm, 8), INK); A.paint(wm, hexc("#16161C"))
        l, t, r_, b = bounds(wp)
        A.paint(s.m(circle((l + r_) / 2, (t + b) / 2, 50)), hexc("#B9BEC6"))
        A.paint(s.m(circle((l + r_) / 2, (t + b) / 2, 18)), INK)
    # headlight accent
    hl = s.m(R(ellipse(CX + 410, 618, 20, 10)))
    A.paint(hl, PAPER); s.accents.append((hl, PAPER, 1.0))
    # titles
    t1 = transformed(T("TOKYO DRIFT", "bangers", (60, 50, 980, 250)), rotate=-5, skew_x=-0.1)
    comic_text(s, t1, [(0, PAPER), (1, CYAN)], paper=10, ink=10, ext=(12, 14), ext_col=hexc("#00303F"))
    t2 = transformed(T("LEAGUE 2026", "bangers", (80, 240, 900, 380)), rotate=-5, skew_x=-0.1)
    comic_text(s, t2, [(0, YEL), (1, MAG)], paper=8, ink=10, ext=(10, 12), ext_col=hexc("#4A0026"))
    t3 = T("首都決戦", "dela", (80, 410, 800, 650), align=(0, 0.5))
    comic_text(s, t3, PAPER, paper=0, ink=9, ext=(12, 14), ext_col=MAG, ht=0.0, shine=False)
    A.paint(s.m(rect(80, 690, 760, 800)), MAG)
    A.paint(s.m(T("10.31 SAT 湾岸特設コース", "noto", (100, 702, 740, 788))), PAPER)
    badge(s, 1880, 170, 140, 120, RED, ["観戦", "無料"], PAPER, font="noto", seed=34, rot=10)
    neon_accent(s, poly([(60, 830), (780, 830)], close=False), CYAN, r=3.0)
    finish_bb(s, gain=0.85)
    return s


# ======================================================================================
def render(names=None):
    names = names or list(REG.keys())
    for n in names:
        s = REG[n]()
        pa, pe = s.save()
        print("wrote", os.path.basename(pa), os.path.basename(pe), flush=True)


def sheets():
    paths = []
    for n in sorted(REG):
        nn = n[3:] if n.startswith("bb_") else n
        paths += [os.path.join(SIGN_DIR, f"{n}_albedo.png"), os.path.join(SIGN_DIR, f"{n}_emission.png")]
    paths = [p for p in paths if os.path.exists(p)]
    contact_sheet(paths, os.path.join(PREVIEWS, "billboards.png"), cell=(440, 220), cols=4, bg="dark",
                  title="ROOFTOP BILLBOARDS  (albedo | emission)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--sheets"]:
        sheets()
    else:
        render(args or None)
        sheets()
