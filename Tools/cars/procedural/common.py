"""Shared spec helpers: shapes, seams, windows, mirrors, lights."""
import math

import numpy as np

from body import Solid, Stamp
from sdf import Shape2D, i_round, sd_box, sd_capsule, sd_ellipsoid, smin, u_round, rot_z, rot_x_axis


def poly(pts, grow=0.0):
    return Shape2D("poly", pts, grow=grow)


def spline(pts, grow=0.0, n_per=10):
    return Shape2D("spline", pts, grow=grow, n_per=n_per)


def stroke(pts, width=0.006, closed=False, smooth=True, n_per=8):
    return Shape2D("stroke", pts, width=width, closed=closed, smooth=smooth, n_per=n_per)


def ellipse(c, r, rot=0.0, grow=0.0):
    return Shape2D("ellipse", c=c, r=r, rot=rot, grow=grow)


def rect(c, half, rot=0.0, grow=0.0):
    return Shape2D("rect", c=c, half=half, rot=rot, grow=grow)


def seam(pts, view="side", win=None, width=0.0065, depth=0.004, closed=False, mat=None, smooth=True, name="seam"):
    """panel gap: a narrow groove (the outline shader inks it); mat None keeps the paint"""
    st = Stamp(stroke(pts, width, closed, smooth), view, win, op="recess", depth=depth, mat=mat or "M_Paint",
               k=0.0016, name=name)
    if mat is None:
        st.mat = None
    return st


class _NoMat(Stamp):
    pass


def glass(shape, view, win, depth=0.006, name="glass"):
    return Stamp(shape, view, win, op="recess", depth=depth, mat="M_Glass", k=0.003, name=name)


def trim(shape, view, win, depth=0.0, mat="M_Trim", name="trim", k=0.003):
    if depth > 0:
        return Stamp(shape, view, win, op="recess", depth=depth, mat=mat, k=k, name=name)
    if depth < 0:
        return Stamp(shape, view, win, op="raise", depth=-depth, mat=mat, k=k, name=name)
    return Stamp(shape, view, win, op="paint", mat=mat, name=name)


def mirror_solids(base, s0, z0, x0, size=(0.20, 0.095, 0.11), yaw=8.0, stalk_to=None, mat_cap="M_Paint"):
    """door mirror: rounded cap (paint) + black stalk + chrome glass on the back face.
    base: (s, x, z) of the stalk root on the door; (s0, x0, z0) mirror centre."""
    L, Wd, H = size  # length along x (lateral), depth along s, height
    c = np.array([s0, x0, z0])

    def cap(P):
        Q = rot_z(P, c, math.radians(-yaw))
        q = Q - c
        # D-shaped housing: ellipsoid front half + box rear
        e = sd_ellipsoid(Q, c + np.array([0.0, 0, 0]), (Wd * 0.62, L / 2, H / 2))
        b = sd_box(Q, c + np.array([-Wd * 0.25, 0, 0]), (Wd * 0.25, L / 2 - 0.004, H / 2 - 0.004), 0.018)
        return smin(e, b, 0.01)

    def stalk(P):
        return sd_capsule(P, np.array(base), c + np.array([0.0, -L * 0.3, -H * 0.15]), 0.016)

    def face(P):
        Q = rot_z(P, c, math.radians(-yaw))
        return sd_box(Q, c + np.array([-Wd * 0.5, 0, 0]), (0.006, L / 2 - 0.012, H / 2 - 0.012), 0.012)

    lo = c - np.array([Wd + 0.05, L / 2 + 0.12, H / 2 + 0.05])
    hi = c + np.array([Wd + 0.05, L / 2 + 0.05, H / 2 + 0.05])
    lo2 = np.minimum(lo, np.array(base) - 0.05)
    hi2 = np.maximum(hi, np.array(base) + 0.05)
    return [Solid(cap, "union", 0.012, mat_cap, "mirror_cap", bound=(lo, hi)),
            Solid(stalk, "union", 0.01, "M_Trim", "mirror_stalk", bound=(lo2, hi2)),
            Solid(face, "sub", 0.003, "M_Chrome", "mirror_glass", bound=(lo, hi))]


def box_solid(c, half, r=0.01, op="union", k=0.006, mat="M_Paint", name="box", yaw=0.0, pitch=0.0):
    c = np.array(c, float)
    half = np.array(half, float)

    def f(P):
        Q = P
        if yaw:
            Q = rot_z(Q, c, math.radians(yaw))
        if pitch:
            Q = rot_x_axis(Q, c, math.radians(pitch))
        return sd_box(Q, c, half, r)

    e = np.linalg.norm(half) + 0.06
    return Solid(f, op, k, mat, name, bound=(c - e, c + e))


def ellipsoid_solid(c, r, op="union", k=0.01, mat="M_Paint", name="ell"):
    c = np.array(c, float)
    r = np.array(r, float)
    return Solid(lambda P: sd_ellipsoid(P, c, r), op, k, mat, name, bound=(c - r - 0.05, c + r + 0.05))


def capsule_solid(a, b, r, op="union", k=0.005, mat="M_Trim", name="cap"):
    a = np.array(a, float)
    b = np.array(b, float)
    return Solid(lambda P: sd_capsule(P, a, b, r), op, k, mat, name,
                 bound=(np.minimum(a, b) - r - 0.05, np.maximum(a, b) + r + 0.05))


def bump(shape, h, fall, coord="sx"):
    """top-surface height bump: shape in (s, x); h > 0 raises; fall = soft edge width"""
    def f(s, x):
        d = shape(s, x, margin=fall * 2 + 0.01)
        t = np.clip(-d / fall, 0, 1)
        return h * t * t * (3 - 2 * t)
    return f


def side_bump(shape, h, fall):
    """side-wall bump in (s, z): h > 0 pushes the wall outward"""
    def f(s, z):
        d = shape(s, z, margin=fall * 2 + 0.01)
        t = np.clip(-d / fall, 0, 1)
        return h * t * t * (3 - 2 * t)
    return f
