"""URBAN set A: utility poles, signals, street lamps, guardrails, railings, bollards, cones,
barriers, road signs, manhole, drain grate, kerb, hydrant sign.
Build:  blender -b -P Tools/blender/props/build_props.py -- props_urban_a [builder ...]"""
import math
from mathutils import Vector
from propkit import (Prop, UV, builder, define_mat, circle2d, rect2d, rounded_rect2d, fillet, thicken2d,
                     arc_points)

define_mat('M_Deco_PoleAd', c='#F4F2EA', r=0.5, tex='prop_pole_ad_albedo.png')
define_mat('M_Deco_StreetName', c='#164AA0', r=0.4, tex='prop_street_name_albedo.png')
define_mat('M_Deco_HydrantSign', c='#D6221C', r=0.4, tex='prop_hydrant_sign_albedo.png')
define_mat('M_Deco_Manhole', c='#4A4A48', r=0.6, m=0.6, tex='prop_manhole_albedo.png', ntex='prop_manhole_normal.png')
define_mat('M_EmissiveSignal_PedRed', c='#FF3424', r=0.3, e=4.0, tex='prop_ped_signal_albedo.png')
define_mat('M_EmissiveSignal_PedGreen', c='#00DCAA', r=0.3, e=4.0, tex='prop_ped_signal_albedo.png')


# ======================================================================================
# Traffic cone (Japanese 700 mm red/white "カラーコーン")
# ======================================================================================
@builder
def build_traffic_cone():
    P = Prop('traffic_cone', 'urban', desc='Japanese 700 mm traffic cone, red with white reflective bands')
    # square base 380 x 380 x 40 with rounded corners
    P.extrude(rounded_rect2d(0.38, 0.38, 0.05, 3), 0.04, axis='Z', mat='M_PlasticRed', bevel=0.008, seg=2)
    # cone body: r 0.150 @ 0.04 -> r 0.024 @ 0.70; bands split into separate parts
    z0, z1, r0, r1 = 0.04, 0.70, 0.150, 0.024

    def rad(z):
        return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    cuts = [(z0, 'M_PlasticRed'), (0.25, 'M_Reflector_White'), (0.35, 'M_PlasticRed'),
            (0.46, 'M_Reflector_White'), (0.54, 'M_PlasticRed'), (z1, None)]
    for (za, m), (zb, _) in zip(cuts[:-1], cuts[1:]):
        prof = [(rad(za), za), (rad(zb), zb)]
        if zb == z1:
            prof = [(rad(za), za), (rad(zb), zb), (r1 - 0.006, zb + 0.006), (0.0, zb + 0.006)]
        P.lathe(prof, seg=20, mat=m, cap_bottom=False, cap_top=False, bevel=0.0, sharp=50,
                uv=UV.cyl((0, 0, 0), (0, 0, 1), norm=True))
    # small flange where cone meets base
    P.lathe([(0.17, 0.04), (0.165, 0.055), (0.15, 0.06)], seg=20, mat='M_PlasticRed', cap_bottom=False, cap_top=False,
            bevel=0.0)
    P.finish()


# ======================================================================================
# W-beam guardrail (Japanese Gr type, white painted, round pipe posts every 2 m)
# ======================================================================================
def _wbeam_profile():
    """W-beam cross section (s = toward road = Blender -Y handled by caller, t = up), 350 x 85 mm."""
    pts = [(0.000, 0.175), (0.012, 0.160), (0.085, 0.118), (0.085, 0.068), (0.022, 0.022), (0.022, -0.022),
           (0.085, -0.068), (0.085, -0.118), (0.012, -0.160), (0.000, -0.175)]
    sm = fillet(pts, 0.03, 2)
    return [(p.x, p.y) for p in sm]


BEAM_Z = 0.60      # beam centre height
POST_R = 0.0699    # 139.8 mm pipe
BEAM_Y0 = -(POST_R + 0.045)   # back plane of the beam (bracket gap), toward road is -Y


def _guard_post(P, x, h=0.80):
    P.cyl((x, 0, 0), (x, 0, h), POST_R, seg=16, mat='M_PaintedMetal_White', bevel=0.006)
    P.cyl((x, 0, h), (x, 0, h + 0.014), POST_R + 0.004, seg=16, mat='M_PaintedMetal_White', bevel=0.005)
    # bracket (post -> beam)
    P.box_mm((x - 0.04, BEAM_Y0 - 0.002, BEAM_Z - 0.09), (x + 0.04, -POST_R + 0.012, BEAM_Z + 0.09),
             mat='M_PaintedMetal_White', bevel=0.006)
    # bolt head on beam face (in the valley)
    P.cyl((x, BEAM_Y0 - 0.022, BEAM_Z), (x, BEAM_Y0 - 0.040, BEAM_Z), 0.016, seg=8, mat='M_Galvanized', bevel=0.003)


def _wbeam(P, x0, x1):
    prof = _wbeam_profile()
    # outline in (y, z): y = BEAM_Y0 - d (d = depth toward the road)
    outline = thicken2d([(BEAM_Y0 - d, BEAM_Z + t) for (d, t) in prof], 0.006)
    P.prism(outline, x0, x1, mat='M_PaintedMetal_White', bevel=0.0, sharp=35,
            uv=UV.box())


def _delineator(P, x):
    """Guardrail delineator: round reflector on a stem at the post top, facing along the road."""
    top = 0.80 + 0.014
    P.box_mm((x - 0.008, -0.02, top), (x + 0.008, 0.02, top + 0.10), mat='M_Galvanized', bevel=0.002)
    P.cyl((x - 0.012, 0, top + 0.17), (x + 0.012, 0, top + 0.17), 0.055, seg=16, mat='M_PlasticWhite', bevel=0.004)
    P.cyl((x - 0.0135, 0, top + 0.17), (x - 0.012, 0, top + 0.17), 0.045, seg=16, mat='M_Reflector_Amber', bevel=0.0,
          caps=True)
    P.cyl((x + 0.012, 0, top + 0.17), (x + 0.0135, 0, top + 0.17), 0.045, seg=16, mat='M_Reflector_White', bevel=0.0,
          caps=True)


@builder
def build_guardrail_wbeam_4m():
    P = Prop('guardrail_wbeam_4m', 'urban', mirror_x=True,
             desc='Japanese W-beam guardrail tile, 4 m, white, round posts every 2 m (posts at X=0 and X=2)',
             origin='ground, at the start post centre (Unity X=0); tile spans Unity X 0..4')
    _wbeam(P, 0.0, 4.0)
    for x in (0.0, 2.0):
        _guard_post(P, x)
    # splice bolts at x=0 overlap (4 on crowns)
    for (dz, dd) in ((0.093, 0.085), (-0.093, 0.085)):
        for dx in (0.06, 0.14):
            P.cyl((dx, BEAM_Y0 - dd - 0.003, BEAM_Z + dz), (dx, BEAM_Y0 - dd - 0.016, BEAM_Z + dz), 0.011, seg=8,
                  mat='M_Galvanized', bevel=0.002)
    _delineator(P, 0.0)
    P.note('Tile: posts at Unity X=0 and X=2; next tile starts at X=4. Close a run with guardrail_end_finish at X=4N '
           'and guardrail_end_start at X=0.')
    P.finish()


def _guardrail_end(name, finish):
    P = Prop(name, 'urban', mirror_x=True,
             desc='W-beam guardrail end wing (袖ビーム) curving away from the road' +
                  (' + end post' if finish else ''),
             origin='ground at the joint (Unity X=0)')
    prof = _wbeam_profile()
    # path: straight 0.25 m then 90deg arc of R=0.35 turning to +Y (away from road), in builder x
    sgn = 1.0 if finish else -1.0
    R = 0.35
    path = [Vector((0, BEAM_Y0, BEAM_Z))]
    straight = 0.30
    path.append(Vector((sgn * straight, BEAM_Y0, BEAM_Z)))
    cx, cy = sgn * straight, BEAM_Y0 + R
    for i in range(1, 9):
        a = math.radians(90 * i / 8)
        path.append(Vector((cx + sgn * R * math.sin(a), cy - R * math.cos(a), BEAM_Z)))
    # profile (s, t): s = side = up x tangent. finish (tangent +X): side=+Y, road is -Y -> s=-(d)
    #                 start (tangent -X): side = -Y -> road -Y -> s=+d
    outline = thicken2d([((-d if finish else d), t) for (d, t) in prof], 0.006)
    P.sweep(path, outline, closed=True, caps=True, mat='M_PaintedMetal_White', bevel=0.0, sharp=35)
    if finish:
        _guard_post(P, 0.0)
        _delineator(P, 0.0)
    P.finish()


@builder
def build_guardrail_end():
    _guardrail_end('guardrail_end_start', False)
    _guardrail_end('guardrail_end_finish', True)


# ======================================================================================
# Utility pole (Japanese concrete distribution pole, 12 m above ground)
# ======================================================================================
POLE_H = 12.0
POLE_R0 = 0.175   # 350 mm at ground
POLE_R1 = 0.095   # 190 mm at top


def pole_r(z):
    return POLE_R0 + (POLE_R1 - POLE_R0) * z / POLE_H


def _pin_insulator(P, x, y, z):
    """6.6 kV pin insulator on a steel pin, base at z. Returns wire anchor (top groove)."""
    P.cyl((x, y, z), (x, y, z + 0.05), 0.012, seg=8, mat='M_Galvanized', bevel=0.0)
    prof = [(0.030, z + 0.04), (0.068, z + 0.075), (0.066, z + 0.090), (0.046, z + 0.098), (0.050, z + 0.118),
            (0.040, z + 0.128), (0.034, z + 0.140), (0.040, z + 0.150), (0.030, z + 0.165), (0.0, z + 0.168)]
    P.lathe(prof, seg=12, loc=(x, y, 0), mat='M_Porcelain', bevel=0.0, sharp=50)
    return (x, y, z + 0.145)


def _spool(P, x, y, z, axis='Y'):
    """Low-voltage spool (rack) insulator; returns anchor point."""
    P.lathe([(0.042, -0.045), (0.042, -0.035), (0.03, -0.028), (0.03, 0.028), (0.042, 0.035), (0.042, 0.045)],
            seg=12, loc=(x, y, z), rot=(90, 0, 0) if axis == 'Y' else (0, 0, 0), mat='M_Porcelain', bevel=0.0,
            sharp=50)
    return (x, y, z)


def _utility_pole(name, with_transformer):
    P = Prop(name, 'urban',
             desc='Japanese concrete distribution pole, 12 m above ground' +
                  (', pole-top transformer' if with_transformer else ''),
             origin='ground, pole centre', front='road side = Unity +Z; wires run along Unity X',
             preview=dict(extra=[('top', 35, 12, ((-0.9, -1.0, 7.4), (0.9, 1.0, 12.1))),
                                 ('base', 35, 12, ((-0.4, -0.4, 0), (0.4, 0.4, 3.8)))]))
    # --- shaft (tapered, 16 seg) + top cap
    P.cyl((0, 0, 0), (0, 0, POLE_H), POLE_R0, POLE_R1, seg=16, mat='M_Concrete', bevel=0.0, caps=False,
          uv=UV.box())
    P.lathe([(POLE_R1 + 0.005, POLE_H - 0.02), (POLE_R1 + 0.005, POLE_H + 0.02), (0.05, POLE_H + 0.07),
             (0.0, POLE_H + 0.08)], seg=16, mat='M_Concrete_Dark', bevel=0.0)
    # --- guard sleeve (yellow/black tiger stripes) 0..1.8 m
    rs = lambda z: pole_r(z) + 0.006
    P.lathe([(rs(0.0), 0.0), (rs(1.8), 1.8)], seg=16, mat='M_Deco_HazardStripe', cap_bottom=False, cap_top=False,
            bevel=0.0, uv=UV.scaled(UV.cyl((0, 0, 0), (0, 0, 1), norm=True, v_norm=False), 2.0, 1 / 0.5))
    P.lathe([(rs(1.8) + 0.004, 1.79), (rs(1.83) + 0.004, 1.83)], seg=16, mat='M_PlasticBlack', cap_bottom=True,
            cap_top=True, bevel=0.0)
    # --- wrap advertisement 2.1..3.6 m facing road (-Y)
    ra = pole_r(2.85) + 0.008
    P.lathe([(pole_r(2.1) + 0.008, 2.1), (pole_r(3.6) + 0.008, 3.6)], seg=6, start_angle=-90 - 60, sweep=120,
            mat='M_Deco_PoleAd', cap_bottom=False, cap_top=False, bevel=0.0, sharp=80,
            uv=UV.planar((0, -1, 0)))
    # ad bands (steel straps)
    for z in (2.12, 3.58):
        P.lathe([(pole_r(z) + 0.011, z - 0.012), (pole_r(z) + 0.011, z + 0.012)], seg=16, mat='M_Galvanized',
                bevel=0.0)
    # --- step bolts, 2.6..10.4 m, alternating +-X (protrude 0.22 m)
    z = 2.6; i = 0
    while z < 10.5:
        s = 1 if i % 2 == 0 else -1
        r = pole_r(z)
        P.cyl((s * (r - 0.02), 0, z), (s * (r + 0.20), 0, z), 0.011, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70)
        P.cyl((s * (r + 0.20), 0, z), (s * (r + 0.20), 0, z + 0.045), 0.011, seg=6, mat='M_Galvanized', bevel=0.0,
              sharp=70)
        z += 0.45; i += 1
    anchors = []
    # --- HV crossarm (腕金) along Y on the +X face, z = 11.55
    za = 11.55
    xa = pole_r(za) + 0.0375 + 0.025
    P.box_mm((xa - 0.0375, -0.90, za - 0.0375), (xa + 0.0375, 0.90, za + 0.0375), mat='M_Galvanized', bevel=0.006)
    P.box_mm((pole_r(za) - 0.01, -0.06, za - 0.06), (xa - 0.0375, 0.06, za + 0.06), mat='M_Galvanized', bevel=0.004)
    # arm ties (braces)
    for sy in (-1, 1):
        P.cyl((xa, sy * 0.55, za - 0.03), (pole_r(za - 0.6) + 0.01, sy * 0.02, za - 0.6), 0.012, seg=6,
              mat='M_Galvanized', bevel=0.0, sharp=70)
    for y in (-0.72, -0.26, 0.72):
        anchors.append(_pin_insulator(P, xa, y, za + 0.0375))
    if with_transformer:
        # second arm with cutout switches (高圧カットアウト) at 10.85
        zc = 10.85
        xc = pole_r(zc) + 0.0375 + 0.025
        P.box_mm((xc - 0.0375, -0.75, zc - 0.0375), (xc + 0.0375, 0.75, zc + 0.0375), mat='M_Galvanized', bevel=0.006)
        for y in (-0.55, 0.0, 0.55):
            if abs(y) < 0.01:
                y = -0.25
            P.box_mm((xc - 0.05, y - 0.045, zc - 0.33), (xc + 0.05, y + 0.045, zc - 0.04), mat='M_Porcelain',
                     bevel=0.01)
            P.box_mm((xc - 0.052, y - 0.047, zc - 0.25), (xc + 0.052, y + 0.047, zc - 0.20), mat='M_PlasticBlack',
                     bevel=0.004)
        # transformer can (柱上変圧器) on the road side (-Y), 9.0..9.95 m
        zt0, zt1 = 9.0, 9.95
        rt = 0.26
        yt = -(pole_r(zt1) + 0.10 + rt)
        P.lathe([(rt, zt0 + 0.03), (rt, zt1 - 0.03), (rt - 0.02, zt1), (rt - 0.05, zt1 + 0.03), (0.0, zt1 + 0.035)],
                seg=20, loc=(0, yt, 0), mat='M_PaintedMetal_LightGray', bevel=0.0)
        P.lathe([(rt - 0.04, zt0 - 0.03), (rt, zt0 + 0.03)], seg=20, loc=(0, yt, 0), mat='M_PaintedMetal_LightGray',
                bevel=0.0)
        # cooling fins (radiator ribs)
        for k in range(8):
            a = math.radians(90 + 45 + k * 13)
            fx, fy = math.cos(a) * (rt + 0.02), yt + math.sin(a) * (rt + 0.02)
            P.box((0.012, 0.05, 0.62), (fx, fy, (zt0 + zt1) / 2 - 0.05), rot=(0, 0, math.degrees(a)),
                  mat='M_PaintedMetal_LightGray', bevel=0.0)
        # hanger bands + bracket
        for z in (zt0 + 0.2, zt1 - 0.25):
            P.box_mm((-0.06, yt + rt - 0.02, z - 0.03), (0.06, -pole_r(z) + 0.01, z + 0.03), mat='M_Galvanized',
                     bevel=0.004)
        # bushings + drop leads to cutouts
        for k, bx in enumerate((-0.12, 0.0, 0.12)):
            bz = zt1 + 0.03
            P.lathe([(0.03, 0), (0.03, 0.04), (0.04, 0.05), (0.025, 0.07), (0.035, 0.08), (0.02, 0.11), (0, 0.115)],
                    seg=10, loc=(bx, yt + 0.06, bz), mat='M_Porcelain', bevel=0.0)
        for k, (bx, y) in enumerate(((-0.12, -0.55), (0.0, -0.25), (0.12, 0.55))):
            p0 = Vector((bx, yt + 0.06, zt1 + 0.14))
            p1 = Vector((xc, y, zc - 0.34))
            mid = (p0 + p1) / 2 + Vector((0, 0, -0.15))
            P.pipe([p0, mid, p1], 0.008, seg=6, mat='M_Cable', bevel=0.0)
        # secondary leads down to LV rack
        for k, bx in enumerate((-0.1, 0.1)):
            p0 = Vector((bx, yt + 0.1, zt0 - 0.02))
            p1 = Vector((bx * 0.5, -(pole_r(8.4) + 0.2), 8.42))
            P.pipe([p0, (p0 + p1) / 2 + Vector((0, -0.05, -0.1)), p1], 0.008, seg=6, mat='M_Cable', bevel=0.0)
    # --- low-voltage rack (低圧ラック) on the road side (-Y), 7.8..8.5 m
    yr = -(pole_r(8.15) + 0.03)
    P.box_mm((-0.03, yr - 0.012, 7.75), (0.03, yr, 8.6), mat='M_Galvanized', bevel=0.003)
    for z in (8.45, 8.15, 7.85):
        P.box_mm((-0.012, yr - 0.20, z - 0.055), (0.012, yr - 0.012, z - 0.045), mat='M_Galvanized', bevel=0.0)
        P.box_mm((-0.012, yr - 0.20, z + 0.045), (0.012, yr - 0.012, z + 0.055), mat='M_Galvanized', bevel=0.0)
        anchors.append(_spool(P, 0.0, yr - 0.15, z, axis='Z'))
    # --- telecom messenger clamp + cable closure on the back side (+Y), 6.2 m
    yc = pole_r(6.2) + 0.03
    P.box_mm((-0.03, yc, 6.1), (0.03, yc + 0.22, 6.16), mat='M_Galvanized', bevel=0.004)
    P.box_mm((-0.04, yc + 0.17, 6.12), (0.04, yc + 0.25, 6.24), mat='M_PlasticBlack', bevel=0.006)
    anchors.append((0.0, yc + 0.21, 6.2))
    P.cyl((-0.45, yc + 0.21, 5.95), (0.45, yc + 0.21, 5.95), 0.075, seg=12, mat='M_PlasticBlack', bevel=0.01)
    for x in (-0.3, 0.3):
        P.cyl((x, yc + 0.21, 6.03), (x, yc + 0.21, 6.2), 0.008, seg=6, mat='M_Galvanized', bevel=0.0)
    # small pole number plate
    P.box_mm((-0.05, -(pole_r(1.95) + 0.006), 1.9), (0.05, -(pole_r(1.95) - 0.002), 2.05), mat='M_PlasticWhite',
             bevel=0.0)
    for i, a in enumerate(anchors):
        P.empty(f'WireAnchor_{i}', a, size=0.12)
    P.note('WireAnchor_0..2 = 6.6 kV phases (pin insulators, ~11.73 m), 3..5 = low-voltage spools '
           '(8.45/8.15/7.85 m, road side), 6 = telecom messenger (6.2 m, back side). Same indices on both variants; '
           'string catenaries between equal indices of neighbouring poles along Unity X.')
    P.finish()


@builder
def build_utility_pole():
    _utility_pole('utility_pole_transformer', True)
    _utility_pole('utility_pole_plain', False)


# ======================================================================================
# shared helpers
# ======================================================================================
def shell_arc(P, cx, cz, y0, y1, r_in, r_out, a0, a1, seg, mat, **kw):
    """Closed thick arc shell (visor) around an axis parallel to Y through (cx, cz), from y0 to y1.
    Angles in degrees in the XZ plane (0 = +X, 90 = +Z)."""
    verts = []
    faces = []
    n = seg + 1
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / seg)
        ca, sa = math.cos(a), math.sin(a)
        for (r, y) in ((r_in, y0), (r_out, y0), (r_out, y1), (r_in, y1)):
            verts.append((cx + r * ca, y, cz + r * sa))
    for i in range(seg):
        b0, b1 = i * 4, (i + 1) * 4
        for k in range(4):
            kk = (k + 1) % 4
            faces.append((b0 + k, b0 + kk, b1 + kk, b1 + k))
    faces.append((0, 1, 2, 3))
    last = seg * 4
    faces.append((last + 3, last + 2, last + 1, last + 0))
    kw.setdefault('bevel', 0.0)
    kw.setdefault('sharp', 40.0)
    o = P.poly(verts, faces, mat=mat, **kw)
    return o


def _fix_normals_outward(obj):
    import bmesh
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data); bm.free()


def sign_lens(P, cx, cz, yf, r, mat, ring_mat='M_PlasticBlack'):
    """Domed lamp lens facing -Y with a black bezel ring; yf = front plane of the housing."""
    P.cyl((cx, yf + 0.004, cz), (cx, yf - 0.012, cz), r + 0.02, seg=20, mat=ring_mat, bevel=0.003)
    P.lathe([(r, 0.0), (r * 0.93, 0.010), (r * 0.6, 0.017), (0.0, 0.019)], seg=20, loc=(cx, yf - 0.012, cz),
            rot=(90, 0, 0), mat=mat, cap_bottom=False, bevel=0.0, sharp=60, uv=UV.planar((0, -1, 0)))


# ======================================================================================
# Vehicle traffic signal (Japanese horizontal 3-lamp: green-yellow-red left->right)
# ======================================================================================
@builder
def build_traffic_signal_vehicle():
    P = Prop('traffic_signal_vehicle', 'urban',
             desc='Japanese overhead vehicle signal: tapered steel pole, 5 m cantilever arm, horizontal '
                  '3-lamp head (green-yellow-red left to right as seen by the driver) with visors, '
                  'intersection name plate',
             origin='ground, pole centre',
             front='lamps face Unity +Z (toward approaching traffic); arm reaches Unity -X (Blender +X) over the road',
             preview=dict(az=-30, el=10, extra=[('head', -25, 6, ((3.6, -0.6, 4.9), (5.4, 0.3, 5.8)))]))
    H = 7.0
    P.cyl((0, 0, 0), (0, 0, H), 0.135, 0.095, seg=16, mat='M_Galvanized', bevel=0.0, caps=False)
    P.lathe([(0.10, H - 0.01), (0.105, H + 0.03), (0.06, H + 0.07), (0, H + 0.08)], seg=16, mat='M_Galvanized',
            bevel=0.0)
    P.lathe([(0.24, -0.02), (0.24, 0.05), (0.2, 0.09), (0.145, 0.10), (0.145, 0.0)], seg=16, mat='M_Concrete',
            bevel=0.0)
    # hand-hole cover
    P.box_mm((-0.05, -0.150, 0.55), (0.05, -0.12, 0.80), mat='M_Galvanized', bevel=0.006)
    # arm: 5.2 m reach at 5.6 m, slight rise, tapered
    za = 5.62
    arm_end = Vector((5.25, 0, za + 0.12))
    P.sweep([Vector((0.0, 0, za)), arm_end], circle2d(0.070, 12, math.pi / 12), mat='M_Galvanized', scales=[1, 0.72],
            bevel=0.0, sharp=50)
    P.lathe([(0.052, 0), (0.054, 0.02), (0, 0.025)], seg=12, loc=arm_end, rot=(0, 90 - 1.3, 0), mat='M_Galvanized',
            bevel=0.0)
    # arm clamp collar on pole + tie rod from pole top
    P.cyl((0, 0, za - 0.18), (0, 0, za + 0.18), 0.125, seg=16, mat='M_Galvanized', bevel=0.008)
    P.cyl((0.06, 0, H - 0.25), (2.9, 0, za + 0.08), 0.018, seg=8, mat='M_Galvanized', bevel=0.0, sharp=60)
    P.cyl((0, 0, H - 0.32), (0, 0, H - 0.18), 0.108, seg=16, mat='M_Galvanized', bevel=0.006)
    # --- signal head
    cx, cz = 4.55, 5.30
    W, Hh, D = 1.26, 0.44, 0.23
    yf = -D / 2 - 0.02
    P.extrude(rounded_rect2d(W, Hh, 0.07, 3), D, axis='Y', offset=yf, origin=(cx, 0, cz), mat='M_PaintedMetal_LightGray',
              bevel=0.012, seg=2)
    lamps = [(-0.405, 'M_EmissiveSignal_Green', 'Lamp_Green'), (0.0, 'M_EmissiveSignal_Yellow', 'Lamp_Yellow'),
             (0.405, 'M_EmissiveSignal_Red', 'Lamp_Red')]
    for dx, m, en in lamps:
        x = cx + dx
        sign_lens(P, x, cz, yf, 0.135, m)
        shell_arc(P, x, cz, yf + 0.005, yf - 0.24, 0.168, 0.176, -25, 205, 14, 'M_PaintedMetal_LightGray')
        P.empty(en, (x, yf - 0.03, cz), size=0.1)
    # back ribs + hanger brackets to the arm
    for dx in (-0.36, 0.36):
        z_arm = za + 0.12 * (cx + dx) / 5.25
        P.box_mm((cx + dx - 0.03, -0.03, cz + Hh / 2 - 0.02), (cx + dx + 0.03, 0.03, z_arm + 0.02),
                 mat='M_Galvanized', bevel=0.005)
        P.cyl((cx + dx - 0.05, 0, z_arm), (cx + dx + 0.05, 0, z_arm), 0.085, seg=12, mat='M_Galvanized', bevel=0.006)
    # --- intersection name plate (交差点名標識) hung from the arm
    px, pz = 2.05, 5.05
    pw, ph = 1.10, 0.55
    P.box_mm((px - pw / 2, -0.012, pz - ph / 2), (px + pw / 2, 0.012, pz + ph / 2), mat='M_Galvanized', bevel=0.006)
    P.ngon([(px - pw / 2 + 0.003, -0.0125, pz - ph / 2 + 0.003), (px + pw / 2 - 0.003, -0.0125, pz - ph / 2 + 0.003),
            (px + pw / 2 - 0.003, -0.0125, pz + ph / 2 - 0.003), (px - pw / 2 + 0.003, -0.0125, pz + ph / 2 - 0.003)],
           mat='M_Deco_StreetName', uv=UV.planar((0, -1, 0)))
    for dx in (-0.35, 0.35):
        z_arm = za + 0.12 * (px + dx) / 5.25
        P.box_mm((px + dx - 0.02, -0.02, pz + ph / 2 - 0.01), (px + dx + 0.02, 0.02, z_arm), mat='M_Galvanized',
                 bevel=0.004)
    P.note('Each lamp has its own emissive material slot (M_EmissiveSignal_Green/Yellow/Red) so the game can '
           'switch lamps by swapping materials; empties Lamp_Green/Yellow/Red sit just in front of each lens. '
           'Name plate uses M_Deco_StreetName (0-1 UV, 2:1).')
    P.finish()


# ======================================================================================
# Pedestrian signal (two stacked boxes: red standing / green walking) + push-button box
# ======================================================================================
@builder
def build_traffic_signal_pedestrian():
    P = Prop('traffic_signal_pedestrian', 'urban',
             desc='Japanese pedestrian signal: 3.6 m post, two stacked lamp boxes (red standing figure over '
                  'green walking figure) with hoods, yellow push-button box',
             origin='ground, pole centre', front='lamps face Unity +Z',
             preview=dict(az=-30, el=8, extra=[('head', -30, 5, ((-0.35, -0.5, 2.3), (0.35, 0.2, 3.4)))]))
    H = 3.6
    P.cyl((0, 0, 0), (0, 0, H), 0.0700, 0.0610, seg=14, mat='M_Galvanized', bevel=0.0, caps=False)
    P.lathe([(0.064, H - 0.01), (0.066, H + 0.02), (0.035, H + 0.05), (0, H + 0.055)], seg=14, mat='M_Galvanized',
            bevel=0.0)
    P.lathe([(0.16, -0.02), (0.16, 0.04), (0.12, 0.07), (0.075, 0.075), (0.075, 0.0)], seg=14, mat='M_Concrete',
            bevel=0.0)
    bw, bh, bd = 0.36, 0.36, 0.20
    yb = -(0.07 + 0.06)          # back of boxes
    yf = yb - bd                  # front plane
    zs = [(3.03, 'M_EmissiveSignal_PedRed', (0.0, 0.0, 0.5, 1.0), 'Lamp_PedRed'),
          (2.63, 'M_EmissiveSignal_PedGreen', (0.5, 0.0, 1.0, 1.0), 'Lamp_PedGreen')]
    for zc, m, rect, en in zs:
        P.extrude(rounded_rect2d(bw, bh, 0.03, 2), bd, axis='Y', offset=yf, origin=(0, 0, zc),
                  mat='M_PaintedMetal_LightGray', bevel=0.008, seg=2)
        fw = 0.29
        P.box_mm((-fw / 2 - 0.012, yf - 0.006, zc - fw / 2 - 0.012), (fw / 2 + 0.012, yf + 0.002, zc + fw / 2 + 0.012),
                 mat='M_PlasticBlack', bevel=0.003)
        P.ngon([(-fw / 2, yf - 0.0065, zc - fw / 2), (fw / 2, yf - 0.0065, zc - fw / 2),
                (fw / 2, yf - 0.0065, zc + fw / 2), (-fw / 2, yf - 0.0065, zc + fw / 2)], mat=m,
               uv=UV.planar((0, -1, 0), rect=rect))
        # hood: top + sides, 0.16 projection, open bottom
        hp = 0.16
        P.box_mm((-bw / 2, yf - hp, zc + bh / 2 - 0.006), (bw / 2, yf + 0.01, zc + bh / 2 + 0.002),
                 mat='M_PaintedMetal_LightGray', bevel=0.002, seg=1)
        for sx in (-1, 1):
            P.extrude([(0.01, bh / 2), (-hp, bh / 2), (0.01, -bh / 2 + 0.06)], 0.006, axis='X',
                      offset=sx * bw / 2 - 0.003, origin=(0, yf, zc), mat='M_PaintedMetal_LightGray', bevel=0.0)
        P.empty(en, (0, yf - 0.03, zc), size=0.08)
    # mounting brackets (two clamps per box)
    for zc in (3.03, 2.63):
        P.box_mm((-0.04, yb - 0.01, zc - 0.03), (0.04, -0.055, zc + 0.03), mat='M_Galvanized', bevel=0.005)
        P.cyl((0, 0, zc - 0.035), (0, 0, zc + 0.035), 0.078, seg=14, mat='M_Galvanized', bevel=0.005)
    # push-button box (押ボタン箱), yellow, facing the sidewalk/road (-Y) at 1.1 m
    P.box_mm((-0.085, -0.073 - 0.09, 1.0), (0.085, -0.062, 1.32), mat='M_PaintedMetal_Yellow', bevel=0.012)
    P.ngon([(-0.07, -0.1635, 1.03), (0.07, -0.1635, 1.03), (0.07, -0.1635, 1.29), (-0.07, -0.1635, 1.29)],
           mat='M_Deco_PedButton', uv=UV.planar((0, -1, 0)))
    P.cyl((0, -0.162, 1.12), (0, -0.182, 1.12), 0.025, seg=14, mat='M_PlasticWhite', bevel=0.004)
    for z in (1.04, 1.28):
        P.cyl((0, 0, z - 0.02), (0, 0, z + 0.02), 0.074, seg=14, mat='M_Galvanized', bevel=0.004)
    P.note('Lamp faces use M_EmissiveSignal_PedRed / M_EmissiveSignal_PedGreen, both sampling the atlas '
           'prop_ped_signal_albedo.png (left half red standing, right half green walking).')
    P.finish()


define_mat('M_Deco_PedButton', c='#F3C300', r=0.4, tex='prop_ped_button_albedo.png')


# ======================================================================================
# Street lamps
# ======================================================================================
def _lamp_pole_path(z_bend, R, ang, arm_len, n=10):
    pts = [Vector((0, 0, 0)), Vector((0, 0, z_bend * 0.5)), Vector((0, 0, z_bend))]
    for i in range(1, n + 1):
        t = math.radians(ang * i / n)
        pts.append(Vector((0, -R * (1 - math.cos(t)), z_bend + R * math.sin(t))))
    t = math.radians(ang)
    d = Vector((0, -math.sin(t), math.cos(t)))
    pts.append(pts[-1] + d * arm_len)
    return pts, d


def _taper_scales(pts, r0, r1):
    L = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        L.append(L[-1] + (b - a).length)
    return [1 + (r1 / r0 - 1) * l / L[-1] for l in L]


@builder
def build_street_lamp_classic():
    P = Prop('street_lamp_classic', 'urban',
             desc='Classic Japanese bend-arm road light (ベンド形), galvanized tapered pole ~9 m, box luminaire '
                  'with sodium bowl, base cover',
             origin='ground, pole centre', front='arm reaches toward the road, Unity +Z',
             preview=dict(az=-55, el=10, extra=[('head', -50, 8, ((-0.4, -2.9, 7.6), (0.4, 0.3, 9.3)))]))
    pts, d = _lamp_pole_path(7.35, 1.35, 80, 0.85, n=12)
    r0, r1 = 0.083, 0.05
    P.sweep(pts, circle2d(r0, 14, math.pi / 14), mat='M_Galvanized', scales=_taper_scales(pts, r0, r1), bevel=0.0,
            sharp=50, caps=True)
    # base cover (ベースカバー)
    P.lathe([(0.17, 0.0), (0.17, 0.05), (0.14, 0.09), (0.12, 0.55), (0.098, 0.6), (0.085, 0.62)], seg=14,
            mat='M_Galvanized', bevel=0.0, sharp=40)
    # luminaire, aligned with the arm tip direction (rises 10 deg)
    tip = pts[-1]
    tilt = -(90 - 80)
    ax = Vector((0, -math.cos(math.radians(10)), math.sin(math.radians(10))))
    c = tip + ax * 0.36 + Vector((0, 0, -0.02))
    P.box((0.34, 0.80, 0.13), c, rot=(tilt, 0, 0), mat='M_Aluminum', bevel=0.045, seg=3)
    P.box((0.26, 0.64, 0.07), c + Vector((0, 0, -0.075)), rot=(tilt, 0, 0), mat='M_EmissiveLamp_Sodium',
          bevel=0.03, seg=2, uv=UV.planar((0, 0, -1)))
    P.box((0.30, 0.72, 0.02), c + Vector((0, 0, -0.06)), rot=(tilt, 0, 0), mat='M_Aluminum', bevel=0.006, seg=1)
    P.empty('LightAnchor_0', c + Vector((0, 0, -0.12)), size=0.2)
    P.note('LightAnchor_0 = centre of the lamp bowl; aim a spot light straight down (-Y Unity).')
    P.finish()


@builder
def build_street_lamp_led():
    P = Prop('street_lamp_led', 'urban',
             desc='Modern Japanese LED road light: slim tapered pole ~8 m, tight bend into a short rising arm, '
                  'flat LED luminaire', origin='ground, pole centre', front='arm reaches toward the road, Unity +Z',
             preview=dict(az=-55, el=10, extra=[('head', -50, 8, ((-0.4, -1.9, 7.0), (0.4, 0.3, 8.4)))]))
    pts, d = _lamp_pole_path(7.45, 0.45, 78, 0.95, n=8)
    r0, r1 = 0.07, 0.042
    P.sweep(pts, circle2d(r0, 14, math.pi / 14), mat='M_PaintedMetal_DarkGray', scales=_taper_scales(pts, r0, r1),
            bevel=0.0, sharp=50)
    P.lathe([(0.13, 0.0), (0.13, 0.03), (0.10, 0.05), (0.078, 0.35), (0.07, 0.37)], seg=14,
            mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=40)
    tip = pts[-1]
    ang = 90 - 78
    ax = Vector((0, -math.cos(math.radians(ang)), math.sin(math.radians(ang))))
    c = tip + ax * 0.30
    # slim flat head
    P.box((0.30, 0.62, 0.06), c, rot=(-ang, 0, 0), mat='M_PaintedMetal_DarkGray', bevel=0.02, seg=2)
    P.box((0.24, 0.50, 0.012), c + Vector((0, -0.01, -0.034)), rot=(-ang, 0, 0), mat='M_EmissiveLamp_LED', bevel=0.004,
          seg=1, uv=UV.planar((0, 0, -1)))
    P.box((0.12, 0.20, 0.035), c + ax * -0.30 + Vector((0, 0, 0.03)), rot=(-ang, 0, 0), mat='M_PaintedMetal_DarkGray',
          bevel=0.01, seg=1)
    P.empty('LightAnchor_0', c + Vector((0, 0, -0.06)), size=0.2)
    P.note('LightAnchor_0 = LED panel centre; aim a spot light straight down.')
    P.finish()


# ======================================================================================
# Pedestrian railings (Tokyo sidewalk fences) - 2 m tiles, post at X=0
# ======================================================================================
def _rail_post(P, x, mat, h=0.85, r=0.0303):
    P.cyl((x, 0, 0), (x, 0, h), r, seg=12, mat=mat, bevel=0.0, caps=False)
    P.lathe([(r + 0.004, h - 0.01), (r + 0.004, h + 0.01), (r * 0.6, h + 0.03), (0, h + 0.035)], seg=12, loc=(x, 0, 0),
            mat=mat, bevel=0.0)
    P.lathe([(r + 0.012, 0.0), (r + 0.012, 0.02), (r + 0.002, 0.03)], seg=12, loc=(x, 0, 0), mat=mat, bevel=0.0)


def _railing(name, style, colour):
    mat = {'green': 'M_PaintedMetal_Green', 'white': 'M_PaintedMetal_White'}[colour]
    P = Prop(name, 'urban', mirror_x=True,
             desc=f'Tokyo sidewalk pedestrian railing, {style} style, {colour}, 2 m tile (post at X=0)',
             origin='ground at the start post (Unity X=0); tile spans Unity X 0..2')
    if style == 'pipe':
        # ガードパイプ: 3 horizontal pipes (48.6) through round posts (60.5), 0.8 m
        _rail_post(P, 0.0, mat, h=0.80)
        for z in (0.74, 0.49, 0.24):
            P.cyl((0.0, 0, z), (2.0, 0, z), 0.0243, seg=10, mat=mat, bevel=0.0, caps=False, sharp=50)
        # pipe clamps on the post
        for z in (0.74, 0.49, 0.24):
            P.cyl((0, 0, z - 0.03), (0, 0, z + 0.03), 0.036, seg=12, mat=mat, bevel=0.004)
    else:
        # 縦格子 vertical-bar fence: top rail, bottom rail, 16 pickets per 2 m
        _rail_post(P, 0.0, mat, h=0.86)
        P.box_mm((0.0, -0.022, 0.78), (2.0, 0.022, 0.83), mat=mat, bevel=0.008, seg=2)
        P.box_mm((0.0, -0.018, 0.13), (2.0, 0.018, 0.17), mat=mat, bevel=0.006, seg=1)
        for i in range(16):
            x = 0.0625 + i * 0.125
            P.cyl((x, 0, 0.17), (x, 0, 0.78), 0.0095, seg=8, mat=mat, bevel=0.0, caps=False, sharp=60)
    P.note('Tile has its post at X=0 only; finish a run with pedestrian_railing_endpost_<colour> at X=2N.')
    P.finish()


@builder
def build_pedestrian_railing():
    for style in ('pipe', 'bars'):
        for colour in ('green', 'white'):
            _railing(f'pedestrian_railing_2m_{style}_{colour}', style, colour)
    for colour in ('green', 'white'):
        mat = {'green': 'M_PaintedMetal_Green', 'white': 'M_PaintedMetal_White'}[colour]
        P = Prop(f'pedestrian_railing_endpost_{colour}', 'urban', mirror_x=True,
                 desc=f'End post closing a pedestrian railing run ({colour})', origin='ground, post centre')
        _rail_post(P, 0.0, mat, h=0.86)
        P.finish()


# ======================================================================================
# Bollards
# ======================================================================================
define_mat('M_StainlessSteel', c='#C8CCCF', r=0.28, m=1.0)


@builder
def build_bollard():
    P = Prop('bollard_steel', 'urban', desc='Stainless round bollard (車止め) Φ114 x 0.85 m with yellow reflective bands',
             origin='ground, centre')
    r = 0.0572
    P.lathe([(r + 0.03, 0.0), (r + 0.03, 0.008), (r + 0.004, 0.014), (r, 0.02), (r, 0.80), (r * 0.85, 0.83),
             (r * 0.45, 0.85), (0.0, 0.855)], seg=18, mat='M_StainlessSteel', bevel=0.0, sharp=35)
    for z0, z1 in ((0.60, 0.65), (0.70, 0.75)):
        P.lathe([(r + 0.0015, z0), (r + 0.0015, z1)], seg=18, mat='M_Reflector_Amber', cap_bottom=False,
                cap_top=False, bevel=0.0, uv=UV.cyl((0, 0, 0), (0, 0, 1), norm=True))
    P.finish()

    P = Prop('bollard_u', 'urban', desc='U-shaped arch bollard (アーチ型車止め), Φ60.5 pipe, 0.8 x 0.8 m, yellow',
             origin='ground, centre between the legs', front='faces Unity +Z (pipe plane is Unity XY)')
    R = 0.32
    path = [Vector((-R, 0, 0.0)), Vector((-R, 0, 0.45))]
    for i in range(1, 18):
        a = math.radians(180 - 180 * i / 18)
        path.append(Vector((R * math.cos(a), 0, 0.45 + R * math.sin(a) * 1.08)))
    path += [Vector((R, 0, 0.45)), Vector((R, 0, 0.0))]
    P.pipe(path, 0.0303, seg=12, mat='M_PaintedMetal_Yellow', bevel=0.0)
    for sx in (-1, 1):
        P.lathe([(0.07, 0.0), (0.07, 0.008), (0.036, 0.016), (0.0303, 0.02)], seg=12, loc=(sx * R, 0, 0),
                mat='M_PaintedMetal_Yellow', bevel=0.0)
        P.lathe([(0.0318, 0.52), (0.0318, 0.58)], seg=12, loc=(sx * R, 0, 0), mat='M_Reflector_White',
                cap_bottom=False, cap_top=False, bevel=0.0, uv=UV.cyl((0, 0, 0), (0, 0, 1), norm=True))
    P.finish()


# ======================================================================================
# Construction A-frame barricade (A型バリケード) with blinker lamp
# ======================================================================================
@builder
def build_construction_barrier():
    P = Prop('construction_barrier', 'urban',
             desc='Japanese A-type folding barricade 1.2 x 0.8 m, yellow/black striped boards both sides, '
                  'red LED blinker on top', origin='ground, centre', front='board faces Unity +Z / -Z')
    W, H = 1.20, 0.80
    spread = 0.27
    tilt = math.degrees(math.atan2(spread, H))
    for side in (-1, 1):
        # leaf rotated about the top hinge line (X axis at z=H)
        def leaf_pt(y_off, z):
            # point on the leaf plane at height z (y offset from the leaf centre plane)
            t = (H - z) / H
            return Vector((0, side * spread * t + y_off, z))
        for sx in (-1, 1):
            x = sx * (W / 2 - 0.03)
            P.cyl((x, side * spread, 0.02), (x, side * 0.012, H - 0.01), 0.016, seg=8, mat='M_PaintedMetal_Yellow',
                  bevel=0.0, sharp=50)
            P.box((0.06, 0.07, 0.03), (x, side * spread, 0.015), mat='M_Rubber', bevel=0.006)
        # boards (stripes): top board 0.18, lower board 0.12
        for zc, bh in ((H - 0.13, 0.18), (0.36, 0.13)):
            yc = side * spread * (H - zc) / H + side * 0.012
            P.box((W, 0.014, bh), (0, yc, zc), rot=(side * tilt, 0, 0), mat='M_Deco_HazardStripe', bevel=0.004,
                  seg=1, uv=UV.box(s=0.5))
    # hinge bar + blinker
    P.cyl((-W / 2 + 0.03, 0, H), (W / 2 - 0.03, 0, H), 0.018, seg=8, mat='M_PaintedMetal_Yellow', bevel=0.0)
    P.box((0.10, 0.08, 0.06), (0, 0, H + 0.04), mat='M_PlasticBlack', bevel=0.01)
    P.lathe([(0.055, 0.0), (0.055, 0.02), (0.05, 0.06), (0.03, 0.09), (0.0, 0.1)], seg=16, loc=(0, 0, H + 0.07),
            mat='M_EmissiveSignal_Red', bevel=0.0, sharp=60, uv=UV.planar((0, -1, 0)))
    P.empty('LightAnchor_0', (0, 0, H + 0.12), size=0.08)
    P.note('M_EmissiveSignal_Red dome = blinking warning lamp (animate emission in Unity).')
    P.finish()


# ======================================================================================
# Road sign posts (single galvanized post Φ60.5, faces on M_SignFace with 0-1 UVs)
# ======================================================================================
POST_R = 0.0303


def _sign_post(P, h):
    P.cyl((0, 0, 0), (0, 0, h), POST_R, seg=12, mat='M_Galvanized', bevel=0.0, caps=False)
    P.lathe([(POST_R + 0.003, h - 0.01), (POST_R + 0.003, h + 0.01), (POST_R * 0.6, h + 0.028), (0, h + 0.032)],
            seg=12, mat='M_PlasticBlack', bevel=0.0)
    P.lathe([(0.075, -0.02), (0.075, 0.03), (0.05, 0.05), (POST_R, 0.052)], seg=12, mat='M_Concrete', bevel=0.0)


def _sign_panel(P, outline, cz, mat_face='M_SignFace', t=0.016, rails=None, bands=None):
    """outline: 2D (x, z) relative to panel centre, panel front at y = yf, mounted in front of the post."""
    yf = -(POST_R + 0.045 + t)
    pts = [(x, z + cz) for (x, z) in outline]
    P.extrude(pts, t, axis='Y', offset=yf, mat='M_Aluminum', cap_front=False, bevel=0.0, sharp=40)
    P.ngon([(x, yf, z) for (x, z) in pts], mat=mat_face, uv=UV.planar((0, -1, 0)))
    xs = [p[0] for p in outline]; zs = [p[1] for p in outline]
    # backing rails (channels) + U-band clamps
    for dz in (rails or ()):
        # rail width = 75 % of the panel width at that height
        inter = []
        for (x0, z0), (x1, z1) in zip(outline, outline[1:] + outline[:1]):
            if (z0 - dz) * (z1 - dz) <= 0 and abs(z1 - z0) > 1e-9:
                inter.append(x0 + (x1 - x0) * (dz - z0) / (z1 - z0))
        w = (max(inter) - min(inter)) * 0.75 if len(inter) >= 2 else (max(xs) - min(xs)) * 0.5
        P.box_mm((-w / 2, yf + t, cz + dz - 0.02), (w / 2, yf + t + 0.03, cz + dz + 0.02), mat='M_Galvanized',
                 bevel=0.004, seg=1)
        P.cyl((0, 0, cz + dz - 0.025), (0, 0, cz + dz + 0.025), POST_R + 0.008, seg=12, mat='M_Galvanized', bevel=0.003)
        P.box_mm((-0.03, -(POST_R + 0.008), cz + dz - 0.025), (0.03, yf + t + 0.03, cz + dz + 0.025),
                 mat='M_Galvanized', bevel=0.003)


def _rounded_poly(pts, r, n=3):
    """Round the corners of a convex 2D polygon."""
    P2 = [Vector(p) for p in pts]
    out = []
    m = len(P2)
    for i in range(m):
        a, b, c = P2[i - 1], P2[i], P2[(i + 1) % m]
        d0 = (a - b).normalized(); d1 = (c - b).normalized()
        ang = d0.angle(d1)
        t = r / math.tan(ang / 2)
        p0 = b + d0 * t; p1 = b + d1 * t
        bis = (d0 + d1).normalized()
        ctr = b + bis * (r / math.sin(ang / 2))
        a0 = math.atan2(p0.y - ctr.y, p0.x - ctr.x); a1 = math.atan2(p1.y - ctr.y, p1.x - ctr.x)
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(n + 1):
            aa = a0 + da * k / n
            out.append((ctr.x + r * math.cos(aa), ctr.y + r * math.sin(aa)))
    return out


@builder
def build_road_sign_post():
    # round regulatory sign Φ600 + auxiliary plate
    P = Prop('road_sign_post_round', 'urban',
             desc='Round regulatory sign Φ0.6 m (blank, M_SignFace) + auxiliary plate 0.6 x 0.25 (M_SignFace_Aux) '
                  'on a Φ60.5 galvanized post', origin='ground, post centre', front='sign faces Unity +Z')
    _sign_post(P, 2.95)
    _sign_panel(P, circle2d(0.30, 32, 0), 2.60, rails=(-0.15, 0.15))
    _sign_panel(P, _rounded_poly(rect2d(0.60, 0.25), 0.02, 2), 2.13, mat_face='M_SignFace_Aux', t=0.012,
                rails=(0.0,))
    P.note('M_SignFace UV 0-1 = bounding square of the disc (1:1). M_SignFace_Aux UV 0-1 over the 0.60 x 0.25 '
           'plate (2.4:1).')
    P.finish()

    P = Prop('road_sign_post_triangle', 'urban',
             desc='Inverted triangle sign (止まれ type), side 0.8 m, blank M_SignFace', origin='ground, post centre',
             front='sign faces Unity +Z')
    _sign_post(P, 2.98)
    h = 0.8 * math.sqrt(3) / 2
    tri = _rounded_poly([(-0.4, h / 2), (0.0, -h / 2), (0.4, h / 2)][::-1], 0.035, 3)
    _sign_panel(P, tri, 2.55, rails=(-0.08, 0.20))
    P.note('M_SignFace UV 0-1 = bounding box 0.80 x 0.69 (point down).')
    P.finish()

    P = Prop('road_sign_post_diamond', 'urban',
             desc='Warning sign (diamond, 0.45 m side), blank M_SignFace', origin='ground, post centre',
             front='sign faces Unity +Z')
    _sign_post(P, 2.90)
    d = 0.45 / math.sqrt(2)
    _sign_panel(P, _rounded_poly([(0, -d), (d, 0), (0, d), (-d, 0)], 0.025, 3), 2.55, rails=(-0.1, 0.1))
    P.note('M_SignFace UV 0-1 = bounding square 0.636 x 0.636.')
    P.finish()

    P = Prop('road_sign_post_rect', 'urban',
             desc='Rectangular sign panel 0.9 x 0.6 m, blank M_SignFace', origin='ground, post centre',
             front='sign faces Unity +Z')
    _sign_post(P, 2.95)
    _sign_panel(P, _rounded_poly(rect2d(0.90, 0.60), 0.03, 2), 2.55, rails=(-0.18, 0.18))
    P.note('M_SignFace UV 0-1 over 0.90 x 0.60 (3:2).')
    P.finish()


# ======================================================================================
# Fire hydrant sign (消火栓 標識)
# ======================================================================================
@builder
def build_fire_hydrant_sign():
    P = Prop('fire_hydrant_sign', 'urban',
             desc='Tokyo-style fire hydrant sign: red 消火栓 board 0.4 x 0.8 m on a Φ60.5 post, top at 3.25 m',
             origin='ground, post centre', front='board faces Unity +Z')
    _sign_post(P, 3.28)
    yf = -(POST_R + 0.045 + 0.014)
    pts = [(x, z + 2.85) for (x, z) in _rounded_poly(rect2d(0.40, 0.80), 0.02, 2)]
    P.extrude(pts, 0.014, axis='Y', offset=yf, mat='M_PaintedMetal_Red', cap_front=False, bevel=0.0)
    P.ngon([(x, yf, z) for (x, z) in pts], mat='M_Deco_HydrantSign', uv=UV.planar((0, -1, 0)))
    for z in (2.6, 3.1):
        P.box_mm((-0.12, yf + 0.014, z - 0.02), (0.12, -(POST_R + 0.008), z + 0.02), mat='M_Galvanized', bevel=0.004)
        P.cyl((0, 0, z - 0.025), (0, 0, z + 0.025), POST_R + 0.008, seg=12, mat='M_Galvanized', bevel=0.003)
    P.finish()


# ======================================================================================
# Manhole cover, drain grating, kerb
# ======================================================================================
@builder
def build_manhole_cover():
    P = Prop('manhole_cover', 'urban',
             desc='Tokyo-style decorative sewer manhole cover Φ0.6 m in a Φ0.72 frame, 6 mm proud of the road',
             origin='road surface, centre')
    P.lathe([(0.30, -0.03), (0.30, 0.006), (0.0, 0.006)], seg=40, mat='M_Steel_Dark', bevel=0.0, sharp=50)
    P.ngon([(0.296 * math.cos(2 * math.pi * i / 40), 0.296 * math.sin(2 * math.pi * i / 40), 0.0062) for i in range(40)],
           mat='M_Deco_Manhole', uv=UV.planar((0, 0, 1), bounds=(-0.296, -0.296, 0.296, 0.296)))
    P.lathe([(0.36, -0.03), (0.36, 0.002), (0.345, 0.005), (0.302, 0.005), (0.302, -0.03)], seg=40,
            mat='M_Steel_Dark', bevel=0.0, sharp=50)
    P.note('Top disc UV 0-1 over the lid; M_Deco_Manhole has albedo + normal map.')
    P.finish()


@builder
def build_drain_grating_1m():
    P = Prop('drain_grating_1m', 'urban', mirror_x=True,
             desc='Steel road-gutter grating (グレーチング) 1.0 x 0.40 m over a U-gutter, flush with the road',
             origin='road surface at the start of the gutter centre-line; tile spans Unity X 0..1')
    W = 0.40
    # frame
    for y in (-W / 2, W / 2 - 0.02):
        P.box_mm((0.0, y, -0.03), (1.0, y + 0.02, 0.002), mat='M_Galvanized', bevel=0.003, seg=1)
    for x in (0.0, 0.98):
        P.box_mm((x, -W / 2, -0.03), (x + 0.02, W / 2, 0.002), mat='M_Galvanized', bevel=0.003, seg=1)
    n = 30
    for i in range(n):
        x = 0.035 + i * (0.93 / (n - 1))
        P.box_mm((x - 0.003, -W / 2 + 0.02, -0.025), (x + 0.003, W / 2 - 0.02, 0.002), mat='M_Galvanized', bevel=0.0)
    for y in (-0.09, 0.09):
        P.box_mm((0.02, y - 0.004, -0.02), (0.98, y + 0.004, -0.006), mat='M_Galvanized', bevel=0.0)
    # gutter void
    P.box_mm((0.0, -W / 2 + 0.02, -0.30), (1.0, W / 2 - 0.02, -0.28), mat='M_Concrete_Dark', bevel=0.0)
    for y in (-W / 2 + 0.02, W / 2 - 0.04):
        P.box_mm((0.0, y, -0.30), (1.0, y + 0.02, -0.03), mat='M_Concrete_Dark', bevel=0.0)
    P.finish()


@builder
def build_kerb_stone_1m():
    P = Prop('kerb_stone_1m', 'urban', mirror_x=True,
             desc='Japanese road/sidewalk boundary kerb block (歩車道境界ブロック), 1.0 m, 180/205 x 250, '
                  '150 mm exposed', origin='road surface level at the road-side face, start of block; tile 0..1 in '
                                           'Unity X; block extends 0.1 m below road and toward -Z (sidewalk side)')
    sm = fillet([(0.205, 0.15), (0.045, 0.15), (0.022, 0.125), (0.0, 0.0)], 0.02, 3)
    prof = [(0.0, -0.10), (0.205, -0.10)] + [(p.x, p.y) for p in sm]
    P.prism(prof, 0.0015, 0.9985, mat='M_Concrete_Light', bevel=0.006, seg=1, sharp=30)
    P.finish()


# ======================================================================================
# Cone bar (コーンバー) - sits on two traffic cones 2 m apart
# ======================================================================================
@builder
def build_cone_bar_2m():
    P = Prop('cone_bar_2m', 'urban', mirror_x=True,
             desc='Yellow/black cone bar 2 m, end rings slip over traffic_cone tips (cones at X=0 and X=2)',
             origin='ground under the first cone centre (Unity X=0)')
    z = 0.62
    n = 18
    x0, x1 = 0.07, 1.93
    for i in range(n):
        a = x0 + (x1 - x0) * i / n; b = x0 + (x1 - x0) * (i + 1) / n
        P.cyl((a, 0, z), (b, 0, z), 0.017, seg=10, mat='M_PlasticYellow' if i % 2 == 0 else 'M_PlasticBlack',
              bevel=0.0, caps=(i == 0 or i == n - 1), sharp=50)
    for x in (0.0, 2.0):
        P.torus((x, 0, z), 0.046, 0.011, seg=16, rseg=6, mat='M_PlasticBlack')
    # bridging links between the end rings and the bar
    for x, xe in ((0.0, 0.07), (2.0, 1.93)):
        P.cyl((x + (0.044 if xe > x else -0.044), 0, z), (xe, 0, z), 0.012, seg=8, mat='M_PlasticBlack', bevel=0.0)
    P.finish()


# ======================================================================================
# Extras: bus stop, shopping-street lamp with banners, hydrant lid, coin-parking sign
# ======================================================================================
define_mat('M_Deco_HydrantLid', c='#EEC414', r=0.6, m=0.3, tex='prop_hydrant_lid_albedo.png')
define_mat('M_Deco_ParkingSign', c='#FAD600', r=0.4, e=1.5, tex='prop_parking_sign_albedo.png')
define_mat('M_BannerFace', c='#E8E2D0', r=0.8)


@builder
def build_bus_stop_pole():
    P = Prop('bus_stop_pole', 'urban',
             desc='Tokyo city-bus stop pole (都営バス style): weighted round base, Φ60.5 pole, double-sided round '
                  'sign Φ0.5 (M_SignFace, both sides 0-1 UV), timetable case (M_SignFace_Aux)',
             origin='ground, base centre', front='sign faces Unity +Z and -Z; timetable faces Unity +Z')
    P.lathe([(0.28, 0.0), (0.28, 0.06), (0.24, 0.11), (0.06, 0.13), (0.04, 0.13)], seg=24,
            mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=40)
    P.cyl((0, 0, 0.12), (0, 0, 2.55), POST_R, seg=12, mat='M_PaintedMetal_White', bevel=0.0, caps=False)
    P.lathe([(POST_R + 0.003, 2.54), (POST_R + 0.003, 2.56), (0.0, 2.585)], seg=12, mat='M_PaintedMetal_White',
            bevel=0.0)
    # round sign: aluminium disc 0.5 m, 18 mm thick, faces both ways, centred on the pole axis plane
    cz = 2.22
    t = 0.018
    yc = -(POST_R + 0.012 + t / 2)
    circ = [(x, z + cz) for (x, z) in circle2d(0.25, 32, 0)]
    P.extrude(circ, t, axis='Y', offset=yc - t / 2, mat='M_Aluminum', cap_front=False, cap_back=False, bevel=0.0)
    P.ngon([(x, yc - t / 2, z) for (x, z) in circ], mat='M_SignFace', uv=UV.planar((0, -1, 0)))
    P.ngon([(x, yc + t / 2, z) for (x, z) in circ][::-1], mat='M_SignFace', uv=UV.planar((0, 1, 0)))
    for z in (cz - 0.12, cz + 0.12):
        P.cyl((0, 0, z - 0.02), (0, 0, z + 0.02), POST_R + 0.008, seg=12, mat='M_Galvanized', bevel=0.003)
        P.box_mm((-0.025, yc + t / 2, z - 0.02), (0.025, -(POST_R + 0.006), z + 0.02), mat='M_Galvanized', bevel=0.0)
    # timetable case
    tw, th, td = 0.38, 0.55, 0.05
    tz = 1.45
    ty = -(POST_R + 0.01 + td)
    P.box_mm((-tw / 2, ty, tz - th / 2), (tw / 2, ty + td, tz + th / 2), mat='M_PaintedMetal_White', bevel=0.01)
    P.ngon([(-tw / 2 + 0.025, ty - 0.001, tz - th / 2 + 0.025), (tw / 2 - 0.025, ty - 0.001, tz - th / 2 + 0.025),
            (tw / 2 - 0.025, ty - 0.001, tz + th / 2 - 0.025), (-tw / 2 + 0.025, ty - 0.001, tz + th / 2 - 0.025)],
           mat='M_SignFace_Aux', uv=UV.planar((0, -1, 0)))
    P.note('Round sign face UV 0-1 (1:1) on both sides; timetable M_SignFace_Aux UV 0-1 (0.33 x 0.50).')
    P.finish()


@builder
def build_shotengai_lamp():
    P = Prop('shotengai_lamp', 'urban',
             desc='Shopping-street (商店街) lamp post ~5 m: globe lantern on top, two banner arms reaching over the '
                  'kerb with a double-sided vertical banner (M_BannerFace, 0-1 UV each side, 0.45 x 1.2 m)',
             origin='ground, pole centre', front='banner arms reach toward the road (Unity +Z); banner faces Unity +-X',
             preview=dict(az=-60, el=10, capsule_pos=(0.9, 0.4)))
    H = 4.6
    P.lathe([(0.15, 0.0), (0.15, 0.04), (0.11, 0.08), (0.09, 0.5), (0.075, 0.55)], seg=16,
            mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=40)
    P.cyl((0, 0, 0.5), (0, 0, H), 0.0700, 0.055, seg=14, mat='M_PaintedMetal_DarkGray', bevel=0.0, caps=False)
    # lantern: collar, globe, cap
    P.lathe([(0.06, H - 0.02), (0.09, H + 0.02), (0.11, H + 0.05)], seg=16, mat='M_PaintedMetal_DarkGray', bevel=0.0)
    P.sphere((0, 0, H + 0.25), 0.21, seg=20, rings=10, mat='M_EmissiveLamp', scale=(1, 1, 1.05),
             uv=UV.planar((0, -1, 0)))
    P.lathe([(0.0, H + 0.42), (0.16, H + 0.43), (0.19, H + 0.46), (0.13, H + 0.52), (0.04, H + 0.56),
             (0.03, H + 0.63), (0.0, H + 0.66)], seg=16, mat='M_PaintedMetal_DarkGray', bevel=0.0)
    P.empty('LightAnchor_0', (0, 0, H + 0.25), size=0.15)
    # banner arms toward the road (-Y)
    bl, bt, bw = 3.0, 4.2, 0.48
    for z in (bl, bt):
        P.cyl((0, -0.05, z), (0, -0.62, z), 0.016, seg=8, mat='M_PaintedMetal_DarkGray', bevel=0.0)
        P.sphere((0, -0.63, z), 0.024, seg=8, rings=5, mat='M_PaintedMetal_DarkGray')
        P.cyl((0, 0, z - 0.03), (0, 0, z + 0.03), 0.075, seg=14, mat='M_PaintedMetal_DarkGray', bevel=0.004)
    y0, y1 = -0.10, -0.58
    P.ngon([(0.0015, y0, bl + 0.03), (0.0015, y1, bl + 0.03), (0.0015, y1, bt - 0.04), (0.0015, y0, bt - 0.04)][::-1],
           mat='M_BannerFace', uv=UV.planar((1, 0, 0)))
    P.ngon([(-0.0015, y0, bl + 0.03), (-0.0015, y1, bl + 0.03), (-0.0015, y1, bt - 0.04), (-0.0015, y0, bt - 0.04)],
           mat='M_BannerFace', uv=UV.planar((-1, 0, 0)))
    P.note('Banner: two back-to-back quads on M_BannerFace, each 0-1 UV seen from its own side (aspect 0.48:1.17).')
    P.finish()


@builder
def build_manhole_cover_hydrant():
    P = Prop('manhole_cover_hydrant', 'urban',
             desc='Yellow-painted fire hydrant lid (消火栓) Φ0.6 m in a Φ0.72 frame, 6 mm proud',
             origin='road surface, centre')
    P.lathe([(0.30, -0.03), (0.30, 0.006), (0.0, 0.006)], seg=40, mat='M_Steel_Dark', bevel=0.0, sharp=50)
    P.ngon([(0.296 * math.cos(2 * math.pi * i / 40), 0.296 * math.sin(2 * math.pi * i / 40), 0.0062) for i in range(40)],
           mat='M_Deco_HydrantLid', uv=UV.planar((0, 0, 1), up=(0, 1, 0), bounds=(-0.296, -0.296, 0.296, 0.296)))
    P.lathe([(0.36, -0.03), (0.36, 0.002), (0.345, 0.005), (0.302, 0.005), (0.302, -0.03)], seg=40,
            mat='M_Steel_Dark', bevel=0.0, sharp=50)
    P.note('Text reads correctly when viewed from Unity +Z looking toward -Z (rotate in Y as needed).')
    P.finish()


@builder
def build_coin_parking_sign():
    P = Prop('coin_parking_sign', 'urban',
             desc='Coin-parking "P" lightbox sign 0.9 x 0.9 m on a 3.3 m square post (fictional operator), '
                  'double-sided, emissive face', origin='ground, post centre', front='faces Unity +Z and -Z')
    P.box_mm((-0.05, -0.05, 0.0), (0.05, 0.05, 2.45), mat='M_PaintedMetal_White', bevel=0.008)
    P.box_mm((-0.12, -0.12, 0.0), (0.12, 0.12, 0.012), mat='M_Galvanized', bevel=0.004)
    s, d = 0.92, 0.16
    zc = 2.45 + s / 2
    P.box_mm((-s / 2, -d / 2, zc - s / 2), (s / 2, d / 2, zc + s / 2), mat='M_PaintedMetal_White', bevel=0.02)
    q = s / 2 - 0.035
    P.ngon([(-q, -d / 2 - 0.002, zc - q), (q, -d / 2 - 0.002, zc - q), (q, -d / 2 - 0.002, zc + q),
            (-q, -d / 2 - 0.002, zc + q)], mat='M_Deco_ParkingSign', uv=UV.planar((0, -1, 0)))
    P.ngon([(q, d / 2 + 0.002, zc - q), (-q, d / 2 + 0.002, zc - q), (-q, d / 2 + 0.002, zc + q),
            (q, d / 2 + 0.002, zc + q)], mat='M_Deco_ParkingSign', uv=UV.planar((0, 1, 0)))
    P.finish()
