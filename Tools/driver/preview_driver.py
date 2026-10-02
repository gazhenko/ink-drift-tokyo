"""Close-up renders of the driver model for review (Cycles).

    blender -b Tools/driver/cache/driver.blend -P Tools/driver/preview_driver.py -- out_dir [--grip]

--grip curls the fingers the way the game does on the steering wheel (same axes: toward the palm).
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else "/tmp/driver_preview"
grip = "--grip" in argv
os.makedirs(out, exist_ok=True)

rig = bpy.data.objects["DriverRig"]
glove = bpy.data.objects["Glove"]
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 48
scene.cycles.use_denoising = True
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
except Exception:
    pass
scene.render.resolution_x, scene.render.resolution_y = 1280, 860
scene.view_settings.view_transform = "AgX"

world = bpy.data.worlds.new("W"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.45, 0.52, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def bone_head(name):
    return rig.matrix_world @ rig.pose.bones[name].head


def look_at(cam, target):
    d = (target - cam.location).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


if grip:
    # curl each finger chain toward the palm (palm normal from the hand's bones)
    for s in ("R", "L"):
        pb = rig.pose.bones
        wr = pb[f"wrist.{s}"].head
        f = (pb[f"finger3-1.{s}"].head - wr).normalized()
        side = (pb[f"finger2-1.{s}"].head - pb[f"finger5-1.{s}"].head).normalized()
        n = f.cross(side).normalized()
        thumb = pb[f"finger1-3.{s}"].tail - wr
        palm = n if thumb.dot(n) > 0 else -n
        angles = [70, 85, 55]
        for i in range(2, 6):
            for j in range(1, 4):
                b = pb[f"finger{i}-{j}.{s}"]
                d = (b.tail - b.head).normalized()
                axis = d.cross(palm).normalized()
                # rotate in armature space, convert to the bone's local frame
                rest = b.bone.matrix_local.to_3x3()
                ax_local = rest.inverted() @ axis
                b.rotation_mode = "QUATERNION"
                b.rotation_quaternion = Quaternion(ax_local, math.radians(angles[j - 1]))
        for j, a in zip(range(1, 4), (35, 30, 35)):
            b = pb[f"finger1-{j}.{s}"]
            d = (b.tail - b.head).normalized()
            axis = d.cross(palm + f * 0.4).normalized()
            ax_local = b.bone.matrix_local.to_3x3().inverted() @ axis
            b.rotation_mode = "QUATERNION"
            b.rotation_quaternion = Quaternion(ax_local, math.radians(a))
    bpy.context.view_layer.update()

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); scene.collection.objects.link(sun)
sun.data.energy = 4.5; sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(-30))
fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA")); scene.collection.objects.link(fill)
fill.data.energy = 60; fill.data.size = 1.5

cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 50

hand = bone_head("metacarpal2.R")
elbow = bone_head("lowerarm01.R")
shots = {
    "hand_back": hand + Vector((-0.10, 0.16, 0.22)),
    "hand_palm": hand + Vector((-0.05, -0.25, -0.10)),
    "forearm": (hand + elbow) * 0.5 + Vector((-0.45, -0.10, 0.18)),
    "both": (bone_head("wrist.R") + bone_head("wrist.L")) * 0.5 + Vector((0.0, -1.3, 0.35)),
}
targets = {"hand_back": hand, "hand_palm": hand, "forearm": (hand + elbow) * 0.5,
           "both": (bone_head("lowerarm01.R") + bone_head("lowerarm01.L")) * 0.5}
for name, pos in shots.items():
    cam.location = pos
    look_at(cam, targets[name])
    fill.location = pos + Vector((0.3, 0.2, 0.4))
    look_at(fill, targets[name])
    cam.data.lens = 35 if name == "both" else 50
    scene.render.filepath = os.path.join(out, name + ("_grip" if grip else "") + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath, flush=True)
