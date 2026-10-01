"""INK DRIFT: TOKYO foliage toolkit (Blender 5.x, run headless).

Core pieces:
  Geo            - accumulates verts/faces/uv/vertex-colour/custom-normals/material slots -> one bpy mesh
  tube()         - generalized cylinder along a polyline (parallel-transport frames), optional root flare
  Branch, grow() - simple tropism/wobble branch growth used by the species builders
  Clump, cards   - alpha-cutout leaf-card clusters placed inside ellipsoid clumps
  BlobField      - sum-of-gaussian-ellipsoids "canopy mass" field. Leaf-card normals are the field
                   gradient (+ global canopy blend), so a toon ramp yields big soft light/shadow masses.
  materials, export_fbx(), render_preview(), verify_fbx()

Vertex colour (FLOAT_COLOR, point domain, exported linear):
  R = ambient occlusion-ish (1 = open, darker toward canopy interior / trunk base)
  G = wind sway weight (0 at trunk base -> 1 at leaf tips)
  B = random per leaf cluster / per branch (hue variation)
  A = 1
"""
import json
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MODEL_DIR = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Trees")
TEX_DIR = os.path.join(MODEL_DIR, "Textures")
PREV_DIR = os.path.join(HERE, "previews")
STATS_DIR = os.path.join(PREV_DIR, "stats")
sys.path.insert(0, HERE)
import atlas_layout  # noqa: E402

Z = np.array([0.0, 0.0, 1.0])


# ============================================================================= math helpers
def unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def any_perp(d):
    a = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    return unit(np.cross(d, a))


def rand_unit(rng, n=None):
    v = rng.normal(size=(3,) if n is None else (n, 3))
    return unit(v)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rot_axis(v, axis, ang):
    """Rodrigues rotation of vector(s) v about unit axis."""
    axis = unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(axis, v) * s + np.outer(np.dot(v, axis), axis).reshape(np.shape(v)) * (1 - c)


# ============================================================================= mesh accumulator
class Geo:
    def __init__(self, name):
        self.name = name
        self.V, self.N, self.UV, self.C = [], [], [], []
        self.faces, self.fmat = [], []
        self.nv = 0
        self.mats = []

    def mat_index(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def add(self, V, N, UV, C, F, mat):
        V = np.asarray(V, np.float64).reshape(-1, 3)
        k = len(V)
        N = np.asarray(N, np.float64).reshape(-1, 3)
        UV = np.asarray(UV, np.float64).reshape(-1, 2)
        C = np.asarray(C, np.float64).reshape(-1, 4) if np.ndim(C) == 2 else np.tile(np.asarray(C, np.float64), (k, 1))
        assert len(N) == k and len(UV) == k and len(C) == k, (len(V), len(N), len(UV), len(C))
        mi = self.mat_index(mat)
        base = self.nv
        self.V.append(V); self.N.append(unit(N)); self.UV.append(UV); self.C.append(C)
        for f in F:
            self.faces.append(tuple(int(i) + base for i in f))
            self.fmat.append(mi)
        self.nv += k
        return base

    def tris(self):
        return sum(len(f) - 2 for f in self.faces)

    def arrays(self):
        return (np.concatenate(self.V), np.concatenate(self.N), np.concatenate(self.UV), np.concatenate(self.C))

    def build(self, materials):
        """Create the bpy object. materials: dict name->bpy material."""
        V, N, UV, C = self.arrays()
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(V.tolist(), [], self.faces)
        me.validate(clean_customdata=False)
        for m in self.mats:
            me.materials.append(materials[m])
        me.polygons.foreach_set("material_index", np.array(self.fmat, np.int32))
        me.polygons.foreach_set("use_smooth", np.ones(len(self.faces), bool))
        # UVs (per loop from per-vertex)
        lv = np.zeros(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        uvl = me.uv_layers.new(name="UVMap")
        uvl.data.foreach_set("uv", UV[lv].astype(np.float32).ravel())
        # vertex colours
        ca = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
        ca.data.foreach_set("color", np.clip(C, 0, 1).astype(np.float32).ravel())
        me.color_attributes.active_color = ca
        me.color_attributes.render_color_index = 0
        me.update()
        me.normals_split_custom_set_from_vertices([tuple(n) for n in N])
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ============================================================================= tubes
def tube(geo, pts, radii, sides, mat, u_rep=1, v_len=1.0, s0=0.0, colors=None, cap=True, flare=None,
         rng=None, base_extend=0.0):
    """Generalized cylinder. colors: (n,4) per ring. flare: (amp, height, lobes) for root flare."""
    pts = np.asarray(pts, np.float64)
    radii = np.asarray(radii, np.float64)
    if base_extend > 0:  # push the first ring below ground so trunks sit into terrain
        d0 = unit(pts[1] - pts[0])
        pts = np.vstack([pts[0] - d0 * base_extend, pts])
        radii = np.concatenate([[radii[0]], radii])
        if colors is not None:
            colors = np.vstack([colors[:1], colors])
    n = len(pts)
    T = unit(np.gradient(pts, axis=0))
    Ns = [any_perp(T[0])]
    for i in range(1, n):
        v = Ns[-1] - T[i] * np.dot(Ns[-1], T[i])
        if np.linalg.norm(v) < 1e-6:
            v = any_perp(T[i])
        Ns.append(unit(v))
    Nn = np.array(Ns)
    B = np.cross(T, Nn)
    ang = 2 * np.pi * np.arange(sides + 1) / sides
    off = np.cos(ang)[None, :, None] * Nn[:, None, :] + np.sin(ang)[None, :, None] * B[:, None, :]
    r = np.repeat(radii[:, None], sides + 1, 1)
    if flare is not None:
        amp, h, lobes = flare
        ph = rng.uniform(0, 6.28) if rng is not None else 0.0
        z = pts[:, 2] - pts[0, 2]
        fall = np.exp(-np.maximum(z, 0) / h)[:, None]
        lobe = (0.5 + 0.5 * np.cos(lobes * ang + ph))[None, :] ** 2
        lobe2 = (0.5 + 0.5 * np.cos((lobes + 1) * ang + ph * 1.7))[None, :] ** 3
        r = r * (1 + amp * fall * (0.35 + 0.65 * lobe + 0.3 * lobe2))
        r[:, -1] = r[:, 0]
    V = pts[:, None, :] + off * r[..., None]
    # normals with taper slope
    dr = np.gradient(radii) / (np.linalg.norm(np.gradient(pts, axis=0), axis=1) + 1e-9)
    Nrm = unit(off - T[:, None, :] * dr[:, None, None] * 0.5)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)]) - (base_extend if base_extend > 0 else 0.0)
    UV = np.zeros((n, sides + 1, 2))
    UV[..., 0] = u_rep * np.arange(sides + 1)[None, :] / sides
    UV[..., 1] = ((s0 + s) / v_len)[:, None]
    if colors is None:
        colors = np.tile([1, 0, 0.5, 1], (n, 1))
    C = np.repeat(np.asarray(colors)[:, None, :], sides + 1, 1)
    F = []
    S1 = sides + 1
    for i in range(n - 1):
        for j in range(sides):
            a = i * S1 + j
            F.append((a, a + 1, a + S1 + 1, a + S1))
    V = V.reshape(-1, 3); Nrm = Nrm.reshape(-1, 3); UV = UV.reshape(-1, 2); C = C.reshape(-1, 4)
    if cap:
        tip = pts[-1] + T[-1] * radii[-1] * 1.5
        ti = len(V)
        V = np.vstack([V, tip]); Nrm = np.vstack([Nrm, T[-1]])
        UV = np.vstack([UV, [u_rep * 0.5, UV[-1, 1] + radii[-1] / v_len]]); C = np.vstack([C, C[-1]])
        last = (n - 1) * S1
        for j in range(sides):
            F.append((last + j, last + j + 1, ti))
    return geo.add(V, Nrm, UV, C, F, mat)


# ============================================================================= branches
class Branch:
    def __init__(self, pts, radii, level, parent=None, t_parent=0.0, rnd=0.5):
        self.pts = np.asarray(pts, np.float64)
        self.radii = np.asarray(radii, np.float64)
        self.level = level
        self.parent = parent
        self.t_parent = t_parent
        seg = np.linalg.norm(np.diff(self.pts, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.s[-1])
        self.s0 = 0.0 if parent is None else parent.s_at(t_parent)
        self.children = []
        self.rnd = rnd
        self.sides = None
        if parent is not None:
            parent.children.append(self)

    def s_at(self, t):
        return self.s0 + t * self.length

    def at(self, t):
        s = np.clip(t, 0, 1) * self.length
        i = int(np.clip(np.searchsorted(self.s, s) - 1, 0, len(self.s) - 2))
        f = (s - self.s[i]) / max(self.s[i + 1] - self.s[i], 1e-9)
        p = self.pts[i] * (1 - f) + self.pts[i + 1] * f
        r = self.radii[i] * (1 - f) + self.radii[i + 1] * f
        T = unit(self.pts[i + 1] - self.pts[i])
        return p, r, T

    @property
    def tip(self):
        return self.pts[-1]


def grow(p0, d0, length, r0, r1, rng, seg=0.3, wobble=0.15, trop=None, trop_k=0.0, rpow=1.0,
         bend_axis=None, bend=0.0, min_pts=3, envelope=None, min_dz=None):
    """Grow a polyline from p0 along d0. trop: unit vector pulled toward with trop_k per meter."""
    n = max(min_pts - 1, int(math.ceil(length / seg)))
    step = length / n
    pts = [np.asarray(p0, np.float64)]
    d = unit(d0)
    w = np.zeros(3)
    for i in range(n):
        rnd = rng.normal(size=3)
        rnd -= rnd.dot(d) * d
        w = 0.55 * w + 0.45 * rnd
        d = d + w * wobble * math.sqrt(step)
        if trop is not None and trop_k:
            d = d + np.asarray(trop) * trop_k * step
        if bend_axis is not None and bend:
            d = rot_axis(d, bend_axis, bend * step)
        d = unit(d)
        if min_dz is not None and d[2] < min_dz:
            d[2] = min_dz
            d = unit(d)
        nxt = pts[-1] + d * step
        if envelope is not None and envelope(nxt) > 1.0 and i > 1:
            # steer back inside the envelope
            d = unit(d - 0.6 * unit(nxt - envelope.center))
            nxt = pts[-1] + d * step
        pts.append(nxt)
    t = np.linspace(0, 1, len(pts))
    radii = r0 + (r1 - r0) * t ** rpow
    return np.array(pts), radii


class Ellipsoid:
    def __init__(self, center, radii):
        self.center = np.asarray(center, np.float64)
        self.radii = np.asarray(radii, np.float64)

    def __call__(self, p):
        return float(np.sqrt(np.sum(((np.asarray(p) - self.center) / self.radii) ** 2)))


class Cone:
    """Conical envelope: base radius rb at z0, apex at z1. value <=1 inside."""

    def __init__(self, z0, z1, rb, power=1.0, zbot=None):
        self.z0, self.z1, self.rb, self.power = z0, z1, rb, power
        self.zbot = z0 if zbot is None else zbot
        self.center = np.array([0.0, 0.0, (z0 + z1) / 2])

    def radius(self, z):
        t = np.clip((z - self.z0) / (self.z1 - self.z0), 0, 1)
        return self.rb * (1 - t) ** self.power + 0.05

    def __call__(self, p):
        p = np.asarray(p)
        r = math.hypot(p[0], p[1])
        v = r / self.radius(p[2])
        if p[2] > self.z1:
            v = max(v, 1 + (p[2] - self.z1))
        if p[2] < self.zbot:
            v = max(v, 1 + (self.zbot - p[2]))
        return float(v)


def fit_length(p, d, L, envelope, min_frac=0.25):
    if envelope is None:
        return L
    lo, hi = 0.0, 1.0
    if envelope(p + d * L) <= 1.0:
        return L
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        if envelope(p + d * L * mid) <= 1.0:
            lo = mid
        else:
            hi = mid
    return max(L * lo, L * min_frac)


def child_dir(T, down, phase):
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    Nn = unit(np.cross(T, ref))
    Bb = np.cross(T, Nn)
    perp = math.cos(phase) * Nn + math.sin(phase) * Bb
    return unit(math.cos(down) * T + math.sin(down) * perp)


def spawn(parent, count, t_range, down_deg, rng, length_fn, r_ratio, tip_r, level, phase0=None,
          envelope=None, golden=True, up_bias=0.0, horiz_bias=0.0, **grow_kw):
    """Spawn `count` child branches along parent between t_range. Returns list of Branch."""
    out = []
    phase = rng.uniform(0, 2 * math.pi) if phase0 is None else phase0
    for k in range(count):
        t = t_range[0] + (t_range[1] - t_range[0]) * (k + rng.uniform(0.15, 0.85)) / count
        p, r, T = parent.at(t)
        phase += (2.39996 if golden else 2 * math.pi / max(count, 1)) + rng.normal(0, 0.35)
        down = math.radians(rng.normal(*down_deg))
        d = child_dir(T, down, phase)
        if up_bias:
            d = unit(d + Z * up_bias)
        if horiz_bias:
            d = unit(d * np.array([1, 1, 1 - horiz_bias]))
        L = length_fn(t, parent, rng)
        if L <= 0.05:
            continue
        L = fit_length(p, d, L, envelope)
        rc = min(r * r_ratio, r * 0.92)
        pts, radii = grow(p, d, L, rc, max(tip_r, rc * 0.15), rng, envelope=envelope, **grow_kw)
        out.append(Branch(pts, radii, level, parent, t, rnd=rng.random()))
    return out


def all_branches(root):
    out, stack = [], [root]
    while stack:
        b = stack.pop()
        out.append(b)
        stack.extend(b.children)
    return out


def mesh_branches(geo, branches, mat, sides_by_level, rng, v_len=1.5, min_radius=0.004, ao_fn=None,
                  wind_fn=None, flare=None, u_rep_by_level=None, trunk_extend=0.15, skip_level=99):
    """Mesh every branch as a tube. Vertex colours from ao_fn(points)->(n,), wind_fn(branch, s)->(n,)."""
    for b in branches:
        if b.level >= skip_level or b.radii[0] < min_radius:
            continue
        sides = sides_by_level[min(b.level, len(sides_by_level) - 1)]
        if sides < 3:
            continue
        ao = ao_fn(b.pts) if ao_fn else np.ones(len(b.pts))
        wind = wind_fn(b, b.s0 + b.s) if wind_fn else np.zeros(len(b.pts))
        col = np.stack([ao, wind, np.full(len(b.pts), b.rnd), np.ones(len(b.pts))], 1)
        u_rep = (u_rep_by_level[min(b.level, len(u_rep_by_level) - 1)] if u_rep_by_level
                 else max(1, int(round(2 * math.pi * b.radii[0] / v_len))))
        tube(geo, b.pts, b.radii, sides, mat, u_rep=u_rep, v_len=v_len, s0=b.s0, colors=col,
             cap=b.level > 0, flare=flare if b.level == 0 else None, rng=rng,
             base_extend=trunk_extend if b.level == 0 else 0.0)


def path_wind(max_s, trunk_free=0.0, power=1.4):
    """Wind weight as function of path distance from the root (0 at base, ~1 at farthest tip)."""
    def f(branch, s):
        x = np.clip((np.asarray(s) - trunk_free) / max(max_s - trunk_free, 1e-6), 0, 1)
        return 0.85 * x ** power
    return f


def max_path(branches):
    return max(b.s0 + b.length for b in branches)


# ============================================================================= canopy field
class BlobField:
    """Sum of gaussian ellipsoid blobs. normal(p) = normalized gradient (outward)."""

    def __init__(self, centers, radii, k=1.0):
        self.c = np.asarray(centers, np.float64).reshape(-1, 3)
        self.r = np.asarray(radii, np.float64).reshape(-1, 3)
        self.k = k

    def eval(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 3)
        F = np.zeros(len(P))
        G = np.zeros((len(P), 3))
        inside = np.zeros(len(P))
        for c, r in zip(self.c, self.r):
            d = (P - c) / r
            q = np.sum(d * d, 1)
            f = np.exp(-self.k * q)
            F += f
            G += (f * 2 * self.k)[:, None] * d / r
            inside = np.maximum(inside, 1 - np.sqrt(q))
        return F, G, inside

    def normals(self, P, global_center=None, global_radii=None, w_local=0.7, up=0.15, eps_frac=0.15):
        F, G, _ = self.eval(P)
        mag = np.linalg.norm(G, axis=1)
        eps = eps_frac * (np.median(mag) + 1e-9)
        nl = G / (mag + eps)[:, None]
        if global_center is not None:
            ng = unit((np.asarray(P) - global_center) / np.asarray(global_radii) ** 2)
        else:
            ng = np.zeros_like(nl)
        n = w_local * nl + (1 - w_local) * ng + up * Z
        return unit(n)


def kmeans(X, k, rng, iters=25):
    X = np.asarray(X, np.float64)
    k = min(k, len(X))
    C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = X[m].mean(0)
    return C, lab


def masses_from_clumps(clumps, k, rng, pad=1.0, min_r=0.6, z_squash=1.0, sharp=2.0):
    """Cluster clump centres into k canopy masses -> BlobField."""
    X = np.array([c.center for c in clumps])
    R = np.array([np.mean(c.radii) for c in clumps])
    C, lab = kmeans(X, k, rng)
    cents, radii = [], []
    for j in range(len(C)):
        m = lab == j
        if not m.any():
            continue
        pts = X[m]
        cen = pts.mean(0)
        sd = pts.std(0) if m.sum() > 1 else np.zeros(3)
        rr = np.maximum(sd * 1.6 + R[m].mean() * pad, min_r)
        rxy = max(rr[0], rr[1])
        cents.append(cen)
        radii.append([rxy, rxy, max(rr[2] * z_squash, min_r * 0.8)])
    return BlobField(cents, radii, k=sharp)


# ============================================================================= leaf cards
class Clump:
    def __init__(self, center, radii, n_cards, size, wind=0.7, rnd=None, out=None, kind="mix", rng=None):
        self.center = np.asarray(center, np.float64)
        self.radii = np.asarray(radii, np.float64) if np.ndim(radii) else np.array([radii] * 3, np.float64)
        self.n = int(n_cards)
        self.size = size
        self.wind = wind
        self.rnd = rng.random() if rnd is None else rnd
        self.out = out  # preferred outward direction (unit) or None
        self.kind = kind


def card_quad(p, right, up, w, h, pivot, uvr, segs=1, bend=0.0, bend_dir=None):
    """Return V (k,3), UV (k,2), F list, tipness (k,) for a (possibly bent) card."""
    u0, v0, u1, v1 = uvr
    if pivot == "center":
        origin = p - right * w / 2 - up * h / 2
    elif pivot == "bottom":
        origin = p - right * w / 2
    else:  # left
        origin = p - up * h / 2
    V, UV, tipness = [], [], []
    for j in range(segs + 1):
        fy = j / segs
        for i in range(2):
            fx = float(i)
            q = origin + right * w * fx + up * h * fy
            if bend and bend_dir is not None:
                q = q + bend_dir * bend * h * fy * fy
            V.append(q)
            UV.append([u0 + (u1 - u0) * fx, v0 + (v1 - v0) * fy])
            if pivot == "center":
                tipness.append(math.hypot(fx - 0.5, fy - 0.5) * 1.4)
            elif pivot == "bottom":
                tipness.append(fy)
            else:
                tipness.append(fx)
    F = []
    for j in range(segs):
        a = j * 2
        F.append((a, a + 1, a + 3, a + 2))
    return np.array(V), np.array(UV), F, np.array(tipness)


def scatter_cards(geo, clumps, atlas, mat, rng, field, gc, gr, round_cells=("round_a", "round_b"),
                  spray_cells=("spray_a", "spray_b"), spray_frac=0.3, shell=(0.35, 1.0), w_local=0.7, up=0.15,
                  ao_floor=0.3, ao_z=(None, None), droop=0.25, spray_len=1.15, face_out=0.8, card_aspect=1.0,
                  normal_override=None):
    """Place leaf cards for each clump. Normals from `field` (BlobField) blended with global ellipsoid."""
    allV, allN, allUV, allC, allF = [], [], [], [], []
    base = 0
    zlo = ao_z[0] if ao_z[0] is not None else min(c.center[2] - c.radii[2] for c in clumps)
    zhi = ao_z[1] if ao_z[1] is not None else max(c.center[2] + c.radii[2] for c in clumps)
    for cl in clumps:
        for k in range(cl.n):
            is_spray = rng.random() < spray_frac
            dirv = rand_unit(rng)
            if cl.out is not None:
                dirv = unit(dirv + cl.out * 0.8)
            if is_spray:
                rf = rng.uniform(0.2, 0.6)
            else:
                rf = shell[0] + (shell[1] - shell[0]) * rng.random() ** 0.6
            p = cl.center + dirv * rf * cl.radii
            outward = unit((p - cl.center) / cl.radii + 1e-6 * rand_unit(rng))
            nc = unit(outward * face_out + rand_unit(rng) * (1 - face_out + 0.35))
            s = cl.size * rng.uniform(0.8, 1.2)
            if is_spray:
                cell = spray_cells[rng.integers(len(spray_cells))]
                # spray grows outward from inside the clump; drooping
                upv = outward - nc * np.dot(outward, nc)
                upv = unit(upv - Z * droop + 1e-6 * rand_unit(rng))
                rightv = unit(np.cross(upv, nc))
                upv = unit(np.cross(nc, rightv))
                V, UV, F, tip = card_quad(p, rightv, upv, s * card_aspect, s * spray_len,
                                          "bottom", atlas_layout.cell_uv(atlas, cell))
            else:
                cell = round_cells[rng.integers(len(round_cells))]
                rightv = unit(np.cross(nc, rand_unit(rng)))
                upv = unit(np.cross(nc, rightv))
                # keep the twig base of the texture roughly pointing down/in
                if np.dot(upv, Z) < -0.2:
                    upv, rightv = -upv, -rightv
                V, UV, F, tip = card_quad(p, rightv, upv, s * card_aspect, s, "center",
                                          atlas_layout.cell_uv(atlas, cell))
            allV.append(V); allUV.append(UV)
            allF.extend([tuple(i + base for i in f) for f in F])
            base += len(V)
            # colour placeholder: wind + rnd, AO computed after
            wind = np.clip(cl.wind + (1 - cl.wind) * tip * 0.9, 0, 1)
            allC.append(np.stack([np.ones(len(V)), wind, np.full(len(V), cl.rnd), np.ones(len(V))], 1))
    if not allV:
        return
    V = np.concatenate(allV); UV = np.concatenate(allUV); C = np.concatenate(allC)
    if normal_override is not None:
        N = normal_override(V)
    else:
        N = field.normals(V, gc, gr, w_local=w_local, up=up)
    # AO: interior of masses + global depth + lower canopy darker
    _, _, inside = field.eval(V)
    gd = np.sqrt(np.sum(((V - gc) / gr) ** 2, 1))
    ao = 1.0 - 0.55 * smoothstep(0.0, 0.6, inside) - 0.3 * (1 - smoothstep(0.35, 1.0, gd))
    ao *= 0.78 + 0.22 * smoothstep(zlo, zhi, V[:, 2])
    ao *= 0.9 + 0.1 * np.clip(N[:, 2] * 0.5 + 0.5, 0, 1)
    C[:, 0] = np.clip(ao, ao_floor, 1.0)
    geo.add(V, N, UV, C, allF, mat)


def clumps_along(branch, spacing, radius, n_cards, size, rng, t_from=0.5, wind_fn=None, jitter=0.25, out_up=0.3,
                 radius_jit=0.25, zr=0.8, lift=0.25):
    """Clumps distributed along the outer part of a branch (and at its tip)."""
    out = []
    L = branch.length * (1 - t_from)
    cnt = max(1, int(round(L / spacing)))
    for k in range(cnt + 1):
        t = 1.0 if k == cnt else t_from + (1 - t_from) * (k + rng.uniform(0.2, 0.8)) / (cnt + 1)
        p, r, T = branch.at(t)
        rr = radius * rng.uniform(1 - radius_jit, 1 + radius_jit)
        c = p + rand_unit(rng) * rr * jitter + Z * rr * lift
        wind = float(wind_fn(branch, np.array([branch.s_at(t)]))[0]) if wind_fn else 0.6
        outd = unit(T + Z * out_up)
        out.append(Clump(c, [rr, rr, rr * zr], n_cards, size, wind=max(wind, 0.45), out=outd, rng=rng))
    return out


# ============================================================================= materials
MAT_REGISTRY = {}


def _img(path, noncolor=False):
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def make_material(name, albedo, normal=None, alpha=False, roughness=0.85, normal_strength=1.0):
    """Principled material (FBX-exportable): base colour tex (+alpha), optional normal map."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-400, 100)
    tex.image = _img(os.path.join(TEX_DIR, albedo))
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        mat.use_backface_culling = False
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
    if normal:
        nm = nt.nodes.new("ShaderNodeTexImage"); nm.location = (-400, -200)
        nm.image = _img(os.path.join(TEX_DIR, normal), noncolor=True)
        nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.location = (-150, -200)
        nmap.inputs["Strength"].default_value = normal_strength
        nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    MAT_REGISTRY[name] = dict(albedo=albedo, normal=normal, alpha=alpha)
    return mat


def std_materials(species, bark=True, leaves=True, bark_tex=None, leaf_tex=None):
    mats = {}
    if bark:
        bt = bark_tex or species
        mats[f"M_Bark_{species}"] = make_material(f"M_Bark_{species}", f"Bark_{bt}_albedo.png", f"Bark_{bt}_normal.png")
    if leaves:
        lt = leaf_tex or f"Leaves_{species}"
        mats[f"M_Leaves_{species}"] = make_material(f"M_Leaves_{species}", f"{lt}_albedo.png", alpha=True,
                                                    roughness=0.7)
    return mats


# ============================================================================= scene / export
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MAT_REGISTRY.clear()
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0


def mesh_stats(ob):
    me = ob.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    bb = np.array([ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box])
    return dict(name=ob.name, tris=int(tris), verts=len(me.vertices),
                size=[round(float(x), 3) for x in (bb.max(0) - bb.min(0))],
                materials=[m.name for m in me.materials if m])


def scrub_fbx_paths(path):
    """Blender's FBX exporter always writes an absolute texture 'FileName' (leaks the local home path).
    Rewrite each absolute '<...>/Models/Trees/Textures/x.png' in place as an EQUAL-LENGTH relative path
    './././.../Textures/x.png' so binary node offsets stay valid. RelativeFilename is already 'Textures/x.png'."""
    data = open(path, "rb").read()
    prefix = (os.path.join(MODEL_DIR, "Textures") + "/").encode()
    out, i, n = bytearray(), 0, 0
    while True:
        j = data.find(prefix, i)
        if j < 0:
            out += data[i:]
            break
        out += data[i:j]
        pad = len(prefix) - len(b"Textures/")
        rel = b"./" * (pad // 2) + (b"/" if pad % 2 else b"") + b"Textures/"
        assert len(rel) == len(prefix)
        out += rel
        i = j + len(prefix)
        n += 1
    if n:
        open(path, "wb").write(bytes(out))
    home = os.path.expanduser("~").encode()
    assert home not in bytes(out), "absolute path still present in " + path
    return n


def export_fbx(objs, name):
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, name + ".fbx")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y", bake_space_transform=True,
        use_mesh_modifiers=True, mesh_smooth_type="OFF", use_tspace=False,
        colors_type="LINEAR", prioritize_active_color=True,
        add_leaf_bones=False, bake_anim=False, path_mode="RELATIVE", embed_textures=False,
        use_custom_props=False)
    scrub_fbx_paths(path)
    print("EXPORTED", path)
    return path


def verify_fbx(path, expect):
    """Re-import into a clean scene and check scale/orientation/materials/normals/colours."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, use_custom_normals=True, colors_type="LINEAR")
    rep = {"file": os.path.relpath(path, REPO), "objects": []}
    ok = True
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        st = mesh_stats(ob)
        bb = np.array([ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box])
        st["zmin"] = round(float(bb[:, 2].min()), 3)
        st["custom_normals"] = bool(me.has_custom_normals)
        st["color_attrs"] = [a.name for a in me.color_attributes]
        st["uv_layers"] = [u.name for u in me.uv_layers]
        st["scale"] = [round(x, 4) for x in ob.matrix_world.to_scale()]
        exp = expect.get(ob.name)
        if exp:
            dz = abs(st["size"][2] - exp["size"][2])
            st["height_match"] = dz < 0.02 * max(1, exp["size"][2])
            st["tris_match"] = st["tris"] == exp["tris"]
            ok &= st["height_match"] and st["tris_match"]
        ok &= st["custom_normals"] and bool(st["color_attrs"]) and len(st["materials"]) > 0
        rep["objects"].append(st)
    rep["ok"] = bool(ok)
    return rep


# ============================================================================= preview rendering
def _toon_material(src_name, L):
    """Preview toon: half-lambert from the (custom) shading normal, NO cast shadows, backfaces NOT flipped
    (matches what the Unity foliage shader should do), 3 hard bands, vertex AO (R) multiplied in."""
    info = MAT_REGISTRY[src_name]
    m = bpy.data.materials.new("PV_" + src_name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _img(os.path.join(TEX_DIR, info["albedo"]))
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    if info.get("normal"):
        nm = nt.nodes.new("ShaderNodeTexImage")
        nm.image = _img(os.path.join(TEX_DIR, info["normal"]), noncolor=True)
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 1.0
        nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
        nsock = nmap.outputs["Normal"]
    else:
        f1 = nt.nodes.new("ShaderNodeMath"); f1.operation = "MULTIPLY_ADD"
        f1.inputs[1].default_value = -2.0; f1.inputs[2].default_value = 1.0
        nt.links.new(geo.outputs["Backfacing"], f1.inputs[0])
        sc_ = nt.nodes.new("ShaderNodeVectorMath"); sc_.operation = "SCALE"
        nt.links.new(geo.outputs["Normal"], sc_.inputs[0])
        nt.links.new(f1.outputs[0], sc_.inputs["Scale"])
        nsock = sc_.outputs[0]
    lv = nt.nodes.new("ShaderNodeCombineXYZ")
    for i in range(3):
        lv.inputs[i].default_value = float(L[i])
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    nt.links.new(nsock, dot.inputs[0]); nt.links.new(lv.outputs[0], dot.inputs[1])
    hl = nt.nodes.new("ShaderNodeMath"); hl.operation = "MULTIPLY_ADD"
    hl.inputs[1].default_value = 0.5; hl.inputs[2].default_value = 0.5
    nt.links.new(dot.outputs["Value"], hl.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.26, 0.24, 0.42, 1)   # shadow (indigo tint, linear)
    e = cr.elements.new(0.40); e.color = (0.58, 0.56, 0.70, 1)  # mid band
    cr.elements[1].position = 0.56
    cr.elements[1].color = (1.0, 0.98, 0.95, 1)     # lit
    nt.links.new(hl.outputs[0], ramp.inputs[0])
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "Col"; attr.attribute_type = "GEOMETRY"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    aom = nt.nodes.new("ShaderNodeMapRange")
    aom.inputs["To Min"].default_value = 0.6
    nt.links.new(sep.outputs[0], aom.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], mul.inputs["A"])
    nt.links.new(ramp.outputs["Color"], mul.inputs["B"])
    mul2 = nt.nodes.new("ShaderNodeVectorMath"); mul2.operation = "SCALE"
    nt.links.new(mul.outputs["Result"], mul2.inputs[0])
    nt.links.new(aom.outputs["Result"], mul2.inputs["Scale"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mul2.outputs[0], em.inputs["Color"])
    if info["alpha"]:
        gt = nt.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.5
        nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(gt.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
        m.use_backface_culling = False
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    return m


def _flat_toon(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    nt.links.new(diff.outputs[0], s2r.inputs[0])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].color = tuple(c * 0.45 for c in rgb) + (1,)
    cr.elements[1].position = 0.35
    cr.elements[1].color = tuple(rgb) + (1,)
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def render_preview(objs, name, label="", human=True, az=35.0, el=12.0, res=1024, ground=True, sun_az=-35.0,
                   sun_el=50.0, frame_pad=1.04, extra_objs=(), offsets=None):
    """Toon-ish EEVEE preview (3/4 view, transparent film -> composited on sky by contact sheet tool)."""
    import mathutils
    sc = bpy.context.scene
    if offsets:
        for o in objs:
            if o.name in offsets:
                o.location = mathutils.Vector(offsets[o.name])
        bpy.context.view_layer.update()
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    # sun (direction TO the sun = local +Z)
    sun_d = bpy.data.lights.new("PV_Sun", "SUN")
    sun_d.energy = 3.2
    sun_d.angle = math.radians(3)
    sun = bpy.data.objects.new("PV_Sun", sun_d)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(90 - sun_el), 0, math.radians(sun_az + 180))
    L = np.array(sun.rotation_euler.to_matrix() @ mathutils.Vector((0, 0, 1)))
    # swap to toon materials
    for o in objs:
        for slot in o.material_slots:
            if slot.material and slot.material.name in MAT_REGISTRY:
                slot.material = _toon_material(slot.material.name, L)
    # world
    world = bpy.data.worlds.new("PV_World")
    world.use_nodes = True
    wn = world.node_tree
    bg = wn.nodes.get("Background")
    bg.inputs[0].default_value = (0.75, 0.82, 0.95, 1)
    bg.inputs[1].default_value = 0.45
    sky = wn.nodes.new("ShaderNodeBackground")
    sky.inputs[0].default_value = (0.62, 0.76, 0.92, 1)
    sky.inputs[1].default_value = 1.0
    lp = wn.nodes.new("ShaderNodeLightPath")
    mx = wn.nodes.new("ShaderNodeMixShader")
    wout = wn.nodes.get("World Output")
    wn.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0])
    wn.links.new(bg.outputs[0], mx.inputs[1])
    wn.links.new(sky.outputs[0], mx.inputs[2])
    wn.links.new(mx.outputs[0], wout.inputs[0])
    sc.world = world
    # bounds
    pts = []
    for o in list(objs) + list(extra_objs):
        pts += [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    P = np.array(pts)
    lo, hi = P.min(0), P.max(0)
    height = hi[2] - max(lo[2], 0)
    # scale reference figure (1.75 m)
    frame_lo, frame_hi = lo.copy(), hi.copy()
    if human:
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.2, depth=1.45,
                                            location=(hi[0] + 0.8, lo[1] + (hi[1] - lo[1]) * 0.3, 0.725))
        body = bpy.context.object
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.14,
                                             location=(body.location.x, body.location.y, 1.61))
        head = bpy.context.object
        hm = _flat_toon("PV_Human", (0.95, 0.30, 0.45))
        for h in (body, head):
            h.data.materials.append(hm)
        frame_hi[0] = max(frame_hi[0], body.location.x + 0.25)
        frame_hi[2] = max(frame_hi[2], 1.75)
    if ground:
        rad = max(hi[0] - lo[0], hi[1] - lo[1]) * 1.6 + 2
        bpy.ops.mesh.primitive_circle_add(vertices=48, radius=rad, fill_type="NGON", location=(0, 0, 0))
        gnd = bpy.context.object
        gnd.data.materials.append(_flat_toon("PV_Ground", (0.62, 0.66, 0.52)))
    # camera: fit projected bounds of the model (+ figure)
    frame_lo[2] = max(frame_lo[2], 0.0)
    vs = []
    for o in list(objs) + list(extra_objs):
        arr = np.zeros(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", arr)
        arr = arr.reshape(-1, 3)
        if len(arr) > 6000:
            arr = arr[np.linspace(0, len(arr) - 1, 6000).astype(int)]
        vs.append(np.array([list(o.matrix_world @ mathutils.Vector(v)) for v in arr]))
    hpts = np.zeros((0, 3))
    if human:
        hx, hy = body.location.x, body.location.y
        hpts = np.array([[hx + dx, hy + dy, z] for dx in (-0.25, 0.25) for dy in (-0.25, 0.25) for z in (0, 1.8)])
    corners = np.concatenate(vs + [hpts])
    corners[:, 2] = np.maximum(corners[:, 2], 0)
    frame_lo, frame_hi = corners.min(0), corners.max(0)
    cen = (frame_lo + frame_hi) / 2
    cam_d = bpy.data.cameras.new("PV_Cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("PV_Cam", cam_d)
    sc.collection.objects.link(cam)
    tanh = math.tan(math.atan(18 / 50)) / frame_pad
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
    fwd = -d
    right = unit(np.cross(fwd, Z))
    upv = np.cross(right, fwd)
    dist = float(np.linalg.norm(frame_hi - frame_lo)) * 2 + 1
    for _ in range(60):
        rel = corners - (cen + d * dist)
        zc = rel @ fwd
        if not np.all(zc > 0.1):
            dist *= 1.5
            continue
        u, w_ = (rel @ right) / zc, (rel @ upv) / zc
        need = max(u.max() - u.min(), w_.max() - w_.min()) / 2
        dist *= (need / tanh) ** 0.5
    cam_d.shift_x = float((u.max() + u.min()) / 2 / (2 * math.tan(math.atan(18 / 50))))
    cam_d.shift_y = float((w_.max() + w_.min()) / 2 / (2 * math.tan(math.atan(18 / 50))))
    cam.location = mathutils.Vector(cen + d * dist)
    look = mathutils.Vector(cen) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    cam_d.clip_end = dist * 4
    sc.camera = cam
    os.makedirs(PREV_DIR, exist_ok=True)
    sc.render.filepath = os.path.join(PREV_DIR, name + ".png")
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", sc.render.filepath)


def write_stats(name, objs, extra=None):
    os.makedirs(STATS_DIR, exist_ok=True)
    st = dict(name=name, objects=[mesh_stats(o) for o in objs])
    if extra:
        st.update(extra)
    with open(os.path.join(STATS_DIR, name + ".json"), "w") as f:
        json.dump(st, f, indent=1)
    return st


def finish(name, objs, preview_kw=None, extra=None):
    """Export FBX, write stats, render preview, then verify re-import (resets the scene)."""
    path = export_fbx(objs, name)
    st = write_stats(name, objs, extra)
    expect = {o["name"]: o for o in st["objects"]}
    render_preview(objs, name, **(preview_kw or {}))
    rep = verify_fbx(path, expect)
    st["verify"] = rep
    with open(os.path.join(STATS_DIR, name + ".json"), "w") as f:
        json.dump(st, f, indent=1)
    print("VERIFY", name, "OK" if rep["ok"] else "FAIL", json.dumps(rep["objects"]))
    return st
