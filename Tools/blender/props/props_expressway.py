"""EXPRESSWAY (Shuto C1) + roadside traffic devices.
Build:  blender -b -P Tools/blender/props/build_props.py -- props_expressway [builder ...]
Textures: Tools/.venv/bin/python Tools/blender/props/make_textures_expressway.py"""
import math
from mathutils import Vector, Matrix, Euler
from propkit import (Prop, UV, builder, define_mat, circle2d, rect2d, rounded_rect2d, fillet, thicken2d,
                     arc_points)

define_mat('M_Deco_Chevron', c='#F6C400', r=0.35, tex='prop_chevron_albedo.png')
define_mat('M_Deco_ChevronWide', c='#F6C400', r=0.35, tex='prop_chevron_wide_albedo.png')
define_mat('M_Deco_EmergencyPhone', c='#007048', r=0.35, tex='prop_emergency_phone_albedo.png')
define_mat('M_Sealant', c='#2B2B2D', r=0.8)


def rot_about(origin, rot_deg):
    """Return f(local)->world: rotate local offset by Euler XYZ (deg) then translate to origin."""
    R = Euler([math.radians(a) for a in rot_deg], 'XYZ').to_matrix()
    o = Vector(origin)

    def f(p):
        return o + R @ Vector(p)
    return f


# ======================================================================================
# 1. Shuto pier (T-shaped RC pier)
# ======================================================================================
@builder
def build_shuto_pier():
    P = Prop('shuto_pier', 'expressway',
             desc='Shuto Expressway T-shaped RC pier: 2.4 x 3.0 m chamfered column, 16 m cap beam, top at 12.0 m',
             origin='ground, column centre', front='cap beam spans Unity Z (across the deck); deck runs along Unity X',
             preview=dict(extra=[('cap', 30, 18, ((-1.6, -8.2, 8.8), (1.6, 8.2, 12.6))),
                                 ('base', 35, 14, ((-2.0, -2.2, 0), (2.0, 2.2, 4.0)))]))
    # footing plinth (visible top of the buried footing)
    P.extrude(rounded_rect2d(3.6, 4.2, 0.25, 2), 0.3, axis='Z', offset=0.0, mat='M_Concrete_Dark', bevel=0.04,
              seg=2)
    # column: octagonal (chamfered rectangle) 2.4 (X) x 3.0 (Y)
    c = 0.35
    hx, hy = 1.2, 1.5
    col = [(-hx + c, -hy), (hx - c, -hy), (hx, -hy + c), (hx, hy - c), (hx - c, hy), (-hx + c, hy), (-hx, hy - c),
           (-hx, -hy + c)]
    P.extrude(col, 9.35, axis='Z', offset=0.28, mat='M_Concrete', bevel=0.04, seg=2, sharp=30)
    # construction-joint grooves (thin dark bands slightly proud... use recessed look via darker ring)
    for zj in (3.3, 6.4):
        ring = [(x * 1.004, y * 1.004) for (x, y) in col]
        P.extrude(ring, 0.03, axis='Z', offset=zj, mat='M_Concrete_Dark', bevel=0.0, sharp=30)
    # cap beam: profile in (y, z), extruded along X (2.6 m wide)
    cap = [(-8.0, 12.0), (-8.0, 10.6), (-2.3, 9.5), (2.3, 9.5), (8.0, 10.6), (8.0, 12.0)]
    P.prism(cap, -1.3, 1.3, mat='M_Concrete', bevel=0.05, seg=2, sharp=10)
    # bearing pedestals + elastomeric bearings + sole plates: 6 girder lines x 2 rows
    for y in (-6.5, -3.9, -1.3, 1.3, 3.9, 6.5):
        for x in (-0.65, 0.65):
            P.box_mm((x - 0.4, y - 0.4, 12.0 - 0.02), (x + 0.4, y + 0.4, 12.18), mat='M_Concrete_Light', bevel=0.02,
                     seg=1)
            P.box_mm((x - 0.28, y - 0.28, 12.18), (x + 0.28, y + 0.28, 12.30), mat='M_Rubber', bevel=0.012, seg=1)
            P.box_mm((x - 0.33, y - 0.33, 12.30), (x + 0.33, y + 0.33, 12.34), mat='M_Steel_Dark', bevel=0.006, seg=1)
    # seismic displacement stoppers (変位制限構造) at cap ends
    for sy in (-1, 1):
        y0 = sy * 7.35
        P.box_mm((-0.45, y0 - 0.35, 11.98), (0.45, y0 + 0.35, 12.55), mat='M_Concrete', bevel=0.03, seg=1)
    # drain pipe down the +X face near the corner (gray painted steel)
    xd = hx + 0.13
    yd = 0.9
    path = [Vector((xd, yd - 0.0, 9.55)), Vector((xd, yd, 0.65)), Vector((xd + 0.25, yd, 0.32))]
    P.pipe(fillet(path, 0.25, 4), 0.075, seg=12, mat='M_PaintedMetal_Gray', bevel=0.0)
    P.cyl((xd, yd, 9.5), (xd, yd, 9.62), 0.095, seg=12, mat='M_PaintedMetal_Gray', bevel=0.006)
    for z in (1.6, 3.6, 5.6, 7.6, 9.2):
        P.box_mm((hx - 0.01, yd - 0.03, z - 0.03), (xd + 0.09, yd + 0.03, z + 0.03), mat='M_Galvanized',
                 bevel=0.005, seg=1)
        P.cyl((xd, yd, z - 0.04), (xd, yd, z + 0.04), 0.085, seg=12, mat='M_Galvanized', bevel=0.004)
    # pier number plate (white) on the -Y face
    P.box_mm((-0.3, -hy - 0.02, 2.4), (0.3, -hy + 0.005, 2.75), mat='M_PlasticWhite', bevel=0.004, seg=1)
    P.note('Top of cap beam at 12.0 m; bearing sole plates top at 12.34 m (girder seat). Cap spans Unity Z -8..8.')
    P.finish()


# ======================================================================================
# 2. Shuto parapet (concrete wall barrier + sound barrier)
# ======================================================================================
PARA_H = 1.10
PARA_PROF = [(0.0, 0.0), (0.45, 0.0), (0.45, PARA_H), (0.20, PARA_H), (0.175, 0.25), (0.0, 0.075)]
PARA_INSET = [(0.015, 0.0), (0.435, 0.0), (0.435, PARA_H - 0.015), (0.212, PARA_H - 0.015), (0.19, 0.255),
              (0.015, 0.088)]


def _parapet_wall(P, L=4.0):
    # traffic face toward -Y; y=0 is the toe front edge; wall extends to +Y (outer side)
    P.prism(PARA_PROF, 0.012, L - 0.012, mat='M_Concrete', bevel=0.02, seg=2, sharp=20)
    # joint sealant at both tile ends (1.2 cm each side -> 2.4 cm joint between tiles)
    P.prism(PARA_INSET, 0.0, 0.012, mat='M_Sealant', bevel=0.0, sharp=20)
    P.prism(PARA_INSET, L - 0.012, L, mat='M_Sealant', bevel=0.0, sharp=20)
    # drain scupper at the base (dark recess plate) mid-tile
    P.box_mm((1.75, -0.004, 0.0), (2.25, 0.02, 0.06), mat='M_Steel_Dark', bevel=0.003, seg=1)
    # delineator: double-faced round reflector on a short stem on the wall top (front edge), facing along the road
    x = 1.0
    yt = 0.235
    P.box_mm((x - 0.03, yt - 0.03, PARA_H), (x + 0.03, yt + 0.03, PARA_H + 0.012), mat='M_Galvanized', bevel=0.003,
             seg=1)
    P.cyl((x, yt, PARA_H + 0.012), (x, yt, PARA_H + 0.12), 0.012, seg=8, mat='M_Galvanized', bevel=0.0)
    zr = PARA_H + 0.17
    P.cyl((x - 0.012, yt, zr), (x + 0.012, yt, zr), 0.055, seg=16, mat='M_PlasticWhite', bevel=0.004)
    P.cyl((x - 0.0135, yt, zr), (x - 0.012, yt, zr), 0.045, seg=16, mat='M_Reflector_White', bevel=0.0)
    P.cyl((x + 0.012, yt, zr), (x + 0.0135, yt, zr), 0.045, seg=16, mat='M_Reflector_White', bevel=0.0)


def _hpost(P, x, path):
    """H-section steel post swept along path; web along Y, flanges parallel to the barrier (XZ plane)."""
    fw, d, tf, tw = 0.15, 0.15, 0.012, 0.008   # flange width (X), depth (Y), flange & web thickness
    # profile (s, t) with path roughly +Z: side = up x tangent; use up=(1,0,0) -> side = X x Z = -Y
    # so s -> -Y, t -> +X
    prof = [(-d / 2, -fw / 2), (-d / 2, fw / 2), (-d / 2 + tf, fw / 2), (-d / 2 + tf, tw / 2), (d / 2 - tf, tw / 2),
            (d / 2 - tf, fw / 2), (d / 2, fw / 2), (d / 2, -fw / 2), (d / 2 - tf, -fw / 2), (d / 2 - tf, -tw / 2),
            (-d / 2 + tf, -tw / 2), (-d / 2 + tf, -fw / 2)]
    P.sweep(path, prof, closed=True, caps=True, up=(1, 0, 0), mat='M_PaintedMetal_Gray', bevel=0.0, sharp=30)


@builder
def build_shuto_parapet():
    for barrier in (True, False):
        name = 'shuto_parapet_4m' if barrier else 'shuto_parapet_4m_nobarrier'
        P = Prop(name, 'expressway', mirror_x=True,
                 desc='Shuto concrete wall parapet (壁高欄) 1.1 m' +
                      (' + 4 m translucent sound barrier on H-posts every 2 m' if barrier else ''),
                 origin='deck level at the traffic-face toe, tile start (Unity X=0); tile spans Unity X 0..4; '
                        'wall body extends to Unity -Z (away from traffic)',
                 preview=dict(az=-30, el=14,
                              extra=[('detail', -35, 10, ((-2.3, -0.6, 0), (0.2, 0.6, 4.1)))] if barrier else []))
        _parapet_wall(P)
        if barrier:
            yc = 0.33          # post centre line on the wall top
            ztop = PARA_H
            zk = 3.35          # knee where the top section inclines toward the road
            lean = math.radians(35)
            ltop = 0.72
            knee = Vector((0, yc, zk))
            top = knee + Vector((0, -math.sin(lean) * ltop, math.cos(lean) * ltop))
            for x in (0.0, 2.0):
                path = [Vector((x, yc, ztop + 0.02)), Vector((x, yc, zk)), Vector((x, top.y, top.z))]
                _hpost(P, x, path)
                # base plate + anchor nuts
                P.box_mm((x - 0.13, yc - 0.12, ztop), (x + 0.13, yc + 0.12, ztop + 0.025), mat='M_PaintedMetal_Gray',
                         bevel=0.004, seg=1)
                for dx in (-0.09, 0.09):
                    for dy in (-0.08, 0.08):
                        P.cyl((x + dx, yc + dy, ztop + 0.025), (x + dx, yc + dy, ztop + 0.05), 0.014, seg=6,
                              mat='M_Galvanized', bevel=0.0, sharp=70)
            # panels run continuously 0..4 through the post webs (tile-safe)
            t = 0.09
            # lower opaque metal panel band (sound absorbing louvre panel), 1.13..1.63
            P.box_mm((0.0, yc - t / 2, ztop + 0.03), (4.0, yc + t / 2, ztop + 0.53), mat='M_Aluminum', bevel=0.006,
                     seg=1, uv=UV.box())
            for z in (ztop + 0.155, ztop + 0.28, ztop + 0.405):
                P.box_mm((0.0, yc - t / 2 - 0.006, z - 0.008), (4.0, yc - t / 2 + 0.001, z + 0.008),
                         mat='M_PaintedMetal_Gray', bevel=0.0)
            # translucent panels with aluminium frames: 1.63..2.5, 2.5..3.35 (vertical) + inclined top
            zs = [ztop + 0.53, 2.49, zk]
            for (za, zb) in zip(zs[:-1], zs[1:]):
                P.box_mm((0.0, yc - 0.008, za + 0.03), (4.0, yc + 0.008, zb - 0.03), mat='M_Glass_SoundBarrier',
                         bevel=0.0, uv=UV.box())
            for z in zs:
                P.box_mm((0.0, yc - 0.035, z - 0.03), (4.0, yc + 0.035, z + 0.03), mat='M_Aluminum', bevel=0.006,
                         seg=1)
            # inclined section (same lean as posts)
            n = Vector((0, -math.sin(lean), math.cos(lean)))       # along the incline
            nrm = Vector((0, math.cos(lean), math.sin(lean)))      # panel normal (toward outside/up)
            a = knee + n * 0.03
            b = top - n * 0.03
            P.poly([(0.0, a.y - nrm.y * 0.008, a.z - nrm.z * 0.008), (4.0, a.y - nrm.y * 0.008, a.z - nrm.z * 0.008),
                    (4.0, b.y - nrm.y * 0.008, b.z - nrm.z * 0.008), (0.0, b.y - nrm.y * 0.008, b.z - nrm.z * 0.008),
                    (0.0, a.y + nrm.y * 0.008, a.z + nrm.z * 0.008), (4.0, a.y + nrm.y * 0.008, a.z + nrm.z * 0.008),
                    (4.0, b.y + nrm.y * 0.008, b.z + nrm.z * 0.008), (0.0, b.y + nrm.y * 0.008, b.z + nrm.z * 0.008)],
                   [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (3, 2, 6, 7), (0, 3, 7, 4), (1, 5, 6, 2)],
                   mat='M_Glass_SoundBarrier', bevel=0.0, uv=UV.box())
            # top edge rail
            P.sweep([Vector((0.0, top.y, top.z)), Vector((4.0, top.y, top.z))],
                    [(-0.035, -0.03), (0.035, -0.03), (0.035, 0.03), (-0.035, 0.03)], mat='M_Aluminum',
                    bevel=0.006, seg=1)
            P.note('Sound barrier: aluminium louvre band 1.13-1.63 m, translucent panels to 3.35 m, inclined top '
                   'section (35 deg toward traffic) to ~3.95 m; H-posts at Unity X=0 and 2.')
        P.note('Concrete wall: 1.10 m tall, base 0.45, top 0.25, F-shape traffic face; 2.4 cm sealant joint at tile ends.')
        P.finish()


# ======================================================================================
# 3. Shuto twin-arm light pole
# ======================================================================================
@builder
def build_shuto_light_pole():
    P = Prop('shuto_light_pole', 'expressway',
             desc='Twin-arm (Y-type) expressway road light, ~10 m, sodium luminaires reaching over both carriageways',
             origin='bottom of the base plate (mount on median/parapet top)', front='arms reach Unity +Z and -Z',
             preview=dict(extra=[('head', 35, 10, ((-0.4, -2.6, 8.4), (0.4, 2.6, 10.3)))]))
    # base plate + anchor nuts + ribs
    P.box_mm((-0.21, -0.21, 0.0), (0.21, 0.21, 0.03), mat='M_Galvanized', bevel=0.006, seg=1)
    for dx in (-0.16, 0.16):
        for dy in (-0.16, 0.16):
            P.cyl((dx, dy, 0.03), (dx, dy, 0.065), 0.018, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70)
            P.cyl((dx, dy, 0.065), (dx, dy, 0.09), 0.010, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70)
    # tapered pole
    H = 8.9
    P.cyl((0, 0, 0.03), (0, 0, H), 0.13, 0.085, seg=16, mat='M_Galvanized', bevel=0.0, caps=False)
    P.cyl((0, 0, 0.03), (0, 0, 0.42), 0.145, seg=16, mat='M_Galvanized', bevel=0.006)   # base collar
    # hand hole door
    P.box_mm((-0.05, -0.138, 0.65), (0.05, -0.118, 0.95), mat='M_Galvanized', bevel=0.006, seg=1)
    # splitting knuckle + two curved arms (Y-type)
    P.cyl((0, 0, H - 0.25), (0, 0, H + 0.1), 0.10, 0.085, seg=16, mat='M_Galvanized', bevel=0.008)
    anchors = []
    for s in (-1, 1):
        path = [Vector((0, s * 0.02, H)), Vector((0, s * 0.05, H + 0.5)), Vector((0, s * 1.95, H + 0.95))]
        P.pipe(fillet(path, 0.8, 8), 0.05, seg=12, mat='M_Galvanized', bevel=0.0)
        # luminaire: flat streamlined housing, long axis along Y
        y0 = s * 1.9
        yc = s * 2.22
        zc = H + 0.95
        outline = rounded_rect2d(0.78, 0.34, 0.12, 3)   # (y, x) after mapping below
        # housing as extrude along Z of a rounded rect in (x, y) plane
        hous = [(x2, y2) for (y2, x2) in outline]
        P.extrude([(x2, y2 + yc) for (x2, y2) in hous], 0.11, axis='Z', offset=zc - 0.03, mat='M_PaintedMetal_LightGray',
                  bevel=0.03, seg=2)
        # domed top
        P.extrude([(x2 * 0.85, y2 * 0.9 + yc) for (x2, y2) in hous], 0.04, axis='Z', offset=zc + 0.08,
                  mat='M_PaintedMetal_LightGray', bevel=0.015, seg=2)
        # arm socket
        P.cyl((0, s * 1.75, zc), (0, s * 1.93, zc + 0.01), 0.055, seg=12, mat='M_PaintedMetal_LightGray', bevel=0.006)
        # emitter (glass bowl underside)
        em = [(x2 * 0.82, y2 * 0.84 + yc) for (x2, y2) in hous]
        P.extrude(em, 0.035, axis='Z', offset=zc - 0.065, mat='M_EmissiveLamp_Sodium', bevel=0.01, seg=1,
                  uv=UV.planar((0, 0, -1)))
        anchors.append((0, yc, zc - 0.07))
    for i, a in enumerate(anchors):
        P.empty(f'LightAnchor_{i}', a, size=0.2)
    P.note('LightAnchor_0/1 at the sodium emitter centres (~9.78 m); aim spot lights straight down (-Unity Y).')
    P.finish()


# ======================================================================================
# 4. Overhead sign gantry (門型標識柱)
# ======================================================================================
@builder
def build_overhead_sign_gantry():
    P = Prop('overhead_sign_gantry', 'expressway',
             desc='Expressway portal sign gantry, 15 m span (3 lanes + shoulders), box truss, 8 x 2.8 m guide sign',
             origin='ground at span centre', front='sign face Unity +Z (traffic approaches heading Unity -Z); span along Unity X',
             preview=dict(az=30, el=12, extra=[('sign', 25, 6, ((-8.0, -0.4, 4.6), (1.0, 1.5, 8.4))),
                                               ('back', 160, 15, ((-8.0, -0.4, 4.6), (8.0, 1.5, 8.4)))]))
    span = 7.5
    yl = 0.6                 # leg / truss centre line (behind the sign)
    zt0, zt1 = 6.1, 7.3      # truss bottom / top chord heights
    ty0, ty1 = 0.2, 1.0      # truss front / back chord y
    # legs: steel pipes on base plates + concrete pedestals
    for sx in (-1, 1):
        x = sx * span
        P.extrude(rounded_rect2d(1.1, 1.1, 0.08, 2, cx=x, cy=yl), 0.35, axis='Z', offset=0.0, mat='M_Concrete',
                  bevel=0.025, seg=2)
        P.box_mm((x - 0.38, yl - 0.38, 0.35), (x + 0.38, yl + 0.38, 0.39), mat='M_PaintedMetal_Gray', bevel=0.006,
                 seg=1)
        for dx in (-0.3, 0.3):
            for dy in (-0.3, 0.3):
                P.cyl((x + dx, yl + dy, 0.39), (x + dx, yl + dy, 0.45), 0.022, seg=6, mat='M_Galvanized', bevel=0.0,
                      sharp=70)
        P.cyl((x, yl, 0.39), (x, yl, zt1 + 0.25), 0.23, 0.2, seg=20, mat='M_PaintedMetal_Gray', bevel=0.01)
        P.cyl((x, yl, zt1 + 0.25), (x, yl, zt1 + 0.29), 0.215, seg=20, mat='M_PaintedMetal_Gray', bevel=0.008)
        # beam-to-leg connection box
        P.box_mm((x - 0.32, ty0 - 0.08, zt0 - 0.15), (x + 0.32, ty1 + 0.08, zt1 + 0.12), mat='M_PaintedMetal_Gray',
                 bevel=0.012, seg=1)
    # box truss: 4 chords + lacing on 4 faces
    xa, xb = -span + 0.32, span - 0.32
    rc = 0.07
    chords = [(ty0, zt0), (ty0, zt1), (ty1, zt0), (ty1, zt1)]
    for (y, z) in chords:
        P.cyl((xa, y, z), (xb, y, z), rc, seg=10, mat='M_PaintedMetal_Gray', bevel=0.0, caps=True)
    nb = 12
    bw = (xb - xa) / nb
    rl = 0.032
    for i in range(nb):
        x0 = xa + i * bw; x1 = x0 + bw
        flip = (i % 2 == 0)
        xs, xe = (x0, x1) if flip else (x1, x0)
        # front & back vertical faces
        for y in (ty0, ty1):
            P.cyl((xs, y, zt0), (xe, y, zt1), rl, seg=6, mat='M_PaintedMetal_Gray', bevel=0.0, sharp=70)
        # top & bottom horizontal faces
        for z in (zt0, zt1):
            P.cyl((xs, ty0, z), (xe, ty1, z), rl * 0.85, seg=6, mat='M_PaintedMetal_Gray', bevel=0.0, sharp=70)
    for i in range(nb + 1):
        x = xa + i * bw
        for y in (ty0, ty1):
            P.cyl((x, y, zt0), (x, y, zt1), rl * 0.9, seg=6, mat='M_PaintedMetal_Gray', bevel=0.0, sharp=70)
    # ---- main sign panel 8.0 x 2.8 (bottom at 5.2 m), centred at x = -2.6
    sx0, sx1, sz0, sz1 = -6.6, 1.4, 5.2, 8.0
    th = 0.06
    P.box_mm((sx0, -0.02, sz0), (sx1, -0.02 + th, sz1), mat='M_Aluminum', bevel=0.012, seg=1)
    P.ngon([(sx0 + 0.004, -0.0215, sz0 + 0.004), (sx1 - 0.004, -0.0215, sz0 + 0.004), (sx1 - 0.004, -0.0215, sz1 - 0.004),
            (sx0 + 0.004, -0.0215, sz1 - 0.004)], mat='M_SignFace', uv=UV.planar((0, -1, 0)))
    # ---- auxiliary panel (lane / distance) 3.2 x 2.0, right side
    ax0, ax1, az0, az1 = 2.2, 5.4, 5.6, 7.6
    P.box_mm((ax0, -0.02, az0), (ax1, -0.02 + th, az1), mat='M_Aluminum', bevel=0.012, seg=1)
    P.ngon([(ax0 + 0.004, -0.0215, az0 + 0.004), (ax1 - 0.004, -0.0215, az0 + 0.004), (ax1 - 0.004, -0.0215, az1 - 0.004),
            (ax0 + 0.004, -0.0215, az1 - 0.004)], mat='M_SignFace_Aux', uv=UV.planar((0, -1, 0)))
    # vertical Z-bar stiffeners behind panels, clamped to the truss front chords
    for x in [sx0 + 0.5 + k * 1.75 for k in range(5)] + [ax0 + 0.5, ax1 - 0.5]:
        z0 = sz0 + 0.1 if x < sx1 else az0 + 0.1
        z1 = sz1 - 0.1 if x < sx1 else az1 - 0.1
        P.box_mm((x - 0.04, 0.04, z0), (x + 0.04, ty0 - 0.02, z1), mat='M_Galvanized', bevel=0.005, seg=1)
    # sign lighting: 4 fixtures on arms below the main panel aiming up at the face
    lights = []
    for x in (-5.6, -3.6, -1.6, 0.4):
        P.box_mm((x - 0.025, -0.02, sz0 - 0.08), (x + 0.025, 0.04, sz0 + 0.06), mat='M_Galvanized', bevel=0.004, seg=1)
        P.box_mm((x - 0.025, -0.62, sz0 - 0.08), (x + 0.025, -0.02, sz0 - 0.04), mat='M_Galvanized', bevel=0.004, seg=1)
        P.box((0.36, 0.2, 0.12), (x, -0.68, sz0 - 0.02), rot=(-35, 0, 0), mat='M_PaintedMetal_LightGray', bevel=0.015,
              seg=1)
        P.box((0.3, 0.012, 0.09), (x, -0.62, sz0 + 0.02), rot=(-35, 0, 0), mat='M_EmissiveLamp_LED', bevel=0.0)
        lights.append((x, -0.62, sz0 + 0.02))
    # maintenance walkway (検査路) behind the sign at the panel-bottom level
    wz = 5.1
    P.box_mm((sx0, 0.06, wz - 0.06), (sx1, 0.86, wz), mat='M_Galvanized', bevel=0.006, seg=1)
    for x in [sx0 + 0.1 + k * 1.0 for k in range(9)]:
        P.box_mm((x - 0.03, 0.80, wz), (x + 0.03, 0.86, wz + 1.1), mat='M_Galvanized', bevel=0.005, seg=1)
        P.cyl((x, 0.46, wz), (x, ty0 + 0.25, zt0), 0.02, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70)
    for z in (wz + 0.55, wz + 1.1):
        P.cyl((sx0, 0.83, z), (sx1 - 0.0, 0.83, z), 0.024, seg=8, mat='M_Galvanized', bevel=0.0)
    for i, l in enumerate(lights):
        P.empty(f'LightAnchor_{i}', l, size=0.15)
    P.note('M_SignFace: main panel 8.0 x 2.8 m (bottom 5.2 m), 0-1 UV, texture aspect 2.86:1. M_SignFace_Aux: '
           '3.2 x 2.0 m panel (aspect 1.6:1). LightAnchor_0..3 = sign-lighting fixtures aimed up at the face.')
    P.finish()


# ======================================================================================
# 5. Jersey barrier (precast concrete, 2 m)
# ======================================================================================
NJ = [(-0.305, 0.0), (0.305, 0.0), (0.305, 0.075), (0.127, 0.33), (0.075, 0.81), (-0.075, 0.81), (-0.127, 0.33),
      (-0.305, 0.075)]


def nj_half(z):
    if z <= 0.075:
        return 0.305
    if z <= 0.33:
        return 0.305 - (z - 0.075) * (0.305 - 0.127) / (0.33 - 0.075)
    return 0.127 - (z - 0.33) * (0.127 - 0.075) / (0.81 - 0.33)


@builder
def build_jersey_barrier_2m():
    P = Prop('jersey_barrier_2m', 'expressway', mirror_x=True,
             desc='Precast concrete New Jersey barrier, 2 m tile (810 tall, 610 base, 150 top)',
             origin='ground, barrier centre line, tile start (Unity X=0); tile spans Unity X 0..2')
    P.prism(NJ, 0.0, 2.0, mat='M_Concrete', bevel=0.015, seg=2, sharp=20)
    # drain scupper openings (dark) on both toes at mid-length
    for sy in (-1, 1):
        y = sy * 0.3062
        pts = [(0.85, y, 0.0), (1.15, y, 0.0), (1.15, y, 0.068), (0.85, y, 0.068)]
        P.ngon(pts if sy < 0 else pts[::-1], mat='M_Steel_Dark', uv=UV.box())
    # lifting anchors on top
    for x in (0.45, 1.55):
        P.box_mm((x - 0.05, -0.03, 0.795), (x + 0.05, 0.03, 0.812), mat='M_Steel_Dark', bevel=0.0)
    # pin-and-loop connectors: steel loops protruding at both ends (interleaving heights)
    def loop(xe, z, sgn):
        path = [Vector((xe - sgn * 0.06, -0.06, z)), Vector((xe + sgn * 0.03, -0.06, z)),
                Vector((xe + sgn * 0.07, 0.0, z)), Vector((xe + sgn * 0.03, 0.06, z)), Vector((xe - sgn * 0.06, 0.06, z))]
        P.pipe(fillet(path, 0.04, 3), 0.011, seg=6, mat='M_Galvanized', bevel=0.0)
    for z in (0.2, 0.6):
        loop(0.0, z, -1)
    for z in (0.32, 0.72):
        loop(2.0, z, 1)
    P.note('Symmetric profile (either side can face traffic). Steel connector loops protrude ~7 cm past both ends '
           'and interleave with the neighbouring tile.')
    P.finish()


# ======================================================================================
# 6. Tunnel lamp strips (sodium / LED)
# ======================================================================================
def _tunnel_strip(name, kind):
    sodium = kind == 'sodium'
    P = Prop(name, 'expressway', mirror_x=True,
             desc=f'Tunnel wall lighting tile, 4 m: cable raceway + 2 {"sodium" if sodium else "LED"} fixtures',
             origin='wall plane at the raceway centre, tile start (Unity X=0); fixtures project toward Unity +Z',
             front='light faces Unity +Z, tilted 30 deg down',
             preview=dict(wall=True, ground_z=-4.6, az=-30, el=8,
                          extra=[('detail', -35, 5, ((-2.0, -0.45, -0.5), (0.0, 0.0, 0.25)))]))
    # continuous raceway
    P.box_mm((0.0, -0.09, -0.06), (4.0, 0.0, 0.06), mat='M_Galvanized', bevel=0.006, seg=1)
    P.box_mm((0.0, -0.095, -0.035), (4.0, -0.088, 0.035), mat='M_Galvanized', bevel=0.0)
    tilt = 30.0
    anchors = []
    for xc in (1.0, 3.0):
        if sodium:
            L, D, Hh = 1.0, 0.24, 0.30
        else:
            L, D, Hh = 1.4, 0.13, 0.20
        # fixture pivot below the raceway, housing hangs and tilts toward the road
        piv = Vector((xc, -0.10, -0.10 - Hh / 2))
        f = rot_about(piv, (tilt, 0, 0))
        # brackets from raceway to housing back
        for dx in (-L * 0.35, L * 0.35):
            P.box_mm((xc + dx - 0.02, -0.12, -0.10), (xc + dx + 0.02, -0.04, 0.06), mat='M_Galvanized', bevel=0.004,
                     seg=1)
        # housing (stainless)
        P.box((L, D, Hh), f((0, -D / 2, 0)), rot=(tilt, 0, 0), mat='M_Aluminum', bevel=0.02, seg=2)
        # front glass frame + emitter
        P.box((L - 0.04, 0.012, Hh - 0.04), f((0, -D - 0.004, 0)), rot=(tilt, 0, 0), mat='M_Galvanized', bevel=0.004,
              seg=1)
        em_c = f((0, -D - 0.012, 0))
        P.box((L - 0.12, 0.01, Hh - 0.1), em_c, rot=(tilt, 0, 0),
              mat='M_EmissiveLamp_Sodium' if sodium else 'M_EmissiveLamp_LED', bevel=0.0,
              uv=UV.planar((0, -math.cos(math.radians(tilt)), -math.sin(math.radians(tilt)))))
        if sodium:
            # cooling fins on top of housing
            for k in range(5):
                fx = (k - 2) * 0.16
                P.box((0.012, D * 0.8, 0.035), f((fx, -D / 2, Hh / 2 + 0.017)), rot=(tilt, 0, 0), mat='M_Aluminum',
                      bevel=0.0)
        # cable gland
        P.cyl(f((L / 2 + 0.0, -D / 2, 0)), f((L / 2 + 0.05, -D / 2, 0)), 0.02, seg=8, mat='M_PlasticBlack', bevel=0.0)
        anchors.append(tuple(em_c))
    for i, a in enumerate(anchors):
        P.empty(f'LightAnchor_{i}', a, size=0.15)
    P.note('Mount on the tunnel wall at ~4.5-5 m; LightAnchor_0/1 at emitter centres (fixtures at Unity X=1 and 3).')
    P.finish()


@builder
def build_tunnel_lamp_strip():
    _tunnel_strip('tunnel_lamp_strip_4m_sodium', 'sodium')
    _tunnel_strip('tunnel_lamp_strip_4m_led', 'led')


# ======================================================================================
# 7. Crash cushion (gore-point impact attenuator)
# ======================================================================================
def _thrie_profile(h0=0.18, h1=0.80, depth=0.06):
    """3-ridge (thrie-beam-like) fender profile centreline: list (d, z), d = outward depth."""
    pts = []
    n = 3
    zs = [h0 + (h1 - h0) * k / (2 * n) for k in range(2 * n + 1)]
    for k, z in enumerate(zs):
        d = depth if k % 2 == 1 else 0.0
        pts.append((d, z))
    pts = [(0.0, h0 - 0.02)] + pts + [(0.0, h1 + 0.02)]
    sm = fillet(pts, 0.04, 2)
    return [(p.x, p.y) for p in sm]


@builder
def build_crash_cushion():
    P = Prop('crash_cushion', 'expressway',
             desc='Gore-point crash cushion (impact attenuator), 4.6 m, overlapping steel fender bays, striped nose',
             origin='ground under the rear backstop centre', front='nose faces oncoming traffic, Unity +Z',
             preview=dict(az=-40, el=18))
    W = 0.80
    hw = W / 2
    # rear backstop
    P.box_mm((-0.48, -0.05, 0.0), (0.48, 0.30, 0.92), mat='M_Steel_Dark', bevel=0.015, seg=1)
    P.box_mm((-0.55, 0.05, 0.0), (0.55, 0.40, 0.06), mat='M_Steel_Dark', bevel=0.01, seg=1)
    # centre guide track
    P.box_mm((-0.09, -4.15, 0.0), (0.09, -0.05, 0.09), mat='M_Galvanized', bevel=0.01, seg=1)
    # diaphragms
    nbay = 5
    bay = 0.80
    ys = [-0.05 - bay * i for i in range(nbay + 1)]
    for y in ys[1:]:
        P.box_mm((-hw + 0.02, y - 0.05, 0.10), (hw - 0.02, y + 0.03, 0.86), mat='M_Galvanized', bevel=0.01, seg=1)
        P.box_mm((-0.12, y - 0.10, 0.0), (0.12, y + 0.08, 0.12), mat='M_Steel_Dark', bevel=0.01, seg=1)
    # energy-absorbing cartridges inside each bay (visible from above)
    for i in range(nbay):
        y0, y1 = ys[i + 1] + 0.06, ys[i] - 0.06
        P.box_mm((-hw + 0.05, y0, 0.14), (hw - 0.05, y1, 0.74), mat='M_PlasticBlack', bevel=0.03, seg=2)
        P.box_mm((-hw + 0.08, y0 + 0.03, 0.74), (hw - 0.08, y1 - 0.03, 0.76), mat='M_PlasticYellow', bevel=0.008,
                 seg=1)
    # side fender panels (telescoping: front panels outermost)
    prof = _thrie_profile()
    for i in range(nbay):
        ya = ys[i] + 0.12          # rear end (overlaps under the panel behind)
        yb = ys[i + 1] - 0.02      # front end
        off = 0.012 * i
        for sgn in (-1, 1):
            xs = sgn * (hw + off)
            # path from front (yb) to rear (ya): tangent +Y, up Z -> side = Z x Y = -X
            # we want outward depth along sgn*X -> s = -sgn * d
            outline = thicken2d([(-sgn * d, z) for (d, z) in prof], 0.006)
            P.sweep([Vector((xs, yb, 0.0)), Vector((xs, ya, 0.0))], outline, closed=True, caps=True,
                    mat='M_Galvanized', bevel=0.0, sharp=35)
            # bolts at the front end
            for z in (0.28, 0.49, 0.70):
                P.cyl((xs + sgn * 0.03, yb + 0.06, z), (xs + sgn * 0.075, yb + 0.06, z), 0.014, seg=6,
                      mat='M_Steel_Dark', bevel=0.0, sharp=70)
    # nose: yellow D-shaped plastic cover with striped curved front
    yn = ys[-1] - 0.04
    R = hw + 0.06
    z0, z1 = 0.08, 0.86
    P.lathe([(R, z0), (R, z1)], seg=16, loc=(0, yn, 0), start_angle=180, sweep=180, mat='M_Deco_HazardStripe',
            cap_bottom=False, cap_top=False, bevel=0.0, sharp=60,
            uv=UV.scaled(UV.cyl((0, yn, 0), (0, yn, 1), norm=True), 2.4, 1 / 0.5))
    top = [(R * math.cos(math.radians(180 + 180 * k / 16)), yn + R * math.sin(math.radians(180 + 180 * k / 16)), z1)
           for k in range(17)]
    P.ngon(top, mat='M_PlasticYellow', uv=UV.box(), flip=False)
    P.ngon([(p[0], p[1], z0) for p in top], mat='M_PlasticYellow', uv=UV.box(), flip=True)
    # nose back plate (closing the D)
    P.box_mm((-R, yn - 0.0, z0), (R, yn + 0.05, z1), mat='M_PlasticYellow', bevel=0.012, seg=1)
    # top rim
    P.lathe([(R + 0.012, z1 - 0.03), (R + 0.012, z1 + 0.01), (R - 0.03, z1 + 0.01)], seg=16, loc=(0, yn, 0),
            start_angle=180, sweep=180, mat='M_PlasticBlack', cap_bottom=False, cap_top=False, bevel=0.0)
    P.note('Nose (yellow/black M_Deco_HazardStripe) at Unity Z ~ +4.5; backstop at origin. Place in gore areas with '
           'the nose toward approaching traffic.')
    P.finish()


# ======================================================================================
# 8. Post cone (ポストコーン)
# ======================================================================================
@builder
def build_post_cone():
    P = Prop('post_cone', 'urban', desc='Japanese flexible delineator post (ポストコーン), 80 mm x 0.8 m, orange/white',
             origin='ground, post centre')
    # bolted round base
    P.lathe([(0.15, 0.0), (0.15, 0.015), (0.12, 0.04), (0.07, 0.05), (0.0, 0.05)], seg=24, mat='M_PlasticBlack',
            bevel=0.0, sharp=40)
    for a in (45, 135, 225, 315):
        x, y = 0.115 * math.cos(math.radians(a)), 0.115 * math.sin(math.radians(a))
        P.cyl((x, y, 0.02), (x, y, 0.035), 0.012, seg=6, mat='M_Galvanized', bevel=0.0, sharp=70)
    # collar
    P.lathe([(0.065, 0.045), (0.065, 0.09), (0.045, 0.105)], seg=16, mat='M_PlasticOrange', bevel=0.0, cap_bottom=False)
    r = 0.04
    cuts = [(0.10, 'M_PlasticOrange'), (0.52, 'M_Reflector_White'), (0.60, 'M_PlasticOrange'),
            (0.67, 'M_Reflector_White'), (0.75, 'M_PlasticOrange'), (0.785, None)]
    for (za, m), (zb, _) in zip(cuts[:-1], cuts[1:]):
        prof = [(r, za), (r, zb)]
        if zb == 0.785:
            prof = [(r, za), (r, zb), (0.032, 0.797), (0.0, 0.80)]
        P.lathe(prof, seg=16, mat=m, cap_bottom=False, cap_top=False, bevel=0.0, sharp=50,
                uv=UV.cyl((0, 0, 0), (0, 0, 1), norm=True))
    P.finish()


# ======================================================================================
# 9. Emergency phone box (非常電話)
# ======================================================================================
@builder
def build_emergency_phone_box():
    P = Prop('emergency_phone_box', 'expressway',
             desc='Expressway emergency telephone (非常電話) cabinet on a pedestal with a green sign plate',
             origin='ground, pedestal centre', front='door + sign face Unity +Z')
    # pedestal
    P.box_mm((-0.17, -0.12, 0.0), (0.17, 0.12, 0.02), mat='M_Galvanized', bevel=0.004, seg=1)
    P.box_mm((-0.09, -0.07, 0.02), (0.09, 0.07, 0.45), mat='M_PaintedMetal_LightGray', bevel=0.01, seg=1)
    # cabinet 0.5 x 0.3 x 0.7
    cz0, cz1 = 0.45, 1.15
    P.box_mm((-0.25, -0.15, cz0), (0.25, 0.15, cz1), mat='M_PaintedMetal_Ivory', bevel=0.02, seg=2)
    # sloped rain hood
    P.poly([(-0.28, -0.20, cz1 + 0.005), (0.28, -0.20, cz1 + 0.005), (0.28, 0.17, cz1 + 0.06), (-0.28, 0.17, cz1 + 0.06),
            (-0.28, -0.20, cz1 + 0.025), (0.28, -0.20, cz1 + 0.025), (0.28, 0.17, cz1 + 0.08), (-0.28, 0.17, cz1 + 0.08)],
           [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)],
           mat='M_PaintedMetal_Ivory', bevel=0.006, seg=1)
    # door (orange, inset frame) + handle + window
    P.box_mm((-0.21, -0.158, cz0 + 0.05), (0.21, -0.145, cz1 - 0.05), mat='M_PaintedMetal_Orange', bevel=0.006, seg=1)
    P.box_mm((0.14, -0.175, 0.74), (0.17, -0.155, 0.86), mat='M_Chrome', bevel=0.004, seg=1)
    P.box_mm((-0.13, -0.162, 0.90), (0.08, -0.155, 1.04), mat='M_Glass', bevel=0.0)
    P.box_mm((-0.15, -0.166, 0.60), (0.06, -0.156, 0.70), mat='M_PlasticWhite', bevel=0.0)
    # sign plate 0.6 x 0.3 on two short posts above the cabinet
    for x in (-0.2, 0.2):
        P.cyl((x, 0.05, cz1 + 0.06), (x, 0.05, cz1 + 0.62), 0.016, seg=8, mat='M_Galvanized', bevel=0.0)
    sz0, sz1 = cz1 + 0.30, cz1 + 0.60
    P.box_mm((-0.3, 0.02, sz0), (0.3, 0.045, sz1), mat='M_Aluminum', bevel=0.005, seg=1)
    P.ngon([(-0.296, 0.0195, sz0 + 0.004), (0.296, 0.0195, sz0 + 0.004), (0.296, 0.0195, sz1 - 0.004),
            (-0.296, 0.0195, sz1 - 0.004)], mat='M_Deco_EmergencyPhone', uv=UV.planar((0, -1, 0)))
    P.finish()


# ======================================================================================
# 10. Chevron curve-alignment signs (矢印板)
# ======================================================================================
def _sign_panel(P, x0, x1, z0, z1, face_mat, y_front=-0.05, th=0.02):
    """Flat sign plate: aluminium body with rolled rim + front face (0-1 UV) facing -Y."""
    P.box_mm((x0, y_front, z0), (x1, y_front + th, z1), mat='M_Aluminum', bevel=0.004, seg=1)
    e = 0.006
    P.ngon([(x0 + e, y_front - 0.0015, z0 + e), (x1 - e, y_front - 0.0015, z0 + e), (x1 - e, y_front - 0.0015, z1 - e),
            (x0 + e, y_front - 0.0015, z1 - e)], mat=face_mat, uv=UV.planar((0, -1, 0)))


def _clamp(P, x, y_post, z, r_post):
    P.box_mm((x - 0.05, y_post - r_post - 0.035, z - 0.02), (x + 0.05, y_post - r_post + 0.005, z + 0.02),
             mat='M_Galvanized', bevel=0.004, seg=1)
    P.torus((x, y_post, z), r_post + 0.006, 0.006, seg=12, rseg=4, mat='M_Galvanized')


@builder
def build_chevron_curve_sign():
    # single chevron on one post
    P = Prop('chevron_curve_sign', 'mountain',
             desc='Yellow/black chevron curve-alignment panel (矢印板) 0.45 x 0.6 m on a galvanized post',
             origin='ground, post centre', front='face Unity +Z (chevron points to Unity -X; rotate 180 about Y '
                                                 'or use the other side of the road for the opposite curve)')
    rp = 0.0303
    P.cyl((0, 0, 0), (0, 0, 1.66), rp, seg=12, mat='M_Galvanized', bevel=0.004)
    P.lathe([(rp + 0.003, 1.655), (rp + 0.003, 1.675), (0.0, 1.69)], seg=12, mat='M_PlasticBlack', bevel=0.0)
    _sign_panel(P, -0.225, 0.225, 1.0, 1.6, 'M_Deco_Chevron', y_front=-rp - 0.04)
    for z in (1.12, 1.48):
        _clamp(P, 0, 0, z, rp)
    P.note('M_Deco_Chevron face (texture prop_chevron_albedo.png) mapped 0-1; chevron points to the viewer\'s right.')
    P.finish()

    P = Prop('chevron_board_wide', 'mountain',
             desc='Wide chevron board (1.2 x 0.45 m, three chevrons) on two galvanized posts',
             origin='ground, between the posts', front='face Unity +Z')
    for x in (-0.45, 0.45):
        P.cyl((x, 0, 0), (x, 0, 1.36), rp, seg=12, mat='M_Galvanized', bevel=0.004)
        P.lathe([(rp + 0.003, 1.355), (rp + 0.003, 1.375), (0.0, 1.39)], seg=12, loc=(x, 0, 0), mat='M_PlasticBlack',
                bevel=0.0)
        for z in (0.97, 1.23):
            _clamp(P, x, 0, z, rp)
    _sign_panel(P, -0.6, 0.6, 0.875, 1.325, 'M_Deco_ChevronWide', y_front=-rp - 0.04)
    P.finish()


# ======================================================================================
# 11. Convex traffic mirror (カーブミラー)
# ======================================================================================
def _mirror(P, centre, yaw=0.0, tilt=6.0, R=0.4):
    """Round convex road mirror (diameter 2R) facing -Y rotated by yaw (deg, about Z) and tilted down."""
    rot = (90 + tilt, 0, yaw)
    c = Vector(centre)
    # orange back shell (dome toward the back = local -Z)
    P.lathe([(R + 0.035, 0.0), (R + 0.03, -0.035), (R * 0.75, -0.075), (0.0, -0.09)], seg=32, loc=c, rot=rot,
            mat='M_PaintedMetal_Orange', bevel=0.0, sharp=50, cap_bottom=False)
    # frame ring (front lip)
    P.lathe([(R - 0.005, 0.012), (R + 0.035, 0.012), (R + 0.04, 0.0), (R + 0.035, -0.005)], seg=32, loc=c, rot=rot,
            mat='M_PaintedMetal_Orange', bevel=0.0, sharp=50, cap_bottom=False, cap_top=False)
    # convex mirror surface
    prof = [(R, 0.0)] + [(R * math.cos(math.radians(a)), 0.035 * math.sin(math.radians(a)) + 0.004)
                         for a in (20, 40, 60, 80)] + [(0.0, 0.039)]
    P.lathe(prof, seg=32, loc=c, rot=rot, mat='M_Mirror', bevel=0.0, sharp=89, cap_bottom=False,
            uv=UV.planar((0, -1, 0)))


@builder
def build_convex_traffic_mirror():
    rp = 0.0381   # 76.3 mm post
    for double in (False, True):
        name = 'convex_traffic_mirror_double' if double else 'convex_traffic_mirror'
        P = Prop(name, 'urban',
                 desc='Japanese road curve mirror (カーブミラー), orange 76.3 mm post, ' +
                      ('two Φ800 convex mirrors on a T bracket' if double else 'Φ800 convex mirror'),
                 origin='ground, post centre', front='mirror faces Unity +Z, tilted 6 deg down',
                 preview=dict(extra=[('head', 25, 8, ((-1.1, -0.5, 2.3), (1.1, 0.3, 3.5)))]))
        H = 3.35
        P.cyl((0, 0, 0), (0, 0, H), rp, seg=14, mat='M_PaintedMetal_Orange', bevel=0.004)
        P.lathe([(rp + 0.004, H - 0.005), (rp + 0.004, H + 0.02), (0.02, H + 0.035), (0.0, H + 0.04)], seg=14,
                mat='M_PaintedMetal_Orange', bevel=0.0)
        # base reflective band (yellow/black) near the ground
        P.lathe([(rp + 0.003, 0.25), (rp + 0.003, 0.65)], seg=14, mat='M_Deco_HazardStripe', cap_bottom=False,
                cap_top=False, bevel=0.0, uv=UV.scaled(UV.cyl((0, 0, 0), (0, 0, 1), norm=True), 1.0, 1 / 0.5))
        zc = 2.9
        if not double:
            yc = -0.16
            # bracket: two clamp bands + arm to the mirror back
            for z in (zc - 0.14, zc + 0.14):
                P.torus((0, 0, z), rp + 0.008, 0.008, seg=14, rseg=4, mat='M_Galvanized')
                P.box_mm((-0.025, -0.10, z - 0.015), (0.025, -rp, z + 0.015), mat='M_Galvanized', bevel=0.004, seg=1)
            P.box_mm((-0.12, -0.11, zc - 0.17), (0.12, -0.085, zc + 0.17), mat='M_Galvanized', bevel=0.005, seg=1)
            _mirror(P, (0, yc, zc))
        else:
            # T bracket: horizontal arm along X
            P.box_mm((-0.05, -0.10, zc + 0.30), (0.05, -rp, zc + 0.34), mat='M_Galvanized', bevel=0.004, seg=1)
            P.torus((0, 0, zc + 0.32), rp + 0.008, 0.008, seg=14, rseg=4, mat='M_Galvanized')
            P.cyl((-0.62, -0.10, zc + 0.32), (0.62, -0.10, zc + 0.32), 0.024, seg=10, mat='M_PaintedMetal_Orange',
                  bevel=0.003)
            for sx in (-1, 1):
                x = sx * 0.50
                yaw = -sx * 18
                # drop bracket to each mirror back
                P.box_mm((x - 0.02, -0.12, zc + 0.05), (x + 0.02, -0.08, zc + 0.32), mat='M_Galvanized', bevel=0.004,
                         seg=1)
                _mirror(P, (x, -0.2, zc), yaw=yaw)
        P.finish()
