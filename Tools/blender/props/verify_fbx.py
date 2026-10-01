"""Verify exported prop FBX files.
Run:  blender -b -P Tools/blender/props/verify_fbx.py -- [name ...]

For every FBX in Game/Assets/InkDrift/Models/Props:
 1. Parse the raw FBX (Blender's bundled parser) -> GlobalSettings (UpAxis, FrontAxis, UnitScaleFactor),
    every Model's Lcl Translation/Rotation/Scaling, geometry bounds; convert to Unity space
    (Unity: x -> -x on import, cm -> m by UnitScaleFactor/100) and compare to the build meta
    (previews/meta/<name>.json): size, ground at Y=0, identity rotation/scale, empties present.
 2. Re-import with Blender's FBX importer and check the bounding-box dimensions again.
Writes previews/verify_report.json and prints a summary table."""
import bpy, sys, os, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import propkit
from io_scene_fbx import parse_fbx

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def props(elem, name):
    for c in elem.elems:
        if c.id == b'Properties70':
            for p in c.elems:
                if p.props and p.props[0] == name.encode():
                    return p.props[4:]
    return None


def child(elem, name):
    for c in elem.elems:
        if c.id == name.encode():
            return c
    return None


def analyse(path):
    root, ver = parse_fbx.parse(path)
    gs = child(root, 'GlobalSettings')
    g = {k: props(gs, k)[0] for k in ('UpAxis', 'UpAxisSign', 'FrontAxis', 'FrontAxisSign', 'CoordAxis',
                                      'CoordAxisSign', 'UnitScaleFactor')}
    objs = child(root, 'Objects')
    models = {}
    geoms = []
    for e in objs.elems:
        if e.id == b'Model':
            nm = e.props[1].split(b'\x00')[0].decode()
            models[nm] = dict(type=e.props[2].decode(),
                              t=list(props(e, 'Lcl Translation') or (0, 0, 0)),
                              r=list(props(e, 'Lcl Rotation') or (0, 0, 0)),
                              s=list(props(e, 'Lcl Scaling') or (1, 1, 1)))
        elif e.id == b'Geometry':
            v = child(e, 'Vertices')
            arr = np.array(v.props[0], np.float64).reshape(-1, 3)
            geoms.append(arr)
    return g, models, geoms


def main():
    files = sorted(f for f in os.listdir(propkit.MODELS_DIR) if f.endswith('.fbx'))
    if argv:
        files = [f for f in files if f[:-4] in argv]
    report = {}
    bad = 0
    for f in files:
        name = f[:-4]
        path = os.path.join(propkit.MODELS_DIR, f)
        meta_p = os.path.join(propkit.META_DIR, name + '.json')
        meta = json.load(open(meta_p)) if os.path.exists(meta_p) else None
        g, models, geoms = analyse(path)
        issues = []
        if not (g['UpAxis'] == 1 and g['UpAxisSign'] == 1):
            issues.append(f'up axis {g["UpAxis"]}/{g["UpAxisSign"]}')
        unit = g['UnitScaleFactor'] / 100.0          # file units -> meters
        mesh_models = [m for m in models.values() if m['type'] == 'Mesh']
        for nm, m in models.items():
            if any(abs(a) > 1e-3 for a in m['r']):
                issues.append(f'{nm} rotation {m["r"]}')
            if any(abs(a - 1.0) > 1e-4 for a in m['s']):
                issues.append(f'{nm} scale {m["s"]}')
        allv = np.concatenate(geoms) * unit
        # geometry is in the mesh model's local space; root mesh has identity transform
        root_t = np.array(mesh_models[0]['t']) * unit if mesh_models else np.zeros(3)
        allv = allv + root_t
        # Unity flips X
        uv = allv.copy(); uv[:, 0] *= -1
        mn = uv.min(axis=0); mx = uv.max(axis=0)
        size = (mx - mn)
        if meta:
            if np.max(np.abs(size - np.array(meta['size_m']))) > 0.01:
                issues.append(f'size {size.round(3).tolist()} != meta {meta["size_m"]}')
            if np.max(np.abs(mn - np.array(meta['unity_bbox_min']))) > 0.01:
                issues.append(f'bbox min {mn.round(3).tolist()} != meta {meta["unity_bbox_min"]}')
            missing = [e for e in meta['empties'] if e not in models]
            if missing:
                issues.append(f'missing empties {missing}')
            for e, pos in meta['empties'].items():
                if e in models:
                    t = np.array(models[e]['t']) * unit
                    t[0] *= -1
                    if np.max(np.abs(t - np.array(pos))) > 0.01:
                        issues.append(f'empty {e} at {t.round(3).tolist()} != {pos}')
        # Blender re-import round trip
        propkit.reset_scene()
        bpy.ops.import_scene.fbx(filepath=path, axis_forward='-Z', axis_up='Y')
        obs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        pts = np.array([list(o.matrix_world @ v.co) for o in obs for v in o.data.vertices])
        bmn = pts.min(axis=0); bmx = pts.max(axis=0)
        bsize = [float(bmx[0] - bmn[0]), float(bmx[2] - bmn[2]), float(bmx[1] - bmn[1])]
        if meta and np.max(np.abs(np.array(bsize) - np.array(meta['size_m']))) > 0.01:
            issues.append(f'reimport size {np.round(bsize, 3).tolist()}')
        report[name] = dict(ok=not issues, issues=issues, unit_scale_factor=g['UnitScaleFactor'],
                            unity_size=size.round(3).tolist(), unity_min=mn.round(3).tolist(),
                            reimport_size_xyz=np.round(bsize, 3).tolist(), n_models=len(models),
                            tris=meta['tris'] if meta else None)
        bad += bool(issues)
        print(f'{"OK " if not issues else "BAD"} {name:34s} unity size {np.round(size, 2).tolist()} '
              f'min {np.round(mn, 2).tolist()} usf={g["UnitScaleFactor"]} models={len(models)} {issues}')
    out = os.path.join(propkit.PREVIEW_DIR, 'verify_report.json')
    old = json.load(open(out)) if os.path.exists(out) and argv else {}
    old.update(report)
    json.dump(old, open(out, 'w'), indent=1)
    print(f'VERIFY: {len(files) - bad}/{len(files)} OK')


main()
