#!/usr/bin/env python3
"""Build Tools/cars/shortlist.json from the (public) Sketchfab search API.

Every candidate is re-queried so the license/faceCount are fresh. Provenance notes are the
result of a manual review of each uploader's other uploads + model descriptions (Sketchfab
licenses are self-declared by the uploader, so obvious game rips / re-uploads are rejected).
Run: Tools/.venv/bin/python Tools/cars/build_shortlist.py
"""
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.sketchfab.com/v3/search"
SLUG = {"CC Attribution": "by", "CC0 Public Domain": "cc0"}

# slot -> (target, [(uid, query, author, provenance, notes)]) ; first entry = chosen
PLAN = {
    "hachi": ("Toyota GR86 / Subaru BRZ (2022+)", [
        ("bcab5a68e83645cd83d48f1b5cf3923d", "subaru brz zd8", "ilvskf", "low risk",
         "Author's own model ('based on my real car'); uploader models Subaru cars and RAYS wheels from scratch. "
         "ZD8 BRZ = GR86 twin. 2.79M tris trackbuild -> heavy decimation needed; RAYS wheel decals + Subaru badges to remove."),
        ("4919d14eba9640599e838230e8e5ed74", "gr86 zn8", "Car2022", "HIGH risk",
         "Exact GR86 ZN8 and good topology, but the uploader posts hundreds of cars with game-style stat blocks "
         "('Class: B, Weight: Medium...') -> very likely ripped game assets. Not used."),
        ("d079f59271df4702bcfdd449ec8241c1", "subaru brz 2022", "mixmamo.studio", "medium risk",
         "Claims original modular model, but the account re-uploads work credited to others (ships, cars). Backup only."),
    ]),
    "kaiju": ("Toyota GR Supra A90 (2020+)", [
        ("41b83cfb912b4eab9af19a802bcf5ffc", "toyota supra 3d model free", "mpgs.studio", "low-medium risk",
         "Uploader states it was made in Blender (studio account with several self-made cars). 2.7M tris, no textures "
         "-> decimate; badges are geometry."),
        ("30528ef37af844919074498f979b9515", "supra mk5 a90", "lbrtwlk", "medium risk",
         "Single-upload account, 857k tris with interior; origin not stated."),
        ("9231f2d5e71a43dd87603dc0b339d99d", "toyota gr supra", "thelightning", "medium-high risk",
         "Best-looking modded A90 (1.44M tris, 4k textures) but the same account also posts CSR2 game rips."),
    ]),
    "zenkai": ("Nissan Z RZ34 (2023+)", [
        ("db9a5f7ae9d84a0fb01cac96afe3e69c", "nissan z proto", "Lexyc16", "low risk",
         "Self-made in Blender 2.82 by a freelance car modeller (takes commissions). It is the 2020 Z Proto, which is the "
         "production RZ34 body almost 1:1 (same panels, lights, grille shape). 67k tris, clean."),
        ("17668144004c4e7d96bcee3e418d1b66", "2023 nissan z rz34", "supercarmodels", "HIGH risk",
         "Exact RZ34, but the account uploads game rips (one is labelled 'From Rennsport'). Not used."),
        ("308cef927d904bcdb0931f7b21e21cb2", "nissan 400z", "nolimitsofficial", "medium-high risk",
         "Exact RZ34 (US 400Z naming); account posts many free supercars with no origin. Backup only."),
    ]),
    "raijin": ("Toyota GR Corolla (2023+), fallback GR Yaris", [
        ("ee2b94827a904360acb61987e1765983", "subaru wrx vb", "ilvskf", "low risk",
         "FALLBACK: no GR Corolla / GR Yaris with a trustworthy CC-BY origin exists on Sketchfab (all are NC/SA, "
         "rips or re-uploads). The 2022+ Subaru WRX (VB) is the closest current Japanese AWD rally-bred car; "
         "self-made by ilvskf, 63k tris."),
        ("204283fa663d4ccea7f3bdfd1ba6680e", "toyota gr corolla", "srineshchethiya", "HIGH risk",
         "Exact GR Corolla (482k) but the account only re-posts high-poly exotics with encyclopedia blurbs; a "
         "near-identical mesh (482718 faces) was posted earlier by 'niev', who re-uploads commercial models."),
        ("4571be42b9e64986901b360329625269", "toyota gr corolla", "tonielpro520", "HIGH risk",
         "Exact GR Corolla (574k) but the account re-uploads hundreds of models ('REUPLOAD' in titles)."),
    ]),
    "tsubame": ("Mazda MX-5 ND (2016+)", [
        ("217b3a2db58f42e699aff41a3596997f", "mazda miata mx5 nd cartoon style", "maurogsw", "low risk",
         "Only clean-origin ND on Sketchfab: self-made stylised low-poly ND (12.5k tris) - below the hero budget, "
         "flat-shaded style. Other NDs are a Humster3D re-upload (plate reads 'HUMSTER3D'), NFS/RR3 rips, or AI meshes."),
        ("d51fcd44b7", "mazda miata mx-5 na", "Lexyc16", "low risk",
         "Clean, detailed (52k) but it is the 1989 NA, not current-gen."),
        ("323b52ebb9be4ad0bf935ee7c02a077d", "2015 pandem mazda mx5 miata", "AnswerBlue38", "HIGH risk",
         "Pandem-kit ND (69k) but the account's uploads use ripped-asset file names ('2022_arash_imperium'...). Not used."),
    ]),
    "kei": ("kei car / kei truck", [
        ("fb477a6082c5442ca060dfcdf8eae928", "simple kei truck", "spookyghostboo", "low risk",
         "Self-made for a Pavlov map, 17k tris, clean white Acty-style kei truck, no visible badges."),
        ("b5a40b838b414d248db2d2fab6a2bb56", "asian mini truck", "evan.hiltz", "low risk",
         "Self-made (Maya/Substance), 14k tris, HiJet-style."),
        ("e1654a399b9d448a9a7ce200410ac91d", "carry pickup suzuki game ready", "by__Rx", "low risk",
         "University project, 23k tris, weathered PBR textures; SUZUKI lettering on the tailgate to remove."),
    ]),
    "taxi": ("Japanese taxi (JPN Taxi / Crown Comfort)", [
        ("6e357d856df44d98a615cac1d0c30b56", "toyota crown super deluxe", "andrasfi1027", "low risk",
         "Self-made in Blender by an indie dev; Crown Super Deluxe (the Crown Comfort taxi body), 81k -> decimate to <30k."),
        ("a8f3ad22901643809ca72450ac3cc5f6", "crown comfort hong kong taxi", "zxgod118", "low risk",
         "Self-made Crown Comfort (HK livery), 54k. Its plate font is personal-use only -> plates get replaced anyway."),
        ("4868854a74", "toyota jpn taxi", "niev", "HIGH risk",
         "Real JPN Taxi (33k) but the uploader re-posts commercial (Humster3D-style) models. Not used."),
    ]),
    "van": ("delivery van (Hiace-like)", [
        ("f83b4ed4d8534efb81def77b6c1b642d", "low poly 2013 toyota hiace", "Alvin.Woodly", "low risk",
         "Self-made low-poly H200 HiAce, 18k tris, real-world scale. Toyota emblem to remove."),
        ("b8abd3caa4864f41aaba6a583591155d", "toyoace van", "roh3d", "low risk",
         "Self-made 11k Toyota cab-over van."),
        ("8785bdc40ea64f19907bcefe86aabb11", "japanese ambulance van", "paul_sawyer_11", "low risk",
         "Self-made Himedic-style van, 5k tris (very low)."),
    ]),
    "truck": ("box truck", [
        ("663a0953c038434a918cb85725c88ffa", "lct 3000 95", "DanielZhabotinsky", "low risk",
         "Generic (fictional) Japanese cab-over box truck, 19k tris, author grants unconditional use. No OEM badges."),
        ("3be03b6a43aa41898c9ca806b8787052", "lct 3000 07", "DanielZhabotinsky", "low risk",
         "Newer-style version of the same generic truck, 16k tris."),
        ("070bc8b65a224ca89a03bb6d67e22edc", "isuzu elf", "Romanov13", "medium risk",
         "Isuzu Elf box truck, 191k (needs heavy decimation), origin not stated."),
    ]),
}


def find(uid, q, author):
    for lic in ("by", "cc0", None):
        params = {"type": "models", "q": q, "count": 24}
        if lic:
            params["license"] = lic
        for _ in range(3):
            r = requests.get(API, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(5)
                continue
            break
        for m in r.json().get("results", []):
            if m["uid"].startswith(uid) and m["user"]["username"] == author:
                return m
        time.sleep(0.3)
    return None


def thumb(m, minw=640):
    imgs = sorted(m.get("thumbnails", {}).get("images", []), key=lambda i: i["width"])
    for i in imgs:
        if i["width"] >= minw:
            return i["url"]
    return imgs[-1]["url"] if imgs else None


def main():
    out = {"generated": time.strftime("%Y-%m-%d"),
           "policy": "Only CC0 / CC-BY (4.0) Sketchfab models. Sketchfab licenses are declared by the uploader, so "
                     "every candidate was also checked for provenance (uploader history, description): game rips, "
                     "re-uploads of paid/NC models and AI meshes are rejected even if labelled CC-BY.",
           "cars": {}}
    for slot, (target, cands) in PLAN.items():
        rows = []
        for uid, q, author, prov, notes in cands:
            m = find(uid, q, author)
            if m is None:
                print("NOT FOUND", slot, uid, author)
                continue
            lab = (m.get("license") or {}).get("label")
            rows.append({
                "uid": m["uid"], "name": m["name"], "author": author,
                "authorName": m["user"].get("displayName"),
                "license": {"slug": SLUG.get(lab, lab), "label": lab},
                "faceCount": m.get("faceCount"), "vertexCount": m.get("vertexCount"),
                "url": m.get("viewerUrl"), "thumbnail": thumb(m),
                "thumbnail_local": f"Tools/cars/thumbs/{m['uid']}.jpg",
                "glbSizeMB": round(((m.get("archives") or {}).get("glb") or {}).get("size", 0) / 1e6, 1),
                "provenance": prov, "notes": notes,
            })
            time.sleep(0.3)
        out["cars"][slot] = {"target": target, "chosen": rows[0]["uid"] if rows else None, "candidates": rows}
        print(slot, [(r["author"], r["license"]["slug"], r["faceCount"]) for r in rows])
    with open(os.path.join(HERE, "shortlist.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
