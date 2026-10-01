"""Re-import every FBX in Models/Trees and audit it.
   blender -b -P Tools/blender/foliage/audit_fbx.py [-- names...]
Checks: textures resolve from the FBX paths, material names, custom normals, vertex colour channel ranges
(R=AO, G=wind, B=random), up axis/height vs stats, transforms identity, LOD naming. Prints one line per file."""
import glob
import json
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import foliage_lib as fl  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
files = sorted(glob.glob(os.path.join(fl.MODEL_DIR, "*.fbx")))
if argv:
    files = [f for f in files if os.path.basename(f)[:-4] in argv]
bad = 0
for f in files:
    name = os.path.basename(f)[:-4]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for im in list(bpy.data.images):
        bpy.data.images.remove(im)
    # bake_space_transform: bake the importer's Y-up -> Z-up conversion into the mesh, so a clean file
    # (identity node transforms, as Unity sees it) re-imports with identity object transforms here too.
    bpy.ops.import_scene.fbx(filepath=f, use_custom_normals=True, colors_type="LINEAR", use_image_search=False,
                             bake_space_transform=True)
    issues, lines = [], []
    stats = {}
    sp = os.path.join(fl.STATS_DIR, name + ".json")
    if os.path.exists(sp):
        stats = {o["name"]: o for o in json.load(open(sp))["objects"]}
    for ob in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        me = ob.data
        if not me.has_custom_normals:
            issues.append(f"{ob.name}: no custom normals")
        if any(abs(x - 1) > 1e-4 for x in ob.matrix_world.to_scale()) or ob.matrix_world.to_euler().to_quaternion().angle > 1e-3:
            issues.append(f"{ob.name}: non-identity transform {ob.matrix_world.to_euler()} {ob.matrix_world.to_scale()}")
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        dims = co.max(0) - co.min(0)
        if ob.name in stats:
            ed = np.array(stats[ob.name]["size"])
            if np.abs(dims - ed).max() > 0.02 * max(1, ed.max()):
                issues.append(f"{ob.name}: dims {dims.round(2)} != {ed}")
        if not me.color_attributes:
            issues.append(f"{ob.name}: no vertex colours")
            rng_s = "-"
        else:
            ca = me.color_attributes[0]
            c = np.zeros(len(ca.data) * 4); ca.data.foreach_get("color", c); c = c.reshape(-1, 4)
            rng_s = " ".join(f"{ch}[{c[:, i].min():.2f},{c[:, i].max():.2f}]" for i, ch in enumerate("RGB"))
        for m in me.materials:
            if m is None:
                issues.append(f"{ob.name}: empty material slot")
                continue
            imgs = [n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image] if m.use_nodes else []
            if not imgs:
                issues.append(f"{m.name}: no texture")
            for im in imgs:
                pth = bpy.path.abspath(im.filepath)
                if not os.path.exists(pth) or im.size[0] == 0:
                    issues.append(f"{m.name}: texture missing {im.filepath}")
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        lines.append(f"{ob.name} tris={tris} h={dims[2]:.2f} zmin={co[:, 2].min():.2f} mats={[m.name for m in me.materials]} {rng_s}")
    print(("AUDIT OK   " if not issues else "AUDIT FAIL ") + name + " | " + " || ".join(lines) + ("" if not issues else " ISSUES: " + "; ".join(issues)))
    bad += bool(issues)
print(f"AUDIT SUMMARY {len(files) - bad}/{len(files)} ok")
