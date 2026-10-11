#!/usr/bin/env python3
"""Odds models vs playout ground truth on REAL human positions (scripts/calib_truth_select.py + build/rollout --moves
engine --horizon 0 --stop-rank R): the measured share of engine playouts that reached the target tile (16384 for the
r14 group, 32768 for r15) per position vs each model's prediction (build/analyze --calib MODEL, position odds incl.
the next-tile survival factor). Per stratum (tight / typical x stage): mean predicted vs measured, mean absolute
error, log-loss against the measured share (a playout-weighted soft label); the 'base' row predicts the stage's base
rate for every position (the model's prediction at the stage's typical value).

usage: calib_truth_report.py [--analyze build_cal6/analyze] [--preset best-notables] [--engine 'flags']
         [--truth GROUP:TARGET:SEL.tsv:ROLLOUT.tsv ... --]   (default: cal6's r14 / r15 / tight30 sets)  MODEL.txt ...
  (cal7: the r15 truth of a new engine lives in results/cal7/truth/; truth3 = cal6's held-out set: r14 group of
   results/cal6/truth3.tsv with results/cal6/truth/truth3_r14.tsv)"""
import collections, json, math, subprocess, sys

def main():
    args = sys.argv[1:]
    exe, preset, engine, specs = 'build_cal6/analyze', 'best-notables', '', []
    while args and args[0].startswith('--'):
        a = args.pop(0)
        if a == '--analyze': exe = args.pop(0)
        elif a == '--preset': preset = args.pop(0)
        elif a == '--engine': engine = args.pop(0)
        elif a == '--truth':
            while args and args[0] != '--': specs.append(args.pop(0))
            if args: args.pop(0)
    specs = specs or ['r14:16384:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv',
                      'r15:32768:results/cal6/truth.tsv:results/cal6/truth/truth_r15.tsv',
                      'r15:32768:results/cal6/truth2.tsv:results/cal6/truth/truth2_r15.tsv',
                      't30:16384:results/cal6/tight30_sel.tsv:results/cal6/tight30_truth.tsv']
    pos, meas = {}, {}
    for spec in specs:
        g, T, selp, rolp = spec.split(':')
        try:
            sel = [l.rstrip('\n').split('\t') for l in open(selp)]
            rows = [l.rstrip('\n').split('\t') for l in open(rolp)]
        except FileNotFoundError:
            continue
        h = {k: i for i, k in enumerate(sel[0])}
        for r in sel[1:]:
            if r[h['group']] == g:
                pos[(selp, g, int(r[h['idx']]))] = dict(stratum=r[h['stratum']], hex=r[h['hex']])
        hh = {k: i for i, k in enumerate(rows[0])}
        for r in rows[1:]:
            meas[(selp, g, int(r[hh['pos']]))] = (float(r[hh['p' + T]]), int(r[hh['n']]), T)
    keys = [k for k in pos if k in meas]
    print(f"{len(keys)} positions with playout truth")
    boards = ''.join(pos[k]['hex'] + '\n' for k in keys)
    res = collections.OrderedDict()
    for model in args:
        out = subprocess.run(['bash', '-c', f'ulimit -s unlimited; ./{exe} --preset {preset} {engine} --calib {model} --stdin'],
                             input=boards, capture_output=True, text=True).stdout.strip().split('\n')
        pred = {}
        for k, line in zip(keys, out):
            a = json.loads(line)
            pred[k] = a.get('odds', {}).get(meas[k][2])
        res[model] = pred
    strata = sorted(set(pos[k]['stratum'] for k in keys), key=lambda s: ('emlt'.find(s[0]), s))
    print(f"{'stratum':8s} {'n':>4s} {'measured':>9s}   " + '   '.join(f"{m.split('/')[-1]:>28s}" for m in res))
    for st in strata + ['all']:
        ks = [k for k in keys if st == 'all' or pos[k]['stratum'] == st]
        y = [meas[k][0] for k in ks]
        cells = []
        for m, pred in res.items():
            ps = [pred[k] for k in ks if pred[k] is not None]
            if len(ps) != len(ks):
                cells.append(' ' * 28); continue
            mae = sum(abs(p - t) for p, t in zip(ps, y)) / len(ks)
            ll = sum(-(t * math.log(min(max(p, 1e-4), 1 - 1e-4)) + (1 - t) * math.log(1 - min(max(p, 1e-4), 1 - 1e-4)))
                     for p, t in zip(ps, y)) / len(ks)
            cells.append(f"pred {sum(ps) / len(ps):.3f} MAE {mae:.3f} LL {ll:.3f}")
        print(f"{st:8s} {len(ks):4d} {sum(y) / len(y):9.3f}   " + '   '.join(cells))
    # reliability over all positions by predicted bin, per model
    for m, pred in res.items():
        print(f"reliability {m}:")
        for T in ('16384', '32768'):
            ks = [k for k in keys if meas[k][2] == T and pred[k] is not None]
            for lo, hi in ((0, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01)):
                b = [k for k in ks if lo <= pred[k] < hi]
                if len(b) >= 5:
                    print(f"   P({T}) predicted {lo:.2f}-{hi:.2f}: n={len(b):3d} mean predicted "
                          f"{sum(pred[k] for k in b) / len(b):.3f} measured {sum(meas[k][0] for k in b) / len(b):.3f}")

if __name__ == '__main__':
    main()
