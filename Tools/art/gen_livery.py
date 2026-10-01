"""Livery decals for INK DRIFT: TOKYO  ->  Game/Assets/InkDrift/Art/Decals/livery_*.png

1024x1024 transparent stickers / graffiti / JDM decals. Pre-coloured (not for tinting).
All names, brands and plates are fictional. No flag / rising-sun imagery.

Usage:  python gen_livery.py              # all
        python gen_livery.py koi oni      # subset (substring match)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decallib import *  # noqa: F401,F403
from inklib import f32

S = 1024
SS = 2
INK, PAPER = C("ink"), C("paper")
MAG, CYAN, YEL, RED, IND, SAK, LIME = (C(n) for n in ("magenta", "cyan", "yellow", "red", "indigo", "sakura", "lime"))
ORANGE = hexc("#FF8A1F")
GOLD = hexc("#FFC21A")


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def T(text, font, box, mode="contain", align=(0.5, 0.5), tracking=0.0, rot=0.0, skew=0.0, size=400,
      sfx=None):
    if sfx:
        p = sfx_text_path(text, font, size, tracking, **sfx)
    else:
        p = text_path(text, font, size, tracking)
    if skew or rot:
        p = transformed(p, rotate=rot, skew_x=skew)
    return fit_path(p, box, mode=mode, align=align)


def V(text, font, box, spacing=1.0, mode="contain", align=(0.5, 0.5)):
    p = vtext_path(text, font, 400, spacing)
    return fit_path(p, box, mode=mode, align=align)


def grad(c, y0, y1, *cols):
    n = len(cols)
    return c.vgrad(y0, y1, [(i / (n - 1), col) for i, col in enumerate(cols)])


def hgrad(c, x0, x1, *cols):
    n = len(cols)
    t = c.ramp((x0, 0), (x1, 0))
    return gradient_map(t, [(i / (n - 1), col) for i, col in enumerate(cols)])


def layer():
    return Canvas(S, S, ss=SS)


def shift_layer(L, dx, dy):
    """Translate a whole layer (design px)."""
    import cv2
    M = np.float32([[1, 0, dx * L.ss], [0, 1, dy * L.ss]])
    L.px = cv2.warpAffine(L.px, M, (L.W, L.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def smooth_border(c, A, w):
    """Die-cut outline: dilated + rounded (simplified like a real plotter cut)."""
    B = c.dilate(A, w * 1.35)
    B = c.blur(B, w * 0.45)
    B = smoothstep(0.42, 0.58, B)
    return np.maximum(B, c.dilate(A, w * 0.75)).astype(f32)


def diecut(c, content, w=18, color=None, rim=True):
    A = content.alpha()
    B = smooth_border(c, A, w)
    c.paint(B, PAPER if color is None else color)
    if rim:
        edge = B * (1 - c.erode(B, 1.8))
        c.paint(edge, hexc("#C9C3B5"), 0.9)
    c.over(content)
    return B


def star4(cx, cy, r, thin=0.18, rot=0.0):
    pts = []
    for i in range(8):
        a = rot + i * math.pi / 4
        rr = r if i % 2 == 0 else r * thin
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return smooth_closed(pts, 0.15)


def sparkle(c, cx, cy, r, color=PAPER, ink=True):
    p = star4(cx, cy, r)
    m = c.mask(p)
    if ink:
        c.paint(c.dilate(m, max(3, r * 0.12)), INK)
    c.paint(m, color)


def drips_from(c, M, color, seed, count=6, width=(10, 22), length=(40, 140), xr=None, ink_r=0):
    """Hang spray drips from the bottom edge of mask M (design coords)."""
    r = rng(seed)
    Hm, Wm = M.shape
    ss = c.ss
    cols = np.where(M.max(axis=0) > 0.5)[0]
    if xr is not None:
        cols = cols[(cols >= xr[0] * ss) & (cols <= xr[1] * ss)]
    if len(cols) == 0:
        return np.zeros_like(M)
    out = np.zeros_like(M)
    for _ in range(count):
        x = int(r.choice(cols))
        colm = M[:, x] > 0.5
        ys = np.where(colm)[0]
        y = ys.max() / ss
        w = r.uniform(*width)
        L = r.uniform(*length)
        dm = c.mask(drip_paths(x / ss, y - w * 0.6, w, L, r))
        np.maximum(out, dm, out=out)
    if ink_r:
        c.paint(c.dilate(out, ink_r), INK)
    c.paint(out, color)
    return out


def ht_shade(c, F, color, p0, p1, period=9, amount=0.55, angle=45, opacity=0.6):
    dots = c.halftone(c.ramp(p0, p1) * amount, period, angle)
    c.paint(F * dots, color, opacity)


def gloss(c, F, box, opacity=0.55, color=None):
    x0, y0, x1, y1 = box
    band = poly([(x0, y0), (x1, y0), (x1, y0 + (y1 - y0) * 0.18), (x0, y0 + (y1 - y0) * 0.38)])
    c.paint(F * c.mask(band), PAPER if color is None else color, opacity)



def cr_sample(pts, n=200):
    """Sample a Catmull-Rom spline through pts -> (n,2) array."""
    P = np.array(pts, dtype=np.float64)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out = []
    segs = len(P) - 3
    for i in range(n):
        u = i / (n - 1) * segs
        k = min(int(u), segs - 1)
        t = u - k
        p0, p1, p2, p3 = P[k], P[k + 1], P[k + 2], P[k + 3]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)


def taper_stroke(pts, w0, w1, prof=None, cap=True):
    """Polygon of a stroke along sampled points pts (n,2); width w0 -> w1 (or prof(t))."""
    P = np.asarray(pts, np.float64)
    n = len(P)
    d = np.gradient(P, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    t = np.linspace(0, 1, n)
    w = prof(t) if prof is not None else w0 + (w1 - w0) * t
    L = P + nrm * (w[:, None] / 2)
    R = P - nrm * (w[:, None] / 2)
    p = poly([tuple(q) for q in L] + [tuple(q) for q in R[::-1]])
    return p


def spiral_pts(cx, cy, r0, turns=1.4, a0=0.0, shrink=0.85, n=120, tail=0.0, sgn=1):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        a = a0 + sgn * t * turns * 2 * math.pi
        rr = r0 * (1 - shrink * t)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pts = pts[::-1]
    if tail > 0:  # straight tail leaving tangentially from the outer end
        (x1, y1), (x0, y0) = pts[-1], pts[-2]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        for k in range(1, 30):
            pts.append((x1 + dx / L * tail * k / 29, y1 + dy / L * tail * k / 29))
    return np.array(pts)


# --------------------------------------------------------------------------------------
# designs
# --------------------------------------------------------------------------------------
def d_team_inkdrift(c):
    L = layer()
    r = rng(11)
    # ink splat backdrop
    sp = splat_path(512, 520, 340, r, arms=16, arm_len=0.75, blob=0.78)
    SPm = L.mask(sp)
    L.paint(SPm, INK)
    # halftone glow inside splat
    ht = L.halftone(np.clip(1 - L.radial(470, 470, 380), 0, 1) * 0.55, 12, 30)
    L.paint(SPm * ht, IND * 1.6, 0.9)
    # spray flecks (behind the lettering)
    L.paint(L.mask(flecks(512, 520, 380, 70, (2, 9), r)), MAG)
    L.paint(L.mask(flecks(512, 520, 380, 50, (2, 7), rng(12))), CYAN)
    # INK
    pI = T("INK", "dela", (170, 225, 700, 470), skew=-0.22, rot=-7, tracking=-0.02)
    FI = L.mask(pI)
    comic_stack(L, FI, grad(L, 230, 470, hexc("#FFF7A8"), YEL, hexc("#FFB000")), paper_r=9, ink_r=13,
                ext=(14, 12), ext_col=MAG * 0.75)
    gloss(L, FI, (170, 225, 700, 470), 0.45, color=C("white"))
    # DRIFT
    pD = T("DRIFT", "dela", (110, 470, 930, 700), skew=-0.22, rot=-7, tracking=-0.03)
    FD = L.mask(pD)
    comic_stack(L, FD, grad(L, 470, 700, hexc("#FF8FBF"), MAG, hexc("#C0105A")), paper_r=9, ink_r=13,
                ext=(14, 12), ext_col=hexc("#3B1A80"))
    ht_shade(L, FD, hexc("#8A0A40"), (0, 560), (0, 700), period=8, amount=0.5)
    gloss(L, FD, (110, 470, 930, 700), 0.35, color=C("white"))
    # TEAM tag
    tag = transformed(poly([(160, 150), (430, 132), (440, 222), (170, 240)]), rotate=-4)
    Tm = L.mask(tag)
    L.paint(L.dilate(Tm, 7), INK)
    L.paint(Tm, CYAN)
    L.paint(L.mask(T("TEAM", "bangers", (195, 146, 405, 222), rot=-7, tracking=0.08)), INK)
    # JP bar
    bar = transformed(poly([(250, 735), (900, 712), (905, 790), (255, 812)]), rotate=0)
    Bm = L.mask(bar)
    L.paint(L.dilate(Bm, 6), PAPER)
    L.paint(Bm, INK)
    L.paint(L.mask(T("インクドリフト東京", "dela", (280, 722, 880, 795), rot=-2)), PAPER)
    tagb = L.mask(poly([(540, 808), (902, 796), (904, 842), (542, 854)]))
    L.paint(tagb, MAG)
    L.paint(L.mask(T("EST.2026 / TOKYO", "chakra", (560, 810, 888, 842), rot=-2, tracking=0.12)), PAPER)
    sparkle(L, 860, 250, 46, YEL)
    sparkle(L, 140, 640, 30, CYAN)
    diecut(c, L, 20)


def brush_kanji(c, ch, box, seed, font="reggae", amount=1.0, angle=-12, wobble=6, color=INK, scale=7):
    F = c.mask(T(ch, font, box))
    B = dry_brush(c, F, seed, angle=angle, amount=amount, wobble=wobble, scale=scale)
    c.paint(B, color)
    return B


def hanko(c, cx, cy, s, text, seed, rot=3.0, color=RED, font="noto"):
    """Red seal stamp, 白文 style (white glyphs knocked out of a red square). 1-2 chars."""
    sq = transformed(rect(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2, radius=s * 0.10), rotate=rot)
    M = c.mask(sq)
    line = c.erode(M, s * 0.06) * (1 - c.erode(M, s * 0.085))
    if len(text) == 1:
        gp = T(text, font, (cx - s * 0.31, cy - s * 0.31, cx + s * 0.31, cy + s * 0.31), mode="fill")
    else:
        gp = V(text, font, (cx - s * 0.27, cy - s * 0.34, cx + s * 0.27, cy + s * 0.34), spacing=0.95, mode="fill")
    g = c.mask(transformed(gp, rotate=rot, pivot=(cx, cy)))
    stamp = np.clip(M - line - g, 0, 1)
    n = c.noise(s * 0.04, seed, beta=1.0)
    stamp = stamp * (0.82 + 0.18 * smoothstep(0.3, 0.6, n)) * (1 - smoothstep(0.78, 0.82, n))
    c.paint(stamp, color)
    return M


def enso(c, cx, cy, R, seed, w0=70, w1=8, start=-40, sweep=315):
    """Brush circle (ensō): tapered stroke along an arc."""
    r = rng(seed)
    n = 120
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        a = math.radians(start + sweep * t)
        rr = R * (1 + 0.025 * math.sin(t * 9 + 1.3))
        w = w0 * (1 - t) ** 0.6 * (0.85 + 0.25 * math.sin(t * 5)) + w1
        if t < 0.05:
            w *= 0.6 + 0.4 * t / 0.05 + 0.25
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        nx, ny = math.cos(a), math.sin(a)
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    p = poly(left + right[::-1])
    F = c.mask(p)
    B = dry_brush(c, F, seed, angle=start + 60, amount=1.2, wobble=3, scale=6)
    return B


def d_sumi_racing(c):
    L = layer()
    E = enso(L, 512, 440, 320, 21, w0=86, start=-60, sweep=318)
    L.paint(E, INK)
    B = brush_kanji(L, "墨", (290, 200, 740, 660), 22, angle=-20)
    # splatter
    L.paint(L.mask(flecks(560, 420, 360, 55, (2, 12), rng(23), sigma=0.45)), INK)
    hanko(L, 790, 640, 120, "墨", 24)
    # SUMI RACING bar
    bar = poly([(150, 770), (880, 750), (870, 860), (140, 880)])
    Bm = L.mask(bar)
    L.paint(L.dilate(Bm, 6), PAPER)
    L.paint(Bm, INK)
    L.paint(L.mask(T("SUMI RACING", "bangers", (185, 762, 840, 868), rot=-1.6, tracking=0.06, skew=-0.12)), PAPER)
    st = L.mask(poly([(150, 895), (720, 880), (716, 896), (148, 911)]))
    L.paint(st, MAG)
    st2 = L.mask(poly([(150, 920), (560, 909), (557, 922), (148, 933)]))
    L.paint(st2, CYAN)
    diecut(c, L, 18)


def d_ryu(c):
    L = layer()
    brush_kanji(L, "龍", (150, 110, 870, 900), 31, angle=-25, wobble=7)
    L.paint(L.mask(flecks(520, 520, 420, 70, (2, 14), rng(32), sigma=0.5)), INK)
    hanko(L, 860, 830, 120, "昇龍", 33)
    c.over(L)


def d_drift_graffiti(c):
    L = layer()
    r = rng(41)
    # spray cloud backdrop
    cloud = scallop_cloud(512, 520, 430, 250, bumps=13, bump=0.30, r=r)
    CL = L.mask(cloud)
    CL = L.blur(CL, 2)
    overspray(L, CL, IND, 42, reach=14, amount=0.9)
    L.paint(CL, IND)
    ht = L.halftone(L.ramp((0, 300), (0, 760)) * 0.5, 14, 20)
    L.paint(CL * ht, CYAN, 0.35)
    p = T("ドリフト", "reggae", (95, 330, 930, 650), sfx=dict(rot_jitter=7, y_jitter=0.05, r=rng(43), wave=-0.08),
          rot=-6, skew=-0.12)
    F = L.mask(p)
    sil = comic_stack(L, F, grad(L, 330, 650, YEL, hexc("#FF9A1F"), MAG), paper_r=10, ink_r=14,
                      ext=(10, 16), ext_col=CYAN * 0.85)
    ht_shade(L, F, hexc("#B0105A"), (0, 520), (0, 650), period=8, amount=0.55)
    gloss(L, F, (95, 330, 930, 650), 0.5, color=C("white"))
    drips_from(L, sil, MAG, 44, count=7, width=(12, 20), length=(50, 150), ink_r=5)
    L.paint(L.mask(flecks(512, 500, 420, 60, (2, 10), rng(45))), MAG)
    L.paint(L.mask(flecks(512, 500, 420, 40, (2, 8), rng(46))), YEL)
    sparkle(L, 860, 300, 50, PAPER)
    sparkle(L, 180, 290, 34, YEL)
    sparkle(L, 820, 700, 28, CYAN)
    c.over(L)


def wind_curl(c, cx, cy, r0, seed, col, sgn=1, tail=260, w=22, a0=0.0):
    pts = spiral_pts(cx, cy, r0, turns=1.25, a0=a0, shrink=0.8, sgn=sgn, tail=tail)
    p = taper_stroke(pts, w * 0.35, w, prof=lambda t: w * (0.35 + 0.65 * np.clip(t * 1.6, 0, 1)) * (1 - 0.7 * np.clip((t - 0.75) / 0.25, 0, 1)))
    m = c.mask(p)
    c.paint(c.dilate(m, 7), INK)
    c.paint(m, col)
    return m


def d_kamikaze(c):
    L = layer()
    r = rng(51)
    # wind streaks behind
    for i in range(7):
        y = 180 + i * 105 + r.uniform(-20, 20)
        x0 = r.uniform(60, 200); x1 = r.uniform(820, 960)
        pts = np.array([(x0 + (x1 - x0) * t, y + math.sin(t * 3.1 + i) * 14) for t in np.linspace(0, 1, 60)])
        p = taper_stroke(pts, 2, 18 + r.uniform(0, 10), prof=lambda t: 3 + 20 * np.sin(np.pi * t) ** 0.8)
        m = L.mask(p)
        L.paint(L.dilate(m, 4), INK)
        L.paint(m, CYAN if i % 2 else PAPER)
    # banner
    ban = poly([(330, 70), (712, 52), (700, 958), (318, 974)])
    Bm = L.mask(ban)
    L.paint(L.dilate(Bm, 12), INK)
    L.paint(Bm, IND)
    ht = L.halftone(L.ramp((0, 70), (0, 970)) * 0.6, 11, 30)
    L.paint(Bm * ht, MAG * 0.8, 0.55)
    # curls
    wind_curl(L, 300, 210, 70, 52, CYAN, sgn=1, tail=150, w=26, a0=2.4)
    wind_curl(L, 760, 820, 64, 53, CYAN, sgn=-1, tail=150, w=24, a0=-0.6)
    wind_curl(L, 735, 330, 46, 54, PAPER, sgn=1, tail=110, w=18, a0=0.5)
    wind_curl(L, 270, 720, 50, 55, PAPER, sgn=-1, tail=120, w=18, a0=3.6)
    # 神風 vertical
    p = V("神風", "dela", (370, 105, 660, 830), spacing=1.02, mode="fill")
    p = transformed(p, rotate=-1.5, skew_x=-0.06)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 110, 830, C("white"), hexc("#BFF8FF"), CYAN), paper_r=0, ink_r=12,
                ext=(12, 12), ext_col=MAG)
    ht_shade(L, F, hexc("#0090B0"), (0, 300), (0, 830), period=9, amount=0.45)
    gloss(L, F, (370, 105, 660, 830), 0.4, color=C("white"))
    # KAMIKAZE label
    tag = poly([(380, 860), (660, 850), (664, 930), (384, 940)])
    Tm = L.mask(tag)
    L.paint(Tm, MAG)
    L.paint(L.mask(T("KAMIKAZE", "bangers", (398, 862, 646, 930), rot=-2, tracking=0.1)), PAPER)
    diecut(c, L, 16)


def skyline(c, x0, x1, base, seed):
    r = rng(seed)
    ps = []
    x = x0
    while x < x1:
        w = r.uniform(26, 70)
        h = r.uniform(60, 190)
        ps.append(rect(x, base - h, min(x + w, x1), base + 5))
        if r.random() < 0.3:
            ps.append(rect(x + w * 0.3, base - h - r.uniform(15, 40), x + w * 0.4, base - h + 2))
        x += w + r.uniform(-6, 4)
    # lattice tower (generic)
    tx = x0 + (x1 - x0) * 0.30
    ps.append(poly([(tx - 46, base + 5), (tx - 6, base - 300), (tx, base - 360), (tx + 6, base - 300), (tx + 46, base + 5), (tx + 20, base + 5), (tx, base - 120), (tx - 20, base + 5)]))
    ps.append(rect(tx - 26, base - 160, tx + 26, base - 145))
    ps.append(rect(tx - 16, base - 250, tx + 16, base - 238))
    # needle tower (generic)
    nx = x0 + (x1 - x0) * 0.74
    ps.append(poly([(nx - 30, base + 5), (nx - 9, base - 330), (nx - 2, base - 420), (nx + 2, base - 420), (nx + 9, base - 330), (nx + 30, base + 5)]))
    ps.append(rect(nx - 20, base - 300, nx + 20, base - 280, radius=6))
    ps.append(rect(nx - 15, base - 360, nx + 15, base - 348, radius=4))
    return ps


def d_tokyo(c):
    L = layer()
    box = rect(120, 120, 904, 904, radius=70)
    Bm = L.mask(box)
    L.paint(L.dilate(Bm, 14), INK)
    sky = L.mask(rect(120, 120, 904, 600, radius=0)) * Bm
    L.paint(Bm, INK)
    L.paint(sky, grad(L, 120, 600, hexc("#2A1660"), IND * 1.4, MAG, hexc("#FF7AA8")))
    ht = L.halftone(L.ramp((0, 330), (0, 600)) * 0.55, 10, 45)
    L.paint(sky * ht, YEL, 0.5)
    for k, (x, y, s) in enumerate([(220, 200, 16), (760, 180, 22), (840, 300, 12), (330, 300, 10), (600, 220, 12)]):
        sparkle(L, x, y, s, PAPER, ink=False)
    sk = L.mask(skyline(L, 120, 904, 600, 61)) * Bm
    L.paint(sk, INK)
    win = L.halftone(np.full(sk.shape, 0.12, f32), 9, 0, shape="square")
    winm = L.erode(sk, 6) * win * smoothstep(0.4, 0.6, L.noise(30, 62))
    L.paint(winm, CYAN, 0.9)
    L.paint(L.mask(rect(120, 596, 904, 612)) * Bm, MAG)
    # 東京
    p = T("東京", "dela", (190, 625, 834, 805), skew=-0.12)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 625, 805, C("white"), PAPER, SAK), paper_r=0, ink_r=0, ext=(10, 10), ext_col=MAG, ext_ink=0)
    L.paint(L.mask(T("T O K Y O", "bangers", (300, 815, 724, 880), tracking=0.05)), CYAN)
    diecut(c, L, 18)


def flame_lick_pts(x0, y0, length, amp, hook, phase=0.0, n=90):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + length * t
        y = y0 + amp * math.sin(t * math.pi * 1.5 + phase) * (0.2 + t) - hook * (t ** 3) * length * 0.10
        pts.append((x, y))
    return np.array(pts)


def flame_lick(x0, y0, length, thick, amp, hook, phase=0.0):
    """Hot-rod flame lick: wavy centre-line, fat round front, long hooked pointed tip."""
    pts = flame_lick_pts(x0, y0, length, amp, hook, phase)
    prof = lambda t: thick * (1 - t) ** 0.8 * (0.9 + 0.2 * np.exp(-((t - 0.2) / 0.15) ** 2))
    return union(taper_stroke(pts, 0, 0, prof=prof), circle(x0 + 2, y0 + amp * math.sin(phase) * 0.2, thick * 0.47))


def d_flames(c):
    L = layer()
    specs = [(120, 240, 760, 160, 52, 1.7, 0.1), (95, 375, 870, 175, 56, 1.7, 0.0), (105, 510, 820, 175, 54, 1.7, -0.1),
             (125, 645, 700, 160, 48, 1.7, 0.05), (160, 770, 540, 140, 40, 1.7, 0.0)]
    licks = [flame_lick(x, y, l, t, a, h, ph) for (x, y, l, t, a, h, ph) in specs]
    inner = [flame_lick(x + 25, y + 6, l * 0.58, t * 0.5, a * 0.8, h * 1.3, ph + 0.15) for (x, y, l, t, a, h, ph) in specs]
    gls = [flame_lick(x + 45, y - t * 0.14, l * 0.36, t * 0.11, a * 0.6, h, ph + 0.1) for (x, y, l, t, a, h, ph) in specs]
    O = L.mask(licks)
    I = L.mask(inner)
    L.paint(L.dilate(O, 24), CYAN)
    L.paint(L.dilate(O, 15), INK)
    L.paint(O, hgrad(L, 40, 990, YEL, hexc("#FF9A1F"), RED, MAG))
    ht = L.halftone(L.ramp((380, 0), (990, 0)) * 0.6, 9, 45)
    L.paint(O * ht, hexc("#9A0040"), 0.5)
    L.paint(L.dilate(I, 6), INK)
    L.paint(I, hgrad(L, 40, 640, C("white"), YEL, hexc("#FFB000")))
    L.paint(L.mask(gls) * I, C("white"), 0.75)
    c.over(L)


def koi_body(cl, wmax):
    """Body polygon from centreline samples cl (n,2) with koi width profile."""
    def prof(t):
        head = np.sqrt(np.clip(t / 0.10, 0, 1))
        body = 1 - np.clip((t - 0.28) / 0.72, 0, 1) ** 1.3 * 0.82
        return wmax * head * body
    return taper_stroke(cl, 0, 0, prof=prof)


def d_koi(c):
    L = layer()
    # backdrop disc with ripples
    disc = L.mask(circle(512, 512, 380))
    L.paint(L.dilate(disc, 12), INK)
    L.paint(disc, grad(L, 130, 890, hexc("#2C2A8C"), IND))
    ht = L.halftone(np.clip(1 - L.radial(512, 512, 380), 0, 1) * 0.5, 12, 15)
    L.paint(disc * ht, CYAN, 0.45)
    for k, rr in enumerate((120, 200, 290)):
        ring = L.mask(circle(470, 560, rr), stroke=10, fill=False) * disc
        L.paint(ring, CYAN, 0.7 - k * 0.15)
    cl = cr_sample([(340, 175), (465, 210), (585, 330), (590, 475), (515, 600), (445, 690)], 220)
    d = cl[-1] - cl[-6]; d /= np.linalg.norm(d)
    n_ = np.array([-d[1], d[0]])
    tb = cl[-1]
    tail = smooth_closed([tuple(tb + n_ * 24), tuple(tb + d * 90 + n_ * 125), tuple(tb + d * 200 + n_ * 110),
                          tuple(tb + d * 125 + n_ * 10), tuple(tb + d * 195 - n_ * 120), tuple(tb + d * 85 - n_ * 135),
                          tuple(tb - n_ * 24)], 0.55)
    # pectoral & pelvic fins
    fins = []
    for (ti, ln, wd, sweep) in ((0.27, 150, 95, 0.7), (0.62, 90, 55, 0.8)):
        k = int(ti * (len(cl) - 1))
        p = cl[k]; dd = cl[k + 2] - cl[k - 2]; dd /= np.linalg.norm(dd)
        nn = np.array([-dd[1], dd[0]])
        for s in (1, -1):
            base = p + nn * s * 40
            tip = base + nn * s * ln + dd * ln * sweep
            tip2 = base + nn * s * ln * 0.55 + dd * ln * (sweep + 0.55)
            fins.append(smooth_closed([tuple(base - dd * wd * 0.3), tuple(tip), tuple(tip2), tuple(base + dd * wd * 0.5)], 0.6))
    body = koi_body(cl, 140)
    FIN = L.mask(fins + [tail])
    BODY = L.mask(body)
    ALL = np.maximum(FIN, BODY)
    L.paint(L.dilate(ALL, 13), INK)
    # fins: paper w/ orange root + rays
    L.paint(FIN, grad(L, 150, 950, C("white"), hexc("#FFE3C4"), hexc("#FFB27A")))
    rays = L.halftone(np.full(FIN.shape, 0.10, f32), 16, 60, shape="line")
    L.paint(FIN * rays, ORANGE, 0.45)
    L.paint(L.dilate(BODY, 6) * FIN, INK)
    # body
    L.paint(BODY, PAPER)
    red = smoothstep(0.49, 0.52, L.noise(120, 74, beta=2.6)) * L.erode(BODY, 16)
    red = np.maximum(red, L.mask(smooth_closed([(370, 215), (430, 200), (500, 250), (470, 300), (400, 290)], 0.7)) * L.erode(BODY, 10))
    L.paint(red, hgrad(L, 300, 700, hexc("#FF4A1F"), RED, hexc("#E0103A")))
    # scales
    x0, y0, x1, y1 = [int(v) for v in bounds(body)]
    surf = skia.Surface(c.W, c.H)
    cv = surf.getCanvas(); cv.clear(skia.ColorBLACK); cv.scale(SS, SS)
    pf = skia.Paint(AntiAlias=True, Color=skia.ColorBLACK)
    ps = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE, Style=skia.Paint.kStroke_Style, StrokeWidth=2.2)
    sp = 26
    j = 0
    yy = y0 - sp
    while yy < y1 + sp:
        xx = x0 - sp + (sp / 2 if j % 2 else 0)
        while xx < x1 + sp:
            cv.drawCircle(xx, yy, sp * 0.62, pf)
            cv.drawCircle(xx, yy, sp * 0.62, ps)
            xx += sp
        yy += sp * 0.55
        j += 1
    scl = surf.makeImageSnapshot().toarray()[..., 0].astype(f32) / 255.0
    L.paint(scl * L.erode(BODY, 8) * smoothstep(0.1, 0.6, L.ramp((0, 230), (0, 380))), INK, 0.45)
    ht_shade(L, BODY, hexc("#7A2A40"), (640, 0), (540, 0), period=7, amount=0.30, opacity=0.35)
    # spine highlight
    spine = taper_stroke(cl[40:200], 8, 2)
    L.paint(L.mask(spine), C("white"), 0.6)
    # eyes
    k = 18
    p = cl[k]; dd = cl[k + 2] - cl[k - 2]; dd /= np.linalg.norm(dd); nn = np.array([-dd[1], dd[0]])
    for s in (1, -1):
        e = p + nn * s * 36
        L.paint(L.mask(circle(e[0], e[1], 12)), INK)
        L.paint(L.mask(circle(e[0] - 3, e[1] - 4, 4)), C("white"))
    # barbels
    nose = cl[0]
    for s in (1, -1):
        bp = cr_sample([tuple(nose + nn * s * 14), tuple(nose - dd * 18 + nn * s * 40), tuple(nose - dd * 10 + nn * s * 70)], 30)
        L.paint(L.mask(taper_stroke(bp, 6, 1)), INK)
    # bubbles
    for (x, y, rr) in ((250, 330, 18), (225, 270, 11), (262, 230, 7), (800, 700, 14)):
        b = L.mask(circle(x, y, rr), stroke=5, fill=False)
        L.paint(L.dilate(b, 2.5), INK)
        L.paint(b, PAPER)
    c.over(L)


def d_oni(c):
    L = layer()
    cx = 512
    r = rng(91)

    def sym(paths):
        out = list(paths)
        out += [mirror_x(p, cx) for p in paths]
        return out
    L.paint(L.mask(flecks(512, 500, 470, 46, (3, 10), rng(92), sigma=0.35)), RED)
    # hair mane
    spikes = []
    for i in range(15):
        a = math.radians(-180 + i * 180 / 14)
        base_r, tip_r = 260, 360 + r.uniform(-20, 50)
        a1, a2 = a - 0.16, a + 0.16
        spikes.append(poly([(cx + math.cos(a1) * base_r, 470 + math.sin(a1) * base_r * 1.05),
                            (cx + math.cos(a) * tip_r, 470 + math.sin(a) * tip_r * 1.0),
                            (cx + math.cos(a2) * base_r, 470 + math.sin(a2) * base_r * 1.05)]))
    side = [poly([(cx - 270, 420), (cx - 360 - r.uniform(0, 40), 520 + k * 70), (cx - 250, 520 + k * 60)]) for k in range(4)]
    HAIR = L.mask(spikes + sym(side) + [ellipse(cx, 470, 290, 280)])
    L.paint(L.dilate(HAIR, 10), INK)
    L.paint(HAIR, IND)
    L.paint(HAIR * L.halftone(L.ramp((0, 150), (0, 700)) * 0.5, 10, 45), MAG, 0.6)
    # horns
    horn = smooth_closed([(400, 300), (350, 230), (300, 140), (262, 70), (300, 120), (372, 190), (455, 262)], 0.5)
    HORN = L.mask(sym([horn]))
    L.paint(L.dilate(HORN, 10), INK)
    L.paint(HORN, grad(L, 60, 300, C("white"), PAPER, GOLD))
    bands = L.halftone(np.full(HORN.shape, 0.16, f32), 34, -55, shape="line")
    L.paint(HORN * bands, hexc("#B07A10"), 0.6)
    # face
    face = smooth_closed([(cx, 255), (cx + 140, 262), (cx + 228, 330), (cx + 250, 450), (cx + 236, 600), (cx + 190, 720),
                          (cx + 100, 800), (cx, 822), (cx - 100, 800), (cx - 190, 720), (cx - 236, 600), (cx - 250, 450),
                          (cx - 228, 330), (cx - 140, 262)], 0.55)
    FACE = L.mask(face)
    L.paint(L.dilate(FACE, 12), INK)
    L.paint(FACE, grad(L, 255, 822, hexc("#FF6A4A"), RED, hexc("#B5122A")))
    side_shade = np.clip(np.abs(L.ramp((cx - 250, 0), (cx + 250, 0)) - 0.5) * 2 - 0.35, 0, 1)
    L.paint(FACE * L.halftone(side_shade * 0.9, 9, 45), hexc("#7A0A1E"), 0.65)
    # forehead wrinkles
    for k, y in enumerate((300, 330)):
        wpts = cr_sample([(cx - 120 + k * 20, y + 12), (cx - 50, y - 6), (cx, y + 4), (cx + 50, y - 6), (cx + 120 - k * 20, y + 12)], 60)
        L.paint(L.mask(taper_stroke(wpts, 7, 7, prof=lambda t: 2 + 8 * np.sin(np.pi * t))), INK)
    # brows
    brow = poly([(cx - 30, 420), (cx - 210, 340), (cx - 180, 372), (cx - 225, 380), (cx - 175, 400), (cx - 200, 420), (cx - 40, 452)])
    L.paint(L.mask(sym([brow])), INK)
    # eyes
    eye = smooth_closed([(cx - 60, 455), (cx - 120, 430), (cx - 190, 430), (cx - 200, 455), (cx - 140, 488)], 0.6)
    E = L.mask(sym([eye]))
    L.paint(L.dilate(E, 6), INK)
    L.paint(E, grad(L, 430, 490, C("white"), YEL, GOLD))
    for s in (-1, 1):
        L.paint(L.mask(circle(cx + s * 125, 458, 20)) * E, INK)
        L.paint(L.mask(circle(cx + s * 125 - 6, 452, 6)), C("white"))
    # nose
    nose = smooth_closed([(cx, 480), (cx + 40, 560), (cx + 75, 590), (cx + 40, 615), (cx, 600), (cx - 40, 615), (cx - 75, 590), (cx - 40, 560)], 0.6)
    N = L.mask(nose)
    L.paint(L.dilate(N, 6), INK)
    L.paint(N, hexc("#E0283A"))
    L.paint(L.mask(sym([ellipse(cx - 35, 595, 16, 10)])), INK)
    # cheek lines
    for s in (-1, 1):
        cpts = cr_sample([(cx + s * 95, 545), (cx + s * 135, 610), (cx + s * 150, 680)], 40)
        L.paint(L.mask(taper_stroke(cpts, 9, 2)), INK)
    # mouth
    mouth = smooth_closed([(cx, 640), (cx + 110, 638), (cx + 160, 660), (cx + 120, 735), (cx, 755), (cx - 120, 735), (cx - 160, 660), (cx - 110, 638)], 0.55)
    M = L.mask(mouth)
    L.paint(L.dilate(M, 8), INK)
    L.paint(M, hexc("#2A0A18"))
    teeth = L.mask(rect(cx - 120, 630, cx + 120, 668)) * M
    L.paint(teeth, PAPER)
    for k in range(-3, 4):
        L.paint(L.mask(rect(cx + k * 32 - 1.5, 640, cx + k * 32 + 1.5, 668)) * teeth, INK, 0.7)
    fangs = sym([poly([(cx - 105, 650), (cx - 70, 650), (cx - 88, 716)]), poly([(cx - 150, 742), (cx - 105, 742), (cx - 140, 620)])])
    FG = L.mask(fangs)
    L.paint(L.dilate(FG, 5), INK)
    L.paint(FG, grad(L, 620, 742, C("white"), PAPER, hexc("#E8DCC0")))
    c.over(L)


def hexagon(cx, cy, r, rot=0.0):
    return poly([(cx + math.cos(rot + k * math.pi / 3) * r, cy + math.sin(rot + k * math.pi / 3) * r) for k in range(6)])


def bee_icon(L, cx, cy, s, rot=-15):
    m = skia.Matrix(); m.setRotate(rot, cx, cy)
    wings = [xform(ellipse(cx - s * 0.15, cy - s * 0.75, s * 0.42, s * 0.62), m), xform(ellipse(cx + s * 0.35, cy - s * 0.65, s * 0.32, s * 0.5), m)]
    W_ = L.mask(wings)
    L.paint(L.dilate(W_, 6), INK)
    L.paint(W_, hexc("#E8FCFF"))
    L.paint(W_ * L.halftone(np.full(W_.shape, 0.2, f32), 8, 45), CYAN, 0.6)
    body = xform(ellipse(cx, cy, s * 0.95, s * 0.6), m)
    B = L.mask(body)
    L.paint(L.dilate(B, 7), INK)
    L.paint(B, grad(L, cy - s * 0.6, cy + s * 0.6, hexc("#FFF59A"), YEL, GOLD))
    for k in (-0.2, 0.25, 0.65):
        st = xform(rect(cx + s * k - s * 0.1, cy - s, cx + s * k + s * 0.1, cy + s), m)
        L.paint(L.mask(st) * B, INK)
    sting = xform(poly([(cx + s * 0.9, cy - s * 0.12), (cx + s * 1.35, cy), (cx + s * 0.9, cy + s * 0.12)]), m)
    L.paint(L.mask(sting), INK)
    L.paint(L.mask(xform(circle(cx - s * 0.62, cy - s * 0.12, s * 0.1), m)), C("white"))
    # motion trail
    trail = skia.Path()
    trail.moveTo(cx - s * 1.3, cy + s * 0.1)
    trail.cubicTo(cx - s * 2.2, cy + s * 0.9, cx - s * 3.2, cy - s * 0.6, cx - s * 4.2, cy + s * 0.4)
    dash = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=s * 0.12, PathEffect=skia.DashPathEffect.Make([s * 0.35, s * 0.25], 0))
    dst = skia.Path(); dash.getFillPath(trail, dst)
    L.paint(L.mask(dst), INK)


def d_name_hachi(c):
    L = layer()
    band = transformed(poly([(70, 400), (960, 340), (960, 640), (70, 700)]), rotate=0)
    BA = L.mask(band)
    L.paint(L.dilate(BA, 12), INK)
    L.paint(BA, IND)
    hr = 46
    cells = []
    for j in range(-1, 14):
        for i in range(-1, 14):
            x = i * hr * 1.5 + 40
            y = j * hr * math.sqrt(3) + (hr * math.sqrt(3) / 2 if i % 2 else 0) + 250
            cells.append(hexagon(x, y, hr - 5))
    HC = L.mask(cells) * BA
    L.paint(HC, grad(L, 340, 700, YEL, GOLD))
    L.paint(HC * L.halftone(L.ramp((0, 420), (0, 700)) * 0.5, 8, 45), hexc("#A86A00"), 0.6)
    p = T("HACHI", "bangers", (100, 300, 900, 700), skew=-0.1, rot=-4, tracking=0.02)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 300, 700, C("white"), PAPER, hexc("#FFF2A0")), paper_r=0, ink_r=16,
                ext=(16, 14), ext_col=hexc("#2A1A10"))
    # bee stripes on the letters' lower half
    stripes = L.halftone(np.full(F.shape, 0.42, f32), 60, -10, shape="line")
    L.paint(F * stripes * smoothstep(0.55, 0.6, L.ramp((0, 300), (0, 700))), INK, 0.9)
    gloss(L, F, (100, 300, 900, 700), 0.6, color=C("white"))
    bee_icon(L, 800, 215, 70)
    tag = poly([(110, 735), (360, 722), (366, 820), (114, 832)])
    TG = L.mask(tag)
    L.paint(L.dilate(TG, 8), INK)
    L.paint(TG, MAG)
    L.paint(L.mask(T("ハチ", "dela", (140, 736, 336, 818), rot=-3)), PAPER)
    hb = hexagon(820, 775, 92, rot=math.pi / 6)
    HB = L.mask(hb)
    L.paint(L.dilate(HB, 10), INK)
    L.paint(HB, YEL)
    L.paint(L.mask(T("08", "chakra", (762, 728, 878, 818), skew=-0.15)), INK)
    diecut(c, L, 16)


def slash_paths(x0, y0, x1, y1, n=3, gap=70, w=60, bend=60):
    out = []
    dx, dy = x1 - x0, y1 - y0
    Ln = math.hypot(dx, dy)
    nx, ny = -dy / Ln, dx / Ln
    for k in range(n):
        o = (k - (n - 1) / 2) * gap
        pts = []
        for i in range(60):
            t = i / 59
            b = math.sin(t * math.pi) * bend
            pts.append((x0 + dx * t + nx * (o + b), y0 + dy * t + ny * (o + b)))
        out.append(taper_stroke(np.array(pts), 0, 0, prof=lambda t: w * np.sin(np.pi * np.clip(t, 0, 1)) ** 0.7 + 1))
    return out


def d_name_kaiju(c):
    L = layer()
    r = rng(121)
    # dorsal spikes silhouette behind
    sp = []
    for i in range(9):
        x = 150 + i * 92
        h = 130 + 70 * math.sin(i / 8 * math.pi) + r.uniform(-15, 15)
        sp.append(poly([(x - 52, 470), (x - 18, 470 - h * 0.6), (x, 470 - h), (x + 14, 470 - h * 0.55), (x + 52, 470)]))
    SP = L.mask(sp)
    L.paint(L.dilate(SP, 10), INK)
    L.paint(SP, grad(L, 250, 470, CYAN, hexc("#2A6CFF"), IND))
    p = T("KAIJU", "dela", (80, 380, 944, 700), skew=-0.14, rot=-3)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 380, 700, hexc("#E8FFB0"), LIME, hexc("#3FBF2A")), paper_r=8, ink_r=14,
                ext=(14, 16), ext_col=hexc("#4A1A7A"))
    ht_shade(L, F, hexc("#1F7A1A"), (0, 560), (0, 700), period=8, amount=0.5)
    gloss(L, F, (80, 380, 944, 700), 0.5, color=C("white"))
    t = T("怪獣", "reggae", (110, 175, 420, 360), rot=-8)
    TF = L.mask(t)
    comic_stack(L, TF, grad(L, 175, 360, SAK, MAG), paper_r=6, ink_r=10, ext=(8, 8), ext_col=INK)
    # claw slashes cut through everything
    S = L.mask(slash_paths(1000, 250, 790, 690, n=3, gap=50, w=16, bend=25))
    rim = np.clip(L.dilate(S, 9) - S, 0, 1) * (L.alpha() > 0.5)
    L.erase(L.dilate(S, 3))
    L.paint(rim * (1 - S), MAG)
    L.paint(L.mask(flecks(880, 470, 150, 30, (2, 8), rng(122), sigma=0.45)) * (1 - L.dilate(S, 3)), MAG)
    shift_layer(L, 0, 70)
    c.over(L)


def d_name_zenkai(c):
    L = layer()
    cx, cy, R = 512, 450, 330
    face = L.mask(circle(cx, cy, R))
    L.paint(L.dilate(face, 14), INK)
    L.paint(face, grad(L, cy - R, cy + R, hexc("#2A2370"), IND, hexc("#0E0A22")))
    L.paint(face * L.halftone(np.clip(1 - L.radial(cx, cy - 80, R), 0, 1) * 0.45, 11, 45), CYAN, 0.35)
    ring = L.mask(circle(cx, cy, R - 6), stroke=12, fill=False)
    L.paint(ring, PAPER)
    a0, a1 = 135, 405
    # redline band 7..9
    red = skia.Path()
    rr = R - 46
    red.addArc(skia.Rect.MakeLTRB(cx - rr, cy - rr, cx + rr, cy + rr), a0 + (a1 - a0) * 7 / 9, (a1 - a0) * 2 / 9)
    L.paint(L.mask(red, stroke=40, fill=False, cap="butt"), hgrad(L, 600, 840, MAG, RED))
    ticks = []
    for i in range(0, 91):
        v = i / 10
        a = math.radians(a0 + (a1 - a0) * v / 9)
        major = i % 10 == 0
        half = i % 5 == 0
        r0 = R - (78 if major else 58 if half else 44)
        r1 = R - 26
        wd = 9 if major else 5 if half else 3
        ticks.append(stroke_outline(poly([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1)], close=False), wd))
    L.paint(L.mask(ticks), PAPER)
    nums = []
    for k in range(10):
        a = math.radians(a0 + (a1 - a0) * k / 9)
        rn = R - 118
        x, y = cx + math.cos(a) * rn, cy + math.sin(a) * rn
        nums.append(fit_path(text_path(str(k), "chakra", 100), (x - 26, y - 30, x + 26, y + 30)))
    L.paint(L.mask(nums[:7]), PAPER)
    L.paint(L.mask(nums[7:]), MAG)
    L.paint(L.mask(T("x1000 r/min", "chakra_reg", (cx - 80, cy - 120, cx + 80, cy - 92))), CYAN)
    # needle pinned past redline
    an = math.radians(a0 + (a1 - a0) * 8.6 / 9)
    tip = (cx + math.cos(an) * (R - 40), cy + math.sin(an) * (R - 40))
    nrm = (-math.sin(an), math.cos(an))
    needle = poly([(cx - math.cos(an) * 50 + nrm[0] * 14, cy - math.sin(an) * 50 + nrm[1] * 14), tip,
                   (cx - math.cos(an) * 50 - nrm[0] * 14, cy - math.sin(an) * 50 - nrm[1] * 14)])
    NM = L.mask(needle)
    L.paint(L.dilate(NM, 5), INK)
    L.paint(NM, hgrad(L, cx, tip[0], YEL, hexc("#FF6A1F")))
    hub = L.mask(circle(cx, cy, 34))
    L.paint(L.dilate(hub, 5), INK)
    L.paint(hub, grad(L, cy - 34, cy + 34, C("white"), hexc("#8A8AA0")))
    # 全開 in the dial
    k = L.mask(T("全開", "dela", (cx - 100, cy + 70, cx + 100, cy + 160)))
    L.paint(L.dilate(k, 6), INK)
    L.paint(k, YEL)
    # ZENKAI wordmark
    p = T("ZENKAI", "chakra", (70, 720, 954, 930), skew=-0.25)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 720, 930, C("white"), CYAN, hexc("#0090C0")), paper_r=0, ink_r=14,
                ext=(12, 10), ext_col=MAG)
    gloss(L, F, (70, 720, 954, 930), 0.5, color=C("white"))
    # speed streaks
    for k_, y in enumerate((760, 800, 840, 880)):
        st = L.mask(poly([(20, y), (110 - k_ * 10, y - 6), (110 - k_ * 10, y + 6)]))
        L.paint(L.dilate(st, 3), INK)
        L.paint(st, MAG)
    c.over(L)


def d_name_raijin(c):
    L = layer()
    r = rng(141)
    # classic comic bolts behind the plate edges
    def bolt(x, y, s, flip=1):
        pts = [(0, 0), (60, 0), (30, 110), (75, 110), (-20, 300), (10, 160), (-35, 160)]
        return poly([(x + px * s * flip, y + py * s) for px, py in pts])
    for (x, y, s, fl) in ((200, 70, 1.15, 1), (800, 50, 1.25, -1), (470, 30, 0.8, 1)):
        BM = L.mask(bolt(x, y, s, fl))
        L.paint(L.dilate(BM, 10), INK)
        L.paint(BM, grad(L, y, y + 300 * s, C("white"), YEL, hexc("#FFB000")))
    plate = poly([(60, 380), (300, 330), (330, 290), (560, 340), (600, 290), (964, 330), (930, 700), (720, 660),
                  (690, 720), (420, 670), (380, 720), (90, 690)])
    PL = L.mask(plate)
    L.paint(L.dilate(PL, 14), INK)
    L.paint(PL, grad(L, 290, 720, hexc("#3A1F8A"), IND))
    L.paint(PL * L.halftone(L.ramp((0, 300), (0, 720)) * 0.5, 10, 45), hexc("#8A4DFF"), 0.6)
    p = T("RAIJIN", "bangers", (100, 350, 924, 680), skew=-0.12, tracking=0.03)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 350, 680, C("white"), YEL, hexc("#FFB000")), paper_r=0, ink_r=15,
                ext=(14, 14), ext_col=hexc("#5A2AB0"))
    ht_shade(L, F, hexc("#C07A00"), (0, 540), (0, 680), period=8, amount=0.5)
    gloss(L, F, (100, 350, 924, 680), 0.55, color=C("white"))
    box = transformed(rect(620, 700, 920, 830, radius=10), rotate=-5)
    BX = L.mask(box)
    L.paint(L.dilate(BX, 8), INK)
    L.paint(BX, CYAN)
    L.paint(L.mask(T("雷神", "dela", (650, 712, 890, 818), rot=-5)), INK)
    # electric arcs
    arcs = []
    for k in range(9):
        a = r.uniform(0, 2 * math.pi)
        x, y = 512 + math.cos(a) * r.uniform(380, 450), 512 + math.sin(a) * r.uniform(250, 330)
        pts = [(x, y)]
        for _ in range(5):
            x += r.uniform(-30, 30); y += r.uniform(-30, 30)
            pts.append((x, y))
        arcs.append(stroke_outline(poly(pts, close=False), 5, join="miter"))
    A = L.mask(arcs)
    L.paint(L.dilate(A, 3), INK)
    L.paint(A, CYAN)
    c.over(L)


def swallow_path():
    """Top-view swallow facing +x: scythe wings swept back, deep forked tail. Symmetric in y."""
    segs = [("q", (185, -24), (140, -26)), ("q", (100, -30), (78, -30)),
            ("c", (40, -140), (-90, -260), (-340, -300)),       # leading edge -> wing tip (swept back)
            ("c", (-190, -235), (-60, -120), (8, -34)),          # trailing edge back to body
            ("q", (-40, -30), (-70, -24)),
            ("q", (-190, -46), (-400, -118)),                    # outer tail streamer
            ("q", (-230, -26), (-150, 0))]                       # into the fork notch
    p = skia.Path()
    p.moveTo(205, 0)
    for s in segs:
        if s[0] == "q":
            p.quadTo(*s[1], *s[2])
        else:
            p.cubicTo(*s[1], *s[2], *s[3])
    # mirrored half, walked in reverse back to the beak
    pts = [(205, 0)]
    for s in segs:
        pts.append(s[-1])
    rev = list(reversed(segs))
    ends = list(reversed(pts[:-1]))
    for s, e in zip(rev, ends):
        if s[0] == "q":
            p.quadTo(s[1][0], -s[1][1], e[0], -e[1])
        else:
            p.cubicTo(s[2][0], -s[2][1], s[1][0], -s[1][1], e[0], -e[1])
    p.close()
    return p


def d_name_tsubame(c):
    L = layer()
    bird = swallow_path()
    m = skia.Matrix()
    m.setScale(1.12, 1.12)
    m.postRotate(-20)
    m.postTranslate(590, 390)
    bird = xform(bird, m)
    # speed trails
    trails = []
    for k, (y, ln) in enumerate(((470, 380), (520, 300), (420, 260), (570, 220))):
        pts = np.array([(80 + t * ln, y + 120 - t * ln * 0.45) for t in np.linspace(0, 1, 30)])
        trails.append(taper_stroke(pts, 2, 14))
    TR = L.mask(trails)
    L.paint(L.dilate(TR, 4), INK)
    L.paint(TR, CYAN)
    BM = L.mask(bird)
    L.paint(L.dilate(BM, 14), INK)
    L.paint(BM, grad(L, 80, 700, hexc("#3B3BB0"), IND, hexc("#0B0B30")))
    # wing highlights
    hl = L.halftone(L.ramp((300, 100), (700, 600)) * 0.6, 9, 45)
    L.paint(BM * hl, CYAN, 0.55)
    belly = xform(ellipse(40, 0, 110, 14), m)
    L.paint(L.mask(belly) * BM, PAPER)
    throat = xform(ellipse(160, 0, 36, 14), m)
    L.paint(L.mask(throat) * BM, MAG)
    eye = xform(circle(170, -12, 6), m)
    L.paint(L.mask(eye), C("white"))
    p = T("TSUBAME", "chakra", (70, 720, 954, 880), skew=-0.28)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 720, 880, C("white"), PAPER, SAK), paper_r=0, ink_r=13,
                ext=(12, 10), ext_col=MAG)
    gloss(L, F, (70, 720, 954, 880), 0.4, color=C("white"))
    badge = L.mask(circle(170, 230, 92))
    L.paint(L.dilate(badge, 10), INK)
    L.paint(badge, CYAN)
    L.paint(L.mask(circle(170, 230, 74), stroke=6, fill=False), INK)
    L.paint(L.mask(T("燕", "dela", (118, 178, 222, 282))), INK)
    st = L.mask(poly([(70, 900), (720, 892), (716, 908), (70, 916)]))
    L.paint(st, MAG)
    c.over(L)


def plate(c, base_col, text_col, region, cls, kana, num, seed):
    """Japanese-format (fictional) licence plate, 2:1, centred."""
    L = layer()
    x0, y0, x1, y1 = 32, 272, 992, 752
    W, H = x1 - x0, y1 - y0
    P = L.mask(rect(x0, y0, x1, y1, radius=34))
    L.paint(L.shift(L.blur(P, 4), 0, 6), C("black"), 0.35)
    L.paint(P, grad(L, y0, y1, base_col * 1.0, base_col * 0.93))
    rim = L.erode(P, 10) * (1 - L.erode(P, 18))
    L.paint(rim, C("black"), 0.10)
    L.paint(L.erode(P, 18) * (1 - L.erode(P, 20)), C("white"), 0.5)
    for bx in (x0 + W * 0.20, x0 + W * 0.80):
        by = y0 + H * 0.13
        bolt = L.mask(circle(bx, by, 22))
        L.paint(L.dilate(bolt, 3), C("black"), 0.4)
        L.paint(bolt, grad(L, by - 22, by + 22, hexc("#F4F4F8"), hexc("#8C8C96")))
        L.paint(L.mask(rect(bx - 15, by - 3, bx + 15, by + 3)), hexc("#55555F"))

    def emboss(path, col):
        M = L.mask(path)
        L.paint(L.shift(M, 2.5, 3.5), C("black"), 0.28)
        L.paint(L.shift(M, -1.5, -1.5), C("white"), 0.45)
        L.paint(M, col)
    top = T(f"{region} {cls}", "noto_bold", (x0 + W * 0.28, y0 + H * 0.08, x0 + W * 0.72, y0 + H * 0.33), mode="fill", tracking=0.08)
    emboss(top, text_col)
    emboss(T(kana, "noto_bold", (x0 + W * 0.05, y0 + H * 0.56, x0 + W * 0.17, y0 + H * 0.80)), text_col)
    emboss(T(num, "noto_bold", (x0 + W * 0.21, y0 + H * 0.38, x0 + W * 0.95, y0 + H * 0.92), mode="fill", tracking=0.02), text_col)
    # light grime
    g = smoothstep(0.55, 0.85, L.noise(30, seed, beta=2.0)) * P
    L.paint(g, hexc("#6A604A"), 0.12)
    L.paint(L.mask(poly([(x0 + W * 0.55, y0), (x0 + W * 0.68, y0), (x0 + W * 0.45, y1), (x0 + W * 0.32, y1)])) * P, C("white"), 0.10)
    c.over(L)


def d_plate_private(c):
    plate(c, hexc("#F7F6F0"), hexc("#11683D"), "練馬", "330", "ゆ", "19-86", 151)


def d_plate_kei(c):
    plate(c, hexc("#F4C51C"), hexc("#111111"), "多摩", "580", "か", "88-08", 152)


def cloth_tail(pts, w, cut_angle=35):
    """Constant-width cloth ribbon along pts with a diagonal cut end."""
    P = cr_sample(pts, 80)
    p = taper_stroke(P, w, w)
    d = P[-1] - P[-3]; d /= np.linalg.norm(d)
    nn = np.array([-d[1], d[0]])
    e = P[-1]
    cut = poly([tuple(e + nn * w + d * w * 0.6), tuple(e - nn * w - d * w * 0.6), tuple(e - nn * w + d * w * 3), tuple(e + nn * w + d * w * 3)])
    return skia.Op(p, cut, skia.PathOp.kDifference_PathOp)


def d_hachimaki(c):
    L = layer()
    n = 90
    xs = np.linspace(40, 745, n)
    top = [(x, 395 + 22 * math.sin(x / 150 + 0.3)) for x in xs]
    bot = [(x, 615 + 16 * math.sin(x / 150 + 0.8)) for x in xs[::-1]]
    band = poly(top + bot)
    t1 = cloth_tail([(790, 520), (850, 640), (820, 760), (860, 890)], 100)
    t2 = cloth_tail([(800, 500), (895, 560), (935, 650), (915, 740)], 86)
    knot = smooth_closed([(715, 430), (805, 405), (870, 470), (860, 580), (800, 630), (720, 600)], 0.6)
    T1, T2, BD, KN = L.mask(t1), L.mask(t2), L.mask(band), L.mask(knot)
    cloth_hi, cloth_lo = C("white"), hexc("#E6DCC4")
    shade = hexc("#B9AE94")
    for M in (T2, T1):
        L.paint(L.dilate(M, 9), INK)
        L.paint(M, grad(L, 480, 920, cloth_hi, cloth_lo))
        L.paint(M * L.halftone(L.ramp((0, 520), (0, 920)) * 0.45, 8, 45), shade, 0.7)
    L.paint(L.dilate(BD, 9), INK)
    L.paint(BD, grad(L, 380, 640, cloth_hi, PAPER, cloth_lo))
    L.paint(BD * L.halftone(L.ramp((0, 520), (0, 640)) * 0.4, 8, 45), shade, 0.55)
    for k, (xa, xb, ya) in enumerate(((60, 230, 430), (330, 520, 600), (560, 740, 440))):
        cpts = cr_sample([(xa, ya), ((xa + xb) / 2, (ya + 515) / 2), (xb, 520)], 30)
        L.paint(L.mask(taper_stroke(cpts, 3, 3, prof=lambda t: 1 + 7 * np.sin(np.pi * t))) * BD, shade, 0.55)
    F = L.mask(T("必勝", "reggae", (180, 405, 600, 610)))
    B = dry_brush(L, F, 153, amount=0.7, wobble=3, scale=6)
    L.paint(B * L.erode(BD, 3), INK)
    L.paint(L.dilate(KN, 9), INK)
    L.paint(KN, grad(L, 405, 630, cloth_hi, cloth_lo))
    L.paint(KN * L.halftone(np.clip(L.radial(785, 520, 120), 0, 1) * 0.5, 8, 45), shade, 0.7)
    kl = cr_sample([(745, 450), (790, 520), (755, 590)], 30)
    L.paint(L.mask(taper_stroke(kl, 3, 3, prof=lambda t: 2 + 6 * np.sin(np.pi * t))), shade)
    hanko(L, 655, 505, 92, "全開", 154, rot=-4)
    L.paint(L.mask(T("INK DRIFT", "bangers", (55, 445, 170, 500), tracking=0.06, rot=-3)), RED)
    c.over(L)


def d_sponsor_tanuki(c):
    L = layer()
    box = rect(70, 330, 954, 694, radius=46)
    B = L.mask(box)
    L.paint(B, INK)
    L.paint(L.mask(rect(84, 344, 940, 680, radius=36), stroke=5, fill=False), YEL)
    # tire icon
    tx, ty, tr = 250, 512, 130
    tire = L.mask(circle(tx, ty, tr))
    L.paint(tire, hexc("#2A2A35"))
    blocks = []
    for k in range(16):
        a = k * 2 * math.pi / 16
        blocks.append(xform(rect(tr - 26, -13, tr + 2, 13), skia.Matrix.RotateRad(a)))
    BL = L.mask([xform(b, skia.Matrix.Translate(tx, ty)) for b in blocks]) * tire
    L.paint(BL, YEL)
    rim = L.mask(circle(tx, ty, tr * 0.62))
    L.paint(rim, grad(L, ty - 80, ty + 80, C("white"), hexc("#9A9AB0")))
    spokes = [xform(rect(-8, -tr * 0.55, 8, -tr * 0.12), skia.Matrix.RotateDeg(k * 72)) for k in range(5)]
    L.paint(L.mask([xform(s, skia.Matrix.Translate(tx, ty)) for s in spokes]), hexc("#2A2A35"))
    L.paint(L.mask(circle(tx, ty, 18)), hexc("#2A2A35"))
    leaf = smooth_closed([(tx - 10, ty - tr - 60), (tx + 50, ty - tr - 120), (tx + 30, ty - tr - 40), (tx - 5, ty - tr - 10)], 0.6)
    LF = L.mask(leaf)
    L.paint(L.dilate(LF, 6), INK)
    L.paint(LF, LIME)
    L.paint(L.mask(T("TANUKI", "bangers", (410, 360, 920, 530), skew=-0.12, tracking=0.04)), YEL)
    L.paint(L.mask(T("TIRES", "bangers", (560, 525, 920, 615), skew=-0.12, tracking=0.25)), PAPER)
    L.paint(L.mask(T("GRIP OR DIE  /  タヌキタイヤ", "noto_bold", (415, 625, 920, 662))), CYAN)
    diecut(c, L, 10)


def d_sponsor_hayate(c):
    L = layer()
    para = poly([(130, 340), (980, 340), (894, 690), (44, 690)])
    P = L.mask(para)
    L.paint(L.dilate(P, 10), INK)
    L.paint(P, grad(L, 340, 690, hexc("#7FF4FF"), CYAN, hexc("#00A8C8")))
    L.paint(P * L.halftone(L.ramp((500, 0), (980, 0)) * 0.5, 9, 45), C("white"), 0.6)
    sq = poly([(150, 360), (380, 360), (322, 670), (92, 670)])
    S = L.mask(sq)
    L.paint(S, INK)
    L.paint(L.mask(V("疾風", "dela", (170, 380, 320, 650), spacing=1.0, mode="fill")), PAPER)
    L.paint(L.mask(T("HAYATE", "chakra", (390, 370, 940, 530), skew=-0.3)), INK)
    L.paint(L.mask(T("TURBO", "chakra", (420, 535, 760, 640), skew=-0.3, tracking=0.12)), MAG)
    # turbo snail spiral icon
    sp = spiral_pts(845, 590, 58, turns=2.2, a0=0, shrink=0.88, sgn=1, tail=0)
    L.paint(L.mask(taper_stroke(sp, 5, 14)), INK)
    L.paint(L.mask(circle(845, 590, 64), stroke=8, fill=False), INK)
    for k in range(4):
        y = 380 + k * 34
        L.paint(L.mask(poly([(960 - k * 8, y), (1010, y - 4), (1010, y + 4)])), INK)
    c.over(L)


def d_sponsor_sumi_oil(c):
    L = layer()
    ov = ellipse(512, 512, 450, 280)
    O = L.mask(ov)
    L.paint(L.dilate(O, 10), PAPER)
    L.paint(L.dilate(O, 4), INK)
    L.paint(O, INK)
    L.paint(L.mask(ellipse(512, 512, 418, 250), stroke=10, fill=False), MAG)
    L.paint(L.mask(ellipse(512, 512, 396, 228), stroke=4, fill=False), PAPER)
    drop = smooth_closed([(512, 280), (560, 360), (575, 405), (548, 448), (512, 456), (476, 448), (449, 405), (464, 360)], 0.5)
    D = L.mask(drop)
    L.paint(D, grad(L, 280, 456, CYAN, hexc("#007FA0")))
    L.paint(L.mask(ellipse(530, 410, 10, 18)), C("white"), 0.8)
    k = L.mask(T("墨油", "dela", (310, 460, 714, 640)))
    L.paint(L.dilate(k, 5), MAG)
    L.paint(k, PAPER)
    L.paint(L.mask(T("SUMI OIL", "bangers", (380, 645, 644, 715), tracking=0.12)), YEL)
    L.paint(L.mask(T("HIGH-REV MOTOR OIL", "chakra", (390, 722, 634, 748), tracking=0.1)), PAPER, 0.85)
    c.over(L)


def d_sponsor_neko(c):
    L = layer()
    shield = smooth_closed([(170, 300), (512, 270), (854, 300), (850, 600), (512, 760), (174, 600)], 0.25)
    S = L.mask(shield)
    L.paint(L.dilate(S, 12), INK)
    L.paint(S, grad(L, 270, 760, hexc("#FF77AA"), MAG, hexc("#C0105A")))
    L.paint(S * L.halftone(L.ramp((0, 450), (0, 760)) * 0.5, 9, 45), hexc("#7A0038"), 0.5)
    # brake disc with cat ears
    dx, dy, dr = 512, 390, 96
    ears = L.mask([poly([(dx - 90, dy - 40), (dx - 70, dy - 135), (dx - 20, dy - 85)]), poly([(dx + 90, dy - 40), (dx + 70, dy - 135), (dx + 20, dy - 85)])])
    L.paint(L.dilate(ears, 7), INK)
    L.paint(ears, PAPER)
    disc = L.mask(circle(dx, dy, dr))
    L.paint(L.dilate(disc, 7), INK)
    L.paint(disc, grad(L, dy - dr, dy + dr, C("white"), hexc("#A8A8BC")))
    holes = []
    for ring_r, cnt in ((70, 12), (48, 8)):
        for k in range(cnt):
            a = k * 2 * math.pi / cnt + ring_r
            holes.append(circle(dx + math.cos(a) * ring_r, dy + math.sin(a) * ring_r, 6))
    L.paint(L.mask(holes), INK)
    L.paint(L.mask(circle(dx, dy, 30)), INK)
    cal = L.mask(rect(dx + 60, dy - 70, dx + 110, dy + 10, radius=14))
    L.paint(L.dilate(cal, 5), INK)
    L.paint(cal, YEL)
    for s in (-1, 1):  # whiskers
        for k in (-1, 0, 1):
            L.paint(L.mask(stroke_outline(poly([(dx + s * 105, dy + 10 + k * 14), (dx + s * 165, dy + k * 26)], close=False), 5, cap="round")), INK)
    F = L.mask(T("NEKO", "dela", (250, 505, 774, 625)))
    L.paint(L.dilate(F, 8), INK)
    L.paint(F, PAPER)
    L.paint(L.mask(T("BRAKES", "bangers", (360, 628, 664, 690), tracking=0.2)), INK)
    L.paint(L.mask(T("ネコブレーキ", "noto_bold", (420, 692, 604, 720))), PAPER)
    c.over(L)


def petal(L, cx, cy, ln, wd, ang):
    p = skia.Path()
    p.moveTo(0, 0)
    p.cubicTo(-wd * 0.7, ln * 0.25, -wd * 0.62, ln * 0.85, -wd * 0.22, ln)
    p.lineTo(0, ln * 0.86)
    p.lineTo(wd * 0.22, ln)
    p.cubicTo(wd * 0.62, ln * 0.85, wd * 0.7, ln * 0.25, 0, 0)
    p.close()
    m = skia.Matrix(); m.setRotate(ang); m.postTranslate(cx, cy)
    return xform(p, m)


def sakura_flower(L, cx, cy, r, rot):
    ps = [petal(L, cx, cy, r, r * 0.8, rot + k * 72) for k in range(5)]
    M = L.mask(ps)
    L.paint(L.dilate(M, 7), INK)
    L.paint(M, gradient_map(L.radial(cx, cy, r), [(0, hexc("#FF6FA8")), (0.35, SAK), (1, C("white"))]))
    for p in ps:
        L.paint(L.mask(p, stroke=2.5, fill=False), hexc("#E07AA0"), 0.7)
    ctr = L.mask(circle(cx, cy, r * 0.18))
    L.paint(ctr, MAG)
    for k in range(10):
        a = math.radians(rot + k * 36 + 18)
        x, y = cx + math.cos(a) * r * 0.42, cy + math.sin(a) * r * 0.42
        L.paint(L.mask(stroke_outline(poly([(cx, cy), (x, y)], close=False), 2.5)), MAG)
        L.paint(L.mask(circle(x, y, r * 0.045)), YEL)
    return M


def d_sakura(c):
    L = layer()
    r = rng(171)
    for (x, y, s, rot) in ((420, 420, 210, 10), (690, 330, 140, -15), (650, 640, 165, 30), (280, 690, 120, 5), (820, 560, 90, 50)):
        sakura_flower(L, x, y, s, rot)
    for k in range(9):
        x, y = r.uniform(120, 920), r.uniform(120, 920)
        if 250 < x < 800 and 250 < y < 760:
            continue
        p = petal(L, x, y, 70, 56, r.uniform(0, 360))
        M = L.mask(p)
        L.paint(L.dilate(M, 5), INK)
        L.paint(M, SAK)
        tr = L.mask(stroke_outline(poly([(x - 100, y + 20), (x - 30, y + 6)], close=False), 4, cap="round"))
        L.paint(tr, INK, 0.8)
    c.over(L)


def d_zenkai_kanji(c):
    L = layer()
    r = rng(181)
    # speed lines
    lines = []
    for k in range(18):
        y = r.uniform(250, 780)
        x1 = r.uniform(700, 1000)
        lines.append(poly([(x1 - r.uniform(300, 600), y), (x1, y - r.uniform(3, 8)), (x1, y + r.uniform(3, 8))]))
    LN = L.mask(lines)
    L.paint(LN, INK)
    p = T("全開", "dela", (90, 240, 934, 700), skew=-0.18, rot=-3)
    F = L.mask(p)
    comic_stack(L, F, grad(L, 240, 700, YEL, hexc("#FF8A1F"), RED), paper_r=10, ink_r=15,
                ext=(18, 16), ext_col=hexc("#4A0A20"))
    ht_shade(L, F, hexc("#A0001E"), (0, 480), (0, 700), period=9, amount=0.55)
    gloss(L, F, (90, 240, 934, 700), 0.55, color=C("white"))
    rb = ribbon(512, 790, 560, 90, angle=-3, tail=0.16, skew=0.25)
    for k, col in (("tails", darken(MAG, 0.35)), ("folds", INK), ("band", MAG)):
        M = L.mask(rb[k])
        L.paint(L.dilate(M, 6), INK)
        L.paint(M, col)
    L.paint(L.mask(T("FULL THROTTLE", "bangers", (300, 755, 724, 828), rot=-3, tracking=0.08)), PAPER)
    c.over(L)


def d_speed_stripes(c):
    L = layer()
    cols = [MAG, CYAN, YEL]
    for k in range(3):
        y = 380 + k * 120
        pts = np.array([(40 + t * 940, y - t * 150 + 20 * math.sin(t * 3)) for t in np.linspace(0, 1, 80)])
        p = taper_stroke(pts, 0, 0, prof=lambda t: 90 * (1 - t) ** 0.6 + 2)
        M = L.mask(p)
        dots = L.halftone(np.clip(1.15 - L.ramp((420, 0), (980, 0)) * 1.1, 0, 1), 16, 30)
        fade = smoothstep(0.35, 0.55, L.ramp((40, 0), (980, 0)))
        Mh = M * (1 - fade) + M * dots * fade
        L.paint(L.dilate(Mh, 7), INK)
        L.paint(Mh, cols[k])
        L.paint(Mh * L.mask(taper_stroke(pts + np.array([0, -22]), 0, 0, prof=lambda t: 18 * (1 - t) ** 0.8)), C("white"), 0.55)
    # chevrons at the front
    for k in range(3):
        x = 70 + k * 70
        ch = poly([(x, 300), (x + 50, 300), (x + 110, 470), (x + 50, 640), (x, 640), (x + 60, 470)])
        M = L.mask(ch)
        L.paint(L.dilate(M, 7), INK)
        L.paint(M, PAPER)
    c.over(L)


DESIGNS = {
    "livery_team_inkdrift": d_team_inkdrift,
    "livery_sumi_racing": d_sumi_racing,
    "livery_ryu_brush": d_ryu,
    "livery_drift_graffiti": d_drift_graffiti,
    "livery_kamikaze": d_kamikaze,
    "livery_tokyo": d_tokyo,
    "livery_flames": d_flames,
    "livery_koi": d_koi,
    "livery_oni": d_oni,
    "livery_name_hachi": d_name_hachi,
    "livery_name_kaiju": d_name_kaiju,
    "livery_name_zenkai": d_name_zenkai,
    "livery_name_raijin": d_name_raijin,
    "livery_name_tsubame": d_name_tsubame,
    "livery_plate_private": d_plate_private,
    "livery_plate_kei": d_plate_kei,
    "livery_hachimaki": d_hachimaki,
    "livery_sponsor_tanuki_tires": d_sponsor_tanuki,
    "livery_sponsor_hayate_turbo": d_sponsor_hayate,
    "livery_sponsor_sumi_oil": d_sponsor_sumi_oil,
    "livery_sponsor_neko_brakes": d_sponsor_neko,
    "livery_sakura": d_sakura,
    "livery_zenkai_kanji": d_zenkai_kanji,
    "livery_speed_stripes": d_speed_stripes,
}


def fit_margin(c, margin=24):
    """Guarantee >= margin px of transparent border: translate (and if needed uniformly
    shrink) the finished artwork so its alpha bbox sits inside [margin, S-margin]."""
    import cv2
    a = c.px[..., 3]
    ys, xs = np.where(a > 0.004)
    if len(xs) == 0:
        return
    s_ = c.ss
    x0, x1, y0, y1 = xs.min() / s_, (xs.max() + 1) / s_, ys.min() / s_, (ys.max() + 1) / s_
    lo, hi = margin, S - margin
    if x0 >= lo and y0 >= lo and x1 <= hi and y1 <= hi:
        return
    k = min(1.0, (hi - lo) / (x1 - x0), (hi - lo) / (y1 - y0))
    w, h = (x1 - x0) * k, (y1 - y0) * k
    # keep position where possible, clamp into the safe box
    nx0 = min(max(lo, (x0 + x1) / 2 - w / 2), hi - w)
    ny0 = min(max(lo, (y0 + y1) / 2 - h / 2), hi - h)
    M = np.float32([[k, 0, (nx0 - x0 * k) * s_], [0, k, (ny0 - y0 * k) * s_]])
    c.px = cv2.warpAffine(c.px, M, (c.W, c.H), flags=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    print(f"  fit_margin: scale {k:.3f}, moved to ({nx0:.0f},{ny0:.0f})")


def render(name):
    c = Canvas(S, S, ss=SS)
    DESIGNS[name](c)
    fit_margin(c, 24)
    p = out_path("Decals", name + ".png")
    c.save(p)
    print("wrote", p)
    return p


def check_margins(min_px=16, names=None):
    """Every livery decal must keep its alpha bbox >= min_px from each canvas edge."""
    from PIL import Image
    bad = []
    for n in (names or DESIGNS):
        pth = os.path.join(ART, "Decals", n + ".png")
        if not os.path.exists(pth):
            continue
        a = np.asarray(Image.open(pth))[..., 3]
        ys, xs = np.where(a > 2)
        h, w = a.shape
        m = (xs.min(), ys.min(), w - 1 - xs.max(), h - 1 - ys.max())
        ok = min(m) >= min_px
        print(f"margin {'OK ' if ok else 'BAD'} {n:34s} L{m[0]:4d} T{m[1]:4d} R{m[2]:4d} B{m[3]:4d}")
        if not ok:
            bad.append(n)
    return bad


def preview():
    paths = [os.path.join(ART, "Decals", n + ".png") for n in DESIGNS]
    paths = [p for p in paths if os.path.exists(p)]
    contact_sheet(paths, os.path.join(PREVIEWS, "livery.png"), cell=(300, 300), cols=6, bg="checker",
                  title="LIVERY DECALS (checker)")
    preview_on(paths, os.path.join(PREVIEWS, "livery_on_paint.png"), car_paint_bg, cell=(300, 300), cols=6,
               title="LIVERY DECALS (on car paint)", frame=False)


if __name__ == "__main__":
    sel = sys.argv[1:]
    for n in DESIGNS:
        if not sel or any(s in n for s in sel):
            render(n)
    bad = check_margins()
    preview()
    if bad:
        raise SystemExit(f"margin check failed: {bad}")
