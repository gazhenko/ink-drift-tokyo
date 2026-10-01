"""MOUNTAIN (Okutama touge) + SHRINE props: slope-protection lattice walls, kenchi-stone retaining wall,
cable guardrail, delineator / snow pole, small-bridge railing + end post, stone torii, stone lantern,
offering box, roadside hokora.
Build:  blender -b -P Tools/blender/props/build_props.py -- props_mountain [builder ...]
Textures: Tools/.venv/bin/python Tools/blender/props/make_textures_mountain.py"""
import math
from mathutils import Vector
from propkit import (Prop, UV, builder, define_mat, circle2d, rect2d, rounded_rect2d, fillet, thicken2d)

define_mat('M_SlopeFill_Grass', c='#6A8838', r=0.95)
define_mat('M_SlopeFill_Shotcrete', c='#A9A598', r=0.95)
define_mat('M_Brass', c='#B8913A', r=0.35, m=0.9)
define_mat('M_CopperRoof', c='#5F907B', r=0.6, m=0.3)
define_mat('M_Deco_BridgePlate', c='#5C4226', r=0.45, m=0.6, tex='prop_bridge_plate_albedo.png')
define_mat('M_Deco_ShrinePlaque', c='#181616', r=0.4, tex='prop_shrine_plaque_albedo.png')
define_mat('M_Deco_Saisen', c='#3E2414', r=0.5, tex='prop_saisen_albedo.png')
define_mat('M_Deco_SnowArrow', c='#DE221E', r=0.4, tex='prop_snow_arrow_albedo.png')


# ======================================================================================
# helpers
# ======================================================================================
def prism_frame(P, p0, p1, lat, nrm, profile, mat, **kw):
    """Prism along p0->p1 with 2D profile [(a, b)] where a runs along `lat` and b along `nrm`."""
    p0 = Vector(p0); p1 = Vector(p1); lat = Vector(lat).normalized(); nrm = Vector(nrm).normalized()
    m = len(profile)
    verts = [p0 + lat * a + nrm * b for (a, b) in profile] + [p1 + lat * a + nrm * b for (a, b) in profile]
    faces = [[j, (j + 1) % m, m + (j + 1) % m, m + j] for j in range(m)]
    faces.append(list(range(m))[::-1])
    faces.append([m + j for j in range(m)])
    kw.setdefault('bevel', 0.0)
    kw.setdefault('sharp', 35.0)
    o = P.poly(verts, faces, mat=mat, **kw)
    _fix_normals(o)
    return o


def _fix_normals(obj):
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data); bm.free()


def poly_closed(P, verts, faces, mat, **kw):
    o = P.poly(verts, faces, mat=mat, **kw)
    _fix_normals(o)
    return o


def inset_poly(pts, offs):
    """Inset a convex CCW 2D polygon; offs[i] = inward offset of edge i (pts[i] -> pts[i+1])."""
    n = len(pts)
    lines = []
    for i in range(n):
        a = Vector(pts[i]); b = Vector(pts[(i + 1) % n])
        d = (b - a).normalized()
        nr = Vector((-d.y, d.x))
        lines.append((a + nr * offs[i], d))
    out = []
    for i in range(n):
        p1, d1 = lines[i - 1]; p2, d2 = lines[i]
        cr = d1.x * d2.y - d1.y * d2.x
        if abs(cr) < 1e-9:
            out.append(Vector(p2)); continue
        w = p2 - p1
        t = (w.x * d2.y - w.y * d2.x) / cr
        out.append(p1 + d1 * t)
    return out


def clip_poly(pts, axis, val, keep_greater):
    out = []
    n = len(pts)
    for i in range(n):
        a = pts[i]; b = pts[(i + 1) % n]
        ina = (a[axis] >= val - 1e-9) if keep_greater else (a[axis] <= val + 1e-9)
        inb = (b[axis] >= val - 1e-9) if keep_greater else (b[axis] <= val + 1e-9)
        if ina:
            out.append(a)
        if ina != inb:
            t = (val - a[axis]) / (b[axis] - a[axis])
            out.append(Vector((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)))
    # dedupe consecutive
    res = []
    for p in out:
        if not res or (p - res[-1]).length > 1e-7:
            res.append(Vector(p))
    if len(res) > 1 and (res[0] - res[-1]).length < 1e-7:
        res.pop()
    return res


def hash01(*k):
    h = 2166136261
    for v in k:
        h = ((h ^ (int(v) & 0xffffffff)) * 16777619) & 0xffffffff
    h ^= h >> 13
    h = (h * 0x5bd1e995) & 0xffffffff
    h ^= h >> 15
    return (h & 0xffff) / 65535.0


def delineator_head(P, x, y, ztop, stem=0.09):
    """Round reflector (Φ100) on a short stem, faces along the road (±X): amber +X / white -X."""
    P.box_mm((x - 0.008, y - 0.015, ztop), (x + 0.008, y + 0.015, ztop + stem), mat='M_Galvanized', bevel=0.002)
    zc = ztop + stem + 0.055
    P.cyl((x - 0.013, y, zc), (x + 0.013, y, zc), 0.062, seg=16, mat='M_PlasticWhite', bevel=0.004)
    P.cyl((x + 0.013, y, zc), (x + 0.0145, y, zc), 0.05, seg=16, mat='M_Reflector_Amber', bevel=0.0)
    P.cyl((x - 0.0145, y, zc), (x - 0.013, y, zc), 0.05, seg=16, mat='M_Reflector_White', bevel=0.0)


def post_cap(P, x, y, z, r, mat):
    P.lathe([(r + 0.003, z), (r + 0.003, z + 0.012), (r * 0.7, z + 0.022), (0.0, z + 0.026)], seg=16,
            loc=(x, y, 0), mat=mat, bevel=0.0, sharp=45)


# ======================================================================================
# 1. Slope protection lattice (吹付法枠) 8 m x 6 m, slope 1:0.5
# ======================================================================================
SLOPE_W = 8.0
SLOPE_H = 6.0
SLOPE_K = 0.5                 # horizontal run per metre of height
TOE_D = 0.5                   # toe / berm depth in front of the slope foot
SL_U = Vector((0, SLOPE_K, 1)).normalized()      # up-slope unit
SL_N = Vector((0, -1, SLOPE_K)).normalized()     # outward normal (toward road, up)
SL_LEN = SLOPE_H * math.sqrt(1 + SLOPE_K ** 2)   # 6.708 m slope length


def slope_pt(x, s, h=0.0):
    return Vector((x, TOE_D, 0)) + SL_U * s + SL_N * h


def _slope_wall(name, fill_mat, pillow):
    P = Prop(name, 'mountain', mirror_x=True,
             desc='法面 吹付法枠: concrete lattice frame on a 1:0.5 cut slope, 8 m wide x 6 m high tile, '
                  'cells on ' + fill_mat,
             origin='ground at the front-bottom edge of the toe, tile start (Unity X=0); tile spans X 0..8',
             front='slope faces Unity +Z (road), leans back toward -Z',
             preview=dict(az=30, el=14))
    nx, ns = 4, 3                       # cells
    cs = SL_LEN / ns                    # 2.236 m along slope (2.0 m vertical)
    cw = SLOPE_W / nx                   # 2.0 m

    def fill(u, v):
        x = u * SLOPE_W
        s = v * SL_LEN
        h = pillow * math.sin(math.pi * (x % cw) / cw) * math.sin(math.pi * (s % cs) / cs)
        return tuple(slope_pt(x, s, h))
    P.grid_surface(fill, nx * 6, ns * 6, mat=fill_mat, bevel=0.0, sharp=50, uv=UV.box())
    # lattice beams 0.30 x 0.30, chamfered, bottom sunk 5 cm into the fill
    full = [(-0.15, -0.05), (0.15, -0.05), (0.15, 0.22), (0.10, 0.30), (-0.10, 0.30), (-0.15, 0.22)]
    half_lo = [(0.0, -0.05), (0.15, -0.05), (0.15, 0.22), (0.10, 0.30), (0.0, 0.30)]
    half_hi = [(-0.15, -0.05), (0.0, -0.05), (0.0, 0.30), (-0.10, 0.30), (-0.15, 0.22)]
    X = Vector((1, 0, 0))
    for i in range(nx + 1):
        x = i * cw
        prof = half_lo if i == 0 else (half_hi if i == nx else full)
        prism_frame(P, slope_pt(x, 0.08), slope_pt(x, SL_LEN), X, SL_N, prof, 'M_Concrete', uv=UV.box())
    for j in range(1, ns + 1):     # bottom half-beam would be buried in the toe -> skipped
        s = j * cs
        prof = half_lo if j == 0 else (half_hi if j == ns else full)
        for i in range(nx):
            xa = i * cw + 0.14
            xb = (i + 1) * cw - 0.14
            prism_frame(P, slope_pt(xa, s), slope_pt(xb, s), SL_U, SL_N, prof, 'M_Concrete', uv=UV.box())
    # toe / berm block: front vertical face at y=0, back face on the slope plane
    yb = TOE_D + SLOPE_K * 0.5
    P.prism([(0.0, 0.0), (TOE_D, 0.0), (yb, 0.5), (0.04, 0.5), (0.0, 0.46)], 0.0, SLOPE_W, mat='M_Concrete',
            bevel=0.0, sharp=30, uv=UV.box())
    P.note(f'Tile along Unity X every {SLOPE_W:.0f} m. Stack vertically with the next panel origin at Unity '
           f'(0, +{SLOPE_H:.1f}, -{TOE_D + SLOPE_K * SLOPE_H:.1f}) (6 m up, 3.5 m back; its toe forms a 0.5 m berm).')
    P.finish()


@builder
def build_slope_protection_grid_wall():
    _slope_wall('slope_protection_grid_wall_grass', 'M_SlopeFill_Grass', 0.12)
    _slope_wall('slope_protection_grid_wall_shotcrete', 'M_SlopeFill_Shotcrete', 0.04)


# ======================================================================================
# 2. Kenchi-ishi (間知石) retaining wall, tani-zumi diagonal coursing, 4 m tile
# ======================================================================================
@builder
def build_stone_retaining_wall_4m():
    L = 4.0
    BAT = 0.3                                  # batter 1:0.3
    Y0 = 0.10                                  # wall face foot (foundation proud 0.1 in front)
    U = Vector((0, BAT, 1)).normalized()       # up the face
    N = Vector((0, -1, BAT)).normalized()      # outward normal
    sl = math.sqrt(1 + BAT * BAT)
    z_found, z_cope = 0.20, 2.75
    w0, w1 = z_found * sl, z_cope * sl

    def F(u, w, h=0.0):
        return Vector((u, Y0, 0)) + U * w + N * h

    P = Prop('stone_retaining_wall_4m', 'mountain', mirror_x=True,
             desc='間知石 retaining wall, tani-zumi diagonal coursing, batter 1:0.3, 4 m tile x 3 m high, '
                  'concrete foundation + coping, weep holes',
             origin='ground at the foundation front edge, tile start (Unity X=0); tile spans X 0..4',
             front='wall face toward Unity +Z, leans back toward -Z',
             preview=dict(az=28, el=12, extra=[('detail', 30, 10, ((-1.8, -0.2, 0), (0, 1.0, 1.6))), ('top', 20, 25, ((-1.6, 0.4, 2.2), (-0.2, 1.2, 3.05)))]))
    n = 9
    d = L / n                                  # diamond width 0.444 (stone face ~0.31 m square)
    joint = 0.018
    cham = 0.03
    verts = []
    faces = []
    rows = int((w1 - w0) / (d / 2)) + 3
    for r in range(-1, rows):
        wc = w0 + r * d / 2
        for c in range(-1, n + 2):
            uc = (c + (0.5 if r % 2 else 0.0)) * d
            dia = [Vector((uc, wc - d / 2)), Vector((uc + d / 2, wc)), Vector((uc, wc + d / 2)),
                   Vector((uc - d / 2, wc))]
            poly = dia
            for (ax, val, kg) in ((0, 0.0, True), (0, L, False), (1, w0, True), (1, w1, False)):
                if len(poly) < 3:
                    break
                poly = clip_poly(poly, ax, val, kg)
            if len(poly) < 3:
                continue
            area = 0
            for i in range(len(poly)):
                a = poly[i]; b = poly[(i + 1) % len(poly)]
                area += a.x * b.y - b.x * a.y
            if area < 0:
                poly = poly[::-1]
            if abs(area) / 2 < 0.004:
                continue
            # merge very short (clip) edges that are not on the tile seam -> avoids inset inversion spikes
            changed = True
            while changed and len(poly) > 3:
                changed = False
                for i in range(len(poly)):
                    a_ = poly[i]; b_ = poly[(i + 1) % len(poly)]
                    on_seam = any(abs(q.x) < 1e-6 or abs(q.x - L) < 1e-6 for q in (a_, b_))
                    if (b_ - a_).length < 0.07 and not on_seam:
                        mid = (a_ + b_) / 2
                        poly[i] = mid
                        del poly[(i + 1) % len(poly)]
                        changed = True
                        break
            m = len(poly)
            bnd = []
            for i in range(m):
                a = poly[i]; b = poly[(i + 1) % m]
                on_b = (abs(a.x) < 1e-6 and abs(b.x) < 1e-6) or (abs(a.x - L) < 1e-6 and abs(b.x - L) < 1e-6)
                bnd.append(on_b)
            cen0 = sum(poly, Vector((0, 0))) / m
            rin = 1e9
            for i in range(m):
                if bnd[i]:
                    continue
                a = poly[i]; b = poly[(i + 1) % m]
                dd = (b - a).normalized()
                rin = min(rin, abs((cen0 - a).x * dd.y - (cen0 - a).y * dd.x))
            if rin < 0.03:
                continue
            k = min(1.0, 0.5 * rin / (joint / 2 + cham))
            base = inset_poly(poly, [0.0 if bb else k * joint / 2 for bb in bnd])
            top = inset_poly(base, [0.0 if bb else k * cham for bb in bnd])
            key_c = c % n
            hs = 0.04 + 0.045 * hash01(r, key_c, 1)
            dome = 0.015 + 0.03 * hash01(r, key_c, 2)
            apex = Vector(((hash01(r, key_c, 3) - 0.5) * 0.06, (hash01(r, key_c, 4) - 0.5) * 0.06))
            k0 = len(verts)
            for p in base:
                verts.append(F(p.x, p.y, 0.0))
            for p in top:
                verts.append(F(p.x, p.y, hs))
            cen = sum(top, Vector((0, 0))) / m
            if m != 4:                 # clipped course-end stones (天端石/根石): flatter faces
                dome *= 0.35
            elif not any(bnd):
                cen = cen + apex
            verts.append(F(cen.x, cen.y, hs + dome))
            ci = len(verts) - 1
            for i in range(m):
                j = (i + 1) % m
                faces.append([k0 + i, k0 + j, k0 + m + j, k0 + m + i])
                faces.append([k0 + m + i, k0 + m + j, ci])
    P.poly(verts, faces, mat='M_Stone', bevel=0.0, sharp=38, uv=UV.box())
    # mortar bed plane
    P.poly([F(0, w0 - 0.02, -0.004), F(L, w0 - 0.02, -0.004), F(L, w1 + 0.02, -0.004), F(0, w1 + 0.02, -0.004)],
           [[0, 1, 2, 3]], mat='M_Concrete_Dark', bevel=0.0, uv=UV.box())
    # foundation (proud 0.1 m) and coping (天端コンクリート)
    yf = Y0 + BAT * z_found
    P.prism([(0.0, 0.0), (Y0 + 0.25, 0.0), (Y0 + 0.25, z_found), (yf, z_found), (0.03, z_found),
             (0.0, z_found - 0.03)], 0.0, L, mat='M_Concrete', bevel=0.0, sharp=30, uv=UV.box())
    yc = Y0 + BAT * z_cope - 0.09
    P.prism([(yc + 0.0, z_cope), (yc + 0.0, 2.97), (yc + 0.03, 3.0), (yc + 0.65, 3.0), (yc + 0.65, z_cope - 0.15),
             (Y0 + BAT * (z_cope - 0.15) + 0.02, z_cope - 0.15)], 0.0, L, mat='M_Concrete', bevel=0.0, sharp=30,
            uv=UV.box())
    # weep holes (PVC Φ75) through the face
    for (u, z) in ((1.0, 0.75), (3.0, 0.75), (2.0, 1.85)):
        w = z * sl
        P.cyl(F(u, w, -0.02), F(u, w, 0.13), 0.04, seg=12, mat='M_PlasticGray', bevel=0.004)
        P.cyl(F(u, w, 0.128), F(u, w, 0.134), 0.031, seg=12, mat='M_PlasticBlack', bevel=0.0)
    P.note('Tile along Unity X every 4 m; diamond stone pattern is periodic (9 stones per tile per course).')
    P.finish()


# ======================================================================================
# 3. Guard cable (ガードケーブル)
# ======================================================================================
GC_POST_R = 0.0572        # Φ114.3
GC_POST_H = 0.95
GC_CABLE_Z = (0.50, 0.60, 0.70, 0.80, 0.90)
GC_CABLE_R = 0.009        # Φ18
GC_CABLE_Y = -(GC_POST_R + 0.012 + GC_CABLE_R)


def _gc_post(P, x, mat):
    P.cyl((x, 0, 0), (x, 0, GC_POST_H), GC_POST_R, seg=16, mat=mat, bevel=0.005)
    post_cap(P, x, 0, GC_POST_H, GC_POST_R, mat)
    # cable brackets (U-bolt clamps) on the road side
    for z in GC_CABLE_Z:
        P.box_mm((x - 0.03, GC_CABLE_Y - 0.016, z - 0.016), (x + 0.03, -GC_POST_R + 0.008, z + 0.016),
                 mat='M_Galvanized', bevel=0.003)
    delineator_head(P, x, 0.0, GC_POST_H + 0.024)


def _gc_cables(P, x0, x1):
    for z in GC_CABLE_Z:
        P.cyl((x0, GC_CABLE_Y, z), (x1, GC_CABLE_Y, z), GC_CABLE_R, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70,
              uv=UV.box())


def _guard_cable_tile(name, mat, colour):
    P = Prop(name, 'mountain', mirror_x=True,
             desc=f'Japanese guard cable (ガードケーブル) tile, 4 m, {colour} Φ114 posts, 5 x Φ18 cables, spacer bar',
             origin='ground at the post centre (Unity X=0); tile spans X 0..4',
             front='cables on the road side (Unity +Z)')
    _gc_post(P, 0.0, mat)
    _gc_cables(P, 0.0, 4.0)
    # mid-span spacer (間隔保持材)
    xs = 2.0
    P.box_mm((xs - 0.015, GC_CABLE_Y - GC_CABLE_R - 0.006, GC_CABLE_Z[0] - 0.04),
             (xs + 0.015, GC_CABLE_Y - GC_CABLE_R, GC_CABLE_Z[-1] + 0.04), mat=mat, bevel=0.002)
    for z in GC_CABLE_Z:
        P.box_mm((xs - 0.02, GC_CABLE_Y - GC_CABLE_R - 0.01, z - 0.014),
                 (xs + 0.02, GC_CABLE_Y + GC_CABLE_R + 0.004, z + 0.014), mat='M_Galvanized', bevel=0.002)
    P.note('Post at Unity X=0 only; cap a run with mountain_guardrail_cable_end_finish at X=4N and '
           'mountain_guardrail_cable_end_start at X=0 (its heavier post encloses the tile post).')
    P.finish()


def _guard_cable_end(name, finish, mat):
    sgn = 1.0 if finish else -1.0      # direction away from the run
    P = Prop(name, 'mountain', mirror_x=True,
             desc='Guard cable end/anchor post (端末支柱) Φ165 with brace, footing and cable turnbuckles',
             origin='ground at the end post centre (attach at the run end, Unity X=4N for _finish, X=0 for _start)')
    R = 0.0826
    H = 1.0
    P.cyl((0, 0, 0), (0, 0, H), R, seg=18, mat=mat, bevel=0.006)
    post_cap(P, 0, 0, H, R, mat)
    P.box_mm((-0.25, -0.25, 0.0), (0.25, 0.25, 0.06), mat='M_Concrete', bevel=0.012)
    # inclined brace on the outside, down to a small footing
    P.cyl((0.0, 0.02, 0.72), (sgn * 0.95, 0.02, 0.05), 0.0305, seg=10, mat=mat, bevel=0.0)
    P.box_mm((sgn * 0.95 - 0.16, -0.14, 0.0), (sgn * 0.95 + 0.16, 0.18, 0.06), mat='M_Concrete', bevel=0.012)
    P.box_mm((sgn * 0.95 - 0.06, -0.04, 0.06), (sgn * 0.95 + 0.06, 0.08, 0.075), mat='M_Galvanized', bevel=0.003)
    # cable terminations: socket + turnbuckle on the run side, anchor plate on the post
    P.box_mm((-0.05, -R - 0.02, GC_CABLE_Z[0] - 0.05), (0.05, -R + 0.01, GC_CABLE_Z[-1] + 0.05), mat='M_Galvanized',
             bevel=0.006)
    for z in GC_CABLE_Z:
        xa = -sgn * 0.04
        xb = -sgn * 0.40
        P.cyl((xa, GC_CABLE_Y, z), (xb, GC_CABLE_Y, z), 0.016, seg=8, mat='M_Galvanized', bevel=0.002)
        P.cyl((xb, GC_CABLE_Y, z), (-sgn * 0.47, GC_CABLE_Y, z), 0.012, seg=8, r1=0.0095,
              mat='M_Galvanized', bevel=0.0)
        # stub sits inside the tile cable (thinner) once assembled
        P.cyl((-sgn * 0.47, GC_CABLE_Y, z), (-sgn * 0.60, GC_CABLE_Y, z), 0.0074, seg=6,
              mat='M_Galvanized', bevel=0.0, sharp=70)
    delineator_head(P, 0.0, 0.0, H + 0.024)
    P.finish()


@builder
def build_mountain_guardrail_cable():
    _guard_cable_tile('mountain_guardrail_cable', 'M_PaintedMetal_White', 'white')
    _guard_cable_tile('mountain_guardrail_cable_brown', 'M_PaintedMetal_Brown', 'brown (national-park)')


@builder
def build_mountain_guardrail_cable_end():
    _guard_cable_end('mountain_guardrail_cable_end_finish', True, 'M_PaintedMetal_White')
    _guard_cable_end('mountain_guardrail_cable_end_start', False, 'M_PaintedMetal_White')


# ======================================================================================
# 4. Delineator post + snow pole
# ======================================================================================
@builder
def build_delineator_post():
    P = Prop('delineator_post', 'mountain',
             desc='視線誘導標: white Φ60.5 post with Φ100 round reflector (amber faces Unity -X, white faces +X)',
             origin='ground, post centre', front='reflectors face along the road (Unity ±X)')
    r = 0.03025
    P.cyl((0, 0, 0), (0, 0, 1.05), r, seg=12, mat='M_PaintedMetal_White', bevel=0.003)
    post_cap(P, 0, 0, 1.05, r, 'M_PaintedMetal_White')
    # reflector housing on a short bracket
    P.box_mm((-0.012, -0.012, 1.0), (0.012, 0.012, 1.10), mat='M_Galvanized', bevel=0.002)
    zc = 1.13
    P.cyl((-0.016, 0, zc), (0.016, 0, zc), 0.064, seg=20, mat='M_PlasticWhite', bevel=0.005)
    P.cyl((0.016, 0, zc), (0.0175, 0, zc), 0.05, seg=20, mat='M_Reflector_Amber', bevel=0.0)
    P.cyl((-0.0175, 0, zc), (-0.016, 0, zc), 0.05, seg=20, mat='M_Reflector_White', bevel=0.0)
    # small reflective band on the post
    P.cyl((0, 0, 0.80), (0, 0, 0.88), r + 0.0015, seg=12, mat='M_Reflector_White', bevel=0.0, caps=False)
    P.finish()


@builder
def build_snow_pole():
    P = Prop('snow_pole', 'mountain',
             desc='Red/white striped snow pole (スノーポール) 2.8 m with a downward arrow plate (矢羽根) on top',
             origin='ground, pole centre', front='arrow plate faces along the road (Unity ±X)',
             preview=dict(extra=[('top', 60, 10, ((-0.25, -0.25, 1.9), (0.25, 0.25, 2.9)))]))
    # concrete base block
    P.box_mm((-0.14, -0.14, 0.0), (0.14, 0.14, 0.12), mat='M_Concrete', bevel=0.015)
    P.cyl((0, 0, 0.12), (0, 0, 0.16), 0.04, seg=12, mat='M_Galvanized', bevel=0.004)
    r = 0.025
    H = 2.8
    band = 0.35
    z = 0.12
    k = 0
    while z < H - 1e-6:
        z2 = min(z + band, H)
        P.cyl((0, 0, z), (0, 0, z2), r, seg=12, mat='M_PlasticRed' if k % 2 == 0 else 'M_Reflector_White',
              bevel=0.0, caps=(z2 >= H - 1e-6))
        z = z2; k += 1
    post_cap(P, 0, 0, H, r, 'M_PlasticBlack')
    # arrow plate: 0.32 wide x 0.62 tall, pointing down, plane normal along X, offset from the pole
    w, h, tip = 0.32, 0.62, 0.18
    ztop = H - 0.02
    zb = ztop - h
    out2 = [(-w / 2, zb + tip), (0.0, zb), (w / 2, zb + tip), (w / 2, ztop), (-w / 2, ztop)]   # (y, z)
    xoff = r + 0.012
    t = 0.006
    # plate body (edges) + textured faces on both sides
    P.extrude([(y, z) for (y, z) in out2], t, axis='X', offset=xoff, mat='M_PlasticWhite', cap_front=False,
              cap_back=False, bevel=0.0)
    P.ngon([(xoff + t + 0.0005, y, z) for (y, z) in out2], mat='M_Deco_SnowArrow',
           uv=UV.planar((1, 0, 0)))
    P.ngon([(xoff - 0.0005, y, z) for (y, z) in reversed(out2)], mat='M_Deco_SnowArrow',
           uv=UV.planar((-1, 0, 0)))
    for zz in (ztop - 0.08, zb + tip + 0.08):
        P.box_mm((-0.012, -0.03, zz - 0.015), (xoff, 0.03, zz + 0.015), mat='M_Galvanized', bevel=0.003)
    P.finish()


# ======================================================================================
# 5. Small bridge railing + bridge end post (親柱)
# ======================================================================================
CURB_D = 0.45
CURB_H = 0.30


def _bridge_railing(name, mat, colour):
    P = Prop(name, 'mountain', mirror_x=True,
             desc=f'Small mountain-bridge railing tile 4 m: concrete curb (地覆) + {colour} steel railing 1.1 m',
             origin='road surface at the curb road-side face, tile start (Unity X=0); tile spans X 0..4',
             front='road side = Unity +Z')
    L = 4.0
    P.prism([(0.0, 0.0), (CURB_D, 0.0), (CURB_D, CURB_H - 0.03), (CURB_D - 0.03, CURB_H), (0.03, CURB_H),
             (0.0, CURB_H - 0.03)], 0.0, L, mat='M_Concrete', bevel=0.0, sharp=30, uv=UV.box())
    yc = CURB_D * 0.5
    for x in (0.0, 2.0):
        P.box_mm((x - 0.09, yc - 0.075, CURB_H), (x + 0.09, yc + 0.075, CURB_H + 0.016), mat=mat, bevel=0.004)
        for dx in (-0.065, 0.065):
            for dy in (-0.05, 0.05):
                P.cyl((x + dx, yc + dy, CURB_H + 0.016), (x + dx, yc + dy, CURB_H + 0.036), 0.011, seg=6,
                      mat='M_Galvanized', bevel=0.0, sharp=70)
        P.box_mm((x - 0.045, yc - 0.035, CURB_H + 0.016), (x + 0.045, yc + 0.035, 1.03), mat=mat, bevel=0.006)
    for (z, r) in ((0.58, 0.0305), (0.82, 0.0305)):
        P.cyl((0.0, yc, z), (L, yc, z), r, seg=12, mat=mat, bevel=0.0, uv=UV.box())
    P.cyl((0.0, yc, 1.055), (L, yc, 1.055), 0.045, seg=14, mat=mat, bevel=0.0, uv=UV.box())
    P.note('Posts at Unity X=0 and 2; finish bridge ends with bridge_end_post.')
    P.finish()


@builder
def build_small_bridge_railing_4m():
    _bridge_railing('small_bridge_railing_4m', 'M_PaintedMetal_Vermilion', 'vermilion')
    _bridge_railing('small_bridge_railing_4m_brown', 'M_PaintedMetal_Brown', 'dark brown')


@builder
def build_bridge_end_post():
    P = Prop('bridge_end_post', 'mountain',
             desc='親柱 bridge end pillar, granite 0.45 x 0.45, 1.25 m, cast bronze name plates '
                  '(kanji 峠沢橋 faces Unity +Z, hiragana とうげさわばし faces Unity -X)',
             origin='ground, pillar centre',
             preview=dict(az=-35, el=14))
    P.box_mm((-0.29, -0.29, 0.0), (0.29, 0.29, 0.10), mat='M_Stone', bevel=0.02)
    P.box_mm((-0.225, -0.225, 0.10), (0.225, 0.225, 1.06), mat='M_Stone', bevel=0.012)
    P.box_mm((-0.265, -0.265, 1.06), (0.265, 0.265, 1.14), mat='M_Stone', bevel=0.015)
    P.lathe([(0.375, 1.14), (0.21, 1.25), (0.0, 1.27)], seg=4, start_angle=45, mat='M_Stone', cap_bottom=True,
            bevel=0.0, sharp=30, uv=UV.box())
    # plates with raised stone frame. front (-Y) kanji; side (+X Blender = Unity -X) hiragana
    pw, ph, zc = 0.24, 0.56, 0.62
    face = -0.225

    def frame_and_plate(axis_sign_face, rect):
        # face plane: front y=-0.225 (normal -Y) or side x=+0.225 (normal +X)
        fw = 0.03
        if axis_sign_face == 'front':
            def Q(u, z, d):
                return (u, face - d, z)
            n = (0, -1, 0)
        else:
            def Q(u, z, d):
                return (-face + d, u, z)
            n = (1, 0, 0)
        # frame
        for (u0, u1, z0, z1) in ((-pw / 2 - fw, pw / 2 + fw, zc + ph / 2, zc + ph / 2 + fw),
                                 (-pw / 2 - fw, pw / 2 + fw, zc - ph / 2 - fw, zc - ph / 2),
                                 (-pw / 2 - fw, -pw / 2, zc - ph / 2, zc + ph / 2),
                                 (pw / 2, pw / 2 + fw, zc - ph / 2, zc + ph / 2)):
            a = Q(u0, z0, 0.0); b = Q(u1, z1, 0.018)
            P.box_mm([min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)], mat='M_Stone',
                     bevel=0.005)
        # bronze plate (slightly proud of the face, below the frame)
        a = Q(-pw / 2, zc - ph / 2, 0.0); b = Q(pw / 2, zc + ph / 2, 0.006)
        P.box_mm([min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)], mat='M_Brass', bevel=0.0)
        if axis_sign_face == 'front':
            pts = [Q(-pw / 2, zc - ph / 2, 0.0065), Q(pw / 2, zc - ph / 2, 0.0065), Q(pw / 2, zc + ph / 2, 0.0065),
                   Q(-pw / 2, zc + ph / 2, 0.0065)]
        else:
            # viewer at +X looking -X: right = +Y? right = up x n = Z x X = +Y
            pts = [Q(-pw / 2, zc - ph / 2, 0.0065), Q(pw / 2, zc - ph / 2, 0.0065), Q(pw / 2, zc + ph / 2, 0.0065),
                   Q(-pw / 2, zc + ph / 2, 0.0065)]
        P.ngon(pts, mat='M_Deco_BridgePlate', uv=UV.planar(n, rect=rect))
    frame_and_plate('front', (0.0, 0.0, 0.5, 1.0))
    frame_and_plate('side', (0.5, 0.0, 1.0, 1.0))
    P.finish()


# ======================================================================================
# 6. Shrine set
# ======================================================================================
def _kasagi_z(x, half, rise):
    return rise * (abs(x) / half) ** 2.6


@builder
def build_torii_stone():
    P = Prop('torii_stone', 'urban',
             desc='Stone myōjin torii, 4.0 m to the kasagi top, inner span 2.6 m, plaque 山神社, shimenawa + shide',
             origin='ground, centre between the pillars', front='plaque faces Unity +Z (approach side)',
             preview=dict(az=25, el=10, extra=[('top', 25, 8, ((-2.4, -0.3, 2.4), (2.4, 0.3, 4.1)))]))
    lean = math.degrees(math.atan(0.08 / 3.4))
    for sx in (-1, 1):
        xb = sx * 1.5
        # base stone + rounded collar (饅頭)
        P.box_mm((xb - 0.31, -0.31, 0.0), (xb + 0.31, 0.31, 0.20), mat='M_Stone', bevel=0.025)
        P.lathe([(0.27, 0.20), (0.27, 0.24), (0.24, 0.31), (0.2, 0.34)], seg=20, loc=(xb, 0, 0), mat='M_Stone',
                bevel=0.0, cap_bottom=False, cap_top=False, sharp=40)
        # pillar (slight taper + inward lean)
        P.lathe([(0.2, 0.0), (0.172, 3.42)], seg=20, loc=(xb, 0, 0.2), rot=(0, -sx * lean, 0), mat='M_Stone',
                bevel=0.0, cap_bottom=False, cap_top=True, uv=UV.box())
    # nuki (tie beam) passing through the pillars
    P.box_mm((-1.86, -0.065, 2.78), (1.86, 0.065, 2.94), mat='M_Stone', bevel=0.02)
    # kusabi wedges outside the pillars
    for sx in (-1, 1):
        xp = sx * (1.5 - 3.0 / 3.4 * 0.08 * 2.9 / 3.0)
        P.box_mm((xp + sx * 0.17 - 0.03, -0.075, 2.94), (xp + sx * 0.17 + 0.03, 0.075, 2.99), mat='M_Stone',
                 bevel=0.008)
    # gakuzuka strut + plaque
    P.box_mm((-0.08, -0.05, 2.94), (0.08, 0.05, 3.6), mat='M_Stone', bevel=0.012)
    P.box_mm((-0.21, -0.115, 2.97), (0.21, -0.05, 3.585), mat='M_Stone_Dark', bevel=0.012)
    P.ngon([(-0.195, -0.1158, 2.985), (0.195, -0.1158, 2.985), (0.195, -0.1158, 3.57), (-0.195, -0.1158, 3.57)],
           mat='M_Deco_ShrinePlaque', uv=UV.planar((0, -1, 0)))
    # shimaki + kasagi with upturned ends (反り)
    half, rise = 2.3, 0.17
    xs = [-half + 2 * half * i / 24 for i in range(25)]
    path_k = [Vector((x, 0, 3.75 + _kasagi_z(x, half, rise))) for x in xs]
    prof_k = [(-0.17, 0.0), (0.17, 0.0), (0.17, 0.2), (0.15, 0.25), (-0.15, 0.25), (-0.17, 0.2)]
    P.sweep(path_k, prof_k, mat='M_Stone', bevel=0.012, seg=1, sharp=30, uv=UV.box())
    hs = 2.08
    xs2 = [-hs + 2 * hs * i / 20 for i in range(21)]
    path_s = [Vector((x, 0, 3.6 + _kasagi_z(x, half, rise))) for x in xs2]
    prof_s = [(-0.13, 0.0), (0.13, 0.0), (0.13, 0.15), (-0.13, 0.15)]
    P.sweep(path_s, prof_s, mat='M_Stone', bevel=0.012, seg=1, sharp=30, uv=UV.box())
    # shimenawa (straw rope, thicker in the middle) hung under the nuki between the pillars
    xr = 1.32
    pts = [Vector((-xr + 2 * xr * i / 16, 0.0, 2.70 - 0.2 * (1 - ((-1 + 2 * i / 16)) ** 2))) for i in range(17)]
    scales = [0.55 + 0.45 * (1 - (-1 + 2 * i / 16) ** 2) for i in range(17)]
    P.sweep(pts, circle2d(0.06, 10), mat='M_Rope', scales=scales, bevel=0.0, sharp=60, uv=UV.box())
    for xi in (-0.8, -0.27, 0.27, 0.8):
        t = (xi + xr) / (2 * xr)
        zr = 2.70 - 0.2 * (1 - (-1 + 2 * t) ** 2) - 0.05
        # zigzag paper shide: 4 steps
        for k in range(4):
            dx = (0.0 if k % 2 == 0 else 0.035)
            P.box_mm((xi + dx - 0.022, -0.004, zr - 0.075 * (k + 1)), (xi + dx + 0.022, 0.004, zr - 0.075 * k),
                     mat='M_Paper', bevel=0.0)
    P.finish()


@builder
def build_toro_stone_lantern():
    P = Prop('toro_stone_lantern', 'urban',
             desc='Kasuga-style stone lantern (春日灯籠) 2.0 m: hex base, round pole, chūdai, hibukuro, curled roof, hōju',
             origin='ground, lantern axis', front='fire-box openings face Unity ±Z',
             preview=dict(extra=[('detail', 30, 15, ((-0.45, -0.45, 1.0), (0.45, 0.45, 2.0)))]))
    st = 'M_Stone'
    # base (基礎) two tiers, hexagonal
    P.lathe([(0.38, 0.0), (0.38, 0.10), (0.35, 0.13), (0.0, 0.13)], seg=6, mat=st, bevel=0.012, sharp=30)
    P.lathe([(0.28, 0.13), (0.28, 0.17), (0.20, 0.24), (0.15, 0.25), (0.0, 0.25)], seg=6, mat=st, bevel=0.008,
            sharp=30)
    # pole (竿) with a node ring (節)
    P.lathe([(0.115, 0.24), (0.105, 0.92)], seg=16, mat=st, bevel=0.0, cap_bottom=False, cap_top=False)
    P.lathe([(0.112, 0.56), (0.13, 0.575), (0.13, 0.605), (0.112, 0.62)], seg=16, mat=st, bevel=0.0,
            cap_bottom=False, cap_top=False, sharp=40)
    # chūdai (中台): flared hexagon
    P.lathe([(0.0, 0.91), (0.16, 0.91), (0.31, 1.03), (0.31, 1.10), (0.0, 1.10)], seg=6, mat=st, bevel=0.01,
            sharp=30)
    # hibukuro (火袋): hex box with corner posts, openings front/back (±Y faces)
    zb, zt = 1.10, 1.46
    P.lathe([(0.0, zb), (0.24, zb), (0.24, zb + 0.04), (0.0, zb + 0.04)], seg=6, mat=st, bevel=0.006, sharp=30)
    P.lathe([(0.0, zt - 0.04), (0.24, zt - 0.04), (0.24, zt), (0.0, zt)], seg=6, mat=st, bevel=0.006, sharp=30)
    R = 0.215
    corners = [Vector((R * math.cos(math.radians(60 * i)), R * math.sin(math.radians(60 * i)), 0)) for i in range(6)]
    for i in range(6):
        c = corners[i]
        P.cyl((c.x, c.y, zb + 0.04), (c.x, c.y, zt - 0.04), 0.035, seg=6, mat=st, bevel=0.0, sharp=70)
    for i in range(6):
        a = corners[i]; b = corners[(i + 1) % 6]
        mid = (a + b) / 2
        ang = math.degrees(math.atan2(mid.y, mid.x))
        if abs(abs(ang) - 90) < 1:      # open faces toward ±Y
            continue
        side = (b - a).length
        P.box((0.035, side - 0.04, zt - zb - 0.08), (mid.x * 0.97, mid.y * 0.97, (zb + zt) / 2),
              rot=(0, 0, ang), mat=st, bevel=0.004)
        # carved round window (moon) as a dark disc on the ±X-ish faces
        nrm = mid.normalized()
        p0 = mid * 0.97 + nrm * 0.0175 + Vector((0, 0, (zb + zt) / 2))
        P.cyl(p0, p0 + nrm * 0.004, 0.055, seg=16, mat='M_Stone_Dark', bevel=0.0)
    # dark interior core (reads as shadow through the openings)
    P.lathe([(0.0, zb + 0.04), (0.11, zb + 0.04), (0.11, zt - 0.04), (0.0, zt - 0.04)], seg=6, mat='M_Stone_Dark',
            bevel=0.0, sharp=30)
    # roof (笠) with curled corners (蕨手)
    P.lathe([(0.0, 1.46), (0.44, 1.46), (0.46, 1.50), (0.30, 1.60), (0.16, 1.68), (0.10, 1.71), (0.0, 1.71)],
            seg=6, mat=st, bevel=0.01, sharp=25)
    for i in range(6):
        a = math.radians(60 * i)
        rd = Vector((math.cos(a), math.sin(a), 0))
        curl = [(0.40, 1.505), (0.455, 1.515), (0.495, 1.545), (0.505, 1.585), (0.49, 1.615), (0.465, 1.62)]
        path = [rd * r + Vector((0, 0, z)) for (r, z) in curl]
        P.sweep(path, circle2d(0.032, 8), mat=st, scales=[1.0, 0.95, 0.85, 0.7, 0.55, 0.45], bevel=0.0, sharp=55)
    # ukebana + hōju (jewel)
    P.lathe([(0.0, 1.70), (0.07, 1.70), (0.105, 1.76), (0.09, 1.79), (0.0, 1.79)], seg=12, mat=st, bevel=0.0,
            sharp=40)
    P.lathe([(0.0, 1.79), (0.06, 1.80), (0.095, 1.85), (0.09, 1.90), (0.06, 1.95), (0.025, 1.985), (0.0, 2.0)],
            seg=12, mat=st, bevel=0.0, sharp=60)
    P.finish()


@builder
def build_saisen_box():
    P = Prop('saisen_box', 'urban',
             desc='Wooden offering box (賽銭箱) 0.94 x 0.58 x 0.6 m, slatted top, brass corner fittings, 賽銭 front plate',
             origin='ground, box centre', front='front plate faces Unity +Z')
    W, D, H = 0.90, 0.54, 0.56
    wd = 'M_Wood_Dark'
    P.box_mm((-0.47, -0.29, 0.0), (0.47, 0.29, 0.06), mat=wd, bevel=0.008)
    t = 0.035
    # walls
    P.box_mm((-W / 2, -D / 2, 0.06), (W / 2, -D / 2 + t, H), mat=wd, bevel=0.006)
    P.box_mm((-W / 2, D / 2 - t, 0.06), (W / 2, D / 2, H), mat=wd, bevel=0.006)
    P.box_mm((-W / 2, -D / 2 + t, 0.06), (-W / 2 + t, D / 2 - t, H), mat=wd, bevel=0.006)
    P.box_mm((W / 2 - t, -D / 2 + t, 0.06), (W / 2, D / 2 - t, H), mat=wd, bevel=0.006)
    # top rim
    rim = 0.05
    P.box_mm((-W / 2 - 0.01, -D / 2 - 0.01, H), (W / 2 + 0.01, -D / 2 + rim, H + 0.035), mat=wd, bevel=0.006)
    P.box_mm((-W / 2 - 0.01, D / 2 - rim, H), (W / 2 + 0.01, D / 2 + 0.01, H + 0.035), mat=wd, bevel=0.006)
    P.box_mm((-W / 2 - 0.01, -D / 2 + rim, H), (-W / 2 + rim, D / 2 - rim, H + 0.035), mat=wd, bevel=0.006)
    P.box_mm((W / 2 - rim, -D / 2 + rim, H), (W / 2 + 0.01, D / 2 - rim, H + 0.035), mat=wd, bevel=0.006)
    # dark interior + triangular slats along X
    P.box_mm((-W / 2 + t, -D / 2 + t, 0.30), (W / 2 - t, D / 2 - t, 0.31), mat='M_PlasticBlack', bevel=0.0)
    ys = [-D / 2 + rim + 0.03 + i * 0.062 for i in range(7)]
    for y in ys:
        P.prism([(y - 0.02, H - 0.03), (y + 0.02, H - 0.03), (y, H + 0.025)], -W / 2 + rim, W / 2 - rim, mat='M_Wood',
                bevel=0.0, sharp=30)
    # front plate (proud) with 賽銭
    P.box_mm((-0.30, -D / 2 - 0.012, 0.20), (0.30, -D / 2, 0.47), mat=wd, bevel=0.004)
    P.ngon([(-0.29, -D / 2 - 0.0125, 0.21), (0.29, -D / 2 - 0.0125, 0.21), (0.29, -D / 2 - 0.0125, 0.46),
            (-0.29, -D / 2 - 0.0125, 0.46)], mat='M_Deco_Saisen', uv=UV.planar((0, -1, 0)))
    # brass corner fittings (L plates) top and bottom of each vertical corner + top edge strip
    f = 0.09
    for sx in (-1, 1):
        for sy in (-1, 1):
            for (z0, z1) in ((0.07, 0.07 + f), (H - f, H)):
                y_out = sy * (D / 2 + 0.003)
                x_out = sx * (W / 2 + 0.003)
                # Y-facing plate (on front/back wall, near the corner)
                P.box_mm((min(sx * (W / 2 - f), x_out), min(sy * D / 2, y_out), z0),
                         (max(sx * (W / 2 - f), x_out), max(sy * D / 2, y_out), z1), mat='M_Brass', bevel=0.0)
                # X-facing plate (on side wall, near the corner)
                P.box_mm((min(sx * W / 2, x_out), min(sy * (D / 2 - f), y_out), z0),
                         (max(sx * W / 2, x_out), max(sy * (D / 2 - f), y_out), z1), mat='M_Brass', bevel=0.0)
    P.box_mm((-W / 2 - 0.012, -D / 2 - 0.014, H + 0.03), (W / 2 + 0.012, -D / 2 + 0.01, H + 0.04), mat='M_Brass',
             bevel=0.0)
    P.finish()


@builder
def build_hokora_small():
    P = Prop('hokora_small', 'urban',
             desc='Small roadside shrine (祠): stone base, wooden body with lattice doors, copper gabled roof, '
                  'chigi/katsuogi, mini shimenawa',
             origin='ground, base centre', front='doors face Unity +Z',
             preview=dict(az=30, el=14))
    # stone base, two tiers
    P.box_mm((-0.45, -0.35, 0.0), (0.45, 0.35, 0.20), mat='M_Stone', bevel=0.02)
    P.box_mm((-0.37, -0.29, 0.20), (0.37, 0.29, 0.34), mat='M_Stone', bevel=0.015)
    # wooden floor (浜床) and body
    P.box_mm((-0.33, -0.27, 0.34), (0.33, 0.25, 0.38), mat='M_Wood_Dark', bevel=0.006)
    bw, bd = 0.26, 0.19        # half sizes
    z0, z1 = 0.38, 0.84
    P.box_mm((-bw, -bd, z0), (bw, bd, z1), mat='M_Wood', bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.box_mm((sx * bw - 0.025, sy * bd - 0.025, z0), (sx * bw + 0.025, sy * bd + 0.025, z1), mat='M_Wood_Dark',
                     bevel=0.005)
    # lattice doors on the front
    yf = -bd - 0.003
    P.box_mm((-0.2, yf - 0.002, z0 + 0.05), (0.2, yf, z1 - 0.05), mat='M_PlasticBlack', bevel=0.0)
    for i in range(7):
        x = -0.18 + i * 0.06
        P.box_mm((x - 0.008, yf - 0.018, z0 + 0.05), (x + 0.008, yf - 0.002, z1 - 0.05), mat='M_Wood_Dark', bevel=0.0)
    for z in (z0 + 0.05, z0 + 0.21, z0 + 0.37):
        P.box_mm((-0.21, yf - 0.02, z - 0.012), (0.21, yf - 0.002, z + 0.012), mat='M_Wood_Dark', bevel=0.0)
    P.box_mm((-0.004, yf - 0.024, z0 + 0.05), (0.004, yf - 0.002, z1 - 0.05), mat='M_Wood_Dark', bevel=0.0)
    # beams under the roof
    P.box_mm((-0.33, -bd - 0.03, z1), (0.33, bd + 0.03, z1 + 0.05), mat='M_Wood_Dark', bevel=0.006)
    # gabled copper roof, ridge along X (平入): eaves front/back
    zr, ze = 1.17, 0.90
    hy = 0.40
    hx = 0.45
    th = 0.035
    for sy in (-1, 1):
        a0 = Vector((-hx, 0.0, zr)); a1 = Vector((hx, 0.0, zr))
        b0 = Vector((-hx, sy * hy, ze)); b1 = Vector((hx, sy * hy, ze))
        dn = Vector((0, 0, -th))
        verts = [a0, a1, b1, b0, a0 + dn, a1 + dn, b1 + dn, b0 + dn]
        faces = [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]]
        poly_closed(P, verts, faces, 'M_CopperRoof', bevel=0.006, seg=1, uv=UV.box())
    # gable boards (破風) and ridge cap
    for sx in (-1, 1):
        x = sx * (hx + 0.005)
        verts = []
        for (y, z) in ((0.0, zr + 0.03), (hy + 0.02, ze - 0.03), (hy + 0.02, ze - 0.07), (0.0, zr - 0.02),
                       (-hy - 0.02, ze - 0.07), (-hy - 0.02, ze - 0.03)):
            verts.append((x, y, z))
        P.extrude([(v[1], v[2]) for v in verts], 0.02, axis='X', offset=x - 0.01, mat='M_Wood_Dark', bevel=0.004)
        # chigi (crossed boards) at the gable ends
        for sy in (-1, 1):
            p0 = Vector((x, sy * 0.06, zr - 0.04)); p1 = Vector((x, -sy * 0.12, zr + 0.16))
            P.sweep([p0, p1], rect2d(0.022, 0.05), mat='M_Wood_Dark', bevel=0.0, sharp=30)
    P.box_mm((-hx - 0.02, -0.05, zr - 0.01), (hx + 0.02, 0.05, zr + 0.045), mat='M_CopperRoof', bevel=0.008)
    for x in (-0.2, 0.0, 0.2):
        P.cyl((x, -0.07, zr + 0.075), (x, 0.07, zr + 0.075), 0.03, seg=10, mat='M_Wood_Dark', bevel=0.004)
    # small shimenawa + shide in front of the doors
    pts = [Vector((-0.28 + 0.56 * i / 10, yf - 0.06, z1 - 0.02 - 0.05 * (1 - (-1 + 2 * i / 10) ** 2))) for i in range(11)]
    P.sweep(pts, circle2d(0.018, 8), mat='M_Rope', bevel=0.0, sharp=60)
    for xi in (-0.12, 0.12):
        zr0 = z1 - 0.02 - 0.05 * (1 - ((xi + 0.28) / 0.28 - 1) ** 2) - 0.015
        for k in range(3):
            dx = 0.0 if k % 2 == 0 else 0.016
            P.box_mm((xi + dx - 0.012, yf - 0.064, zr0 - 0.04 * (k + 1)), (xi + dx + 0.012, yf - 0.058, zr0 - 0.04 * k),
                     mat='M_Paper', bevel=0.0)
    P.finish()
