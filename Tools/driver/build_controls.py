"""Shifter and hydraulic handbrake, modelled for the in-car view (the driver's left hand works them).

    blender -b -P Tools/driver/build_controls.py

Out: Game/Assets/InkDrift/Models/Driver/Resources/Driver/shifter.fbx and handbrake.fbx, each built in its pivot's
Unity frame (x right, y up, z forward toward the dash), matching CockpitBuilder / CockpitRig:
  * shifter (pivot 45 mm up in the boot): "ShiftLever" moves with the lever (chrome rod, jam nut, 46 mm round
    Delrin knob with the 6-speed pattern raised in white paint); "ShiftBoot" stays put (leather gaiter with
    irregular folds, four stitched corner seams, top collar, satin trim bezel with four screws)
  * handbrake (pivot 20 mm under the console top, lever leaning 18 degrees back): "HbLever" moves (anodised flat
    bar, ribbed rubber grip, end cap); "HbBase" stays put (slotted cover plate, bracket cheeks, polished master
    cylinder with reservoir, push rod, braided lines into the console)
Material names (M_Ctl*) are mapped to cockpit materials at runtime (CockpitBuilder).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Models", "Driver", "Resources", "Driver")
FONT = os.path.join(REPO, "Game", "Assets", "InkDrift", "Art", "Fonts", "ChakraPetch-Bold.ttf")
MATS = ["M_CtlKnob", "M_CtlPaint", "M_CtlChrome", "M_CtlBoot", "M_CtlStitch", "M_CtlTrim",
        "M_CtlAnodized", "M_CtlRubber", "M_CtlSteel"]
KNOB, PAINT, CHROME, BOOT, STITCH, TRIM, ANOD, RUBBER, STEEL = range(len(MATS))

# shifter frame (CockpitBuilder): lever from (0,-0.045,0) to (0,0.135,-0.01); knob centre (0,0.155,-0.012)
KNOB_C = np.array([0.0, 0.155, -0.012])
KNOB_R = 0.023
CONSOLE_Y = -0.050                       # console top in the shifter pivot frame
# handbrake frame: lever leans back 18 degrees (Unity Euler(-18,0,0)), 0.30 m to the top of the grip
HB_TILT = math.radians(-18.0)
HB_LEN = 0.30
HB_CONSOLE_Y = 0.020                     # console top in the handbrake pivot frame


def u2b(p):
    """Unity frame -> Blender (FBX export: forward -Z, up Y, baked space transform)"""
    return Vector((-p[0], -p[2], p[1]))


def log(*a):
    print("[controls]", *a, flush=True)


def rot_x(v, a):
    """Unity rotation about +x (left-handed: +y turns toward +z)"""
    c, s = math.cos(a), math.sin(a)
    return np.array([v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c])


def nrm(v):
    return v / max(np.linalg.norm(v), 1e-12)


def new_obj(name):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in MATS:
        me.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    return ob


def grid(bm, P, mat, closed_u=True, closed_v=False, smooth=True):
    """quad surface from a (nu, nv, 3) array of Unity points"""
    nu, nv = P.shape[:2]
    V = [[bm.verts.new(u2b(P[i, j])) for j in range(nv)] for i in range(nu)]
    for i in range(nu if closed_u else nu - 1):
        for j in range(nv if closed_v else nv - 1):
            f = bm.faces.new((V[i][j], V[(i + 1) % nu][j], V[(i + 1) % nu][(j + 1) % nv], V[i][(j + 1) % nv]))
            f.material_index = mat
            f.smooth = smooth
    return V


def cap(bm, ring, centre, mat, smooth=True):
    """fan a closed ring of verts to a centre point"""
    c = bm.verts.new(u2b(centre))
    for i in range(len(ring)):
        f = bm.faces.new((ring[i], ring[(i + 1) % len(ring)], c))
        f.material_index = mat
        f.smooth = smooth


def frame(axis):
    """two unit vectors perpendicular to axis"""
    a = nrm(np.asarray(axis, float))
    ref = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 0, 1.0])
    u = nrm(np.cross(a, ref))
    return u, np.cross(a, u)


def tube(bm, p0, p1, r0, r1, mat, n=20, caps=True, rings=2, smooth=True):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    u, v = frame(p1 - p0)
    P = np.zeros((n, rings, 3))
    for i in range(n):
        a = 2 * math.pi * i / n
        d = u * math.cos(a) + v * math.sin(a)
        for j in range(rings):
            t = j / (rings - 1)
            P[i, j] = p0 + (p1 - p0) * t + d * (r0 + (r1 - r0) * t)
    V = grid(bm, P, mat, smooth=smooth)
    if caps:
        cap(bm, [V[i][0] for i in range(n)], p0, mat, smooth=False)
        cap(bm, [V[i][-1] for i in range(n)], p1, mat, smooth=False)


def path_tube(bm, pts, r, mat, n=10):
    """tube swept along a polyline (parallel-transported frame)"""
    pts = [np.asarray(p, float) for p in pts]
    u, _ = frame(pts[1] - pts[0])
    P = np.zeros((n, len(pts), 3))
    for j, p in enumerate(pts):
        t = nrm(pts[min(j + 1, len(pts) - 1)] - pts[max(j - 1, 0)])
        u = nrm(u - t * np.dot(u, t))
        v = np.cross(t, u)
        for i in range(n):
            a = 2 * math.pi * i / n
            P[i, j] = p + (u * math.cos(a) + v * math.sin(a)) * r
    V = grid(bm, P, mat)
    cap(bm, [V[i][0] for i in range(n)], pts[0], mat, smooth=False)
    cap(bm, [V[i][-1] for i in range(n)], pts[-1], mat, smooth=False)


def hex_prism(bm, c, axis, across_flats, h, mat):
    c, a = np.asarray(c, float), nrm(np.asarray(axis, float))
    u, v = frame(a)
    r = across_flats / math.sqrt(3)
    bot, top = [], []
    for k in range(6):
        ang = math.pi / 6 + k * math.pi / 3
        d = (u * math.cos(ang) + v * math.sin(ang)) * r
        bot.append(bm.verts.new(u2b(c - a * h / 2 + d)))
        top.append(bm.verts.new(u2b(c + a * h / 2 + d)))
    for k in range(6):
        f = bm.faces.new((bot[k], bot[(k + 1) % 6], top[(k + 1) % 6], top[k])); f.material_index = mat
    for ring in (bot, top):
        f = bm.faces.new(ring); f.material_index = mat


def dome(bm, c, axis, r, h, mat, n=16, m=5):
    """low dome (screw head) on a plane"""
    c, a = np.asarray(c, float), nrm(np.asarray(axis, float))
    u, v = frame(a)
    P = np.zeros((n, m, 3))
    for i in range(n):
        ang = 2 * math.pi * i / n
        d = u * math.cos(ang) + v * math.sin(ang)
        for j in range(m):
            t = j / (m - 1) * 0.92
            P[i, j] = c + d * r * math.cos(t * math.pi / 2) + a * h * math.sin(t * math.pi / 2)
    V = grid(bm, P, mat)
    cap(bm, [V[i][-1] for i in range(n)], c + a * h, mat)


def superellipse(th, half, e=4.0):
    """rounded-square radius at angle th (|x|^e + |z|^e = half^e)"""
    c, s = abs(math.cos(th)), abs(math.sin(th))
    return half / (c ** e + s ** e) ** (1 / e)


def stitch_dash(bm, p, along, normal, length=0.0025, width=0.0007, height=0.0004, mat=None):
    along, normal = nrm(along), nrm(normal)
    side = np.cross(normal, along)
    tube(bm, p - along * length / 2 + normal * height * 0.3, p + along * length / 2 + normal * height * 0.3,
         width / 2, width / 2, STITCH if mat is None else mat, n=6, caps=True)


# ---------------------------------------------------------------- shifter
def knob(bm):
    """46 mm Delrin ball with a flat underside where the lever threads in"""
    n, m = 48, 30
    phi_max = math.acos(-0.0185 / KNOB_R)
    P = np.zeros((n, m, 3))
    for i in range(n):
        th = 2 * math.pi * i / n
        for j in range(m):
            ph = phi_max * (j + 1) / m
            P[i, j] = KNOB_C + KNOB_R * np.array([math.sin(ph) * math.cos(th), math.cos(ph), math.sin(ph) * math.sin(th)])
    V = grid(bm, P, KNOB)
    cap(bm, [V[i][0] for i in range(n)], KNOB_C + np.array([0, KNOB_R, 0]), KNOB)
    # flat underside, closed round the threaded boss the lever screws into
    y = KNOB_C[1] - 0.0185
    Q = np.zeros((n, 2, 3))
    for i in range(n):
        th = 2 * math.pi * i / n
        Q[i, 0] = P[i, -1]
        Q[i, 1] = np.array([0.0105 * math.cos(th), y, KNOB_C[2] + 0.0105 * math.sin(th)])
    W = grid(bm, Q, KNOB)
    cap(bm, [W[i][1] for i in range(n)], np.array([0.0, y, KNOB_C[2]]), KNOB, smooth=False)


def on_knob(x, z, lift=0.00015):
    """point on the knob's top surface above (x, z) of the pattern plane"""
    dx, dz = x, z
    y = math.sqrt(max(KNOB_R ** 2 - dx * dx - dz * dz, 0.0))
    p = np.array([dx, y, dz])
    return KNOB_C + p / np.linalg.norm(p) * (KNOB_R + lift)


def strip(bm, a, b, w, segs=8):
    """painted line on the knob from pattern point a to b"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = nrm(b - a)
    s = np.array([-d[1], d[0]]) * w / 2
    a, b = a - d * w / 2, b + d * w / 2
    V = []
    for k in range(segs + 1):
        q = a + (b - a) * k / segs
        V.append((bm.verts.new(u2b(on_knob(*(q - s)))), bm.verts.new(u2b(on_knob(*(q + s))))))
    for k in range(segs):
        f = bm.faces.new((V[k][0], V[k + 1][0], V[k + 1][1], V[k][1]))
        f.material_index = PAINT
        f.smooth = True


def glyph(bm, ch, cx, cz, size):
    """a character from the HUD font, filled, laid on the knob top (reads with forward = up)"""
    cu = bpy.data.curves.new("g", "FONT")
    cu.body = ch
    cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.fill_mode = "BOTH"
    cu.resolution_u = 4
    ob = bpy.data.objects.new("g", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    vs = [bm.verts.new(u2b(on_knob(cx + v.co.x, cz + v.co.y, 0.0002))) for v in me.vertices]
    for p in me.polygons:
        try:
            f = bm.faces.new([vs[k] for k in p.vertices])
            f.material_index = PAINT
        except ValueError:
            pass
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)


def shift_pattern(bm):
    """R 1 3 5 over 2 4 6, as the CockpitRig gate: R far left and up"""
    w, col, row = 0.0009, 0.006, 0.0058
    xs = [-1.5 * col, -0.5 * col, 0.5 * col, 1.5 * col]
    strip(bm, (xs[0], 0.0), (xs[3], 0.0), w, 16)
    strip(bm, (xs[0], 0.0), (xs[0], row), w)
    for x in xs[1:]:
        strip(bm, (x, -row), (x, row), w)
    for ch, x, z in (("R", xs[0], 1), ("1", xs[1], 1), ("3", xs[2], 1), ("5", xs[3], 1),
                     ("2", xs[1], -1), ("4", xs[2], -1), ("6", xs[3], -1)):
        glyph(bm, ch, x, z * (row + 0.0035), 0.0042)


def lever(bm):
    tube(bm, (0, -0.045, 0), (0, 0.135, -0.01), 0.0085, 0.0075, CHROME, n=20)
    # jam nut locking the knob, and a thin washer
    a = nrm(np.array([0, 0.18, -0.01]))
    hex_prism(bm, np.array([0, 0.128, -0.0093]), a, 0.017, 0.007, CHROME)
    tube(bm, (0, 0.1314, -0.0095), (0, 0.1328, -0.0096), 0.0105, 0.0105, CHROME, n=24)


def boot(bm):
    """leather gaiter: rounded-square base on the bezel, gathered round the lever with soft irregular folds"""
    n, m = 112, 44
    y0, y1 = CONSOLE_Y + 0.007, 0.012
    r_top = 0.0145
    rng = np.random.default_rng(3)
    ph1, ph2 = rng.uniform(0, 2 * math.pi, 2)
    P = np.zeros((n, m, 3))
    for i in range(n):
        th = 2 * math.pi * i / n
        rb = superellipse(th, 0.053)
        for j in range(m):
            h = j / (m - 1)
            e = 1 - (1 - h) ** 1.6                                   # gathers quickly toward the top
            r = rb + (r_top - rb) * e
            r += 0.006 * math.sin(math.pi * h) * (1 - h)             # the leather balloons a little
            # folds: rings that wander round the boot, deepest mid-height, fading at both ends
            k = h * 5.2 + 0.18 * math.sin(2 * th + ph1) + 0.1 * math.sin(5 * th + ph2)
            fold = math.sin(2 * math.pi * k) ** 2 * math.sin(math.pi * h) ** 1.2
            r += 0.0022 * fold * (0.5 + 0.5 * h)
            # corner seams sink a little
            seam = max(math.exp(-((((th - math.pi / 4) % (math.pi / 2)) - math.pi / 4) / 0.035) ** 2), 0)
            r -= 0.0008 * seam * math.sin(math.pi * min(h * 1.3, 1))
            y = y0 + (y1 - y0) * (h ** 0.85)
            P[i, j] = np.array([r * math.cos(th), y, r * math.sin(th)])
    grid(bm, P, BOOT)
    # twin-needle stitching down the four corner seams
    for c in range(4):
        th0 = math.pi / 4 + c * math.pi / 2
        for side in (-1, 1):
            for j in range(3, m - 4, 2):
                h = j / (m - 1)
                th = th0 + side * 0.06 * (1 - 0.7 * h)
                ii = int(round(th / (2 * math.pi) * n)) % n
                p = P[ii, j]
                q = P[ii, j + 1]
                out = nrm(np.array([p[0], 0.25 * (1 - h), p[2]]))
                stitch_dash(bm, p + out * 0.0003, q - p, out, length=0.0022)
    # collar where the leather is tied round the lever
    tube(bm, (0, y1 - 0.004, 0), (0, y1 + 0.003, -0.0004), r_top + 0.0012, 0.0112, TRIM, n=28)


def bezel(bm):
    """satin trim frame round the boot, four domed screws"""
    n = 112
    prof = [(0.0, CONSOLE_Y), (0.0, CONSOLE_Y + 0.0062), (0.05, CONSOLE_Y + 0.0072), (0.5, CONSOLE_Y + 0.0076),
            (0.95, CONSOLE_Y + 0.0068), (1.0, CONSOLE_Y + 0.0052), (1.0, CONSOLE_Y)]
    P = np.zeros((n, len(prof), 3))
    for i in range(n):
        th = 2 * math.pi * i / n
        ri, ro = superellipse(th, 0.052), superellipse(th, 0.074)
        for j, (d, y) in enumerate(prof):
            r = ri + (ro - ri) * d
            P[i, j] = np.array([r * math.cos(th), y, r * math.sin(th)])
    grid(bm, P, TRIM)
    for sx in (-1, 1):
        for sz in (-1, 1):
            dome(bm, (sx * 0.0465, CONSOLE_Y + 0.0074, sz * 0.0465), (0, 1, 0), 0.0028, 0.0011, CHROME)


# ---------------------------------------------------------------- handbrake
def hb_axis(s):
    """point at fraction s of the lever length"""
    return rot_x(np.array([0, HB_LEN * s, 0]), HB_TILT)


def hb_lever(bm):
    a = nrm(hb_axis(1.0))
    side = np.array([1.0, 0, 0])
    fwd = np.cross(side, a)                                         # in the lever plane, across the bar
    # flat bar: 8 mm thick (x), 24 -> 19 mm deep, rounded edges, from below the pivot to the grip
    n, m = 24, 10
    P = np.zeros((n, m, 3))
    for j in range(m):
        s = -0.06 + (0.62 + 0.06) * j / (m - 1)
        c = hb_axis(s)
        half_d = 0.012 - 0.0025 * max(s, 0) / 0.62
        for i in range(n):
            th = 2 * math.pi * i / n
            cx, cz = math.cos(th), math.sin(th)
            # rounded rectangle: 4 mm half-thickness, half_d deep
            sx = math.copysign(abs(cx) ** 0.35, cx) * 0.004
            sz = math.copysign(abs(cz) ** 0.35, cz) * half_d
            P[i, j] = c + side * sx + fwd * sz
    V = grid(bm, P, ANOD)
    cap(bm, [V[i][0] for i in range(n)], hb_axis(-0.06), ANOD, smooth=False)
    # pivot boss and the push-rod clevis
    tube(bm, hb_axis(0) - side * 0.0062, hb_axis(0) + side * 0.0062, 0.0105, 0.0105, ANOD, n=24)
    # ribbed rubber grip
    n, m = 28, 48
    P = np.zeros((n, m, 3))
    u, v = side, fwd
    for j in range(m):
        t = j / (m - 1)
        s = 0.6 + 0.385 * t
        r = 0.0158 + 0.0012 * math.sin(math.pi * t)
        r -= 0.0011 * max(math.sin(2 * math.pi * t * 4.5 + 0.6), 0) ** 3 * (0.2 < t < 0.95)   # finger grooves
        if t < 0.04:
            r = 0.0128 + (r - 0.0128) * t / 0.04
        for i in range(n):
            th = 2 * math.pi * i / n
            P[i, j] = hb_axis(s) + (u * math.cos(th) + v * math.sin(th)) * r
    V = grid(bm, P, RUBBER)
    cap(bm, [V[i][0] for i in range(n)], hb_axis(0.6), RUBBER, smooth=False)
    # anodised end cap
    n2, m2 = 28, 8
    Q = np.zeros((n2, m2, 3))
    for j in range(m2):
        t = j / (m2 - 1) * 0.95
        for i in range(n2):
            th = 2 * math.pi * i / n2
            Q[i, j] = hb_axis(0.985) + a * 0.012 * math.sin(t * math.pi / 2) + \
                (u * math.cos(th) + v * math.sin(th)) * 0.0172 * math.cos(t * math.pi / 2)
    W = grid(bm, Q, ANOD)
    cap(bm, [W[i][-1] for i in range(n2)], hb_axis(0.985) + a * 0.012, ANOD)
    cap(bm, [W[i][0] for i in range(n2)], hb_axis(0.985), ANOD, smooth=False)


def box(bm, c, size, mat):
    c, h = np.asarray(c, float), np.asarray(size, float) / 2
    vs = {}
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                vs[ix, iy, iz] = bm.verts.new(u2b(c + h * np.array([ix, iy, iz])))
    for quad in (((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)), ((-1, -1, 1), (-1, 1, 1), (1, 1, 1), (1, -1, 1)),
                 ((-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)), ((1, -1, -1), (1, -1, 1), (1, 1, 1), (1, 1, -1)),
                 ((-1, -1, -1), (-1, -1, 1), (1, -1, 1), (1, -1, -1)), ((-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1))):
        f = bm.faces.new([vs[q] for q in quad])
        f.material_index = mat


def hb_base(bm):
    y = HB_CONSOLE_Y
    # cover plate on the console: a 52 x 150 mm stadium, 5 mm thick with a rounded edge
    n = 64
    prof = [(1.0, y), (1.0, y + 0.004), (0.96, y + 0.005), (0.6, y + 0.0052), (0.0, y + 0.0052)]
    P = np.zeros((n, len(prof), 3))
    for i in range(n):
        th = 2 * math.pi * i / n
        r = superellipse(th, 1.0, 3.0)
        ox, oz = r * math.cos(th) * 0.026, r * math.sin(th) * 0.075
        for j, (k, yy) in enumerate(prof):
            P[i, j] = np.array([ox * k, yy, 0.02 + oz * k])
    grid(bm, P, TRIM)
    # the slot the lever swings in (dark inset)
    box(bm, (0, y + 0.0053, -0.012), (0.011, 0.0006, 0.07), RUBBER)
    # bracket cheeks either side of the lever, with the pivot bolt's head and nut
    for sx in (-1, 1):
        box(bm, (sx * 0.0078, y + 0.017, -0.004), (0.0032, 0.024, 0.042), STEEL)
        hex_prism(bm, (sx * 0.0112, y + 0.019, -0.004), (1, 0, 0), 0.011, 0.0042, CHROME)
    # master cylinder lying forward of the lever on two feet, reservoir on top
    cy = y + 0.017
    # polished body (dark steel vanishes in a night cabin and leaves the nose and cap floating)
    tube(bm, (0, cy, 0.03), (0, cy, 0.105), 0.0115, 0.0115, CHROME, n=24)
    for z in (0.034, 0.101):                                        # machined end rings
        tube(bm, (0, cy, z - 0.002), (0, cy, z + 0.002), 0.0122, 0.0122, ANOD, n=24)
    tube(bm, (0, cy, 0.105), (0, cy, 0.112), 0.0085, 0.006, CHROME, n=24)
    tube(bm, (0, cy + 0.011, 0.06), (0, cy + 0.03, 0.06), 0.009, 0.0095, CHROME, n=20)
    tube(bm, (0, cy + 0.03, 0.06), (0, cy + 0.034, 0.06), 0.0105, 0.0105, ANOD, n=20)    # reservoir cap
    tube(bm, (0, cy - 0.0115, 0.04), (0, y + 0.004, 0.04), 0.008, 0.009, STEEL, n=16)   # feet
    tube(bm, (0, cy - 0.0115, 0.095), (0, y + 0.004, 0.095), 0.008, 0.009, STEEL, n=16)
    # push rod: from the cylinder down through the slot to the lever's clevis under the console
    tube(bm, (0, cy, 0.03), (0, y - 0.004, 0.008), 0.003, 0.003, CHROME, n=12)
    # braided lines: out of the cylinder nose, looping down into the console
    for sx in (-1, 1):
        pts = []
        for k in range(14):
            t = k / 13
            pts.append(np.array([sx * (0.004 + 0.012 * t), cy - 0.002 - 0.025 * t * t, 0.112 + 0.03 * math.sin(t * math.pi * 0.8)]))
        pts.append(pts[-1] + np.array([0, -0.03, 0]))
        path_tube(bm, pts, 0.0028, STEEL)


def export(objs, root_name, fname):
    root = bpy.data.objects.new(root_name, None)
    bpy.context.scene.collection.objects.link(root)
    for ob in objs:
        ob.parent = root
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.select_set(o in objs or o == root)
    bpy.context.view_layer.objects.active = root
    path = os.path.join(OUT, fname)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},
        axis_forward="-Z", axis_up="Y", apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
        bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=True,
        use_tspace=False, add_leaf_bones=False, path_mode="RELATIVE", embed_textures=False, bake_anim=False,
        colors_type="NONE")
    tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
    log("exported", path, "triangles", tris)


def build(name, fns):
    ob = new_obj(name)
    bm = bmesh.new()
    for f in fns:
        f(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # painted pattern faces are open flakes: point them away from the knob centre explicitly
    kc = u2b(KNOB_C)
    for f in bm.faces:
        if f.material_index == PAINT:
            f.normal_update()
            if f.normal.dot(f.calc_center_median() - kc) < 0:
                f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for m in MATS:
        bpy.data.materials.new(m)
    lev = build("ShiftLever", [lever, knob, shift_pattern])
    bt = build("ShiftBoot", [boot, bezel])
    export([lev, bt], "Shifter", "shifter.fbx")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    hl = build("HbLever", [hb_lever])
    hbb = build("HbBase", [hb_base])
    export([hl, hbb], "Handbrake", "handbrake.fbx")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    # keep a scene for previews
    for fn in ("shifter.fbx", "handbrake.fbx"):
        bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, fn))
    os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cache", "controls.blend"))


if __name__ == "__main__":
    main()
