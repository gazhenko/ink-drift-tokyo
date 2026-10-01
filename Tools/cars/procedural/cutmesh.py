"""Split a polygon mesh along the zero level of scalar fields (exact material borders).

Mesh representation: V (n,3) float, polys as CSR: idx (m,) vertex indices, off (k+1,) offsets.
"""
import numpy as np


def quads_to_csr(Q):
    Q = np.asarray(Q, np.int64)
    return Q.ravel().copy(), np.arange(0, Q.size + 1, Q.shape[1], dtype=np.int64)


def cut(V, idx, off, f):
    """split polygons crossed by the zero level of f (values at V). Returns V2, idx2, off2."""
    f = np.where(f == 0, 1e-12, f)
    neg = f < 0
    sz = np.diff(off)
    # polygons with mixed signs
    nneg = np.add.reduceat(neg[idx].astype(np.int64), off[:-1])
    mixed = np.nonzero((nneg > 0) & (nneg < sz))[0]
    if len(mixed) == 0:
        return V, idx, off
    newV = []
    nV = len(V)
    edge_vert = {}
    keep = np.ones(len(sz), bool)
    keep[mixed] = False
    out_polys = []

    def xvert(a, b):
        key = (a, b) if a < b else (b, a)
        v = edge_vert.get(key)
        if v is None:
            t = f[a] / (f[a] - f[b])
            newV.append(V[a] + t * (V[b] - V[a]))
            v = nV + len(newV) - 1
            edge_vert[key] = v
        return v

    for p in mixed:
        vs = idx[off[p]:off[p + 1]].tolist()
        k = len(vs)
        crossings = 0
        A, B = [], []
        for i in range(k):
            a, b = vs[i], vs[(i + 1) % k]
            (A if neg[a] else B).append(a)
            if neg[a] != neg[b]:
                c = xvert(a, b)
                A.append(c)
                B.append(c)
                crossings += 1
        if crossings != 2 or len(A) < 3 or len(B) < 3:
            out_polys.append(vs)  # saddle / degenerate: keep as is
            continue
        out_polys.append(A)
        out_polys.append(B)
    V2 = np.concatenate([V, np.array(newV).reshape(-1, 3)]) if newV else V
    kept_sz = sz[keep]
    kept_idx = idx[np.repeat(keep, sz)]
    new_sz = np.array([len(q) for q in out_polys], np.int64)
    new_idx = np.array([i for q in out_polys for i in q], np.int64)
    idx2 = np.concatenate([kept_idx, new_idx])
    off2 = np.concatenate([[0], np.cumsum(np.concatenate([kept_sz, new_sz]))]).astype(np.int64)
    return V2, idx2, off2


def centers(V, idx, off):
    sz = np.diff(off)
    s = np.add.reduceat(V[idx], off[:-1], axis=0)
    return s / sz[:, None]
