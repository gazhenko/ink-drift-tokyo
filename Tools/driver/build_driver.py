"""The driver's arms for the in-car view: MakeHuman CC0 anatomy -> racing-suit sleeves and gloves, rigged with
MakeHuman's own skeleton and hand-painted skin weights.

    Tools/.venv/bin/python Tools/driver/driver_textures.py      # tiles + decals first
    blender -b -P Tools/driver/build_driver.py

Source (CC0, see src/README.md): MakeHuman base mesh, default skeleton + weights, young-male muscle target.
Out: Game/Assets/InkDrift/Models/Driver/Resources/Driver/driver_arms.fbx (+ the textures beside it).

Construction
  * body mesh + 40 % "max muscle" target, scaled to a 1.75 m adult, arms cut out by their skin weights
  * sleeve = arm surface smoothed (fabric hides muscle definition), offset 7-9 mm, elbow crease folds, quilted
    Nomex with a contrasting top stripe, a stretch panel in the elbow crease and a knit cuff under the glove
  * glove = hand surface offset 1.6 mm with a flared gauntlet over the sleeve, rolled hem, Velcro strap with a
    pull tab, padded knuckle guard, suede palm with silicone print, leather back with the brand logo, stitched
    seam grooves wherever two panels meet
  * Catmull-Clark subdivision before detailing (weights interpolate), suit patches as conforming decals
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Driver", "Resources", "Driver")
SCALE = 0.105            # MakeHuman decimetres -> metres for a 1.75 m driver
MUSCLE = 0.4
GAUNT = 0.082            # glove gauntlet reaches this far up the forearm from the wrist joint
SIDES = ("R", "L")
FINGERS = [f"finger{i}-{j}" for i in range(1, 6) for j in range(1, 4)]
ARM = ["upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist", "metacarpal1", "metacarpal2", "metacarpal3", "metacarpal4"] + FINGERS
CHAIN = ["clavicle", "shoulder01"] + ARM

# material slots (names are read by Unity's AssetPipeline: /Models/Driver/ -> DriverMaterial)
MATS = ["M_DrvSuit", "M_DrvStripe", "M_DrvStretch", "M_DrvKnit", "M_DrvGloveBack", "M_DrvGlovePalm", "M_DrvKnuckle",
        "M_DrvStrap", "M_DrvLogo", "M_DrvPatchInk", "M_DrvPatchFlag", "M_DrvPatchClass",
        "M_DrvGusset", "M_DrvStitch", "M_DrvStitchSuit"]
SUIT, STRIPE, STRETCH, KNIT, BACK, PALM, KNUCKLE, STRAP, LOGO, PINK, PFLAG, PCLASS, GUSSET, STITCH, STITCH_SUIT = range(len(MATS))
NO_TILE_UV = (LOGO, PINK, PFLAG, PCLASS, STITCH, STITCH_SUIT)
LOOK = {   # linear base colour, roughness, normal tile, decal image
    "M_DrvSuit": ((0.045, 0.11, 0.38), 0.8, "suit_n.png", None),
    "M_DrvStripe": ((0.78, 0.78, 0.8), 0.75, "twill_n.png", None),
    "M_DrvStretch": ((0.015, 0.022, 0.06), 0.9, "twill_n.png", None),
    "M_DrvKnit": ((0.012, 0.012, 0.016), 0.95, "knit_n.png", None),
    "M_DrvGloveBack": ((0.048, 0.048, 0.054), 0.45, "leather_n.png", None),
    "M_DrvGlovePalm": ((0.17, 0.17, 0.18), 0.9, "suede_n.png", None),
    "M_DrvKnuckle": ((0.5, 0.012, 0.035), 0.5, "leather_n.png", None),
    "M_DrvStrap": ((0.022, 0.022, 0.025), 0.95, "velcro_n.png", None),
    "M_DrvLogo": ((1, 1, 1), 0.6, None, "glove_logo.png"),
    "M_DrvPatchInk": ((1, 1, 1), 0.7, None, "patch_ink.png"),
    "M_DrvPatchFlag": ((1, 1, 1), 0.7, None, "patch_flag.png"),
    "M_DrvPatchClass": ((1, 1, 1), 0.7, None, "patch_class.png"),
    "M_DrvGusset": ((0.03, 0.03, 0.033), 0.7, "perf_n.png", None),
    "M_DrvStitch": ((0.45, 0.03, 0.04), 0.6, None, None),
    "M_DrvStitchSuit": ((0.7, 0.7, 0.72), 0.6, None, None),
}


def log(*a):
    print("[driver]", *a, flush=True)


# ---------------------------------------------------------------- MakeHuman sources
def load_obj(path):
    V, faces, group = [], [], None
    for line in open(path):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("g "):
            group = line.split()[1]
        elif line.startswith("f ") and group == "body":
            faces.append([int(p.split("/")[0]) - 1 for p in line.split()[1:]])
    return np.array(V), faces


def apply_target(V, path, w):
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        V[int(p[0])] += w * np.array([float(p[1]), float(p[2]), float(p[3])])


def to_blender(P):
    """MakeHuman (x = character's left, y up, z forward, dm) -> Blender car frame (X left, -Y forward, Z up, m)"""
    P = np.asarray(P, float)
    return np.stack([P[..., 0], -P[..., 2], P[..., 1]], -1) * SCALE


# ---------------------------------------------------------------- helpers
def nrm(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-9)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)


def activate(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def noise3(P, freq, seed):
    """cheap smooth 3D noise: sum of random oriented sines"""
    r = np.random.default_rng(seed)
    out = np.zeros(len(P))
    for k in range(6):
        d = nrm(r.normal(size=3))
        out += np.sin(P @ d * freq * (1 + 0.37 * k) + r.random() * 6.28) / (k + 1)
    return out / 2.45


def make_material(name):
    col, rough, ntile, decal = LOOK[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*col, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if ntile:
        img = bpy.data.images.load(os.path.join(OUT, ntile), check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if decal:
        img = bpy.data.images.load(os.path.join(OUT, decal), check_existing=True)
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.extension = "CLIP"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    return m


# ---------------------------------------------------------------- build
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    V, faces = load_obj(os.path.join(SRC, "base.obj"))
    apply_target(V, os.path.join(SRC, "universal-male-young-maxmuscle-averageweight.target"), MUSCLE)
    sk = json.load(open(os.path.join(SRC, "default.mhskel")))
    wts = json.load(open(os.path.join(SRC, "default_weights.mhw")))["weights"]
    VB = to_blender(V)

    def joint(n):
        return VB[sk["joints"][n]].mean(0)

    bones = {}
    for s in SIDES:
        for b in CHAIN:
            name = f"{b}.{s}"
            d = sk["bones"][name]
            parent = d["parent"] if b != "clavicle" else "chest"
            while parent not in [f"{x}.{s}" for x in CHAIN] + ["chest"]:   # skip bones we don't keep
                parent = sk["bones"][parent]["parent"] if parent in sk["bones"] else "chest"
            bones[name] = (joint(d["head"]), joint(d["tail"]), parent)
    chest = (bones["clavicle.R"][0] + bones["clavicle.L"][0]) * 0.5
    bones["chest"] = (chest - np.array([0, 0, 0.15]), chest, None)

    # ---- per-vertex skin weights restricted to our skeleton
    W = {b: np.zeros(len(V)) for b in bones}
    for b in bones:
        for i, w in wts.get(b, []):
            W[b][i] = w
    armw = np.zeros(len(V))
    for s in SIDES:
        for b in ARM:
            armw += W[f"{b}.{s}"]
    keep = [f for f in faces if armw[f].min() >= 0.22]
    used = np.unique(np.concatenate(keep))
    remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    log("arm faces", len(keep), "verts", len(used))

    # ---- hand / limb frames per side (rest pose)
    fr = {}
    for s in SIDES:
        H = lambda b: bones[f"{b}.{s}"][0]
        T = lambda b: bones[f"{b}.{s}"][1]
        sh, el, wr = H("upperarm01"), H("lowerarm01"), H("wrist")
        f = nrm(H("finger3-1") - wr)
        side = nrm(H("finger2-1") - H("finger5-1"))          # index -> pinky reversed
        n = nrm(np.cross(f, side))
        back = -n if np.dot(T("finger1-3") - wr, n) > 0 else n   # the thumb sits on the palm side
        outer = np.array([-1.0, 0, 0]) if s == "R" else np.array([1.0, 0, 0])
        fore = nrm(wr - el)
        upper = nrm(el - sh)
        flex = nrm(fore - upper * np.dot(fore, upper))         # the way the elbow folds (anterior)
        fr[s] = dict(sh=sh, el=el, wr=wr, f=f, side=side, back=back, outer=outer, fore=fore, upper=upper, flex=flex,
                     knuckles=(H("finger2-1"), H("finger5-1")), sign=-1.0 if s == "R" else 1.0)
        log(s, "upper %.3f fore %.3f hand %.3f" % (np.linalg.norm(el - sh), np.linalg.norm(wr - el), np.linalg.norm(T("finger3-3") - wr)))

    def side_of(p):
        return "R" if p[0] < 0 else "L"

    def t_of(p, s):
        return float(np.dot(p - fr[s]["wr"], fr[s]["fore"]))

    # ---- coarse arm mesh with vertex groups
    def build(name, face_ok):
        me = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, me)
        link(obj)
        for m in MATS:
            me.materials.append(bpy.data.materials.get(m) or make_material(m))
        for b in bones:
            obj.vertex_groups.new(name=b)
        bm = bmesh.new()
        dl = bm.verts.layers.deform.verify()
        vmap = {}
        gi = {b: obj.vertex_groups[b].index for b in bones}
        for f in keep:
            P = VB[f]
            if not face_ok(f, P):
                continue
            vs = []
            for i in f:
                if i not in vmap:
                    v = bm.verts.new(VB[i])
                    for b in bones:
                        if W[b][i] > 1e-4:
                            v[dl][gi[b]] = float(W[b][i])
                    vmap[i] = v
                vs.append(vmap[i])
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
        bm.normal_update()
        return obj, bm

    def glove_ok(f, P):           # generous here: exact plane cuts trim it after subdivision
        s = side_of(P.mean(0))
        return max(t_of(p, s) for p in P) > -GAUNT - 0.03

    def sleeve_ok(f, P):
        s = side_of(P.mean(0))
        return min(t_of(p, s) for p in P) < 0.03

    for m in MATS:
        make_material(m)
    glove, gbm = build("Glove", glove_ok)
    sleeve, sbm = build("Sleeve", sleeve_ok)
    for obj, bm in ((glove, gbm), (sleeve, sbm)):
        bm.to_mesh(obj.data); bm.free()

    # ---- subdivide (weights carry through), then cut openings and panel seams with exact planes
    for obj, lv in ((glove, 2), (sleeve, 2)):
        activate(obj)
        md = obj.modifiers.new("Sub", "SUBSURF")
        md.levels = lv; md.render_levels = lv
        bpy.ops.object.modifier_apply(modifier=md.name)
        log(obj.name, "verts", len(obj.data.vertices))
    # smooth before cutting: fabric skims over muscle definition, leather over the finest skin detail;
    # smoothing after the cuts would drag the seam lines out of true
    pre_smooth(sleeve, 8, 0.5)
    pre_smooth(glove, 2, 0.35)
    fingertip_smooth(glove)
    cut_panels(glove, sleeve, fr, side_of, t_of)

    detail_sleeve(sleeve, fr, side_of, t_of)
    for sd in SIDES:   # finger joints (knuckle, middle, end) for the glove creases
        fr[sd]["joints"] = [(bones[f"finger{i}-{j}.{sd}"][0], nrm(bones[f"finger{i}-{j}.{sd}"][1] - bones[f"finger{i}-{j}.{sd}"][0]), i)
                            for i in range(1, 6) for j in range(1, 4)]
    detail_glove(glove, fr, side_of, t_of)
    stitch_seams(glove, {(BACK, PALM), (BACK, KNUCKLE), (BACK, STRAP), (PALM, STRAP), (KNUCKLE, PALM)}, STITCH)
    finger_details(glove, fr)
    stitch_seams(sleeve, {(SUIT, STRIPE), (SUIT, KNIT), (STRIPE, KNIT)}, STITCH_SUIT, spacing=0.0042, offset=0.0022, length=0.003)
    decals(glove, sleeve, fr, side_of, t_of)
    uvs(glove, sleeve, fr, side_of, t_of)
    if "--no-bake" not in sys.argv:
        bake(glove, sleeve)

    # ---- armature
    arm_data = bpy.data.armatures.new("DriverRig")
    rig = bpy.data.objects.new("DriverRig", arm_data)
    link(rig)
    activate(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for name in ["chest"] + [n for n in bones if n != "chest"]:
        h, t, _ = bones[name]
        b = arm_data.edit_bones.new(name)
        b.head = Vector(h); b.tail = Vector(t)
        eb[name] = b
    for name, (h, t, p) in bones.items():
        if p:
            eb[name].parent = eb[p]
            eb[name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in (glove, sleeve):
        obj.parent = rig
        md = obj.modifiers.new("Armature", "ARMATURE"); md.object = rig
        for poly in obj.data.polygons:
            poly.use_smooth = True

    # ---- export
    os.makedirs(OUT, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (rig, glove, sleeve))
    bpy.context.view_layer.objects.active = rig
    path = os.path.join(OUT, "driver_arms.fbx")
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="OFF", use_triangles=True,
        use_tspace=False, add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=True, path_mode="RELATIVE", embed_textures=False, bake_anim=False,
        colors_type="NONE")
    tris = sum(len(p.vertices) - 2 for o in (glove, sleeve) for p in o.data.polygons)
    log("exported", path, "triangles", tris)
    if "--blend" in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cache", "driver.blend"))


# ---------------------------------------------------------------- panels
STRAP_T = (-0.072, -0.050)
KNIT_T = -0.034
STRIPE_W = 0.016          # contrasting stripe down the top of the arm (constant width)


def sleeve_off(t, upper):
    """suit sleeve thickness over the skin: roomy, then a snug knit cuff that ends just past the wrist"""
    base = np.where(upper, 0.0088, 0.0072)
    k = np.clip((t - KNIT_T) / (0.008 - KNIT_T), 0, 1)
    return np.where(t > KNIT_T, 0.0072 + (0.0024 - 0.0072) * k, base)


def glove_off(t):
    """glove over the skin: thin on the hand, wraps the cuff at the wrist, gauntlet flares over the sleeve"""
    s0 = sleeve_off(np.zeros_like(t), False)
    over = np.maximum(0.0042, sleeve_off(t, False) + 0.0018)
    flare = 0.0025 * np.clip((-t - 0.045) / (GAUNT - 0.045), 0, 1) ** 2
    wrist = s0 + 0.0018 + (0.0016 - s0 - 0.0018) * np.clip(t / 0.02, 0, 1)
    hand = 0.0016 - 0.0006 * np.clip((t - 0.075) / 0.03, 0, 1)        # leather hugs the fingers tighter than the palm
    return np.where(t >= 0.02, hand, np.where(t >= 0.0, wrist, over + flare))


def on_upper(p, F):
    return not (np.dot(p - F["el"], F["upper"]) > 0.0 and np.dot(p - F["wr"], F["fore"]) > -0.30)


def cut_panels(glove, sleeve, fr, side_of, t_of):
    def side_geom(bm, s, pred=lambda p: True):
        vs = [v for v in bm.verts if side_of(np.array(v.co)) == s and pred(np.array(v.co))]
        vset = set(vs)
        es = [e for e in bm.edges if e.verts[0] in vset and e.verts[1] in vset]
        fs = [f for f in bm.faces if all(v in vset for v in f.verts)]
        return vs + es + fs

    def cut(bm, s, co, no, pred=lambda p: True, inner=False, outer=False):
        bmesh.ops.bisect_plane(bm, geom=side_geom(bm, s, pred), dist=1e-6, plane_co=Vector(co), plane_no=Vector(no),
                               clear_inner=inner, clear_outer=outer)

    # glove: opening, strap edges, wrist line, palm/back split, knuckle guard
    bm = bmesh.new(); bm.from_mesh(glove.data)
    for s in ("R", "L"):
        F = fr[s]
        cut(bm, s, F["wr"] - F["fore"] * GAUNT, F["fore"], inner=True)
        for t in STRAP_T + (0.004,):
            cut(bm, s, F["wr"] + F["fore"] * t, F["fore"])
        mid = F["wr"] + F["f"] * 0.05
        cut(bm, s, mid, F["back"], pred=lambda p, F=F: np.dot(p - F["wr"], F["fore"]) > 0.0)
        k0, k1 = F["knuckles"]
        dk = np.dot((k0 + k1) * 0.5 - F["wr"], F["f"])
        for d in (dk - 0.017, dk + 0.008):
            cut(bm, s, F["wr"] + F["f"] * d, F["f"], pred=lambda p, F=F, mid=mid: np.dot(p - mid, F["back"]) > -0.002)
    bm.normal_update()
    for f in bm.faces:
        c = np.array(f.calc_center_median()); s = side_of(c); F = fr[s]
        t = t_of(c, s)
        if STRAP_T[0] < t < STRAP_T[1]:
            mat = STRAP
        elif t < 0.004:
            mat = BACK
        else:
            mid = F["wr"] + F["f"] * 0.05
            mat = PALM if np.dot(c - mid, F["back"]) < 0 else BACK
            k0, k1 = F["knuckles"]
            dk = np.dot((k0 + k1) * 0.5 - F["wr"], F["f"])
            d = np.dot(c - F["wr"], F["f"])
            seg = k1 - k0
            u = np.dot(c - k0, seg) / np.dot(seg, seg)
            if mat == BACK and dk - 0.017 < d < dk + 0.008 and -0.12 < u < 1.12 and np.dot(np.array(f.normal), F["back"]) > 0.2:
                mat = KNUCKLE

        f.material_index = mat
    bm.to_mesh(glove.data); bm.free()

    # sleeve: cuff end, shoulder trim, knit cuff line, top stripe on upper arm and forearm
    bm = bmesh.new(); bm.from_mesh(sleeve.data)
    for s in ("R", "L"):
        F = fr[s]
        cut(bm, s, F["wr"] + F["fore"] * 0.008, F["fore"], outer=True)
        cut(bm, s, F["sh"] + F["upper"] * 0.03, F["upper"], inner=True)
        cut(bm, s, F["wr"] + F["fore"] * KNIT_T, F["fore"])
        for seg_upper in (True, False):
            o, a = (F["sh"], F["upper"]) if seg_upper else (F["el"], F["fore"])
            ref = stripe_ref(F, a)
            ref2 = np.cross(a, ref)
            for sgn in (-1, 1):
                cut(bm, s, o + ref2 * (sgn * STRIPE_W / 2), ref2, pred=lambda p, F=F, u=seg_upper: on_upper(p, F) == u)
    bm.normal_update()
    for f in bm.faces:
        c = np.array(f.calc_center_median()); s = side_of(c); F = fr[s]
        t = t_of(c, s)
        up = on_upper(c, F)
        o, a = (F["sh"], F["upper"]) if up else (F["el"], F["fore"])
        ref = stripe_ref(F, a)
        r = c - o; r = r - a * np.dot(r, a)
        mat = SUIT
        if np.dot(r, ref) > 0 and abs(np.dot(r, np.cross(a, ref))) < STRIPE_W / 2:
            mat = STRIPE
        if t > KNIT_T:
            mat = KNIT
        f.material_index = mat
    bm.to_mesh(sleeve.data); bm.free()
    log("panels cut: glove", len(glove.data.vertices), "sleeve", len(sleeve.data.vertices))


def stripe_ref(F, a):
    ref = nrm(F["outer"] * 0.8 + np.array([0, 0, 0.6]))
    return nrm(ref - a * np.dot(ref, a))


def fingertip_smooth(obj, iters=12):
    """Taubin smoothing (no shrinkage) on the end finger segments: the glove skims over nails and pad creases"""
    me = obj.data
    names = [f"finger{i}-{j}.{s}" for i in range(1, 6) for j in (2, 3) for s in ("R", "L")]
    gw = {obj.vertex_groups[n].index: (1.0 if n.split("-")[1][0] == "3" else 0.45) for n in names if n in obj.vertex_groups}
    w = np.zeros(len(me.vertices))
    for v in me.vertices:
        for g in v.groups:
            if g.group in gw:
                w[v.index] += g.weight * gw[g.group]
    w = np.clip(w * 1.6, 0, 1)[:, None]
    P = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", P); P = P.reshape(-1, 3)
    E = neighbours(me)
    cnt = np.zeros(len(P)); np.add.at(cnt, E[:, 0], 1); np.add.at(cnt, E[:, 1], 1)
    def lap(Q):
        acc = np.zeros_like(Q); np.add.at(acc, E[:, 0], Q[E[:, 1]]); np.add.at(acc, E[:, 1], Q[E[:, 0]])
        return acc / np.maximum(cnt, 1)[:, None] - Q
    for _ in range(iters):
        P = P + lap(P) * 0.55 * w
        P = P + lap(P) * -0.58 * w
    me.vertices.foreach_set("co", P.ravel())
    me.update()
    log("fingertips smoothed:", int((w[:, 0] > 0.2).sum()), "verts")


def bake(glove, sleeve, size=2048):
    """unique UV1 + Cycles bakes -> <obj>_bake_mask.png: R ambient occlusion, G convexity, B cavity"""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 96
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"; prefs.get_devices()
        for d in prefs.devices: d.use = True
        scene.cycles.device = "GPU"
    except Exception:
        pass
    if scene.world is None:
        scene.world = bpy.data.worlds.new("BakeWorld")
    scene.world.light_settings.distance = 0.045
    mats = [bpy.data.materials[m] for m in MATS]

    for obj in (glove, sleeve):
        me = obj.data
        tiling = me.uv_layers[0]
        bake_uv = me.uv_layers.new(name="Bake")
        me.uv_layers.active = bake_uv
        activate(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, area_weight=0.0, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        out = {}
        for kind in ("AO", "POINT"):
            img = bpy.data.images.new(f"{obj.name}_{kind}", size, size, alpha=False, float_buffer=True)
            img.colorspace_settings.name = "Non-Color"
            saved = []
            for m in mats:
                nt = m.node_tree
                node = nt.nodes.new("ShaderNodeTexImage"); node.image = img
                nt.nodes.active = node
                if kind == "POINT":                       # temporarily emit mesh curvature
                    outn = nt.nodes.get("Material Output")
                    old = [l.from_socket for l in outn.inputs["Surface"].links]
                    geo = nt.nodes.new("ShaderNodeNewGeometry"); em = nt.nodes.new("ShaderNodeEmission")
                    nt.links.new(geo.outputs["Pointiness"], em.inputs["Color"])
                    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
                    saved.append((m, node, old, geo, em))
                else:
                    saved.append((m, node, None, None, None))
            activate(obj)
            bpy.ops.object.bake(type="AO" if kind == "AO" else "EMIT", margin=6, use_clear=True)
            px = np.empty(size * size * 4, np.float32); img.pixels.foreach_get(px)
            out[kind] = px.reshape(size, size, 4)[..., 0].copy()
            for m, node, old, geo, em in saved:
                nt = m.node_tree
                if old is not None:
                    outn = nt.nodes.get("Material Output")
                    for l in list(outn.inputs["Surface"].links): nt.links.remove(l)
                    for src in old: nt.links.new(src, outn.inputs["Surface"])
                    nt.nodes.remove(geo); nt.nodes.remove(em)
                nt.nodes.remove(node)
            bpy.data.images.remove(img)
            log(obj.name, kind, "baked")
        pt = out["POINT"]
        conv = np.clip((pt - 0.5) * 5.0 + 0.5, 0, 1)
        cav = np.clip((0.5 - pt) * 6.0, 0, 1)
        rgba = np.stack([np.clip(out["AO"], 0, 1), conv, cav, np.ones_like(conv)], -1).astype(np.float32)
        res = bpy.data.images.new(f"{obj.name}_bake", size, size, alpha=False, float_buffer=False)
        res.colorspace_settings.name = "Non-Color"
        res.pixels.foreach_set(rgba.ravel())
        res.filepath_raw = os.path.join(OUT, f"{obj.name.lower()}_bake_mask.png")
        res.file_format = "PNG"
        res.save()
        me.uv_layers.active = tiling                      # UV0 stays the tiling layout, Bake exports as UV1
        log("wrote", res.filepath_raw)


def stitch_seams(obj, pairs, mat, spacing=0.0034, offset=0.0016, length=0.0024, width=0.00055, lift=0.0004):
    """twin-needle stitching: a row of thread beads either side of every seam between the given panel pairs"""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    dl = bm.verts.layers.deform.verify()
    ok = set(pairs) | {(b, a) for a, b in pairs}
    seam = [e for e in bm.edges if len(e.link_faces) == 2 and (e.link_faces[0].material_index, e.link_faces[1].material_index) in ok]
    adj = {}
    for e in seam:
        for v in e.verts:
            adj.setdefault(v, []).append(e)
    used, lines = set(), []
    starts = [v for v, es in adj.items() if len(es) != 2] + list(adj.keys())   # open ends first, then loops
    for v0 in starts:
        for e0 in adj[v0]:
            if e0 in used:
                continue
            line, v, e = [v0], v0, e0
            while e is not None and e not in used:
                used.add(e)
                v = e.other_vert(v)
                line.append(v)
                nxt = [x for x in adj.get(v, []) if x not in used]
                e = nxt[0] if len(adj.get(v, [])) == 2 and nxt else None
            if len(line) > 2:
                lines.append(line)
    count = 0
    for line in lines:
        P = np.array([v.co for v in line]); Nn = np.array([v.normal for v in line])
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        for d in np.arange(spacing * 0.5, cum[-1], spacing):
            i = min(np.searchsorted(cum, d) - 1, len(seg) - 1)
            i = max(i, 0)
            k = (d - cum[i]) / max(seg[i], 1e-9)
            p = P[i] + (P[i + 1] - P[i]) * k
            t = nrm(P[i + 1] - P[i])
            n = nrm(Nn[i] * (1 - k) + Nn[i + 1] * k)
            t = nrm(t - n * np.dot(t, n))
            b = np.cross(n, t)
            src = line[i] if k < 0.5 else line[i + 1]
            for row in (-offset, offset):
                c = p + b * row + n * lift * 0.5
                geo = bmesh.ops.create_cube(bm, size=1.0)
                M = np.stack([t * length, b * width, n * lift], 1)
                for v in geo["verts"]:
                    v.co = Vector(c + M @ np.array(v.co))
                    for gi, w in src[dl].items():
                        v[dl][gi] = w
                for f in {f for v in geo["verts"] for f in v.link_faces}:
                    f.material_index = mat
                    f.smooth = True
                count += 1
    bm.to_mesh(me); bm.free()
    me.update()
    log(obj.name, "stitches:", count, "along", len(lines), "seams")


def finger_details(obj, fr):
    """external seams down both sides of each finger and the thumb, joined over every tip; vent perforations"""
    me = obj.data
    P, N = vert_arrays(me)
    sides = np.where(P[:, 0] < 0, "R", "L")
    mats = np.zeros(len(P), int)
    for poly in me.polygons:
        for vi in poly.vertices:
            mats[vi] = poly.material_index
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    dl = bm.verts.layers.deform.verify()
    W0 = [dict(v[dl]) for v in bm.verts]          # original skin weights (new geometry invalidates the index table)

    def snap(s, q, want=None):
        """nearest surface vertex of side s (optionally of given materials)"""
        m = sides == s
        if want is not None:
            m &= np.isin(mats, want)
        idx = np.where(m)[0]
        k = idx[np.argmin(((P[idx] - q) ** 2).sum(1))]
        return k

    def bead(k, c, t, n, length, width, height, mat, round_=False):
        b = np.cross(n, t)
        geo = (bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10, radius1=0.5, radius2=0.5, depth=1.0)
               if round_ else bmesh.ops.create_cube(bm, size=1.0))
        Mx = np.stack([t * length, b * width, n * height], 1)
        for v in geo["verts"]:
            v.co = Vector(c + Mx @ np.array(v.co))
            for gi, w in W0[k].items():
                v[dl][gi] = w
        for f in {f for v in geo["verts"] for f in v.link_faces}:
            f.material_index = mat
            f.smooth = True

    def stitch_line(s, q_of, t_of_, n_steps):
        """stitch beads along a parametric line q(u), snapped onto the glove"""
        count = 0
        for u in np.linspace(0, 1, n_steps):
            q = q_of(u)
            k = snap(s, q, [BACK, PALM, KNUCKLE])
            if np.linalg.norm(P[k] - q) > 0.008:
                continue
            c, n = P[k], nrm(N[k])
            t = t_of_(u); t = nrm(t - n * np.dot(t, n))
            bead(k, c + n * 0.0003, t, n, 0.0022, 0.0006, 0.0005, STITCH)
            count += 1
        return count

    seams = vents = 0
    for s in ("R", "L"):
        F = fr[s]
        J = F["joints"]
        for i in range(1, 6):
            chain = [J[(i - 1) * 3 + j] for j in range(3)]
            heads = [c for c, _, _ in chain]
            tip_dir = chain[2][1]
            if i == 1:
                # the thumb's nail faces half-way between the back of the hand and its own outer side
                out = heads[1] - J[3][0]
                out = nrm(out - F["back"] * np.dot(out, F["back"]))
                dorsal = nrm(F["back"] + out)
                lat_of = [nrm(np.cross(chain[j][1], dorsal)) for j in range(3)]
                tip_len, half_w, lift = 0.02, 0.0115, dorsal * 0.0015
            else:
                lat_of = [F["side"]] * 3
                tip_len, half_w, lift = 0.022, 0.012, F["back"] * 0.002
            tip = heads[2] + tip_dir * tip_len
            pts = heads + [tip]
            # twin side seams from the knuckle to the tip
            for side_sign in (-1, 1):
                for seg in range(3):
                    if i == 1 and seg == 0:
                        continue                                  # the thumb's first bone is inside the palm
                    a, b = pts[seg], pts[seg + 1]
                    L = np.linalg.norm(b - a)
                    lat = lat_of[seg] * side_sign
                    n_steps = max(2, int(L * 0.88 / 0.0034))
                    seams += stitch_line(s, lambda u, a=a, b=b, lat=lat: a + (b - a) * (0.12 + 0.88 * u) + lat * half_w + lift,
                                         lambda u, a=a, b=b: b - a, n_steps)
            # and over the tip, joining the two side seams (one continuous seam round the finger end)
            centre = heads[2] + tip_dir * (tip_len - half_w)
            lat = lat_of[2]
            seams += stitch_line(s, lambda u: centre + lat * half_w * math.cos(math.pi * u) + tip_dir * half_w * math.sin(math.pi * u) + lift,
                                 lambda u: -lat * math.sin(math.pi * u) + tip_dir * math.cos(math.pi * u), 11)
            if i == 1:
                continue
            # vents: 2 x 3 holes on the back of the first segment
            a, b = heads[0], heads[1]
            for u in (0.35, 0.6, 0.85):
                for off in (-0.0028, 0.0028):
                    q = a + (b - a) * u + F["side"] * off + F["back"] * 0.012
                    k = snap(s, q, [BACK])
                    c, n = P[k], nrm(N[k])
                    if np.linalg.norm(c - q) > 0.01:
                        continue
                    t = nrm(b - a); t = nrm(t - n * np.dot(t, n))
                    bead(k, c + n * 0.00015, t, n, 0.0014, 0.0014, 0.0002, GUSSET, round_=True)
                    vents += 1
    bm.to_mesh(me); bm.free()
    me.update()
    log("finger seams:", seams, "stitches,", vents, "vents")


def pre_smooth(obj, iters, k):
    me = obj.data
    P = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", P)
    P = smooth(P.reshape(-1, 3), neighbours(me), boundary_verts(me), iters, k)
    me.vertices.foreach_set("co", P.ravel())
    me.update()


def vert_arrays(me):
    P = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", P)
    me.update()
    N = np.empty(len(me.vertices) * 3); me.vertex_normals.foreach_get("vector", N)
    return P.reshape(-1, 3), N.reshape(-1, 3)


def neighbours(me):
    E = np.empty(len(me.edges) * 2, int); me.edges.foreach_get("vertices", E)
    return E.reshape(-1, 2)


def smooth(P, E, fixed, iters, k):
    for _ in range(iters):
        acc = np.zeros_like(P); cnt = np.zeros(len(P))
        np.add.at(acc, E[:, 0], P[E[:, 1]]); np.add.at(acc, E[:, 1], P[E[:, 0]])
        np.add.at(cnt, E[:, 0], 1); np.add.at(cnt, E[:, 1], 1)
        avg = acc / np.maximum(cnt, 1)[:, None]
        P = np.where(fixed[:, None], P, P + (avg - P) * k)
    return P


def boundary_verts(me):
    bm = bmesh.new(); bm.from_mesh(me)
    b = np.array([v.is_boundary for v in bm.verts]); bm.free()
    return b


def seam_verts(me):
    """vertices where two different materials meet"""
    mats = {}
    for p in me.polygons:
        for vi in p.vertices:
            mats.setdefault(vi, set()).add(p.material_index)
    out = np.zeros(len(me.vertices), bool)
    for vi, s in mats.items():
        out[vi] = len(s) > 1
    return out


def touches(me, mat):
    """vertices used by any face of a material"""
    out = np.zeros(len(me.vertices), bool)
    for p in me.polygons:
        if p.material_index == mat:
            out[list(p.vertices)] = True
    return out


def detail_sleeve(obj, fr, side_of, t_of):
    me = obj.data
    P, N = vert_arrays(me)
    sides = np.array([side_of(p) for p in P])
    off = np.zeros(len(P))
    fold = np.zeros(len(P))
    for s in ("R", "L"):
        m = sides == s
        F = fr[s]
        Q = P[m]
        along_u = (Q - F["sh"]) @ F["upper"]
        t = (Q - F["wr"]) @ F["fore"]
        ups = np.array([on_upper(q, F) for q in Q])
        off[m] = sleeve_off(t, ups)
        loose = np.clip((KNIT_T - 0.01 - t) / 0.03, 0, 1)   # the knit cuff is snug: no folds there
        # elbow: compression folds on the inside of the bend, softer ones round the back
        de = np.linalg.norm(Q - F["el"], axis=1)
        inner = np.clip(N[m] @ F["flex"], 0, 1)
        ph = (Q - F["el"]) @ F["upper"] / 0.026 * 2 * np.pi + noise3(Q, 60, 3) * 1.4
        fall = np.clip(1 - de / 0.13, 0, 1) ** 1.5
        fold[m] += np.sin(ph) * 0.0032 * fall * (0.35 + 0.65 * inner) * loose
        # long drape folds down the upper arm and twist folds on the forearm
        fold[m] += noise3(Q, 28, 5) * 0.0016 * loose
        fold[m] += np.sin((Q @ nrm(F["fore"] + F["outer"] * 0.6)) / 0.05 * 2 * np.pi + noise3(Q, 20, 7)) * 0.0009 * (t > -0.3)
    newP = P + N * (off + fold)[:, None]
    seam = seam_verts(me)
    newP -= N * (seam * 0.0007)[:, None]                 # stitched seams pull in
    me.vertices.foreach_set("co", newP.ravel())
    me.update()


def creases(P, N, sides, fr):
    """inward offset: flexion creases across the palm side of every finger joint, fine wrinkles over the knuckles"""
    out = np.zeros(len(P))
    for s in ("R", "L"):
        m = np.where(sides == s)[0]
        if len(m) == 0:
            continue
        Q, Nm = P[m], N[m]
        back = fr[s]["back"]
        best = np.full(len(m), 1e9); along_b = np.zeros(len(m)); thumb = np.zeros(len(m), bool)
        for c, a, fi in fr[s]["joints"]:
            d = Q - c
            along = d @ a
            radial = np.linalg.norm(d - np.outer(along, a), axis=1)
            ok = (radial < 0.017) & (np.abs(along) < np.abs(best))
            best = np.where(ok, along, best); along_b = np.where(ok, along, along_b); thumb = np.where(ok, fi == 1, thumb)
        near = np.abs(best) < 0.011
        facing = Nm @ back
        palm = near & (facing < -0.15)
        top = near & (facing > 0.25)
        x = along_b
        # palm side: the leather bunches into two folds per joint, with a puff between them (a worn glove). The
        # folds are ~1.3 mm wide so the ~1 mm mesh actually carries them
        palm_c = (np.exp(-((x - 0.0016) / 0.0013) ** 2) + 0.75 * np.exp(-((x + 0.0019) / 0.0012) ** 2)) * 0.0009 \
            - np.exp(-(x / 0.0010) ** 2) * 0.00025
        # back of the finger: stretch wrinkles over the knuckle that fade away from the joint
        top_c = np.maximum(np.sin(x / 0.0022 * np.pi), 0) ** 2 * np.exp(-(x / 0.006) ** 2) * 0.0004
        o = np.where(palm, palm_c, 0) + np.where(top, top_c * np.where(thumb, 0.6, 1.0), 0)
        out[m] = o * np.clip((np.abs(facing) - 0.1) * 3, 0, 1)
    return out


def detail_glove(obj, fr, side_of, t_of):
    me = obj.data
    P, N = vert_arrays(me)
    E = neighbours(me)
    fixed = boundary_verts(me)
    sides = np.array([side_of(p) for p in P])
    off = np.full(len(P), 0.0016)
    for s in ("R", "L"):
        m = sides == s
        F = fr[s]
        t = (P[m] - F["wr"]) @ F["fore"]
        off[m] = glove_off(t)
    # padded knuckle guard and strap stand proud (smoothed so the pad has a rounded edge)
    inside = touches(me, KNUCKLE)
    pad = inside.astype(float)
    strap = touches(me, STRAP).astype(float)
    for _ in range(4):                                   # erode from the panel edge -> rounded padding
        acc = np.zeros(len(P)); cnt = np.zeros(len(P))
        np.add.at(acc, E[:, 0], pad[E[:, 1]]); np.add.at(acc, E[:, 1], pad[E[:, 0]])
        np.add.at(cnt, E[:, 0], 1); np.add.at(cnt, E[:, 1], 1)
        pad = np.where(inside, acc / np.maximum(cnt, 1), 0.0)
    off += pad * 0.0026 + strap * 0.0021
    # segmented knuckle guard: a groove between each pair of finger knuckles splits the pad into four
    for s in ("R", "L"):
        m = (sides == s) & inside
        if not m.any():
            continue
        kn = [fr[s]["joints"][(i - 1) * 3][0] for i in range(2, 6)]          # knuckles of index .. little finger
        for a, b in zip(kn[:-1], kn[1:]):
            mid, nrm_ = (a + b) * 0.5, nrm(b - a)
            d = (P[m] - mid) @ nrm_
            off[m] -= 0.0021 * np.exp(-(d / 0.0011) ** 2) * np.clip(pad[m] * 1.5, 0, 1)
    # the wrist: soft circumferential folds where the glove bunches between the hand and the gauntlet. Their phase
    # wanders round the wrist so they read as fabric folds rather than machined rings
    for s in ("R", "L"):
        m = np.where(sides == s)[0]
        if len(m) == 0:
            continue
        F = fr[s]
        d = P[m] - F["wr"]
        t = d @ F["fore"]
        ang = np.arctan2(d @ F["outer"], d @ F["back"])
        phase = t / 0.0075 + 0.35 * np.sin(3 * ang + 0.7) + 0.2 * np.sin(5 * ang)
        window = np.clip((t + 0.012) / 0.008, 0, 1) * np.clip((0.024 - t) / 0.008, 0, 1)
        fold = np.maximum(np.sin(phase * 2 * np.pi), 0) ** 1.5 * window * ~inside[m] * (1 - strap[m])
        off[m] -= fold * 0.0007
    newP = P + N * off[:, None]
    seam = seam_verts(me)
    newP -= N * (seam * 0.0005)[:, None]
    newP -= N * creases(P, N, sides, fr)[:, None]
    me.vertices.foreach_set("co", newP.ravel())
    me.update()

    # rolled hem at the gauntlet opening: turn the edge inward so the glove has thickness
    bm = bmesh.new(); bm.from_mesh(me)
    bm.normal_update()
    edges = [e for e in bm.edges if e.is_boundary and all(t_of(np.array(v.co), side_of(np.array(v.co))) < -0.04 for v in e.verts)]
    inward = {v: -v.normal.copy() for e in edges for v in e.verts}
    res = bmesh.ops.extrude_edge_only(bm, edges=edges)
    newv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    for v in newv:
        # each new vertex sits on top of an old boundary vertex; push it under the glove
        near = min(inward, key=lambda o: (o.co - v.co).length)
        v.co = v.co + inward[near] * 0.0036 + Vector(fr[side_of(np.array(v.co))]["fore"]) * 0.0012
    for f in res["geom"]:
        if isinstance(f, bmesh.types.BMFace):
            f.material_index = BACK
    # Velcro pull tab on the outside of each strap
    dl = bm.verts.layers.deform.verify()
    for s in ("R", "L"):
        F = fr[s]
        cands = [v for v in bm.verts if side_of(np.array(v.co)) == s and -0.064 < t_of(np.array(v.co), s) < -0.058]
        if not cands:
            continue
        v0 = max(cands, key=lambda v: np.dot(np.array(v.normal), F["back"] * 0.6 + F["outer"] * 0.8))
        c = np.array(v0.co) + np.array(v0.normal) * 0.0022
        n = nrm(np.array(v0.normal)); a = F["fore"]; w = nrm(np.cross(n, a))
        geo = bmesh.ops.create_cube(bm, size=1.0)
        tab = geo["verts"]
        M = np.stack([w * 0.019, a * 0.0125, n * 0.0024], 1)
        for v in tab:
            p = np.array(v.co)
            v.co = Vector(c + M @ p + w * 0.004 - n * 0.0006)
            for k, val in v0[dl].items():
                v[dl][k] = val
        for f in {f for v in tab for f in v.link_faces}:
            f.material_index = STRAP
    bm.to_mesh(me); bm.free()
    me.update()


def decals(glove, sleeve, fr, side_of, t_of):
    """conforming patches: faces near a surface point are duplicated, lifted 0.4 mm and planar-mapped"""
    def patch(obj, center_fn, mat, w, h, side_axis, up_axis):
        me = obj.data
        bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
        uvl = bm.loops.layers.uv.verify()
        for s in ("R", "L"):
            c0, nrm_hint = center_fn(s)
            verts = [v for v in bm.verts if side_of(np.array(v.co)) == s]
            v0 = min(verts, key=lambda v: np.linalg.norm(np.array(v.co) - c0) - 0.02 * np.dot(np.array(v.normal), nrm_hint))
            c = np.array(v0.co); n = nrm(np.array(v0.normal))
            U = nrm(side_axis(s) - n * np.dot(side_axis(s), n)); Vv = nrm(np.cross(n, U))
            if np.dot(Vv, up_axis(s)) < 0:
                Vv = -Vv
            r = 0.5 * math.hypot(w, h) + 0.006
            faces = [f for f in bm.faces if f.material_index not in NO_TILE_UV
                     and np.linalg.norm(np.array(f.calc_center_median()) - c) < r and np.dot(np.array(f.normal), n) > 0.5]
            if not faces:
                continue
            fv = {v for f in faces for v in f.verts}
            fe = {e for f in faces for e in f.edges}
            dup = bmesh.ops.duplicate(bm, geom=list(fv) + list(fe) + faces)
            nf = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)]
            nv = [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]
            for v in nv:
                v.co = v.co + Vector(n * 0.0004 + np.array(v.normal) * 0.0003)
            for f in nf:
                f.material_index = mat
                for l in f.loops:
                    d = np.array(l.vert.co) - c
                    l[uvl].uv = (0.5 + np.dot(d, U) / w, 0.5 + np.dot(d, Vv) / h)
        bm.to_mesh(me); bm.free()

    # brand logo across the back of each glove, reading from the driver's seat
    patch(glove, lambda s: (fr[s]["wr"] + fr[s]["f"] * 0.045 + fr[s]["back"] * 0.03, fr[s]["back"]), LOGO, 0.042, 0.042,
          lambda s: -fr[s]["side"] if s == "R" else fr[s]["side"], lambda s: fr[s]["f"])
    # suit patches: INK DRIFT on the outer forearm, flag on the upper arm, label near the cuff
    fore_mid = lambda s: fr[s]["el"] + (fr[s]["wr"] - fr[s]["el"]) * 0.45
    patch(sleeve, lambda s: (fore_mid(s) + nrm(fr[s]["outer"] + np.array([0, 0, 0.7])) * 0.05, nrm(fr[s]["outer"] + np.array([0, 0, 0.7]))),
          PINK, 0.075, 0.0375, lambda s: fr[s]["fore"], lambda s: np.array([0, 0, 1.0]))
    up_mid = lambda s: fr[s]["sh"] + (fr[s]["el"] - fr[s]["sh"]) * 0.42
    patch(sleeve, lambda s: (up_mid(s) + fr[s]["outer"] * 0.06, fr[s]["outer"]), PFLAG, 0.06, 0.04,
          lambda s: -fr[s]["upper"] if s == "R" else fr[s]["upper"], lambda s: np.array([0, 0, 1.0]))


def uvs(glove, sleeve, fr, side_of, t_of):
    """tiling UVs in metres / tile: cylindrical round each limb for the suit, box-projected in the hand frame for gloves"""
    def run(obj, fn):
        me = obj.data
        bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
        uvl = bm.loops.layers.uv.verify()
        for f in bm.faces:
            if f.material_index in NO_TILE_UV:
                continue
            uv = [fn(np.array(l.vert.co), np.array(f.normal), f.material_index) for l in f.loops]
            us = [u for u, _ in uv]
            if max(us) - min(us) > 0.5 * fn.wrap:         # keep faces across the cylinder seam contiguous
                uv = [(u + fn.wrap if u < (max(us) + min(us)) / 2 else u, v) for u, v in uv]
            for l, (u, v) in zip(f.loops, uv):
                l[uvl].uv = (u, v)
        bm.to_mesh(me); bm.free()

    def sleeve_uv(p, n, mat):
        s = side_of(p); F = fr[s]
        on_fore = np.dot(p - F["el"], F["upper"]) > 0.0 and t_of(p, s) > -0.30
        o, a = (F["el"], F["fore"]) if on_fore else (F["sh"], F["upper"])
        ref = nrm(F["outer"] - a * np.dot(F["outer"], a)); ref2 = np.cross(a, ref)
        d = p - o
        ang = math.atan2(np.dot(d, ref2), np.dot(d, ref))
        tile = 0.04 if mat in (STRIPE, STRETCH, KNIT) else 0.08
        return ang * 0.05 / tile, np.dot(d, a) / tile
    sleeve_uv.wrap = 2 * math.pi * 0.05 / 0.08

    def glove_uv(p, n, mat):
        s = side_of(p); F = fr[s]
        basis = [F["side"], F["f"], F["back"]]
        k = int(np.argmax([abs(np.dot(n, b)) for b in basis]))
        a, b = [basis[i] for i in range(3) if i != k]
        d = p - F["wr"]
        return np.dot(d, a) / 0.04, np.dot(d, b) / 0.04
    glove_uv.wrap = 1e9

    run(sleeve, sleeve_uv)
    run(glove, glove_uv)


if __name__ == "__main__":
    main()
