#!/usr/bin/env python3
"""Claims on the expert's own move in mx's 300 random expert positions (unselected), per engine config, block player
vs snake experts: how often the engine calls an ordinary expert move a mistake (> 3%) or a blunder (> 10%); value-based
(as analyze) and table-aware (block table decided: p_best - p_move). usage: pdf_random_report.py NAME ..."""
import json, sys, collections
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def claims(path, table_aware):
    out = []
    for line in open(path):
        a = json.loads(line)
        if not a.get('moves'):
            out.append(None); continue
        vals = {NAME[m['move']]: m['value'] for m in a['moves']}
        lock = {NAME[m['move']] for m in a['moves'] if m.get('breaks_corner')}
        eng = NAME.get(a.get('engine_move') or '', None)
        if table_aware and a.get('source') == 'block':
            ps = {NAME[m['move']]: max(0.0, m.get('p', 0.0)) for m in a['moves']}
            best = max(ps.values())
            out.append(({m: max(0.0, best - p) for m, p in ps.items()}, a.get('source'))); continue
        if eng is not None and a.get('source', 'search') != 'search': refm = eng
        else:
            ok = [m for m in vals if m not in lock] or list(vals)
            refm = max(ok, key=lambda m: vals[m])
        ref = vals[refm]
        out.append(({m: max(0.0, ref - v) / max(100000.0, abs(ref)) for m, v in vals.items()}, a.get('source')))
    return out

def main():
    ids = [l.strip() for l in open('results/pdf/random_in.ids')]
    pos = {}
    with open('results/mx/positions.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            pos[r['id']] = r
    print(f"{'config':10s} {'mode':6s} | block player (183): >3%  >10%  block-decided | snake experts (117): >3%  >10%")
    for name in sys.argv[1:]:
        for ta in (False, True):
            C = claims(f'results/pdf/rclaims_{name}.jsonl', ta)
            c = collections.Counter()
            for i, cl in zip(ids, C):
                r = pos[i]
                g = 'block' if r['player'] == 'd4Nf6Bg5' else 'snake'
                if cl is None: continue
                rel, src = cl
                x = rel.get(r['played'], 0.0)
                c[(g, 'n')] += 1; c[(g, '3')] += x > 0.03; c[(g, '10')] += x > 0.10; c[(g, 'blk')] += src == 'block'
            print(f"{name:10s} {'table' if ta else 'value':6s} | {c[('block','3')]:24d} {c[('block','10')]:5d} {c[('block','blk')]:14d} | "
                  f"{c[('snake','3')]:24d} {c[('snake','10')]:5d}")

if __name__ == '__main__':
    main()
