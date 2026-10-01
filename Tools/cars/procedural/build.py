"""INK DRIFT: TOKYO -- procedural car builder (original geometry, no third-party assets).

    blender -b -P Tools/cars/procedural/build.py -- <car_id> [--h <mm>] [--no-preview] [--quick]

<car_id>: hachi | kaiju | zenkai | raijin | tsubame | traffic_kei | traffic_taxi | traffic_van | traffic_truck

Body = signed distance field built from parametric profiles (specs/<id>.py), meshed with surface nets,
projected onto the iso-surface, mirrored, material-classified, decimated with material borders protected.
Wheels / kit / plates / decals / export / dims follow the contract of Tools/cars/prep_car.py (whose helpers are
reused: kit, plates, decals, FBX export, slot materials, preview scene).
"""
import importlib
import json
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True  # keep Tools/cars free of __pycache__
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CARS_DIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(CARS_DIR, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, CARS_DIR)

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import blendutil as BU  # noqa: E402
import prep_car as PC  # noqa: E402
import wheels as WH  # noqa: E402
from body import CarBody, CustomBody  # noqa: E402
from mesher import mesh_sdf  # noqa: E402

OUT_CARS = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Cars")
PC.INSPECT_DIR = os.path.join(HERE, "cache")  # keep prep_car's decal-atlas scratch json inside procedural/
PREVIEWS = os.path.join(HERE, "previews")
T0 = time.time()

# base colours (linear) the Unity importer reads as DiffuseColor; paint white (tinted at runtime)
LOOK = {
    "M_Paint": ((1.0, 1.0, 1.0), 0.3, 0.25),
    "M_PaintAccent": ((0.03, 0.03, 0.035), 0.3, 0.3),
    "M_Glass": ((0.015, 0.018, 0.025), 0.0, 0.05),
    "M_Chrome": ((0.85, 0.86, 0.88), 1.0, 0.12),
    "M_Trim": ((0.03, 0.03, 0.033), 0.0, 0.55),
    "M_Carbon": ((0.025, 0.025, 0.028), 0.3, 0.3),
    "M_Grille": ((0.012, 0.012, 0.014), 0.0, 0.6),
    "M_HeadLight": ((0.80, 0.84, 0.90), 0.5, 0.1),
    "M_TailLight": ((0.60, 0.02, 0.025), 0.0, 0.15),
    "M_Interior": ((0.05, 0.05, 0.055), 0.0, 0.7),
    "M_Rim": ((0.14, 0.14, 0.155), 0.9, 0.3),
    "M_Tire": ((0.025, 0.025, 0.027), 0.0, 0.85),
    "M_Brake": ((0.32, 0.32, 0.33), 0.8, 0.45),
    "M_Decal": ((1.0, 1.0, 1.0), 0.0, 0.35),
    "M_Plate": ((1.0, 1.0, 1.0), 0.0, 0.4),
    "M_Underbody": ((0.02, 0.02, 0.022), 0.0, 0.85),
}


def log(*a):
    print(f"[build {time.time() - T0:7.1f}s]", *a, flush=True)


def setup_materials():
    for slot, (c, met, rough) in LOOK.items():
        m = BU.get_mat(slot)
        em = None
        if slot == "M_HeadLight":
            em = (0.5, 0.5, 0.5)
        PC.setup_material(m, c, met, rough, None, emission=em)


# ----------------------------------------------------------------------------------------------
VENV_PY = os.path.join(REPO, "Tools", ".venv", "bin", "python")
CUT_FIRST = "--decimate-first" not in sys.argv
VG_FACTOR = None


def sdf_mesh(car_id, h, raw=False):
    """mesh the body SDF in a subprocess (parallel; fork deadlocks inside Blender)"""
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
    out = os.path.join(HERE, "cache", f"{car_id}_{int(round(h * 10000))}{'_raw' if raw else ''}.npz")
    cmd = [VENV_PY, os.path.join(HERE, "sdfmesh.py"), car_id, str(h * 1000), out] + (["--raw"] if raw else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError("sdfmesh failed: " + r.stderr[-3000:])
    with np.load(out) as d:
        res = (d["V"], d["Q"]) if raw else (d["V"], d["idx"], d["off"], d["mats"])
    if "--keep-cache" not in sys.argv:
        os.remove(out)
    return res


def body_mesh(spec, h):
    """dense, exactly cut + classified body (shape previews)"""
    V, idx, off, mats = sdf_mesh(spec["id"], h)
    o = BU.mesh_from_csr("Body", BU.m2b(V), idx, off, mats=mats)
    BU.mirror_x(o)
    return o


def mesh_arrays(o):
    me = o.data
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    n = len(me.polygons)
    ls = np.empty(n, np.int64)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    off = np.concatenate([ls, [len(lv)]])
    order = np.argsort(ls)
    assert np.all(order == np.arange(n))
    return V.reshape(-1, 3), lv, off


def border_group(o, name="border"):
    """vertex group: 1 on vertices touching a material border"""
    me = o.data
    n = len(me.polygons)
    mi = np.empty(n, np.int64)
    me.polygons.foreach_get("material_index", mi)
    ne = len(me.edges)
    ev = np.empty(ne * 2, np.int64)
    me.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    # edge -> faces via loops
    le = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("edge_index", le)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    lf = np.repeat(np.arange(n), lt)
    fmin = np.full(ne, 1 << 30)
    fmax = np.full(ne, -1)
    np.minimum.at(fmin, le, mi[lf])
    np.maximum.at(fmax, le, mi[lf])
    border = fmin != fmax
    w = np.zeros(len(me.vertices), bool)
    w[ev[border].ravel()] = True
    vg = o.vertex_groups.new(name=name)
    idx = np.nonzero(w)[0].tolist()
    if idx:
        vg.add(idx, 1.0, "REPLACE")
    return int(w.sum())


def snap_outliers(o, body, tol=0.005, iters=4):
    """decimation can leave a few vertices off the surface (spikes): pull those back onto the SDF iso-surface"""
    me = o.data
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    P = BU.b2m(V)
    d = body(P)
    bad = np.abs(d) > tol
    if not bad.any():
        return 0
    Q = P[bad]
    eps = 0.001
    E = np.eye(3) * eps
    for _ in range(iters):
        f = body(Q)
        g = np.stack([(body(Q + E[a]) - body(Q - E[a])) / (2 * eps) for a in range(3)], 1)
        gg = np.maximum((g * g).sum(1), 1e-8)
        Q = Q - (f / gg)[:, None] * g
    P[bad] = Q
    me.vertices.foreach_set("co", BU.m2b(P).astype(np.float32).ravel())
    me.update()
    return int(bad.sum())


def build_body_cutfirst(spec, h, target):
    """dense exact cut + classify (subprocess) -> mirror -> decimate with material borders protected"""
    body = (CustomBody if "sdf" in spec["body"] else CarBody)(spec["body"])
    o = body_mesh(spec, h)
    n0 = BU.tri_count(o.data)
    lim = spec.get("dissolve_deg", 0.25 if spec.get("traffic") else 0.0)
    if lim > 0:  # planar pre-pass: boxy traffic bodies collapse badly otherwise
        BU.activate(o)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(lim), delimit={"MATERIAL"})
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
        bpy.ops.object.mode_set(mode="OBJECT")
        log(f"  planar dissolve {n0} -> {BU.tri_count(o.data)} tris")
    nb = border_group(o)
    n1 = BU.tri_count(o.data)
    if n1 > target:
        mod = o.modifiers.new("dec", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = target / n1
        mod.use_symmetry = True
        mod.symmetry_axis = "X"
        mod.use_collapse_triangulate = True
        mod.vertex_group = "border"
        mod.invert_vertex_group = True
        mod.vertex_group_factor = spec.get("vg_factor", 1.0)
        BU.activate(o)
        bpy.ops.object.modifier_apply(modifier="dec")
    o.vertex_groups.clear()
    nfix = snap_outliers(o, body)
    PC.box_uv(o.data, 1.0)
    log(f"body (cut-first): {n0} -> {BU.tri_count(o.data)} tris, {nb} border verts, {nfix} outlier verts re-projected")
    return body, o


def build_body(spec, h, target):
    """raw SDF mesh -> mirror -> decimate (geometry only) -> exact material cuts -> classify -> triangulate"""
    if spec.get("cut_first", CUT_FIRST):
        return build_body_cutfirst(spec, h, target)
    from cutmesh import centers, cut
    body = (CustomBody if "sdf" in spec["body"] else CarBody)(spec["body"])
    V, Q = sdf_mesh(spec["id"], h, raw=True)
    o = BU.mesh_from_np("Body", BU.m2b(V), Q, smooth=True)
    BU.mirror_x(o)
    n0 = BU.tri_count(o.data)
    n1 = BU.decimate(o, int(target * spec.get("pre_cut_ratio", 0.9)), symmetry=True)
    Vb, idx, off = mesh_arrays(o)
    Vm = BU.b2m(Vb)
    t0 = time.time()
    for name, fn, slot in body.regions():
        P = Vm.copy()
        P[:, 1] = np.abs(P[:, 1])
        Vm, idx, off = cut(Vm, idx, off, fn(P))
    mats = body.classify(centers(Vm, idx, off))
    bpy.data.objects.remove(o, do_unlink=True)
    o = BU.mesh_from_csr("Body", BU.m2b(Vm), idx, off, mats=np.array(mats, dtype="U16"))
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bm.to_mesh(o.data)
    bm.free()
    PC.box_uv(o.data, 1.0)
    log(f"body: {n0} -> {n1} tris decimated, cut+classified in {time.time() - t0:.1f}s -> {BU.tri_count(o.data)} tris")
    return body, o


def sdf_loop_normals(o, body, nfaces, eps=0.0012):
    """custom normals from the SDF gradient for the first `nfaces` polygons of o (the SDF body); each face corner is
    sampled 30% towards its face centre so creases stay crisp. Other loops keep their current normals."""
    me = o.data
    nl = len(me.loops)
    cn = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    n = len(me.polygons)
    ls = np.empty(n, np.int64)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    C = np.empty(n * 3)
    me.polygons.foreach_get("center", C)
    C = C.reshape(-1, 3)
    lf = np.repeat(np.arange(n), lt)
    sel = lf < nfaces
    Pb = V[lv[sel]] * 0.7 + C[lf[sel]] * 0.3
    Pm = BU.b2m(Pb)
    g = np.zeros_like(Pm)
    E = np.eye(3) * eps
    for a in range(3):
        g[:, a] = body(Pm + E[a]) - body(Pm - E[a])
    gb = np.stack([g[:, 1], -g[:, 0], g[:, 2]], 1)
    ln = np.linalg.norm(gb, axis=1)
    ok = ln > 1e-9
    gb[ok] /= ln[ok, None]
    # keep the mesh normal where the gradient is degenerate or disagrees strongly with the face (thin parts)
    cur = cn[sel]
    bad = (~ok) | ((gb * cur).sum(1) < 0.2)
    gb[bad] = cur[bad]
    cn[sel] = gb
    me.normals_split_custom_set(cn.tolist())
    return int(bad.sum())


def make_wheels(spec, body_obj):
    wh = spec["wheels"]
    wd = spec["wheel_design"]
    objs, cals, info = {}, {}, {}
    for key in ("FL", "FR", "RL", "RR"):
        a = "f" if key[0] == "F" else "r"
        side = 1 if key[1] == "L" else -1
        s_ax = spec["body"]["wb"] / 2 * (1 if a == "f" else -1)
        R, W = wh["r_" + a], wh["w_" + a]
        cfg = dict(spec.get("wheel_design_rear", wd) if a == "r" else wd)
        cfg.update(R=R, Wt=W)
        wparts, cparts = WH.build_wheel(cfg)
        V, F, S = wparts.merged()
        if side < 0:
            V = V * np.array([-1, 1, 1])
            F = [f[::-1] for f in F]
        o = BU.mesh_from_np("Wheel_" + key, V, F)
        PC.box_uv(o.data, 2.0)
        slots = np.array(S, dtype=object)
        BU.assign_slots(o, slots)
        center = Vector((side * wh["track_" + a] / 2, -s_ax, R))
        o.location = center
        objs[key] = o
        cV, cF, cS = cparts.merged()
        if len(cV):
            # caliper sits at the trailing upper side: rotate so it is behind the axle (towards +Y = rear)
            if side < 0:
                cV = cV * np.array([-1, 1, 1])
                cF = [f[::-1] for f in cF]
            c = BU.mesh_from_np("Caliper_" + key, cV, cF)
            PC.box_uv(c.data, 2.0)
            BU.assign_slots(c, np.array(cS, dtype=object))
            c.location = center
            cals[key] = c
        info[key] = dict(c=center.copy(), r=R, w=W, xo=side * (wh["track_" + a] / 2 + W / 2))
    return objs, cals, info


def lathe_obj(name, profile, seg, slot, mat_world):
    V, F = WH.lathe(profile, seg)
    V = np.asarray(V)
    o = BU.mesh_from_np(name, V, F, slot)
    o.data.transform(mat_world)
    return o


def exhaust_tips(spec, body=None):
    """chrome tips: list of dict(c=(s,x,z) model of the open end (s None -> raycast, + out), r, len, oval, single)"""
    objs = []
    bvh = PC.bvh_of(body) if body is not None else None
    for t in spec.get("exhaust_tips", []):
        s, x, z = t["c"]
        if s is None:  # bumper surface just above the pipe opening (not the pocket bottom)
            hit = PC.raycast(bvh, (x, 6.0, z + t["r"] * float(t.get("oval", 1.0) and 1.0) + 0.05), (0, -1, 0), 10.0)
            s = -(hit[0].y if hit[0] else 2.1) - t.get("out", 0.02)
            t["c"] = (s, x, z)
        r, ln = t["r"], t.get("len", 0.12)
        ov = t.get("oval", 1.0)
        for sx in (1, -1):
            if t.get("single") and sx < 0:
                continue
            xx = sx * x if not t.get("single") else x
            # tube: inner wall -> rolled lip -> outer wall (lathe about local X, open end at x=0)
            prof = [(-ln * 0.7, 0.84 * r), (0.0, 0.86 * r), (0.003, 0.93 * r), (0.0, r), (-ln, r)]
            V, F = WH.lathe(prof, 28)
            V = np.asarray(V)
            V[:, 1] *= ov
            M = Matrix.Translation(Vector((xx, -s, z))) @ Matrix.Rotation(math.radians(90), 4, "Z")
            o = BU.mesh_from_np("tip", V, F, t.get("slot", "M_Chrome"))
            o.data.transform(M)
            objs.append(o)
            V2, F2 = WH.disc_cap(-ln * 0.7, r * 0.85, 20)
            V2 = np.asarray(V2)
            V2[:, 1] *= ov
            o2 = BU.mesh_from_np("tip_in", V2, F2, "M_Underbody")
            o2.data.transform(M)
            objs.append(o2)
    return objs


def box_mesh(name, lo, hi, slot):
    """axis aligned box in blender coords"""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return BU.mesh_from_np(name, np.array(V), F, slot, smooth=False)


def slats(spec, body):
    """grille fins: spec['slats'] = [dict(view='front'|'rear', x=half_span, zs=[...], thick, depth, gap, slot, xs=None)]
    each fin is placed `gap` in front of the recess bottom found by raycasting at the fin's centre line."""
    out = []
    bvh = PC.bvh_of(body)
    for sl in spec.get("slats", []):
        sgn = -1 if sl.get("view", "front") == "front" else 1   # blender y direction of the outside
        for z in sl["zs"]:
            hx = sl["x"](z) if callable(sl["x"]) else sl["x"]
            if hx <= 0:
                continue
            hit = PC.raycast(bvh, (0.0, sgn * 6.0, z), (0, -sgn, 0), 12.0)
            if not hit[0]:
                continue
            yb = hit[0].y
            y0 = yb + sgn * sl.get("gap", 0.004)
            y1 = y0 + sgn * sl.get("depth", 0.035)
            th = sl.get("thick", 0.012)
            hole = sl.get("hole")  # (half width, z0, z1): leave room for the number plate
            if hole and hole[1] < z < hole[2]:
                for sx in (1, -1):
                    xa, xb = sorted((sx * hole[0], sx * hx))
                    out.append(box_mesh("slat", (xa, min(y0, y1), z - th / 2), (xb, max(y0, y1), z + th / 2),
                                        sl.get("slot", "M_Grille")))
            else:
                out.append(box_mesh("slat", (-hx, min(y0, y1), z - th / 2), (hx, max(y0, y1), z + th / 2),
                                    sl.get("slot", "M_Grille")))
        for xv in sl.get("xs", []):
            z0, z1 = sl["zs"][0], sl["zs"][-1]
            for sx in ((1, -1) if xv > 0 else (1,)):
                hit = PC.raycast(bvh, (sx * xv, sgn * 6.0, (z0 + z1) / 2), (0, -sgn, 0), 12.0)
                if not hit[0]:
                    continue
                y0 = hit[0].y + sgn * sl.get("gap", 0.004)
                y1 = y0 + sgn * sl.get("depth", 0.035)
                th = sl.get("thick", 0.012)
                out.append(box_mesh("slat_v", (sx * xv - th / 2, min(y0, y1), z0), (sx * xv + th / 2, max(y0, y1), z1),
                                    sl.get("slot", "M_Grille")))
    return out


def roof_sign(spec, body, tex_dir):
    """generic lit roof sign ('andon'): trapezoid prism, text faces UV-mapped to a generated banner (M_Decal)"""
    rs = spec.get("roof_sign")
    if not rs:
        return []
    import json as _json
    path = os.path.join(tex_dir, f"{spec['id']}_sign.png")
    rj = os.path.join(HERE, "cache", f"{spec['id']}_sign.json")
    PC.run_cartex("atlas", path, rj, rs.get("text", "TAXI"), rs.get("accent", "#FFE600"))
    u0, v0, u1, v1, aspect = _json.load(open(rj))["banner"]
    img = bpy.data.images.load(path, check_existing=False)
    mat = BU.get_mat("M_Decal")
    PC.setup_material(mat, (1, 1, 1), 0.0, 0.35, img, alpha=True)
    bvh = PC.bvh_of(body)
    s0 = rs["s"]
    hit = PC.raycast(bvh, (0.0, -s0, 5.0), (0, 0, -1), 10.0)
    zb = hit[0].z if hit[0] else 1.7
    w, d, hgt = rs.get("size", (0.42, 0.14, 0.13))
    y0, y1 = -s0 - d / 2, -s0 + d / 2
    top_in = 0.035
    V = [(-w / 2, y0, zb - 0.01), (w / 2, y0, zb - 0.01), (w / 2, y1, zb - 0.01), (-w / 2, y1, zb - 0.01),
         (-w / 2 + top_in, y0 + 0.02, zb + hgt), (w / 2 - top_in, y0 + 0.02, zb + hgt),
         (w / 2 - top_in, y1 - 0.02, zb + hgt), (-w / 2 + top_in, y1 - 0.02, zb + hgt)]
    out = []
    uc = (u0 + u1) / 2
    hu = (v1 - v0) * ((w - top_in) / max(hgt, 1e-3)) / 2
    u0, u1 = uc - hu, uc + hu
    # front & back faces with the text
    for name, idx, flip in (("sign_f", (0, 1, 5, 4), False), ("sign_b", (2, 3, 7, 6), False)):
        q = [V[i] for i in idx]
        o = BU.mesh_from_np(name, np.array(q), [(0, 1, 2, 3)], "M_Decal", smooth=False)
        uvl = o.data.uv_layers.new(name="UVMap")
        uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for li, l in enumerate(o.data.loops):
            uvl.data[li].uv = uv[li]
        out.append(o)
    rest = [(0, 3, 2, 1), (4, 5, 6, 7), (1, 2, 6, 5), (3, 0, 4, 7)]
    out.append(BU.mesh_from_np("sign_body", np.array(V), rest, "M_Paint", smooth=False))
    return out


def extra_meshes(spec):
    """spec['meshes']: callables returning list of (name, V_model, F, slot)"""
    out = []
    for fn in spec.get("meshes", []):
        for name, V, F, slot in fn():
            o = BU.mesh_from_np(name, BU.m2b(np.asarray(V, float)), F, slot)
            out.append(o)
    return out


# ----------------------------------------------------------------------------------------------
def kit_cfg(spec, json_cfg):
    k = {"wing": {}, "splitter": {}, "canards": {}, "skirts": {}}
    k.update(json_cfg.get("kit", {}))
    for key, v in spec.get("kit", {}).items():
        if v is False or v is None:
            k[key] = False
        else:
            k[key] = dict(k.get(key) or {}, **v)
    return k


def preview_toon(root, car_id, dims, color):
    """EEVEE with constant-banded shading + Freestyle ink lines (approximation of the in-game look)."""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = 1.6
    vl = sc.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(118)
    ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("ink")
    ls.select_by_visibility = True
    ls.select_silhouette = True
    ls.select_border = True
    ls.select_crease = True
    ls.select_edge_mark = False
    ls.select_material_boundary = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("ink")
    ls.linestyle.color = (0.04, 0.04, 0.07)
    ls.linestyle.thickness = 1.8
    # toon materials: diffuse -> shader to rgb -> constant ramp -> emission
    saved = {}
    for m in bpy.data.materials:
        if not m.node_tree or m.name.startswith("_"):
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if not bsdf or not out:
            continue
        saved[m.name] = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
        col = bsdf.inputs["Base Color"]
        dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
        if col.links:
            nt.links.new(col.links[0].from_socket, dif.inputs["Color"])
        else:
            dif.inputs["Color"].default_value = col.default_value
        s2r = nt.nodes.new("ShaderNodeShaderToRGB")
        nt.links.new(dif.outputs[0], s2r.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        e = ramp.color_ramp.elements
        e[0].position = 0.0
        e[0].color = (0.42, 0.42, 0.5, 1)
        e[1].position = 0.08
        e[1].color = (0.75, 0.75, 0.8, 1)
        e3 = e.new(0.35)
        e3.color = (1.0, 1.0, 1.0, 1)
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(s2r.outputs[0], bw.inputs[0])
        nt.links.new(bw.outputs[0], ramp.inputs[0])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        if col.links:
            nt.links.new(col.links[0].from_socket, mix.inputs["A"])
        else:
            mix.inputs["A"].default_value = col.default_value
        nt.links.new(ramp.outputs[0], mix.inputs["B"])
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(mix.outputs["Result"], em.inputs["Color"])
        if bsdf.inputs["Alpha"].links:
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            mx = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(bsdf.inputs["Alpha"].links[0].from_socket, mx.inputs[0])
            nt.links.new(tr.outputs[0], mx.inputs[1])
            nt.links.new(em.outputs[0], mx.inputs[2])
            nt.links.new(mx.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], out.inputs["Surface"])
    return saved


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    car_id = argv[0]
    quick = "--quick" in argv
    h = None
    if "--h" in argv:
        h = float(argv[argv.index("--h") + 1]) / 1000
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_materials()
    mod = importlib.import_module("specs." + car_id)
    spec = mod.spec()
    traffic = spec.get("traffic", False)
    json_cfg = PC.load_config(car_id)
    for k in ("plates", "decals", "banner", "banner_accent", "preview_color"):
        if k in spec:
            if isinstance(spec[k], dict) and isinstance(json_cfg.get(k), dict):
                json_cfg[k].update(spec[k])
            else:
                json_cfg[k] = spec[k]
    json_cfg["kit"] = kit_cfg(spec, json_cfg)
    h = h or spec.get("h", 0.010 if traffic else 0.005)
    if quick:
        h = max(h, 0.008)
    target = spec.get("body_tris", 14000 if traffic else 92000)
    if traffic:
        out_dir = os.path.join(OUT_CARS, "Traffic")
    else:
        out_dir = os.path.join(OUT_CARS, car_id)
    tex_dir = os.path.join(out_dir, "Textures")
    os.makedirs(tex_dir, exist_ok=True)

    body_sdf, body = build_body(spec, h, target)
    wheel_objs, cal_objs, winfo = make_wheels(spec, body)
    log("wheels:", {k: BU.tri_count(o.data) for k, o in wheel_objs.items()})

    bco = PC.obj_world_co(body)
    hw = spec.get("half_width") or float(np.percentile(np.abs(bco[:, 0]), 99.7))
    dims = dict(half_width=hw, y_front=float(bco[:, 1].min()),
                y_rear=float(bco[:, 1].max()), height=float(bco[:, 2].max()),
                front_axle_y=float(-spec["body"]["wb"] / 2), rear_axle_y=float(spec["body"]["wb"] / 2),
                r_front=spec["wheels"]["r_f"], r_rear=spec["wheels"]["r_r"],
                length=float(bco[:, 1].max() - bco[:, 1].min()))

    extra = []
    extra += exhaust_tips(spec, body)
    for k, t in enumerate(spec.get("exhaust_tips", [])):
        s, x, z = t["c"]
        for nm, sx in (("Exhaust_L", 1), ("Exhaust_R", -1)):
            if nm in spec["empties"] and not t.get("keep_empty"):
                spec["empties"][nm] = (s - 0.02, sx * x if not t.get("single") else x, z)
        break
    extra += extra_meshes(spec)
    extra += slats(spec, body)
    extra += roof_sign(spec, body, tex_dir)
    if not traffic:
        extra += PC.build_kit(body, winfo, json_cfg, dims)
    extra += PC.build_plates(body, json_cfg, dims, car_id if not traffic else car_id, tex_dir)
    if json_cfg.get("decals") or (json_cfg.get("banner") and not traffic):
        extra += PC.build_decals(body, json_cfg, dims, car_id, tex_dir)
    for o in extra:
        PC.fix_normals(o, 30)
    n_body_faces = len(body.data.polygons)
    body = BU.join([body] + extra, "Body")
    PC.ensure_slot_materials()
    PC.merge_slots(body)
    for o in [body] + list(wheel_objs.values()) + list(cal_objs.values()):
        BU.smooth_by_angle(o, 30)
    nbad = sdf_loop_normals(body, body_sdf, n_body_faces)
    log(f"sdf normals set ({nbad} corners kept mesh normals)")

    # hierarchy
    root = bpy.data.objects.new(f"Car_{car_id}", None)
    bpy.context.scene.collection.objects.link(root)
    for o in [body] + list(wheel_objs.values()) + list(cal_objs.values()):
        o.parent = root
    empties = {}
    for name, p in spec["empties"].items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = "SINGLE_ARROW" if "Exhaust" in name else "PLAIN_AXES"
        e.empty_display_size = 0.15
        bpy.context.scene.collection.objects.link(e)
        e.location = Vector((p[1], -p[0], p[2]))
        if "Tail" in name or "Exhaust" in name:
            e.rotation_euler = (0, 0, math.pi)
        e.parent = root
        empties[name] = e
    for o in root.children:
        o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()

    fbx_path = os.path.join(out_dir, f"{car_id}.fbx")
    PC.export_fbx(root, fbx_path)
    log("exported", fbx_path)

    # dims
    allco = np.concatenate([PC.obj_world_co(o) for o in root.children if o.type == "MESH"])
    bco = PC.obj_world_co(body)
    tris = sum(BU.tri_count(o.data) for o in root.children if o.type == "MESH")
    fl, fr, rl, rr = (wheel_objs[k].matrix_world.translation for k in ("FL", "FR", "RL", "RR"))
    height = float(allco[:, 2].max() - allco[:, 2].min())
    gc = float(bco[:, 2].min())
    com = round(gc + (0.30 if not traffic else 0.34) * (float(bco[:, 2].max()) - gc), 3)
    out = {
        "id": car_id,
        "units": "meters",
        "frame": "Unity: x right, y up, z forward; origin on the ground (tyre contact) midway between the axles",
        "source": "original procedural model (Tools/cars/procedural), no third-party assets",
        "wheelbase": round(abs(-fl.y + rl.y), 4),
        "front_axle_z": round(-(fl.y + fr.y) / 2, 4),
        "rear_axle_z": round(-(rl.y + rr.y) / 2, 4),
        "front_track": round(fl.x - fr.x, 4),
        "rear_track": round(rl.x - rr.x, 4),
        "wheel_radius": round(max(winfo["FL"]["r"], winfo["RL"]["r"]), 4),
        "wheel_radius_front": round(winfo["FL"]["r"], 4),
        "wheel_radius_rear": round(winfo["RL"]["r"], 4),
        "wheel_width": round(max(winfo["FL"]["w"], winfo["RL"]["w"]), 4),
        "wheel_width_front": round(winfo["FL"]["w"], 4),
        "wheel_width_rear": round(winfo["RL"]["w"], 4),
        "hub_height": round((fl.z + rl.z) / 2, 4),
        "length": round(float(allco[:, 1].max() - allco[:, 1].min()), 4),
        "width": round(float(allco[:, 0].max() - allco[:, 0].min()), 4),
        "width_body": round(2 * float(np.abs(bco[:, 0]).max()), 4),
        "height": round(height, 4),
        "ground_clearance": round(gc, 4),
        "tris": tris,
        "tri_count": tris,
        "com_height": com,
        "wheels": {k: PC.b2c(wheel_objs[k].matrix_world.translation) for k in ("FL", "FR", "RL", "RR")},
        "empties": {n: PC.b2c(e.matrix_world.translation) for n, e in empties.items()},
        "materials": sorted({m.name for o in root.children if o.type == "MESH" for m in o.data.materials if m}),
    }
    if "wing" in dims:
        out["wing"] = {"span": round(dims["wing"]["span"], 3), "chord": round(dims["wing"]["chord"], 3),
                       "wing_z": round(dims["wing"]["z"], 3)}
    with open(os.path.join(out_dir, f"{car_id}_dims.json"), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log("dims", json.dumps({k: v for k, v in out.items() if not isinstance(v, (dict, list))}))

    if "--no-preview" not in argv:
        dims["length"] = out["length"]
        dims["height"] = float(allco[:, 2].max())
        cam = PC.setup_preview_scene(json_cfg["preview_color"])
        views = ["front34", "rear34", "side"] if quick else ["front34", "rear34", "side", "front", "rear", "low"]
        ps = PC.render_views(cam, car_id, dims, PREVIEWS, views=views)
        preview_toon(root, car_id, dims, json_cfg["preview_color"])
        ps += PC.render_views(cam, car_id, dims, PREVIEWS, prefix="toon_", views=["front34", "rear34"])
        PC.run_cartex("sheet", os.path.join(PREVIEWS, f"{car_id}_sheet.jpg"), *ps)
        log("previews ->", PREVIEWS)
    log("done", car_id, "tris", tris)


if __name__ == "__main__":
    main()
