#!/usr/bin/env python3
"""Build a labeled thumbnail grid of candidate CC0 materials for visual selection.

Usage:
  Tools/.venv/bin/python Tools/textures/preview_candidates.py OUT.png ph:clean_asphalt acg:Asphalt026A ...

Sources: Poly Haven (ph:) thumbnails from cdn.polyhaven.com, ambientCG (acg:) thumbnails.
Thumbnails are cached under Tools/textures/cache/thumbs/.
"""
import io
import os
import sys

import requests
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache", "thumbs")
UA = {"User-Agent": "InkDriftTokyo-asset-fetch/1.0"}
TILE = 256


def thumb(spec):
    src, aid = spec.split(":", 1)
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{src}_{aid}.png")
    if not os.path.exists(path):
        if src == "ph":
            url = f"https://cdn.polyhaven.com/asset_img/thumbs/{aid}.png?width=256&height=256"
        elif src == "phhdri":
            url = f"https://cdn.polyhaven.com/asset_img/thumbs/{aid}.png?width=512&height=256"
        else:
            url = f"https://acg-media.struffelproductions.com/file/ambientCG-Web/media/thumbnail/256-PNG/{aid}.png"
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        Image.open(io.BytesIO(r.content)).convert("RGB").save(path)
    return Image.open(path).convert("RGB")


def main():
    out = sys.argv[1]
    specs = sys.argv[2:]
    cols = 6
    wide = any(s.startswith("phhdri:") for s in specs)
    tw = TILE * 2 if wide else TILE
    if wide:
        cols = 3
    rows = (len(specs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (TILE + 22)), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    for i, s in enumerate(specs):
        x, y = (i % cols) * tw, (i // cols) * (TILE + 22)
        try:
            im = thumb(s)
            im.thumbnail((tw, TILE))
            sheet.paste(im, (x, y + 22))
        except Exception as e:  # noqa: BLE001
            d.text((x + 4, y + 60), f"ERR {e}"[:40], fill=(255, 80, 80), font=font)
        d.text((x + 4, y + 3), s, fill=(255, 255, 255), font=font)
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
