"""TSUBAME RS -- 2010s/20s Japanese featherweight roadster (Mazda MX-5 ND proportions), soft top up.
3915 L x 1735 W x 1235 H, wheelbase 2310.  Model coords: s fwd from axle midpoint, x lateral (+ = left), z up."""
from common import *  # noqa

WB = 2.31
SF, SR = WB / 2, -WB / 2


def spec():
    wheels = dict(r_f=0.308, r_r=0.308, w_f=0.215, w_r=0.225, track_f=1.505, track_r=1.515)
    sp = dict(
        wb=WB, wheels=wheels,
        top=[(2.0, 0.52), (1.88, 0.565), (1.78, 0.605), (1.60, 0.645), (1.35, 0.69), (1.155, 0.715), (0.9, 0.765),
             (0.65, 0.815), (0.52, 0.838), (0.3, 0.85), (-0.5, 0.86), (-1.0, 0.875), (-1.4, 0.88), (-1.7, 0.885),
             (-1.88, 0.895), (-1.96, 0.905), (-2.05, 0.88)],
        top_smooth=0.035,
        bot=[(1.95, 0.20), (1.8, 0.15), (1.5, 0.13), (0, 0.12), (-1.5, 0.13), (-1.8, 0.20), (-2.0, 0.25)],
        nose=[(0.12, 1.84), (0.20, 1.895), (0.30, 1.918), (0.40, 1.92), (0.48, 1.905), (0.55, 1.87), (0.60, 1.82),
              (0.64, 1.75), (0.68, 1.65)],
        nose_plan=[(0, 0), (0.2, 0.012), (0.35, 0.04), (0.48, 0.085), (0.58, 0.14), (0.67, 0.21), (0.75, 0.31),
                   (0.82, 0.45), (0.90, 0.70)],
        tail=[(0.14, -1.86), (0.24, -1.94), (0.36, -1.98), (0.50, -1.995), (0.64, -1.99), (0.76, -1.975),
              (0.86, -1.958), (0.92, -1.952)],
        tail_smooth=0.015,
        tail_plan=[(0, 0), (0.3, 0.015), (0.48, 0.05), (0.60, 0.10), (0.70, 0.17), (0.77, 0.26), (0.83, 0.38),
                   (0.90, 0.60)],
        halfw=[(1.95, 0.72), (1.8, 0.79), (1.55, 0.825), (1.25, 0.836), (0.9, 0.826), (0.4, 0.815), (-0.2, 0.818),
               (-0.7, 0.835), (-1.15, 0.845), (-1.5, 0.84), (-1.8, 0.81), (-2.0, 0.75)],
        sections=[(1.15, [(0.0, -0.10), (0.15, -0.055), (0.30, -0.016), (0.42, 0.0), (0.54, -0.004),
                          (0.64, -0.02), (0.72, -0.05), (0.82, -0.10)]),
                  (0.0, [(0.0, -0.10), (0.16, -0.055), (0.30, -0.02), (0.45, -0.004), (0.58, 0.0), (0.70, -0.012),
                         (0.80, -0.035), (0.90, -0.08)]),
                  (-1.15, [(0.0, -0.10), (0.15, -0.055), (0.30, -0.018), (0.46, 0.0), (0.60, -0.004),
                           (0.72, -0.02), (0.82, -0.05), (0.93, -0.10)])],
        crown=[(2.0, 0.025), (1.15, 0.03), (0.5, 0.02), (-1.15, 0.03), (-2.0, 0.025)],
        peaks=dict(amp=[(2.0, 0.0), (1.82, 0.04), (1.55, 0.07), (1.05, 0.072), (0.7, 0.04), (0.5, 0.0),
                        (-0.8, 0.0), (-1.15, 0.035), (-1.6, 0.03), (-1.95, 0.0)],
                   x=[(1.8, 0.60), (1.3, 0.66), (0.8, 0.68), (-1.15, 0.67)], w=0.12),
        flares=[dict(s=SF + 0.03, z=0.58, amp=0.03, ss=0.34, sz=0.15, p=1.5),
                dict(s=SR - 0.04, z=0.60, amp=0.028, ss=0.42, sz=0.16, p=1.4)],
        r_sh=[(2.0, 0.05), (1.15, 0.05), (0.5, 0.03), (-0.4, 0.03), (-1.15, 0.06), (-2.0, 0.05)],
        r_nose=0.05, r_tail=0.045, r_bot=0.05,
        roof=[(0.72, 0.74), (0.55, 0.835), (0.40, 0.92), (0.22, 1.03), (0.05, 1.135), (-0.05, 1.19), (-0.22, 1.215),
              (-0.50, 1.222), (-0.72, 1.205), (-0.90, 1.155), (-1.05, 1.06), (-1.15, 0.97), (-1.25, 0.88)],
        roof_smooth=0.025,
        gh_s=(-1.27, 0.74),
        gh_w=[(0.74, 0.60), (0.55, 0.64), (0.2, 0.69), (-0.3, 0.70), (-0.8, 0.68), (-1.1, 0.64), (-1.25, 0.60)],
        belt=[(0.55, 0.84), (-0.4, 0.855), (-1.1, 0.875)],
        tumble=[(0.5, 30), (0.0, 22), (-0.6, 18), (-1.1, 20)],
        roof_crown=[(0.4, 0.04), (-0.5, 0.05), (-1.1, 0.05)],
        r_rail=[(0.4, 0.045), (-0.3, 0.06), (-1.0, 0.06)],
        r_belt=0.01,
        arches=dict(gap=0.04, dz=0.018, r_lip=0.008, inner=0.05, lip=dict(amp=0.006, off=0.03, w=0.022)),
        extra_w=0.14,
        side_bumps=[side_bump(spline([(0.78, 0.20), (0.76, 0.52), (0.40, 0.50), (-0.20, 0.45), (-0.60, 0.44),
                                      (-0.78, 0.48), (-0.82, 0.20)]), -0.016, 0.025)],
    )
    st = []
    WG = dict(x_min=0.55, z_min=0.82)
    # soft top: everything on the greenhouse behind the header is black fabric
    st.append(Stamp(poly([(0.0, 0.0), (0.0, 0.9), (-1.27, 0.9), (-1.27, 0.0)]), "top", dict(z_min=0.89),
                    op="paint", mat="M_Trim", name="softtop"))
    st.append(seam([(-0.02, 0.0), (-0.02, 0.62)], "top", dict(z_min=1.1), width=0.008, depth=0.006, name="top_front"))
    dlo = [(0.50, 0.85, "c"), (0.24, 0.97), (0.0, 1.10), (-0.10, 1.13), (-0.42, 1.14), (-0.62, 1.05, "c"),
           (-0.60, 0.88, "c"), (-0.3, 0.866), (0.2, 0.855)]
    st.append(trim(spline(dlo, grow=0.012), "side", WG, depth=0.002, name="dlo_frame"))
    st.append(glass(spline(dlo), "side", WG, name="dlo"))
    st.append(glass(poly([(0.53, 0.0), (0.53, 0.56), (0.30, 0.565), (0.02, 0.53), (0.01, 0.0)]), "top",
                    dict(z_min=0.85, x_max=0.58), name="windshield"))
    st.append(glass(poly([(-0.86, 0.0), (-0.86, 0.36), (-0.98, 0.40), (-1.10, 0.36), (-1.12, 0.0)]), "top",
                    dict(z_min=0.95, x_max=0.5), name="backlight"))
    st.append(trim(rect((0.56, 0.0), (0.028, 0.60)), "top", dict(z_min=0.78, x_max=0.62), depth=0.006, name="cowl"))
    # seams
    st.append(seam([(0.60, 0.0, "c"), (0.60, 0.58, "c"), (1.1, 0.60), (1.55, 0.57), (1.75, 0.45), (1.80, 0.25),
                    (1.81, 0.0)], "top", dict(z_min=0.5), name="hood"))
    st.append(seam([(0.50, 0.83, "c"), (0.54, 0.62), (0.52, 0.38), (0.48, 0.25, "c"), (-0.62, 0.27, "c"),
                    (-0.66, 0.55), (-0.62, 0.865, "c")], "side", dict(x_min=0.6), name="door"))
    st.append(seam([(-1.25, 0.0, "c"), (-1.25, 0.52, "c"), (-1.70, 0.54), (-1.93, 0.48)], "top", dict(z_min=0.8),
                   name="trunk"))
    st.append(trim(rect((-0.45, 0.77), (0.06, 0.012)), "side", dict(x_min=0.6), depth=0.006, name="handle"))
    st.append(trim(poly([(SF - 0.40, 0.0), (SF - 0.40, 0.22), (SR + 0.42, 0.23), (SR + 0.42, 0.0)]), "side",
                   dict(x_min=0.6), depth=-0.004, name="sill"))
    # front
    WF = dict(s_min=1.6)
    st.append(Stamp(spline([(0.0, 0.43, "c"), (0.30, 0.425), (0.50, 0.39), (0.56, 0.32), (0.52, 0.22), (0.42, 0.175),
                            (0.0, 0.17, "c")]), "front", WF, op="recess", depth=0.06, mat="M_Grille",
                    wall_mat="M_Trim", name="grille"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.15), (0.55, 0.16), (0.75, 0.2), (0.95, 0.2), (0.95, 0.0)]), "front",
                   dict(s_min=1.75), depth=-0.003, name="chin"))
    hl = spline([(0.46, 0.555, "c"), (0.60, 0.592), (0.72, 0.628), (0.80, 0.648, "c"), (0.81, 0.615),
                 (0.74, 0.585), (0.60, 0.553), (0.50, 0.545)])
    WH_ = dict(s_min=1.45)
    st.append(Stamp(hl, "front", WH_, op="recess", depth=0.014, mat="M_HeadLight", wall_mat="M_Trim",
                    name="headlight"))
    st.append(Stamp(spline([(0.50, 0.55, "c"), (0.62, 0.56), (0.74, 0.588), (0.79, 0.61), (0.70, 0.596),
                            (0.58, 0.572)]), "front", WH_, op="paint", mat="M_Trim", name="hl_housing"))
    st.append(Stamp(stroke([(0.50, 0.566), (0.62, 0.592), (0.74, 0.625), (0.795, 0.638)], 0.008), "front", WH_,
                    op="raise", depth=0.003, mat="M_Chrome", name="drl"))
    st.append(Stamp(ellipse((0.66, 0.590), (0.024, 0.02)), "front", WH_, op="raise", depth=0.005, mat="M_Chrome",
                    name="projector"))
    # rear: round-ish lamps
    WR = dict(s_max=-1.7)
    for (cx, cz, rx, rz) in ((0.66, 0.775, 0.075, 0.048),):
        st.append(Stamp(spline([(0.50, 0.78), (0.58, 0.815), (0.72, 0.822), (0.80, 0.80), (0.82, 0.765),
                                (0.76, 0.738), (0.60, 0.738), (0.52, 0.755)]), "rear", WR, op="recess",
                        depth=0.010, mat="M_TailLight", wall_mat="M_Trim", name="taillight"))
        st.append(Stamp(stroke([(cx + 0.032 * __import__("math").cos(a / 12 * 6.2832),
                                 cz + 0.032 * __import__("math").sin(a / 12 * 6.2832)) for a in range(13)], 0.008),
                        "rear", WR, op="paint", mat="M_Trim", name="ring"))
    st.append(seam([(0.0, 0.70), (0.45, 0.705)], "rear", WR, name="trunk_rear"))
    st.append(trim(poly([(0.0, 0.0), (0.0, 0.33), (0.40, 0.33), (0.62, 0.36), (0.78, 0.36), (0.95, 0.33),
                         (0.95, 0.0)]), "rear", dict(s_max=-1.7), depth=-0.004, name="diffuser"))
    st.append(Stamp(ellipse((0.40, 0.255), (0.06, 0.05)), "rear", dict(s_max=-1.8), op="recess", depth=0.05,
                    mat="M_Underbody", name="exh_hole"))
    st.append(Stamp(rect((0.0, 0.25), (0.05, 0.015)), "rear", dict(s_max=-1.8), op="raise", depth=0.004,
                    mat="M_TailLight", name="fog"))
    sp["stamps"] = st
    so = []
    so += mirror_solids((0.42, 0.78, 0.90), 0.34, 0.95, 0.89, size=(0.18, 0.085, 0.10), yaw=6)
    sp["solids"] = so
    return dict(
        id="tsubame", body=sp, wheels=wheels,
        wheel_design=dict(rim_in=17, design=dict(kind="straight", n=7, w_rim=0.011, w_hub=0.017, twist=0.0),
                          dish=0.045, stretch=0.006),
        body_tris=76000,
        exhaust_tips=[dict(c=(None, 0.40, 0.255), r=0.045, len=0.13, out=0.03)],
        slats=[dict(view="front", x=0.42, zs=[0.22, 0.27, 0.32, 0.37], thick=0.011, depth=0.035,
                    hole=(0.18, 0.18, 0.40))],
        empties={"Light_Head_L": (1.84, 0.66, 0.59), "Light_Head_R": (1.84, -0.66, 0.59),
                 "Light_Tail_L": (-1.97, 0.66, 0.78), "Light_Tail_R": (-1.97, -0.66, 0.78),
                 "Exhaust_L": (-2.05, 0.40, 0.255), "Exhaust_R": (-2.05, -0.40, 0.255)},
        plates={"front": [0.0, 0.29, 1.92], "rear": [0.0, 0.50, -1.995]},
        decals=[{"img": "livery_name_tsubame", "where": "side", "sides": "both", "z": -0.05, "y": 0.53, "w": 0.85}, {"img": "livery_koi", "where": "side", "sides": "both", "z": -0.95, "y": 0.58, "w": 0.32}, {"img": "livery_sumi_racing", "where": "side", "sides": "both", "z": 0.95, "y": 0.58, "w": 0.28}],
        half_width=0.8675,
        kit={"wing": {"span": 1.45, "chord": 0.25, "height": 0.30, "mount_x": 0.34, "from_rear": 0.08},
             "splitter": {"protrude": 0.045, "depth": 0.28}},
    )
