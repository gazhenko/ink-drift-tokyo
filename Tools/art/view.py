"""Dev helper: composite PNG(s) over a background for review. usage: view.py out.png bg in1.png [in2.png ...]
bg: gray | paper | dark | checker | night"""
import sys, os
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import checker

def bg_img(kind, w, h):
    if kind == "checker":
        return checker(w, h, 32).convert("RGBA")
    col = {"gray": (128, 128, 134), "paper": (255, 248, 231), "dark": (20, 18, 30), "night": (27, 19, 64)}[kind]
    return Image.new("RGBA", (w, h), col + (255,))

def main():
    out, kind, *ins = sys.argv[1:]
    ims = [Image.open(p).convert("RGBA") for p in ins]
    w = max(i.width for i in ims); h = sum(i.height for i in ims)
    canvas = Image.new("RGBA", (w, h))
    y = 0
    for im in ims:
        b = bg_img(kind, im.width, im.height)
        b.alpha_composite(im)
        canvas.paste(b, (0, y)); y += im.height
    s = min(1.0, 2000 / max(canvas.size))
    if s < 1:
        canvas = canvas.resize((int(canvas.width * s), int(canvas.height * s)), Image.LANCZOS)
    canvas.convert("RGB").save(out)

if __name__ == "__main__":
    main()
