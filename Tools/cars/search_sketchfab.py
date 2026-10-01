#!/usr/bin/env python3
"""Search Sketchfab (public API, no token) for CC0 / CC-BY downloadable car models.

Usage: Tools/.venv/bin/python Tools/cars/search_sketchfab.py [slot ...]

Writes raw results + model details (incl. description, for provenance checks) to
Tools/cars/cache/search/<slot>.json. The curated shortlist lives in shortlist.json.
"""
import json
import os
import sys
import time

import requests

API = "https://api.sketchfab.com/v3"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cache", "search")

QUERIES = {
    "hachi": ["gr86", "gr 86", "toyota 86 2022", "subaru brz 2022", "brz zd8", "zn8", "gr86 zn8", "brz"],
    "kaiju": ["gr supra", "supra a90", "supra mk5", "supra 2020", "toyota supra", "supra mk v"],
    "zenkai": ["nissan z 2023", "nissan z rz34", "rz34", "nissan z", "400z", "nissan z proto", "fairlady z 2023"],
    "raijin": ["gr corolla", "corolla gr", "gr yaris", "toyota yaris gr", "gr corolla 2023", "corolla hatchback"],
    "tsubame": ["mx-5 nd", "mazda mx5", "miata nd", "mazda mx-5", "roadster nd", "mx5 nd"],
    "kei": ["kei car", "kei truck", "suzuki carry", "honda n-box", "daihatsu hijet", "kei", "mini truck japan",
            "suzuki every", "honda acty", "low poly kei"],
    "taxi": ["japan taxi", "jpn taxi", "japanese taxi", "toyota crown comfort", "tokyo taxi", "taxi low poly",
             "crown taxi"],
    "van": ["hiace", "toyota hiace", "delivery van low poly", "japanese van", "nv350", "caravan van",
            "van low poly"],
    "truck": ["box truck", "isuzu elf", "japanese truck", "delivery truck low poly", "box truck low poly",
              "mitsubishi canter", "hino truck", "cargo truck low poly"],
}


LICENSE_SLUGS = {"CC Attribution": "by", "CC0 Public Domain": "cc0", "CC Attribution-ShareAlike": "by-sa",
                 "CC Attribution-NoDerivs": "by-nd", "CC Attribution-NonCommercial": "by-nc",
                 "CC Attribution-NonCommercial-ShareAlike": "by-nc-sa",
                 "CC Attribution-NonCommercial-NoDerivs": "by-nc-nd"}


def search(q, lic, cursor=None, count=24):
    params = {"type": "models", "q": q, "downloadable": "true", "count": count, "license": lic}
    if cursor:
        params["cursor"] = cursor
    r = requests.get(f"{API}/search", params=params, timeout=30)
    if r.status_code == 429:
        time.sleep(10)
        return search(q, lic, cursor, count)
    r.raise_for_status()
    return r.json()


def details(uid):
    for _ in range(5):
        r = requests.get(f"{API}/models/{uid}", timeout=30)
        if r.status_code == 429:
            time.sleep(10)
            continue
        r.raise_for_status()
        return r.json()
    return None


def thumb(model, minw=640):
    imgs = sorted(model.get("thumbnails", {}).get("images", []), key=lambda i: i["width"])
    for i in imgs:
        if i["width"] >= minw:
            return i["url"]
    return imgs[-1]["url"] if imgs else None


def run(slot):
    os.makedirs(OUT, exist_ok=True)
    seen = {}
    for q in QUERIES[slot]:
        for lic in ("by", "cc0"):
            d = search(q, lic)
            for r in d["results"]:
                seen.setdefault(r["uid"], r)
            time.sleep(0.3)
    rows = []
    for uid, r in seen.items():
        det = r  # search results already carry everything we need (detail endpoint is rate-limited)
        lic = dict(det.get("license") or {})
        lic["slug"] = LICENSE_SLUGS.get(lic.get("label"), lic.get("slug"))
        rows.append({
            "uid": uid,
            "name": det.get("name", r["name"]),
            "author": det.get("user", {}).get("username"),
            "authorName": det.get("user", {}).get("displayName"),
            "license": {"slug": lic.get("slug"), "label": lic.get("label")},
            "faceCount": det.get("faceCount"),
            "vertexCount": det.get("vertexCount"),
            "url": det.get("viewerUrl"),
            "thumbnail": thumb(det or r),
            "likes": det.get("likeCount"),
            "views": det.get("viewCount"),
            "published": det.get("publishedAt"),
            "tags": [t["slug"] for t in det.get("tags", [])],
            "archives": {k: {kk: vv for kk, vv in (v or {}).items() if kk in ("faceCount", "size", "textureCount", "textureMaxResolution", "vertexCount")}
                         for k, v in (r.get("archives") or {}).items()},
            "textureCount": det.get("textureCount"),
            "materialCount": det.get("materialCount"),
            "description": (det.get("description") or "")[:1500],
        })
    rows.sort(key=lambda x: -(x["likes"] or 0))
    with open(os.path.join(OUT, f"{slot}.json"), "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    print(slot, len(rows))


if __name__ == "__main__":
    for s in (sys.argv[1:] or QUERIES.keys()):
        run(s)
