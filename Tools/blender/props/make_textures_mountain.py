"""Procedural decal textures for the mountain + shrine props.
Run:  Tools/.venv/bin/python Tools/blender/props/make_textures_mountain.py
Writes PNGs to Game/Assets/InkDrift/Models/Props/Textures/ (prop_<name>_albedo.png).
Original procedural artwork; fonts are the repo's OFL fonts (Art/Fonts)."""
import os
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


def vtext(d, cx, cy, s, f, fill, spacing=0, box_h=None):
    """Vertical (tategaki) text centred at (cx, cy); optionally spread over box_h."""
    hs = []
    for ch in s:
        b = d.textbbox((0, 0), ch, font=f)
        hs.append(b[3] - b[1])
    if box_h is not None and len(s) > 1:
        spacing = (box_h - sum(hs)) / (len(s) - 1)
    tot = sum(hs) + spacing * (len(s) - 1)
    y = cy - tot / 2
    for ch, h in zip(s, hs):
        b = d.textbbox((0, 0), ch, font=f)
        d.text((cx - (b[2] + b[0]) / 2, y - b[1]), ch, font=f, fill=fill)
        y += h + spacing


def noise(shape, scale, seed):
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, shape[0] // scale), max(2, shape[1] // scale)))
    im = Image.fromarray((small * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.asarray(im).astype(np.float32) / 255.0


def emboss_text(size, draw_fn, base_rgb, text_rgb, seed=1, relief=1.0):
    """Draw a mask with draw_fn(ImageDraw, W, H) (white = raised), then shade it like cast/carved relief."""
    W, H = size
    m = Image.new('L', (W, H), 0)
    draw_fn(ImageDraw.Draw(m), W, H)
    mb = np.asarray(m.filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
    gy, gx = np.gradient(mb)
    light = np.clip((-gx - gy) * 6 * relief, -1, 1)
    n = noise((H, W), 8, seed) * 0.5 + noise((H, W), 32, seed + 1) * 0.5
    base = np.array(base_rgb, np.float32)[None, None, :] * (0.85 + 0.3 * n[..., None])
    txt = np.array(text_rgb, np.float32)[None, None, :] * (0.9 + 0.2 * n[..., None])
    a = mb[..., None]
    col = base * (1 - a) + txt * a
    col = col * (1 + 0.35 * light[..., None])
    return Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))


def bridge_plate():
    """512x512 atlas: left half kanji 峠沢橋, right half hiragana とうげさわばし (cast bronze plates)."""
    W, H = 256, 512

    def kanji(d, w, h):
        d.rectangle((10, 10, w - 10, h - 10), outline=255, width=8)
        vtext(d, w / 2, h / 2, '峠沢橋', font('NotoSansJP-Black.ttf', 150), 255, box_h=h - 90)

    def kana(d, w, h):
        d.rectangle((10, 10, w - 10, h - 10), outline=255, width=8)
        vtext(d, w / 2, h / 2, 'とうげさわばし', font('NotoSansJP-Bold.ttf', 58), 255, box_h=h - 70)
    bronze = (92, 66, 38)
    raised = (176, 138, 82)
    a = emboss_text((W, H), kanji, bronze, raised, seed=3)
    b = emboss_text((W, H), kana, bronze, raised, seed=4)
    im = Image.new('RGB', (512, 512))
    im.paste(a, (0, 0)); im.paste(b, (256, 0))
    save(im, 'prop_bridge_plate_albedo.png')


def shrine_plaque():
    """256x512 torii plaque (額): black lacquer with gold border and 山神社."""
    W, H = 256, 512

    def draw(d, w, h):
        d.rectangle((8, 8, w - 8, h - 8), outline=255, width=10)
        d.rectangle((26, 26, w - 26, h - 26), outline=255, width=3)
        vtext(d, w / 2, h / 2, '山神社', font('NotoSansJP-Black.ttf', 130), 255, box_h=h - 120)
    save(emboss_text((W, H), draw, (24, 22, 22), (214, 172, 72), seed=7), 'prop_shrine_plaque_albedo.png')


def saisen():
    """512x256 offering-box front plate: gold 賽銭 on dark wood."""
    W, H = 512, 256

    def draw(d, w, h):
        d.rectangle((10, 10, w - 10, h - 10), outline=255, width=8)
        f = font('NotoSansJP-Black.ttf', 150)
        for i, ch in enumerate('賽銭'):
            b = d.textbbox((0, 0), ch, font=f)
            cx = w * (0.3 + 0.4 * i)
            d.text((cx - (b[2] + b[0]) / 2, h / 2 - (b[3] + b[1]) / 2), ch, font=f, fill=255)
    im = emboss_text((W, H), draw, (62, 36, 20), (212, 170, 70), seed=9)
    # wood grain
    a = np.asarray(im).astype(np.float32)
    y = np.arange(H)[:, None]
    x = np.arange(W)[None, :]
    grain = 0.5 + 0.5 * np.sin(y * 0.35 + np.sin(x * 0.01) * 6 + noise((H, W), 16, 2) * 4)
    a *= (0.92 + 0.12 * grain)[..., None]
    save(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), 'prop_saisen_albedo.png')


def snow_arrow():
    """256x512 arrow plate (矢羽根): red/white diagonal chevron stripes pointing down."""
    W, H = 256, 512
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    # chevron bands pointing down: band index from (y + |x - W/2|)
    t = (y + np.abs(x - W / 2) * 0.9) / 96.0
    band = np.floor(t).astype(int) % 2
    img = np.zeros((H, W, 3), np.uint8)
    img[band == 0] = (222, 34, 30)
    img[band == 1] = (248, 248, 244)
    im = Image.fromarray(img).filter(ImageFilter.GaussianBlur(0.7))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=(240, 240, 236), width=6)
    save(im, 'prop_snow_arrow_albedo.png')


if __name__ == '__main__':
    bridge_plate()
    shrine_plaque()
    saisen()
    snow_arrow()
