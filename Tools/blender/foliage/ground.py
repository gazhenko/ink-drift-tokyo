"""Ground cover builders: grass clumps, ferns, susuki (pampas) + autumn weeds, leaf/petal litter patches.

All are alpha-cutout card meshes. Normals are bent strongly toward +Z (domed slightly outward) so in the
toon shader they light like the ground they sit on instead of flickering per card.
"""
import math

import numpy as np

import atlas_layout
import foliage_lib as fl
from foliage_lib import Z, unit, smoothstep
from shrubs import CardAcc, cell_uv_in


def _mats(mat, tex):
    return {mat: fl.make_material(mat, tex, alpha=True, roughness=0.8)}


def strip_card(base, up_dir, out_dir, w, h, segs, bend, uvr, lean=0.0):
    """Vertical-ish card rising from `base`; bends toward out_dir with height (quadratic)."""
    side = unit(np.cross(up_dir, out_dir)) if abs(np.dot(unit(up_dir), unit(out_dir))) < 0.99 else np.array([1.0, 0, 0])
    u0, v0, u1, v1 = uvr
    V, UV, tip = [], [], []
    for j in range(segs + 1):
        f = j / segs
        c = base + up_dir * h * f + out_dir * (lean * h * f + bend * h * f * f)
        for i in (0, 1):
            V.append(c + side * w * (i - 0.5))
            UV.append([u0 + (u1 - u0) * i, v0 + (v1 - v0) * f])
            tip.append(f)
    F = [(j * 2, j * 2 + 1, j * 2 + 3, j * 2 + 2) for j in range(segs)]
    return np.array(V), np.array(UV), F, np.array(tip)


def finish_cover(name, mat, tex, acc, H, n_up=0.85, dome_c=(0, 0, -0.25), wind_scale=1.0, ao_min=0.5,
                 preview_kw=None):
    geo = fl.Geo(name)
    V, UV, tip, rnd, depth = acc.arrays()
    out = unit(V - np.array(dome_c))
    N = unit(out * (1 - n_up) + Z * n_up)
    hgt = np.clip(V[:, 2] / max(H, 1e-3), 0, 1)
    ao = ao_min + (1 - ao_min) * smoothstep(0.0, 0.7, hgt)
    wind = np.clip((0.15 * hgt + 0.85 * tip ** 1.5) * wind_scale, 0, 1)
    C = np.stack([ao, wind, rnd, np.ones(len(V))], 1)
    geo.add(V, N, UV, C, acc.F, mat)
    ob = geo.build(_mats(mat, tex))
    print(f"{name}: tris={geo.tris()}")
    return [ob], dict(preview_kw=preview_kw or dict(human=False, el=20))


# ============================================================================= grass
def grass(name, tufts, seed):
    """tufts: list of (offset_xy, height, width, n_cards, cells)."""
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    acc = CardAcc()
    Hmax = 0
    for off, h, w, n, cells in tufts:
        base0 = np.array([off[0], off[1], -0.03])
        a0 = rng.uniform(0, math.pi)
        rnd = rng.random()
        for k in range(n):
            a = a0 + math.pi * k / n + rng.normal(0, 0.12)
            outd = np.array([math.cos(a + math.pi / 2), math.sin(a + math.pi / 2), 0.0])
            if rng.random() < 0.5:
                outd = -outd
            hh = h * rng.uniform(0.85, 1.1)
            ww = w * rng.uniform(0.85, 1.1)
            cell = cells[rng.integers(len(cells))]
            # card plane spans direction `a`; it leans/bends slightly toward its normal side
            dirv = np.array([math.cos(a), math.sin(a), 0.0])
            nrm = unit(np.cross(dirv, Z))
            if np.dot(nrm, outd) < 0:
                nrm = -nrm
            base = base0 + rng.normal(0, w * 0.06, 3) * [1, 1, 0]
            V, UV, F, tip = strip_card(base, Z, nrm, ww, hh, 2, rng.uniform(0.05, 0.15),
                                       cell_uv_in("Grass", cell, 6), lean=rng.uniform(0.0, 0.12))
            acc.add(V, UV, F, tip, rnd)
            Hmax = max(Hmax, hh)
    return finish_cover(name, "M_Grass", "Grass_albedo.png", acc, Hmax, n_up=0.85)


def grass_a():
    return grass("Grass_A", [((0, 0), 0.42, 0.6, 4, ("clump_a",)), ((0.28, 0.18), 0.34, 0.5, 4, ("clump_b",)),
                             ((-0.26, 0.12), 0.36, 0.5, 4, ("clump_a", "clump_b"))], 401)


def grass_b():
    return grass("Grass_B", [((0, 0), 0.68, 0.62, 3, ("tall",)), ((0.3, -0.15), 0.4, 0.55, 3, ("clump_a",)),
                             ((-0.25, -0.2), 0.42, 0.55, 3, ("clump_b",)), ((-0.05, 0.3), 0.55, 0.5, 2, ("tall",))],
                 402)


def grass_c():
    return grass("Grass_C", [((0, 0), 0.4, 0.58, 4, ("flowers",)), ((0.3, 0.1), 0.32, 0.5, 4, ("clump_b",)),
                             ((-0.2, -0.22), 0.36, 0.52, 4, ("flowers", "clump_a"))], 403)


# ============================================================================= ferns
def fern(name, n_fronds, length, elev, droop, cells, seed, width_frac=0.5, segs=5):
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    acc = CardAcc()
    a0 = rng.uniform(0, 6.28)
    Hmax = 0
    for k in range(n_fronds):
        az = a0 + 2 * math.pi * k / n_fronds + rng.normal(0, 0.18)
        L = length * rng.uniform(0.78, 1.12)
        e0 = math.radians(elev + rng.normal(0, 8))
        dr = math.radians(droop + rng.normal(0, 10))
        hdir = np.array([math.cos(az), math.sin(az), 0.0])
        side = np.array([-math.sin(az), math.cos(az), 0.0])
        roll = rng.normal(0, 0.25)
        cell = cells[rng.integers(len(cells))]
        u0, v0, u1, v1 = cell_uv_in("Fern", cell, 5)
        if rng.random() < 0.5:  # mirror for variety
            u0, u1 = u1, u0
        p = np.array([0.0, 0.0, 0.02]) + hdir * 0.03
        V, UV, tip = [], [], []
        W = L * width_frac
        for j in range(segs + 1):
            f = j / segs
            # tangent elevation goes from e0 down to -(dr) along the frond
            if j > 0:
                ang = e0 - (e0 + dr) * (f - 0.5 / segs) ** 1.3
                p = p + (hdir * math.cos(ang) + Z * math.sin(ang)) * (L / segs)
            t = unit(hdir * math.cos(e0 - (e0 + dr) * f ** 1.3) + Z * math.sin(e0 - (e0 + dr) * f ** 1.3))
            sd = unit(side * math.cos(roll) + np.cross(t, side) * math.sin(roll))
            # leaflets narrow to zero at the base visually via texture; keep base slightly narrower
            ww = W * (0.75 + 0.25 * min(1, f * 3))
            for i in (0, 1):
                V.append(p + sd * ww * (i - 0.5))
                UV.append([u0 + (u1 - u0) * i, v0 + (v1 - v0) * f])
                tip.append(f)
            Hmax = max(Hmax, p[2])
        F = [(j * 2, j * 2 + 1, j * 2 + 3, j * 2 + 2) for j in range(segs)]
        acc.add(np.array(V), np.array(UV), F, np.array(tip), rng.random())
    return finish_cover(name, "M_Fern", "Fern_albedo.png", acc, Hmax, n_up=0.7, dome_c=(0, 0, -0.15),
                        ao_min=0.45, preview_kw=dict(human=False, el=28))


def fern_a():
    return fern("Fern_A", 11, 0.85, 55, 35, ("frond_a", "frond_b"), 411)


def fern_b():
    # shuttlecock-like, more upright, smaller
    return fern("Fern_B", 9, 0.62, 70, 5, ("frond_b", "frond_a"), 412, width_frac=0.48)


# ============================================================================= tall grasses / weeds
def tall_clump(name, cell, height, width, n_main, n_low, seed, n_up=0.6):
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    acc = CardAcc()
    uvr = cell_uv_in("Weeds", cell, 5)
    a0 = rng.uniform(0, math.pi)
    for k in range(n_main + n_low):
        low = k >= n_main
        a = a0 + math.pi * k / (n_main if not low else n_low) + rng.normal(0, 0.15) + (0.3 if low else 0)
        dirv = np.array([math.cos(a), math.sin(a), 0.0])
        nrm = unit(np.cross(dirv, Z))
        if rng.random() < 0.5:
            nrm = -nrm
        h = height * (rng.uniform(0.9, 1.08) if not low else rng.uniform(0.62, 0.78))
        w = width * (rng.uniform(0.9, 1.1) if not low else rng.uniform(0.8, 0.95))
        base = np.array([0, 0, -0.04]) + rng.normal(0, 0.05, 3) * [1, 1, 0]
        V, UV, F, tip = strip_card(base, Z, nrm, w, h, 3, rng.uniform(0.04, 0.1) if not low else 0.16, uvr,
                                   lean=rng.uniform(0.02, 0.08) if not low else rng.uniform(0.12, 0.2))
        acc.add(V, UV, F, tip, rng.random())
    return finish_cover(name, "M_Weeds", "Weeds_albedo.png", acc, height, n_up=n_up, dome_c=(0, 0, -0.4),
                        ao_min=0.45, preview_kw=dict(human=True, el=14))


def susuki_a():
    return tall_clump("Susuki_A", "susuki", 1.55, 0.8, 4, 3, 421)


def weeds_autumn_a():
    return tall_clump("Weeds_Autumn_A", "weeds", 0.95, 0.5, 4, 2, 422)


# ============================================================================= litter patches
def litter(name, cell, seed):
    rng = np.random.default_rng(seed)
    fl.reset_scene()
    acc = CardAcc()
    uvr = cell_uv_in("Litter", cell, 5)
    # main 2x1 m flat card
    cards = [(np.array([0.0, 0.0, 0.012]), 0.0, 2.0, 1.0, 0.0)]
    for k in range(3):
        cards.append((np.array([rng.uniform(-0.55, 0.55), rng.uniform(-0.2, 0.2), 0.02 + 0.006 * k]),
                      rng.uniform(0, 2 * math.pi), rng.uniform(0.9, 1.1), rng.uniform(0.45, 0.55),
                      math.radians(rng.uniform(2, 5))))
    for c, rot, w, h, tilt in cards:
        r = np.array([math.cos(rot), math.sin(rot), 0.0])
        u = np.array([-math.sin(rot), math.cos(rot), 0.0])
        # slight tilt around the card's long axis
        u = unit(u * math.cos(tilt) + Z * math.sin(tilt))
        V, UV, F, tip = fl.card_quad(c, r, u, w, h, "center", uvr)
        # make sure faces point up
        if np.cross(V[1] - V[0], V[2] - V[0])[2] < 0:
            F = [tuple(reversed(f)) for f in F]
        acc.add(V, UV, F, np.zeros(len(V)), rng.random())
    geo = fl.Geo(name)
    V, UV, tip, rnd, depth = acc.arrays()
    N = np.tile(Z, (len(V), 1))
    C = np.stack([np.full(len(V), 0.9), np.zeros(len(V)), rnd, np.ones(len(V))], 1)
    geo.add(V, N, UV, C, acc.F, "M_Litter")
    ob = geo.build(_mats("M_Litter", "Litter_albedo.png"))
    print(f"{name}: tris={geo.tris()}")
    return [ob], dict(preview_kw=dict(human=False, el=42))


def litter_autumn():
    return litter("Litter_Autumn", "autumn", 431)


def litter_petals():
    return litter("Litter_Petals", "petals", 432)


BUILDERS = {
    "Grass_A": grass_a,
    "Grass_B": grass_b,
    "Grass_C": grass_c,
    "Fern_A": fern_a,
    "Fern_B": fern_b,
    "Susuki_A": susuki_a,
    "Weeds_Autumn_A": weeds_autumn_a,
    "Litter_Autumn": litter_autumn,
    "Litter_Petals": litter_petals,
}
