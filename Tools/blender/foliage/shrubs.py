"""Shrub builders for INK DRIFT foliage: tiling hedge modules (tsutsuji azalea, boxwood) and round bushes.

Hedge modules are 2 m long along X (x in [-1, 1]) and tile seamlessly: the normal field is a superellipse
cross-section (Y/Z) extruded along X plus bumps that are periodic over 2 m, so neighbouring modules get
identical normals at the joint. An inner low-poly core shell (UV'd to a fully opaque part of the leaf atlas,
darkened via vertex AO) stops see-through.
"""
import math
import os

import bpy
import numpy as np

import atlas_layout
import foliage_lib as fl
from foliage_lib import Z, unit, rand_unit, smoothstep


# ============================================================================= shared helpers
class CardAcc:
    """Accumulates leaf cards; normals/colours are computed once for all vertices."""

    def __init__(self):
        self.V, self.UV, self.F = [], [], []
        self.tip, self.rnd, self.depth = [], [], []
        self.n = 0

    def add(self, V, UV, F, tip, rnd, depth=0.0):
        self.F += [tuple(i + self.n for i in f) for f in F]
        self.V.append(V); self.UV.append(UV)
        self.tip.append(np.asarray(tip, float))
        self.rnd.append(np.full(len(V), rnd))
        self.depth.append(np.full(len(V), depth))
        self.n += len(V)

    def arrays(self):
        return (np.concatenate(self.V), np.concatenate(self.UV), np.concatenate(self.tip),
                np.concatenate(self.rnd), np.concatenate(self.depth))


def cell_uv_in(atlas, cell, px=4):
    """Cell UV rect inset by `px` texels so filtering/mips don't bleed neighbouring cells onto card edges."""
    u0, v0, u1, v1 = atlas_layout.cell_uv(atlas, cell)
    W, H = atlas_layout.ATLASES[atlas]["size"]
    du, dv = px / W, px / H
    return (u0 + du, v0 + dv, u1 - du, v1 - dv)


def card_frame(nrm, rng, roll=None, up_hint=None):
    """right/up vectors for a card facing nrm."""
    nrm = unit(nrm)
    if up_hint is None:
        r = unit(np.cross(nrm, rand_unit(rng)))
    else:
        u = up_hint - nrm * np.dot(up_hint, nrm)
        if np.linalg.norm(u) < 1e-4:
            u = rand_unit(rng)
        u = unit(u)
        r = unit(np.cross(u, nrm))
    u = unit(np.cross(nrm, r))
    return r, u


_OPAQUE_CACHE = {}


def opaque_uv_rect(tex_file, atlas, cell, thresh=0.55, max_bad=0.004):
    """Largest square UV sub-rect of an atlas cell whose alpha is (almost) all >= thresh."""
    key = (tex_file, atlas, cell)
    if key in _OPAQUE_CACHE:
        return _OPAQUE_CACHE[key]
    img = bpy.data.images.load(os.path.join(fl.TEX_DIR, tex_file), check_existing=True)
    W, H = img.size
    px = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(px)
    A = px.reshape(H, W, 4)[..., 3]  # row 0 = bottom (UV space)
    u0, v0, u1, v1 = atlas_layout.cell_uv(atlas, cell)
    x0, x1, y0, y1 = int(u0 * W), int(u1 * W), int(v0 * H), int(v1 * H)
    bad = (A[y0:y1, x0:x1] < thresh).astype(np.float64)
    ii = np.pad(bad.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    h, w = bad.shape
    best = None
    for s in range(int(min(h, w) * 0.7), 8, -4):
        ys = np.arange(0, h - s, 4)
        xs = np.arange(0, w - s, 4)
        Y, X = np.meshgrid(ys, xs, indexing="ij")
        tot = ii[Y + s, X + s] - ii[Y, X + s] - ii[Y + s, X] + ii[Y, X]
        ok = tot <= max_bad * s * s
        if ok.any():
            # prefer the most central acceptable square
            cy, cx = (h - s) / 2, (w - s) / 2
            dd = np.where(ok, (Y - cy) ** 2 + (X - cx) ** 2, np.inf)
            j = np.unravel_index(np.argmin(dd), dd.shape)
            yy, xx = Y[j], X[j]
            best = ((x0 + xx) / W, (y0 + yy) / H, (x0 + xx + s) / W, (y0 + yy + s) / H)
            break
    if best is None:
        cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
        best = (cu - 0.01, cv - 0.01, cu + 0.01, cv + 0.01)
    _OPAQUE_CACHE[key] = best
    return best


def shrub_materials(leaf_mat, leaf_tex, bark=False):
    mats = {leaf_mat: fl.make_material(leaf_mat, leaf_tex, alpha=True, roughness=0.7)}
    if bark:
        mats["M_Bark_Shrub"] = fl.make_material("M_Bark_Shrub", "Bark_Shrub_albedo.png", "Bark_Shrub_normal.png")
    return mats


def grad_num(fn, P, h=0.01):
    G = np.zeros_like(P)
    for i in range(3):
        d = np.zeros(3); d[i] = h
        G[:, i] = (fn(P + d) - fn(P - d)) / (2 * h)
    return G


# ============================================================================= hedge modules
class HedgeShape:
    """Superellipse cross-section in Y/Z, extruded along X; bumps periodic over 2 m in X."""

    def __init__(self, a, zc, b, p, bump=0.05, rng=None):
        self.a, self.zc, self.b, self.p, self.bump = a, zc, b, p, bump
        self.ph = rng.uniform(0, 6.28, 6)

    def g(self, P):
        P = np.atleast_2d(P)
        y = np.abs(P[:, 1]) / self.a
        z = np.abs(P[:, 2] - self.zc) / self.b
        base = (y ** self.p + z ** self.p) ** (1.0 / self.p)
        return base - self.bump * self.bumpval(P)

    def bumpval(self, P):
        P = np.atleast_2d(P)
        x = P[:, 0]
        ph = self.ph
        bump = (np.sin(2 * math.pi * x + 3.1 * P[:, 1] + ph[0]) * np.cos(3 * math.pi * x + 4.3 * P[:, 2] + ph[1])
                + 0.7 * np.sin(math.pi * x + 5.0 * P[:, 2] + ph[2]) * np.sin(5 * math.pi * x + 2.0 * P[:, 1] + ph[3])
                + 0.5 * np.sin(4 * math.pi * x + 6.0 * P[:, 1] + 3.0 * P[:, 2] + ph[4]))
        return bump / 2.2

    def normals(self, P, up=0.12):
        G = grad_num(self.g, P, 0.008)
        return unit(unit(G) + up * Z)

    def profile(self, n=400, zmin=0.0):
        """Arc-length table of the cross-section outline above z=zmin: returns (theta, y, z, s)."""
        p = self.p
        th = np.linspace(-0.5 * math.pi, 1.5 * math.pi, 4000)
        c, s_ = np.cos(th), np.sin(th)
        y = self.a * np.sign(c) * np.abs(c) ** (2 / p)
        z = self.zc + self.b * np.sign(s_) * np.abs(s_) ** (2 / p)
        keep = z >= zmin
        # keep the upper contiguous arc (starts right side, goes over the top to the left side)
        idx = np.where(keep)[0]
        th, y, z = th[idx], y[idx], z[idx]
        seg = np.hypot(np.diff(y), np.diff(z))
        s = np.concatenate([[0], np.cumsum(seg)])
        return th, y, z, s


def build_hedge(name, leaf_mat, leaf_tex, atlas, P, seed):
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    mats = shrub_materials(leaf_mat, leaf_tex)
    geo = fl.Geo(name)
    H = P["height"]
    shape = HedgeShape(P["half_depth"], P["zc"], H - P["zc"], P["p"], bump=P.get("bump", 0.05), rng=rng)
    th, py, pz, ps = shape.profile(zmin=0.0)
    L = ps[-1]
    acc = CardAcc()

    def surf_point(x, s_frac):
        s = s_frac * L
        y = np.interp(s, ps, py)
        z = np.interp(s, ps, pz)
        return np.array([x, y, z])

    def add_layer(n, depth_rng, size_rng, cells, face_out):
        for k in range(n):
            x = rng.uniform(-1.0, 1.0) * P.get("x_extent", 0.93)
            sp = surf_point(x, rng.random())
            if sp[2] < 0.04:
                continue
            nrm0 = shape.normals(sp[None], up=0.0)[0]
            d = rng.uniform(*depth_rng)
            lump = float(shape.bumpval(sp[None])[0]) * shape.bump * shape.a * P.get("lump_geo", 1.0)
            c = sp + nrm0 * (d + lump)
            c[2] = max(c[2], 0.06)
            nc = unit(nrm0 * face_out + rand_unit(rng) * (1 - face_out + 0.3))
            s = rng.uniform(*size_rng)
            r, u = card_frame(nc, rng)
            cell = cells[rng.integers(len(cells))]
            V, UV, F, tip = fl.card_quad(c, r, u, s, s, "center", cell_uv_in(atlas, cell))
            acc.add(V, UV, F, tip, rng.random(), d)

    for lay in P["layers"]:
        add_layer(*lay)
    # end caps: a few cards just outside the core ends (hidden by the neighbour when tiled)
    for side in (-1, 1):
        for k in range(P.get("end_cards", 12)):
            s_frac = rng.random()
            sp = surf_point(side * 1.0, s_frac)
            # pull toward the inside of the cross-section
            yz = np.array([0.0, sp[1] * rng.uniform(0.1, 0.95), max(0.1, P["zc"] + (sp[2] - P["zc"]) * rng.uniform(0.1, 0.95))])
            c = np.array([side * rng.uniform(0.94, 1.0), yz[1], yz[2]])
            nc = unit(np.array([side * 1.0, 0, 0]) + rand_unit(rng) * 0.35)
            s = rng.uniform(*P["layers"][0][2])
            r, u = card_frame(nc, rng)
            cells = P["layers"][0][3]
            cell = cells[rng.integers(len(cells))]
            V, UV, F, tip = fl.card_quad(c, r, u, s, s, "center", cell_uv_in(atlas, cell))
            acc.add(V, UV, F, tip, rng.random(), -0.05)

    V, UV, tip, rnd, depth = acc.arrays()
    N = shape.normals(V, up=P.get("n_up", 0.12))
    ao = (0.55 + 0.45 * smoothstep(-0.16, 0.02, depth)) * (0.62 + 0.38 * smoothstep(0.0, H * 0.6, V[:, 2]))
    wind = np.clip(0.05 + 0.18 * smoothstep(0, H, V[:, 2]) + 0.08 * tip * smoothstep(-0.1, 0.03, depth), 0, 0.32)
    C = np.stack([np.clip(ao, 0.25, 1), wind, rnd, np.ones(len(V))], 1)
    geo.add(V, N, UV, C, acc.F, leaf_mat)
    ncards = len(acc.V)

    # ---- core shell: inset cross-section extruded along X, UV'd into an opaque square of a leaf cell
    inset = P.get("core_inset", 0.1)
    ring_s = np.linspace(0, L, 13)
    ry = np.interp(ring_s, ps, py)
    rz = np.interp(ring_s, ps, pz)
    nr = shape.normals(np.stack([np.zeros_like(ry), ry, rz], 1), up=0.0)
    ry2 = ry - nr[:, 1] * inset
    rz2 = np.maximum(rz - nr[:, 2] * inset, 0.0)
    rz2[0] = rz2[-1] = 0.0
    ou = opaque_uv_rect(leaf_tex, atlas, P.get("core_cell", "round_a"))
    xe = P.get("core_end", 0.92)
    xs = np.array([-xe, 0.0, xe])
    CV, CUV, CF = [], [], []
    m = len(ring_s)
    for i, x in enumerate(xs):
        tap = 0.86 if abs(x) > 0.5 else 1.0  # slight taper so the end caps hide behind end cards
        for j in range(m):
            CV.append([x, ry2[j] * tap, rz2[j] * (0.5 + 0.5 * tap) if j not in (0, m - 1) else 0.0])
            CUV.append([ou[0] + (ou[2] - ou[0]) * (x + 1) / 2, ou[1] + (ou[3] - ou[1]) * j / (m - 1)])
    for i in range(len(xs) - 1):
        for j in range(m - 1):
            a = i * m + j
            b = (i + 1) * m + j
            CF.append((a, a + 1, b + 1, b))
    # orientation check: first quad normal should point outward
    CV = np.array(CV)
    q = CF[m // 2]
    fn = np.cross(CV[q[1]] - CV[q[0]], CV[q[3]] - CV[q[0]])
    if np.dot(fn, CV[q[0]] - np.array([CV[q[0]][0], 0, P["zc"]])) < 0:
        CF = [tuple(reversed(f)) for f in CF]
    # end caps (fan, faces outward along +-X)
    base = len(CV)
    capV, capUV = [], []
    for side, ring_i in ((-1, 0), (1, len(xs) - 1)):
        cidx = base + len(capV)
        capV.append([side * xe, 0.0, P["zc"] * 0.8])
        capUV.append([(ou[0] + ou[2]) / 2, (ou[1] + ou[3]) / 2])
        for j in range(m - 1):
            a, b = ring_i * m + j, ring_i * m + j + 1
            f = (a, b, cidx) if side > 0 else (b, a, cidx)
            fnn = np.cross(CV[f[1]] - CV[f[0]], (np.array(capV[-1]) if f[2] >= base else CV[f[2]]) - CV[f[0]])
            if fnn[0] * side < 0:
                f = (f[1], f[0], f[2])
            CF.append(f)
    CV = np.vstack([CV, np.array(capV)])
    CUV = np.vstack([np.array(CUV), np.array(capUV)])
    CN = shape.normals(np.where(CV[:, 2:3] < 0.02, CV + np.array([0, 0, 0.05]), CV), up=0.1)
    cao = 0.3 + 0.2 * smoothstep(0, H, CV[:, 2])
    CC = np.stack([cao, np.full(len(CV), 0.05), np.full(len(CV), 0.5), np.ones(len(CV))], 1)
    geo.add(CV, CN, CUV, CC, CF, leaf_mat)

    ob = geo.build(mats)
    print(f"{name}: cards={ncards} tris={geo.tris()}")
    # preview: show the module tiled x3 (linked duplicates) to check the joints
    copies = []
    for dx in (-2.0, 2.0):
        c = ob.copy()
        c.location.x = dx
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    return [ob], dict(n_cards=ncards, preview_kw=dict(extra_objs=copies, az=28, el=16),
                      tiling="2 m module along X (x in [-1,1]); place modules every 2 m")


def hedge_azalea():
    cells_out = ("round_b", "round_a")
    cells_in = ("spray_a", "spray_b", "round_a")
    P = dict(height=0.78, half_depth=0.43, zc=0.3, p=3.0, bump=0.2, lump_geo=0.8,
             layers=[(560, (-0.05, 0.03), (0.28, 0.4), cells_out, 0.8),
                     (260, (-0.16, -0.06), (0.32, 0.44), cells_in, 0.7)],
             end_cards=34, core_inset=0.13, core_cell="spray_b", n_up=0.12)
    return build_hedge("Hedge_Azalea", "M_Leaves_Azalea", "Leaves_Azalea_albedo.png", "Leaves_Azalea", P, 301)


def hedge_boxwood():
    cells = ("round_a", "round_b", "spray_a", "spray_b")
    P = dict(height=0.9, half_depth=0.4, zc=0.34, p=4.5, bump=0.1, lump_geo=0.5,
             layers=[(580, (-0.04, 0.025), (0.26, 0.36), cells, 0.85),
                     (240, (-0.14, -0.05), (0.3, 0.4), cells, 0.7)],
             end_cards=34, core_inset=0.11, core_cell="round_a", n_up=0.1)
    return build_hedge("Hedge_Boxwood", "M_Leaves_Boxwood", "Leaves_Boxwood_albedo.png", "Leaves_Boxwood", P, 302)


# ============================================================================= round bushes
def low_ellipsoid(center, radii, segs=8, rings=5, zfloor=0.12):
    V, F = [], []
    V.append([center[0], center[1], center[2] + radii[2]])
    for i in range(1, rings):
        phi = math.pi * i / rings
        for j in range(segs):
            th = 2 * math.pi * j / segs
            V.append([center[0] + radii[0] * math.sin(phi) * math.cos(th),
                      center[1] + radii[1] * math.sin(phi) * math.sin(th),
                      max(zfloor, center[2] + radii[2] * math.cos(phi))])
    V.append([center[0], center[1], max(zfloor, center[2] - radii[2])])
    for j in range(segs):
        F.append((0, 1 + j, 1 + (j + 1) % segs))
    for i in range(rings - 2):
        for j in range(segs):
            a = 1 + i * segs + j
            b = 1 + i * segs + (j + 1) % segs
            F.append((a, a + segs, b + segs, b))
    last = len(V) - 1
    for j in range(segs):
        a = 1 + (rings - 2) * segs + j
        b = 1 + (rings - 2) * segs + (j + 1) % segs
        F.append((a, last, b))
    return np.array(V, float), F


def build_bush(name, leaf_mat, leaf_tex, atlas, P, seed):
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    mats = shrub_materials(leaf_mat, leaf_tex, bark=True)
    geo = fl.Geo(name)
    cents = np.array(P["masses_c"], float)
    radii = np.array(P["masses_r"], float)
    field = fl.BlobField(cents, radii, k=P.get("sharp", 2.0))
    lo = (cents - radii).min(0); hi = (cents + radii).max(0)
    gc = (lo + hi) / 2
    gr = (hi - lo) / 2
    H = hi[2]
    zcut = P.get("zcut", 0.2)
    cells = P["cells"]

    # ---- stems
    for k in range(P.get("stems", 5)):
        a = 2 * math.pi * k / P.get("stems", 5) + rng.normal(0, 0.3)
        p0 = np.array([math.cos(a) * 0.08, math.sin(a) * 0.08, 0.0])
        d0 = unit(Z + np.array([math.cos(a), math.sin(a), 0]) * rng.uniform(0.35, 0.7))
        Ls = rng.uniform(0.5, 0.8) * H
        pts, rad = fl.grow(p0, d0, Ls, P.get("stem_r", 0.028), 0.008, rng, seg=Ls / 4, wobble=0.25)
        nn = len(pts)
        col = np.stack([0.4 + 0.3 * np.linspace(0, 1, nn), 0.35 * np.linspace(0, 1, nn) ** 1.5,
                        np.full(nn, rng.random()), np.ones(nn)], 1)
        fl.tube(geo, pts, rad, 5, "M_Bark_Shrub", u_rep=1, v_len=1.0, colors=col, cap=True, base_extend=0.06)
    ntris_stems = geo.tris()

    # ---- cards on the blob masses
    acc = CardAcc()
    tries = 0
    target = P["n_cards"]
    while len(acc.V) < target and tries < target * 20:
        tries += 1
        i = rng.integers(len(cents))
        dirv = rand_unit(rng)
        dirv[2] = abs(dirv[2]) * 0.9 + dirv[2] * 0.1 if rng.random() < 0.6 else dirv[2]
        dirv = unit(dirv)
        depth = rng.uniform(*P["depth"])
        p = cents[i] + dirv * radii[i] * (1 + depth / np.mean(radii[i]))
        if p[2] < zcut:
            continue
        # skip points buried deep inside other masses
        q = np.sqrt((((p - cents) / radii) ** 2).sum(1))
        q[i] = 9
        if q.min() < 0.7:
            continue
        nrm0 = field.normals(p[None], gc, gr, w_local=0.85, up=0.0)[0]
        nc = unit(nrm0 * P.get("face_out", 0.8) + rand_unit(rng) * 0.45)
        s = rng.uniform(*P["size"])
        r, u = card_frame(nc, rng)
        cell = cells[rng.integers(len(cells))]
        V, UV, F, tip = fl.card_quad(p, r, u, s, s, "center", cell_uv_in(atlas, cell))
        acc.add(V, UV, F, tip, rng.random(), depth)
    V, UV, tip, rnd, depth = acc.arrays()
    N = field.normals(V, gc, gr, w_local=P.get("w_local", 0.8), up=P.get("n_up", 0.12))
    _, _, inside = field.eval(V)
    ao = (1 - 0.5 * smoothstep(0.0, 0.45, inside)) * (0.6 + 0.4 * smoothstep(zcut * 0.5, H * 0.8, V[:, 2]))
    wind = np.clip(0.25 + 0.45 * smoothstep(0, H, V[:, 2]) + 0.25 * tip, 0, 1)
    C = np.stack([np.clip(ao, 0.25, 1), wind, rnd, np.ones(len(V))], 1)
    geo.add(V, N, UV, C, acc.F, leaf_mat)
    ncards = len(acc.V)

    # ---- core ellipsoids (opaque leaf region, dark AO)
    ou = opaque_uv_rect(leaf_tex, atlas, P.get("core_cell", cells[0]))
    for c, r in zip(cents, radii):
        CV, CF = low_ellipsoid(c, r * P.get("core_scale", 0.72), zfloor=zcut + 0.05)
        rel = unit(CV - c)
        cu = ou[0] + (ou[2] - ou[0]) * (0.5 + 0.5 * rel[:, 0])
        cv_ = ou[1] + (ou[3] - ou[1]) * (0.5 + 0.5 * rel[:, 2])
        CUV = np.stack([cu, cv_], 1)
        CN = field.normals(CV, gc, gr, w_local=0.8, up=0.1)
        cao = 0.3 + 0.2 * smoothstep(0, H, CV[:, 2])
        CC = np.stack([cao, 0.2 + 0.3 * smoothstep(0, H, CV[:, 2]), np.full(len(CV), 0.5), np.ones(len(CV))], 1)
        geo.add(CV, CN, CUV, CC, CF, leaf_mat)
    ob = geo.build(mats)
    print(f"{name}: cards={ncards} stems_tris={ntris_stems} tris={geo.tris()}")
    return [ob], dict(n_cards=ncards)


def bush_round_a():
    # dark glossy (camellia / Japanese holly), ~1.6 m tall, ~1.9 m wide dome
    P = dict(masses_c=[[0, 0, 0.7], [0.5, 0.3, 0.95], [-0.5, 0.35, 0.9], [0.1, -0.55, 0.88], [-0.2, -0.1, 1.25],
                       [0.35, -0.2, 1.2], [-0.55, -0.35, 0.72], [0.62, -0.25, 0.6]],
             masses_r=[[0.75, 0.72, 0.55], [0.5, 0.5, 0.46], [0.52, 0.48, 0.46], [0.5, 0.48, 0.44],
                       [0.48, 0.48, 0.38], [0.44, 0.44, 0.36], [0.42, 0.42, 0.38], [0.4, 0.4, 0.36]],
             n_cards=1050, size=(0.34, 0.48), depth=(-0.14, 0.04), cells=("round_a", "round_b"),
             zcut=0.22, stems=5, stem_r=0.032, face_out=0.8, w_local=0.92, sharp=3.0)
    return build_bush("Bush_Round_A", "M_Leaves_Bush", "Leaves_Bush_albedo.png", "Leaves_Bush", P, 311)


def bush_round_b():
    # lighter deciduous shrub, ~1.1 m, irregular lobes
    P = dict(masses_c=[[0.05, 0.0, 0.48], [0.45, 0.22, 0.6], [-0.42, 0.15, 0.55], [0.05, -0.4, 0.55],
                       [-0.15, 0.05, 0.82], [0.3, -0.12, 0.8]],
             masses_r=[[0.5, 0.48, 0.38], [0.36, 0.34, 0.32], [0.38, 0.34, 0.3], [0.34, 0.32, 0.3],
                       [0.32, 0.32, 0.26], [0.3, 0.3, 0.24]],
             n_cards=900, size=(0.26, 0.38), depth=(-0.1, 0.04), cells=("spray_a", "spray_b"),
             zcut=0.15, stems=4, stem_r=0.022, face_out=0.75, w_local=0.92, sharp=3.0)
    return build_bush("Bush_Round_B", "M_Leaves_Bush", "Leaves_Bush_albedo.png", "Leaves_Bush", P, 312)


BUILDERS = {
    "Hedge_Azalea": hedge_azalea,
    "Hedge_Boxwood": hedge_boxwood,
    "Bush_Round_A": bush_round_a,
    "Bush_Round_B": bush_round_b,
}
