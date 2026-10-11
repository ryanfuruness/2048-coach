#!/usr/bin/env python3
"""The real-position odds truth sets (cal6 / cal7) in one table for workstream anypos: per position the hex board, the
target, the measured share of engine playouts that reached it and the playout count.
usage: anypos_human.py OUT.tsv"""
import sys
SPECS = ['r14:16384:results/cal6/truth.tsv:results/cal6/truth/truth_r14.tsv',
         'r15:32768:results/cal6/truth.tsv:results/cal7/truth/truth_r15.tsv',
         'r15:32768:results/cal6/truth2.tsv:results/cal7/truth/truth2_r15.tsv',
         'r14:16384:results/cal6/truth3.tsv:results/cal6/truth/truth3_r14.tsv',
         't30:16384:results/cal6/tight30_sel.tsv:results/cal6/tight30_truth.tsv',
         'r15:32768:results/cal7/truth4.tsv:results/cal7/truth/truth4_r15.tsv']
out = open(sys.argv[1], 'w')
out.write('set\tstratum\ttarget\thex\ty\tn\n')
tot = 0
for spec in SPECS:
    g, T, selp, rolp = spec.split(':')
    sel = [l.rstrip('\n').split('\t') for l in open(selp)]
    rows = [l.rstrip('\n').split('\t') for l in open(rolp)]
    h = {k: i for i, k in enumerate(sel[0])}
    pos = {int(r[h['idx']]): r for r in sel[1:] if r[h['group']] == g}
    hh = {k: i for i, k in enumerate(rows[0])}
    for r in rows[1:]:
        p = pos.get(int(r[hh['pos']]))
        if p is None: continue
        out.write(f"{selp.split('/')[-1]}:{g}\t{p[h['stratum']]}\t{T}\t{p[h['hex']]}\t{r[hh['p' + T]]}\t{r[hh['n']]}\n")
        tot += 1
print(tot, 'positions', file=sys.stderr)
