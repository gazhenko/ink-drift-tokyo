"""Traffic: Japanese one-box delivery van (Hiace H200-like proportions), semi cab-over, sliding side door.
4695 L x 1695 W x 1980 H, wheelbase 2570.  Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
from common import *  # noqa

WB = 2.57
SF, SR = WB / 2, -WB / 2


def spec():
    wheels = dict(r_f=0.335, r_r=0.335, w_f=0.195, w_r=0.195, track_f=1.465, track_r=1.46)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.35, 0.85), (2.25, 0.955), (2.10, 1.03), (1.95, 1.075), (1.0, 1.09), (-1.0, 1.10), (-2.3, 1.10),
             (-2.45, 1.05)],
        bot=[(2.3, 0.26), (2.1, 0.20), (1.8, 0.18), (0, 0.17), (-2.0, 0.18), (-2.3, 0.24), (-2.45, 0.30)],
        nose=[(0.20, 2.24), (0.30, 2.275), (0.45, 2.285), (0.70, 2.28), (0.90, 2.262), (1.0, 2.225), (1.06, 2.15)],
        nose_plan=[(0, 0), (0.4, 0.01), (0.6, 0.04), (0.72, 0.09), (0.80, 0.16), (0.86, 0.28)],
        tail=[(0.22, -2.35), (0.35, -2.40), (0.5, -2.41), (1.5, -2.41), (2.0, -2.40)],
        tail_plan=[(0, 0), (0.5, 0.008), (0.7, 0.03), (0.8, 0.07), (0.86, 0.15)],
        halfw=[(2.25, 0.80), (2.0, 0.84), (1.5, 0.8475), (-2.0, 0.8475), (-2.35, 0.83)],
        sections=[(0.0, [(0.0, -0.08), (0.2, -0.03), (0.35, -0.005), (0.5, 0.0), (1.0, 0.0), (1.2, -0.01)])],
        crown=0.02, r_sh=0.045, r_nose=0.06, r_tail=0.035, r_bot=0.05,
        roof=[(2.12, 1.0), (1.98, 1.08), (1.75, 1.35), (1.55, 1.62), (1.38, 1.85), (1.22, 1.95), (1.0, 1.975),
              (-2.0, 1.975), (-2.30, 1.955), (-2.38, 1.88), (-2.42, 1.3)],
        roof_smooth=0.02, gh_s=(-2.42, 2.12),
        gh_w=[(2.0, 0.76), (1.5, 0.80), (0.0, 0.825), (-2.3, 0.825)],
        belt=[(2.0, 1.07), (-2.3, 1.10)], tumble=4.0, roof_crown=0.03, r_rail=0.065, r_belt=0.012,
        arches=dict(gap=0.04, dz=0.02, r_lip=0.008, inner=0.05),
        extra_w=0.12,
    )
    st = []
    st.append(glass(spline([(0.0, 1.90, "c"), (0.66, 1.885), (0.73, 1.82), (0.75, 1.16), (0.70, 1.10),
                            (0.0, 1.10, "c")]), "front", dict(s_min=1.0, z_min=1.0), name="windshield"))
    W = dict(x_min=0.6, z_min=1.0)
    for shp in (poly([(1.93, 1.12), (1.43, 1.85), (0.98, 1.86), (0.98, 1.12)]),
                poly([(0.82, 1.13), (0.82, 1.86), (-0.22, 1.86), (-0.22, 1.13)])):
        st.append(trim(shp, "side", W, depth=0.002, name="win_frame"))
        st.append(glass(shp, "side", W, name="side_win"))
    st.append(glass(rect((0.0, 1.55), (0.64, 0.30)), "rear", dict(s_max=-2.0, z_min=1.1), name="backlight"))
    st.append(seam([(1.98, 1.08), (1.45, 1.90), (0.92, 1.90), (0.92, 0.32), (1.88, 0.32), (1.98, 0.6),
                    (1.98, 1.08)], "side", dict(x_min=0.6), smooth=False, name="door_f"))
    st.append(seam([(0.86, 1.90), (-0.30, 1.90), (-0.30, 0.32), (0.86, 0.32)], "side", dict(x_min=0.6),
                   smooth=False, name="slide"))
    st.append(seam([(-0.32, 1.05), (-2.30, 1.05)], "side", dict(x_min=0.7), name="rail"))
    for hs in (1.05, -0.18):
        st.append(trim(rect((hs, 0.98), (0.07, 0.014)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    st.append(seam([(0.70, 0.30), (0.70, 1.92)], "rear", dict(s_max=-2.2), name="hatch_r"))
    st.append(trim(poly([(SF + 0.4, 0.0), (SF + 0.4, 0.30), (SR - 0.4, 0.30), (SR - 0.4, 0.0)]), "side",
                   dict(x_min=0.6), depth=-0.003, name="sill"))
    WF = dict(s_min=1.9)
    st.append(Stamp(rect((0.0, 0.90), (0.40, 0.065)), "front", WF, op="recess", depth=0.03, mat="M_Grille",
                    wall_mat="M_Chrome", name="grille"))
    st.append(Stamp(spline([(0.45, 0.85, "c"), (0.78, 0.86), (0.82, 0.92), (0.80, 0.985), (0.45, 0.975, "c")]),
                    "front", WF, op="recess", depth=0.012, mat="M_HeadLight", wall_mat="M_Trim", name="headlight"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.56), (0.80, 0.58), (0.95, 0.58), (0.95, 0.0)]), "front",
                   dict(s_min=2.0), depth=-0.003, name="bumper"))
    st.append(Stamp(rect((0.72, 0.45), (0.06, 0.025)), "front", WF, op="raise", depth=0.004, mat="M_HeadLight",
                    name="turn"))
    WR = dict(s_max=-2.2)
    st.append(Stamp(rect((0.79, 0.95), (0.045, 0.24)), "rear", WR, op="recess", depth=0.01, mat="M_TailLight",
                    wall_mat="M_Trim", name="taillight"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.42), (0.95, 0.44), (0.95, 0.0)]), "rear", dict(s_max=-2.3),
                   depth=-0.003, name="bumper_r"))
    sp["stamps"] = st
    sp["solids"] = mirror_solids((1.80, 0.82, 1.15), 1.74, 1.22, 0.95, size=(0.20, 0.08, 0.16), yaw=4)
    return dict(
        id="traffic_van", traffic=True, body=sp, wheels=wheels, h=0.011, body_tris=13000,
        wheel_design=dict(rim_in=15, design=dict(kind="steel", holes=6, r_hub=0.06, cap_mat="M_Chrome"), dish=0.02,
                          seg=24, grooves=2, no_caliper=True, no_disc=True),
        slats=[dict(view="front", x=0.38, zs=[0.87, 0.90, 0.93], thick=0.009, depth=0.02, slot="M_Chrome")],
        empties={"Light_Head_L": (2.27, 0.63, 0.92), "Light_Head_R": (2.27, -0.63, 0.92),
                 "Light_Tail_L": (-2.41, 0.79, 0.95), "Light_Tail_R": (-2.41, -0.79, 0.95),
                 "Exhaust_L": (-2.3, 0.50, 0.25), "Exhaust_R": (-2.3, -0.50, 0.25)},
        plates={"front": [0.0, 0.42, 2.285], "rear": [0.0, 0.62, -2.41]},
        preview_color=[0.9, 0.9, 0.9],
    )
