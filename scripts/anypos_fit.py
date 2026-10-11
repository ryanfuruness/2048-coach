#!/usr/bin/env python3
"""A value-term correction of the odds model for odd positions (workstream anypos), fitted on the odd positions'
engine-playout truth together with the real-position truth sets, validated leave-one-category-out, by folds of the
real positions, and on an independent test set (other seed, three unseen categories).

Correction (per target T, hat-interpolated over the model's knots like every other odds term):
    z_T += dslope_T(s) * u + dhinge_T(s) * min(0, u - U0)          (u = log(value / vbar(s)), as calib.h)
The base rates (u = 0) and therefore fresh-board odds and the chain rule's base ratios stay as installed; with
--no-hinge only dslope is fitted, which folds into the model's existing b coefficients (no code change needed).

usage: anypos_fit.py [--model M] [--u0 -0.15] [--lam 3] [--no-hinge] [--write OUT_MODEL]"""
import argparse, collections, json, math, os, sys
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(__file__))
from anypos_odds import Model  # noqa: E402

D = 'results/anypos'

def odd_pairs(pos_tsv, pred_jsonl, truth_prefix, stages):
    pos = [l.rstrip('\n').split('\t') for l in open(pos_tsv)][1:]
    pred = [json.loads(l) for l in open(pred_jsonl)]
    out = []
    base = os.path.basename(pos_tsv)[:-4]  # pos / posB
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
                out.append(dict(src='odd', cat=pos[g][1], stage=R, T=T, y=float(r[h[f'p{T}']]), n=int(r[h['n']]),
                                oi=oi, key=f'{base}:{g}'))
    return out

def human_pairs():
    rows = [l.rstrip('\n').split('\t') for l in open(f'{D}/human_truth.tsv')][1:]
    pred = [json.loads(l) for l in open(f'{D}/human_pred.jsonl')]
    out = []
    for i, (r, a) in enumerate(zip(rows, pred)):
        oi = a.get('odds_in')
        if not oi: continue
        out.append(dict(src='human', cat=r[0], stratum=r[1], stage=int(math.log2(oi['max'])), T=int(r[2]),
                        y=float(r[4]), n=int(r[5]), oi=oi, key=f'h:{i}'))
    return out

class Fit:
    def __init__(self, model, u0, hinge, shared=True):
        self.m, self.u0, self.hinge, self.shared = model, u0, hinge, shared
        self.T = sorted(model.target)
        self.nk = len(model.knots)

    def prep(self, pairs):
        """Per pair: hats, u, the installed z of every target above the max tile, base probabilities."""
        m = self.m
        P = []
        for q in pairs:
            oi = q['oi']
            s = math.log2(max(oi['sum'], 2.0))
            B = np.array(m.hats(s))
            ts = [T for T in self.T if T > oi['max']]
            zs = np.array([m.z(T, oi['sum'], oi['value'])[0] for T in ts])
            u = m.z(ts[0], oi['sum'], oi['value'])[1] if ts else 0.0
            avg = max(1.0, float(B @ np.array(m.vbar)))
            base = np.array([m.prob(T, oi['sum'], avg) for T in ts])
            P.append(dict(B=B, u=u, ts=ts, zs=zs, base=base, surv=oi['survival'], j=ts.index(q['T']) if q['T'] in ts else -1,
                          y=q['y'], w=q['n'] / 64.0))
        return P

    def nparams(self):
        return (1 if self.shared else len(self.T)) * self.nk * (2 if self.hinge else 1)

    def coefs(self, th):
        if self.shared:  # one correction for every target (the chain rule carries it to the bigger targets)
            c = th.reshape(-1, self.nk)
            return {T: c for T in self.T}
        th = th.reshape(len(self.T), -1, self.nk)
        return {T: th[i] for i, T in enumerate(self.T)}

    def predict(self, P, th):
        C = self.coefs(th)
        out = np.empty(len(P))
        for n, p in enumerate(P):
            if p['j'] < 0: out[n] = np.nan; continue
            prev, prev_base = -1.0, -1.0
            h = min(0.0, p['u'] - self.u0)
            for i, T in enumerate(p['ts'][:p['j'] + 1]):
                c = C[T]
                z = p['zs'][i] + float(p['B'] @ c[0]) * p['u'] + (float(p['B'] @ c[1]) * h if self.hinge else 0.0)
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
        ll = -(y * np.log(p) + (1 - y) * np.log(1 - p))
        return float((w * ll).sum() / w.sum()) + lam * float((th ** 2).sum()) / len(th)

    def fit(self, P, lam, th0=None):
        th0 = np.zeros(self.nparams()) if th0 is None else th0
        r = minimize(self.loss, th0, args=(P, lam), method='L-BFGS-B', options=dict(maxiter=500, maxfun=20000))
        return r.x

def metrics(p, P):
    y = np.array([q['y'] for q in P]); p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(np.mean(np.abs(p - y))), float(np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p)))), float(np.mean(p)), float(np.mean(y))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=f'{D}/model_installed.txt')
    ap.add_argument('--u0', type=float, default=-0.15)
    ap.add_argument('--lam', type=float, default=3.0)
    ap.add_argument('--no-hinge', action='store_true')
    ap.add_argument('--per-target', action='store_true', help='a correction per target (default: one shared)')
    ap.add_argument('--write')
    ap.add_argument('--quick', action='store_true', help='skip the cross-validations')
    a = ap.parse_args()
    m = Model(a.model)
    F = Fit(m, a.u0, not a.no_hinge, shared=not a.per_target)
    A = odd_pairs(f'{D}/pos.tsv', f'{D}/pred.jsonl', 'truth', range(9, 15))
    Bt = odd_pairs(f'{D}/posB.tsv', f'{D}/predB.jsonl', 'truthB', range(10, 15)) if os.path.exists(f'{D}/predB.jsonl') else []
    H = human_pairs()
    PA, PB, PH = F.prep(A), F.prep(Bt), F.prep(H)
    zero = np.zeros(F.nparams())
    print(f"pairs: odd A {len(A)}, odd B {len(Bt)}, human {len(H)}; params {F.nparams()} (hinge {F.hinge}, shared {F.shared}, u0 {a.u0}, lam {a.lam})")

    def report(name, P, pairs, th):
        rows = collections.defaultdict(list)
        p0, p1 = F.predict(P, zero), F.predict(P, th)
        for i, q in enumerate(pairs):
            rows[q['cat']].append(i); rows['ALL'].append(i)
        print(f"  {name}: group  n  measured | installed pred MAE LL | corrected pred MAE LL")
        for g, ix in sorted(rows.items(), key=lambda kv: (kv[0] == 'ALL', kv[0])):
            sub = [P[i] for i in ix]
            m0, m1 = metrics(p0[ix], sub), metrics(p1[ix], sub)
            print(f"    {g:24s} {len(ix):4d} {m0[3]:.3f} | {m0[2]:.3f} {m0[0]:.3f} {m0[1]:.3f} | {m1[2]:.3f} {m1[0]:.3f} {m1[1]:.3f}")

    if not a.quick:
        # 1. leave one category out (odd A): fit on human + the other categories
        print("\n== leave-one-category-out on odd set A (fit on all real positions + the other categories)")
        cats = sorted(set(q['cat'] for q in A))
        p0all, pcv = F.predict(PA, zero), np.full(len(PA), np.nan)
        for c in cats:
            tr = [P for P, q in zip(PA, A) if q['cat'] != c] + PH
            th = F.fit(tr, a.lam)
            ix = [i for i, q in enumerate(A) if q['cat'] == c]
            pcv[ix] = F.predict([PA[i] for i in ix], th)
        for c in cats + ['ALL']:
            ix = [i for i, q in enumerate(A) if c == 'ALL' or q['cat'] == c]
            sub = [PA[i] for i in ix]
            m0, m1 = metrics(p0all[ix], sub), metrics(pcv[ix], sub)
            print(f"    {c:14s} {len(ix):4d} meas {m0[3]:.3f} | installed {m0[2]:.3f} MAE {m0[0]:.3f} LL {m0[1]:.3f} | LOCO {m1[2]:.3f} MAE {m1[0]:.3f} LL {m1[1]:.3f}")
        # 2. real positions, 5 folds (fit on odd A + the other folds)
        print("\n== real positions, 5-fold (fit on odd A + the other 4 folds)")
        fold = np.array([hash(q['key']) % 5 if False else (int(q['key'][2:]) * 7919) % 5 for q in H])
        p0h, pcvh = F.predict(PH, zero), np.full(len(PH), np.nan)
        for f in range(5):
            tr = PA + [P for P, k in zip(PH, fold) if k != f]
            th = F.fit(tr, a.lam)
            ix = [i for i in range(len(PH)) if fold[i] == f]
            pcvh[ix] = F.predict([PH[i] for i in ix], th)
        groups = sorted(set(q['cat'] for q in H)) + ['ALL']
        for g in groups:
            ix = [i for i, q in enumerate(H) if g == 'ALL' or q['cat'] == g]
            sub = [PH[i] for i in ix]
            m0, m1 = metrics(p0h[ix], sub), metrics(pcvh[ix], sub)
            print(f"    {g:24s} {len(ix):4d} meas {m0[3]:.3f} | installed {m0[2]:.3f} MAE {m0[0]:.3f} LL {m0[1]:.3f} | CV {m1[2]:.3f} MAE {m1[0]:.3f} LL {m1[1]:.3f}")
    # 3. final fit on everything we have for training; test on set B
    th = F.fit(PA + PH, a.lam)
    print("\n== final fit (odd A + real positions)")
    report('odd A (in-sample)', PA, A, th)
    report('real (in-sample)', PH, H, th)
    if Bt:
        report('odd B (independent test set)', PB, Bt, th)
    if a.write:
        C = F.coefs(th)
        lines = []
        for line in m.lines:
            p = line.split()
            if p and p[0] == 'target' and int(p[1]) in C and a.no_hinge:
                T = int(p[1]); c = [float(x) for x in p[2:]]
                n = len(m.knots)
                c = c[:n] + [c[n + k] + C[T][0][k] for k in range(n)]
                line = 'target ' + str(T) + ' ' + ' '.join(f'{x:.6g}' for x in c)
            lines.append(line)
        if not a.no_hinge:  # new lines, read by calib.h once the coordinator wires them in
            lines.append(f'uhinge {a.u0}')
            for T in F.T:
                lines.append(f'target_corr {T} ' + ' '.join(f'{x:.6g}' for x in list(C[T][0]) + list(C[T][1])))
        open(a.write, 'w').write('\n'.join(l for l in lines if l is not None).rstrip('\n') + '\n')
        print(f"-> {a.write}")

if __name__ == '__main__':
    main()
