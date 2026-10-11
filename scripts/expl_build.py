#!/usr/bin/env python3
"""Tool input for build/expl_tool from the sample's analysis (workstream expl).

For every sampled (position, move) whose current analysis (build/analyze --stdin --json on PREFIX.in) is decided by
search, with an estimated real loss >= --min-loss: one line per reason of the move ("ID HEX D BV CODE", risk split into
risk_dead / risk_bad by its wording), and the reasons' order and text in PREFIX_reasons.tsv. With --probe, also one
"probe" line per pair (the single cells that recover most of the loss).

usage: expl_build.py PREFIX [--analysis PREFIX_analysis.jsonl] [--min-loss 0.03] [--probe] > PREFIX_tool.in"""
import json, sys

DIRS = ['up', 'right', 'down', 'left']

def main():
    a = sys.argv[1:]
    pre = a.pop(0)
    ana, min_loss, probe = pre + '_analysis.jsonl', 0.03, False
    while a:
        k = a.pop(0)
        if k == '--analysis': ana = a.pop(0)
        elif k == '--min-loss': min_loss = float(a.pop(0))
        elif k == '--probe': probe = True
    rows = [l.rstrip('\n').split('\t') for l in open(pre + '.tsv')][1:]
    out = open(pre + '_reasons.tsv', 'w')
    out.write('pair\trank\tcode\tstage\ttier\treal_loss\tloss_rel\ttext\tlock\n')
    npairs = 0
    for row, line in zip(rows, open(ana)):
        pid, hx, d, stage, tier = row[0], row[1], int(row[2]), row[3], row[4]
        r = json.loads(line)
        if r.get('source') != 'search' or r.get('judged') is False or not r.get('moves'):
            continue
        mv = {m['move']: m for m in r['moves']}
        m = mv.get(DIRS[d])
        if not m or (m.get('real_loss') or 0) < min_loss or not m.get('reasons'):
            continue
        refs = [x for x in r['moves'] if x.get('loss') == 0]
        if not refs:
            continue
        ref = next((x for x in refs if x['move'] == r.get('engine_move')), refs[0])
        bv = DIRS.index(ref['move'])
        if bv == d:
            continue
        npairs += 1
        best = ref['value']
        rel = max(0.0, best - m['value']) / max(100000.0, abs(best))
        for k, rs in enumerate(m['reasons']):
            code = rs['code']
            if code == 'risk':
                code = 'risk_dead' if rs['text'].startswith('lets the next tile end the game') else 'risk_bad'
            print(f'{pid}_{k} {r["hex"]} {d} {bv} {code}')
            out.write(f'{pid}\t{k}\t{code}\t{stage}\t{tier}\t{m["real_loss"]}\t{rel:.5f}\t{rs["text"]}\t'
                      f'{int(bool(m.get("breaks_corner")))}\n')
        if probe:
            print(f'{pid}_p {r["hex"]} {d} {bv} probe')
    print(f'{npairs} pairs', file=sys.stderr)

if __name__ == '__main__':
    main()
