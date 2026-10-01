"""Tree species builders for INK DRIFT foliage (sakura, keyaki, ginkgo, momiji, sugi, kuromatsu, bamboo)."""
import math

import numpy as np

import foliage_lib as fl
from foliage_lib import Z, unit, rand_unit, smoothstep


# ============================================================================= generic broadleaf
def broadleaf(name, species, P, seed):
    """Generic decurrent/excurrent broadleaf tree from a parameter dict. Returns list of objects."""
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    mats = fl.std_materials(species)
    bark, leaves = f"M_Bark_{species}", f"M_Leaves_{species}"
    geo = fl.Geo(name)
    H, W = P["height"], P["crown_w"]
    if P.get("envelope") is not None:
        env = P["envelope"]
    else:
        env = fl.Ellipsoid(P.get("env_center", (0, 0, H * 0.6)), P.get("env_radii", (W / 2, W / 2, H * 0.42)))

    # ---- trunk
    lean = unit(np.array([rng.normal(0, 1), rng.normal(0, 1), 0.0]))
    tr = P["trunk"]
    d0 = unit(Z + lean * tr.get("lean", 0.1))
    tpts, trad = fl.grow([0, 0, 0], d0, tr["length"], tr["r0"], tr["r1"], rng, seg=tr.get("seg", 0.4),
                         wobble=tr.get("wobble", 0.12), trop=Z, trop_k=tr.get("trop_k", 0.05), rpow=tr.get("rpow", 0.7))
    trunk = fl.Branch(tpts, trad, 0, rnd=rng.random())
    branches = [trunk]

    # ---- levels
    parents = [trunk]
    for li, L in enumerate(P["levels"], start=1):
        new = []
        for par in parents:
            if L.get("only_level") is not None and par.level != L["only_level"]:
                continue
            cnt = L["count"] if not L.get("per_m") else max(1, int(round(par.length * L["per_m"])))
            cnt = max(1, int(round(cnt * rng.uniform(0.85, 1.15))))
            ln = L["length"]

            def length_fn(t, parent, rng, ln=ln, L=L):
                base = parent.length * ln[0] if L.get("relative", True) else ln[0]
                shape = L.get("shape", lambda t: 1.0)(t)
                return base * shape * rng.uniform(1 - ln[1], 1 + ln[1])
            kids = fl.spawn(par, cnt, L["t"], L["down"], rng, length_fn, L["r_ratio"], L.get("tip_r", 0.006), li,
                            envelope=env if L.get("envelope", True) else None, golden=L.get("golden", True),
                            up_bias=L.get("up_bias", 0.0), horiz_bias=L.get("horiz_bias", 0.0),
                            seg=L.get("seg", 0.35), wobble=L.get("wobble", 0.2), trop=L.get("trop", Z),
                            trop_k=L.get("trop_k", 0.0), rpow=L.get("rpow", 0.9), min_dz=L.get("min_dz"))
            new += kids
        branches += new
        parents = new if not P.get("cumulative_parents") else parents + new

    # ---- clumps
    cp = P["clumps"]
    max_s = fl.max_path(branches)
    wind_fn = fl.path_wind(max_s, trunk_free=tr["length"] * 0.4)
    clumps = []
    for b in branches:
        if b.level in cp["levels"]:
            clumps += fl.clumps_along(b, cp["spacing"], cp["radius"], cp["n_cards"], cp["size"], rng,
                                      t_from=cp.get("t_from", 0.4), wind_fn=wind_fn, jitter=cp.get("jitter", 0.3),
                                      out_up=cp.get("out_up", 0.3), zr=cp.get("zr", 0.8), lift=cp.get("lift", 0.25))
    # cull clumps far below crown / outside envelope (keeps silhouette clean)
    zmin = cp.get("zmin", 0)
    clumps = [c for c in clumps if c.center[2] > zmin and env(c.center) < cp.get("env_max", 1.15)]

    # ---- canopy field
    k_m = P.get("k_masses") or max(6, len(clumps) // P.get("clumps_per_mass", 14))
    field = fl.masses_from_clumps(clumps, k_m, rng, pad=P.get("mass_pad", 1.0),
                                  min_r=P.get("mass_min_r", 0.8), z_squash=P.get("mass_z", 1.0),
                                  sharp=P.get("mass_sharp", 2.0))
    X = np.array([c.center for c in clumps])
    gc = (X.max(0) + X.min(0)) / 2
    gr = (X.max(0) - X.min(0)) / 2 + cp["radius"]
    gr[0] = gr[1] = max(gr[0], gr[1])

    # ---- branch mesh
    def ao_fn(pts):
        z = pts[:, 2]
        a = 0.4 + 0.6 * smoothstep(0.0, P.get("ao_base_h", 1.8), z)
        gd = np.sqrt(np.sum(((pts - gc) / gr) ** 2, 1))
        a *= 1 - 0.3 * (1 - smoothstep(0.5, 1.0, gd))
        return np.clip(a, 0.25, 1)
    fl.mesh_branches(geo, branches, bark, P["sides"], rng, v_len=P.get("bark_v", 0.8), ao_fn=ao_fn,
                     wind_fn=wind_fn, flare=P.get("flare", (0.35, 0.6, 4)), min_radius=P.get("min_radius", 0.006),
                     skip_level=P.get("skip_level", 99), u_rep_by_level=P.get("u_rep"))
    ntris_branch = geo.tris()
    fl.scatter_cards(geo, clumps, f"Leaves_{species}" if not P.get("atlas") else P["atlas"], leaves, rng, field, gc,
                     gr, spray_frac=P.get("spray_frac", 0.3), w_local=P.get("w_local", 0.7), up=P.get("n_up", 0.15),
                     droop=P.get("droop", 0.25), face_out=P.get("face_out", 0.8), shell=P.get("shell", (0.35, 1.0)),
                     spray_len=P.get("spray_len", 1.15))
    ob = geo.build(mats)
    print(f"{name}: branches={len(branches)} clumps={len(clumps)} tris branch={ntris_branch} total={geo.tris()}")
    return [ob], dict(n_branches=len(branches), n_clumps=len(clumps), tris_branches=ntris_branch)


# ============================================================================= sakura
def sakura(variant):
    v = "ABC".index(variant)
    rng = np.random.default_rng(100 + v)
    H = [7.2, 7.8, 6.2][v]
    W = [11.0, 12.0, 9.0][v]
    P = dict(
        height=H, crown_w=W,
        env_center=(0, 0, H * 0.56), env_radii=(W / 2, W / 2, H * 0.46),
        trunk=dict(length=[2.4, 3.0, 2.0][v], r0=[0.25, 0.29, 0.21][v], r1=0.17, lean=0.2, wobble=0.2, trop_k=0.02),
        levels=[
            # scaffold limbs: rise ~35deg off horizontal then arch outward (umbrella crown)
            dict(count=[5, 5, 4][v], t=[(0.6, 1.0), (0.75, 1.0), (0.6, 1.0)][v], down=(55, 8), length=(1.0, 0.12),
                 relative=False,
                 r_ratio=0.8, tip_r=0.03, wobble=0.3, trop=-Z, trop_k=0.07, seg=0.45, min_dz=-0.05,
                 shape=lambda t, H=H: H * 0.8),
            dict(per_m=1.7, count=0, t=(0.2, 1.0), down=(50, 12), length=(0.45, 0.25), r_ratio=0.6, tip_r=0.012,
                 wobble=0.4, trop=Z, trop_k=0.1, seg=0.55, up_bias=0.1, shape=lambda t: 1.0 - 0.4 * t, min_dz=-0.2),
            dict(per_m=[1.8, 1.4, 1.8][v], count=0, t=(0.3, 1.0), down=(42, 12), length=(0.45, 0.25), r_ratio=0.6,
                 tip_r=0.006,
                 wobble=0.5, trop=Z, trop_k=0.08, seg=0.6, up_bias=0.15, shape=lambda t: 1.0 - 0.5 * t),
        ],
        clumps=dict(levels=(2, 3), spacing=0.6, radius=0.55, n_cards=[7, 9, 7][v], size=1.0, t_from=0.45, jitter=0.35,
                    out_up=0.6, zmin=[2.9, 3.6, 2.5][v]),
        sides=(12, 7, 5, 3), clumps_per_mass=[12, 18, 12][v], mass_pad=0.9, mass_min_r=0.9, mass_sharp=2.2, min_radius=0.01,
        flare=(0.45, 0.5, 4), spray_frac=0.18, spray_len=0.85, w_local=0.85, n_up=0.12, droop=0.1, ao_base_h=2.0,
        face_out=0.9,
    )
    return broadleaf(f"Sakura_{variant}", "Sakura", P, [100, 207, 102][v])


# ============================================================================= keyaki (zelkova)
def keyaki(variant):
    v = "ABC".index(variant)
    H = [10.5, 12.0, 8.5][v]
    W = [9.5, 10.5, 8.0][v]
    P = dict(
        height=H, crown_w=W,
        env_center=(0, 0, H * 0.64), env_radii=(W / 2, W / 2, H * 0.37),
        trunk=dict(length=[2.6, 3.0, 2.2][v], r0=[0.32, 0.36, 0.27][v], r1=0.24, lean=0.02, wobble=0.04, trop_k=0.1),
        levels=[
            # many ascending scaffold limbs -> vase / broom
            dict(count=[7, 8, 6][v], t=(0.8, 1.0), down=(33, 6), length=(1.0, 0.1), relative=False,
                 r_ratio=0.7, tip_r=0.03, wobble=0.12, trop=Z, trop_k=0.02, seg=0.6, golden=True,
                 shape=lambda t, H=H: H * 0.58),
            dict(per_m=1.5, count=0, t=(0.35, 1.0), down=(35, 10), length=(0.42, 0.25), r_ratio=0.55, tip_r=0.01,
                 wobble=0.3, trop=Z, trop_k=0.08, seg=0.6, up_bias=0.2, shape=lambda t: 1.0 - 0.4 * t),
            dict(per_m=[1.8, 1.5, 1.8][v], count=0, t=(0.3, 1.0), down=(40, 12), length=(0.5, 0.25), r_ratio=0.6,
                 tip_r=0.005, wobble=0.4, trop=Z, trop_k=0.05, seg=0.6, up_bias=0.1, shape=lambda t: 1.0 - 0.5 * t),
        ],
        clumps=dict(levels=(2, 3), spacing=0.65, radius=0.6, n_cards=[6, 5, 6][v], size=1.05, t_from=0.45,
                    jitter=0.35, out_up=0.5, zmin=H * 0.5),
        sides=(12, 7, 5, 3), clumps_per_mass=14, mass_pad=0.9, mass_min_r=1.0, mass_sharp=2.2, min_radius=0.012,
        flare=(0.35, 0.6, 5), spray_frac=0.2, spray_len=0.9, w_local=0.85, n_up=0.12, droop=0.15, ao_base_h=2.0,
        face_out=0.92,
    )
    return broadleaf(f"Keyaki_{variant}", "Keyaki", P, [311, 312, 313][v])


# ============================================================================= ginkgo (icho)
def ginkgo(variant):
    v = "AB".index(variant)
    H = [12.0, 9.5][v]
    W = [6.6, 6.2][v]
    z0 = [2.4, 2.0][v]
    P = dict(
        height=H, crown_w=W,
        envelope=fl.Cone(z0 - 0.6, H, W / 2, power=[1.0, 0.75][v], zbot=z0 - 0.8),
        trunk=dict(length=H * 0.95, r0=[0.3, 0.26][v], r1=0.03, lean=0.0, wobble=0.03, trop_k=0.3, seg=0.6,
                   rpow=0.8),
        levels=[
            dict(count=[32, 26][v], t=(z0 / H, 0.97), down=(64, 6), length=(1.0, 0.1), relative=False,
                 r_ratio=0.42, tip_r=0.012, wobble=0.1, trop=Z, trop_k=0.1, seg=0.5,
                 shape=lambda t, W=W: W * 0.6 * (1 - t) ** 0.9 + 0.45),
            dict(per_m=2.2, count=0, t=(0.2, 1.0), down=(50, 10), length=(0.35, 0.25), r_ratio=0.6, tip_r=0.005,
                 wobble=0.25, trop=Z, trop_k=0.1, seg=0.6, up_bias=0.1, shape=lambda t: 1.0 - 0.5 * t),
        ],
        clumps=dict(levels=(1, 2), spacing=0.5, radius=0.5, n_cards=8, size=0.78, t_from=0.25, jitter=0.25,
                    out_up=0.4, zmin=z0 - 0.1, env_max=1.15),
        sides=(12, 6, 4), clumps_per_mass=11, mass_pad=0.9, mass_min_r=1.0, mass_sharp=2.2, min_radius=0.01,
        flare=(0.3, 0.5, 5), spray_frac=0.2, spray_len=0.9, w_local=0.85, n_up=0.1, droop=0.1, ao_base_h=2.0,
        face_out=0.92,
    )
    return broadleaf(f"Ginkgo_{variant}", "Ginkgo", P, [411, 412][v])


# ============================================================================= momiji (japanese maple)
def momiji(variant):
    v = "ABC".index(variant)
    H = [6.0, 7.0, 5.2][v]
    W = [8.0, 9.0, 6.8][v]
    P = dict(
        height=H, crown_w=W,
        env_center=(0, 0, H * 0.56), env_radii=(W / 2, W / 2, H * 0.46),
        trunk=dict(length=[1.5, 1.9, 1.1][v], r0=[0.17, 0.2, 0.13][v], r1=0.12, lean=0.25, wobble=0.25, trop_k=0.0),
        levels=[
            dict(count=[5, 6, 6][v], t=(0.5, 1.0), down=(48, 10), length=(1.0, 0.15), relative=False,
                 r_ratio=0.75, tip_r=0.02, wobble=0.35, trop=-Z, trop_k=0.04, seg=0.4, min_dz=0.1,
                 shape=lambda t, W=W: W * 0.62),
            # tiered horizontal sprays
            dict(per_m=[1.3, 1.3, 1.7][v], count=0, t=(0.25, 1.0), down=(62, 10), length=(0.5, 0.25), r_ratio=0.55, tip_r=0.008,
                 wobble=0.3, trop=Z, trop_k=0.0, seg=0.5, horiz_bias=0.75, min_dz=-0.2,
                 shape=lambda t: 1.0 - 0.45 * t),
            dict(per_m=1.6, count=0, t=(0.35, 1.0), down=(55, 12), length=(0.5, 0.25), r_ratio=0.6, tip_r=0.004,
                 wobble=0.35, trop=Z, trop_k=0.0, seg=0.6, horiz_bias=0.7, min_dz=-0.25,
                 shape=lambda t: 1.0 - 0.5 * t),
        ],
        clumps=dict(levels=[(3,), (3,), (2, 3)][v], spacing=0.5, radius=0.62, n_cards=9, size=1.0, t_from=0.35,
                    jitter=0.2,
                    out_up=0.05, zr=0.42, lift=0.2, zmin=[1.7, 2.1, 1.3][v]),
        sides=(10, 6, 4, 3), clumps_per_mass=9, mass_pad=0.85, mass_min_r=0.8, mass_sharp=2.4, mass_z=0.45,
        min_radius=0.008, flare=(0.3, 0.4, 4), spray_frac=0.3, spray_len=0.9, w_local=0.88, n_up=0.18,
        droop=0.35, ao_base_h=1.5, face_out=0.9,
    )
    return broadleaf(f"Momiji_{variant}", "Momiji", P, [511, 512, 527][v])


# ============================================================================= sugi (japanese cedar)
def _sugi_geo(name, H, R0, crown_base, rng, lod, atlas="Leaves_Sugi"):
    """Sugi: straight trunk + whorls of drooping crossed spray cards forming a narrow cone."""
    import atlas_layout
    geo = fl.Geo(name)
    bark, leaves = "M_Bark_Sugi", "M_Leaves_Sugi"
    r0 = 0.012 * H + 0.08
    # ---- trunk
    nseg = 9 if lod == 0 else 3
    zs = np.linspace(0, H * 0.985, nseg + 1)
    sway = rng.normal(0, 0.04, 2)
    pts = np.stack([sway[0] * (zs / H) ** 2, sway[1] * (zs / H) ** 2, zs], 1)
    radii = r0 * (1 - zs / H) ** 0.9 + 0.015
    ao = 0.4 + 0.6 * smoothstep(0, 2.5, zs)
    ao *= 1 - 0.35 * smoothstep(crown_base - 1, crown_base + 2, zs)
    wind = 0.6 * (zs / H) ** 2
    col = np.stack([ao, wind, np.full(len(zs), 0.5), np.ones(len(zs))], 1)
    fl.tube(geo, pts, radii, 8 if lod == 0 else 5, bark, u_rep=3 if lod == 0 else 2, v_len=1.6, colors=col,
            cap=True, flare=(0.35, 0.7, 5) if lod == 0 else None, rng=rng, base_extend=0.2)

    def cone_r(z):
        t = np.clip((z - crown_base) / (H - crown_base), 0, 1)
        # slightly convex cone, a bit narrower at the very bottom
        return R0 * (1 - t) ** 0.85 * (0.75 + 0.25 * smoothstep(0.0, 0.12, t)) + 0.15

    # ---- branches (cards)
    V, UV, F, C, tipn = [], [], [], [], []
    nb = 0
    whorl_dz = 0.2 if lod == 0 else 0.5
    per_whorl = 6
    z = crown_base
    phase = rng.uniform(0, 6.28)
    cells = atlas_layout.cells(atlas)
    while z < H - 0.6:
        for k in range(per_whorl):
            phase += 2.39996 + rng.normal(0, 0.25)
            zz = z + rng.uniform(-0.15, 0.15) * whorl_dz
            t_c = (zz - crown_base) / (H - crown_base)
            L = cone_r(zz) * rng.uniform(0.85, 1.15) * (1.0 if lod == 0 else 1.1)
            if L < 0.35:
                continue
            u = np.array([math.cos(phase), math.sin(phase), 0.0])
            beta = math.radians(-rng.uniform(8, 22) * (1.2 - 0.6 * t_c))
            d = unit(u * math.cos(beta) + Z * math.sin(beta))
            side = unit(np.cross(Z, u))
            curv = rng.uniform(0.12, 0.22)
            base = np.array([0.0, 0.0, zz]) + u * 0.05
            cards = [(rng.uniform(-0.6, 0.6), 1.0), (math.pi / 2 + rng.uniform(-0.3, 0.3), 0.7)]
            for roll, wscale in cards:
                wv = unit(side * math.cos(roll) + np.cross(d, side) * math.sin(roll))
                h = L * 0.5 * wscale * (1.0 if lod == 0 else 1.15)
                cell = cells[rng.integers(len(cells))]
                u0, v0, u1, v1 = atlas_layout.cell_uv(atlas, cell)
                ts = (0.0, 0.5, 1.0) if lod == 0 else (0.0, 1.0)
                b0 = len(V)
                for t in ts:
                    c = base + d * L * t + Z * L * curv * (t * t - t)
                    for e in (-0.5, 0.5):
                        V.append(c + wv * h * e)
                        UV.append([u0 + (u1 - u0) * t, v0 + (v1 - v0) * (e + 0.5)])
                        tipn.append(t)
                for i in range(len(ts) - 1):
                    a_ = b0 + i * 2
                    F.append((a_, a_ + 2, a_ + 3, a_ + 1))
                nb += 1
        z += whorl_dz
    # leader tip: vertical sprays
    for k in range(3 if lod == 0 else 2):
        ang = k * 2 * math.pi / 3 + phase
        u = np.array([math.cos(ang), math.sin(ang), 0.0])
        L = 1.4
        base = np.array([0, 0, H - 1.5])
        d = unit(Z + u * 0.12)
        wv = unit(np.cross(Z, u))
        cell = cells[k % len(cells)]
        u0, v0, u1, v1 = atlas_layout.cell_uv(atlas, cell)
        b0 = len(V)
        for t in (0.0, 1.0):
            c = base + d * L * t
            for e in (-0.5, 0.5):
                V.append(c + wv * 0.45 * e)
                UV.append([u0 + (u1 - u0) * t, v0 + (v1 - v0) * (e + 0.5)])
                tipn.append(t)
        F.append((b0, b0 + 2, b0 + 3, b0 + 1))
    V = np.array(V); UV = np.array(UV); tipn = np.array(tipn)
    # ---- normals: tier blobs + cone normal
    tiers = np.arange(crown_base + 0.6, H - 0.5, 1.7)
    field = fl.BlobField([[0, 0, tz] for tz in tiers], [[cone_r(tz) * 1.05, cone_r(tz) * 1.05, 1.15] for tz in tiers],
                         k=2.0)
    Fv, G, inside = field.eval(V)
    nl = G / (np.linalg.norm(G, axis=1) + 0.15 * np.median(np.linalg.norm(G, axis=1)))[:, None]
    radial = V * np.array([1, 1, 0])
    rl = np.linalg.norm(radial, axis=1, keepdims=True) + 1e-6
    slope = R0 / (H - crown_base)
    ncone = unit(radial / rl + Z * slope * 1.3)
    N = unit(0.55 * nl + 0.45 * ncone + Z * 0.1)
    # ---- vertex colours
    rr = rl[:, 0] / np.maximum([cone_r(z_) for z_ in V[:, 2]], 0.2)
    ao = 0.45 + 0.55 * smoothstep(0.1, 0.95, rr)
    ao *= 0.8 + 0.2 * smoothstep(crown_base, H, V[:, 2])
    wind = np.clip(0.25 + 0.45 * (V[:, 2] / H) ** 1.5 + 0.35 * tipn, 0, 1)
    rnd = np.repeat(rng.random(len(V) // 2), 2)[:len(V)]
    C = np.stack([np.clip(ao, 0.3, 1), wind, rnd, np.ones(len(V))], 1)
    geo.add(V, N, UV, C, F, leaves)
    return geo


def sugi(variant):
    v = "ABC".index(variant)
    rng = np.random.default_rng(600 + v)
    fl.reset_scene()
    mats = fl.std_materials("Sugi")
    H = [24.0, 28.0, 19.0][v]
    R0 = [2.5, 2.9, 2.2][v]
    cb = H * [0.45, 0.5, 0.38][v]
    g0 = _sugi_geo(f"Sugi_{variant}_LOD0", H, R0, cb, np.random.default_rng(600 + v), 0)
    g1 = _sugi_geo(f"Sugi_{variant}_LOD1", H, R0, cb, np.random.default_rng(600 + v), 1)
    o0 = g0.build(mats)
    o1 = g1.build(mats)
    print(f"Sugi_{variant}: LOD0 tris={g0.tris()} LOD1 tris={g1.tris()}")
    return [o0, o1], dict(preview_kw=dict(offsets={o1.name: (R0 * 2 + 1.5, R0 * 1.2, 0)}))


# ============================================================================= kuromatsu (cloud-pruned black pine)
def kuromatsu(variant):
    import atlas_layout
    v = "AB".index(variant)
    rng = np.random.default_rng(700 + v)
    fl.reset_scene()
    mats = fl.std_materials("Pine")
    bark, leaves = "M_Bark_Pine", "M_Leaves_Pine"
    name = f"Kuromatsu_{variant}"
    geo = fl.Geo(name)
    H = [4.6, 3.6][v]
    # ---- S-curved, leaning trunk
    n = 16
    t = np.linspace(0, 1, n)
    az = rng.uniform(0, 6.28)
    lean_dir = np.array([math.cos(az), math.sin(az), 0])
    side_dir = np.array([-math.sin(az), math.cos(az), 0])
    amp = [0.55, 0.4][v]
    x = amp * np.sin(np.pi * t * 1.3) + 0.35 * t
    y = 0.25 * np.sin(np.pi * t * 2.1 + 0.5) * t
    pts = (x[:, None] * lean_dir + y[:, None] * side_dir) + np.outer(t * H * 0.86, Z)
    pts[0] = [0, 0, 0]
    r0 = [0.2, 0.16][v]
    radii = r0 * (1 - 0.72 * t ** 0.8)
    trunk = fl.Branch(pts, radii, 0, rnd=rng.random())
    branches = [trunk]
    # ---- limbs ending in cloud pads
    pads = []
    n_limbs = [7, 5][v]
    heights = np.sort(rng.uniform(0.32, 0.86, n_limbs))
    phase = rng.uniform(0, 6.28)
    for i, th in enumerate(heights):
        phase += 2.39996 + rng.normal(0, 0.3)
        p, r, T = trunk.at(th)
        d = unit(np.array([math.cos(phase), math.sin(phase), 0.15]))
        L = rng.uniform(1.0, 2.0) * (1.25 - 0.5 * th) * (H / 4.6)
        lp, lr = fl.grow(p, d, L, r * 0.62, 0.03, rng, seg=0.25, wobble=0.45, trop=Z, trop_k=0.05, min_dz=-0.25)
        limb = fl.Branch(lp, lr, 1, trunk, th, rnd=rng.random())
        branches.append(limb)
        rx = rng.uniform(0.75, 1.15) * (1.15 - 0.45 * th) * (H / 4.6) ** 0.5
        pads.append((lp[-1] + Z * 0.15, np.array([rx, rx * rng.uniform(0.75, 0.95), rx * rng.uniform(0.42, 0.5)]),
                     rng.uniform(0, 6.28), limb))
    # apex pad
    tip = trunk.pts[-1]
    pads.append((tip + Z * 0.25, np.array([0.95, 0.85, 0.55]) * (H / 4.6) ** 0.5, rng.uniform(0, 6.28), trunk))
    # sub-branches radiating under each pad
    for c, rad, rot, par in pads:
        for k in range(5):
            a = rot + k * 2 * math.pi / 5 + rng.normal(0, 0.3)
            d = unit(np.array([math.cos(a), math.sin(a), 0.1]))
            start = c - Z * 0.12
            lp, lr = fl.grow(start, d, rad[0] * 0.7, 0.025, 0.008, rng, seg=0.25, wobble=0.3)
            branches.append(fl.Branch(lp, lr, 2, par, 1.0, rnd=rng.random()))
    max_s = fl.max_path(branches)
    wind_fn = fl.path_wind(max_s, trunk_free=1.0, power=1.2)

    def ao_fn(P):
        return np.clip(0.5 + 0.5 * smoothstep(0, 1.5, P[:, 2]), 0.3, 1) * 0.9
    fl.mesh_branches(geo, branches, bark, (10, 6, 3), rng, v_len=0.7, ao_fn=ao_fn, wind_fn=wind_fn,
                     flare=(0.4, 0.4, 4), min_radius=0.005)
    ntb = geo.tris()
    # ---- needle cards on pads
    V, UV, Fc, C, tipn, rnds = [], [], [], [], [], []
    for c, rad, rot, par in pads:
        Rz = np.array([[math.cos(rot), -math.sin(rot), 0], [math.sin(rot), math.cos(rot), 0], [0, 0, 1]])
        ncard = int(120 * rad[0] * rad[1] + 24)
        prnd = rng.random()
        w_pad = float(wind_fn(par, np.array([par.s0 + par.length]))[0])
        for k in range(ncard):
            dvec = rand_unit(rng)
            if dvec[2] < -0.3:
                dvec[2] = -dvec[2] * 0.5 if rng.random() < 0.75 else dvec[2] * 0.6
            dvec = unit(dvec)
            pos = c + Rz @ (dvec * rad * rng.uniform(0.86, 1.06))
            outward = unit(Rz @ (dvec / rad))
            nc = unit(outward * 0.9 + Z * 0.15 + rand_unit(rng) * 0.3)
            sz = rng.uniform(0.3, 0.42) * (rad[0] / 1.0) ** 0.3
            cell = ["round_a", "round_b", "spray_a", "spray_b"][rng.integers(4)]
            rightv = unit(np.cross(nc, rand_unit(rng)))
            upv = unit(np.cross(nc, rightv))
            if upv[2] < -0.2:
                upv, rightv = -upv, -rightv
            cv_, cuv, cf, ctip = fl.card_quad(pos, rightv, upv, sz, sz, "center",
                                              atlas_layout.cell_uv("Leaves_Pine", cell))
            b0 = len(V)
            V += list(cv_); UV += list(cuv); tipn += list(ctip)
            Fc += [tuple(i + b0 for i in f) for f in cf]
            rnds += [prnd] * len(cv_)
            C += [w_pad] * len(cv_)
    # opaque flattened core dome per pad (mapped to the dense centre of the needle atlas)
    cu0, cv0, cu1, cv1 = atlas_layout.cell_uv("Leaves_Pine", "round_a")
    ucen, vcen = (cu0 + cu1) / 2, (cv0 + cv1) / 2 - 0.02
    core_faces_start = len(V)
    for c, rad, rot, par in pads:
        Rz = np.array([[math.cos(rot), -math.sin(rot), 0], [math.sin(rot), math.cos(rot), 0], [0, 0, 1]])
        nseg, nring = 10, 5
        b0 = len(V)
        prnd = rng.random()
        for i in range(nring + 1):
            el = -0.35 * math.pi / 2 + (math.pi / 2 + 0.35 * math.pi / 2) * i / nring
            for j in range(nseg):
                az_ = 2 * math.pi * j / nseg
                dv = np.array([math.cos(el) * math.cos(az_), math.cos(el) * math.sin(az_), math.sin(el)])
                q = c + Rz @ (dv * rad * np.array([0.78, 0.78, 0.82]))
                V.append(q)
                UV.append([ucen + 0.055 * dv[0], vcen + 0.055 * dv[1]])
                tipn.append(0.0); rnds.append(prnd); C.append(0.3)
        for i in range(nring):
            for j in range(nseg):
                a_ = b0 + i * nseg + j
                b_ = b0 + i * nseg + (j + 1) % nseg
                Fc.append((a_, b_, b_ + nseg, a_ + nseg))
        # flat bottom cap
        ci = len(V)
        V.append(c + Rz @ (np.array([0, 0, -0.35 * math.sin(0.35 * math.pi / 2)]) * rad))
        UV.append([ucen, vcen]); tipn.append(0.0); rnds.append(prnd); C.append(0.3)
        for j in range(nseg):
            Fc.append((b0 + (j + 1) % nseg, b0 + j, ci))
    V = np.array(V); UV = np.array(UV)
    field = fl.BlobField([p[0] for p in pads], [p[1] * np.array([1.08, 1.08, 1.5]) for p in pads], k=2.5)
    allc = np.array([p[0] for p in pads])
    gc = (allc.max(0) + allc.min(0)) / 2
    gr = (allc.max(0) - allc.min(0)) / 2 + 1.0
    N = field.normals(V, gc, gr, w_local=0.9, up=0.12)
    _, _, inside = field.eval(V)
    zrel = np.array([(V[i, 2] - 0) for i in range(len(V))])
    ao = 1 - 0.5 * smoothstep(0.0, 0.5, inside)
    ao *= 0.75 + 0.25 * np.clip(N[:, 2] * 0.5 + 0.5, 0, 1)
    wind = np.clip(np.array(C) + 0.25 * np.array(tipn), 0, 1)
    Ccol = np.stack([np.clip(ao, 0.3, 1), wind, np.array(rnds), np.ones(len(V))], 1)
    geo.add(V, N, UV, Ccol, Fc, leaves)
    ob = geo.build(mats)
    print(f"{name}: pads={len(pads)} tris branch={ntb} total={geo.tris()}")
    return [ob], dict(n_pads=len(pads))


# ============================================================================= bamboo grove clump
def bamboo(variant):
    import atlas_layout
    v = "AB".index(variant)
    rng = np.random.default_rng(800 + v)
    fl.reset_scene()
    mats = fl.std_materials("Bamboo")
    bark, leaves = "M_Bark_Bamboo", "M_Leaves_Bamboo"
    name = f"Bamboo_{variant}"
    geo = fl.Geo(name)
    n_culms = [15, 9][v]
    Hmax = [11.0, 9.0][v]
    Rg = [1.7, 1.05][v]
    internode = 0.36
    culms = []
    for i in range(n_culms):
        for _ in range(50):
            a = rng.uniform(0, 6.28)
            r = Rg * math.sqrt(rng.random())
            b = np.array([r * math.cos(a), r * math.sin(a), 0.0])
            if all(np.linalg.norm(b[:2] - c[0][:2]) > 0.22 for c in culms):
                break
        H = Hmax * rng.uniform(0.72, 1.0) * (1 - 0.15 * r / Rg)
        out = unit(b + rand_unit(rng) * 0.4 * Rg) * np.array([1, 1, 0])
        out = unit(out + 1e-6)
        lean = rng.uniform(0.03, 0.09) + 0.06 * r / Rg
        arch = rng.uniform(0.12, 0.25)
        rad = rng.uniform(0.042, 0.062) * (H / Hmax) ** 0.5
        culms.append((b, H, out, lean, arch, rad, rng.random()))
    # ---- culms (tubes); node rings come from the texture (v tiles once per internode)
    tops = []
    for (b, H, out, lean, arch, rad, rnd) in culms:
        zs = np.linspace(0, H, 13)
        t = zs / H
        off = out[None, :] * (lean * zs + arch * H * np.maximum(t - 0.55, 0) ** 2 * 2.2)[:, None]
        pts = b + off + np.outer(zs, Z)
        radii = rad * (1 - 0.55 * t ** 1.5) + 0.004
        ao = 0.5 + 0.5 * smoothstep(0, 2.5, zs)
        wind = 0.95 * t ** 1.6
        col = np.stack([ao, wind, np.full(len(zs), rnd), np.ones(len(zs))], 1)
        fl.tube(geo, pts, radii, 6, bark, u_rep=1, v_len=internode, colors=col, cap=True, base_extend=0.1)
        tops.append(fl.Branch(pts, radii, 0, rnd=rnd))
    ntb = geo.tris()
    # ---- leaf sprays hanging from the upper culms
    V, UV, F, wind_l, rnds, tipn = [], [], [], [], [], []
    blobs_c, blobs_r = [], []
    cells = ["round_a", "round_b", "spray_a", "spray_b"]
    for br, (b, H, out, lean, arch, rad, rnd) in zip(tops, culms):
        t0 = rng.uniform(0.4, 0.5)
        n_att = int((1 - t0) * H / 0.2)
        for k in range(n_att):
            t = t0 + (1 - t0) * (k + rng.uniform(0, 1)) / n_att
            p, r, T = br.at(t)
            for j in range(rng.integers(2, 5)):
                az = rng.uniform(0, 6.28)
                hor = np.array([math.cos(az), math.sin(az), 0.0])
                hor = unit(hor + out * 0.6)
                ln = rng.uniform(0.25, 0.9) * (1.1 - 0.6 * (t - t0) / (1 - t0))
                attach = p + hor * ln * 0.5
                upv = unit(hor * 0.75 + Z * rng.uniform(0.35, 0.8))
                side = unit(np.cross(upv, Z) + rand_unit(rng) * 0.25)
                sz = rng.uniform(0.95, 1.3)
                cell = cells[rng.integers(4)]
                cv_, cuv, cf, ctip = fl.card_quad(attach, side, upv, sz, sz, "bottom",
                                                  atlas_layout.cell_uv("Leaves_Bamboo", cell), segs=2, bend=0.18,
                                                  bend_dir=-Z)
                b0 = len(V)
                V += list(cv_); UV += list(cuv); tipn += list(ctip)
                F += [tuple(i + b0 for i in f) for f in cf]
                rnds += [rnd] * len(cv_)
                wind_l += [0.95 * t ** 1.6] * len(cv_)
        # mass for this culm's foliage
        pc, _, _ = br.at((t0 + 1) / 2)
        blobs_c.append(pc + Z * 0.0)
        blobs_r.append([1.5, 1.5, (1 - t0) * H * 0.62])
    V = np.array(V); UV = np.array(UV)
    field = fl.BlobField(blobs_c, blobs_r, k=1.6)
    allc = np.array(blobs_c)
    gc = (allc.max(0) + allc.min(0)) / 2
    gr = (allc.max(0) - allc.min(0)) / 2 + np.array([1.8, 1.8, 2.0])
    N = field.normals(V, gc, gr, w_local=0.6, up=0.12)
    _, _, inside = field.eval(V)
    gd = np.sqrt(np.sum(((V - gc) / gr) ** 2, 1))
    ao = 1 - 0.35 * smoothstep(0, 0.6, inside) - 0.25 * (1 - smoothstep(0.3, 1.0, gd))
    wind = np.clip(np.array(wind_l) + 0.2 * np.array(tipn), 0, 1)
    C = np.stack([np.clip(ao, 0.3, 1), wind, np.array(rnds), np.ones(len(V))], 1)
    geo.add(V, N, UV, C, F, leaves)
    ob = geo.build(mats)
    print(f"{name}: culms={n_culms} tris culms={ntb} total={geo.tris()}")
    return [ob], dict(n_culms=n_culms)


BUILDERS = {}
for _v in "ABC":
    BUILDERS[f"Sakura_{_v}"] = (lambda v=_v: sakura(v))
for _v in "ABC":
    BUILDERS[f"Keyaki_{_v}"] = (lambda v=_v: keyaki(v))
for _v in "AB":
    BUILDERS[f"Ginkgo_{_v}"] = (lambda v=_v: ginkgo(v))
for _v in "ABC":
    BUILDERS[f"Momiji_{_v}"] = (lambda v=_v: momiji(v))
for _v in "ABC":
    BUILDERS[f"Sugi_{_v}"] = (lambda v=_v: sugi(v))
for _v in "AB":
    BUILDERS[f"Kuromatsu_{_v}"] = (lambda v=_v: kuromatsu(v))
for _v in "AB":
    BUILDERS[f"Bamboo_{_v}"] = (lambda v=_v: bamboo(v))
