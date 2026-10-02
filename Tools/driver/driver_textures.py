"""Surface textures for the driver's racing suit and gloves (seamless tiles + decals), all generated here.

    Tools/.venv/bin/python Tools/driver/driver_textures.py

Normal maps (OpenGL convention, *_n.png so Unity imports them as normal maps):
  suit_n      quilted multi-layer Nomex: diamond quilting with stitch rows over a fine twill weave (tile = 8 cm)
  twill_n     plain twill for stripes and stretch panels                                             (tile = 4 cm)
  leather_n   glove back: pebbled full-grain leather                                                  (tile = 4 cm)
  suede_n     palm: brushed suede with a printed silicone grip pattern                                (tile = 4 cm)
  knit_n      ribbed knit cuff                                                                         (tile = 4 cm)
  velcro_n    hook-and-loop strap                                                                      (tile = 4 cm)
Decals (RGBA, alpha-clipped): glove_logo, patch_ink, patch_flag, patch_fia.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Driver", "Resources", "Driver")
FONTS = os.path.join(REPO, "Game", "Assets", "InkDrift", "Art", "Fonts")
N = 1024
rng = np.random.default_rng(7)


def grid():
    y, x = np.mgrid[0:N, 0:N].astype(np.float64) / N
    return x, y


def tile_noise(freq, octaves=4, seed=0):
    """seamless value noise (periodic lattice) in [0,1]"""
    r = np.random.default_rng(seed)
    out = np.zeros((N, N))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        f = freq * (2 ** o)
        lat = r.random((f, f))
        x, y = grid()
        gx, gy = x * f, y * f
        x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
        fx, fy = gx - x0, gy - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x1, y1 = (x0 + 1) % f, (y0 + 1) % f
        x0, y0 = x0 % f, y0 % f
        v = (lat[y0, x0] * (1 - fx) + lat[y0, x1] * fx) * (1 - fy) + (lat[y1, x0] * (1 - fx) + lat[y1, x1] * fx) * fy
        out += v * amp
        tot += amp
        amp *= 0.5
    return out / tot


def worley(cells, seed=0):
    """seamless cellular noise: distance to nearest feature point (cells x cells grid)"""
    r = np.random.default_rng(seed)
    jitter = r.random((cells, cells, 2))                                # feature point inside each cell
    x, y = grid()
    gx, gy = x * cells, y * cells
    cx, cy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    d = np.full((N, N), 9.0)
    d2 = np.full((N, N), 9.0)
    for oy in (-1, 0, 1):          # only the 3x3 neighbourhood can hold the nearest points
        for ox in (-1, 0, 1):
            nx_, ny_ = cx + ox, cy + oy
            j = jitter[ny_ % cells, nx_ % cells]
            dd = (gx - (nx_ + j[..., 0])) ** 2 + (gy - (ny_ + j[..., 1])) ** 2
            m = dd < d
            d2 = np.where(m, d, np.minimum(d2, dd))
            d = np.where(m, dd, d)
    return np.sqrt(d), np.sqrt(d2)


def height_to_normal(h, strength):
    """tileable normal map from a height field (h in 0..1)"""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)   # OpenGL (+Y up in UV)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5
    return Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8), "RGB")


def save(img, name):
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, name))
    print("wrote", name)


def twill(freq):
    x, y = grid()
    t = np.sin(2 * np.pi * (x + y) * freq) * 0.5 + 0.5                  # diagonal twill ribs
    cross = np.sin(2 * np.pi * (x - y) * freq * 0.5) * 0.5 + 0.5
    return t * 0.75 + cross * 0.25


def suit():
    """quilted Nomex: puffy diamonds separated by stitched grooves, over twill (tile = 8 cm, 2x2 diamonds)"""
    x, y = grid()
    u, v = (x + y) * 2.0, (x - y) * 2.0                                 # diamond lattice, 2 per tile edge
    fu, fv = u - np.floor(u), v - np.floor(v)
    du, dv = np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)             # distance to the quilting lines
    edge = np.minimum(du, dv)
    puff = np.clip(edge / 0.5, 0, 1) ** 0.55                              # pillow shape inside each diamond
    groove = 1 - np.exp(-(edge / 0.018) ** 2)                            # stitched seam pulls the fabric in
    # stitches along the groove: short dashes
    along = np.where(du < dv, fv, fu)
    dash = (np.sin(2 * np.pi * along * 28) > 0.2).astype(float) * np.exp(-(edge / 0.008) ** 2)
    h = puff * 0.55 * groove + twill(96) * 0.06 + tile_noise(16, 3, 3) * 0.05 - dash * 0.08
    save(height_to_normal(h, 9.0), "suit_n.png")


def twill_panel():
    h = twill(64) * 0.35 + tile_noise(32, 3, 5) * 0.15
    save(height_to_normal(h, 5.0), "twill_n.png")


def leather():
    f1, f2 = worley(42, 11)
    pebble = np.clip(f2 - f1, 0, 1)                                       # ridges between pebbles
    h = (1 - np.exp(-pebble * 6)) * 0.6 + tile_noise(48, 3, 12) * 0.25
    save(height_to_normal(h, 7.0), "leather_n.png")


def suede():
    x, y = grid()
    fibre = tile_noise(128, 2, 21) * 0.5 + tile_noise(64, 2, 22) * 0.3
    # printed silicone grip: staggered small hexagon-ish dots, 3 mm pitch on a 4 cm tile
    k = 13
    gy = y * k
    row = np.floor(gy)
    gx = x * k + (row % 2) * 0.5
    cx, cy = gx - np.floor(gx) - 0.5, gy - row - 0.5
    d = np.maximum(np.abs(cx) * 1.0 + np.abs(cy) * 0.58, np.abs(cy) * 1.15)
    dots = np.clip((0.30 - d) / 0.04, 0, 1)
    h = fibre * 0.25 + dots * 0.8
    save(height_to_normal(h, 6.0), "suede_n.png")


def knit():
    x, y = grid()
    rib = np.abs(np.sin(np.pi * x * 24)) ** 0.6
    loops = np.abs(np.sin(np.pi * y * 48)) * 0.3
    h = rib * 0.8 + loops * rib * 0.3 + tile_noise(32, 2, 31) * 0.1
    save(height_to_normal(h, 6.0), "knit_n.png")


def velcro():
    h = tile_noise(96, 3, 41) * 0.7 + tile_noise(256, 1, 42) * 0.3
    save(height_to_normal(h, 4.0), "velcro_n.png")


# ---------------------------------------------------------------- decals
def font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, name), px)


def glove_logo():
    """brand mark for the back of the glove: slashed 'INK' with a speed wedge"""
    S = 512
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(40, 330), (472, 250), (440, 300), (60, 370)], fill=(255, 45, 122, 255))     # magenta wedge
    d.text((256, 220), "INK", font=font("Bangers-Regular.ttf", 230), fill=(245, 245, 245, 255), anchor="mm")
    d.text((256, 410), "RACEWEAR", font=font("ChakraPetch-Bold.ttf", 52), fill=(245, 245, 245, 255), anchor="mm")
    save(im, "glove_logo.png")


def patch_ink():
    S = 512
    im = Image.new("RGBA", (S, S // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, S - 6, S // 2 - 6], radius=26, fill=(14, 14, 22, 255), outline=(255, 230, 0, 255), width=10)
    d.text((S // 2, 104), "INK DRIFT", font=font("Bangers-Regular.ttf", 140), fill=(255, 45, 122, 255), anchor="mm")
    d.text((S // 2, 196), "TOKYO · 東京", font=font("NotoSansJP-Bold.ttf", 54), fill=(255, 248, 231, 255), anchor="mm")
    save(im, "patch_ink.png")


def patch_flag():
    W, H = 384, 256
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, W - 4, H - 4], radius=14, fill=(250, 250, 250, 255), outline=(30, 30, 40, 255), width=8)
    d.ellipse([W / 2 - 77, H / 2 - 77, W / 2 + 77, H / 2 + 77], fill=(200, 16, 46, 255))
    save(im, "patch_flag.png")


def patch_class():
    """homologation-style label (fictional): 'INK SPORT · 8856-2018 style' block"""
    W, H = 512, 192
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, W - 4, H - 4], fill=(240, 240, 240, 255), outline=(20, 20, 20, 255), width=6)
    d.rectangle([4, 4, 150, H - 4], fill=(20, 20, 20, 255))
    d.text((77, H // 2), "ID", font=font("ChakraPetch-Bold.ttf", 96), fill=(255, 230, 0, 255), anchor="mm")
    d.text((330, 64), "INK SPORT", font=font("ChakraPetch-Bold.ttf", 58), fill=(20, 20, 20, 255), anchor="mm")
    d.text((330, 132), "FIRE-RESISTANT · CLASS 3", font=font("ChakraPetch-Regular.ttf", 30), fill=(20, 20, 20, 255), anchor="mm")
    save(im, "patch_class.png")


if __name__ == "__main__":
    suit(); twill_panel(); leather(); suede(); knit(); velcro()
    glove_logo(); patch_ink(); patch_flag(); patch_class()
