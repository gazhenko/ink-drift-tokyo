"""Photo-scanned CC0 materials for the driver's suit/gloves and the cockpit interior (Poly Haven).

    Tools/.venv/bin/python Tools/driver/fetch_scans.py

Out: Game/Assets/InkDrift/Cockpit/Resources/Scan/<set>_albedo.jpg, <set>_n.png (OpenGL normal), <set>_mask.png
(R metal, G AO, B height, A smoothness) at 1K, plus scans.json: real-world size (m), mean albedo / luminance /
smoothness (the realistic shader tints a scan to a target colour while keeping its own variation), credits.
"""
import json
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "textures"))
import fetch_textures as FT  # noqa: E402

OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Cockpit", "Resources", "Scan")
SIZE = 1024
SETS = {   # set -> (Poly Haven id, use)
    "leather_grain": ("leather_white", "glove back + knuckle guard, embossed dash plastic"),
    "suede": ("scuba_suede", "glove palm, Alcantara wheel rim and headliner"),
    "nomex_weave": ("stretch_poplin", "race-suit outer weave"),
    "knit": ("jersey_melange", "knit cuffs"),
    "seat_fabric": ("poly_wool_herringbone", "bucket-seat fabric"),
    "carpet": ("dirty_carpet", "floor carpet"),
    "door_leather": ("fabric_leather_02", "stitched door-card leather"),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for name, (aid, use) in SETS.items():
        work = os.path.join(HERE, "cache", "scan_" + name)
        os.makedirs(work, exist_ok=True)
        maps, info = FT.fetch_polyhaven(aid, work)
        alb = cv2.imread(maps["albedo"], cv2.IMREAD_COLOR)
        alb = cv2.resize(alb, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(OUT, f"{name}_albedo.jpg"), alb, [cv2.IMWRITE_JPEG_QUALITY, 93])
        n = FT.fit(FT.read_float(maps["normal"]), (SIZE, SIZE)) * 2.0 - 1.0
        n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
        FT.write_rgb(os.path.join(OUT, f"{name}_n.png"), n * 0.5 + 0.5)
        one = np.ones((SIZE, SIZE), np.float32)
        if maps.get("arm"):
            arm = FT.fit(FT.read_float(maps["arm"]), (SIZE, SIZE))
            ao, rough, metal = arm[..., 0], arm[..., 1], arm[..., 2]
        else:
            ao = FT.fit(FT.read_float(maps["ao"], gray=True), (SIZE, SIZE)) if maps.get("ao") else one
            rough = FT.fit(FT.read_float(maps["rough"], gray=True), (SIZE, SIZE)) if maps.get("rough") else one * 0.7
            metal = one * 0
        height = FT.norm_height(FT.fit(FT.read_float(maps["height"], gray=True), (SIZE, SIZE))) if maps.get("height") else one * 0
        smooth = 1.0 - rough
        FT.write_rgba(os.path.join(OUT, f"{name}_mask.png"), metal * 0, ao, height, smooth)
        lin = (alb[..., ::-1].astype(np.float32) / 255.0) ** 2.2          # mean in linear space, reported as sRGB
        mean = lin.reshape(-1, 3).mean(0)
        lum = float((lin @ np.array([0.2126, 0.7152, 0.0722])).mean())
        dims = FT.get(f"https://api.polyhaven.com/info/{aid}").json().get("dimensions", [300, 300])
        meta[name] = {
            "asset": aid, "use": use, "url": info["url"], "authors": info["authors"], "license": "CC0",
            "size_m": round(float(dims[0]) / 1000.0, 4),
            "mean_srgb": [round(float(c) ** (1 / 2.2), 4) for c in mean], "mean_lum_srgb": round(lum ** (1 / 2.2), 4),
            "mean_smooth": round(float(smooth.mean()), 4), "mean_ao": round(float(ao.mean()), 4),
        }
        shutil.rmtree(work, ignore_errors=True)
        print(f"[scan] {name:14s} <- {aid:22s} {meta[name]['size_m']} m  mean {meta[name]['mean_srgb']}  smooth {meta[name]['mean_smooth']}", flush=True)
    with open(os.path.join(OUT, "scans.json"), "w") as f:
        json.dump({"sets": [dict(name=k, **v) for k, v in meta.items()]}, f, indent=1)


if __name__ == "__main__":
    main()
