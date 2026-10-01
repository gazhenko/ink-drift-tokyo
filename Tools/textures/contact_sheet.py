#!/usr/bin/env python3
"""Contact sheet of every processed material set (albedo + mask/normal strips) and HDRI.

Usage: Tools/.venv/bin/python Tools/textures/contact_sheet.py [--maps]
Writes Tools/textures/contact_sheet.png. With --maps each tile also shows normal / metal / AO / height /
smoothness thumbnails under the albedo (handy for spotting broken channels).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEX = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art", "Textures")
HDRI = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art", "HDRI")
OUT = os.path.join(HERE, "contact_sheet.png")
T = 256
LABEL = 20


def font(sz=14):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def thumb(path, size, mode=None):
    im = Image.open(path)
    if mode:
        im = im.convert(mode)
    im.thumbnail(size, Image.LANCZOS)
    return im


def tonemap_hdr(path, width=512):
    hdr = cv2.imread(path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
    if hdr is None:
        return None
    h = int(width / 2)
    hdr = cv2.resize(hdr, (width, h), interpolation=cv2.INTER_AREA)
    lum = 0.2126 * hdr[..., 2] + 0.7152 * hdr[..., 1] + 0.0722 * hdr[..., 0]
    key = np.exp(np.mean(np.log(lum + 1e-4)))
    x = hdr * (0.18 / key)
    x = x / (1.0 + x)
    x = np.power(np.clip(x, 0, 1), 1 / 2.2)
    return Image.fromarray((x[..., ::-1] * 255).astype(np.uint8))


def main():
    show_maps = "--maps" in sys.argv
    sets = sorted(d for d in os.listdir(TEX) if os.path.isdir(os.path.join(TEX, d)))
    cols = 6
    strip = T // 5 if show_maps else 0
    cell_h = LABEL + T + strip
    rows = (len(sets) + cols - 1) // cols
    hdris = sorted(f for f in os.listdir(HDRI) if f.lower().endswith((".hdr", ".exr"))) if os.path.isdir(HDRI) else []
    hdri_rows = (len(hdris) + 2) // 3
    W = cols * T
    H = rows * cell_h + (hdri_rows * (LABEL + 256) + 30 if hdris else 0)
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f = font(14)
    for i, s in enumerate(sets):
        x, y = (i % cols) * T, (i // cols) * cell_h
        folder = os.path.join(TEX, s)
        alb = next((os.path.join(folder, n) for n in os.listdir(folder) if "_albedo." in n), None)
        d.text((x + 4, y + 3), s, fill=(255, 255, 255), font=f)
        if alb:
            sheet.paste(thumb(alb, (T, T), "RGB"), (x, y + LABEL))
        if show_maps:
            q = T // 5
            nrm = os.path.join(folder, f"{s}_normal.png")
            msk = os.path.join(folder, f"{s}_mask.png")
            tiles = []
            if os.path.exists(nrm):
                tiles.append(thumb(nrm, (q, q), "RGB"))
            if os.path.exists(msk):
                m = Image.open(msk)
                r, g, b, a = m.split()
                for ch in (r, g, b, a):  # metal, AO, height, smoothness
                    c = ch.copy()
                    c.thumbnail((q, q))
                    tiles.append(c.convert("RGB"))
            for j, t in enumerate(tiles):  # normal, metal, AO, height, smoothness
                sheet.paste(t, (x + j * q, y + LABEL + T))
    if hdris:
        y0 = rows * cell_h + 10
        d.text((4, y0), "HDRIs (Reinhard tonemapped preview)", fill=(255, 220, 120), font=f)
        y0 += 20
        for i, h in enumerate(hdris):
            x, y = (i % 3) * 512, y0 + (i // 3) * (LABEL + 256)
            d.text((x + 4, y + 3), h, fill=(255, 255, 255), font=f)
            im = tonemap_hdr(os.path.join(HDRI, h))
            if im:
                sheet.paste(im, (x, y + LABEL))
    sheet.save(OUT)
    print(OUT, sheet.size)


if __name__ == "__main__":
    main()
