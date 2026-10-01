"""Traffic: Tokyo taxi -- tall 2010s/20s purpose-built taxi MPV (JPN-Taxi-like proportions), generic lit TAXI sign.
4400 L x 1695 W x 1750 H, wheelbase 2750.  Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
import math

from common import *  # noqa

WB = 2.75
SF, SR = WB / 2, -WB / 2


def spec():
    wheels = dict(r_f=0.30, r_r=0.30, w_f=0.185, w_r=0.185, track_f=1.46, track_r=1.46)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.25, 0.70), (2.10, 0.80), (1.95, 0.86), (1.70, 0.90), (1.375, 0.955), (1.2, 1.0), (1.0, 1.02),
             (0.0, 1.03), (-1.5, 1.04), (-2.1, 1.05), (-2.3, 1.0)],
        bot=[(2.2, 0.24), (2.0, 0.19), (1.7, 0.17), (0, 0.16), (-1.8, 0.17), (-2.1, 0.24), (-2.3, 0.30)],
        nose=[(0.15, 2.09), (0.25, 2.135), (0.40, 2.155), (0.55, 2.15), (0.70, 2.12), (0.80, 2.07), (0.88, 1.98),
              (0.93, 1.88)],
        nose_plan=[(0, 0), (0.3, 0.01), (0.5, 0.04), (0.65, 0.09), (0.75, 0.16), (0.82, 0.26), (0.88, 0.42)],
        tail=[(0.18, -2.17), (0.30, -2.23), (0.50, -2.245), (0.90, -2.245), (1.05, -2.24)],
        tail_plan=[(0, 0), (0.4, 0.01), (0.6, 0.03), (0.72, 0.07), (0.80, 0.14), (0.86, 0.26)],
        halfw=[(2.15, 0.78), (1.9, 0.83), (1.375, 0.845), (0.0, 0.8475), (-1.375, 0.845), (-2.0, 0.84),
               (-2.2, 0.82)],
        sections=[(0.0, [(0.0, -0.09), (0.2, -0.04), (0.35, -0.01), (0.5, 0.0), (0.8, 0.0), (0.95, -0.01),
                         (1.05, -0.03), (1.2, -0.08)])],
        crown=0.03,
        r_sh=0.05, r_nose=0.06, r_tail=0.04, r_bot=0.05,
        roof=[(1.32, 0.95), (1.20, 1.0), (1.0, 1.15), (0.75, 1.36), (0.50, 1.55), (0.30, 1.68), (0.10, 1.735),
              (-0.5, 1.75), (-1.5, 1.75), (-2.0, 1.735), (-2.15, 1.69), (-2.22, 1.58), (-2.26, 1.35), (-2.29, 1.0)],
        roof_smooth=0.02,
        gh_s=(-2.30, 1.32),
        gh_w=[(1.3, 0.70), (1.0, 0.76), (0.0, 0.80), (-1.8, 0.80), (-2.2, 0.78)],
        belt=[(1.1, 1.0), (-2.2, 1.04)],
        tumble=8.0, roof_crown=0.04, r_rail=0.07, r_belt=0.012,
        arches=dict(gap=0.04, dz=0.02, r_lip=0.008, inner=0.05),
        extra_w=0.12,
    )
    st = []
    st.append(glass(spline([(0.0, 1.655, "c"), (0.60, 1.645), (0.69, 1.58), (0.71, 1.12), (0.66, 1.05),
                            (0.0, 1.05, "c")]), "front", dict(s_min=0.3, z_min=1.0), name="windshield"))
    dlo = [(1.08, 1.055, "c"), (0.70, 1.38), (0.38, 1.63), (0.1, 1.665), (-1.5, 1.67), (-2.02, 1.64), (-2.12, 1.55),
           (-2.14, 1.08, "c"), (-1.0, 1.065), (0.2, 1.06)]
    W = dict(x_min=0.6, z_min=1.0)
    st.append(glass(spline(dlo), "side", W, name="dlo"))
    for a, b, wd in (((0.12, 1.06), (0.12, 1.67), 0.07), ((-1.08, 1.06), (-1.08, 1.67), 0.06),
                     ((-1.90, 1.07), (-1.88, 1.66), 0.08)):
        st.append(trim(stroke([a, b], wd), "side", W, name="pillar"))
    st.append(glass(spline([(0.0, 1.62, "c"), (0.58, 1.60), (0.64, 1.50), (0.64, 1.18), (0.58, 1.12),
                            (0.0, 1.12, "c")]), "rear", dict(s_max=-1.9, z_min=1.0), name="backlight"))
    st.append(seam([(1.12, 1.03), (1.18, 0.60), (1.10, 0.30), (0.14, 0.30), (0.12, 1.05)], "side", dict(x_min=0.6),
                   smooth=False, name="door_f"))
    st.append(seam([(0.06, 1.05), (0.08, 0.30), (-1.02, 0.30), (-1.06, 1.05)], "side", dict(x_min=0.6), smooth=False,
                   name="door_r"))
    for hs in (0.25, -0.90):
        st.append(trim(rect((hs, 0.92), (0.07, 0.014)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    st.append(trim(poly([(SF + 0.3, 0.0), (SF + 0.3, 0.28), (SR - 0.3, 0.28), (SR - 0.3, 0.0)]), "side",
                   dict(x_min=0.6), depth=-0.003, name="sill"))
    # front: round lamps + chrome grille
    WF = dict(s_min=1.7)
    st.append(Stamp(rect((0.0, 0.72), (0.30, 0.085)), "front", WF, op="recess", depth=0.04, mat="M_Grille",
                    wall_mat="M_Chrome", name="grille"))
    st.append(Stamp(ellipse((0.575, 0.78), (0.098, 0.098)), "front", WF, op="recess", depth=0.012,
                    mat="M_HeadLight", wall_mat="M_Chrome", name="headlight"))
    st.append(Stamp(stroke([(0.575 + 0.098 * math.cos(a / 16 * 6.2832), 0.78 + 0.098 * math.sin(a / 16 * 6.2832))
                            for a in range(17)], 0.016), "front", WF, op="raise", depth=0.004, mat="M_Chrome",
                    name="ring"))
    st.append(Stamp(rect((0.73, 0.58), (0.06, 0.02)), "front", WF, op="raise", depth=0.004, mat="M_TailLight",
                    name="turn"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.36), (0.6, 0.38), (0.95, 0.40), (0.95, 0.0)]), "front",
                   dict(s_min=1.9), depth=-0.003, name="bumper"))
    # rear
    WR = dict(s_max=-1.95)
    st.append(Stamp(rect((0.77, 1.02), (0.05, 0.22)), "rear", WR, op="recess", depth=0.01, mat="M_TailLight",
                    wall_mat="M_Trim", name="taillight"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.40), (0.95, 0.42), (0.95, 0.0)]), "rear", dict(s_max=-2.1),
                   depth=-0.003, name="bumper_r"))
    sp["stamps"] = st
    sp["solids"] = mirror_solids((1.00, 0.80, 1.10), 0.94, 1.16, 0.93, size=(0.18, 0.08, 0.12), yaw=4)
    return dict(
        id="traffic_taxi", traffic=True, body=sp, wheels=wheels, h=0.010, body_tris=13000,
        wheel_design=dict(rim_in=15, design=dict(kind="steel", holes=8, r_hub=0.06, cap_mat="M_Chrome"), dish=0.02,
                          seg=24, grooves=2, no_caliper=True, no_disc=True),
        slats=[dict(view="front", x=0.28, zs=[0.665, 0.70, 0.735, 0.77], thick=0.009, depth=0.03, slot="M_Chrome")],
        roof_sign=dict(s=0.05, text="TAXI", accent="#FFE600", size=(0.44, 0.15, 0.14)),
        empties={"Light_Head_L": (2.15, 0.575, 0.78), "Light_Head_R": (2.15, -0.575, 0.78),
                 "Light_Tail_L": (-2.25, 0.77, 1.02), "Light_Tail_R": (-2.25, -0.77, 1.02),
                 "Exhaust_L": (-2.2, 0.45, 0.25), "Exhaust_R": (-2.2, -0.45, 0.25)},
        plates={"front": [0.0, 0.48, 2.155], "rear": [0.0, 0.62, -2.245]},
        preview_color=[0.02, 0.03, 0.10],
    )
