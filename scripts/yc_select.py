#!/usr/bin/env python3
"""Workstream yc: real positions for the human-chance ground truth (build/hv_tool first).
From results/human_ds/analysis.jsonl (curated real games), per largest tile (64 ... 4096) N positions: half
"corner-relevant" (the largest tile sits in a corner and some legal move takes it out while another keeps it), half
random; with the player's last 20 moves (same video segment) for the move model's habits.
usage: yc_select.py OUT.tsv [N=30] [SEED=1]"""
import json, random, sys

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

def parse(h):
    return [int(c, 16) for c in h]

def corner(b):
    m = max(b)
    return any(b[c] == m for c in (0, 3, 12, 15))

out, n, seed = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30, int(sys.argv[3]) if len(sys.argv) > 3 else 1
rng = random.Random(seed)
recs = [json.loads(l) for l in open('results/human_ds/analysis.jsonl')]
hist = {}
strata = {r: {'corner': [], 'any': []} for r in range(6, 13)}
prev_key, moves = None, []
for rec in recs:
    key = (rec['video'], rec.get('segment', 0))
    if key != prev_key:
        moves = []
        prev_key = key
    b = parse(rec['hex'])
    if max(b) > 15:
        continue
    played = (rec.get('played') or '?')[0].upper()
    legal = [d for d in 'URDL' if apply(b, d) != b]
    top = max(b)
    if top in strata and len(legal) >= 2:
        item = (rec['video'] + ':' + str(rec['ply']), rec['hex'], ''.join(moves[-20:]), rec.get('tier', ''))
        strata[top]['any'].append(item)
        if corner(b):
            keeps = [corner(apply(b, d)) for d in legal]
            if any(keeps) and not all(keeps):
                strata[top]['corner'].append(item)
    if played in 'URDL':
        moves.append(played)
with open(out, 'w') as f:
    f.write('id\tboard\thist\ttier\tset\n')
    for top, s in strata.items():
        c = rng.sample(s['corner'], min(n // 2, len(s['corner'])))
        used = {x[0] for x in c}
        a = rng.sample([x for x in s['any'] if x[0] not in used], min(n - len(c), len(s['any'])))
        for x in c: f.write('\t'.join(x) + '\tcorner\n')
        for x in a: f.write('\t'.join(x) + '\tany\n')
        print(1 << top, 'corner-relevant', len(s['corner']), 'all', len(s['any']), 'chosen', len(c), len(a))
