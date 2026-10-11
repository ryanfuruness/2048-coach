#!/usr/bin/env python3
"""Workstream hm3: personal-odds models vs real outcomes on COMMON positions (rows written by scripts/hm_skill_real.py:
per position-target the prediction with the key from the review t (skill map), from theta directly (theta map) and from
t predicted by theta (out of fold)). Per model x mapping: log-loss, Brier, AUC, mean predicted vs observed, by tier;
game-clustered bootstrap of the log-loss difference vs the reference (first model, given mapping).
usage: hm3_compare.py REF_MAPPING NAME=ROWS.tsv ...   (REF_MAPPING: t | theta | tt; the first model is the reference)"""
import collections, csv, sys
import numpy as np

def load(path):
    d = {}
    with open(path) as f:
        for r in csv.DictReader(f, delimiter='\t'):
            d[(r['video'], r['segment'], r['ply'], r['mult'])] = r
    return d

def auc(p, y):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / max(1, n1 * n0)

def main():
    refmap = sys.argv[1]
    models = [(a.split('=')[0], load(a.split('=')[1])) for a in sys.argv[2:]]
    keys = set(models[0][1])
    for _, d in models[1:]: keys &= set(d)
    keys = sorted(keys)
    rng = np.random.default_rng(3)
    for mult in ('2', '4'):
        ks = [k for k in keys if k[3] == mult]
        if not ks: continue
        y = np.array([int(models[0][1][k]['y']) for k in ks], float)
        g = np.array([int(models[0][1][k]['game']) for k in ks])
        tier = np.array([models[0][1][k]['tier'] for k in ks])
        print(f"== {mult}x: {len(ks)} common position-targets, {len(set(g))} games, observed {y.mean():.3f}")
        gu = np.unique(g); gi = {x: np.where(g == x)[0] for x in gu}
        boots = [np.concatenate([gi[x] for x in rng.choice(gu, len(gu))]) for _ in range(400)]
        ref = None
        for name, d in models:
            for mp in ('t', 'theta', 'tt'):
                p = np.clip(np.array([float(d[k]['p_' + mp]) for k in ks]), 1e-6, 1 - 1e-6)
                ll = -(y * np.log(p) + (1 - y) * np.log(1 - p))
                if ref is None and mp == refmap: ref = ll
                diff = ''
                if ref is not None and not (name == models[0][0] and mp == refmap):
                    ds = [ll[b].mean() - ref[b].mean() for b in boots]
                    lo, hi = np.percentile(ds, [5, 95])
                    diff = f"  diff {ll.mean() - ref.mean():+.3f} [{lo:+.3f}, {hi:+.3f}]"
                by = '  '.join(f"{t[:3]} {p[tier == t].mean():.3f}/{y[tier == t].mean():.3f} ll{ll[tier == t].mean():.3f}"
                               for t in ('novice', 'intermediate', 'strong') if (tier == t).any())
                print(f"   {name:10s} {mp:5s} ll {ll.mean():.3f} Brier {((p - y) ** 2).mean():.3f} AUC {auc(p, y):.3f} "
                      f"mean {p.mean():.3f}{diff}\n        {by}")

if __name__ == '__main__':
    main()
