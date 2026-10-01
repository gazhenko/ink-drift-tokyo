"""inklib — shared 2D art toolkit for INK DRIFT: TOKYO generators.

Design units = final output pixels. A Canvas renders internally at `ss`x (default 2) and
box-downsamples on save, so every edge is anti-aliased. Geometry is built as skia Paths
(true AA vector rasterisation) and turned into float32 coverage masks; compositing is done
in numpy with premultiplied float RGBA.

Conventions
-----------
* colours are float32 RGB arrays in 0..1 (sRGB), get them with `C('magenta')` or `hexc('#..')`
* masks are float32 HxW arrays in 0..1 at the canvas' INTERNAL resolution
* all generator randomness must come from `rng(seed)` so outputs are deterministic

Do not add category-specific code here; put it in the category script.
"""
from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

import cv2
import numpy as np
import skia
from PIL import Image, ImageDraw, ImageFont

f32 = np.float32

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
TOOLS_ART = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TOOLS_ART, "..", ".."))
ART = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art")
FONTS = os.path.join(ART, "Fonts")
PREVIEWS = os.path.join(TOOLS_ART, "previews")


def out_path(*parts: str) -> str:
    p = os.path.join(ART, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# --------------------------------------------------------------------------------------
# Palette (Docs/DESIGN.md)
# --------------------------------------------------------------------------------------
PALETTE = {
    "ink": "#0B0B12",
    "paper": "#FFF8E7",
    "magenta": "#FF2D7A",
    "cyan": "#00E5FF",
    "yellow": "#FFE600",
    "red": "#FF3B30",
    "indigo": "#1B1340",
    "sakura": "#FFB7D5",
    "lime": "#B6FF3B",
    "white": "#FFFFFF",
    "black": "#000000",
}


def hexc(h: str) -> np.ndarray:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=f32)


def C(name: str) -> np.ndarray:
    """Palette colour by token name (or a '#rrggbb' literal)."""
    if name.startswith("#"):
        return hexc(name)
    return hexc(PALETTE[name])


def mix(a, b, t: float) -> np.ndarray:
    a = np.asarray(a, f32); b = np.asarray(b, f32)
    return (a + (b - a) * t).astype(f32)


def darken(c, k: float) -> np.ndarray:
    """Multiply toward ink-ish dark while keeping saturation (k=0 unchanged, 1 = ink)."""
    c = np.asarray(c, f32)
    return mix(c * (1 - 0.35 * k), C("ink"), k * 0.75)


def lighten(c, k: float) -> np.ndarray:
    return mix(c, C("paper"), k)


def hsv_shift(c, dh=0.0, ds=0.0, dv=0.0) -> np.ndarray:
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[float(x) for x in c])
    h = (h + dh) % 1.0
    s = min(1, max(0, s + ds)); v = min(1, max(0, v + dv))
    return np.array(colorsys.hsv_to_rgb(h, s, v), f32)


# --------------------------------------------------------------------------------------
# RNG
# --------------------------------------------------------------------------------------
def rng(seed) -> np.random.Generator:
    """Seeded generator. NOTE: string seeds are folded to 32 bits from their little-endian bytes,
    so only the first 4 characters matter (kept as-is so existing outputs stay reproducible;
    use a CRC of the full name if you need distinct streams for names sharing a prefix)."""
    if isinstance(seed, str):
        seed = int.from_bytes(seed.encode("utf8"), "little") % (2**32)
    return np.random.default_rng(seed)


# --------------------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------------------
FONT_FILES = {
    "dela": "DelaGothicOne-Regular.ttf",
    "rampart": "RampartOne-Regular.ttf",
    "reggae": "ReggaeOne-Regular.ttf",
    "bangers": "Bangers-Regular.ttf",
    "chakra": "ChakraPetch-Bold.ttf",
    "chakra_reg": "ChakraPetch-Regular.ttf",
    "noto": "NotoSansJP-Black.ttf",
    "noto_bold": "NotoSansJP-Bold.ttf",
}
_TF_CACHE: dict = {}


def typeface(name: str) -> skia.Typeface:
    if name not in _TF_CACHE:
        fn = FONT_FILES.get(name, name)
        _TF_CACHE[name] = skia.Typeface.MakeFromFile(os.path.join(FONTS, fn))
    return _TF_CACHE[name]


def pil_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, FONT_FILES.get(name, name)), size)


def _font(name, size):
    f = skia.Font(typeface(name), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_path(text: str, font: str = "dela", size: float = 100, tracking: float = 0.0,
              x: float = 0, y: float = 0) -> skia.Path:
    """Horizontal text as a path; baseline at y, starting at x. tracking in em units."""
    f = _font(font, size)
    glyphs = f.textToGlyphs(text)
    widths = f.getWidths(glyphs)
    path = skia.Path()
    cx = x
    for g, w in zip(glyphs, widths):
        gp = f.getPath(g)
        if gp is not None:
            gp.offset(cx, y)
            path.addPath(gp)
        cx += w + tracking * size
    return path


def text_advance(text: str, font: str = "dela", size: float = 100, tracking: float = 0.0) -> float:
    f = _font(font, size)
    glyphs = f.textToGlyphs(text)
    ws = f.getWidths(glyphs)
    return float(sum(ws) + tracking * size * max(0, len(ws) - 1))


def glyph_paths(text: str, font: str = "dela", size: float = 100, tracking: float = 0.0):
    """List of (char, path at origin-baseline, x_advance_pos, width) for per-glyph styling."""
    f = _font(font, size)
    glyphs = f.textToGlyphs(text)
    widths = f.getWidths(glyphs)
    out = []
    cx = 0.0
    for ch, g, w in zip(text, glyphs, widths):
        gp = f.getPath(g) or skia.Path()
        out.append((ch, gp, cx, w))
        cx += w + tracking * size
    return out


def sfx_text_path(text: str, font: str = "dela", size: float = 100, tracking: float = 0.0,
                  rot_jitter: float = 0.0, y_jitter: float = 0.0, scale_jitter: float = 0.0,
                  r: np.random.Generator | None = None, scales: Sequence[float] | None = None,
                  wave: float = 0.0) -> skia.Path:
    """Manga SFX lettering: each glyph gets its own small rotation/offset/scale.
    `scales` optionally gives a per-character size multiplier. Baseline y=0, starts x=0."""
    r = r or rng(0)
    path = skia.Path()
    cx = 0.0
    n = len(text)
    for i, ch in enumerate(text):
        sc = (scales[i] if scales is not None else 1.0) * (1 + scale_jitter * r.uniform(-1, 1))
        f = _font(font, size * sc)
        g = f.textToGlyphs(ch)[0]
        w = f.getWidths([g])[0]
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


_VERT_ROTATE = set("ー－-—―～〜…‥（）()「」『』【】〔〕［］<>〈〉《》=＝→←")
_VERT_SMALL = set("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ、。，．")


def vtext_path(text: str, font: str = "noto", size: float = 100, spacing: float = 1.0,
               x: float = 0, y: float = 0) -> skia.Path:
    """Tategaki (vertical) text: characters stacked downward, column centre at x, top at y.
    Long-vowel marks / brackets rotate 90deg; small kana shift to the upper-right."""
    f = _font(font, size)
    path = skia.Path()
    m = f.getMetrics()
    asc, desc = -m.fAscent, m.fDescent
    em_mid = (asc - desc) / 2  # baseline offset that vertically centres the em box
    cy = y
    for ch in text:
        if ch == " ":
            cy += size * spacing * 0.5
            continue
        g = f.textToGlyphs(ch)[0]
        w = f.getWidths([g])[0]
        gp = f.getPath(g) or skia.Path()
        mat = skia.Matrix()
        if ch in _VERT_ROTATE:
            b = gp.computeTightBounds()
            # rotate around em-centre
            mat.setRotate(90, w / 2, -size * 0.38)
            gp.transform(mat)
            b = gp.computeTightBounds()
            gp.offset(x - (b.left() + b.right()) / 2, cy + size * spacing / 2 - (b.top() + b.bottom()) / 2)
        else:
            dx, dy = 0.0, 0.0
            if ch in _VERT_SMALL:
                dx, dy = size * 0.12, -size * 0.12
                if ch in "、。，．":
                    dx, dy = size * 0.55, -size * 0.55
            gp.offset(x - w / 2 + dx, cy + size * spacing / 2 + size * 0.38 + dy)
        path.addPath(gp)
        cy += size * spacing
    return path


def bounds(path: skia.Path):
    b = path.computeTightBounds()
    return b.left(), b.top(), b.right(), b.bottom()


def fit_path(path: skia.Path, box, mode: str = "contain", align=(0.5, 0.5), stretch=(1.0, 1.0)) -> skia.Path:
    """Scale+translate path so its tight bounds fit box=(x0,y0,x1,y1). stretch scales x/y extra
    (e.g. (1,3) for elongated road lettering) before fitting. Returns a new path."""
    p = skia.Path(path)
    if stretch != (1.0, 1.0):
        p.transform(skia.Matrix.Scale(stretch[0], stretch[1]))
    l, t, r_, b = bounds(p)
    bw, bh = max(r_ - l, 1e-6), max(b - t, 1e-6)
    x0, y0, x1, y1 = box
    sx, sy = (x1 - x0) / bw, (y1 - y0) / bh
    if mode == "contain":
        s = min(sx, sy); sx = sy = s
    elif mode == "width":
        sy = sx
    elif mode == "height":
        sx = sy
    m = skia.Matrix()
    m.setTranslate(-l, -t)
    m.postScale(sx, sy)
    ox = x0 + (x1 - x0 - bw * sx) * align[0]
    oy = y0 + (y1 - y0 - bh * sy) * align[1]
    m.postTranslate(ox, oy)
    p.transform(m)
    return p


def transformed(path: skia.Path, rotate=0.0, skew_x=0.0, scale=(1.0, 1.0), translate=(0.0, 0.0),
                pivot=None) -> skia.Path:
    """Copy of path rotated (deg) / skewed (tan) / scaled about pivot (default bounds centre)."""
    p = skia.Path(path)
    if pivot is None:
        l, t, r_, b = bounds(p)
        pivot = ((l + r_) / 2, (t + b) / 2)
    m = skia.Matrix()
    m.setTranslate(-pivot[0], -pivot[1])
    m.postScale(scale[0], scale[1])
    if skew_x:
        m.postSkew(skew_x, 0)
    if rotate:
        m.postRotate(rotate)
    m.postTranslate(pivot[0] + translate[0], pivot[1] + translate[1])
    p.transform(m)
    return p


# --------------------------------------------------------------------------------------
# Path primitives
# --------------------------------------------------------------------------------------
def poly(points: Iterable, close: bool = True) -> skia.Path:
    pts = list(points)
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


def circle(cx, cy, r) -> skia.Path:
    p = skia.Path(); p.addCircle(cx, cy, r); return p


def ellipse(cx, cy, rx, ry) -> skia.Path:
    p = skia.Path(); p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)); return p


def rect(x0, y0, x1, y1, radius: float = 0) -> skia.Path:
    p = skia.Path()
    r_ = skia.Rect.MakeLTRB(x0, y0, x1, y1)
    if radius > 0:
        p.addRoundRect(r_, radius, radius)
    else:
        p.addRect(r_)
    return p


def smooth_closed(points, tension: float = 0.5) -> skia.Path:
    """Closed Catmull-Rom spline through points (as cubic beziers)."""
    pts = [tuple(map(float, q)) for q in points]
    n = len(pts)
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        p.cubicTo(*c1, *c2, *p2)
    p.close()
    return p


def smooth_open(points, tension: float = 0.5) -> skia.Path:
    pts = [tuple(map(float, q)) for q in points]
    n = len(pts)
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        p.cubicTo(*c1, *c2, *p2)
    return p


def starburst(cx, cy, rx, ry, n=18, inner=0.62, jitter=0.25, r: np.random.Generator | None = None,
              rot=0.0, curve: float = 0.0, long_every: int = 0, long_amt: float = 0.35) -> skia.Path:
    """Comic starburst. curve>0 makes concave (quad-curved) flanks for an explosive look.
    long_every>0 makes every k-th spike longer (by long_amt)."""
    r = r or rng(1)
    pts = []
    tips = []
    for i in range(n):
        a0 = rot + 2 * math.pi * i / n + r.uniform(-0.25, 0.25) * 2 * math.pi / n * jitter * 2
        a1 = rot + 2 * math.pi * (i + 0.5) / n + r.uniform(-0.2, 0.2) * 2 * math.pi / n * jitter * 2
        k = 1 + r.uniform(-jitter, jitter * 0.6)
        if long_every and i % long_every == 0:
            k += long_amt * r.uniform(0.6, 1.0)
        ki = inner * (1 + r.uniform(-jitter, jitter) * 0.5)
        tips.append((cx + math.cos(a0) * rx * k, cy + math.sin(a0) * ry * k))
        pts.append((cx + math.cos(a1) * rx * ki, cy + math.sin(a1) * ry * ki))
    p = skia.Path()
    p.moveTo(*tips[0])
    for i in range(n):
        v = pts[i]
        t2 = tips[(i + 1) % n]
        if curve > 0:
            # control points pulled toward centre -> concave flanks
            c1 = (mix(np.array(tips[i]), np.array(v), 0.5) * (1 - curve) + np.array([cx, cy]) * curve)
            c2 = (mix(np.array(v), np.array(t2), 0.5) * (1 - curve) + np.array([cx, cy]) * curve)
            p.quadTo(float(c1[0]), float(c1[1]), *v)
            p.quadTo(float(c2[0]), float(c2[1]), *t2)
        else:
            p.lineTo(*v)
            p.lineTo(*t2)
    p.close()
    return p


def jagged_ellipse(cx, cy, rx, ry, teeth=40, depth=0.08, r=None, jitter=0.3, rot=0.0) -> skia.Path:
    """Spiky speech balloon: ellipse with saw teeth."""
    r = r or rng(2)
    pts = []
    for i in range(teeth * 2):
        a = rot + 2 * math.pi * i / (teeth * 2)
        out = (i % 2 == 0)
        k = 1 + (depth * (1 + r.uniform(-jitter, jitter)) if out else -depth * 0.2)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return poly(pts)


def scallop_cloud(cx, cy, rx, ry, bumps=14, bump=0.22, r=None, jitter=0.25) -> list:
    """Puffy cloud balloon as list of paths (ellipse + circles) - union them as masks."""
    r = r or rng(3)
    paths = [ellipse(cx, cy, rx * 0.95, ry * 0.95)]
    for i in range(bumps):
        a = 2 * math.pi * (i + r.uniform(-0.2, 0.2)) / bumps
        rr = min(rx, ry) * bump * (1 + r.uniform(-jitter, jitter))
        x = cx + math.cos(a) * rx * 0.92
        y = cy + math.sin(a) * ry * 0.92
        paths.append(ellipse(x, y, rr * (rx / ry) ** 0.3, rr))
    return paths


def wedge(cx, cy, a, r0, r1, w0, w1) -> skia.Path:
    """Radial wedge from radius r0 (width w0) to r1 (width w1), angle a (rad)."""
    ca, sa = math.cos(a), math.sin(a)
    nx, ny = -sa, ca
    pts = [(cx + ca * r0 + nx * w0 / 2, cy + sa * r0 + ny * w0 / 2),
           (cx + ca * r1 + nx * w1 / 2, cy + sa * r1 + ny * w1 / 2),
           (cx + ca * r1 - nx * w1 / 2, cy + sa * r1 - ny * w1 / 2),
           (cx + ca * r0 - nx * w0 / 2, cy + sa * r0 - ny * w0 / 2)]
    return poly(pts)


def action_lines(cx, cy, r_in, r_out, count, width, r=None, aspect=1.0, len_jitter=0.3,
                 width_jitter=0.6) -> skia.Path:
    """Manga focus/speed lines: needles pointing at centre, thick at r_out, sharp at r_in."""
    r = r or rng(4)
    p = skia.Path()
    for i in range(count):
        a = r.uniform(0, 2 * math.pi)
        ri = r_in * (1 + r.uniform(-len_jitter, len_jitter))
        w = width * (1 + r.uniform(-width_jitter, width_jitter))
        q = wedge(0, 0, a, ri, r_out, 0.0, w)
        q.transform(skia.Matrix.Scale(aspect, 1.0))
        q.offset(cx, cy)
        p.addPath(q)
    return p


def lightning(x0, y0, x1, y1, width, segs=5, r=None, amp=0.25) -> skia.Path:
    """Comic lightning bolt polygon from (x0,y0) to (x1,y1)."""
    r = r or rng(5)
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    left, right = [], []
    for i in range(segs + 1):
        t = i / segs
        off = 0 if i in (0, segs) else r.uniform(-amp, amp) * L / segs * 2.2
        zig = (1 if i % 2 else -1) * L / segs * 0.35 if 0 < i < segs else 0
        w = width * (1 - t) ** 0.7 + width * 0.05
        px = x0 + dx * t + nx * (off + zig)
        py = y0 + dy * t + ny * (off + zig)
        left.append((px + nx * w / 2 + ux * w * 0.3, py + ny * w / 2 + uy * w * 0.3))
        right.append((px - nx * w / 2 - ux * w * 0.3, py - ny * w / 2 - uy * w * 0.3))
    right[-1] = left[-1] = (x1, y1)
    return poly(left + right[::-1])


def drip_paths(x, y, width, length, r=None, bulb=1.25) -> list:
    """Spray-paint drip hanging from (x,y): fillet root + tapering stem + bulb."""
    r = r or rng(6)
    w = width
    paths = []
    # stem (slight taper, slight wobble)
    wob = r.uniform(-0.15, 0.15) * w
    p = skia.Path()
    p.moveTo(x - w * 0.5, y)
    p.cubicTo(x - w * 0.5, y + length * 0.4, x - w * 0.42 + wob, y + length * 0.7, x - w * 0.38 + wob, y + length)
    p.lineTo(x + w * 0.38 + wob, y + length)
    p.cubicTo(x + w * 0.42 + wob, y + length * 0.7, x + w * 0.5, y + length * 0.4, x + w * 0.5, y)
    p.close()
    paths.append(p)
    # bulb
    br = w * 0.5 * bulb * r.uniform(0.9, 1.15)
    paths.append(ellipse(x + wob, y + length + br * 0.15, br, br * 1.15))
    # fillet root (concave widening into the source shape)
    fw = w * 1.6
    q = skia.Path()
    q.moveTo(x - w * 0.5 - fw, y - w * 0.3)
    q.quadTo(x - w * 0.5, y - w * 0.3, x - w * 0.5, y + w * 1.2)
    q.lineTo(x + w * 0.5, y + w * 1.2)
    q.quadTo(x + w * 0.5, y - w * 0.3, x + w * 0.5 + fw, y - w * 0.3)
    q.close()
    paths.append(q)
    return paths


def splat_path(cx, cy, radius, r=None, arms=14, arm_len=0.9, blob=0.55) -> list:
    """Paint splat: central wobbly blob + radial arms ending in droplets + loose droplets."""
    r = r or rng(7)
    paths = []
    n = 28
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = blob * (1 + 0.25 * math.sin(a * 3 + r.uniform(0, 6)) + r.uniform(-0.12, 0.12))
        pts.append((cx + math.cos(a) * radius * k, cy + math.sin(a) * radius * k))
    paths.append(smooth_closed(pts, 0.8))
    for i in range(arms):
        a = r.uniform(0, 2 * math.pi)
        L = radius * r.uniform(0.6, 1.0) * arm_len + radius * blob * 0.6
        w = radius * r.uniform(0.06, 0.16)
        paths.append(wedge(cx, cy, a, radius * blob * 0.5, L, w * 2.2, w * 0.7))
        dr = w * r.uniform(0.7, 1.3)
        paths.append(circle(cx + math.cos(a) * L, cy + math.sin(a) * L, dr))
        if r.random() < 0.6:
            L2 = L + radius * r.uniform(0.1, 0.35)
            paths.append(circle(cx + math.cos(a) * L2, cy + math.sin(a) * L2, dr * r.uniform(0.3, 0.7)))
    return paths


def flecks(cx, cy, radius, count, size=(2, 14), r=None, sigma=0.5, elong=0.3) -> skia.Path:
    """Splatter flecks scattered around a centre (gaussian radial distribution).
    Larger flecks are rarer (power law); some are elongated radially."""
    r = r or rng(8)
    p = skia.Path()
    for _ in range(count):
        a = r.uniform(0, 2 * math.pi)
        d = abs(r.normal(0, sigma)) * radius + radius * 0.15
        s = size[0] + (size[1] - size[0]) * (r.random() ** 3)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        if r.random() < elong:
            q = ellipse(0, 0, s * r.uniform(1.6, 3.0), s * 0.6)
            q.transform(skia.Matrix.RotateRad(a))
            q.offset(x, y)
            p.addPath(q)
        else:
            p.addCircle(x, y, s)
    return p


def ribbon(cx, cy, w, h, angle=0.0, tail=0.18, notch=0.45, fold=0.06, skew=0.0):
    """Banner ribbon with V-notched tails. Returns dict of paths: band, tails, folds.
    Geometry before rotation: band centred at (cx,cy) width w height h; tails behind,
    dropped down by `fold*w`."""
    t = w * tail
    dy = h * 0.35
    fx = w * fold
    band = poly([(-w / 2 + skew * h / 2, -h / 2), (w / 2 + skew * h / 2, -h / 2),
                 (w / 2 - skew * h / 2, h / 2), (-w / 2 - skew * h / 2, h / 2)])
    lt = poly([(-w / 2 + fx, -h / 2 + dy), (-w / 2 - t, -h / 2 + dy), (-w / 2 - t + notch * h * 0.7, dy),
               (-w / 2 - t, h / 2 + dy), (-w / 2 + fx, h / 2 + dy)])
    rt = poly([(w / 2 - fx, -h / 2 + dy), (w / 2 + t, -h / 2 + dy), (w / 2 + t - notch * h * 0.7, dy),
               (w / 2 + t, h / 2 + dy), (w / 2 - fx, h / 2 + dy)])
    lf = poly([(-w / 2 - skew * h / 2, h / 2), (-w / 2 + fx, h / 2 + dy), (-w / 2 + fx, h / 2)])
    rf = poly([(w / 2 - skew * h / 2, h / 2), (w / 2 - fx, h / 2 + dy), (w / 2 - fx, h / 2)])
    m = skia.Matrix()
    m.setRotate(angle)
    m.postTranslate(cx, cy)
    out = {}
    for k, pth in (("band", band), ("tails", None), ("folds", None)):
        pass
    tails = skia.Path(); tails.addPath(lt); tails.addPath(rt)
    folds = skia.Path(); folds.addPath(lf); folds.addPath(rf)
    for k, pth in (("band", band), ("tails", tails), ("folds", folds)):
        pth.transform(m)
        out[k] = pth
    return out


def union(*paths) -> skia.Path:
    acc = None
    for p in paths:
        if p is None:
            continue
        if isinstance(p, (list, tuple)):
            p = union(*p)
        acc = skia.Path(p) if acc is None else skia.Op(acc, p, skia.PathOp.kUnion_PathOp)
    return acc if acc is not None else skia.Path()


def combine(*paths) -> skia.Path:
    """Cheap concatenation (non-zero winding ~ union for same-direction shapes)."""
    acc = skia.Path()
    for p in paths:
        if isinstance(p, (list, tuple)):
            p = combine(*p)
        acc.addPath(p)
    return acc


# --------------------------------------------------------------------------------------
# Rasterisation
# --------------------------------------------------------------------------------------
def raster(path, w: int, h: int, scale: float = 1.0, stroke: float = 0.0, fill: bool = True,
           join: str = "round", cap: str = "round", miter: float = 4.0, evenodd: bool = False,
           aa: bool = True) -> np.ndarray:
    """Rasterise path(s) to float32 coverage mask (h,w). Geometry is multiplied by `scale`.
    stroke>0 & fill -> fill+stroke (i.e. dilation by stroke/2); stroke>0 & not fill -> stroke only."""
    surf = skia.Surface.MakeRaster(skia.ImageInfo.MakeA8(w, h))
    cv = surf.getCanvas()
    cv.clear(0)
    cv.scale(scale, scale)
    paint = skia.Paint(AntiAlias=aa)
    if stroke > 0:
        paint.setStyle(skia.Paint.kStrokeAndFill_Style if fill else skia.Paint.kStroke_Style)
        paint.setStrokeWidth(stroke)
        paint.setStrokeJoin({"round": skia.Paint.kRound_Join, "miter": skia.Paint.kMiter_Join,
                             "bevel": skia.Paint.kBevel_Join}[join])
        paint.setStrokeCap({"round": skia.Paint.kRound_Cap, "butt": skia.Paint.kButt_Cap,
                            "square": skia.Paint.kSquare_Cap}[cap])
        paint.setStrokeMiter(miter)
    paths = path if isinstance(path, (list, tuple)) else [path]
    for p in paths:
        if evenodd:
            p = skia.Path(p); p.setFillType(skia.PathFillType.kEvenOdd)
        cv.drawPath(p, paint)
    a = surf.makeImageSnapshot().toarray()
    if a.ndim == 3:
        a = a[..., -1]
    return (a.astype(f32) / 255.0)


def mask_union(*ms):
    out = None
    for m in ms:
        out = m.copy() if out is None else np.maximum(out, m)
    return out


def mask_sub(a, b):
    return a * (1 - b)


def dilate(m: np.ndarray, r: float) -> np.ndarray:
    """Round dilation by r px (AA edge) using an exact euclidean distance transform."""
    if r <= 0:
        return m
    outside = (m < 0.5).astype(np.uint8)
    d = cv2.distanceTransform(outside, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    # sub-pixel correction from AA coverage on the boundary
    cov = np.clip(r + 0.5 - d, 0, 1)
    return np.maximum(m, cov).astype(f32)


def erode(m: np.ndarray, r: float) -> np.ndarray:
    if r <= 0:
        return m
    return (1 - dilate(1 - m, r)).astype(f32)


def blur(m: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return m
    k = int(sigma * 3) * 2 + 1
    return cv2.GaussianBlur(m, (k, k), sigma, borderType=cv2.BORDER_REFLECT)


def blur_wrap(m: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur with wrap-around borders (for tileable textures)."""
    if sigma <= 0:
        return m
    pad = int(sigma * 3) + 1
    k = pad * 2 + 1
    big = np.pad(m, [(pad, pad), (pad, pad)] + [(0, 0)] * (m.ndim - 2), mode="wrap")
    big = cv2.GaussianBlur(big, (k, k), sigma)
    return big[pad:-pad, pad:-pad]


def shift(m: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Sub-pixel translate a mask (zero fill)."""
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(m, M, (m.shape[1], m.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def extrude(m: np.ndarray, dx: float, dy: float, steps: int | None = None) -> np.ndarray:
    """Union of m swept along (dx,dy) -> 3D block extrusion mask (includes m)."""
    L = math.hypot(dx, dy)
    steps = steps or max(2, int(L / 1.5))
    out = m.copy()
    for i in range(1, steps + 1):
        t = i / steps
        np.maximum(out, shift(m, dx * t, dy * t), out=out)
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------------------
# Procedural fields
# --------------------------------------------------------------------------------------
def coords(h, w):
    yy, xx = np.mgrid[0:h, 0:w].astype(f32)
    return xx, yy


def noise(h: int, w: int, scale: float = 64.0, seed=0, beta: float = 2.0, aniso=(1.0, 1.0),
          octaves_cut: float = 0.0) -> np.ndarray:
    """Tileable (periodic) fractal noise in 0..1 via spectral synthesis.
    scale ~ feature size in px; beta = spectral slope (2 = cloudy, 1 = grainy);
    aniso=(ax, ay) stretches features (e.g. (1, 8) = vertical streaks)."""
    r = rng(seed)
    wn = r.standard_normal((h, w)).astype(f32)
    F = np.fft.rfft2(wn)
    fy = np.fft.fftfreq(h)[:, None] * aniso[1]
    fx = np.fft.rfftfreq(w)[None, :] * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    f0 = 1.0 / max(scale, 1e-3)
    amp = 1.0 / np.power(np.maximum(f, f0 * 0.25) / f0 + 1.0, beta)
    amp[0, 0] = 0
    if octaves_cut > 0:
        amp *= np.exp(-(f / (f0 * octaves_cut)) ** 2)
    out = np.fft.irfft2(F * amp, s=(h, w)).astype(f32)
    out -= out.mean()
    sd = out.std() + 1e-8
    out = 0.5 + out / (sd * 5.0)
    return np.clip(out, 0, 1).astype(f32)


def worley(h: int, w: int, cell: float, seed=0, tile: bool = True) -> np.ndarray:
    """Tileable F1 worley (distance to nearest feature point), normalised ~0..1."""
    r = rng(seed)
    nx, ny = max(1, int(round(w / cell))), max(1, int(round(h / cell)))
    cw, ch = w / nx, h / ny
    pts = []
    for j in range(ny):
        for i in range(nx):
            pts.append(((i + r.random()) * cw, (j + r.random()) * ch))
    pts = np.array(pts, f32)
    if tile:
        ext = [pts + np.array([dx * w, dy * h], f32) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        pts = np.concatenate(ext)
    # rasterise via distance transform on a seed image (fast, approximate)
    img = np.ones((h * 3, w * 3) if tile else (h, w), np.uint8)
    off = np.array([w, h], f32) if tile else np.zeros(2, f32)
    for (x, y) in pts:
        xi, yi = int(x + off[0]), int(y + off[1])
        if 0 <= xi < img.shape[1] and 0 <= yi < img.shape[0]:
            img[yi, xi] = 0
    d = cv2.distanceTransform(img, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    if tile:
        d = d[h:2 * h, w:2 * w]
    return np.clip(d / (cell * 0.75), 0, 1).astype(f32)


def halftone(h: int, w: int, value, period: float, angle: float = 45.0, offset=(0.0, 0.0),
             scale: float = 1.0, max_r: float = 0.72, shape: str = "dot") -> np.ndarray:
    """AA halftone screen mask. value = coverage 0..1 (scalar or HxW array, at this res).
    period and offsets in internal px. shape: 'dot' | 'line' | 'square'."""
    xx, yy = coords(h, w)
    xx = xx + offset[0]; yy = yy + offset[1]
    a = math.radians(angle)
    u = (xx * math.cos(a) + yy * math.sin(a)) / period
    v = (-xx * math.sin(a) + yy * math.cos(a)) / period
    fu = u - np.floor(u) - 0.5
    fv = v - np.floor(v) - 0.5
    val = np.clip(np.asarray(value, f32), 0, 1)
    if shape == "line":
        half = val * 0.5 * period
        d = np.abs(fv) * period
        return np.clip(half - d + 0.5, 0, 1).astype(f32)
    if shape == "square":
        d = np.maximum(np.abs(fu), np.abs(fv)) * period
        half = np.sqrt(val) * 0.5 * period
        return np.clip(half - d + 0.5, 0, 1).astype(f32)
    d = np.sqrt(fu * fu + fv * fv) * period
    rad = np.minimum(np.sqrt(val / math.pi), max_r) * period
    m = np.clip(rad - d + 0.5, 0, 1)
    m = np.where(val <= 0.002, 0, m)
    return m.astype(f32)


def lin_ramp(h, w, p0, p1) -> np.ndarray:
    """0..1 ramp along p0->p1 (clamped)."""
    xx, yy = coords(h, w)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L2 = dx * dx + dy * dy + 1e-9
    t = ((xx - p0[0]) * dx + (yy - p0[1]) * dy) / L2
    return np.clip(t, 0, 1).astype(f32)


def rad_ramp(h, w, cx, cy, r) -> np.ndarray:
    xx, yy = coords(h, w)
    return np.clip(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r, 0, 1).astype(f32)


def gradient_map(t: np.ndarray, stops) -> np.ndarray:
    """Map 0..1 field to colours. stops: list of (pos, rgb). Returns HxWx3."""
    stops = sorted(stops, key=lambda s: s[0])
    pos = np.array([s[0] for s in stops], f32)
    cols = np.stack([np.asarray(s[1], f32) for s in stops])
    out = np.empty(t.shape + (3,), f32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def vgrad_col(h: int, y0: float, y1: float, stops) -> np.ndarray:
    """Vertical gradient as (h,1,3) column (broadcastable, cheap)."""
    y = np.arange(h, dtype=f32)
    t = np.clip((y - y0) / max(y1 - y0, 1e-6), 0, 1)
    return gradient_map(t, stops)[:, None, :]


# --------------------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------------------
class Canvas:
    """Premultiplied float RGBA canvas rendered at ss x the output size."""

    def __init__(self, w: int, h: int, ss: int = 2, bg=None):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.px = np.zeros((self.H, self.W, 4), f32)
        if bg is not None:
            self.px[..., :3] = np.asarray(bg, f32)
            self.px[..., 3] = 1.0

    # ---- geometry -> masks (design units) ----
    def mask(self, path, stroke: float = 0.0, fill: bool = True, **kw) -> np.ndarray:
        return raster(path, self.W, self.H, scale=self.ss, stroke=stroke, fill=fill, **kw)

    def dilate(self, m, r):
        return dilate(m, r * self.ss)

    def erode(self, m, r):
        return erode(m, r * self.ss)

    def blur(self, m, s):
        return blur(m, s * self.ss)

    def shift(self, m, dx, dy):
        return shift(m, dx * self.ss, dy * self.ss)

    def extrude(self, m, dx, dy, steps=None):
        return extrude(m, dx * self.ss, dy * self.ss, steps)

    def halftone(self, value, period, angle=45.0, **kw):
        return halftone(self.H, self.W, value, period * self.ss, angle, **kw)

    def noise(self, scale, seed=0, **kw):
        return noise(self.H, self.W, scale * self.ss, seed, **kw)

    def ramp(self, p0, p1):
        s = self.ss
        return lin_ramp(self.H, self.W, (p0[0] * s, p0[1] * s), (p1[0] * s, p1[1] * s))

    def radial(self, cx, cy, r):
        s = self.ss
        return rad_ramp(self.H, self.W, cx * s, cy * s, r * s)

    def vgrad(self, y0, y1, stops):
        return vgrad_col(self.H, y0 * self.ss, y1 * self.ss, stops)

    # ---- compositing ----
    def paint(self, mask, color, opacity: float = 1.0):
        """Normal 'over'. color: (3,) rgb, (H,1,3)/(H,W,3) array."""
        a = mask * opacity if opacity != 1.0 else mask
        col = np.asarray(color, f32)
        a3 = a[..., None]
        self.px[..., :3] *= (1 - a3)
        self.px[..., :3] += col * a3
        self.px[..., 3] *= (1 - a)
        self.px[..., 3] += a

    def paint_atop(self, mask, color, opacity: float = 1.0):
        """Source-atop: paint only where the canvas already has alpha (keeps alpha)."""
        a = mask * opacity
        da = self.px[..., 3]
        col = np.asarray(color, f32)
        a3 = a[..., None]
        self.px[..., :3] = col * (a * da)[..., None] + self.px[..., :3] * (1 - a3)

    def multiply(self, mask, color, opacity: float = 1.0):
        """Multiply-blend colour onto existing pixels inside mask."""
        a = (mask * opacity)[..., None]
        col = np.asarray(color, f32)
        self.px[..., :3] *= (1 - a) + a * col

    def screen(self, mask, color, opacity: float = 1.0):
        a = (mask * opacity)[..., None]
        col = np.asarray(color, f32)
        da = self.px[..., 3:4]
        # screen in premultiplied space restricted to existing coverage
        rgb = self.px[..., :3]
        self.px[..., :3] = rgb + (col * da - rgb * col) * a

    def add(self, mask, color, opacity: float = 1.0):
        a = (mask * opacity)[..., None]
        self.px[..., :3] += np.asarray(color, f32) * a
        self.px[..., 3] = np.maximum(self.px[..., 3], mask * opacity)

    def erase(self, mask, opacity: float = 1.0):
        k = 1 - mask * opacity
        self.px *= k[..., None]

    def clip_to(self, mask):
        self.px *= mask[..., None]

    def over(self, other: "Canvas", opacity: float = 1.0):
        src = other.px * opacity
        self.px = src + self.px * (1 - src[..., 3:4])

    def alpha(self):
        return self.px[..., 3]

    def copy(self):
        c = Canvas.__new__(Canvas)
        c.w, c.h, c.ss, c.W, c.H = self.w, self.h, self.ss, self.W, self.H
        c.px = self.px.copy()
        return c

    # ---- output ----
    def final(self) -> np.ndarray:
        """Downsampled straight-alpha float RGBA (h,w,4)."""
        px = self.px
        if self.ss != 1:
            px = cv2.resize(px, (self.w, self.h), interpolation=cv2.INTER_AREA)
        a = np.clip(px[..., 3:4], 0, 1)
        rgb = np.where(a > 1e-6, px[..., :3] / np.maximum(a, 1e-6), 0)
        return np.concatenate([np.clip(rgb, 0, 1), a], axis=-1)

    def image(self, mode: str = "RGBA") -> Image.Image:
        return to_image(self.final(), mode)

    def save(self, path: str, mode: str = "RGBA", flatten=None):
        img = self.final()
        if flatten is not None:
            a = img[..., 3:4]
            img = np.concatenate([img[..., :3] * a + np.asarray(flatten, f32) * (1 - a), np.ones_like(a)], -1)
        save_image(img, path, mode)
        return path


def to_image(arr: np.ndarray, mode: str = "RGBA") -> Image.Image:
    """float (h,w,C) 0..1 -> PIL image with light ordered dithering to avoid banding."""
    arr = np.asarray(arr, f32)
    h, w = arr.shape[:2]
    dither = (_bayer(h, w) - 0.5) / 255.0
    if arr.ndim == 2:
        u8 = np.clip((arr + dither) * 255 + 0.5, 0, 255).astype(np.uint8)
        return Image.fromarray(u8, "L")
    u8 = np.clip((arr + dither[..., None]) * 255 + 0.5, 0, 255).astype(np.uint8)
    if arr.shape[2] == 4:
        # keep fully transparent pixels exactly 0 alpha and exact opaque at 255
        u8[..., 3] = np.clip(arr[..., 3] * 255 + 0.5, 0, 255).astype(np.uint8)
    img = Image.fromarray(u8, "RGBA" if arr.shape[2] == 4 else "RGB")
    if mode != img.mode:
        img = img.convert(mode)
    return img


_BAYER_CACHE = {}


def _bayer(h, w):
    key = (h, w)
    if key not in _BAYER_CACHE:
        b = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], f32) / 16.0
        _BAYER_CACHE[key] = np.tile(b, (h // 4 + 1, w // 4 + 1))[:h, :w]
    return _BAYER_CACHE[key]


def save_image(arr_or_img, path: str, mode: str = "RGBA"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = arr_or_img if isinstance(arr_or_img, Image.Image) else to_image(arr_or_img, mode)
    img.save(path, optimize=False, compress_level=7)
    return path


# --------------------------------------------------------------------------------------
# Texture helpers (normal maps, tiling)
# --------------------------------------------------------------------------------------
def normal_from_height(hgt: np.ndarray, strength: float = 4.0, wrap: bool = True) -> np.ndarray:
    """OpenGL (+Y up) tangent-space normal map from a height field (0..1). Returns (h,w,3) 0..1."""
    if wrap:
        dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
        dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
    else:
        dy, dx = np.gradient(hgt)
    nx = -dx * strength
    ny = dy * strength  # image y points down; OpenGL green points up
    nz = np.ones_like(hgt)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / L, ny / L, nz / L], -1)
    return (n * 0.5 + 0.5).astype(f32)


def tile_preview(img: Image.Image, nx=2, ny=2, max_size=1600) -> Image.Image:
    w, h = img.size
    out = Image.new(img.mode, (w * nx, h * ny))
    for j in range(ny):
        for i in range(nx):
            out.paste(img, (i * w, j * h))
    s = min(1.0, max_size / max(out.size))
    if s < 1:
        out = out.resize((int(out.width * s), int(out.height * s)), Image.LANCZOS)
    return out


# --------------------------------------------------------------------------------------
# Contact sheets
# --------------------------------------------------------------------------------------
def checker(w, h, s=16, c0=(200, 200, 205), c1=(170, 170, 178)) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx // s + yy // s) % 2).astype(bool)
    arr = np.where(m[..., None], np.array(c1, np.uint8), np.array(c0, np.uint8)).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def contact_sheet(paths: Sequence[str], out: str, cell=(360, 240), cols: int = 5, bg: str = "checker",
                  label: bool = True, title: str | None = None):
    """Grid of thumbnails (aspect-preserving) over checker/dark/light bg, labelled with file names."""
    rows = (len(paths) + cols - 1) // cols
    pad, lab = 10, (22 if label else 0)
    top = 40 if title else 0
    W = cols * (cell[0] + pad) + pad
    H = top + rows * (cell[1] + pad + lab) + pad
    sheet = Image.new("RGB", (W, H), (34, 30, 44))
    d = ImageDraw.Draw(sheet)
    try:
        fnt = pil_font("chakra", 15)
        tfnt = pil_font("bangers", 30)
    except Exception:
        fnt = tfnt = None
    if title:
        d.text((pad, 4), title, fill=(255, 248, 231), font=tfnt)
    for i, p in enumerate(paths):
        r_, c_ = divmod(i, cols)
        x = pad + c_ * (cell[0] + pad)
        y = top + pad + r_ * (cell[1] + pad + lab)
        if bg == "checker":
            back = checker(cell[0], cell[1])
        elif bg == "dark":
            back = Image.new("RGB", cell, (20, 18, 28))
        else:
            back = Image.new("RGB", cell, (235, 232, 222))
        try:
            im = Image.open(p)
            im.load()
            im = im.convert("RGBA")
            s = min(cell[0] / im.width, cell[1] / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            back = back.convert("RGBA")
            back.alpha_composite(im, ((cell[0] - im.width) // 2, (cell[1] - im.height) // 2))
        except Exception as e:  # pragma: no cover
            print("contact sheet: failed", p, e)
        sheet.paste(back.convert("RGB"), (x, y))
        if label:
            d.text((x, y + cell[1] + 2), os.path.basename(p)[:44], fill=(220, 215, 205), font=fnt)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return out
