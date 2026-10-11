#!/usr/bin/env python3
"""Workstream yc: a your-chance model (build/hv_tool eval output) vs the rollout ground truth (build/hv_tool first).
usage: yc_compare.py POS.tsv GT.tsv EVAL.tsv [KEY]"""
import collections, csv, math, sys

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
    m = max(b)
    return any(b[c] == m for c in (0, 3, 12, 15))

def corr(xs, ys):
    n = len(xs)
    if n < 3: return float('nan')
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx > 0 and sy > 0 else float('nan')

pos_file, gt_file, ev_file = sys.argv[1:4]
keys = set(sys.argv[4].split(',')) if len(sys.argv) > 4 else None
P = {r['id']: r for r in csv.DictReader(open(pos_file), delimiter='\t')}
gt = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
for r in csv.DictReader(open(gt_file), delimiter='\t'):
    if keys and r['key'] not in keys: continue
    for d in 'URDL':
        x = int(r['r_' + d])
        if x >= 0: gt[(r['id'], r['key'])][d][0] += x; gt[(r['id'], r['key'])][d][1] += 1
md = collections.defaultdict(dict)
for r in csv.DictReader(open(ev_file), delimiter='\t'):
    if r['move'] != '-': md[(r['id'], r['key'])][r['move']] = float(r['q'])
by = collections.defaultdict(list)
for k, mv in gt.items():
    if k not in md: continue
    b = [int(c, 16) for c in P[k[0]]['board']]
    by[(1 << max(b), k[1])].append((k, {d: s / n for d, (s, n) in mv.items()}, md[k], b))
print('tile  key     n  | mean chance rollout / model | corr(best chance) | within-position: corr of move deviations, '
      'same best | corner keep-leave rollout / model')
allx, ally = [], []
for (top, key) in sorted(by):
    rows = by[(top, key)]
    rb = [max(g.values()) for _, g, m, _ in rows]; mb = [max(m.values()) for _, g, m, _ in rows]
    dx, dy, same, kl_r, kl_m = [], [], 0, [], []
    for k, g, m, b in rows:
        ds = [d for d in g if d in m]
        if len(ds) < 2: continue
        gm = sum(g[d] for d in ds) / len(ds); mm = sum(m[d] for d in ds) / len(ds)
        for d in ds: dx.append(g[d] - gm); dy.append(m[d] - mm)
        same += max(ds, key=g.get) == max(ds, key=m.get)
        if corner(b):
            keep = [d for d in ds if corner(apply(b, d))]; leave = [d for d in ds if not corner(apply(b, d))]
            if keep and leave:
                kl_r.append(max(g[d] for d in keep) - max(g[d] for d in leave))
                kl_m.append(max(m[d] for d in keep) - max(m[d] for d in leave))
    allx += dx; ally += dy
    print(f"{top:5d} {key:6s} {len(rows):3d} | {sum(rb)/len(rb):.3f} / {sum(mb)/len(mb):.3f} | {corr(rb, mb):+.2f} | "
          f"{corr(dx, dy):+.2f}  {same}/{len(rows)} | {sum(kl_r)/max(1,len(kl_r)):+.3f} / {sum(kl_m)/max(1,len(kl_m)):+.3f} ({len(kl_r)})")
print(f"all move deviations: corr {corr(allx, ally):+.3f} (n {len(allx)}; rollout noise alone caps it: SE ~0.025 per move)")
