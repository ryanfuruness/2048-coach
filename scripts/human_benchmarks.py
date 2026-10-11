#!/usr/bin/env python3
"""Population benchmarks for reviews: per player level (the largest tile of the video), the share of best-or-good moves
(estimated real loss < 1%), inaccuracies (1-3%), mistakes (3-10%) and blunders (>= 10%) per 100 moves, with the same
loss map as build/analyze (weights/calib/model.txt 'lossmap'). Uses the cached human analysis (observed decisions of
videos with explained_share >= 0.9).
usage: human_benchmarks.py [results/human/analysis.jsonl] [--model weights/calib/model.txt]"""
import json, sys, collections, statistics as st

def lossmap(path):
    for line in open(path):
        if line.startswith('lossmap '):
            xs = [float(x) for x in line.split()[1:]]
            return list(zip(xs[0::2], xs[1::2]))
    return None

def real(lm, x):
    if not lm: return x
    if x <= lm[0][0]: return lm[0][1]
    for (x0, y0), (x1, y1) in zip(lm, lm[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, lm[-1][1] * x / max(1e-12, lm[-1][0]))

def main():
    args = sys.argv[1:]
    path = args[0] if args and not args[0].startswith('--') else 'results/human/analysis.jsonl'
    model = args[args.index('--model') + 1] if '--model' in args else 'weights/calib/model.txt'
    lm = lossmap(model)
    summ = {d['video']: d for d in json.load(open('results/human/summary.json'))}
    per = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for line in open(path):
        a = json.loads(line)
        d = summ.get(a['video'])
        if not d or (d.get('explained') or 0) < 0.9 or a.get('observed') is False or a.get('game_over'):
            continue
        if 'played' not in a or len(a['moves']) < 2: continue
        ref = [m for m in a['moves'] if m['move'] == a['engine_move']]
        pm = [m for m in a['moves'] if m['move'] == a['played']]
        if not ref or not pm: continue
        x = max(0.0, ref[0]['value'] - pm[0]['value']) / max(100000.0, abs(ref[0]['value']))
        r = real(lm, x)
        c = per[a['video']]
        c[0] += 1; c[1] += r < 0.01; c[2] += 0.01 <= r < 0.03; c[3] += 0.03 <= r < 0.10; c[4] += r >= 0.10
    groups = collections.defaultdict(list)
    for vid, (n, g, i, m, b) in per.items():
        if n < 300: continue
        mt = summ[vid]['max_tile']
        k = '<=512' if mt <= 512 else '1024' if mt == 1024 else '2048-4096' if mt <= 4096 else '8192-16384' if mt <= 16384 else '32768+'
        groups[k].append((g / n, 100 * i / n, 100 * m / n, 100 * b / n))
    print("level        videos  best/good   inaccuracies   mistakes   blunders   (per 100 moves, medians)")
    out = {}
    for k in ['<=512', '1024', '2048-4096', '8192-16384', '32768+']:
        xs = groups.get(k)
        if not xs: continue
        med = [st.median(x[j] for x in xs) for j in range(4)]
        out[k] = dict(videos=len(xs), good=med[0], inaccuracies=med[1], mistakes=med[2], blunders=med[3])
        print(f"{k:12s} {len(xs):6d}   {100 * med[0]:6.1f}%   {med[1]:10.2f}   {med[2]:8.2f}   {med[3]:8.2f}")
    json.dump(out, open('results/human/benchmarks.json', 'w'), indent=1)

if __name__ == '__main__':
    main()
