"""KAIJU SPR-X -- 2020s Japanese straight-six FR coupe (GR Supra A90 proportions).
4379 L x 1854 W x 1292 H, wheelbase 2470 (short), long hood, double-bubble roof, big haunches, ducktail.
Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
from common import *  # noqa

WB = 2.47
SF, SR = WB / 2, -WB / 2


def spec():
    wheels = dict(r_f=0.335, r_r=0.338, w_f=0.265, w_r=0.285, track_f=1.60, track_r=1.60)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.35, 0.52), (2.20, 0.57), (2.06, 0.632), (1.85, 0.69), (1.55, 0.745), (1.235, 0.79), (0.9, 0.85),
             (0.6, 0.90), (0.42, 0.928), (0.2, 0.94), (-0.5, 0.955), (-1.0, 0.975), (-1.5, 1.005), (-1.75, 1.025),
             (-1.95, 1.05), (-2.06, 1.08), (-2.2, 1.04)],
        top_smooth=0.035,
        bot=[(2.3, 0.18), (2.12, 0.15), (1.8, 0.13), (0, 0.12), (-1.7, 0.14), (-2.0, 0.22), (-2.25, 0.28)],
        nose=[(0.10, 2.12), (0.17, 2.17), (0.26, 2.205), (0.36, 2.215), (0.44, 2.20), (0.52, 2.165), (0.59, 2.11),
              (0.65, 2.04), (0.70, 1.95)],
        nose_plan=[(0, 0), (0.15, 0.012), (0.30, 0.04), (0.45, 0.085), (0.58, 0.14), (0.68, 0.20), (0.77, 0.28),
                   (0.84, 0.38), (0.90, 0.52), (0.96, 0.75)],
        tail=[(0.14, -2.04), (0.24, -2.12), (0.36, -2.16), (0.50, -2.168), (0.66, -2.16), (0.78, -2.14),
              (0.88, -2.105), (0.96, -2.08), (1.03, -2.075), (1.08, -2.075)],
        tail_smooth=0.015,
        tail_plan=[(0, 0), (0.3, 0.008), (0.5, 0.025), (0.60, 0.045), (0.68, 0.11), (0.76, 0.22), (0.83, 0.38),
                   (0.90, 0.62)],
        halfw=[(2.3, 0.74), (2.1, 0.81), (1.85, 0.845), (1.5, 0.855), (1.2, 0.855), (0.8, 0.84), (0.3, 0.826),
               (-0.2, 0.83), (-0.6, 0.84), (-1.0, 0.855), (-1.3, 0.86), (-1.6, 0.85), (-1.9, 0.82), (-2.1, 0.77),
               (-2.25, 0.70)],
        sections=[(1.3, [(0.0, -0.10), (0.15, -0.06), (0.30, -0.018), (0.45, 0.0), (0.58, -0.004), (0.68, -0.02),
                         (0.78, -0.055), (0.9, -0.11)]),
                  (0.0, [(0.0, -0.12), (0.18, -0.07), (0.32, -0.03), (0.50, -0.008), (0.64, 0.0), (0.78, -0.012),
                         (0.90, -0.04), (1.0, -0.08)]),
                  (-1.25, [(0.0, -0.15), (0.15, -0.095), (0.30, -0.035), (0.48, 0.0), (0.62, 0.0), (0.74, -0.025),
                           (0.84, -0.068), (0.94, -0.125), (1.06, -0.20)])],
        crown=[(2.2, 0.03), (1.3, 0.035), (0.5, 0.03), (-1.3, 0.04), (-2.2, 0.03)],
        peaks=dict(amp=[(2.3, 0.0), (2.1, 0.045), (1.8, 0.08), (1.2, 0.085), (0.8, 0.05), (0.5, 0.0),
                        (-0.7, 0.0), (-1.2, 0.045), (-1.7, 0.05), (-2.05, 0.02), (-2.2, 0.0)],
                   x=[(2.0, 0.64), (1.5, 0.70), (0.9, 0.72), (-1.25, 0.72), (-1.9, 0.66)], w=0.115),
        flares=[dict(s=SF + 0.03, z=0.60, amp=0.05, ss=0.36, sz=0.17, p=1.5),
                dict(s=SR - 0.08, z=0.66, amp=0.068, ss=0.48, sz=0.22, p=1.25)],
        r_sh=[(2.2, 0.05), (1.3, 0.05), (0.6, 0.035), (0.0, 0.03), (-0.6, 0.045), (-1.25, 0.09), (-2.2, 0.06)],
        r_nose=0.05, r_tail=0.04, r_bot=0.05,
        roof=[(0.60, 0.83), (0.42, 0.93), (0.20, 1.05), (0.0, 1.16), (-0.18, 1.235), (-0.40, 1.282), (-0.62, 1.285),
              (-0.85, 1.25), (-1.10, 1.185), (-1.35, 1.12), (-1.55, 1.07), (-1.75, 1.03), (-1.90, 0.99)],
        gh_s=(-1.92, 0.62),
        gh_w=[(0.62, 0.58), (0.42, 0.62), (0.0, 0.69), (-0.5, 0.71), (-1.0, 0.68), (-1.4, 0.59), (-1.7, 0.50),
              (-1.9, 0.43)],
        belt=[(0.4, 0.935), (-0.3, 0.95), (-1.0, 0.985), (-1.6, 1.02)],
        tumble=[(0.4, 28), (-0.4, 24), (-1.2, 33), (-1.8, 40)],
        roof_crown=[(0.4, 0.04), (-0.5, 0.045), (-1.4, 0.05)],
        r_rail=[(0.4, 0.05), (-0.5, 0.07), (-1.4, 0.09)],
        bubble=dict(depth=0.022, w=0.13, s0=-1.25, s1=0.05),
        r_belt=0.012,
        arches=dict(gap=0.042, dz=0.018, r_lip=0.008, inner=0.05, lip=dict(amp=0.006, off=0.03, w=0.022)),
        extra_w=0.14,
        top_bumps=[bump(spline([(0.50, 0.0, "c"), (0.50, 0.16), (1.0, 0.19), (1.70, 0.16), (2.0, 0.09),
                                (2.05, 0.0, "c")]), 0.011, 0.10)],
        side_bumps=[side_bump(spline([(0.80, 0.22), (0.78, 0.38), (0.30, 0.44), (-0.30, 0.52), (-0.70, 0.60),
                                      (-0.88, 0.56), (-0.92, 0.40), (-0.90, 0.22)]), -0.03, 0.03)],
    )
    st = []
    WG = dict(x_min=0.55, z_min=0.9)
    dlo = [(0.40, 0.945, "c"), (0.15, 1.07), (-0.05, 1.18), (-0.30, 1.238), (-0.62, 1.245), (-0.92, 1.19),
           (-1.18, 1.10), (-1.36, 1.035, "c"), (-1.1, 1.0), (-0.5, 0.965), (0.2, 0.948)]
    st.append(trim(spline(dlo, grow=0.012), "side", WG, depth=0.002, name="dlo_frame"))
    st.append(glass(spline(dlo), "side", WG, name="dlo"))
    st.append(trim(stroke([(-0.88, 0.985), (-0.95, 1.21)], 0.026), "side", WG, name="q_bar"))
    st.append(glass(poly([(0.40, 0.0), (0.40, 0.52), (0.20, 0.53), (-0.15, 0.48), (-0.17, 0.0)]), "top",
                    dict(z_min=0.95, x_max=0.56), name="windshield"))
    st.append(glass(poly([(-0.85, 0.0), (-0.85, 0.42), (-1.10, 0.46), (-1.45, 0.42), (-1.58, 0.28), (-1.60, 0.0)]),
                    "top", dict(z_min=1.0, x_max=0.56), name="backlight"))
    st.append(trim(rect((0.43, 0.0), (0.03, 0.60)), "top", dict(z_min=0.86, x_max=0.6), depth=0.006, name="cowl"))
    # seams
    st.append(seam([(0.47, 0.0, "c"), (0.47, 0.58, "c"), (1.0, 0.63), (1.6, 0.60), (1.98, 0.42), (2.06, 0.2),
                    (2.08, 0.0)], "top", dict(z_min=0.55), name="hood"))
    st.append(seam([(0.38, 0.93, "c"), (0.42, 0.70), (0.40, 0.42), (0.36, 0.25, "c"), (-0.86, 0.29, "c"),
                    (-0.90, 0.62), (-0.86, 0.985, "c")], "side", dict(x_min=0.6), name="door"))
    st.append(seam([(-1.62, 0.0, "c"), (-1.62, 0.50, "c"), (-1.9, 0.53), (-2.06, 0.50)], "top", dict(z_min=0.95),
                   name="trunk"))
    st.append(trim(rect((-0.62, 0.86), (0.065, 0.012)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    # side vents
    st.append(Stamp(spline([(0.86, 0.66), (0.82, 0.665), (0.74, 0.50), (0.70, 0.43), (0.75, 0.44), (0.82, 0.52)]),
                    "side", dict(x_min=0.6, s_min=0.6, s_max=1.0), op="recess", depth=0.022, mat="M_Grille",
                    name="fender_vent"))
    st.append(Stamp(spline([(-0.74, 0.585), (-0.86, 0.60), (-0.92, 0.48), (-0.90, 0.36), (-0.82, 0.40),
                            (-0.78, 0.50)]), "side", dict(x_min=0.6, s_min=-1.0, s_max=-0.6), op="recess",
                    depth=0.025, mat="M_Grille", name="door_vent"))
    st.append(trim(poly([(SF - 0.42, 0.0), (SF - 0.42, 0.225), (SR + 0.45, 0.245), (SR + 0.45, 0.0)]), "side",
                   dict(x_min=0.6), depth=-0.004, name="sill"))
    # hood vents
    for sx_ in (1,):
        st.append(Stamp(poly([(1.55, 0.14), (1.72, 0.16), (1.73, 0.23), (1.56, 0.21)]), "top", dict(z_min=0.6),
                        op="recess", depth=0.012, mat="M_Grille", name="hood_vent"))
    # front
    WF = dict(s_min=1.85)
    st.append(Stamp(spline([(0.0, 0.36, "c"), (0.28, 0.36), (0.36, 0.33), (0.40, 0.20), (0.36, 0.165),
                            (0.0, 0.165, "c")]), "front", WF, op="recess", depth=0.06, mat="M_Grille",
                    wall_mat="M_Trim", name="intake_c"))
    st.append(Stamp(spline([(0.50, 0.43, "c"), (0.62, 0.48), (0.76, 0.515, "c"), (0.82, 0.40), (0.82, 0.24),
                            (0.76, 0.19), (0.56, 0.18), (0.48, 0.24)]), "front", dict(s_min=1.7), op="recess",
                    depth=0.06, mat="M_Grille", wall_mat="M_Trim", name="intake_s"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.155), (0.5, 0.16), (0.85, 0.17), (0.95, 0.17), (0.95, 0.0)]), "front",
                   dict(s_min=1.95), depth=-0.003, name="chin"))
    hl = spline([(0.50, 0.565, "c"), (0.64, 0.615), (0.78, 0.66), (0.875, 0.685, "c"), (0.89, 0.64), (0.82, 0.59),
                 (0.66, 0.552), (0.55, 0.548)])
    WH_ = dict(s_min=1.62)
    st.append(Stamp(hl, "front", WH_, op="recess", depth=0.016, mat="M_Trim", wall_mat="M_Trim", name="headlight"))
    st.append(Stamp(stroke([(0.52, 0.572), (0.66, 0.622), (0.80, 0.665), (0.87, 0.678)], 0.012), "front", WH_,
                    op="raise", depth=0.004, mat="M_HeadLight", name="drl"))
    for cx, cz in ((0.62, 0.585), (0.70, 0.607), (0.78, 0.632)):
        st.append(Stamp(ellipse((cx, cz), (0.022, 0.019)), "front", WH_, op="raise", depth=0.006,
                        mat="M_HeadLight", name="projector"))
    # rear
    WR = dict(s_max=-1.85)
    tl = spline([(0.36, 0.928, "c"), (0.58, 0.955), (0.78, 0.99), (0.87, 0.995, "c"), (0.86, 0.95), (0.72, 0.918),
                 (0.52, 0.905)])
    st.append(Stamp(tl, "rear", WR, op="recess", depth=0.010, mat="M_TailLight", wall_mat="M_Trim", name="taillight"))
    st.append(seam([(0.0, 0.905), (0.30, 0.91)], "rear", WR, name="trunk_rear"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.42), (0.30, 0.42), (0.55, 0.44), (0.72, 0.50), (0.95, 0.52),
                         (0.95, 0.0)]), "rear", dict(s_max=-1.80), depth=-0.004, name="diffuser"))
    st.append(trim(poly([(SR - 0.40, 0.0), (SR - 0.40, 0.25), (SR - 0.55, 0.36), (-2.0, 0.45), (-2.4, 0.45),
                         (-2.4, 0.0)]), "side", dict(x_min=0.55, s_max=-1.55), depth=-0.004, name="rear_lower_side"))
    for fx in (0.14, 0.27):
        st.append(Stamp(stroke([(fx, 0.12), (fx, 0.32)], 0.01), "rear", dict(s_max=-1.9), op="raise", depth=0.03,
                        mat="M_Trim", name="fin"))
    st.append(Stamp(rect((0.0, 0.27), (0.022, 0.06)), "rear", dict(s_max=-1.9), op="raise", depth=0.006,
                    mat="M_TailLight", name="fog"))
    st.append(Stamp(ellipse((0.47, 0.265), (0.065, 0.058)), "rear", dict(s_max=-1.95), op="recess", depth=0.06,
                    mat="M_Underbody", name="exh_hole"))
    st.append(Stamp(rect((0.80, 0.50), (0.05, 0.009)), "rear", dict(s_max=-1.95), op="raise", depth=0.003,
                    mat="M_TailLight", name="reflector"))
    sp["stamps"] = st
    so = []
    so += mirror_solids((0.27, 0.80, 0.975), 0.20, 1.03, 0.94, size=(0.19, 0.09, 0.10), yaw=6)
    sp["solids"] = so
    return dict(
        id="kaiju", body=sp, wheels=wheels,
        wheel_design=dict(rim_in=19, design=dict(kind="y", n=5, gap=0.13, split=0.5, twist=0.4), dish=0.04,
                          stretch=0.006),
        body_tris=82000,
        exhaust_tips=[dict(c=(None, 0.47, 0.265), r=0.05, len=0.14, out=0.03)],
        slats=[dict(view="front", x=0.33, zs=[0.21, 0.26, 0.31], thick=0.012, depth=0.035, hole=(0.18, 0.15, 0.5)),
               dict(view="front", x=0.0, zs=[0.22, 0.44], xs=[0.58, 0.66, 0.74], thick=0.012, depth=0.035)],
        empties={"Light_Head_L": (2.06, 0.70, 0.62), "Light_Head_R": (2.06, -0.70, 0.62),
                 "Light_Tail_L": (-2.10, 0.70, 0.945), "Light_Tail_R": (-2.10, -0.70, 0.945),
                 "Exhaust_L": (-2.2, 0.47, 0.265), "Exhaust_R": (-2.2, -0.47, 0.265)},
        plates={"front": [0.0, 0.29, 2.21], "rear": [0.0, 0.56, -2.165]},
        half_width=0.927,
        kit={"wing": {"span": 1.60, "chord": 0.28, "height": 0.22, "mount_x": 0.36, "from_rear": 0.14},
             "splitter": {"protrude": 0.05, "depth": 0.30}},
    )
