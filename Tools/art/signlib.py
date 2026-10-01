"""signlib — helpers for storefront signs, billboards and vending fronts (INK DRIFT: TOKYO).

A `Sign` holds two outputs rendered together at 2x:
  * albedo  — the board as seen in daylight (tubes off, panel unlit, light grime)
  * emission— black background, what glows at night (backlit acrylic, neon tubes, LEDs)

Backlit acrylic: paint panel art with `lit=` (light transmission 0..1); `bake_backlight()` turns the
clean panel colours * transmission into emission.  Neon / LEDs / bulbs add emission directly.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import *  # noqa: F401,F403
from inklib import f32
import cv2
import numpy as np
import skia

SIGN_DIR = os.path.join(ART, "Signs")

WHITE = np.array([1, 1, 1], f32)
STEEL = hexc("#8C9096")
DARK_STEEL = hexc("#3A3D44")
BOARD_BLACK = hexc("#15151B")
WARM_WHITE = hexc("#FFF6E2")
COOL_WHITE = hexc("#F2FBFF")


def col(h):
    return hexc(h) if isinstance(h, str) else np.asarray(h, f32)


# --------------------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------------------
_COVER = {}


def has_glyphs(text, font):
    key = (text, font)
    if key not in _COVER:
        f = skia.Font(typeface(font), 50)
        g = f.textToGlyphs(text.replace(" ", ""))
        _COVER[key] = all(int(x) != 0 for x in g)
    return _COVER[key]


def fb(text, font):
    """Font fallback: Latin-only fonts (bangers/chakra) fall back to Noto for Japanese text."""
    return font if has_glyphs(text, font) else ("noto" if font in ("chakra", "bangers") else "noto_bold")


def T(text, font, box, mode="contain", align=(0.5, 0.5), stretch=(1.0, 1.0), tracking=0.0):
    """Horizontal text fitted into box (x0,y0,x1,y1)."""
    font = fb(text, font)
    return fit_path(text_path(text, font, 200, tracking), box, mode, align, stretch)


def VT(text, font, box, spacing=1.0, mode="contain", align=(0.5, 0.5), stretch=(1.0, 1.0)):
    """Vertical (tategaki) text fitted into box."""
    font = fb(text, font)
    return fit_path(vtext_path(text, font, 200, spacing), box, mode, align, stretch)


def TS(text, font, x, y, size, anchor="c", tracking=0.0):
    """Text at a given font size; anchor l/c/r horizontally, y = baseline."""
    w = text_advance(text, font, size, tracking)
    x0 = {"l": x, "c": x - w / 2, "r": x - w}[anchor]
    return text_path(text, font, size, tracking, x0, y)


def VTS(text, font, x, y, size, spacing=1.0):
    return vtext_path(text, font, size, spacing, x, y)


# --------------------------------------------------------------------------------------
# Sub-region canvas (fast local drawing of small elements; writes go straight to the parent)
# --------------------------------------------------------------------------------------
class SubCanvas(Canvas):
    def __init__(self, parent: Canvas, box):
        ss = parent.ss
        pox, poy = getattr(parent, "ox", 0), getattr(parent, "oy", 0)
        x0, y0, x1, y1 = box
        x0 = max(0, int(math.floor(x0 - pox))); y0 = max(0, int(math.floor(y0 - poy)))
        x1 = min(parent.w, int(math.ceil(x1 - pox))); y1 = min(parent.h, int(math.ceil(y1 - poy)))
        self.lx, self.ly = x0, y0  # offset inside the parent
        self.ox, self.oy = pox + x0, poy + y0
        self.w, self.h, self.ss = x1 - x0, y1 - y0, ss
        self.W, self.H = self.w * ss, self.h * ss
        self.px = parent.px[y0 * ss:y1 * ss, x0 * ss:x1 * ss]

    def _t(self, p):
        q = skia.Path(p)
        q.offset(-self.ox, -self.oy)
        return q

    def mask(self, path, stroke: float = 0.0, fill: bool = True, **kw):
        paths = path if isinstance(path, (list, tuple)) else [path]
        return raster([self._t(p) for p in paths], self.W, self.H, scale=self.ss, stroke=stroke, fill=fill, **kw)

    def ramp(self, p0, p1):
        return super().ramp((p0[0] - self.ox, p0[1] - self.oy), (p1[0] - self.ox, p1[1] - self.oy))

    def radial(self, cx, cy, r):
        return super().radial(cx - self.ox, cy - self.oy, r)

    def vgrad(self, y0, y1, stops):
        return super().vgrad(y0 - self.oy, y1 - self.oy, stops)

    def halftone(self, value, period, angle=45.0, **kw):
        kw.setdefault("offset", (self.ox * self.ss, self.oy * self.ss))
        return super().halftone(value, period, angle, **kw)


# --------------------------------------------------------------------------------------
# Sign
# --------------------------------------------------------------------------------------
class Sign:
    def __init__(self, name: str, w: int, h: int, bg=BOARD_BLACK, ss: int = 2):
        self.name, self.w, self.h, self.ss = name, w, h, ss
        self.A = Canvas(w, h, ss=ss, bg=col(bg))
        self.W, self.H = self.A.W, self.A.H
        self.L = np.zeros((self.H, self.W), f32)
        self.E = np.zeros((self.H, self.W, 3), f32)
        self.r = rng(_h("sign", name))
        self._baked = False

    def sub(self, box):
        """Sign view restricted to box (design px). Same absolute coordinates; much faster for
        small elements. Albedo / transmission / emission writes land in the parent."""
        c = Sign.__new__(Sign)
        c.name, c.ss, c.r = self.name, self.ss, self.r
        c.A = SubCanvas(self.A, box)
        c.w, c.h, c.W, c.H = c.A.w, c.A.h, c.A.W, c.A.H
        y0, x0 = c.A.ly * self.ss, c.A.lx * self.ss
        c.L = self.L[y0:y0 + c.H, x0:x0 + c.W]
        c.E = self.E[y0:y0 + c.H, x0:x0 + c.W]
        c._baked = False
        return c

    # ----- geometry
    def m(self, path, **kw):
        if isinstance(path, np.ndarray):
            return path
        return self.A.mask(path, **kw)

    def fill(self, shape, color, lit=None, opacity=1.0, stroke=0.0):
        m = self.m(shape, stroke=stroke) if not isinstance(shape, np.ndarray) else shape
        self.A.paint(m, col(color) if not isinstance(color, np.ndarray) or color.ndim == 1 else color, opacity)
        if lit is not None:
            a = m * opacity
            self.L *= (1 - a)
            self.L += a * lit
        return m

    def stroke(self, shape, color, width, lit=None, opacity=1.0, join="round"):
        m = self.A.mask(shape, stroke=width, fill=False, join=join)
        return self.fill(m, color, lit, opacity)

    def outlined(self, path, fill, outline, width, lit_fill=None, lit_outline=None, outline2=None,
                 width2=0.0, lit_outline2=None):
        """Text/shape with outer stroke(s): outline2 (outermost) -> outline -> fill."""
        F = self.m(path)
        if outline2 is not None and width2 > 0:
            self.fill(self.A.dilate(F, width + width2), outline2, lit_outline2)
        if outline is not None and width > 0:
            self.fill(self.A.dilate(F, width), outline, lit_outline)
        self.fill(F, fill, lit_fill)
        return F

    def occlude(self, mask):
        """An opaque element drawn on top: kills emission/backlight underneath it."""
        self.E *= (1 - mask)[..., None]
        self.L *= (1 - mask)

    def emit(self, mask, color, k=1.0):
        self.E += mask[..., None] * (col(color) * k)

    def emit_rgb(self, rgb, k=1.0):
        self.E += rgb * k

    # ----- backlight
    def bake_backlight(self, gain=1.0, tubes="v", tube_count=3, warm=0.0, vignette=0.18, sat=1.12):
        """Emission += clean albedo * transmission. Adds fluorescent-tube banding + edge falloff."""
        H, W = self.H, self.W
        rgb = self.A.px[..., :3].copy()
        # boost saturation a touch (light through coloured acrylic is richer than print)
        lum = (rgb * np.array([0.3, 0.59, 0.11], f32)).sum(-1, keepdims=True)
        rgb = np.clip(lum + (rgb - lum) * sat, 0, 1)
        if warm:
            rgb = rgb * mix(WHITE, WARM_WHITE, warm)
        xx = np.linspace(0, 1, W, dtype=f32)[None, :]
        yy = np.linspace(0, 1, H, dtype=f32)[:, None]
        if tubes == "v":
            band = 0.95 + 0.05 * np.cos((xx * tube_count) * 2 * math.pi) ** 2
        elif tubes == "h":
            band = 0.95 + 0.05 * np.cos((yy * tube_count) * 2 * math.pi) ** 2
        else:
            band = np.ones((1, 1), f32)
        L = self.L
        if vignette > 0:
            Lb = blur(L, max(W, H) * 0.012)
            L = L * (1 - vignette + vignette * np.clip(Lb * 1.15, 0, 1))
        self.E += rgb * (L * band * gain)[..., None]
        self._baked = True

    # ----- neon tubes
    def _centerline(self, src, thin=0.7):
        if isinstance(src, np.ndarray):
            return src
        return self.A.mask(src, stroke=thin, fill=False)

    def neon(self, src, color, r=5.0, shadow=0.55, clips=0.0, core=0.85, halo=1.0, glass=None,
             emit=1.0, highlight=0.8, board=True):
        """Neon tube along path centreline (or a thin skeleton mask). r = tube radius (design px)."""
        cl = self._centerline(src)
        d = cv2.distanceTransform((cl < 0.35).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        R = r * self.ss
        body = np.clip(R - d + 0.5, 0, 1).astype(f32)
        prof = np.sqrt(np.clip(1 - (d / R) ** 2, 0, 1)).astype(f32)
        c = col(color)
        # --- albedo: shadow on board, pale glass tube with highlight
        if shadow > 0 and board:
            sh = blur(shift(body, R * 0.5, R * 1.1), R * 0.9)
            self.A.multiply(sh, hexc("#202028"), shadow)
        g = col(glass) if glass is not None else mix(c, hexc("#EEF0EE"), 0.62)
        shade = (0.5 + 0.5 * prof)[..., None]
        self.A.paint(body, g * shade)
        if highlight > 0:
            gy = np.gradient(d, axis=0)
            hl = np.clip(1 - np.abs(d - R * 0.45) / (R * 0.22), 0, 1) * np.clip(-gy * 1.5, 0, 1)
            self.A.paint(hl * body, WHITE, highlight)
        self.L *= (1 - body)
        # --- emission
        if emit > 0:
            hal = np.exp(-np.maximum(d - R, 0) / (R * 2.2)).astype(f32) * 0.42 * halo
            wide = blur(body, R * 5.0) * 0.55 * halo
            cor = np.clip(R * 0.42 - d + 0.5, 0, 1)
            e = c[None, None, :] * (body * 1.05 + hal + wide)[..., None]
            e += mix(c, WHITE, 0.8)[None, None, :] * (cor * core)[..., None]
            self.E += e * emit
        if clips > 0:
            self._tube_clips(cl, R, clips)
        return body

    def _tube_clips(self, cl, R, density):
        ys, xs = np.nonzero(cl > 0.5)
        if len(xs) == 0:
            return
        n = max(2, int(len(xs) / (self.ss * 90) * density))
        idx = self.r.choice(len(xs), size=min(n, len(xs)), replace=False)
        p = skia.Path()
        for i in idx:
            x, y = xs[i] / self.ss, ys[i] / self.ss
            p.addCircle(x + R / self.ss * 0.2, y + R / self.ss * 1.0, R / self.ss * 0.55)
        m = self.A.mask(p)
        self.A.paint(m, hexc("#5A5D66"))
        self.A.paint(self.A.erode(m, 0.8) * 0.6, hexc("#9CA0A8"))

    def neon_text(self, path, color, r=4.5, mode="outline", inset=0.0, **kw):
        """mode 'outline': tube follows glyph contours (inset by `inset`);
        mode 'skeleton': single tube along the glyph medial axis (handwritten neon look)."""
        if mode == "skeleton":
            sk = self.skeleton(path)
            return self.neon(sk, color, r=r, **kw)
        if inset:
            F = self.A.mask(path)
            F = self.A.erode(F, inset)
            edge = (F > 0.5).astype(np.uint8)
            cl = (cv2.morphologyEx(edge, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0).astype(f32)
            return self.neon(cl, color, r=r, **kw)
        return self.neon(path, color, r=r, **kw)

    def skeleton(self, path, smooth=1.5):
        from skimage.morphology import skeletonize
        F = self.A.mask(path) if not isinstance(path, np.ndarray) else path
        if smooth:
            F = blur(F, smooth * self.ss)
        sk = skeletonize(F > 0.5)
        sk = prune_spurs(sk, int(9 * self.ss))
        return sk.astype(f32)

    # ----- LEDs / bulbs
    def led_matrix(self, text_path_or_mask, box, color, pitch=10.0, dot=0.36, off_col=hexc("#26262C"),
                   on_albedo=None, glow=1.0, threshold=0.42):
        """Dot-matrix LED: dots in box; dots that fall inside text are lit."""
        x0, y0, x1, y1 = box
        nx = int((x1 - x0) / pitch); ny = int((y1 - y0) / pitch)
        F = self.m(text_path_or_mask)
        on_on = []
        off = skia.Path(); on = skia.Path()
        ss = self.ss
        for j in range(ny):
            for i in range(nx):
                cx = x0 + (i + 0.5) * pitch; cy = y0 + (j + 0.5) * pitch
                xi0, yi0 = int((cx - pitch * 0.5) * ss), int((cy - pitch * 0.5) * ss)
                cell = F[max(yi0, 0):yi0 + int(pitch * ss), max(xi0, 0):xi0 + int(pitch * ss)]
                v = cell.mean() if cell.size else 0
                (on if v > threshold else off).addCircle(cx, cy, pitch * dot)
        mo = self.A.mask(off); mn = self.A.mask(on)
        c = col(color)
        self.A.paint(mo, off_col)
        self.A.paint(mn, col(on_albedo) if on_albedo is not None else mix(c, hexc("#303034"), 0.55))
        self.A.paint(self.A.erode(mn, pitch * 0.12) * 0.35, WHITE)
        self.L *= (1 - mo) * (1 - mn)
        self.emit(mn, mix(c, WHITE, 0.15), 1.1)
        self.emit(blur(mn, pitch * ss * 0.6), c, 0.55 * glow)
        return mn

    def bulbs(self, pts, rad, color=hexc("#FFD27A"), on=None, glow=1.0):
        p = skia.Path()
        for (x, y) in pts:
            p.addCircle(x, y, rad)
        m = self.A.mask(p)
        sock = self.A.dilate(m, rad * 0.35)
        self.A.paint(sock, hexc("#2C2A2E"))
        self.A.paint(m, hexc("#F3EEDC"))
        hl = skia.Path()
        for (x, y) in pts:
            hl.addCircle(x - rad * 0.3, y - rad * 0.3, rad * 0.32)
        self.A.paint(self.A.mask(hl), WHITE, 0.9)
        self.L *= (1 - sock)
        c = col(color)
        self.emit(m, mix(c, WHITE, 0.5), 1.0)
        self.emit(blur(m, rad * self.ss * 1.6), c, 0.9 * glow)
        return m

    # ----- hardware
    def frame(self, x0, y0, x1, y1, width, color=STEEL, bolts=0, bolt_r=None, radius=0.0, bevel=0.5):
        """Metal frame ring (outside of inner rect), opaque. Bevel = lit top-left, dark bottom-right."""
        outer = self.A.mask(rect(x0, y0, x1, y1, radius))
        inner = self.A.mask(rect(x0 + width, y0 + width, x1 - width, y1 - width, max(0, radius - width)))
        ring = outer * (1 - inner)
        c = col(color)
        self.fill(ring, c, lit=0.0)
        if bevel:
            hi = outer * (1 - self.A.shift(outer, width * 0.25, width * 0.25))
            lo = outer * (1 - self.A.shift(outer, -width * 0.25, -width * 0.25))
            self.A.paint(hi * ring, mix(c, WHITE, 0.45), bevel)
            self.A.paint(lo * ring, darken(c, 0.5), bevel)
            ihi = inner * (1 - self.A.shift(inner, -width * 0.18, -width * 0.18))  # inner lip (shadow side)
            self.A.paint(self.A.dilate(ihi, 1) * ring, darken(c, 0.6), bevel * 0.8)
        if bolts:
            br = bolt_r or width * 0.22
            pts = []
            for (px, py) in [(x0 + width / 2, y0 + width / 2), (x1 - width / 2, y0 + width / 2),
                             (x0 + width / 2, y1 - width / 2), (x1 - width / 2, y1 - width / 2)]:
                pts.append((px, py))
            if bolts > 4:
                k = (bolts - 4) // 2
                for i in range(1, k + 1):
                    t = i / (k + 1)
                    if (x1 - x0) >= (y1 - y0):
                        pts += [(x0 + (x1 - x0) * t, y0 + width / 2), (x0 + (x1 - x0) * t, y1 - width / 2)]
                    else:
                        pts += [(x0 + width / 2, y0 + (y1 - y0) * t), (x1 - width / 2, y0 + (y1 - y0) * t)]
            self.bolts(pts, br)
        return ring

    def bolts(self, pts, br, rust=0.5):
        p = skia.Path(); h = skia.Path()
        for (x, y) in pts:
            p.addCircle(x, y, br)
            h.addCircle(x - br * 0.25, y - br * 0.25, br * 0.45)
        m = self.A.mask(p)
        # rust streak below each bolt
        if rust:
            st = skia.Path()
            for (x, y) in pts:
                L = br * self.r.uniform(6, 16)
                st.addPath(poly([(x - br * 0.6, y), (x + br * 0.6, y), (x + br * 0.25, y + L), (x - br * 0.25, y + L)]))
            sm = self.A.blur(self.A.mask(st), br * 0.5)
            self.A.multiply(sm, hexc("#8A5A3A"), rust * 0.55)
        self.A.paint(self.A.dilate(m, br * 0.25), hexc("#2A2A30"), 0.8)
        self.A.paint(m, hexc("#9A9EA6"))
        self.A.paint(self.A.mask(h), hexc("#D8DCE2"), 0.8)
        self.L *= (1 - m)

    # ----- weathering
    def weather(self, amount=1.0, streak=1.0, dust=1.0, fade=0.03, seed=0, top_band=None):
        """Subtle rain-run grime: sparse thin streaks hanging from the top edge / ledges, blotchy
        low-frequency dirt, dust specks, darker edges. Albedo only."""
        H, W = self.H, self.W
        s = self.ss
        r = rng(_h(self.name, seed, "w"))
        yy = np.linspace(0, 1, H, dtype=f32)[:, None]
        xx = np.linspace(0, 1, W, dtype=f32)[None, :]
        # sparse streak columns: 1D noise across x thresholded, modulated along y
        cols = noise(1, W, 6 * s, seed=_h(self.name, seed, 1), beta=1.2)[0]
        cols = np.clip((cols - 0.64) * 4.0, 0, 1)
        ymod = noise(H, W, 60 * s, seed=_h(self.name, seed, 2), beta=1.8, aniso=(1.0, 10.0))
        y0 = (top_band or 0) / self.h
        fall = np.clip(1 - (yy - y0) / (0.25 + 0.35 * ymod), 0, 1) * (yy >= y0)
        streaks = cols[None, :] * fall * np.clip(ymod * 1.6 - 0.2, 0, 1)
        streaks = blur(streaks.astype(f32), 0.8 * s)
        blot = noise(H, W, 160 * s, seed=_h(self.name, seed, 3), beta=2.2)
        grime = (streaks * 0.22 * streak + np.clip(blot - 0.45, 0, 1) * 0.16) * amount
        self.A.multiply(grime.astype(f32), hexc("#4E463C"), 1.0)
        # bottom accumulation
        bottom = np.clip((yy - 0.82) / 0.18, 0, 1) ** 2 * (0.5 + 0.5 * blot)
        self.A.multiply(np.broadcast_to(bottom, (H, W)).astype(f32) * amount, hexc("#6A5F50"), 0.25)
        if dust:
            sp = noise(H, W, 1.2 * s, seed=_h(self.name, seed, 4), beta=0.5)
            specks = np.clip((sp - 0.8) * 6, 0, 1) * dust * amount
            self.A.multiply(specks, hexc("#6E6656"), 0.35)
        if fade:
            self.A.paint(np.full((H, W), 1.0, f32) * blot, hexc("#D9D2C3"), fade * amount)
        edge = np.clip(1 - np.minimum(np.minimum(xx, 1 - xx) * W, np.minimum(yy, 1 - yy) * H) / (14 * s), 0, 1)
        self.A.multiply(edge * amount, hexc("#4A443C"), 0.4)

    # ----- output
    def emission_final(self):
        e = self.E
        mx = e.max(-1, keepdims=True)
        excess = np.clip(mx - 1, 0, None)
        e = e / np.maximum(mx, 1.0)
        e = e + (1 - e) * np.clip(excess * 0.6, 0, 1)
        e = cv2.resize(e, (self.w, self.h), interpolation=cv2.INTER_AREA)
        return np.clip(e, 0, 1)

    def save(self, outdir=SIGN_DIR, prefix=""):
        os.makedirs(outdir, exist_ok=True)
        a = self.A.final()[..., :3]
        pa = os.path.join(outdir, f"{prefix}{self.name}_albedo.png")
        pe = os.path.join(outdir, f"{prefix}{self.name}_emission.png")
        save_image(a, pa, "RGB")
        save_image(self.emission_final(), pe, "RGB")
        return pa, pe


def _h(*parts):
    """Stable (process-independent) hash for seeding."""
    import zlib
    return zlib.crc32(repr(parts).encode()) & 0x7FFFFFFF


def prune_spurs(sk: np.ndarray, length: int) -> np.ndarray:
    """Remove skeleton branches shorter than `length` px that end in a free endpoint."""
    sk = sk.astype(bool).copy()
    H, W = sk.shape
    k = np.ones((3, 3), np.uint8)

    def nbrs(img):
        return cv2.filter2D(img.astype(np.uint8), -1, k, borderType=cv2.BORDER_CONSTANT) - img.astype(np.uint8)

    nb = nbrs(sk)
    ends = np.argwhere(sk & (nb == 1))
    junction = sk & (nb >= 3)
    for (y, x) in ends:
        path = [(y, x)]
        visited = {(y, x)}
        cy, cx = y, x
        ok = False
        for _ in range(length):
            nxt = None
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < H and 0 <= xx < W and sk[yy, xx] and (yy, xx) not in visited:
                        if junction[yy, xx]:
                            ok = True
                        nxt = (yy, xx)
            if ok or nxt is None:
                break
            visited.add(nxt)
            path.append(nxt)
            cy, cx = nxt
        if ok and len(path) < length:
            for (py, px) in path:
                sk[py, px] = False
    return sk


# --------------------------------------------------------------------------------------
# Pictograms — functions return skia paths fitted into box=(x0,y0,x1,y1)
# Each is designed in a 100x100 unit square.
# --------------------------------------------------------------------------------------
def _fit(p, box, align=(0.5, 0.5)):
    return fit_path(p, box, "contain", align)


def picto_bowl(box, steam=True):
    p = skia.Path()
    bowl = skia.Path()
    bowl.moveTo(8, 52); bowl.lineTo(92, 52)
    bowl.cubicTo(90, 75, 72, 86, 50, 86); bowl.cubicTo(28, 86, 10, 75, 8, 52); bowl.close()
    p.addPath(bowl)
    p.addPath(rect(36, 86, 64, 93, 2))
    # chopsticks
    p.addPath(poly([(58, 46), (96, 14), (98, 17), (61, 48)]))
    p.addPath(poly([(64, 48), (99, 24), (100, 27), (67, 50)]))
    if steam:
        for x in (28, 42):
            s = smooth_open([(x, 44), (x - 5, 36), (x + 4, 28), (x - 3, 19), (x + 3, 10)])
            sp = skia.Path(); sp.addPath(s)
            p.addPath(stroke_path(sp, 4.2))
    return _fit(p, box)


def stroke_path(p, w, cap="round"):
    """Convert a stroked path into a fill path (skia fillPath)."""
    paint = skia.Paint(Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                       StrokeCap=skia.Paint.kRound_Cap if cap == "round" else skia.Paint.kButt_Cap,
                       StrokeJoin=skia.Paint.kRound_Join)
    out = skia.Path()
    paint.getFillPath(p, out)
    return out


def picto_mug(box):
    p = skia.Path()
    p.addPath(rect(18, 30, 70, 94, 6))
    ring = skia.Path(); ring.addRoundRect(skia.Rect.MakeLTRB(60, 42, 92, 80), 14, 14)
    p.addPath(stroke_path(ring, 8))
    for (x, y, r_) in [(22, 28, 12), (36, 22, 14), (52, 24, 13), (64, 30, 10), (30, 34, 9)]:
        p.addCircle(x, y, r_)
    return _fit(p, box)


def picto_mic(box):
    p = skia.Path()
    p.addCircle(50, 26, 20)
    p.addPath(poly([(38, 44), (62, 44), (56, 96), (44, 96)]))
    return _fit(p, box)


def picto_mic_grille(box):
    """grille lines to subtract/overlay on picto_mic (same box)."""
    p = skia.Path()
    for i in range(-3, 4):
        p.addPath(rect(33, 26 + i * 5 - 0.9, 67, 26 + i * 5 + 0.9))
    q = skia.Path(); q.addPath(p)
    full = skia.Path(); full.addRect(0, 0, 100, 100)
    mic = skia.Path(); mic.addCircle(50, 26, 20)
    q = skia.Op(q, mic, skia.PathOp.kIntersect_PathOp)
    # ensure same fitting frame as picto_mic by adding invisible extremes
    ref = skia.Path(); ref.addPath(mic); ref.addPath(poly([(38, 44), (62, 44), (56, 96), (44, 96)]))
    l, t, r_, b = bounds(ref)
    x0, y0, x1, y1 = box
    s = min((x1 - x0) / (r_ - l), (y1 - y0) / (b - t))
    m = skia.Matrix(); m.setTranslate(-l, -t); m.postScale(s, s)
    m.postTranslate(x0 + (x1 - x0 - (r_ - l) * s) / 2, y0 + (y1 - y0 - (b - t) * s) / 2)
    q.transform(m)
    return q


def picto_cup(box):
    p = skia.Path()
    cup = skia.Path()
    cup.moveTo(16, 44); cup.lineTo(74, 44); cup.cubicTo(74, 72, 64, 84, 45, 84); cup.cubicTo(26, 84, 16, 72, 16, 44)
    cup.close()
    p.addPath(cup)
    ring = skia.Path(); ring.addOval(skia.Rect.MakeLTRB(64, 50, 90, 70))
    p.addPath(stroke_path(ring, 7))
    p.addPath(ellipse(46, 90, 40, 6))
    for x in (34, 50):
        p.addPath(stroke_path(smooth_open([(x, 38), (x - 5, 30), (x + 4, 22), (x - 2, 12)]), 4.5))
    return _fit(p, box)


def picto_star(box, n=5, inner=0.45, rot=-90):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + 180 * i / n)
        rr = 50 if i % 2 == 0 else 50 * inner
        pts.append((50 + math.cos(a) * rr, 50 + math.sin(a) * rr))
    return _fit(poly(pts), box)


def picto_moon(box):
    a = circle(50, 50, 45)
    b = circle(68, 38, 38)
    return _fit(skia.Op(a, b, skia.PathOp.kDifference_PathOp), box)


def picto_flame(box):
    p = skia.Path()
    p.moveTo(50, 98)
    p.cubicTo(18, 98, 6, 72, 18, 50)
    p.cubicTo(24, 62, 30, 64, 34, 60)
    p.cubicTo(26, 36, 40, 14, 56, 2)
    p.cubicTo(54, 22, 70, 30, 74, 46)
    p.cubicTo(78, 40, 80, 34, 80, 28)
    p.cubicTo(96, 48, 96, 98, 50, 98)
    p.close()
    return _fit(p, box)


def picto_flame_inner(box):
    """inner flame tongue aligned to picto_flame's box."""
    outer = skia.Path()
    outer.moveTo(50, 98); outer.cubicTo(18, 98, 6, 72, 18, 50); outer.cubicTo(24, 62, 30, 64, 34, 60)
    outer.cubicTo(26, 36, 40, 14, 56, 2); outer.cubicTo(54, 22, 70, 30, 74, 46); outer.cubicTo(78, 40, 80, 34, 80, 28)
    outer.cubicTo(96, 48, 96, 98, 50, 98); outer.close()
    inner = skia.Path()
    inner.moveTo(50, 94); inner.cubicTo(32, 94, 26, 78, 34, 66); inner.cubicTo(38, 72, 42, 72, 44, 70)
    inner.cubicTo(42, 56, 50, 44, 58, 36); inner.cubicTo(58, 50, 74, 60, 70, 80); inner.cubicTo(68, 90, 60, 94, 50, 94)
    inner.close()
    l, t, r_, b = bounds(outer)
    x0, y0, x1, y1 = box
    s = min((x1 - x0) / (r_ - l), (y1 - y0) / (b - t))
    m = skia.Matrix(); m.setTranslate(-l, -t); m.postScale(s, s)
    m.postTranslate(x0 + (x1 - x0 - (r_ - l) * s) / 2, y0 + (y1 - y0 - (b - t) * s) / 2)
    inner.transform(m)
    return inner


def picto_butterfly(box):
    p = skia.Path()
    for sgn in (-1, 1):
        w1 = smooth_closed([(50, 48), (50 + sgn * 18, 14), (50 + sgn * 46, 8), (50 + sgn * 44, 34), (50 + sgn * 22, 50)], 0.7)
        w2 = smooth_closed([(50, 54), (50 + sgn * 30, 56), (50 + sgn * 38, 80), (50 + sgn * 20, 92), (50 + sgn * 6, 74)], 0.7)
        p.addPath(w1); p.addPath(w2)
        p.addPath(stroke_path(smooth_open([(50, 40), (50 + sgn * 8, 20), (50 + sgn * 16, 6)]), 2.4))
    p.addPath(ellipse(50, 56, 4, 22))
    return _fit(p, box)


def picto_tooth(box):
    p = skia.Path()
    p.moveTo(50, 20)
    p.cubicTo(64, 8, 90, 10, 88, 36)
    p.cubicTo(86, 56, 78, 62, 76, 80)
    p.cubicTo(74, 96, 62, 98, 60, 84)
    p.cubicTo(58, 70, 56, 62, 50, 62)
    p.cubicTo(44, 62, 42, 70, 40, 84)
    p.cubicTo(38, 98, 26, 96, 24, 80)
    p.cubicTo(22, 62, 14, 56, 12, 36)
    p.cubicTo(10, 10, 36, 8, 50, 20)
    p.close()
    return _fit(p, box)


def picto_dice(box):
    """isometric die outline faces: returns (top, left, right, pips)"""
    top = poly([(50, 6), (92, 28), (50, 50), (8, 28)])
    left = poly([(8, 28), (50, 50), (50, 96), (8, 74)])
    right = poly([(50, 50), (92, 28), (92, 74), (50, 96)])
    pips = skia.Path()
    pips.addOval(skia.Rect.MakeLTRB(42, 23, 58, 33))
    for (x, y) in [(20, 46), (38, 74)]:
        pips.addOval(skia.Rect.MakeLTRB(x - 5, y - 6, x + 5, y + 6))
    for (x, y) in [(62, 50), (71, 62), (80, 74), (62, 70), (80, 54)]:
        pass
    for (x, y) in [(62, 52), (80, 72), (71, 62)]:
        pips.addOval(skia.Rect.MakeLTRB(x - 5, y - 6, x + 5, y + 6))
    allp = skia.Path(); allp.addPath(top); allp.addPath(left); allp.addPath(right)
    l, t, r_, b = bounds(allp)
    x0, y0, x1, y1 = box
    s = min((x1 - x0) / (r_ - l), (y1 - y0) / (b - t))
    m = skia.Matrix(); m.setTranslate(-l, -t); m.postScale(s, s)
    m.postTranslate(x0 + (x1 - x0 - (r_ - l) * s) / 2, y0 + (y1 - y0 - (b - t) * s) / 2)
    out = []
    for q in (top, left, right, pips):
        q = skia.Path(q); q.transform(m); out.append(q)
    return out


def picto_fish(box):
    p = skia.Path()
    p.moveTo(6, 50)
    p.cubicTo(24, 22, 60, 20, 78, 46)
    p.lineTo(96, 26); p.lineTo(90, 50); p.lineTo(96, 74); p.lineTo(78, 54)
    p.cubicTo(60, 80, 24, 78, 6, 50)
    p.close()
    eye = circle(22, 46, 4)
    return _fit(skia.Op(p, eye, skia.PathOp.kDifference_PathOp), box)


def picto_house(box):
    p = poly([(50, 6), (96, 46), (84, 46), (84, 94), (16, 94), (16, 46), (4, 46)])
    door = rect(42, 64, 58, 94)
    win = rect(26, 54, 38, 66)
    q = skia.Op(p, door, skia.PathOp.kDifference_PathOp)
    q = skia.Op(q, win, skia.PathOp.kDifference_PathOp)
    return _fit(q, box)


def picto_capsule(box, angle=-35):
    p = rect(10, 36, 90, 64, 14)
    m = skia.Matrix(); m.setRotate(angle, 50, 50); p.transform(m)
    return _fit(p, box)


def picto_cocktail(box):
    p = skia.Path()
    p.addPath(poly([(10, 12), (90, 12), (52, 52), (48, 52)]))
    p.addPath(rect(47, 50, 53, 86))
    p.addPath(ellipse(50, 88, 24, 5))
    p.addPath(stroke_path(poly([(62, 4), (40, 34)], close=False), 3))
    p.addCircle(40, 34, 6)
    return _fit(p, box)


def picto_skewer(box):
    p = skia.Path()
    p.addPath(stroke_path(poly([(10, 92), (92, 10)], close=False), 3.2))
    for i, t in enumerate((0.3, 0.48, 0.66)):
        x = 10 + 82 * t; y = 92 - 82 * t
        p.addPath(transformed(rect(x - 11, y - 9, x + 11, y + 9, 6), rotate=-45, pivot=(x, y)))
    return _fit(p, box)


def picto_onsen(box):
    p = skia.Path()
    bowl = skia.Path()
    bowl.addArc(skia.Rect.MakeLTRB(8, 44, 92, 98), -20, 220)
    p.addPath(stroke_path(bowl, 9))
    for x in (30, 50, 70):
        s = smooth_open([(x, 66), (x - 7, 54), (x + 6, 40), (x - 6, 26), (x + 4, 10)])
        p.addPath(stroke_path(s, 8))
    return _fit(p, box)


def picto_gamepad(box):
    p = skia.Path()
    body = smooth_closed([(20, 30), (80, 30), (96, 70), (84, 84), (66, 66), (34, 66), (16, 84), (4, 70)], 0.6)
    hole = skia.Path()
    hole.addPath(rect(20, 44, 38, 50)); hole.addPath(rect(26, 38, 32, 56))
    hole.addCircle(68, 42, 4); hole.addCircle(76, 50, 4); hole.addCircle(60, 50, 4); hole.addCircle(68, 58, 4)
    return _fit(skia.Op(body, hole, skia.PathOp.kDifference_PathOp), box)


def picto_book(box):
    p = skia.Path()
    p.addPath(poly([(4, 20), (46, 14), (50, 20), (50, 90), (46, 84), (4, 90)]))
    p.addPath(poly([(96, 20), (54, 14), (50, 20), (50, 90), (54, 84), (96, 90)]))
    return _fit(p, box)


def picto_bubbles(box):
    p = skia.Path()
    for (x, y, r_) in [(30, 60, 24), (66, 40, 18), (70, 78, 12), (40, 22, 10), (88, 62, 7)]:
        c = skia.Path(); c.addCircle(x, y, r_)
        p.addPath(stroke_path(c, 4.5))
        p.addPath(stroke_path(smooth_open([(x - r_ * 0.55, y - r_ * 0.1), (x - r_ * 0.4, y - r_ * 0.45), (x - r_ * 0.05, y - r_ * 0.6)]), 3))
    return _fit(p, box)


def picto_arrow(box, direction="right"):
    p = poly([(0, 35), (60, 35), (60, 10), (100, 50), (60, 90), (60, 65), (0, 65)])
    rot = {"right": 0, "down": 90, "left": 180, "up": 270}[direction]
    m = skia.Matrix(); m.setRotate(rot, 50, 50); p.transform(m)
    return _fit(p, box)


def picto_lightning(box):
    p = poly([(58, 0), (14, 56), (44, 56), (30, 100), (86, 38), (54, 38), (72, 0)])
    return _fit(p, box)


def picto_crown(box):
    p = poly([(6, 30), (28, 56), (50, 14), (72, 56), (94, 30), (84, 84), (16, 84)])
    p.addCircle(6, 26, 7); p.addCircle(50, 10, 7); p.addCircle(94, 26, 7)
    return _fit(p, box)


def picto_note(box):
    p = skia.Path()
    p.addPath(ellipse(28, 80, 16, 12)); p.addPath(ellipse(76, 70, 16, 12))
    p.addPath(rect(40, 16, 46, 80)); p.addPath(rect(88, 6, 94, 70))
    p.addPath(poly([(40, 16), (94, 6), (94, 20), (40, 30)]))
    return _fit(p, box)


def picto_mahjong(box):
    return _fit(rect(10, 2, 90, 98, 12), box)


def picto_hand(box):
    """simple open palm (massage)"""
    p = skia.Path()
    p.addPath(rect(26, 46, 78, 96, 18))
    for (x, top, w) in [(30, 16, 11), (43, 6, 11), (56, 8, 11), (69, 18, 10)]:
        p.addPath(rect(x - w / 2 + 2, top, x + w / 2 + 2, 60, w / 2))
    p.addPath(transformed(rect(8, 40, 22, 80, 7), rotate=-35, pivot=(18, 70)))
    return _fit(p, box)


def picto_leaf(box):
    p = skia.Path()
    p.moveTo(10, 90); p.cubicTo(10, 40, 40, 10, 92, 8); p.cubicTo(90, 60, 60, 92, 10, 90); p.close()
    vein = stroke_path(smooth_open([(14, 86), (50, 50), (84, 16)]), 3.5)
    return _fit(skia.Op(p, vein, skia.PathOp.kDifference_PathOp), box)


def seigaiha_paint(sign, box, r_, bg, fg, clip=None, lit=1.0, rings=(1.0, 0.76, 0.52, 0.28), ring_w=0.11):
    """Proper overlapping seigaiha: row by row, each scale = bg disk then concentric fg rings."""
    x0, y0, x1, y1 = box
    rows = int((y1 - y0) / (r_ * 0.5)) + 3
    cols = int((x1 - x0) / (r_ * 2)) + 2
    for j in range(rows):
        disks = skia.Path(); ring = skia.Path()
        cy = y0 + (j - 1) * r_ * 0.5
        for i in range(-1, cols + 1):
            cx = x0 + i * r_ * 2 + (r_ if j % 2 else 0)
            disks.addCircle(cx, cy, r_)
            for k in rings:
                c = skia.Path(); c.addCircle(cx, cy, r_ * k - r_ * ring_w * 0.5)
                ring.addPath(stroke_path(c, r_ * ring_w))
        dm = sign.m(disks); rm = sign.m(ring)
        if clip is not None:
            dm = dm * clip; rm = rm * clip
        sign.fill(dm, bg, lit)
        sign.fill(rm * dm, fg, lit)


def seigaiha(box, r_, rows, cols):
    """Seigaiha wave pattern as list of concentric arc ring paths covering box."""
    x0, y0, x1, y1 = box
    p = skia.Path()
    for j in range(rows):
        for i in range(cols + 1):
            cx = x0 + i * r_ * 2 + (r_ if j % 2 else 0)
            cy = y0 + j * r_ * 0.5 + r_
            for k, rr in enumerate((r_, r_ * 0.78, r_ * 0.56, r_ * 0.34)):
                c = skia.Path(); c.addCircle(cx, cy, rr)
                p.addPath(stroke_path(c, r_ * 0.1))
    return p


# --------------------------------------------------------------------------------------
# misc fills
# --------------------------------------------------------------------------------------
def brushed_metal(sign: Sign, mask, base=STEEL, seed=0, horizontal=True, amount=0.12):
    n = noise(sign.H, sign.W, 3 * sign.ss, seed=seed, beta=1.0, aniso=(1.0, 0.02) if horizontal else (0.02, 1.0))
    rgb = base[None, None, :] * (1 - amount + amount * 2 * n)[..., None]
    sign.A.paint(mask, rgb)


def wood(sign: Sign, mask, base=hexc("#7A4A2A"), seed=0, vertical=True, ring=0.25):
    """Wood planks: warped growth-ring stripes + fine fibres along the grain."""
    H, W = sign.H, sign.W
    s = sign.ss
    long_ = (1.0, 10.0) if vertical else (10.0, 1.0)
    nw = noise(H, W, 90 * s, seed=seed, beta=2.0, aniso=long_)
    fib = noise(H, W, 2.5 * s, seed=seed + 1, beta=1.0, aniso=(1.0, 40.0) if vertical else (40.0, 1.0))
    blot = noise(H, W, 200 * s, seed=seed + 2, beta=2.2)
    xx = np.arange(W, dtype=f32)[None, :] if vertical else np.arange(H, dtype=f32)[:, None]
    rings = 0.5 + 0.5 * np.sin(2 * math.pi * (xx / (26 * s) + nw * 4.0))
    k = 0.8 + 0.16 * rings ** 3 - 0.1 * (1 - rings) ** 6 + 0.16 * (fib - 0.5) + ring * 0.3 * (blot - 0.5)
    sign.A.paint(mask, np.clip(base[None, None, :] * k[..., None], 0, 1))


def acrylic_gloss(sign: Sign, box, strength=0.08):
    """subtle diagonal sheen on acrylic panels (albedo only)."""
    x0, y0, x1, y1 = box
    m = sign.A.mask(rect(x0, y0, x1, y1))
    rr = sign.A.ramp((x0, y0), (x1, y1))
    band = np.clip(1 - np.abs(rr - 0.32) / 0.12, 0, 1) * 0.6 + np.clip(1 - np.abs(rr - 0.45) / 0.03, 0, 1) * 0.4
    sign.A.paint(m * band, WHITE, strength)


def grad_fill(sign: Sign, shape, y0, y1, stops, lit=None, x_dir=False):
    m = sign.m(shape)
    if x_dir:
        t = sign.A.ramp((y0, 0), (y1, 0))
        g = gradient_map(t, stops)
    else:
        g = sign.A.vgrad(y0, y1, stops)
    sign.A.paint(m, g)
    if lit is not None:
        sign.L = sign.L * (1 - m) + m * lit
    return m


def halftone_fill(sign: Sign, mask, color, period, value, angle=45, opacity=1.0, lit=None):
    ht = sign.A.halftone(value, period, angle)
    sign.fill(mask * ht, color, lit, opacity)
