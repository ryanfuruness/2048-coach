#!/usr/bin/env python3
"""Dispute metric (scripts/exp_late_claims.py report) with TABLE-AWARE claims (workstream pdf): when the block tables
decided a position (source "block"), a move's claim is its loss in the sub-game's success probability,
max(0, p_best - p_move) (moves that move the block: p = 0), instead of the network's value loss.
usage: pdf_claims_report.py [--split] CLAIMS.jsonl ..."""
import json, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import exp_late_claims as E

_orig = E.claims

def claims_table_aware(path):
    out = _orig(path)
    for i, line in enumerate(open(path)):
        a = json.loads(line)
        if out[i] is None or a.get('source') != 'block': continue
        ps = {E.NAME[m['move']]: max(0.0, m.get('p', 0.0)) for m in a['moves']}
        best = max(ps.values())
        out[i]['rel'] = {m: max(0.0, best - p) for m, p in ps.items()}
    return out

if __name__ == '__main__':
    E.claims = claims_table_aware
    args = sys.argv[1:]
    if '--split' in args:
        args.remove('--split')
        for g in ('PDF', 'snake'):
            E.report(args, g)
    else:
        E.report(args)
