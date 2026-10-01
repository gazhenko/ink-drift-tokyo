#!/usr/bin/env python3
"""Minimal binary-FBX reader to check what Unity will see (file space, independent of Blender's importer).
Run: Tools/.venv/bin/python Tools/blender/foliage/fbx_inspect.py [files...]
Reports per file: FBX version, axis settings, UnitScaleFactor, every Model's Lcl Translation/Rotation/Scaling,
geometry extents in metres (vertices * UnitScaleFactor/100), presence of normals/colours/UV layers, materials,
and texture RelativeFilenames (and that FileName contains no absolute path)."""
import glob
import os
import struct
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..", "Game", "Assets", "InkDrift", "Models", "Trees"))


class Node:
    __slots__ = ("name", "props", "children")

    def __init__(self, name, props, children):
        self.name, self.props, self.children = name, props, children

    def find(self, name):
        return [c for c in self.children if c.name == name]

    def first(self, name):
        r = self.find(name)
        return r[0] if r else None


def _read_prop(d, o):
    t = chr(d[o]); o += 1
    if t == "Y":
        return struct.unpack_from("<h", d, o)[0], o + 2
    if t == "C":
        return bool(d[o]), o + 1
    if t == "I":
        return struct.unpack_from("<i", d, o)[0], o + 4
    if t == "F":
        return struct.unpack_from("<f", d, o)[0], o + 4
    if t == "D":
        return struct.unpack_from("<d", d, o)[0], o + 8
    if t == "L":
        return struct.unpack_from("<q", d, o)[0], o + 8
    if t in "fdlib":
        n, enc, clen = struct.unpack_from("<III", d, o); o += 12
        raw = d[o:o + clen]; o += clen
        if enc == 1:
            raw = zlib.decompress(raw)
        dt = {"f": "<f4", "d": "<f8", "l": "<i8", "i": "<i4", "b": "u1"}[t]
        return np.frombuffer(raw, dt, n), o
    if t in "SR":
        n = struct.unpack_from("<I", d, o)[0]; o += 4
        v = d[o:o + n]
        return (v.decode("utf8", "replace") if t == "S" else v), o + n
    raise ValueError("bad prop type %r" % t)


def _read_node(d, o, v64):
    if v64:
        end, nprops, plen = struct.unpack_from("<QQQ", d, o); o += 24
    else:
        end, nprops, plen = struct.unpack_from("<III", d, o); o += 12
    nlen = d[o]; o += 1
    if end == 0:
        return None, o
    name = d[o:o + nlen].decode(); o += nlen
    props = []
    for _ in range(nprops):
        p, o = _read_prop(d, o)
        props.append(p)
    children = []
    null = 25 if v64 else 13
    while o < end - null + 0 and o < end:
        if o + null <= end and d[o:o + null] == b"\0" * null and o + null == end:
            break
        c, o = _read_node(d, o, v64)
        if c is None:
            break
        children.append(c)
    return Node(name, props, children), end


def read_fbx(path):
    d = open(path, "rb").read()
    assert d[:20] == b"Kaydara FBX Binary  ", "not a binary FBX"
    ver = struct.unpack_from("<I", d, 23)[0]
    v64 = ver >= 7500
    o, top = 27, []
    while o < len(d):
        n, o = _read_node(d, o, v64)
        if n is None:
            break
        top.append(n)
    return ver, Node("root", [], top), d


def p70(node):
    out = {}
    pr = node.first("Properties70") if node else None
    for p in (pr.children if pr else []):
        out[p.props[0]] = p.props[4:] if len(p.props) > 4 else []
    return out


def inspect(path):
    ver, root, raw = read_fbx(path)
    gs = p70(root.first("GlobalSettings"))
    usf = gs.get("UnitScaleFactor", [1.0])[0]
    objs = root.first("Objects")
    rep = dict(file=os.path.basename(path), version=ver, UpAxis=gs.get("UpAxis", [None])[0],
               UpAxisSign=gs.get("UpAxisSign", [None])[0], FrontAxis=gs.get("FrontAxis", [None])[0],
               FrontAxisSign=gs.get("FrontAxisSign", [None])[0], UnitScaleFactor=usf, models=[], geoms=[],
               materials=[], textures=[])
    for m in objs.find("Model"):
        pp = p70(m)
        rep["models"].append(dict(name=m.props[1].split("\x00")[0], T=pp.get("Lcl Translation", [0, 0, 0]),
                                  R=pp.get("Lcl Rotation", [0, 0, 0]), S=pp.get("Lcl Scaling", [1, 1, 1])))
    for g in objs.find("Geometry"):
        v = g.first("Vertices").props[0].reshape(-1, 3) * usf / 100.0
        layers = [c.name for c in g.children if c.name.startswith("Layer")]
        col = g.first("LayerElementColor")
        cvals = None
        if col is not None:
            cv = col.first("Colors").props[0].reshape(-1, 4)
            cvals = [round(float(cv[:, i].min()), 2) for i in range(3)] + [round(float(cv[:, i].max()), 2) for i in range(3)]
        rep["geoms"].append(dict(name=g.props[1].split("\x00")[0], min=v.min(0).round(3).tolist(),
                                 max=v.max(0).round(3).tolist(), normals=g.first("LayerElementNormal") is not None,
                                 uv=len(g.find("LayerElementUV")), colors=cvals, layers=layers))
    for m in objs.find("Material"):
        rep["materials"].append(m.props[1].split("\x00")[0])
    for t in objs.find("Texture"):
        fn = t.first("FileName").props[0] if t.first("FileName") else ""
        rf = t.first("RelativeFilename").props[0] if t.first("RelativeFilename") else ""
        rep["textures"].append(dict(rel=rf, abs_ok=not fn.startswith("/") and ":" not in fn))
    rep["home_leak"] = os.path.expanduser("~").encode() in raw
    return rep


def main(files):
    files = files or sorted(glob.glob(os.path.join(MODEL_DIR, "*.fbx")))
    bad = 0
    for f in files:
        r = inspect(f)
        issues = []
        if (r["UpAxis"], r["UpAxisSign"]) != (1, 1):
            issues.append("up axis not +Y")
        for m in r["models"]:
            if any(abs(x) > 1e-4 for x in m["R"]) or any(abs(x - 1) > 1e-4 for x in m["S"]) or any(abs(x) > 1e-4 for x in m["T"]):
                issues.append(f"model {m['name']} transform T{m['T']} R{m['R']} S{m['S']}")
        for g in r["geoms"]:
            if not g["normals"] or not g["uv"] or g["colors"] is None:
                issues.append(f"{g['name']} missing normals/uv/colours")
            if g["min"][1] > 0.01 or g["min"][1] < -0.5 * max(1, g["max"][1]):
                issues.append(f"{g['name']} base y {g['min'][1]}")
        for t in r["textures"]:
            if not t["abs_ok"] or not t["rel"].startswith("Textures/") or not os.path.exists(os.path.join(MODEL_DIR, t["rel"])):
                issues.append(f"texture {t['rel']}")
        if r["home_leak"]:
            issues.append("absolute home path inside file")
        bad += bool(issues)
        geo = "; ".join(f"{g['name']}: y[{g['min'][1]:.2f}..{g['max'][1]:.2f}] x[{g['min'][0]:.1f}..{g['max'][0]:.1f}] "
                        f"col RGB min{g['colors'][:3]} max{g['colors'][3:]}" for g in r["geoms"])
        print(("OK   " if not issues else "FAIL ") + f"{r['file']} v{r['version']} unit={r['UnitScaleFactor']} "
              f"mats={r['materials']} tex={len(r['textures'])} | {geo}" + ("" if not issues else "  ISSUES: " + "; ".join(issues)))
    print(f"SUMMARY {len(files) - bad}/{len(files)} ok")


if __name__ == "__main__":
    main(sys.argv[1:])
