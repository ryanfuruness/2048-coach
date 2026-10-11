#!/usr/bin/env python3
"""Location precision of build/grow plans (workstream plan): among positions where the tile the chain's end needs
appears next to the chain's end within the horizon, the share where it appears first in the cell the plan names.
Old plans (plan_lib port) vs new (results/plan/info_new.jsonl), engine and player continuations.
usage: plan_location.py"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_lib as pl

def nbs_of(c):
    r, k = divmod(c, 4)
    return [x for x in (c - 4 if r > 0 else -1, c + 4 if r < 3 else -1, c - 1 if k > 0 else -1, c + 1 if k < 3 else -1) if x >= 0]

def main():
    recs = {json.loads(l)['id']: json.loads(l) for l in open('results/plan/sample.jsonl')}
    new = {json.loads(l)['id']: json.loads(l) for l in open('results/plan/info_new.jsonl')}
    eng = {}
    for f in glob.glob('results/plan/run1/engine_*.jsonl'):
        for l in open(f):
            e = json.loads(l); eng[e['id']] = [pl.ranks_of_hex(h) for h in e['boards']]
    tab = collections.defaultdict(lambda: [0, 0])
    for i, r in recs.items():
        for ver, I in (('old', pl.old_info(r['ranks'])), ('new', new[i]['plan_info'])):
            st = I.get('step', I['type'])
            if st not in ('build', 'grow', 'merge') or 'next_cell' not in I:
                continue
            end = pl.rk(I['needs']); cells = I['chain']; endc = cells[-1]
            cand = [x for x in nbs_of(endc) if x not in cells]
            if len(cand) < 2:
                continue  # only one place to build: nothing to choose
            H = pl.horizon2(I)
            for grp, seq in (('engine', eng.get(i)), ('players', r['human'])):
                if not seq:
                    continue
                k = next(((k, [x for x in cand if b[x] == end and r['ranks'][x] != end or (st == 'merge' and x == I['next_cell'])])
                          for k, b in enumerate(seq[:H]) if any(b[x] == end for x in cand)), None)
                if k is None:
                    continue
                first_cells = [x for x in cand if seq[k[0]][x] == end]
                tab[(grp, ver, r['stage'])][0] += I['next_cell'] in first_cells
                tab[(grp, ver, r['stage'])][1] += 1
                tab[(grp, ver, 'all')][0] += I['next_cell'] in first_cells
                tab[(grp, ver, 'all')][1] += 1
    for grp in ('engine', 'players'):
        for ver in ('old', 'new'):
            row = [f"{s}: {tab[(grp, ver, s)][0] / max(1, tab[(grp, ver, s)][1]):.2f} ({tab[(grp, ver, s)][1]})"
                   for s in ('<=512', '1024-2048', '4096-8192', '16384+', 'all')]
            print(f'{grp:8s} {ver}: ' + '  '.join(row))

if __name__ == '__main__':
    main()
