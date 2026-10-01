"""URBAN set B: vending machines, recycle bin, bicycle, post boxes, bench, AC outdoor units,
rooftop water tank, rooftop billboard frame, shop awnings, lanterns, noren, garbage cage,
sidewalk transformer box.
Build:  blender -b -P Tools/blender/props/build_props.py -- props_urban_b [builder ...]
Textures: Tools/.venv/bin/python Tools/blender/props/make_textures_urban_b.py (run first)."""
import math
import numpy as np
from mathutils import Vector
from propkit import (Prop, UV, builder, define_mat, circle2d, rect2d, rounded_rect2d, fillet, thicken2d,
                     arc_points)

# ---------------------------------------------------------------------------------- materials
define_mat('M_VendingBody', c='#E6E8EA', r=0.35)
define_mat('M_BikeFrame', c='#8FB3C9', r=0.3, m=0.2)
define_mat('M_FRP_Tank', c='#BCD7DD', r=0.6)
define_mat('M_PaintedMetal_GrayGreen', c='#A7B3A4', r=0.5)
define_mat('M_GarbageBag', c='#E6EAE0', r=0.35)
define_mat('M_WireMesh_Cutout', c='#2E6846', r=0.5, tex='prop_wiremesh_green_albedo.png', cut=True)
define_mat('M_WireMesh_Silver_Cutout', c='#BCC0C4', r=0.4, m=0.6, tex='prop_wiremesh_silver_albedo.png', cut=True)
define_mat('M_Deco_AwningRedWhite', c='#C42024', r=0.8, tex='prop_awning_redwhite_albedo.png')
define_mat('M_Deco_AwningGreenWhite', c='#1C7046', r=0.8, tex='prop_awning_greenwhite_albedo.png')
define_mat('M_EmissiveLantern_Red', c='#CE1E18', r=0.7, e=1.2, tex='prop_chochin_matsuri_albedo.png')
define_mat('M_EmissiveLantern_Akachochin', c='#CE1E18', r=0.7, e=1.2, tex='prop_akachochin_albedo.png')
define_mat('M_Deco_Noren', c='#1C2856', r=0.85, tex='prop_noren_albedo.png')
define_mat('M_Deco_PostLabel', c='#C81E1A', r=0.4, tex='prop_postbox_label_albedo.png')
define_mat('M_Deco_RecycleLabel', c='#F6F6F2', r=0.5, tex='prop_recycle_label_albedo.png')
define_mat('M_Deco_GarbageSign', c='#F6F6F0', r=0.5, tex='prop_garbage_sign_albedo.png')
define_mat('M_Deco_HVWarning', c='#FAD200', r=0.4, tex='prop_hv_warning_albedo.png')

SQ2 = math.sqrt(2.0)


def _member(P, p0, p1, s, mat, bevel):
    """Square-section structural member of side s from p0 to p1 (1-segment chamfer if bevel > 0)."""
    o = P.cyl(p0, p1, s / SQ2, seg=4, twist=45.0, mat=mat, sharp=40.0, bevel=bevel, bevel_angle=40.0)
    P.parts[-1].seg = 1      # single-segment chamfer (Part.seg = bevel segments)
    return o


def curved_decal(P, r, z0, z1, half_angle, mat, rect, center=(0, 0), seg=4):
    """Curved decal strip on a vertical cylinder of radius r, centred facing -Y."""
    return P.lathe([(r, z0), (r, z1)], seg=seg, loc=(center[0], center[1], 0), start_angle=-90 - half_angle,
                   sweep=2 * half_angle, mat=mat, cap_bottom=False, cap_top=False, bevel=0.0, sharp=80,
                   uv=UV.planar((0, -1, 0), rect=rect))


def front_decal(P, x0, x1, z0, z1, y, mat, rect=(0, 0, 1, 1)):
    """Flat decal quad facing -Y at depth y."""
    return P.ngon([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], mat=mat,
                  uv=UV.planar((0, -1, 0), rect=rect))


# ======================================================================================
# 1. Vending machines
# ======================================================================================
def _vending(name, W, D=0.73, H=1.83):
    P = Prop(name, 'urban',
             desc=f'Japanese drink vending machine {W:.1f} x {D:.2f} x {H:.2f} m; front face on M_VendingFront (0-1 UV)',
             origin='ground, footprint centre', front='vending face = Unity +Z')
    hw = W / 2
    yf = -D / 2            # front of bezel
    yb = D / 2
    # plinth + levelling feet
    P.box_mm((-hw + 0.03, yf + 0.06, 0.035), (hw - 0.03, yb - 0.04, 0.10), mat='M_PlasticBlack', bevel=0.006)
    for sx in (-1, 1):
        for y in (yf + 0.09, yb - 0.08):
            P.cyl((sx * (hw - 0.07), y, 0.0), (sx * (hw - 0.07), y, 0.04), 0.028, seg=10, mat='M_Rubber', bevel=0.004)
    # cabinet (back offset by two stand-off rails so the machine sits 15 mm off the wall)
    P.box_mm((-hw, yf + 0.035, 0.09), (hw, yb - 0.015, H - 0.07), mat='M_VendingBody', bevel=0.012)
    for sx in (-1, 1):
        P.box_mm((sx * (hw - 0.06) - 0.03, yb - 0.02, 0.12), (sx * (hw - 0.06) + 0.03, yb, H - 0.12),
                 mat='M_PaintedMetal_DarkGray', bevel=0.004)
    # door bezel (frame proud of the recessed face)
    bz0, bz1 = 0.10, H - 0.09
    bw = 0.04
    P.box_mm((-hw, yf, bz0), (-hw + bw, yf + 0.04, bz1), mat='M_VendingBody', bevel=0.008)
    P.box_mm((hw - bw, yf, bz0), (hw, yf + 0.04, bz1), mat='M_VendingBody', bevel=0.008)
    P.box_mm((-hw + bw, yf, bz0), (hw - bw, yf + 0.04, bz0 + bw), mat='M_VendingBody', bevel=0.008)
    P.box_mm((-hw + bw, yf, bz1 - bw), (hw - bw, yf + 0.04, bz1), mat='M_VendingBody', bevel=0.008)
    # the face (one quad, 0-1 UV, u right / v up as seen from the front)
    fx0, fx1, fz0, fz1 = -hw + bw, hw - bw, bz0 + bw, bz1 - bw
    yface = yf + 0.012
    P.ngon([(fx0, yface, fz0), (fx1, yface, fz0), (fx1, yface, fz1), (fx0, yface, fz1)], mat='M_VendingFront',
           uv=UV.planar((0, -1, 0)))
    # top header / canopy
    P.box_mm((-hw - 0.012, yf - 0.025, H - 0.09), (hw + 0.012, yb - 0.015, H), mat='M_VendingBody', bevel=0.012)
    P.box_mm((-hw + 0.02, yf - 0.03, H - 0.075), (hw - 0.02, yf - 0.02, H - 0.015), mat='M_PlasticWhite', bevel=0.003)
    # product retrieval bin (取出口): protruding housing + smoked flap
    bxw = min(0.42, hw - 0.12)
    P.box_mm((-bxw, yf - 0.05, 0.17), (bxw, yface + 0.004, 0.40), mat='M_PlasticGray', bevel=0.012)
    P.box_mm((-bxw + 0.025, yf - 0.058, 0.195), (bxw - 0.025, yf - 0.045, 0.375), mat='M_PlasticBlack', bevel=0.006)
    P.box_mm((-bxw + 0.06, yf - 0.064, 0.33), (bxw - 0.06, yf - 0.055, 0.35), mat='M_PlasticGray', bevel=0.003)
    # coin-return cup + money module (coin slot, bill acceptor, display)
    cx = hw - 0.17
    P.box_mm((cx - 0.075, yf - 0.045, 0.47), (cx + 0.075, yface + 0.004, 0.575), mat='M_Aluminum', bevel=0.01)
    P.box_mm((cx - 0.055, yf - 0.05, 0.49), (cx + 0.055, yf - 0.03, 0.54), mat='M_PlasticBlack', bevel=0.004)
    mx0, mx1 = hw - 0.25, hw - 0.08
    P.box_mm((mx0, yf - 0.018, 0.84), (mx1, yface + 0.004, 1.13), mat='M_Aluminum', bevel=0.008)
    P.box_mm((mx0 + 0.02, yf - 0.024, 1.07), (mx0 + 0.07, yf - 0.012, 1.10), mat='M_PlasticBlack', bevel=0.002)
    P.box_mm((mx0 + 0.02, yf - 0.024, 0.96), (mx1 - 0.02, yf - 0.012, 0.985), mat='M_PlasticBlack', bevel=0.002)
    P.box_mm((mx0 + 0.02, yf - 0.024, 0.88), (mx1 - 0.02, yf - 0.012, 0.93), mat='M_Glass', bevel=0.002)
    # side ventilation louvres (both sides, low at the back)
    for sx in (-1, 1):
        for k in range(6):
            z = 0.16 + k * 0.035
            P.box_mm((sx * hw - 0.006 if sx > 0 else -hw - 0.008, 0.02, z),
                     (sx * hw + 0.008 if sx > 0 else -hw + 0.006, yb - 0.08, z + 0.016),
                     mat='M_PaintedMetal_DarkGray', bevel=0.0)
    P.empty('LightAnchor_0', (0.0, yf - 0.35, 1.2), size=0.12)
    fu = lambda x: (x - fx0) / (fx1 - fx0)
    fv = lambda z: (z - fz0) / (fz1 - fz0)
    P.note('M_VendingFront: single quad, UV 0-1 = whole recessed face (u right, v up seen from the front, '
           f'{fx1 - fx0:.2f} x {fz1 - fz0:.2f} m, aspect {(fx1 - fx0) / (fz1 - fz0):.3f}). 3D modules sit over the face: '
           f'retrieval bin u {fu(-bxw):.2f}-{fu(bxw):.2f} v {fv(0.17):.2f}-{fv(0.40):.2f}; coin-return cup u '
           f'{fu(cx - 0.075):.2f}-{fu(cx + 0.075):.2f} v {fv(0.47):.2f}-{fv(0.575):.2f}; money panel u {fu(mx0):.2f}-'
           f'{fu(mx1):.2f} v {fv(0.84):.2f}-{fv(1.13):.2f}. LightAnchor_0: optional light 0.35 m in front of the face.')
    P.finish()


@builder
def build_vending_machine():
    _vending('vending_machine_large', 1.2)
    _vending('vending_machine_slim', 0.8)


# ======================================================================================
# 2. Recycle bin beside vending machines
# ======================================================================================
@builder
def build_vending_recycle_bin():
    P = Prop('vending_recycle_bin', 'urban', desc='Can/PET bottle recycle box placed beside vending machines',
             origin='ground, footprint centre')
    P.box_mm((-0.25, -0.20, 0.0), (0.25, 0.20, 0.04), mat='M_PlasticGray', bevel=0.008)
    P.box_mm((-0.24, -0.19, 0.04), (0.24, 0.19, 0.80), mat='M_PlasticBlue', bevel=0.02)
    P.box_mm((-0.252, -0.202, 0.78), (0.252, 0.202, 0.85), mat='M_PlasticWhite', bevel=0.02)
    # white insert panel with two round openings
    P.box_mm((-0.215, -0.198, 0.56), (0.215, -0.18, 0.765), mat='M_PlasticWhite', bevel=0.01)
    for x in (-0.105, 0.105):
        P.cyl((x, -0.201, 0.66), (x, -0.19, 0.66), 0.056, seg=20, mat='M_PlasticBlack', bevel=0.0)
        P.torus((x, -0.201, 0.66), 0.060, 0.009, seg=20, rseg=6, rot=(90, 0, 0), mat='M_PlasticGray')
    # label
    front_decal(P, -0.17, 0.17, 0.17, 0.51, -0.1925, 'M_Deco_RecycleLabel')
    # collection door seam (lower front)
    P.box_mm((-0.20, -0.194, 0.10), (0.20, -0.19, 0.14), mat='M_PlasticGray', bevel=0.0)
    P.finish()


# ======================================================================================
# 3. Bicycle (mamachari)
# ======================================================================================
@builder
def build_bicycle():
    P = Prop('bicycle', 'urban', desc='Japanese city bike (mamachari) on its two-leg stand, 26" wheels',
             origin='ground, midway between the wheel contact points', front='bike length along Unity X',
             preview=dict(extra=[('detail', 60, 20, ((-0.95, -0.3, 0.0), (0.8, 0.3, 1.05)))]))
    R_T, r_t = 0.309, 0.023          # tyre torus -> outer radius 0.332
    AZ = 0.332
    xr, xf = -0.56, 0.56
    frame = 'M_BikeFrame'
    for xc, rear in ((xr, True), (xf, False)):
        P.torus((xc, 0, AZ), R_T, r_t, seg=24, rseg=5, rot=(90, 0, 0), mat='M_Rubber')
        P.torus((xc, 0, AZ), 0.284, 0.010, seg=20, rseg=3, rot=(90, 0, 0), mat='M_Chrome')
        hub_r = 0.048 if rear else 0.026
        P.cyl((xc, -0.05, AZ), (xc, 0.05, AZ), hub_r, seg=10, mat='M_Chrome', bevel=0.0)
        for k in range(14):
            a = 2 * math.pi * k / 14
            side = 0.032 if k % 2 == 0 else -0.032
            p0 = Vector((xc + math.cos(a + 0.25) * 0.03, side, AZ + math.sin(a + 0.25) * 0.03))
            p1 = Vector((xc + math.cos(a) * 0.278, 0.0, AZ + math.sin(a) * 0.278))
            P.cyl(p0, p1, 0.0022, seg=3, caps=False, mat='M_Chrome', bevel=0.0, sharp=89)
    # fenders (stainless), swept C-section along an arc around each axle
    fprof = thicken2d([(-0.032, -0.007), (0.0, 0.006), (0.032, -0.007)], 0.003)

    def fender(xc, a0, a1, n=8):
        path = [Vector((xc + 0.362 * math.cos(math.radians(a0 + (a1 - a0) * i / n)), 0,
                        AZ + 0.362 * math.sin(math.radians(a0 + (a1 - a0) * i / n)))) for i in range(n + 1)]
        up = (math.cos(math.radians(a0)), 0, math.sin(math.radians(a0)))
        P.sweep(path, fprof, up=up, mat='M_Chrome', bevel=0.0, sharp=50)
    fender(xf, 12, 196)
    fender(xr, 62, 212)
    for xc, a in ((xf, 18), (xr, 205)):
        pe = Vector((xc + 0.355 * math.cos(math.radians(a)), 0, AZ + 0.355 * math.sin(math.radians(a))))
        for sy in (-1, 1):
            P.cyl(pe + Vector((0, sy * 0.03, 0)), (xc, sy * 0.055, AZ), 0.003, seg=4, caps=False, mat='M_Chrome',
                  bevel=0.0, sharp=89)
    # frame tubes
    P.pipe(fillet([(0.44, 0, 0.71), (0.32, 0, 0.47), (0.15, 0, 0.32), (0.0, 0, 0.30)], 0.16, 4), 0.024, seg=8,
           mat=frame, bevel=0.0)
    P.cyl((0.45, 0, 0.67), (0.40, 0, 0.845), 0.022, seg=8, mat=frame, bevel=0.0)           # head tube
    P.cyl((0.0, -0.045, 0.30), (0.0, 0.045, 0.30), 0.027, seg=8, mat=frame, bevel=0.0)      # BB shell
    P.cyl((0.0, 0, 0.30), (-0.17, 0, 0.80), 0.017, seg=10, mat=frame, bevel=0.0)              # seat tube
    for sy in (-1, 1):
        P.cyl((0.0, sy * 0.04, 0.30), (xr, sy * 0.058, AZ), 0.010, seg=5, mat=frame, bevel=0.0)       # chain stay
        P.cyl((-0.155, sy * 0.022, 0.75), (xr, sy * 0.058, AZ), 0.009, seg=5, mat=frame, bevel=0.0)   # seat stay
        P.cyl((0.447, sy * 0.042, 0.665), (xf + 0.004, sy * 0.05, AZ), 0.011, seg=8, mat=frame, bevel=0.0)  # fork
    P.box((0.07, 0.11, 0.03), (0.447, 0, 0.665), rot=(0, -18, 0), mat=frame, bevel=0.006, seg=1)        # fork crown
    # stem, handlebar (swept-back), grips, levers, bell
    P.cyl((0.40, 0, 0.84), (0.385, 0, 0.965), 0.013, seg=8, mat='M_Chrome', bevel=0.0)
    hb = fillet([(0.19, -0.285, 1.025), (0.29, -0.255, 1.005), (0.375, -0.10, 0.968), (0.385, 0.0, 0.965),
                 (0.375, 0.10, 0.968), (0.29, 0.255, 1.005), (0.19, 0.285, 1.025)], 0.06, 2)
    P.pipe(hb, 0.0115, seg=4, mat='M_Chrome', bevel=0.0)
    for sy in (-1, 1):
        a = Vector((0.19, sy * 0.285, 1.025)); b = Vector((0.29, sy * 0.255, 1.005))
        d = (b - a).normalized()
        P.cyl(a - d * 0.01, a + d * 0.115, 0.017, seg=8, mat='M_PlasticBlack', bevel=0.0)
        P.cyl(a + d * 0.12 + Vector((0.01, 0, 0.012)), a + d * 0.02 + Vector((0.07, 0, -0.01)), 0.006, seg=4,
              mat='M_Chrome', bevel=0.0)
    P.cyl((0.30, -0.235, 1.03), (0.30, -0.235, 1.045), 0.022, seg=8, mat='M_Chrome', bevel=0.0)   # bell
    # saddle on springs
    P.cyl((-0.17, 0, 0.80), (-0.197, 0, 0.905), 0.0135, seg=8, mat='M_Chrome', bevel=0.0)
    P.sphere((-0.215, 0, 0.955), 0.1, seg=12, rings=6, scale=(1.32, 1.05, 0.36), mat='M_PlasticBlack')
    for sy in (-1, 1):
        P.cyl((-0.29, sy * 0.055, 0.905), (-0.29, sy * 0.055, 0.935), 0.014, seg=8, mat='M_Chrome', bevel=0.0)
    P.box((0.16, 0.10, 0.012), (-0.24, 0, 0.912), mat='M_Chrome', bevel=0.0)
    # chain case (full cover, drive side = -Y)
    case = []
    for i in range(10):
        a = math.radians(-80 + 160 * i / 9)
        case.append((0.0 + 0.105 * math.cos(a), 0.30 + 0.105 * math.sin(a)))
    for i in range(10):
        a = math.radians(100 + 160 * i / 9)
        case.append((xr + 0.06 * math.cos(a), AZ + 0.06 * math.sin(a)))
    P.extrude(case, 0.028, axis='Y', offset=-0.098, mat='M_PlasticGray', bevel=0.006, seg=1)
    # cranks + pedals
    for sy, ang in ((-1, -35), (1, 145)):
        a = math.radians(ang)
        pe = Vector((0.165 * math.cos(a), sy * 0.11, 0.30 + 0.165 * math.sin(a)))
        P.cyl((0, sy * 0.105, 0.30), pe, 0.011, seg=4, mat='M_Chrome', bevel=0.0)
        P.box((0.07, 0.10, 0.025), pe + Vector((0, sy * 0.06, 0)), mat='M_PlasticBlack', bevel=0.004, seg=1)
    # rear carrier
    ct = 0.765
    for sy in (-1, 1):
        P.cyl((-0.30, sy * 0.075, ct), (-0.80, sy * 0.075, ct), 0.006, seg=4, mat='M_Chrome', bevel=0.0)
        P.cyl((-0.80, sy * 0.075, ct), (xr - 0.01, sy * 0.06, AZ), 0.006, seg=4, mat='M_Chrome', bevel=0.0)
        P.cyl((-0.66, sy * 0.075, ct), (xr + 0.03, sy * 0.06, AZ + 0.02), 0.005, seg=4, mat='M_Chrome', bevel=0.0)
        P.cyl((-0.30, sy * 0.075, ct), (-0.16, sy * 0.025, 0.76), 0.005, seg=4, mat='M_Chrome', bevel=0.0)
    for x in (-0.34, -0.52, -0.70):
        P.cyl((x, -0.08, ct), (x, 0.08, ct), 0.005, seg=4, mat='M_Chrome', bevel=0.0)
    # front wire basket (frame + silver mesh panels, alpha cutout)
    bx0, bx1, by, bz0, bz1 = 0.47, 0.76, 0.19, 0.79, 1.03
    for z in (bz0, bz1):
        rim = [(bx0, -by, z), (bx1, -by, z), (bx1, by, z), (bx0, by, z), (bx0, -by, z)]
        P.pipe(rim, 0.0045, seg=4, mat='M_Chrome', caps=False, bevel=0.0)
    for (x, y) in ((bx0, -by), (bx1, -by), (bx1, by), (bx0, by)):
        P.cyl((x, y, bz0), (x, y, bz1), 0.0045, seg=4, mat='M_Chrome', bevel=0.0)
    t = 0.0015
    P.box_mm((bx0, -by, bz0 - t), (bx1, by, bz0 + t), mat='M_WireMesh_Silver_Cutout', bevel=0.0)
    P.box_mm((bx0 - t, -by, bz0), (bx0 + t, by, bz1), mat='M_WireMesh_Silver_Cutout', bevel=0.0)
    P.box_mm((bx1 - t, -by, bz0), (bx1 + t, by, bz1), mat='M_WireMesh_Silver_Cutout', bevel=0.0)
    for y in (-by, by):
        P.box_mm((bx0, y - t, bz0), (bx1, y + t, bz1), mat='M_WireMesh_Silver_Cutout', bevel=0.0)
    for sy in (-1, 1):
        P.cyl((0.70, sy * 0.06, bz0), (xf + 0.01, sy * 0.055, AZ + 0.03), 0.005, seg=4, mat='M_Chrome', bevel=0.0)
    P.cyl((bx0, 0, 0.95), (0.39, 0, 0.93), 0.007, seg=4, mat='M_Chrome', bevel=0.0)
    # head lamp on fork crown, rear reflector, ring lock, stand
    P.cyl((0.47, 0, 0.62), (0.53, 0, 0.62), 0.032, seg=10, mat='M_PlasticBlack', bevel=0.0)
    P.cyl((0.53, 0, 0.62), (0.536, 0, 0.62), 0.027, seg=12, mat='M_Reflector_White', bevel=0.0)
    P.box((0.012, 0.05, 0.04), (xr - 0.375, 0, AZ + 0.075), mat='M_Reflector_Red', bevel=0.0)
    lk = Vector((xr + 0.30 * math.cos(math.radians(72)), 0, AZ + 0.30 * math.sin(math.radians(72))))
    P.box((0.07, 0.085, 0.06), lk, rot=(0, -20, 0), mat='M_PlasticBlack', bevel=0.006, seg=1)
    for sy in (-1, 1):
        P.cyl((xr - 0.01, sy * 0.075, AZ - 0.02), (xr - 0.13, sy * 0.13, 0.012), 0.008, seg=6, mat='M_Chrome',
              bevel=0.0)
    P.cyl((xr - 0.13, -0.135, 0.012), (xr - 0.13, 0.135, 0.012), 0.009, seg=4, mat='M_Chrome', bevel=0.0)
    P.finish()


# ======================================================================================
# 4. Post boxes
# ======================================================================================
ATL_TEI = (0.0, 0.5, 0.5, 1.0)       # 〒
ATL_POST = (0.5, 0.5, 1.0, 1.0)      # 郵便 POST
ATL_TIME = (0.0, 0.0, 0.5, 0.5)      # collection times
ATL_SLOT_L = (0.5, 0.25, 1.0, 0.5)   # 手紙・はがき
ATL_SLOT_R = (0.5, 0.0, 1.0, 0.25)   # 速達・大型郵便


@builder
def build_post_box_round():
    P = Prop('post_box_round', 'urban', desc='Classic Japanese round red post box (丸型ポスト), 1.36 m',
             origin='ground, centre')
    red = 'M_PaintedMetal_Red'
    P.box_mm((-0.25, -0.25, 0.0), (0.25, 0.25, 0.06), mat='M_Concrete', bevel=0.01)
    P.lathe([(0.235, 0.06), (0.235, 0.10), (0.22, 0.12), (0.205, 0.145)], seg=24, mat=red, bevel=0.0, sharp=40)
    P.lathe([(0.2, 0.14), (0.2, 1.12)], seg=24, mat=red, cap_bottom=False, cap_top=False, bevel=0.0)
    P.lathe([(0.207, 0.16), (0.207, 0.19)], seg=24, mat=red, bevel=0.0, sharp=40)
    P.lathe([(0.20, 1.115), (0.245, 1.135), (0.247, 1.17), (0.232, 1.19), (0.20, 1.245), (0.15, 1.295),
             (0.08, 1.325), (0.0, 1.335)], seg=24, mat=red, bevel=0.0, sharp=40)
    P.sphere((0, 0, 1.345), 0.022, seg=10, rings=6, mat=red)
    # slot with hood
    P.box_mm((-0.105, -0.236, 1.035), (0.105, -0.15, 1.058), mat=red, bevel=0.006)
    P.box_mm((-0.095, -0.214, 0.99), (0.095, -0.15, 1.03), mat='M_PlasticBlack', bevel=0.003)
    # door panel, hinge, keyhole
    P.lathe([(0.204, 0.30), (0.204, 0.84)], seg=6, start_angle=-90 - 38, sweep=76, mat=red, cap_bottom=False,
            cap_top=False, bevel=0.0, sharp=80)
    for a in (-38, 38):
        ar = math.radians(-90 + a)
        P.cyl((0.205 * math.cos(ar), 0.205 * math.sin(ar), 0.30), (0.205 * math.cos(ar), 0.205 * math.sin(ar), 0.84),
              0.006, seg=6, mat=red, bevel=0.0)
    P.cyl((0.07, -0.20, 0.45), (0.07, -0.214, 0.45), 0.014, seg=10, mat='M_Chrome', bevel=0.002)
    # decals: 〒 on the door, collection time plate under the slot
    curved_decal(P, 0.2065, 0.52, 0.68, 22, 'M_Deco_PostLabel', ATL_TEI)
    curved_decal(P, 0.2065, 0.86, 0.96, 17, 'M_Deco_PostLabel', ATL_TIME)
    P.finish()


@builder
def build_post_box_square():
    P = Prop('post_box_square', 'urban', desc='Modern Japanese square red post box on a pedestal, two slots',
             origin='ground, centre')
    red = 'M_PaintedMetal_Red'
    P.box_mm((-0.18, -0.18, 0.0), (0.18, 0.18, 0.02), mat='M_Galvanized', bevel=0.004)
    P.box_mm((-0.11, -0.11, 0.02), (0.11, 0.11, 0.60), mat=red, bevel=0.01)
    P.box_mm((-0.31, -0.21, 0.58), (0.31, 0.21, 1.28), mat=red, bevel=0.02)
    P.box_mm((-0.33, -0.23, 1.27), (0.33, 0.23, 1.31), mat=red, bevel=0.018, seg=3)
    for (x0, x1, rect) in ((-0.28, -0.03, ATL_SLOT_L), (0.03, 0.28, ATL_SLOT_R)):
        P.box_mm((x0 + 0.01, -0.222, 1.115), (x1 - 0.01, -0.19, 1.148), mat='M_PlasticBlack', bevel=0.003)
        P.box_mm((x0, -0.25, 1.15), (x1, -0.205, 1.164), rot=None, mat=red, bevel=0.005)
        front_decal(P, x0, x1, 1.178, 1.240, -0.2105, 'M_Deco_PostLabel', rect)
    front_decal(P, -0.27, -0.10, 0.90, 1.07, -0.2105, 'M_Deco_PostLabel', ATL_TEI)
    front_decal(P, -0.07, 0.27, 0.90, 1.07, -0.2105, 'M_Deco_PostLabel', ATL_POST)
    # door
    P.box_mm((-0.28, -0.216, 0.62), (0.28, -0.205, 0.87), mat=red, bevel=0.004)
    front_decal(P, -0.09, 0.09, 0.65, 0.84, -0.2165, 'M_Deco_PostLabel', ATL_TIME)
    P.cyl((0.20, -0.21, 0.75), (0.20, -0.226, 0.75), 0.014, seg=10, mat='M_Chrome', bevel=0.002)
    P.finish()


# ======================================================================================
# 5. Bench
# ======================================================================================
@builder
def build_bench():
    P = Prop('bench', 'urban', desc='Japanese street/park bench 1.8 m: cast frames, wooden slats, centre armrest',
             origin='ground, centre', front='seat front = Unity +Z')
    fm = 'M_PaintedMetal_DarkGray'
    prof = rect2d(0.045, 0.035)
    for x in (-0.80, 0.0, 0.80):
        P.sweep(fillet([(x, -0.22, 0.0), (x, -0.20, 0.375), (x, 0.16, 0.355), (x, 0.265, 0.84)], 0.06, 3), prof,
                mat=fm, bevel=0.006, seg=1, sharp=40)
        P.sweep([(x, 0.19, 0.0), (x, 0.145, 0.36)], prof, mat=fm, bevel=0.006, seg=1, sharp=40)
        P.sweep([(x, -0.205, 0.10), (x, 0.175, 0.10)], rect2d(0.03, 0.025), mat=fm, bevel=0.004, seg=1, sharp=40)
        for y in (-0.22, 0.19):
            P.box_mm((x - 0.045, y - 0.05, 0.0), (x + 0.045, y + 0.05, 0.012), mat=fm, bevel=0.003)
    # armrests (ends) + centre divider
    for x in (-0.84, 0.84):
        P.pipe(fillet([(x, -0.19, 0.38), (x, -0.215, 0.62), (x, 0.10, 0.635), (x, 0.205, 0.60)], 0.06, 3), 0.018,
               seg=8, mat=fm, bevel=0.0)
    P.pipe(fillet([(0.0, -0.13, 0.42), (0.0, -0.13, 0.60), (0.0, 0.10, 0.60), (0.0, 0.12, 0.42)], 0.05, 3), 0.016,
           seg=8, mat=fm, bevel=0.0)
    # seat slats (follow the slight seat rake)
    for k in range(5):
        y = -0.19 + k * 0.083
        z = 0.375 + (0.355 - 0.375) * (y + 0.20) / 0.36 + 0.035 / 2 + 0.018
        P.box((1.80, 0.07, 0.034), (0, y, z), rot=(-3, 0, 0), mat='M_Wood', bevel=0.008, seg=2)
    # back slats
    a = math.atan2(0.105, 0.48)
    n = Vector((0, -math.cos(a), math.sin(a)))
    for t in (0.30, 0.56, 0.82):
        p = Vector((0, 0.16 + 0.105 * t, 0.355 + 0.48 * t)) + n * 0.035
        P.box((1.80, 0.03, 0.09), p, rot=(-math.degrees(a), 0, 0), mat='M_Wood', bevel=0.008, seg=2)
    P.finish()


# ======================================================================================
# 6. AC outdoor units
# ======================================================================================
def _fan_grille(P, cx, cz, yf, R):
    """Round fan grille on a front face at y=yf (front faces -Y)."""
    P.cyl((cx, yf + 0.002, cz), (cx, yf - 0.003, cz), R, seg=20, mat='M_PlasticBlack', bevel=0.0)
    P.torus((cx, yf - 0.006, cz), R + 0.006, 0.012, seg=20, rseg=4, rot=(90, 0, 0), mat='M_PaintedMetal_Ivory')
    for k in range(3):
        a = math.radians(k * 120 + 20)
        mid = Vector((cx + math.cos(a) * R * 0.5, yf - 0.012, cz + math.sin(a) * R * 0.5))
        P.box((R * 0.62, 0.006, R * 0.36), mid, rot=(-25, -math.degrees(a), 0), mat='M_PlasticGray', bevel=0.0)
    P.cyl((cx, yf - 0.005, cz), (cx, yf - 0.03, cz), R * 0.17, seg=14, mat='M_PlasticGray', bevel=0.004)
    yg = yf - 0.032
    for f in (0.42, 0.72, 0.98):
        P.torus((cx, yg, cz), R * f, 0.0035, seg=20, rseg=3, rot=(90, 0, 0), mat='M_PaintedMetal_DarkGray')
    for k in range(6):
        a = math.radians(k * 60 + 30)
        P.cyl((cx + math.cos(a) * R * 0.18, yg, cz + math.sin(a) * R * 0.18),
              (cx + math.cos(a) * R * 0.99, yg, cz + math.sin(a) * R * 0.99), 0.003, seg=4, caps=False,
              mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=89)
    P.cyl((cx, yg + 0.004, cz), (cx, yg - 0.004, cz), R * 0.15, seg=14, mat='M_PaintedMetal_DarkGray', bevel=0.002)


def _fin_panel(P, axis, c, a0, a1, z0, z1):
    """Heat-exchanger fin panel with guard wires on a side/back face.  axis 'Y': plane y=c (back),
    spans x a0..a1;  axis 'X': plane x=c (left side), spans y a0..a1."""
    s = 1 if c > 0 else -1
    if axis == 'Y':
        P.box_mm((a0, c - 0.002, z0), (a1, c + s * 0.004, z1), mat='M_Steel_Dark', bevel=0.0)
        n = int((a1 - a0) / 0.08)
        for i in range(1, n):
            x = a0 + (a1 - a0) * i / n
            P.cyl((x, c + s * 0.012, z0 + 0.01), (x, c + s * 0.012, z1 - 0.01), 0.0025, seg=4, caps=False,
                  mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=89)
    else:
        P.box_mm((c - 0.002 if s > 0 else c - 0.004, a0, z0), (c + 0.004 if s > 0 else c + 0.002, a1, z1),
                 mat='M_Steel_Dark', bevel=0.0)
        n = int((a1 - a0) / 0.06)
        for i in range(1, n):
            y = a0 + (a1 - a0) * i / n
            P.cyl((c + s * 0.012, y, z0 + 0.01), (c + s * 0.012, y, z1 - 0.01), 0.0025, seg=4, caps=False,
                  mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=89)
    for z in (z0 + (z1 - z0) * 0.33, z0 + (z1 - z0) * 0.66):
        if axis == 'Y':
            P.cyl((a0 + 0.01, c + s * 0.016, z), (a1 - 0.01, c + s * 0.016, z), 0.0025, seg=4, caps=False,
                  mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=89)
        else:
            P.cyl((c + s * 0.016, a0 + 0.01, z), (c + s * 0.016, a1 - 0.01, z), 0.0025, seg=4, caps=False,
                  mat='M_PaintedMetal_DarkGray', bevel=0.0, sharp=89)


def _ac_unit(name, W, H, D, fans, blocks):
    P = Prop(name, 'urban', desc=f'Japanese split air-conditioner outdoor unit {W} x {H} x {D} m',
             origin='ground (bottom of base), body centre', front='fan grille = Unity +Z')
    iv = 'M_PaintedMetal_Ivory'
    hw, hd = W / 2, D / 2
    if blocks:
        zb = 0.16
        for x in (-hw + 0.14, hw - 0.14):
            P.box_mm((x - 0.07, -hd - 0.03, 0.0), (x + 0.07, hd + 0.05, 0.13), mat='M_PlasticGray', bevel=0.012)
    else:
        zb = 0.08
        for x in (-hw + 0.1, hw - 0.1):
            P.box_mm((x - 0.05, -hd - 0.04, 0.0), (x + 0.05, hd + 0.04, 0.05), mat='M_Concrete', bevel=0.008, seg=1)
    for x in (-hw + 0.14 if blocks else -hw + 0.1, hw - 0.14 if blocks else hw - 0.1):
        P.box_mm((x - 0.035, -hd + 0.01, zb - 0.03), (x + 0.035, hd - 0.01, zb), mat='M_PaintedMetal_DarkGray',
                 bevel=0.004)
    P.box_mm((-hw, -hd, zb), (hw, hd, zb + H), mat=iv, bevel=0.012)
    P.box_mm((-hw - 0.006, -hd - 0.006, zb + H - 0.02), (hw + 0.006, hd + 0.006, zb + H + 0.012), mat=iv,
             bevel=0.008)
    # fans
    for (fx, fz, R) in fans:
        _fan_grille(P, fx, zb + fz, -hd, R)
    # badge + service panel seam on the right of the front
    P.box_mm((hw - 0.17, -hd - 0.004, zb + H - 0.10), (hw - 0.05, -hd + 0.001, zb + H - 0.07), mat='M_Aluminum',
             bevel=0.0)
    P.box_mm((hw - 0.205, -hd - 0.003, zb + 0.04), (hw - 0.199, -hd + 0.001, zb + H - 0.04),
             mat='M_PaintedMetal_LightGray', bevel=0.0)
    # fins: back + left side
    _fin_panel(P, 'Y', hd, -hw + 0.04, hw - 0.12, zb + 0.06, zb + H - 0.06)
    _fin_panel(P, 'X', -hw, -hd + 0.04, hd - 0.04, zb + 0.06, zb + H - 0.06)
    # carry handle recesses on the sides
    for sx in (-1, 1):
        P.box_mm((sx * hw - 0.004, -0.06, zb + H - 0.12), (sx * hw + 0.004, 0.06, zb + H - 0.09),
                 mat='M_PlasticBlack', bevel=0.0)
    # service valve cover (right side) + insulated refrigerant pipes up the wall + drain hose
    P.box_mm((hw - 0.002, -0.02, zb + 0.04), (hw + 0.06, hd - 0.02, zb + 0.30), mat=iv, bevel=0.01)
    yw = hd + 0.07
    for (dy, r) in ((0.0, 0.021), (0.05, 0.016)):
        y0 = 0.06 + dy * 0.6
        path = fillet([(hw + 0.06, y0, zb + 0.12 + dy), (hw + 0.13 + dy * 0.5, y0, zb + 0.12 + dy),
                       (hw + 0.13 + dy * 0.5, yw, zb + 0.12 + dy), (hw + 0.13 + dy * 0.5, yw, zb + H + 0.35)], 0.07, 3)
        P.pipe(path, r, seg=6, mat='M_PlasticWhite', bevel=0.0)
    P.pipe(fillet([(hw - 0.08, 0.0, zb), (hw - 0.08, 0.0, 0.02), (hw - 0.08, -hd - 0.15, 0.015)], 0.04, 3),
           0.008, seg=6, mat='M_PlasticBlack', bevel=0.0)
    P.note('Pipes rise behind the right side to the wall plane (Unity z = -%.2f); place the unit with its back '
           '~0.07 m from a wall.' % yw)
    P.finish()


@builder
def build_ac_outdoor_unit():
    _ac_unit('ac_outdoor_unit_small', 0.80, 0.55, 0.29, [(-0.12, 0.275, 0.205)], blocks=True)
    _ac_unit('ac_outdoor_unit_large', 0.95, 1.30, 0.35, [(-0.10, 0.34, 0.255), (-0.10, 0.96, 0.255)],
             blocks=False)


# ======================================================================================
# 7. Rooftop FRP panel water tank
# ======================================================================================
def _hbeam_x(P, x0, x1, yc, z0, h, b, tf=0.012, tw=0.008, mat='M_Galvanized'):
    o = [(yc - b / 2, z0), (yc + b / 2, z0), (yc + b / 2, z0 + tf), (yc + tw / 2, z0 + tf), (yc + tw / 2, z0 + h - tf),
         (yc + b / 2, z0 + h - tf), (yc + b / 2, z0 + h), (yc - b / 2, z0 + h), (yc - b / 2, z0 + h - tf),
         (yc - tw / 2, z0 + h - tf), (yc - tw / 2, z0 + tf), (yc - b / 2, z0 + tf)]
    P.prism(o, x0, x1, mat=mat, bevel=0.0, sharp=40)


def _hbeam_y(P, y0, y1, xc, z0, h, b, tf=0.012, tw=0.008, mat='M_Galvanized'):
    o = [(xc - b / 2, z0), (xc + b / 2, z0), (xc + b / 2, z0 + tf), (xc + tw / 2, z0 + tf), (xc + tw / 2, z0 + h - tf),
         (xc + b / 2, z0 + h - tf), (xc + b / 2, z0 + h), (xc - b / 2, z0 + h), (xc - b / 2, z0 + h - tf),
         (xc - tw / 2, z0 + h - tf), (xc - tw / 2, z0 + tf), (xc - b / 2, z0 + tf)]
    P.extrude(o, y1 - y0, axis='Y', offset=y0, mat=mat, bevel=0.0, sharp=40)


@builder
def build_rooftop_water_tank():
    P = Prop('rooftop_water_tank', 'urban', desc='FRP sectional panel water tank (受水槽) 3 x 2 x 2 m on steel base',
             origin='roof surface, footprint centre')
    tk = 'M_FRP_Tank'
    X0, X1, Y0, Y1, Z0, Z1 = -1.5, 1.5, -1.0, 1.0, 0.5, 2.5
    # steel base: sills along X + cross beams along Y
    for yc in (-0.85, 0.85):
        _hbeam_x(P, -1.62, 1.62, yc, 0.0, 0.2, 0.2)
    for xc in (-1.5, -0.5, 0.5, 1.5):
        _hbeam_y(P, -1.05, 1.05, xc, 0.2, 0.3, 0.15)
    P.box_mm((X0, Y0, Z0), (X1, Y1, Z1), mat=tk, bevel=0.03, seg=2)
    # pyramidal panel faces (1 m modules) + exterior flange ribs
    def pyramid(c, u, v, n, h=0.035):
        c = Vector(c); u = Vector(u); v = Vector(v); n = Vector(n)
        q = [c - u - v + n * 0.004, c + u - v + n * 0.004, c + u + v + n * 0.004, c - u + v + n * 0.004]
        apex = c + n * h
        P.poly(q + [apex], [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], mat=tk, bevel=0.0, sharp=20)
    hp = 0.46
    for i in range(3):
        for j in range(2):
            x = X0 + 0.5 + i; z = Z0 + 0.5 + j
            pyramid((x, Y0, z), (hp, 0, 0), (0, 0, hp), (0, -1, 0))
            pyramid((x, Y1, z), (-hp, 0, 0), (0, 0, hp), (0, 1, 0))
            pyramid((x, Y0 + 0.5 + j, Z1), (hp, 0, 0), (0, hp, 0), (0, 0, 1))
    for i in range(2):
        for j in range(2):
            y = Y0 + 0.5 + i; z = Z0 + 0.5 + j
            pyramid((X1, y, z), (0, hp, 0), (0, 0, hp), (1, 0, 0))
            pyramid((X0, y, z), (0, -hp, 0), (0, 0, hp), (-1, 0, 0))
    rw, rp = 0.035, 0.05
    for x in (-0.5, 0.5):
        for y in (Y0, Y1):
            s = -1 if y < 0 else 1
            P.box_mm((x - rw / 2, min(y, y + s * rp), Z0), (x + rw / 2, max(y, y + s * rp), Z1), mat=tk, bevel=0.006,
                     seg=1)
        P.box_mm((x - rw / 2, Y0, Z1), (x + rw / 2, Y1, Z1 + rp), mat=tk, bevel=0.006, seg=1)
    for y in (Y0, Y1):
        s = -1 if y < 0 else 1
        P.box_mm((X0, min(y, y + s * rp), Z0 + 1 - rw / 2), (X1, max(y, y + s * rp), Z0 + 1 + rw / 2), mat=tk,
                 bevel=0.006, seg=1)
    for x in (X0, X1):
        s = -1 if x < 0 else 1
        P.box_mm((min(x, x + s * rp), Y0, Z0 + 1 - rw / 2), (max(x, x + s * rp), Y1, Z0 + 1 + rw / 2), mat=tk,
                 bevel=0.006, seg=1)
        P.box_mm((min(x, x + s * rp), -rw / 2, Z0), (max(x, x + s * rp), rw / 2, Z1), mat=tk, bevel=0.006, seg=1)
    P.box_mm((X0, -rw / 2, Z1), (X1, rw / 2, Z1 + rp), mat=tk, bevel=0.006, seg=1)
    # corner / edge flanges
    for x in (X0, X1):
        for y in (Y0, Y1):
            P.box_mm((x - 0.03, y - 0.03, Z0), (x + 0.03, y + 0.03, Z1 + 0.02), mat=tk, bevel=0.01, seg=1)
    # top: manhole hatch with padlock, mushroom vent, level electrode box
    P.cyl((-1.0, 0.5, Z1), (-1.0, 0.5, Z1 + 0.12), 0.30, seg=20, mat=tk, bevel=0.01)
    P.cyl((-1.0, 0.5, Z1 + 0.12), (-1.0, 0.5, Z1 + 0.15), 0.33, seg=20, mat=tk, bevel=0.008)
    P.box((0.05, 0.03, 0.06), (-1.0, 0.5 - 0.335, Z1 + 0.10), mat='M_Chrome', bevel=0.004)
    P.cyl((-1.0, 0.25, Z1 + 0.15), (-1.0, 0.75, Z1 + 0.15), 0.012, seg=6, mat='M_Chrome', bevel=0.0)
    P.cyl((1.0, 0.5, Z1), (1.0, 0.5, Z1 + 0.35), 0.05, seg=10, mat='M_PlasticGray', bevel=0.0)
    P.lathe([(0.0, Z1 + 0.33), (0.11, Z1 + 0.34), (0.11, Z1 + 0.37), (0.07, Z1 + 0.42), (0.0, Z1 + 0.43)], seg=14,
            loc=(1.0, 0.5, 0), mat='M_PlasticGray', bevel=0.0)
    P.box_mm((0.05, -0.55, Z1), (0.30, -0.35, Z1 + 0.18), mat='M_PlasticWhite', bevel=0.012)
    # ladder on the front face (+ goose-neck grab rails over the top)
    yl = Y0 - 0.20
    for x in (0.82, 1.18):
        P.pipe(fillet([(x, yl, 0.0), (x, yl, Z1 + 0.65), (x, -0.80, Z1 + 0.65), (x, -0.80, Z1 + 0.05)], 0.16, 3),
               0.02, seg=6, mat='M_Galvanized', bevel=0.0)
        for z in (1.0, 2.0):
            P.box_mm((x - 0.015, yl, z - 0.02), (x + 0.015, Y0 - 0.05, z + 0.02), mat='M_Galvanized', bevel=0.0)
    z = 0.3
    while z < Z1 + 0.5:
        P.cyl((0.82, yl, z), (1.18, yl, z), 0.013, seg=5, mat='M_Galvanized', bevel=0.0)
        z += 0.3
    # pipes: inlet (right side) and outlet (back) down to the roof, with flanges
    pg = 'M_PlasticGray'
    P.pipe(fillet([(X1 + 0.03, 0.3, 0.80), (X1 + 0.45, 0.3, 0.80), (X1 + 0.45, 0.3, 0.12), (X1 + 0.45, 1.3, 0.12)],
                  0.15, 3), 0.05, seg=8, mat=pg, bevel=0.0)
    P.cyl((X1 + 0.02, 0.3, 0.80), (X1 + 0.08, 0.3, 0.80), 0.085, seg=8, mat=pg, bevel=0.0)
    P.pipe(fillet([(-0.8, Y1 + 0.03, 0.70), (-0.8, Y1 + 0.40, 0.70), (-0.8, Y1 + 0.40, 0.12),
                   (-1.7, Y1 + 0.40, 0.12)], 0.15, 3), 0.06, seg=8, mat=pg, bevel=0.0)
    P.cyl((-0.8, Y1 + 0.02, 0.70), (-0.8, Y1 + 0.08, 0.70), 0.095, seg=8, mat=pg, bevel=0.0)
    P.cyl((-0.8, Y1 + 0.40, 0.42), (-0.8, Y1 + 0.40, 0.52), 0.085, seg=8, mat='M_PaintedMetal_Blue', bevel=0.0)
    for p in ((X1 + 0.45, 1.25), (-1.65, Y1 + 0.40)):
        P.box((0.12, 0.12, 0.07), (p[0], p[1], 0.035), mat='M_Concrete', bevel=0.01)
    P.finish()


# ======================================================================================
# 8. Rooftop billboard frame
# ======================================================================================
@builder
def build_rooftop_billboard_frame():
    P = Prop('rooftop_billboard_frame', 'urban',
             desc='Rooftop advertising tower (屋上広告塔): 10 x 5 m board on raking steel lattice, catwalk + floodlights',
             origin='roof surface, centre of the board foot line', front='board face = Unity +Z',
             preview=dict(az=-38, el=14))
    st = 'M_PaintedMetal_Gray'
    BW, BZ0, BZ1 = 10.0, 1.8, 6.8
    xs = [-4.75, -2.375, 0.0, 2.375, 4.75]
    yc = 0.22
    for x in xs:
        C = [Vector((x, yc, 0.0)), Vector((x, yc, 2.0)), Vector((x, yc, 4.2)), Vector((x, yc, 6.3))]
        sy = lambda z: yc + 3.0 * (6.3 - z) / 6.3
        S = [Vector((x, sy(0.0), 0.0)), Vector((x, sy(2.0), 2.0)), Vector((x, sy(4.2), 4.2))]
        _member(P, (x, yc, 0.0), (x, yc, BZ1 + 0.05), 0.16, st, 0.006)          # column
        _member(P, C[3], S[0] + Vector((0, 0, 0.12)), 0.13, st, 0.005)          # raking strut (ends in pedestal)
        _member(P, C[0] + Vector((0, 0, 0.1)), S[0] + Vector((0, 0, 0.1)), 0.10, st, 0.0)
        _member(P, C[1], S[1], 0.09, st, 0.0)
        _member(P, C[2], S[2], 0.09, st, 0.0)
        _member(P, C[1], S[0] + Vector((0, 0, 0.12)), 0.07, st, 0.0)
        _member(P, C[2], S[1], 0.07, st, 0.0)
        for p in (C[0], S[0]):
            P.box((0.45, 0.45, 0.22), (p.x, p.y, 0.11), mat='M_Concrete', bevel=0.02)
            P.box((0.30, 0.30, 0.02), (p.x, p.y, 0.23), mat=st, bevel=0.0)
    # longitudinal girts behind the board + rear chords + rear X-bracing
    for z in (BZ0 + 0.1, 3.05, 4.3, 5.55, BZ1 - 0.1):
        _member(P, (-5.0, 0.12, z), (5.0, 0.12, z), 0.08, st, 0.0)
    sy = lambda z: yc + 3.0 * (6.3 - z) / 6.3
    for z in (2.0, 4.2):
        _member(P, (xs[0], sy(z), z), (xs[-1], sy(z), z), 0.08, st, 0.0)
    _member(P, (xs[0], sy(0.1), 0.1), (xs[-1], sy(0.1), 0.1), 0.09, st, 0.0)
    for i in range(4):
        a, b = xs[i], xs[i + 1]
        _member(P, (a, sy(0.15), 0.15), (b, sy(4.2), 4.2), 0.06, st, 0.0)
        _member(P, (b, sy(0.15), 0.15), (a, sy(4.2), 4.2), 0.06, st, 0.0)
    # board: backing panel, frame border, face (M_BillboardFace, 0-1 UV, 2:1)
    P.box_mm((-BW / 2, 0.0, BZ0), (BW / 2, 0.06, BZ1), mat=st, bevel=0.0)
    bt = 0.10
    P.box_mm((-BW / 2 - bt, -0.06, BZ0 - bt), (BW / 2 + bt, 0.0, BZ0), mat=st, bevel=0.01)
    P.box_mm((-BW / 2 - bt, -0.06, BZ1), (BW / 2 + bt, 0.0, BZ1 + bt), mat=st, bevel=0.01)
    P.box_mm((-BW / 2 - bt, -0.06, BZ0), (-BW / 2, 0.0, BZ1), mat=st, bevel=0.01)
    P.box_mm((BW / 2, -0.06, BZ0), (BW / 2 + bt, 0.0, BZ1), mat=st, bevel=0.01)
    P.ngon([(-BW / 2, -0.02, BZ0), (BW / 2, -0.02, BZ0), (BW / 2, -0.02, BZ1), (-BW / 2, -0.02, BZ1)],
           mat='M_BillboardFace', uv=UV.planar((0, -1, 0)))
    # top catwalk (grating) behind the board, with handrail
    cz = BZ1 + 0.10
    P.box_mm((-5.0, 0.08, cz - 0.05), (5.0, 0.80, cz), mat='M_Galvanized', bevel=0.0)
    for k in range(9):
        x = -5.0 + k * 1.25
        P.cyl((x, 0.78, cz), (x, 0.78, cz + 1.1), 0.02, seg=6, mat='M_Galvanized', bevel=0.0)
    for z in (cz + 0.55, cz + 1.1):
        P.cyl((-5.0, 0.78, z), (5.0, 0.78, z), 0.02, seg=6, mat='M_Galvanized', bevel=0.0)
    for x in (-5.0, 5.0):
        for z in (cz + 0.55, cz + 1.1):
            P.cyl((x, 0.08, z), (x, 0.78, z), 0.02, seg=6, mat='M_Galvanized', bevel=0.0)
        P.cyl((x, 0.08, cz), (x, 0.08, cz + 1.1), 0.02, seg=6, mat='M_Galvanized', bevel=0.0)
    for x in (-4.4, -1.8, 1.8, 4.4):
        _member(P, (x, 0.12, BZ1 - 0.6), (x, 0.70, cz - 0.05), 0.05, st, 0.0)
    # floodlight arms projecting forward over the face, heads aimed back/down at the board
    k = 0
    for x in (-4.0, -2.0, 0.0, 2.0, 4.0):
        P.pipe(fillet([(x, 0.05, BZ1 + 0.12), (x, -0.55, BZ1 + 0.35), (x, -1.25, BZ1 + 0.35)], 0.2, 3), 0.035,
               seg=8, mat=st, bevel=0.0)
        hc = Vector((x, -1.32, BZ1 + 0.22))
        n = Vector((0, 1.0, -0.75)).normalized()
        ang = -math.degrees(math.atan2(0.75, 1.0))
        P.box((0.38, 0.16, 0.24), hc, rot=(ang, 0, 0), mat='M_PaintedMetal_DarkGray', bevel=0.012)
        P.box((0.32, 0.012, 0.18), hc + n * 0.082, rot=(ang, 0, 0), mat='M_EmissiveLamp', bevel=0.0)
        P.empty(f'LightAnchor_{k}', tuple(hc + n * 0.1), size=0.2)
        k += 1
    P.note('M_BillboardFace: one quad 10 x 5 m, UV 0-1 (2:1, u right, v up). LightAnchor_0..4 = floodlight '
           'emitters (aim spot lights toward Unity -Z and down at the face).')
    P.finish()


# ======================================================================================
# 9. Shop awnings (wall mounted, origin = top-centre attach line on the wall)
# ======================================================================================
def AWN_UV(P_, N_, pidx):
    """Stripe UV independent of the face normal: u = x / 0.5 m (one red+white repeat), v along the drop."""
    return np.stack([P_[:, 0] / 0.5, (P_[:, 2] - P_[:, 1]) / 0.5], axis=1)


AWN_SIDE_UV = UV.box(s=0.5)


def _slab(P, pts_front, n, t, mat, uv):
    """Thin slab from a planar polygon (front side CCW seen from n) thickened by t opposite to n."""
    n = Vector(n).normalized()
    A = [Vector(p) for p in pts_front]
    B = [p - n * t for p in A]
    m = len(A)
    verts = A + B
    faces = [tuple(range(m)), tuple(range(2 * m - 1, m - 1, -1))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, i + m, j + m, j))
    return P.poly(verts, faces, mat=mat, uv=uv, bevel=0.0, sharp=35)


@builder
def build_shop_awning_flat():
    W, PJ, DROP, VAL = 3.0, 1.2, 0.45, 0.25
    P = Prop('shop_awning_flat', 'urban',
             desc='Fixed sloped canvas shop awning 3.0 x 1.2 m with valance + side wings, red/white stripes',
             origin='wall plane, top-centre attach line (mount ~2.6 m above pavement)', front='projects to Unity +Z',
             preview=dict(wall=True, ground_z=-2.6))
    fab = 'M_Deco_AwningRedWhite'
    hw = W / 2
    # canvas top (sloped) : wall (y=0,z=0) -> front (y=-PJ, z=-DROP)
    n = Vector((0, -DROP, PJ)).normalized()   # outward (up/front)
    _slab(P, [(-hw, -PJ, -DROP), (hw, -PJ, -DROP), (hw, 0.0, 0.0), (-hw, 0.0, 0.0)], n, 0.008, fab, AWN_UV)
    # valance
    _slab(P, [(-hw, -PJ - 0.008, -DROP - VAL), (hw, -PJ - 0.008, -DROP - VAL), (hw, -PJ - 0.008, -DROP + 0.004),
              (-hw, -PJ - 0.008, -DROP + 0.004)], (0, -1, 0), 0.008, fab, AWN_UV)
    # side wings
    for sx in (-1, 1):
        x = sx * hw
        pts = [(x, 0.0, 0.0), (x, -PJ, -DROP), (x, 0.0, -DROP)] if sx > 0 else [(x, 0.0, -DROP), (x, -PJ, -DROP),
                                                                                 (x, 0.0, 0.0)]
        _slab(P, pts, (sx, 0, 0), 0.008, fab, AWN_SIDE_UV)
    # steel frame under the canvas
    fm = 'M_PaintedMetal_DarkGray'
    P.cyl((-hw + 0.02, -0.03, -0.035), (hw - 0.02, -0.03, -0.035), 0.016, seg=8, mat=fm, bevel=0.0)
    P.cyl((-hw + 0.02, -PJ + 0.03, -DROP - 0.025), (hw - 0.02, -PJ + 0.03, -DROP - 0.025), 0.016, seg=8, mat=fm,
          bevel=0.0)
    for x in (-hw + 0.03, 0.0, hw - 0.03):
        P.cyl((x, -0.03, -0.035), (x, -PJ + 0.03, -DROP - 0.025), 0.014, seg=8, mat=fm, bevel=0.0)
    for x in (-hw + 0.05, hw - 0.05):
        P.cyl((x, -0.005, -0.75), (x, -0.62, -0.27), 0.012, seg=8, mat=fm, bevel=0.0)
        P.box_mm((x - 0.04, -0.012, -0.80), (x + 0.04, 0.0, -0.70), mat=fm, bevel=0.003)
    P.box_mm((-hw, -0.012, -0.06), (hw, 0.0, 0.02), mat=fm, bevel=0.004)
    P.note('Stripe texture repeats every 0.5 m across the width (UV.box s=0.5, tileable).')
    P.finish()


@builder
def build_shop_awning_dome():
    W, R, VAL = 2.5, 0.9, 0.18
    P = Prop('shop_awning_dome', 'urban',
             desc='Quarter-round (R-type) canvas shop awning 2.5 m wide, 0.9 m projection, green/white stripes',
             origin='wall plane, top-centre attach line (mount ~2.8 m above pavement)', front='projects to Unity +Z',
             preview=dict(wall=True, ground_z=-2.8))
    fab = 'M_Deco_AwningGreenWhite'
    hw = W / 2
    N = 12
    prof = [(-R * math.sin(math.pi / 2 * i / N), -R + R * math.cos(math.pi / 2 * i / N)) for i in range(N + 1)]
    # outer canvas surface (normals outward) + inner surface
    for (rr, flip) in ((1.0, True), (0.991, False)):
        verts = []
        for (y, z) in prof:
            yy, zz = y * rr, -R + (z + R) * rr
            verts += [(-hw, yy, zz), (hw, yy, zz)]
        faces = []
        for i in range(N):
            a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
            faces.append((a, b, c, d) if not flip else (d, c, b, a))
        P.poly(verts, faces, mat=fab, uv=AWN_UV, bevel=0.0, sharp=35)
    # end caps (quarter discs)
    for sx in (-1, 1):
        x = sx * hw
        pts = [(x, 0.0, -R)] + [(x, y, z) for (y, z) in prof]
        if sx < 0:
            pts = pts[::-1]
        _slab(P, pts, (sx, 0, 0), 0.008, fab, AWN_SIDE_UV)
    # valance with scalloped hem
    vy = -R - 0.004
    hem = []
    nsc = 10
    for i in range(nsc * 4 + 1):
        x = -hw + W * i / (nsc * 4)
        hem.append((x, vy, -R - VAL + 0.035 * abs(math.sin(math.pi * i / 4))))
    top = [(hw, vy, -R + 0.004), (-hw, vy, -R + 0.004)]
    verts = hem + top
    m = len(verts)
    back = [(x, y + 0.008, z) for (x, y, z) in verts]
    allv = verts + back
    faces = [tuple(range(m)), tuple(range(2 * m - 1, m - 1, -1))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, i + m, j + m, j))
    P.poly(allv, faces, mat=fab, uv=AWN_UV, bevel=0.0, sharp=35)
    # frame bows + bars
    fm = 'M_PaintedMetal_DarkGray'
    bow = [(x, y * 0.975, -R + (z + R) * 0.975) for (y, z) in prof for x in (0,)]
    for x in (-hw + 0.03, -0.42, 0.42, hw - 0.03):
        P.pipe([(x, y, z) for (_, y, z) in bow], 0.012, seg=6, mat=fm, bevel=0.0)
    P.cyl((-hw + 0.02, -R + 0.02, -R + 0.01), (hw - 0.02, -R + 0.02, -R + 0.01), 0.014, seg=8, mat=fm, bevel=0.0)
    P.box_mm((-hw, -0.012, -0.06), (hw, 0.0, 0.02), mat=fm, bevel=0.004)
    P.box_mm((-hw, -0.012, -R - 0.02), (hw, 0.0, -R + 0.03), mat=fm, bevel=0.004)
    P.note('Stripe texture repeats every 0.5 m across the width (UV.box s=0.5, tileable).')
    P.finish()


# ======================================================================================
# 10. Lanterns
# ======================================================================================
def _lantern(P, cx, cy, top, H, R, cap_r, body_mat, ribs=8, seg=12, cap_mat='M_PaintedMetal_Black'):
    """Paper lantern hanging with its top cap at z=top. Returns centre point."""
    bot = top - H
    ch = 0.035 * H / 0.4
    # caps
    P.lathe([(cap_r * 0.85, top - ch), (cap_r, top - ch * 0.8), (cap_r, top), (0.0, top + 0.004)], seg=seg,
            loc=(cx, cy, 0), mat=cap_mat, bevel=0.0, sharp=40)
    P.lathe([(0.0, bot - 0.004), (cap_r, bot), (cap_r, bot + ch * 0.8), (cap_r * 0.85, bot + ch)], seg=seg,
            loc=(cx, cy, 0), mat=cap_mat, bevel=0.0, sharp=40)
    # ribbed barrel body
    z0, z1 = bot + ch * 0.9, top - ch * 0.9
    n = ribs * 2
    prof = []
    for i in range(n + 1):
        s = i / n
        base = cap_r * 0.9 + (R - cap_r * 0.9) * math.sin(math.pi * s) ** 0.55
        rib = 1.0 - (0.035 if i % 2 == 1 else 0.0) * math.sin(math.pi * s)
        prof.append((base * rib, z0 + (z1 - z0) * s))
    xf = -cx if P.mirror_x else cx
    P.lathe(prof, seg=seg, loc=(cx, cy, 0), mat=body_mat, cap_bottom=False, cap_top=False, bevel=0.0, sharp=70,
            uv=UV.cyl((xf, cy, z0), (xf, cy, z1), norm=True, v_norm=True))
    return (cx, cy, (top + bot) / 2)


@builder
def build_chochin_string_4m():
    P = Prop('chochin_string_4m', 'urban', mirror_x=True,
             desc='Festival red paper lanterns (祭り提灯) on a rope, 4 m tile with 5 lanterns',
             origin='rope start (Unity X=0); rope along Unity X 0..4 at y=0; lanterns hang below',
             preview=dict(ground_z=-2.6, extra=[('detail', 30, 8, ((-1.7, -0.2, -0.5), (-0.1, 0.2, 0.05)))]))
    P.cyl((0.0, 0, 0), (4.0, 0, 0), 0.006, seg=6, mat='M_Rope', bevel=0.0)
    for i in range(5):
        x = 0.4 + 0.8 * i
        P.cyl((x, 0, 0.004), (x, 0, -0.055), 0.0025, seg=4, mat='M_PaintedMetal_Black', bevel=0.0)
        P.torus((x, 0, 0.0), 0.012, 0.003, seg=8, rseg=4, rot=(90, 0, 0), mat='M_PaintedMetal_Black')
        c = _lantern(P, x, 0.0, -0.055, 0.40, 0.12, 0.075, 'M_EmissiveLantern_Red', ribs=8, seg=10)
        P.empty(f'LightAnchor_{i}', c, size=0.08)
    P.note('Tile: chain at Unity X += 4. LightAnchor_0..4 = lantern centres (optional warm point lights). '
           'Body texture wraps cylindrically (u=0.5 faces Unity +Z).')
    P.finish()


@builder
def build_akachochin_single():
    P = Prop('akachochin_single', 'urban', desc='Large izakaya red lantern (赤提灯, Φ0.36 x 0.6 m) on a wall bracket',
             origin='wall plane at the bracket (mount ~2.4 m)', front='projects to Unity +Z',
             preview=dict(wall=True, ground_z=-2.4))
    bm = 'M_PaintedMetal_Black'
    P.box_mm((-0.04, -0.012, -0.22), (0.04, 0.0, 0.05), mat=bm, bevel=0.003)
    P.box_mm((-0.011, -0.42, -0.011), (0.011, -0.012, 0.011), mat=bm, bevel=0.003)
    P.cyl((0, -0.012, -0.20), (0, -0.26, -0.005), 0.008, seg=6, mat=bm, bevel=0.0)
    P.cyl((0, -0.40, 0.0), (0, -0.40, -0.07), 0.004, seg=6, mat=bm, bevel=0.0)
    c = _lantern(P, 0.0, -0.40, -0.07, 0.60, 0.18, 0.105, 'M_EmissiveLantern_Akachochin', ribs=10, seg=16)
    P.empty('LightAnchor_0', c, size=0.1)
    P.note('LightAnchor_0 = lantern centre. Text faces Unity +Z (front 焼鳥, back 酒).')
    P.finish()


# ======================================================================================
# 11. Noren curtain
# ======================================================================================
@builder
def build_noren_curtain():
    P = Prop('noren_curtain', 'urban', desc='Shop entrance noren: 1.8 m rod, 4 indigo panels (0.42 x 0.9 m) らーめん',
             origin='wall plane under the rod centre, at rod height (~2.0 m)', front='Unity +Z',
             preview=dict(wall=True, ground_z=-2.0))
    yr = -0.07
    P.cyl((-0.92, yr, 0.0), (0.92, yr, 0.0), 0.017, seg=10, mat='M_Wood', bevel=0.003)
    for sx in (-1, 1):
        P.cyl((sx * 0.92, yr, 0), (sx * 0.95, yr, 0), 0.022, seg=10, mat='M_Wood_Dark', bevel=0.004)
        x = sx * 0.78
        P.box_mm((x - 0.012, yr - 0.004, 0.022), (x + 0.012, 0.0, 0.034), mat='M_PaintedMetal_Black', bevel=0.002)
        P.box_mm((x - 0.012, yr - 0.03, -0.01), (x + 0.012, yr - 0.018, 0.034), mat='M_PaintedMetal_Black',
                 bevel=0.002)
    X0, X1, ZT, ZB = -0.855, 0.855, 0.0, -0.90
    uvf = UV.planar((0, -1, 0), bounds=(X0, ZB, X1, ZT))
    # sleeve around the rod (top band)
    P.cyl((X0, yr, 0), (X1, yr, 0), 0.024, seg=10, caps=False, mat='M_Deco_Noren', bevel=0.0, sharp=60, uv=uvf)
    yc = yr - 0.026
    zb_band = -0.12

    def cloth(xa, xb, za, zb, nu, nv, amp_top, amp_bot, phase):
        verts_f, verts_b = [], []
        for j in range(nv + 1):
            z = za + (zb - za) * j / nv
            t = j / nv
            amp = amp_top + (amp_bot - amp_top) * t
            for i in range(nu + 1):
                x = xa + (xb - xa) * i / nu
                y = yc - amp * math.sin(2 * math.pi * (x - xa) / 0.21 + phase) - 0.004 * t
                verts_f.append((x, y, z))
                verts_b.append((x, y + 0.003, z))
        W_ = nu + 1
        faces = []
        for j in range(nv):
            for i in range(nu):
                a = j * W_ + i
                # rows go downward (z decreasing): CCW seen from -Y
                faces.append((a + W_, a + W_ + 1, a + 1, a))
        nvtx = len(verts_f)
        faces_b = [tuple(v + nvtx for v in reversed(f)) for f in faces]
        P.poly(verts_f + verts_b, faces + faces_b, mat='M_Deco_Noren', uv=uvf, bevel=0.0, sharp=60)
    # top band (0 .. -0.12), continuous
    cloth(X0, X1, ZT, zb_band, 16, 1, 0.0, 0.004, 0.0)
    pw, gap = 0.42, 0.01
    for k in range(4):
        xa = X0 + k * (pw + gap)
        cloth(xa, xa + pw, zb_band, ZB, 8, 5, 0.004, 0.014, 0.6 * k)
    P.note('M_Deco_Noren UV: planar 0-1 over the whole curtain (u right, v up, from the front); swap texture for '
           'other shop names.')
    P.finish()


# ======================================================================================
# 12. Garbage collection cage
# ======================================================================================
@builder
def build_garbage_cage():
    P = Prop('garbage_cage', 'urban', desc='Garbage collection station: folding steel mesh cage 1.2 x 0.7 x 0.9 m',
             origin='ground, footprint centre')
    fm = 'M_PaintedMetal_Green'
    X, Y, H = 0.6, 0.35, 0.85
    s = 0.03
    for (x, y) in ((-X, -Y), (X, -Y), (X, Y), (-X, Y)):
        _member(P, (x, y, 0.0), (x, y, H), s, fm, 0.004)
    for z in (0.02, H):
        _member(P, (-X, -Y, z), (X, -Y, z), s, fm, 0.004)
        _member(P, (-X, Y, z), (X, Y, z), s, fm, 0.004)
        _member(P, (-X, -Y, z), (-X, Y, z), s, fm, 0.004)
        _member(P, (X, -Y, z), (X, Y, z), s, fm, 0.004)
    t = 0.0015
    P.box_mm((-X, -Y - t, 0.02), (X, -Y + t, H), mat='M_WireMesh_Cutout', bevel=0.0)
    P.box_mm((-X, Y - t, 0.02), (X, Y + t, H), mat='M_WireMesh_Cutout', bevel=0.0)
    P.box_mm((-X - t, -Y, 0.02), (-X + t, Y, H), mat='M_WireMesh_Cutout', bevel=0.0)
    P.box_mm((X - t, -Y, 0.02), (X + t, Y, H), mat='M_WireMesh_Cutout', bevel=0.0)
    # lid (closed), hinged at the back
    LZ = H + 0.03
    LX, LY = X + 0.02, Y + 0.02
    for (a, b) in (((-LX, -LY), (LX, -LY)), ((-LX, LY), (LX, LY)), ((-LX, -LY), (-LX, LY)), ((LX, -LY), (LX, LY))):
        _member(P, (a[0], a[1], LZ), (b[0], b[1], LZ), 0.028, fm, 0.004)
    P.box_mm((-LX, -LY, LZ - t), (LX, LY, LZ + t), mat='M_WireMesh_Cutout', bevel=0.0)
    for x in (-0.4, 0.4):
        P.cyl((x - 0.05, Y + 0.012, H + 0.012), (x + 0.05, Y + 0.012, H + 0.012), 0.012, seg=8, mat=fm, bevel=0.0)
    P.box_mm((-0.08, -LY - 0.03, LZ - 0.05), (0.08, -LY - 0.01, LZ + 0.01), mat=fm, bevel=0.004)
    # garbage bags inside
    bag = [(0.0, 0.0), (0.14, 0.012), (0.20, 0.07), (0.215, 0.16), (0.19, 0.26), (0.11, 0.33), (0.035, 0.36),
           (0.03, 0.39), (0.065, 0.42), (0.045, 0.445), (0.0, 0.44)]
    for (x, y, sc, rz) in ((-0.32, 0.05, 1.0, 10), (0.12, 0.08, 0.92, 70), (-0.08, -0.12, 0.8, 40), (0.38, -0.1, 0.7, 0)):
        P.lathe([(r * sc, z * sc) for (r, z) in bag], seg=10, loc=(x, y, 0.0), rot=(0, 0, rz), mat='M_GarbageBag',
                bevel=0.0, sharp=70)
    # folded blue crow net on the lid
    P.box((0.55, 0.32, 0.05), (0.28, 0.0, LZ + 0.03), rot=(0, 2, 4), mat='M_PlasticBlue', bevel=0.02, seg=2)
    P.box((0.50, 0.30, 0.04), (0.26, 0.01, LZ + 0.07), rot=(0, -3, -3), mat='M_PlasticBlue', bevel=0.016, seg=2)
    # sign plate on the front
    P.box_mm((-0.26, -Y - 0.02, 0.54), (0.26, -Y - 0.008, 0.80), mat='M_PlasticWhite', bevel=0.004)
    front_decal(P, -0.25, 0.25, 0.545, 0.795, -Y - 0.0205, 'M_Deco_GarbageSign')
    P.note('M_WireMesh_Cutout = alpha-cutout (double-sided thin panels); needs a cutout toon material.')
    P.finish()


# ======================================================================================
# 13. Sidewalk transformer box
# ======================================================================================
@builder
def build_sidewalk_transformer_box():
    P = Prop('sidewalk_transformer_box', 'urban',
             desc='Ground-mounted power distribution box (地上機器) on Tokyo pavements, 1.4 x 0.5 x 1.4 m',
             origin='ground, footprint centre')
    gm = 'M_PaintedMetal_GrayGreen'
    P.box_mm((-0.76, -0.31, 0.0), (0.76, 0.31, 0.12), mat='M_Concrete', bevel=0.015)
    P.box_mm((-0.70, -0.25, 0.12), (0.70, 0.25, 1.38), mat=gm, bevel=0.012)
    P.box_mm((-0.725, -0.275, 1.38), (0.725, 0.275, 1.42), mat=gm, bevel=0.012)
    P.box_mm((-0.70, -0.25, 0.12), (0.70, 0.25, 0.17), mat='M_PaintedMetal_DarkGray', bevel=0.004)
    for sy in (-1, 1):
        yf = sy * 0.25
        for (x0, x1) in ((-0.68, -0.012), (0.012, 0.68)):
            P.box_mm((x0, yf - 0.006 if sy < 0 else yf, 0.19), (x1, yf if sy < 0 else yf + 0.006, 1.35), mat=gm,
                     bevel=0.004)
            for zz in (1.12, 0.26):
                for k in range(5):
                    z = zz + k * 0.035
                    P.box_mm((x0 + 0.08, yf - 0.016 if sy < 0 else yf + 0.004, z),
                             (x1 - 0.08, yf - 0.004 if sy < 0 else yf + 0.016, z + 0.016), mat=gm, bevel=0.0)
        for x in (-0.05, 0.05):
            P.box_mm((x - 0.012, yf - 0.03 if sy < 0 else yf + 0.006, 0.66), (x + 0.012, yf - 0.006 if sy < 0 else yf + 0.03, 0.84),
                     mat='M_Chrome', bevel=0.004)
    # warning sticker, lifting eyes
    front_decal(P, 0.18, 0.46, 0.92, 1.06, -0.2565, 'M_Deco_HVWarning')
    for x in (-0.6, 0.6):
        for y in (-0.18, 0.18):
            P.torus((x, y, 1.445), 0.025, 0.006, seg=10, rseg=4, rot=(90, 0, 90), mat='M_Galvanized')
    # side vents
    for sx in (-1, 1):
        for k in range(6):
            z = 1.0 + k * 0.04
            P.box_mm((sx * 0.70 - 0.004 if sx > 0 else -0.716, -0.16, z), (0.716 if sx > 0 else -0.70 + 0.004, 0.16, z + 0.018),
                     mat=gm, bevel=0.0)
    P.finish()
