#!/usr/bin/env python3
"""Odds vs engine-continuation truth on the odd positions (workstream anypos): analyze's position odds (pred*.jsonl,
in the order of results/anypos/pos.tsv) vs the share of engine playouts that reached the next one / two doublings
(truth_rR.tsv per stage, rows mapped back through pos_rR.idx). Per category and per stage: n, mean predicted vs
measured, MAE, log-loss against the measured share (a soft label, clipped); reliability bins over everything.
usage: anypos_report.py [--dir results/anypos] [--pred pred.jsonl ...] [--tsv out.tsv]"""
import argparse, collections, json, math, os

def ll(p, y):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))

def load(d, pred_files):
    pos = [l.rstrip('\n').split('\t') for l in open(os.path.join(d, 'pos.tsv'))][1:]
    preds = []
    for pf in pred_files:
        preds.append([json.loads(l) for l in open(pf if os.path.sep in pf else os.path.join(d, pf))])
    rows = []
    for R in range(8, 15):
        tf = os.path.join(d, f'truth_r{R}.tsv')
        if not os.path.exists(tf): continue
        idx = [int(x) for x in open(os.path.join(d, f'pos_r{R}.idx')).read().split()]
        t = [l.rstrip('\n').split('\t') for l in open(tf)]
        h = {k: i for i, k in enumerate(t[0])}
        for r in t[1:]:
            g = idx[int(r[h['pos']])]
            cat, stage, hx = pos[g][1], int(pos[g][2]), pos[g][3]
            n = int(r[h['n']])
            for k, T in ((1, 1 << (stage + 1)), (2, 1 << (stage + 2))):
                key = f'p{T}'
                if key not in h or stage + k > 15: continue
                if k == 2 and stage + 2 > 15: continue
                y = float(r[h[key]])
                ps = [pr[g].get('odds', {}).get(str(T)) for pr in preds]
                if any(p is None for p in ps): continue
                oi = preds[0][g].get('odds_in', {})
                rows.append(dict(g=g, cat=cat, stage=stage, k=k, T=T, y=y, n=n, p=ps, hex=hx,
                                 value=oi.get('value'), surv=oi.get('survival'), sum=oi.get('sum')))
    return rows

def table(rows, key, names):
    groups = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: (str(r[key]))):
        groups.setdefault(r[key], []).append(r)
    head = f"{key:12s} {'n':>4s} {'meas':>6s} " + ''.join(f"| {nm[:22]:>22s} pred   MAE    LL " for nm in names)
    print(head)
    for g, rs in list(groups.items()) + [('ALL', rows)]:
        y = sum(r['y'] for r in rs) / len(rs)
        cells = ''
        for j in range(len(names)):
            p = sum(r['p'][j] for r in rs) / len(rs)
            mae = sum(abs(r['p'][j] - r['y']) for r in rs) / len(rs)
            l = sum(ll(r['p'][j], r['y']) for r in rs) / len(rs)
            cells += f"| {'':22s} {p:5.3f} {mae:5.3f} {l:5.3f} "
        print(f"{str(g):12s} {len(rs):4d} {y:6.3f} {cells}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='results/anypos')
    ap.add_argument('--pred', nargs='+', default=['pred.jsonl'])
    ap.add_argument('--tsv')
    a = ap.parse_args()
    rows = load(a.dir, a.pred)
    print(f"{len(rows)} (position, target) pairs from {len(set(r['g'] for r in rows))} positions; models: {a.pred}")
    for k in (1, 2):
        rk = [r for r in rows if r['k'] == k]
        if not rk: continue
        print(f"\n== {'next doubling' if k == 1 else 'two doublings'}: by category")
        table(rk, 'cat', a.pred)
        print(f"\n== {'next doubling' if k == 1 else 'two doublings'}: by stage (largest tile rank)")
        table(rk, 'stage', a.pred)
    print("\n== reliability (all pairs), first model")
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, .9), (.9, .97), (.97, 1.01)):
        b = [r for r in rows if lo <= r['p'][0] < hi]
        if len(b) >= 5:
            print(f"   predicted {lo:.2f}-{hi:.2f}: n={len(b):4d}  mean predicted {sum(r['p'][0] for r in b) / len(b):.3f}"
                  f"  measured {sum(r['y'] for r in b) / len(b):.3f}")
    if a.tsv:
        with open(a.tsv, 'w') as f:
            f.write('g\tcat\tstage\tk\tT\ty\tn\tvalue\tsurv\tsum\thex\t' + '\t'.join(f'p{j}' for j in range(len(a.pred))) + '\n')
            for r in rows:
                f.write(f"{r['g']}\t{r['cat']}\t{r['stage']}\t{r['k']}\t{r['T']}\t{r['y']}\t{r['n']}\t{r['value']}\t"
                        f"{r['surv']}\t{r['sum']}\t{r['hex']}\t" + '\t'.join(f'{p:.4f}' for p in r['p']) + '\n')

if __name__ == '__main__':
    main()
