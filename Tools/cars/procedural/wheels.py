"""Procedural wheels: tyre (sidewall bulge, shoulder, circumferential grooves + tread notches), multi-spoke rim
(several designs), polished lip, lug nuts, centre cap, brake disc (+ hat) and a separate caliper.

Local frame (Blender units, meters): spin axis = +X (outer face at +X), wheel centre at the origin.
Returns MeshParts: list of (V (n,3), faces (list of tuples), slot).
"""
import math

import numpy as np


class Parts:
    def __init__(self):
        self.V = []
        self.F = []
        self.S = []
        self.n = 0

    def add(self, V, F, slot, closed=False):
        V = np.asarray(V, float)
        if closed:
            vol = 0.0
            for f in F:
                a = V[f[0]]
                for k in range(1, len(f) - 1):
                    vol += np.dot(a, np.cross(V[f[k]], V[f[k + 1]]))
            if vol < 0:
                F = [tuple(f)[::-1] for f in F]
        self.V.append(V)
        self.F += [tuple(int(i) + self.n for i in f) for f in F]
        self.S += [slot] * len(F)
        self.n += len(V)

    def merged(self):
        return np.concatenate(self.V) if self.V else np.zeros((0, 3)), self.F, self.S


def lathe(profile, seg, a0=0.0, a1=2 * math.pi, closed=True, phase=0.0):
    """profile: list of (axial x, radius r). Revolve about X. Returns V, F (quads)."""
    prof = np.asarray(profile, float)
    m = len(prof)
    n = seg if closed else seg + 1
    th = a0 + phase + (a1 - a0) * np.arange(n) / seg
    V = np.zeros((n * m, 3))
    for i, t in enumerate(th):
        V[i * m:(i + 1) * m, 0] = prof[:, 0]
        V[i * m:(i + 1) * m, 1] = prof[:, 1] * math.cos(t)
        V[i * m:(i + 1) * m, 2] = prof[:, 1] * math.sin(t)
    F = []
    for i in range(seg):
        i2 = (i + 1) % n if closed else i + 1
        for j in range(m - 1):
            F.append((i * m + j, i * m + j + 1, i2 * m + j + 1, i2 * m + j))
    return V, F


def disc_cap(x, r, seg, flip=False):
    """flat n-gon fan (as one ngon) at axial x"""
    th = 2 * math.pi * np.arange(seg) / seg
    V = np.stack([np.full(seg, x), r * np.cos(th), r * np.sin(th)], 1)
    f = tuple(range(seg))
    return V, [f[::-1] if flip else f]


def prism(poly2d, x0, x1, center=(0, 0), ang=0.0, rad=None):
    """extrude a 2D polygon (in the wheel plane, (t, r) local coords) along X from x0 to x1.
    If rad is given the polygon is placed at radius rad rotated by ang (t = tangential, r = radial offset)."""
    P = np.asarray(poly2d, float)
    k = len(P)
    ca, sa = math.cos(ang), math.sin(ang)
    er = np.array([ca, sa])
    et = np.array([-sa, ca])
    base = er * (rad or 0.0)
    pts = base[None, :] + P[:, 0:1] * et[None, :] + P[:, 1:2] * er[None, :]
    V = np.concatenate([np.stack([np.full(k, x1), pts[:, 0], pts[:, 1]], 1),
                        np.stack([np.full(k, x0), pts[:, 0], pts[:, 1]], 1)])
    F = [tuple(range(k)), tuple(range(2 * k - 1, k - 1, -1))]
    for i in range(k):
        j = (i + 1) % k
        F.append((i, k + i, k + j, j))
    return V, F


# ----------------------------------------------------------------------------------------------
def tyre(parts, R, Wt, R_rim, seg=72, stretch=0.0, grooves=3, notch=True):
    """R outer radius, Wt section width, R_rim bead radius. stretch>0 pulls the sidewall in (stretched look)."""
    h = R - R_rim
    hw = Wt / 2
    sw = hw - stretch  # sidewall max half width
    prof = []
    # outer sidewall (from bead up to shoulder), +x side
    bead_x = hw - 0.004 + stretch * 0.5
    side = [(bead_x, R_rim - 0.004), (bead_x + 0.004, R_rim + 0.006), (sw + 0.002, R_rim + 0.35 * h),
            (sw + 0.003, R_rim + 0.55 * h), (sw - 0.002, R_rim + 0.78 * h), (hw - 0.014, R - 0.010),
            (hw - 0.026, R - 0.0015)]
    prof += side
    # tread with grooves
    tread_hw = hw - 0.03
    xs = np.linspace(tread_hw, -tread_hw, 2 * grooves + 3)
    gw = 0.0065
    gpos = np.linspace(tread_hw * 0.62, -tread_hw * 0.62, grooves) if grooves else []
    tp = [(tread_hw, R)]
    for g in gpos:
        tp += [(g + gw, R), (g + gw * 0.7, R - 0.007), (g - gw * 0.7, R - 0.007), (g - gw, R)]
    tp += [(-tread_hw, R)]
    prof += tp
    prof += [(-x, r) for (x, r) in side[::-1]]
    V, F = lathe(prof, seg)
    parts.add(V, F, "M_Tire")
    # inner closure (barrel side of the tyre hidden by rim) - bead ring to make it watertight-ish
    return R_rim


def rim(parts, design, R_rim, Wr, dish=0.03, seg=72):
    """design: dict(kind='split'|'straight'|'y'|'mesh6', n=5|6|7|10, ...). Outer face at +X."""
    lip_x = Wr / 2
    R_lip = R_rim + 0.012
    # polished lip + barrel (lathe): outer flange -> lip face -> inner barrel back to the inner flange
    # walking rule for lathe profiles: the visible side is to the right of the walking direction in (x, r)
    face_x = lip_x - 0.008 - dish * 0.15  # outer edge of the spoke face at the rim
    bprof = [(-Wr / 2 - 0.004, R_rim + 0.006), (-Wr / 2, R_rim - 0.01), (-Wr / 2 + 0.02, R_rim - 0.024),
             (face_x - 0.02, R_rim - 0.024), (lip_x - 0.008, R_rim - 0.018)]
    V, F = lathe(bprof, seg)
    parts.add(V, F, "M_Rim")
    prof = [(lip_x - 0.008, R_rim - 0.018), (lip_x + 0.004, R_rim - 0.012), (lip_x + 0.006, R_lip - 0.012),
            (lip_x + 0.002, R_lip - 0.002), (lip_x - 0.012, R_rim + 0.002)]
    V, F = lathe(prof, seg)
    parts.add(V, F, "M_Chrome")
    # spokes
    r_hub = design.get("r_hub", 0.078)
    r_out = R_rim - 0.016
    kind = design.get("kind", "split")
    n = design.get("n", 5)

    def a_face(r):
        t = min(max((r - r_hub) / (r_out - r_hub), 0.0), 1.0)
        return face_x - dish * (1 - t) ** 1.4

    def fr(r, r0=None, r1=None):
        r0 = r_hub if r0 is None else r0
        r1 = r_out if r1 is None else r1
        return min(max((r - r0) / (r1 - r0), 0.0), 1.0)

    def spoke(theta_fn, w_fn, t_fn, r0, r1, K=9, chamfer=0.35):
        rs = np.linspace(r0, r1, K)
        secs = []
        for r in rs:
            th = theta_fn(r)
            w = w_fn(r)
            t = t_fn(r)
            af = a_face(r)
            c = min(w * chamfer, 0.006)
            loc = [(-w, af - c), (-w + c, af), (w - c, af), (w, af - c), (w * 0.75, af - t), (-w * 0.75, af - t)]
            er = np.array([0.0, math.cos(th), math.sin(th)])
            et = np.array([0.0, -math.sin(th), math.cos(th)])
            pts = [r * er + o * et + np.array([a, 0, 0]) for o, a in loc]
            secs.append(pts)
        m = 6
        Vs = np.array([p for s in secs for p in s])
        Fs = []
        for k in range(K - 1):
            for i in range(m):
                j = (i + 1) % m
                Fs.append((k * m + i, k * m + j, (k + 1) * m + j, (k + 1) * m + i))
        Fs.append(tuple(range(m))[::-1])
        Fs.append(tuple(range((K - 1) * m, K * m)))
        parts.add(Vs, Fs, "M_Rim", closed=True)

    tw = design.get("twist", 0.0)
    if kind == "steel":  # pressed steel wheel with a hub cap and vent holes (traffic)
        a0 = a_face(r_hub)
        fp = [(a0 + 0.004, r_hub), (a0 + 0.004, r_hub + 0.04), (a0 - 0.006, r_hub + 0.07), (a0 - 0.002, r_out - 0.03),
              (face_x - 0.006, r_out - 0.012), (face_x - 0.012, r_out + 0.004)]
        V, F = lathe(fp, seg // 2 if seg > 40 else seg)
        parts.add(V, F, "M_Rim")
        for i in range(design.get("holes", 6)):
            th = 2 * math.pi * i / design.get("holes", 6)
            rr = r_hub + 0.075
            V, F = disc_cap(0.0, 0.016, 8)
            V = np.asarray(V)
            V[:, 0] = a0 - 0.0005
            V[:, 1] += rr * math.cos(th)
            V[:, 2] += rr * math.sin(th)
            parts.add(V, F, "M_Underbody")
        cp = [(a0 + 0.03, 0.0), (a0 + 0.026, r_hub * 0.6), (a0 + 0.01, r_hub + 0.01), (a0 + 0.004, r_hub + 0.03)]
        V, F = lathe(cp, 24)
        parts.add(V, F, design.get("cap_mat", "M_Chrome"))
        return face_x
    if kind == "split":  # n double spokes (V pairs)
        gap = design.get("gap", 0.11)  # angular half gap at the rim (rad)
        w0, w1 = design.get("w_hub", 0.012), design.get("w_rim", 0.0075)
        for i in range(n):
            th0 = 2 * math.pi * i / n + design.get("phase", 0.0)
            for sgn in (-1, 1):
                spoke(lambda r, th0=th0, sgn=sgn: th0 + sgn * gap * fr(r) ** design.get("pw", 0.8) +
                      tw * (r - r_hub),
                      lambda r, w0=w0, w1=w1: w0 + (w1 - w0) * fr(r),
                      lambda r: 0.022, r_hub - 0.01, r_out + 0.004)
    elif kind == "straight":
        for i in range(n):
            th0 = 2 * math.pi * i / n + design.get("phase", 0.0)
            wr, wh_ = design.get("w_rim", 0.012), design.get("w_hub", 0.018)
            spoke(lambda r, th0=th0: th0 + tw * (r - r_hub),
                  lambda r, wr=wr, wh_=wh_: wh_ + (wr - wh_) * (r - r_hub) / (r_out - r_hub),
                  lambda r: 0.026, r_hub - 0.01, r_out + 0.004)
    elif kind == "y":
        split = design.get("split", 0.55)
        gap = design.get("gap", 0.10)
        r_s = r_hub + split * (r_out - r_hub)
        for i in range(n):
            th0 = 2 * math.pi * i / n + design.get("phase", 0.0)
            spoke(lambda r, th0=th0: th0 + tw * (r - r_hub), lambda r: 0.019 - 0.004 * (r - r_hub) / (r_s - r_hub),
                  lambda r: 0.028, r_hub - 0.01, r_s + 0.012)
            for sgn in (-1, 1):
                spoke(lambda r, th0=th0, sgn=sgn: th0 + tw * (r - r_hub) + sgn * gap * fr(r, r_s) ** 0.9,
                      lambda r: 0.0105, lambda r: 0.024, r_s - 0.004, r_out + 0.004, K=6)
    elif kind == "te":  # 6 thick spokes with a raised rib, slightly tapered (TE37-like silhouette)
        for i in range(n):
            th0 = 2 * math.pi * i / n + design.get("phase", 0.0)
            spoke(lambda r, th0=th0: th0, lambda r: 0.024 - 0.008 * (r - r_hub) / (r_out - r_hub),
                  lambda r: 0.03, r_hub - 0.01, r_out + 0.004, chamfer=0.25)
    # hub disc
    ah = a_face(r_hub) - 0.004
    hp = [(ah + 0.0, 0.036), (ah + 0.004, 0.0405), (ah + 0.004, r_hub - 0.006), (ah, r_hub + 0.004),
          (ah - 0.03, r_hub + 0.004)]
    V, F = lathe(hp, 40)
    parts.add(V, F, "M_Rim")
    # centre cap
    cp = [(ah + 0.018, 0.0), (ah + 0.016, 0.022), (ah + 0.010, 0.033), (ah, 0.036)]
    V, F = lathe(cp, 32)
    parts.add(V, F, design.get("cap_mat", "M_Trim"))
    # lug nuts (hex) on 114.3 PCD
    nl = design.get("lugs", 5)
    for i in range(nl):
        th = 2 * math.pi * i / nl + math.pi / nl
        hexp = [(0.0095 * math.cos(k * math.pi / 3), 0.0095 * math.sin(k * math.pi / 3)) for k in range(6)]
        V, F = prism(hexp, ah + 0.002, ah + 0.02, ang=th, rad=0.05715)
        parts.add(V, F, "M_Chrome", closed=True)
    return face_x


def brake_disc(parts, R_disc, x_c=-0.035, th=0.026, seg=48):
    hp = [(x_c + th / 2, R_disc * 0.55), (x_c + th / 2, R_disc), (x_c - th / 2, R_disc), (x_c - th / 2, R_disc * 0.55),
          (x_c + th / 2, R_disc * 0.55)]
    V, F = lathe(hp, seg)
    parts.add(V, F, "M_Brake")
    # hat
    hat = [(x_c + th / 2 + 0.034, 0.03), (x_c + th / 2 + 0.03, R_disc * 0.5), (x_c + th / 2, R_disc * 0.56)]
    V, F = lathe(hat, 32)
    parts.add(V, F, "M_Brake")


def caliper(parts, R_disc, x_c=-0.035, th=0.026, ang_c=math.radians(155), span=math.radians(62), front=True):
    """block straddling the disc; ang_c measured in the (Y,Z) plane from +Y (car rear in Blender = +Y)."""
    r0, r1 = R_disc * 0.62, R_disc + 0.022
    x0, x1 = x_c - th / 2 - 0.028, x_c + th / 2 + 0.024
    K = 10
    angs = np.linspace(ang_c - span / 2, ang_c + span / 2, K)
    prof = [(x0, r0), (x1, r0 + 0.008), (x1, r1 - 0.006), (x1 - 0.008, r1), (x0, r1)]
    m = len(prof)
    V = []
    for a in angs:
        for (x, r) in prof:
            V.append((x, r * math.cos(a), r * math.sin(a)))
    F = []
    for k in range(K - 1):
        for i in range(m):
            j = (i + 1) % m
            F.append((k * m + i, (k + 1) * m + i, (k + 1) * m + j, k * m + j))
    F.append(tuple(range(m)))
    F.append(tuple(range((K - 1) * m, K * m))[::-1])
    parts.add(np.array(V), F, "M_Brake", closed=True)


def build_wheel(cfg):
    """cfg: R (tyre radius), Wt (tyre width), rim_in (inch), design, dish, stretch -> (wheel Parts, caliper Parts)"""
    R, Wt = cfg["R"], cfg["Wt"]
    R_rim = cfg["rim_in"] * 0.0254 / 2
    Wr = cfg.get("Wr", Wt * 0.86)
    w = Parts()
    tyre(w, R, Wt, R_rim + 0.006, seg=cfg.get("seg", 72), stretch=cfg.get("stretch", 0.0),
         grooves=cfg.get("grooves", 3))
    rim(w, cfg.get("design", {"kind": "split", "n": 5}), R_rim, Wr, cfg.get("dish", 0.03), seg=cfg.get("seg", 72))
    R_disc = min(R_rim - 0.045, cfg.get("disc", 0.17))
    if not cfg.get("no_disc"):
        brake_disc(w, R_disc, seg=cfg.get("disc_seg", 48))
    c = Parts()
    if not cfg.get("no_caliper"):
        caliper(c, R_disc)
    if cfg.get("dual"):  # dual rear tyres (trucks): second tyre + rim inboard
        w2 = Parts()
        tyre(w2, R, Wt, R_rim + 0.006, seg=cfg.get("seg", 72), grooves=cfg.get("grooves", 3))
        V, F, S = w2.merged()
        V = V + np.array([-Wt - 0.02, 0, 0])
        w.add(V, F, "M_Tire")
    return w, c
