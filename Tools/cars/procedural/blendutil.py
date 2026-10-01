"""Blender helpers for the procedural car builder (mesh creation from numpy, mirroring, decimation, previews)."""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


def m2b(V):
    """model (s, x, z) -> blender (X=x left, Y=-s, Z=z)"""
    V = np.asarray(V, float)
    return np.stack([V[:, 1], -V[:, 0], V[:, 2]], 1)


def b2m(V):
    V = np.asarray(V, float)
    return np.stack([-V[:, 1], V[:, 0], V[:, 2]], 1)


def get_mat(slot):
    return bpy.data.materials.get(slot) or bpy.data.materials.new(slot)


def mesh_from_np(name, V, F, slot=None, link=True, smooth=True):
    """V (n,3) blender coords, F list/array of faces (equal-size ndarray or list of tuples)"""
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, np.float64)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    if isinstance(F, np.ndarray) and F.ndim == 2:
        k = F.shape[1]
        me.loops.add(F.size)
        me.loops.foreach_set("vertex_index", F.astype(np.int32).ravel())
        me.polygons.add(len(F))
        me.polygons.foreach_set("loop_start", (np.arange(len(F)) * k).astype(np.int32))
    else:
        sizes = np.array([len(f) for f in F], np.int32)
        flat = np.concatenate([np.asarray(f, np.int32) for f in F]) if len(F) else np.zeros(0, np.int32)
        me.loops.add(len(flat))
        me.loops.foreach_set("vertex_index", flat)
        me.polygons.add(len(F))
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32) if len(F) else np.zeros(0, np.int32)
        me.polygons.foreach_set("loop_start", starts)
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    if slot:
        me.materials.append(get_mat(slot))
    me.polygons.foreach_set("use_smooth", np.full(len(me.polygons), smooth))
    o = bpy.data.objects.new(name, me)
    if link:
        bpy.context.scene.collection.objects.link(o)
    return o


def mesh_from_csr(name, V, idx, off, mats=None, link=True):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", np.asarray(V, np.float32).ravel())
    me.loops.add(len(idx))
    me.loops.foreach_set("vertex_index", np.asarray(idx, np.int32))
    me.polygons.add(len(off) - 1)
    me.polygons.foreach_set("loop_start", np.asarray(off[:-1], np.int32))
    if mats is not None:
        uniq = sorted(set(np.asarray(mats).tolist()))
        for u in uniq:
            me.materials.append(get_mat(u))
        lut = {u: i for i, u in enumerate(uniq)}
        me.polygons.foreach_set("material_index", np.array([lut[m] for m in np.asarray(mats).tolist()], np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    o = bpy.data.objects.new(name, me)
    if link:
        bpy.context.scene.collection.objects.link(o)
    return o


def activate(o):
    for x in bpy.context.scene.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def mirror_x(o, merge=0.0008):
    """keep x>=0 half, mirror to -x, weld the seam"""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
    for v in bm.verts:
        if abs(v.co.x) < 1e-4:
            v.co.x = 0.0
    orig = set(bm.faces)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], matrix=Matrix.Identity(4), merge_dist=merge,
                     axis="X")
    new = [f for f in bm.faces if f not in orig]
    bmesh.ops.reverse_faces(bm, faces=new)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def tri_count(me):
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum())


def decimate(o, target, symmetry=True, vgroup=None, vg_factor=1.0):
    n = tri_count(o.data)
    if n <= target:
        return n
    mod = o.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target / n
    mod.use_symmetry = symmetry
    mod.symmetry_axis = "X"
    mod.use_collapse_triangulate = True
    if vgroup:
        mod.vertex_group = vgroup
        mod.vertex_group_factor = vg_factor
    activate(o)
    bpy.ops.object.modifier_apply(modifier="dec")
    return tri_count(o.data)


def face_data(me):
    n = len(me.polygons)
    c = np.empty(n * 3)
    me.polygons.foreach_get("center", c)
    nr = np.empty(n * 3)
    me.polygons.foreach_get("normal", nr)
    return c.reshape(-1, 3), nr.reshape(-1, 3)


def assign_slots(o, names):
    """names: array of slot name per face"""
    me = o.data
    uniq = sorted(set(names.tolist()))
    me.materials.clear()
    for u in uniq:
        me.materials.append(get_mat(u))
    lut = {u: i for i, u in enumerate(uniq)}
    idx = np.array([lut[n] for n in names], np.int32)
    me.polygons.foreach_set("material_index", idx)
    me.update()


def smooth_by_angle(o, angle=30):
    activate(o)
    o.data.polygons.foreach_set("use_smooth", np.ones(len(o.data.polygons), bool))
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle), keep_sharp_edges=True)
    except Exception as ex:  # pragma: no cover
        print("smooth_by_angle failed", ex)


def weighted_normals(o, weight=50):
    """face-area weighted custom normals (keeps the sharp edges from smooth-by-angle): cleaner shading on the
    decimated flat panels; exported to FBX as the mesh normals."""
    activate(o)
    m = o.modifiers.new("wn", "WEIGHTED_NORMAL")
    m.mode = "FACE_AREA"
    m.weight = weight
    m.keep_sharp = True
    try:
        bpy.ops.object.modifier_apply(modifier="wn")
    except Exception as ex:  # pragma: no cover
        print("weighted normals failed", ex)
        o.modifiers.remove(m)


def join(objs, name):
    objs = [o for o in objs if o is not None]
    for x in bpy.context.scene.objects:
        x.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


# ----------------------------------------------------------------------------------------------
# quick workbench previews (shape iteration)
def quick_scene(paint=(0.85, 0.85, 0.85)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = False
    sh.show_object_outline = True
    sh.show_specular_highlight = True
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    cam_d = bpy.data.cameras.new("qcam")
    cam = bpy.data.objects.new("_qcam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def shoot(cam, pos, look, lens, path, ortho=None):
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
