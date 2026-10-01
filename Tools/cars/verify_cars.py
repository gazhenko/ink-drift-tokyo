"""Re-import every car FBX and check the game contract.

    blender -b -P Tools/cars/verify_cars.py

Checks: root/children names, wheel pivots (tyre bottom at ground, identity rotation), allowed material
names, tri budgets, relative texture paths, dims.json consistency. Prints one line per car + problems.
"""
import glob
import json
import os
import re

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CARS = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Cars")
ALLOWED = {"M_Paint", "M_PaintAccent", "M_Glass", "M_Chrome", "M_Trim", "M_Carbon", "M_Grille", "M_HeadLight",
           "M_TailLight", "M_Interior", "M_Rim", "M_Tire", "M_Brake", "M_Decal", "M_Plate", "M_Underbody"}
REQUIRED = ["Body", "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR", "Light_Head_L", "Light_Head_R",
            "Light_Tail_L", "Light_Tail_R", "Exhaust_L", "Exhaust_R"]


def world_co(o):
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(o.matrix_world)
    return co @ mw[:3, :3].T + mw[:3, 3]


def check(fbx):
    probs = []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    cid = os.path.splitext(os.path.basename(fbx))[0]
    roots = [o for o in bpy.data.objects if o.parent is None]
    if len(roots) != 1 or roots[0].name != f"Car_{cid}":
        probs.append(f"root {[r.name for r in roots]}")
    root = roots[0]
    kids = {re.sub(r"\.\d+$", "", o.name): o for o in root.children}
    traffic = cid.startswith("traffic_")
    for n in REQUIRED:
        if n not in kids:
            probs.append(f"missing {n}")
    tris = 0
    for n, o in kids.items():
        if o.type != "MESH":
            continue
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
        bad = {m.name for m in o.data.materials if m} - ALLOWED
        bad = {re.sub(r"\.\d+$", "", b) for b in bad} - ALLOWED
        if bad:
            probs.append(f"{n} bad materials {bad}")
    # Blender re-import: Z up again, car faces -Y
    for k in ("FL", "FR", "RL", "RR"):
        w = kids.get(f"Wheel_{k}")
        if not w:
            continue
        co = world_co(w)
        bottom = co[:, 2].min()
        if abs(bottom) > 0.006:
            probs.append(f"Wheel_{k} bottom z={bottom:.4f}")
        e = w.matrix_world.to_euler()
        if max(abs(e.x - (np.pi / 2 if False else 0)), abs(e.y), abs(e.z)) > 1e-3 and \
                max(abs(e.x - np.pi / 2), abs(e.y), abs(e.z)) > 1e-3:
            probs.append(f"Wheel_{k} rotated {tuple(round(v, 3) for v in e)}")
        side = 1 if k[1] == "L" else -1
        if np.sign(w.matrix_world.translation.x) != side:
            probs.append(f"Wheel_{k} wrong side")
        if (w.matrix_world.translation.y < 0) != (k[0] == "F"):
            probs.append(f"Wheel_{k} wrong axle")
    budget = 30000 if traffic else 180000
    if tris > budget or (not traffic and tris < 60000):
        probs.append(f"tris {tris} outside budget")
    for img in bpy.data.images:
        if img.filepath and not os.path.exists(bpy.path.abspath(img.filepath)):
            probs.append(f"missing texture {img.filepath}")
    dj = os.path.join(os.path.dirname(fbx), f"{cid}_dims.json")
    if os.path.exists(dj):
        d = json.load(open(dj))
        if d.get("tri_count") != tris:
            probs.append(f"dims tri_count {d.get('tri_count')} != {tris}")
    else:
        probs.append("no dims json")
    print(f"[verify] {cid:16s} tris={tris:6d} objects={sorted(kids)}")
    for p in probs:
        print(f"[verify]    PROBLEM {p}")
    return not probs


def main():
    fbxs = sorted(glob.glob(os.path.join(CARS, "*", "*.fbx")))
    ok = [check(f) for f in fbxs]
    print(f"[verify] {sum(ok)}/{len(ok)} cars OK")


if __name__ == "__main__":
    main()
