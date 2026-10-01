#!/usr/bin/env python3
"""Procedural texture generator for INK DRIFT: TOKYO foliage.

Run with the repo venv:   Tools/.venv/bin/python Tools/blender/foliage/gen_textures.py [names...]
With no args every texture is generated. Outputs PNGs to
Game/Assets/InkDrift/Models/Trees/Textures/ :
  Leaves_<Species>_albedo.png  RGBA alpha-cutout leaf-cluster atlases (layout in atlas_layout.py)
  Bark_<Species>_albedo.png / _normal.png  tileable 1024 bark (OpenGL +Y normals)
Everything is drawn from scratch (no source images).
"""
import colorsys
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Trees", "Textures")
sys.path.insert(0, HERE)
from atlas_layout import ATLASES  # noqa: E402

SS = 2  # supersampling factor for leaf drawing


# ----------------------------------------------------------------------------- colour utils
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def jit(c, rng, h=0.015, s=0.08, v=0.08):
    H, S, V = colorsys.rgb_to_hsv(*[float(x) for x in c])
    H = (H + rng.uniform(-h, h)) % 1.0
    S = float(np.clip(S * (1 + rng.uniform(-s, s)), 0, 1))
    V = float(np.clip(V * (1 + rng.uniform(-v, v)), 0, 1))
    return np.array(colorsys.hsv_to_rgb(H, S, V), np.float32)


def pick(cols, rng, w=None):
    i = rng.choice(len(cols), p=w)
    return cols[i]


def mix(a, b, t):
    return a * (1 - t) + b * t


# ----------------------------------------------------------------------------- canvas
class Canvas:
    """Supersampled RGBA canvas. Alpha is binary at SS resolution; AA comes from downsampling."""

    def __init__(self, w, h, seed=0):
        self.w, self.h = w, h
        self.W, self.H = w * SS, h * SS
        self.rgb = np.zeros((self.H, self.W, 3), np.float32)
        self.a = np.zeros((self.H, self.W), np.float32)
        rng = np.random.default_rng(seed + 991)
        n = smooth_noise((self.H // 8, self.W // 8), 6, rng)
        self.mottle = cv2.resize(n, (self.W, self.H), interpolation=cv2.INTER_CUBIC) * 2 - 1

    def draw(self, polys=None, colfn=None, rim=0.86, rim_w=2, lines=(), dark=1.0, mask_fn=None,
             bbox=None, mottle=0.06):
        """Fill polygons (list of Nx2 canvas coords) with colour field colfn(xx, yy)->(h,w,3)."""
        if polys is not None:
            allp = np.concatenate(polys)
            bx0, by0 = allp.min(0)
            bx1, by1 = allp.max(0)
        else:
            bx0, by0, bx1, by1 = bbox
        x0 = int(max(0, math.floor(bx0) - 3)); x1 = int(min(self.W, math.ceil(bx1) + 4))
        y0 = int(max(0, math.floor(by0) - 3)); y1 = int(min(self.H, math.ceil(by1) + 4))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        off = np.array([x0, y0], np.float32)
        if polys is not None:
            for p in polys:
                q = np.round((p - off) * 16).astype(np.int32)
                cv2.fillPoly(m, [q], 1, lineType=cv2.LINE_8, shift=4)
        if mask_fn is not None:
            mask_fn(m, off)
        sel = m > 0
        if not sel.any():
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        col = colfn(xx, yy).astype(np.float32)
        if col.ndim == 1:
            col = np.broadcast_to(col, (y1 - y0, x1 - x0, 3)).copy()
        for pts, lc, th in lines:
            lm = np.zeros_like(m)
            q = np.round((np.asarray(pts, np.float32) - off) * 16).astype(np.int32)
            cv2.polylines(lm, [q], False, 1, max(1, int(th)), lineType=cv2.LINE_8, shift=4)
            lsel = lm > 0
            if callable(lc):
                col[lsel] = lc(col[lsel])
            else:
                col[lsel] = lc
        if rim and rim < 1:
            er = cv2.erode(m, np.ones((2 * rim_w + 1, 2 * rim_w + 1), np.uint8))
            rs = sel & (er == 0)
            col[rs] *= rim
        if mottle:
            col *= (1 + mottle * self.mottle[y0:y1, x0:x1])[..., None]
        col *= dark
        sub = self.rgb[y0:y1, x0:x1]
        sub[sel] = np.clip(col[sel], 0, 1)
        self.a[y0:y1, x0:x1][sel] = 1.0

    def stroke(self, pts, w0, w1, col, dark=1.0, rim=0.8, colfn=None):
        """Tapered stroke along a polyline (canvas coords)."""
        pts = np.asarray(pts, np.float32)
        if len(pts) < 2:
            return
        d = np.gradient(pts, axis=0)
        d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-6
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        w = np.linspace(w0, w1, len(pts))[:, None] * 0.5
        poly = np.concatenate([pts + nrm * w, (pts - nrm * w)[::-1]])
        if colfn is None:
            c = np.asarray(col, np.float32)
            colfn = lambda xx, yy: c  # noqa: E731
        self.draw([poly], colfn, rim=rim, rim_w=1, dark=dark)

    def finalize(self, bleed=True):
        """Downsample to final res, un-premultiply, colour-bleed into transparent area."""
        pm = self.rgb * self.a[..., None]
        pm = cv2.resize(pm, (self.w, self.h), interpolation=cv2.INTER_AREA)
        a = cv2.resize(self.a, (self.w, self.h), interpolation=cv2.INTER_AREA)
        rgb = pm / np.maximum(a[..., None], 1e-4)
        if bleed:
            rgb = push_pull(rgb, a)
        return np.clip(rgb, 0, 1), np.clip(a, 0, 1)


def push_pull(rgb, a):
    """Fill RGB where alpha is 0 with smoothly extrapolated colours (prevents dark mip fringes)."""
    w = (a > 0.02).astype(np.float32)
    levels = []
    c, ww = rgb * w[..., None], w
    while min(c.shape[:2]) > 2:
        levels.append((c, ww))
        h2, w2 = c.shape[0] // 2, c.shape[1] // 2
        c = cv2.resize(c, (w2, h2), interpolation=cv2.INTER_AREA)
        ww = cv2.resize(ww, (w2, h2), interpolation=cv2.INTER_AREA)
    fill = c.sum((0, 1)) / max(ww.sum(), 1e-6)
    cur = np.broadcast_to(fill, c.shape).astype(np.float32)
    for c, ww in reversed(levels):
        up = cv2.resize(cur, (c.shape[1], c.shape[0]), interpolation=cv2.INTER_LINEAR)
        val = c / np.maximum(ww[..., None], 1e-6)
        k = np.clip(ww * 4, 0, 1)[..., None]
        cur = val * k + up * (1 - k)
    out = rgb.copy()
    m = a <= 0.02
    out[m] = cur[m]
    return out


def save_rgba(path, rgb, a):
    img = np.dstack([rgb, a])
    img = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(path, optimize=True)
    print("wrote", os.path.relpath(path, REPO), img.shape)


def save_rgb(path, rgb):
    img = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img, "RGB").save(path, optimize=True)
    print("wrote", os.path.relpath(path, REPO), img.shape)


# ----------------------------------------------------------------------------- noise
def smooth_noise(shape, freq, rng):
    """Non-periodic smooth noise in [0,1] (bicubic-upsampled random grid)."""
    h, w = shape
    g = rng.random((max(2, int(freq * h / max(h, w))) + 3, max(2, int(freq * w / max(h, w))) + 3)).astype(np.float32)
    n = cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
    n = (n - n.min()) / (np.ptp(n) + 1e-6)
    return n


def pnoise(n, freq, rng, aniso=(1.0, 1.0)):
    """Periodic (tileable) gaussian-filtered noise, zero-mean unit-std. freq ~ features per tile.
    aniso=(ax, ay): ay<1 stretches features vertically."""
    wn = rng.standard_normal((n, n))
    F = np.fft.fft2(wn)
    fy = np.fft.fftfreq(n)[:, None] * n
    fx = np.fft.fftfreq(n)[None, :] * n
    k = np.sqrt((fx / aniso[0]) ** 2 + (fy / aniso[1]) ** 2)
    filt = np.exp(-(k / freq) ** 2)
    r = np.real(np.fft.ifft2(F * filt))
    r -= r.mean()
    r /= r.std() + 1e-9
    return r.astype(np.float32)


def fbm(n, freq, rng, octaves=5, gain=0.5, aniso=(1.0, 1.0)):
    s = np.zeros((n, n), np.float32)
    amp, tot = 1.0, 0.0
    for i in range(octaves):
        s += amp * pnoise(n, freq * 2 ** i, rng, aniso)
        tot += amp
        amp *= gain
    s /= tot
    return s / (s.std() + 1e-9)


def pvoronoi(n, count, rng, stretch=(1.0, 1.0), jitter_pts=None):
    """Periodic Worley: returns (d1, d2, cell_id) in pixels. stretch scales metric per axis."""
    sx, sy = stretch
    pts = rng.random((count, 2)) * [n * sx, n * sy]
    tree = cKDTree(pts, boxsize=[n * sx, n * sy])
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    q = np.stack([xx.ravel() * sx, yy.ravel() * sy], 1)
    if jitter_pts is not None:
        q += jitter_pts.reshape(-1, 2)
        q[:, 0] %= n * sx
        q[:, 1] %= n * sy
    d, i = tree.query(q, k=2)
    return (d[:, 0].reshape(n, n).astype(np.float32), d[:, 1].reshape(n, n).astype(np.float32),
            i[:, 0].reshape(n, n))


def norm01(x):
    return (x - x.min()) / (np.ptp(x) + 1e-9)


def height_to_normal(hgt, strength):
    """Tileable OpenGL (+Y up) normal map from height (rows go down = -v)."""
    dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
    dy = (np.roll(hgt, 1, 0) - np.roll(hgt, -1, 0)) * 0.5  # row-1 is "up"
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(hgt)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.dstack([nx / l, ny / l, nz / l]) * 0.5 + 0.5


def colormap(t, stops):
    """t array [0,1] -> rgb using list of (pos, hex)."""
    pos = np.array([p for p, _ in stops], np.float32)
    cols = np.array([hexc(c) for _, c in stops], np.float32)
    out = np.zeros(t.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


# ----------------------------------------------------------------------------- geometry helpers
def rot(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]], np.float32)


def xf(P, base, ang, scale, squash=1.0, squash_ang=0.0):
    """Local shape (x along leaf, y lateral, length-1 units) -> canvas coords."""
    P = np.asarray(P, np.float32) * scale
    if squash != 1.0:
        R = rot(squash_ang)
        P = (P @ R) * [1.0, squash] @ R.T
    return P @ rot(ang).T + np.asarray(base, np.float32)


def shape_ovate(w=0.3, serr=0.0, nt=10, n=48, tipp=0.75, basew=0.0, asym=0.0):
    t = np.linspace(0, 1, n)
    hw = w * np.sin(np.pi * np.clip(t, 0, 1) ** tipp) ** 0.85 + basew * (1 - t) ** 4
    hw[0] = basew
    up = hw.copy()
    lo = hw.copy() * (1 - asym)
    if serr:
        saw = (t * nt) % 1.0
        tooth = serr * saw * (t > 0.12) * (t < 0.97)
        up = up * (1 + tooth)
        lo = lo * (1 + serr * ((t * nt + 0.5) % 1.0) * (t > 0.12) * (t < 0.97))
    upper = np.stack([t, up], 1)
    lower = np.stack([t[::-1], -lo[::-1]], 1)
    return np.concatenate([upper, lower])


def shape_petal(rr=0.42, notch=0.10, n=28):
    th = np.linspace(-math.pi / 2, math.pi / 2, n)
    x = 1 - rr + rr * np.cos(th) - notch * np.exp(-(th / 0.22) ** 2)
    y = rr * np.sin(th) * 1.05
    tip = np.stack([x, y], 1)
    base = np.array([[0.0, 0.0]], np.float32)
    return np.concatenate([base, tip[::-1] * [1, 1], base])[::-1]


def shape_fan(spread=1.25, notch=0.22, n=40, rng=None, wave=0.03):
    ph = rng.uniform(0, 6) if rng is not None else 0
    phi = np.linspace(-spread / 2, spread / 2, n)
    r = 1.0 - notch * np.exp(-(phi / 0.07) ** 2) + wave * np.sin(phi * 14 + ph)
    r *= 1 - 0.08 * (np.abs(phi) / (spread / 2)) ** 2
    arc = np.stack([np.cos(phi) * r, np.sin(phi) * r], 1)
    return np.concatenate([[[0.0, -0.03]], arc, [[0.0, 0.03]]])


def bezier(p0, p1, p2, n=16):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


# ----------------------------------------------------------------------------- colour fields
def cf_grad(c0, c1, p0, p1, gamma=1.0):
    c0 = np.asarray(c0, np.float32); c1 = np.asarray(c1, np.float32)
    p0 = np.asarray(p0, np.float32); d = np.asarray(p1, np.float32) - p0
    dd = float(d @ d) + 1e-6

    def f(xx, yy):
        t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / dd, 0, 1) ** gamma
        return c0 + (c1 - c0) * t[..., None]
    return f


def cf_radial(c0, c1, center, r, gamma=1.0):
    c0 = np.asarray(c0, np.float32); c1 = np.asarray(c1, np.float32)

    def f(xx, yy):
        t = np.clip(np.hypot(xx - center[0], yy - center[1]) / r, 0, 1) ** gamma
        return c0 + (c1 - c0) * t[..., None]
    return f


# ----------------------------------------------------------------------------- leaf primitives
def leaf_simple(cv, base, ang, L, col, dark, shape, vein=1.12, laterals=0, tipcol=None, basecol=None,
                petiole=0.0, petcol=None, squash=1.0, rim=0.86):
    poly = xf(shape, base, ang, L, squash=squash, squash_ang=0.0)
    tipv = xf([[1, 0]], base, ang, L, squash)[0]
    c0 = basecol if basecol is not None else col * 0.8
    c1 = tipcol if tipcol is not None else col * 1.06
    lines = []
    th = max(1, int(L * 0.025))
    lines.append(([base, tipv], (lambda c: np.clip(c * vein, 0, 1)), th))
    for k in range(laterals):
        t = 0.15 + 0.75 * k / max(1, laterals - 1)
        for sgn in (1, -1):
            p0 = xf([[t, 0]], base, ang, L, squash)[0]
            p1 = xf([[t + 0.17, sgn * 0.2]], base, ang, L, squash)[0]
            lines.append(([p0, p1], (lambda c: c * 0.93), max(1, th - 1)))
    if petiole > 0:
        pe = xf([[-petiole, 0], [0.02, 0]], base, ang, L, squash)
        cv.stroke(pe, L * 0.04, L * 0.035, petcol if petcol is not None else c0 * 0.8, dark=dark)
    cv.draw([poly], cf_grad(c0, c1, base, tipv), lines=lines, dark=dark, rim=rim)


def leaf_palmate(cv, rng, base, ang, L, col, dark, lobes=7, tipcol=None, squash=1.0):
    """Japanese maple leaf: 5-7 serrated lobes radiating from the petiole point."""
    if lobes == 7:
        angs = np.radians([-112, -72, -36, 0, 36, 72, 112])
        lens = np.array([0.42, 0.72, 0.92, 1.0, 0.92, 0.72, 0.42])
    else:
        angs = np.radians([-80, -40, 0, 40, 80])
        lens = np.array([0.6, 0.88, 1.0, 0.88, 0.6])
    angs = angs + rng.normal(0, 0.05, len(angs))
    lens = lens * rng.uniform(0.92, 1.06, len(lens))
    lobe = shape_ovate(w=0.2, serr=0.22, nt=11, tipp=0.55)
    polys, lines = [], []
    tips = []
    for a, l in zip(angs, lens):
        P = lobe * [l, 1.0 * l ** 0.5] + [0.05, 0]
        P = P @ rot(a).T
        polys.append(xf(P, base, ang, L * 0.62, squash))
        tip = xf((np.array([[l + 0.05, 0]]) @ rot(a).T), base, ang, L * 0.62, squash)[0]
        tips.append(tip)
        lines.append(([base, tip], (lambda c: np.clip(c * 1.1 + 0.03, 0, 1)), max(1, int(L * 0.018))))
    # petiole
    pe = xf([[0.0, 0], [-0.45, 0.04]], base, ang, L * 0.62, squash)
    cv.stroke(pe, L * 0.03, L * 0.02, col * 0.75, dark=dark)
    c0 = col * 0.82 if tipcol is None else col
    c1 = tipcol if tipcol is not None else col * 1.08
    cv.draw(polys, cf_radial(c0, c1, base, L * 0.62), lines=lines, dark=dark, rim=0.85)


def leaf_fan(cv, rng, base, ang, L, col, dark, squash=1.0):
    """Ginkgo fan leaf with long petiole; base = petiole start."""
    pet = rng.uniform(0.45, 0.65)
    shape = shape_fan(spread=rng.uniform(1.6, 2.2), notch=rng.uniform(0.05, 0.3), rng=rng)
    P = shape + [pet, 0]
    poly = xf(P, base, ang, L, squash)
    blade_base = xf([[pet, 0]], base, ang, L, squash)[0]
    cv.stroke(xf([[0, 0], [pet + 0.05, 0]], base, ang, L, squash), L * 0.035, L * 0.03, col * 0.7, dark=dark)
    lines = []
    for phi in np.linspace(-0.9, 0.9, 9):
        p1 = xf([[pet + 0.85 * math.cos(phi), 0.85 * math.sin(phi)]], base, ang, L, squash)[0]
        lines.append(([blade_base, p1], (lambda c: c * 0.94), max(1, int(L * 0.01))))
    cv.draw([poly], cf_radial(col * 0.86, np.clip(col * 1.08, 0, 1), blade_base, L), lines=lines, dark=dark, rim=0.86)


def flower5(cv, rng, center, R, petal_cols, center_col, dark, squash=1.0, squash_ang=0.0, n=5,
            petal_shape=None, spot_col=None, stamen_col=None):
    """5-petal flower (sakura / azalea). R = petal length in canvas px."""
    a0 = rng.uniform(0, 2 * math.pi)
    shape = petal_shape if petal_shape is not None else shape_petal(rr=0.44, notch=rng.uniform(0.06, 0.13))
    polys = []
    for k in range(n):
        a = a0 + 2 * math.pi * k / n + rng.normal(0, 0.08)
        P = shape @ rot(a).T * R * rng.uniform(0.92, 1.05)
        if squash != 1.0:
            Rm = rot(squash_ang)
            P = (P @ Rm) * [1.0, squash] @ Rm.T
        polys.append(P + center)
    edge, mid = petal_cols
    cv.draw(polys, cf_radial(center_col, edge, center, R * 1.0, gamma=0.55), dark=dark, rim=0.9,
            lines=[], mottle=0.04)
    if spot_col is not None:  # azalea throat spots on upper petal
        a = a0
        for j in range(6):
            p = center + (np.array([math.cos(a), math.sin(a)]) * R * rng.uniform(0.2, 0.5)
                          + rng.normal(0, R * 0.05, 2)) * [1, squash]
            cv.draw([circle(p, R * 0.04)], lambda xx, yy: spot_col, rim=0, dark=dark, mottle=0)
    # stamens
    sc = stamen_col if stamen_col is not None else hexc("#F6D36B")
    for j in range(rng.integers(6, 11)):
        a = rng.uniform(0, 2 * math.pi)
        r = R * rng.uniform(0.18, 0.38)
        p = center + np.array([math.cos(a) * r, math.sin(a) * r * squash])
        cv.stroke([center, p], R * 0.03, R * 0.02, center_col * 0.9, dark=dark, rim=1)
        cv.draw([circle(p, R * 0.045)], lambda xx, yy: sc, rim=0, dark=dark, mottle=0)


def circle(c, r, n=12):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([c[0] + r * np.cos(t), c[1] + r * np.sin(t)], 1).astype(np.float32)


def needle_tuft(cv, rng, center, L, cols, dark, n=26, up=(0, -1), spread=2.6, w=3):
    """Pine needle fascicle cluster drawn as thin needles fanning from a point."""
    base_dir = math.atan2(up[1], up[0])
    segs = []
    for k in range(n):
        a = base_dir + rng.uniform(-spread / 2, spread / 2)
        l = L * rng.uniform(0.6, 1.0)
        bend = rng.uniform(-0.15, 0.15)
        p0 = np.asarray(center, np.float32)
        p2 = p0 + l * np.array([math.cos(a), math.sin(a)])
        p1 = p0 + 0.5 * l * np.array([math.cos(a + bend), math.sin(a + bend)])
        segs.append(bezier(p0, p1, p2, 6))
    allp = np.concatenate(segs)
    bb = (allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max())

    def mfn(m, off):
        for s in segs:
            q = np.round((s - off) * 16).astype(np.int32)
            cv2.polylines(m, [q], False, 1, w, lineType=cv2.LINE_8, shift=4)
    c0, c1 = cols
    cv.draw(None, cf_radial(c0, c1, center, L), rim=0, mask_fn=mfn, bbox=bb, dark=dark, mottle=0.05)


# ----------------------------------------------------------------------------- cluster builders
def twig_tree(rng, start, center, R, n_sub=6, up_bias=0.0):
    """Return list of polylines (canvas coords): main twig start->center and sub-twigs."""
    main = bezier(np.array(start), (np.array(start) + np.array(center)) / 2 + rng.normal(0, R * 0.08, 2),
                  np.array(center), 10)
    twigs = [main]
    for k in range(n_sub):
        a = -math.pi / 2 + rng.uniform(-1.9, 1.9) + up_bias
        r = R * rng.uniform(0.45, 0.85)
        s = main[rng.integers(5, 10)]
        e = np.array(center) + r * np.array([math.cos(a), math.sin(a)])
        mid = (s + e) / 2 + rng.normal(0, R * 0.07, 2)
        twigs.append(bezier(s, mid, e, 8))
    return twigs


def in_rect(p, rect, m):
    x0, y0, x1, y1 = rect
    return x0 + m <= p[0] <= x1 - m and y0 + m <= p[1] <= y1 - m


def blob_ok(p, center, R, phase, amp=0.18):
    """irregular lumpy boundary test"""
    d = p - center
    a = math.atan2(d[1], d[0])
    rr = R * (1 + amp * (math.sin(3 * a + phase[0]) * 0.6 + math.sin(5 * a + phase[1]) * 0.4))
    return np.hypot(*d) <= rr


def cluster_round(cv, rng, rect, leaf_fn, n, twig_col, radius=0.44, size=(0.2, 0.3), twig_w=0.035,
                  dark_range=(0.62, 1.0), n_sub=7, outward=0.75, extra=None, center_off=(0, 0), margin=0.0, fill=0.0):
    x0, y0, x1, y1 = rect
    W, H = x1 - x0, y1 - y0
    R = radius * min(W, H)
    c = np.array([x0 + W / 2 + center_off[0] * W, y0 + H / 2 + center_off[1] * H], np.float32)
    start = np.array([x0 + W / 2 + rng.normal(0, W * 0.05), y1 - H * 0.02])
    twigs = twig_tree(rng, start, c, R, n_sub=n_sub)
    phase = rng.uniform(0, 6, 2)
    for t in twigs:
        cv.stroke(t, R * twig_w, R * twig_w * 0.45, twig_col, dark=0.8)
    items = []
    tries = 0
    while len(items) < n and tries < n * 30:
        tries += 1
        if rng.random() < fill:
            a_ = rng.uniform(0, 2 * math.pi)
            p = c + R * 0.95 * math.sqrt(rng.random()) * np.array([math.cos(a_), math.sin(a_)])
        else:
            tw = twigs[rng.integers(0, len(twigs))]
            p = tw[rng.integers(2, len(tw))] + rng.normal(0, R * 0.22, 2)
        if not blob_ok(p, c, R * 0.92, phase):
            continue
        d = p - c
        a_out = math.atan2(d[1], d[0]) if np.hypot(*d) > 1e-3 else rng.uniform(0, 6.28)
        ang = a_out * outward + rng.uniform(-math.pi, math.pi) * (1 - outward) + rng.normal(0, 0.45)
        L = R * rng.uniform(*size)
        tip = p + L * np.array([math.cos(ang), math.sin(ang)])
        if not in_rect(tip, rect, 6 * SS + margin * L) or not in_rect(p, rect, 6 * SS + margin * L):
            continue
        depth = rng.random()
        items.append((depth, p, ang, L))
    if extra:
        items += extra(c, R)
    items.sort(key=lambda it: it[0])
    for depth, p, ang, L in items:
        up = np.clip((c[1] - p[1]) / R, -1, 1)  # brighter on top
        dark = mix(dark_range[0], dark_range[1], depth) * (1 + 0.07 * up)
        leaf_fn(p, ang, L, dark)
    return c, R


def spray_twigs(rng, rect, n_side=7, curve=0.12):
    x0, y0, x1, y1 = rect
    W, H = x1 - x0, y1 - y0
    p0 = np.array([x0 + W / 2, y1 - H * 0.01])
    p2 = np.array([x0 + W / 2 + rng.normal(0, W * 0.08), y0 + H * 0.12])
    p1 = (p0 + p2) / 2 + [W * rng.uniform(-curve, curve), 0]
    main = bezier(p0, p1, p2, 20)
    twigs = [main]
    for k in range(n_side):
        i = int(4 + (len(main) - 6) * (k + rng.uniform(0, 0.8)) / n_side)
        i = min(i, len(main) - 2)
        s = main[i]
        side = 1 if k % 2 == 0 else -1
        frac = i / len(main)
        ln = W * (0.42 - 0.22 * frac) * rng.uniform(0.75, 1.1)
        a = -math.pi / 2 + side * rng.uniform(0.6, 1.1)
        e = s + ln * np.array([math.cos(a), math.sin(a)])
        e[0] = np.clip(e[0], x0 + W * 0.08, x1 - W * 0.08)
        twigs.append(bezier(s, (s + e) / 2 + rng.normal(0, W * 0.03, 2), e, 8))
    return twigs


def cluster_spray(cv, rng, rect, leaf_fn, n, twig_col, size=(0.1, 0.16), n_side=7, dark_range=(0.65, 1.0),
                  twig_w=0.022, spread=0.6, margin=0.0):
    x0, y0, x1, y1 = rect
    W, H = x1 - x0, y1 - y0
    twigs = spray_twigs(rng, rect, n_side)
    for i, t in enumerate(twigs):
        cv.stroke(t, W * twig_w * (1.0 if i == 0 else 0.6), W * twig_w * 0.3, twig_col, dark=0.8)
    items = []
    tries = 0
    while len(items) < n and tries < n * 30:
        tries += 1
        tw = twigs[rng.integers(0, len(twigs))]
        j = rng.integers(1, len(tw))
        p = tw[j] + rng.normal(0, W * 0.02, 2)
        tang = tw[min(j, len(tw) - 1)] - tw[max(j - 1, 0)]
        ta = math.atan2(tang[1], tang[0])
        ang = ta + rng.choice([-1, 1]) * rng.uniform(0.3, 1.1) * spread / 0.6
        L = W * rng.uniform(*size)
        tip = p + L * np.array([math.cos(ang), math.sin(ang)])
        if not in_rect(tip, rect, 6 * SS + margin * L) or not in_rect(p, rect, 4 * SS + margin * L):
            continue
        items.append((rng.random(), p, ang, L))
    items.sort(key=lambda it: it[0])
    for depth, p, ang, L in items:
        leaf_fn(p, ang, L, mix(dark_range[0], dark_range[1], depth))


def scaled_rect(name, cell):
    x0, y0, x1, y1 = ATLASES[name]["cells"][cell]
    return (x0 * SS, y0 * SS, x1 * SS, y1 * SS)


# ============================================================================= LEAF ATLASES
def atlas_keyaki(seed=11):
    name = "Leaves_Keyaki"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#4E8E33", "#5C9C38", "#3F7D2E", "#6BAA40", "#4A8A3A", "#7FB447")]
    twig = hexc("#5A4535")
    shape = lambda: shape_ovate(w=rng.uniform(0.26, 0.32), serr=0.10, nt=9, tipp=0.8)  # noqa: E731

    def leaf(p, ang, L, dark):
        c = jit(pick(greens, rng), rng)
        leaf_simple(cv, p, ang, L, c, dark, shape(), laterals=4, tipcol=np.clip(c * 1.12, 0, 1),
                    basecol=c * 0.78, petiole=0.08, squash=rng.uniform(0.55, 1.0))
    cluster_round(cv, rng, scaled_rect(name, "round_a"), leaf, 360, twig, size=(0.12, 0.19), fill=0.35)
    cluster_round(cv, rng, scaled_rect(name, "round_b"), leaf, 330, twig, size=(0.13, 0.2), radius=0.43, fill=0.35)
    cluster_spray(cv, rng, scaled_rect(name, "spray_a"), leaf, 190, twig, size=(0.08, 0.125))
    cluster_spray(cv, rng, scaled_rect(name, "spray_b"), leaf, 170, twig, size=(0.085, 0.13), n_side=6)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_ginkgo(seed=12):
    name = "Leaves_Ginkgo"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    golds = [hexc(c) for c in ("#FFCB1F", "#FFD93E", "#F7BE16", "#FFE24E", "#F5B021", "#FFD233")]
    greenish = [hexc("#C8C334"), hexc("#B9BE3A")]
    twig = hexc("#5E5040")

    def leaf(p, ang, L, dark):
        c = jit(pick(golds, rng) if rng.random() > 0.08 else pick(greenish, rng), rng, s=0.05)
        leaf_fan(cv, rng, p, ang, L, c, dark, squash=rng.uniform(0.5, 1.0))
    dr = (0.78, 1.0)
    cluster_round(cv, rng, scaled_rect(name, "round_a"), leaf, 300, twig, size=(0.12, 0.17), margin=1.0, dark_range=dr)
    cluster_round(cv, rng, scaled_rect(name, "round_b"), leaf, 280, twig, size=(0.13, 0.18), radius=0.43,
                  margin=1.0, dark_range=dr)
    cluster_spray(cv, rng, scaled_rect(name, "spray_a"), leaf, 190, twig, size=(0.075, 0.11), margin=1.0, dark_range=dr)
    cluster_spray(cv, rng, scaled_rect(name, "spray_b"), leaf, 180, twig, size=(0.075, 0.115), n_side=6,
                  margin=1.0, dark_range=dr)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_momiji(seed=13):
    name = "Leaves_Momiji"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    reds = [hexc(c) for c in ("#D9281F", "#E63A24", "#C41E2A", "#EE4A26", "#B8182A")]
    oranges = [hexc(c) for c in ("#F2702A", "#F68A2C", "#EE5E26")]
    yellows = [hexc(c) for c in ("#F4B530", "#F0C23C")]
    twig = hexc("#4A2E2A")

    def mk(wr, wo, wy):
        w = np.array([wr, wo, wy], np.float64); w /= w.sum()

        def leaf(p, ang, L, dark):
            grp = [reds, oranges, yellows][rng.choice(3, p=w)]
            c = jit(pick(grp, rng), rng, h=0.01, s=0.05)
            tip = np.clip(c * np.array([1.05, 0.85, 0.85]), 0, 1) if rng.random() < 0.5 else None
            leaf_palmate(cv, rng, p, ang, L, c, dark, lobes=7 if rng.random() < 0.8 else 5, tipcol=tip,
                         squash=rng.uniform(0.55, 1.0))
        return leaf
    cluster_round(cv, rng, scaled_rect(name, "round_a"), mk(0.8, 0.18, 0.02), 150, twig, size=(0.2, 0.28))
    cluster_round(cv, rng, scaled_rect(name, "round_b"), mk(0.35, 0.5, 0.15), 140, twig, size=(0.2, 0.29),
                  radius=0.43)
    cluster_spray(cv, rng, scaled_rect(name, "spray_a"), mk(0.75, 0.22, 0.03), 85, twig, size=(0.13, 0.18))
    cluster_spray(cv, rng, scaled_rect(name, "spray_b"), mk(0.3, 0.45, 0.25), 80, twig, size=(0.13, 0.18),
                  n_side=6)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_sakura(seed=14):
    name = "Leaves_Sakura"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    edges = [hexc(c) for c in ("#FFC4DC", "#FFB7D5", "#FFD3E4", "#FFACCB", "#FFE0EC", "#F9BCD6")]
    centers = [hexc(c) for c in ("#E86F98", "#DE5C8A", "#F08AAE")]
    leafc = [hexc(c) for c in ("#8DAF4A", "#9C8A3E", "#7FA040", "#A0703C")]
    twig = hexc("#4A3030")
    stamen = hexc("#F7D778")

    def flower(p, ang, L, dark):
        if rng.random() < 0.06:  # young leaf
            c = jit(pick(leafc, rng), rng)
            leaf_simple(cv, p, ang, L * 0.9, c, dark, shape_ovate(w=0.3, serr=0.06, nt=12), laterals=3,
                        squash=rng.uniform(0.5, 1))
            return
        if rng.random() < 0.08:  # bud
            c = jit(hexc("#F27AA2"), rng)
            leaf_simple(cv, p, ang, L * 0.4, c, dark, shape_ovate(w=0.42, tipp=0.9), vein=1.0,
                        petiole=0.8, petcol=hexc("#7A9A3A"))
            return
        e = jit(pick(edges, rng), rng, h=0.01, s=0.12, v=0.03)
        cc = jit(pick(centers, rng), rng, h=0.01)
        if rng.random() < 0.3:  # short pedicel, mostly hidden
            q = p - L * 0.45 * np.array([math.cos(ang), math.sin(ang)])
            cv.stroke([q, p], L * 0.04, L * 0.035, hexc("#5E6A34"), dark=dark * 0.85, rim=1)
        sq = rng.uniform(0.45, 1.0)
        flower5(cv, rng, p, L * 0.55, (e, e), cc, dark, squash=sq, squash_ang=rng.uniform(0, 3.14),
                stamen_col=stamen)

    def loose_petals(c, R):
        return []
    cluster_round(cv, rng, scaled_rect(name, "round_a"), flower, 420, twig, size=(0.15, 0.19), n_sub=8,
                  dark_range=(0.74, 1.0))
    cluster_round(cv, rng, scaled_rect(name, "round_b"), flower, 390, twig, size=(0.15, 0.2), radius=0.43,
                  n_sub=8, dark_range=(0.74, 1.0))
    cluster_spray(cv, rng, scaled_rect(name, "spray_a"), flower, 240, twig, size=(0.085, 0.11), spread=1.2,
                  twig_w=0.026, dark_range=(0.74, 1.0))
    cluster_spray(cv, rng, scaled_rect(name, "spray_b"), flower, 220, twig, size=(0.085, 0.115), n_side=6,
                  spread=1.2, twig_w=0.026, dark_range=(0.74, 1.0))
    # a few loose petals scattered inside the cells (falling petals read on cards edges)
    for cell in ("round_a", "round_b", "spray_a", "spray_b"):
        x0, y0, x1, y1 = scaled_rect(name, cell)
        for k in range(10):
            p = np.array([rng.uniform(x0 + 60, x1 - 60), rng.uniform(y0 + 60, y1 - 60)])
            e = jit(pick(edges, rng), rng)
            leaf_simple(cv, p, rng.uniform(0, 6.28), 44 * SS * rng.uniform(0.8, 1.2), e, 1.0,
                        shape_petal(rr=0.45, notch=0.12), vein=1.0, basecol=pick(centers, rng) * 1.05 + 0.0,
                        tipcol=e, squash=rng.uniform(0.4, 1))
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_bamboo(seed=15):
    name = "Leaves_Bamboo"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#6FA23E", "#5E9336", "#86B84C", "#4F8530", "#7AAA42")]
    yellowed = [hexc("#B6BE58"), hexc("#A8B04C")]
    twig = hexc("#6B7E3A")

    def leaf(p, ang, L, dark):
        c = jit(pick(greens, rng) if rng.random() > 0.07 else pick(yellowed, rng), rng)
        leaf_simple(cv, p, ang, L, c, dark, shape_ovate(w=0.11, tipp=0.55, asym=0.15, basew=0.02),
                    vein=1.12, tipcol=np.clip(c * 1.1, 0, 1), basecol=c * 0.8, squash=rng.uniform(0.5, 1),
                    petiole=0.04)

    def droop_spray(rect, n, nfans):
        x0, y0, x1, y1 = rect
        Wc, Hc = x1 - x0, y1 - y0
        # bamboo: thin twigs with fans of 3-7 drooping leaves at the ends
        main = bezier(np.array([x0 + Wc * 0.5, y1 - 4]),
                      np.array([x0 + Wc * rng.uniform(0.35, 0.65), y0 + Hc * 0.45]),
                      np.array([x0 + Wc * rng.uniform(0.3, 0.7), y0 + Hc * 0.12]), 18)
        cv.stroke(main, Wc * 0.014, Wc * 0.006, twig, dark=0.85)
        fans = []
        for k in range(nfans):
            s = main[rng.integers(3, len(main))]
            a = -math.pi / 2 + rng.uniform(-1.4, 1.4)
            ln = Wc * rng.uniform(0.08, 0.2)
            e = s + ln * np.array([math.cos(a), math.sin(a)])
            cv.stroke([s, e], Wc * 0.008, Wc * 0.005, twig, dark=0.85)
            fans.append(e)
        items = []
        for e in fans:
            m = rng.integers(3, 7)
            base_a = math.pi / 2 + rng.uniform(-1.3, 1.3)  # droop (down in image = +y)
            for j in range(m):
                a = base_a + (j - (m - 1) / 2) * rng.uniform(0.25, 0.45)
                L = Wc * rng.uniform(0.22, 0.34)
                tip = e + L * np.array([math.cos(a), math.sin(a)])
                if not in_rect(tip, rect, 8) or not in_rect(e, rect, 8):
                    L *= 0.6
                    tip = e + L * np.array([math.cos(a), math.sin(a)])
                    if not in_rect(tip, rect, 8):
                        continue
                items.append((rng.random(), e, a, L))
        items.sort(key=lambda it: it[0])
        for d, p, a, L in items:
            leaf(p, a, L, mix(0.65, 1.0, d))
    droop_spray(scaled_rect(name, "round_a"), 0, 16)
    droop_spray(scaled_rect(name, "round_b"), 0, 15)
    droop_spray(scaled_rect(name, "spray_a"), 0, 12)
    droop_spray(scaled_rect(name, "spray_b"), 0, 13)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_pine(seed=16):
    name = "Leaves_Pine"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    dk = [hexc(c) for c in ("#22432A", "#2A4F2E", "#1E3D27")]
    lt = [hexc(c) for c in ("#4E7C3C", "#5C8A42", "#46733A")]
    for ci, cell in enumerate(("round_a", "round_b", "spray_a", "spray_b")):
        x0, y0, x1, y1 = scaled_rect(name, cell)
        Wc = x1 - x0
        c = np.array([(x0 + x1) / 2, (y0 + y1) / 2 + Wc * 0.05])
        R = Wc * 0.4
        phase = rng.uniform(0, 6, 2)
        # twigs
        for k in range(6):
            a = -math.pi / 2 + rng.uniform(-1.5, 1.5)
            e = c + R * 0.6 * np.array([math.cos(a), math.sin(a)])
            cv.stroke([np.array([c[0], y1 - 4]), c, e], Wc * 0.022, Wc * 0.01, hexc("#3A2C26"), dark=0.8)
        tufts = []
        flat = cell.startswith("spray")  # spray cells: flatter wider pads
        for k in range(150):
            for _ in range(40):
                p = c + rng.normal(0, 1, 2) * R * [0.6, 0.38 if flat else 0.5]
                if blob_ok(p, c, R * 0.82, phase, amp=0.12) and in_rect(p, (x0, y0, x1, y1), Wc * 0.2):
                    break
            tufts.append((p[1] + rng.normal(0, R * 0.2), p))
        tufts.sort(key=lambda t: -t[0])  # lower tufts first (behind)
        for depth, p in tufts:
            dark = mix(0.7, 1.08, np.clip((c[1] + R - p[1]) / (2 * R), 0, 1))
            needle_tuft(cv, rng, p, Wc * rng.uniform(0.075, 0.11), (pick(dk, rng), jit(pick(lt, rng), rng)), dark,
                        n=rng.integers(45, 70), up=(rng.normal(0, 0.4), -1), spread=4.2, w=2)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_sugi(seed=17):
    name = "Leaves_Sugi"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    dk = [hexc(c) for c in ("#264A2C", "#2B5230", "#224328")]
    lt = [hexc(c) for c in ("#5A853E", "#678F42", "#4F7A40")]

    def rope(pts, w, cdark, clight, dark):
        """sugi branchlet: cord of awl needles"""
        pts = np.asarray(pts, np.float32)
        n = len(pts)
        for i in range(n - 1):
            t = i / (n - 1)
            c = mix(cdark, clight, t ** 1.4)
            seg = pts[i:i + 2]
            d = seg[1] - seg[0]
            l = np.linalg.norm(d) + 1e-6
            d /= l
            nrm = np.array([-d[1], d[0]])
            ww = w * (1 - 0.55 * t)
            # needles as short strokes splaying forward on both sides
            for k in range(3):
                b = seg[0] + d * l * k / 3
                for sgn in (1, -1):
                    e = b + (d * 0.9 + nrm * sgn * 0.75) * ww * rng.uniform(0.9, 1.4)
                    cv.stroke([b, e], ww * 0.55, ww * 0.15, c * rng.uniform(0.9, 1.08), dark=dark, rim=0.9)
            cv.stroke(seg, ww * 0.9, ww * 0.85, c * 0.92, dark=dark, rim=1)

    for cell in ("spray_a", "spray_b"):
        x0, y0, x1, y1 = scaled_rect(name, cell)
        Wc, Hc = x1 - x0, y1 - y0
        yc = (y0 + y1) / 2
        # main axis from left-centre to right, gently drooping then rising tip
        main = bezier(np.array([x0 + 6, yc]), np.array([x0 + Wc * 0.5, yc + Hc * 0.12]),
                      np.array([x1 - Wc * 0.04, yc - Hc * 0.05]), 26)
        cv.stroke(main[:14], Hc * 0.045, Hc * 0.02, hexc("#5A3A28"), dark=0.8)
        items = []
        for k in range(26):
            i = int(2 + (len(main) - 4) * (k + rng.uniform(0, 1)) / 26)
            s = main[min(i, len(main) - 2)]
            frac = i / len(main)
            side = 1 if k % 2 == 0 else -1
            ln = Hc * (0.42 * (1 - frac) ** 0.6 + 0.08) * rng.uniform(0.75, 1.1)
            a = side * rng.uniform(0.6, 1.1)
            e = s + ln * np.array([math.cos(a), math.sin(a)])
            e[1] = np.clip(e[1], y0 + Hc * 0.08, y1 - Hc * 0.08)
            branch = bezier(s, (s + e) / 2 + rng.normal(0, Hc * 0.03, 2), e, 7)
            items.append((rng.random(), branch, ln))
            # tertiary
            for j in range(rng.integers(2, 4)):
                b = branch[rng.integers(2, 6)]
                a2 = a + rng.choice([-1, 1]) * rng.uniform(0.5, 0.9) * 0.6
                l2 = ln * rng.uniform(0.3, 0.5)
                e2 = b + l2 * np.array([math.cos(a2), math.sin(a2)])
                e2[1] = np.clip(e2[1], y0 + Hc * 0.06, y1 - Hc * 0.06)
                items.append((rng.random(), bezier(b, (b + e2) / 2, e2, 5), l2))
        items.append((1.0, main, Wc))
        items.sort(key=lambda it: it[0])
        for depth, br, ln in items:
            rope(br, Hc * 0.05, pick(dk, rng), jit(pick(lt, rng), rng), mix(0.7, 1.0, depth))
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_azalea(seed=18):
    name = "Leaves_Azalea"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#3E6E2E", "#4C7E34", "#356428", "#5A8A3A")]
    pinks = [hexc(c) for c in ("#FF5FA2", "#FF7DB5", "#F7509A", "#FF96C6", "#FFA8CF")]
    twig = hexc("#4A3A30")
    azshape = shape_petal(rr=0.4, notch=0.03)

    def mk(pflower):
        def leaf(p, ang, L, dark):
            if rng.random() < pflower:
                pc = jit(pick(pinks, rng), rng, h=0.01)
                flower5(cv, rng, p, L * 0.8, (pc, pc), np.clip(pc * 0.9 + 0.1, 0, 1), max(dark, 0.8),
                        squash=rng.uniform(0.6, 1.0), squash_ang=rng.uniform(0, 3), petal_shape=azshape,
                        spot_col=hexc("#B8205E"), stamen_col=hexc("#FFE3F0"))
            else:
                c = jit(pick(greens, rng), rng)
                leaf_simple(cv, p, ang, L * 0.7, c, dark, shape_ovate(w=0.32, tipp=0.7), laterals=0,
                            squash=rng.uniform(0.5, 1))
        return leaf
    kw = dict(radius=0.46, margin=0.5, dark_range=(0.68, 1.0), fill=0.65)
    cluster_round(cv, rng, scaled_rect(name, "round_a"), mk(0.3), 480, twig, size=(0.12, 0.17), **kw)
    cluster_round(cv, rng, scaled_rect(name, "round_b"), mk(0.42), 440, twig, size=(0.12, 0.17), **kw)
    cluster_round(cv, rng, scaled_rect(name, "spray_a"), mk(0.12), 560, twig, size=(0.12, 0.16), **kw)
    cluster_round(cv, rng, scaled_rect(name, "spray_b"), mk(0.0), 600, twig, size=(0.12, 0.16), **kw)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_boxwood(seed=19):
    name = "Leaves_Boxwood"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#4E7F2E", "#5E9338", "#3E6A28", "#6A9C3C")]
    new = [hexc("#86B44A"), hexc("#7AAA45")]

    def leaf(p, ang, L, dark):
        c = jit(pick(greens, rng) if rng.random() > 0.15 else pick(new, rng), rng)
        leaf_simple(cv, p, ang, L, c, dark, shape_ovate(w=0.42, tipp=1.0), laterals=0,
                    tipcol=np.clip(c * 1.15, 0, 1), basecol=c * 0.85, squash=rng.uniform(0.5, 1), rim=0.8)
    for cell in ("round_a", "round_b", "spray_a", "spray_b"):
        cluster_round(cv, rng, scaled_rect(name, cell), leaf, 1700, hexc("#4A3A2A"), size=(0.07, 0.1),
                      radius=0.47, n_sub=10, outward=0.45, margin=0.5, fill=0.7)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_bush(seed=20):
    name = "Leaves_Bush"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    dark_g = [hexc(c) for c in ("#2F5E2A", "#3A6C30", "#284F26", "#467A35")]   # camellia/glossy
    light_g = [hexc(c) for c in ("#6DA040", "#7FB247", "#5E9138", "#90BF4C")]  # light deciduous

    def mk(cols, w):
        def leaf(p, ang, L, dark):
            c = jit(pick(cols, rng), rng)
            leaf_simple(cv, p, ang, L, c, dark, shape_ovate(w=w, tipp=0.75, serr=0.04, nt=10), laterals=3,
                        tipcol=np.clip(c * 1.12, 0, 1), basecol=c * 0.8, squash=rng.uniform(0.5, 1))
        return leaf
    cluster_round(cv, rng, scaled_rect(name, "round_a"), mk(dark_g, 0.33), 480, hexc("#4A3A2A"), size=(0.13, 0.19), fill=0.55,
                  radius=0.46)
    cluster_round(cv, rng, scaled_rect(name, "round_b"), mk(dark_g, 0.36), 450, hexc("#4A3A2A"), size=(0.14, 0.2), fill=0.55,
                  radius=0.46)
    cluster_round(cv, rng, scaled_rect(name, "spray_a"), mk(light_g, 0.3), 560, hexc("#5A4A35"), size=(0.12, 0.17), fill=0.55,
                  radius=0.46)
    cluster_round(cv, rng, scaled_rect(name, "spray_b"), mk(light_g, 0.28), 540, hexc("#5A4A35"), size=(0.12, 0.18), fill=0.55,
                  radius=0.46)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


# ----------------------------------------------------------------------------- ground cover
def blade(cv, rng, base, height, lean, width, c0, c1, dark, mid=None, curl=0.0):
    tip = base + np.array([lean, -height])
    ctrl = base + np.array([lean * 0.25 + curl, -height * 0.6])
    spine = bezier(base, ctrl, tip, 14)
    d = np.gradient(spine, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-6
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    t = np.linspace(0, 1, len(spine))[:, None]
    w = width * (1 - t ** 1.3) * 0.5 + 0.6
    poly = np.concatenate([spine + nrm * w, (spine - nrm * w)[::-1]])
    lines = []
    if mid is not None:
        lines.append((spine[1:-2], mid, max(1, int(width * 0.18))))
    cv.draw([poly], cf_grad(c0, c1, base, tip, gamma=0.8), dark=dark, rim=0.9, lines=lines)
    return spine


def atlas_grass(seed=21):
    name = "Grass"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#6E9E3A", "#7FAE42", "#5C8A33", "#94BC4C", "#86A63E")]
    dry = [hexc("#B9B060"), hexc("#A89A50")]

    def clump(cell, n, hmin, hmax, spread, seed_heads=False, flowers=False, width=(14, 22)):
        x0, y0, x1, y1 = scaled_rect(name, cell)
        Wc, Hc = x1 - x0, y1 - y0
        items = []
        for k in range(n):
            bx = x0 + Wc / 2 + rng.normal(0, Wc * spread)
            bx = np.clip(bx, x0 + Wc * 0.12, x1 - Wc * 0.12)
            h = Hc * rng.uniform(hmin, hmax) * (1 - 0.5 * abs(bx - (x0 + Wc / 2)) / (Wc / 2))
            lean = (bx - (x0 + Wc / 2)) * rng.uniform(0.4, 1.4) + rng.normal(0, Wc * 0.06)
            lean = np.clip(lean, x0 + 10 - bx, x1 - 10 - bx)
            items.append((rng.random(), bx, h, lean))
        items.sort(key=lambda i: i[0])
        for depth, bx, h, lean in items:
            c = jit(pick(greens, rng) if rng.random() > 0.1 else pick(dry, rng), rng)
            blade(cv, rng, np.array([bx, y1 - 2]), h, lean, rng.uniform(*width) * SS, c * 0.45, np.clip(c * 1.1, 0, 1),
                  mix(0.75, 1.0, depth))
        if seed_heads:
            for k in range(7):
                bx = x0 + Wc / 2 + rng.normal(0, Wc * 0.15)
                h = Hc * rng.uniform(0.7, 0.92)
                lean = rng.normal(0, Wc * 0.1)
                sp = blade(cv, rng, np.array([bx, y1 - 2]), h, lean, 5 * SS, hexc("#6E7A3A"), hexc("#A8A860"), 0.95)
                tip = sp[-1]
                for j in range(12):
                    p = tip + np.array([rng.normal(0, 6), j * 7.0 + rng.normal(0, 3)])
                    cv.draw([xf(shape_ovate(w=0.35), p, -math.pi / 2 + rng.normal(0, 0.4), 28)],
                            lambda xx, yy: hexc("#C9B878"), rim=0.85, dark=rng.uniform(0.85, 1.0))
        if flowers:
            for k in range(9):
                bx = x0 + Wc / 2 + rng.normal(0, Wc * 0.18)
                bx = np.clip(bx, x0 + 40, x1 - 40)
                h = Hc * rng.uniform(0.35, 0.65)
                sp = blade(cv, rng, np.array([bx, y1 - 2]), h, rng.normal(0, Wc * 0.05), 4 * SS,
                           hexc("#5C7A30"), hexc("#7A9A3A"), 0.95)
                col = [hexc("#FFFFFF"), hexc("#FFE45A"), hexc("#C9A2E8")][k % 3]
                flower5(cv, rng, sp[-1], 22 * SS * rng.uniform(0.8, 1.2), (col, col), hexc("#F2C23A"), 1.0,
                        squash=rng.uniform(0.6, 1.0), petal_shape=shape_petal(rr=0.5, notch=0.0),
                        stamen_col=hexc("#F2A23A"))
    clump("clump_a", 120, 0.5, 0.95, 0.2)
    clump("clump_b", 110, 0.4, 0.8, 0.22)
    clump("tall", 90, 0.6, 0.97, 0.18, seed_heads=True, width=(12, 18))
    clump("flowers", 100, 0.35, 0.7, 0.22, flowers=True)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_fern(seed=22):
    name = "Fern"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    greens = [hexc(c) for c in ("#4F8A34", "#5F9A3C", "#46803A", "#6BA444")]
    for ci, cell in enumerate(("frond_a", "frond_b")):
        x0, y0, x1, y1 = scaled_rect(name, cell)
        Wc, Hc = x1 - x0, y1 - y0
        base = np.array([x0 + Wc / 2, y1 - 4])
        tip = np.array([x0 + Wc / 2 + Wc * (0.08 if ci == 0 else -0.06), y0 + Hc * 0.04])
        ctrl = np.array([x0 + Wc / 2 + Wc * (0.1 if ci == 0 else -0.1), y0 + Hc * 0.5])
        rach = bezier(base, ctrl, tip, 60)
        c = pick(greens, rng)
        n_p = 30 if ci == 0 else 24
        items = []
        for k in range(n_p):
            t = 0.1 + 0.88 * k / n_p
            i = int(t * (len(rach) - 1))
            s = rach[i]
            d = rach[min(i + 1, len(rach) - 1)] - rach[max(i - 1, 0)]
            ra = math.atan2(d[1], d[0])
            for side in (1, -1):
                prof = math.sin(math.pi * (0.12 + 0.88 * t)) ** 0.7
                L = Wc * 0.46 * prof * rng.uniform(0.92, 1.05)
                if L < 8:
                    continue
                a = ra + side * math.radians(70 - 25 * t) * rng.uniform(0.9, 1.1)
                tipp = s + L * np.array([math.cos(a), math.sin(a)])
                if tipp[0] < x0 + 8 or tipp[0] > x1 - 8:
                    L *= 0.8
                items.append((s, a, L, side))
        for s, a, L, side in items:
            tt = np.linspace(0, 1, 40)
            nl = 9
            hw = 0.13 * (1 - tt) ** 0.7 * (0.55 + 0.45 * np.abs(np.sin(np.pi * tt * nl))) + 0.01
            shape = np.concatenate([np.stack([tt, hw], 1), np.stack([tt[::-1], -hw[::-1]], 1)])
            cc = jit(c, rng, s=0.04, v=0.05)
            leaf_simple(cv, s, a, L, cc, rng.uniform(0.85, 1.0), shape, vein=0.85, basecol=cc * 0.75,
                        tipcol=np.clip(cc * 1.12, 0, 1), rim=0.88)
        cv.stroke(rach, Wc * 0.02, Wc * 0.006, hexc("#3E5A26"), dark=0.9)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_weeds(seed=23):
    name = "Weeds"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    # --- susuki (Miscanthus): arching blades with white midrib + silvery plumes
    x0, y0, x1, y1 = scaled_rect(name, "susuki")
    Wc, Hc = x1 - x0, y1 - y0
    bladec = [hexc(c) for c in ("#8FA04A", "#A8A456", "#7E9442", "#B8A85E")]
    items = []
    for k in range(70):
        bx = np.clip(x0 + Wc / 2 + rng.normal(0, Wc * 0.08), x0 + 30, x1 - 30)
        h = Hc * rng.uniform(0.3, 0.62)
        lean = rng.normal(0, Wc * 0.22)
        lean = np.clip(lean, x0 + 12 - bx, x1 - 12 - bx)
        items.append((rng.random(), bx, h, lean))
    items.sort(key=lambda i: i[0])
    for d, bx, h, lean in items:
        c = jit(pick(bladec, rng), rng)
        blade(cv, rng, np.array([bx, y1 - 2]), h, lean, rng.uniform(9, 14) * SS, c * 0.5, np.clip(c * 1.1, 0, 1),
              mix(0.75, 1.0, d), mid=(lambda cc: np.clip(cc * 1.35 + 0.12, 0, 1)), curl=rng.normal(0, 30))
    plume_cols = [hexc(c) for c in ("#EFE6CC", "#E2D2B0", "#D6C29E", "#EAD3C8")]
    for k in range(9):
        bx = np.clip(x0 + Wc / 2 + rng.normal(0, Wc * 0.1), x0 + 60, x1 - 60)
        h = Hc * rng.uniform(0.72, 0.9)
        lean = rng.normal(0, Wc * 0.12)
        stem = blade(cv, rng, np.array([bx, y1 - 2]), h, lean, 5 * SS, hexc("#7A7A3E"), hexc("#B8A870"), 0.95)
        top = stem[-1]
        droop = rng.choice([-1, 1])
        pc = pick(plume_cols, rng)
        segs = []
        for j in range(22):
            s = top + np.array([0, j * Hc * 0.006])
            a = -math.pi / 2 + droop * rng.uniform(0.15, 0.9)
            L = Hc * rng.uniform(0.07, 0.15)
            e = s + L * np.array([math.cos(a), math.sin(a)]) + np.array([0, L * 0.4])
            segs.append(bezier(s, s + (e - s) * 0.5 + [0, -L * 0.3], e, 8))
        allp = np.concatenate(segs)
        bb = (allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max())

        def mfn(m, off, segs=segs):
            for sg in segs:
                q = np.round((sg - off) * 16).astype(np.int32)
                cv2.polylines(m, [q], False, 1, 7, lineType=cv2.LINE_8, shift=4)
                for p in sg[2::2]:  # fluffy tufts
                    cv2.circle(m, tuple(np.round((p - off) * 16).astype(int)), 5 * 16, 1, -1, shift=4)
        cv.draw(None, cf_radial(pc * 0.85, np.clip(pc * 1.05, 0, 1), top, Hc * 0.15), mask_fn=mfn, bbox=bb, rim=0.92,
                dark=rng.uniform(0.9, 1.0))
    # --- autumn weeds: goldenrod-like yellow panicles + dry grass + small leaves
    x0, y0, x1, y1 = scaled_rect(name, "weeds")
    Wc, Hc = x1 - x0, y1 - y0
    items = []
    for k in range(55):
        bx = np.clip(x0 + Wc / 2 + rng.normal(0, Wc * 0.12), x0 + 30, x1 - 30)
        items.append((rng.random(), bx, Hc * rng.uniform(0.2, 0.5), rng.normal(0, Wc * 0.15)))
    items.sort(key=lambda i: i[0])
    for d, bx, h, lean in items:
        c = jit(pick([hexc("#A49A4A"), hexc("#8C8A40"), hexc("#B5A15A"), hexc("#7E8A3A")], rng), rng)
        lean = np.clip(lean, x0 + 12 - bx, x1 - 12 - bx)
        blade(cv, rng, np.array([bx, y1 - 2]), h, lean, rng.uniform(8, 12) * SS, c * 0.5, np.clip(c * 1.1, 0, 1),
              mix(0.75, 1.0, d))
    for k in range(7):
        bx = np.clip(x0 + Wc / 2 + rng.normal(0, Wc * 0.14), x0 + 70, x1 - 70)
        h = Hc * rng.uniform(0.6, 0.9)
        lean = rng.normal(0, Wc * 0.06)
        stem = blade(cv, rng, np.array([bx, y1 - 2]), h, lean, 6 * SS, hexc("#5A6A2E"), hexc("#7A8A3A"), 0.95)
        # leaves on stem
        for j in range(4, 12, 2):
            s = stem[j]
            side = 1 if j % 4 == 0 else -1
            leaf_simple(cv, s, -math.pi / 2 + side * 1.0, Hc * 0.08, jit(hexc("#6A8A36"), rng), 0.9,
                        shape_ovate(w=0.16, tipp=0.6), laterals=0)
        # yellow panicle: arching side branches with tiny florets
        top = stem[-1]
        for j in range(16):
            s = stem[-1 - int(j * 0.25)] if j < 16 else top
            s = top + (stem[-4] - top) * (j / 16)
            side = 1 if j % 2 == 0 else -1
            L = Wc * (0.13 * (1 - j / 18) + 0.04) * rng.uniform(0.7, 1.1)
            a = -math.pi / 2 + side * rng.uniform(0.5, 1.0)
            e = s + L * np.array([math.cos(a), math.sin(a)])
            br = bezier(s, s + (e - s) * 0.5 + [0, -L * 0.2], e, 8)
            cv.stroke(br, 3 * SS, 2 * SS, hexc("#8A8A3A"), rim=1)
            for p in br[2:]:
                for q in range(2):
                    pp = p + rng.normal(0, 4 * SS, 2)
                    cv.draw([circle(pp, rng.uniform(4, 6.5) * SS, 8)], (lambda xx, yy, c=jit(hexc("#F2C82E"), rng): c),
                            rim=0.85, dark=rng.uniform(0.85, 1.05))
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


def atlas_litter(seed=24):
    name = "Litter"
    W, H = ATLASES[name]["size"]
    cv = Canvas(W, H, seed)
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = scaled_rect(name, "autumn")
    Wc, Hc = x1 - x0, y1 - y0
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    phase = rng.uniform(0, 6, 2)
    cols = [hexc(h) for h in ("#D9281F", "#E64A24", "#F28A2C", "#F4C21C", "#C8A040", "#9A5A30", "#B0302A",
                              "#7A4A28")]
    pts = []
    for k in range(260):
        for _ in range(20):
            p = c + rng.normal(0, 1, 2) * [Wc * 0.22, Hc * 0.22]
            if in_rect(p, (x0, y0, x1, y1), 60) and blob_ok((p - c) * [0.5, 1] + c, c, Hc * 0.48, phase, 0.2):
                break
        else:
            continue
        pts.append(p)
    order = rng.permutation(len(pts))
    for idx, k in enumerate(order):
        p = pts[k]
        d = 0.6 + 0.4 * idx / len(pts)
        col = jit(pick(cols, rng), rng)
        kind = rng.random()
        L = Hc * rng.uniform(0.07, 0.11)
        ang = rng.uniform(0, 6.28)
        if kind < 0.45:
            leaf_palmate(cv, rng, p, ang, L * 1.2, col, d, squash=rng.uniform(0.75, 1))
        elif kind < 0.7:
            leaf_fan(cv, rng, p, ang, L, jit(pick(cols[3:5], rng), rng), d, squash=rng.uniform(0.75, 1))
        else:
            leaf_simple(cv, p, ang, L * 1.1, col, d, shape_ovate(w=0.3, serr=0.08, nt=9), laterals=4, petiole=0.1,
                        squash=rng.uniform(0.8, 1))
    # petals
    x0, y0, x1, y1 = scaled_rect(name, "petals")
    Wc, Hc = x1 - x0, y1 - y0
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    pinks = [hexc(h) for h in ("#FFC4DC", "#FFB7D5", "#FFD9E8", "#FFE8F0", "#F7A8C8")]
    for k in range(700):
        p = c + rng.normal(0, 1, 2) * [Wc * 0.2, Hc * 0.2]
        if not in_rect(p, (x0, y0, x1, y1), 40) or not blob_ok((p - c) * [0.5, 1] + c, c, Hc * 0.48, phase, 0.25):
            continue
        e = jit(pick(pinks, rng), rng)
        if rng.random() < 0.04:
            flower5(cv, rng, p, Hc * 0.035, (e, e), hexc("#E86F98"), rng.uniform(0.8, 1), squash=rng.uniform(0.8, 1))
        else:
            leaf_simple(cv, p, rng.uniform(0, 6.28), Hc * rng.uniform(0.025, 0.04), e, rng.uniform(0.82, 1.0),
                        shape_petal(rr=0.45, notch=0.12), vein=1.0, basecol=hexc("#F48FB4"), tipcol=e,
                        squash=rng.uniform(0.6, 1), rim=0.9)
    rgb, a = cv.finalize()
    save_rgba(os.path.join(OUT, name + "_albedo.png"), rgb, a)


# ============================================================================= BARK (tileable 1024)
N = 1024


def bark_sakura(seed=31):
    rng = np.random.default_rng(seed)
    base = fbm(N, 6, rng, 5, 0.55, aniso=(1.0, 0.6))
    # horizontal lenticels: short horizontal dashes
    len_ = pnoise(N, 70, rng, aniso=(0.25, 1.4))
    lent = np.clip((len_ - 1.9) * 2.0, 0, 1)
    bands = pnoise(N, 9, rng, aniso=(0.3, 1.0)) + 0.4 * pnoise(N, 30, rng)  # horizontal peeling bands
    peel = np.clip((bands - 1.3) * 2.0, 0, 1)
    fine = fbm(N, 60, rng, 3, 0.5, aniso=(0.5, 1.0))
    hgt = 0.5 * base + 0.25 * fine - 0.9 * lent + 0.5 * peel
    t = norm01(base * 0.6 + fine * 0.4)
    alb = colormap(t, [(0, "#2E2124"), (0.45, "#4A3432"), (0.75, "#5E4540"), (1, "#7A6058")])
    alb = mix(alb, hexc("#7A6A66")[None, None], (peel * 0.45)[..., None])  # silver peel
    alb = mix(alb, hexc("#A8805A")[None, None], (lent * 0.85)[..., None])  # orange-tan lenticels
    return alb, hgt, 3.0


def bark_keyaki(seed=32):
    rng = np.random.default_rng(seed)
    big = fbm(N, 5, rng, 4, 0.5, aniso=(1.0, 0.7))
    patch = pnoise(N, 7, rng, aniso=(1.0, 0.55)) + 0.35 * pnoise(N, 30, rng)
    pm = np.clip((patch + 0.55) * 3.0, 0, 1)  # 1 = grey outer bark, 0 = exfoliated patch
    fine = fbm(N, 50, rng, 3, 0.5)
    hgt = 0.25 * big + 0.15 * fine + 0.5 * pm
    alb = colormap(norm01(big * 0.6 + fine * 0.4), [(0, "#6E6A60"), (0.5, "#8E8A7E"), (1, "#A8A496")])
    under = colormap(norm01(fine), [(0, "#8A5E3C"), (1, "#B07E52")])
    alb = mix(under, alb, pm[..., None])
    edge = np.clip(1 - np.abs(patch + 0.55) * 8, 0, 1)
    alb *= (1 - 0.35 * edge)[..., None]
    return alb, hgt, 3.0


def bark_ginkgo(seed=33):
    rng = np.random.default_rng(seed)
    ridges = pnoise(N, 14, rng, aniso=(1.0, 0.12))
    r = 1 - np.abs(np.tanh(ridges * 1.3))  # ridged
    fine = fbm(N, 50, rng, 4, 0.5, aniso=(1.0, 0.4))
    crack = np.clip((pnoise(N, 25, rng, aniso=(1.0, 0.18)) - 1.2) * 2, 0, 1)
    hgt = 0.7 * (1 - r) + 0.3 * fine - 0.6 * crack
    alb = colormap(norm01(hgt), [(0, "#2E2620"), (0.4, "#5A4E42"), (0.7, "#766A5C"), (1, "#8E8476")])
    return alb, hgt, 5.0


def bark_sugi(seed=34):
    rng = np.random.default_rng(seed)
    strips = pnoise(N, 22, rng, aniso=(1.0, 0.05))
    fib = fbm(N, 80, rng, 3, 0.55, aniso=(1.0, 0.06))
    big = fbm(N, 4, rng, 3, 0.5, aniso=(1.0, 0.3))
    hgt = 0.55 * np.tanh(strips * 1.5) + 0.35 * fib + 0.2 * big
    t = norm01(hgt)
    alb = colormap(t, [(0, "#3A2218"), (0.35, "#6A3C26"), (0.6, "#84503A"), (0.85, "#9A6A50"), (1, "#A88A76")])
    grey = np.clip((big - 0.6) * 1.5, 0, 1)
    alb = mix(alb, hexc("#8A8076")[None, None] * (0.8 + 0.3 * t[..., None]), grey[..., None] * 0.6)
    return alb, hgt, 5.0


def bark_momiji(seed=35):
    rng = np.random.default_rng(seed)
    base = fbm(N, 6, rng, 4, 0.5, aniso=(1.0, 0.5))
    stripes = pnoise(N, 30, rng, aniso=(1.0, 0.08))
    fine = fbm(N, 70, rng, 3, 0.5)
    lent = np.clip((pnoise(N, 50, rng, aniso=(0.3, 1.0)) - 2.0) * 2, 0, 1)
    hgt = 0.3 * base + 0.25 * stripes + 0.15 * fine
    alb = colormap(norm01(base * 0.7 + stripes * 0.3), [(0, "#4E4A40"), (0.5, "#6E6A5A"), (1, "#868070")])
    alb = mix(alb, hexc("#5E6A48")[None, None], np.clip(base * 0.3, 0, 0.35)[..., None])  # green tint
    alb = mix(alb, hexc("#A09A88")[None, None], lent[..., None] * 0.7)
    return alb, hgt, 2.0


def bark_pine(seed=36):
    rng = np.random.default_rng(seed)
    warp = (np.stack([pnoise(N, 8, rng), pnoise(N, 8, rng)], -1) * 18.0).astype(np.float64)
    d1, d2, cid = pvoronoi(N, 70, rng, stretch=(1.0, 0.6), jitter_pts=warp)
    crack = np.clip(1 - (d2 - d1) / 26.0, 0, 1) ** 1.6
    plate = np.clip(d1 / 60.0, 0, 1)
    fine = fbm(N, 60, rng, 3, 0.5)
    cell_rand = (cid * 7919 % 101) / 100.0
    hgt = 0.6 * (1 - crack) - 0.2 * plate + 0.12 * fine + 0.12 * cell_rand
    alb = colormap(norm01(0.5 * fine + 0.5 * cell_rand - 0.3 * plate),
                   [(0, "#2E2622"), (0.4, "#453C38"), (0.8, "#5A524C"), (1, "#6E6660")])
    alb *= (1 - 0.75 * crack)[..., None]
    inner = hexc("#7A3E2A")[None, None]
    alb = mix(alb, inner * (0.7 + 0.3 * fine[..., None]), (crack ** 1.5 * 0.7)[..., None])
    return alb, hgt, 6.0


def bark_bamboo(seed=37):
    """Culm: v = one internode (node at bottom edge, wraps to top). u = around circumference."""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, N, endpoint=False)[:, None] * np.ones((1, N))
    v = 1 - yy  # v up
    streak = pnoise(N, 60, rng, aniso=(1.0, 0.02))
    fine = fbm(N, 30, rng, 3, 0.5, aniso=(1.0, 0.1))
    dnode = np.minimum(v, 1 - v)  # distance to node (at v=0/1)
    ridge = np.exp(-(dnode / 0.012) ** 2)
    scar = np.exp(-((v - 0.035) / 0.006) ** 2)
    wax = np.exp(-((1 - v) / 0.06) ** 2) * (1 - ridge)  # white powder band just below node
    hgt = 0.08 * streak + 0.06 * fine + 0.9 * ridge - 0.4 * scar
    base = colormap(norm01(streak * 0.5 + fine * 0.5), [(0, "#4F7E2A"), (0.5, "#6A9A36"), (1, "#86B048")])
    yel = np.clip(pnoise(N, 2, rng, aniso=(1.0, 1.0)) * 0.25 + 0.15, 0, 0.4)
    alb = mix(base, hexc("#A8A84A")[None, None], yel[..., None])
    alb = mix(alb, hexc("#C6CDA8")[None, None], (wax * 0.65)[..., None])
    alb = mix(alb, hexc("#8A8A3E")[None, None], (ridge * 0.6)[..., None])
    alb = mix(alb, hexc("#5A5A2E")[None, None], (scar * 0.7)[..., None])
    return alb, hgt, 4.0


def bark_shrub(seed=38):
    rng = np.random.default_rng(seed)
    base = fbm(N, 8, rng, 4, 0.5, aniso=(1.0, 0.3))
    fine = fbm(N, 60, rng, 3, 0.5, aniso=(1.0, 0.3))
    hgt = 0.5 * base + 0.3 * fine
    alb = colormap(norm01(hgt), [(0, "#3A2E26"), (0.5, "#5A4A3C"), (1, "#7A6A58")])
    return alb, hgt, 3.0


BARKS = {"Sakura": bark_sakura, "Keyaki": bark_keyaki, "Ginkgo": bark_ginkgo, "Sugi": bark_sugi,
         "Momiji": bark_momiji, "Pine": bark_pine, "Bamboo": bark_bamboo, "Shrub": bark_shrub}

ATLAS_FUNCS = {"Leaves_Keyaki": atlas_keyaki, "Leaves_Ginkgo": atlas_ginkgo, "Leaves_Momiji": atlas_momiji,
               "Leaves_Sakura": atlas_sakura, "Leaves_Bamboo": atlas_bamboo, "Leaves_Pine": atlas_pine,
               "Leaves_Sugi": atlas_sugi, "Leaves_Azalea": atlas_azalea, "Leaves_Boxwood": atlas_boxwood,
               "Leaves_Bush": atlas_bush, "Grass": atlas_grass, "Fern": atlas_fern, "Weeds": atlas_weeds,
               "Litter": atlas_litter}


def make_bark(name):
    alb, hgt, strength = BARKS[name]()
    hgt = norm01(hgt)
    save_rgb(os.path.join(OUT, f"Bark_{name}_albedo.png"), alb)
    save_rgb(os.path.join(OUT, f"Bark_{name}_normal.png"), height_to_normal(hgt, strength * N / 256.0))


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    targets = argv or (list(ATLAS_FUNCS) + ["Bark_" + b for b in BARKS])
    for t in targets:
        if t in ATLAS_FUNCS:
            ATLAS_FUNCS[t]()
        elif t.startswith("Bark_") and t[5:] in BARKS:
            make_bark(t[5:])
        elif t == "barks":
            for b in BARKS:
                make_bark(b)
        elif t == "atlases":
            for f in ATLAS_FUNCS.values():
                f()
        else:
            print("unknown target", t)


if __name__ == "__main__":
    main(sys.argv[1:])
