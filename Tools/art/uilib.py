"""uilib — UI/logo specific helpers on top of inklib (INK DRIFT: TOKYO).

Kept separate from inklib (shared) on purpose. Everything deterministic.
"""
from __future__ import annotations

import math
import os
import sys

import cv2
import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import *  # noqa: E402,F401,F403
import inklib  # noqa: E402

f32 = np.float32
UI_DIR = os.path.join(inklib.ART, "UI")


class FCanvas(inklib.Canvas):
    """Canvas that accepts a float supersample factor (ss<1 = fast low-res preview)."""

    def __init__(self, w: int, h: int, ss: float = 2.0, bg=None):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = int(round(w * ss)), int(round(h * ss))
        self.px = np.zeros((self.H, self.W, 4), f32)
        if bg is not None:
            self.px[..., :3] = np.asarray(bg, f32)
            self.px[..., 3] = 1.0

    def final(self) -> np.ndarray:
        px = self.px
        if self.ss > 1:
            px = cv2.resize(px, (self.w, self.h), interpolation=cv2.INTER_AREA)
        a = np.clip(px[..., 3:4], 0, 1)
        rgb = np.where(a > 1e-6, px[..., :3] / np.maximum(a, 1e-6), 0)
        return np.concatenate([np.clip(rgb, 0, 1), a], axis=-1)


# --------------------------------------------------------------------------------------
# shapes
# --------------------------------------------------------------------------------------
def sparkle(cx, cy, r, thin=0.16, rot=0.0) -> skia.Path:
    """4-point manga sparkle (concave star)."""
    p = skia.Path()
    pts = []
    for i in range(4):
        a = rot + i * math.pi / 2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    p.moveTo(*pts[0])
    for i in range(4):
        nxt = pts[(i + 1) % 4]
        p.quadTo(cx + (pts[i][0] - cx + nxt[0] - cx) * thin, cy + (pts[i][1] - cy + nxt[1] - cy) * thin, *nxt)
    p.close()
    return p


def crown(cx, cy, w, h) -> skia.Path:
    """Simple 5-point crown, base centred at (cx, cy+h/2)."""
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    band = h * 0.28
    pts = [(x0, y1), (x0 - w * 0.02, y0 + h * 0.18), (x0 + w * 0.22, y0 + h * 0.52), (cx - w * 0.17, y0 + h * 0.02),
           (cx, y0 + h * 0.42), (cx + w * 0.17, y0 + h * 0.02), (x1 - w * 0.22, y0 + h * 0.52), (x1 + w * 0.02, y0 + h * 0.18),
           (x1, y1)]
    p = poly(pts)
    return p


def para(x0, y0, x1, y1, slant) -> skia.Path:
    """Parallelogram: rect x0..x1, y0..y1 with top edge shifted right by `slant`."""
    return poly([(x0 + slant, y0), (x1 + slant, y0), (x1, y1), (x0, y1)])


def wrap_copies(path: skia.Path, W: float, H: float) -> skia.Path:
    """Path + 8 offset copies so the drawing tiles seamlessly on a WxH torus."""
    out = skia.Path()
    for dx in (-W, 0, W):
        for dy in (-H, 0, H):
            q = skia.Path(path)
            q.offset(dx, dy)
            out.addPath(q)
    return out


def bottom_edges(mask: np.ndarray, ss: float, xs, thresh=0.5):
    """For design-unit x positions return the lowest covered y (design units) or None."""
    out = []
    H = mask.shape[0]
    for x in xs:
        xi = int(round(x * ss))
        if xi < 0 or xi >= mask.shape[1]:
            out.append(None); continue
        col = np.nonzero(mask[:, xi] > thresh)[0]
        out.append(None if len(col) == 0 else col[-1] / ss)
    return out


def depth_extrude(cv, K: np.ndarray, dx: float, dy: float, steps: int | None = None):
    """Extrusion of mask K along (dx,dy) design units. Returns (E coverage, depth 0..1 map
    where 0 = nearest the face)."""
    sdx, sdy = dx * cv.ss, dy * cv.ss
    L = math.hypot(sdx, sdy)
    steps = steps or max(4, int(L / 1.25))
    E = K.copy()
    depth = np.where(K > 0.5, 0.0, 2.0).astype(f32)
    for i in range(steps, 0, -1):
        t = i / steps
        s = shift(K, sdx * t, sdy * t)
        np.maximum(E, s, out=E)
    # nearest-first depth (iterate from near to far, fill only unset)
    for i in range(1, steps + 1):
        t = i / steps
        s = shift(K, sdx * t, sdy * t)
        sel = (s > 0.5) & (depth > 1.5)
        depth[sel] = t
    depth[depth > 1.5] = 1.0
    return E, depth


def comic_text(cv, F: np.ndarray, stops, paper_w: float, ink_w: float, ext=(0.0, 0.0),
               ext_near=None, ext_far=None, ht_color=None, ht_period=14.0, ht_amt=0.5, ht_dir=None,
               shine: tuple | None = None, shine_col=None, rim_w: float = 0.0, rim_col=None,
               grad_box=None, ink_col=None, paper_col=None, ext_outline: float = 0.0,
               ext_lines: bool = True):
    """Full comic title-lettering treatment of fill mask F onto canvas cv.

    stops: gradient stops for the fill (vertical over grad_box=(y0,y1)).
    ext: 3D extrusion offset; ext_near/ext_far colours. ht_*: halftone overlay on fill.
    shine: (x0,y0,x1,y1, width) diagonal glossy streak clipped to fill.
    Returns dict of masks (F, P, K, E)."""
    ink_col = C("ink") if ink_col is None else ink_col
    paper_col = C("paper") if paper_col is None else paper_col
    P = cv.dilate(F, paper_w)
    K = cv.dilate(P, ink_w)
    out = {"F": F, "P": P, "K": K}
    if ext != (0.0, 0.0) and (ext[0] or ext[1]):
        E, depth = depth_extrude(cv, K, ext[0], ext[1])
        EK = cv.dilate(E, max(ext_outline, ink_w * 0.35))
        cv.paint(EK, ink_col)
        near = ext_near if ext_near is not None else C("indigo")
        far = ext_far if ext_far is not None else darken(C("indigo"), 0.6)
        col = gradient_map(depth, [(0, near), (1, far)])
        inner = cv.erode(E, ink_w * 0.18)
        cv.paint(inner, col)
        if ext_lines:
            # thin ink contour lines across the extrusion (gives the 3D block its "ridges")
            lines = np.clip(1 - np.abs(((depth * 3.0) % 1.0) - 0.5) * 2 * 6, 0, 1) * 0
            del lines
        out["E"] = E
        del depth, col, EK
    cv.paint(K, ink_col)
    if rim_w > 0:
        R = cv.dilate(F, paper_w + rim_w)
        cv.paint(R, rim_col if rim_col is not None else C("paper"))
    cv.paint(P, paper_col)
    y0, y1 = grad_box if grad_box else (0, cv.h)
    cv.paint(F, cv.vgrad(y0, y1, stops))
    if ht_color is not None:
        if ht_dir is None:
            ramp = cv.ramp((0, y0 + (y1 - y0) * 0.35), (0, y1))
        else:
            ramp = cv.ramp(ht_dir[0], ht_dir[1])
        dots = cv.halftone(ramp * ht_amt, ht_period, 45)
        cv.paint(F * dots, ht_color, 0.85)
        del dots, ramp
    if shine is not None:
        x0, y0s, x1, y1s, w = shine
        band = poly([(x0, y0s), (x1, y1s), (x1, y1s + w), (x0, y0s + w)])
        band2 = poly([(x0, y0s + w * 1.55), (x1, y1s + w * 1.55), (x1, y1s + w * 1.85), (x0, y0s + w * 1.85)])
        sm = cv.mask(combine(band, band2))
        cv.paint(F * sm, shine_col if shine_col is not None else C("paper"), 0.55)
        del sm
    return out


def drips_from(cv, mask: np.ndarray, xs, widths, lengths, color, r, overlap=6.0):
    """Hang drips from the lowest covered pixel at each x."""
    ys = bottom_edges(mask, cv.ss, xs)
    for x, y, w, L in zip(xs, ys, widths, lengths):
        if y is None:
            continue
        for dp in drip_paths(x, y - overlap, w, L, r):
            cv.paint(cv.mask(dp), color)


def spray_mist(cv, cx, cy, rx, ry, count, size, color, r, opacity=1.0):
    """Fine overspray speckles (gaussian cloud) as tiny circles."""
    p = skia.Path()
    for _ in range(count):
        x = cx + r.normal(0, rx)
        y = cy + r.normal(0, ry)
        s = size * (0.35 + r.random() ** 2.5 * 1.3)
        p.addCircle(float(x), float(y), float(s))
    cv.paint(cv.mask(p), color, opacity)


def save_l(arr: np.ndarray, path: str):
    """Save float 0..1 grayscale as 8-bit L PNG."""
    save_image(to_image(arr, "L"), path)
    return path


# --------------------------------------------------------------------------------------
# Dry brush (sumi / paint swipe)
# --------------------------------------------------------------------------------------
def _resample_polyline(pts, n):
    pts = np.asarray(pts, np.float64)
    seg = np.sqrt(((pts[1:] - pts[:-1]) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n)
    x = np.interp(t, s, pts[:, 0]); y = np.interp(t, s, pts[:, 1])
    return np.stack([x, y], 1), s[-1]


def brush_paths(spine_pts, width, r, bristles=90, press=0.10, taper=0.35, dry=0.55,
                head_blob=False, wobble=0.04, samples=240, dry_start=0.35, splay=0.25):
    """Dry-brush stroke along a spine (list of points, ideally smooth/dense).
    width: max stroke width. dry: 0..1 how much the bristles break up toward the end.
    Returns list of (skia.Path, stroke_width) bristle groups + optional head path."""
    # smooth dense spine
    sp = smooth_open(spine_pts)
    pm = skia.PathMeasure(sp, False)
    L = pm.getLength()
    ss = np.linspace(0, 1, samples)
    P_ = []; N_ = []
    for u in ss:
        pos, tan = pm.getPosTan(u * L)
        P_.append((pos.x(), pos.y()))
        N_.append((-tan.y(), tan.x()))
    P_ = np.array(P_); N_ = np.array(N_)
    # width profile: quick press-in, long body, taper + splay at the end
    prof = 0.62 + 0.38 * np.clip(ss / max(press, 1e-3), 0, 1) ** 0.5
    prof *= 1 - np.clip((ss - (1 - taper)) / taper, 0, 1) ** 2 * 0.55
    groups = []
    for b in range(bristles):
        t = (b + r.uniform(0.15, 0.85)) / bristles * 2 - 1        # lateral position -1..1
        bw = width / bristles * r.uniform(1.6, 3.2)
        # bristle-specific ink supply: ends somewhere in the dry zone
        end = 1 - r.uniform(0, 1) ** 1.5 * dry * (0.3 + 0.7 * abs(t))
        # rounded loaded start (semicircle-ish) + jitter
        start = press * 0.9 * (1 - math.sqrt(max(0.0, 1 - t * t))) + r.uniform(0, 0.012)
        # 1D gap noise along the bristle (dry-brush skips), ~N(0,1)
        k = np.cumsum(r.normal(0, 1, samples)); k = (k - k.mean()) / (k.std() + 1e-6)
        g = np.sin(ss * r.uniform(25, 70) + r.uniform(0, 6)) * 0.7 + k * 0.6
        dry_amt = np.clip((ss - dry_start) / (1 - dry_start), 0, 1) ** 1.3 * dry
        thr = dry_amt * 2.8 - 1.7
        on = (ss >= start) & (ss <= end) & (g > thr)
        # splay: lateral spread grows at the tail
        spread = 1 + splay * np.clip((ss - (1 - taper)) / taper, 0, 1) * (abs(t) + 0.2)
        wob = np.cumsum(r.normal(0, wobble, samples)) * 0.05 * width
        pts = P_ + N_ * (t * width / 2 * prof * spread + wob)[:, None]
        path = skia.Path()
        i = 0
        while i < samples:
            if on[i]:
                j = i
                while j + 1 < samples and on[j + 1]:
                    j += 1
                if j > i:
                    path.moveTo(*pts[i])
                    for q in range(i + 1, j + 1):
                        path.lineTo(*pts[q])
                i = j + 1
            else:
                i += 1
        groups.append((path, bw))
    head = None
    if head_blob:
        u = press * 0.6
        pos, tan = pm.getPosTan(u * L)
        a = math.degrees(math.atan2(tan.y(), tan.x()))
        head = ellipse(0, 0, width * 0.32, width * 0.47)
        head.transform(skia.Matrix.RotateDeg(a))
        head.offset(pos.x(), pos.y())
    return groups, head


def brush_mask(cv, spine_pts, width, r, **kw):
    groups, head = brush_paths(spine_pts, width, r, **kw)
    m = np.zeros((cv.H, cv.W), f32)
    # batch bristles into width bins (one raster call per bin) — much faster at high res
    bins = {}
    for path, bw in groups:
        k = round(bw * 2) / 2
        bins.setdefault(k, skia.Path()).addPath(path)
    for bw, path in bins.items():
        np.maximum(m, cv.mask(path, stroke=max(bw, 0.5), fill=False, cap="round"), out=m)
    if head is not None:
        np.maximum(m, cv.mask(head), out=m)
    return m


# --------------------------------------------------------------------------------------
# Organic paint splat + clean drips
# --------------------------------------------------------------------------------------
def organic_splat(cx, cy, R, r, arms=16, blob=0.52, wob=0.22, sat=0.7, arm_len=(0.25, 0.95)) -> list:
    """Paint splat: wobbly central blob + tapered curved arms with teardrop ends + satellites."""
    paths = []
    n = 90
    ph = r.uniform(0, 2 * math.pi, 5)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = blob * (1 + wob * (0.45 * math.sin(2 * a + ph[0]) + 0.3 * math.sin(3 * a + ph[1])
                               + 0.2 * math.sin(5 * a + ph[2]) + 0.12 * math.sin(9 * a + ph[3]))
                    + r.uniform(-0.025, 0.025))
        pts.append((cx + math.cos(a) * R * k, cy + math.sin(a) * R * k))
    paths.append(smooth_closed(pts, 0.9))
    for i in range(arms):
        a = 2 * math.pi * (i + r.uniform(0.1, 0.9)) / arms
        L = R * r.uniform(*arm_len)
        w0 = R * r.uniform(0.05, 0.12)
        s0 = R * blob * 0.6
        bend = r.uniform(-0.25, 0.25)
        left, right = [], []
        N = 14
        for j in range(N + 1):
            t = j / N
            ang = a + bend * t * t
            d = s0 + t * L
            x, y = cx + math.cos(ang) * d, cy + math.sin(ang) * d
            nx, ny = -math.sin(ang), math.cos(ang)
            w = w0 * ((1 - t) ** 1.6 * 0.95 + 0.22)
            left.append((x + nx * w / 2, y + ny * w / 2))
            right.append((x - nx * w / 2, y - ny * w / 2))
        paths.append(poly(left + right[::-1]))
        ang = a + bend
        ex, ey = cx + math.cos(ang) * (s0 + L), cy + math.sin(ang) * (s0 + L)
        br = w0 * r.uniform(0.38, 0.6)
        drop = ellipse(0, 0, br * 1.25, br)
        drop.transform(skia.Matrix.RotateRad(ang))
        drop.offset(ex + math.cos(ang) * br * 0.4, ey + math.sin(ang) * br * 0.4)
        paths.append(drop)
        # satellites beyond the arm tip
        if r.random() < sat:
            d = s0 + L + br * r.uniform(2.0, 4.0)
            sr = br * r.uniform(0.35, 0.7)
            paths.append(circle(cx + math.cos(ang) * d, cy + math.sin(ang) * d, sr))
            if r.random() < 0.5:
                d2 = d + sr * r.uniform(2.5, 4.5)
                paths.append(circle(cx + math.cos(ang) * d2, cy + math.sin(ang) * d2, sr * 0.5))
    return paths


def drips_clean(cv, mask: np.ndarray, xs, widths, lengths, color, r, overlap=6.0, paint=True, margin=28.0):
    """Like drips_from but the widening root fillet is clipped to the neighbourhood of the
    source mask, so it never pokes out sideways on sloped edges. Returns the drip mask."""
    ys = bottom_edges(mask, cv.ss, xs)
    out = np.zeros_like(mask)
    near = None
    for x, y, w, L in zip(xs, ys, widths, lengths):
        if y is None:
            continue
        L = min(L, cv.h - margin - (y - overlap) - w * 0.8)
        if L < w:
            continue
        stem, bulb, fillet = drip_paths(x, y - overlap, w, L, r)
        np.maximum(out, cv.mask(stem), out=out)
        np.maximum(out, cv.mask(bulb), out=out)
        if near is None:
            near = cv.dilate(mask, 3)
        np.maximum(out, cv.mask(fillet) * near, out=out)
    if paint:
        cv.paint(out, color)
    return out


def flecks_in(cx, cy, radius, count, size, r, box, sigma=0.5, elong=0.3) -> skia.Path:
    """inklib.flecks() but every fleck is kept fully inside box=(x0,y0,x1,y1)."""
    p = skia.Path()
    x0, y0, x1, y1 = box
    for _ in range(count):
        a = r.uniform(0, 2 * math.pi)
        d = abs(r.normal(0, sigma)) * radius + radius * 0.15
        s = size[0] + (size[1] - size[0]) * (r.random() ** 3)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        ext = s * 3.2
        if not (x0 + ext < x < x1 - ext and y0 + ext < y < y1 - ext):
            continue
        if r.random() < elong:
            q = ellipse(0, 0, s * r.uniform(1.6, 3.0), s * 0.6)
            q.transform(skia.Matrix.RotateRad(a))
            q.offset(x, y)
            p.addPath(q)
        else:
            p.addCircle(x, y, s)
    return p
