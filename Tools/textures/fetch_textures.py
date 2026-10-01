#!/usr/bin/env python3
"""Fetch CC0 PBR material sets + HDRIs for INK DRIFT: TOKYO and convert them to the project
texture convention (Docs/DESIGN.md -> Asset conventions).

Sources (CC0 only):
  * Poly Haven  - https://polyhaven.com   (api.polyhaven.com, dl.polyhaven.org)
  * ambientCG   - https://ambientcg.com    (ambientcg.com/api/v2)

Output per material set  ->  Game/Assets/InkDrift/Art/Textures/<set>/
  <set>_albedo.jpg   sRGB base color (source 2K JPG, copied untouched when already power-of-two)
  <set>_normal.png   tangent-space normal, OpenGL (+Y up) convention, 8-bit RGB
  <set>_mask.png     linear RGBA mask: R=metallic, G=ambient occlusion, B=height (0 if none),
                     A=smoothness (1 - roughness)
  <set>_height.png   8-bit grayscale height (ground materials only)
Height data (B channel and _height.png) is min/max-normalized (0.5..99.5 percentile) per set.
In Unity: albedo = sRGB on; normal = Normal map; mask/height = sRGB OFF.

HDRIs -> Game/Assets/InkDrift/Art/HDRI/<polyhaven_id>_<res>.hdr

Also writes Docs/credits/textures.md.

Usage:
  Tools/.venv/bin/python Tools/textures/fetch_textures.py            # everything
  Tools/.venv/bin/python Tools/textures/fetch_textures.py road_asphalt_worn nature_grass   # subset
  Tools/.venv/bin/python Tools/textures/fetch_textures.py --credits-only
Raw downloads go to Tools/textures/cache/ and are deleted after each set is processed.
"""
import json
import os
import shutil
import sys
import zipfile

import cv2
import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEX_OUT = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art", "Textures")
HDRI_OUT = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art", "HDRI")
CREDITS = os.path.join(ROOT, "Docs", "credits", "textures.md")
CACHE = os.path.join(HERE, "cache")
UA = {"User-Agent": "InkDriftTokyo-asset-fetch/1.0 (CC0 asset pipeline)"}

# set name -> (source, asset id, group, note, is_ground)
SETS = {
    # --- road ---
    "road_asphalt_fresh":        ("ph", "asphalt_track", "road", "fresh dark fine tarmac", True),
    "road_asphalt_worn":         ("ph", "asphalt_02", "road", "weathered grey asphalt with tar-sealed cracks", True),
    "road_asphalt_highway":      ("ph", "clean_asphalt", "road", "fine-grain grey highway asphalt (Shuto)", True),
    # --- sidewalk ---
    "sidewalk_pavers_interlock": ("ph", "patterned_concrete_pavers", "sidewalk", "grey interlocking concrete pavers", True),
    "sidewalk_tiles_square":     ("ph", "concrete_pavement_02", "sidewalk", "square concrete sidewalk slabs", True),
    "sidewalk_curb_granite":     ("acg", "Granite002B", "sidewalk", "rough grey salt-and-pepper granite (mikage-ishi) for curbs", False),
    # --- concrete ---
    "concrete_smooth":           ("acg", "Concrete034", "concrete", "smooth light cast concrete (expressway piers/parapets)", False),
    "concrete_weathered":        ("ph", "concrete_wall_007", "concrete", "rough weathered concrete wall, formboard lines, patches", False),
    "concrete_formwork":         ("ph", "concrete_wall_009", "concrete", "fair-faced concrete with formwork seams and tie holes", False),
    # --- metal ---
    "metal_painted":             ("ph", "green_metal_rust", "metal", "green-painted steel plate, light rust (Shuto girder green)", False),
    "metal_galvanized":          ("acg", "Metal040", "metal", "hot-dip galvanized steel with zinc spangle", False),
    "metal_corrugated_rusty":    ("ph", "rusty_corrugated_iron", "metal", "rusty corrugated iron sheet", False),
    "metal_brushed_aluminum":    ("acg", "Metal009", "metal", "brushed silver metal (aluminum/steel trim)", False),
    # --- building ---
    "building_plaster":          ("ph", "white_stucco", "building", "white stucco / plaster (tintable)", False),
    "building_tile_mosaic":      ("ph", "rounded_square_tiled_wall", "building", "small square ceramic facade tiles (mansion facade)", False),
    "building_brick_red":        ("acg", "Bricks101", "building", "clean red brick / brick tile", False),
    # --- nature ---
    "nature_bark_sakura":        ("ph", "sakura_bark", "nature", "cherry (sakura) bark", False),
    "nature_bark_cedar":         ("ph", "japanese_cedar_bark", "nature", "Japanese cedar (sugi) bark", False),
    "nature_forest_floor_autumn": ("ph", "forest_floor", "nature", "forest floor with red/orange autumn leaves", True),
    "nature_rock_mossy":         ("ph", "mossy_rock", "nature", "mossy / lichened rock", False),
    "nature_rock_cliff":         ("acg", "Rock030", "nature", "grey layered cliff rock", False),
    "nature_grass":              ("acg", "Grass004", "nature", "short grass ground", True),
    "nature_gravel":             ("acg", "Gravel040", "nature", "grey crushed gravel (road shoulder / ballast)", True),
    "nature_dirt_shoulder":      ("ph", "rocky_trail", "nature", "compacted stony dirt (road shoulder)", True),
    # --- misc ---
    "misc_rubber":               ("acg", "Rubber004", "misc", "black rubber (generic; no tire tread available)", False),
    "misc_carbon_fiber":         ("acg", "Fabric004", "misc", "woven carbon fiber", False),
    "misc_canvas":               ("acg", "Fabric061", "misc", "light woven canvas (awnings, tintable)", False),
}

# Deliberate corrections to source data (documented in the credits file):
#  * Fabric004 ships an all-white metalness map; carbon fibre is a clear-coated dielectric -> metal 0.
#  * Grass004's roughness map is very low (median smoothness ~0.75, reads wet/plastic) -> scale smoothness.
OVERRIDES = {
    "misc_carbon_fiber": {"metal": 0.0},
    "nature_grass": {"smooth_mul": 0.4},
}

# file name stem -> (polyhaven id, resolution, lighting note)
HDRIS = [
    ("shanghai_bund", "4k", "night city: neon skyline across a river, artificial light (SHIBUYA NEON)"),
    ("the_sky_is_on_fire", "4k", "vivid orange/magenta sunset over an urban seafront (SHUTO C1 LOOP)"),
    ("autumn_forest_04", "4k", "low golden-hour sun through an autumn forest, leaf litter (OKUTAMA TOUGE)"),
    ("overcast_soil_puresky", "2k", "soft neutral overcast sky, no direct sun (model/car previews)"),
]


# ----------------------------------------------------------------------------- helpers
def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=300, **kw)
    r.raise_for_status()
    return r


def download(url, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with requests.get(url, headers=UA, timeout=600, stream=True) as r:
        r.raise_for_status()
        tmp = dst + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        os.replace(tmp, dst)
    return dst


def read_float(path_or_bytes, gray=False):
    """Read 8/16-bit image -> float32 0..1 (BGR->RGB for colour)."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        arr = np.frombuffer(path_or_bytes, np.uint8)
        im = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    else:
        im = cv2.imread(path_or_bytes, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise RuntimeError(f"could not decode {path_or_bytes if isinstance(path_or_bytes, str) else 'bytes'}")
    scale = 65535.0 if im.dtype == np.uint16 else 255.0
    im = im.astype(np.float32) / scale
    if im.ndim == 3:
        im = im[..., :3][..., ::-1]  # drop alpha, BGR->RGB
        if gray:
            im = im[..., 0]
    return im


def pow2(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    # pick the nearer power of two
    return p * 2 if (p * 2 - n) < (n - p) else p


def fit(im, size_wh):
    if (im.shape[1], im.shape[0]) == size_wh:
        return im
    return cv2.resize(im, size_wh, interpolation=cv2.INTER_AREA)


def to8(im):
    return np.clip(im * 255.0 + 0.5, 0, 255).astype(np.uint8)


def norm_height(h):
    lo, hi = np.percentile(h, 0.5), np.percentile(h, 99.5)
    if hi - lo < 1e-6:
        return np.zeros_like(h)
    return np.clip((h - lo) / (hi - lo), 0, 1)


def write_rgb(path, rgb):
    cv2.imwrite(path, cv2.cvtColor(to8(rgb), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 9])


def write_rgba(path, r, g, b, a):
    bgra = np.dstack([to8(b), to8(g), to8(r), to8(a)])
    cv2.imwrite(path, bgra, [cv2.IMWRITE_PNG_COMPRESSION, 9])


# ----------------------------------------------------------------------------- sources
def fetch_polyhaven(aid, work):
    files = get(f"https://api.polyhaven.com/files/{aid}").json()

    def pick(key, fmts=("png", "jpg")):
        if key not in files or "2k" not in files[key]:
            return None
        for fmt in fmts:
            if fmt in files[key]["2k"]:
                url = files[key]["2k"][fmt]["url"]
                return download(url, os.path.join(work, os.path.basename(url)))
        return None

    maps = {
        "albedo": pick("Diffuse", ("jpg", "png")),
        "normal": pick("nor_gl", ("png", "jpg")),
        "arm": pick("arm", ("png", "jpg")),
        "height": pick("Displacement", ("png", "jpg")),
    }
    if maps["arm"] is None:
        maps["ao"] = pick("AO")
        maps["rough"] = pick("Rough")
        maps["metal"] = pick("Metal")
    info = get(f"https://api.polyhaven.com/info/{aid}").json()
    meta = {
        "name": info.get("name", aid),
        "authors": ", ".join(info.get("authors", {}).keys()),
        "url": f"https://polyhaven.com/a/{aid}",
        "source": "Poly Haven",
    }
    return maps, meta


def fetch_ambientcg(aid, work):
    data = get(f"https://ambientcg.com/api/v2/full_json?id={aid}&include=downloadData").json()
    asset = data["foundAssets"][0]
    dls = asset["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]
    dl = next(d for d in dls if d["attribute"] == "2K-JPG")
    zpath = download(dl["downloadLink"], os.path.join(work, dl["fileName"]))
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            base = os.path.basename(n)
            low = base.lower()
            key = None
            if low.endswith("_color.jpg"):
                key = "albedo"
            elif low.endswith("_normalgl.jpg"):
                key = "normal"
            elif low.endswith("_roughness.jpg"):
                key = "rough"
            elif low.endswith("_metalness.jpg"):
                key = "metal"
            elif low.endswith("_ambientocclusion.jpg"):
                key = "ao"
            elif low.endswith("_displacement.jpg"):
                key = "height"
            if key:
                dst = os.path.join(work, base)
                with z.open(n) as src, open(dst, "wb") as f:
                    shutil.copyfileobj(src, f)
                out[key] = dst
    os.remove(zpath)
    meta = {
        "name": asset.get("displayName", aid),
        "authors": "ambientCG",
        "url": f"https://ambientcg.com/view?id={aid}",
        "source": "ambientCG",
    }
    return out, meta


# ----------------------------------------------------------------------------- processing
def process_set(name, spec):
    src, aid, group, note, is_ground = spec
    work = os.path.join(CACHE, "work", name)
    os.makedirs(work, exist_ok=True)
    maps, meta = (fetch_polyhaven if src == "ph" else fetch_ambientcg)(aid, work)
    if not maps.get("albedo") or not maps.get("normal"):
        raise RuntimeError(f"{name}: missing albedo/normal ({maps})")

    out_dir = os.path.join(TEX_OUT, name)
    os.makedirs(out_dir, exist_ok=True)

    # albedo: keep source JPG bytes when already power-of-two, otherwise resize+re-encode
    alb = cv2.imread(maps["albedo"], cv2.IMREAD_COLOR)
    h, w = alb.shape[:2]
    W, H = pow2(w), pow2(h)
    alb_out = os.path.join(out_dir, f"{name}_albedo.jpg")
    if (w, h) == (W, H) and maps["albedo"].lower().endswith(".jpg"):
        shutil.copyfile(maps["albedo"], alb_out)
    else:
        cv2.imwrite(alb_out, fit(alb, (W, H)), [cv2.IMWRITE_JPEG_QUALITY, 95])
    size = (W, H)

    # normal (OpenGL +Y): pass through (renormalize after resize)
    nrm = fit(read_float(maps["normal"]), size)
    v = nrm * 2.0 - 1.0
    v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
    write_rgb(os.path.join(out_dir, f"{name}_normal.png"), v * 0.5 + 0.5)

    # mask: R=metal G=AO B=height A=smoothness
    one = np.ones((H, W), np.float32)
    zero = np.zeros((H, W), np.float32)
    if maps.get("arm"):
        arm = fit(read_float(maps["arm"]), size)
        ao, rough, metal = arm[..., 0], arm[..., 1], arm[..., 2]
    else:
        ao = fit(read_float(maps["ao"], gray=True), size) if maps.get("ao") else one
        rough = fit(read_float(maps["rough"], gray=True), size) if maps.get("rough") else one * 0.8
        metal = fit(read_float(maps["metal"], gray=True), size) if maps.get("metal") else zero
    height = norm_height(fit(read_float(maps["height"], gray=True), size)) if maps.get("height") else None
    smooth = 1.0 - rough
    ov = OVERRIDES.get(name, {})
    if "metal" in ov:
        metal = np.full((H, W), ov["metal"], np.float32)
    if "smooth_mul" in ov:
        smooth = smooth * ov["smooth_mul"]
    rough = 1.0 - smooth
    write_rgba(os.path.join(out_dir, f"{name}_mask.png"), metal, ao, height if height is not None else zero,
               smooth)
    if is_ground and height is not None:
        cv2.imwrite(os.path.join(out_dir, f"{name}_height.png"), to8(height), [cv2.IMWRITE_PNG_COMPRESSION, 9])

    shutil.rmtree(work, ignore_errors=True)
    stats = {
        "metal_mean": float(metal.mean()), "ao_mean": float(ao.mean()),
        "smooth_mean": float(1.0 - rough.mean()), "size": f"{W}x{H}", "has_height": height is not None,
    }
    meta.update({"set": name, "asset_id": aid, "group": group, "note": note, "stats": stats, "overrides": ov})
    print(f"[ok] {name:28s} <- {src}:{aid:28s} {W}x{H} metal={stats['metal_mean']:.2f} "
          f"ao={stats['ao_mean']:.2f} smooth={stats['smooth_mean']:.2f} height={height is not None}", flush=True)
    return meta


def fetch_hdri(aid, res):
    files = get(f"https://api.polyhaven.com/files/{aid}").json()["hdri"]
    entry = files[res]["hdr"]
    if entry["size"] > 40 * 1024 * 1024:
        raise RuntimeError(f"{aid} {res} hdr is {entry['size']/1e6:.1f} MB (> 40 MB)")
    dst = os.path.join(HDRI_OUT, f"{aid}_{res}.hdr")
    if not os.path.exists(dst) or os.path.getsize(dst) != entry["size"]:
        download(entry["url"], dst)
    info = get(f"https://api.polyhaven.com/info/{aid}").json()
    print(f"[ok] HDRI {os.path.basename(dst)} {entry['size']/1e6:.1f} MB", flush=True)
    return {
        "file": os.path.basename(dst), "name": info.get("name", aid),
        "authors": ", ".join(info.get("authors", {}).keys()), "url": f"https://polyhaven.com/a/{aid}",
        "source": "Poly Haven",
    }


# ----------------------------------------------------------------------------- credits
MANIFEST = os.path.join(HERE, "manifest.json")


def write_credits(manifest):
    lines = [
        "# Texture & HDRI credits",
        "",
        "All assets below are **CC0 1.0 (public domain)**. Attribution is not required but given anyway.",
        "Fetched and converted by `Tools/textures/fetch_textures.py` (2K maps; mask = R metal, G AO,",
        "B height, A smoothness).",
        "",
        "- Poly Haven license: https://polyhaven.com/license",
        "- ambientCG license: https://docs.ambientcg.com/license/",
        "",
        "## Materials (`Game/Assets/InkDrift/Art/Textures/`)",
        "",
        "| Set | Used as | Source asset | Author(s) | Source URL | License |",
        "|-----|---------|--------------|-----------|------------|---------|",
    ]
    for name in SETS:
        m = manifest["sets"].get(name)
        if not m:
            continue
        lines.append(f"| `{name}` | {m['note']} | {m['name']} ({m['source']}) | {m['authors']} | {m['url']} | CC0 |")
    lines += [
        "",
        "Modifications: maps resized/repacked only, except `misc_carbon_fiber` (source metalness map",
        "replaced by 0 - carbon fibre is a dielectric) and `nature_grass` (smoothness scaled x0.4; the",
        "source roughness read as wet/plastic).",
    ]
    lines += [
        "",
        "## HDRIs (`Game/Assets/InkDrift/Art/HDRI/`)",
        "",
        "| File | Source asset | Author(s) | Source URL | License | Lighting |",
        "|------|--------------|-----------|------------|---------|----------|",
    ]
    for aid, res, note in HDRIS:
        m = manifest["hdris"].get(aid)
        if not m:
            continue
        lines.append(f"| `{m['file']}` | {m['name']} (Poly Haven) | {m['authors']} | {m['url']} | CC0 | {note} |")
    os.makedirs(os.path.dirname(CREDITS), exist_ok=True)
    with open(CREDITS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", CREDITS)


def main():
    args = sys.argv[1:]
    manifest = {"sets": {}, "hdris": {}}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST))
    if "--credits-only" in args:
        write_credits(manifest)
        return
    only = [a for a in args if not a.startswith("--")]
    do_hdri = not only or "hdri" in only
    failures = []
    for name, spec in SETS.items():
        if only and name not in only:
            continue
        try:
            manifest["sets"][name] = process_set(name, spec)
        except Exception as e:  # noqa: BLE001
            failures.append((name, repr(e)))
            print(f"[FAIL] {name}: {e}", flush=True)
        json.dump(manifest, open(MANIFEST, "w"), indent=1)
    if do_hdri:
        os.makedirs(HDRI_OUT, exist_ok=True)
        for aid, res, _ in HDRIS:
            try:
                manifest["hdris"][aid] = fetch_hdri(aid, res)
            except Exception as e:  # noqa: BLE001
                failures.append((aid, repr(e)))
                print(f"[FAIL] {aid}: {e}", flush=True)
        json.dump(manifest, open(MANIFEST, "w"), indent=1)
    write_credits(manifest)
    if failures:
        print("FAILURES:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
