#!/usr/bin/env python3
"""Personal odds vs softmax-player playouts from REAL human positions (scripts/calib_pers_run.sh / _run2.sh): for each
temperature t of the personal model and each position (results/cal6/pers.tsv), the measured share of 32 soft:t
playouts that reached 2x / 4x the position's largest tile vs the model's prediction (weights/calib/personal.txt or
--model; the analysis' formula: model odds at the engine move's value x the next tile's survival).

usage: calib_pers_report.py [--model weights/calib/personal.txt] [--rows OUT.tsv]"""
import collections, math, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from calib_personal_real import Personal, apply, survival, parse  # noqa: E402

def main():
    args = sys.argv[1:]
    mpath, rows_out = 'weights/calib/personal.txt', None
    while args:
        a = args.pop(0)
        if a == '--model': mpath = args.pop(0)
        elif a == '--rows': rows_out = args.pop(0)
    pm = Personal(mpath)
    sel = [l.rstrip('\n').split('\t') for l in open('results/cal6/pers.tsv')]
    h = {k: i for i, k in enumerate(sel[0])}
    pos = {(r[h['group']], int(r[h['idx']])): r for r in sel[1:]}
    out = []
    for t in sorted(pm.coef):
        for R in range(9, 16):
            for mult, suffix in ((4, ''), (2, '_2x')):
                try:
                    rows = [l.rstrip('\n').split('\t') for l in open(f'results/cal6/pers/soft{t:g}_r{R}{suffix}.tsv')]
                except FileNotFoundError:
                    continue
                hh = {k: i for i, k in enumerate(rows[0])}
                for r in rows[1:]:
                    k = (f'r{R}', int(r[hh['pos']]))
                    if k not in pos: continue
                    p = pos[k]
                    top = int(p[h['max']]); T = top * mult
                    b = parse(p[h['hex']])
                    d = r[hh['move']]
                    sv = survival(apply(b, d))
                    po = pm.odds(t, top, float(p[h['sum']]), float(r[hh['value']])).get(T)
                    if po is None: continue
                    meas = 1 - float(r[hh['died']])
                    out.append((t, top, mult, po * sv, meas, int(r[hh['n']]), float(p[h['ratio']]), p[h['tier']]))
    if rows_out:
        with open(rows_out, 'w') as f:
            f.write('t\ttop\tmult\tpred\tmeasured\tn\tratio\ttier\n')
            for r in out: f.write('\t'.join(str(x) for x in r) + '\n')
    print(f"model {mpath}: {len(out)} (position, t, target) pairs")
    for mult in (2, 4):
        print(f"== {mult}x the position's tile")
        for t in sorted(set(r[0] for r in out)):
            rs = [r for r in out if r[0] == t and r[2] == mult]
            if not rs: continue
            mae = sum(abs(r[3] - r[4]) for r in rs) / len(rs)
            ll = sum(-(r[4] * math.log(min(max(r[3], 1e-4), 1 - 1e-4)) + (1 - r[4]) * math.log(1 - min(max(r[3], 1e-4), 1 - 1e-4)))
                     for r in rs) / len(rs)
            by = '  '.join(f"{top}:{sum(r[3] for r in b) / len(b):.2f}/{sum(r[4] for r in b) / len(b):.2f}"
                           for top in sorted(set(r[1] for r in rs)) for b in [[r for r in rs if r[1] == top]])
            print(f"   t={t:<6g} n={len(rs):4d} predicted {sum(r[3] for r in rs) / len(rs):.3f} measured "
                  f"{sum(r[4] for r in rs) / len(rs):.3f} MAE {mae:.3f} LL {ll:.3f} | by tile (pred/meas) {by}")

if __name__ == '__main__':
    main()
