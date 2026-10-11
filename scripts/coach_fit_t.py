#!/usr/bin/env python3
"""Coach test, step 2: the softmax players' temperature per tier and stage group, by maximum likelihood of the human
moves under soft_move's own model (relative 1-ply losses from `build/coach --mode fit`; a player with temperature t
plays move m with probability ~ exp(-loss(m) / t)). Players are pooled per (tier, group); also per player, to show
the spread. A small epsilon-random mixture (lapse rate) is fitted too: humans make moves no softmax over 1-ply values
explains (finger slips, misreads), and a pure softmax would otherwise need a high t to cover them.
usage: coach_fit_t.py [results/coach/fit_out.tsv results/coach/fit_meta.tsv]"""
import math, sys, collections
import numpy as np

def load(out_path, meta_path):
    meta = {}
    with open(meta_path) as f:
        next(f)
        for line in f:
            i, g, tier, pl, top = line.rstrip('\n').split('\t')
            meta[i] = (g, tier, pl, int(top))
    rows = []
    with open(out_path) as f:
        next(f)
        for line in f:
            p = line.rstrip('\n').split('\t')
            i, played = p[0], p[1]
            l = [float(x) for x in p[2:6]]
            k = 'URDL'.index(played) if played in 'URDL' else -1
            if k < 0 or math.isnan(l[k]): continue
            if sum(not math.isnan(x) for x in l) < 2: continue
            rows.append((i, k, l))
    return meta, rows

def nll(L, P, t, eps):
    # L: (n,4) losses (nan illegal), P: played index; mixture (1-eps) softmax + eps uniform over legal moves
    legal = ~np.isnan(L)
    Z = np.where(legal, np.exp(-np.nan_to_num(L, nan=0.0) / t), 0.0)
    ps = Z[np.arange(len(P)), P] / Z.sum(1)
    nl = legal.sum(1)
    p = (1 - eps) * ps + eps / nl
    return -np.log(np.maximum(p, 1e-300)).sum()

def fit(L, P, with_eps=True):
    best = (1e300, None, None)
    for t in np.exp(np.linspace(math.log(1e-4), math.log(3.0), 60)):
        for eps in ([0.0, 0.01, 0.02, 0.05, 0.1, 0.2] if with_eps else [0.0]):
            v = nll(L, P, t, eps)
            if v < best[0]: best = (v, t, eps)
    return best

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'results/coach/fit_out.tsv'
    meta_path = sys.argv[2] if len(sys.argv) > 2 else 'results/coach/fit_meta.tsv'
    meta, rows = load(out_path, meta_path)
    cells = collections.defaultdict(list)
    for i, k, l in rows:
        g, tier, pl, top = meta[i]
        if g == '-': continue
        cells[(g, tier)].append((k, l, pl))
    print("group tier          n      t(pure)  t(mix)   eps    match1ply  players: median t (mix-free) [IQR]")
    res = {}
    for (g, tier) in sorted(cells):
        xs = cells[(g, tier)]
        if len(xs) < 300: continue
        L = np.array([l for _, l, _ in xs]); P = np.array([k for k, _, _ in xs])
        _, t0, _ = fit(L, P, False)
        _, t1, e1 = fit(L, P, True)
        best1 = np.nanargmin(np.where(np.isnan(L), np.inf, L), axis=1)
        match = float((best1 == P).mean())
        per = collections.defaultdict(list)
        for k, l, pl in xs: per[pl].append((k, l))
        pts = []
        for pl, ys in per.items():
            if len(ys) < 200: continue
            Lp = np.array([l for _, l in ys]); Pp = np.array([k for k, _ in ys])
            pts.append(fit(Lp, Pp, False)[1])
        q = np.percentile(pts, [25, 50, 75]) if pts else [float('nan')] * 3
        print(f"{g}    {tier:12s} {len(xs):6d}   {t0:.4f}   {t1:.4f}  {e1:.2f}   {match:.3f}     "
              f"{len(pts)}: {q[1]:.4f} [{q[0]:.4f}-{q[2]:.4f}]")
        res[(g, tier)] = (t0, t1, e1)

if __name__ == '__main__':
    main()
