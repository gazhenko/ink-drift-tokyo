"""Procedural decal textures for street props (urban set B).
Run:  Tools/.venv/bin/python Tools/blender/props/make_textures_urban_b.py
Writes power-of-two PNGs to Game/Assets/InkDrift/Models/Props/Textures/ (prop_<name>_albedo.png).
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
    print('wrote', p, img.size, img.mode)


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


def noise_img(w, h, scale=8, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.random((max(2, h // scale), max(2, w // scale)))
    return np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)).astype(np.float32) / 255


def grime(img, amount=10, seed=1):
    a = np.asarray(img).astype(np.float32)
    n = (noise_img(a.shape[1], a.shape[0], 6, seed) - 0.5) * amount
    a[..., :3] = np.clip(a[..., :3] + n[..., None], 0, 255)
    return Image.fromarray(a.astype(np.uint8), img.mode)


def awning(name, col, white=(244, 242, 234)):
    """Tileable canvas stripe: left half colour, right half white. One repeat = 0.5 m of width."""
    S = 256
    a = np.zeros((S, S, 3), np.float32)
    a[:, :S // 2] = col
    a[:, S // 2:] = white
    # woven canvas texture (fine cross hatch), tileable
    y, x = np.mgrid[0:S, 0:S]
    weave = (np.sin(x * 2 * math.pi / 4) * np.sin(y * 2 * math.pi / 4)) * 4
    a += weave[..., None]
    # tiny seam line at stripe borders
    for xs in (0, S // 2):
        a[:, max(xs - 1, 0):xs + 1] *= 0.9
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    save(im, name)


def lantern(name, W, H, chars_front, chars_back, size_front, size_back, base=(206, 30, 24)):
    """Cylindrical-wrap lantern texture: u=0.5 faces the viewer (front), u=0/1 = back.
    Faint horizontal bamboo rib shading; v=0 bottom, v=1 top."""
    a = np.zeros((H, W, 3), np.float32)
    a[:] = base
    y = np.arange(H)[:, None]
    ribs = 0.92 + 0.08 * np.cos(y / H * 2 * math.pi * 14)
    a *= ribs[..., None]
    # darker towards caps
    t = np.abs((y / (H - 1)) - 0.5) * 2
    a *= (1 - 0.25 * t ** 3)[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    black = (16, 12, 12)
    text_center(d, (W / 2, H / 2), chars_front, font('ReggaeOne-Regular.ttf', size_front), black,
                vertical=len(chars_front) > 1, spacing=4)
    if chars_back:
        for cx in (0, W):
            text_center(d, (cx, H / 2), chars_back, font('ReggaeOne-Regular.ttf', size_back), black,
                        vertical=len(chars_back) > 1, spacing=4)
    save(grime(im, 8, 7), name)


def noren():
    """Indigo noren across 4 panels (u 0..1 spans the whole curtain, v up), white characters らーめん."""
    W, H = 1024, 512
    im = Image.new('RGB', (W, H), (28, 40, 86))
    d = ImageDraw.Draw(im)
    # top band (sleeve) slightly darker
    d.rectangle((0, 0, W, int(H * 0.13)), fill=(22, 31, 68))
    chars = ['ら', 'ー', 'め', 'ん']
    pw = W / 4
    for i, ch in enumerate(chars):
        cx = pw * (i + 0.5)
        text_center(d, (cx, H * 0.56), ch, font('NotoSansJP-Black.ttf', 190), (246, 244, 236))
    # small white crest circle on first panel top + shop name strip on last
    d.ellipse((pw * 0.5 - 34, H * 0.2 - 34, pw * 0.5 + 34, H * 0.2 + 34), outline=(246, 244, 236), width=8)
    text_center(d, (pw * 0.5, H * 0.2), '麺', font('NotoSansJP-Black.ttf', 40), (246, 244, 236))
    text_center(d, (pw * 3.5, H * 0.88), '営業中', font('NotoSansJP-Bold.ttf', 44), (246, 244, 236))
    save(grime(im, 10, 8), 'prop_noren_albedo.png')


def postbox_label():
    """512x512 atlas.  TL: white 〒 on red.  TR: 郵便/POST white on red.
    BL: white collection-time plate.  BR top: 手紙・はがき, BR bottom: 速達・大型郵便 (white on red)."""
    S = 512
    red = (200, 30, 26)
    im = Image.new('RGB', (S, S), red)
    d = ImageDraw.Draw(im)
    h = S // 2
    text_center(d, (h / 2, h / 2), '〒', font('NotoSansJP-Black.ttf', 200), (255, 255, 255))
    text_center(d, (h + h / 2, h / 2 - 40), '郵便', font('NotoSansJP-Black.ttf', 92), (255, 255, 255))
    text_center(d, (h + h / 2, h / 2 + 70), 'POST', font('NotoSansJP-Black.ttf', 64), (255, 255, 255))
    # collection time plate
    d.rectangle((0, h, h, S), fill=(246, 246, 240))
    d.rectangle((8, h + 8, h - 8, S - 8), outline=(40, 40, 40), width=4)
    text_center(d, (h / 2, h + 40), '取集時刻', font('NotoSansJP-Black.ttf', 40), (30, 30, 30))
    for k, t in enumerate(('平日 10:30', '　　 15:00', '休日 11:00')):
        text_center(d, (h / 2, h + 100 + k * 50), t, font('NotoSansJP-Bold.ttf', 34), (30, 30, 30))
    text_center(d, (h + h / 2, h + h / 4), '手紙・はがき', font('NotoSansJP-Black.ttf', 40), (255, 255, 255))
    d.line((h, h + h / 2, S, h + h / 2), fill=(150, 20, 18), width=4)
    text_center(d, (h + h / 2, h + 3 * h / 4), '速達・大型郵便', font('NotoSansJP-Black.ttf', 34), (255, 255, 255))
    save(grime(im, 6, 9), 'prop_postbox_label_albedo.png')


def wiremesh(name, col, pitch_px, wire_px):
    """Tileable RGBA welded wire mesh (alpha-cutout). 256 px = 1 m with UV.box()."""
    S = 256
    a = np.zeros((S, S, 4), np.uint8)
    y, x = np.mgrid[0:S, 0:S]
    m = ((x % pitch_px) < wire_px) | ((y % pitch_px) < wire_px)
    shade = 1.0 - 0.25 * (((x % pitch_px) < wire_px) & ((y % pitch_px) < wire_px))
    for c in range(3):
        a[..., c] = np.clip(col[c] * shade, 0, 255)
    a[..., 3] = np.where(m, 255, 0)
    save(Image.fromarray(a, 'RGBA'), name)


def recycle_label():
    S = 256
    im = Image.new('RGB', (S, S), (246, 246, 242))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, S, 70), fill=(24, 92, 170))
    text_center(d, (S / 2, 35), 'リサイクル', font('NotoSansJP-Black.ttf', 40), (255, 255, 255))
    text_center(d, (S / 2, 120), 'あき缶', font('NotoSansJP-Black.ttf', 48), (24, 92, 170))
    text_center(d, (S / 2, 180), 'ペットボトル', font('NotoSansJP-Black.ttf', 38), (24, 92, 170))
    text_center(d, (S / 2, 228), 'CANS / BOTTLES', font('NotoSansJP-Bold.ttf', 22), (60, 60, 60))
    save(grime(im, 5, 11), 'prop_recycle_label_albedo.png')


def garbage_sign():
    W, H = 512, 256
    im = Image.new('RGB', (W, H), (246, 246, 240))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 86), fill=(30, 120, 64))
    text_center(d, (W / 2, 43), 'ごみ集積所', font('NotoSansJP-Black.ttf', 62), (255, 255, 255))
    text_center(d, (W / 2, 128), '燃やすごみ　月・木', font('NotoSansJP-Black.ttf', 40), (30, 30, 30))
    text_center(d, (W / 2, 180), '資源ごみ　水', font('NotoSansJP-Black.ttf', 40), (30, 30, 30))
    text_center(d, (W / 2, 228), '朝8時までに出してください', font('NotoSansJP-Bold.ttf', 26), (200, 40, 30))
    d.rectangle((0, 0, W - 1, H - 1), outline=(40, 40, 40), width=4)
    save(grime(im, 6, 12), 'prop_garbage_sign_albedo.png')


def hv_warning():
    W, H = 256, 128
    im = Image.new('RGB', (W, H), (250, 210, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((4, 4, W - 5, H - 5), outline=(20, 20, 20), width=6)
    # lightning bolt triangle
    d.polygon([(64, 18), (14, 110), (114, 110)], outline=(20, 20, 20), fill=(250, 210, 0), width=6)
    d.polygon([(70, 40), (52, 74), (66, 74), (54, 102), (80, 64), (66, 64), (78, 40)], fill=(20, 20, 20))
    text_center(d, (186, 44), '危険', font('NotoSansJP-Black.ttf', 44), (20, 20, 20))
    text_center(d, (186, 92), '高電圧', font('NotoSansJP-Black.ttf', 34), (20, 20, 20))
    save(im, 'prop_hv_warning_albedo.png')


if __name__ == '__main__':
    awning('prop_awning_redwhite_albedo.png', (196, 32, 36))
    awning('prop_awning_greenwhite_albedo.png', (28, 112, 70))
    lantern('prop_chochin_matsuri_albedo.png', 512, 256, '祭', '祭', 150, 150)
    lantern('prop_akachochin_albedo.png', 1024, 512, '焼鳥', '酒', 190, 300)
    noren()
    postbox_label()
    wiremesh('prop_wiremesh_green_albedo.png', (46, 104, 70), 13, 2)
    wiremesh('prop_wiremesh_silver_albedo.png', (188, 192, 196), 10, 2)
    recycle_label()
    garbage_sign()
    hv_warning()
