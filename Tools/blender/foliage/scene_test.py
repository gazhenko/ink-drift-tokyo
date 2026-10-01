"""Integration test: import exported FBX files (not in-memory builds), arrange a small vignette and render the toon
preview, to check cross-asset scale/orientation coherence.
   blender -b -P Tools/blender/foliage/scene_test.py -- okutama|shibuya"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import foliage_lib as fl  # noqa: E402

SCENES = {
    "okutama": [  # (fbx, x, y, rot_z_deg)
        ("Sugi_A", -9, 14, 0), ("Sugi_B", -3, 18, 40), ("Sugi_C", 4, 15, 80), ("Sugi_A", 10, 19, 120),
        ("Sugi_C", 15, 13, 10), ("Sugi_B", -14, 20, 200),
        ("Cliff_B", -12, 4, 100), ("Momiji_A", -2, 4, 0), ("Momiji_C", 7, 6, 60), ("Ginkgo_B", 13, 4, 0),
        ("Rock_Mossy_A", 2.5, 0.5, 30), ("Rock_Mossy_C", 4, -0.5, 0), ("Susuki_A", -5, -1, 0), ("Susuki_A", -4.2, -1.6, 90),
        ("Weeds_Autumn_A", 0.5, -1.5, 0), ("Grass_B", -1.5, -2, 0), ("Fern_A", 6, 1, 0), ("Litter_Autumn", -1, 1.5, 20),
        ("Grass_A", 8, -1.5, 0), ("Kuromatsu_B", -8, 0, 0),
    ],
    "shibuya": [
        ("Sakura_A", -6, 6, 0), ("Sakura_C", 5, 7, 90), ("Keyaki_C", 14, 10, 0), ("Hedge_Azalea", -2, -1, 0),
        ("Hedge_Azalea", 0, -1, 0), ("Hedge_Azalea", 2, -1, 0), ("Hedge_Boxwood", 6, -1, 0), ("Hedge_Boxwood", 8, -1, 0),
        ("Bush_Round_A", -7, 0, 0), ("Bamboo_B", 11, 2, 0), ("Litter_Petals", -4, 1.5, 0), ("Grass_C", 3, 1, 0),
        ("Kuromatsu_A", -12, 2, 30),
    ],
}


def main():
    which = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "okutama"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = []
    for name, x, y, rz in SCENES[which]:
        path = os.path.join(fl.MODEL_DIR, name + ".fbx")
        if not os.path.exists(path):
            print("missing", name)
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path, use_custom_normals=True, colors_type="LINEAR")
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if o.name.endswith("_LOD1"):
                bpy.data.objects.remove(o)
                continue
            o.location = (x, y, 0)
            o.rotation_euler.z = math.radians(rz)
            objs.append(o)
    # register imported materials for the toon preview
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        alb = nrm = None
        alpha = False
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                fn = os.path.basename(n.image.filepath)
                if "_normal" in fn:
                    nrm = fn
                else:
                    alb = fn
                    alpha = alpha or any(lk.from_socket.name == "Alpha" for lk in n.outputs["Alpha"].links)
        if alb:
            fl.MAT_REGISTRY[m.name] = dict(albedo=alb, normal=nrm, alpha=alpha or alb.startswith(("Leaves_", "Grass", "Fern", "Weeds", "Litter")))
    bpy.context.view_layer.update()
    fl.render_preview(objs, "scene_" + which, res=1400, human=True, az=20, el=8, sun_az=-50, sun_el=40)


main()
