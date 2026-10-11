#!/usr/bin/env python3
"""Human move model (workstream hm): fit a model on all players and export it for the C++ policy (src/human.h) as a
text file: 'wv k1 w1 k2 w2 ...' (hinge knots and weights of the value part), 'ws NAME w' per structure feature,
'wh NAME w' per habit, 'eps', 'gab ga gb' (tied structure skill), and per player 'player THETA TIER NAME', plus tier
medians 'tier T THETA'.
usage: hm_export.py MODEL OUT.txt"""
import sys, numpy as np, torch
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit

def main():
    model, out = sys.argv[1], sys.argv[2]
    D = dict(np.load('results/hm/data.npz'))
    R = np.load('results/hm/recent.npz'); D['_recent'] = (R['cnt'], R['hl'])
    m, B, T = hm_fit.fit_all(D, model)
    nv, ns, nh = B['names']
    with open(out, 'w') as f:
        f.write(f'# human move model {model} (scripts/hm_fit.py, all {len(D["played"])} clean decisions, '
                f'{len(D["players"])} players)\n')
        f.write('wv ' + ' '.join(f'{k} {w:.6f}' for k, w in zip(hm_fit.KNOTS, m.wv.detach().numpy())) + '\n')
        for a, w in zip(ns, m.ws.detach().numpy()): f.write(f'ws {a} {w:.6f}\n')
        for a, w in zip(nh, m.wh.detach().numpy()): f.write(f'wh {a} {w:.6f}\n')
        f.write(f'eps {float(torch.sigmoid(m.leps)):.6g}\n')
        if m.gab is not None: f.write(f'gab {float(m.gab[0]):.6f} {float(m.gab[1]):.6f}\n')
        th = m.theta.detach().numpy()
        tiers = ['novice', 'intermediate', 'strong', 'expert']
        for p in range(len(D['players'])):
            t = int(np.bincount(D['tier'][D['player'] == p] + 1).argmax()) - 1
            f.write(f'player {th[p]:.4f} {tiers[t] if t >= 0 else "?"} {D["players"][p]}\n')
        for t in range(4):
            ps = np.unique(D['player'][D['tier'] == t])
            f.write(f'tier {tiers[t]} {np.median(th[ps]):.4f} {np.quantile(th[ps], 0.25):.4f} {np.quantile(th[ps], 0.75):.4f}\n')
    print(open(out).read())

if __name__ == '__main__':
    main()
