#!/usr/bin/env python3
"""Personal odds vs real outcomes: compare two calib_personal_real.py outputs on the positions both cover (matched by
player, game, stage tile, target and the order within that group). Log-loss, Brier and AUC per target multiple (2x, 4x),
by tier, plus a game-clustered bootstrap of the log-loss difference.
usage: hm_pers_compare.py A.tsv B.tsv"""
import collections, math, sys
import numpy as np

def load(path):
    rows = collections.defaultdict(list)
    with open(path) as f:
        h = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(h, line.rstrip('\n').split('\t')))
            if r['personal'] in ('None', 'nan', ''): continue
            rows[(r['player'], r['game'], r['top'], r['mult'], r['target'])].append((float(r['personal']), int(r['reached']), r['tier']))
    return rows

def auc(p, y):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / max(1, n1 * n0)

def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    for mult in ('2', '4'):
        pa, pb, y, g, tier = [], [], [], [], []
        for k in A:
            if k[3] != mult or k not in B: continue
            n = min(len(A[k]), len(B[k]))
            for i in range(n):
                pa.append(A[k][i][0]); pb.append(B[k][i][0]); y.append(A[k][i][1]); g.append(k[0] + '/' + k[1]); tier.append(A[k][i][2])
        pa, pb, y = np.clip(pa, 1e-4, 1 - 1e-4), np.clip(pb, 1e-4, 1 - 1e-4), np.array(y)
        g = np.array(g); tier = np.array(tier)
        ll = lambda p, yy: float(-(yy * np.log(p) + (1 - yy) * np.log(1 - p)).mean())
        br = lambda p, yy: float(((p - yy) ** 2).mean())
        print(f"{mult}x: {len(y)} common positions, {len(set(g))} games, observed {y.mean():.3f}; mean predicted A {pa.mean():.3f} B {pb.mean():.3f}")
        print(f"   log-loss A {ll(pa, y):.4f} B {ll(pb, y):.4f} | Brier A {br(pa, y):.4f} B {br(pb, y):.4f} | AUC A {auc(pa, y):.3f} B {auc(pb, y):.3f}")
        for t in ('novice', 'intermediate', 'strong'):
            s = tier == t
            if s.sum() < 100: continue
            print(f"   {t:12s} n={s.sum():6d} obs {y[s].mean():.3f} pred A {pa[s].mean():.3f} B {pb[s].mean():.3f}  log-loss A {ll(pa[s], y[s]):.4f} B {ll(pb[s], y[s]):.4f}")
        # game-clustered bootstrap of the log-loss difference (B - A)
        games = sorted(set(g)); idx = {k: np.where(g == k)[0] for k in games}
        rng = np.random.RandomState(0); d = []
        la = -(y * np.log(pa) + (1 - y) * np.log(1 - pa)); lb = -(y * np.log(pb) + (1 - y) * np.log(1 - pb))
        for _ in range(500):
            sel = np.concatenate([idx[games[i]] for i in rng.randint(0, len(games), len(games))])
            d.append(lb[sel].mean() - la[sel].mean())
        print(f"   log-loss B - A: {np.mean(d):+.4f}, 90% interval [{np.quantile(d, 0.05):+.4f}, {np.quantile(d, 0.95):+.4f}] (game bootstrap)")

if __name__ == '__main__':
    main()
