#!/usr/bin/env python3
"""Board statistics by stage (largest tile 128 / 256 / 512 / 1024 / 2048) of a messy trace (corner held, chain length,
empty cells, big tiles off the edge) and the games' outcome rates; with --human, the same statistics of the curated
human positions per tier. usage: hm_genstats.py LABEL GAMES.tsv TRACE | hm_genstats.py --human"""
import collections, subprocess, sys
import numpy as np
KEYS = ['corner', 'chain_len', 'empty', 'big_off_edge', 'trapped']

def stats(rows):
    by = collections.defaultdict(list)
    for r in rows:
        mx = int(r['max_rank'])
        if 7 <= mx <= 11: by[mx].append(r)
    return {mx: {k: float(np.mean([float(x[k]) for x in xs])) for k in KEYS} | {'n': len(xs)} for mx, xs in by.items()}

def fmt(label, st, extra=''):
    cells = []
    for mx in range(7, 12):
        s = st.get(mx)
        cells.append(f"{2**mx:4d}: " + (f"c{s['corner']:.2f} ch{s['chain_len']:.1f} e{s['empty']:.1f} off{s['big_off_edge']:.2f}" if s and s['n'] >= 200 else '        -               '))
    print(f"{label:22s} " + ' | '.join(cells) + extra, flush=True)

def main():
    if sys.argv[1] == '--human':
        D = np.load('results/hm/data.npz')
        tiers = ['novice', 'intermediate', 'strong', 'expert']
        for t in range(4):
            ids = set(D['ids'][D['tier'] == t].tolist())
            rows = []
            with open('results/hm/feat.tsv') as f:
                hdr = f.readline().rstrip('\n').split('\t')
                for line in f:
                    p = line.rstrip('\n').split('\t')
                    if p[1] == '-1' and p[0] in ids: rows.append(dict(zip(hdr, p)))
            fmt('human ' + tiers[t], stats(rows))
        return
    label, games, trace = sys.argv[1:4]
    boards = [l.strip() for l in open(trace) if l.strip()]
    step = max(1, len(boards) // 60000)
    boards = boards[::step]
    inp = 'id\thex\n' + ''.join(f'{i}\t{b}\n' for i, b in enumerate(boards))
    out = subprocess.run(['./build_hm/hm_tool', '--preset', 'best-notables'], input=inp, capture_output=True,
                         text=True).stdout.strip().split('\n')
    hdr = out[0].split('\t')
    rows = [dict(zip(hdr, l.split('\t'))) for l in out[1:] if l.split('\t')[1] == '-1']
    c = collections.Counter()
    with open(games) as f:
        h = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(h, line.rstrip('\n').split('\t')))
            c[int(r['final_max'])] += 1
    n = sum(c.values())
    cum = lambda T: sum(v for k, v in c.items() if k >= T) / max(1, n)
    fmt(label, stats(rows), f"  || reach 512 {cum(512):.2f} 1024 {cum(1024):.2f} 2048 {cum(2048):.2f} 4096 {cum(4096):.2f} 8192 {cum(8192):.2f} ({n} games)")

if __name__ == '__main__':
    main()
