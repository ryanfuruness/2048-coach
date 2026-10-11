#!/usr/bin/env python3
"""Outcome check of the first-listed reasons before / after the per-position verification (workstream expl).

build/expl_tool --rollouts K: the engine plays on (K playouts with common random numbers, H moves + the network
value at the horizon) from the reference move's afterstate, the move's afterstate and the edited afterstate (the
first reason's defect removed). share = mean gain of the edit / mean loss of the move, over the pairs where the
playouts confirm a loss (mean loss > 2 standard errors). Corner-lock moves are left out (their values are not trusted).

usage: expl_roll_report.py ROLL.out BEFORE_reasons.tsv AFTER_reasons.tsv"""
import sys, statistics as st, collections

def first(fn):
    f = {}
    for l in list(open(fn))[1:]:
        p = l.rstrip('\n').split('\t')
        if p[1] == '0' and not (len(p) > 8 and p[8] == '1'):
            f[p[0]] = p[2]
    return f

def main():
    roll, bf, af = sys.argv[1:4]
    res = {}
    for l in list(open(roll))[1:]:
        p = l.rstrip('\n').split('\t')
        if p[6] != '1':
            continue
        pid, code = p[0].split('_', 1)
        L, g, sL, sg = map(float, p[2:6])
        res[(pid, code)] = (L, g, sL, sg)
    b, a = first(bf), first(af)
    for name, f in (('before', b), ('after', a)):
        v = [(res[(pid, c)], c) for pid, c in f.items() if (pid, c) in res and res[(pid, c)][0] > 2 * res[(pid, c)][2]]
        sh = [max(-2, min(2, x[1] / x[0])) for x, _ in v]
        tot_l = sum(x[0] for x, _ in v)
        tot_g = sum(x[1] for x, _ in v)
        print(f'{name}: {len(v)} pairs with a confirmed loss and an edit-type first reason: median share {st.median(sh):.2f}, '
              f'>= 50% in {sum(s >= 0.5 for s in sh) / len(sh):.2f}, <= 0 in {sum(s <= 0 for s in sh) / len(sh):.2f}; '
              f'pooled share (sum of gains / sum of losses) {tot_g / tot_l:.2f}')
        by = collections.defaultdict(list)
        for (x, c), s in zip(v, sh):
            by[c].append(s)
        print('   by code: ' + ', '.join(f'{c} {len(s)}: {st.median(s):.2f}' for c, s in sorted(by.items(), key=lambda t: -len(t[1]))))
    # the pairs whose first reason changed
    ch = [pid for pid in b if pid in a and b[pid] != a[pid] and (pid, b[pid]) in res and (pid, a[pid]) in res
          and res[(pid, a[pid])][0] > 2 * res[(pid, a[pid])][2]]
    if ch:
        sb = [max(-2, min(2, res[(p, b[p])][1] / res[(p, b[p])][0])) for p in ch]
        sa = [max(-2, min(2, res[(p, a[p])][1] / res[(p, a[p])][0])) for p in ch]
        better = sum(x > y for x, y in zip(sa, sb))
        print(f'pairs whose first reason changed (both edit-type, loss confirmed): {len(ch)}; median share before '
              f'{st.median(sb):.2f} -> after {st.median(sa):.2f}; the new first reason recovers more in {better} '
              f'({better / len(ch):.2f})')

if __name__ == '__main__':
    main()
