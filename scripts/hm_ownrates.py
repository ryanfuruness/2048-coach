#!/usr/bin/env python3
"""Big-mistake rates of a simulated player on its OWN trajectory (messy --trace): consecutive boards -> the move made,
a sample analysed by build/analyze (search losses on analyze's scale); rates of moves losing >= 3% / >= 15% per 100
moves by stage, next to the human players' rates on their own positions (results/hm/data.npz).
usage: hm_ownrates.py TRACE [N=3000] [TIER for the human comparison: 1]"""
import json, random, subprocess, sys
import numpy as np
DIRS = 'URDL'

def slide(row):
    nz = [x for x in row if x]; out = []; i = 0
    while i < len(nz):
        if i + 1 < len(nz) and nz[i] == nz[i + 1]: out.append(nz[i] + 1); i += 2
        else: out.append(nz[i]); i += 1
    return out + [0] * (4 - len(out))

def move(b, d):  # b: 16 ranks, d: 0 U 1 R 2 D 3 L
    g = [b[r * 4:(r + 1) * 4] for r in range(4)]
    if d in (1, 3):
        rows = [slide(r[::-1])[::-1] if d == 1 else slide(r) for r in g]
        return [x for r in rows for x in r]
    cols = [[g[r][c] for r in range(4)] for c in range(4)]
    cols = [slide(c[::-1])[::-1] if d == 2 else slide(c) for c in cols]
    return [cols[c][r] for r in range(4) for c in range(4)]

def infer(b, nb):
    for d in range(4):
        a = move(b, d)
        if a == b: continue
        diff = [i for i in range(16) if a[i] != nb[i]]
        if len(diff) == 1 and a[diff[0]] == 0 and nb[diff[0]] in (1, 2): return d
    return -1

def main():
    trace = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    tier = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    games, cur = [], []
    for line in open(trace):
        line = line.strip()
        if not line:
            if cur: games.append(cur); cur = []
            continue
        cur.append([int(ch, 16) for ch in line])
    if cur: games.append(cur)
    pairs = [(g[i], g[i + 1]) for g in games for i in range(len(g) - 1)]
    random.seed(1); random.shuffle(pairs)
    sel = []
    for b, nb in pairs:
        if not 7 <= max(b) <= 11: continue
        d = infer(b, nb)
        if d >= 0: sel.append((b, d))
        if len(sel) >= N: break
    inp = ''.join(f"played={DIRS[d]} | {''.join('%x' % x for x in b)}\n" for b, d in sel)
    out = subprocess.run(['./build/analyze', '--preset', 'best-notables', '--json', '--stdin'], input=inp,
                         capture_output=True, text=True).stdout.strip().split('\n')
    res = {}
    for (b, d), line in zip(sel, out):
        a = json.loads(line)
        vals = {m['move']: m['value'] for m in a['moves']}
        ref = vals.get(a['engine_move'], max(vals.values()))
        name = ['up', 'right', 'down', 'left'][d]
        if name not in vals: continue
        x = max(0.0, ref - vals[name]) / max(100000.0, abs(ref))
        st = 0 if max(b) <= 9 else 1
        res.setdefault(st, []).append(x)
    D = np.load('results/hm/data.npz')
    LS = np.nan_to_num(D['losss'], nan=0.0); P = D['played']; n = len(P)
    lp = LS[np.arange(n), P]
    for st, xs in sorted(res.items()):
        xs = np.array(xs)
        lo, hi = (7, 9) if st == 0 else (10, 11)
        s = (D['tier'] == tier) & (D['mx'] >= 2 ** lo) & (D['mx'] <= 2 ** hi)
        print(f"  stage {'128-512' if st == 0 else '1024-2048'}: own trajectory n={len(xs)}: >=3% {100 * (xs >= 0.03).mean():.2f} "
              f">=15% {100 * (xs >= 0.15).mean():.2f} per 100 moves | humans tier {tier} n={s.sum()}: "
              f">=3% {100 * (lp[s] >= 0.03).mean():.2f} >=15% {100 * (lp[s] >= 0.15).mean():.2f}")

if __name__ == '__main__':
    main()
