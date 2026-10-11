#!/usr/bin/env python3
"""Is the softmax player a faithful skill model? For each player and phase (largest tile <= 512, 1024-2048, 4096-8192,
16384+), fit the temperature t by maximum likelihood (as the review does), then compare the moves the softmax player
of that t would make with the moves the player made: expected vs actual number of moves per relative value loss bin
(loss vs the engine's move, the analysis' measure), summed over the player-phases of each tier.
usage: calib_skill_check.py [results/human_ds/analysis.jsonl]"""
import collections, json, math, sys
PHASES = [(0, 512), (1024, 2048), (4096, 8192), (16384, 1 << 30)]
BINS = [0, 0.001, 0.01, 0.03, 0.1, 0.3, 10]

def fit_t(ch):
    bt, bll, t = None, -1e300, 0.0003
    while t <= 1.0:
        ll = sum(-r[p] / t - math.log(sum(math.exp(-v / t) for v in r.values())) for r, p in ch)
        if ll > bll: bll, bt = ll, t
        t *= 1.1
    return bt

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'results/human_ds/analysis.jsonl'
    ch, tier = collections.defaultdict(list), {}
    for line in open(path):
        a = json.loads(line)
        if a.get('observed') is False or a.get('undone') or a.get('maybe_two_moves') or a.get('rest_ambiguous'): continue
        vals = {m['move']: m['value'] for m in a['moves']}
        if len(vals) < 2 or a.get('played') not in vals or a['engine_move'] not in vals: continue
        ref = vals[a['engine_move']]
        rel = {d: max(0.0, ref - v) / max(100000.0, abs(ref)) for d, v in vals.items()}
        top = max(max(r) for r in a['board'])
        ph = next(i for i, (lo, hi) in enumerate(PHASES) if lo <= top <= hi)
        ch[(a['player'], ph)].append((rel, a['played'])); tier[a['player']] = a.get('tier', '?')
    agg = collections.defaultdict(lambda: [[0.0] * (len(BINS) - 1), [0] * (len(BINS) - 1), 0, []])
    for (pl, ph), xs in ch.items():
        if len(xs) < 100: continue
        t = fit_t(xs)
        g = agg[(tier[pl], ph)]
        g[2] += len(xs); g[3].append(t)
        for rel, p in xs:
            z = sum(math.exp(-v / t) for v in rel.values())
            for d, v in rel.items():
                b = max(i for i in range(len(BINS) - 1) if v >= BINS[i])
                g[0][b] += math.exp(-v / t) / z
            b = max(i for i in range(len(BINS) - 1) if rel[p] >= BINS[i])
            g[1][b] += 1
    print("moves per 1000 by relative value loss of the chosen move: softmax player at the fitted t (expected) vs the "
          "players (actual); bins " + ' '.join(f"[{100 * a:g}-{100 * b:g}%)" for a, b in zip(BINS, BINS[1:])))
    for (tr, ph) in sorted(agg, key=lambda k: (['novice', 'intermediate', 'strong', 'expert'].index(k[0]), k[1])):
        e, a, n, ts = agg[(tr, ph)]
        ts.sort()
        print(f"{tr:12s} phase {PHASES[ph][0]:>5}-{min(PHASES[ph][1], 99999):<5} n={n:6d} median t {ts[len(ts) // 2]:.4f}: "
              + '  '.join(f"{1000 * x / n:6.1f}/{1000 * y / n:6.1f}" for x, y in zip(e, a)))

if __name__ == '__main__':
    main()
