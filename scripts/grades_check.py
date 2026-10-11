#!/usr/bin/env python3
"""Move grades in real situations (app v3; src/analyze.cpp grade_moves). Feeds build/analyze --stdin and checks:
  A. corner: real positions whose biggest tile sits in a corner - every legal move that takes it out (without making a
     new biggest tile) while another move keeps it: share graded blunder, per largest tile
  B. random key: one uniformly random legal move from real positions: grade shares per largest tile
  C. random keys in a row: 15 random moves (random new tiles) from real positions: grades per step, and how soon the
     first questionable or blunder comes
  D. real players' moves (reference only): grade shares per tier
usage: grades_check.py OUTDIR [N_PER_STAGE=250] [SEED=1]"""
import collections, csv, json, os, random, subprocess, sys

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

def corner(b):
    m = max(b); return m > 0 and any(b[c] == m for c in (0, 3, 12, 15))

def spawn(b, rng):
    e = [i for i, x in enumerate(b) if x == 0]
    b = list(b); b[rng.choice(e)] = 2 if rng.random() < 0.1 else 1; return b

def hexb(b): return ''.join('0123456789abcdef'[x] for x in b)
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

out_dir = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 250; rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
os.makedirs(out_dir, exist_ok=True)
rows = list(csv.DictReader(open('results/yc/pos_real.tsv'), delimiter='\t'))
by = collections.defaultdict(list)
for r in rows:
    b = [int(c, 16) for c in r['board']]
    if any(apply(b, d) != b for d in 'URDL'): by[max(b)].append(r)
stages = [8, 9, 10, 11, 12, 13]
sample = {st: rng.sample(by[st], min(N, len(by[st]))) for st in stages}
# the positions to analyze: the real ones, and the random-key sequences
seqs = []
for st in stages:
    for r in sample[st][:60]:
        b = [int(c, 16) for c in r['board']]; moves = []; boards = [b]
        for k in range(15):
            legal = [d for d in 'URDL' if apply(b, d) != b]
            if not legal: break
            d = rng.choice(legal); moves.append(d)
            b = spawn(apply(b, d), rng); boards.append(b)
        seqs.append((st, boards, moves))
lines, keys = [], []
for st in stages:
    for r in sample[st]: lines.append(r['board']); keys.append(('real', st, r['id']))
for i, (st, boards, moves) in enumerate(seqs):
    for k, b in enumerate(boards[:len(moves)]): lines.append(hexb(b)); keys.append(('seq', st, (i, k)))
res = subprocess.run(['./build/analyze', '--preset', 'best-notables', '--packed', 'weights/serve/v6c_i16.wp', '--stdin'],
                     input='\n'.join(lines) + '\n', capture_output=True, text=True)
an = [json.loads(l) for l in res.stdout.splitlines()]
assert len(an) == len(lines), (len(an), len(lines))
A = {k: a for k, a in zip(keys, an)}
def grades(a): return {NAME[m['move']]: m for m in a['moves'] if 'grade' in m}
rep = []
def say(s=''): print(s); rep.append(s)
say('A. biggest tile out of its corner (another move keeps it): share graded blunder')
for st in stages:
    n = bl = 0; miss = []
    for r in sample[st]:
        b = [int(c, 16) for c in r['board']]
        if not corner(b): continue
        g = grades(A[('real', st, r['id'])])
        keep = [d for d in g if corner(apply(b, d))]
        for d in g:
            a2 = apply(b, d)
            if corner(a2) or max(a2) > max(b) or not keep: continue
            n += 1; bl += g[d]['grade'] == 'blunder'
            if g[d]['grade'] != 'blunder': miss.append((r['board'], d, g[d]['grade'], g[d].get('why', '')))
    say(f"   {1 << st:5d}: {bl}/{n} = {100 * bl / max(1, n):.0f}%" + ('  (free stretch: not flagged by design)' if st <= 8 else '') +
        (f"   not blunders e.g. {miss[:2]}" if miss and st > 8 else ''))
say('B. one random key from a real position: grade shares')
for st in stages:
    c = collections.Counter()
    for r in sample[st]:
        g = grades(A[('real', st, r['id'])])
        if g: c[g[rng.choice(sorted(g))]['grade']] += 1
    n = sum(c.values())
    say(f"   {1 << st:5d}: n {n:3d}  best {100*c['best']/n:4.0f}%  good {100*c['good']/n:4.0f}%  questionable {100*c['questionable']/n:4.0f}%  blunder {100*c['blunder']/n:4.0f}%  -> flagged {100*(c['questionable']+c['blunder'])/n:4.0f}%")
say('C. 15 random keys in a row: share flagged per move, and moves until the first flag')
for st in stages:
    c = collections.Counter(); first = []
    for i, (s2, boards, moves) in enumerate(seqs):
        if s2 != st: continue
        f = None
        for k, d in enumerate(moves):
            g = grades(A[('seq', st, (i, k))])
            gr = g.get(d, {}).get('grade', 'none'); c[gr] += 1
            if f is None and gr in ('questionable', 'blunder'): f = k + 1
        first.append(f if f is not None else 99)
    n = sum(c.values()); first.sort()
    say(f"   {1 << st:5d}: moves {n:4d}  flagged {100*(c['questionable']+c['blunder'])/max(1,n):4.0f}% (blunders {100*c['blunder']/max(1,n):4.0f}%)  first flag after {first[len(first)//2]} moves (median), within 5 moves in {100*sum(1 for x in first if x<=5)/max(1,len(first)):.0f}% of runs")
say('D. real players (reference only): grade shares of the move they played')
for tier in ('novice', 'intermediate', 'strong'):
    c = collections.Counter()
    for st in stages:
        for r in sample[st]:
            if r['tier'] != tier: continue
            g = grades(A[('real', st, r['id'])])
            if r['played'] in g: c[g[r['played']]['grade']] += 1
    n = sum(c.values())
    if n: say(f"   {tier:12s} n {n:4d}  best {100*c['best']/n:4.0f}%  good {100*c['good']/n:4.0f}%  questionable {100*c['questionable']/n:4.0f}%  blunder {100*c['blunder']/n:5.1f}%")
open(os.path.join(out_dir, 'check.txt'), 'w').write('\n'.join(rep) + '\n')
