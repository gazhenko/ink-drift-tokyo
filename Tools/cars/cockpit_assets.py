"""Cockpit data for the hero cars: cabin dimensions read from each car's procedural spec, and gauge face textures.

    Tools/.venv/bin/python Tools/cars/cockpit_assets.py

Writes Game/Assets/InkDrift/Cockpit/Resources/Cockpit/<id>.json (Unity frame: x right, y up, z forward, metres,
origin on the ground midway between the axles) plus tach_<id>.png / gauge_boost.png / gauge_water.png.
The runtime CockpitBuilder sizes the interior (dash, pillars, headliner, doors, seats, cage) from these numbers.
"""
import importlib
import json
import math
import os
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "procedural"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Cockpit", "Resources", "Cockpit")
FONTS = os.path.join(REPO, "Game", "Assets", "InkDrift", "Art", "Fonts")
CARS = ["hachi", "kaiju", "zenkai", "raijin", "tsubame"]
DIAL_START, DIAL_SWEEP = 225.0, 270.0   # degrees CCW from 3 o'clock at 0, clockwise sweep


def curve(pts):
    """[(s, v)] -> f(s) with clamped linear interpolation"""
    a = np.array(sorted(pts), float)
    return lambda s: float(np.interp(s, a[:, 0], a[:, 1]))


def stamp(sp, name):
    for st in sp["stamps"]:
        if st.name == name:
            return st.shape.poly
    raise KeyError(name)


def cabin(car_id):
    spec = importlib.import_module(f"specs.{car_id}").spec()
    body = spec["body"]
    roof, belt, ghw, tumble = curve(body["roof"]), curve(body["belt"]), curve(body["gh_w"]), curve(body["tumble"])
    ws = stamp(body, "windshield")            # top view (s, lateral)
    dlo = stamp(body, "dlo")                  # side view (s, z)
    bl = stamp(body, "backlight")             # top view
    s_base, s_top = ws[:, 0].max(), ws[:, 0].min()
    w_base = ws[ws[:, 0] > s_base - 0.03][:, 1].max()
    w_top = ws[ws[:, 0] < s_top + 0.03][:, 1].max()

    def glass_x(s, z):                        # side glass half-width at height z (tumblehome from the belt)
        return ghw(s) - max(0.0, z - belt(s)) * math.tan(math.radians(tumble(s)))

    eye_z = s_top - 0.50
    eye_y = roof(eye_z) - 0.19
    zs = np.round(np.arange(s_top, bl[:, 0].min() - 0.001, -0.1), 3)
    if zs[-1] > bl[:, 0].min():
        zs = np.append(zs, round(bl[:, 0].min(), 3))
    wheels = spec["wheels"]
    return {
        "id": car_id,
        "eye": [0.36, round(eye_y, 4), round(eye_z, 4)],
        "cowlZ": round(s_base, 4), "cowlY": round(roof(s_base), 4), "cowlHalfW": round(w_base, 4),
        "headerZ": round(s_top, 4), "headerY": round(roof(s_top), 4), "headerHalfW": round(w_top, 4),
        "sideFrontZ": round(dlo[:, 0].max(), 4), "sideRearZ": round(dlo[:, 0].min(), 4),
        "backTopZ": round(bl[:, 0].max(), 4), "backBottomZ": round(bl[:, 0].min(), 4),
        "floorY": round(min(p[1] for p in body["bot"]) + 0.11, 4),
        "frontAxleZ": spec["body"]["wb"] / 2, "wheelRadius": wheels["r_f"],
        # stations from the windshield header back to the bottom of the rear window
        "z": [float(z) for z in zs],
        "roofY": [round(roof(z), 4) for z in zs],
        "beltY": [round(belt(z), 4) for z in zs],
        "beltHalfW": [round(ghw(z), 4) for z in zs],
        "roofHalfW": [round(glass_x(z, roof(z) - 0.03), 4) for z in zs],
    }


def catalog():
    """redline / limiter per car from CarCatalog.cs"""
    src = open(os.path.join(REPO, "Game/Assets/InkDrift/Scripts/Runtime/Vehicle/CarCatalog.cs")).read()
    out = {}
    for m in re.finditer(r'id = "(\w+)".*?redlineRpm = ([\d.]+)f, revLimitRpm = ([\d.]+)f', src, re.S):
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


# ---------------------------------------------------------------- gauge faces
S = 1024   # drawn at 2x, downsampled to 512


def font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, name), px)


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def face(values, labels, red_from=None, title="", sub="", accent=(255, 45, 122), minor=1):
    """values: dial positions 0..1 of major ticks; labels: text per major tick"""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    d.ellipse([8, 8, S - 8, S - 8], fill=(14, 14, 22, 255))
    d.ellipse([8, 8, S - 8, S - 8], outline=(200, 200, 210, 255), width=10)
    d.ellipse([60, 60, S - 60, S - 60], outline=accent + (255,), width=4)
    if red_from is not None:   # redline arc
        a0 = DIAL_START - DIAL_SWEEP * red_from
        a1 = DIAL_START - DIAL_SWEEP
        box = [92, 92, S - 92, S - 92]
        d.arc(box, -a0, -a1, fill=(255, 40, 40, 255), width=46)
    n = len(values)
    for i in range(n):         # majors + minors
        t = values[i]
        a = DIAL_START - DIAL_SWEEP * t
        hot = red_from is not None and t >= red_from - 1e-6
        col = (255, 70, 70, 255) if hot else (245, 245, 240, 255)
        d.line([polar(c, c, S * 0.44, a), polar(c, c, S * 0.36, a)], fill=col, width=16)
        tx, ty = polar(c, c, S * 0.28, a)
        f = font("ChakraPetch-Bold.ttf", 92 if len(labels[i]) < 3 else 70)
        d.text((tx, ty), labels[i], font=f, fill=col, anchor="mm")
        if i < n - 1:
            for k in range(1, minor + 1):
                tm = t + (values[i + 1] - t) * k / (minor + 1)
                am = DIAL_START - DIAL_SWEEP * tm
                hotm = red_from is not None and tm >= red_from
                d.line([polar(c, c, S * 0.44, am), polar(c, c, S * 0.40, am)],
                       fill=(255, 70, 70, 255) if hotm else (190, 190, 200, 255), width=8)
    if title:
        d.text((c, c + S * 0.30), title, font=font("ChakraPetch-Bold.ttf", 54), fill=(200, 200, 210, 255), anchor="mm")
    if sub:
        d.text((c, c + S * 0.37), sub, font=font("ChakraPetch-Regular.ttf", 40), fill=accent + (255,), anchor="mm")
    return img.resize((S // 2, S // 2), Image.LANCZOS)


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("wrote", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    cat = catalog()
    for cid in CARS:
        cab = cabin(cid)
        red, limit = cat[cid]
        dial_max = math.ceil((limit + 300) / 1000.0) * 1000
        cab.update(redline=red, revLimit=limit, dialMaxRpm=dial_max)
        with open(os.path.join(OUT, f"{cid}.json"), "w") as f:
            json.dump(cab, f, indent=1)
        print(cid, "eye", cab["eye"], "cowl", (cab["cowlZ"], cab["cowlY"]), "header", (cab["headerZ"], cab["headerY"]))
        k = int(dial_max // 1000)
        save(face([i / k for i in range(k + 1)], [str(i) for i in range(k + 1)], red_from=red / dial_max,
                  title="x1000 r/min", sub="INK DRIFT", minor=1), f"tach_{cid}.png")
    save(face([i / 3 for i in range(4)], ["-1", "0", "1", "2"], red_from=None, title="BOOST", sub="bar", minor=4),
         "gauge_boost.png")
    save(face([i / 4 for i in range(5)], ["50", "70", "90", "110", "130"], red_from=0.82, title="WATER", sub="°C", minor=1),
         "gauge_water.png")


if __name__ == "__main__":
    main()
