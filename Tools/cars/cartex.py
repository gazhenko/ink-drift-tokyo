#!/usr/bin/env python3
"""Car texture helpers for INK DRIFT: TOKYO (run with Tools/.venv/bin/python).

  cartex.py plate  <out.png> <style> "<region class>" "<kana>" "<number>"
        style: private (white/green) | kei (yellow/black) | commercial (green/white)
               | kei_commercial (black/yellow)
        e.g.   cartex.py plate out.png private "品川 300" "あ" "86-86"
  cartex.py atlas  <out.png> <out.json> <banner text|-> <banner accent hex> <decal.png> ...
        Packs the decals (cropped to their alpha bbox) + an optional generated windshield
        banner into one 2048x2048 RGBA atlas; writes the UV rect of each item to JSON
        (keys = file stem, "banner"), UV origin bottom-left (Blender convention).
  cartex.py sheet  <out.jpg> <img> ...   simple preview contact sheet (2 columns)
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FONTS = os.path.join(REPO, "Game", "Assets", "InkDrift", "Art", "Fonts")
NOTO_BOLD = os.path.join(FONTS, "NotoSansJP-Bold.ttf")
NOTO_BLACK = os.path.join(FONTS, "NotoSansJP-Black.ttf")
DELA = os.path.join(FONTS, "DelaGothicOne-Regular.ttf")

INK = (11, 11, 18)
PAPER = (255, 248, 231)
MAGENTA = (255, 45, 122)
CYAN = (0, 229, 255)

PLATE_STYLES = {
    # background, text, border
    "private": ((246, 246, 240), (18, 92, 52), (18, 92, 52)),
    "kei": ((250, 210, 30), (20, 20, 20), (20, 20, 20)),
    "commercial": ((18, 92, 52), (246, 246, 240), (246, 246, 240)),
    "kei_commercial": ((22, 22, 22), (250, 210, 30), (250, 210, 30)),
}


def _fit_font(path, text, max_w, max_h, start=400):
    size = start
    while size > 8:
        f = ImageFont.truetype(path, size)
        l, t, r, b = f.getbbox(text)
        if r - l <= max_w and b - t <= max_h:
            return f
        size -= 2
    return ImageFont.truetype(path, 8)


def _draw_centered(d, box, text, font, fill, stretch_w=None):
    l, t, r, b = font.getbbox(text)
    x0, y0, x1, y1 = box
    x = x0 + (x1 - x0 - (r - l)) / 2 - l
    y = y0 + (y1 - y0 - (b - t)) / 2 - t
    d.text((x, y), text, font=font, fill=fill)


def make_plate(out, style, top, kana, num, w=1024, h=512):
    """Japanese 'medium' plate 330x165 mm (2:1). Layout follows the real one: region + class
    number on top, hiragana small at left, big 4-digit serial number."""
    bg, fg, border = PLATE_STYLES[style]
    ss = 2
    W, H = w * ss, h * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(0.06 * H)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=bg)
    m = int(0.035 * H)
    d.rounded_rectangle((m, m, W - 1 - m, H - 1 - m), radius=r - m // 2, outline=border, width=max(2, int(0.012 * H)))
    # bolts
    for bx in (0.2, 0.8):
        cx, cy, br = bx * W, 0.12 * H, 0.045 * H
        d.ellipse((cx - br, cy - br, cx + br, cy + br), fill=(170, 170, 175), outline=(90, 90, 95), width=3)
        d.line((cx - br * 0.6, cy, cx + br * 0.6, cy), fill=(90, 90, 95), width=4)
    # top line: region + class number
    ft = _fit_font(NOTO_BOLD, top, 0.52 * W, 0.24 * H)
    _draw_centered(d, (0.22 * W, 0.06 * H, 0.78 * W, 0.36 * H), top, ft, fg)
    # kana
    fk = _fit_font(NOTO_BOLD, kana, 0.12 * W, 0.24 * H)
    _draw_centered(d, (0.04 * W, 0.50 * H, 0.17 * W, 0.86 * H), kana, fk, fg)
    # big number (slightly condensed like the real plate font)
    fn = ImageFont.truetype(NOTO_BOLD, int(0.62 * H))
    l, t, rr, b = fn.getbbox(num)
    tmp = Image.new("RGBA", (rr - l + 20, b - t + 20), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10 - l, 10 - t), num, font=fn, fill=fg)
    tw, th = int(0.76 * W), int(0.56 * H)
    tmp = tmp.resize((tw, th), Image.LANCZOS)
    img.alpha_composite(tmp, (int(0.20 * W), int(0.37 * H)))
    img = img.resize((w, h), Image.LANCZOS)
    # pad to POT square-ish: keep 1024x512 (POT both sides)
    img.save(out)


def make_banner(text, accent, w=2048, h=256):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, h), fill=INK + (255,))
    d.rectangle((0, h - 22, w, h), fill=accent + (255,))
    d.rectangle((0, 0, w, 10), fill=accent + (255,))
    f = _fit_font(DELA, text, int(0.92 * w), int(0.56 * h), start=220)
    l, t, r, b = f.getbbox(text)
    x = (w - (r - l)) / 2 - l
    y = (h - 22 + 10 - (b - t)) / 2 - t
    # comic offset shadow + paper text
    d.text((x + 8, y + 7), text, font=f, fill=accent + (255,))
    d.text((x, y), text, font=f, fill=PAPER + (255,), stroke_width=3, stroke_fill=INK + (255,))
    return img


def make_atlas(out_png, out_json, banner_text, banner_accent, paths, size=2048):
    items = []
    if banner_text and banner_text != "-":
        acc = tuple(int(banner_accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        items.append(("banner", make_banner(banner_text, acc, size, size // 8)))
    for p in paths:
        im = Image.open(p).convert("RGBA")
        bb = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if bb:
            pad = 6
            bb = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))
            im = im.crop(bb)
        items.append((os.path.splitext(os.path.basename(p))[0], im))
    # shelf packing; scale decals down uniformly until everything fits
    scale = 1.0
    while True:
        placed, x, y, shelf_h, ok = {}, 0, 0, 0, True
        order = [items[0]] + sorted(items[1:], key=lambda it: -it[1].height) if items and items[0][0] == "banner" \
            else sorted(items, key=lambda it: -it[1].height)
        for name, im in order:
            s = 1.0 if name == "banner" else scale
            w, h = max(1, int(im.width * s)), max(1, int(im.height * s))
            if x + w > size:
                x, y, shelf_h = 0, y + shelf_h + 4, 0
            if y + h > size:
                ok = False
                break
            placed[name] = (x, y, w, h, im)
            x += w + 4
            shelf_h = max(shelf_h, h)
        if ok:
            break
        scale *= 0.92
    atlas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rects = {}
    for name, (x, y, w, h, im) in placed.items():
        atlas.alpha_composite(im.resize((w, h), Image.LANCZOS), (x, y))
        # UV rect (u0, v0, u1, v1), v up from bottom; inset half a texel
        rects[name] = [(x + 0.5) / size, 1 - (y + h - 0.5) / size, (x + w - 0.5) / size, 1 - (y + 0.5) / size,
                       w / h]
    # dilate colour into transparent texels so mip-maps don't get dark fringes
    rgb = atlas.convert("RGB")
    a = atlas.getchannel("A")
    bleed = rgb
    for _ in range(4):
        bleed = bleed.filter(ImageFilter.MaxFilter(5))
    base = Image.composite(rgb, bleed, a.point(lambda v: 255 if v > 0 else 0))
    base.putalpha(a)
    base.save(out_png)
    with open(out_json, "w") as f:
        json.dump(rects, f, indent=1)


def sheet(out, paths, cols=2, w=1280):
    ims = [Image.open(p).convert("RGB") for p in paths]
    tw = w // cols
    th = int(tw * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    s = Image.new("RGB", (cols * tw, rows * th), "white")
    for i, im in enumerate(ims):
        s.paste(im.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    s.save(out, quality=88)


def texsheet(out, paths, tw=384):
    """labelled grid of textures (for spotting logos/brand text baked into source textures)"""
    cols = 5
    rows = (len(paths) + cols - 1) // cols
    s = Image.new("RGB", (cols * tw, max(1, rows) * (tw + 24)), (60, 60, 66))
    d = ImageDraw.Draw(s)
    f = ImageFont.truetype(NOTO_BOLD, 14)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
        bg.alpha_composite(im)
        im = bg.convert("RGB")
        im.thumbnail((tw, tw))
        x, y = (i % cols) * tw, (i // cols) * (tw + 24)
        s.paste(im, (x, y))
        d.text((x + 2, y + tw + 2), os.path.basename(p)[:44], fill="white", font=f)
    s.save(out, quality=88)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "plate":
        make_plate(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
    elif cmd == "atlas":
        make_atlas(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:])
    elif cmd == "sheet":
        sheet(sys.argv[2], sys.argv[3:])
    elif cmd == "texsheet":
        texsheet(sys.argv[2], sys.argv[3:])
    else:
        raise SystemExit(__doc__)
