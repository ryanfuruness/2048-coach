#!/usr/bin/env python3
"""Workstream review (2026-10-07): pick real game stretches for validating build/analyze --review.
A stretch = W consecutive records of one video (time order, across segments: the review bridges gaps of up to 3 moves
and skips the rest), written as boards (16 tile values per line) to results/review/stretches/<id>.txt, plus the board
the last move led to. Stratified by tier (novice / intermediate / strong / expert) and stage of the stretch's first
position (S1 <= 512, S2 1024-2048, S3 4096-8192, S4 >= 16384), round robin over players. Experts' block-formation
positions (src/block.h at a real 16384+) are avoided: a stretch is dropped if > 10% of its positions are block ones.
usage: review_select.py [--per-tier novice=15,intermediate=30,strong=30,expert=25] [--w 300] [--seed 7]"""
import collections, gzip, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_detect import block_formation  # noqa: E402

DIG = '0123456789abcdefgh'


def tiles(board):
    return [0 if c == '0' else 1 << DIG.index(c) for c in board]


def stage(mx):
    return 'S1' if mx <= 512 else 'S2' if mx <= 2048 else 'S3' if mx <= 8192 else 'S4'


def is_block(r):
    """r: 16 real ranks; as build/analyze: the detector only at a real 16384 or more"""
    return max(r) >= 14 and block_formation(r)


def main():
    args = sys.argv[1:]
    per = {'novice': 15, 'intermediate': 30, 'strong': 30, 'expert': 25}
    W, seed = 300, 7
    while args:
        a = args.pop(0)
        if a == '--per-tier': per = {k: int(v) for k, v in (x.split('=') for x in args.pop(0).split(','))}
        elif a == '--w': W = int(args.pop(0))
        elif a == '--seed': seed = int(args.pop(0))
    rng = random.Random(seed)
    byv = collections.defaultdict(list)
    for line in gzip.open('../2048-human-data/dataset_build/positions.jsonl.gz', 'rt'):
        a = json.loads(line)
        byv[a['video']].append(a)
    cands = collections.defaultdict(lambda: collections.defaultdict(list))  # tier -> player -> windows
    for v, rs in byv.items():
        rs.sort(key=lambda r: (r.get('t') or 0, r['segment'], r['ply']))
        # cut into games where the tile sum drops (a new game), then windows of W records
        games, cur, prev = [], [], None
        for r in rs:
            s = sum(tiles(r['board']))
            if prev is not None and (s < prev - 64 or (s <= 16 and prev > 64)):
                games.append(cur); cur = []
            cur.append(r); prev = s
        games.append(cur)
        for g in games:
            for k in range(0, max(1, len(g) - W // 2), W):
                win = g[k:k + W + 1]
                if len(win) < W // 2: continue
                nblock = sum(is_block([DIG.index(c) if c != '0' else 0 for c in r['board']]) for r in win)
                if nblock > 0.1 * len(win): continue
                mx = max(tiles(win[0]['board']))
                cands[win[0]['tier']][win[0]['player']].append((v, k, win, stage(mx)))
    meta = []
    for tier, n in per.items():
        players = list(cands[tier])
        rng.shuffle(players)
        for p in players: rng.shuffle(cands[tier][p])
        # round robin over players, preferring stages not yet covered
        picked, cover = [], collections.Counter()
        while len(picked) < n and any(cands[tier][p] for p in players):
            for p in players:
                if len(picked) >= n: break
                ws = cands[tier][p]
                if not ws: continue
                ws.sort(key=lambda w: cover[w[3]])
                picked.append(ws.pop(0)); cover[picked[-1][3]] += 1
        for i, (v, k, win, st) in enumerate(picked):
            sid = f"{tier[:3]}{i:02d}"
            with open(f'results/review/stretches/{sid}.txt', 'w') as f:
                for r in win: f.write(' '.join(map(str, tiles(r['board']))) + '\n')
            meta.append((sid, tier, win[0]['player'], v, k, len(win) - 1, max(tiles(win[0]['board'])), st))
    with open('results/review/stretches.tsv', 'w') as f:
        f.write('id\ttier\tplayer\tvideo\toffset\tmoves\tmax_start\tstage\n')
        for m in meta: f.write('\t'.join(map(str, m)) + '\n')
    c = collections.Counter((m[1], m[7]) for m in meta)
    print(len(meta), 'stretches;', dict(sorted(c.items())))
    print('players per tier:', {t: len({m[2] for m in meta if m[1] == t}) for t in per})


if __name__ == '__main__':
    main()
