"""Procedural decal textures for street props (urban set A).
Run:  Tools/.venv/bin/python Tools/blender/props/make_textures.py
Writes power-of-two PNGs to Game/Assets/InkDrift/Models/Props/Textures/ (prop_<name>_albedo/_normal).
All artwork is original/procedural; fonts are the repo's OFL fonts (Art/Fonts)."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(REPO, 'Game', 'Assets', 'InkDrift', 'Models', 'Props', 'Textures')
FONTS = os.path.join(REPO, 'Game', 'Assets', 'InkDrift', 'Art', 'Fonts')
os.makedirs(OUT, exist_ok=True)


def font(name='NotoSansJP-Black.ttf', size=64):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def save(img, name):
    p = os.path.join(OUT, name)
    img.save(p, optimize=True)
    print('wrote', p, img.size)


def text_center(d, xy, s, f, fill, vertical=False, spacing=0):
    x, y = xy
    if vertical:
        hs = []
        for ch in s:
            b = d.textbbox((0, 0), ch, font=f)
            hs.append(b[3] - b[1])
        tot = sum(hs) + spacing * (len(s) - 1)
        cy = y - tot / 2
        for ch, h in zip(s, hs):
            b = d.textbbox((0, 0), ch, font=f)
            d.text((x - (b[2] + b[0]) / 2, cy - b[1]), ch, font=f, fill=fill)
            cy += h + spacing
        return
    b = d.textbbox((0, 0), s, font=f)
    d.text((x - (b[2] + b[0]) / 2, y - (b[3] + b[1]) / 2), s, font=f, fill=fill)


def grime(img, amount=10, seed=1):
    rng = np.random.default_rng(seed)
    a = np.asarray(img).astype(np.float32)
    n = rng.normal(0, amount, a.shape[:2])
    n = np.asarray(Image.fromarray(((n - n.min()) / (np.ptp(n) + 1e-6) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)
    n = (n / 255.0 - 0.5) * amount
    a[..., :3] = np.clip(a[..., :3] + n[..., None], 0, 255)
    return Image.fromarray(a.astype(np.uint8), img.mode)


def hazard_stripe():
    """Yellow/black 45deg stripes, tileable. One tile = 0.5 m -> 4 stripes of 12.5 cm."""
    S = 512
    y, x = np.mgrid[0:S, 0:S]
    band = ((x + y) // (S // 4)) % 2   # period S/2 along diagonal -> tileable
    img = np.zeros((S, S, 3), np.uint8)
    img[band == 0] = (245, 196, 0)
    img[band == 1] = (24, 24, 26)
    im = Image.fromarray(img).filter(ImageFilter.GaussianBlur(0.6))
    save(grime(im, 8, 2), 'prop_hazard_stripe_albedo.png')


def ped_signal():
    """512x256 atlas: left = red standing figure, right = green walking figure (on near-black)."""
    W, H = 512, 256
    im = Image.new('RGB', (W, H), (14, 14, 16))
    d = ImageDraw.Draw(im)

    def standing(cx, cy, s, col):
        d.ellipse((cx - 0.09 * s, cy - 0.42 * s, cx + 0.09 * s, cy - 0.24 * s), fill=col)
        d.rounded_rectangle((cx - 0.13 * s, cy - 0.21 * s, cx + 0.13 * s, cy + 0.08 * s), radius=int(0.05 * s), fill=col)
        d.rectangle((cx - 0.12 * s, cy + 0.06 * s, cx - 0.02 * s, cy + 0.42 * s), fill=col)
        d.rectangle((cx + 0.02 * s, cy + 0.06 * s, cx + 0.12 * s, cy + 0.42 * s), fill=col)
        d.rectangle((cx - 0.19 * s, cy - 0.19 * s, cx - 0.14 * s, cy + 0.10 * s), fill=col)
        d.rectangle((cx + 0.14 * s, cy - 0.19 * s, cx + 0.19 * s, cy + 0.10 * s), fill=col)

    def walking(cx, cy, s, col):
        d.ellipse((cx - 0.02 * s, cy - 0.44 * s, cx + 0.16 * s, cy - 0.26 * s), fill=col)
        w = int(0.085 * s)
        d.line((cx + 0.05 * s, cy - 0.22 * s, cx - 0.01 * s, cy + 0.05 * s), fill=col, width=int(0.14 * s))
        d.line((cx - 0.01 * s, cy + 0.03 * s, cx + 0.16 * s, cy + 0.22 * s), fill=col, width=w)
        d.line((cx + 0.16 * s, cy + 0.22 * s, cx + 0.18 * s, cy + 0.42 * s), fill=col, width=w)
        d.line((cx - 0.01 * s, cy + 0.03 * s, cx - 0.12 * s, cy + 0.24 * s), fill=col, width=w)
        d.line((cx - 0.12 * s, cy + 0.24 * s, cx - 0.24 * s, cy + 0.40 * s), fill=col, width=w)
        d.line((cx + 0.04 * s, cy - 0.17 * s, cx + 0.20 * s, cy - 0.02 * s), fill=col, width=int(0.07 * s))
        d.line((cx + 0.04 * s, cy - 0.17 * s, cx - 0.12 * s, cy - 0.05 * s), fill=col, width=int(0.07 * s))
    standing(128, 128, 220, (255, 52, 36))
    walking(384, 128, 220, (0, 220, 170))
    save(im.filter(ImageFilter.GaussianBlur(0.8)), 'prop_ped_signal_albedo.png')


def pole_ad():
    """Vertical utility-pole advertisement plate (fictional clinic), 128x512 (0.33 x 1.3 m)."""
    W, H = 256, 1024
    im = Image.new('RGB', (W, H), (246, 244, 236))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 150), fill=(18, 92, 170))
    text_center(d, (W / 2, 75), '歯科', font(size=96), (255, 255, 255))
    text_center(d, (W / 2, 520), 'さくら歯科', font(size=150), (20, 20, 24), vertical=True, spacing=8)
    d.rectangle((0, 880, W, H), fill=(214, 40, 36))
    text_center(d, (W / 2, 925), 'この先50m', font(size=50), (255, 255, 255))
    d.polygon([(W / 2 - 60, 975), (W / 2 + 40, 975), (W / 2 + 40, 955), (W / 2 + 90, 990),
               (W / 2 + 40, 1020), (W / 2 + 40, 1003), (W / 2 - 60, 1003)], fill=(255, 255, 255))
    d.rectangle((0, 0, W - 1, H - 1), outline=(60, 60, 60), width=4)
    save(grime(im.resize((128, 512), Image.LANCZOS), 6, 3), 'prop_pole_ad_albedo.png')


def street_name():
    """Intersection name plate (blue, white kanji + romaji), 512x256 (approx 1.2 x 0.6 m)."""
    W, H = 1024, 512
    im = Image.new('RGB', (W, H), (22, 74, 160))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((14, 14, W - 14, H - 14), radius=30, outline=(250, 250, 250), width=12)
    text_center(d, (W / 2, 205), '神宮前二丁目', font(size=150), (255, 255, 255))
    text_center(d, (W / 2, 390), 'Jingumae 2-chome', font('NotoSansJP-Bold.ttf', 84), (255, 255, 255))
    save(im.resize((512, 256), Image.LANCZOS), 'prop_street_name_albedo.png')


def hydrant_sign():
    """Tokyo-style fire hydrant sign 消火栓 (red board), 256x512 (0.4 x 0.8 m)."""
    W, H = 512, 1024
    im = Image.new('RGB', (W, H), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 640), fill=(214, 34, 28))
    d.rectangle((20, 20, W - 20, 620), outline=(255, 255, 255), width=10)
    text_center(d, (W / 2, 300), '消火栓', font(size=150), (255, 255, 255), vertical=True, spacing=6)
    text_center(d, (W / 2, 590), 'FIRE HYDRANT', font('NotoSansJP-Bold.ttf', 44), (255, 255, 255))
    # lower ad / info area
    text_center(d, (W / 2, 730), '駐車禁止', font(size=96), (214, 34, 28))
    text_center(d, (W / 2, 860), '消防署', font('NotoSansJP-Bold.ttf', 64), (40, 40, 40))
    d.rectangle((0, 0, W - 1, H - 1), outline=(80, 80, 80), width=6)
    save(grime(im.resize((256, 512), Image.LANCZOS), 5, 4), 'prop_hydrant_sign_albedo.png')


def manhole():
    """Tokyo-style decorative sewer manhole cover (sakura motif + ring grip pattern).
    512x512 albedo + OpenGL normal map. Disk fills the UV square."""
    S = 1024
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    cx = cy = (S - 1) / 2
    dx, dy = xx - cx, yy - cy
    r = np.sqrt(dx * dx + dy * dy) / (S / 2)
    th = np.arctan2(dy, dx)
    h = np.zeros((S, S), np.float32)
    # outer rim
    h += np.where((r > 0.93) & (r <= 1.0), 1.0, 0)
    # grip ring: small raised studs/hexes
    ring = (r > 0.70) & (r < 0.90)
    stud = (np.sin(th * 48) > 0.2) & (np.sin((r - 0.70) / 0.2 * math.pi * 4) > 0)
    h += np.where(ring & stud, 0.8, 0)
    h += np.where((r > 0.66) & (r < 0.70), 1.0, 0)
    # inner field: 5-petal sakura flowers arranged in a ring + centre flower
    def flower(fx, fy, R):
        ddx, ddy = xx - fx, yy - fy
        rr = np.sqrt(ddx * ddx + ddy * ddy) / R
        tt = np.arctan2(ddy, ddx)
        petal = 0.55 + 0.45 * np.abs(np.cos(tt * 2.5))
        notch = 1 - 0.18 * np.exp(-((np.mod(tt * 5 / (2 * math.pi), 1) - 0.5) ** 2) / 0.002)
        return ((rr < petal * notch) & (rr > 0.18)).astype(np.float32) * 0.9
    field = np.zeros_like(h)
    field = np.maximum(field, flower(cx, cy, S * 0.13))
    for k in range(6):
        a = k * math.pi / 3 + math.pi / 6
        field = np.maximum(field, flower(cx + math.cos(a) * S * 0.205, cy + math.sin(a) * S * 0.205, S * 0.075))
    # background waves (river lines) in the field
    waves = (np.sin(yy / S * 60 + np.sin(xx / S * 12) * 2) > 0.75).astype(np.float32) * 0.45
    inner = r < 0.66
    h += np.where(inner, np.maximum(field, waves * (field < 0.1)), 0)
    h = np.where(r > 1.0, 0, h)
    hb = np.asarray(Image.fromarray((np.clip(h, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0))).astype(np.float32) / 255
    # albedo: cast iron, raised parts polished lighter, recesses dark
    rng = np.random.default_rng(5)
    noise = np.asarray(Image.fromarray((rng.random((S // 8, S // 8)) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255
    base = 58 + 30 * noise
    col = base + hb * 70
    alb = np.stack([col * 1.0, col * 0.98, col * 0.93], -1)
    rust = np.clip((noise - 0.6) * 2.5, 0, 1) * (1 - hb)
    alb[..., 0] += rust * 35; alb[..., 1] += rust * 12
    alb = np.where((r > 1.0)[..., None], 60, alb)
    save(Image.fromarray(np.clip(alb, 0, 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS), 'prop_manhole_albedo.png')
    # normal map (OpenGL +Y up): image row 0 = top (v=1)
    gy, gx = np.gradient(hb * 6.0)
    nx = -gx; ny = gy; nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1)
    save(Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS), 'prop_manhole_normal.png')


def ped_button():
    """Pedestrian push-button box face (押ボタン式), 128x256."""
    W, H = 256, 512
    im = Image.new('RGB', (W, H), (243, 195, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, W - 10, H - 10), radius=18, outline=(30, 30, 30), width=6)
    text_center(d, (W / 2, 70), '押ボタン式', font(size=44), (20, 20, 20))
    d.ellipse((W / 2 - 62, 150, W / 2 + 62, 274), fill=(250, 250, 248), outline=(30, 30, 30), width=5)
    text_center(d, (W / 2, 330), 'おしてください', font('NotoSansJP-Bold.ttf', 32), (20, 20, 20))
    text_center(d, (W / 2, 395), 'PUSH BUTTON', font('NotoSansJP-Bold.ttf', 26), (20, 20, 20))
    text_center(d, (W / 2, 445), 'FOR GREEN', font('NotoSansJP-Bold.ttf', 26), (20, 20, 20))
    save(grime(im.resize((128, 256), Image.LANCZOS), 5, 7), 'prop_ped_button_albedo.png')


def hydrant_lid():
    """Yellow painted fire-hydrant lid (消火栓) Φ0.6, 512x512, disk fills the square."""
    S = 1024
    im = Image.new('RGB', (S, S), (60, 58, 55))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, S - 4, S - 4), fill=(72, 70, 66))
    d.ellipse((40, 40, S - 40, S - 40), fill=(238, 196, 20))
    # anti-slip studs ring
    for k in range(64):
        a = 2 * math.pi * k / 64
        x, y = S / 2 + math.cos(a) * 430, S / 2 + math.sin(a) * 430
        d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(200, 160, 10))
    text_center(d, (S / 2, S / 2 - 20), '消火栓', font(size=230), (30, 28, 26))
    text_center(d, (S / 2, S / 2 + 200), 'FIRE HYDRANT', font('NotoSansJP-Bold.ttf', 70), (30, 28, 26))
    im = grime(im, 14, 9)
    save(im.resize((512, 512), Image.LANCZOS), 'prop_hydrant_lid_albedo.png')


def parking_sign():
    """Coin-parking sign (fictional operator), 512x512 square face."""
    S = 1024
    im = Image.new('RGB', (S, S), (250, 214, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((60, 40, S - 60, 700), radius=60, fill=(20, 70, 160))
    text_center(d, (S / 2, 360), 'P', font('DelaGothicOne-Regular.ttf', 560), (255, 255, 255))
    text_center(d, (S / 2, 790), '24H  ¥220/20分', font(size=92), (20, 20, 24))
    text_center(d, (S / 2, 920), 'コインパーキング', font(size=84), (20, 20, 24))
    save(im.resize((512, 512), Image.LANCZOS), 'prop_parking_sign_albedo.png')


if __name__ == '__main__':
    hydrant_lid()
    parking_sign()
    ped_button()
    hazard_stripe()
    ped_signal()
    pole_ad()
    street_name()
    hydrant_sign()
    manhole()
