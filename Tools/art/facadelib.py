"""facadelib — multi-channel, wrap-aware painting helpers for tileable building facades.

A `Facade` holds aligned channels at internal resolution (ss x output):
  alb (H,W,3)  albedo, sRGB 0..1
  hgt (H,W)    height, 0 = deepest recess, ~0.5 = wall plane, 1 = most proud element
  metal (H,W)  metallic
  smooth (H,W) smoothness
  emis (H,W,3) night emission
  aom (H,W)    hand-painted AO multiplier (1 = no occlusion)

Every path goes through `P()` which adds wrapped copies (offset by +-W / +-H) so elements
crossing a tile edge reappear on the opposite edge -> perfectly seamless tiles.
All drawing coordinates are in OUTPUT pixels (design units).
"""
from __future__ import annotations

import math
import os
import sys

import cv2
import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import (C, hexc, mix, rng, noise, blur_wrap, normal_from_height, save_image,  # noqa: E402
                    raster, rect, poly, circle, ellipse, text_path, vtext_path, fit_path, bounds,
                    smooth_closed, combine, f32, out_path, typeface)


# --------------------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------------------
def K(t):
    """Approximate black-body tint (normalised so max channel = 1) for colour temperature t (K)."""
    t = t / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    c = np.clip(np.array([r, g, b], f32) / 255.0, 0, 1)
    return (c / c.max()).astype(f32)


def rgb(h):
    return hexc(h)


# --------------------------------------------------------------------------------------
# Facade canvas
# --------------------------------------------------------------------------------------
class Region:
    __slots__ = ("m", "ys", "xs")

    def __init__(self, m, ys, xs):
        self.m, self.ys, self.xs = m, ys, xs


class Facade:
    def __init__(self, name, w=2048, h=2048, ss=2, wrap_x=True, wrap_y=True, seed=0):
        self.name = name
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.wrap_x, self.wrap_y = wrap_x, wrap_y
        self.seed = seed
        H, W = self.H, self.W
        self.alb = np.zeros((H, W, 3), f32)
        self.hgt = np.full((H, W), 0.5, f32)
        self.metal = np.zeros((H, W), f32)
        self.smooth = np.full((H, W), 0.2, f32)
        self.emis = np.zeros((H, W, 3), f32)
        self.aom = np.ones((H, W), f32)
        self.windows = []  # (x0, y0, x1, y1, lit) for every glazed opening painted
        self._yy = (np.arange(H, dtype=f32)[:, None] + 0.5) / ss  # design-unit coordinates
        self._xx = (np.arange(W, dtype=f32)[None, :] + 0.5) / ss

    # ---------------- geometry ----------------
    def P(self, path: skia.Path) -> skia.Path:
        """Add wrapped copies of path for seamless tiling."""
        l, t, r_, b = bounds(path)
        out = skia.Path(path)
        offs_x = [0]
        offs_y = [0]
        if self.wrap_x:
            if l < 0:
                offs_x.append(self.w)
            if r_ > self.w:
                offs_x.append(-self.w)
        if self.wrap_y:
            if t < 0:
                offs_y.append(self.h)
            if b > self.h:
                offs_y.append(-self.h)
        for ox in offs_x:
            for oy in offs_y:
                if ox == 0 and oy == 0:
                    continue
                q = skia.Path(path)
                q.offset(ox, oy)
                out.addPath(q)
        return out

    def region(self, path, stroke=0.0, fill=True, evenodd=False, **kw) -> Region | None:
        """Rasterise (wrapped) path into a cropped mask region."""
        pw = self.P(path)
        l, t, r_, b = bounds(pw)
        pad = stroke / 2 + 2
        s = self.ss
        x0 = max(0, int(math.floor((l - pad) * s)))
        y0 = max(0, int(math.floor((t - pad) * s)))
        x1 = min(self.W, int(math.ceil((r_ + pad) * s)))
        y1 = min(self.H, int(math.ceil((b + pad) * s)))
        if x1 <= x0 or y1 <= y0:
            return None
        surf = skia.Surface.MakeRaster(skia.ImageInfo.MakeA8(x1 - x0, y1 - y0))
        cv = surf.getCanvas()
        cv.clear(0)
        cv.translate(-x0, -y0)
        cv.scale(s, s)
        paint = skia.Paint(AntiAlias=True)
        if stroke > 0:
            paint.setStyle(skia.Paint.kStrokeAndFill_Style if fill else skia.Paint.kStroke_Style)
            paint.setStrokeWidth(stroke)
            paint.setStrokeJoin(skia.Paint.kRound_Join if kw.get("join", "miter") == "round" else skia.Paint.kMiter_Join)
            paint.setStrokeCap(skia.Paint.kRound_Cap if kw.get("cap", "butt") == "round" else skia.Paint.kButt_Cap)
        if evenodd:
            pw.setFillType(skia.PathFillType.kEvenOdd)
        cv.drawPath(pw, paint)
        a = surf.makeImageSnapshot().toarray()
        if a.ndim == 3:
            a = a[..., -1]
        return Region(a.astype(f32) / 255.0, slice(y0, y1), slice(x0, x1))

    def R(self, x0, y0, x1, y1, radius=0):
        return self.region(rect(x0, y0, x1, y1, radius))

    def full(self) -> Region:
        return Region(np.ones((self.H, self.W), f32), slice(0, self.H), slice(0, self.W))

    def from_mask(self, m) -> Region:
        return Region(m.astype(f32), slice(0, self.H), slice(0, self.W))

    # ---------------- fields (design-unit coordinates, cropped to region) ----------------
    def Y(self, reg: Region):
        return self._yy[reg.ys]

    def X(self, reg: Region):
        return self._xx[:, reg.xs]

    def lx(self, reg: Region, x0, ww):
        """Wrap-aware local x (design px) relative to an element spanning [x0, x0+ww]."""
        X = self.X(reg)
        if not self.wrap_x or ww >= self.w * 0.98:
            return X - x0
        xc = x0 + ww / 2
        return ((X - xc + self.w / 2) % self.w) - self.w / 2 + ww / 2

    def ly(self, reg: Region, y0, hh):
        Y = self.Y(reg)
        if not self.wrap_y or hh >= self.h * 0.98:
            return Y - y0
        yc = y0 + hh / 2
        return ((Y - yc + self.h / 2) % self.h) - self.h / 2 + hh / 2

    def tile_period(self, approx_design_px, angle45=True):
        """Internal-px halftone period near approx that tiles exactly across W and H."""
        k = math.sqrt(2) if angle45 else 1.0
        n = max(1, round(self.W / (approx_design_px * self.ss * k)))
        return self.W / (n * k)

    def _fit(self, val, reg: Region):
        if val is None:
            return None
        v = np.asarray(val, f32)
        if v.ndim == 0 or (v.ndim == 1 and v.shape[0] in (1, 3)):
            return v
        if v.shape[0] == self.H and (v.ndim == 1 or v.shape[1] == self.W):
            return v[reg.ys, reg.xs]
        if v.shape[0] == self.H and v.shape[1] == 1:
            return v[reg.ys]
        if v.shape[0] == 1 and v.shape[1] == self.W:
            return v[:, reg.xs]
        return v  # assume already region-shaped

    # ---------------- painting ----------------
    def put(self, reg: Region | None, alb=None, h=None, hmode="set", metal=None, smooth=None,
            emis=None, emode="set", ao=None, opacity=1.0):
        """Lerp channels toward given values inside region mask.
        hmode: 'set' (lerp to h), 'add' (+= h*m), 'max' (raise to at least h), 'min'.
        emode: 'set' lerp, 'add' additive, 'mul' multiply.
        ao: multiply hand AO by lerp(1, ao, m)."""
        if reg is None:
            return
        m = reg.m * opacity if opacity != 1 else reg.m
        sl = (reg.ys, reg.xs)
        m3 = m[..., None]
        if alb is not None:
            v = self._fit(alb, reg)
            a = self.alb[sl]
            a += (v - a) * m3
        if h is not None:
            v = self._fit(h, reg)
            a = self.hgt[sl]
            if hmode == "set":
                a += (v - a) * m
            elif hmode == "add":
                a += v * m
            elif hmode == "max":
                a += (np.maximum(a, v) - a) * m
            elif hmode == "min":
                a += (np.minimum(a, v) - a) * m
        if metal is not None:
            v = self._fit(metal, reg)
            a = self.metal[sl]
            a += (v - a) * m
        if smooth is not None:
            v = self._fit(smooth, reg)
            a = self.smooth[sl]
            a += (v - a) * m
        if emis is not None:
            v = self._fit(emis, reg)
            a = self.emis[sl]
            if emode == "set":
                a += (v - a) * m3
            elif emode == "add":
                a += v * m3
            elif emode == "mul":
                a *= (1 - m3) + v * m3
        if ao is not None:
            v = self._fit(ao, reg)
            a = self.aom[sl]
            a *= (1 - m) + v * m

    def tint(self, reg: Region | None, color, amount=1.0):
        """Multiply albedo by colour (grime, stains)."""
        if reg is None:
            return
        m = (reg.m * amount)[..., None]
        v = self._fit(color, reg)
        a = self.alb[reg.ys, reg.xs]
        a *= (1 - m) + v * m

    # ---------------- noise on demand (periodic) ----------------
    def noise(self, scale, seed, **kw):
        return noise(self.H, self.W, scale * self.ss, seed, **kw)

    # ---------------- output ----------------
    def finalize(self, outdir, normal_strength=6.0, height_blur=0.8, ao_radii=(3, 10, 28),
                 ao_gain=(2.0, 1.2, 0.6), ao_clip=(0.45, 0.3, 0.2), albedo_ao=0.35, write_height=True,
                 emis_gain=1.0, preview_dir=None):
        os.makedirs(outdir, exist_ok=True)
        w, h, s = self.w, self.h, self.ss
        name = self.name

        def down(a):
            return cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA) if s != 1 else a

        def wblur(a, sig):
            if self.wrap_x and self.wrap_y:
                return blur_wrap(a, sig)
            # horizontal wrap only: pad x wrap, y reflect
            pad = int(sig * 3) + 1
            k = pad * 2 + 1
            big = np.pad(a, [(pad, pad), (0, 0)] + [(0, 0)] * (a.ndim - 2), mode="reflect")
            big = np.pad(big, [(0, 0), (pad, pad)] + [(0, 0)] * (a.ndim - 2), mode="wrap")
            big = cv2.GaussianBlur(big, (k, k), sig)
            return big[pad:-pad, pad:-pad]

        # ---- normal from internal-res height (beveled), then downsample ----
        hb = wblur(self.hgt, height_blur * s)
        nrm = normal_from_height(hb, strength=normal_strength * s, wrap=True)
        if not self.wrap_y:
            # avoid wrap artefacts on top/bottom rows for non-vertically-tiling sets
            nrm[:2] = nrm[2:3]; nrm[-2:] = nrm[-3:-2]
        nrm = down(nrm) * 2 - 1
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-8
        nrm = nrm * 0.5 + 0.5
        del hb

        hgt = down(self.hgt)
        # ---- AO: multi-scale cavity from height * hand-painted AO ----
        ao = np.ones((h, w), f32)
        for rad, g, cl in zip(ao_radii, ao_gain, ao_clip):
            cav = wblur(hgt, rad) - hgt
            ao *= 1 - np.clip(cav * g, 0, cl)
        ao *= down(self.aom)
        ao = np.clip(ao, 0.05, 1).astype(f32)

        alb = down(self.alb)
        alb = alb * (1 - albedo_ao * (1 - ao))[..., None]
        emis = np.clip(down(self.emis) * emis_gain, 0, 1)
        metal = np.clip(down(self.metal), 0, 1)
        smooth = np.clip(down(self.smooth), 0, 1)
        mask = np.stack([metal, ao, np.zeros_like(ao), smooth], -1)

        paths = {}
        if self.windows:
            import json
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews",
                                   f"facade_{name}_windows.json"), "w") as fh:
                json.dump([list(map(float, w[:4])) + [w[4]] for w in self.windows], fh)
        paths["albedo"] = save_image(np.clip(alb, 0, 1), os.path.join(outdir, f"{name}_albedo.png"), "RGB")
        paths["normal"] = save_image(nrm, os.path.join(outdir, f"{name}_normal.png"), "RGB")
        paths["emission"] = save_image(emis, os.path.join(outdir, f"{name}_emission.png"), "RGB")
        paths["mask"] = save_image(mask, os.path.join(outdir, f"{name}_mask.png"), "RGBA")
        if write_height:
            hn = (hgt - hgt.min()) / max(1e-6, hgt.max() - hgt.min())
            paths["height"] = save_image(hn, os.path.join(outdir, f"{name}_height.png"), "L")
        return paths


# --------------------------------------------------------------------------------------
# Stamps / small shapes
# --------------------------------------------------------------------------------------
def person_path(cx, base_y, height, r: np.random.Generator, facing=0.0):
    """Silhouette of a person's upper body (head+shoulders+torso) standing at base_y."""
    hh = height
    head_r = hh * 0.095
    shoulder_w = hh * r.uniform(0.26, 0.32)
    neck_y = base_y - hh + head_r * 2.1
    p = skia.Path()
    p.addCircle(cx + facing * head_r * 0.3, base_y - hh + head_r, head_r)
    torso = smooth_closed([
        (cx - shoulder_w * 0.5, neck_y + hh * 0.06),
        (cx - shoulder_w * 0.18, neck_y),
        (cx + shoulder_w * 0.18, neck_y),
        (cx + shoulder_w * 0.5, neck_y + hh * 0.06),
        (cx + shoulder_w * 0.45, base_y),
        (cx - shoulder_w * 0.45, base_y),
    ], 0.3)
    p.addPath(torso)
    return p


def plant_path(cx, base_y, height, r: np.random.Generator):
    p = skia.Path()
    pw = height * 0.28
    p.addPath(poly([(cx - pw / 2, base_y - pw * 0.9), (cx + pw / 2, base_y - pw * 0.9),
                    (cx + pw * 0.38, base_y), (cx - pw * 0.38, base_y)]))
    for i in range(9):
        a = -math.pi / 2 + r.uniform(-1.1, 1.1)
        L = height * r.uniform(0.45, 0.8)
        tipx = cx + math.cos(a) * L * 0.8
        tipy = base_y - pw * 0.9 + math.sin(a) * L
        lw = height * r.uniform(0.05, 0.09)
        mx, my = (cx + tipx) / 2, (base_y - pw * 0.9 + tipy) / 2
        nx, ny = -(tipy - (base_y - pw)), (tipx - cx)
        nl = math.hypot(nx, ny) + 1e-6
        nx, ny = nx / nl * lw, ny / nl * lw
        q = skia.Path()
        q.moveTo(cx, base_y - pw * 0.9)
        q.quadTo(mx + nx, my + ny, tipx, tipy)
        q.quadTo(mx - nx, my - ny, cx, base_y - pw * 0.9)
        q.close()
        p.addPath(q)
    return p


def shelf_path(x0, y0, x1, y1, r: np.random.Generator):
    """Bookshelf / storage silhouette: frame with irregular 'books'."""
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
    return p


# --------------------------------------------------------------------------------------
# Window interiors
# --------------------------------------------------------------------------------------
# stylised night interior tints (pushed saturation so windows read at night under bloom)
WARM = np.array([1.0, 0.60, 0.26], f32)      # ~2700K incandescent / LED warm
WARM2 = np.array([1.0, 0.74, 0.42], f32)     # ~3200K
NEUTRAL = np.array([1.0, 0.88, 0.70], f32)   # ~4200K
COOL = np.array([0.80, 0.92, 1.0], f32)      # ~5600K office LED
COOLER = np.array([0.74, 0.97, 0.94], f32)   # fluorescent tube green-cyan
TV_BLUE = np.array([0.35, 0.55, 1.0], f32)
BAR_PINK = np.array([1.0, 0.32, 0.68], f32)
BAR_PURPLE = np.array([0.72, 0.38, 1.0], f32)
CURTAINS = [rgb("#E9DCC4"), rgb("#D8C49A"), rgb("#9DB4C8"), rgb("#C9A27E"), rgb("#B8C9A6"),
            rgb("#E4C4C8"), rgb("#7F93B5"), rgb("#EFE8DA"), rgb("#C78F6B"), rgb("#A8B8B0")]


def window_state(r: np.random.Generator, kind="home", lit_p=0.45):
    st = {"kind": kind, "lit": r.random() < lit_p}
    if kind == "office":
        st["temp"] = COOL if r.random() < 0.7 else (NEUTRAL if r.random() < 0.6 else COOLER)
        st["cover"] = r.choice(["none", "none", "blinds", "blinds", "blinds_half"])
    elif kind == "bar":
        st["temp"] = BAR_PINK if r.random() < 0.5 else BAR_PURPLE
        st["cover"] = r.choice(["none", "blinds"])
    else:
        roll = r.random()
        st["temp"] = WARM if roll < 0.55 else (WARM2 if roll < 0.75 else (COOL if roll < 0.92 else NEUTRAL))
        st["cover"] = r.choice(["curtain", "curtain", "curtain_open", "lace", "blinds", "none"])
        st["tv"] = r.random() < 0.15
    st["curtain"] = CURTAINS[int(r.integers(len(CURTAINS)))]
    st["blind_drop"] = float(r.uniform(0.15, 1.0))
    st["gap"] = float(r.uniform(0.05, 0.35))
    st["bright"] = float(r.uniform(0.7, 1.0))
    st["seed"] = int(r.integers(1 << 30))
    return st


def paint_window(F: Facade, x0, y0, x1, y1, st, glass_alb, glass_reflect=None, smooth=0.93,
                 h=0.32, interior_vis=0.45, emis_scale=1.0, frame=None):
    """Paint one glazed opening: daylight albedo (reflective glass + visible curtains/blinds),
    and night emission according to window state `st`."""
    r = rng(st["seed"])
    reg = F.R(x0, y0, x1, y1)
    if reg is None:
        return
    F.windows.append((x0, y0, x1, y1, bool(st["lit"])))
    ww, wh = x1 - x0, y1 - y0
    ty = np.clip(F.ly(reg, y0, wh) / wh, 0, 1)
    tx = np.clip(F.lx(reg, x0, ww) / ww, 0, 1)
    shape = np.broadcast_shapes(ty.shape, tx.shape)
    ty = np.broadcast_to(ty, shape); tx = np.broadcast_to(tx, shape)

    # ---------------- daylight albedo ----------------
    g = np.asarray(glass_alb, f32)
    base = g * (1.08 - 0.25 * ty[..., None])  # sky above reflects brighter
    if glass_reflect is not None:
        gr = F._fit(glass_reflect, reg)
        if gr.ndim == 2:
            gr = gr[..., None] * np.array([0.85, 0.95, 1.0], f32)
        base = base + gr
    cov_a = np.zeros(shape, f32)   # coverage of visible interior covering (curtain/blind)
    cov_col = np.zeros(shape + (3,), f32)
    cover = st["cover"]
    if cover in ("curtain", "lace", "curtain_open"):
        col = st["curtain"] if cover != "lace" else rgb("#F2EEE6")
        fw_ = max(7.0, ww / r.uniform(10, 16))
        xw = tx * ww
        folds = (0.5 + 0.33 * np.sin(xw / fw_ * math.pi * 2 + r.uniform(0, 6))
                 + 0.17 * np.sin(xw / (fw_ * 0.43) * math.pi * 2 + r.uniform(0, 6)))
        folds = folds * (1 - 0.12 * ty) # slight hem shading
        if cover == "curtain_open":
            gap = 0.62
        else:
            gap = st["gap"] if cover == "curtain" else 0.0
        side = np.where((tx < 0.5 - gap / 2) | (tx > 0.5 + gap / 2), 1.0, 0.0).astype(f32)
        if cover == "curtain_open":
            side = np.where((tx < 0.17) | (tx > 0.83), 1.0, 0.0).astype(f32)
        cov_a = side * (0.85 if cover != "lace" else 0.6)
        cov_col = col * (0.82 + 0.18 * folds[..., None])
    elif cover in ("blinds", "blinds_half"):
        drop = st["blind_drop"] if cover == "blinds" else 0.5
        slat = 0.5 + 0.5 * np.sin(ty * wh / 3.5 * math.pi)
        inb = (ty < drop).astype(f32)
        cov_a = inb * 0.85
        cov_col = rgb("#D9D9D4") * (0.8 + 0.2 * slat[..., None])
    alb = base * (1 - cov_a[..., None] * interior_vis) + cov_col * cov_a[..., None] * interior_vis
    F.put(reg, alb=alb, h=h, metal=0.0, smooth=smooth)

    # ---------------- night emission ----------------
    if not st["lit"]:
        return
    col = np.asarray(st["temp"], f32) * st["bright"] * emis_scale
    # vertical falloff: ceiling brighter, floor darker; slight horizontal vignette
    prof = (0.72 + 0.28 * (1 - ty) ** 1.3) * (0.86 + 0.14 * np.sin(np.clip(tx, 0, 1) * math.pi))
    e = col * prof[..., None]
    kind = st["kind"]
    # ceiling fixtures
    if kind == "office":
        fix = np.zeros(shape, f32)
        nfx = max(2, int(ww / 60))
        for i in range(nfx):
            cx = (i + 0.5) / nfx
            fix = np.maximum(fix, ((np.abs(tx - cx) < 0.32 / nfx) & (np.abs(ty - 0.05) < 0.018)).astype(f32))
            fix = np.maximum(fix, ((np.abs(tx - cx) < 0.22 / nfx) & (np.abs(ty - 0.13) < 0.012)).astype(f32) * 0.8)
        e = e + fix[..., None] * 0.45
        # desks / partitions band with monitor glows
        desk = (ty > 0.70).astype(f32)
        e = e * (1 - desk[..., None] * 0.55)
        for i in range(int(r.integers(1, 4))):
            mx = r.uniform(0.1, 0.9)
            mon = ((np.abs(tx - mx) < 0.05) & (ty > 0.62) & (ty < 0.71)).astype(f32)
            e = e * (1 - mon[..., None]) + mon[..., None] * np.array([0.55, 0.75, 1.0], f32) * 0.6
    else:
        if r.random() < 0.6:
            cx = r.uniform(0.3, 0.7)
            glow = np.exp(-(((tx - cx) * ww) ** 2 + ((ty - 0.06) * wh) ** 2) / (2 * (wh * 0.1) ** 2))
            e = e + col * glow[..., None] * 0.5
    # silhouettes (people/plants/shelves) -> darken
    sil = np.zeros(shape, f32)
    if kind != "office" or r.random() < 0.22:
        n_sil = int(r.integers(0, 3)) if kind != "office" else 1
        for _ in range(n_sil):
            typ = r.choice(["person", "plant", "shelf", "person"])
            sx = x0 + ww * r.uniform(0.15, 0.85)
            if typ == "person":
                pth = person_path(sx, y1, wh * r.uniform(0.62, 0.8), r)
            elif typ == "plant":
                pth = plant_path(sx, y1, wh * r.uniform(0.35, 0.55), r)
            else:
                sw = ww * r.uniform(0.12, 0.25)
                pth = rect(sx - sw / 2, y1 - wh * r.uniform(0.4, 0.7), sx + sw / 2, y1)
            sreg = F.region(pth)
            if sreg is None:
                continue
            # paste into local sil (intersection of rects)
            ys0 = max(sreg.ys.start, reg.ys.start); ys1 = min(sreg.ys.stop, reg.ys.stop)
            xs0 = max(sreg.xs.start, reg.xs.start); xs1 = min(sreg.xs.stop, reg.xs.stop)
            if ys1 > ys0 and xs1 > xs0:
                sub = sreg.m[ys0 - sreg.ys.start:ys1 - sreg.ys.start, xs0 - sreg.xs.start:xs1 - sreg.xs.start]
                tgt = sil[ys0 - reg.ys.start:ys1 - reg.ys.start, xs0 - reg.xs.start:xs1 - reg.xs.start]
                np.maximum(tgt, sub, out=tgt)
    e = e * (1 - sil[..., None] * 0.82)
    # TV flicker glow
    if st.get("tv"):
        e = e * 0.45 + TV_BLUE * (0.35 + 0.25 * (1 - ty))[..., None]
    # coverings filter the light
    if cover in ("curtain", "curtain_open", "lace"):
        trans = np.asarray(st["curtain"], f32) * 0.85 + 0.15 if cover != "lace" else np.array([1, 1, 1], f32) * 0.9
        filt = (1 - cov_a[..., None]) + cov_a[..., None] * trans * (0.55 if cover != "lace" else 0.8)
        # folds modulate transmitted light
        e = e * filt
    elif cover in ("blinds", "blinds_half"):
        drop = st["blind_drop"] if cover == "blinds" else 0.5
        slat = (np.sin(ty * wh / 3.5 * math.pi) > 0.5).astype(f32)
        inb = (ty < drop).astype(f32)
        filt = 1 - inb * (0.5 - 0.3 * slat)
        e = e * filt[..., None]
    F.put(reg, emis=np.clip(e, 0, 1.2))


# --------------------------------------------------------------------------------------
# Grime / streaks (periodic)
# --------------------------------------------------------------------------------------
def streak_field(F: Facade, seed, scale=6.0, aniso=14.0):
    """Vertical streak noise field 0..1 (periodic)."""
    return noise(F.H, F.W, scale * F.ss, seed, beta=2.1, aniso=(1.0, aniso))


def wrap_fade_rows(F: Facade, y_start, length, power=1.3):
    """(H,1) column: 1 at y_start fading to 0 at y_start+length, wrapping vertically."""
    y = F._yy
    d = (y - y_start) % F.h if F.wrap_y else (y - y_start)
    t = np.where((d >= 0) & (d < length), 1 - d / length, 0)
    return (np.clip(t, 0, 1) ** power).astype(f32)


def wrap_band_cols(F: Facade, x0, x1, soft=2.0):
    """(1,W) row: 1 inside [x0,x1] (wrapping horizontally), soft edges."""
    x = F._xx
    w = x1 - x0
    d = (x - x0) % F.w
    inside = np.clip(np.minimum(d, w - d) / soft + 0.5, 0, 1) * (d <= w + soft)
    return inside.astype(f32)


def assign_lit(rooms_by_floor, target, r, min_per_floor=1):
    """Light rooms so that the lit *module* fraction approaches target (0..1), keeping
    every floor partially lit and partially dark. rooms_by_floor: list of lists of
    (start, width, state). Mutates state['lit']."""
    allr = [(fi, ri) for fi, fl in enumerate(rooms_by_floor) for ri in range(len(fl))]
    total = sum(rm[1] for fl in rooms_by_floor for rm in fl)
    for fl in rooms_by_floor:
        for rm in fl:
            rm[2]["lit"] = False
    order = list(r.permutation(len(allr)))
    lit = 0
    # guarantee per-floor minimum
    for fi, fl in enumerate(rooms_by_floor):
        if len(fl) > 1 and min_per_floor:
            ri = int(r.integers(len(fl)))
            fl[ri][2]["lit"] = True
            lit += fl[ri][1]
    for k in order:
        fi, ri = allr[k]
        rm = rooms_by_floor[fi][ri]
        if rm[2]["lit"]:
            continue
        if (lit + rm[1]) / total > target + 0.04:
            continue
        # keep at least one dark room per floor
        if sum(1 for q in rooms_by_floor[fi] if not q[2]["lit"]) <= 1:
            continue
        rm[2]["lit"] = True
        lit += rm[1]
    return lit / max(1, total)


# --------------------------------------------------------------------------------------
# Tile / brick fields (periodic across the whole tile)
# --------------------------------------------------------------------------------------
def tile_field(F: Facade, cols: int, rows: int, grout: float, bond: str = "running", seed=0,
               y0: float = 0.0):
    """Masonry/tile grid that repeats exactly cols x rows over the tile.
    Returns dict: grout (H,W) 0..1 (1 = joint), rnd (H,W) per-tile random 0..1,
    rnd2 second random, u,v local 0..1 coords inside each tile, edge (distance-to-edge, design px).
    bond: 'running' (half offset each row), 'stack', 'third' (1/3 offset)."""
    H, W, s = F.H, F.W, F.ss
    tw = F.w / cols
    th = F.h / rows
    y = F._yy - y0
    x = F._xx
    row = np.floor(y / th)
    if bond == "running":
        off = (row % 2) * 0.5
    elif bond == "third":
        off = (row % 3) / 3.0
    else:
        off = row * 0.0
    xs = x / tw + off
    col = np.floor(xs)
    u = xs - col
    v = (y / th - row) * np.ones_like(u)
    colw = np.mod(col, cols).astype(np.int64)
    roww = np.mod(row, rows).astype(np.int64) * np.ones_like(colw)
    h = (colw * 73856093 ^ roww * 19349663 ^ (seed * 83492791)) & 0xFFFFFF
    rnd = (h % 10007) / 10007.0
    rnd2 = ((h // 7) % 9973) / 9973.0
    du = np.minimum(u, 1 - u) * tw
    dv = np.minimum(v, 1 - v) * th
    edge = np.minimum(du, dv)
    g = np.clip((grout / 2 - edge) * s + 0.5, 0, 1)
    return {"grout": g.astype(f32), "rnd": rnd.astype(f32), "rnd2": rnd2.astype(f32),
            "u": u.astype(f32), "v": v.astype(f32), "edge": edge.astype(f32), "tw": tw, "th": th}


# --------------------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------------------
def ac_unit(F: Facade, x0, y0, w, h, r: np.random.Generator, body=None, hgt=0.86):
    """Outdoor AC unit seen from the front: ivory casing, round fan grille on the left/right,
    side louvres, base feet. Painted steel (low metallic)."""
    body = rgb("#E7E4DA") if body is None else body
    reg = F.R(x0, y0, x0 + w, y0 + h, radius=min(w, h) * 0.04)
    if reg is None:
        return
    ty = np.clip(F.ly(reg, y0, h) / h, 0, 1)
    shade = (1.02 - 0.08 * ty)[..., None]
    F.put(reg, alb=body * shade, h=hgt, metal=0.25, smooth=0.45, ao=1.0)
    # fan grille
    fan_left = r.random() < 0.5
    fr = h * 0.36
    fcx = x0 + (w * 0.33 if fan_left else w * 0.67)
    fcy = y0 + h * 0.5
    reg2 = F.region(circle(fcx, fcy, fr))
    if reg2 is not None:
        lx = F.lx(reg2, fcx - fr, 2 * fr) - fr
        ly = F.ly(reg2, fcy - fr, 2 * fr) - fr
        d = np.sqrt(lx * lx + ly * ly)
        rings = (np.sin(d / (fr / 6.5) * math.pi * 2) > 0.2).astype(f32)
        spokes = (np.abs(np.sin(np.arctan2(ly, lx) * 2)) < 0.08).astype(f32)
        grille = np.maximum(rings, spokes)
        col = mix(rgb("#2A2C2E"), body * 0.85, 0.0) * (1 - grille[..., None]) + body * 0.78 * grille[..., None]
        F.put(reg2, alb=col, h=hgt - 0.12 + grille * 0.08, metal=0.3, smooth=0.35, ao=0.75)
    # louvres on the other side
    lx0 = x0 + (w * 0.66 if fan_left else w * 0.08)
    lx1 = lx0 + w * 0.26
    n = 9
    for i in range(n):
        yy = y0 + h * (0.18 + 0.66 * i / (n - 1))
        F.put(F.R(lx0, yy - h * 0.012, lx1, yy + h * 0.012), alb=body * 0.72, h=hgt - 0.03, ao=0.85)
    # feet / base shadow
    F.put(F.R(x0 + w * 0.06, y0 + h, x0 + w * 0.16, y0 + h * 1.06), alb=rgb("#55575A"), h=hgt - 0.1, metal=0.5)
    F.put(F.R(x0 + w * 0.84, y0 + h, x0 + w * 0.94, y0 + h * 1.06), alb=rgb("#55575A"), h=hgt - 0.1, metal=0.5)
    # pipe out of the side (insulated, cream tape)
    side = x0 + w if fan_left else x0
    p = skia.Path()
    px = side + (w * 0.05 if fan_left else -w * 0.05)
    p.moveTo(side, y0 + h * 0.75)
    p.cubicTo(px + (w * 0.12 if fan_left else -w * 0.12), y0 + h * 0.75,
              px + (w * 0.12 if fan_left else -w * 0.12), y0 + h * 0.3,
              px + (w * 0.12 if fan_left else -w * 0.12), y0 - h * 0.6)
    reg3 = F.region(p, stroke=h * 0.09, fill=False, cap="butt")
    F.put(reg3, alb=rgb("#DCD6C4"), h=hgt + 0.02, metal=0.0, smooth=0.3)


def pipe_v(F: Facade, xc, y0, y1, radius, color=None, brackets=None, hgt=0.8, metal=0.0, smooth=0.35):
    """Vertical pipe with cylindrical height profile and periodic brackets."""
    color = rgb("#BDB9AE") if color is None else color
    reg = F.R(xc - radius, y0, xc + radius, y1)
    if reg is None:
        return
    t = np.clip(F.lx(reg, xc - radius, 2 * radius) / (2 * radius), 0, 1)
    cyl = np.sqrt(np.clip(1 - (2 * t - 1) ** 2, 0, 1))
    col = color * (0.88 + 0.12 * cyl)[..., None]
    F.put(reg, alb=col, h=hgt - 0.2 + 0.2 * cyl, metal=metal, smooth=smooth)
    F.put(F.R(xc - radius - 6, y0, xc + radius + 6, y1), ao=0.82, opacity=0.5)
    if brackets:
        yb = y0
        while yb < y1:
            F.put(F.R(xc - radius * 1.25, yb - radius * 0.35, xc + radius * 1.25, yb + radius * 0.35),
                  alb=color * 0.8, h=hgt + 0.03, metal=metal)
            yb += brackets


def text_region(F: Facade, text, box, font="noto", mode="contain", align=(0.5, 0.5), vertical=False,
                stretch=(1.0, 1.0), tracking=0.0):
    if vertical:
        p = vtext_path(text, font, 100, 1.0)
    else:
        p = text_path(text, font, 100, tracking)
    p = fit_path(p, box, mode=mode, align=align, stretch=stretch)
    return F.region(p)


def sheen_field(F: Facade, seed=0, strength=1.0, clouds=0.14):
    """Periodic stylised glass reflection: diagonal sheen bands + soft clouds. Scalar (H,W)."""
    S = F.w
    xx, yy = F._xx, F._yy
    r = rng(seed)
    diag = ((xx / F.w) * 2 + (yy / F.h) * 1) % 1.0
    out = np.zeros((F.H, F.W), f32)
    for _ in range(3):
        c = r.uniform(0, 1); w = r.uniform(0.02, 0.07); a = r.uniform(0.05, 0.11)
        d = np.abs(((diag - c) + 0.5) % 1.0 - 0.5)
        out += (np.clip(1 - d / w, 0, 1) ** 2 * a).astype(f32)
    out *= 1.25 * strength
    if clouds:
        out += (F.noise(420, seed + 1, beta=2.2) - 0.5) * clouds
    return out


def ring(F: Facade, x0, y0, x1, y1, t):
    """Region of a rectangular ring of thickness t inside the rect (wrap-aware)."""
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
    p.addRect(skia.Rect.MakeLTRB(x0 + t, y0 + t, x1 - t, y1 - t))
    return F.region(p, evenodd=True)
