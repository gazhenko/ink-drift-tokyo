"""Mesh a car body SDF outside Blender (multiprocessing fork works in a plain interpreter, not inside Blender).

    Tools/.venv/bin/python Tools/cars/procedural/sdfmesh.py <car_id> <h_mm> <out.npz>

Writes V (model coords s,x,z; half car x >= ~0) and Q (quads) to out.npz.
"""
import importlib
import os
import sys

sys.dont_write_bytecode = True  # keep Tools/cars free of __pycache__
import time

for _k in ("OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_k] = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

from body import CarBody, CustomBody  # noqa: E402
from cutmesh import centers, cut, quads_to_csr  # noqa: E402
from mesher import mesh_sdf  # noqa: E402


def main():
    cid, hmm, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    t0 = time.time()
    spec = importlib.import_module("specs." + cid).spec()
    body = (CustomBody if "sdf" in spec["body"] else CarBody)(spec["body"])
    lo, hi = body.bounds()
    V, Q = mesh_sdf(body, lo, hi, hmm / 1000.0)
    if "--raw" in sys.argv:
        np.savez(out, V=V.astype(np.float64), Q=Q.astype(np.int64))
        print(f"[sdfmesh] {cid}: raw {len(V)} verts {len(Q)} quads in {time.time() - t0:.1f}s -> {out}", flush=True)
        return
    idx, off = quads_to_csr(Q)
    t1 = time.time()
    Pa = V.copy()
    for name, fn, slot in body.regions():
        Pa = V.copy()
        Pa[:, 1] = np.abs(Pa[:, 1])
        V, idx, off = cut(V, idx, off, fn(Pa))
    C = centers(V, idx, off)
    mats = body.classify(C)
    print(f"[sdfmesh] cut + classify {len(off) - 1} polys in {time.time() - t1:.1f}s", flush=True)
    np.savez(out, V=V.astype(np.float64), idx=idx, off=off, mats=np.array(mats, dtype="U16"))
    print(f"[sdfmesh] {cid}: {len(V)} verts {len(off) - 1} polys in {time.time() - t0:.1f}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
