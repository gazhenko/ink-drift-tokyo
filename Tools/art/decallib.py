"""decallib — helpers shared by gen_road_decals.py and gen_livery.py (INK DRIFT: TOKYO).

Builds on inklib (do not edit inklib from here). Everything deterministic / seeded.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import skia
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import *  # noqa: F401,F403
from inklib import f32

DECALS = os.path.join(ART, "Decals")


# --------------------------------------------------------------------------------------
# path utilities
# --------------------------------------------------------------------------------------
def stroke_outline(path: skia.Path, width: float, join="miter", cap="butt", miter=6.0) -> skia.Path:
    """Convert a stroked centre-line into a fill outline path (so it can be stretched later)."""
    paint = skia.Paint(Style=skia.Paint.kStroke_Style, StrokeWidth=width)
    paint.setStrokeJoin({"round": skia.Paint.kRound_Join, "miter": skia.Paint.kMiter_Join,
                         "bevel": skia.Paint.kBevel_Join}[join])
    paint.setStrokeCap({"round": skia.Paint.kRound_Cap, "butt": skia.Paint.kButt_Cap,
                        "square": skia.Paint.kSquare_Cap}[cap])
    paint.setStrokeMiter(miter)
    dst = skia.Path()
    paint.getFillPath(path, dst)
    return dst


def xform(path: skia.Path, m: skia.Matrix) -> skia.Path:
    p = skia.Path(path)
    p.transform(m)
    return p


def mirror_x(path: skia.Path, cx: float) -> skia.Path:
    m = skia.Matrix()
    m.setScale(-1, 1, cx, 0)
    return xform(path, m)


def glyph(ch: str, font: str, size: float = 200) -> skia.Path:
    return text_path(ch, font, size)


def tiled_copies(path: skia.Path, w: float, h: float, x=True, y=True) -> skia.Path:
    """Path plus copies shifted by +-w / +-h (for seamless tiles)."""
    out = skia.Path()
    for dx in ((-w, 0, w) if x else (0,)):
        for dy in ((-h, 0, h) if y else (0,)):
            q = skia.Path(path)
            q.offset(dx, dy)
            out.addPath(q)
    return out


# --------------------------------------------------------------------------------------
# road paint wear
# --------------------------------------------------------------------------------------
def crack_paths(w, h, r, count=8, tile=False, length=(150, 700), step=(6, 16)) -> list:
    """Random-walk crack polylines (design units), returned as list of (path, width)."""
    out = []
    for _ in range(count):
        x, y = r.uniform(0, w), r.uniform(0, h)
        ang = r.uniform(0, 2 * math.pi)
        L = r.uniform(*length)
        pts = [(x, y)]
        d = 0
        while d < L:
            s = r.uniform(*step)
            ang += r.normal(0, 0.45)
            x += math.cos(ang) * s
            y += math.sin(ang) * s
            pts.append((x, y))
            d += s
            if r.random() < 0.04:  # branch
                bx, by, ba = x, y, ang + r.choice([-1, 1]) * r.uniform(0.6, 1.2)
                bp = [(bx, by)]
                for _k in range(int(r.uniform(4, 18))):
                    ba += r.normal(0, 0.5)
                    s2 = r.uniform(*step)
                    bx += math.cos(ba) * s2; by += math.sin(ba) * s2
                    bp.append((bx, by))
                out.append((poly(bp, close=False), r.uniform(0.8, 1.6)))
        out.append((poly(pts, close=False), r.uniform(1.2, 2.6)))
    if tile:
        out = [(tiled_copies(p, w, h), wd) for p, wd in out]
    return out


def road_paint(c: Canvas, M: np.ndarray, color, seed: int, tracks=(), wear: float = 0.5,
               tile: bool = False, cracks: int = 8, grime: float = 0.5, pores: float = 0.5,
               ghost: float = 0.10):
    """Paint mask M onto canvas as worn thermoplastic road paint.

    tracks: list of (x_center, half_width) in design px = wheel-track wear bands (vertical,
    i.e. along driving direction). tile -> all randomness wraps (seamless)."""
    H, W = M.shape
    ss = c.ss
    r = rng(seed)
    bl = blur_wrap if tile else blur
    # --- rough, chipped edges (noise-displaced threshold of a softened mask)
    eb = bl(M, 2.6 * ss)
    n_edge = noise(H, W, 2.5 * ss, seed + 11, beta=1.0)
    n_edge2 = noise(H, W, 14.0 * ss, seed + 12, beta=1.6)
    field = eb + (n_edge - 0.5) * 0.55 + (n_edge2 - 0.5) * 0.45
    Mr = smoothstep(0.46, 0.54, field) * smoothstep(0.02, 0.2, eb)
    # --- wheel-track wear bands
    xx = np.arange(W, dtype=f32)[None, :] / ss
    tr = np.zeros((1, W), f32)
    for (tx, tw) in tracks:
        if tile:
            for k in (-1, 0, 1):
                tr = np.maximum(tr, np.exp(-((xx - tx - k * W / ss) / tw) ** 2))
        else:
            tr = np.maximum(tr, np.exp(-((xx - tx) / tw) ** 2))
    # --- wear patches (blotchy + streaky along driving direction)
    n1 = noise(H, W, 70.0 * ss, seed + 13, beta=2.3)
    n2 = noise(H, W, 22.0 * ss, seed + 14, beta=1.7, aniso=(1.0, 6.0))
    n3 = noise(H, W, 6.0 * ss, seed + 15, beta=1.3)
    wf = n1 * 0.5 + n2 * 0.33 + n3 * 0.17 + tr * 0.24 * (0.5 + wear)
    th = 0.82 - wear * 0.22
    E = smoothstep(th - 0.010, th + 0.010, wf)
    # --- thin / faded paint
    thin = 0.90 + 0.10 * smoothstep(0.3, 0.7, noise(H, W, 40.0 * ss, seed + 16, beta=2.0))
    thin = thin * (1 - 0.22 * tr * wear)
    # --- aggregate pores (dark asphalt peaks poking through): sparse 1-4px pits
    pn = noise(H, W, 2.2 * ss, seed + 17, beta=1.15)
    dens = noise(H, W, 60.0 * ss, seed + 18, beta=2.0)
    pth = 0.815 - pores * 0.05 - (dens - 0.5) * 0.10 - tr * 0.03
    P = smoothstep(pth - 0.015, pth + 0.015, pn)
    # --- cracks
    cr = np.zeros_like(M)
    for pth_, wd in crack_paths(W / ss, H / ss, r, cracks, tile, step=(4, 10)):
        np.maximum(cr, c.mask(pth_, stroke=wd * 0.8, fill=False), out=cr)
    cr = cr * smoothstep(0.35, 0.6, noise(H, W, 30 * ss, seed + 21, beta=2.0))  # cracks fade in/out
    alpha = Mr * (1 - E * (1 - ghost)) * thin * (1 - P * 0.92) * (1 - cr * 0.95)
    # --- colour: grime, tyre rubber in tracks, faint bead sparkle
    col = np.asarray(color, f32)
    g = smoothstep(0.5, 0.85, noise(H, W, 30.0 * ss, seed + 19, beta=1.9)) * grime
    dirt = np.array([0.42, 0.40, 0.37], f32)
    rub = np.array([0.20, 0.20, 0.22], f32)
    colimg = col[None, None, :] * (1 - 0.30 * g[..., None]) + dirt * (0.30 * g[..., None])
    colimg = colimg * (1 - 0.28 * tr[..., None] * wear * n1[..., None]) + rub * (0.28 * tr[..., None] * wear * n1[..., None])
    grain = noise(H, W, 1.5 * ss, seed + 20, beta=0.9)
    colimg = np.clip(colimg * (0.965 + 0.05 * grain[..., None]), 0, 1)
    c.paint(np.clip(alpha, 0, 1).astype(f32), colimg.astype(f32))
    return alpha


def asphalt(w, h, seed=5) -> Image.Image:
    """Procedural asphalt (for previews only)."""
    n = noise(h, w, 2.0, seed, beta=0.5)
    n2 = noise(h, w, 60, seed + 1, beta=2.0)
    v = 0.22 + (n - 0.5) * 0.16 + (n2 - 0.5) * 0.08
    rgb = np.stack([v * 0.97, v * 0.97, v * 1.02], -1)
    return to_image(np.clip(rgb, 0, 1), "RGB")


def preview_on(paths, out, bg_fn, cell=(300, 300), cols=6, title=None, frame=True):
    """Contact sheet with every thumbnail composited over bg_fn(w,h) -> PIL RGB."""
    rows = (len(paths) + cols - 1) // cols
    pad, lab = 10, 22
    top = 44 if title else 0
    W = cols * (cell[0] + pad) + pad
    H = top + rows * (cell[1] + pad + lab) + pad
    sheet = Image.new("RGB", (W, H), (34, 30, 44))
    d = ImageDraw.Draw(sheet)
    fnt = pil_font("chakra", 15)
    if title:
        d.text((pad, 6), title, fill=(255, 248, 231), font=pil_font("bangers", 30))
    for i, p in enumerate(paths):
        r_, c_ = divmod(i, cols)
        x = pad + c_ * (cell[0] + pad)
        y = top + pad + r_ * (cell[1] + pad + lab)
        back = bg_fn(cell[0], cell[1], i).convert("RGBA")
        im = Image.open(p).convert("RGBA")
        s = min(cell[0] / im.width, cell[1] / im.height)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        ox, oy = (cell[0] - im.width) // 2, (cell[1] - im.height) // 2
        back.alpha_composite(im, (ox, oy))
        if frame:
            ImageDraw.Draw(back).rectangle((ox, oy, ox + im.width - 1, oy + im.height - 1), outline=(90, 90, 105))
        sheet.paste(back.convert("RGB"), (x, y))
        d.text((x, y + cell[1] + 2), os.path.basename(p)[:40], fill=(220, 215, 205), font=fnt)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return out


# --------------------------------------------------------------------------------------
# livery / sticker helpers
# --------------------------------------------------------------------------------------
def comic_stack(c: Canvas, F: np.ndarray, fill, paper_r: float = 8, ink_r: float = 14,
                ext=(0.0, 0.0), ext_col=None, ext_ink: float = 4.0, ht: float = 0.0, ht_col=None,
                ht_period: float = 9.0, shine: float = 0.0, shine_box=None, paper=None, ink=None,
                ht_angle: float = 45.0, ht_dir=None):
    """Comic lettering layer stack: [extrusion+ink] -> ink stroke -> paper stroke -> fill
    (+ halftone shading + gloss). F = glyph mask (internal res). Returns outer silhouette mask."""
    paper = C("paper") if paper is None else paper
    ink = C("ink") if ink is None else ink
    P = c.dilate(F, paper_r) if paper_r > 0 else F
    K = c.dilate(P, ink_r) if ink_r > 0 else P
    sil = K
    if ext[0] or ext[1]:
        E = c.extrude(K, ext[0], ext[1])
        EK = c.dilate(E, ext_ink)
        c.paint(EK, ink)
        if ext_col is not None:
            c.paint(c.erode(E, ext_ink * 0.4), ext_col)
            # hatching on the extrusion sides (comic depth lines)
            hl = c.halftone(np.full(F.shape, 0.30, f32), 7, -45, shape="line")
            c.paint(c.erode(E, ext_ink * 0.4) * hl * (1 - K), ink, 0.35)
        sil = EK
    c.paint(K, ink)
    if paper_r > 0:
        c.paint(P, paper)
    c.paint(F, fill)
    if ht > 0:
        val = ht
        if ht_dir is not None:
            val = c.ramp(*ht_dir) * ht
        dots = c.halftone(val, ht_period, ht_angle)
        c.paint(F * dots, ht_col if ht_col is not None else darken(np.asarray(fill if np.ndim(fill) == 1 else C("ink")), 0.4), 0.55)
    if shine > 0 and shine_box is not None:
        x0, y0, x1, y1 = shine_box
        band = poly([(x0, y0), (x1, y0), (x1, y0 + (y1 - y0) * 0.22), (x0, y0 + (y1 - y0) * 0.42)])
        c.paint(F * c.mask(band), C("white"), shine)
    return sil


def die_cut(c: Canvas, M: np.ndarray, width: float = 18, color=None, edge=True, shadow=True):
    """Paint a die-cut sticker backing under the current content: paper border around M.
    Must be called BEFORE drawing the content; returns border mask."""
    color = C("paper") if color is None else color
    B = c.dilate(M, width)
    if shadow:
        c.paint(c.shift(c.blur(B, 3), 3, 5), C("black"), 0.18)
    c.paint(B, color)
    if edge:
        rim = B * (1 - c.erode(B, 1.6))
        c.paint(rim, np.array([0.78, 0.76, 0.72], f32), 0.9)
    return B


def overspray(c: Canvas, M: np.ndarray, color, seed: int, reach: float = 10, amount: float = 0.6):
    """Spray-paint overspray speckle just outside mask edges."""
    halo = c.blur(M, reach) * (1 - M)
    sp = noise(c.H, c.W, 1.3 * c.ss, seed, beta=0.5)
    speck = smoothstep(0.72 - halo * 0.35, 0.76 - halo * 0.35, sp) * np.clip(halo * 2.2, 0, 1)
    c.paint(speck, color, amount)


def _streak_fields(H, W, ss, seed, scale=5.0, angles=(0, 45, 90, 135), stretch=40.0):
    """Oriented streak noise fields: field k varies along its normal angle angles[k]."""
    big = int(math.ceil(math.hypot(H, W) / 8.0)) * 8
    out = []
    for k, ang in enumerate(angles):
        base = noise(big, big, scale * ss, seed + 7 * k, beta=1.3, aniso=(1.0, stretch))
        f = rotate_field(base, ang)
        y0, x0 = (big - H) // 2, (big - W) // 2
        f = f[y0:y0 + H, x0:x0 + W]
        f = (f - f.mean()) / (f.std() + 1e-6)
        out.append(f)
    return out


def dry_brush(c: Canvas, F: np.ndarray, seed: int, angle: float = -15.0, amount: float = 0.6,
              wobble: float = 4.0, fringe: float = 1.0, oriented: bool = True, scale: float = 5.0) -> np.ndarray:
    """Turn a solid glyph mask into a calligraphy dry-brush (飛白 kasure) stroke mask.
    Core of strokes stays solid; long streak gaps appear near stroke edges and in random
    'dry' regions; bristle fringes stick out of dry edges. oriented=True follows the local
    stroke direction (structure tensor), otherwise streaks run along `angle` (deg)."""
    import cv2
    H, W = F.shape
    ss = c.ss
    # 1) wobbly edge via low-frequency displacement
    dxn = (noise(H, W, 50 * ss, seed + 1, beta=2.4) - 0.5) * wobble * ss * 2
    dyn = (noise(H, W, 50 * ss, seed + 2, beta=2.4) - 0.5) * wobble * ss * 2
    xx, yy = coords(H, W)
    Fw = cv2_remap(F, xx + dxn, yy + dyn)
    Fw = smoothstep(0.3, 0.7, c.blur(Fw, 1.0))
    # 2) streak field (z-scored)
    if oriented:
        Fb = c.blur(Fw, 6)
        gx = cv2.Sobel(Fb, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(Fb, cv2.CV_32F, 0, 1, ksize=3)
        jxx, jxy, jyy = c.blur(gx * gx, 18), c.blur(gx * gy, 18), c.blur(gy * gy, 18)
        th_n = 0.5 * np.arctan2(2 * jxy, jxx - jyy)
        angs = (0, 45, 90, 135)
        fields = _streak_fields(H, W, ss, seed + 3, scale, angs)
        wsum = np.zeros_like(F); streak = np.zeros_like(F)
        for k, phi in enumerate(angs):
            w = (np.cos(th_n - math.radians(phi)) ** 2) ** 8
            streak += fields[k] * w; wsum += w
        streak = streak / (wsum + 1e-6)
    else:
        streak = _streak_fields(H, W, ss, seed + 3, scale, (angle + 90,))[0]
    # 3) dryness: strongest at stroke edges, plus random dry patches; core stays solid
    inner = c.blur(Fw, 10)
    edge_w = np.clip(1.0 - (inner - 0.5) * 2.6, 0, 1) ** 1.5
    dry = smoothstep(0.45, 0.8, noise(H, W, 180 * ss, seed + 5, beta=2.4))
    drive = amount * (edge_w * 0.9 + dry * 0.55 * (0.3 + edge_w))
    th = 2.4 - drive * 2.6  # z-score threshold
    holes = smoothstep(th - 0.12, th + 0.12, streak) * smoothstep(0.05, 0.5, Fw)
    out = Fw * (1 - holes)
    # 4) bristle fringe outside dry edges
    if fringe > 0:
        ring = np.clip(c.dilate(Fw, 6) - Fw, 0, 1) * np.clip(c.blur(Fw, 3) * 3, 0, 1)
        fr = ring * smoothstep(-0.9, -1.2, streak) * (0.35 + 0.65 * dry) * fringe
        out = np.maximum(out, fr)
    return np.clip(out, 0, 1).astype(f32)


def cv2_remap(m, mapx, mapy):
    import cv2
    return cv2.remap(m, mapx.astype(f32), mapy.astype(f32), interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def rotate_field(m, deg):
    import cv2
    h, w = m.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(m, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def car_paint_bg(w, h, i=0) -> Image.Image:
    """Glossy car-paint swatch (preview background)."""
    cols = [C("indigo"), np.array([0.85, 0.86, 0.88], f32), np.array([0.62, 0.05, 0.10], f32),
            np.array([0.08, 0.09, 0.10], f32), np.array([0.05, 0.30, 0.55], f32), C("yellow") * 0.92]
    base = cols[i % len(cols)]
    yy = np.linspace(0, 1, h, dtype=f32)[:, None, None]
    xx = np.linspace(0, 1, w, dtype=f32)[None, :, None]
    g = base * (0.65 + 0.55 * np.exp(-((yy - 0.32) / 0.12) ** 2) * 0.6 + 0.35 * (1 - yy))
    g = g + 0.25 * np.exp(-((yy - 0.30 - 0.15 * xx) / 0.03) ** 2)
    return to_image(np.clip(g, 0, 1) * np.ones((h, w, 1), f32), "RGB")
