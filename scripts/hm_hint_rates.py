#!/usr/bin/env python3
"""How often real players would get analyze's hint (workstream hm2): per decision of the curated data (hm's data.npz),
the human move model's move probabilities at the player's own skill theta for the phase (maximum likelihood over their
moves in the phase, as a review fits it), each move's your_cost (weights/calib/model.txt lossmap_own of its relative
search loss), error risk = sum p x your_cost, hint = risk >= the phase's threshold. Hints per 100 moves by tier and
phase (median over players with >= 100 moves in the phase).
usage: hm_hint_rates.py [--hint 0.05,0.08,0.08,-1]"""
import collections, math, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit
from hm_skill_real import load_model, TGRID

def interp(m, x):
    xs, ys = np.array(m[0::2]), np.array(m[1::2])
    y = np.interp(x, xs, ys)
    beyond = x > xs[-1]
    y[beyond] = np.minimum(1.0, ys[-1] * x[beyond] / xs[-1])
    return y

def main():
    thr = [float(x) for x in (sys.argv[sys.argv.index('--hint') + 1] if '--hint' in sys.argv else '0.05,0.08,0.08,-1').split(',')]
    own = {}
    for line in open('weights/calib/model.txt'):
        p = line.split()
        if p and p[0] == 'lossmap_own': own[int(p[1])] = [float(x) for x in p[2:]]
    D = dict(np.load('results/hm/data.npz'))
    R = np.load('results/hm/recent.npz'); D['_recent'] = (R['cnt'], R['hl'])
    B = hm_fit.build(D, 'full_tied_death_recent')
    M = load_model('results/hm/human_model_v2.txt')
    names_v, names_s, names_h = B['names']
    Vw = B['V'] @ M['wv']; Sw = B['S'] @ np.array([M['ws'][k] for k in names_s]); Hw = B['H'] @ np.array([M['wh'][k] for k in names_h])
    legal, played = B['legal'], B['played']
    L = np.nan_to_num(D['losss'], nan=0.0)
    phase = np.where(D['mx'] <= 512, 0, np.where(D['mx'] <= 2048, 1, np.where(D['mx'] <= 8192, 2, 3)))
    ok = legal.sum(1) >= 2
    eps, ga, gb = M['eps'], M['ga'], M['gb']
    def probs(idx, th):
        z = np.exp(th) * Vw[idx] + np.exp(ga + gb * th) * Sw[idx] + Hw[idx]
        lg = legal[idx]
        z = np.where(lg, z, -1e30); z = z - z.max(1, keepdims=True)
        e = np.exp(z) * lg
        return (1 - eps) * e / e.sum(1, keepdims=True) + eps / lg.sum(1, keepdims=True)
    groups = collections.defaultdict(list)
    for i in np.where(ok)[0]: groups[(int(D['player'][i]), int(phase[i]))].append(i)
    tiers = {int(D['player'][i]): int(D['tier'][i]) for i in range(len(played))}
    names = ['novice', 'intermediate', 'strong', 'expert']
    rates = collections.defaultdict(list)
    hards = collections.defaultdict(list)
    for (pl, ph), idx in groups.items():
        if len(idx) < 100 or ph not in own or thr[ph] < 0: continue
        idx = np.array(idx)
        ll = np.zeros(len(TGRID))
        for g, th in enumerate(TGRID):
            P = probs(idx, th)
            ll[g] = np.log(np.maximum(1e-300, P[np.arange(len(idx)), played[idx]])).sum()
        th = TGRID[ll.argmax()]
        P = probs(idx, th)
        C = interp(own[ph], L[idx].ravel()).reshape(L[idx].shape) * legal[idx]
        risk = (P * C).sum(1)
        rates[(tiers[pl], ph)].append(100.0 * (risk >= thr[ph]).mean())
        # hard moments (the review's): habits aside, error risk >= 1% and the reference move found by < 20%
        z = np.exp(th) * Vw[idx] + np.exp(ga + gb * th) * Sw[idx]
        lg = legal[idx]; z = np.where(lg, z, -1e30); z = z - z.max(1, keepdims=True)
        e = np.exp(z) * lg
        P0 = (1 - eps) * e / e.sum(1, keepdims=True) + eps / lg.sum(1, keepdims=True)
        ref = np.where(lg, L[idx], 1e9).argmin(1)
        r0 = (P0 * C).sum(1)
        hard = (r0 >= 0.01) & (P0[np.arange(len(idx)), ref] < 0.2)
        hards[(tiers[pl], ph)].append((100.0 * hard.mean(), hard.sum(), (hard & (played[idx] == ref)).sum()))
    print(f"hints per 100 moves at the thresholds {thr} (median over players [range]; players with >= 100 moves in the phase)")
    for (t, ph), xs in sorted(rates.items()):
        print(f"   {names[t]:12s} phase {ph}: {len(xs):3d} players  median {np.median(xs):5.2f}  [{min(xs):.2f} - {max(xs):.2f}]")
    print("hard moments per 100 moves (median over players) and the share found (pooled)")
    for (t, ph), xs in sorted(hards.items()):
        tot = sum(x[1] for x in xs); fnd = sum(x[2] for x in xs)
        print(f"   {names[t]:12s} phase {ph}: median {np.median([x[0] for x in xs]):5.2f} per 100  found {fnd}/{tot} "
              f"({100.0 * fnd / max(1, tot):.0f}%)")

if __name__ == '__main__':
    main()
