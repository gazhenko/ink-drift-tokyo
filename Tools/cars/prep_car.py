"""INK DRIFT: TOKYO -- car processing pipeline (Blender 5.2, headless).

    blender -b -P Tools/cars/prep_car.py -- <input.glb> <car_id> <out_dir> [options]

options:
    --inspect        import/orient/analyse only: prints objects, materials, slot mapping, wheel
                     detection, badge suspects; renders quick views + texture sheet into
                     Tools/cars/cache/inspect/  (nothing is exported)
    --no-preview     skip the EEVEE preview renders
    --config <path>  config JSON (default Tools/cars/configs/<car_id>.json)

Per-car tuning lives in Tools/cars/configs/<car_id>.json (see DEFAULTS below). Every position in
a config is in *car coordinates* = Unity convention: x = right, y = up, z = forward, meters,
origin on the ground midway between the axles (same frame as the <id>_dims.json output).

Output (contract with the game, see Docs/DESIGN.md):
  <out_dir>/<car_id>.fbx   root `Car_<id>`; children `Body`, `Wheel_FL|FR|RL|RR` (pivot = hub,
                           spin axis local X), optional `Caliper_*` (pivot = hub), empties
                           `Light_Head_L|R`, `Light_Tail_L|R`, `Exhaust_L|R` (tail/exhaust point
                           backward). FBX: -Z forward, Y up, transforms applied, meters,
                           triangulated. Car faces Unity +Z.
  <out_dir>/Textures/<car_id>_<slot>_albedo.png ...
  <out_dir>/<car_id>_dims.json
  Tools/cars/previews/<car_id>_*.png
Inside Blender the car faces -Y, its left side is +X, up is +Z (=> Unity +Z fwd, -X left).
"""
import bpy
import bmesh
import json
import math
import os
import re
import subprocess
import sys
import time

import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
VENV_PY = os.path.join(REPO, "Tools", ".venv", "bin", "python")
CARTEX = os.path.join(HERE, "cartex.py")
DECAL_DIR = os.path.join(REPO, "Game", "Assets", "InkDrift", "Art", "Decals")
PREVIEW_DIR = os.path.join(HERE, "previews")
INSPECT_DIR = os.path.join(HERE, "cache", "inspect")

SLOTS = ["M_Paint", "M_PaintAccent", "M_Glass", "M_Chrome", "M_Trim", "M_Carbon", "M_Grille", "M_HeadLight",
         "M_TailLight", "M_Interior", "M_Rim", "M_Tire", "M_Brake", "M_Decal", "M_Plate", "M_Underbody"]

# flat look of every slot (linear RGB, metallic, roughness); textured slots multiply their texture
SLOT_LOOK = {
    "M_Paint": ((0.80, 0.80, 0.80), 0.35, 0.30),
    "M_PaintAccent": ((0.03, 0.03, 0.035), 0.3, 0.30),
    "M_Glass": ((0.012, 0.014, 0.02), 0.0, 0.04),
    "M_Chrome": ((0.85, 0.85, 0.87), 1.0, 0.12),
    "M_Trim": ((0.025, 0.025, 0.028), 0.0, 0.55),
    "M_Carbon": ((0.018, 0.018, 0.02), 0.2, 0.25),
    "M_Grille": ((0.02, 0.02, 0.022), 0.1, 0.5),
    "M_HeadLight": ((0.75, 0.78, 0.82), 0.6, 0.12),
    "M_TailLight": ((0.55, 0.02, 0.02), 0.0, 0.15),
    "M_Interior": ((0.04, 0.04, 0.045), 0.0, 0.65),
    "M_Rim": ((0.55, 0.56, 0.58), 0.9, 0.3),
    "M_Tire": ((0.03, 0.03, 0.03), 0.0, 0.85),
    "M_Brake": ((0.30, 0.30, 0.31), 0.8, 0.45),
    "M_Decal": ((1.0, 1.0, 1.0), 0.0, 0.35),
    "M_Plate": ((1.0, 1.0, 1.0), 0.0, 0.4),
    "M_Underbody": ((0.02, 0.02, 0.022), 0.0, 0.8),
}
TEXTURE_SLOTS_DEFAULT = ["M_Interior", "M_Rim", "M_Tire", "M_HeadLight", "M_TailLight", "M_Grille", "M_Brake"]

# keyword heuristics, evaluated in order on "<material name> | <object name>" (lower case)
SLOT_KEYWORDS = [
    ("DELETE", r"logo|emblem|badge|sticker|brand|lettering|insignia|\bscript\b|manufacturer|watermark"),
    ("M_Plate", r"licen[cs]e|plate|kennzeichen|matricula|number_?plate"),
    ("M_Glass", r"glass|window|windshield|windscreen|vidrio|vitre|scheibe|cristal|glas\b|_glas"),
    ("M_TailLight", r"tail|rear.?light|rear.?lamp|brake.?light|stop.?light|backlight|reverse|rearlight"),
    ("M_HeadLight", r"head|front.?light|lamp|light|lens|reflector|drl|fog|indicator|signal|blinker|turn"),
    ("M_Interior", r"interior|seat|dash|leather|fabric|cloth|steer|carpet|alcantara|cabin|inside|gauge|console|"
                   r"belt|pedal|liner|floormat|stitch|speedo|cluster|screen|display"),
    ("M_Tire", r"tire|tyre|pneu|reifen|neumatic|tread|sidewall"),
    ("M_Brake", r"brake|disc\b|disk|rotor|calip"),
    ("M_Rim", r"\brim|rim\b|rims|wheel|alloy|felge|llanta|jante|spoke"),
    ("M_Carbon", r"carbon|\bcf\b|_cf_|fibre|fiber"),
    ("M_Grille", r"grill|grid|mesh|honeycomb|\bnet\b"),
    ("M_Chrome", r"chrome|chromium|mirror|polished|silver|alumin"),
    ("M_Underbody", r"under|chassis|engine|exhaust|suspension|frame|mechanic|muffler|pipe|axle|bottom|motor"),
    ("M_Trim", r"trim|black|plastic|rubber|seal|matte|wiper|gasket|hardware|bumper_?black"),
    ("M_Paint", r"paint|body|carpaint|exterior|colou?r|shell|coat|main|car_?body"),
]

DEFAULTS = {
    "traffic": False,
    "rotate": [0, 0, 0],            # euler XYZ deg applied first (fix up-axis of odd imports)
    "forward": "auto",              # Blender axis the nose points to after 'rotate': -Y|+Y|-X|+X|auto
    "wheelbase": None,              # real wheelbase [m] -> scale (preferred)
    "length": None,                 # real length [m] -> scale (fallback)
    "scale": None,                  # explicit scale factor (overrides both)
    "delete_objects": [],           # regex on source object names -> removed before anything else
    "delete_materials": [],         # regex on source material names -> faces removed
    "delete_boxes": [],             # [[x,y,z, sx,sy,sz], ...] car coords: loose parts fully inside are removed
    "delete_parts_near": [],        # [[x,y,z, radius, maxsize], ...] car coords: loose parts whose bbox centre is
                                    # within radius and whose largest extent < maxsize are removed (badges)
    "material_map": {},             # regex(material name) -> slot
    "object_map": {},               # regex(object name) -> slot (wins over material_map)
    "box_map": [],                  # [[x,y,z, sx,sy,sz, slot], ...] faces whose centre is inside -> slot
    "texture_slots": None,          # slots that keep textures (default TEXTURE_SLOTS_DEFAULT)
    "texture_fixes": {},            # regex(image name) -> {"drop":true} | {"fill":[[u0,v0,u1,v1],...],
                                    #  "color":[r,g,b](0-255) | "median"}
    "max_texture": 2048,
    "wheel_objects": {},            # optional {"FL": regex, ...} (source object names) instead of auto
    "caliper_regex": r"calip|brake.?pad",      # regex (material/object) for parts that steer but don't spin
    "no_caliper": False,
    "tri_budget": 170000,
    "wheel_tris": 9000,
    "slot_weights": {},
    "drop_interior": False,         # delete M_Interior faces (traffic)
    "lower": 0.03,                  # ride height drop [m]
    "flush": True,
    "max_push": 0.05,
    "track_push_extra": 0.0,
    "kit": {"wing": {}, "splitter": {}, "canards": {}, "skirts": {}},
    "plates": {"style": "private", "top": "品川 300", "kana": "あ", "num": "86-86",
               "front": "auto", "rear": "auto", "front_y": 0.38, "rear_y": 0.55},
    "decals": [],
    "banner": None,                 # windshield banner text (None -> no banner)
    "banner_accent": "#FF2D7A",
    "lights": {},                   # overrides {"Light_Head_L": [x,y,z], ...} car coords
    "exhaust": None,                # [[x,y,z],[x,y,z]] car coords (L, R) override
    "preview_color": [0.9, 0.05, 0.3],
    "paint_from_texture": False,
}

T0 = time.time()


def log(*a):
    print(f"[prep_car {time.time() - T0:7.1f}s]", *a, flush=True)


# ----------------------------------------------------------------------------------------------
# coordinates: car (Unity-like: x right, y up, z fwd)  <->  Blender (x left, y back, z up)
def c2b(p):
    return Vector((-p[0], -p[2], p[1]))


def b2c(v):
    return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]


# ----------------------------------------------------------------------------------------------
# generic helpers
def deselect_all():
    for o in bpy.context.scene.objects:
        if o is not None:
            o.select_set(False)


def activate(obj, select_only=True):
    if select_only:
        deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_np(me):
    nv, npoly, nl = len(me.vertices), len(me.polygons), len(me.loops)
    co = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get("co", co)
    ls = np.empty(npoly, np.int64)
    lt = np.empty(npoly, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    mi = np.empty(npoly, np.int64)
    me.polygons.foreach_get("material_index", mi)
    ctr = np.empty(npoly * 3, np.float64)
    me.polygons.foreach_get("center", ctr)
    nrm = np.empty(npoly * 3, np.float64)
    me.polygons.foreach_get("normal", nrm)
    area = np.empty(npoly, np.float64)
    me.polygons.foreach_get("area", area)
    src = np.zeros(npoly, np.int64)
    if "src" in me.attributes:
        me.attributes["src"].data.foreach_get("value", src)
    return dict(co=co.reshape(-1, 3), ls=ls, lt=lt, lv=lv, mi=mi, ctr=ctr.reshape(-1, 3),
                nrm=nrm.reshape(-1, 3), area=area, src=src)


def tri_count(me):
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum())


def select_faces(obj, mask):
    me = obj.data
    mask = np.asarray(mask, bool)
    n = len(me.polygons)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("edge_index", le)
    lmask = np.repeat(mask, lt)
    vs = np.zeros(len(me.vertices), bool)
    vs[lv[lmask]] = True
    es = np.zeros(len(me.edges), bool)
    es[le[lmask]] = True
    me.vertices.foreach_set("select", vs)
    me.edges.foreach_set("select", es)
    me.polygons.foreach_set("select", mask)
    me.update()


def delete_faces(obj, mask):
    if not np.any(mask):
        return
    activate(obj)
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    select_faces(obj, mask)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")


def split_faces(obj, mask, name):
    """Move the masked faces of obj into a new object called name; returns it (or None)."""
    if not np.any(mask):
        return None
    if np.all(mask):
        dup = obj.copy()
        dup.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(dup)
        delete_faces(obj, np.ones(len(obj.data.polygons), bool))
        dup.name = name
        return dup
    before = set(bpy.data.objects)
    activate(obj)
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    select_faces(obj, mask)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    new = [o for o in bpy.data.objects if o not in before]
    if not new:
        return None
    new[0].name = name
    new[0].data.name = name
    return new[0]


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    deselect_all()
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    if name:
        o.name = name
        o.data.name = name
    return o


def components(me, co=None):
    """Connected components (vertex labels 0..K-1) via vectorised union-find over edges."""
    nv = len(me.vertices)
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    parent = np.arange(nv)
    for _ in range(200):
        a, b = parent[ev[:, 0]], parent[ev[:, 1]]
        diff = a != b
        if not diff.any():
            break
        a, b = a[diff], b[diff]
        m = np.minimum(a, b)
        np.minimum.at(parent, a, m)
        np.minimum.at(parent, b, m)
        for _ in range(64):
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    _, lab = np.unique(parent, return_inverse=True)
    return lab


class Analysis:
    """Per-loose-part bounding boxes, materials, face sets."""

    def __init__(self, obj):
        me = obj.data
        d = mesh_np(me)
        self.__dict__.update(d)
        self.vlab = components(me)
        self.flab = self.vlab[self.lv[self.ls]] if len(self.ls) else np.zeros(0, np.int64)
        K = int(self.vlab.max()) + 1 if len(self.vlab) else 0
        self.K = K
        co = self.co
        self.cmin = np.full((K, 3), np.inf)
        self.cmax = np.full((K, 3), -np.inf)
        for ax in range(3):
            np.minimum.at(self.cmin[:, ax], self.vlab, co[:, ax])
            np.maximum.at(self.cmax[:, ax], self.vlab, co[:, ax])
        self.cfaces = np.bincount(self.flab, minlength=K)
        self.carea = np.bincount(self.flab, weights=self.area, minlength=K)
        # dominant material and source object per component (by area)
        self.cmat = np.zeros(K, np.int64)
        self.csrc = np.zeros(K, np.int64)
        if len(self.flab):
            for arr, out in ((self.mi, self.cmat), (self.src, self.csrc)):
                key = self.flab * 100000 + arr
                uk, inv = np.unique(key, return_inverse=True)
                w = np.bincount(inv, weights=self.area + 1e-9)
                comp = uk // 100000
                order = np.lexsort((-w, comp))
                firsts = order[np.r_[True, comp[order][1:] != comp[order][:-1]]]
                out[comp[firsts]] = uk[firsts] % 100000
        self.cctr = (self.cmin + self.cmax) / 2
        self.cext = self.cmax - self.cmin
        valid = self.cfaces > 0
        self.bmin = self.cmin[valid].min(0)
        self.bmax = self.cmax[valid].max(0)


# ----------------------------------------------------------------------------------------------
# config
def load_config(car_id, path=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    path = path or os.path.join(HERE, "configs", f"{car_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        log("config", path)
    else:
        log("no config at", path, "-> defaults")
    if cfg["traffic"]:
        cfg.setdefault("_traffic_defaults", True)
        if "tri_budget" not in (user if os.path.exists(path) else {}):
            cfg["tri_budget"] = 28000
        cfg["wheel_tris"] = min(cfg["wheel_tris"], 1500)
        if "drop_interior" not in (user if os.path.exists(path) else {}):
            cfg["drop_interior"] = True  # traffic: interior is invisible behind the dark glass
    return cfg


# ----------------------------------------------------------------------------------------------
# 1. import + flatten
def import_model(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".blend":
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects = src.objects
        for o in dst.objects:
            if o:
                bpy.context.scene.collection.objects.link(o)
    else:
        raise SystemExit(f"unsupported input {path}")
    log("imported", path, len(bpy.data.objects), "objects")


def flatten(cfg):
    """Every renderable object -> a world-space mesh with one UV map, no colours; returns names list."""
    deps = bpy.context.evaluated_depsgraph_get()
    del_obj = [re.compile(r, re.I) for r in cfg["delete_objects"]]
    auto_del = re.compile(r"shadow|ground|backdrop|studio|floor_?plane|^plane(\.\d+)?$|cube_?map|env_?sphere", re.I)
    names, new_objs = [], []
    originals = list(bpy.data.objects)
    for o in originals:
        if o.type not in ("MESH", "CURVE", "SURFACE", "FONT", "META"):
            continue
        if o.hide_render or not o.visible_get():
            log("  skip hidden", o.name)
            continue
        if any(r.search(o.name) for r in del_obj):
            log("  delete (config)", o.name)
            continue
        if auto_del.search(o.name) and o.type == "MESH":
            log("  delete (auto ground/shadow)", o.name)
            continue
        ev = o.evaluated_get(deps)
        try:
            me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=deps)
        except RuntimeError:
            continue
        if me is None or len(me.polygons) == 0:
            continue
        mw = o.matrix_world.copy()
        me.transform(mw)
        if mw.determinant() < 0:
            me.flip_normals()
        # object-level material slots -> mesh
        if len(o.material_slots) and any(s.link == "OBJECT" for s in o.material_slots):
            me.materials.clear()
            for s in o.material_slots:
                me.materials.append(s.material)
        # one UV map called UVMap
        if len(me.uv_layers) == 0:
            me.uv_layers.new(name="UVMap")
        act = me.uv_layers.active_index if me.uv_layers.active_index >= 0 else 0
        for i in reversed(range(len(me.uv_layers))):
            if i != act:
                me.uv_layers.remove(me.uv_layers[i])
        me.uv_layers[0].name = "UVMap"
        for ca in list(me.color_attributes):
            me.color_attributes.remove(ca)
        a = me.attributes.new("src", "INT", "FACE")
        a.data.foreach_set("value", np.full(len(me.polygons), len(names), np.int64))
        nob = bpy.data.objects.new("tmp_" + o.name, me)
        bpy.context.scene.collection.objects.link(nob)
        names.append(o.name)
        new_objs.append(nob)
    for o in originals:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    for o in new_objs:  # placeholder material for empty slots
        if len(o.data.materials) == 0:
            o.data.materials.append(None)
    obj = join(new_objs, "Source")
    # empty material slots -> a dummy material so slot logic works
    me = obj.data
    for i, m in enumerate(me.materials):
        if m is None:
            dm = bpy.data.materials.get("_nomat") or bpy.data.materials.new("_nomat")
            me.materials[i] = dm
    log("flattened", len(names), "objects ->", len(me.polygons), "faces,", tri_count(me), "tris,",
        len(me.materials), "materials")
    return obj, names


# ----------------------------------------------------------------------------------------------
# 2. orientation
def orient(obj, cfg, names):
    me = obj.data
    if any(cfg["rotate"]):
        me.transform(Euler([math.radians(a) for a in cfg["rotate"]]).to_matrix().to_4x4())
    fwd = cfg["forward"]
    yaw = {"-Y": 0, "+Y": 180, "+X": -90, "-X": 90}
    if fwd in yaw:
        me.transform(Matrix.Rotation(math.radians(yaw[fwd]), 4, "Z"))
    else:
        d = mesh_np(me)
        ext = d["co"].max(0) - d["co"].min(0)
        if ext[0] > ext[1]:
            me.transform(Matrix.Rotation(math.radians(90), 4, "Z"))
            d = mesh_np(me)
        # head vs tail lights by names
        mats = [m.name.lower() if m else "" for m in me.materials]
        head = re.compile(r"head|front.?light|front.?lamp|drl|grill", re.I)
        tail = re.compile(r"tail|rear.?light|rear.?lamp|brake.?light|stop.?light|exhaust|muffler", re.I)
        fh = np.array([bool(head.search(mats[m] + " " + names[s])) for m, s in zip(d["mi"], d["src"])]) \
            if len(d["mi"]) < 4_000_000 else np.zeros(len(d["mi"]), bool)
        ft = np.array([bool(tail.search(mats[m] + " " + names[s])) for m, s in zip(d["mi"], d["src"])]) \
            if len(d["mi"]) < 4_000_000 else np.zeros(len(d["mi"]), bool)
        if fh.any() and ft.any():
            yh = np.average(d["ctr"][fh, 1], weights=d["area"][fh] + 1e-9)
            yt = np.average(d["ctr"][ft, 1], weights=d["area"][ft] + 1e-9)
            if yh > yt:
                me.transform(Matrix.Rotation(math.radians(180), 4, "Z"))
            log("auto forward: head y=%.2f tail y=%.2f" % (yh, yt))
        else:
            log("WARNING auto forward: no head/tail names -> assuming nose at -Y; set 'forward' in config")
    me.update()


# ----------------------------------------------------------------------------------------------
# 3. wheels
def remove_ground_planes(obj):
    A = Analysis(obj)
    ext = A.cext
    flat = (ext[:, 2] < 0.01 * np.maximum(ext[:, 0], ext[:, 1])) & (A.cfaces > 0)
    span = A.bmax - A.bmin
    big = (ext[:, 0] > 0.85 * span[0]) & (ext[:, 1] > 0.85 * span[1])
    low = A.cmin[:, 2] <= A.bmin[2] + 0.02 * span[1]
    kill = flat & big & low
    if kill.any():
        log("removing", int(kill.sum()), "ground/shadow plane parts")
        delete_faces(obj, kill[A.flab])


def find_wheels(A, cfg, names):
    """Returns {key: dict(c=Vector, r, x_in, x_out, comps=set)} in current (unscaled) coords."""
    lo, hi = np.percentile(A.co, 0.5, axis=0), np.percentile(A.co, 99.5, axis=0)
    span = hi - lo
    L = span[1]
    xc = float(np.average(A.ctr[:, 0], weights=A.area + 1e-12))
    yc = (lo[1] + hi[1]) / 2
    ext, ctr = A.cext, A.cctr
    wheels = {}
    keys = (("FL", 1, -1), ("FR", -1, -1), ("RL", 1, 1), ("RR", -1, 1))
    if cfg["wheel_objects"]:
        for key, sx, sy in keys:
            rx = re.compile(cfg["wheel_objects"][key], re.I)
            srcs = [i for i, n in enumerate(names) if rx.search(n)]
            fm = np.isin(A.src, srcs)
            comps = set(np.unique(A.flab[fm]).tolist())
            if not comps:
                raise SystemExit(f"wheel_objects {key}: nothing matched")
            idx = np.array(sorted(comps))
            mn, mx = A.cmin[idx].min(0), A.cmax[idx].max(0)
            c = (mn + mx) / 2
            r = max(mx[1] - mn[1], mx[2] - mn[2]) / 2
            wheels[key] = dict(c=Vector(c), r=r, x_in=mn[0] if sx > 0 else mx[0], x_out=mx[0] if sx > 0 else mn[0],
                               tire=comps)
        return wheels
    zmin = lo[2]
    sq = np.abs(ext[:, 1] - ext[:, 2]) < 0.16 * np.maximum(ext[:, 2], 1e-6)
    cand = (A.cfaces > 0) & (A.cmin[:, 2] <= zmin + 0.025 * L) & (ext[:, 2] > 0.10 * L) & (ext[:, 2] < 0.28 * L) \
        & sq & (ext[:, 0] < 0.16 * L) & (ext[:, 0] < 0.85 * ext[:, 2]) & (np.abs(ctr[:, 0] - xc) > 0.22 * span[0])
    if cand.any():
        ground = A.cmin[cand, 2].min()
        cand &= A.cmin[:, 2] <= ground + 0.012 * L
    for key, sx, sy in keys:
        sel = np.where(cand & (np.sign(ctr[:, 0] - xc) == sx) & (np.sign(ctr[:, 1] - yc) == sy))[0]
        if len(sel) == 0:
            raise SystemExit(f"wheel {key} not found (no ground-touching round part); use wheel_objects")
        main = sel[np.argmax(ext[sel, 2] * (1 + 0.01 * ext[sel, 0]))]
        c0, r0 = ctr[main], ext[main, 2] / 2
        near = sel[(np.abs(ctr[sel, 1] - c0[1]) < 0.2 * r0) & (np.abs(ctr[sel, 2] - c0[2]) < 0.2 * r0)
                   & (np.abs(ctr[sel, 0] - c0[0]) < 1.2 * r0)]
        mn, mx = A.cmin[near].min(0), A.cmax[near].max(0)
        c = (mn + mx) / 2
        r = max(mx[1] - mn[1], mx[2] - mn[2]) / 2
        wheels[key] = dict(c=Vector(c), r=r, x_in=mn[0] if sx > 0 else mx[0], x_out=mx[0] if sx > 0 else mn[0],
                           tire=set(near.tolist()))
    return wheels


def classify_wheel_parts(A, wheels, cfg, mats, names):
    """Assign loose parts to wheels (spin) or calipers (steer only). Returns face target array."""
    target = np.zeros(len(A.flab), np.int64)  # 0 body, 1-4 wheels, 5-8 calipers
    comp_t = np.zeros(A.K, np.int64)
    cal_rx = re.compile(cfg["caliper_regex"], re.I) if cfg["caliper_regex"] else None
    tire_rx = re.compile(SLOT_KEYWORDS[5][1] + "|" + SLOT_KEYWORDS[7][1], re.I)
    ext, ctr = A.cext, A.cctr
    for wi, key in enumerate(("FL", "FR", "RL", "RR")):
        w = wheels[key]
        c, r = w["c"], w["r"]
        sx = 1 if key[1] == "L" else -1
        lo_x, hi_x = (w["x_in"] - 0.5 * r, w["x_out"] + 0.08 * r) if sx > 0 else (w["x_out"] - 0.08 * r,
                                                                                 w["x_in"] + 0.5 * r)
        k = 1.04 * r
        inside = (A.cfaces > 0) & (A.cmin[:, 1] >= c[1] - k) & (A.cmax[:, 1] <= c[1] + k) & \
                 (A.cmin[:, 2] >= c[2] - k) & (A.cmax[:, 2] <= c[2] + k) & (A.cmin[:, 0] >= lo_x) & \
                 (A.cmax[:, 0] <= hi_x)
        yz = np.maximum(ext[:, 1], ext[:, 2])
        ratio = np.minimum(ext[:, 1], ext[:, 2]) / np.maximum(yz, 1e-9)
        centered = (np.abs(ctr[:, 1] - c[1]) < 0.12 * r) & (np.abs(ctr[:, 2] - c[2]) < 0.12 * r) & (ratio > 0.7)
        spin = inside & centered
        spin[list(w["tire"])] = True
        spin_mats = set(A.cmat[spin].tolist())
        offc = np.where(inside & ~spin)[0]
        for ci in offc:
            label = (mats[A.cmat[ci]] + " " + names[A.csrc[ci]]).lower()
            is_cal = bool(cal_rx and cal_rx.search(label))
            if not is_cal and A.cmat[ci] not in spin_mats and yz[ci] > 0.12 * r:
                is_cal = True
            if tire_rx.search(label):
                is_cal = False
            if cfg["no_caliper"]:
                is_cal = False
            comp_t[ci] = 5 + wi if is_cal else 1 + wi
        comp_t[spin] = 1 + wi
    return comp_t[A.flab], comp_t


def unsteer_wheels(obj, A, wheels, comp_t):
    """Remove steer/camber baked into the source wheels: rotate each wheel (and its caliper) so the
    tyre's spin axis (smallest PCA axis of the tyre vertices) is the X axis."""
    me = obj.data
    co = A.co.copy()
    changed = False
    for wi, key in enumerate(("FL", "FR", "RL", "RR")):
        w = wheels[key]
        tire_v = np.isin(A.vlab, list(w["tire"]))
        pts = co[tire_v] - np.array(w["c"])
        if len(pts) < 20:
            continue
        cov = np.cov(pts.T)
        evals, evecs = np.linalg.eigh(cov)
        ax = evecs[:, 0]
        if ax[0] < 0:
            ax = -ax
        yaw = math.degrees(math.atan2(ax[1], ax[0]))
        camber = math.degrees(math.atan2(ax[2], math.hypot(ax[0], ax[1])))
        log(f"  wheel {key} axis yaw {yaw:.1f} camber {camber:.1f} evals {np.round(evals, 4).tolist()}")
        if (abs(yaw) < 0.8 and abs(camber) < 0.8) or abs(yaw) > 45 or abs(camber) > 15:
            continue
        R = Vector(ax).rotation_difference(Vector((1, 0, 0))).to_matrix()
        comps = np.where((comp_t == 1 + wi) | (comp_t == 5 + wi))[0]
        vm = np.isin(A.vlab, comps)
        c = np.array(w["c"])
        co[vm] = (co[vm] - c) @ np.array(R).T + c
        changed = True
        log(f"  unsteer {key}: yaw {yaw:.1f} deg, camber {camber:.1f} deg removed")
    if changed:
        me.vertices.foreach_set("co", co.ravel())
        me.update()
    return changed


# ----------------------------------------------------------------------------------------------
# 4. materials -> slots
def node_upstream_image(sock, depth=0):
    if not sock.is_linked or depth > 8:
        return None
    n = sock.links[0].from_node
    if n.type == "TEX_IMAGE" and n.image:
        return n.image
    for inp in n.inputs:
        if inp.type in ("RGBA", "VALUE", "VECTOR") and inp.is_linked:
            img = node_upstream_image(inp, depth + 1)
            if img:
                return img
    return None


def mat_info(m):
    info = dict(name=m.name if m else "_nomat", color=(0.5, 0.5, 0.5), alpha=1.0, metallic=0.0, roughness=0.5,
                image=None, normal=None, emission=None, uses_alpha=False, transmission=0.0)
    if not m or not m.node_tree:
        if m:
            info["color"] = tuple(m.diffuse_color[:3])
        return info
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        img = next((n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
        info["image"] = img
        em = next((n for n in m.node_tree.nodes if n.type == "EMISSION"), None)
        if em:
            info["color"] = tuple(em.inputs["Color"].default_value[:3])
        return info
    bc = bsdf.inputs["Base Color"]
    info["color"] = tuple(bc.default_value[:3])
    info["image"] = node_upstream_image(bc)
    if info["image"] is not None:
        # factor colour from a multiply node, if any
        n = bc.links[0].from_node
        if n.type in ("MIX", "MIX_RGB"):
            for inp in n.inputs:
                if inp.type == "RGBA" and not inp.is_linked:
                    info["color"] = tuple(inp.default_value[:3])
                    break
        else:
            info["color"] = (1.0, 1.0, 1.0)
    info["metallic"] = bsdf.inputs["Metallic"].default_value
    info["roughness"] = bsdf.inputs["Roughness"].default_value
    a = bsdf.inputs["Alpha"]
    info["alpha"] = a.default_value
    info["uses_alpha"] = a.is_linked or a.default_value < 0.99
    t = bsdf.inputs.get("Transmission Weight")
    if t is not None:
        info["transmission"] = t.default_value
    nm = bsdf.inputs["Normal"]
    if nm.is_linked:
        info["normal"] = node_upstream_image(nm)
    return info


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def img_mean(img):
    if img is None:
        return None
    try:
        w, h = img.size
        if w * h == 0:
            return None
        small = img.copy()
        small.scale(min(64, w), min(64, h))
        a = np.empty(small.size[0] * small.size[1] * 4, np.float32)
        small.pixels.foreach_get(a)
        bpy.data.images.remove(small)
        a = a.reshape(-1, 4)
        srgb = a[:, :3].mean(0)
        return tuple(float(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92) for v in srgb)
    except Exception:
        return None


def heuristic_slot(info, label, in_wheel, is_caliper):
    s = None
    for slot, rx in SLOT_KEYWORDS:
        if re.search(rx, label, re.I):
            s = slot
            break
    col = info["color"]
    if info["image"] is not None:
        mc = img_mean(info["image"])
        if mc:
            col = tuple(a * b for a, b in zip(col, mc))
    if s == "DELETE":
        return "DELETE"
    if is_caliper:
        return "M_Brake"
    if in_wheel:
        if s in ("M_Tire", "M_Brake"):
            return s
        if s == "M_Rim":
            return s
        if lum(col) < 0.05 and info["roughness"] > 0.45 and info["metallic"] < 0.5:
            return "M_Tire"
        return "M_Rim"
    if s is None:
        if info["transmission"] > 0.5 or (info["uses_alpha"] and info["alpha"] < 0.7 and info["image"] is None):
            s = "M_Glass"
        elif info["metallic"] > 0.7 and info["roughness"] < 0.35:
            s = "M_Chrome"
        else:
            s = "M_Trim"
    if s == "M_Tire":
        s = "M_Trim"
    elif s == "M_Rim":
        s = "M_Chrome"
    elif s == "M_Brake":
        s = "M_Underbody"
    return s


def assign_slots(objs, cfg, names, report):
    """objs: list of (obj, role) role in body|wheel|caliper. Rebuilds material slots -> final names.
    Returns {slot: [source info dicts with face area]}"""
    mm = [(re.compile(k, re.I), v) for k, v in cfg["material_map"].items()]
    om = [(re.compile(k, re.I), v) for k, v in cfg["object_map"].items()]
    sources = {}
    infos = {}
    for obj, role in objs:
        me = obj.data
        d = mesh_np(me)
        mats = list(me.materials)
        for m in mats:
            if m not in infos:
                infos[m] = mat_info(m)
        pair = d["mi"] * 100000 + d["src"]
        up, inv = np.unique(pair, return_inverse=True)
        slot_of_pair = []
        for p in up:
            mi_, si = int(p // 100000), int(p % 100000)
            m = mats[mi_]
            if m not in infos:
                infos[m] = mat_info(m)
            info = infos[m]
            mname, oname = info["name"], names[si] if si < len(names) else ""
            slot = None
            for rx, s in om:
                if rx.search(oname):
                    slot = s
                    break
            if slot is None:
                for rx, s in mm:
                    if rx.search(mname):
                        slot = s
                        break
            if slot is None:
                slot = heuristic_slot(info, (mname + " | " + oname).lower(), role == "wheel", role == "caliper")
            if slot != "DELETE" and cfg["traffic"] and slot == "M_PaintAccent":
                slot = "M_Paint"
            if slot == "DELETE":
                pass
            elif role == "wheel" and slot not in ("M_Rim", "M_Tire", "M_Brake", "M_Decal"):
                slot = "M_Rim" if slot != "M_Trim" else "M_Tire"
            if role == "caliper" and slot != "DELETE":
                slot = "M_Brake"
            if role == "body" and slot in ("M_Rim", "M_Tire", "M_Brake"):
                slot = {"M_Rim": "M_Chrome", "M_Tire": "M_Trim", "M_Brake": "M_Underbody"}[slot]
            if slot == "DELETE":
                slot = "_DELETE"
            slot_of_pair.append(slot)
            report.setdefault((role, mname, oname), slot)
        face_slot = np.array(slot_of_pair, dtype=object)[inv]
        # box overrides
        for bx in cfg["box_map"]:
            c = c2b(bx[:3])
            s = Vector((abs(bx[3]), abs(bx[5]), abs(bx[4]))) / 2
            ins = np.all(np.abs(d["ctr"] - np.array(c)) <= np.array(s), axis=1)
            face_slot[ins] = bx[6]
        # delete
        dele = face_slot == "_DELETE"
        if role == "body" and cfg.get("drop_interior"):
            dele |= face_slot == "M_Interior"
        # source tracking for texture building
        for p_i, p in enumerate(up):
            mi_ = int(p // 100000)
            fm = (inv == p_i) & ~dele
            if not fm.any():
                continue
            for slot in np.unique(face_slot[fm]):
                if slot == "_DELETE":
                    continue
                a = float(d["area"][fm & (face_slot == slot)].sum())
                sources.setdefault(slot, {}).setdefault(infos[mats[mi_]]["name"], [infos[mats[mi_]], 0.0])
                sources[slot][infos[mats[mi_]]["name"]][1] += a
        # store per-face slot + original material index (for UV/texture remap) as attributes
        uslots = [s for s in SLOTS if s in set(face_slot.tolist())]
        sidx = np.array([uslots.index(s) if s in uslots else 0 for s in face_slot.tolist()], np.int64)
        a = me.attributes.get("srcmat") or me.attributes.new("srcmat", "INT", "FACE")
        a.data.foreach_set("value", d["mi"])
        obj["_srcmats"] = [infos[m]["name"] for m in mats]
        me.materials.clear()
        for s in uslots:
            me.materials.append(bpy.data.materials.get(s) or bpy.data.materials.new(s))
        me.polygons.foreach_set("material_index", sidx)
        me.update()
        if dele.any():
            delete_faces(obj, dele)
    return sources


# ----------------------------------------------------------------------------------------------
# 5. textures
def img_pixels(img, w=None, h=None):
    if w and h and tuple(img.size) != (w, h):
        im2 = img.copy()
        im2.scale(w, h)
        a = np.empty(w * h * 4, np.float32)
        im2.pixels.foreach_get(a)
        bpy.data.images.remove(im2)
        return a.reshape(h, w, 4)
    W, H = img.size
    a = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(H, W, 4)


def save_png(arr, path):
    h, w, _ = arr.shape
    name = os.path.basename(path)
    old = bpy.data.images.get(name)
    if old:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.clip(arr, 0, 1).astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.filepath = path
    return img


def pot(n, cap):
    p = 1
    while p < n and p < cap:
        p *= 2
    return min(p, cap)


def lin2srgb(c):
    return [((1.055 * (v ** (1 / 2.4)) - 0.055) if v > 0.0031308 else 12.92 * v) for v in c]


def apply_texture_fixes(img, arr, cfg):
    for rx, fx in cfg["texture_fixes"].items():
        if re.search(rx, img.name, re.I):
            if fx.get("drop"):
                return None
            H, W, _ = arr.shape
            for (u0, v0, u1, v1) in fx.get("fill", []):
                x0, x1 = int(u0 * W), int(math.ceil(u1 * W))
                y0, y1 = int(v0 * H), int(math.ceil(v1 * H))
                if fx.get("color", "median") == "median":
                    ring = np.concatenate([arr[max(0, y0 - 4):y0, x0:x1].reshape(-1, 4),
                                           arr[y1:y1 + 4, x0:x1].reshape(-1, 4),
                                           arr[y0:y1, max(0, x0 - 4):x0].reshape(-1, 4),
                                           arr[y0:y1, x1:x1 + 4].reshape(-1, 4)])
                    col = np.median(ring, axis=0) if len(ring) else np.array([0, 0, 0, 1])
                else:
                    col = np.array(list(np.array(fx["color"]) / 255.0) + [1.0])
                arr[y0:y1, x0:x1] = col
    return arr


def clean_tire_texture(arr):
    """Tyre sidewalls carry brand names / size lettering: paint every light texel with the median rubber
    colour (rubber is dark, lettering is light)."""
    if arr is None:
        return arr
    rgb = arr[..., :3]
    lum_ = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    sat = rgb.max(-1) - rgb.min(-1)
    rubber = (lum_ < 0.2) & (sat < 0.08)
    if rubber.mean() < 0.3:
        return arr  # not a dark rubber texture
    med = np.median(rgb[rubber], axis=0)
    letter = ~rubber
    for _ in range(2):  # grow over anti-aliased edges
        letter = letter | np.roll(letter, 1, 0) | np.roll(letter, -1, 0) | np.roll(letter, 1, 1) | np.roll(letter, -1, 1)
    arr[letter, :3] = med
    return arr


def build_materials(objs, sources, cfg, car_id, tex_dir):
    """Create the final M_* materials (and their textures)."""
    tex_slots = cfg["texture_slots"] or TEXTURE_SLOTS_DEFAULT
    os.makedirs(tex_dir, exist_ok=True)
    made = {}
    for slot in SLOTS:
        if slot not in sources or slot in ("M_Decal", "M_Plate"):
            continue
        srcs = sorted(sources[slot].values(), key=lambda x: -x[1])
        base, met, rough = SLOT_LOOK[slot]
        total = sum(a for _, a in srcs) + 1e-12
        textured = [(i, a) for i, a in srcs if i["image"] is not None and i["image"].size[0] > 0]
        tex = None
        uv_remap = None
        if slot in tex_slots and textured:
            imgs = []
            for i, a in textured:
                if i["image"] not in imgs:
                    imgs.append(i["image"])
            cap = cfg["max_texture"] if slot in ("M_Interior", "M_Rim", "M_Tire", "M_HeadLight", "M_TailLight") \
                else 1024
            flat_srcs = [i for i, a in srcs if i["image"] is None]
            if len(imgs) == 1 and not flat_srcs:
                img = imgs[0]
                w, h = pot(img.size[0], cap), pot(img.size[1], cap)
                arr = img_pixels(img, w, h)
                arr = apply_texture_fixes(img, arr, cfg)
                if slot == "M_Tire" and cfg.get("tire_clean", True):
                    arr = clean_tire_texture(arr)
                if arr is not None:
                    # multiply by the factor colour of the dominant source
                    fc = textured[0][0]["color"]
                    if max(fc) < 0.99:
                        arr[..., :3] *= np.array(lin2srgb(fc))
                    tex = save_png(arr, os.path.join(tex_dir, f"{car_id}_{slot[2:].lower()}_albedo.png"))
            else:
                # atlas: textured sources in a grid, flat sources as swatches in a bottom strip
                S = cap
                g = int(math.ceil(math.sqrt(len(imgs))))
                strip = 32 if flat_srcs else 0
                cw, ch = S // g, (S - strip) // g
                atlas = np.zeros((S, S, 4), np.float32)
                cells = {}
                # NOTE: numpy row 0 == image bottom (Blender pixel order), so y0 counts from bottom
                atlas = np.zeros((S, S, 4), np.float32)
                for k, img in enumerate(imgs):
                    cx, cy = k % g, k // g
                    arr = img_pixels(img, cw, ch)
                    arr = apply_texture_fixes(img, arr, cfg)
                    if slot == "M_Tire" and cfg.get("tire_clean", True):
                        arr = clean_tire_texture(arr)
                    if arr is None:
                        arr = np.ones((ch, cw, 4), np.float32)
                    fc = next((i["color"] for i, a in textured if i["image"] == img), (1, 1, 1))
                    if max(fc) < 0.99:
                        arr[..., :3] *= np.array(lin2srgb(fc))
                    y0 = strip + cy * ch
                    atlas[y0:y0 + ch, cx * cw:(cx + 1) * cw] = arr
                    cells[img.name] = ((cx * cw + 1) / S, (y0 + 1) / S, (cw - 2) / S, (ch - 2) / S)
                sw = {}
                for k, i in enumerate(flat_srcs):
                    x0 = (k % (S // strip)) * strip if strip else 0
                    col = lin2srgb(i["color"]) + [1.0]
                    atlas[0:strip, x0:x0 + strip] = np.array(col)
                    sw[i["name"]] = ((x0 + strip / 2) / S, (strip / 2) / S)
                tex = save_png(atlas, os.path.join(tex_dir, f"{car_id}_{slot[2:].lower()}_albedo.png"))
                uv_remap = dict(cells=cells, swatches=sw, wrap=True)
                log(f"  {slot}: atlas of {len(imgs)} textures + {len(flat_srcs)} swatches")
            if tex is not None:
                base = (1.0, 1.0, 1.0)
                met = float(np.average([i["metallic"] for i, a in srcs], weights=[a for i, a in srcs]))
                rough = float(np.average([i["roughness"] for i, a in srcs], weights=[a for i, a in srcs]))
        if tex is None and slot not in ("M_Paint", "M_PaintAccent", "M_Glass") and srcs:
            # flat: area-weighted source colour (texture means included) but keep the slot's character
            cols, ws = [], []
            for i, a in srcs:
                c = i["color"]
                if i["image"] is not None:
                    mc = img_mean(i["image"])
                    if mc:
                        c = tuple(x * y for x, y in zip(c, mc))
                cols.append(c)
                ws.append(a)
            col = tuple(np.average(np.array(cols), axis=0, weights=ws))
            if slot in ("M_Trim", "M_Carbon", "M_Underbody", "M_Grille", "M_Tire"):
                col = tuple(min(c, 0.06) for c in col)
            if slot in ("M_HeadLight", "M_TailLight", "M_Interior", "M_Rim", "M_Brake", "M_Grille"):
                base = col
        mat = bpy.data.materials.get(slot) or bpy.data.materials.new(slot)
        setup_material(mat, base, met, rough, tex, alpha=(slot in ("M_Grille",) and tex is not None
                                                            and any(i["uses_alpha"] for i, a in srcs)))
        made[slot] = dict(tex=tex, remap=uv_remap)
    for slot in SLOTS:
        mat = bpy.data.materials.get(slot)
        if mat and slot not in made and not mat.get("_inkdrift"):
            base, met, rough = SLOT_LOOK[slot]
            setup_material(mat, base, met, rough, None)
    # apply UV remaps for atlased slots
    for obj, role in objs:
        me = obj.data
        srcmats = list(obj.get("_srcmats", []))
        for si, m in enumerate(me.materials):
            if m is None or m.name not in made or not made[m.name]["remap"]:
                continue
            remap = made[m.name]["remap"]
            d = mesh_np(me)
            sm = np.empty(len(me.polygons), np.int64)
            me.attributes["srcmat"].data.foreach_get("value", sm)
            uv = np.empty(len(me.loops) * 2, np.float64)
            me.uv_layers[0].data.foreach_get("uv", uv)
            uv = uv.reshape(-1, 2)
            for k, sname in enumerate(srcmats):
                fm = (d["mi"] == si) & (sm == k)
                if not fm.any():
                    continue
                info = sources[m.name].get(sname, [None])[0]
                lidx = np.concatenate([np.arange(s, s + t) for s, t in zip(d["ls"][fm], d["lt"][fm])])
                face_of_loop = np.repeat(np.arange(fm.sum()), d["lt"][fm])
                if info is not None and info["image"] is not None and info["image"].name in remap["cells"]:
                    u0, v0, du, dv = remap["cells"][info["image"].name]
                    fu = uv[lidx]
                    # shift each face so its min uv is inside [0,1)
                    fmin = np.full((fm.sum(), 2), np.inf)
                    np.minimum.at(fmin, face_of_loop, fu)
                    fu = fu - np.floor(fmin)[face_of_loop]
                    fu = np.clip(fu, 0, 1)
                    uv[lidx, 0] = u0 + fu[:, 0] * du
                    uv[lidx, 1] = v0 + fu[:, 1] * dv
                elif info is not None and info["name"] in remap["swatches"]:
                    uv[lidx] = remap["swatches"][info["name"]]
            me.uv_layers[0].data.foreach_set("uv", uv.ravel())
    return made


def setup_material(mat, base, metallic, rough, tex=None, alpha=False, emission=None):
    if not mat.node_tree:
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if tex is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = tex
        t.location = (-400, 0)
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if alpha:
            nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
            mat.surface_render_method = "DITHERED"
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1.0)
        b.inputs["Emission Strength"].default_value = 1.0
    mat.diffuse_color = (*base, 1.0)
    mat["_inkdrift"] = 1
    return mat


def ensure_slot_materials():
    for slot in SLOTS:
        mat = bpy.data.materials.get(slot)
        if mat and not mat.get("_inkdrift"):
            base, met, rough = SLOT_LOOK[slot]
            setup_material(mat, base, met, rough, None)


# ----------------------------------------------------------------------------------------------
# 6. geometry ops
def obj_world_co(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(obj.matrix_world)
    return co @ mw[:3, :3].T + mw[:3, 3]


def translate_mesh(obj, v):
    obj.data.transform(Matrix.Translation(Vector(v)))


def set_origin(obj, p):
    """keep geometry in place, move the object origin to world point p (objects are unrotated)."""
    p = Vector(p)
    off = p - obj.matrix_world.translation
    obj.data.transform(Matrix.Translation(-off))
    obj.matrix_world = Matrix.Translation(p)


def bvh_of(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(obj, deps)


def face_slots(obj):
    mi = np.empty(len(obj.data.polygons), np.int64)
    obj.data.polygons.foreach_get("material_index", mi)
    names = [m.name if m else "" for m in obj.data.materials]
    return mi, names


def add_mesh_obj(name, verts, faces, slot, uvs=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    m = bpy.data.materials.get(slot) or bpy.data.materials.new(slot)
    me.materials.append(m)
    uvl = me.uv_layers.new(name="UVMap")
    if uvs is not None:
        arr = np.array([uvs[li] for li in range(len(me.loops))], np.float64) if callable(uvs) is False and \
            isinstance(uvs, dict) else None
        if arr is None:
            lv = np.empty(len(me.loops), np.int64)
            me.loops.foreach_get("vertex_index", lv)
            uvs = np.asarray(uvs, np.float64)
            arr = uvs[lv]
        uvl.data.foreach_set("uv", arr.ravel())
    else:
        box_uv(me)
    me.polygons.foreach_set("use_smooth", np.full(len(me.polygons), smooth))
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def box_uv(me, scale=1.0):
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    n = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get("normal", n)
    n = np.abs(n.reshape(-1, 3))
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    ax = np.repeat(np.argmax(n, axis=1), lt)
    p = co[lv]
    uv = np.where(ax[:, None] == 0, p[:, [1, 2]], np.where(ax[:, None] == 1, p[:, [0, 2]], p[:, [0, 1]])) * scale
    if len(me.uv_layers) == 0:
        me.uv_layers.new(name="UVMap")
    me.uv_layers[0].data.foreach_set("uv", uv.ravel())


def extrude_profile(profile_yz, x0, x1, name, slot, twist=None):
    """Prism: 2D closed profile in (y,z) extruded along X from x0 to x1."""
    n = len(profile_yz)
    verts = [(x0, y, z) for y, z in profile_yz] + [(x1, y, z) for y, z in profile_yz]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return add_mesh_obj(name, verts, faces, slot)


def extrude_profile_x(profile_xz_list, ys, name, slot):
    """Loft of closed (x,z) profiles placed at successive y positions (same vertex count)."""
    n = len(profile_xz_list[0])
    verts, faces = [], []
    for k, (prof, y) in enumerate(zip(profile_xz_list, ys)):
        verts += [(x, y, z) for x, z in prof]
    m = len(ys)
    faces.append(tuple(range(n))[::-1])
    faces.append(tuple(range((m - 1) * n, m * n)))
    for k in range(m - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b = k * n + i, k * n + j
            faces.append((a, b, b + n, a + n))
    return add_mesh_obj(name, verts, faces, slot)


def plate_obj(name, verts_xyz, thickness, slot):
    """closed flat slab from a convex-ish polygon in world coords (list of Vector), thickness along its normal"""
    p = [Vector(v) for v in verts_xyz]
    n = (p[1] - p[0]).cross(p[2] - p[0]).normalized()
    top = [v + n * thickness / 2 for v in p]
    bot = [v - n * thickness / 2 for v in p]
    k = len(p)
    faces = [tuple(range(k)), tuple(range(k, 2 * k))[::-1]]
    for i in range(k):
        j = (i + 1) % k
        faces.append((i, k + i, k + j, j))
    return add_mesh_obj(name, top + bot, faces, slot)


def airfoil(chord, thick=0.12, camber=0.06, n=18):
    """inverted cambered airfoil (y forward=-, z up) for a downforce wing; LE at y=0, TE at y=+chord."""
    pts_u, pts_l = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * thick * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        p = 0.4
        yc = camber / p ** 2 * (2 * p * x - x * x) if x < p else camber / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x)
        yc = -yc  # inverted
        pts_u.append((x * chord, (yc + yt) * chord))
        pts_l.append((x * chord, (yc - yt) * chord))
    prof = pts_u + pts_l[::-1][1:-1]
    return prof


# ----------------------------------------------------------------------------------------------
# 7. kit
def raycast(bvh, origin, direction, maxd=10.0):
    loc, nrm, idx, dist = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), maxd)
    return loc, nrm, idx, dist


def build_kit(body, wheels, cfg, dims):
    kit = cfg["kit"]
    bvh = bvh_of(body)
    co = obj_world_co(body)
    parts = []
    W2 = dims["half_width"]
    y_front, y_rear = dims["y_front"], dims["y_rear"]
    fa, ra = dims["front_axle_y"], dims["rear_axle_y"]
    r = dims["r_front"]

    # --- GT wing
    wcfg = kit.get("wing")
    if wcfg is not None and wcfg is not False and wcfg.get("enabled", True):
        span = wcfg.get("span", min(2 * W2 * 0.9, 1.78))
        chord = wcfg.get("chord", 0.30)
        mount_x = wcfg.get("mount_x", 0.36)
        y_le = -wcfg["z"] if "z" in wcfg else y_rear - wcfg.get("from_rear", 0.12) - chord
        style = wcfg.get("style", "swan")
        # trunk surface under the mounts
        mount_y = y_le + chord * (0.55 if style == "swan" else 0.45)
        zs = []
        for sx in (1, -1):
            hit = raycast(bvh, (sx * mount_x, mount_y, 4.0), (0, 0, -1))
            zs.append(hit[0].z if hit[0] else dims["height"] * 0.75)
        z_trunk = max(zs)
        h = wcfg.get("height", 0.30)
        z_wing = wcfg["y"] if "y" in wcfg else z_trunk + h
        aoa = math.radians(wcfg.get("aoa", 9))
        prof = airfoil(chord, 0.11, 0.07)
        # rotate profile: TE up by aoa about LE, then place
        rp = []
        for (py, pz) in prof:
            yy = py * math.cos(aoa) - pz * math.sin(aoa)
            zz = py * math.sin(aoa) + pz * math.cos(aoa)
            rp.append((y_le + yy, z_wing + zz))
        parts.append(extrude_profile(rp, -span / 2, span / 2, "kit_wing", "M_Carbon"))
        # gurney flap
        te = (y_le + chord * math.cos(aoa), z_wing + chord * math.sin(aoa))
        gp = [(te[0] - 0.006, te[1] - 0.004), (te[0] + 0.004, te[1] - 0.004), (te[0] + 0.004, te[1] + 0.022),
              (te[0] - 0.006, te[1] + 0.022)]
        parts.append(extrude_profile(gp, -span / 2, span / 2, "kit_gurney", "M_Trim"))
        # end plates
        ep_y0, ep_y1 = y_le - 0.05, y_le + chord + 0.06
        ep_z0, ep_z1 = z_wing - 0.11, z_wing + chord * math.sin(aoa) + 0.07
        for sx in (1, -1):
            x = sx * (span / 2 + 0.004)
            prof2 = [(ep_y0, ep_z0 + 0.04), (ep_y0 + 0.05, ep_z0), (ep_y1, ep_z0), (ep_y1, ep_z1),
                     (ep_y0 + 0.08, ep_z1 - 0.02), (ep_y0, ep_z1 - 0.07)]
            parts.append(extrude_profile(prof2, x - 0.004, x + 0.004, "kit_endplate", "M_Carbon"))
        # mounts
        thick = 0.012
        for sx, zt in zip((1, -1), zs):
            x = sx * mount_x
            zb = zt - 0.02  # sink into the deck lid
            if style == "pedestal":
                y0 = y_le + chord * 0.28
                y1 = y_le + chord * 0.62
                # underside height of wing at y (approx straight line LE->TE minus thickness)
                def zu(y):
                    t = (y - y_le) / chord
                    return z_wing + t * chord * math.sin(aoa) - 0.02
                prof3 = [(y0 - 0.03, zb), (y1 + 0.03, zb), (y1, zu(y1)), (y0, zu(y0))]
                parts.append(extrude_profile(prof3, x - thick / 2, x + thick / 2, "kit_mount", "M_Trim"))
            else:
                # swan neck: rises behind the wing, hooks over and grabs the top surface
                yb = y_le + chord * 0.95
                ztop = z_wing + chord * math.sin(aoa) + 0.06
                ya = y_le + chord * 0.40
                za = z_wing + 0.40 * chord * math.sin(aoa) + 0.012
                pts = []
                steps = 14
                for i in range(steps + 1):
                    t = i / steps
                    # quadratic bezier from base (yb, zb) via (yb+0.02, ztop+0.05) to (ya, za+0.01)
                    p0, p1, p2 = (yb, zb), (yb + 0.04, ztop + 0.07), (ya, za)
                    yy = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
                    zz = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
                    pts.append((yy, zz))
                wbase, wtop = 0.10, 0.045
                left, right = [], []
                for i, (yy, zz) in enumerate(pts):
                    j0, j1 = max(0, i - 1), min(len(pts) - 1, i + 1)
                    ty, tz = pts[j1][0] - pts[j0][0], pts[j1][1] - pts[j0][1]
                    ln = math.hypot(ty, tz) or 1
                    ny, nz = -tz / ln, ty / ln
                    wdt = (wbase + (wtop - wbase) * (i / steps)) / 2
                    left.append((yy + ny * wdt, zz + nz * wdt))
                    right.append((yy - ny * wdt, zz - nz * wdt))
                prof3 = left + right[::-1]
                parts.append(extrude_profile(prof3, x - thick / 2, x + thick / 2, "kit_mount", "M_Trim"))
                # foot plate
                fp = [(yb - 0.07, zb - 0.005), (yb + 0.07, zb - 0.005), (yb + 0.07, zb + 0.022), (yb - 0.07, zb + 0.022)]
                parts.append(extrude_profile(fp, x - 0.035, x + 0.035, "kit_foot", "M_Trim"))
        dims["wing"] = dict(span=span, chord=chord, z=z_wing, y_le=y_le, mount_z=zs)

    # --- front splitter
    scfg = kit.get("splitter")
    if scfg is not None and scfg is not False and scfg.get("enabled", True):
        front = co[co[:, 1] < fa - 0.75 * r]
        zlow = np.percentile(front[:, 2], 1.0)
        band = front[front[:, 2] < zlow + scfg.get("band", 0.10)]
        nb = 25
        xs = np.linspace(-W2 * 0.92, W2 * 0.92, nb)
        edge = []
        for x in xs:
            sel = band[np.abs(band[:, 0] - x) < W2 / nb * 1.6]
            if len(sel) < 3:
                edge.append(None)
                continue
            edge.append(sel[:, 1].min())
        valid = [i for i, e in enumerate(edge) if e is not None]
        xs = xs[valid[0]:valid[-1] + 1]
        edge = np.array([e if e is not None else np.nan for e in edge[valid[0]:valid[-1] + 1]])
        edge = np.where(np.isnan(edge), np.nanmax(edge), edge)
        # smooth
        edge = np.convolve(np.pad(edge, 2, mode="edge"), np.ones(5) / 5, mode="valid")
        out = scfg.get("protrude", 0.06)
        depth = scfg.get("depth", 0.32)
        zsp = zlow - 0.003 + scfg.get("dz", 0.0)
        t = 0.014
        front_pts = [(x, e - out) for x, e in zip(xs, edge)]
        back_pts = [(x, e + depth) for x, e in zip(xs, edge)][::-1]
        ring = front_pts + back_pts
        verts = [(x, y, zsp - t / 2) for x, y in ring] + [(x, y, zsp + t / 2) for x, y in ring]
        n = len(ring)
        faces = []
        m = len(front_pts)
        # top/bottom as quads strips between front and back rows
        for i in range(m - 1):
            a, b = i, i + 1
            c, d = n - 1 - (i + 1), n - 1 - i
            faces.append((a, b, c, d))  # bottom
            faces.append((n + d, n + c, n + b, n + a))  # top
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, n + i, n + j, j))
        parts.append(add_mesh_obj("kit_splitter", verts, faces, "M_Carbon"))
        dims["splitter_z"] = zsp
        # end fences (small vertical plates)
        for sx in (1, -1):
            x = sx * (abs(xs[0 if sx < 0 else -1]) - 0.01)
            e = edge[0 if sx < 0 else -1]
            prof = [(e - out, zsp), (e + 0.15, zsp), (e + 0.05, zsp + 0.06), (e - out + 0.02, zsp + 0.05)]
            parts.append(extrude_profile(prof, x - 0.004, x + 0.004, "kit_fence", "M_Carbon"))

    # --- canards (2 per side on the bumper corners)
    ccfg = kit.get("canards")
    if ccfg is not None and ccfg is not False and ccfg.get("enabled", True):
        zl = dims.get("splitter_z", 0.15)
        for k, (dz, ln, wd) in enumerate(ccfg.get("planes", [(0.12, 0.20, 0.075), (0.22, 0.16, 0.06)])):
            z = zl + dz
            ycorner = ccfg.get("y_offset", 0.16)
            for sx in (1, -1):
                # find bumper surface: ray from the side at y near the front corner
                y = y_front + ycorner
                hit = raycast(bvh, (sx * (W2 + 1.0), y, z), (-sx, 0, 0))
                if not hit[0]:
                    continue
                p = hit[0]
                x0 = p.x - sx * 0.012
                ang = math.radians(ccfg.get("angle", 14))
                pts = [Vector((x0, y - ln / 2, z - math.tan(ang) * (-ln / 2))),
                       Vector((x0, y + ln / 2, z - math.tan(ang) * (ln / 2))),
                       Vector((x0 + sx * wd * 0.55, y + ln * 0.25, z - math.tan(ang) * (ln * 0.25))),
                       Vector((x0 + sx * wd, y - ln * 0.45, z + math.tan(ang) * ln * 0.45))]
                parts.append(plate_obj("kit_canard", pts if sx > 0 else pts[::-1], 0.006, "M_Carbon"))

    # --- side skirts
    kcfg = kit.get("skirts")
    if kcfg is not None and kcfg is not False and kcfg.get("enabled", True):
        y0 = fa + dims["r_front"] + kcfg.get("gap", 0.07)
        y1 = ra - dims["r_rear"] - kcfg.get("gap", 0.07)
        ys = np.linspace(y0, y1, 14)
        for sx in (1, -1):
            profs = []
            okys = []
            for y in ys:
                side = co[(np.abs(co[:, 1] - y) < 0.06) & (np.sign(co[:, 0]) == sx) & (np.abs(co[:, 0]) > W2 - 0.3)]
                if len(side) < 3:
                    continue
                zb = side[:, 2].min()
                hit = raycast(bvh, (sx * (W2 + 1.0), y, zb + kcfg.get("attach", 0.06)), (-sx, 0, 0))
                xs_ = hit[0].x if hit[0] else sx * (W2 - 0.03)
                out = kcfg.get("out", 0.035)
                drop = kcfg.get("drop", 0.03)
                xi = xs_ - sx * 0.015
                prof = [(xi, zb + 0.09), (xs_ + sx * 0.004, zb + 0.09), (xs_ + sx * out, zb - drop + 0.012),
                        (xs_ + sx * (out - 0.004), zb - drop), (xi, zb - drop + 0.004)]
                if sx < 0:
                    prof = prof[::-1]
                profs.append(prof)
                okys.append(y)
            if len(profs) >= 2:
                parts.append(extrude_profile_x(profs, okys, "kit_skirt", "M_Carbon"))
    return parts


# ----------------------------------------------------------------------------------------------
# 8. plates & decals
def run_cartex(*args):
    r = subprocess.run([VENV_PY, CARTEX] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("cartex failed: " + r.stderr[-2000:])
    return r.stdout


def find_plate_spots(body, cfg, dims):
    mi, names = face_slots(body)
    me = body.data
    d = mesh_np(me)
    spots = {}
    pc = cfg["plates"]
    if "M_Plate" in names:
        k = names.index("M_Plate")
        fm = mi == k
        for key, sgn in (("front", -1), ("rear", 1)):
            sm = fm & (np.sign(d["ctr"][:, 1]) == sgn)
            if sm.sum() >= 1 and pc.get(key, "auto") == "auto":
                w = d["area"][sm] + 1e-9
                c = np.average(d["ctr"][sm], axis=0, weights=w)
                n = np.average(d["nrm"][sm], axis=0, weights=w)
                n = Vector(n).normalized()
                spots[key] = (Vector(c), n)
        delete_faces(body, fm)
    bvh = bvh_of(body)
    for key, sgn in (("front", -1), ("rear", 1)):
        if key in spots:
            continue
        pos = pc.get(key, "auto")
        if isinstance(pos, list):
            p = c2b(pos)
            hit = raycast(bvh, p + Vector((0, sgn * 1.0, 0)), (0, -sgn, 0))
            spots[key] = (hit[0] if hit[0] else p, hit[1] if hit[0] else Vector((0, sgn, 0)))
        elif pos is not None and pos is not False:
            z = pc.get("front_y" if key == "front" else "rear_y")
            y0 = dims["y_front"] - 1 if key == "front" else dims["y_rear"] + 1
            hit = raycast(bvh, (0, y0, z), (0, -sgn, 0))
            if hit[0]:
                spots[key] = (hit[0], hit[1])
    return spots


def build_plates(body, cfg, dims, car_id, tex_dir):
    pc = cfg["plates"]
    spots = find_plate_spots(body, cfg, dims)
    if not spots:
        return []
    path = os.path.join(tex_dir, f"{car_id}_plate_albedo.png")
    run_cartex("plate", path, pc["style"], pc["top"], pc["kana"], pc["num"])
    img = bpy.data.images.load(path, check_existing=False)
    img.name = os.path.basename(path)
    setup_material(bpy.data.materials.get("M_Plate") or bpy.data.materials.new("M_Plate"), (1, 1, 1), 0.0, 0.4, img)
    parts = []
    bvh = bvh_of(body)
    for key, (c, n) in spots.items():
        sgn = -1 if key == "front" else 1
        n = Vector((0, n.y, n.z))
        if n.length < 0.3 or (n.y * sgn) < 0.3:
            n = Vector((0, sgn, 0))
        n.normalize()
        up = Vector((0, 0, 1))
        up = (up - n * up.dot(n)).normalized()
        right = up.cross(n).normalized()  # viewer's right
        # viewer looks along -n; viewer right = (-n) x up
        right = (-n).cross(up).normalized()
        W, H = 0.33, 0.165
        # push the plate out so all 4 corners clear the bumper surface
        off = 0.0
        for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, 0)):
            q = c + right * du * W / 2 + up * dv * H / 2
            hit = raycast(bvh, q + n * 0.3, -n, 0.6)
            if hit[0]:
                off = max(off, (hit[0] - c).dot(n))
        c2 = c + n * (off + 0.006)
        q = [c2 + right * du * W / 2 + up * dv * H / 2 for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        o = add_mesh_obj("plate_" + key, q, [(0, 1, 2, 3)], "M_Plate", uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
        parts.append(o)
        # backing frame (black) that closes the gap to the bumper
        fw, fh = W + 0.016, H + 0.016
        depth = off + 0.012
        front_q = [c2 - n * 0.002 + right * du * fw / 2 + up * dv * fh / 2 for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        back_q = [v - n * (depth + 0.01) for v in front_q]
        verts = front_q + back_q
        faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        parts.append(add_mesh_obj("plate_frame_" + key, verts, faces, "M_Trim"))
        dims["plate_" + key] = b2c(c2)
    return parts


def build_decals(body, cfg, dims, car_id, tex_dir):
    decals = cfg["decals"]
    banner = cfg.get("banner")
    if not decals and not banner:
        return []
    imgs = sorted({d["img"] for d in decals if d["img"] != "banner"})
    paths = [os.path.join(DECAL_DIR, i + ".png") for i in imgs]
    paths = [p for p in paths if os.path.exists(p)]
    atlas = os.path.join(tex_dir, f"{car_id}_decals.png")
    rj = os.path.join(INSPECT_DIR, f"{car_id}_decals.json")
    os.makedirs(INSPECT_DIR, exist_ok=True)
    run_cartex("atlas", atlas, rj, banner or "-", cfg.get("banner_accent", "#FF2D7A"), *paths)
    rects = json.load(open(rj))
    img = bpy.data.images.load(atlas, check_existing=False)
    img.name = os.path.basename(atlas)
    mat = bpy.data.materials.get("M_Decal") or bpy.data.materials.new("M_Decal")
    setup_material(mat, (1, 1, 1), 0.0, 0.35, img, alpha=True)
    bvh = bvh_of(body)
    mi, names = face_slots(body)
    glass = names.index("M_Glass") if "M_Glass" in names else -1
    parts = []
    W2 = dims["half_width"]
    items = list(decals)
    if banner:
        items.append({"img": "banner", "where": "windshield", "h": cfg.get("banner_h", 0.12)})
    for dc in items:
        name = dc["img"]
        if name not in rects:
            log("  decal missing:", name)
            continue
        u0, v0, u1, v1, aspect = rects[name]
        where = dc.get("where", "side")
        if where == "side":
            sides = {"both": (1, -1), "left": (1,), "right": (-1,)}[dc.get("sides", "both")]
            for sx in sides:
                w = dc["w"]
                h = dc.get("h", w / aspect)
                yc = -dc["z"]
                zc = dc["y"]
                o = project_decal(bvh, mi, glass, name, (u0, v0, u1, v1), w, h,
                                  origin_fn=lambda u, v, sx=sx, yc=yc, zc=zc, w=w, h=h:
                                  (Vector((sx * (W2 + 1.0), yc + sx * (u - 0.5) * w, zc + (v - 0.5) * h)),
                                   Vector((-sx, 0, 0))),
                                  allow_glass=dc.get("glass", False))
                if o:
                    parts.append(o)
        elif where in ("hood", "roof", "trunk", "top"):
            w = dc["w"]
            h = dc.get("h", w / aspect)
            yc, xc = -dc["z"], -dc.get("x", 0.0)
            rot = dc.get("rotate", 0)  # 0: text reads left->right for a viewer in front of the car
            def ofn(u, v, w=w, h=h, yc=yc, xc=xc):
                # viewer at the front looking back: right = +X (car left), up on the hood = toward rear (+Y)
                return Vector((xc + (u - 0.5) * w, yc + (v - 0.5) * h, 4.0)), Vector((0, 0, -1))
            o = project_decal(bvh, mi, glass, name, (u0, v0, u1, v1), w, h, origin_fn=ofn, allow_glass=False)
            if o:
                parts.append(o)
        elif where == "windshield":
            if glass < 0:
                continue
            d = mesh_np(body.data)
            fm = (mi == glass) & (d["nrm"][:, 1] < -0.3) & (d["nrm"][:, 2] > 0.25) & (np.abs(d["ctr"][:, 0]) < 0.35) \
                & (d["ctr"][:, 1] < 0.6)
            if not fm.any():
                log("  no windshield found")
                continue
            ztop = d["ctr"][fm, 2].max()
            top = fm & (d["ctr"][:, 2] > ztop - 0.10)
            c = Vector(np.average(d["ctr"][top], axis=0, weights=d["area"][top] + 1e-9))
            c.x = 0.0
            nrm = Vector(np.average(d["nrm"][fm], axis=0, weights=d["area"][fm] + 1e-9)).normalized()
            up = (Vector((0, 0, 1)) - nrm * nrm.z).normalized()
            right = Vector((1, 0, 0))
            h = dc.get("h", 0.12)
            w = dc.get("w", h * aspect)
            wmax = 2 * W2 * 0.62
            if w > wmax:
                w = wmax
                h = w / aspect
            cc = c - up * (h / 2 + 0.035)
            o = project_decal(bvh, mi, glass, name, (u0, v0, u1, v1), w, h,
                              origin_fn=lambda u, v, cc=cc, w=w, h=h, up=up, nrm=nrm:
                              (cc + right * (u - 0.5) * w + up * (v - 0.5) * h + nrm * 0.5, -nrm),
                              allow_glass=True, offset=0.003)
            if o:
                parts.append(o)
    return parts


def atlas_json_path(atlas_png):
    return os.path.splitext(atlas_png)[0] + ".json"


def project_decal(bvh, mi, glass, name, rect, w, h, origin_fn, allow_glass=False, offset=0.0025, res=0.03):
    u0, v0, u1, v1 = rect
    nu = max(2, int(math.ceil(w / res)))
    nv = max(2, int(math.ceil(h / res)))
    P = {}
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            o, dvec = origin_fn(u, v)
            loc, nrm, idx, dist = bvh.ray_cast(o, dvec.normalized(), 6.0)
            if loc is None:
                continue
            if not allow_glass and idx is not None and mi[idx] == glass:
                continue
            if nrm.dot(-dvec.normalized()) < 0.25:
                continue
            P[(i, j)] = (loc + nrm * offset, dist, (u0 + u * (u1 - u0), v0 + v * (v1 - v0)))
    verts, uvs, faces, index = [], [], [], {}
    for (i, j), (p, dist, uv) in P.items():
        index[(i, j)] = len(verts)
        verts.append(p)
        uvs.append(uv)
    for j in range(nv):
        for i in range(nu):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(k in P for k in q):
                ds = [P[k][1] for k in q]
                if max(ds) - min(ds) > 0.05 + 0.5 * res:
                    continue
                faces.append(tuple(index[k] for k in q))
    if not faces:
        log("  decal", name, "projected nothing")
        return None
    o = add_mesh_obj("decal_" + name, verts, faces, "M_Decal", uvs=uvs, smooth=True)
    bpy.context.view_layer.update()
    return o


# ----------------------------------------------------------------------------------------------
# 9. decimation, normals
def decimate_body(obj, target, cfg):
    total = tri_count(obj.data)
    if total <= target:
        log(f"  body {total} tris <= budget {target}, no decimation")
        return
    weights = dict(M_Paint=1.0, M_PaintAccent=1.0, M_Glass=0.6, M_HeadLight=0.6, M_TailLight=0.6, M_Grille=0.35,
                   M_Chrome=0.5, M_Trim=0.45, M_Carbon=0.8, M_Interior=0.18, M_Underbody=0.10, M_Plate=0.2,
                   M_Decal=1.0)
    weights.update(cfg.get("slot_weights", {}))
    mi, names = face_slots(obj)
    lt = np.empty(len(obj.data.polygons), np.int64)
    obj.data.polygons.foreach_get("loop_total", lt)
    n = np.array([int((lt[mi == k] - 2).sum()) for k in range(len(names))], float)
    w = np.array([weights.get(s, 0.5) for s in names])
    lo, hi = 0.0, 1.0 / max(w.min(), 1e-3)
    for _ in range(50):
        k = (lo + hi) / 2
        t = (n * np.minimum(1, k * w)).sum()
        lo, hi = (k, hi) if t < target else (lo, k)
    ratios = np.minimum(1, lo * w)
    log("  decimation ratios:", {s: round(float(r), 3) for s, r in zip(names, ratios) if n[names.index(s)] > 0})
    # split by material, decimate, rejoin
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    pieces = [o for o in bpy.context.selected_objects]
    for p in pieces:
        pm, _ = face_slots(p)
        if len(pm) == 0:
            continue
        k = int(np.bincount(pm).argmax())
        r = float(ratios[k])
        if r < 0.98:
            mod = p.modifiers.new("dec", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = r
            mod.use_symmetry = True
            mod.symmetry_axis = "X"
            mod.use_collapse_triangulate = True
            activate(p)
            bpy.ops.object.modifier_apply(modifier="dec")
    join([obj] + [p for p in pieces if p != obj], obj.name)
    # collapse rarely lands exactly on the ratio (symmetry/boundaries) -> top up with uniform passes
    for _ in range(4):
        n = tri_count(obj.data)
        if n <= target * 1.03:
            break
        mod = obj.modifiers.new("dec", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = max(0.05, target / n * 0.98)
        mod.use_symmetry = True
        mod.symmetry_axis = "X"
        mod.use_collapse_triangulate = True
        activate(obj)
        bpy.ops.object.modifier_apply(modifier="dec")
    log(f"  body {total} -> {tri_count(obj.data)} tris (target {target})")


def subdivide(obj, levels, crease_angle=35.0):
    """Catmull-Clark for low-poly sources: sharp (>crease_angle) and boundary edges are fully creased so
    silhouettes / panel breaks stay, faceting in between gets smoothed."""
    if levels <= 0:
        return
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    cr = np.zeros(len(bm.edges), np.float32)
    lim = math.radians(crease_angle)
    for i, e in enumerate(bm.edges):
        if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim:
            cr[i] = 1.0
    bm.free()
    a = me.attributes.get("crease_edge") or me.attributes.new("crease_edge", "FLOAT", "EDGE")
    a.data.foreach_set("value", cr)
    mod = obj.modifiers.new("subd", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    mod.use_creases = True
    mod.boundary_smooth = "PRESERVE_CORNERS"
    activate(obj)
    bpy.ops.object.modifier_apply(modifier="subd")
    log(f"  subdivided {obj.name} x{levels} -> {tri_count(obj.data)} tris")


def decimate_to(obj, target):
    total = tri_count(obj.data)
    if total <= target:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = target / total
    mod.use_collapse_triangulate = True
    activate(obj)
    bpy.ops.object.modifier_apply(modifier="dec")


def fix_normals(obj, angle=30):
    activate(obj)
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except RuntimeError:
        pass
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle), keep_sharp_edges=True)


# ----------------------------------------------------------------------------------------------
# 10. lights / exhaust
def find_lights(body, cfg, dims, names, A_src_names):
    mi, slots = face_slots(body)
    d = mesh_np(body.data)
    res = {}
    for key, slot, region in (("Light_Head", "M_HeadLight", "front"), ("Light_Tail", "M_TailLight", "rear")):
        k = slots.index(slot) if slot in slots else -1
        for side, sx in (("L", 1), ("R", -1)):
            name = f"{key}_{side}"
            if name in cfg["lights"]:
                res[name] = c2b(cfg["lights"][name])
                continue
            fm = (mi == k) & (np.sign(d["ctr"][:, 0]) == sx) & (np.abs(d["ctr"][:, 0]) > 0.15)
            if region == "front":
                fm &= d["ctr"][:, 1] < dims["front_axle_y"]
                fm &= d["nrm"][:, 1] < 0.2
            else:
                fm &= d["ctr"][:, 1] > dims["rear_axle_y"]
                fm &= d["nrm"][:, 1] > -0.2
            if fm.sum() > 0:
                c = np.average(d["ctr"][fm], axis=0, weights=d["area"][fm] + 1e-9)
                # put it on the outer surface: front-/rear-most of these faces
                ext = d["ctr"][fm, 1].min() if region == "front" else d["ctr"][fm, 1].max()
                res[name] = Vector((c[0], (c[1] + ext) / 2, c[2]))
            else:
                y = dims["y_front"] + 0.15 if region == "front" else dims["y_rear"] - 0.1
                res[name] = Vector((sx * (dims["half_width"] - 0.25), y, 0.68))
                log("  WARNING no", slot, "faces for", name, "-> guessed")
    return res


def find_exhaust(body, cfg, dims, names):
    if cfg.get("exhaust"):
        e = cfg["exhaust"]
        return {"Exhaust_L": c2b(e[0]), "Exhaust_R": c2b(e[1])}
    A = Analysis(body)
    rx = re.compile(r"exhaust|muffler|tail_?pipe|tip|pipe|auspuff|escape", re.I)
    ext, ctr = A.cext, A.cctr
    rear = (A.cmax[:, 1] > dims["y_rear"] - 0.35) & (ctr[:, 2] < 0.55) & (A.cfaces > 0)
    named = np.array([bool(rx.search(names[s])) if s < len(names) else False for s in A.csrc])
    tube = (np.abs(ext[:, 0] - ext[:, 2]) < 0.35 * np.maximum(ext[:, 0], ext[:, 2])) & \
           (np.maximum(ext[:, 0], ext[:, 2]) > 0.05) & (np.maximum(ext[:, 0], ext[:, 2]) < 0.2) & (ext[:, 1] > 0.03)
    cand = np.where(rear & (named | tube))[0]
    res = {}
    if len(cand):
        for side, sx in (("L", 1), ("R", -1)):
            cs = cand[np.sign(ctr[cand, 0]) == sx]
            if len(cs) == 0:
                cs = cand
            # rear-most tip, outermost
            best = cs[np.argmax(A.cmax[cs, 1] + 0.3 * np.abs(ctr[cs, 0]))]
            res[f"Exhaust_{side}"] = Vector((ctr[best, 0], A.cmax[best, 1], ctr[best, 2]))
    for side, sx in (("L", 1), ("R", -1)):
        if f"Exhaust_{side}" not in res:
            res[f"Exhaust_{side}"] = Vector((sx * 0.45, dims["y_rear"] - 0.05, 0.28))
            log("  WARNING exhaust guessed", side)
    return res


# ----------------------------------------------------------------------------------------------
# 11. preview
def setup_preview_scene(color):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.film_transparent = False
    try:
        sc.eevee.taa_render_samples = 32
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    world = bpy.data.worlds.new("studio")
    sc.world = world
    if not world.node_tree:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.42, 0.44, 0.48, 1)
    bg.inputs["Strength"].default_value = 0.9
    # ground
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "_preview_ground"
    gm = bpy.data.materials.new("_ground")
    setup_material(gm, (0.5, 0.5, 0.52), 0.0, 0.7)
    g.data.materials.append(gm)
    for nm, loc, energy, size in (("key", (4, -5, 6), 1500, 5), ("fill", (-6, -2, 4), 600, 6), ("rim", (0, 7, 5), 900, 5)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new("_light_" + nm, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.6)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    pm = bpy.data.materials.get("M_Paint")
    if pm and pm.node_tree:
        b = next(n for n in pm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (*color, 1)
    pa = bpy.data.materials.get("M_PaintAccent")
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("_cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render_views(cam, car_id, dims, out_dir, prefix="", views=None):
    os.makedirs(out_dir, exist_ok=True)
    L, H = dims["length"], dims["height"]
    tgt = Vector((0, 0, H * 0.45))
    D = L * 1.45
    allv = {
        "front34": (Vector((D * 0.62, -D * 0.78, H * 1.05)), tgt, 40),
        "rear34": (Vector((-D * 0.62, D * 0.78, H * 1.05)), tgt, 40),
        "side": (Vector((D * 1.25, 0, H * 0.55)), Vector((0, 0, H * 0.45)), 38),
        "front": (Vector((0, -D * 0.95, H * 0.75)), Vector((0, 0, H * 0.45)), 45),
        "rear": (Vector((0, D * 0.95, H * 0.9)), Vector((0, 0, H * 0.5)), 45),
        "top": (Vector((0, 0.001, D * 1.6)), Vector((0, 0, 0)), 35),
        "wheel": (Vector((dims["half_width"] + 1.3, dims["front_axle_y"] - 0.4, 0.45)),
                  Vector((dims["half_width"], dims["front_axle_y"], 0.32)), 50),
        "low": (Vector((D * 0.55, -D * 0.55, 0.25)), Vector((0, 0, 0.35)), 35),
    }
    out = []
    for v in (views or ["front34", "rear34", "side"]):
        pos, look, lens = allv[v]
        cam.location = pos
        cam.rotation_euler = (look - pos).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        p = os.path.join(out_dir, f"{prefix}{car_id}_{v}.png")
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        out.append(p)
    return out


# ----------------------------------------------------------------------------------------------
# 12. export
def patch_fbx_texture_paths():
    try:
        from io_scene_fbx import export_fbx_bin as efb
        if getattr(efb, "_inkdrift_patched", False):
            return
        orig = efb._gen_vid_path

        def _gen_vid_path(img, scene_data):
            fa, fr = orig(img, scene_data)
            return fr, fr
        efb._gen_vid_path = _gen_vid_path
        efb._inkdrift_patched = True
    except Exception as ex:
        log("could not patch FBX texture paths:", ex)


def export_fbx(root, path):
    patch_fbx_texture_paths()
    deselect_all()
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=True,
        use_tspace=False, add_leaf_bones=False, path_mode="RELATIVE", embed_textures=False,
        use_custom_props=False, colors_type="NONE", bake_anim=False)


# ----------------------------------------------------------------------------------------------
def measure(objs_by_name, wheels_final):
    body = objs_by_name["Body"]
    allco = np.concatenate([obj_world_co(o) for n, o in objs_by_name.items() if o.type == "MESH"])
    bco = obj_world_co(body)
    d = {}
    d["length"] = float(allco[:, 1].max() - allco[:, 1].min())
    d["width"] = float(allco[:, 0].max() - allco[:, 0].min())
    d["height"] = float(allco[:, 2].max() - allco[:, 2].min())
    d["ground_clearance"] = float(bco[:, 2].min())
    return d


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    flags = [a for a in argv if a.startswith("--")]
    pos = [a for a in argv if not a.startswith("--")]
    cfg_path = None
    if "--config" in argv:
        cfg_path = argv[argv.index("--config") + 1]
        pos.remove(cfg_path)
    inp, car_id, out_dir = pos[0], pos[1], pos[2]
    inspect = "--inspect" in flags
    cfg = load_config(car_id, cfg_path)
    traffic = cfg["traffic"]
    tex_dir = os.path.join(out_dir, "Textures")

    import_model(inp)
    src_images = [i for i in bpy.data.images if i.size[0] > 0]
    obj, names = flatten(cfg)
    orient(obj, cfg, names)
    remove_ground_planes(obj)

    # delete by material name
    if cfg["delete_materials"]:
        mats = [m.name if m else "" for m in obj.data.materials]
        rx = [re.compile(r, re.I) for r in cfg["delete_materials"]]
        bad = [i for i, m in enumerate(mats) if any(r.search(m) for r in rx)]
        if bad:
            d = mesh_np(obj.data)
            delete_faces(obj, np.isin(d["mi"], bad))
            log("deleted faces of materials", [mats[i] for i in bad])

    A = Analysis(obj)
    mats = [m.name if m else "" for m in obj.data.materials]
    wheels = find_wheels(A, cfg, names)
    yf = (wheels["FL"]["c"].y + wheels["FR"]["c"].y) / 2
    yr = (wheels["RL"]["c"].y + wheels["RR"]["c"].y) / 2
    wb = abs(yr - yf)
    span = A.bmax - A.bmin
    if cfg["scale"]:
        s = cfg["scale"]
    elif cfg["wheelbase"]:
        s = cfg["wheelbase"] / wb
    elif cfg["length"]:
        s = cfg["length"] / span[1]
    else:
        s = 1.0
    cx = np.mean([w["c"].x for w in wheels.values()])
    cy = (yf + yr) / 2
    zg = np.mean([w["c"].z - w["r"] for w in wheels.values()])
    M = Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation((-cx, -cy, -zg))
    obj.data.transform(M)
    obj.data.update()
    log(f"scale {s:.4f} (model wheelbase {wb:.3f}) length now {span[1] * s:.3f} m")

    # delete boxes / badge parts (car coords)
    A = Analysis(obj)
    kill = np.zeros(A.K, bool)
    for bx in cfg["delete_boxes"]:
        c = np.array(c2b(bx[:3]))
        hs = np.array([abs(bx[3]), abs(bx[5]), abs(bx[4])]) / 2
        kill |= np.all(A.cmin >= c - hs, axis=1) & np.all(A.cmax <= c + hs, axis=1)
    for pn in cfg["delete_parts_near"]:
        c = np.array(c2b(pn[:3]))
        kill |= (np.linalg.norm(A.cctr - c, axis=1) < pn[3]) & (A.cext.max(1) < pn[4])
    if kill.any():
        log("deleting", int(kill.sum()), "loose parts (boxes / badges)")
        delete_faces(obj, kill[A.flab])
        A = Analysis(obj)

    # wheels in final coords
    wheels = find_wheels(A, cfg, names)
    target, comp_t = classify_wheel_parts(A, wheels, cfg, mats, names)

    if unsteer_wheels(obj, A, wheels, comp_t):
        A = Analysis(obj)
        wheels = find_wheels(A, cfg, names)
        target, comp_t = classify_wheel_parts(A, wheels, cfg, mats, names)

    # badge suspects report (small parts near the centre line at the nose/tail)
    L = A.bmax[1] - A.bmin[1]
    sus = np.where((A.cfaces > 0) & (A.cext.max(1) < 0.30) & (np.abs(A.cctr[:, 0]) < 0.30) &
                   ((A.cctr[:, 1] < A.bmin[1] + 0.45) | (A.cctr[:, 1] > A.bmax[1] - 0.45)) &
                   (A.cctr[:, 2] > 0.2) & (comp_t == 0))[0]
    log("badge suspects (car coords x,y,z | size | material | object):")
    for ci in sus[np.argsort(A.cctr[sus, 1])]:
        log("   ", b2c(Vector(A.cctr[ci])), np.round(A.cext[ci], 3).tolist(), mats[A.cmat[ci]], "|",
            names[A.csrc[ci]] if A.csrc[ci] < len(names) else "")

    if inspect:
        do_inspect(obj, A, target, wheels, cfg, names, mats, car_id, src_images)
        return

    # split into objects
    wheel_objs, cal_objs = {}, {}
    for wi, key in enumerate(("FL", "FR", "RL", "RR")):
        d = mesh_np(obj.data)
        A2t = target  # target aligned with current faces
        wheel_objs[key] = split_faces(obj, A2t == 1 + wi, "Wheel_" + key)
        target = target[A2t != 1 + wi]
        cal_objs[key] = split_faces(obj, target == 5 + wi, "Caliper_" + key)
        target = target[target != 5 + wi]
    body = obj
    body.name = body.data.name = "Body"
    for k, o in wheel_objs.items():
        log(f"  Wheel_{k}: {tri_count(o.data)} tris; caliper {tri_count(cal_objs[k].data) if cal_objs[k] else 0}")

    # materials
    report = {}
    roles = [(body, "body")] + [(o, "wheel") for o in wheel_objs.values()] + \
            [(o, "caliper") for o in cal_objs.values() if o is not None]
    sources = assign_slots(roles, cfg, names, report)
    log("material mapping:")
    for (role, mname, oname), slot in sorted(report.items(), key=lambda kv: (kv[0][0], kv[1])):
        log(f"   {role:7s} {slot:14s} <- {mname} | {oname}")
    build_materials(roles, sources, cfg, car_id, tex_dir)

    if cfg.get("subdivide"):
        subdivide(body, int(cfg["subdivide"]), cfg.get("crease_angle", 35.0))
    if cfg.get("subdivide_wheels"):
        for o in wheel_objs.values():
            subdivide(o, int(cfg["subdivide_wheels"]), cfg.get("crease_angle", 35.0))

    # wheel hubs, measurements (radius = largest radial distance of the wheel geometry from the hub)
    wfinal = {}
    for key, o in wheel_objs.items():
        w = wheels[key]
        c = Vector(w["c"])
        co = obj_world_co(o)
        r = float(np.sqrt((co[:, 1] - c.y) ** 2 + (co[:, 2] - c.z) ** 2).max())
        wfinal[key] = dict(c=c, r=r, w=abs(w["x_out"] - w["x_in"]), xo=w["x_out"])
        set_origin(o, c)
        if cal_objs[key]:
            set_origin(cal_objs[key], c)

    # re-ground: tyre bottoms at z=0 exactly
    zb = np.mean([w["c"].z - w["r"] for w in wfinal.values()])
    for o in [body] + list(wheel_objs.values()) + [c for c in cal_objs.values() if c]:
        o.location.z -= zb
    for w in wfinal.values():
        w["c"].z -= zb
    bpy.context.view_layer.update()
    for o in [body] + list(wheel_objs.values()) + [c for c in cal_objs.values() if c]:
        if o is not body:
            continue
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)

    # ride height & flush fitment
    bco = obj_world_co(body)
    gaps = []
    for key, w in wfinal.items():
        c, r = w["c"], w["r"]
        dy = bco[:, 1] - c.y
        sel = (np.abs(bco[:, 0] - c.x) < w["w"] / 2 - 0.01) & (np.abs(dy) < 0.9 * r) & (bco[:, 2] > c.z + 0.3 * r)
        if sel.any():
            surf = c.z + np.sqrt(np.maximum(r * r - dy[sel] ** 2, 0))
            clr = bco[sel, 2] - surf
            clr = clr[clr > -0.02]  # ignore parts that already sit inside the tyre (suspension etc.)
            if len(clr):
                gaps.append(float(clr.min()))
    gap = min(gaps) if gaps else 0.05
    lower = 0.0 if traffic else max(0.0, min(cfg["lower"], gap - 0.012))
    if lower > 0:
        translate_mesh(body, (0, 0, -lower))
    log(f"arch gap {gap * 1000:.0f} mm -> lowered {lower * 1000:.0f} mm")
    bco = obj_world_co(body)
    pushes = {}
    if cfg["flush"] and not traffic:
        for axle in ("F", "R"):
            ps = []
            for side, sx in (("L", 1), ("R", -1)):
                w = wfinal[axle + side]
                c, r = w["c"], w["r"]
                sel = (np.abs(bco[:, 1] - c.y) < 0.6 * r) & (bco[:, 2] > c.z + 0.55 * r) & (bco[:, 2] < c.z + 1.35 * r) \
                    & (np.sign(bco[:, 0]) == sx)
                fender = np.abs(bco[sel, 0]).max() if sel.any() else abs(w["xo"])
                ps.append(fender - abs(w["xo"]) - 0.004)
            p = float(np.clip(min(ps), 0, cfg["max_push"])) + cfg["track_push_extra"]
            pushes[axle] = p
            for side, sx in (("L", 1), ("R", -1)):
                k = axle + side
                wheel_objs[k].location.x += sx * p
                if cal_objs[k]:
                    cal_objs[k].location.x += sx * p
                wfinal[k]["c"].x += sx * p
        log(f"flush push front {pushes['F'] * 1000:.0f} mm, rear {pushes['R'] * 1000:.0f} mm")
    bpy.context.view_layer.update()

    # decimate
    for o in wheel_objs.values():
        decimate_to(o, cfg["wheel_tris"])
    for o in cal_objs.values():
        if o:
            decimate_to(o, 800 if not traffic else 200)
    wheel_tris = sum(tri_count(o.data) for o in wheel_objs.values()) + \
        sum(tri_count(o.data) for o in cal_objs.values() if o)
    body_budget = cfg["tri_budget"] - wheel_tris - (6000 if not traffic else 300)
    decimate_body(body, body_budget, cfg)

    # dims so far
    bco = obj_world_co(body)
    dims = dict(half_width=float(np.abs(bco[:, 0]).max()), y_front=float(bco[:, 1].min()),
                y_rear=float(bco[:, 1].max()), height=float(bco[:, 2].max()),
                front_axle_y=float((wfinal["FL"]["c"].y + wfinal["FR"]["c"].y) / 2),
                rear_axle_y=float((wfinal["RL"]["c"].y + wfinal["RR"]["c"].y) / 2),
                r_front=wfinal["FL"]["r"], r_rear=wfinal["RL"]["r"],
                length=float(bco[:, 1].max() - bco[:, 1].min()))

    # lights/exhaust from the stock body (before kit/decals)
    lights = find_lights(body, cfg, dims, names, names)
    exh = find_exhaust(body, cfg, dims, names)

    extra = []
    if not traffic:
        extra += build_kit(body, wfinal, cfg, dims)
    extra += build_plates(body, cfg, dims, car_id, tex_dir)
    if not traffic or cfg["decals"]:
        extra += build_decals(body, cfg, dims, car_id, tex_dir)
    for o in extra:
        fix_normals(o, 30)
    body = join([body] + extra, "Body")
    ensure_slot_materials()
    # merge duplicate material slots (same material) in body
    merge_slots(body)
    for o in [body] + list(wheel_objs.values()) + [c for c in cal_objs.values() if c]:
        fix_normals(o, 30)

    # hierarchy
    root = bpy.data.objects.new(f"Car_{car_id}", None)
    bpy.context.scene.collection.objects.link(root)
    for o in [body] + list(wheel_objs.values()) + [c for c in cal_objs.values() if c]:
        o.parent = root
    empties = {}
    for name, p in list(lights.items()) + list(exh.items()):
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = "SINGLE_ARROW" if "Exhaust" in name else "PLAIN_AXES"
        e.empty_display_size = 0.15
        bpy.context.scene.collection.objects.link(e)
        e.location = p
        if "Tail" in name or "Exhaust" in name:
            e.rotation_euler = (0, 0, math.pi)  # local -Y (= Unity +Z) points to the car's rear
        e.parent = root
        empties[name] = e
    for o in root.children:
        o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()

    os.makedirs(out_dir, exist_ok=True)
    fbx_path = os.path.join(out_dir, f"{car_id}.fbx")
    export_fbx(root, fbx_path)
    log("exported", fbx_path)

    # dims json (car coords)
    objs = {o.name: o for o in root.children}
    m = measure(objs, wfinal)
    tris = sum(tri_count(o.data) for o in root.children if o.type == "MESH")
    fl, fr, rl, rr = (wheel_objs[k].matrix_world.translation for k in ("FL", "FR", "RL", "RR"))
    out = {
        "id": car_id,
        "units": "meters",
        "frame": "Unity: x right, y up, z forward; origin on the ground (tyre contact) midway between the axles",
        "wheelbase": round(abs(-fl.y + rl.y), 4),
        "front_axle_z": round(-(fl.y + fr.y) / 2, 4),
        "rear_axle_z": round(-(rl.y + rr.y) / 2, 4),
        "front_track": round(fl.x - fr.x, 4),
        "rear_track": round(rl.x - rr.x, 4),
        "wheel_radius": round(max(wfinal["FL"]["r"], wfinal["RL"]["r"]), 4),
        "wheel_radius_front": round(wfinal["FL"]["r"], 4),
        "wheel_radius_rear": round(wfinal["RL"]["r"], 4),
        "wheel_width": round(max(wfinal["FL"]["w"], wfinal["RL"]["w"]), 4),
        "wheel_width_front": round(wfinal["FL"]["w"], 4),
        "wheel_width_rear": round(wfinal["RL"]["w"], 4),
        "hub_height": round((fl.z + rl.z) / 2, 4),
        "length": round(m["length"], 4),
        "width": round(m["width"], 4),
        "height": round(m["height"], 4),
        "ground_clearance": round(m["ground_clearance"], 4),
        "tri_count": tris,
        "com_height_suggested": round(m["ground_clearance"] + 0.30 * (dims["height"] - m["ground_clearance"]) +
                                      (0.04 if traffic else 0.0), 3),
        "wheels": {k: b2c(wheel_objs[k].matrix_world.translation) for k in ("FL", "FR", "RL", "RR")},
        "empties": {n: b2c(e.matrix_world.translation) for n, e in empties.items()},
        "ride_height_drop_mm": round(lower * 1000),
        "wheel_push_mm": {k: round(v * 1000) for k, v in pushes.items()},
        "materials": sorted({m.name for o in root.children if o.type == "MESH" for m in o.data.materials if m}),
    }
    if "wing" in dims:
        out["wing"] = {"span": round(dims["wing"]["span"], 3), "chord": round(dims["wing"]["chord"], 3),
                       "height": round(dims["wing"]["z"], 3)}
    jp = os.path.join(out_dir, f"{car_id}_dims.json")
    with open(jp, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log("dims", json.dumps({k: v for k, v in out.items() if not isinstance(v, (dict, list))}))

    if "--no-preview" not in flags:
        dims["length"] = m["length"]
        dims["height"] = m["height"]
        cam = setup_preview_scene(cfg["preview_color"])
        views = ["front34", "rear34", "side", "front", "rear", "top", "wheel", "low"]
        ps = render_views(cam, car_id, dims, PREVIEW_DIR, views=views)
        run_cartex("sheet", os.path.join(PREVIEW_DIR, f"{car_id}_sheet.jpg"), *ps)
        log("previews ->", PREVIEW_DIR)


def merge_slots(obj):
    me = obj.data
    mats = list(me.materials)
    uniq = []
    for m in mats:
        if m not in uniq:
            uniq.append(m)
    # order by canonical slot order
    uniq.sort(key=lambda m: SLOTS.index(m.name) if m and m.name in SLOTS else 99)
    remap = np.array([uniq.index(m) for m in mats], np.int64)
    mi = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("material_index", mi)
    me.materials.clear()
    for m in uniq:
        me.materials.append(m)
    if len(mi):
        me.polygons.foreach_set("material_index", remap[mi])
    # drop unused
    used = set(np.unique(remap[mi]).tolist()) if len(mi) else set()
    activate(obj)
    bpy.ops.object.material_slot_remove_unused()


def do_inspect(obj, A, target, wheels, cfg, names, mats, car_id, src_images):
    os.makedirs(INSPECT_DIR, exist_ok=True)
    log("objects:", len(names))
    d = mesh_np(obj.data)
    # per material stats
    rows = []
    for k, m in enumerate(mats):
        fm = d["mi"] == k
        if not fm.any():
            continue
        info = mat_info(obj.data.materials[k])
        srcs = sorted({names[s] for s in np.unique(d["src"][fm])})
        c = np.average(d["ctr"][fm], axis=0, weights=d["area"][fm] + 1e-9)
        rows.append((m, int((d["lt"][fm] - 2).sum()), info["image"].name if info["image"] else "-",
                     [round(x, 2) for x in info["color"]], round(info["metallic"], 2), round(info["roughness"], 2),
                     b2c(Vector(c)), srcs[:6]))
    log("materials (name | tris | image | color | metal | rough | centroid car coords | objects):")
    for r in sorted(rows, key=lambda r: -r[1]):
        log("   ", r[0], "|", r[1], "|", r[2], "|", r[3], r[4], r[5], "|", r[6], "|", r[7])
    for k, w in wheels.items():
        log(f"wheel {k}: centre {b2c(w['c'])} r={w['r']:.3f} width={abs(w['x_out'] - w['x_in']):.3f}")
    cnt = np.bincount(target, minlength=9)
    log("face targets body/wheels/calipers:", cnt.tolist())
    # textures
    tdir = os.path.join(INSPECT_DIR, f"{car_id}_tex")
    os.makedirs(tdir, exist_ok=True)
    tex_paths = []
    for img in src_images:
        try:
            w, h = img.size
            s = min(1.0, 512 / max(w, h))
            arr = img_pixels(img, max(1, int(w * s)), max(1, int(h * s)))
            p = os.path.join(tdir, re.sub(r"[^\w.-]", "_", img.name) + ".png")
            save_png(arr, p)
            tex_paths.append(p)
            log(f"   image {img.name} {w}x{h}")
        except Exception as ex:
            log("   image fail", img.name, ex)
    if tex_paths:
        run_cartex("texsheet", os.path.join(INSPECT_DIR, f"{car_id}_textures.jpg"), *tex_paths)
    bpy.context.view_layer.update()
    co = obj_world_co(obj)
    dims = dict(length=float(co[:, 1].max() - co[:, 1].min()), height=float(co[:, 2].max()),
                half_width=float(np.abs(co[:, 0]).max()),
                front_axle_y=float(wheels["FL"]["c"].y))
    cam = setup_preview_scene(cfg["preview_color"])
    ps = render_views(cam, car_id, dims, INSPECT_DIR, prefix="raw_", views=["front34", "rear34", "side", "front", "rear", "top"])
    run_cartex("sheet", os.path.join(INSPECT_DIR, f"raw_{car_id}_sheet.jpg"), *ps)
    log("inspect renders ->", INSPECT_DIR)


if __name__ == "__main__":
    main()
