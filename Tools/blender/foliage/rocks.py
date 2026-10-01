"""Rocks for INK DRIFT foliage: 4 mossy boulders (shared 2048 atlas) + 2 gorge cliff chunks.

Pipeline per rock:
  1. shape = radial function over icosphere directions: base ellipsoid / superellipsoid, soft-min'd against
     random cutting planes (flat facets), + strata / vertical joints (cliffs) + fbm + worley cracks.
  2. high poly (ico subdiv 7-8) carries per-vertex cavity / moss / height attributes -> procedural
     emission shader (stone, lichen, moss caps, dirt) + bump.
  3. low poly = same shape at ico subdiv 5-6, decimated (collapse) to budget, smart-UV'd.
  4. Cycles bake selected->active: EMIT -> albedo, NORMAL (tangent, OpenGL +Y) -> normal map.
  5. low poly: smooth vertex normals stored as custom normals, vertex colour R=AO (ray traced, ground
     counts as occluder), G=0 (no wind), B=random per rock.
The four boulders are baked together (one per atlas quadrant) the first time any of them is built in a
Blender session; the low-poly data is cached at module level so the other three reuse it.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import foliage_lib as fl

TEX = fl.TEX_DIR

# ============================================================================= vectorized noise
GRAD3 = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]], np.float64)


class Noise:
    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        p = rng.permutation(256)
        self.perm = np.concatenate([p, p])
        self.off = rng.uniform(0, 200, 3)
        self.seed = seed

    def perlin(self, P):
        P = np.asarray(P, np.float64) + self.off
        Pi = np.floor(P).astype(np.int64)
        f = P - Pi
        Pi &= 255
        u = f ** 3 * (f * (f * 6 - 15) + 10)
        X, Y, Zc = Pi[:, 0], Pi[:, 1], Pi[:, 2]
        perm = self.perm
        x, y, z = f[:, 0], f[:, 1], f[:, 2]

        def g(ix, iy, iz, fx, fy, fz):
            h = perm[perm[perm[ix] + iy] + iz] % 12
            G = GRAD3[h]
            return G[:, 0] * fx + G[:, 1] * fy + G[:, 2] * fz
        n000 = g(X, Y, Zc, x, y, z)
        n100 = g(X + 1, Y, Zc, x - 1, y, z)
        n010 = g(X, Y + 1, Zc, x, y - 1, z)
        n110 = g(X + 1, Y + 1, Zc, x - 1, y - 1, z)
        n001 = g(X, Y, Zc + 1, x, y, z - 1)
        n101 = g(X + 1, Y, Zc + 1, x - 1, y, z - 1)
        n011 = g(X, Y + 1, Zc + 1, x, y - 1, z - 1)
        n111 = g(X + 1, Y + 1, Zc + 1, x - 1, y - 1, z - 1)
        ux, uy, uz = u[:, 0], u[:, 1], u[:, 2]
        nx00 = n000 + ux * (n100 - n000)
        nx10 = n010 + ux * (n110 - n010)
        nx01 = n001 + ux * (n101 - n001)
        nx11 = n011 + ux * (n111 - n011)
        nxy0 = nx00 + uy * (nx10 - nx00)
        nxy1 = nx01 + uy * (nx11 - nx01)
        return nxy0 + uz * (nxy1 - nxy0)

    def fbm(self, P, octaves=5, lac=2.0, gain=0.5):
        s = np.zeros(len(P))
        a, tot, q = 1.0, 0.0, np.asarray(P, np.float64)
        for i in range(octaves):
            s += a * self.perlin(q * (lac ** i) + i * 17.3)
            tot += a
            a *= gain
        return s / tot

    def ridged(self, P, octaves=4):
        s = np.zeros(len(P))
        a, tot = 1.0, 0.0
        for i in range(octaves):
            s += a * (1 - np.abs(self.perlin(np.asarray(P) * (2 ** i) + i * 7.7)))
            tot += a
            a *= 0.5
        return s / tot


def _hash3(C, seed):
    c = C.astype(np.int64)
    h = (c[:, 0] * 73856093) ^ (c[:, 1] * 19349663) ^ (c[:, 2] * 83492791) ^ (seed * 2654435761)
    h = h & 0xFFFFFFFF
    out = []
    for k in range(4):
        h = (h * 1103515245 + 12345 + k * 977) & 0x7FFFFFFF
        out.append((h % 100003) / 100003.0)
    return np.stack(out, 1)


def worley(P, seed, jitter=0.85):
    """F1, F2 and cell random value for each point (unit cell size)."""
    P = np.asarray(P, np.float64)
    Pi = np.floor(P)
    f1 = np.full(len(P), 9.0)
    f2 = np.full(len(P), 9.0)
    cid = np.zeros(len(P))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                C = Pi + np.array([dx, dy, dz], np.float64)
                r = _hash3(C, seed)
                feat = C + 0.5 + (r[:, :3] - 0.5) * jitter
                d = np.linalg.norm(P - feat, axis=1)
                closer = d < f1
                f2 = np.where(closer, f1, np.minimum(f2, d))
                cid = np.where(closer, r[:, 3], cid)
                f1 = np.where(closer, d, f1)
    return f1, f2, cid


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ============================================================================= mesh helpers
def ico_dirs(subdiv):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    bm.verts.ensure_lookup_table()
    U = np.array([v.co[:] for v in bm.verts], np.float64)
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    F = np.array([[v.index for v in f.verts] for f in bm.faces], np.int64)
    bm.free()
    return U, F


def mesh_from(name, V, F):
    me = bpy.data.meshes.new(name)
    n = len(V)
    me.vertices.add(n)
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    nf = len(F)
    me.loops.add(nf * 3)
    me.loops.foreach_set("vertex_index", F.astype(np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", (np.arange(nf) * 3).astype(np.int32))
    me.update(calc_edges=True)
    me.validate()
    me.polygons.foreach_set("use_smooth", np.ones(nf, bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def vertex_normals(me):
    arr = np.zeros(len(me.vertices) * 3)
    me.vertex_normals.foreach_get("vector", arr)
    return arr.reshape(-1, 3)


def edges_of(me):
    e = np.zeros(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def smooth_field(E, n, x, iters):
    """Laplacian smoothing of a per-vertex field x (n,) or (n,k) over edges E."""
    a = np.concatenate([E[:, 0], E[:, 1]])
    b = np.concatenate([E[:, 1], E[:, 0]])
    deg = np.bincount(a, minlength=n).astype(np.float64)
    x = np.asarray(x, np.float64)
    two = x.ndim == 1
    if two:
        x = x[:, None]
    for _ in range(iters):
        s = np.stack([np.bincount(a, weights=x[b, k], minlength=n) for k in range(x.shape[1])], 1)
        x = 0.5 * x + 0.5 * s / np.maximum(deg, 1)[:, None]
    return x[:, 0] if two else x


# ============================================================================= shapes
def softmin(vals, k):
    m = np.min(vals, axis=0)
    return m - np.log(np.sum(np.exp(-k * (vals - m)), axis=0)) / k


def cut_planes(U, r_base, planes, k):
    """planes: list of (normal, offset). r(u) = softmin(r_base, d/dot(u,n))."""
    vals = [r_base]
    for n, d in planes:
        dn = U @ n
        t = np.where(dn > 1e-3, d / np.maximum(dn, 1e-3), 1e9)
        vals.append(np.minimum(t, 1e3))
    return softmin(np.array(vals), k)


def boulder_shape(U, prm, detail=True):
    nz = Noise(prm["seed"])
    a, b, c = prm["radii"]
    size = max(a, b, c)
    r_e = 1.0 / np.sqrt((U[:, 0] / a) ** 2 + (U[:, 1] / b) ** 2 + (U[:, 2] / c) ** 2)
    r_e = r_e * (1 + 0.14 * nz.fbm(U * 1.1 + 2.0, 3))                     # lumpy, asymmetric base
    r = cut_planes(U, r_e, prm["planes"], prm.get("soft", 18.0) / size)   # broad facets, rounded edges
    for m, w, dep in prm.get("notches", ()):                                # concave chips / notches
        r *= 1 - dep * np.exp(-(1 - U @ m) / w)
    P = U * r[:, None]
    disp = size * (0.022 * nz.fbm(P / size * 1.5, 3) + 0.005 * nz.fbm(P / size * 5 + 3.1, 2))
    if detail:
        disp += size * 0.0025 * nz.fbm(P / size * 16 + 9.7, 3)
        disp -= size * 0.016 * nz.ridged(P / size * 2.2 + 4.4, 3) ** 6       # weathered crevices
        f1, f2, _ = worley(P / (size * 0.75) + 11.3, prm["seed"])
        crack_mask = smoothstep(-0.05, 0.25, nz.fbm(P / size * 1.8 + 7.0, 2))
        disp -= size * 0.02 * smoothstep(0.07, 0.0, f2 - f1) * crack_mask
    P = U * (r + disp)[:, None]
    P[:, 2] += prm["zc"]
    P[:, 2] = np.maximum(P[:, 2], prm["zfloor"])
    return P


def cliff_shape(U, prm, detail=True):
    nz = Noise(prm["seed"])
    a, b, c = prm["radii"]
    p = prm.get("p", 4.5)
    r_s = (np.abs(U[:, 0] / a) ** p + np.abs(U[:, 1] / b) ** p + np.abs(U[:, 2] / c) ** p) ** (-1.0 / p)
    r_s = r_s * (1 + 0.06 * nz.fbm(U * 1.3 + 1.0, 3))
    size = max(a, b, c)
    r = cut_planes(U, r_s, prm["planes"], prm.get("soft", 40.0) / size)
    P = U * r[:, None]
    disp = size * 0.02 * nz.fbm(P / size * 1.1, 3)
    horiz = np.sqrt(U[:, 0] ** 2 + U[:, 1] ** 2)
    hw = smoothstep(0.25, 0.75, horiz)      # strata / columns only on the steep sides
    # strata: layers of random thickness, gently dipping, each receding toward its top (ledges)
    zeta = P[:, 2] + prm["zc"] + prm["dip"] * P[:, 0] + 0.35 * nz.fbm(P * 0.1 + 4.0, 3)
    bnd = prm["layers"]

    def strata_at(zz):
        k = np.clip(np.searchsorted(bnd, zz) - 1, 0, len(bnd) - 2)
        frac = (zz - bnd[k]) / (bnd[k + 1] - bnd[k])
        lean = -prm["layer_lean"] * smoothstep(0.1, 1.0, frac)
        chip = -0.12 * smoothstep(0.06, 0.0, frac)
        return prm["layer_off"][k] + lean + chip
    if detail:  # narrow filter: steps span a few high-poly triangles (no aliasing teeth)
        strata = np.mean([strata_at(zeta + d) for d in np.linspace(-0.07, 0.07, 7)], axis=0) * hw
    else:  # low-poly cage: box-filtered steps -> clean slopes the decimator can follow
        strata = np.mean([strata_at(zeta + d) for d in np.linspace(-0.3, 0.3, 9)], axis=0) * hw
    # vertical joints -> blocky columns with recessed cracks
    jp = np.stack([P[:, 0] / prm["joint"], P[:, 1] / prm["joint"], P[:, 2] / (prm["joint"] * 5.0)], 1)
    f1, f2, cid = worley(jp + 2.2, prm["seed"] + 1)
    edge = f2 - f1
    cols = ((cid - 0.5) * 2 * prm["col_amp"] * smoothstep(0.02, 0.3, edge)
            - 0.18 * smoothstep(0.1, 0.0, edge)) * hw
    disp += strata + cols
    if detail:
        disp += 0.035 * nz.fbm(P * 1.2 + 9.7, 4)
        disp -= 0.06 * nz.ridged(P * 0.45 + 1.3, 3) ** 5
    P = U * (r + disp)[:, None]
    P[:, 2] += prm["zc"]
    P[:, 2] = np.maximum(P[:, 2], prm["zfloor"])
    return P


def rand_planes(rng, n, r_fn, frac=(0.72, 0.92), zmin=-0.35, horiz=False, extra=()):
    planes = list(extra)
    while len(planes) < n + len(extra):
        v = rng.normal(size=3)
        if horiz:
            v[2] *= 0.25
        v /= np.linalg.norm(v)
        if v[2] < zmin:
            continue
        planes.append((v, r_fn(v) * rng.uniform(*frac)))
    return planes


# ============================================================================= attributes / materials
def high_attributes(ob, kind, size):
    """Per-vertex 'rk' colour attr on the high poly: R=cavity(0 deep..0.5 flat..1 ridge), G=moss base, B=height."""
    me = ob.data
    n = len(me.vertices)
    V = np.zeros(n * 3); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
    N = vertex_normals(me)
    E = edges_of(me)
    s1 = smooth_field(E, n, V, 6)
    s2 = smooth_field(E, n, V, 40)
    c1 = np.sum((V - s1) * N, 1) / (size * 0.004)
    c2 = np.sum((V - s2) * N, 1) / (size * 0.02)
    cav = np.clip(0.5 + 0.25 * np.tanh(c1) + 0.25 * np.tanh(c2), 0, 1)
    Ns = fl.unit(smooth_field(E, n, N, 12 if kind == "boulder" else 4))
    zrel = (V[:, 2] - V[:, 2].min()) / max(np.ptp(V[:, 2]), 1e-6)
    if kind == "boulder":
        moss = smoothstep(0.25, 0.85, Ns[:, 2]) * (0.55 + 0.45 * smoothstep(0.2, 0.8, zrel))
        moss += 0.18 * smoothstep(0.5, 0.2, cav) * smoothstep(0.0, 0.3, Ns[:, 2])
    else:
        moss = smoothstep(0.5, 0.8, Ns[:, 2]) * 0.95 + 0.15 * smoothstep(0.4, 0.15, cav) * smoothstep(0.35, 0.6, Ns[:, 2])
        moss += 0.35 * smoothstep(0.85, 1.0, zrel) * smoothstep(0.0, 0.5, Ns[:, 2])
    hgt = np.clip(V[:, 2] / max(V[:, 2].max(), 1e-6), 0, 1)
    ca = me.color_attributes.new("rk", "FLOAT_COLOR", "POINT")
    col = np.stack([cav, np.clip(moss, 0, 1), hgt, np.ones(n)], 1)
    ca.data.foreach_set("color", col.astype(np.float32).ravel())


def _ramp(nt, stops, inp):
    r = nt.nodes.new("ShaderNodeValToRGB")
    cr = r.color_ramp
    for i, (pos, hx) in enumerate(stops):
        col = tuple(int(hx[j:j + 2], 16) / 255 for j in (1, 3, 5))
        col = tuple(cc ** 2.2 for cc in col) + (1.0,)  # sRGB hex -> linear
        if i < 2:
            e = cr.elements[i]
            e.position = pos
        else:
            e = cr.elements.new(pos)
        e.color = col
    nt.links.new(inp, r.inputs[0])
    return r.outputs[0]


def _noise(nt, vec, scale, detail=4.0, rough=0.55, dist=0.0):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    if "Distortion" in n.inputs:
        n.inputs["Distortion"].default_value = dist
    nt.links.new(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _math(nt, op, a, b=None, c=None, clamp=False):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    m.use_clamp = clamp
    for i, x in enumerate((a, b, c)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            m.inputs[i].default_value = x
        else:
            nt.links.new(x, m.inputs[i])
    return m.outputs[0]


def _maprange(nt, x, a, b, c=0.0, d=1.0, smooth=True):
    m = nt.nodes.new("ShaderNodeMapRange")
    if smooth:
        m.interpolation_type = "SMOOTHSTEP"
    m.inputs["From Min"].default_value = a
    m.inputs["From Max"].default_value = b
    m.inputs["To Min"].default_value = c
    m.inputs["To Max"].default_value = d
    nt.links.new(x, m.inputs["Value"])
    return m.outputs["Result"]


def _mix(nt, a, b, fac, mode="MIX"):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.blend_type = mode
    m.clamp_result = True
    for sock, x in (("A", a), ("B", b)):
        if isinstance(x, tuple):
            m.inputs[sock].default_value = x
        else:
            nt.links.new(x, m.inputs[sock])
    if isinstance(fac, (int, float)):
        m.inputs["Factor"].default_value = fac
    else:
        nt.links.new(fac, m.inputs["Factor"])
    return m.outputs["Result"]


def _hexlin(hx):
    return tuple((int(hx[j:j + 2], 16) / 255) ** 2.2 for j in (1, 3, 5)) + (1.0,)


def high_material(kind, size):
    """Procedural painterly stone + moss emission (for EMIT bake) + diffuse with bump (for NORMAL bake)."""
    m = bpy.data.materials.new(f"HP_{kind}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "rk"; attr.attribute_type = "GEOMETRY"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    cav, mossb, hgt = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    s = 1.0 / size
    # --- stone base: mid-scale patches + subtle strata/streaks
    n_big = _noise(nt, obj, 1.4 * s * 4, 3, 0.5)
    n_mid = _noise(nt, obj, 6.0 * s * 4 / 4, 6, 0.6, dist=0.3)
    base_v = _math(nt, "MULTIPLY_ADD", n_big, 0.6, _math(nt, "MULTIPLY", n_mid, 0.4))
    if kind == "boulder":
        stone = _ramp(nt, [(0.28, "#5E5A55"), (0.42, "#7C776C"), (0.56, "#968E7E"), (0.72, "#ACA28C")], base_v)
    else:
        stone = _ramp(nt, [(0.30, "#666158"), (0.45, "#857E70"), (0.58, "#9A917F"), (0.72, "#B0A690")], base_v)
        # horizontal strata tint
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (0.15, 0.15, 2.2)
        nt.links.new(obj, mp.inputs["Vector"])
        sband = _noise(nt, mp.outputs[0], 1.0, 2, 0.4)
        stone = _mix(nt, stone, _hexlin("#8C7A62"), _maprange(nt, sband, 0.55, 0.7, 0.0, 0.35))
        # dark vertical water streaks
        mp2 = nt.nodes.new("ShaderNodeMapping")
        mp2.inputs["Scale"].default_value = (1.6, 1.6, 0.12)
        nt.links.new(obj, mp2.inputs["Vector"])
        streak = _noise(nt, mp2.outputs[0], 1.0, 3, 0.5)
        stone = _mix(nt, stone, _hexlin("#4E4A44"), _maprange(nt, streak, 0.56, 0.72, 0.0, 0.55))
    # cool / warm hue drift
    cool = _noise(nt, obj, 0.9 * s * 2, 2, 0.5)
    stone = _mix(nt, stone, _hexlin("#6C7584"), _maprange(nt, cool, 0.5, 0.68, 0.0, 0.45))
    warm = _noise(nt, _mix(nt, obj, (3.3, 1.7, 0.9, 1.0), 0.0), 1.3 * s * 2, 2, 0.5)
    stone = _mix(nt, stone, _hexlin("#A08660"), _maprange(nt, warm, 0.52, 0.7, 0.0, 0.4))
    # convex edges lighter, cavities darker
    stone = _mix(nt, stone, _hexlin("#C2B8A2"), _maprange(nt, cav, 0.58, 0.9, 0.0, 0.55))
    stone = _mix(nt, stone, _hexlin("#3A3631"), _maprange(nt, cav, 0.42, 0.12, 0.0, 0.75))
    # lichen spots
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 3.5 * s * 2
    lw = _noise(nt, obj, 6.0 * s * 2, 3, 0.6)
    nt.links.new(_mix(nt, obj, lw, 0.15), vor.inputs["Vector"])
    spots = _maprange(nt, vor.outputs["Distance"], 0.3, 0.18, 0.0, 1.0)
    lichen_n = _noise(nt, obj, 3.0 * s * 2, 2, 0.5)
    stone = _mix(nt, stone, _hexlin("#B9B894"), _math(nt, "MULTIPLY", spots, _maprange(nt, lichen_n, 0.5, 0.62, 0, 0.45)))
    stone = _mix(nt, stone, _hexlin("#B08A58"), _math(nt, "MULTIPLY", spots, _maprange(nt, lichen_n, 0.4, 0.3, 0, 0.35)))
    # --- moss
    mn = _noise(nt, obj, 2.2 * s * 2, 5, 0.6, dist=0.4)
    mval = _math(nt, "ADD", mossb, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", mn, 0.5), 0.9))
    mmask = _maprange(nt, mval, 0.5, 0.6, 0.0, 1.0)
    mcol_n = _noise(nt, obj, 5.0 * s * 2, 4, 0.6)
    mcol = _ramp(nt, [(0.3, "#3E6A2C"), (0.45, "#5C8C34"), (0.58, "#7BA640"), (0.7, "#9DBE52")], mcol_n)
    mcol = _mix(nt, mcol, _hexlin("#2F5225"), _maprange(nt, cav, 0.45, 0.2, 0.0, 0.6))
    # moss fringe slightly yellow
    fringe = _math(nt, "SUBTRACT", _maprange(nt, mval, 0.44, 0.56, 0, 1), mmask)
    col = _mix(nt, stone, _hexlin("#A3A55A"), _math(nt, "MULTIPLY", fringe, 0.8, clamp=True))
    col = _mix(nt, col, mcol, mmask)
    # dirt near ground
    col = _mix(nt, col, _hexlin("#4C4034"), _maprange(nt, hgt, 0.1 if kind == "boulder" else 0.05, 0.0, 0.0, 0.7))
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col, em.inputs["Color"])
    # bump for normal bake
    bh = _noise(nt, obj, 22.0 * s * 2, 8, 0.65)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.004 * size
    nt.links.new(bh, bump.inputs["Height"])
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    nt.links.new(bump.outputs["Normal"], diff.inputs["Normal"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(em.outputs[0], add.inputs[0])
    nt.links.new(diff.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m


# ============================================================================= low poly
def make_low(name, P_fn, prm, subdiv, target_tris):
    U, F = ico_dirs(subdiv)
    V = P_fn(U, prm, detail=False)
    ob = mesh_from(name, V, F)
    ratio = min(1.0, target_tris / len(F))
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me2
    bpy.data.meshes.remove(old)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    # drop the buried flat base (never visible; frees texture space)
    bm.normal_update()
    tol = 0.01 + 0.002 * max(prm["radii"])
    base = [f for f in bm.faces if f.normal.z < -0.9 and f.calc_center_median().z < prm["zfloor"] + tol]
    if base:
        bmesh.ops.delete(bm, geom=base, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.polygons.foreach_set("use_smooth", np.ones(len(ob.data.polygons), bool))
    ob.data.update()
    return ob


def uv_unwrap(ob, rect=(0, 0, 1, 1), angle=60.0, margin=0.006):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    except Exception as e:  # noqa: BLE001
        print("pack_islands failed", e)
    bpy.ops.object.mode_set(mode="OBJECT")
    me = ob.data
    uv = np.zeros(len(me.loops) * 2)
    me.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    x0, y0, x1, y1 = rect
    pad = 0.008
    uv = np.column_stack([x0 + pad + uv[:, 0] * (x1 - x0 - 2 * pad), y0 + pad + uv[:, 1] * (y1 - y0 - 2 * pad)])
    me.uv_layers[0].data.foreach_set("uv", uv.ravel())


def low_data(ob, rnd, size):
    """Extract arrays + compute vertex colours (ray-traced AO) and smooth normals."""
    me = ob.data
    n = len(me.vertices)
    V = np.zeros(n * 3); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
    N = vertex_normals(me)
    F = np.array([list(p.vertices) for p in me.polygons], np.int64)
    uv = np.zeros(len(me.loops) * 2); me.uv_layers[0].data.foreach_get("uv", uv)
    bvh = BVHTree.FromPolygons([tuple(v) for v in V], [tuple(f) for f in F])
    rng = np.random.default_rng(int(rnd * 1e6))
    nd = 48
    dirs = rng.normal(size=(nd, 3)); dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    ao = np.zeros(n)
    reach = size * 0.6
    for i in range(n):
        nn = N[i]
        occ, tot = 0.0, 0.0
        for d in dirs:
            c = d @ nn
            if c <= 0.05:
                continue
            o = V[i] + nn * size * 0.004
            w = c
            tot += w
            hit = bvh.ray_cast(Vector(o), Vector(d), reach)
            if hit[0] is not None:
                occ += w
            elif d[2] < 0 and o[2] > -0.02:
                tg = (o[2] - 0.0) / -d[2]
                if tg < reach:
                    occ += w * 0.85
        ao[i] = 1 - occ / max(tot, 1e-6)
    ao = np.clip(0.3 + 0.75 * ao, 0.3, 1.0)
    zb = smoothstep(-0.05 * size, 0.25 * size, V[:, 2])
    ao *= 0.7 + 0.3 * zb
    C = np.stack([np.clip(ao, 0.25, 1), np.zeros(n), np.full(n, rnd), np.ones(n)], 1)
    return dict(V=V, F=F, N=N, UV=uv.reshape(-1, 2), C=C)


def build_from_data(name, d, mat):
    V, F = d["V"], d["F"]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.update()
    me.materials.append(mat)
    me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", d["UV"].astype(np.float32).ravel())
    ca = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    ca.data.foreach_set("color", d["C"].astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.update()
    me.normals_split_custom_set_from_vertices([tuple(n) for n in fl.unit(d["N"])])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ============================================================================= bake
def setup_cycles(samples=4):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    try:
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.render.bake.margin = 16
    try:
        sc.render.bake.margin_type = "EXTEND"
    except Exception:
        pass


def new_image(name, size, fill, noncolor=False):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    px = np.tile(np.array(list(fill) + [1.0], np.float32), size * size)
    img.pixels.foreach_set(px)
    return img


def bake_pair(highs, low, albedo_img, normal_img, size_ref):
    """Bake EMIT -> albedo and NORMAL -> normal map from highs onto the (joined) low."""
    bake_mat = bpy.data.materials.new("BAKE_low")
    bake_mat.use_nodes = True
    nt = bake_mat.node_tree
    tnode = nt.nodes.new("ShaderNodeTexImage")
    low.data.materials.clear()
    low.data.materials.append(bake_mat)
    bpy.ops.object.select_all(action="DESELECT")
    for h in highs:
        h.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    kw = dict(use_selected_to_active=True, cage_extrusion=0.03 * size_ref, max_ray_distance=0.1 * size_ref,
              margin=16, use_clear=False, target="IMAGE_TEXTURES")
    for typ, img in (("EMIT", albedo_img), ("NORMAL", normal_img)):
        tnode.image = img
        nt.nodes.active = tnode
        extra = dict(normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z") if typ == "NORMAL" else {}
        bpy.ops.object.bake(type=typ, **kw, **extra)
        print("BAKED", typ, img.name)


def save_img(img, fname):
    path = os.path.join(TEX, fname)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("wrote", path)
    return path


# ============================================================================= boulders
BOULDERS = {
    "A": dict(radii=(1.75, 1.3, 1.0), n_planes=18, seed=511, soft=30.0),            # big flat-topped ~2.4 m
    "B": dict(radii=(0.86, 0.75, 0.66), n_planes=16, seed=512, soft=30.0),          # chunky ~1.4 m
    "C": dict(radii=(0.4, 0.33, 0.3), n_planes=13, seed=513, soft=28.0),            # small ~0.65 m
    "D": dict(radii=(1.0, 0.8, 1.06), n_planes=20, seed=514, soft=45.0,             # angular upright ~1.7 m
              frac=(0.6, 0.84), notches=3),
}
QUAD = {"A": (0.0, 0.5, 0.5, 1.0), "B": (0.5, 0.5, 1.0, 1.0), "C": (0.0, 0.0, 0.5, 0.5), "D": (0.5, 0.0, 1.0, 0.5)}
BOULDER_TRIS = {"A": 1400, "B": 1100, "C": 500, "D": 1300}
_BOULDER_CACHE = {}


def boulder_prm(key):
    b = BOULDERS[key]
    rng = np.random.default_rng(b["seed"])
    a, bb, c = b["radii"]

    def r_e(v):
        return 1.0 / math.sqrt((v[0] / a) ** 2 + (v[1] / bb) ** 2 + (v[2] / c) ** 2)
    t0 = np.array([rng.normal(0, 0.2), rng.normal(0, 0.2), 1.0]); t0 /= np.linalg.norm(t0)
    top = [(t0, r_e(t0) * rng.uniform(0.74, 0.84))]
    planes = rand_planes(rng, b["n_planes"], r_e, frac=b.get("frac", (0.62, 0.86)), zmin=-0.3, extra=top)
    notches = []
    for k in range(b.get("notches", 2)):
        m = rng.normal(size=3); m[2] = abs(m[2]) * 0.5; m /= np.linalg.norm(m)
        notches.append((m, rng.uniform(0.04, 0.09), rng.uniform(0.08, 0.16)))
    sink = 0.08 * 2 * c
    return dict(radii=b["radii"], planes=planes, seed=b["seed"], zc=c - sink, zfloor=-sink * 1.3,
                soft=b.get("soft", 18.0), notches=notches)


def bake_boulders():
    print("== baking boulder atlas")
    fl.reset_scene()
    setup_cycles(4)
    alb = new_image("Rock_Mossy_albedo", 2048, (0.35, 0.33, 0.3))
    nrm = new_image("Rock_Mossy_normal", 2048, (0.5, 0.5, 1.0), noncolor=True)
    highs, lows = [], []
    datas = {}
    for i, key in enumerate("ABCD"):
        prm = boulder_prm(key)
        size = max(prm["radii"]) * 2
        U, F = ico_dirs(7)
        Vh = boulder_shape(U, prm, detail=True)
        hi = mesh_from(f"HI_{key}", Vh, F)
        high_attributes(hi, "boulder", size)
        hi.data.materials.append(high_material("boulder", size))
        lo = make_low(f"Rock_Mossy_{key}", boulder_shape, prm, 5, BOULDER_TRIS[key])
        uv_unwrap(lo, QUAD[key])
        off = Vector((i * 8.0, 0, 0))
        hi.location = off
        lo.location = off
        bpy.context.view_layer.update()
        # bake per boulder (each into its own quadrant, use_clear=False keeps the others)
        bake_pair([hi], lo, alb, nrm, size)
        lo.location = (0, 0, 0)
        hi.hide_render = True
        datas[key] = low_data(lo, np.random.default_rng(BOULDERS[key]["seed"]).random(), size)
        highs.append(hi); lows.append(lo)
    save_img(alb, "Rock_Mossy_albedo.png")
    save_img(nrm, "Rock_Mossy_normal.png")
    _BOULDER_CACHE.update(datas)


def boulder(key):
    if key not in _BOULDER_CACHE:
        bake_boulders()
    fl.reset_scene()
    mat = fl.make_material("M_Rock_Mossy", "Rock_Mossy_albedo.png", "Rock_Mossy_normal.png", roughness=0.9)
    ob = build_from_data(f"Rock_Mossy_{key}", _BOULDER_CACHE[key], mat)
    size = max(ob.dimensions)
    return [ob], dict(preview_kw=dict(human=size > 1.0, el=18.0, sun_az=150.0, sun_el=45.0))


# ============================================================================= cliffs
CLIFFS = {
    "A": dict(radii=(5.0, 2.7, 6.2), seed=611, joint=2.8, col_amp=0.3, dip=0.05, tris=5600, thick=(0.55, 1.6)),
    "B": dict(radii=(4.6, 3.0, 7.4), seed=612, joint=2.6, col_amp=0.42, dip=-0.13, tris=5800, thick=(0.5, 1.9)),
}


def cliff_prm(key):
    c = CLIFFS[key]
    rng = np.random.default_rng(c["seed"])
    a, b, cc = c["radii"]
    p = 4.5

    def r_s(v):
        return (abs(v[0] / a) ** p + abs(v[1] / b) ** p + abs(v[2] / cc) ** p) ** (-1 / p)
    extra = [(np.array([0.0, 1.0, 0.0]), b * 0.6)]  # flat-ish back against the mountain
    t = np.array([rng.normal(0, 0.25), rng.normal(0, 0.2), 1.0]); t /= np.linalg.norm(t)
    extra.append((t, r_s(t) * 0.86))
    planes = rand_planes(rng, 12, r_s, frac=(0.82, 0.96), zmin=-0.05, horiz=True, extra=extra)
    planes += rand_planes(rng, 3, r_s, frac=(0.8, 0.92), zmin=0.4)
    zc = cc * 0.42
    bnd = [-4.0]
    while bnd[-1] < 20:
        bnd.append(bnd[-1] + rng.uniform(*c["thick"]))
    nl = len(bnd)
    off = rng.uniform(-0.3, 0.3, nl)
    deep = rng.random(nl) < 0.18
    off[deep] -= 0.45                      # a few deeply recessed bands
    prm = dict(c)
    prm.update(radii=c["radii"], planes=planes, zc=zc, zfloor=-0.5, soft=60.0, p=p, layers=np.array(bnd),
               layer_off=off, layer_lean=0.38)
    return prm


def cliff(key):
    prm = cliff_prm(key)
    size = max(prm["radii"]) * 2
    fl.reset_scene()
    setup_cycles(4)
    alb = new_image(f"Rock_Cliff_{key}_albedo", 2048, (0.35, 0.33, 0.3))
    nrm = new_image(f"Rock_Cliff_{key}_normal", 2048, (0.5, 0.5, 1.0), noncolor=True)
    U, F = ico_dirs(8)
    Vh = cliff_shape(U, prm, detail=True)
    hi = mesh_from(f"HI_{key}", Vh, F)
    high_attributes(hi, "cliff", size)
    hi.data.materials.append(high_material("cliff", size))
    lo = make_low(f"Cliff_{key}", cliff_shape, prm, 6, prm["tris"])
    uv_unwrap(lo, (0, 0, 1, 1), angle=55.0, margin=0.004)
    bake_pair([hi], lo, alb, nrm, size * 0.6)
    save_img(alb, f"Rock_Cliff_{key}_albedo.png")
    save_img(nrm, f"Rock_Cliff_{key}_normal.png")
    d = low_data(lo, np.random.default_rng(prm["seed"]).random(), size)
    fl.reset_scene()
    mat = fl.make_material(f"M_Rock_Cliff_{key}", f"Rock_Cliff_{key}_albedo.png", f"Rock_Cliff_{key}_normal.png",
                           roughness=0.9)
    ob = build_from_data(f"Cliff_{key}", d, mat)
    return [ob], dict(preview_kw=dict(human=True, el=10.0, sun_az=150.0, sun_el=45.0))


BUILDERS = {}
for _k in "ABCD":
    BUILDERS[f"Rock_Mossy_{_k}"] = (lambda k=_k: boulder(k))
for _k in "AB":
    BUILDERS[f"Cliff_{_k}"] = (lambda k=_k: cliff(k))
