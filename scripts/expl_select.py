#!/usr/bin/env python3
"""Sample real positions with a clearly worse move for the reasons' faithfulness study (workstream expl).

From the curated human positions analysed with the current engine (results/human_ds_v6b/analysis.jsonl), positions
decided by search (no exact table, not a block formation) that have a non-reference move with an estimated real loss
>= --min-loss and a reason; per position one such move (the played one when it qualifies, else a random one).
Stratified by stage (largest tile <= 512, 1024-2048, 4096-8192, 16384+) x tier, up to --per cells' share.

usage: expl_select.py OUT_PREFIX [--n 1000] [--min-loss 0.02] [--seed 1]
writes OUT_PREFIX.tsv (id hex move stage tier player video ply) and OUT_PREFIX.in (one hex board per line, for
build/analyze --stdin --json)"""
import json, random, sys, collections

DIRS = ['up', 'right', 'down', 'left']

def stage_of(board):
    m = max(max(r) for r in board)
    return 0 if m <= 512 else 1 if m <= 2048 else 2 if m <= 8192 else 3

def main():
    a = sys.argv[1:]
    out = a.pop(0)
    n, min_loss, seed, src = 1000, 0.02, 1, 'results/human_ds_v6b/analysis.jsonl'
    while a:
        k = a.pop(0)
        if k == '--n': n = int(a.pop(0))
        elif k == '--min-loss': min_loss = float(a.pop(0))
        elif k == '--seed': seed = int(a.pop(0))
        elif k == '--src': src = a.pop(0)
    rng = random.Random(seed)
    cells = collections.defaultdict(list)
    for line in open(src):
        r = json.loads(line)
        if r.get('game_over') or r.get('source') != 'search' or r.get('judged') is False or 'moves' not in r:
            continue
        cand = [m for m in r['moves'] if (m.get('real_loss') or 0) >= min_loss and m.get('reasons')
                and m['move'] != r.get('engine_move')]
        if not cand:
            continue
        pick = next((m for m in cand if m['move'] == r.get('played')), None) or rng.choice(cand)
        key = (stage_of(r['board']), r.get('tier', '?'))
        cells[key].append((r['hex'], DIRS.index(pick['move']), r.get('player', ''), r.get('video', ''), r.get('ply', 0),
                           r.get('tier', '?')))
    keys = sorted(cells)
    # round robin over the strata, so that rare strata are fully used before common ones dominate
    for k in keys:
        rng.shuffle(cells[k])
    sel, i = [], 0
    while len(sel) < n and any(cells[k] for k in keys):
        k = keys[i % len(keys)]
        if cells[k]:
            sel.append((k[0],) + cells[k].pop())
        i += 1
    with open(out + '.tsv', 'w') as f, open(out + '.in', 'w') as g:
        f.write('id\thex\tmove\tstage\ttier\tplayer\tvideo\tply\n')
        for j, (st, hx, d, pl, vid, ply, tier) in enumerate(sel):
            f.write(f'{j}\t{hx}\t{d}\t{st}\t{tier}\t{pl}\t{vid}\t{ply}\n')
            g.write(hx + '\n')
    cnt = collections.Counter((s[0], s[6]) for s in sel)
    print(f'{len(sel)} positions; by (stage, tier):', dict(sorted(cnt.items())))

if __name__ == '__main__':
    main()
