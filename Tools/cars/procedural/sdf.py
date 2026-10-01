"""INK DRIFT: TOKYO -- tiny numpy SDF toolkit for the procedural car bodies (pure numpy, runs inside Blender).

Conventions used by the car builders: points are (N,3) arrays in *model* coordinates
    s = longitudinal (forward +, 0 midway between the axles), x = lateral (|x| for symmetric parts), z = up (ground 0).
All distances in meters.  Ops follow hg_sdf / iq naming.
"""
import math

import numpy as np


# ----------------------------------------------------------------------------------------------
# scalar ops
def clamp(v, a, b):
    return np.minimum(np.maximum(v, a), b)


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smin(a, b, k):
    """polynomial smooth min (iq), k = blend size in meters"""
    if k <= 0:
        return np.minimum(a, b)
    h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def u_round(a, b, r):
    """union with a circular fillet of radius r (hg_sdf fOpUnionRound)"""
    if r <= 0:
        return np.minimum(a, b)
    ua = np.maximum(r - a, 0.0)
    ub = np.maximum(r - b, 0.0)
    return np.maximum(r, np.minimum(a, b)) - np.sqrt(ua * ua + ub * ub)


def i_round(a, b, r):
    """intersection with a circular round of radius r (hg_sdf fOpIntersectionRound)"""
    if r <= 0:
        return np.maximum(a, b)
    ua = np.maximum(r + a, 0.0)
    ub = np.maximum(r + b, 0.0)
    return np.minimum(-r, np.maximum(a, b)) + np.sqrt(ua * ua + ub * ub)


def d_round(a, b, r):
    """a minus b with rounded edge"""
    return i_round(a, -b, r)


def i_round_v(a, b, r):
    """i_round with per-point radius array"""
    r = np.maximum(r, 1e-5)
    ua = np.maximum(r + a, 0.0)
    ub = np.maximum(r + b, 0.0)
    return np.minimum(-r, np.maximum(a, b)) + np.sqrt(ua * ua + ub * ub)


def u_round_v(a, b, r):
    r = np.maximum(r, 1e-5)
    ua = np.maximum(r - a, 0.0)
    ub = np.maximum(r - b, 0.0)
    return np.maximum(r, np.minimum(a, b)) - np.sqrt(ua * ua + ub * ub)


# ----------------------------------------------------------------------------------------------
# 1D profile curves
def _pchip_slopes(x, y):
    h = np.diff(x)
    d = np.diff(y) / h
    n = len(x)
    m = np.zeros(n)
    if n == 2:
        m[:] = d[0]
        return m
    for k in range(1, n - 1):
        if d[k - 1] * d[k] <= 0:
            m[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0] = d[0]
    m[-1] = d[-1]
    return m


def pchip(x, y, t):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = _pchip_slopes(x, y)
    t = np.asarray(t, float)
    k = np.clip(np.searchsorted(x, t) - 1, 0, len(x) - 2)
    h = x[k + 1] - x[k]
    u = (t - x[k]) / h
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    v = h00 * y[k] + h10 * h * m[k] + h01 * y[k + 1] + h11 * h * m[k + 1]
    # linear extrapolation outside
    v = np.where(t < x[0], y[0] + m[0] * (t - x[0]), v)
    v = np.where(t > x[-1], y[-1] + m[-1] * (t - x[-1]), v)
    return v


class Curve:
    """Smooth single-valued profile v(t) through control points (PCHIP, then Gaussian smoothed).
    Linear extrapolation beyond the ends (constant if flat_ends)."""

    def __init__(self, pts, smooth=0.02, dt=0.002, flat_ends=False, margin=1.0):
        pts = sorted([(float(a), float(b)) for a, b in pts])
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        self.t0, self.t1 = xs[0] - margin, xs[-1] + margin
        T = np.arange(self.t0, self.t1 + dt, dt)
        V = pchip(xs, ys, T)
        if flat_ends:
            V = np.where(T < xs[0], ys[0], np.where(T > xs[-1], ys[-1], V))
        if smooth > 0:
            sig = smooth / dt
            r = int(3 * sig) + 1
            k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
            k /= k.sum()
            # pad with linear extrapolation to keep slopes at the ends
            left = V[0] + (V[0] - V[1]) * np.arange(r, 0, -1)
            right = V[-1] + (V[-1] - V[-2]) * np.arange(1, r + 1)
            V = np.convolve(np.concatenate([left, V, right]), k, mode="valid")
        self.T, self.V = T, V
        self.D = np.gradient(V, dt)
        self.dt = dt

    def __call__(self, t):
        t = np.asarray(t, float)
        v = np.interp(t, self.T, self.V)
        lo, hi = t < self.T[0], t > self.T[-1]
        if lo.any() or hi.any():
            v = np.where(lo, self.V[0] + self.D[0] * (t - self.T[0]), v)
            v = np.where(hi, self.V[-1] + self.D[-1] * (t - self.T[-1]), v)
        return v

    def d(self, t):
        return np.interp(np.asarray(t, float), self.T, self.D)


def const_curve(v):
    return Curve([(-10, v), (10, v)], smooth=0)


# ----------------------------------------------------------------------------------------------
# 2D shapes (signed distance in a 2D plane, negative inside)
def catmull_closed(pts, n_per=8):
    """closed centripetal-ish Catmull-Rom through pts -> dense polyline (no repeated end point).
    A point given as (x, y, 'c') is a sharp corner (no rounding through it)."""
    P = [(p[0], p[1]) for p in pts]
    sharp = [len(p) > 2 and p[2] == "c" for p in pts]
    n = len(P)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (np.array(P[(i + k) % n], float) for k in (-1, 0, 1, 2))
        if sharp[i]:
            p0 = p1 - (p2 - p1)
        if sharp[(i + 1) % n]:
            p3 = p2 + (p2 - p1)
        for j in range(n_per):
            t = j / n_per
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(v)
    return np.array(out)


def catmull_open(pts, n_per=8):
    P = [np.array((p[0], p[1]), float) for p in pts]
    n = len(P)
    if n < 3:
        return np.array(P)
    out = []
    for i in range(n - 1):
        p1, p2 = P[i], P[i + 1]
        p0 = P[i - 1] if i > 0 else p1 - (p2 - p1)
        p3 = P[i + 2] if i + 2 < n else p2 + (p2 - p1)
        if len(pts[i]) > 2 and pts[i][2] == "c":
            p0 = p1 - (p2 - p1)
        if len(pts[i + 1]) > 2 and pts[i + 1][2] == "c":
            p3 = p2 + (p2 - p1)
        for j in range(n_per):
            t = j / n_per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return np.array(out)


def sd_polyline(px, py, line):
    line = np.asarray(line, float)
    d = np.full(px.shape, 1e9)
    for i in range(len(line) - 1):
        ax, ay = line[i]
        ex, ey = line[i + 1] - line[i]
        ee = ex * ex + ey * ey
        if ee < 1e-14:
            continue
        wx, wy = px - ax, py - ay
        t = clamp((wx * ex + wy * ey) / ee, 0.0, 1.0)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
    return np.sqrt(d)


def sd_poly(px, py, poly):
    """signed distance to a closed polygon (iq). poly: (M,2)"""
    poly = np.asarray(poly, float)
    vx, vy = poly[:, 0], poly[:, 1]
    d = (px - vx[0]) ** 2 + (py - vy[0]) ** 2
    s = np.ones_like(px)
    M = len(poly)
    for i in range(M):
        j = i - 1
        ex, ey = vx[j] - vx[i], vy[j] - vy[i]
        wx, wy = px - vx[i], py - vy[i]
        ee = ex * ex + ey * ey
        if ee < 1e-14:
            continue
        t = clamp((wx * ex + wy * ey) / ee, 0.0, 1.0)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = py >= vy[i]
        c2 = py < vy[j]
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


class Shape2D:
    """2D region. kinds: poly (sharp), spline (closed Catmull-Rom; ('x','y','c') = sharp corner),
    ellipse (c, r), rect (c, half, round), superellipse (c, r, n). grow = offset outward (rounds corners).
    Evaluation restricted to the bbox (+margin) for speed: outside returns bbox distance (>0)."""

    def __init__(self, kind="poly", pts=None, c=(0, 0), r=(0.1, 0.1), half=(0.1, 0.1), n=4.0, grow=0.0,
                 rot=0.0, n_per=10, width=0.006, closed=False, smooth=True):
        self.kind = kind
        self.width = width
        self.grow = grow
        self.c = np.array(c, float)
        self.r = np.array(r if np.ndim(r) else (r, r), float)
        self.half = np.array(half, float)
        self.n = n
        self.rot = rot
        if kind == "spline":
            self.poly = catmull_closed(pts, n_per)
        elif kind == "poly":
            self.poly = np.array([(p[0], p[1]) for p in pts], float)
        elif kind == "stroke":
            if closed:
                self.poly = catmull_closed(pts, n_per) if smooth else np.array([(p[0], p[1]) for p in pts], float)
                self.poly = np.vstack([self.poly, self.poly[:1]])
            else:
                self.poly = catmull_open(pts, n_per) if smooth else np.array([(p[0], p[1]) for p in pts], float)
            grow = grow + width / 2
            self.grow = grow
        else:
            self.poly = None
        if self.poly is not None:
            lo, hi = self.poly.min(0), self.poly.max(0)
        elif kind in ("ellipse", "superellipse"):
            e = max(self.r) if rot else None
            lo = self.c - (self.r if not rot else np.array([e, e]))
            hi = self.c + (self.r if not rot else np.array([e, e]))
        else:
            e = np.hypot(*self.half) if rot else None
            lo = self.c - (self.half if not rot else np.array([e, e]))
            hi = self.c + (self.half if not rot else np.array([e, e]))
        self.lo = lo - grow
        self.hi = hi + grow

    def bbox_dist(self, u, v):
        dx = np.maximum(np.maximum(self.lo[0] - u, u - self.hi[0]), 0)
        dy = np.maximum(np.maximum(self.lo[1] - v, v - self.hi[1]), 0)
        return np.sqrt(dx * dx + dy * dy)

    def _eval(self, u, v):
        if self.kind in ("poly", "spline"):
            return sd_poly(u, v, self.poly)
        if self.kind == "stroke":
            return sd_polyline(u, v, self.poly)
        du, dv = u - self.c[0], v - self.c[1]
        if self.rot:
            ca, sa = math.cos(self.rot), math.sin(self.rot)
            du, dv = ca * du + sa * dv, -sa * du + ca * dv
        if self.kind == "ellipse":
            k0 = np.sqrt((du / self.r[0]) ** 2 + (dv / self.r[1]) ** 2)
            return (k0 - 1.0) * min(self.r)
        if self.kind == "superellipse":
            k0 = (np.abs(du / self.r[0]) ** self.n + np.abs(dv / self.r[1]) ** self.n) ** (1.0 / self.n)
            return (k0 - 1.0) * min(self.r)
        if self.kind == "rect":
            qx = np.abs(du) - self.half[0]
            qy = np.abs(dv) - self.half[1]
            return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0)
        raise ValueError(self.kind)

    def __call__(self, u, v, margin=0.05):
        out = self.bbox_dist(u, v) + margin * 0.0
        m = out < margin
        out = np.where(m, 0.0, np.maximum(out, margin))
        if m.any():
            out[m] = self._eval(u[m], v[m]) - self.grow
        return out


def shape_union(shapes):
    class _U:
        def __init__(self, ss):
            self.ss = ss
            self.lo = np.min([s.lo for s in ss], axis=0)
            self.hi = np.max([s.hi for s in ss], axis=0)

        def __call__(self, u, v, margin=0.05):
            d = self.ss[0](u, v, margin)
            for s in self.ss[1:]:
                d = np.minimum(d, s(u, v, margin))
            return d
    return _U(shapes)


# ----------------------------------------------------------------------------------------------
# 3D primitives (P: (N,3) arrays of s, x, z)
def sd_box(P, c, half, r=0.0):
    q = np.abs(P - np.asarray(c)) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0) - r


def sd_ellipsoid(P, c, r):
    r = np.asarray(r, float)
    q = (P - np.asarray(c)) / r
    k0 = np.linalg.norm(q, axis=1)
    k1 = np.linalg.norm(q / r, axis=1)
    return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -min(r))


def sd_capsule(P, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    pa = P - a
    ba = b - a
    h = clamp((pa[:, 0] * ba[0] + pa[:, 1] * ba[1] + pa[:, 2] * ba[2]) / float(np.dot(ba, ba)), 0.0, 1.0)
    q = pa - h[:, None] * ba
    return np.sqrt((q * q).sum(1)) - r


def sd_cyl_x(P, c, r, half_len, round_=0.0):
    """cylinder with axis along model x (lateral)"""
    d2 = np.sqrt((P[:, 0] - c[0]) ** 2 + (P[:, 2] - c[2]) ** 2) - r
    dx = np.abs(P[:, 1] - c[1]) - half_len
    return i_round(d2, dx, round_) if round_ > 0 else np.maximum(d2, dx)


def sd_cyl_s(P, c, r, half_len, round_=0.0):
    """cylinder with axis along model s (longitudinal)"""
    d2 = np.sqrt((P[:, 1] - c[1]) ** 2 + (P[:, 2] - c[2]) ** 2) - r
    ds = np.abs(P[:, 0] - c[0]) - half_len
    return i_round(d2, ds, round_) if round_ > 0 else np.maximum(d2, ds)


def rot_z(P, c, ang):
    """rotate points about a vertical axis through c (model coords) by -ang (to evaluate a shape rotated by ang)"""
    ca, sa = math.cos(ang), math.sin(ang)
    Q = P - np.asarray(c, float)
    s = ca * Q[:, 0] + sa * Q[:, 1]
    x = -sa * Q[:, 0] + ca * Q[:, 1]
    return np.stack([s, x, Q[:, 2]], 1) + np.asarray(c, float)


def rot_x_axis(P, c, ang):
    """rotate about the lateral (x) axis (pitch) through c by -ang"""
    ca, sa = math.cos(ang), math.sin(ang)
    Q = P - np.asarray(c, float)
    s = ca * Q[:, 0] + sa * Q[:, 2]
    z = -sa * Q[:, 0] + ca * Q[:, 2]
    return np.stack([s, Q[:, 1], z], 1) + np.asarray(c, float)
