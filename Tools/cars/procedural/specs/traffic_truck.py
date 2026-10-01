"""Traffic: Japanese 2-ton cab-over box truck (Elf/Dutro-class proportions), dual rear tyres.
~5.9 m L x 1.98 W x 3.02 H, wheelbase 3000.  Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
import numpy as np

from common import *  # noqa
from sdf import i_round, sd_box, smin, u_round

WB = 3.0
SF, SR = WB / 2, -WB / 2
S_FRONT, S_CAB_BACK, S_TAIL = 2.6, 0.95, -3.3


def sdf(P):
    s, x, z = P[:, 0], P[:, 1], P[:, 2]
    cab = sd_box(P, (0.5 * (S_FRONT + S_CAB_BACK), 0.0, 1.44), (0.5 * (S_FRONT - S_CAB_BACK), 0.94, 0.82), 0.10)
    sf = S_FRONT - np.maximum(0.0, z - 1.30) * 0.10
    cab = i_round(cab, (s - sf) / 1.005, 0.06)
    box = sd_box(P, (0.5 * (S_TAIL + 0.86), 0.0, 2.05), (0.5 * (0.86 - S_TAIL), 0.99, 0.97), 0.03)
    d = np.minimum(cab, box)
    frame = sd_box(P, (-0.35, 0.0, 0.88), (2.75, 0.45, 0.20), 0.02)
    d = np.minimum(d, frame)
    bumper = sd_box(P, (2.60, 0.0, 0.57), (0.08, 0.93, 0.15), 0.03)
    d = smin(d, bumper, 0.01)
    under = sd_box(P, (S_TAIL + 0.06, 0.0, 0.62), (0.05, 0.82, 0.07), 0.01)
    d = np.minimum(d, under)
    tank = sd_box(P, (-0.1, 0.70, 0.78), (0.45, 0.15, 0.14), 0.05)
    d = np.minimum(d, tank)
    guard = sd_box(P, (SR, 0.80, 1.04), (0.50, 0.19, 0.02), 0.01)
    d = np.minimum(d, guard)
    return d


def spec():
    wheels = dict(r_f=0.347, r_r=0.347, w_f=0.195, w_r=0.195, track_f=1.65, track_r=1.60)
    st = []
    st.append(glass(spline([(0.0, 2.08, "c"), (0.80, 2.07), (0.87, 2.0), (0.88, 1.40), (0.84, 1.33),
                            (0.0, 1.33, "c")]), "front", dict(s_min=1.8, z_min=1.2), name="windshield"))
    st.append(glass(poly([(2.52, 1.36), (2.47, 2.05), (1.75, 2.05), (1.75, 1.36)]), "side",
                    dict(x_min=0.7, z_min=1.2, s_min=1.0), name="side_win"))
    st.append(seam([(2.55, 1.30), (2.50, 2.12), (1.68, 2.12), (1.68, 0.70), (2.40, 0.70), (2.55, 1.0),
                    (2.55, 1.30)], "side", dict(x_min=0.7, s_min=1.0), smooth=False, name="door"))
    st.append(trim(rect((1.80, 1.25), (0.07, 0.014)), "side", dict(x_min=0.7, s_min=1.0), depth=0.006, name="handle"))
    WF = dict(s_min=2.3)
    st.append(Stamp(rect((0.0, 1.03), (0.52, 0.15)), "front", WF, op="recess", depth=0.03, mat="M_Grille",
                    wall_mat="M_Trim", name="grille"))
    st.append(Stamp(rect((0.70, 0.95), (0.16, 0.075)), "front", WF, op="recess", depth=0.012, mat="M_HeadLight",
                    wall_mat="M_Trim", name="headlight"))
    st.append(trim(rect((0.0, 1.24), (0.95, 0.05)), "front", WF, depth=-0.003, name="garnish"))
    st.append(Stamp(rect((0.70, 0.83), (0.07, 0.025)), "front", WF, op="raise", depth=0.004, mat="M_HeadLight",
                    name="turn"))
    # cargo box: panel joints, rear doors, latches
    for ss in (0.0, -0.9, -1.8, -2.7):
        st.append(seam([(ss, 1.10), (ss, 3.0)], "side", dict(x_min=0.9, s_max=0.8), width=0.008, name="panel"))
    WR = dict(s_max=-3.1)
    st.append(seam([(0.0, 1.12), (0.0, 2.98)], "rear", WR, width=0.01, name="door_mid"))
    st.append(seam([(0.94, 1.12), (0.94, 2.98)], "rear", WR, width=0.01, name="door_side"))
    for lx in (0.08, 0.80):
        st.append(Stamp(stroke([(lx, 1.15), (lx, 2.95)], 0.022), "rear", WR, op="raise", depth=0.012, mat="M_Chrome",
                        name="latch"))
    st.append(trim(rect((0.0, 3.0), (0.99, 0.03)), "rear", WR, depth=-0.003, name="top_rail"))
    st.append(Stamp(rect((0.62, 0.62), (0.12, 0.04)), "rear", dict(s_max=-3.2), op="raise", depth=0.006,
                    mat="M_TailLight", name="taillight"))
    body = dict(wb=WB, wheels=wheels, sdf=sdf, bounds=((S_TAIL - 0.08, -0.02, 0.35), (S_FRONT + 0.25, 1.2, 3.1)),
                arch_axles=("f",), arches=dict(gap=0.04, dz=0.02, inner=0.05, r_lip=0.008), stamps=st,
                solids=mirror_solids((2.45, 0.95, 1.55), 2.5, 1.65, 1.10, size=(0.22, 0.06, 0.26), yaw=4)
                + [Solid(lambda P: sd_box(P, np.array([-0.1, 0.70, 0.78]), np.array([0.45, 0.15, 0.14]), 0.05),
                         "union", 0.002, "M_Chrome", "tank", bound=((-0.7, 0.4, 0.5), (0.5, 1.0, 1.0))),
                   Solid(lambda P: sd_box(P, np.array([-0.35, 0.0, 0.88]), np.array([2.75, 0.45, 0.20]), 0.02),
                         "union", 0.002, "M_Underbody", "frame", bound=((-3.2, -0.6, 0.6), (2.5, 0.6, 1.15))),
                   Solid(lambda P: sd_box(P, np.array([SR, 0.80, 1.04]), np.array([0.50, 0.19, 0.02]), 0.01),
                         "union", 0.002, "M_Trim", "guard", bound=((SR - 0.6, 0.55, 0.95), (SR + 0.6, 1.05, 1.12))),
                   Solid(lambda P: sd_box(P, np.array([2.60, 0.0, 0.57]), np.array([0.08, 0.93, 0.15]), 0.03),
                         "union", 0.002, "M_Trim", "bumper", bound=((2.45, -1.0, 0.35), (2.75, 1.0, 0.8))),
                   Solid(lambda P: sd_box(P, np.array([S_TAIL + 0.06, 0.0, 0.62]), np.array([0.05, 0.82, 0.07]),
                                          0.01), "union", 0.002, "M_Trim", "underrun",
                         bound=((S_TAIL - 0.05, -0.9, 0.5), (S_TAIL + 0.2, 0.9, 0.75)))],
                under_z=0.0)
    return dict(
        id="traffic_truck", traffic=True, body=body, wheels=wheels, h=0.013, body_tris=12500,
        wheel_design=dict(rim_in=16, design=dict(kind="steel", holes=6, r_hub=0.07, cap_mat="M_Chrome"), dish=0.03,
                          seg=24, grooves=2, no_caliper=True, no_disc=True),
        wheel_design_rear=dict(rim_in=16, design=dict(kind="steel", holes=6, r_hub=0.07, cap_mat="M_Chrome"),
                               dish=0.05, seg=24, grooves=2, no_caliper=True, no_disc=True, dual=True),
        slats=[dict(view="front", x=0.50, zs=[0.94, 1.0, 1.06, 1.12], thick=0.012, depth=0.02, slot="M_Trim")],
        empties={"Light_Head_L": (2.62, 0.70, 0.95), "Light_Head_R": (2.62, -0.70, 0.95),
                 "Light_Tail_L": (-3.30, 0.62, 0.62), "Light_Tail_R": (-3.30, -0.62, 0.62),
                 "Exhaust_L": (-0.8, 0.55, 0.62), "Exhaust_R": (-0.8, -0.55, 0.62)},
        plates={"front": [0.0, 0.57, 2.68], "rear": [0.0, 0.62, -3.31]},
        preview_color=[0.92, 0.92, 0.9],
    )
