#!/usr/bin/env python3
"""Held-out fit of the human move model with fixed weights (workstream hm2): per player, the skill theta fitted on the
first half of their decisions (grid, as the review), negative log-likelihood per decision on the second half, by stage
group (max tile <= 512, 1024-2048, 4096-8192, 16384+) and for tile sums >= 20480 (where best_v6b's late networks
change the 1-ply values); and the predicted vs observed rate of moves losing >= 15% (search loss) per 100 decisions.
usage: hm_late_eval.py DATA.npz MODEL.txt [MODEL_LATE.txt]   (MODEL_LATE: value hinge for tile sums >= 20480)"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit
from hm_skill_real import load_model, TGRID

def terms(D, M, ML=None):
    B = hm_fit.build(D, 'full_tied_death_recent')
    names_v, names_s, names_h = B['names']
    Vw = B['V'] @ M['wv']
    if ML is not None:
        late = D['tsum'] >= 20480
        Vw[late] = B['V'][late] @ ML['wv']
    Sw = B['S'] @ np.array([M['ws'][k] for k in names_s]); Hw = B['H'] @ np.array([M['wh'][k] for k in names_h])
    return Vw, Sw, Hw, B['legal'], B['played']

def main():
    D = dict(np.load(sys.argv[1]))
    R = np.load(sys.argv[1].replace('data.npz', 'recent.npz')); D['_recent'] = (R['cnt'], R['hl'])
    M = load_model(sys.argv[2]); ML = load_model(sys.argv[3]) if len(sys.argv) > 3 else None
    Vw, Sw, Hw, legal, played = terms(D, M, ML)
    eps, ga, gb = M['eps'], M['ga'], M['gb']
    n = len(played)
    def logp(idx, th):
        z = np.exp(th) * Vw[idx] + np.exp(ga + gb * th) * Sw[idx] + Hw[idx]
        lg = legal[idx]; z = np.where(lg, z, -1e30); z = z - z.max(1, keepdims=True)
        e = np.exp(z) * lg
        return np.log(np.maximum(1e-300, (1 - eps) * e / e.sum(1, keepdims=True) + eps / lg.sum(1, keepdims=True)))
    order = np.lexsort((D['ply'], D['seg'], D['video']))
    stage = np.where(D['mx'] <= 512, 0, np.where(D['mx'] <= 2048, 1, np.where(D['mx'] <= 8192, 2, 3)))
    late = D['tsum'] >= 20480
    big = np.nan_to_num(D['losss'], nan=0.0) >= 0.15
    nll = np.full(n, np.nan); pbig = np.full(n, np.nan)
    for p in np.unique(D['player']):
        ix = order[D['player'][order] == p]
        a, b = ix[:len(ix) // 2], ix[len(ix) // 2:]
        if len(a) < 20: continue
        ll = [logp(a, th)[np.arange(len(a)), played[a]].sum() for th in TGRID]
        th = TGRID[int(np.argmax(ll))]
        L = logp(b, th)
        nll[b] = -L[np.arange(len(b)), played[b]]
        pbig[b] = (np.exp(L) * big[b] * legal[b]).sum(1)
    ok = ~np.isnan(nll)
    print(f"{sys.argv[1]} with {sys.argv[2]}{' + ' + sys.argv[3] if ML else ''}: held-out nll {nll[ok].mean():.4f} "
          f"({ok.sum()} decisions)  by stage " + ' '.join(f"{nll[ok & (stage == g)].mean():.4f}" for g in range(4)) +
          f"  sum>=20480 {nll[ok & late].mean():.4f} (n={int((ok & late).sum())})")
    tiers = ['novice', 'intermediate', 'strong', 'expert']
    for t in range(4):
        for g in (2, 3):
            s = ok & (D['tier'] == t) & (stage == g)
            if s.sum() < 300: continue
            print(f"   {tiers[t]:12s} stage {g}: moves losing >= 15% per 100: predicted {100 * pbig[s].mean():.2f} "
                  f"observed {100 * big[s][np.arange(s.sum()), played[s]].mean():.2f}  (n={int(s.sum())})")

if __name__ == '__main__':
    main()
