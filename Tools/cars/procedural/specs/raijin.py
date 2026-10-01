"""RAIJIN BX-R -- 2020s Japanese turbo-boxer AWD sports sedan (Subaru WRX VB proportions).
4670 L x 1825 W x 1465 H, wheelbase 2670; hood scoop, black arch cladding, hexagon grille, C-lamps, quad pipes.
Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
from common import *  # noqa

WB = 2.67
SF, SR = WB / 2, -WB / 2


def spec():
    wheels = dict(r_f=0.327, r_r=0.327, w_f=0.255, w_r=0.255, track_f=1.575, track_r=1.585)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.42, 0.62), (2.26, 0.70), (2.12, 0.755), (1.85, 0.80), (1.335, 0.865), (0.95, 0.925), (0.70, 0.975),
             (0.55, 1.0), (0.3, 1.015), (-0.5, 1.03), (-1.2, 1.05), (-1.8, 1.075), (-2.1, 1.085), (-2.30, 1.10),
             (-2.36, 1.09), (-2.45, 1.05)],
        top_smooth=0.035,
        bot=[(2.4, 0.22), (2.2, 0.17), (1.9, 0.15), (0, 0.145), (-1.9, 0.16), (-2.2, 0.24), (-2.45, 0.30)],
        nose=[(0.12, 2.23), (0.20, 2.285), (0.30, 2.31), (0.42, 2.318), (0.52, 2.31), (0.62, 2.285), (0.70, 2.24),
              (0.76, 2.16), (0.80, 2.07)],
        nose_plan=[(0, 0), (0.3, 0.012), (0.5, 0.045), (0.62, 0.09), (0.72, 0.15), (0.80, 0.24), (0.86, 0.36),
                   (0.94, 0.62)],
        tail=[(0.16, -2.25), (0.26, -2.32), (0.38, -2.35), (0.52, -2.358), (0.70, -2.355), (0.84, -2.345),
              (0.96, -2.335), (1.06, -2.33), (1.10, -2.33)],
        tail_smooth=0.015,
        tail_plan=[(0, 0), (0.3, 0.012), (0.5, 0.04), (0.62, 0.08), (0.72, 0.13), (0.80, 0.21), (0.86, 0.32),
                   (0.93, 0.55)],
        halfw=[(2.4, 0.78), (2.2, 0.84), (1.9, 0.862), (1.5, 0.872), (1.0, 0.868), (0.3, 0.862), (-0.5, 0.866),
               (-1.0, 0.875), (-1.5, 0.878), (-1.9, 0.87), (-2.2, 0.85), (-2.4, 0.80)],
        sections=[(1.3, [(0.0, -0.10), (0.15, -0.055), (0.30, -0.015), (0.45, 0.0), (0.62, -0.004), (0.74, -0.02),
                         (0.84, -0.05), (0.95, -0.10)]),
                  (0.0, [(0.0, -0.10), (0.18, -0.05), (0.32, -0.018), (0.50, -0.004), (0.66, 0.0), (0.82, -0.012),
                         (0.95, -0.035), (1.06, -0.08)]),
                  (-1.3, [(0.0, -0.10), (0.15, -0.055), (0.30, -0.016), (0.50, 0.0), (0.70, -0.004), (0.86, -0.02),
                          (0.98, -0.05), (1.12, -0.10)])],
        crown=[(2.3, 0.03), (1.3, 0.035), (0.5, 0.03), (-1.3, 0.035), (-2.3, 0.03)],
        peaks=dict(amp=[(2.4, 0.0), (2.15, 0.015), (1.6, 0.022), (0.9, 0.015), (0.6, 0.0)],
                   x=[(2.0, 0.66), (1.3, 0.72), (0.6, 0.74)], w=0.12),
        flares=[dict(s=SF + 0.02, z=0.60, amp=0.018, ss=0.40, sz=0.16, p=1.4),
                dict(s=SR - 0.03, z=0.62, amp=0.018, ss=0.44, sz=0.17, p=1.4)],
        r_sh=[(2.3, 0.045), (1.3, 0.04), (0.5, 0.025), (-0.6, 0.025), (-1.3, 0.04), (-2.3, 0.035)],
        r_nose=0.05, r_tail=0.04, r_bot=0.05,
        roof=[(0.72, 0.90), (0.55, 1.0), (0.30, 1.14), (0.05, 1.28), (-0.20, 1.388), (-0.45, 1.435), (-0.75, 1.445),
              (-1.05, 1.428), (-1.30, 1.39), (-1.55, 1.305), (-1.80, 1.19), (-1.98, 1.11), (-2.1, 1.07)],
        gh_s=(-2.1, 0.74),
        gh_w=[(0.74, 0.60), (0.55, 0.65), (0.0, 0.73), (-0.6, 0.745), (-1.2, 0.735), (-1.6, 0.68), (-1.9, 0.60)],
        belt=[(0.55, 1.0), (-0.5, 1.02), (-1.3, 1.055), (-1.8, 1.08)],
        tumble=[(0.5, 26), (-0.5, 21), (-1.3, 24), (-1.8, 30)],
        roof_crown=[(0.4, 0.045), (-0.6, 0.05), (-1.6, 0.05)],
        r_rail=[(0.4, 0.05), (-0.6, 0.06), (-1.6, 0.07)],
        r_belt=0.012,
        arches=dict(gap=0.05, dz=0.02, r_lip=0.006, inner=0.05, sx=1.06, sz=1.0, n=2.6,
                    lip=dict(amp=0.012, off=0.04, w=0.04)),
        extra_w=0.14,
        side_bumps=[side_bump(spline([(0.85, 0.27), (0.82, 0.38), (0.0, 0.40), (-0.85, 0.42), (-0.92, 0.27)]),
                              -0.008, 0.025)],
    )
    st = []
    WG = dict(x_min=0.58, z_min=0.95)
    dlo = [(0.50, 1.02, "c"), (0.22, 1.16), (-0.05, 1.30), (-0.30, 1.375), (-0.70, 1.392), (-1.10, 1.372),
           (-1.40, 1.31), (-1.62, 1.20), (-1.76, 1.11, "c"), (-1.45, 1.08), (-0.6, 1.045), (0.2, 1.025)]
    st.append(trim(spline(dlo, grow=0.012), "side", WG, depth=0.002, name="dlo_frame"))
    st.append(glass(spline(dlo), "side", WG, name="dlo"))
    st.append(trim(stroke([(-0.40, 1.03), (-0.43, 1.40)], 0.07), "side", WG, name="b_pillar"))
    st.append(trim(stroke([(-1.42, 1.075), (-1.32, 1.33)], 0.025), "side", WG, name="c_bar"))
    st.append(glass(poly([(0.53, 0.0), (0.53, 0.56), (0.30, 0.57), (-0.19, 0.53), (-0.21, 0.0)]), "top",
                    dict(z_min=1.0, x_max=0.6), name="windshield"))
    st.append(glass(poly([(-1.32, 0.0), (-1.32, 0.50), (-1.50, 0.53), (-1.88, 0.50), (-1.97, 0.40), (-1.99, 0.0)]),
                    "top", dict(z_min=1.08, x_max=0.6), name="backlight"))
    st.append(trim(rect((0.565, 0.0), (0.03, 0.62)), "top", dict(z_min=0.92, x_max=0.62), depth=0.006, name="cowl"))
    # seams
    st.append(seam([(0.60, 0.0, "c"), (0.60, 0.62, "c"), (1.2, 0.66), (1.8, 0.64), (2.10, 0.52), (2.15, 0.3),
                    (2.16, 0.0)], "top", dict(z_min=0.65), name="hood"))
    st.append(seam([(0.50, 1.0, "c"), (0.54, 0.75), (0.52, 0.45), (0.48, 0.31, "c"), (-0.40, 0.31),
                    (-0.43, 1.03, "c")], "side", dict(x_min=0.6), name="door_f"))
    st.append(seam([(-0.45, 0.31, "c"), (-1.0, 0.31), (-1.10, 0.36), (-1.20, 0.55), (-1.30, 0.80), (-1.36, 1.06, "c")],
                   "side", dict(x_min=0.6), name="door_r"))
    st.append(seam([(-2.03, 0.0, "c"), (-2.03, 0.56, "c"), (-2.22, 0.58), (-2.33, 0.55)], "top", dict(z_min=1.0),
                   name="trunk"))
    for hs in (0.05, -0.92):
        st.append(trim(rect((hs, 0.90), (0.065, 0.012)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    # black cladding: arches (ring band), sills, lower bumpers
    for sa, R in ((SF, wheels["r_f"] + 0.05), (SR, wheels["r_r"] + 0.05)):
        ring = spline([(sa - (R + 0.075) * 1.06, wheels["r_f"] - 0.06, "c"), (sa - (R + 0.07) * 1.0, 0.55),
                       (sa - (R + 0.06) * 0.62, 0.78), (sa, 0.425 + R), (sa + (R + 0.06) * 0.62, 0.78),
                       (sa + (R + 0.07) * 1.0, 0.55), (sa + (R + 0.075) * 1.06, wheels["r_f"] - 0.06, "c")])
        st.append(trim(ring, "side", dict(x_min=0.62), depth=-0.004, name="clad_arch"))
    st.append(trim(poly([(SF + 0.2, 0.0), (SF + 0.2, 0.30), (SR - 0.2, 0.30), (SR - 0.2, 0.0)]), "side",
                   dict(x_min=0.62), depth=-0.004, name="clad_sill"))
    # hood scoop: raised box with a black mouth
    so = []
    so.append(box_solid((1.60, 0.0, 0.832), (0.25, 0.28, 0.045), r=0.03, k=0.035, mat=None, name="scoop", pitch=-5))
    sp["late"] = [Stamp(rect((0.0, 0.87), (0.25, 0.018)), "front", dict(s_min=1.55, s_max=1.95, z_min=0.84),
                        op="recess", depth=0.06, mat="M_Grille", name="scoop_mouth")]
    # front
    WF = dict(s_min=1.95)
    st.append(Stamp(poly([(0.0, 0.665), (0.36, 0.665), (0.42, 0.60), (0.36, 0.43), (0.30, 0.40), (0.0, 0.40)]),
                    "front", WF, op="recess", depth=0.06, mat="M_Grille", wall_mat="M_Trim", name="grille"))
    st.append(Stamp(spline([(0.50, 0.42, "c"), (0.70, 0.46), (0.80, 0.42), (0.83, 0.30), (0.78, 0.22),
                            (0.55, 0.20), (0.48, 0.26)]), "front", dict(s_min=1.9), op="recess", depth=0.05,
                    mat="M_Grille", wall_mat="M_Trim", name="intake_s"))
    st.append(Stamp(spline([(0.0, 0.33, "c"), (0.36, 0.33), (0.40, 0.25), (0.34, 0.20), (0.0, 0.20, "c")]), "front",
                    WF, op="recess", depth=0.05, mat="M_Grille", name="intake_c"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.36), (0.44, 0.36), (0.86, 0.44), (0.95, 0.44), (0.95, 0.0)]), "front",
                   dict(s_min=2.0), depth=-0.003, name="bumper_low"))
    hl = spline([(0.42, 0.705, "c"), (0.60, 0.735), (0.80, 0.765), (0.87, 0.76, "c"), (0.87, 0.71), (0.78, 0.672),
                 (0.60, 0.662), (0.46, 0.67)])
    WH_ = dict(s_min=1.8)
    st.append(Stamp(hl, "front", WH_, op="recess", depth=0.014, mat="M_HeadLight", wall_mat="M_Trim",
                    name="headlight"))
    st.append(Stamp(stroke([(0.50, 0.712), (0.47, 0.69), (0.50, 0.672), (0.62, 0.668)], 0.01), "front", WH_,
                    op="raise", depth=0.004, mat="M_Chrome", name="c_drl"))
    st.append(Stamp(stroke([(0.55, 0.72), (0.70, 0.74), (0.82, 0.755)], 0.012), "front", WH_, op="paint",
                    mat="M_Trim", name="hl_brow"))
    for cx, cz in ((0.66, 0.705), (0.75, 0.718)):
        st.append(Stamp(ellipse((cx, cz), (0.024, 0.02)), "front", WH_, op="raise", depth=0.005, mat="M_Chrome",
                        name="projector"))
    # rear
    WR = dict(s_max=-2.0)
    tl = spline([(0.40, 0.99, "c"), (0.70, 1.012), (0.86, 1.006), (0.905, 0.96), (0.89, 0.87), (0.80, 0.858),
                 (0.74, 0.90), (0.50, 0.928)])
    st.append(Stamp(tl, "rear", WR, op="recess", depth=0.010, mat="M_TailLight", wall_mat="M_Trim", name="taillight"))
    st.append(Stamp(stroke([(0.50, 0.968), (0.80, 0.982), (0.86, 0.95), (0.84, 0.905)], 0.009), "rear", WR,
                    op="paint", mat="M_Trim", name="c_line"))
    st.append(seam([(0.0, 0.88), (0.40, 0.885)], "rear", WR, name="trunk_rear"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.45), (0.50, 0.45), (0.80, 0.50), (0.95, 0.50), (0.95, 0.0)]), "rear",
                   dict(s_max=-2.05), depth=-0.004, name="bumper_low_r"))
    for fx in (0.10, 0.22):
        st.append(Stamp(stroke([(fx, 0.15), (fx, 0.34)], 0.012), "rear", dict(s_max=-2.1), op="raise", depth=0.03,
                        mat="M_Trim", name="fin"))
    st.append(Stamp(rect((0.52, 0.27), (0.13, 0.06)), "rear", dict(s_max=-2.1), op="recess", depth=0.05,
                    mat="M_Underbody", name="exh_hole"))
    st.append(Stamp(rect((0.80, 0.38), (0.035, 0.035)), "rear", dict(s_max=-2.05), op="recess", depth=0.02,
                    mat="M_Grille", name="r_vent"))
    sp["stamps"] = st
    so += mirror_solids((0.42, 0.82, 1.06), 0.36, 1.11, 0.95, size=(0.20, 0.09, 0.12), yaw=6)
    so.append(box_solid((-2.27, 0.0, 1.098), (0.035, 0.46, 0.012), r=0.01, k=0.02, mat="M_Paint", name="lip"))
    sp["solids"] = so
    return dict(
        id="raijin", body=sp, wheels=wheels,
        wheel_design=dict(rim_in=18, design=dict(kind="straight", n=10, w_rim=0.0085, w_hub=0.013, twist=0.0),
                          dish=0.03, stretch=0.004),
        body_tris=82000,
        exhaust_tips=[dict(c=(None, 0.46, 0.27), r=0.042, len=0.13, out=0.03),
                      dict(c=(None, 0.58, 0.27), r=0.042, len=0.13, out=0.03)],
        slats=[dict(view="front", x=0.38, zs=[0.46, 0.51, 0.56, 0.61], thick=0.012, depth=0.035)],
        empties={"Light_Head_L": (2.22, 0.68, 0.72), "Light_Head_R": (2.22, -0.68, 0.72),
                 "Light_Tail_L": (-2.33, 0.72, 0.95), "Light_Tail_R": (-2.33, -0.72, 0.95),
                 "Exhaust_L": (-2.4, 0.52, 0.27), "Exhaust_R": (-2.4, -0.52, 0.27)},
        plates={"front": [0.0, 0.27, 2.32], "rear": [0.0, 0.66, -2.358]},
        half_width=0.9125,
        kit={"wing": {"span": 1.60, "chord": 0.28, "height": 0.26, "mount_x": 0.38, "from_rear": 0.08},
             "splitter": {"protrude": 0.05, "depth": 0.30}},
    )
