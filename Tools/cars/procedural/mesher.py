"""Narrow-band SDF sampling + naive surface nets (quads) + Newton projection onto the iso-surface.

    verts, quads = mesh_sdf(fn, lo, hi, h)

fn(P) takes an (N,3) float64 array and returns (N,) signed distances (negative inside).
"""
import math
import multiprocessing as mp
import os
import time

import numpy as np

_FN = None
NPROC = max(1, min(8, (os.cpu_count() or 4) - 1))


def _work(args):
    lo, idx, h = args
    return _FN(lo + idx * h).astype(np.float32)


def _work_pts(P):
    return _FN(P)


def peval(fn, P, batch=200_000):
    """evaluate fn over P (N,3) in parallel (fork)"""
    global _FN
    if len(P) < 2 * batch or NPROC == 1:
        return fn(P)
    _FN = fn
    chunks = [P[i:i + batch] for i in range(0, len(P), batch)]
    ctx = mp.get_context("fork")
    with ctx.Pool(NPROC) as pool:
        res = pool.map(_work_pts, chunks)
    return np.concatenate(res)


def _log(*a):
    print("[mesher]", *a, flush=True)


def sample_grid(fn, lo, hi, h, block=8, band=1.0, batch=1_500_000, log=_log):
    lo = np.asarray(lo, float)
    hi = np.asarray(hi, float)
    nb = np.ceil((hi - lo) / (h * block)).astype(int)
    n = nb * block + 1
    H = h * block
    t0 = time.time()
    # coarse nodes
    gi = [np.arange(nb[a] + 1) * H + lo[a] for a in range(3)]
    C = np.stack(np.meshgrid(*gi, indexing="ij"), -1).reshape(-1, 3)
    Fc = peval(fn, C).reshape(nb + 1)
    # blocks needing fine evaluation
    corners = [Fc[a:a + nb[0], b:b + nb[1], c:c + nb[2]] for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    mn = np.minimum.reduce([np.abs(x) for x in corners])
    sgn_any_neg = np.logical_or.reduce([x < 0 for x in corners])
    sgn_any_pos = np.logical_or.reduce([x >= 0 for x in corners])
    act = (mn < band * H * math.sqrt(3)) | (sgn_any_neg & sgn_any_pos)
    F = np.empty(tuple(n), np.float32)
    # fill inactive blocks with the sign of their centre coarse value
    cen = np.sign(np.mean(np.stack(corners), axis=0))
    cen[cen == 0] = 1
    F[:] = np.repeat(np.repeat(np.repeat(np.pad(cen, ((0, 1), (0, 1), (0, 1)), mode="edge"), block, 0), block, 1),
                     block, 2)[:n[0], :n[1], :n[2]].astype(np.float32)
    bi = np.argwhere(act)
    off = np.stack(np.meshgrid(np.arange(block + 1), np.arange(block + 1), np.arange(block + 1), indexing="ij"),
                   -1).reshape(-1, 3)
    per = len(off)
    step = max(1, 150_000 // per)
    nev = 0
    global _FN
    _FN = fn
    jobs = []
    for k in range(0, len(bi), step):
        b = bi[k:k + step]
        jobs.append((b[:, None, :] * block + off[None, :, :]).reshape(-1, 3))
    ctx = mp.get_context("fork")
    with ctx.Pool(NPROC) as pool:
        for idx, v in zip(jobs, pool.imap(_work, [(lo, j, h) for j in jobs], chunksize=1)):
            F[idx[:, 0], idx[:, 1], idx[:, 2]] = v
            nev += len(idx)
    log(f"grid {tuple(n)} h={h * 1000:.1f}mm, active blocks {len(bi)}/{act.size}, {nev / 1e6:.1f}M evals, "
        f"{time.time() - t0:.1f}s")
    return F


def surface_nets(F, lo, h):
    nx, ny, nz = F.shape
    inside = F < 0
    c0 = inside[:-1, :-1, :-1]
    any_in = c0.copy()
    all_in = c0.copy()
    for a in (0, 1):
        for b in (0, 1):
            for c in (0, 1):
                if a == b == c == 0:
                    continue
                v = inside[a:nx - 1 + a, b:ny - 1 + b, c:nz - 1 + c]
                any_in |= v
                all_in &= v
    active = any_in & ~all_in
    del any_in, all_in
    ci = np.nonzero(active)
    del active
    ci = [x.astype(np.int64) for x in ci]
    nc = len(ci[0])
    pos = np.zeros((nc, 3))
    cnt = np.zeros(nc)
    edges = [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0)), ((0, 0, 1), (1, 0, 1)), ((0, 1, 1), (1, 1, 1)),
             ((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0)), ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1)),
             ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1))]
    for a, b in edges:
        fa = F[ci[0] + a[0], ci[1] + a[1], ci[2] + a[2]].astype(np.float64)
        fb = F[ci[0] + b[0], ci[1] + b[1], ci[2] + b[2]].astype(np.float64)
        m = (fa < 0) != (fb < 0)
        t = np.where(m, fa / np.where(m, fa - fb, 1.0), 0.0)
        p = np.array(a, float)[None, :] + t[:, None] * (np.array(b, float) - np.array(a, float))[None, :]
        pos[m] += p[m]
        cnt[m] += 1
    pos = pos / np.maximum(cnt, 1)[:, None] + np.stack(ci, 1)
    verts = np.asarray(lo, float) + pos * h
    lin = (ci[0] * (ny - 1) + ci[1]) * (nz - 1) + ci[2]

    def vid(a, b, c):
        key = (a * (ny - 1) + b) * (nz - 1) + c
        return np.searchsorted(lin, key)

    quads = []
    # x edges
    e = inside[:-1, 1:-1, 1:-1] != inside[1:, 1:-1, 1:-1]
    i, j, k = [x.astype(np.int64) for x in np.nonzero(e)]
    j += 1
    k += 1
    fl = inside[i, j, k]
    q = np.stack([vid(i, j - 1, k - 1), vid(i, j, k - 1), vid(i, j, k), vid(i, j - 1, k)], 1)
    q[~fl] = q[~fl][:, ::-1]
    quads.append(q)
    # y edges
    e = inside[1:-1, :-1, 1:-1] != inside[1:-1, 1:, 1:-1]
    i, j, k = [x.astype(np.int64) for x in np.nonzero(e)]
    i += 1
    k += 1
    fl = inside[i, j, k]
    q = np.stack([vid(i - 1, j, k - 1), vid(i - 1, j, k), vid(i, j, k), vid(i, j, k - 1)], 1)
    q[~fl] = q[~fl][:, ::-1]
    quads.append(q)
    # z edges
    e = inside[1:-1, 1:-1, :-1] != inside[1:-1, 1:-1, 1:]
    i, j, k = [x.astype(np.int64) for x in np.nonzero(e)]
    i += 1
    j += 1
    fl = inside[i, j, k]
    q = np.stack([vid(i - 1, j - 1, k), vid(i, j - 1, k), vid(i, j, k), vid(i - 1, j, k)], 1)
    q[~fl] = q[~fl][:, ::-1]
    quads.append(q)
    return verts, np.concatenate(quads)


def _proj_eval(P):
    eps = _EPS
    E = np.eye(3) * eps
    f = _FN(P)
    g = np.stack([(_FN(P + E[a]) - _FN(P - E[a])) / (2 * eps) for a in range(3)], 1)
    return f, g


_EPS = 0.002


def project(fn, V, h, iters=3, batch=60_000):
    global _FN, _EPS
    _FN = fn
    _EPS = h * 0.35
    V = V.copy()
    ctx = mp.get_context("fork")
    for it in range(iters):
        chunks = [V[k:k + batch] for k in range(0, len(V), batch)]
        with ctx.Pool(NPROC) as pool:
            res = pool.map(_proj_eval, chunks)
        for k, (P, (f, g)) in zip(range(0, len(V), batch), zip(chunks, res)):
            gg = np.maximum((g * g).sum(1), 1e-8)
            step = -(f / gg)[:, None] * g
            ln = np.linalg.norm(step, axis=1)
            lim = 0.6 * h
            step *= np.minimum(1.0, lim / np.maximum(ln, 1e-12))[:, None]
            V[k:k + len(P)] = P + step
    return V


def mesh_sdf(fn, lo, hi, h, block=8, band=1.0, proj_iters=3, log=_log):
    t0 = time.time()
    F = sample_grid(fn, lo, hi, h, block, band, log=log)
    V, Q = surface_nets(F, lo, h)
    del F
    log(f"surface nets: {len(V)} verts, {len(Q)} quads ({time.time() - t0:.1f}s)")
    if proj_iters:
        V = project(fn, V, h, proj_iters)
        log(f"projected ({time.time() - t0:.1f}s)")
    return V, Q
