#!/usr/bin/env python3
"""Workstream yc: real positions with outcomes for the your-chance checks (the games of scripts/calib_personal_real.py:
a video's records in time order, split where the tile sum drops; outcome known when the game reached the target, or
ended in an observed death before - the board after the game's last recorded move and spawn has no legal move; else
censored). Per position: its milestone (2048, then the next doubling of the largest tile) and its next doubling.
Writes id, board, hist (the player's last 20 moves in the game), tier, player, game, played, milestone, outcome
(1 / 0 / -1 censored), double, outcome2 (the next doubling).
usage: yc_real.py OUT.tsv"""
import collections, gzip, json, sys

def slide(r):
    nz = [x for x in r if x]; out = []; i = 0
    while i < len(nz):
        if i + 1 < len(nz) and nz[i] == nz[i + 1]: out.append(nz[i] + 1); i += 2
        else: out.append(nz[i]); i += 1
    return out + [0] * (4 - len(out))

def apply(b, d):
    g = [b[i * 4:(i + 1) * 4] for i in range(4)]
    if d == 'L': g = [slide(r) for r in g]
    elif d == 'R': g = [slide(r[::-1])[::-1] for r in g]
    elif d == 'U':
        cols = [slide([g[i][c] for i in range(4)]) for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    else:
        cols = [slide([g[i][c] for i in range(4)][::-1])[::-1] for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    return sum(g, [])

def can_move(b):
    return any(apply(b, d) != b for d in 'URDL')

def parse(h):
    return [0 if c == '0' else 16 if c == 'g' else 17 if c == 'h' else int(c, 16) for c in h]

out = sys.argv[1]
rec = {}
for line in gzip.open('../2048-human-data/dataset_build/positions.jsonl.gz', 'rt'):
    a = json.loads(line)
    rec[(a['video'], a['segment'], a['ply'])] = a
byv = collections.defaultdict(list)
for k, a in rec.items(): byv[a['video']].append(a)
games = []
for v, rs in byv.items():
    rs.sort(key=lambda a: (a.get('t') or 0, a['segment'], a['ply']))
    prev, cur = None, []
    for a in rs:
        s = sum(1 << x for x in parse(a['board']) if x)
        if prev is not None and (s < prev - 64 or (s <= 16 and prev > 64)):
            games.append(cur); cur = []
        cur.append(a); prev = s
    games.append(cur)
n = dead_games = 0
cnt = collections.Counter()
with open(out, 'w') as f:
    f.write('id\tboard\thist\ttier\tplayer\tgame\tplayed\tmilestone\toutcome\tdouble\toutcome2\n')
    for gi, g in enumerate(games):
        boards = [parse(a['board']) for a in g]
        tops = [max(b) for b in boards]
        last = g[-1]; nb = apply(boards[-1], last['move']) if last.get('move') in ('U', 'R', 'D', 'L') else list(boards[-1])
        dead = None
        if last.get('spawn'):
            nb[last['spawn'][0]] = 1 if last['spawn'][1] == 2 else 2
            dead = not can_move(nb)
        dead_games += bool(dead)
        fin = max(max(nb), tops[-1])
        suf = [0] * len(g); m = fin
        for i in range(len(g) - 1, -1, -1):
            m = max(m, tops[i]); suf[i] = m
        moves = []
        for i, a in enumerate(g):
            played = a.get('move')
            if played not in ('U', 'R', 'D', 'L'):
                continue
            b = boards[i]
            if 1 <= tops[i] <= 13 and max(b) <= 15:
                M = max(11, tops[i] + 1); D = tops[i] + 1
                o1 = 1 if suf[i] >= M else (0 if dead else -1)
                o2 = 1 if suf[i] >= D else (0 if dead else -1)
                h = ''.join('0123456789abcdef'[x] for x in b)
                f.write(f"{a['video']}:{a['segment']}:{a['ply']}\t{h}\t{''.join(moves[-20:])}\t{a.get('tier','')}\t{a.get('player','')}\t{gi}\t{played}\t{1 << M}\t{o1}\t{1 << D}\t{o2}\n")
                n += 1; cnt[(a.get('tier', ''), o1)] += 1
            moves.append(played)
print(n, 'positions,', len(games), 'games,', dead_games, 'end in an observed death')
for k in sorted(cnt): print(k, cnt[k])
