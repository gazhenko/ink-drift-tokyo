"""ZENKAI Z -- 2020s Japanese twin-turbo V6 fastback coupe (Nissan Z RZ34 proportions).
4380 L x 1845 W x 1315 H, wheelbase 2550.  Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
import math

from common import *  # noqa

WB = 2.55
SF, SR = WB / 2, -WB / 2


def arc(cx, cz, r, a0, a1, n=9):
    return [(cx + r * math.cos(math.radians(a)), cz + r * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / (n - 1) for i in range(n)]]


def spec():
    wheels = dict(r_f=0.341, r_r=0.341, w_f=0.255, w_r=0.275, track_f=1.565, track_r=1.585)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.30, 0.60), (2.12, 0.665), (1.97, 0.728), (1.75, 0.765), (1.275, 0.825), (0.9, 0.878), (0.6, 0.918),
             (0.42, 0.94), (0.2, 0.952), (-0.5, 0.962), (-1.2, 0.972), (-1.6, 0.972), (-1.85, 0.968), (-2.0, 0.975),
             (-2.09, 0.988), (-2.25, 0.95)],
        top_smooth=0.035,
        bot=[(2.25, 0.21), (2.05, 0.16), (1.8, 0.14), (0, 0.13), (-1.8, 0.15), (-2.05, 0.22), (-2.25, 0.27)],
        nose=[(0.12, 2.09), (0.20, 2.14), (0.30, 2.165), (0.42, 2.172), (0.52, 2.165), (0.60, 2.14), (0.67, 2.08),
              (0.73, 1.99), (0.78, 1.88)],
        nose_plan=[(0, 0), (0.3, 0.01), (0.5, 0.04), (0.62, 0.08), (0.72, 0.14), (0.80, 0.23), (0.87, 0.37),
                   (0.95, 0.66)],
        tail=[(0.14, -2.08), (0.24, -2.16), (0.36, -2.198), (0.50, -2.208), (0.66, -2.205), (0.78, -2.19),
              (0.86, -2.178), (0.95, -2.162), (1.0, -2.14)],
        tail_smooth=0.015,
        tail_plan=[(0, 0), (0.3, 0.008), (0.5, 0.025), (0.64, 0.05), (0.72, 0.11), (0.80, 0.21), (0.87, 0.37),
                   (0.94, 0.62)],
        halfw=[(2.25, 0.79), (2.05, 0.842), (1.75, 0.865), (1.3, 0.872), (0.8, 0.862), (0.3, 0.855), (-0.3, 0.862),
               (-0.8, 0.885), (-1.275, 0.898), (-1.7, 0.886), (-2.0, 0.858), (-2.2, 0.80)],
        sections=[(1.3, [(0.0, -0.10), (0.15, -0.06), (0.30, -0.018), (0.45, 0.0), (0.60, -0.004), (0.70, -0.018),
                         (0.80, -0.05), (0.92, -0.10)]),
                  (0.0, [(0.0, -0.11), (0.18, -0.06), (0.32, -0.022), (0.50, -0.004), (0.66, 0.0), (0.80, -0.01),
                         (0.92, -0.035), (1.02, -0.08)]),
                  (-1.3, [(0.0, -0.12), (0.15, -0.075), (0.30, -0.028), (0.50, 0.0), (0.66, 0.0), (0.78, -0.02),
                          (0.88, -0.055), (0.97, -0.10), (1.06, -0.16)])],
        crown=[(2.2, 0.035), (1.3, 0.04), (0.5, 0.03), (-1.3, 0.04), (-2.2, 0.03)],
        peaks=dict(amp=[(2.25, 0.0), (2.0, 0.02), (1.7, 0.03), (1.1, 0.03), (0.6, 0.012), (0.4, 0.0),
                        (-0.9, 0.0), (-1.3, 0.018), (-1.9, 0.012), (-2.2, 0.0)],
                   x=[(2.0, 0.66), (1.3, 0.72), (0.6, 0.74), (-1.3, 0.72)], w=0.13),
        flares=[dict(s=SF + 0.02, z=0.62, amp=0.022, ss=0.38, sz=0.16, p=1.4),
                dict(s=SR - 0.05, z=0.66, amp=0.026, ss=0.50, sz=0.20, p=1.3)],
        r_sh=[(2.2, 0.05), (1.3, 0.045), (0.5, 0.03), (-0.6, 0.035), (-1.3, 0.06), (-2.2, 0.045)],
        r_nose=0.05, r_tail=0.04, r_bot=0.05,
        roof=[(0.62, 0.85), (0.42, 0.945), (0.25, 1.04), (0.05, 1.16), (-0.08, 1.232), (-0.25, 1.285),
              (-0.45, 1.288), (-0.75, 1.24), (-1.05, 1.175), (-1.35, 1.105), (-1.62, 1.042), (-1.85, 0.995),
              (-2.0, 0.965), (-2.1, 0.94)],
        gh_s=(-2.08, 0.64),
        gh_w=[(0.64, 0.62), (0.42, 0.67), (0.0, 0.725), (-0.5, 0.74), (-1.0, 0.71), (-1.4, 0.635), (-1.8, 0.52),
              (-2.05, 0.43)],
        belt=[(0.4, 0.95), (-0.5, 0.962), (-1.2, 0.978), (-1.8, 0.975)],
        tumble=[(0.4, 28), (-0.4, 24), (-1.2, 32), (-1.8, 42)],
        roof_crown=[(0.4, 0.05), (-0.4, 0.06), (-1.4, 0.06)],
        r_rail=[(0.4, 0.05), (-0.4, 0.065), (-1.4, 0.09)],
        r_belt=0.012,
        arches=dict(gap=0.042, dz=0.018, r_lip=0.008, inner=0.05, lip=dict(amp=0.006, off=0.03, w=0.022)),
        extra_w=0.14,
        top_bumps=[bump(spline([(0.50, 0.0, "c"), (0.50, 0.22), (1.0, 0.26), (1.55, 0.22), (1.80, 0.12),
                                (1.84, 0.0, "c")]), 0.012, 0.14)],
        side_bumps=[side_bump(spline([(0.85, 0.22), (0.80, 0.33), (0.20, 0.36), (-0.60, 0.40), (-0.88, 0.42),
                                      (-0.92, 0.22)]), -0.010, 0.025)],
    )
    st = []
    WG = dict(x_min=0.58, z_min=0.92)
    dlo = [(0.37, 0.965, "c"), (0.12, 1.075), (-0.05, 1.17), (-0.28, 1.215), (-0.6, 1.207), (-0.95, 1.152),
           (-1.25, 1.075), (-1.44, 1.022, "c"), (-1.2, 1.0), (-0.5, 0.985), (0.2, 0.972)]
    st.append(trim(spline(dlo, grow=0.012), "side", WG, depth=0.002, name="dlo_frame"))
    st.append(glass(spline(dlo), "side", WG, name="dlo"))
    st.append(trim(stroke([(-0.96, 0.99), (-1.0, 1.18)], 0.026), "side", WG, name="b_bar"))
    st.append(Stamp(stroke([(0.02, 1.215), (-0.12, 1.245), (-0.30, 1.258), (-0.6, 1.25), (-0.95, 1.196),
                            (-1.25, 1.118), (-1.50, 1.054), (-1.75, 1.0), (-1.92, 0.975)], 0.022), "side",
                    dict(x_min=0.5, z_min=0.95), op="raise", depth=0.002, mat="M_Chrome", name="roof_chrome"))
    st.append(glass(poly([(0.43, 0.0), (0.43, 0.575), (0.25, 0.57), (-0.02, 0.515), (-0.04, 0.0)]), "top",
                    dict(z_min=0.96, x_max=0.585), name="windshield"))
    st.append(glass(poly([(-0.70, 0.0), (-0.70, 0.47), (-1.0, 0.51), (-1.45, 0.45), (-1.62, 0.30), (-1.65, 0.0)]),
                    "top", dict(z_min=1.0, x_max=0.585), name="backlight"))
    st.append(trim(rect((0.455, 0.0), (0.03, 0.64)), "top", dict(z_min=0.88, x_max=0.64), depth=0.006, name="cowl"))
    # seams
    st.append(seam([(0.49, 0.0, "c"), (0.49, 0.63, "c"), (1.0, 0.665), (1.6, 0.645), (1.92, 0.53), (1.975, 0.3),
                    (1.985, 0.0)], "top", dict(z_min=0.6), name="hood"))
    st.append(seam([(0.36, 0.95, "c"), (0.40, 0.70), (0.38, 0.42), (0.34, 0.27, "c"), (-0.95, 0.29, "c"),
                    (-0.99, 0.60), (-0.955, 0.982, "c")], "side", dict(x_min=0.6), name="door"))
    st.append(seam([(-0.66, 0.0, "c"), (-0.66, 0.53, "c"), (-1.4, 0.55), (-1.9, 0.53), (-2.04, 0.45)], "top",
                   dict(z_min=0.9), name="hatch"))
    st.append(seam([(-1.12, 0.86), (-1.04, 0.86), (-1.04, 0.80), (-1.12, 0.80)], "side", dict(x_min=0.6),
                   closed=True, smooth=False, name="fuel"))
    st.append(trim(rect((-0.72, 0.86), (0.07, 0.012)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    st.append(trim(poly([(SF - 0.42, 0.0), (SF - 0.42, 0.235), (SR + 0.44, 0.25), (SR + 0.44, 0.0)]), "side",
                   dict(x_min=0.6), depth=-0.004, name="sill"))
    # front
    WF = dict(s_min=1.75)
    st.append(Stamp(spline([(0.0, 0.505, "c"), (0.40, 0.505), (0.455, 0.49), (0.475, 0.44), (0.475, 0.27),
                            (0.45, 0.215), (0.40, 0.20), (0.0, 0.20, "c")]), "front", WF, op="recess", depth=0.06,
                    mat="M_Grille", wall_mat="M_Trim", name="grille"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.17), (0.55, 0.18), (0.75, 0.22), (0.95, 0.22), (0.95, 0.0)]), "front",
                   dict(s_min=1.9), depth=-0.003, name="chin"))
    hl = spline([(0.47, 0.605, "c"), (0.58, 0.66), (0.72, 0.70), (0.83, 0.712), (0.875, 0.69), (0.875, 0.635),
                 (0.82, 0.598), (0.70, 0.578), (0.56, 0.578)])
    WH_ = dict(s_min=1.62)
    st.append(Stamp(hl, "front", WH_, op="recess", depth=0.014, mat="M_HeadLight", wall_mat="M_Trim",
                    name="headlight"))
    st.append(Stamp(spline([(0.50, 0.60, "c"), (0.62, 0.592), (0.80, 0.605), (0.86, 0.63), (0.80, 0.625),
                            (0.62, 0.612)]), "front", WH_, op="paint", mat="M_Trim", name="hl_housing"))
    for cx, cz in ((0.615, 0.632), (0.745, 0.652)):
        st.append(Stamp(stroke(arc(cx, cz, 0.04, 200, 340), 0.009), "front", WH_, op="raise", depth=0.004,
                        mat="M_Chrome", name="halfmoon"))
        st.append(Stamp(ellipse((cx, cz + 0.005), (0.022, 0.018)), "front", WH_, op="raise", depth=0.005,
                        mat="M_Chrome", name="projector"))
    # rear: black band with paired light bars
    WR = dict(s_max=-1.85)
    st.append(Stamp(spline([(0.0, 0.928, "c"), (0.78, 0.928), (0.88, 0.915), (0.905, 0.875), (0.88, 0.835),
                            (0.78, 0.83), (0.0, 0.83, "c")]), "rear", WR, op="recess", depth=0.008, mat="M_Trim",
                    name="tl_band"))
    for zc in (0.898, 0.860):
        st.append(Stamp(spline([(0.52, zc + 0.012, "c"), (0.84, zc + 0.012), (0.875, zc), (0.84, zc - 0.012),
                                (0.52, zc - 0.012, "c")]), "rear", WR, op="raise", depth=0.004, mat="M_TailLight",
                        name="tl_bar"))
    st.append(seam([(0.0, 0.81), (0.5, 0.812)], "rear", WR, name="hatch_rear"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.34), (0.42, 0.34), (0.66, 0.37), (0.80, 0.36), (0.95, 0.32),
                         (0.95, 0.0)]), "rear", dict(s_max=-1.9), depth=-0.004, name="diffuser"))
    for fx in (0.10, 0.22, 0.34):
        st.append(Stamp(stroke([(fx, 0.13), (fx, 0.30)], 0.01), "rear", dict(s_max=-1.9), op="raise", depth=0.03,
                        mat="M_Trim", name="fin"))
    st.append(Stamp(ellipse((0.60, 0.275), (0.07, 0.06)), "rear", dict(s_max=-1.95), op="recess", depth=0.06,
                    mat="M_Underbody", name="exh_hole"))
    st.append(Stamp(rect((0.76, 0.44), (0.05, 0.009)), "rear", dict(s_max=-1.95), op="raise", depth=0.003,
                    mat="M_TailLight", name="reflector"))
    sp["stamps"] = st
    so = []
    so += mirror_solids((0.30, 0.83, 1.0), 0.24, 1.05, 0.95, size=(0.20, 0.09, 0.11), yaw=6)
    sp["solids"] = so
    return dict(
        id="zenkai", body=sp, wheels=wheels,
        wheel_design=dict(rim_in=19, design=dict(kind="te", n=6), dish=0.045, stretch=0.006),
        body_tris=82000,
        exhaust_tips=[dict(c=(None, 0.60, 0.275), r=0.052, len=0.14, out=0.03)],
        slats=[dict(view="front", x=0.44, zs=[0.25, 0.30, 0.35, 0.40, 0.45], thick=0.012, depth=0.04,
                    hole=(0.18, 0.23, 0.43))],
        empties={"Light_Head_L": (2.06, 0.68, 0.645), "Light_Head_R": (2.06, -0.68, 0.645),
                 "Light_Tail_L": (-2.19, 0.70, 0.88), "Light_Tail_R": (-2.19, -0.70, 0.88),
                 "Exhaust_L": (-2.25, 0.60, 0.275), "Exhaust_R": (-2.25, -0.60, 0.275)},
        plates={"front": [0.0, 0.33, 2.17], "rear": [0.0, 0.56, -2.205]},
        decals=[{"img": "livery_name_zenkai", "where": "side", "sides": "both", "z": 0.0, "y": 0.56, "w": 0.85}, {"img": "livery_sponsor_neko_brakes", "where": "side", "sides": "both", "z": 1.05, "y": 0.64, "w": 0.3}, {"img": "livery_zenkai_kanji", "where": "side", "sides": "both", "z": -1.08, "y": 0.66, "w": 0.4}],
        half_width=0.9225,
        kit={"wing": {"span": 1.62, "chord": 0.28, "height": 0.24, "mount_x": 0.36, "from_rear": 0.10},
             "splitter": {"protrude": 0.05, "depth": 0.30}},
    )
