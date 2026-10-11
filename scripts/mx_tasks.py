#!/usr/bin/env python3
"""Workstream mx (macroxue as an independent judge): build the position list and the task files for the judge driver
(~/macroxue/judge on the research machine; see /home/ryanf/projects/2048-macroxue-judge/README.md).

Positions: the expert disputes + controls (results/disputes/expert.tsv, boards from expert_h300.tsv; real tiles
recovered from results/human_ds/analysis.jsonl by video, ply and engine hex) and a random sample of expert-tier
positions with a tile >= 16384 (unbiased agreement rate).
Writes results/mx/positions.tsv and, with --eval DEPTH / --play DEPTH K HMAX, task files for the driver.

usage: mx_tasks.py [--random N] [--eval DEPTH ...] [--play DEPTH K HMAX [--groups dispute,control]] [--out PREFIX]
       mx_tasks.py --pool POOL.bin SEEDS DEPTH HMAX   (macroxue from every board of one of our start pools, e.g. the
                                                    16384-phase test weights/exps1/pool700.bin; no forced first move)"""
import json, math, random, sys, collections, zlib

ANALYSIS = 'results/human_ds/analysis.jsonl'
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def ranks(board):
    return [0 if t == 0 else int(round(math.log2(t))) for row in board for t in row]

def claimed(a):
    vals = {m['move']: m['value'] for m in a['moves']}
    if a.get('played') not in vals or a.get('engine_move') not in vals:
        return None
    best = vals[a['engine_move']]
    return max(0.0, best - vals[a['played']]) / max(100000.0, abs(best))

def pool_tasks(path, seeds, depth, hmax, out):
    import struct
    data = open(path, 'rb').read()
    boards = [struct.unpack_from('<Q', data, 8 * i)[0] for i in range(len(data) // 8)]
    name = path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    with open(out + f'{name}_d{depth}.tasks', 'w') as f:
        for s in range(seeds):
            for k, b in enumerate(boards):
                rk = [(b >> (4 * c)) & 15 for c in range(16)]
                f.write(f"P p{k} {depth} {999 + 7919 * s + 104729 * k} - {hmax} {' '.join(map(str, rk))}\n")
    print(f"{len(boards)} boards x {seeds} seeds -> {out}{name}_d{depth}.tasks")

def main():
    args = sys.argv[1:]
    if args and args[0] == '--pool':
        pool_tasks(args[1], int(args[2]), int(args[3]), int(args[4]), 'results/mx/')
        return
    n_random, evals, play, groups, out, differ, tag = 300, [], None, ('dispute',), 'results/mx/', False, ''
    while args:
        a = args.pop(0)
        if a == '--random': n_random = int(args.pop(0))
        elif a == '--eval': evals.append(int(args.pop(0)))
        elif a == '--play': play = (int(args.pop(0)), int(args.pop(0)), int(args.pop(0)))
        elif a == '--groups': groups = tuple(args.pop(0).split(','))
        elif a == '--out': out = args.pop(0)
        elif a == '--differ': differ = True        # only positions where the player's and our engine's moves differ
        elif a == '--tag': tag = args.pop(0)
    # disputes: metadata + engine hex per index
    meta = {}
    with open('results/disputes/expert.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            meta[int(r['idx'])] = r
    hexes = {}
    with open('results/disputes/expert_h300.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            hexes[int(r['pos'])] = r['board']
    want = {(m['video'], int(m['ply']), hexes.get(i)): i for i, m in meta.items()}
    found = {}
    pool = []
    for line in open(ANALYSIS):
        a = json.loads(line)
        key = (a.get('video'), a.get('ply'), a.get('hex'))
        if key in want and want[key] not in found:
            found[want[key]] = a
        if a.get('tier') != 'expert' or a.get('game_over') or 'played' not in a or len(a['moves']) < 2:
            continue
        if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'):
            continue
        if max(max(r) for r in a['board']) < 16384:
            continue
        c = claimed(a)
        if c is None:
            continue
        pool.append((a, c))
    missing = [i for i in meta if i not in found]
    if missing:
        print(f"WARNING: {len(missing)} dispute positions without a real board: {missing[:10]}", file=sys.stderr)
    rows = []
    for i in sorted(found):
        m, a = meta[i], found[i]
        rows.append(dict(id=f"d{i}", group=m['group'], video=m['video'], ply=m['ply'], played=NAME[m['played']],
                         engine=NAME[m['engine']], claimed=float(m['claimed_loss']), max=int(m['max']),
                         player=a.get('player', ''), hex=a['hex'], ranks=ranks(a['board'])))
    taken = {(r['video'], int(r['ply'])) for r in rows}
    random.seed(11)
    pool = [p for p in pool if (p[0]['video'], p[0]['ply']) not in taken]
    for k, (a, c) in enumerate(random.sample(pool, min(n_random, len(pool)))):
        rows.append(dict(id=f"r{k}", group='random', video=a['video'], ply=a['ply'], played=NAME[a['played']],
                         engine=NAME[a['engine_move']], claimed=c, max=max(max(r) for r in a['board']),
                         player=a.get('player', ''), hex=a['hex'], ranks=ranks(a['board'])))
    with open(out + 'positions.tsv', 'w') as f:
        f.write('id\tgroup\tvideo\tply\tplayed\tengine\tclaimed\tmax\tplayer\thex\tranks\n')
        for r in rows:
            f.write(f"{r['id']}\t{r['group']}\t{r['video']}\t{r['ply']}\t{r['played']}\t{r['engine']}\t{r['claimed']:.4f}"
                    f"\t{r['max']}\t{r['player']}\t{r['hex']}\t{','.join(map(str, r['ranks']))}\n")
    cnt = collections.Counter(r['group'] for r in rows)
    print(f"positions: {dict(cnt)} (expert pool {len(pool)}) -> {out}positions.tsv")
    for d in evals:
        with open(out + f'eval_d{d}.tasks', 'w') as f:
            for r in rows:
                f.write(f"E {r['id']} {d} {' '.join(map(str, r['ranks']))}\n")
        print(f"eval tasks depth {d}: {len(rows)} -> {out}eval_d{d}.tasks")
    if play:
        d, k, hmax = play
        n = 0
        with open(out + f'play{tag}_d{d}_h{hmax}.tasks', 'w') as f:
            # interleave positions so that every shard gets a mix (playout lengths vary a lot)
            for s in range(k):
                for r in rows:
                    if r['group'] not in groups or (differ and r['played'] == r['engine']):
                        continue
                    moves = [r['played']] if r['played'] == r['engine'] else [r['played'], r['engine']]
                    for mv in moves:
                        # common random numbers: the same seed for both moves of a position and playout index
                        seed = 1000 * zlib.crc32(r['id'].encode()) + s
                        f.write(f"P {r['id']} {d} {seed} {mv} {hmax} {' '.join(map(str, r['ranks']))}\n")
                        n += 1
        print(f"play tasks depth {d}, {k} playouts, hmax {hmax}, groups {groups}: {n} -> {out}play{tag}_d{d}_h{hmax}.tasks")

if __name__ == '__main__':
    main()
