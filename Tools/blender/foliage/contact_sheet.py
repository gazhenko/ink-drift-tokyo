#!/usr/bin/env python3
"""Contact sheet of all foliage previews.  Run: Tools/.venv/bin/python Tools/blender/foliage/contact_sheet.py
Reads previews/<Name>.png + previews/stats/<Name>.json, writes previews/contact_sheet.png."""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PREV = os.path.join(HERE, "previews")
ORDER = ["Sakura", "Keyaki", "Ginkgo", "Momiji", "Sugi", "Kuromatsu", "Bamboo", "Hedge", "Bush", "Grass", "Fern",
         "Susuki", "Weeds", "Litter", "Rock", "Cliff"]


def font(sz):
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def key(n):
    for i, p in enumerate(ORDER):
        if n.startswith(p):
            return (i, n)
    return (99, n)


def main(cols=7, cell=360):
    names = sorted([f[:-4] for f in os.listdir(PREV) if f.endswith(".png") and f != "contact_sheet.png"
                    and not f.startswith("scene_")], key=key)
    rows = (len(names) + cols - 1) // cols
    lab = 46
    sheet = Image.new("RGB", (cols * cell, rows * (cell + lab) + 60), (24, 22, 34))
    d = ImageDraw.Draw(sheet)
    d.text((14, 14), "INK DRIFT: TOKYO - foliage / rocks (toon preview: N.L from custom normals, 3 bands, vertex AO)",
           font=font(26), fill=(255, 248, 231))
    f1, f2 = font(19), font(15)
    for i, n in enumerate(names):
        x, y = (i % cols) * cell, 60 + (i // cols) * (cell + lab)
        im = Image.open(os.path.join(PREV, n + ".png")).convert("RGB").resize((cell - 6, cell - 6), Image.LANCZOS)
        sheet.paste(im, (x + 3, y + 3))
        info = ""
        sp = os.path.join(PREV, "stats", n + ".json")
        if os.path.exists(sp):
            st = json.load(open(sp))
            objs = st.get("objects", [])
            tris = " / ".join(str(o["tris"]) for o in objs)
            sz = objs[0]["size"] if objs else [0, 0, 0]
            ok = st.get("verify", {}).get("ok")
            info = f"{tris} tris   {sz[0]:.1f}x{sz[1]:.1f}x{sz[2]:.1f} m   {'reimport OK' if ok else 'reimport ?'}"
        d.text((x + 8, y + cell + 2), n, font=f1, fill=(255, 45, 122))
        d.text((x + 8, y + cell + 24), info, font=f2, fill=(220, 220, 230))
    out = os.path.join(PREV, "contact_sheet.png")
    sheet.save(out, optimize=True)
    print("wrote", out, sheet.size, len(names), "models")


if __name__ == "__main__":
    main()
