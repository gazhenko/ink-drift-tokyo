"""Deep-dish 350 mm drift steering wheel, modelled for the in-car view.

    blender -b -P Tools/driver/build_wheel.py

Out: Game/Assets/InkDrift/Models/Driver/Resources/Driver/steering_wheel.fbx. Built in the wheel pivot's Unity frame
(x right, y up, z along the column toward the dash; rim centred on the origin in the z = 0 plane, hub dished +z).
  * rim: swept oval section (wider and deeper at the 9/3 thumb grips), Alcantara cover with an inner seam groove and
    baseball stitching, raised 12 o'clock marker band
  * 3 spokes (3, 9, 6 o'clock): tapered 4 mm plates dished to the hub, two drilled lightening holes each, bevelled
  * hub: 6 hex bolts, horn button with ring, quick-release collar and pull ring
Material names (M_Whl*) are mapped to cockpit materials at runtime (CockpitBuilder).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Driver", "Resources", "Driver", "steering_wheel.fbx")
R = 0.172          # rim centre-line radius (matches CockpitRig.wheelRadius)
DISH = 0.065       # hub offset toward the dash
MATS = ["M_WhlRim", "M_WhlMarker", "M_WhlStitch", "M_WhlSpoke", "M_WhlBolt", "M_WhlHorn", "M_WhlCollar"]
RIM, MARKER, STITCH, SPOKE, BOLT, HORN, COLLAR = range(len(MATS))


def u2b(p):
    """Unity wheel frame -> Blender (FBX export: forward -Z, up Y, baked space transform)"""
    return Vector((-p[0], -p[2], p[1]))


def log(*a):
    print("[wheel]", *a, flush=True)


def new_obj(name):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in MATS:
        me.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    return ob


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ang_dist(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def rim(bm):
    N, M = 144, 28
    verts = []
    for i in range(N):
        th = 2 * math.pi * i / N
        grip = max(smoothstep(math.radians(30), 0, ang_dist(th, 0)), smoothstep(math.radians(30), 0, ang_dist(th, math.pi)))
        a = 0.0132 + 0.0026 * grip          # radial half-width
        b = 0.0158 + 0.0022 * grip          # half-depth along the column
        rhat = np.array([math.cos(th), math.sin(th), 0.0])
        c = rhat * R
        marker = smoothstep(math.radians(7), math.radians(5.5), ang_dist(th, math.pi / 2))
        row = []
        for j in range(M):
            ph = 2 * math.pi * j / M
            # inner seam groove (facing the hub)
            groove = 0.00045 * math.exp(-((ang_dist(ph, math.pi)) / 0.09) ** 2)
            k = 1.0 - groove / a + 0.00035 * marker / a
            p = c + rhat * (a * k * math.cos(ph)) + np.array([0, 0, b * k * math.sin(ph)])
            row.append(bm.verts.new(u2b(p)))
        verts.append(row)
    for i in range(N):
        th = 2 * math.pi * (i + 0.5) / N
        is_marker = ang_dist(th, math.pi / 2) < math.radians(6.2)
        for j in range(M):
            f = bm.faces.new((verts[i][j], verts[(i + 1) % N][j], verts[(i + 1) % N][(j + 1) % M], verts[i][(j + 1) % M]))
            f.material_index = MARKER if is_marker else RIM
            f.smooth = True
    log("rim faces", N * M)


def stitch_box(bm, c, t, n, length, width, height, mat):
    b = np.cross(n, t)
    geo = bmesh.ops.create_cube(bm, size=1.0)
    Mx = np.stack([t * length, b * width, n * height], 1)
    for v in geo["verts"]:
        v.co = u2b(c + Mx @ np.array(v.co))
    for f in {f for v in geo["verts"] for f in v.link_faces}:
        f.material_index = mat
        f.smooth = True


def baseball_stitch(bm):
    """cross stitches over the inner seam every 7 mm (the thread pulls the two cover edges together)"""
    count = 0
    a = 0.0132
    for th in np.arange(0, 2 * math.pi, 0.007 / (R - a)):
        if ang_dist(th, math.pi / 2) < math.radians(6.5):
            continue
        rhat = np.array([math.cos(th), math.sin(th), 0.0])
        tang = np.array([-math.sin(th), math.cos(th), 0.0])
        c = rhat * (R - a + 0.00025)
        n = -rhat
        z = np.array([0, 0, 1.0])
        for sgn in (-1, 1):
            d = tang * 0.55 + z * sgn * 0.83
            d /= np.linalg.norm(d)
            stitch_box(bm, c + z * sgn * 0.0011, d, n, 0.0034, 0.0007, 0.0006, STITCH)
            count += 1
    log("stitches", count)


def spokes(bm):
    """tapered, dished plates; holes added with booleans on a separate object"""
    for th in (0.0, math.pi, 1.5 * math.pi):
        d = np.array([math.cos(th), math.sin(th), 0.0])
        side = np.array([-math.sin(th), math.cos(th), 0.0])
        p0 = d * 0.030 + np.array([0, 0, DISH])
        p1 = d * (R - 0.004) + np.array([0, 0, 0.002])
        axis = p1 - p0
        L = np.linalg.norm(axis); axis /= L
        nrm = np.cross(axis, side); nrm /= np.linalg.norm(nrm)
        steps = 10
        ring = []
        for s in range(steps + 1):
            u = s / steps
            w = 0.0235 * (1 - u) + 0.0155 * u
            c = p0 + axis * L * u
            q = [c + side * w + nrm * 0.002, c - side * w + nrm * 0.002, c - side * w - nrm * 0.002, c + side * w - nrm * 0.002]
            ring.append([bm.verts.new(u2b(x)) for x in q])
        for s in range(steps):
            for k in range(4):
                f = bm.faces.new((ring[s][k], ring[s + 1][k], ring[s + 1][(k + 1) % 4], ring[s][(k + 1) % 4]))
                f.material_index = SPOKE
        for cap in (ring[0], ring[-1]):
            f = bm.faces.new(cap if cap is ring[-1] else list(reversed(cap)))
            f.material_index = SPOKE


def hub(bm):
    def cyl(c, axis, r, h, mat, seg=40):
        geo = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=h)
        M = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        z = np.array(axis, float); z /= np.linalg.norm(z)
        x = np.cross(z, [0, 1, 0]) if abs(z[1]) < 0.9 else np.cross(z, [1, 0, 0]); x /= np.linalg.norm(x)
        y = np.cross(z, x)
        for v in geo["verts"]:
            p = np.array(v.co)
            v.co = u2b(np.array(c) + x * p[0] + y * p[1] + z * p[2])
        for f in {f for v in geo["verts"] for f in v.link_faces}:
            f.material_index = mat
            f.smooth = bool(abs(np.dot(np.array(f.normal), np.array(u2b(z)))) < 0.9)   # flat caps, smooth sides
    zf = np.array([0, 0, 1.0])
    cyl([0, 0, DISH], zf, 0.043, 0.009, SPOKE, 64)                       # spoke boss
    cyl([0, 0, DISH - 0.0075], zf, 0.0285, 0.006, HORN, 48)              # horn button
    cyl([0, 0, DISH - 0.0105], zf, 0.018, 0.0012, COLLAR, 40)            # horn centre ring
    for k in range(6):                                                   # hex bolts on the driver side
        a = 2 * math.pi * (k + 0.5) / 6
        c = np.array([math.cos(a) * 0.035, math.sin(a) * 0.035, DISH - 0.0055])
        cyl(c, zf, 0.0042, 0.003, BOLT, 6)
    cyl([0, 0, DISH + 0.022], zf, 0.024, 0.035, COLLAR, 48)              # quick-release collar
    torus = bmesh.ops.create_circle(bm, cap_ends=False, segments=48, radius=0.027)
    # pull ring: thin tube around the collar
    ring_pts = [np.array([math.cos(2 * math.pi * i / 48) * 0.027, math.sin(2 * math.pi * i / 48) * 0.027, DISH + 0.012]) for i in range(48)]
    for v in torus["verts"]:
        bm.verts.remove(v)
    prev = None
    rows = []
    for p in ring_pts:
        rhat = np.array([p[0], p[1], 0]); rhat /= np.linalg.norm(rhat)
        rows.append([bm.verts.new(u2b(p + rhat * 0.0022 * math.cos(2 * math.pi * j / 10) + zf * 0.0022 * math.sin(2 * math.pi * j / 10))) for j in range(10)])
    for i in range(48):
        for j in range(10):
            f = bm.faces.new((rows[i][j], rows[(i + 1) % 48][j], rows[(i + 1) % 48][(j + 1) % 10], rows[i][(j + 1) % 10]))
            f.material_index = COLLAR
            f.smooth = True


def drill(ob):
    """two lightening holes per spoke"""
    cutters = []
    for th in (0.0, math.pi, 1.5 * math.pi):
        d = np.array([math.cos(th), math.sin(th), 0.0])
        for r_along, rad in ((0.075, 0.0068), (0.118, 0.0055)):
            # point on the dished plate at that radius
            p0 = d * 0.030 + np.array([0, 0, DISH]); p1 = d * (R - 0.004) + np.array([0, 0, 0.002])
            u = (r_along - 0.030) / ((R - 0.004) - 0.030)
            c = p0 + (p1 - p0) * u
            axis = p1 - p0; axis /= np.linalg.norm(axis)
            side = np.array([-math.sin(th), math.cos(th), 0.0])
            n = np.cross(axis, side); n /= np.linalg.norm(n)
            bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=rad, depth=0.02, location=u2b(c))
            cut = bpy.context.active_object
            cut.rotation_mode = "QUATERNION"
            cut.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(u2b(n))
            cutters.append(cut)
    bpy.context.view_layer.update()
    for cut in cutters:
        md = ob.modifiers.new("Drill", "BOOLEAN")
        md.operation = "DIFFERENCE"; md.object = cut; md.solver = "EXACT"
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=md.name)
        bpy.data.objects.remove(cut, do_unlink=True)
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width = 0.0006; md.segments = 2; md.limit_method = "ANGLE"; md.angle_limit = math.radians(40)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=md.name)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for m in MATS:
        bpy.data.materials.new(m)
    rim_ob = new_obj("WheelRim")
    bm = bmesh.new(); rim(bm); baseball_stitch(bm); bm.to_mesh(rim_ob.data); bm.free()
    spoke_ob = new_obj("WheelSpokes")
    bm = bmesh.new(); spokes(bm); bm.normal_update(); bm.to_mesh(spoke_ob.data); bm.free()
    drill(spoke_ob)
    hub_ob = new_obj("WheelHub")
    bm = bmesh.new(); hub(bm); bm.normal_update(); bm.to_mesh(hub_ob.data); bm.free()
    for ob in (rim_ob, spoke_ob, hub_ob):
        ob.data.update()
    root = bpy.data.objects.new("SteeringWheel", None)
    bpy.context.scene.collection.objects.link(root)
    for ob in (rim_ob, spoke_ob, hub_ob):
        ob.parent = root
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (root, rim_ob, spoke_ob, hub_ob))
    bpy.context.view_layer.objects.active = root
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=OUT, use_selection=True, object_types={"MESH", "EMPTY"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=True,
        use_tspace=False, add_leaf_bones=False, path_mode="RELATIVE", embed_textures=False, bake_anim=False,
        colors_type="NONE")
    tris = sum(len(p.vertices) - 2 for o in (rim_ob, spoke_ob, hub_ob) for p in o.data.polygons)
    log("exported", OUT, "triangles", tris)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cache", "wheel.blend"))


if __name__ == "__main__":
    main()
