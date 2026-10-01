"""Parametric car body as a signed distance field.

Model coordinates: s = forward (0 midway between the axles), x = lateral (fields use |x|), z = up (ground = 0).

The body = rounded intersection "hull" (side wall W(s,z), top surface T(s,x), underside, nose, tail)
          ∪ greenhouse (roof profile, plan width, tumblehome, roof crown / double bubble)
          − wheel arches (cylinders, with fender lips)
          ± stamps (2D shapes projected from a view: recess / raise / paint-only), ± extra solids.
Every stamp / solid / region carries a material slot name; classify() assigns slots to face centres.
"""
import math

import numpy as np

from sdf import (Curve, Shape2D, clamp, d_round, i_round, i_round_v, sd_box, sd_capsule, sd_cyl_s, sd_cyl_x,
                 sd_ellipsoid, smax, smin, smoothstep, u_round, rot_z, rot_x_axis)

D = 0.004  # finite-difference step for normalisation gradients


def C(pts, smooth=0.03, **kw):
    if isinstance(pts, Curve):
        return pts
    if isinstance(pts, (int, float)):
        return Curve([(-20, float(pts)), (20, float(pts))], smooth=0)
    return Curve(pts, smooth=smooth, **kw)


def view_frame(view):
    """-> (origin, u, v, n) unit vectors in (s, x, z)"""
    if isinstance(view, str):
        return {
            "side": ((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
            "front": ((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)),
            "rear": ((0, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0)),
            "top": ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        }[view]
    yaw = math.radians(view.get("yaw", 0.0))
    pit = math.radians(view.get("pitch", 0.0))
    n = np.array([math.cos(pit) * math.cos(yaw), math.cos(pit) * math.sin(yaw), math.sin(pit)])
    u = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    v = np.cross(n, u)
    return (tuple(view.get("origin", (0, 0, 0))), tuple(u), tuple(v), tuple(n))


class Stamp:
    """2D shape projected along a view direction, limited by a window of half-space constraints."""

    def __init__(self, shape, view="side", win=None, op="paint", depth=0.006, mat="M_Trim", k=None, name="",
                 wall_mat=None, sym=True, rel=None):
        if k is None:  # rounder rims on deep pockets: surface nets resolve fillets without stair-stepping
            k = min(max(0.25 * depth, 0.0035), 0.0075)
        self.rel = rel or ("base" if op == "recess" else "current")
        self.shape = shape
        self.frame = view_frame(view)
        self.win = win or {}
        self.op = op
        self.depth = depth
        self.mat = mat
        self.k = k
        self.name = name
        self.wall_mat = wall_mat
        self.sym = sym

    def sd3(self, P):
        o, u, v, n = (np.asarray(a, float) for a in self.frame)
        Q = P - o
        U = Q[:, 0] * u[0] + Q[:, 1] * u[1] + Q[:, 2] * u[2]
        Vv = Q[:, 0] * v[0] + Q[:, 1] * v[1] + Q[:, 2] * v[2]
        Nn = Q[:, 0] * n[0] + Q[:, 1] * n[1] + Q[:, 2] * n[2]
        d = self.shape(U, Vv)
        w = self.win
        s, x, z = P[:, 0], P[:, 1], P[:, 2]
        for key, val in w.items():
            if key == "s_min":
                d = np.maximum(d, val - s)
            elif key == "s_max":
                d = np.maximum(d, s - val)
            elif key == "x_min":
                d = np.maximum(d, val - x)
            elif key == "x_max":
                d = np.maximum(d, x - val)
            elif key == "z_min":
                d = np.maximum(d, val - z)
            elif key == "z_max":
                d = np.maximum(d, z - val)
            elif key == "n_min":
                d = np.maximum(d, val - Nn)
            elif key == "n_max":
                d = np.maximum(d, Nn - val)
        return d

    def apply(self, d, P, base=None):
        if self.op == "paint":
            return d
        sd = self.sd3(P)
        ref = base if (self.rel == "base" and base is not None) else d
        if self.op == "recess":
            inner = smin(-sd, ref + self.depth, self.k)
            return smax(d, inner, self.k)
        if self.op == "raise":
            outer = smax(sd, ref - self.depth, self.k)
            return smin(d, outer, self.k)
        if self.op == "cut":  # through-cut: remove the prism completely
            return smax(d, -sd, self.k)
        raise ValueError(self.op)


class Solid:
    """extra 3D primitive: union / subtract / intersect-with-body, with its own material"""

    def __init__(self, fn, op="union", k=0.005, mat="M_Paint", name="", round_=None, bound=None):
        self.fn = fn
        self.op = op
        self.k = k
        self.mat = mat
        self.name = name
        self.round = round_
        self.bound = bound  # (lo, hi) arrays in model coords (|x|) -> skip eval outside

    def eval(self, P):
        if self.bound is None:
            return self.fn(P)
        lo, hi = (np.asarray(a, float) for a in self.bound)
        q = np.maximum(np.maximum(lo - P, P - hi), 0)
        bd = np.linalg.norm(q, axis=1)
        out = np.maximum(bd, 0.05)
        m = bd < 0.05
        if m.any():
            out[m] = self.fn(P[m])
        return out

    def apply(self, d, P):
        e = self.eval(P)
        if self.op == "union":
            return u_round(d, e, self.k) if self.round else smin(d, e, self.k)
        if self.op == "sub":
            return d_round(d, e, self.k) if self.round else smax(d, -e, self.k)
        if self.op == "inter":
            return smax(d, e, self.k)
        raise ValueError(self.op)


class CarBody:
    def __init__(self, spec):
        self.spec = sp = spec
        self.wb = sp["wb"]
        self.sf = self.wb / 2  # front axle s
        self.sr = -self.wb / 2
        wh = sp["wheels"]
        self.wh = wh
        g = lambda k, d=None: sp.get(k, d)
        # hull curves
        self.top = C(sp["top"], g("top_smooth", 0.03))
        self.bot = C(sp["bot"], g("bot_smooth", 0.04))
        self.nose = C(sp["nose"], g("nose_smooth", 0.02))         # z -> s of front face
        self.tail = C(sp["tail"], g("tail_smooth", 0.02))         # z -> s of rear face
        self.nose_plan = C(sp.get("nose_plan", [(0, 0), (1, 0)]), 0.02)   # x -> recession (m)
        self.tail_plan = C(sp.get("tail_plan", [(0, 0), (1, 0)]), 0.02)
        self.halfw = C(sp["halfw"], g("halfw_smooth", 0.05))
        self.sections = [(s, C(pts, 0.02)) for s, pts in sp["sections"]]
        self.crown = C(g("crown", 0.03), 0.05)
        pk = g("peaks", None)
        self.pk_amp = C(pk["amp"], 0.05) if pk else None
        self.pk_x = C(pk["x"], 0.05) if pk else None
        self.pk_w = pk.get("w", 0.12) if pk else 0.1
        self.flares = g("flares", [])
        self.r_sh = C(g("r_sh", 0.03), 0.05)
        self.r_nose = g("r_nose", 0.04)
        self.r_tail = g("r_tail", 0.03)
        self.r_bot = g("r_bot", 0.04)
        # greenhouse
        self.has_gh = "roof" in sp
        if self.has_gh:
            self.roof = C(sp["roof"], g("roof_smooth", 0.03))
            self.gh_w = C(sp["gh_w"], g("gh_w_smooth", 0.04))
            self.belt = C(sp["belt"], 0.05)
            self.tumble = C(g("tumble", 22.0), 0.05)
            self.roof_crown = C(g("roof_crown", 0.05), 0.05)
            self.r_rail = C(g("r_rail", 0.06), 0.05)
            self.bubble = g("bubble", None)
            self.r_belt = g("r_belt", 0.012)
            rs = [p[0] for p in sp["roof"]]
            self.gh_s = g("gh_s", (min(rs), max(rs)))
        # arches
        ar = g("arches", {})
        self.arch = []
        for key, sa in (("f", self.sf), ("r", self.sr)):
            R = wh["r_" + key] + ar.get("gap", 0.045)
            za = wh["r_" + key] + ar.get("dz", 0.02)
            x_in = wh["track_" + key] / 2 - wh["w_" + key] / 2 - ar.get("inner", 0.05)
            self.arch.append(dict(s=sa + ar.get("ds_" + key, 0.0), z=za, R=R, x_in=x_in,
                                  sx=ar.get("sx", 1.0), sz=ar.get("sz", 1.0), n=ar.get("n", 2.0)))
        self.r_lip = ar.get("r_lip", 0.008)
        self.lip = ar.get("lip", None)
        self.stamps = [st for st in g("stamps", [])]
        self.solids = [so for so in g("solids", [])]
        self.top_bumps = g("top_bumps", [])
        self.side_bumps = g("side_bumps", [])
        self.late = g("late", [])  # stamps/solids applied after everything (e.g. cuts through solids)

    # ------------------------------------------------------------------ hull pieces
    def sec(self, s, z, deriv=False):
        """section offset and (optionally) its partial derivatives (d/ds, d/dz)"""
        secs = self.sections
        if len(secs) == 1:
            c = secs[0][1]
            return (c(z), np.zeros_like(s), c.d(z)) if deriv else c(z)
        ss = np.array([a for a, _ in secs])
        idx = np.clip(np.searchsorted(ss, s) - 1, 0, len(ss) - 2)
        span = ss[idx + 1] - ss[idx]
        u = clamp((s - ss[idx]) / span, 0, 1)
        t = u * u * (3 - 2 * u)
        V = np.stack([c(z) for _, c in secs])
        n = np.arange(len(s))
        a, b = V[idx, n], V[idx + 1, n]
        out = a * (1 - t) + b * t
        if not deriv:
            return out
        dt = np.where((u > 0) & (u < 1), 6 * u * (1 - u) / span, 0.0)
        Dz = np.stack([c.d(z) for _, c in secs])
        dz = Dz[idx, n] * (1 - t) + Dz[idx + 1, n] * t
        return out, (b - a) * dt, dz

    def arch_r2(self, s, z, a):
        ds = (s - a["s"]) / a["sx"]
        dz = (z - a["z"]) / a["sz"]
        nn = a["n"]
        if nn == 2.0:
            return np.sqrt(ds * ds + dz * dz)
        return (np.abs(ds) ** nn + np.abs(dz) ** nn) ** (1.0 / nn)

    def W(self, s, z, deriv=False):
        if deriv:
            sec, sec_s, sec_z = self.sec(s, z, True)
        else:
            sec = self.sec(s, z)
        w = self.halfw(s) + sec
        for f in self.flares:
            e = ((s - f["s"]) / f["ss"]) ** 2 + ((z - f["z"]) / f["sz"]) ** 2
            w = w + f["amp"] * np.exp(-e ** f.get("p", 1.0))
        for b in self.side_bumps:
            w = w + b(s, z)
        if self.lip:
            for a in self.arch:
                r2 = self.arch_r2(s, z, a)
                t = (r2 - (a["R"] + self.lip.get("off", 0.02))) / self.lip.get("w", 0.03)
                w = w + self.lip["amp"] * np.exp(-t * t) * smoothstep(a["z"] - 0.12, a["z"] + 0.02, z)
        if deriv:
            return w, self.halfw.d(s) + sec_s, sec_z
        return w

    def T(self, s, x, deriv=False):
        hw = np.maximum(self.halfw(s), 0.2)
        cr = self.crown(s)
        t = self.top(s) - cr * (x / hw) ** 2
        tx = -2 * cr * x / (hw * hw)
        if self.pk_amp is not None:
            u = (x - self.pk_x(s)) / self.pk_w
            g = self.pk_amp(s) * np.exp(-u * u)
            t = t + g
            tx = tx - 2 * u / self.pk_w * g
        for b in self.top_bumps:
            t = t + b(s, x)
        if deriv:
            return t, self.top.d(s), tx
        return t

    def hull(self, P):
        s, x, z = P[:, 0], P[:, 1], P[:, 2]
        W, Ws, Wz = self.W(s, z, True)
        d_side = (x - W) / np.sqrt(1 + Ws * Ws + Wz * Wz)
        T, Ts, Tx = self.T(s, x, True)
        d_top = (z - T) / np.sqrt(1 + Ts * Ts + Tx * Tx)
        B = self.bot(s)
        d_bot = (B - z) / np.sqrt(1 + self.bot.d(s) ** 2)
        Nf = self.nose(z) - self.nose_plan(x)
        d_front = (s - Nf) / np.sqrt(1 + self.nose.d(z) ** 2 + self.nose_plan.d(x) ** 2)
        Nr = self.tail(z) + self.tail_plan(x)
        d_rear = (Nr - s) / np.sqrt(1 + self.tail.d(z) ** 2 + self.tail_plan.d(x) ** 2)
        h = i_round_v(d_side, d_top, self.r_sh(s))
        h = i_round(h, d_bot, self.r_bot)
        h = i_round(h, d_front, self.r_nose)
        h = i_round(h, d_rear, self.r_tail)
        return h

    def Zr(self, s, x, deriv=False):
        wg = np.maximum(self.gh_w(s), 0.2)
        rc = self.roof_crown(s)
        z = self.roof(s) - rc * (x / wg) ** 2
        if deriv:
            zx = -2 * rc * x / (wg * wg)
        if self.bubble:
            b = self.bubble
            u = x / b["w"]
            z = z - b["depth"] * np.exp(-u * u) * smoothstep(b.get("s0", -9), b.get("s0", -9) + 0.25, s) * \
                (1 - smoothstep(b.get("s1", 9) - 0.25, b.get("s1", 9), s))
            if deriv:
                zx = zx + b["depth"] * 2 * u / b["w"] * np.exp(-u * u)
        if deriv:
            return z, self.roof.d(s), zx
        return z

    def Wg(self, s, z):
        return self.gh_w(s) - (z - self.belt(s)) * np.tan(np.radians(self.tumble(s)))

    def greenhouse(self, P):
        s, x, z = P[:, 0], P[:, 1], P[:, 2]
        Z, Zs, Zx = self.Zr(s, x, True)
        d_top = (z - Z) / np.sqrt(1 + Zs * Zs + Zx * Zx)
        tn = np.tan(np.radians(self.tumble(s)))
        Wg = self.gh_w(s) - (z - self.belt(s)) * tn
        Wgs = self.gh_w.d(s) + self.belt.d(s) * tn
        Wgz = -tn
        d_side = (x - Wg) / np.sqrt(1 + Wgs * Wgs + Wgz * Wgz)
        d = i_round_v(d_top, d_side, self.r_rail(s))
        d = np.maximum(d, self.belt(s) - 0.25 - z)  # bottom (buried in the hull)
        s0, s1 = self.gh_s
        d = np.maximum(d, np.maximum(s0 - s, s - s1))  # ends (buried in the hull)
        # never beyond the hull's nose / tail faces
        d = np.maximum(d, s - (self.nose(z) - self.nose_plan(x)))
        d = np.maximum(d, (self.tail(z) + self.tail_plan(x)) - s)
        return d

    # ------------------------------------------------------------------ full field
    def base(self, P):
        d = self.hull(P)
        if self.has_gh:
            d = u_round(d, self.greenhouse(P), self.r_belt)
        return d

    def __call__(self, P):
        P = np.asarray(P, float)
        if P[:, 1].min() < 0:
            P = P.copy()
            P[:, 1] = np.abs(P[:, 1])
        d = self.base(P)
        for so in self.solids:
            if so.op == "union":
                d = so.apply(d, P)
        for a in self.arch:
            r2 = self.arch_r2(P[:, 0], P[:, 2], a)
            da = np.maximum(r2 - a["R"], a["x_in"] - P[:, 1])
            d = d_round(d, da, self.r_lip)
        base = d
        for st in self.stamps:
            d = st.apply(d, P, base)
        for so in self.solids:
            if so.op != "union":
                d = so.apply(d, P)
        for it in self.late:
            d = it.apply(d, P, base) if isinstance(it, Stamp) else it.apply(d, P)
        return d

    # ------------------------------------------------------------------ materials
    def regions(self):
        """material regions in priority order: (name, field(P) -> negative inside, slot)"""
        R = []
        R.append(("under", lambda P: P[:, 2] - (self.bot(P[:, 0]) + 0.012), "M_Underbody"))
        for a in self.arch:
            R.append(("well", lambda P, a=a: self.arch_r2(P[:, 0], P[:, 2], a) - (a["R"] + 0.0015), "M_Underbody"))
        tol = self.spec.get("mat_tol", 0.0015)
        for st in self.stamps + [it for it in self.late if isinstance(it, Stamp)]:
            if st.mat is None:
                continue
            if st.wall_mat:
                R.append((st.name + "_wall", lambda P, st=st: st.sd3(P) - tol, st.wall_mat))
                R.append((st.name, lambda P, st=st: st.sd3(P) + 0.004, st.mat))
            else:
                R.append((st.name, lambda P, st=st: st.sd3(P) - tol, st.mat))
        for so in self.solids + [it for it in self.late if isinstance(it, Solid)]:
            if so.mat is None:
                continue
            off = 0.003 if so.op == "union" else 0.0015
            R.append((so.name, lambda P, so=so, off=off: so.eval(P) - off, so.mat))
        return R

    def classify(self, P, N=None):
        """P: (n,3) face centres (model coords, x may be signed) -> array of slot names"""
        P = np.asarray(P, float).copy()
        P[:, 1] = np.abs(P[:, 1])
        mat = np.array(["M_Paint"] * len(P), dtype=object)
        for name, fn, slot in self.regions():
            mat[fn(P) < 0] = slot
        return mat

    def bounds(self, margin=0.05):
        sp = self.spec
        smin_ = min(p[1] for p in sp["tail"]) - 0.1
        smax_ = max(p[1] for p in sp["nose"]) + 0.1
        zmax = max(max(p[1] for p in sp["top"]), max(p[1] for p in sp.get("roof", [(0, 0)]))) + 0.12
        wmax = max(p[1] for p in sp["halfw"]) + 0.12 + sp.get("extra_w", 0.0)
        return (np.array([smin_ - margin, -0.012, 0.0]), np.array([smax_ + margin, wmax + margin, zmax + margin]))


class CustomBody(CarBody):
    """free-form body: spec['sdf'](P) gives the base shape; arches / stamps / solids / regions as CarBody.
    spec keys: wb, wheels, sdf, bounds=(lo, hi), arch_axles=('f','r'), arches={...}, stamps, solids, late, under_z"""

    def __init__(self, spec):
        self.spec = sp = spec
        self.wb = sp["wb"]
        self.sf, self.sr = self.wb / 2, -self.wb / 2
        wh = sp["wheels"]
        self.wh = wh
        ar = sp.get("arches", {})
        self.arch = []
        for key, sa in (("f", self.sf), ("r", self.sr)):
            if key not in sp.get("arch_axles", ("f", "r")):
                continue
            R = wh["r_" + key] + ar.get("gap", 0.045)
            za = wh["r_" + key] + ar.get("dz", 0.02)
            x_in = wh["track_" + key] / 2 - wh["w_" + key] / 2 - ar.get("inner", 0.05)
            self.arch.append(dict(s=sa, z=za, R=R, x_in=x_in, sx=ar.get("sx", 1.0), sz=ar.get("sz", 1.0),
                                  n=ar.get("n", 2.0)))
        self.r_lip = ar.get("r_lip", 0.008)
        self.lip = None
        self.stamps = list(sp.get("stamps", []))
        self.solids = list(sp.get("solids", []))
        self.late = list(sp.get("late", []))
        self.bot = C(sp.get("under_z", 0.0))
        self.has_gh = False

    def base(self, P):
        return self.spec["sdf"](P)

    def bounds(self, margin=0.05):
        lo, hi = self.spec["bounds"]
        return np.array(lo, float) - margin, np.array(hi, float) + margin
