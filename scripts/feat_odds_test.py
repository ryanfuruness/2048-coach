#!/usr/bin/env python3
"""Do board concepts predict the engine's outcome beyond the value? Logistic models for P(reach T) on handover rows
(engine-future positions): base (log2 sum bins) + u vs base + u + concept features (corner, chain length, exposed
cells, trapped tiles, biggest tile off-corner distance), held-out games. Python ports of explain.h's features."""
import sys, math, numpy as np
PATH = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]

def cell_of(j, p):
    c = PATH[p]; rr, cc = c // 4, c % 4
    if j & 1: cc = 3 - cc
    if j & 2: rr = 3 - rr
    if j >= 4: rr, cc = cc, rr
    return rr * 4 + cc

def feats(h):
    b = [int(c, 16) for c in h]
    mx = max(b)
    corner = any(b[c] == mx for c in (0, 3, 12, 15))
    best = 0
    for j in range(8):
        if b[cell_of(j, 0)] != mx: continue
        prev, k = 99, 0
        for p in range(16):
            v = b[cell_of(j, p)]
            if v == 0 or v >= prev: break
            prev = v; k += 1
        best = max(best, k)
    big = max(6, mx - 3)
    exposed = trapped = 0
    for c in range(16):
        r, k = divmod(c, 4)
        nb = [b[c + d] for d, ok in ((-1, k > 0), (1, k < 3), (-4, r > 0), (4, r < 3)) if ok]
        if b[c] == 0 and any(v >= big for v in nb): exposed += 1
        if 0 < b[c] <= 3 and sum(v >= 7 for v in nb) >= 2: trapped += 1
    dist = min(min(c // 4, 3 - c // 4) + min(c % 4, 3 - c % 4) for c in range(16) if b[c] == mx)
    return [float(corner), best, exposed, trapped, dist]

def logistic(X, y, lam=1.0, iters=60):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + lam * w
        H = (X * (p * (1 - p))[:, None]).T @ X + lam * np.eye(X.shape[1])
        st = np.linalg.solve(H, g); w -= st
        if np.max(np.abs(st)) < 1e-7: break
    return w

rows = []
for path in sys.argv[1:]:
    hdr = None
    for line in open(path):
        t = line.rstrip('\n').split('\t')
        if hdr is None: hdr = {k: i for i, k in enumerate(t)}; continue
        if 'engine_future' in hdr and t[hdr['engine_future']] != '1': continue
        if t[hdr['switch']] != '1': continue
        rows.append((float(t[hdr['sum']]), int(t[hdr['max']]), float(t[hdr['value']]), int(t[hdr['final_max']]),
                     feats(t[hdr['board']]), hash((path, t[hdr['game']])) & 0xffff))
print(len(rows), 'handover rows')
s = np.log2([r[0] for r in rows]); v = np.array([r[2] for r in rows])
edges = [6, 9, 11, 13, 14, 15, 16.5]
B = np.array([[1.0 if lo <= x < hi else 0.0 for lo, hi in zip(edges, edges[1:])] for x in s])
vb = np.array([v[B[:, k] > 0].mean() if (B[:, k] > 0).any() else 1 for k in range(B.shape[1])])
u = v / np.maximum(B @ vb, 1) - 1
F = np.array([r[4] for r in rows]); F = (F - F.mean(0)) / np.maximum(F.std(0), 1e-9)
gid = np.array([r[5] for r in rows]); test = gid % 5 == 0
for T in (8192, 16384, 32768):
    m = np.array([r[1] < T for r in rows]); y = np.array([float(r[3] >= T) for r in rows])
    out = []
    for name, X in (('base', B), ('base+u', np.hstack([B, u[:, None]])), ('base+u+features', np.hstack([B, u[:, None], F]))):
        w = logistic(X[m & ~test], y[m & ~test], lam=3.0)
        p = 1 / (1 + np.exp(-np.clip(X[m & test] @ w, -30, 30)))
        yt = y[m & test]
        ll = -np.mean(yt * np.log(np.maximum(p, 1e-9)) + (1 - yt) * np.log(np.maximum(1 - p, 1e-9)))
        out.append(f"{name} {ll:.4f}")
        if name == 'base+u+features':
            coef = w[-5:]
    print(f"T={T}: n={int(m.sum())} base rate {y[m].mean():.3f} held-out log-loss: " + ', '.join(out) +
          "  | feature coefs (corner, chain, exposed, trapped, corner_dist): " + ' '.join(f"{c:+.2f}" for c in coef))
