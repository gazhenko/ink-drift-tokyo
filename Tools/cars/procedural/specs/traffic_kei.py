"""Traffic: Japanese kei pickup truck (cab-over, drop-side bed). 3395 L x 1475 W x 1765 H, wheelbase 1905.
Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
import numpy as np

from common import *  # noqa
from sdf import i_round, sd_box, smin, u_round

WB = 1.905
SF, SR = WB / 2, -WB / 2
S_FRONT, S_CAB_BACK, S_TAIL = 1.50, 0.36, -1.895
HW = 0.7375


def sdf(P):
    s, x, z = P[:, 0], P[:, 1], P[:, 2]
    cab = sd_box(P, (0.5 * (S_FRONT + S_CAB_BACK), 0.0, 1.0325), (0.5 * (S_FRONT - S_CAB_BACK), HW, 0.7325), 0.075)
    # sloped windshield / nose
    sf = S_FRONT - np.maximum(0.0, z - 1.02) * 0.30
    d_front = (s - sf) / np.sqrt(1 + 0.09 * (z > 1.02))
    cab = i_round(cab, d_front, 0.05)
    bed_o = sd_box(P, (0.5 * (S_TAIL + 0.33), 0.0, 0.77), (0.5 * (0.33 - S_TAIL), HW, 0.165), 0.012)
    bed_i = sd_box(P, (0.5 * (S_TAIL + 0.33), 0.0, 1.0), (0.5 * (0.33 - S_TAIL) - 0.035, HW - 0.035, 0.36), 0.006)
    bed = np.maximum(bed_o, -bed_i)
    d = u_round(cab, bed, 0.01)
    chassis = sd_box(P, (-0.45, 0.0, 0.48), (1.15, 0.42, 0.12), 0.02)
    d = np.minimum(d, chassis)
    bumper = sd_box(P, (1.49, 0.0, 0.32), (0.05, 0.725, 0.085), 0.025)
    d = smin(d, bumper, 0.01)
    rbump = sd_box(P, (S_TAIL + 0.05, 0.0, 0.52), (0.04, 0.70, 0.07), 0.015)
    d = np.minimum(d, rbump)
    # headboard guard frame behind the cab
    fr_o = sd_box(P, (0.335, 0.0, 1.22), (0.015, 0.71, 0.30), 0.008)
    fr_i = sd_box(P, (0.335, 0.0, 1.22), (0.05, 0.64, 0.24), 0.004)
    d = np.minimum(d, np.maximum(fr_o, -fr_i))
    for bx in (0.0, 0.21, 0.42):
        d = np.minimum(d, sd_box(P, (0.335, bx, 1.22), (0.008, 0.008, 0.26), 0.003))
    return d


def spec():
    wheels = dict(r_f=0.268, r_r=0.268, w_f=0.145, w_r=0.145, track_f=1.29, track_r=1.30)
    st = []
    st.append(glass(spline([(0.0, 1.645, "c"), (0.56, 1.645), (0.64, 1.60), (0.66, 1.12), (0.62, 1.07),
                            (0.0, 1.07, "c")]), "front", dict(s_min=1.2, z_min=1.0), name="windshield"))
    st.append(glass(poly([(1.38, 1.075), (1.215, 1.62), (0.52, 1.62), (0.48, 1.58), (0.48, 1.075)]), "side",
                    dict(x_min=0.6, z_min=1.0), name="side_win"))
    st.append(glass(rect((0.0, 1.32), (0.52, 0.17)), "rear", dict(s_max=0.45, z_min=1.0), name="rear_win"))
    st.append(seam([(1.43, 0.95), (1.25, 1.66), (0.47, 1.66), (0.46, 0.40), (1.30, 0.40), (1.40, 0.62),
                    (1.43, 0.95)], "side", dict(x_min=0.6), closed=False, smooth=False, name="door"))
    st.append(trim(rect((0.62, 1.0), (0.06, 0.012)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    st.append(Stamp(rect((0.575, 0.715), (0.115, 0.07)), "front", dict(s_min=1.3), op="recess", depth=0.012,
                    mat="M_HeadLight", wall_mat="M_Trim", name="headlight"))
    st.append(Stamp(rect((0.0, 0.715), (0.40, 0.05)), "front", dict(s_min=1.3), op="recess", depth=0.02,
                    mat="M_Grille", name="grille"))
    st.append(Stamp(rect((0.66, 0.60), (0.04, 0.02)), "front", dict(s_min=1.3), op="raise", depth=0.004,
                    mat="M_TailLight", name="turn"))
    st.append(trim(rect((0.0, 0.88), (0.74, 0.02)), "front", dict(s_min=1.3), depth=0.0, name="belt_line"))
    st.append(Stamp(rect((0.60, 0.53), (0.075, 0.035)), "rear", dict(s_max=-1.8), op="raise", depth=0.006,
                    mat="M_TailLight", name="taillight"))
    for gs in (-0.20, -1.0):
        st.append(seam([(gs, 0.62), (gs, 0.92)], "side", dict(x_min=0.7), name="gate_hinge"))
    body = dict(wb=WB, wheels=wheels, sdf=sdf, bounds=((S_TAIL - 0.05, -0.02, 0.15), (S_FRONT + 0.25, HW + 0.2, 1.8)),
                arch_axles=("f",), arches=dict(gap=0.035, dz=0.02, inner=0.04, r_lip=0.006), stamps=st,
                solids=mirror_solids((1.30, 0.70, 1.12), 1.33, 1.20, 0.82, size=(0.16, 0.06, 0.12), yaw=4),
                under_z=0.0)
    return dict(
        id="traffic_kei", traffic=True, body=body, wheels=wheels, h=0.010, body_tris=12000,
        wheel_design=dict(rim_in=12, design=dict(kind="steel", holes=6, r_hub=0.05, cap_mat="M_Chrome"), dish=0.02,
                          seg=24, grooves=2, no_caliper=True, no_disc=True),
        empties={"Light_Head_L": (1.52, 0.575, 0.715), "Light_Head_R": (1.52, -0.575, 0.715),
                 "Light_Tail_L": (-1.92, 0.60, 0.53), "Light_Tail_R": (-1.92, -0.60, 0.53),
                 "Exhaust_L": (-1.55, 0.30, 0.33), "Exhaust_R": (-1.55, -0.30, 0.33)},
        plates={"front": [0.0, 0.32, 1.54], "rear": [0.0, 0.52, -1.90]},
        preview_color=[0.92, 0.92, 0.9],
    )
