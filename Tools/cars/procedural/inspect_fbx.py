"""Close-up shading check of an exported car FBX (workbench, studio light + specular).

    blender -b -P Tools/cars/procedural/inspect_fbx.py -- <fbx> <out_prefix> [views]
"""
import os
import sys

sys.dont_write_bytecode = True  # keep Tools/cars free of __pycache__

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
fbx, prefix = argv[0], argv[1]
views = argv[2].split(",") if len(argv) > 2 else ["cf", "cr", "cs"]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "MATCAP"
sh.studio_light = "check_normal+y.exr" if False else sh.studio_light
sh.color_type = "MATERIAL"
sh.show_specular_highlight = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 800
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
sc.collection.objects.link(cam)
sc.camera = cam
for m in bpy.data.materials:
    if m.name.startswith("M_Paint"):
        m.diffuse_color = (0.85, 0.85, 0.87, 1)
shots = {
    "cf": ((1.9, -3.0, 1.1), (0.3, -1.4, 0.55), 40),
    "cr": ((-1.9, 3.0, 1.2), (-0.3, 1.4, 0.6), 40),
    "cs": ((3.2, 0.0, 0.9), (0.0, 0.0, 0.6), 28),
    "top": ((0.8, -1.5, 3.0), (0.0, -0.6, 0.8), 35),
}
for v in views:
    pos, look, lens = shots[v]
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    sc.render.filepath = f"{prefix}_{v}.png"
    bpy.ops.render.render(write_still=True)
print("ok")
