#!/usr/bin/env python3
"""Refit the odds model's value slopes on REAL human positions with playout truth (scripts/calib_truth_select.py +
build/rollout --moves engine; results/cal6/truth*), keeping the base rates a_T(s) of a synthetic fit
(scripts/fit_calib.py --slope-bands ...).

Why: on real positions the synthetic slopes are wrong in the 4096-16384 band (tight real positions repair better than
the synthetic fit says; the network undervalues human formations). The model is evaluated exactly as build/analyze
does: p = survival x sigmoid(a(s) + slope(s) * u), u = log(max(v / vbar(s), 0.01)), v = mean value of the surviving
next tiles, slope(s) = hats(s) . b with b tied within bands - the inputs come from build/analyze --odds-inputs.
Labels: the share of playouts that reached the target (weight = playouts). Slopes per band >= 0, maximum likelihood;
5-fold cross-validation over PLAYERS compares base model / refit.

usage: fit_calib_real.py BASE.json OUT.txt [--analyze build_cal6/analyze] [--engine 'engine flags'] [--bands 12,14]
       [--truth GROUP:TARGET:SEL.tsv:ROLLOUT.tsv ...]   (default: r14:16384 and r15:32768 from results/cal6)"""
import collections, json, math, subprocess, sys, zlib
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from fit_calib import hats, KNOTS  # noqa: E402

def analyze_inputs(exe, model_txt, hexes, engine=''):
    out = subprocess.run(['bash', '-c', f'ulimit -s unlimited; ./{exe} --preset best-notables {engine} --calib {model_txt} '
                          f'--odds-inputs --stdin'], input=''.join(h + '\n' for h in hexes), capture_output=True,
                         text=True).stdout.strip().split('\n')
    return [json.loads(l).get('odds_in') for l in out]

def write_txt(model, path):
    with open(path, 'w') as f:
        f.write('knots ' + ' '.join(map(str, model['knots'])) + '\n')
        f.write(f"umode {1 if model.get('umode') == 'log' else 0}\n")
        f.write('vbar ' + ' '.join(f"{x:.6g}" for x in model['vbar']) + '\n')
        f.write('ratio ' + ' '.join(f"{x:.6g}" for x in model['future_ratio']) + '\n')
        for t, ab in model['targets'].items():
            f.write(f"target {t} " + ' '.join(f"{x:.6g}" for x in ab['a'] + ab['b']) + '\n')

def main():
    args = sys.argv[1:]
    base, out = args.pop(0), args.pop(0)
    exe, bands, truth, engine = 'build_cal6/analyze', [12.0, 14.0], [], ''
    while args:
        a = args.pop(0)
        if a == '--analyze': exe = args.pop(0)
        elif a == '--engine': engine = args.pop(0)
        elif a == '--bands': bands = [float(x) for x in args.pop(0).split(',')]
        elif a == '--truth':
            while args and not args[0].startswith('--'): truth.append(args.pop(0))
    if not truth:
        truth = ['r14:16384:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv',
                 'r14:8192:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv',
                 't30:16384:results/cal6/tight30_sel.tsv:results/cal6/tight30_truth.tsv',
                 'r15:32768:results/cal6/truth.tsv:results/cal6/truth/truth_r15.tsv',
                 'r15:32768:results/cal6/truth2.tsv:results/cal6/truth/truth2_r15.tsv']
    model = json.load(open(base))
    band_of = [sum(k >= c for c in bands) for k in KNOTS]
    nb = len(bands) + 1
    base_txt = out + '.base.tmp'
    write_txt(model, base_txt)
    new = json.loads(json.dumps(model))
    vb = np.array(model['vbar'])
    report = []
    data_by_T = collections.defaultdict(list)
    for spec in truth:
        g, T, selp, rolp = spec.split(':')
        sel = [l.rstrip('\n').split('\t') for l in open(selp)]
        h = {k: i for i, k in enumerate(sel[0])}
        pos = {int(r[h['idx']]): r for r in sel[1:] if r[h['group']] == g}
        try:
            rows = [l.rstrip('\n').split('\t') for l in open(rolp)]
        except FileNotFoundError:
            print(f"{spec}: no rollout file yet"); continue
        hh = {k: i for i, k in enumerate(rows[0])}
        data = []
        for r in rows[1:]:
            i = int(r[hh['pos']])
            if i in pos and int(pos[i][h['max']]) < int(T):  # only positions below the target
                data.append((pos[i], float(r[hh['p' + T]]), int(r[hh['n']])))
        ins = analyze_inputs(exe, base_txt, [d[0][h['hex']] for d in data], engine)
        X = []
        for (p, y, n), oi in zip(data, ins):
            if not oi: continue
            s = math.log2(max(oi['sum'], 2))
            B = hats(np.array([s]))[0]
            u = math.log(max(oi['value'] / max(1.0, float(B @ vb)), 0.01))
            a = float(B @ np.array(model['targets'][T]['a']))
            ub = np.array([u * B[[k for k in range(len(KNOTS)) if band_of[k] == j]].sum() for j in range(nb)])
            X.append((a, ub, oi['survival'], y, n, p[h['player']], p[h['stratum']]))
        data_by_T[T] += X
    for T, X in data_by_T.items():
        b_old = np.array(model['targets'][T]['b'])
        # the base model's per-knot slopes as band values (mean over the band's knots) for reporting
        def nll(bv, xs):
            tot = 0.0
            for a, ub, sv, y, n, *_ in xs:
                pr = sv / (1 + math.exp(-max(-30, min(30, a + float(ub @ bv)))))
                pr = min(max(pr, 1e-6), 1 - 1e-6)
                tot -= n * (y * math.log(pr) + (1 - y) * math.log(1 - pr))
            return tot
        def fit(xs):
            used = [j for j in range(nb) if any(abs(x[1][j]) > 1e-9 for x in xs)]
            r = minimize(lambda z: nll(np.array([z[used.index(j)] if j in used else 0.0 for j in range(nb)]), xs)
                         + 0.5 * float(np.sum(np.square(z))),  # weak ridge toward 0
                         x0=np.ones(len(used)), bounds=[(0, 30)] * len(used), method='L-BFGS-B')
            return np.array([r.x[used.index(j)] if j in used else 0.0 for j in range(nb)])
        def pred_old(x):
            a, ub, sv = x[0], x[1], x[2]
            # the base model's slope at this position: per-knot b interpolated = sum over bands of (u * B_band) * b_k,
            # with b_k constant within a band in the base fit
            bands_b = np.array([np.mean([b_old[k] for k in range(len(KNOTS)) if band_of[k] == j] or [0]) for j in range(nb)])
            return sv / (1 + math.exp(-max(-30, min(30, a + float(ub @ bands_b)))))
        players = sorted(set(x[5] for x in X))
        fold = {pl: zlib.crc32(pl.encode()) % 5 for pl in players}
        cv = collections.defaultdict(lambda: [0.0, 0.0, 0])
        for f in range(5):
            tr = [x for x in X if fold[x[5]] != f]; te = [x for x in X if fold[x[5]] == f]
            if not te or not tr: continue
            bv = fit(tr)
            for x in te:
                for name, pr in (('base', pred_old(x)), ('refit', x[2] / (1 + math.exp(-max(-30, min(30, x[0] + float(x[1] @ bv))))))):
                    pr = min(max(pr, 1e-4), 1 - 1e-4)
                    c = cv[(name, x[6])]
                    c[0] += -(x[3] * math.log(pr) + (1 - x[3]) * math.log(1 - pr)); c[1] += abs(pr - x[3]); c[2] += 1
                    c = cv[(name, 'all')]
                    c[0] += -(x[3] * math.log(pr) + (1 - x[3]) * math.log(1 - pr)); c[1] += abs(pr - x[3]); c[2] += 1
        bv = fit(X)
        cb, cr = cv[('base', 'all')], cv[('refit', 'all')]
        keep = cb[2] and cr[0] / cr[2] > cb[0] / cb[2]  # the refit must beat the base model out of sample
        if not keep:
            new['targets'][T]['b'] = [float(bv[band_of[k]]) for k in range(len(KNOTS))]
        report.append(f"T={T}: {len(X)} real positions, {len(players)} players; band slopes refit "
                      f"{' / '.join(f'{x:.2f}' for x in bv)} (base fit per knot: {' '.join(f'{x:.2f}' for x in b_old)})"
                      + (" -> KEPT the base slopes (the refit is worse out of sample)" if keep else " -> refit used"))
        for st in sorted(set(x[6] for x in X)) + ['all']:
            cb, cr = cv[('base', st)], cv[('refit', st)]
            if cb[2]:
                report.append(f"   {st:5s} n={cb[2]:4d}  5-fold by player: base log-loss {cb[0] / cb[2]:.3f} MAE {cb[1] / cb[2]:.3f}"
                              f"  | refit log-loss {cr[0] / cr[2]:.3f} MAE {cr[1] / cr[2]:.3f}")
    write_txt(new, out)
    json.dump(new, open(out.rsplit('.', 1)[0] + '.json', 'w'), indent=1)
    subprocess.run(['rm', '-f', base_txt])
    print('\n'.join(report))
    print('model ->', out)

if __name__ == '__main__':
    main()
