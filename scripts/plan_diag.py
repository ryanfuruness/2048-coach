#!/usr/bin/env python3
"""Diagnostics for the plan study (workstream plan): where plans fail. usage: plan_diag.py [ENGINE_GLOB]"""
import collections, glob, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_lib as pl

def main():
    eglob = sys.argv[1] if len(sys.argv) > 1 else 'results/plan/run1/engine_*.jsonl'
    recs = {json.loads(l)['id']: json.loads(l) for l in open('results/plan/sample.jsonl')}
    eng = {}
    for f in glob.glob(eglob):
        for l in open(f):
            e = json.loads(l); eng[e['id']] = e
    # (a) no_corner: where is the biggest tile, what is in the nearest corner
    pat = collections.Counter()
    for r in recs.values():
        if r['type'] != 'no_corner': continue
        b = r['ranks']; mx = max(b)
        cells = [c for c in range(16) if b[c] == mx]
        adj = {1: 0, 4: 0, 2: 3, 7: 3, 8: 12, 13: 12, 11: 15, 14: 15}
        kind = 'center' if any(c in (5, 6, 9, 10) for c in cells) and not any(c in adj for c in cells) else 'edge-far'
        for c in cells:
            if c in adj:
                cr = b[adj[c]]
                kind = 'next-to-corner, corner=max-1' if cr == mx - 1 else 'next-to-corner, corner<=max-2' if cr else 'next-to-corner, corner empty'
                break
        pat[(r['stage'], kind)] += 1
    print('(a) no_corner positions: where the biggest tile is'); [print('   ', k, v) for k, v in sorted(pat.items())]
    # (b) single: does the tile at path cell 1 grow within 200 moves, corner kept
    for grp in ('engine', 'players'):
        res = collections.defaultdict(list)
        for i, r in recs.items():
            if r['type'] != 'single': continue
            P = pl.plan_info(r['ranks'])
            if P['type'] != 'single': continue
            seq = [pl.ranks_of_hex(h) for h in eng[i]['boards']] if grp == 'engine' and i in eng else (r['human'] if grp == 'players' else None)
            if seq is None: continue
            ch = P['chain']; c1 = pl.path_cell(ch['orient'], 1); c0 = P['corner']; v1 = r['ranks'][c1]
            win = seq[:200]
            grew = any(b[c1] > v1 and b[c0] >= r['ranks'][c0] for b in win)
            res[r['stage']].append(grew if (grew or len(seq) >= 200) else None)
        print(f'(b) single, {grp}: the tile next to the corner (path cell 1) grows within 200 moves with the corner kept:',
              {s: (round(sum(x for x in v if x is not None) / max(1, sum(x is not None for x in v)), 2), sum(x is not None for x in v)) for s, v in res.items()})
    # (c) agreement by empty cells (engine), main check
    byE = collections.defaultdict(list)
    for i, r in recs.items():
        if r['type'] in ('block', 'single', 'no_corner') or i not in eng: continue
        P = pl.plan_info(r['ranks'])
        if P['type'] != r['type']: continue
        ev = pl.events(P, r['ranks'], [pl.ranks_of_hex(h) for h in eng[i]['boards']])
        e = sum(1 for v in r['ranks'] if v == 0)
        byE['0-2' if e <= 2 else '3-5' if e <= 5 else '6+'].append(ev.get(pl.main_check(r['type'])))
    print('(c) engine agreement (merge/build/grow/blocked main checks) by empty cells:',
          {k: (round(sum(x for x in v if x is not None) / max(1, sum(x is not None for x in v)), 2), len(v)) for k, v in sorted(byE.items())})
    # (d) location baseline for build/grow: the end tile appears at the named next cell vs at another neighbour of the
    # chain end (first occurrence within the horizon)
    for grp in ('engine', 'players'):
        named = other = both = n = 0
        for i, r in recs.items():
            if r['type'] not in ('build', 'grow'): continue
            P = pl.plan_info(r['ranks'])
            if P['type'] != r['type']: continue
            seq = [pl.ranks_of_hex(h) for h in eng[i]['boards']] if grp == 'engine' and i in eng else (r['human'] if grp == 'players' else None)
            if not seq: continue
            endc = P['cells'][-1]; rr, cc = divmod(endc, 4)
            nbs = [x for x in (endc - 4 if rr > 0 else -1, endc + 4 if rr < 3 else -1, endc - 1 if cc > 0 else -1, endc + 1 if cc < 3 else -1)
                   if x >= 0 and x not in P['cells'] and x != P['next_cell']]
            H = pl.horizon(P)
            tn = next((k for k, b in enumerate(seq[:H]) if b[P['next_cell']] == P['end']), None)
            to = next((k for k, b in enumerate(seq[:H]) if any(b[x] == P['end'] for x in nbs)), None) if nbs else None
            if tn is None and to is None: continue
            n += 1
            if tn is not None and (to is None or tn < to): named += 1
            elif to is not None and (tn is None or to < tn): other += 1
            else: both += 1
        print(f'(d) build/grow, {grp}: the end tile appears first at the NAMED cell {named}, at another neighbour of the chain end {other}, same move {both} (n={n})')

if __name__ == '__main__':
    main()
