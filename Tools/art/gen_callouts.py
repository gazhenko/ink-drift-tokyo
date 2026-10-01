"""Drift / event callouts for INK DRIFT: TOKYO (Docs/DESIGN.md -> "Drift callout tiers").

Outputs (Game/Assets/InkDrift/Art/Callouts/), all 2048x1024 RGBA, all aligned to the same frame
so layers can be stacked/animated independently in Unity:
  callout_<id>.png        full composite (burst + text + fx)
  callout_<id>_text.png   JP + EN subtitle only
  callout_<id>_jp.png     JP lettering only (extrusion, strokes, drips)
  callout_<id>_en.png     EN ribbon + Bangers subtitle only
  callout_<id>_fx.png     splatter flecks / sparkles / confetti only
  burst_<style>.png       burst shape for each style, TINTABLE: white/grey fill + ink outline
                          (multiply by a colour in Unity; ink and shadows stay black)

usage: python gen_callouts.py [id ...]     (no args = everything)
"""
from __future__ import annotations

import math
import os
import sys
import time
from multiprocessing import Pool

import cv2
import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import *  # noqa

W, H = 2048, 1024
SS = 2
CX, CY = 1024, 500
OUT = os.path.join(ART, "Callouts")
INK = C("ink")
PAPER = C("paper")

# ------------------------------------------------------------------------------------
# Colour ramps per tier colour: (highlight, base, shadow-hue, extrusion)
# ------------------------------------------------------------------------------------
RAMPS = {
    "lime": ("#F6FFD6", "#B6FF3B", "#2FC43A", "#0E5A2C"),
    "cyan": ("#E2FDFF", "#00E5FF", "#0070FF", "#0A2E8A"),
    "yellow": ("#FFFCD6", "#FFE600", "#FF8A00", "#9A3300"),
    "magenta": ("#FFD6E8", "#FF2D7A", "#C0129C", "#4E0A5C"),
    "red": ("#FFE0D0", "#FF3B30", "#C2002E", "#4A0018"),
    "fail": ("#FFE3DC", "#E8584E", "#8A2A3C", "#2A1030"),
}


def ramp_cols(name):
    return [hexc(h) for h in RAMPS[name]]


# ------------------------------------------------------------------------------------
# Callout definitions
# runs: (text, scale, x_em, y_em) baseline positions in em of the base size
# ------------------------------------------------------------------------------------
CALLOUTS = {
    "nice": dict(runs=[("ナイス！", 1, 0, 0)], en="NICE!", color="lime", burst="pop", rot=-5, skew=-0.16,
                 box=(250, 150, 1800, 640), energy=1,
                 scheme=dict(outer="magenta", inner="sakura", core="paper", accent="cyan", lines="ink"),
                 banner=dict(band="ink", under="cyan", text="lime", rot=3, y=810)),
    "good": dict(runs=[("成功！", 1, 0, 0)], en="SUCCESS!", color="cyan", burst="spiky", rot=4, skew=-0.14,
                 box=(330, 140, 1720, 640), energy=2,
                 scheme=dict(outer="yellow", inner="paper", core="paper", accent="magenta", lines="ink"),
                 banner=dict(band="magenta", under="ink", text="paper", rot=-3, y=815)),
    "great": dict(runs=[("グレート", 0.78, 0.0, 0), ("ドリフト！", 1.0, 0.55, 1.02)], en="GREAT DRIFT!",
                  color="yellow", burst="star", rot=-6, skew=-0.18, box=(230, 70, 1800, 720), energy=3,
                  scheme=dict(outer="magenta", inner="cyan", core="cyan", accent="cyan", lines="ink"),
                  banner=dict(band="ink", under="cyan", text="yellow", rot=4, y=830)),
    "awesome": dict(runs=[("すごい！", 1, 0, 0)], en="AWESOME!", color="magenta", burst="boom", rot=-4, skew=-0.17,
                    box=(240, 140, 1800, 650), energy=4,
                    scheme=dict(outer="cyan", inner="yellow", core="paper", accent="indigo", lines="ink"),
                    banner=dict(band="ink", under="yellow", text="magenta", rot=-4, y=830)),
    "insane": dict(runs=[("やばい！！", 1, 0, 0)], en="INSANE!!", color="magenta", burst="shatter", rot=5, skew=-0.2,
                   box=(200, 130, 1840, 650), energy=5,
                   scheme=dict(outer="indigo", inner="cyan", core="paper", accent="yellow", lines="paper"),
                   banner=dict(band="yellow", under="magenta", text="ink", rot=-5, y=835)),
    "perfect": dict(runs=[("完璧！", 1, 0, 0)], en="PERFECT!", color="yellow", burst="sparkle", rot=-3, skew=-0.12,
                    box=(330, 130, 1720, 650), energy=5,
                    scheme=dict(outer="cyan", inner="indigo", core="magenta", accent="paper", lines="ink"),
                    banner=dict(band="magenta", under="ink", text="paper", rot=3, y=835)),
    "god": dict(runs=[("神", 1.9, 0.0, 0.62), ("ドリフト！！", 0.95, 1.95, 0.3)],
                en="GOD DRIFT!!", color="red", burst="god", rot=-5, skew=-0.16, box=(170, 70, 1880, 730),
                energy=7,
                scheme=dict(outer="red", inner="yellow", core="paper", accent="cyan", accent2="cyan", lines="ink"),
                banner=dict(band="ink", under="red", text="yellow", rot=4, y=830)),
    # ---- events ----
    "fail": dict(runs=[("失敗…", 1, 0, 0)], en="FAIL...", color="fail", burst="gloom", rot=6, skew=0.08,
                 box=(250, 190, 1800, 730), energy=0, droop=True,
                 scheme=dict(outer="indigo", inner="#2C2358", core="#3A3170", accent="#8C86B8", lines="paper"),
                 banner=dict(band="#5A5478", under="ink", text="paper", rot=-6, y=820)),
    "best_lap": dict(runs=[("最高！", 1, 0, 0)], en="BEST LAP!", color="yellow", burst="rosette", rot=-4,
                     skew=-0.14, box=(360, 150, 1690, 640), energy=4,
                     scheme=dict(outer="magenta", inner="indigo", core="#2A1F66", accent="cyan", lines="ink"),
                     banner=dict(band="cyan", under="ink", text="ink", rot=-3, y=830)),
    "new_record": dict(runs=[("新記録！", 1, 0, 0)], en="NEW RECORD!", color="magenta", burst="confetti", rot=4,
                       skew=-0.15, box=(260, 150, 1790, 640), energy=5,
                       scheme=dict(outer="yellow", inner="paper", core="paper", accent="cyan", lines="ink"),
                       banner=dict(band="ink", under="cyan", text="yellow", rot=-4, y=835)),
    "start": dict(runs=[("スタート！", 1, 0, 0)], en="START!", color="cyan", burst="speed", rot=-3, skew=-0.22,
                  box=(200, 200, 1840, 620), energy=3,
                  scheme=dict(outer="ink", inner="magenta", core="#3A2C8A", accent="paper", lines="cyan"),
                  banner=dict(band="yellow", under="ink", text="ink", rot=-3, y=820)),
    "count_3": dict(runs=[("3", 1, 0, 0)], en="THREE", color="cyan", burst="ring", rot=-4, skew=-0.1,
                    box=(700, 110, 1350, 760), energy=2, kana="さん！", kana_color="yellow",
                    scheme=dict(outer="magenta", inner="ink", core="indigo", accent="paper", lines="ink"),
                    banner=dict(band="ink", under="magenta", text="cyan", rot=-4, y=830)),
    "count_2": dict(runs=[("2", 1, 0, 0)], en="TWO", color="yellow", burst="ring", rot=3, skew=-0.1,
                    box=(700, 110, 1350, 760), energy=2, kana="に！", kana_color="magenta",
                    scheme=dict(outer="cyan", inner="ink", core="indigo", accent="paper", lines="ink"),
                    banner=dict(band="ink", under="cyan", text="yellow", rot=3, y=830)),
    "count_1": dict(runs=[("1", 1, 0, 0)], en="ONE", color="magenta", burst="ring", rot=-3, skew=-0.1,
                    box=(740, 110, 1310, 760), energy=3, kana="いち！", kana_color="cyan",
                    scheme=dict(outer="yellow", inner="ink", core="indigo", accent="paper", lines="ink"),
                    banner=dict(band="ink", under="yellow", text="magenta", rot=-3, y=830)),
    "go": dict(runs=[("ゴー！", 1, 0, 0)], en="GO!!", color="lime", burst="boom", rot=-6, skew=-0.2,
               box=(300, 110, 1760, 660), energy=6,
               scheme=dict(outer="magenta", inner="indigo", core="cyan", accent="yellow", lines="ink"),
               banner=dict(band="yellow", under="ink", text="ink", rot=-4, y=830)),
    "final_lap": dict(runs=[("ファイナル", 0.82, 0.0, 0), ("ラップ！", 1.0, 1.5, 1.0)], en="FINAL LAP!",
                      color="magenta", burst="slash", rot=-5, skew=-0.2, box=(250, 120, 1800, 770), energy=4,
                      scheme=dict(outer="ink", inner="cyan", core="paper", core2="#3A2C8A", accent="yellow", lines="ink"),
                      banner=dict(band="yellow", under="ink", text="ink", rot=4, y=830)),
    "goal": dict(runs=[("ゴール！", 1, 0, 0)], en="GOAL!", color="yellow", burst="checker", rot=-4, skew=-0.16,
                 box=(260, 140, 1790, 650), energy=5,
                 scheme=dict(outer="paper", inner="magenta", core="ink", accent="cyan", lines="ink"),
                 banner=dict(band="ink", under="magenta", text="yellow", rot=3, y=830)),
    "drift_king": dict(runs=[("ドリフト", 0.86, 0.0, 0), ("キング！", 1.0, 0.95, 1.02)], en="DRIFT KING!",
                       color="yellow", burst="crown", rot=-4, skew=-0.15, box=(270, 150, 1780, 760), energy=6,
                       scheme=dict(outer="indigo", inner="magenta", core="#2A1F66", accent="cyan", lines="ink"),
                       banner=dict(band="magenta", under="ink", text="paper", rot=3, y=830)),
    "ikee": dict(runs=[("いけー！", 1, 0, 0)], en="GO!! GO!!", color="red", burst="flame", rot=-6, skew=-0.2,
                 box=(270, 170, 1780, 660), energy=5,
                 scheme=dict(outer="red", inner="#FF8A00", core="yellow", accent="paper", lines="ink"),
                 banner=dict(band="ink", under="yellow", text="paper", rot=-3, y=830)),
    "near_miss": dict(runs=[("ニアミス！", 1, 0, 0)], en="NEAR MISS!", color="yellow", burst="spark", rot=5,
                      skew=-0.18, box=(220, 170, 1830, 630), energy=4,
                      scheme=dict(outer="cyan", inner="indigo", core="#2A1F66", accent="yellow", lines="ink"),
                      banner=dict(band="ink", under="cyan", text="yellow", rot=-4, y=820)),
    "overtake": dict(runs=[("オーバー", 0.84, 0.0, 0), ("テイク！", 1.0, 1.05, 1.02)], en="OVERTAKE!",
                     color="cyan", burst="arrow", rot=-4, skew=-0.2, box=(260, 80, 1780, 720), energy=5,
                     scheme=dict(outer="magenta", inner="#2A1F66", core="yellow", accent="cyan", lines="ink"),
                     banner=dict(band="yellow", under="ink", text="ink", rot=3, y=830)),
}

TINT_SCHEME = dict(outer="#FFFFFF", inner="#D6D6D6", core="#F2F2F2", accent="#B4B4B4", lines="#FFFFFF",
                   shade="#9A9A9A")


def col(name):
    if isinstance(name, np.ndarray):
        return name
    if name.startswith("#"):
        return hexc(name)
    return C(name)


# ------------------------------------------------------------------------------------
# Extra shapes
# ------------------------------------------------------------------------------------
def sparkle(cx, cy, R, r_ratio=0.18, rot=0.0) -> skia.Path:
    """4-point manga sparkle with concave flanks."""
    p = skia.Path()
    pts = []
    for i in range(4):
        a = rot + i * math.pi / 2
        pts.append((cx + math.cos(a) * R, cy + math.sin(a) * R))
    p.moveTo(*pts[0])
    k = R * r_ratio
    for i in range(4):
        a = rot + (i + 0.5) * math.pi / 2
        ctrl = (cx + math.cos(a) * k, cy + math.sin(a) * k)
        p.quadTo(*ctrl, *pts[(i + 1) % 4])
    p.close()
    return p


BOLT = [(0.52, 0.0), (0.12, 0.52), (0.42, 0.50), (0.18, 1.0), (0.88, 0.36), (0.56, 0.38), (0.86, 0.0)]


def bolt(cx, cy, size, angle=0.0, flip=False) -> skia.Path:
    """Classic comic lightning bolt (zig-zag, thick top -> sharp tip), centred at cx,cy."""
    pts = [((1 - x) if flip else x, y) for x, y in BOLT]
    p = poly([((x - 0.5) * size * 0.62, (y - 0.5) * size) for x, y in pts])
    m = skia.Matrix(); m.setRotate(angle); m.postTranslate(cx, cy)
    p.transform(m)
    return p


def shard(cx, cy, size, r, angle=None):
    a = r.uniform(0, 2 * math.pi) if angle is None else angle
    pts = [(cx + math.cos(a) * size * 1.7, cy + math.sin(a) * size * 1.7)]
    for o, k in ((2.1, 0.7), (3.0, 0.9), (4.1, 0.75)):
        aa = a + o + r.uniform(-0.25, 0.25)
        pts.append((cx + math.cos(aa) * size * k, cy + math.sin(aa) * size * k))
    return poly(pts)


def blob_polygon(cx, cy, rx, ry, n, r, jit=0.25, rot=0.0):
    pts = []
    for i in range(n):
        a = rot + 2 * math.pi * (i + r.uniform(-0.3, 0.3)) / n
        k = 1 + r.uniform(-jit, jit)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return pts


def flame_tongue(bx, by, ang, length, width, curl, r) -> skia.Path:
    """Flame lick from base (bx,by) pointing along ang (rad), with curling tip."""
    ux, uy = math.cos(ang), math.sin(ang)
    nx, ny = -uy, ux
    tipx = bx + ux * length + nx * curl * length
    tipy = by + uy * length + ny * curl * length
    w = width / 2
    p = skia.Path()
    p.moveTo(bx - nx * w, by - ny * w)
    p.cubicTo(bx - nx * w * 1.3 + ux * length * 0.35, by - ny * w * 1.3 + uy * length * 0.35,
              tipx - ux * length * 0.35 - nx * w * 0.6, tipy - uy * length * 0.35 - ny * w * 0.6,
              tipx, tipy)
    p.cubicTo(tipx - ux * length * 0.25 + nx * w * 0.5, tipy - uy * length * 0.25 + ny * w * 0.5,
              bx + nx * w * 1.2 + ux * length * 0.45, by + ny * w * 1.2 + uy * length * 0.45,
              bx + nx * w, by + ny * w)
    p.close()
    return p


def crown_path(cx, base_y, w, h) -> tuple:
    """Crown silhouette: returns (body_path, list_of_tip_balls, band_rect_path)."""
    pts = [(cx - w / 2, base_y)]
    tips = 5
    for i in range(tips):
        t = i / (tips - 1)
        x = cx - w / 2 + w * t
        th = h * (1.0 if i in (0, 4) else (1.18 if i == 2 else 0.98))
        if i > 0:
            vx = cx - w / 2 + w * (i - 0.5) / (tips - 1)
            pts.append((vx, base_y - h * 0.42))
        pts.append((x + (w * 0.04 if i == 0 else -w * 0.04 if i == 4 else 0), base_y - th))
    pts.append((cx + w / 2, base_y))
    body = poly(pts)
    balls = []
    for i in range(tips):
        t = i / (tips - 1)
        x = cx - w / 2 + w * t + (w * 0.04 if i == 0 else -w * 0.04 if i == 4 else 0)
        th = h * (1.0 if i in (0, 4) else (1.18 if i == 2 else 0.98))
        balls.append((x, base_y - th, h * 0.085))
    band = rect(cx - w / 2 - w * 0.03, base_y - h * 0.18, cx + w / 2 + w * 0.03, base_y + h * 0.12, h * 0.04)
    return body, balls, band


# ------------------------------------------------------------------------------------
# Burst styles -> list of ops
#   ('body', mask, role, dict(shade=, shadow=, outline=))  bordered filled shape
#   ('flat', mask, role)                                    plain fill (lines, stripes)
# Geometry in design units; masks at internal res.
# ------------------------------------------------------------------------------------
def B_lines(cv, r, inner, count, width, outer=468, aspect=2.12, cx=CX, cy=CY):
    """Manga focus lines ending on an (irregular) ellipse that fits inside the canvas."""
    p = skia.Path()
    for i in range(count):
        a = r.uniform(0, 2 * math.pi)
        ro = outer * r.uniform(0.86, 1.0)
        ri = outer * inner * r.uniform(0.75, 1.25)
        w = width * r.uniform(0.35, 1.6)
        q = wedge(0, 0, a, ri, ro, 0.0, w)
        q.transform(skia.Matrix.Scale(aspect, 1.0))
        q.offset(cx, cy)
        p.addPath(q)
    return cv.mask(p)


def clamp_to_canvas(cv, m, margin=10):
    """Fade mask to zero near canvas border so nothing is hard-clipped."""
    H_, W_ = m.shape
    mg = int(margin * cv.ss)
    yy = np.arange(H_)[:, None]; xx = np.arange(W_)[None, :]
    d = np.minimum(np.minimum(xx, W_ - 1 - xx), np.minimum(yy, H_ - 1 - yy)).astype(np.float32)
    return m * np.clip((d - mg) / (mg + 1), 0, 1)


def burst_pop(cv, r):
    ops = []
    parts = scallop_cloud(CX, CY + 10, 600, 300, bumps=15, bump=0.30, r=r, jitter=0.3)
    B = cv.mask(parts)
    ops.append(("body", B, "outer", dict(shade=0.5)))
    inner = scallop_cloud(CX - 30, CY - 10, 470, 225, bumps=13, bump=0.26, r=rng(11), jitter=0.3)
    I = cv.mask(inner)
    ops.append(("body", I, "inner", dict(shade=0.35, outline=0, shadow=None)))
    # satellite puffs
    sat = [circle(CX - 610, CY + 290, 46), circle(CX - 700, CY + 360, 28), circle(CX + 640, CY - 300, 40),
           circle(CX + 720, CY - 360, 22)]
    ops.append(("body", cv.mask(sat), "outer", dict(shade=0.2)))
    return ops


def burst_spiky(cv, r):
    ops = []
    L = B_lines(cv, r, 0.57, 70, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(jagged_ellipse(CX, CY, 780, 370, teeth=30, depth=0.16, r=r, jitter=0.45))
    ops.append(("body", B, "outer", dict(shade=0.55)))
    I = cv.mask(jagged_ellipse(CX, CY - 8, 640, 290, teeth=26, depth=0.09, r=rng(21), jitter=0.4))
    ops.append(("body", I, "inner", dict(shade=0.3, outline=6, shadow=None)))
    return ops


def burst_star(cv, r):
    ops = []
    L = B_lines(cv, r, 0.6, 90, 16)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(starburst(CX, CY, 920, 460, n=22, inner=0.72, jitter=0.16, r=r, curve=0.06,
                          long_every=2, long_amt=0.1))
    ops.append(("body", B, "outer", dict(shade=0.55)))
    I = cv.mask(starburst(CX, CY + 6, 760, 350, n=20, inner=0.82, jitter=0.12, r=rng(31), rot=0.08, curve=0.04))
    ops.append(("body", I, "inner", dict(shade=0.5, outline=8, shadow=(12, 14))))
    return ops


def burst_boom(cv, r):
    ops = []
    L = B_lines(cv, r, 0.55, 120, 18)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(starburst(CX, CY, 860, 440, n=17, inner=0.6, jitter=0.45, r=r, curve=0.42,
                          long_every=3, long_amt=0.25))
    ops.append(("body", B, "outer", dict(shade=0.55)))
    I = cv.mask(starburst(CX, CY, 720, 350, n=15, inner=0.7, jitter=0.35, r=rng(41), rot=0.2, curve=0.18))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=8, shadow=(12, 14))))
    K = cv.mask(starburst(CX, CY + 5, 580, 262, n=13, inner=0.78, jitter=0.28, r=rng(42), rot=0.5, curve=0.12))
    ops.append(("body", K, "core", dict(shade=0.35, outline=7, shadow=None)))
    return ops


def burst_shatter(cv, r):
    ops = []
    L = B_lines(cv, r, 0.48, 160, 20)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    # main jagged polygon with very sharp irregular spikes
    pts = []
    n = 26
    for i in range(n):
        a = 2 * math.pi * i / n + r.uniform(-0.08, 0.08)
        k = r.uniform(0.62, 0.78) if i % 2 else r.uniform(0.92, 1.12)
        if i % 5 == 0:
            k += 0.1
        pts.append((CX + math.cos(a) * 860 * k, CY + math.sin(a) * 430 * k))
    B = cv.mask(poly(pts))
    ops.append(("body", B, "outer", dict(shade=0.6)))
    # glass shards flying out
    shards = []
    for i in range(16):
        a = r.uniform(0, 2 * math.pi)
        d = r.uniform(0.95, 1.12)
        x, y = CX + math.cos(a) * 840 * d, CY + math.sin(a) * 420 * d
        s = r.uniform(26, 60)
        tri = [(x + math.cos(a + o) * s * k, y + math.sin(a + o) * s * k)
               for o, k in ((0, 1.6), (2.2 + r.uniform(-.3, .3), 0.8), (4.0 + r.uniform(-.3, .3), 0.9))]
        shards.append(poly(tri))
    S = clamp_to_canvas(cv, cv.mask(shards), 16)
    ops.append(("body", S, "inner", dict(shade=0.2, outline=6, shadow=(8, 10))))
    # inner crack shape
    pts2 = []
    for i in range(18):
        a = 2 * math.pi * i / 18 + r.uniform(-0.1, 0.1)
        k = r.uniform(0.7, 0.8) if i % 2 else r.uniform(0.9, 1.0)
        pts2.append((CX + math.cos(a) * 700 * k, CY + math.sin(a) * 320 * k))
    I = cv.mask(poly(pts2))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=7, shadow=(14, 16))))
    # lightning bolts
    bolts = [bolt(CX - 700, CY - 260, 230, -25), bolt(CX + 760, CY + 250, 210, 155, True),
             bolt(CX + 640, CY - 330, 150, 20, True)]
    ops.append(("body", cv.mask(bolts), "accent", dict(shade=0.0, outline=7, shadow=(10, 10))))
    return ops


def burst_sparkle(cv, r):
    ops = []
    L = B_lines(cv, r, 0.55, 110, 12)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    # big 8-point star: 4 long + 4 short
    p = skia.Path()
    pts = []
    for i in range(16):
        a = 2 * math.pi * i / 16 - math.pi / 2
        if i % 4 == 0:
            k = 1.0
        elif i % 2 == 0:
            k = 0.78
        else:
            k = 0.6
        pts.append((CX + math.cos(a) * 980 * k, CY + math.sin(a) * 480 * k))
    B = cv.mask(starburst(CX, CY, 900, 450, n=32, inner=0.84, jitter=0.12, r=r, long_every=4, long_amt=0.1))
    B = np.maximum(B, cv.mask(smooth_closed(pts, 0.0)))
    ops.append(("body", B, "outer", dict(shade=0.5)))
    I = cv.mask(ellipse(CX, CY, 700, 300))
    I = np.maximum(I, cv.mask(starburst(CX, CY, 740, 330, n=28, inner=0.9, jitter=0.1, r=rng(61))))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=8, shadow=(12, 14))))
    # big sparkles at corners
    sp = [sparkle(CX - 820, CY - 300, 120), sparkle(CX + 840, CY + 260, 100), sparkle(CX + 720, CY - 380, 64),
          sparkle(CX - 700, CY + 380, 58), sparkle(CX - 920, CY + 60, 40)]
    ops.append(("body", clamp_to_canvas(cv, cv.mask(sp)), "core", dict(shade=0.0, outline=7, shadow=(8, 8))))
    return ops


def burst_god(cv, r):
    ops = []
    L = B_lines(cv, r, 0.36, 260, 26)
    ops.append(("flat", clamp_to_canvas(cv, L, 6), "lines"))
    L2 = B_lines(cv, rng(71), 0.5, 80, 10)
    ops.append(("flat", clamp_to_canvas(cv, L2, 6), "accent"))
    B = cv.mask(starburst(CX, CY, 900, 445, n=20, inner=0.6, jitter=0.32, r=r, curve=0.22,
                          long_every=2, long_amt=0.16))
    ops.append(("body", B, "outer", dict(shade=0.6, shadow=(22, 26))))
    I = cv.mask(starburst(CX, CY, 770, 375, n=18, inner=0.7, jitter=0.28, r=rng(72), rot=0.15, curve=0.12,
                          long_every=3, long_amt=0.14))
    ops.append(("body", I, "inner", dict(shade=0.5, outline=9, shadow=(16, 18))))
    K = cv.mask(starburst(CX, CY - 40, 540, 230, n=16, inner=0.8, jitter=0.2, r=rng(73), rot=0.4, curve=0.08))
    ops.append(("body", K, "core", dict(shade=0.4, outline=8, shadow=(12, 14))))
    bolts = [bolt(CX - 760, CY - 280, 250, -35), bolt(CX + 770, CY - 270, 240, 35, True),
             bolt(CX - 720, CY + 300, 180, -145, True), bolt(CX + 730, CY + 300, 170, 145)]
    ops.append(("body", clamp_to_canvas(cv, cv.mask(bolts), 8), "accent2", dict(shade=0.0, outline=9, shadow=(12, 14))))
    rr = rng(78)
    deb = []
    for i in range(16):
        a = rr.uniform(0, 2 * math.pi)
        d = rr.uniform(0.95, 1.08)
        x, y = CX + math.cos(a) * 880 * d, CY + math.sin(a) * 430 * d
        deb.append(shard(x, y, rr.uniform(14, 30), rr, angle=a))
    ops.append(("body", clamp_to_canvas(cv, cv.mask(deb), 12), "core", dict(shade=0.0, outline=6, shadow=(6, 8))))
    return ops


def burst_gloom(cv, r):
    """Fail: deflated, melting dark blob with manga gloom lines and a crack."""
    ops = []
    pts = []
    n = 22
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + 0.05 * math.sin(a * 5 + 1.3) + r.uniform(-0.03, 0.03)
        y = math.sin(a) * 300 * k
        if y > 0:  # sag the bottom
            y *= 1.0 + 0.18 * (1 - abs(math.cos(a)))
        pts.append((CX + math.cos(a) * 640 * k, CY + 30 + y * 0.9))
    body = [smooth_closed(pts, 0.9)]
    # melting drips off the bottom
    rr = rng(81)
    for x, L_, w in ((CX - 430, 110, 48), (CX - 180, 170, 60), (CX + 90, 90, 40), (CX + 300, 150, 54),
                     (CX + 500, 70, 34)):
        y0 = CY + 20 + 300 * math.sqrt(max(0.0, 1 - ((x - CX) / 700) ** 2)) * 1.12 - 40
        body += drip_paths(x, y0, w, L_, rr, bulb=1.3)
    B = cv.mask(body)
    ops.append(("body", B, "outer", dict(shade=0.55, shadow=(14, 18))))
    I = cv.mask(smooth_closed([(CX + (x - CX) * 0.82, CY + 10 + (y - CY - 20) * 0.74) for x, y in pts], 0.9))
    ops.append(("body", I, "inner", dict(shade=0.35, outline=0, shadow=None)))
    # vertical gloom lines (縦線) hanging from the top, inside the blob
    gl = skia.Path()
    for i in range(46):
        x = CX - 600 + i * 26 + rr.uniform(-6, 6)
        top = CY - 330
        Ln = rr.uniform(140, 380)
        w = rr.uniform(3, 7)
        gl.addPath(poly([(x - w / 2, top), (x + w / 2, top), (x, top + Ln)]))
    G = cv.mask(gl) * B
    ops.append(("flat", G, "lines"))
    # crack
    crack = []
    x, y = CX - 520, CY - 200
    pts_c = [(x, y)]
    for i in range(9):
        x += rr.uniform(90, 140); y += rr.uniform(-60, 80)
        pts_c.append((x, y))
    cp = skia.Path(); cp.moveTo(*pts_c[0])
    for q in pts_c[1:]:
        cp.lineTo(*q)
    ops.append(("flat", cv.mask(cp, stroke=9, fill=False, join="miter") * B, "accent"))
    # sweat drops
    drops = []
    for (x, y, s, a) in ((CX + 720, CY - 300, 46, 0.5), (CX + 790, CY - 190, 30, 0.7), (CX - 760, CY - 260, 36, -0.5)):
        d = skia.Path()
        d.moveTo(x, y - s * 1.6)
        d.cubicTo(x + s * 0.2, y - s * 0.9, x + s, y - s * 0.3, x + s, y + s * 0.2)
        d.cubicTo(x + s, y + s * 0.85, x - s, y + s * 0.85, x - s, y + s * 0.2)
        d.cubicTo(x - s, y - s * 0.3, x - s * 0.2, y - s * 0.9, x, y - s * 1.6)
        d.close()
        mr = skia.Matrix(); mr.setRotate(math.degrees(a * 0.4), x, y)
        d.transform(mr)
        drops.append(d)
    ops.append(("body", cv.mask(drops), "core", dict(shade=0.0, outline=6, shadow=None)))
    return ops


def burst_rosette(cv, r):
    ops = []
    L = B_lines(cv, r, 0.56, 80, 12)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    # ribbon tails behind
    tails = []
    for sgn in (-1, 1):
        x = CX + sgn * 300
        t = poly([(x - 90, CY + 200), (x + 90, CY + 200), (x + 90 + sgn * 70, CY + 470),
                  (x + sgn * 40, CY + 410), (x - 90 + sgn * 70, CY + 480)])
        tails.append(t)
    ops.append(("body", cv.mask(tails), "accent", dict(shade=0.45, shadow=(10, 12))))
    # scalloped rosette ring
    parts = [ellipse(CX, CY, 760, 380)]
    nb = 34
    for i in range(nb):
        a = 2 * math.pi * i / nb
        parts.append(ellipse(CX + math.cos(a) * 760, CY + math.sin(a) * 380, 74, 60))
    B = cv.mask(parts)
    ops.append(("body", B, "outer", dict(shade=0.5)))
    # pleat lines on ring
    pl = skia.Path()
    for i in range(nb):
        a = 2 * math.pi * (i + 0.5) / nb
        pl.addPath(wedge(CX, CY, a, 0, 840, 0, 10))
    pl.transform(skia.Matrix.Scale(1.0, 1.0))
    PL = cv.mask(pl)
    ring_in = cv.mask(ellipse(CX, CY, 640, 300))
    ops.append(("flat", PL * B * (1 - ring_in) * 0.35, "lines"))
    I = cv.mask(ellipse(CX, CY, 650, 305))
    ops.append(("body", I, "inner", dict(shade=0.4, outline=9, shadow=None)))
    I2 = cv.mask(ellipse(CX, CY, 600, 268), stroke=6, fill=False)
    ops.append(("flat", I2, "accent"))
    return ops


def burst_confetti(cv, r):
    ops = []
    L = B_lines(cv, r, 0.59, 90, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(jagged_ellipse(CX, CY, 800, 380, teeth=22, depth=0.2, r=r, jitter=0.5))
    ops.append(("body", B, "outer", dict(shade=0.5)))
    I = cv.mask(jagged_ellipse(CX, CY, 660, 300, teeth=20, depth=0.1, r=rng(91), jitter=0.4))
    ops.append(("body", I, "inner", dict(shade=0.3, outline=7, shadow=(10, 12))))
    return ops


def burst_speed(cv, r):
    ops = []
    # horizontal speed streaks
    sp = skia.Path()
    rr = rng(101)
    for i in range(70):
        y = rr.uniform(CY - 420, CY + 420)
        x1 = rr.uniform(1400, 2020)
        Ln = rr.uniform(300, 1300)
        w = rr.uniform(4, 16)
        sp.addPath(poly([(x1 - Ln, y), (x1, y - w / 2), (x1, y + w / 2)]))
    ops.append(("flat", clamp_to_canvas(cv, cv.mask(sp), 8), "lines"))
    under = poly([(150, CY - 250), (2000, CY - 330), (1880, CY + 240), (40, CY + 300)])
    ops.append(("body", cv.mask(under), "inner", dict(shade=0.5, shadow=(16, 18))))
    slab = poly([(120, CY - 290), (1950, CY - 280), (1880, CY + 250), (60, CY + 230)])
    SL = cv.mask(slab)
    ops.append(("body", SL, "outer", dict(shade=0.0, shadow=None)))
    # halftone glow fading from the right on the slab + inner pinstripe
    val = cv.ramp((700, 0), (1900, 0)) ** 1.3 * 0.6
    ops.append(("flat", SL * cv.halftone(val, 16, 45), "core"))
    ops.append(("flat", SL * (1 - cv.erode(SL, 16)) * cv.erode(SL, 10), "lines"))
    # chevrons at the right end of slab
    ch = skia.Path()
    for i in range(3):
        x = 1660 + i * 90
        ch.addPath(poly([(x, CY - 160), (x + 60, CY - 160), (x + 150, CY - 20), (x + 60, CY + 120), (x, CY + 120),
                         (x + 90, CY - 20)]))
    ops.append(("flat", cv.mask(ch), "accent"))
    stripe = cv.mask(poly([(120, CY - 290), (1950, CY - 280), (1948, CY - 262), (119, CY - 270)]))
    ops.append(("flat", stripe, "lines"))
    return ops


def burst_ring(cv, r):
    ops = []
    L = B_lines(cv, r, 0.47, 70, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    R = 455
    B = cv.mask(circle(CX, CY, R))
    ops.append(("body", B, "outer", dict(shade=0.5)))
    I = cv.mask(circle(CX, CY, R - 70))
    ops.append(("body", I, "inner", dict(shade=0.0, outline=8, shadow=None)))
    K = cv.mask(circle(CX, CY, R - 110))
    ops.append(("body", K, "core", dict(shade=0.5, outline=0, shadow=None)))
    # ticks
    tk = skia.Path()
    for i in range(60):
        a = 2 * math.pi * i / 60
        long = (i % 5 == 0)
        tk.addPath(wedge(CX, CY, a, R - 102 + (0 if long else 16), R - 76, 10 if long else 6, 10 if long else 6))
    ops.append(("flat", cv.mask(tk), "accent"))
    return ops


def burst_slash(cv, r):
    ops = []
    sp = skia.Path()
    rr = rng(111)
    for i in range(60):
        y = rr.uniform(80, 940)
        x1 = rr.uniform(1300, 2010)
        Ln = rr.uniform(260, 1000)
        w = rr.uniform(3, 12)
        sp.addPath(poly([(x1 - Ln, y), (x1, y - w / 2), (x1, y + w / 2)]))
    ops.append(("flat", clamp_to_canvas(cv, cv.mask(sp), 8), "lines"))
    s1 = poly([(80, 330), (1950, 90), (1990, 400), (110, 650)])
    ops.append(("body", cv.mask(s1), "inner", dict(shade=0.5, shadow=(16, 18))))
    s2 = poly([(60, 520), (1960, 380), (1940, 760), (90, 900)])
    S2 = cv.mask(s2)
    ops.append(("body", S2, "outer", dict(shade=0.0, shadow=(16, 18))))
    val = cv.ramp((300, 0), (1700, 0)) ** 1.2 * 0.55
    ops.append(("flat", S2 * cv.halftone(val, 16, 45), "core2"))
    # checker strip along slab 2 bottom
    xx, yy = coords(cv.H, cv.W)
    s = cv.ss
    # strip band along line from (90,900) to (1940,760) -> local coordinates
    ang = math.atan2(760 - 900, 1940 - 90)
    u = ((xx / s - 90) * math.cos(ang) + (yy / s - 900) * math.sin(ang))
    v = (-(xx / s - 90) * math.sin(ang) + (yy / s - 900) * math.cos(ang))
    cell = 34
    chk = np.clip(0.5 + 40 * np.sin(math.pi * u / cell) * np.sin(math.pi * v / cell), 0, 1)
    band = ((v > -72) & (v < -4)).astype(np.float32)
    ops.append(("flat", chk * band * S2, "accent"))
    return ops


def burst_checker(cv, r):
    ops = []
    L = B_lines(cv, r, 0.59, 100, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(starburst(CX, CY, 900, 450, n=20, inner=0.72, jitter=0.35, r=r, curve=0.2, long_every=3,
                          long_amt=0.12))
    ops.append(("body", B, "outer", dict(shade=0.0)))
    xx, yy = coords(cv.H, cv.W)
    s = cv.ss
    u = xx / s + 26 * np.sin(yy / s / 140.0)
    v = yy / s + 30 * np.sin(xx / s / 170.0 + 1.0)
    cell = 64
    chk = np.clip(0.5 + 30 * np.sin(math.pi * u / cell) * np.sin(math.pi * v / cell), 0, 1)
    # ripple shading
    rip = 0.5 + 0.5 * np.sin(xx / s / 170.0 + 1.0)
    ops.append(("flat", chk * B, "ink"))
    ops.append(("flat", B * (rip > 0.75) * 0.18, "inner"))
    I = cv.mask(jagged_ellipse(CX, CY - 20, 600, 250, teeth=24, depth=0.1, r=rng(121), jitter=0.4))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=9, shadow=(14, 16))))
    return ops


def burst_crown(cv, r):
    ops = []
    L = B_lines(cv, r, 0.55, 110, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(starburst(CX, CY + 60, 880, 400, n=26, inner=0.8, jitter=0.25, r=r, long_every=2, long_amt=0.1))
    ops.append(("body", B, "outer", dict(shade=0.55)))
    I = cv.mask(starburst(CX, CY + 70, 720, 320, n=22, inner=0.86, jitter=0.18, r=rng(131)))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=8, shadow=(12, 14))))
    body, balls, band = crown_path(CX - 380, 250, 440, 230)
    crown = [transformed(body, rotate=-14, pivot=(CX - 380, 200))]
    crown += [transformed(circle(x, y, rr_), rotate=-14, pivot=(CX - 380, 200)) for x, y, rr_ in balls]
    crown += [transformed(band, rotate=-14, pivot=(CX - 380, 200))]
    Cm = cv.mask(crown)
    ops.append(("body", Cm, "crown", dict(shade=0.45, outline=10, shadow=(12, 14))))
    jew = [transformed(circle(CX - 380 + dx, 250 - 18, 20), rotate=-14, pivot=(CX - 380, 200))
           for dx in (-145, 0, 145)]
    ops.append(("body", cv.mask(jew), "accent", dict(shade=0.0, outline=5, shadow=None)))
    band_line = cv.mask(transformed(band, rotate=-14, pivot=(CX - 380, 200)), stroke=8, fill=False)
    ops.append(("flat", band_line, "ink"))
    sp = [sparkle(CX + 760, CY - 270, 90), sparkle(CX - 820, CY + 280, 70), sparkle(CX + 860, CY + 200, 50),
          sparkle(CX - 640, CY - 380, 40), sparkle(CX + 420, CY - 400, 46)]
    ops.append(("body", clamp_to_canvas(cv, cv.mask(sp)), "spark", dict(shade=0.0, outline=6, shadow=(6, 6))))
    return ops


def flame_ring(cx, cy, rx, ry, n, r, inner=0.6, curl=0.35, jit=0.25, rot=0.0, up=0.25):
    """Swirling fireball: ring of curved flame tongues (all curling the same way), biased upward."""
    parts = [ellipse(cx, cy, rx * inner * 1.05, ry * inner * 1.05)]
    for i in range(n):
        a = rot + 2 * math.pi * (i + r.uniform(-0.2, 0.2)) / n
        upk = 1 + up * max(0.0, -math.sin(a))  # longer flames on top
        L = (1 + r.uniform(-jit, jit)) * upk
        half = math.pi / n * 1.25
        b0 = (cx + math.cos(a - half) * rx * inner, cy + math.sin(a - half) * ry * inner)
        b1 = (cx + math.cos(a + half) * rx * inner, cy + math.sin(a + half) * ry * inner)
        ta = a + curl * 0.9
        tip = (cx + math.cos(ta) * rx * L, cy + math.sin(ta) * ry * L)
        ma = a + curl * 0.35
        mid_out = (cx + math.cos(ma + half * 0.6) * rx * (inner + (L - inner) * 0.55),
                   cy + math.sin(ma + half * 0.6) * ry * (inner + (L - inner) * 0.55))
        mid_in = (cx + math.cos(ma - half * 0.2) * rx * (inner + (L - inner) * 0.45),
                  cy + math.sin(ma - half * 0.2) * ry * (inner + (L - inner) * 0.45))
        p = skia.Path()
        p.moveTo(*b0)
        p.quadTo(*mid_in, *tip)
        p.quadTo(*mid_out, *b1)
        p.close()
        parts.append(p)
    return parts


def burst_flame(cv, r):
    ops = []
    L = B_lines(cv, r, 0.55, 90, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    B = cv.mask(flame_ring(CX, CY + 20, 900, 450, 15, rng(142), inner=0.55, curl=0.45, jit=0.2))
    ops.append(("body", B, "outer", dict(shade=0.5)))
    I = cv.mask(flame_ring(CX, CY + 30, 740, 360, 13, rng(143), inner=0.6, curl=0.5, jit=0.18, rot=0.2))
    ops.append(("body", I, "inner", dict(shade=0.4, outline=7, shadow=(10, 12))))
    K = cv.mask(flame_ring(CX, CY + 40, 590, 280, 11, rng(144), inner=0.66, curl=0.55, jit=0.15, rot=0.45))
    ops.append(("body", K, "core", dict(shade=0.3, outline=6, shadow=None)))
    rr = rng(141)
    em = skia.Path()
    for i in range(26):
        a = rr.uniform(0, 2 * math.pi)
        d = rr.uniform(0.95, 1.12)
        em.addPath(sparkle(CX + math.cos(a) * 880 * d, CY + math.sin(a) * 430 * d, rr.uniform(8, 20)))
    ops.append(("body", clamp_to_canvas(cv, cv.mask(em)), "core", dict(shade=0.0, outline=4, shadow=None)))
    return ops


def burst_spark(cv, r):
    ops = []
    L = B_lines(cv, r, 0.55, 90, 14)
    ops.append(("flat", clamp_to_canvas(cv, L), "lines"))
    # hazard stripe band behind
    band = poly([(70, CY + 170), (1990, CY - 40), (1990, CY + 120), (70, CY + 330)])
    Bd = cv.mask(band)
    ops.append(("body", Bd, "core", dict(shade=0.0, shadow=(12, 14))))
    hz = cv.halftone(np.float32(0.5), 70, -40, shape="line")
    ops.append(("flat", hz * Bd, "accent"))
    # electric jagged outline
    pts = []
    n = 64
    for i in range(n):
        a = 2 * math.pi * i / n
        k = (1.08 if i % 2 == 0 else 0.9) + r.uniform(-0.06, 0.06)
        if i % 8 == 0:
            k += 0.12
        pts.append((CX + math.cos(a) * 820 * k, CY + math.sin(a) * 340 * k))
    B = cv.mask(poly(pts))
    ops.append(("body", B, "outer", dict(shade=0.5)))
    I = cv.mask(ellipse(CX, CY, 690, 270))
    ops.append(("body", I, "inner", dict(shade=0.45, outline=8, shadow=(12, 14))))
    bolts = [bolt(CX - 840, CY - 250, 220, -30), bolt(CX + 850, CY - 260, 220, 30, True),
             bolt(CX + 800, CY + 300, 170, 150)]
    ops.append(("body", clamp_to_canvas(cv, cv.mask(bolts), 8), "accent", dict(shade=0.0, outline=7, shadow=(8, 8))))
    return ops


def burst_arrow(cv, r):
    ops = []
    sp = skia.Path()
    rr = rng(161)
    for i in range(80):
        y = rr.uniform(90, 930)
        x1 = rr.uniform(700, 1500)
        Ln = rr.uniform(260, 900)
        w = rr.uniform(3, 12)
        sp.addPath(poly([(max(30, x1 - Ln), y), (x1, y - w / 2), (x1, y + w / 2)]))
    ops.append(("flat", clamp_to_canvas(cv, cv.mask(sp), 8), "lines"))
    # trailing chevrons
    ch = []
    for i, x in enumerate((70, 250)):
        th = 110
        ch.append(poly([(x, 250), (x + th, 250), (x + th + 200, CY), (x + th, 750), (x, 750), (x + 200, CY)]))
    ops.append(("body", cv.mask(ch), "core", dict(shade=0.4, shadow=(12, 14))))
    # giant block arrow
    arrow = poly([(470, 300), (1380, 270), (1360, 90), (1990, CY), (1360, 910), (1380, 730), (470, 700),
                  (560, CY)])
    A = cv.mask(arrow)
    ops.append(("body", A, "outer", dict(shade=0.55, shadow=(18, 22))))
    inner = poly([(620, 360), (1440, 335), (1430, 220), (1840, CY), (1430, 780), (1440, 665), (620, 640),
                   (690, CY)])
    ops.append(("body", cv.mask(inner), "inner", dict(shade=0.0, outline=0, shadow=None)))
    hl = cv.mask(inner, stroke=10, fill=False, join="miter")
    ops.append(("flat", hl, "accent"))
    return ops


BURST_DRIPS = {"pop": 2, "spiky": 2, "star": 3, "boom": 3, "shatter": 0, "sparkle": 0, "god": 0, "gloom": 0,
               "rosette": 0, "confetti": 3, "speed": 3, "ring": 2, "slash": 3, "checker": 0, "crown": 2,
               "flame": 0, "spark": 0, "arrow": 2}

BURSTS = {
    "pop": burst_pop, "spiky": burst_spiky, "star": burst_star, "boom": burst_boom, "shatter": burst_shatter,
    "sparkle": burst_sparkle, "god": burst_god, "gloom": burst_gloom, "rosette": burst_rosette,
    "confetti": burst_confetti, "speed": burst_speed, "ring": burst_ring, "slash": burst_slash,
    "checker": burst_checker, "crown": burst_crown, "flame": burst_flame, "spark": burst_spark,
    "arrow": burst_arrow,
}


def fit_ops(cv, ops, margin=14, allowance=34):
    """Uniformly scale all burst masks about the canvas centre so bodies (+ outline/shadow
    allowance) keep `margin` px from every edge."""
    acc = None
    for op in ops:
        m = op[1]
        if op[0] == "body":
            acc = (m > 0.02) if acc is None else (acc | (m > 0.02))
    if acc is None:
        return ops
    ys, xs = np.nonzero(acc)
    s_ = cv.ss
    x0, x1, y0, y1 = xs.min() / s_, xs.max() / s_, ys.min() / s_, ys.max() / s_
    need = [(CX - margin) / max(CX - (x0 - allowance * 0.4), 1), (W - margin - CX) / max((x1 + allowance) - CX, 1),
            (CY - margin) / max(CY - (y0 - allowance * 0.4), 1), (H - margin - CY) / max((y1 + allowance) - CY, 1)]
    k = min(1.0, *need)
    if k >= 0.999:
        return ops
    M = np.float32([[k, 0, CX * s_ * (1 - k)], [0, k, CY * s_ * (1 - k)]])
    out = []
    for op in ops:
        m2 = cv2.warpAffine(op[1], M, (cv.W, cv.H), flags=cv2.INTER_LINEAR, borderValue=0)
        out.append((op[0], m2) + tuple(op[2:]))
    return out


def role_color(role, scheme, tint=False):
    if role == "ink":
        return INK
    if tint:
        if role in ("crown", "spark"):
            return hexc("#E8E8E8")
        return hexc(TINT_SCHEME.get(role, "#FFFFFF"))
    if role == "crown":
        return C("yellow")
    if role == "spark":
        return C("paper")
    return col(scheme.get(role, "paper"))


def shade_color(c, tint=False, scheme=None):
    if tint:
        return hexc(TINT_SCHEME["shade"])
    c = np.asarray(c, np.float32)
    import colorsys
    h_, s_, v_ = colorsys.rgb_to_hsv(*[float(x) for x in c])
    if s_ < 0.3 and v_ > 0.7 and scheme:
        # near-white fill: shade with a saturated scheme colour instead of grey
        for k in ("outer", "accent", "inner"):
            cand = col(scheme.get(k, "magenta"))
            hh, ss_, vv = colorsys.rgb_to_hsv(*[float(x) for x in cand])
            if ss_ > 0.4 and vv > 0.5:
                return mix(cand, c, 0.15)
        return C("magenta")
    # darker, slightly cooler version for halftone shading
    return np.clip(mix(c * 0.62, C("indigo"), 0.25), 0, 1)


def burst_drips(cv, m, n, seed):
    """Paint drips running off the bottom of burst body m (design-unit sizes)."""
    r = rng(seed)
    out = np.zeros_like(m)
    Mb = m > 0.5
    ys, xs = np.nonzero(Mb)
    if len(xs) == 0 or n <= 0:
        return out
    x_lo, x_hi = xs.min(), xs.max()
    placed = []
    tries = 0
    while len(placed) < n and tries < 300:
        tries += 1
        x = int(r.uniform(x_lo + (x_hi - x_lo) * 0.25, x_hi - (x_hi - x_lo) * 0.25))
        colm = np.nonzero(Mb[:, x])[0]
        if len(colm) == 0:
            continue
        yb = colm.max()
        ok = True
        for dx in (-14 * cv.ss, 14 * cv.ss):
            c2 = np.nonzero(Mb[:, x + dx])[0]
            if len(c2) == 0 or abs(c2.max() - yb) > 10 * cv.ss:
                ok = False
        if not ok or any(abs(x - p) < 120 * cv.ss for p in placed):
            continue
        placed.append(x)
        xd, yd = x / cv.ss, yb / cv.ss
        w = r.uniform(16, 30)
        L = min(r.uniform(50, 150), 1024 - 40 - yd - w)
        if L < 30:
            continue
        out = np.maximum(out, cv.mask(drip_paths(xd, yd - w * 0.8, w, L, r)))
    return out


def render_burst(cv, ops, scheme, tint=False, ink_w=11, drips=0, seed=0):
    first_body = True
    for op in ops:
        kind, m, role = op[0], op[1], op[2]
        colr = role_color(role, scheme, tint)
        if kind == "flat":
            if role == "lines":
                # contrasting hairline edge so focus lines read over both dark and bright scenes
                edge = INK if float(np.mean(colr)) > 0.45 else (hexc("#FFFFFF") if tint else PAPER)
                cv.paint(cv.dilate(m, 1.6), edge, 0.85)
            cv.paint(m, colr)
            continue
        o = op[3] if len(op) > 3 else {}
        if first_body and drips and role == "outer":
            m = np.maximum(m, burst_drips(cv, m, drips, seed))
        first_body = False
        ow = o.get("outline", ink_w)
        shadow = o.get("shadow", (18, 22))
        O = cv.dilate(m, ow) if ow else m
        if shadow:
            cv.paint(cv.shift(O, *shadow), INK)
        if ow:
            cv.paint(O, INK)
        cv.paint(m, colr)
        sh = o.get("shade", 0.0)
        if sh > 0:
            # dots grow toward lower right
            ys, xs = np.nonzero(m > 0.5)
            if len(ys):
                y0, y1 = ys.min() / cv.ss, ys.max() / cv.ss
                x0, x1 = xs.min() / cv.ss, xs.max() / cv.ss
                val = cv.ramp((x0 + (x1 - x0) * 0.25, y0 + (y1 - y0) * 0.2), (x1, y1)) ** 1.4 * sh
                dots = cv.halftone(val, 15, 45)
                cv.paint(dots * m, shade_color(colr, tint, scheme), 0.9)
                # top-left rim light
                rim = m * (1 - cv.shift(m, 7, 8))
                cv.paint(rim, mix(colr, PAPER, 0.55) if not tint else hexc("#FFFFFF"), 0.6)


# ------------------------------------------------------------------------------------
# Lettering
# ------------------------------------------------------------------------------------
KERN = {("！", "！"): -0.42, ("*", "！"): -0.1, ("ー", "！"): -0.05, ("！", "?"): 0.0}


def sfx_path(text, size, r, scales=None, tracking=-0.04, rot_jitter=5.5, y_jitter=0.035, scale_jitter=0.05,
             wave=0.0, font="dela"):
    """Per-glyph jittered lettering (like inklib.sfx_text_path) with pair kerning for full-width marks."""
    path = skia.Path()
    cx = 0.0
    n = len(text)
    for i, ch in enumerate(text):
        sc = (scales[i] if scales is not None else 1.0) * (1 + scale_jitter * r.uniform(-1, 1))
        f = skia.Font(typeface(font), size * sc)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        g = f.textToGlyphs(ch)[0]
        w = f.getWidths([g])[0]
        if i > 0:
            k = KERN.get((text[i - 1], ch), KERN.get(("*", ch), 0.0) if text[i - 1] != "！" else KERN.get((text[i - 1], ch), 0.0))
            cx += k * size
        gp = f.getPath(g) or skia.Path()
        b = gp.computeTightBounds()
        pcx, pcy = (b.left() + b.right()) / 2, (b.top() + b.bottom()) / 2
        m = skia.Matrix()
        ang = rot_jitter * r.uniform(-1, 1)
        dy = y_jitter * size * r.uniform(-1, 1) + wave * size * math.sin(i / max(1, n - 1) * math.pi)
        m.setRotate(ang, pcx, pcy)
        m.postTranslate(cx, dy)
        gp.transform(m)
        path.addPath(gp)
        cx += w + tracking * size
    return path


def build_runs(spec, base=300.0, seed=0):
    r = rng(seed)
    paths = []
    for (txt, sc, xe, ye) in spec["runs"]:
        n = len(txt)
        scales = [1.0] * n
        if txt.endswith("！！"):
            scales[-1] = scales[-2] = 1.05
        elif txt.endswith("！"):
            scales[-1] = 1.08
        p = sfx_path(txt, base * sc, r, scales=scales,
                     wave=-0.05 if spec.get("energy", 0) >= 3 and n > 2 else 0.0)
        if spec.get("droop"):
            # fail: letters sag progressively downward + rotate
            q = skia.Path()
            xcur = 0.0
            for i, (ch, gp, x0, w) in enumerate(glyph_paths(txt, "dela", base * sc, 0.0)):
                g = skia.Path(gp)
                if ch == "…":
                    g.transform(skia.Matrix.Scale(0.72, 0.72))
                b = g.computeTightBounds()
                m = skia.Matrix()
                m.setRotate(3 + i * 6, (b.left() + b.right()) / 2, (b.top() + b.bottom()) / 2)
                m.postTranslate(xcur - b.left() + (0 if i == 0 else base * 0.1), i * base * 0.1)
                xcur += (b.right() - b.left()) + (0 if i == 0 else base * 0.1)
                g.transform(m)
                q.addPath(g)
            p = q
        p.offset(xe * base, ye * base)
        paths.append(p)
    return paths


def layout_text(spec, seed):
    """Returns (list of run paths in canvas space, em_px)."""
    base = 300.0
    runs = build_runs(spec, base, seed)
    allp = combine(runs)
    l, t, r_, b = bounds(allp)
    x0, y0, x1, y1 = spec["box"]
    em = base
    # iterate: margins from strokes scale with em
    for _ in range(3):
        m = em * (0.05 + 0.07) + 2
        ex = em * 0.11
        box = (x0 + m, y0 + m, x1 - m - ex, y1 - m - ex)
        s = min((box[2] - box[0]) / (r_ - l), (box[3] - box[1]) / (b - t))
        em = base * s
    mat = skia.Matrix()
    mat.setTranslate(-l, -t)
    mat.postScale(s, s)
    ox = box[0] + ((box[2] - box[0]) - (r_ - l) * s) / 2
    oy = box[1] + ((box[3] - box[1]) - (b - t) * s) / 2
    mat.postTranslate(ox, oy)
    cxp = ox + (r_ - l) * s / 2
    cyp = oy + (b - t) * s / 2
    m2 = skia.Matrix()
    m2.setTranslate(-cxp, -cyp)
    m2.postSkew(spec.get("skew", -0.15), 0)
    m2.postRotate(spec.get("rot", 0))
    m2.postTranslate(cxp, cyp)
    out = []
    for p in runs:
        q = skia.Path(p)
        q.transform(mat)
        q.transform(m2)
        out.append(q)
    # rotation may push outside box: shrink to fit box
    l2, t2, r2, b2 = bounds(combine(out))
    m_ = em * 0.12 + 2
    ex = em * 0.11
    fx = min(1.0, (x1 - x0 - 2 * m_ - ex) / (r2 - l2), (y1 - y0 - 2 * m_ - ex) / (b2 - t2))
    if fx < 1.0:
        m3 = skia.Matrix()
        m3.setTranslate(-cxp, -cyp); m3.postScale(fx, fx); m3.postTranslate(cxp, cyp)
        for q in out:
            q.transform(m3)
        em *= fx
    return out, em


def lettering_layers(cv, spec, seed, extra_paths=None):
    """Render JP lettering into a fresh canvas; returns canvas + key masks."""
    runs, em = layout_text(spec, seed)
    if extra_paths:
        runs = runs + extra_paths
    hi, base, shd, ext = ramp_cols(spec["color"])
    r_paper = em * 0.046
    r_ink = em * 0.072
    exv = (em * 0.085, em * 0.105)
    Fs = [cv.mask(p) for p in runs]
    F = mask_union(*Fs)
    P = cv.dilate(F, r_paper)
    K = cv.dilate(P, r_ink)
    # drips from ink outline bottom edges
    r = rng(seed + 7)
    nd = {0: 3, 1: 2, 2: 2, 3: 3, 4: 4, 5: 5, 6: 5, 7: 6}.get(spec.get("energy", 2), 3)
    E = cv.extrude(K, *exv)
    EO = cv.dilate(E, em * 0.022)
    drips = drip_masks(cv, EO, nd, em, r)
    lay = Canvas(cv.w, cv.h, cv.ss)
    lay.paint(EO, INK)
    lay.paint(E, ext)
    # hatch lines on extrusion
    hatch = lay.halftone(np.float32(0.32), em * 0.06, 45, shape="line")
    lay.paint(E * (1 - K) * hatch, INK, 0.45)
    lay.paint(drips, INK)
    # glossy wet highlight on drips
    lay.paint(drips * (1 - cv.shift(drips, -em * 0.012, 0)) * (1 - EO), hexc("#5A5670"), 0.9)
    # extrusion side highlight near face edge
    lay.paint(K, INK)
    lay.paint(P, PAPER)
    # paper stroke subtle inner shadow (bottom-right) for thickness
    ps = P * (1 - cv.shift(P, -em * 0.012, -em * 0.014))
    lay.paint(ps, hexc("#D9CFC0"), 0.8)
    for Fi, p in zip(Fs, runs):
        l, t, r_, b = bounds(p)
        grad = lay.vgrad(t, b, [(0.0, hi), (0.42, base), (0.58, base), (1.0, shd)])
        lay.paint(Fi, grad)
        # halftone shading: dots densify to the bottom of each run
        val = lay.ramp((0, t + (b - t) * 0.35), (0, b)) ** 1.2 * 0.55
        dots = lay.halftone(val, max(8.0, em * 0.045), 45)
        lay.paint(Fi * dots, mix(shd, INK, 0.25), 0.55)
        # glossy upper band (manga logo shine) with a wavy cut
        cut = t + (b - t) * 0.36
        shine_path = skia.Path()
        shine_path.moveTo(l - 50, t - 50)
        shine_path.lineTo(r_ + 50, t - 50)
        n = 10
        for i in range(n, -1, -1):
            x = l - 50 + (r_ - l + 100) * i / n
            shine_path.lineTo(x, cut + math.sin(i * 1.7) * (b - t) * 0.04 - (x - l) / (r_ - l + 1) * (b - t) * 0.08)
        shine_path.close()
        SH = lay.mask(shine_path)
        lay.paint(Fi * SH * (1 - lay.shift(Fi, 0, em * 0.03)), PAPER, 0.0)
        lay.paint(Fi * SH, PAPER, 0.28)
    # inner rim: dark on bottom-right edge, light top-left edge
    rim_d = F * (1 - cv.shift(F, -em * 0.016, -em * 0.02))
    lay.paint(rim_d, mix(shd, INK, 0.35), 0.75)
    rim_l = F * (1 - cv.shift(F, em * 0.012, em * 0.014))
    lay.paint(rim_l, PAPER, 0.75)
    # specular glints
    return lay, dict(F=F, P=P, K=K, E=E, em=em)


def drip_masks(cv, K, n, em, r):
    """Pick bottom-edge points of mask K and hang drips there."""
    out = np.zeros_like(K)
    if n <= 0:
        return out
    Kb = K > 0.5
    ys, xs = np.nonzero(Kb)
    if len(xs) == 0:
        return out
    x_lo, x_hi = xs.min(), xs.max()
    cols = []
    tries = 0
    while len(cols) < n and tries < 400:
        tries += 1
        x = int(r.uniform(x_lo + (x_hi - x_lo) * 0.06, x_hi - (x_hi - x_lo) * 0.06))
        col_ = np.nonzero(Kb[:, x])[0]
        if len(col_) == 0:
            continue
        ybot = col_.max()
        # require a reasonably flat bottom (neighbouring columns similar)
        ok = True
        for dx in (-int(em * 0.04 * cv.ss), int(em * 0.04 * cv.ss)):
            c2 = np.nonzero(Kb[:, min(max(x + dx, 0), Kb.shape[1] - 1)])[0]
            if len(c2) == 0 or abs(c2.max() - ybot) > em * 0.05 * cv.ss:
                ok = False
        if not ok or any(abs(x - c) < em * 0.35 * cv.ss for c in cols):
            continue
        cols.append(x)
        xd, yd = x / cv.ss, ybot / cv.ss
        width = em * r.uniform(0.07, 0.105)
        length = em * r.uniform(0.2, 0.5)
        length = min(length, (1024 - 70) - yd - width * 1.4)
        if length < width * 1.5:
            continue
        out = np.maximum(out, cv.mask(drip_paths(xd, yd - width * 0.9, width, length, r)))
    return out


def en_banner(cv, spec, seed):
    """EN Bangers subtitle on a tilted ribbon. Returns layer canvas."""
    bn = spec["banner"]
    txt = spec["en"]
    size = 96
    tp = text_path(txt, "bangers", size, tracking=0.04)
    l, t, r_, b = bounds(tp)
    tw, th = r_ - l, b - t
    pad_x, bh = 70, th + 52
    bw = tw + pad_x * 2
    cx = CX + (40 if bn.get("rot", 0) < 0 else -40)
    cy = bn["y"]
    ang = bn.get("rot", 0)
    lay = Canvas(cv.w, cv.h, cv.ss)
    for _ in range(4):
        under = ribbon(cx + 14, cy + 16, bw + 30, bh + 10, angle=ang + 1.2, tail=0.0, skew=0.35)
        rb = ribbon(cx, cy, bw, bh, angle=ang, tail=0.12, notch=0.5, fold=0.05, skew=0.3)
        lo = max(bounds(under["band"])[3], bounds(rb["tails"])[3], bounds(rb["band"])[3]) + 9 + 14
        if lo <= H - 46:
            break
        cy -= lo - (H - 46)
    band_c, under_c, text_c = col(bn["band"]), col(bn["under"]), col(bn["text"])
    U = lay.mask(under["band"])
    T = lay.mask(rb["tails"])
    Fd = lay.mask(rb["folds"])
    Bd = lay.mask(rb["band"])
    allm = np.maximum(np.maximum(U, T), Bd)
    lay.paint(lay.shift(lay.dilate(allm, 9), 12, 14), INK)
    lay.paint(lay.dilate(allm, 9), INK)
    lay.paint(U, under_c)
    lay.paint(T, darken(band_c, 0.35) if bn["band"] != "ink" else hexc("#2A2638"))
    lay.paint(Fd, darken(band_c, 0.7) if bn["band"] != "ink" else C("black"))
    lay.paint(lay.dilate(Bd, 0), band_c)
    # band inner pinstripe
    lay.paint(Bd * (1 - lay.erode(Bd, 9)) * (1 - lay.erode(Bd, 5) * 0), mix(band_c, PAPER, 0.35) if bn["band"] != "ink" else under_c, 0.0)
    inner = lay.erode(Bd, 12)
    lay.paint(Bd * (1 - inner) * lay.erode(Bd, 7), under_c if bn["band"] == "ink" else PAPER, 0.85)
    # band halftone texture
    dots = lay.halftone(lay.ramp((0, cy - bh / 2), (0, cy + bh / 2)) * 0.35, 9, 45)
    lay.paint(Bd * dots, INK if bn["band"] != "ink" else hexc("#2A2638"), 0.25)
    # little sparkles flanking the text
    for sgn in (-1, 1):
        sx = sgn * (tw / 2 + pad_x * 0.5)
        sp = sparkle(sx, 0, bh * 0.2)
        mm = skia.Matrix(); mm.setRotate(ang); mm.postTranslate(cx, cy)
        sp.transform(mm)
        SPm = lay.mask(sp)
        lay.paint(lay.dilate(SPm, 3), INK)
        lay.paint(SPm, under_c if bn["band"] == "ink" else (PAPER if bn["band"] != "paper" else INK))
    # text
    m = skia.Matrix()
    m.setTranslate(-(l + r_) / 2, -(t + b) / 2)
    m.postSkew(-0.12, 0)
    m.postRotate(ang)
    m.postTranslate(cx, cy)
    tp2 = skia.Path(tp); tp2.transform(m)
    TF = lay.mask(tp2)
    dark_text = float(np.mean(text_c)) < 0.3
    if dark_text:
        # dark letters on a bright band: crisp drop of band-darkened colour, no ink blob
        lay.paint(lay.shift(TF, 5, 6), darken(band_c, 0.45), 0.9)
        lay.paint(TF, text_c)
    else:
        ink_ring = lay.dilate(TF, 7)
        lay.paint(lay.shift(ink_ring, 5, 6), INK)
        lay.paint(ink_ring, INK)
        lay.paint(TF, text_c)
    if bn["text"] != "ink":
        lay.paint(TF * lay.ramp((0, cy), (0, cy + th / 2)) , darken(text_c, 0.3), 0.35)
    return lay


def fx_layer(cv, spec, seed, burst_alpha):
    """Splatter flecks, spray mist, sparkles, confetti."""
    r = rng(seed + 99)
    lay = Canvas(cv.w, cv.h, cv.ss)
    e = spec.get("energy", 2)
    hi, base, shd, ext = ramp_cols(spec["color"])
    sch = spec["scheme"]
    # splatter clusters near the burst edge
    nclus = 2 + e // 2
    for i in range(nclus):
        a = r.uniform(0, 2 * math.pi)
        cx, cy = CX + math.cos(a) * 820, CY + math.sin(a) * 380
        cx = min(max(cx, 140), 1908); cy = min(max(cy, 110), 914)
        colr = [INK, base, col(sch["outer"]) if sch["outer"] not in ("ink", "indigo") else PAPER][i % 3]
        fl = flecks(cx, cy, 70 + 15 * e, 22 + 6 * e, (2, 9 + e), r, sigma=0.7, elong=0.35)
        m = clamp_to_canvas(lay, lay.mask(fl), 10)
        lay.paint(m, colr)
    # overspray mist hugging the burst silhouette
    if burst_alpha is not None:
        band = blur(burst_alpha, 18 * cv.ss) - burst_alpha * 0.9
        band = np.clip(band * 2.2, 0, 1)
        h_, w_ = band.shape
        n = 2600 + 400 * e
        ys = r.integers(0, h_, n); xs = r.integers(0, w_, n)
        keep = r.random(n) < band[ys, xs]
        p = skia.Path()
        for y, x in zip(ys[keep], xs[keep]):
            p.addCircle(float(x) / cv.ss, float(y) / cv.ss, float(r.uniform(0.8, 2.6)))
        lay.paint(clamp_to_canvas(lay, lay.mask(p), 6), INK, 0.85)
    if spec["burst"] in ("confetti",):
        conf = []
        cols = [C("magenta"), C("cyan"), C("lime"), C("paper"), C("yellow")]
        for i in range(70):
            a = r.uniform(0, 2 * math.pi)
            d = r.uniform(0.85, 1.12)
            x, y = CX + math.cos(a) * 900 * d, CY + math.sin(a) * 440 * d
            if not (40 < x < 2008 and 40 < y < 984):
                continue
            s = r.uniform(10, 24)
            shape = rect(-s, -s * 0.5, s, s * 0.5) if i % 3 else poly([(0, -s), (s, s * 0.8), (-s, s * 0.8)])
            shape = transformed(shape, rotate=r.uniform(0, 180), pivot=(0, 0), translate=(x, y))
            m = lay.mask(shape)
            lay.paint(lay.dilate(m, 3.5), INK)
            lay.paint(m, cols[i % len(cols)])
    if spec["burst"] in ("sparkle", "crown", "rosette") or spec.get("energy", 0) >= 6:
        for i in range(7):
            a = r.uniform(0, 2 * math.pi)
            x, y = CX + math.cos(a) * r.uniform(650, 900), CY + math.sin(a) * r.uniform(330, 430)
            x = min(max(x, 80), 1968); y = min(max(y, 80), 944)
            s = r.uniform(22, 46)
            m = lay.mask(sparkle(x, y, s, rot=r.uniform(-0.2, 0.2)))
            lay.paint(lay.dilate(m, 5), INK)
            lay.paint(m, PAPER if i % 2 else C("yellow"))
    return lay


# ------------------------------------------------------------------------------------
# Countdown kana tag
# ------------------------------------------------------------------------------------
def kana_tag(cv, spec, seed, em):
    kana = spec.get("kana")
    if not kana:
        return None
    p = sfx_text_path(kana, "dela", 190, tracking=-0.05, rot_jitter=6, r=rng(seed + 3))
    p = fit_path(p, (1270, 150, 1830, 400))
    p = transformed(p, rotate=8, skew_x=-0.15)
    lay = Canvas(cv.w, cv.h, cv.ss)
    Fm = lay.mask(p)
    P = lay.dilate(Fm, 11)
    K = lay.dilate(P, 15)
    E = lay.extrude(K, 14, 16)
    lay.paint(lay.dilate(E, 4), INK)
    lay.paint(E, INK)
    l, t, r_, b = bounds(p)
    hi, base, shd, ext = ramp_cols(spec.get("kana_color", "yellow"))
    lay.paint(E * (1 - K), ext)
    lay.paint(K, INK)
    lay.paint(P, PAPER)
    lay.paint(Fm, lay.vgrad(t, b, [(0, hi), (0.45, base), (1, shd)]))
    dots = lay.halftone(lay.ramp((0, t + (b - t) * 0.4), (0, b)) * 0.5, 9, 45)
    lay.paint(Fm * dots, mix(shd, INK, 0.3), 0.5)
    return lay


# ------------------------------------------------------------------------------------
# Main per-callout render
# ------------------------------------------------------------------------------------
def check_margin(img_alpha, margin, name, what):
    ys, xs = np.nonzero(img_alpha > 0.02)
    if len(xs) == 0:
        return
    h_, w_ = img_alpha.shape
    m = min(xs.min(), ys.min(), w_ - 1 - xs.max(), h_ - 1 - ys.max())
    if m < margin:
        print(f"  !! {name} {what}: margin {m}px < {margin}px  bbox x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}")
    return m


def render_one(cid):
    t0 = time.time()
    spec = CALLOUTS[cid]
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(cid))
    cv = Canvas(W, H, SS)
    style = spec["burst"]
    ops = fit_ops(cv, BURSTS[style](cv, rng(style)))
    burst = Canvas(W, H, SS)
    render_burst(burst, ops, spec["scheme"], tint=False, drips=BURST_DRIPS.get(style, 0), seed=len(style))
    jp, km = lettering_layers(cv, spec, seed)
    kt = kana_tag(cv, spec, seed, km["em"])
    if kt is not None:
        jp.over(kt)
    en = en_banner(cv, spec, seed)
    fx = fx_layer(cv, spec, seed, burst.alpha())
    # composite
    comp = Canvas(W, H, SS)
    comp.over(burst)
    comp.over(fx)
    comp.over(jp)
    comp.over(en)
    os.makedirs(OUT, exist_ok=True)
    comp.save(os.path.join(OUT, f"callout_{cid}.png"))
    text = Canvas(W, H, SS)
    text.over(jp); text.over(en)
    tf = text.final()
    check_margin(tf[..., 3], 40, cid, "text")
    save_image(tf, os.path.join(OUT, f"callout_{cid}_text.png"))
    jp.save(os.path.join(OUT, f"callout_{cid}_jp.png"))
    en.save(os.path.join(OUT, f"callout_{cid}_en.png"))
    fx.save(os.path.join(OUT, f"callout_{cid}_fx.png"))
    print(f"{cid}: {time.time() - t0:.1f}s")
    return cid


def render_burst_tint(style):
    cv = Canvas(W, H, SS)
    ops = fit_ops(cv, BURSTS[style](cv, rng(style)))
    render_burst(cv, ops, {}, tint=True, drips=BURST_DRIPS.get(style, 0), seed=len(style))
    f = cv.final()
    check_margin(f[..., 3], 4, style, "burst")
    save_image(f, os.path.join(OUT, f"burst_{style}.png"))
    print("burst", style)
    return style


def previews():
    ids = [i for i in CALLOUTS if os.path.exists(os.path.join(OUT, f"callout_{i}.png"))]
    contact_sheet([os.path.join(OUT, f"callout_{i}.png") for i in ids], os.path.join(PREVIEWS, "callouts.png"),
                  cell=(400, 200), cols=4, bg="dark", title="INK DRIFT callouts (composite)")
    contact_sheet([os.path.join(OUT, f"callout_{i}.png") for i in ids],
                  os.path.join(PREVIEWS, "callouts_checker.png"), cell=(400, 200), cols=4, bg="checker",
                  title="callouts on checker")
    contact_sheet([os.path.join(OUT, f"callout_{i}_text.png") for i in ids],
                  os.path.join(PREVIEWS, "callouts_text.png"), cell=(400, 200), cols=4, bg="checker",
                  title="callout text layers")
    styles = [s for s in sorted(set(s["burst"] for s in CALLOUTS.values()))
              if os.path.exists(os.path.join(OUT, f"burst_{s}.png"))]
    contact_sheet([os.path.join(OUT, f"burst_{s}.png") for s in styles], os.path.join(PREVIEWS, "bursts.png"),
                  cell=(400, 200), cols=4, bg="checker", title="tintable bursts")


JP_TEXT = {  # canonical line per Docs/DESIGN.md (layout runs may split/stack it)
    "nice": "ナイス！", "good": "成功！", "great": "グレートドリフト！", "awesome": "すごい！", "insane": "やばい！！",
    "perfect": "完璧！", "god": "神ドリフト！！", "fail": "失敗…", "best_lap": "最高！", "new_record": "新記録！",
    "start": "スタート！", "count_3": "さん！", "count_2": "に！", "count_1": "いち！", "go": "ゴー！",
    "final_lap": "ファイナルラップ！", "goal": "ゴール！", "drift_king": "ドリフトキング！", "ikee": "いけー！",
    "near_miss": "ニアミス！", "overtake": "オーバーテイク！",
}


def to_hex(c):
    c = col(c) if isinstance(c, str) else c
    return "#%02X%02X%02X" % tuple(int(round(float(x) * 255)) for x in c)


def manifest():
    import json
    items = []
    for cid, sp in CALLOUTS.items():
        items.append({
            "id": cid,
            "jp": JP_TEXT[cid],
            "en": sp["en"],
            "text_color": RAMPS[sp["color"]][1],
            "burst_style": sp["burst"],
            "burst_tint_suggestion": to_hex(sp["scheme"]["outer"]),
            "files": {
                "composite": f"callout_{cid}.png", "text": f"callout_{cid}_text.png", "jp": f"callout_{cid}_jp.png",
                "en": f"callout_{cid}_en.png", "fx": f"callout_{cid}_fx.png", "burst": f"burst_{sp['burst']}.png",
            },
        })
    doc = {
        "canvas": [W, H],
        "note": "All layers share one 2048x1024 frame; stack burst (tinted, multiply) -> fx -> jp -> en to rebuild the "
                "composite. burst_*.png are grey/white with ink outlines: tint by multiplying with a colour.",
        "callouts": items,
    }
    with open(os.path.join(OUT, "callouts_manifest.json"), "w", encoding="utf8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def main(argv):
    if argv == ["manifest"]:
        manifest(); return
    if argv == ["previews"]:
        previews(); return
    ids = [a for a in argv if a in CALLOUTS]
    do_bursts = (not argv) or ("bursts" in argv)
    if not argv:
        ids = list(CALLOUTS)
    procs = int(os.environ.get("INK_PROCS", "2"))
    with Pool(procs) as pool:
        if ids:
            pool.map(render_one, ids)
        if do_bursts:
            pool.map(render_burst_tint, sorted(set(s["burst"] for s in CALLOUTS.values())))
    manifest()
    previews()


if __name__ == "__main__":
    main(sys.argv[1:])
