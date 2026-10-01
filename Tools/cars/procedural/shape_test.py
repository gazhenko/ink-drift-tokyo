"""Quick body-shape iteration: SDF -> mesh -> workbench renders (no wheels details, no export).

    blender -b -P Tools/cars/procedural/shape_test.py -- <car_id> [h_mm] [views]
"""
import importlib
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # keep Tools/cars free of __pycache__
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa
import numpy as np  # noqa

import blendutil as BU  # noqa
from body import CarBody, CustomBody  # noqa
from mesher import mesh_sdf  # noqa

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VENV_PY = os.path.join(REPO, "Tools", ".venv", "bin", "python")
OUT = os.path.join(HERE, "previews", "_shape")

COL = {"M_Paint": (0.85, 0.85, 0.86), "M_Glass": (0.08, 0.10, 0.14), "M_Trim": (0.05, 0.05, 0.06),
       "M_Underbody": (0.12, 0.12, 0.12), "M_HeadLight": (0.75, 0.82, 0.9), "M_TailLight": (0.75, 0.05, 0.05),
       "M_Grille": (0.02, 0.02, 0.02), "M_Chrome": (0.9, 0.9, 0.95), "M_Carbon": (0.12, 0.12, 0.13),
       "M_PaintAccent": (0.1, 0.1, 0.1), "M_Plate": (1, 1, 1), "M_Decal": (1, 0, 1), "M_Interior": (0.2, 0.2, 0.2),
       "M_Rim": (0.4, 0.4, 0.42), "M_Tire": (0.05, 0.05, 0.05), "M_Brake": (0.5, 0.5, 0.5)}


def build_body(spec, h, log=print):
    sys.path.insert(0, os.path.dirname(HERE))
    import build as B
    body = (CustomBody if "sdf" in spec["body"] else CarBody)(spec["body"])
    t0 = time.time()
    o = B.body_mesh(spec, h)
    log(f"body mesh {len(o.data.vertices)} v, {BU.tri_count(o.data)} tris, {time.time() - t0:.1f}s")
    return body, o


def classify(body, o):
    c, n = BU.face_data(o.data)
    names = body.classify(BU.b2m(c), BU.b2m(n))
    BU.assign_slots(o, names)


def simple_wheels(spec):
    import bmesh
    wh = spec["wheels"]
    objs = []
    for key, s, sx in (("FL", spec["body"]["wb"] / 2, 1), ("FR", spec["body"]["wb"] / 2, -1),
                       ("RL", -spec["body"]["wb"] / 2, 1), ("RR", -spec["body"]["wb"] / 2, -1)):
        a = "f" if key[0] == "F" else "r"
        r, w, tr = wh["r_" + a], wh["w_" + a], wh["track_" + a]
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r, depth=w, location=(sx * tr / 2, -s, r),
                                            rotation=(0, 1.5708, 0))
        t = bpy.context.active_object
        t.data.materials.append(BU.get_mat("M_Tire"))
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r * 0.66, depth=w + 0.01,
                                            location=(sx * tr / 2, -s, r), rotation=(0, 1.5708, 0))
        rm = bpy.context.active_object
        rm.data.materials.append(BU.get_mat("M_Rim"))
        objs += [t, rm]
    return objs


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    cid = argv[0]
    h = float(argv[1]) / 1000 if len(argv) > 1 else 0.008
    views = argv[2].split(",") if len(argv) > 2 else ["side", "front34", "rear34", "front", "rear", "top"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mod = importlib.import_module("specs." + cid)
    spec = mod.spec()
    body, o = build_body(spec, h)
    BU.smooth_by_angle(o, 30)
    if "wheel_design" in spec:
        sys.path.insert(0, os.path.dirname(HERE))
        import build as B
        B.make_wheels(spec, o)
    else:
        simple_wheels(spec)
    for k, c in COL.items():
        m = BU.get_mat(k)
        m.diffuse_color = (*c, 1)
        m.roughness = 0.3
    cam = BU.quick_scene()
    os.makedirs(OUT, exist_ok=True)
    L = 4.6
    H = 1.3
    shots = {
        "side": ((8, 0, 0.62), (0, 0, 0.62), 0, 5.0),
        "front": ((0, -8, 0.65), (0, 0, 0.65), 0, 2.4),
        "rear": ((0, 8, 0.65), (0, 0, 0.65), 0, 2.4),
        "top": ((0, 0, 9), (0, 0.0001, 0), 0, 5.0),
        "front34": ((4.6, -5.6, 1.7), (0, 0, 0.55), 45, None),
        "rear34": ((-4.6, 5.6, 1.9), (0, 0, 0.55), 45, None),
        "low34": ((3.2, -4.2, 0.55), (0, 0, 0.55), 35, None),
        "fronthi": ((2.2, -5.0, 2.6), (0, -0.6, 0.6), 45, None),
        "rf34": ((-2.55, -3.95, 1.0), (0, -0.2, 0.5), 32, None),
        "rr34": ((-2.9, 4.0, 1.15), (0, 0.3, 0.5), 32, None),
        "rside": ((-8, 0, 0.62), (0, 0, 0.62), 0, 5.0),
        "lf34": ((2.55, -3.95, 1.0), (0, -0.2, 0.5), 32, None),
        "lr34": ((2.9, 4.0, 1.15), (0, 0.3, 0.5), 32, None),
    }
    ps = []
    for v in views:
        pos, look, lens, ortho = shots[v]
        ps.append(BU.shoot(cam, pos, look, lens, os.path.join(OUT, f"{cid}_{v}.png"), ortho))
    subprocess.run([VENV_PY, os.path.join(REPO, "Tools", "cars", "cartex.py"), "sheet",
                    os.path.join(OUT, f"{cid}_sheet.jpg")] + ps)
    print("done", OUT)


main()
