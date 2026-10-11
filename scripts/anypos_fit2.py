#!/usr/bin/env python3
"""Odds correction for odd positions with a value hinge AND formation features (workstream anypos).

    z_T += B(s)·dslope · u + B(s)·dhinge · min(0, u - U0) + sum_j B(s)·G_j · x_j     (same for every target T)

B(s) = the model's hat basis on log2 tile sum; corrections live only on knots >= KMIN (early positions are repaired by
the engine whatever their shape); x = formation features of the engine move's afterstate (explain.h, as analyze
--features prints them): exposed cells next to big tiles, trapped small tiles, big tiles off the edge, the biggest tile
out of its corner, a short chain, the biggest tile's distance from its corner. The base rates (u = 0, x = 0) and the
chain rule's base ratios stay as installed. Validation: leave one category out (odd set A), 5 folds of the real
positions, and the independent odd set B (other seed, three unseen categories).
usage: anypos_fit2.py [--u0 -0.15] [--lam 0.01] [--feats exposed,trapped,center,corner,chain,corner_dist] [--write F]"""
import argparse, collections, json, math, os, sys
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(__file__))
from anypos_odds import Model  # noqa: E402
from anypos_feats import feats as board_feats  # noqa: E402

D = 'results/anypos'
def crowd(f):  # 0 on a nearly empty board (any shape can be repaired there), 1 on a full one
    return min(1.0, max(0.0, 1.0 - f.get('empty', 0) / 12.0))

FEATS = {  # name -> x(features, odds inputs); x = 0 for a sane snake position
    'exposed': lambda f, oi: f.get('exposed', 0) / 4.0,
    'trapped': lambda f, oi: f.get('trapped', 0) / 2.0,
    'center': lambda f, oi: f.get('center', 0) / 2.0 * crowd(f),
    'corner': lambda f, oi: (1.0 - f.get('corner', 1)) * crowd(f),
    'chain': lambda f, oi: max(0, 5 - f.get('chain', 5)) / 5.0,
    'chainshare': lambda f, oi: max(0.0, 1.0 - f.get('chain_ranks', 0) / max(1.0, oi['sum'])) * crowd(f),
    'corner_dist': lambda f, oi: f.get('corner_dist', 0) / 3.0 * crowd(f),
    # gated versions: zero inside the range real positions occupy (exposed <= 2 cells, trapped <= 1 tile, the biggest
    # tile at most one step from its corner), so real positions keep the installed odds
    'exposed_g': lambda f, oi: max(0, f.get('exposed', 0) - 2) / 2.0,
    'trapped_g': lambda f, oi: max(0, f.get('trapped', 0) - 1) / 2.0,
    'corner_g': lambda f, oi: max(0, f.get('corner_dist', 0) - 1) / 2.0 * crowd(f),
    'far_g': lambda f, oi: max(0, f.get('far', 0) - 1) / 3.0,  # big tiles stranded far from the others
    'far': lambda f, oi: f.get('far', 0) / 3.0,
    'far_g3': lambda f, oi: max(0, f.get('far', 0) - 2) / 3.0,
}

def engine_feats(a):
    """explain.h features + the board-level 'far' of the engine move's afterstate (the board the odds value is taken
    from: analyze computes a position's odds from its best move's afterstate)."""
    em = a.get('engine_move')
    for mv in a.get('moves', []):
        if mv['move'] == em: return {**mv.get('features', {}), **board_feats(mv['after'])}
    return {}

def odd_pairs(base, pred_jsonl, truth_prefix, stages):
    pos = [l.rstrip('\n').split('\t') for l in open(f'{D}/{base}.tsv')][1:]
    pred = [json.loads(l) for l in open(pred_jsonl)]
    out = []
    for R in stages:
        tf = f'{D}/{truth_prefix}_r{R}.tsv'
        if not os.path.exists(tf): continue
        idx = [int(x) for x in open(f'{D}/{base}_r{R}.idx').read().split()]
        t = [l.rstrip('\n').split('\t') for l in open(tf)]
        h = {k: i for i, k in enumerate(t[0])}
        for r in t[1:]:
            g = idx[int(r[h['pos']])]
            oi = pred[g].get('odds_in')
            if not oi: continue
            for k in (1, 2):
                T = 1 << (R + k)
                if f'p{T}' not in h or R + k > 15: continue
                out.append(dict(cat=pos[g][1], stage=R, k=k, T=T, y=float(r[h[f'p{T}']]), n=int(r[h['n']]), oi=oi,
                                f=engine_feats(pred[g]), key=f'{base}:{g}', g=g))
    return out

def human_pairs():
    rows = [l.rstrip('\n').split('\t') for l in open(f'{D}/human_truth.tsv')][1:]
    pred = [json.loads(l) for l in open(f'{D}/human_pred.jsonl')]
    out = []
    for i, (r, a) in enumerate(zip(rows, pred)):
        oi = a.get('odds_in')
        if not oi or a.get('game_over'): continue
        out.append(dict(cat=r[0], stratum=r[1], stage=int(math.log2(oi['max'])), k=0, T=int(r[2]), y=float(r[4]),
                        n=int(r[5]), oi=oi, f=engine_feats(a), key=f'h:{i}', g=i))
    return out

class Fit:
    def __init__(self, m, u0, feats, kmin=3, hinge=True, value=True):
        self.m, self.u0, self.feats, self.hinge, self.value = m, u0, feats, hinge and value, value
        self.T = sorted(m.target)
        self.nk = len(m.knots)
        self.act = list(range(kmin, self.nk))  # knots that carry corrections
        self.na = len(self.act)

    def nparams(self):
        return self.na * ((1 if self.value else 0) + (1 if self.hinge else 0) + len(self.feats))

    def prep(self, pairs):
        m, P = self.m, []
        for q in pairs:
            oi = q['oi']
            B = np.array(m.hats(math.log2(max(oi['sum'], 2.0))))[self.act]
            ts = [T for T in self.T if T > oi['max']]
            if q['T'] not in ts: continue
            zs = [m.z(T, oi['sum'], oi['value'])[0] for T in ts]
            u = m.z(ts[0], oi['sum'], oi['value'])[1]
            avg = max(1.0, float(np.array(m.hats(math.log2(max(oi['sum'], 2.0)))) @ np.array(m.vbar)))
            base = [m.prob(T, oi['sum'], avg) for T in ts]
            x = np.array([FEATS[n](q['f'], oi) for n in self.feats])
            P.append(dict(B=B, u=u, h=min(0.0, u - self.u0), x=x, ts=ts, zs=zs, base=base, surv=oi['survival'],
                          j=ts.index(q['T']), y=q['y'], w=q['n'] / 64.0, q=q))
        return P

    def shift(self, p, th):
        """The correction of z for pair p (the same for every target)."""
        c = th.reshape(-1, self.na) @ p['B']  # per term: coefficient at this tile sum
        d, i = 0.0, 0
        if self.value: d += c[0] * p['u']; i = 1
        if self.hinge: d += c[1] * p['h']; i = 2
        if len(self.feats): d += float(c[i:] @ p['x'])
        return d

    def predict(self, P, th):
        out = np.empty(len(P))
        for n, p in enumerate(P):
            d = self.shift(p, th)
            prev, prev_base = -1.0, -1.0
            for i in range(p['j'] + 1):
                z = p['zs'][i] + d
                q = 1 / (1 + math.exp(-max(-30, min(30, z))))
                b = p['base'][i]
                if prev >= 0 and prev_base > 0: q = min(q, prev * min(1.0, b / prev_base))
                if prev >= 0: q = min(q, prev)
                prev, prev_base = q, b
            out[n] = prev * p['surv']
        return out

    def loss(self, th, P, lam):
        p = np.clip(self.predict(P, th), 1e-4, 1 - 1e-4)
        y = np.array([q['y'] for q in P]); w = np.array([q['w'] for q in P])
        return float((w * -(y * np.log(p) + (1 - y) * np.log(1 - p))).sum() / w.sum()) + lam * float((th ** 2).mean())

    def fit(self, P, lam):
        r = minimize(self.loss, np.zeros(self.nparams()), args=(P, lam), method='L-BFGS-B',
                     options=dict(maxiter=600, maxfun=40000))
        return r.x

def metrics(p, P):
    y = np.array([q['y'] for q in P]); p = np.clip(p, 1e-4, 1 - 1e-4)
    return (float(np.mean(np.abs(p - y))), float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p)))),
            float(np.mean(p)), float(np.mean(y)))

def show(title, groups, P, p0, p1, lab1):
    print(title)
    for g, ix in groups:
        if not ix: continue
        sub = [P[i] for i in ix]
        a, b = metrics(p0[ix], sub), metrics(p1[ix], sub)
        print(f"    {str(g):24s} {len(ix):4d} meas {a[3]:.3f} | installed {a[2]:.3f} MAE {a[0]:.3f} LL {a[1]:.3f} | "
              f"{lab1} {b[2]:.3f} MAE {b[0]:.3f} LL {b[1]:.3f}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=f'{D}/model_installed.txt')
    ap.add_argument('--u0', type=float, default=-0.15)
    ap.add_argument('--lam', type=float, default=0.01)
    ap.add_argument('--feats', default='exposed,trapped,center,corner,chain,corner_dist')
    ap.add_argument('--no-hinge', action='store_true')
    ap.add_argument('--no-value', action='store_true', help='no value terms (formation features only)')
    ap.add_argument('--kmin', type=int, default=3)
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--write')
    a = ap.parse_args()
    feats = [f for f in a.feats.split(',') if f]
    m = Model(a.model)
    F = Fit(m, a.u0, feats, a.kmin, not a.no_hinge, not a.no_value)
    A = odd_pairs('pos', f'{D}/pred.jsonl', 'truth', range(9, 15))
    Bt = odd_pairs('posB', f'{D}/predB.jsonl', 'truthB', range(10, 15))
    H = human_pairs()
    PA, PB, PH = F.prep(A), F.prep(Bt), F.prep(H)
    z0 = np.zeros(F.nparams())
    print(f"pairs: odd A {len(PA)}, odd B {len(PB)}, real {len(PH)}; params {F.nparams()} (feats {feats}, hinge "
          f"{F.hinge} u0 {a.u0}, lam {a.lam}, knots from {m.knots[a.kmin]})")
    by = lambda P, key: [(g, [i for i, p in enumerate(P) if p['q'][key] == g]) for g in sorted(set(p['q'][key] for p in P))]
    if not a.quick:
        cats = sorted(set(p['q']['cat'] for p in PA))
        pcv = np.full(len(PA), np.nan)
        for c in cats:
            th = F.fit([p for p in PA if p['q']['cat'] != c] + PH, a.lam)
            ix = [i for i, p in enumerate(PA) if p['q']['cat'] == c]
            pcv[ix] = F.predict([PA[i] for i in ix], th)
        show("== odd A, leave one category out (fit on the other categories + all real positions)",
             by(PA, 'cat') + by(PA, 'stage') + [('ALL', list(range(len(PA))))], PA, F.predict(PA, z0), pcv, 'LOCO')
        fold = np.array([(p['q']['g'] * 7919) % 5 for p in PH])
        pcvh = np.full(len(PH), np.nan)
        for f in range(5):
            th = F.fit(PA + [p for p, k in zip(PH, fold) if k != f], a.lam)
            ix = [i for i in range(len(PH)) if fold[i] == f]
            pcvh[ix] = F.predict([PH[i] for i in ix], th)
        show("== real positions, 5 folds (fit on odd A + the other folds)",
             by(PH, 'cat') + [('ALL', list(range(len(PH))))], PH, F.predict(PH, z0), pcvh, 'CV  ')
    th = F.fit(PA + PH, a.lam)
    if PB:
        show("== odd B: independent test set (other seed; near_corner / twin_max / diagonal unseen)",
             by(PB, 'cat') + by(PB, 'stage') + [('ALL', list(range(len(PB))))], PB, F.predict(PB, z0),
             F.predict(PB, th), 'fit ')
    show("== real positions, in-sample (final fit)", [('ALL', list(range(len(PH))))], PH, F.predict(PH, z0),
         F.predict(PH, th), 'fit ')
    C = th.reshape(-1, F.na)
    names = (['dslope'] if F.value else []) + (['dhinge'] if F.hinge else []) + feats
    print("coefficients by knot (log2 sum " + ' '.join(f'{m.knots[k]:g}' for k in F.act) + "):")
    for nm, row in zip(names, C):
        print(f"    {nm:12s} " + ' '.join(f'{x:7.3f}' for x in row))
    if a.write:
        with open(a.write, 'w') as f:
            f.write(open(a.model).read().rstrip('\n') + '\n')
            f.write("# anypos (2026-10-07): odds correction for odd formations, z_T += sum_j B(s).ocorr_j * x_j for every target\n"
                    "# (base ratios of the chain rule unchanged); x from the best move's afterstate a: exposed_g = max(0,\n"
                    "# exposed(a) - 2) / 2, corner_g = max(0, corner_dist(a) - 1) / 2 * clip(1 - empty(a) / 12, 0, 1), far_g3 =\n"
                    "# max(0, far(a) - 2) / 3 (scripts/anypos_feats.py: big tiles of rank >= max - 3, each adds its distance - 1 to\n"
                    "# the nearest bigger-or-equal big tile before it in rank order)\n")
            for nm, row in zip(names, C):
                full = [0.0] * F.nk
                for j, k in enumerate(F.act): full[k] = row[j]
                f.write(f"ocorr {nm} " + ' '.join(f'{x:.6g}' for x in full) + '\n')
        print(f"-> {a.write}")

if __name__ == '__main__':
    main()
