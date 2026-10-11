#!/usr/bin/env python3
"""Claims on the block player's disputes vs macroxue's judgment (workstream mx: playouts with macroxue continuing after
the expert's and our engine's move, results/mx/for_late.txt columns mx_playout_rel_loss / mx_playout_sig), the better
judge in block positions. Claims: value-based (as analyze) or table-aware (block table decided: p_best - p_move).
usage: pdf_vs_mx.py CLAIMS.jsonl ..."""
import json, sys, math
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import exp_late_claims as E
from pdf_claims_report import claims_table_aware

def load_mx():
    out = {}
    hdr = None
    for line in open('results/mx/for_late.txt'):
        p = line.rstrip('\n').split('\t')
        if p[0] == 'sides': hdr = p; continue
        if hdr and len(p) == len(hdr):
            r = dict(zip(hdr, p))
            out[int(r['id'][1:])] = r
    return out

def main():
    mx = load_mx()
    rows = E.meta()
    print(f"{'claims':22s} {'mode':6s} {'n':>4s} {'>10%':>5s} {'>10% & mx: no sig. loss':>24s} {'>10% & mx: expert worse':>24s} {'pearson(claim, mx loss)':>24s}")
    for path in sys.argv[1:]:
        for mode, fn in (('value', E.claims), ('table', claims_table_aware)):
            C = fn(path)
            xs, ys = [], []
            n = big = bigf = bigt = 0
            for i, r in enumerate(rows):
                if i not in mx or C[i] is None: continue
                m = mx[i]
                if m['player'] != 'd4Nf6Bg5': continue
                p = E.NAME[r['played']]
                if p not in C[i]['rel']: continue
                cl = C[i]['rel'][p]
                try:
                    loss = float(m['mx_playout_rel_loss'])
                except ValueError:
                    continue
                n += 1
                xs.append(cl); ys.append(loss)
                if cl > 0.10:
                    big += 1
                    if m['mx_playout_sig'] == 'engine': bigt += 1
                    else: bigf += 1
            name = path.rsplit('/', 1)[-1].replace('claims_', '').replace('.jsonl', '')
            print(f"{name:22s} {mode:6s} {n:4d} {big:5d} {bigf:24d} {bigt:24d} {E.pearson(xs, ys):24.3f}")

if __name__ == '__main__':
    main()
