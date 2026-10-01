#!/usr/bin/env python3
"""Download Sketchfab thumbnails (public) and build labelled contact sheets.

Usage:
  Tools/.venv/bin/python Tools/cars/thumbs.py search <slot> [uid ...]   # sheet of search results
  Tools/.venv/bin/python Tools/cars/thumbs.py shortlist                  # thumbs for shortlist.json
Thumbnails -> Tools/cars/thumbs/<uid>.jpg ; sheets -> Tools/cars/cache/sheets/<slot>_<n>.jpg
"""
import json
import os
import sys

import requests
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
THUMBS = os.path.join(HERE, "thumbs")  # shortlist thumbs (search sheets use cache/thumbs)
CACHE_THUMBS = os.path.join(HERE, "cache", "thumbs")
SHEETS = os.path.join(HERE, "cache", "sheets")
FONT = os.path.join(HERE, "..", "..", "Game", "Assets", "InkDrift", "Art", "Fonts", "ChakraPetch-Bold.ttf")


def fetch(uid, url, folder=None):
    folder = folder or CACHE_THUMBS
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, f"{uid}.jpg")
    if not os.path.exists(p) and url:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(p, "wb") as f:
            f.write(r.content)
    return p


def sheet(rows, name, cols=3, tw=640, th=360, folder=None):
    os.makedirs(SHEETS, exist_ok=True)
    font = ImageFont.truetype(FONT, 18)
    per = cols * 3
    out = []
    for n in range(0, len(rows), per):
        chunk = rows[n:n + per]
        nrows = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (cols * tw, nrows * (th + 46)), "white")
        d = ImageDraw.Draw(img)
        for i, r in enumerate(chunk):
            x, y = (i % cols) * tw, (i // cols) * (th + 46)
            try:
                t = Image.open(fetch(r["uid"], r["thumbnail"], folder)).convert("RGB")
                t.thumbnail((tw, th))
                img.paste(t, (x + (tw - t.width) // 2, y))
            except Exception as e:  # noqa
                d.text((x + 10, y + 10), f"ERR {e}", fill="red", font=font)
            lic = (r.get("license") or {}).get("slug")
            d.text((x + 4, y + th + 2), f"{n + i}: {r['name'][:38]}", fill="black", font=font)
            d.text((x + 4, y + th + 22), f"{r['uid'][:8]} {lic} {r.get('faceCount')}f {r.get('author')}"[:60],
                   fill="black", font=font)
        p = os.path.join(SHEETS, f"{name}_{n // per}.jpg")
        img.save(p, quality=85)
        out.append(p)
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "search":
        slot = sys.argv[2]
        rows = json.load(open(os.path.join(HERE, "cache", "search", f"{slot}.json")))
        want = sys.argv[3:]
        if want:
            rows = [r for r in rows if any(r["uid"].startswith(w) for w in want)]
        for p in sheet(rows, slot):
            print(p)
    elif mode == "shortlist":
        sl = json.load(open(os.path.join(HERE, "shortlist.json")))
        for slot, entry in sl["cars"].items():
            rows = entry["candidates"]
            for r in rows:
                fetch(r["uid"], r["thumbnail"], THUMBS)
            for p in sheet(rows, f"shortlist_{slot}", folder=THUMBS):
                print(p)
