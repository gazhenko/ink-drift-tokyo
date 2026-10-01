"""
propkit.py - shared procedural hard-surface prop toolkit for INK DRIFT: TOKYO.

Driven by build_props.py:
    blender -b -P Tools/blender/props/build_props.py -- <module> [builder ...] [--no-preview]

CONVENTIONS (Blender space, Z up, meters)
  * Origin = ground contact point (wall props: the wall-mount point on the wall plane).
  * The prop's FRONT (road / viewer facing side) faces Blender -Y  ==> Unity +Z.
  * FBX export: axis_forward='-Z', axis_up='Y', bake_space_transform, FBX_SCALE_ALL.
    Mapping Blender (x, y, z) -> Unity (-x, z, -y).  (Unity flips X on FBX import.)
  * Linear tiling props are created with Prop(..., mirror_x=True); the builder then
    writes x in [0, L] and the exported tile spans Unity X in [0, L] with the
    "start" at Unity X = 0, front facing Unity +Z.
  * One mesh object per prop (multi-material), named after the prop; helper
    empties (WireAnchor_N, LightAnchor_N, ...) are parented to it.
"""
import bpy, bmesh, math, os, json, time, traceback
import numpy as np
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MODELS_DIR = os.path.join(REPO, 'Game', 'Assets', 'InkDrift', 'Models', 'Props')
TEX_DIR = os.path.join(MODELS_DIR, 'Textures')
PREVIEW_DIR = os.path.join(HERE, 'previews')
META_DIR = os.path.join(PREVIEW_DIR, 'meta')
SIGN_ART_DIR = os.path.join(REPO, 'Game', 'Assets', 'InkDrift', 'Art', 'Signs')
for _d in (MODELS_DIR, TEX_DIR, PREVIEW_DIR, META_DIR, os.path.join(PREVIEW_DIR, 'detail')):
    os.makedirs(_d, exist_ok=True)

OPTIONS = {'preview': True, 'export': True}
REGISTRY = {}          # builder name -> (fn, module name)


def builder(fn):
    """Decorator: register a builder function (name = fn name without 'build_')."""
    name = fn.__name__[6:] if fn.__name__.startswith('build_') else fn.__name__
    REGISTRY[name] = (fn, fn.__module__)
    return fn


# --------------------------------------------------------------------------------------
# colour / materials
# --------------------------------------------------------------------------------------
def srgb_to_lin(c):
    c = c / 255.0 if c > 1.0 else c
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip('#')
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


# c=sRGB hex, r=roughness, m=metallic, e=emission strength, a=alpha (blended),
# tex=albedo png in TEX_DIR, cut=alpha-cutout from texture, etex=emission from texture
MAT_LIB = {
    # --- tiling / generic surfaces (Unity side maps to tileable toon materials) ---
    'M_Concrete':              dict(c='#A19E95', r=0.92),
    'M_Concrete_Dark':         dict(c='#7C7A74', r=0.92),
    'M_Concrete_Light':        dict(c='#BDBAB0', r=0.9),
    'M_Stone':                 dict(c='#8F8C84', r=0.88),
    'M_Stone_Dark':            dict(c='#5E5C57', r=0.9),
    'M_Galvanized':            dict(c='#A9AEB0', r=0.45, m=0.85),
    'M_Steel_Dark':            dict(c='#4B4F53', r=0.5, m=0.7),
    'M_Chrome':                dict(c='#DADEE2', r=0.12, m=1.0),
    'M_Aluminum':              dict(c='#C4C8CB', r=0.35, m=0.85),
    'M_PaintedMetal_White':    dict(c='#EDEEE9', r=0.4),
    'M_PaintedMetal_Gray':     dict(c='#8E9398', r=0.45),
    'M_PaintedMetal_LightGray': dict(c='#C3C7C8', r=0.45),
    'M_PaintedMetal_DarkGray': dict(c='#4E5257', r=0.45),
    'M_PaintedMetal_Green':    dict(c='#2F6B48', r=0.45),
    'M_PaintedMetal_Orange':   dict(c='#F0761C', r=0.4),
    'M_PaintedMetal_Red':      dict(c='#D2281F', r=0.35),
    'M_PaintedMetal_Yellow':   dict(c='#F3C300', r=0.4),
    'M_PaintedMetal_Ivory':    dict(c='#E7E2D3', r=0.5),
    'M_PaintedMetal_Brown':    dict(c='#5B4636', r=0.5),
    'M_PaintedMetal_Black':    dict(c='#27292B', r=0.45),
    'M_PaintedMetal_Vermilion': dict(c='#D9481F', r=0.45),
    'M_PaintedMetal_Blue':     dict(c='#1F5FB0', r=0.4),
    'M_Glass':                 dict(c='#A8CAD6', r=0.05, a=0.35),
    'M_Glass_SoundBarrier':    dict(c='#A6D4C4', r=0.08, a=0.45),
    'M_Mirror':                dict(c='#E9EFF3', r=0.03, m=1.0),
    'M_Rubber':                dict(c='#1F2022', r=0.85),
    'M_PlasticRed':            dict(c='#D9271D', r=0.5),
    'M_PlasticOrange':         dict(c='#F2681A', r=0.5),
    'M_PlasticYellow':         dict(c='#F5C400', r=0.5),
    'M_PlasticGreen':          dict(c='#2E8B4E', r=0.5),
    'M_PlasticBlue':           dict(c='#1E5BB8', r=0.5),
    'M_PlasticWhite':          dict(c='#F2F2EE', r=0.5),
    'M_PlasticGray':           dict(c='#7E8185', r=0.55),
    'M_PlasticBlack':          dict(c='#212225', r=0.55),
    'M_Porcelain':             dict(c='#ECE9DF', r=0.2),
    'M_Reflector_White':       dict(c='#FFFFFF', r=0.15),
    'M_Reflector_Amber':       dict(c='#FFAE00', r=0.15),
    'M_Reflector_Red':         dict(c='#E8221A', r=0.15),
    'M_Wood':                  dict(c='#9C6C43', r=0.7),
    'M_Wood_Dark':             dict(c='#5A3A23', r=0.7),
    'M_Cable':                 dict(c='#1C1C1E', r=0.6),
    'M_Rope':                  dict(c='#C8B07A', r=0.9),
    'M_Paper':                 dict(c='#F7F4EA', r=0.8),
    # --- emissive (Unity: toon emissive, bloom) ---
    'M_EmissiveLamp':          dict(c='#FFF3D6', r=0.3, e=6.0),
    'M_EmissiveLamp_LED':      dict(c='#EAF4FF', r=0.3, e=6.0),
    'M_EmissiveLamp_Sodium':   dict(c='#FF9B2F', r=0.3, e=6.0),
    'M_EmissiveSignal_Green':  dict(c='#00D2B0', r=0.3, e=5.0),
    'M_EmissiveSignal_Yellow': dict(c='#FFB000', r=0.3, e=5.0),
    'M_EmissiveSignal_Red':    dict(c='#FF2A1C', r=0.3, e=5.0),
    # --- shared decal materials (textures from make_textures.py) ---
    'M_Deco_HazardStripe':     dict(c='#F5C400', r=0.5, tex='prop_hazard_stripe_albedo.png'),
    # --- 0-1 UV face slots, textures assigned on the Unity side ---
    'M_SignFace':              dict(c='#F4F4F4', r=0.35),
    'M_SignFace_Aux':          dict(c='#F4F4F4', r=0.35),
    'M_VendingFront':          dict(c='#DADDE0', r=0.3),
    'M_BillboardFace':         dict(c='#ECECEC', r=0.5),
}


def define_mat(name, **spec):
    """Register (or override) a material spec before use."""
    MAT_LIB[name] = spec


def _principled(mat):
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    out = None
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            out = n
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return b


def get_mat(name):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    spec = MAT_LIB.get(name)
    if spec is None:
        print(f'[propkit] WARNING unknown material {name}, using grey')
        spec = dict(c='#888888', r=0.5)
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    b = _principled(mat)
    base = hex_lin(spec.get('c', '#888888'))
    b.inputs['Base Color'].default_value = (*base, 1.0)
    b.inputs['Roughness'].default_value = spec.get('r', 0.5)
    b.inputs['Metallic'].default_value = spec.get('m', 0.0)
    mat.diffuse_color = (*base, 1.0)
    mat.roughness = spec.get('r', 0.5)
    tex = spec.get('tex')
    if tex:
        path = os.path.join(TEX_DIR, tex)
        if os.path.exists(path):
            img = bpy.data.images.load(path, check_existing=True)
            tn = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tn.image = img
            tn.location = (-400, 200)
            mat.node_tree.links.new(tn.outputs['Color'], b.inputs['Base Color'])
            if spec.get('cut'):
                mat.node_tree.links.new(tn.outputs['Alpha'], b.inputs['Alpha'])
                try:
                    mat.surface_render_method = 'DITHERED'
                except Exception:
                    pass
            if spec.get('e'):
                mat.node_tree.links.new(tn.outputs['Color'], b.inputs['Emission Color'])
                b.inputs['Emission Strength'].default_value = spec['e']
        else:
            print(f'[propkit] WARNING missing texture {path}')
            if spec.get('e'):
                b.inputs['Emission Color'].default_value = (*base, 1.0)
                b.inputs['Emission Strength'].default_value = spec['e']
    elif spec.get('e'):
        b.inputs['Emission Color'].default_value = (*base, 1.0)
        b.inputs['Emission Strength'].default_value = spec['e']
    ntex = spec.get('ntex')   # optional OpenGL normal map in TEX_DIR
    if ntex and os.path.exists(os.path.join(TEX_DIR, ntex)):
        nimg = bpy.data.images.load(os.path.join(TEX_DIR, ntex), check_existing=True)
        nimg.colorspace_settings.name = 'Non-Color'
        ntn = mat.node_tree.nodes.new('ShaderNodeTexImage')
        ntn.image = nimg
        ntn.location = (-600, -200)
        nmap = mat.node_tree.nodes.new('ShaderNodeNormalMap')
        nmap.location = (-300, -200)
        mat.node_tree.links.new(ntn.outputs['Color'], nmap.inputs['Color'])
        mat.node_tree.links.new(nmap.outputs['Normal'], b.inputs['Normal'])
    if spec.get('a') is not None:
        b.inputs['Alpha'].default_value = spec['a']
        mat.diffuse_color = (*base, spec['a'])
        try:
            mat.surface_render_method = 'BLENDED'
        except Exception:
            pass
    return mat


# --------------------------------------------------------------------------------------
# UV projections (operate on numpy loop data)
# each returns f(P[N,3] loop positions, NRM[N,3] polygon normal per loop, pidx[N]) -> UV[N,2]
# --------------------------------------------------------------------------------------
class UV:
    @staticmethod
    def box(s=1.0, offset=(0.0, 0.0, 0.0)):
        """Box projection, 1 UV unit = s meters (default 1 m texel scale)."""
        off = np.array(offset, np.float64)

        def f(P, NRM, pidx):
            P = P + off
            uv = np.zeros((len(P), 2))
            ax = np.argmax(np.abs(NRM), axis=1)
            sg = np.sign(NRM[np.arange(len(P)), ax])
            sg[sg == 0] = 1
            x, y, z = P[:, 0], P[:, 1], P[:, 2]
            m = ax == 0
            uv[m, 0] = y[m] * sg[m]; uv[m, 1] = z[m]
            m = ax == 1
            uv[m, 0] = -x[m] * sg[m]; uv[m, 1] = z[m]
            m = ax == 2
            uv[m, 0] = x[m]; uv[m, 1] = y[m] * sg[m]
            return uv / s
        return f

    @staticmethod
    def cyl(p0, p1, s=1.0, norm=False, radius=None, ref=None, v_norm=False):
        """Cylindrical projection around axis p0->p1.
        norm=True: u in 0..1 around; else u in meters (needs radius or uses actual).
        v in meters along axis (or 0..1 if v_norm)."""
        p0 = np.array(p0, np.float64); p1 = np.array(p1, np.float64)
        a = p1 - p0; L = np.linalg.norm(a); a = a / L
        if ref is None:
            ref = np.array((0, 0, 1.0)) if abs(a[2]) < 0.9 else np.array((0, -1.0, 0))
        e1 = np.array(ref, np.float64); e1 = e1 - a * e1.dot(a); e1 /= np.linalg.norm(e1)
        e2 = np.cross(a, e1)

        def f(P, NRM, pidx):
            d = P - p0
            h = d @ a
            r = d - np.outer(h, a)
            ang = np.arctan2(r @ e2, r @ e1)  # -pi..pi
            u = (ang + math.pi) / (2 * math.pi)
            # seam fix per polygon
            for p in np.unique(pidx):
                m = pidx == p
                uu = u[m]
                if uu.max() - uu.min() > 0.5:
                    uu[uu < 0.5] += 1.0
                    u[m] = uu
            if not norm:
                rad = radius if radius else float(np.median(np.linalg.norm(r, axis=1)))
                u = u * 2 * math.pi * rad / s
            v = h / L if v_norm else h / s
            uv = np.stack([u, v], axis=1)
            # caps (normal parallel to axis): planar
            capm = np.abs(NRM @ a) > 0.9
            if capm.any():
                uv[capm, 0] = (r[capm] @ e1) / s
                uv[capm, 1] = (r[capm] @ e2) / s
            return uv
        return f

    @staticmethod
    def planar(n=(0, -1, 0), s=None, rect=(0, 0, 1, 1), up=None, bounds=None):
        """Planar projection viewed against normal n (n = direction the face points).
        s=None -> normalise to part bounds (0..1 mapped into rect); else meters/s.
        bounds=(umin, vmin, umax, vmax) in projected meters to normalise against."""
        n = np.array(n, np.float64); n /= np.linalg.norm(n)
        if up is None:
            up = np.array((0, 0, 1.0)) if abs(n[2]) < 0.9 else np.array((0, 1.0, 0))
        up = np.array(up, np.float64); up = up - n * up.dot(n); up /= np.linalg.norm(up)
        right = np.cross(up, n)

        def f(P, NRM, pidx):
            u = P @ right; v = P @ up
            if s is not None:
                return np.stack([u / s, v / s], axis=1)
            if bounds is not None:
                u0, v0, u1, v1 = bounds
            else:
                u0, u1, v0, v1 = u.min(), u.max(), v.min(), v.max()
            uu = (u - u0) / max(u1 - u0, 1e-9); vv = (v - v0) / max(v1 - v0, 1e-9)
            r0, r1, r2, r3 = rect
            return np.stack([r0 + uu * (r2 - r0), r1 + vv * (r3 - r1)], axis=1)
        return f

    @staticmethod
    def scaled(fn, su=1.0, sv=1.0, ou=0.0, ov=0.0):
        """Wrap a projection: uv * (su, sv) + (ou, ov)."""
        def f(P, NRM, pidx):
            uv = fn(P, NRM, pidx)
            uv[:, 0] = uv[:, 0] * su + ou
            uv[:, 1] = uv[:, 1] * sv + ov
            return uv
        return f

    @staticmethod
    def fixed(u=0.5, v=0.5):
        def f(P, NRM, pidx):
            uv = np.zeros((len(P), 2)); uv[:, 0] = u; uv[:, 1] = v
            return uv
        return f


def _apply_uv(me, fn):
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    nl = len(me.loops)
    if nl == 0:
        return
    vidx = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', vidx)
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3).astype(np.float64)
    lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
    pidx = np.repeat(np.arange(len(me.polygons)), lt)
    pn = np.empty(len(me.polygons) * 3, np.float32); me.polygons.foreach_get('normal', pn)
    pn = pn.reshape(-1, 3).astype(np.float64)
    uv = fn(co[vidx], pn[pidx], pidx)
    me.uv_layers[0].data.foreach_set('uv', uv.astype(np.float32).ravel())


# --------------------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------------------
def V(*a):
    if len(a) == 1:
        return Vector(a[0])
    return Vector(a)


def rot_matrix(rot):
    """rot: None | (rx, ry, rz) degrees | Matrix | Euler"""
    if rot is None:
        return Matrix.Identity(4)
    if isinstance(rot, Matrix):
        return rot.to_4x4()
    return Euler([math.radians(r) for r in rot], 'XYZ').to_matrix().to_4x4()


def look_matrix(direction, up_hint=(0, 0, 1)):
    """3x3->4x4 rotation taking local +Z to `direction`."""
    d = Vector(direction).normalized()
    return d.to_track_quat('Z', 'X' if abs(d.z) > 0.999 else 'Y').to_matrix().to_4x4()


def arc_points(center, radius, a0, a1, n, plane='XZ'):
    """Points on an arc. plane 'XZ': angle measured from +X towards +Z. a in degrees."""
    c = Vector(center)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        ca, sa = math.cos(a), math.sin(a)
        if plane == 'XZ':
            pts.append(c + Vector((ca * radius, 0, sa * radius)))
        elif plane == 'YZ':
            pts.append(c + Vector((0, ca * radius, sa * radius)))
        else:
            pts.append(c + Vector((ca * radius, sa * radius, 0)))
    return pts


def fillet(points, radius, n=6):
    """Round the interior corners of a polyline with arcs of `radius` (n segments each)."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3 or radius <= 0:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        d0 = (p0 - p1).normalized(); d2 = (p2 - p1).normalized()
        ang = d0.angle(d2)
        if ang > math.pi - 1e-3:
            out.append(p1); continue
        t = radius / math.tan(ang / 2)
        t = min(t, (p0 - p1).length * 0.49, (p2 - p1).length * 0.49)
        a = p1 + d0 * t; b = p1 + d2 * t
        # quadratic-ish arc through bezier-like interpolation (good for small n)
        for k in range(n + 1):
            s = k / n
            q = (1 - s) ** 2 * a + 2 * (1 - s) * s * p1 + s * s * b
            out.append(q)
    out.append(pts[-1])
    return out


def circle2d(r, n, start=0.0):
    return [(r * math.cos(start + 2 * math.pi * i / n), r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def rect2d(w, h, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def rounded_rect2d(w, h, r, n=3, cx=0.0, cy=0.0):
    pts = []
    corners = [(cx + w / 2 - r, cy - h / 2 + r, -90), (cx + w / 2 - r, cy + h / 2 - r, 0),
               (cx - w / 2 + r, cy + h / 2 - r, 90), (cx - w / 2 + r, cy - h / 2 + r, 180)]
    for (x, y, a0) in corners:
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    return pts


def thicken2d(pts, t, closed=False):
    """Offset an open 2D polyline by +-t/2 along its normals -> closed outline."""
    P = [Vector((p[0], p[1])) for p in pts]
    n = len(P)
    normals = []
    for i in range(n):
        if i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        d.normalize()
        nn = Vector((-d.y, d.x))
        if 0 < i < n - 1:
            d0 = (P[i] - P[i - 1]).normalized()
            c = max(abs(nn.dot(Vector((-d0.y, d0.x)))), 0.3)
            nn = nn / c
        normals.append(nn)
    a = [tuple(P[i] + normals[i] * t / 2) for i in range(n)]
    b = [tuple(P[i] - normals[i] * t / 2) for i in range(n)]
    return a + b[::-1]


def polygon_area2d(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2


# --------------------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    return sc


class Part:
    __slots__ = ('obj', 'uv', 'bevel', 'seg', 'sharp', 'bevel_angle')


class Prop:
    """Accumulates parts (one material each), then finish() -> one mesh + empties."""

    def __init__(self, name, category='urban', mirror_x=False, desc='', origin='ground contact',
                 front='Unity +Z', preview=None):
        reset_scene()
        self.name = name
        self.category = category
        self.mirror_x = mirror_x
        self.desc = desc
        self.origin = origin
        self.front = front
        self.parts = []
        self.empties = []
        self.preview = dict(ground_z=0.0, wall=False, capsule=True, az=35.0, el=16.0,
                            res=1024, extra=[])
        if preview:
            self.preview.update(preview)
        self.notes = []
        self.col = bpy.context.scene.collection

    # ---------------- core part creation ----------------
    def _xf(self, v):
        v = Vector(v)
        if self.mirror_x:
            v = Vector((-v.x, v.y, v.z))
        return v

    def add_bmesh(self, bm, mat, uv='box', bevel='auto', seg=2, sharp=30.0, bevel_angle=None,
                  name=None, smooth=True):
        if self.mirror_x:
            bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.normal_update()
        me = bpy.data.meshes.new(name or f'{self.name}_part{len(self.parts)}')
        bm.to_mesh(me)
        bm.free()
        obj = bpy.data.objects.new(me.name, me)
        self.col.objects.link(obj)
        me.materials.append(get_mat(mat))
        if smooth:
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(sharp))
        else:
            me.shade_flat()
        p = Part()
        p.obj = obj
        if isinstance(uv, str):
            uv = {'box': UV.box(), 'none': None, 'front01': UV.planar((0, -1, 0)),
                  'top01': UV.planar((0, 0, 1))}[uv]
        p.uv = uv
        if bevel == 'auto':
            dims = obj.dimensions
            md = min([d for d in dims if d > 1e-5] or [0])
            bevel = 0.0 if md < 0.025 else min(max(md * 0.06, 0.003), 0.02)
        p.bevel = bevel or 0.0
        p.seg = seg
        p.sharp = sharp
        p.bevel_angle = bevel_angle if bevel_angle is not None else sharp
        self.parts.append(p)
        return obj

    # ---------------- primitives ----------------
    def box(self, size, loc=(0, 0, 0), rot=None, mat='M_Concrete', **kw):
        """Axis-aligned box of `size` centred at loc, optionally rotated (deg XYZ) about loc."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        M = Matrix.Translation(Vector(loc)) @ rot_matrix(rot)
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        return self.add_bmesh(bm, mat, **kw)

    def box_mm(self, mn, mx, mat='M_Concrete', **kw):
        mn = Vector(mn); mx = Vector(mx)
        return self.box(mx - mn, (mn + mx) / 2, mat=mat, **kw)

    def cyl(self, p0, p1, r, r1=None, seg=16, caps=True, mat='M_Galvanized', twist=0.0, **kw):
        """Cylinder / cone frustum from p0 (radius r) to p1 (radius r1)."""
        p0 = Vector(p0); p1 = Vector(p1)
        d = p1 - p0
        L = d.length
        bm = bmesh.new()
        r1 = r if r1 is None else r1
        bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r,
                              radius2=max(r1, 0.0), depth=L)
        bmesh.ops.translate(bm, vec=(0, 0, L / 2), verts=bm.verts)
        M = Matrix.Translation(p0) @ look_matrix(d) @ Matrix.Rotation(math.radians(twist), 4, 'Z')
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        kw.setdefault('sharp', max(35.0, 360.0 / seg + 12))
        if r1 <= 1e-5:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
        return self.add_bmesh(bm, mat, **kw)

    def sphere(self, loc, r, seg=16, rings=8, scale=(1, 1, 1), rot=None, mat='M_PlasticWhite', **kw):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
        bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
        M = Matrix.Translation(Vector(loc)) @ rot_matrix(rot)
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        kw.setdefault('sharp', 80.0)
        kw.setdefault('bevel', 0.0)
        return self.add_bmesh(bm, mat, **kw)

    def lathe(self, profile, seg=24, loc=(0, 0, 0), rot=None, mat='M_Concrete', cap_bottom=True,
              cap_top=True, start_angle=0.0, sweep=360.0, **kw):
        """Revolve profile [(r, z), ...] (bottom->top) around local Z, then rot/loc."""
        bm = bmesh.new()
        full = abs(sweep - 360.0) < 1e-6
        nseg = seg if full else seg + 1
        rings = []
        for (r, z) in profile:
            ring = []
            if r < 1e-6:
                ring = [bm.verts.new((0, 0, z))] * nseg
            else:
                for i in range(nseg):
                    a = math.radians(start_angle + sweep * i / seg)
                    ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
            rings.append(ring)
        for k in range(len(rings) - 1):
            A, B = rings[k], rings[k + 1]
            rng = range(seg) if full else range(nseg - 1)
            for i in rng:
                j = (i + 1) % nseg
                vs = [A[i], A[j], B[j], B[i]]
                uniq = []
                for v in vs:
                    if v not in uniq:
                        uniq.append(v)
                if len(uniq) >= 3:
                    try:
                        bm.faces.new(uniq)
                    except ValueError:
                        pass
        if full:
            if cap_bottom and profile[0][0] > 1e-6:
                f = bm.faces.new(list(reversed(rings[0])))
            if cap_top and profile[-1][0] > 1e-6:
                bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        M = Matrix.Translation(Vector(loc)) @ rot_matrix(rot)
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        kw.setdefault('sharp', 40.0)
        return self.add_bmesh(bm, mat, **kw)

    def sweep(self, path, profile, closed=True, caps=True, up=(0, 0, 1), mat='M_Galvanized',
              scales=None, **kw):
        """Sweep 2D profile [(s, t)] along path. Frame: side = up x tangent, (s->side, t->up).
        For a path along +X with up=Z: s -> +Y, t -> +Z."""
        pts = [Vector(p) for p in path]
        n = len(pts)
        T = []
        for i in range(n):
            if i == 0:
                t = pts[1] - pts[0]
            elif i == n - 1:
                t = pts[-1] - pts[-2]
            else:
                t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
            T.append(t.normalized())
        uph = Vector(up)
        if abs(T[0].dot(uph)) > 0.999:
            uph = Vector((1, 0, 0)) if abs(T[0].x) < 0.9 else Vector((0, 1, 0))
        N = [(uph - T[0] * uph.dot(T[0])).normalized()]
        for i in range(1, n):
            q = T[i - 1].rotation_difference(T[i])
            Ni = q @ N[-1]
            Ni = (Ni - T[i] * Ni.dot(T[i])).normalized()
            N.append(Ni)
        bm = bmesh.new()
        rings = []
        for i in range(n):
            side = N[i].cross(T[i]).normalized()
            miter_k = None; mf = 1.0
            if 0 < i < n - 1:
                tin = (pts[i] - pts[i - 1]).normalized(); tout = (pts[i + 1] - pts[i]).normalized()
                k = tout - tin
                if k.length > 1e-6:
                    ang = tin.angle(tout)
                    mf = 1.0 / max(math.cos(ang / 2), 0.25)
                    miter_k = k.normalized()
            sc = scales[i] if scales else 1.0
            ring = []
            for (s, t) in profile:
                o = (side * s + N[i] * t) * sc
                if miter_k is not None:
                    o = o + miter_k * (o.dot(miter_k) * (mf - 1.0))
                ring.append(bm.verts.new(pts[i] + o))
            rings.append(ring)
        m = len(profile)
        for i in range(n - 1):
            A, B = rings[i], rings[i + 1]
            rng = range(m) if closed else range(m - 1)
            for j in rng:
                k = (j + 1) % m
                bm.faces.new([A[j], A[k], B[k], B[j]])
        if caps and closed:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        kw.setdefault('sharp', 40.0)
        return self.add_bmesh(bm, mat, **kw)

    def pipe(self, path, r, seg=10, caps=True, mat='M_Galvanized', **kw):
        kw.setdefault('sharp', max(40.0, 360.0 / seg + 12))
        return self.sweep(path, circle2d(r, seg, math.pi / seg), closed=True, caps=caps, mat=mat, **kw)

    def prism(self, profile_yz, x0, x1, mat='M_Concrete', caps=True, **kw):
        """Extrude a closed 2D profile given in (y, z) along X from x0 to x1."""
        bm = bmesh.new()
        prof = list(profile_yz)
        if polygon_area2d(prof) < 0:
            prof = prof[::-1]
        A = [bm.verts.new((x0, y, z)) for (y, z) in prof]
        B = [bm.verts.new((x1, y, z)) for (y, z) in prof]
        m = len(prof)
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new([A[j], A[k], B[k], B[j]])
        if caps:
            bm.faces.new(list(reversed(A)))
            bm.faces.new(B)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self.add_bmesh(bm, mat, **kw)

    def extrude(self, outline, depth, axis='Y', offset=0.0, origin=(0, 0, 0), rot=None,
                mat='M_Galvanized', cap_front=True, cap_back=True, **kw):
        """Extrude a closed 2D outline. axis 'Y': outline in (x, z), from y=offset to offset+depth
        (front cap at y=offset faces -Y). axis 'Z': outline (x, y), from z=offset up.
        axis 'X': outline (y, z)."""
        bm = bmesh.new()
        pts = list(outline)
        if polygon_area2d(pts) < 0:
            pts = pts[::-1]

        def P(a, b, w):
            if axis == 'Y':
                return (a, w, b)
            if axis == 'Z':
                return (a, b, w)
            return (w, a, b)
        A = [bm.verts.new(P(a, b, offset)) for (a, b) in pts]
        B = [bm.verts.new(P(a, b, offset + depth)) for (a, b) in pts]
        m = len(pts)
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new([A[j], A[k], B[k], B[j]])
        if cap_front:
            bm.faces.new(list(reversed(A)) if axis != 'Y' else A)
        if cap_back:
            bm.faces.new(B if axis != 'Y' else list(reversed(B)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        M = Matrix.Translation(Vector(origin)) @ rot_matrix(rot)
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        return self.add_bmesh(bm, mat, **kw)

    def ngon(self, points, mat='M_SignFace', uv='front01', flip=False, **kw):
        """Single flat polygon from 3D points (CCW seen from the front side)."""
        bm = bmesh.new()
        vs = [bm.verts.new(Vector(p)) for p in points]
        f = bm.faces.new(vs if not flip else vs[::-1])
        kw.setdefault('bevel', 0.0)
        return self.add_bmesh(bm, mat, uv=uv, **kw)

    def poly(self, verts, faces, mat='M_Concrete', **kw):
        bm = bmesh.new()
        vs = [bm.verts.new(Vector(v)) for v in verts]
        for f in faces:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        return self.add_bmesh(bm, mat, **kw)

    def grid_surface(self, fn, nu, nv, mat='M_Concrete', **kw):
        """Surface from fn(u, v)->(x,y,z) for u,v in [0,1], nu x nv quads (normals: u x v)."""
        bm = bmesh.new()
        G = [[bm.verts.new(Vector(fn(i / nu, j / nv))) for j in range(nv + 1)] for i in range(nu + 1)]
        for i in range(nu):
            for j in range(nv):
                bm.faces.new([G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]])
        return self.add_bmesh(bm, mat, **kw)

    def torus(self, loc, R, r, seg=24, rseg=8, rot=None, mat='M_Rubber', arc=360.0, **kw):
        path = [Vector((R * math.cos(math.radians(arc * i / seg)), R * math.sin(math.radians(arc * i / seg)), 0))
                for i in range(seg + (0 if abs(arc - 360) < 1e-6 else 1))]
        bm = bmesh.new()
        rings = []
        for p in path:
            radial = Vector((p.x, p.y, 0)).normalized()
            ring = []
            for k in range(rseg):
                a = 2 * math.pi * k / rseg
                ring.append(bm.verts.new(p + radial * (r * math.cos(a)) + Vector((0, 0, r * math.sin(a)))))
            rings.append(ring)
        nr = len(rings)
        closed = abs(arc - 360) < 1e-6
        for i in range(nr if closed else nr - 1):
            A, B = rings[i], rings[(i + 1) % nr]
            for k in range(rseg):
                kk = (k + 1) % rseg
                bm.faces.new([A[k], B[k], B[kk], A[kk]])
        if not closed:
            bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        M = Matrix.Translation(Vector(loc)) @ rot_matrix(rot)
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        kw.setdefault('sharp', 60.0)
        kw.setdefault('bevel', 0.0)
        return self.add_bmesh(bm, mat, **kw)

    def empty(self, name, loc, rot=None, size=0.15):
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'ARROWS'
        e.empty_display_size = size
        e.location = self._xf(loc)
        if rot is not None:
            r = Euler([math.radians(a) for a in rot], 'XYZ')
            if self.mirror_x:
                r = Euler((r.x, -r.y, -r.z), 'XYZ')
            e.rotation_euler = r
        self.col.objects.link(e)
        self.empties.append(e)
        return e

    def note(self, s):
        self.notes.append(s)

    # ---------------- finishing ----------------
    def _bake_parts(self):
        dg = bpy.context.evaluated_depsgraph_get()
        for p in self.parts:
            o = p.obj
            if p.bevel > 0:
                m = o.modifiers.new('bevel', 'BEVEL')
                m.width = p.bevel
                m.segments = p.seg
                m.limit_method = 'ANGLE'
                m.angle_limit = math.radians(p.bevel_angle)
                m.harden_normals = True
                m.use_clamp_overlap = True
                m.miter_outer = 'MITER_ARC' if p.seg > 1 else 'MITER_SHARP'
            t = o.modifiers.new('tri', 'TRIANGULATE')
            t.min_vertices = 5
            t.quad_method = 'BEAUTY'
            t.ngon_method = 'BEAUTY'
            if hasattr(t, 'keep_custom_normals'):
                t.keep_custom_normals = True
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        for p in self.parts:
            o = p.obj
            ev = o.evaluated_get(dg)
            nm = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
            old = o.data
            o.modifiers.clear()
            o.data = nm
            bpy.data.meshes.remove(old)
            if p.uv is not None:
                _apply_uv(nm, p.uv)
            else:
                if not nm.uv_layers:
                    nm.uv_layers.new(name='UVMap')

    def _join(self):
        objs = [p.obj for p in self.parts]
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.name = self.name
        ob.data.name = self.name
        # dedupe material slots
        me = ob.data
        mats = list(me.materials)
        uniq = []
        remap = []
        for m in mats:
            if m not in uniq:
                uniq.append(m)
            remap.append(uniq.index(m))
        if len(uniq) != len(mats):
            mi = np.empty(len(me.polygons), np.int32)
            me.polygons.foreach_get('material_index', mi)
            mi = np.array(remap, np.int32)[mi]
            me.materials.clear()
            for m in uniq:
                me.materials.append(m)
            me.polygons.foreach_set('material_index', mi)
        # UV channel name
        if me.uv_layers:
            me.uv_layers[0].name = 'UVMap'
        return ob

    def finish(self):
        t0 = time.time()
        self._bake_parts()
        ob = self._join()
        for e in self.empties:
            e.parent = ob
            e.matrix_parent_inverse = Matrix.Identity(4)
        me = ob.data
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        bb = np.array([v.co[:] for v in me.vertices])
        mn = bb.min(axis=0); mx = bb.max(axis=0)
        # Unity space bbox: (-x, z, -y)
        u_min = [float(-mx[0]), float(mn[2]), float(-mx[1])]
        u_max = [float(-mn[0]), float(mx[2]), float(-mn[1])]
        meta = dict(
            name=self.name, category=self.category, desc=self.desc, origin=self.origin,
            front=self.front, file=f'{self.name}.fbx', tris=tris, verts=len(me.vertices),
            size_m=[round(u_max[i] - u_min[i], 3) for i in range(3)],
            unity_bbox_min=[round(v, 3) for v in u_min], unity_bbox_max=[round(v, 3) for v in u_max],
            materials=[m.name for m in me.materials],
            empties={e.name: [round(-e.location.x, 3), round(e.location.z, 3), round(-e.location.y, 3)]
                     for e in self.empties},
            notes=self.notes,
            textures=sorted({n.image.name for m in me.materials if m.node_tree
                             for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}),
        )
        if OPTIONS['export']:
            self._export(ob)
        with open(os.path.join(META_DIR, f'{self.name}.json'), 'w') as f:
            json.dump(meta, f, indent=1)
        if OPTIONS['preview']:
            render_preview(ob, self, os.path.join(PREVIEW_DIR, f'{self.name}.png'))
        print(f'[propkit] {self.name}: {tris} tris, size(Unity XYZ) {meta["size_m"]}, '
              f'mats {meta["materials"]}, empties {list(meta["empties"])}  ({time.time() - t0:.1f}s)')
        return meta

    def _export(self, ob):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        for e in self.empties:
            e.select_set(True)
        bpy.context.view_layer.objects.active = ob
        path = os.path.join(MODELS_DIR, f'{self.name}.fbx')
        _patch_fbx_texture_paths()
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
            axis_forward='-Z', axis_up='Y', apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
            bake_space_transform=True, use_mesh_modifiers=True, mesh_smooth_type='OFF',
            use_tspace=False, add_leaf_bones=False, path_mode='RELATIVE', embed_textures=False,
            use_custom_props=False, colors_type='NONE', bake_anim=False)


def _patch_fbx_texture_paths():
    """Make the FBX 'FileName' of textures the same relative path as 'RelativeFilename'
    (Blender normally embeds the absolute local path, e.g. /Users/<name>/...)."""
    try:
        from io_scene_fbx import export_fbx_bin as efb
        if getattr(efb, '_inkdrift_patched', False):
            return
        orig = efb._gen_vid_path

        def _gen_vid_path(img, scene_data):
            fname_abs, fname_rel = orig(img, scene_data)
            return fname_rel, fname_rel
        efb._gen_vid_path = _gen_vid_path
        efb._inkdrift_patched = True
    except Exception as ex:
        print('[propkit] could not patch FBX texture paths:', ex)


# --------------------------------------------------------------------------------------
# preview rendering
# --------------------------------------------------------------------------------------
def _preview_mat(name, hexc, rough=0.8):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = _principled(m)
    b.inputs['Base Color'].default_value = (*hex_lin(hexc), 1)
    b.inputs['Roughness'].default_value = rough
    return m


def _add_capsule(x, y, z, col):
    r = 0.22; h = 1.7
    me = bpy.data.meshes.new('ref_capsule')
    bm = bmesh.new()
    prof = []
    for i in range(7):
        a = -math.pi / 2 + (math.pi / 2) * i / 6
        prof.append((r * math.cos(a), r + r * math.sin(a)))
    for i in range(7):
        a = (math.pi / 2) * i / 6
        prof.append((r * math.cos(a), h - r + r * math.sin(a)))
    seg = 24
    rings = []
    for (rr, zz) in prof:
        if rr < 1e-6:
            rings.append([bm.verts.new((0, 0, zz))] * seg)
        else:
            rings.append([bm.verts.new((rr * math.cos(2 * math.pi * i / seg), rr * math.sin(2 * math.pi * i / seg), zz))
                          for i in range(seg)])
    for k in range(len(rings) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            vs = []
            for v in (rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                try:
                    bm.faces.new(vs)
                except ValueError:
                    pass
    bm.to_mesh(me); bm.free()
    me.shade_smooth()
    o = bpy.data.objects.new('ref_capsule', me)
    o.location = (x, y, z)
    me.materials.append(col)
    bpy.context.scene.collection.objects.link(o)
    return o


def _fit_camera(cam_obj, cam, pts, az, el, aspect=1.0):
    d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                -math.cos(math.radians(az)) * math.cos(math.radians(el)),
                math.sin(math.radians(el))))
    center = sum(pts, Vector()) / len(pts)
    rot = (-d).to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot.to_euler()
    R = rot.to_matrix()
    right = R @ Vector((1, 0, 0)); up = R @ Vector((0, 1, 0)); fwd = R @ Vector((0, 0, -1))
    tanx = math.tan(cam.angle / 2)
    tany = tanx / aspect if aspect >= 1 else tanx
    tanx = tanx if aspect >= 1 else tanx * aspect
    pos = center + d * 10
    for _ in range(4):
        # required distance so every point fits; then recentre
        need = 0.0
        xs = []; ys = []
        for p in pts:
            q = p - center
            x = q.dot(right); y = q.dot(up); z = q.dot(fwd)
            need = max(need, abs(x) / (tanx * 0.92) - z, abs(y) / (tany * 0.92) - z)
            xs.append(x); ys.append(y)
        pos = center - fwd * need
        # recentre using projected extents at that distance
        px = []; py = []
        for p in pts:
            q = p - pos
            z = q.dot(fwd)
            px.append(q.dot(right) / z); py.append(q.dot(up) / z)
        cx = (max(px) + min(px)) / 2; cy = (max(py) + min(py)) / 2
        center = center + right * cx * need + up * cy * need
    cam_obj.location = center - fwd * need
    cam.clip_start = max(0.01, need * 0.01)
    cam.clip_end = need * 10 + 100


def render_preview(ob, prop, path, az=None, el=None, res=None, capsule=None):
    pv = prop.preview
    az = pv['az'] if az is None else az
    el = pv['el'] if el is None else el
    res = pv['res'] if res is None else res
    capsule = pv['capsule'] if capsule is None else capsule
    sc = bpy.context.scene
    tmp = []
    gz = pv['ground_z']
    # bbox of prop + empties
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    gmat = _preview_mat('_pv_ground', '#D9D6CE', 0.95)
    me = bpy.data.meshes.new('_pv_ground')
    ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    S = max(25.0, ext * 4.0)
    gbm = bmesh.new()
    bmesh.ops.create_grid(gbm, x_segments=64, y_segments=64, size=S)
    bmesh.ops.translate(gbm, vec=((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, gz), verts=gbm.verts)
    gbm.to_mesh(me); gbm.free()
    me.materials.append(gmat)
    g = bpy.data.objects.new('_pv_ground', me); sc.collection.objects.link(g); tmp.append(g)
    if pv.get('wall'):
        wm = bpy.data.meshes.new('_pv_wall')
        wy = 0.002
        wx0, wx1 = min(xs) - 1.0, max(xs) + 1.0
        wz1 = max(zs) + 1.0
        wm.from_pydata([(wx0, wy, gz), (wx1, wy, gz), (wx1, wy, wz1), (wx0, wy, wz1)], [], [(0, 1, 2, 3)])
        wm.materials.append(_preview_mat('_pv_wall', '#B7B2A8', 0.95))
        w = bpy.data.objects.new('_pv_wall', wm); sc.collection.objects.link(w); tmp.append(w)
    fit = list(pts)
    if capsule:
        cx = min(xs) - 0.6
        cy = (min(ys) + max(ys)) / 2 if not pv.get('wall') else min(ys) - 0.4
        if pv.get('capsule_pos'):
            cx, cy = pv['capsule_pos']
        cap = _add_capsule(cx, cy, gz, _preview_mat('_pv_capsule', '#5B8BD9', 0.6))
        tmp.append(cap)
        fit += [Vector((cx + dx, cy + dy, gz + dz)) for dx in (-0.22, 0.22) for dy in (-0.22, 0.22) for dz in (0, 1.7)]
    cam = bpy.data.cameras.new('_pv_cam'); cam.lens_unit = 'FOV'; cam.angle = math.radians(30)
    co = bpy.data.objects.new('_pv_cam', cam); sc.collection.objects.link(co); tmp.append(co)
    _fit_camera(co, cam, fit, az, el)
    sc.camera = co
    sun = bpy.data.lights.new('_pv_sun', 'SUN'); sun.energy = 3.2; sun.angle = math.radians(3)
    so = bpy.data.objects.new('_pv_sun', sun); so.rotation_euler = (math.radians(48), 0, math.radians(-30))
    sc.collection.objects.link(so); tmp.append(so)
    fill = bpy.data.lights.new('_pv_fill', 'SUN'); fill.energy = 0.6
    fo = bpy.data.objects.new('_pv_fill', fill); fo.rotation_euler = (math.radians(70), 0, math.radians(150))
    sc.collection.objects.link(fo); tmp.append(fo)
    w = bpy.data.worlds.get('_pv_world') or bpy.data.worlds.new('_pv_world')
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = None
    for n in w.node_tree.nodes:
        if n.type == 'BACKGROUND':
            bg = n
    if bg:
        bg.inputs[0].default_value = (*hex_lin('#C9D3DD'), 1)
        bg.inputs[1].default_value = 0.9
    sc.world = w
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    sc.render.resolution_x = res; sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = 'ABSOLUTE'
    sc.render.line_thickness = 1.3
    try:
        vl = sc.view_layers[0]
        vl.use_freestyle = True
        fs = vl.freestyle_settings
        ls = fs.linesets[0] if fs.linesets else fs.linesets.new('ink')
        if ls.linestyle is None:
            ls.linestyle = bpy.data.linestyles.get('ink') or bpy.data.linestyles.new('ink')
        ls.select_by_visibility = True
        ls.select_silhouette = True; ls.select_border = True; ls.select_crease = True
        ls.linestyle.color = (0.04, 0.04, 0.07)
        ls.linestyle.thickness = 1.3
        fs.crease_angle = math.radians(140)
    except Exception as ex:
        print('[propkit] freestyle setup failed', ex)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for extra in pv.get('extra', []):
        # extra = (suffix, az, el) or (suffix, az, el, (min_xyz, max_xyz)) focus box (Blender coords)
        suf, a2, e2 = extra[:3]
        fpts = fit
        if len(extra) > 3:
            (x0, y0, z0), (x1, y1, z1) = extra[3]
            fpts = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        _fit_camera(co, cam, fpts, a2, e2)
        sc.render.filepath = os.path.join(PREVIEW_DIR, 'detail', os.path.basename(path).replace('.png', f'_{suf}.png'))
        bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)


def run_builders(module_name, names=None):
    import importlib, sys
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    mod = importlib.import_module(module_name)
    todo = [n for n, (fn, mn) in REGISTRY.items() if mn == mod.__name__]
    if names:
        todo = [n for n in todo if n in names]
        missing = [n for n in names if n not in todo]
        if missing:
            print('[propkit] unknown builders:', missing, 'available:', list(REGISTRY))
    failures = []
    for n in todo:
        fn = REGISTRY[n][0]
        try:
            print(f'[propkit] === building {n}')
            fn()
        except Exception:
            traceback.print_exc()
            failures.append(n)
    print('[propkit] DONE', module_name, 'built', len(todo) - len(failures), 'failed', failures)
    return failures
