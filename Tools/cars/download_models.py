#!/usr/bin/env python3
"""Download shortlisted Sketchfab models (needs a Sketchfab API token).

The token is read from ~/.inkdrift.env (line `SKETCHFAB_TOKEN=...`). It is never printed or written
anywhere. Files land in Tools/cars/cache/models/<slot>__<uid>.glb (gitignored).

  Tools/.venv/bin/python Tools/cars/download_models.py              # chosen model of every slot
  Tools/.venv/bin/python Tools/cars/download_models.py --all        # every shortlist candidate
  Tools/.venv/bin/python Tools/cars/download_models.py <uid> ...    # specific models
"""
import io
import json
import os
import sys
import time
import zipfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cache", "models")
API = "https://api.sketchfab.com/v3"


def token():
    p = os.path.expanduser("~/.inkdrift.env")
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SKETCHFAB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("SKETCHFAB_TOKEN missing in ~/.inkdrift.env")


def download(uid, slot, tok):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, f"{slot}__{uid}.glb")
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        print(f"{slot} {uid}: cached")
        return dst
    for attempt in range(8):
        r = requests.get(f"{API}/models/{uid}/download", headers={"Authorization": f"Token {tok}"}, timeout=60)
        if r.status_code == 429:
            time.sleep(15 * (attempt + 1))
            continue
        if r.status_code != 200:
            print(f"{slot} {uid}: download API HTTP {r.status_code}")
            return None
        break
    else:
        print(f"{slot} {uid}: rate limited")
        return None
    info = r.json()
    if "glb" in info:
        url, kind = info["glb"]["url"], "glb"
    elif "gltf" in info:
        url, kind = info["gltf"]["url"], "gltf"
    else:
        print(f"{slot} {uid}: no glTF archive offered ({list(info)})")
        return None
    data = requests.get(url, timeout=600)
    data.raise_for_status()
    if kind == "glb":
        with open(dst, "wb") as f:
            f.write(data.content)
    else:
        d = os.path.join(OUT, f"{slot}__{uid}")
        zipfile.ZipFile(io.BytesIO(data.content)).extractall(d)
        dst = next((os.path.join(dp, fn) for dp, _, fns in os.walk(d) for fn in fns if fn.endswith(".gltf")), d)
    print(f"{slot} {uid}: {kind} {len(data.content) / 1e6:.1f} MB -> {os.path.relpath(dst, HERE)}")
    return dst


def main():
    tok = token()
    sl = json.load(open(os.path.join(HERE, "shortlist.json")))
    jobs = []
    args = sys.argv[1:]
    for slot, e in sl["cars"].items():
        for c in e["candidates"]:
            if (not args and c["uid"] == e["chosen"]) or "--all" in args or c["uid"] in args:
                jobs.append((slot, c["uid"]))
    for slot, uid in jobs:
        try:
            download(uid, slot, tok)
        except Exception as ex:  # keep going, never echo request headers
            print(f"{slot} {uid}: failed ({type(ex).__name__})")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
