#!/usr/bin/env python3
"""Coach test: which softmax temperature makes as many COSTLY mistakes as each human tier? The maximum-likelihood t
(coach_fit_t.py) explains every move choice, most of which are harmless near-ties early in a game; what decides
outcomes is how often a player makes a move that really costs (estimated real loss >= 3% / >= 10% by the installed
maps, losses from the engine's analysis at its depth). For every human position the softmax player's probabilities
come from soft_move's 1-ply losses (build/coach --mode fit), and its expected mistake / blunder rate is compared with
the humans' own rate on the same positions, per (stage group, tier).
usage: coach_match_t.py"""
import json, math, sys, collections
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from coach_select import load_model, stage_map, interp, group_of, DIRS  # noqa: E402

def main():
    knots, vbar, maps = load_model()
    l1 = {}
    with open('results/coach/fit_out.tsv') as f:
        next(f)
        for line in f:
            p = line.rstrip('\n').split('\t')
            l1[p[0]] = [float(x) for x in p[2:6]]
    TS = [0.001, 0.002, 0.003, 0.005, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2]
    acc = collections.defaultdict(lambda: np.zeros(3 + 3 * len(TS)))  # n, human mist, human blun, per t: mist, blun, match
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        rid = f"{a['video']}:{a['segment']}:{a['ply']}"
        if rid not in l1 or not a.get('engine_move'): continue
        tiles = [v for row in a['board'] for v in row]
        g = group_of(max(tiles))
        if g is None: continue
        vals = {DIRS[m['move']]: m['value'] for m in a['moves']}
        em = DIRS[a['engine_move']]
        if em not in vals: continue
        ref = vals[em]
        top = max(tiles)
        lm = stage_map(maps, top)
        rl = {}
        for d, v in vals.items():
            rl[d] = interp(lm, max(0.0, ref - v) / max(100000.0, abs(ref)))
        pl = DIRS.get(a['played'])
        if pl not in rl: continue
        L = l1[rid]
        c = acc[(g, a['tier'])]
        c[0] += 1; c[1] += rl[pl] >= 0.03; c[2] += rl[pl] >= 0.10
        legal = [k for k in range(4) if not math.isnan(L[k]) and 'URDL'[k] in rl]
        for j, t in enumerate(TS):
            w = np.array([math.exp(-L[k] / t) for k in legal]); w /= w.sum()
            c[3 + 3 * j] += sum(wi for wi, k in zip(w, legal) if rl['URDL'[k]] >= 0.03)
            c[4 + 3 * j] += sum(wi for wi, k in zip(w, legal) if rl['URDL'[k]] >= 0.10)
            c[5 + 3 * j] += sum(wi for wi, k in zip(w, legal) if 'URDL'[k] == em)
    print("per 100 moves: real mistakes (>= 3%) and blunders (>= 10%); softmax players on the same positions")
    print("group tier            n   human m/b  | " + "  ".join(f"t={t:g}: m/b" for t in TS))
    for k in sorted(acc):
        c = acc[k]; n = c[0]
        if n < 300: continue
        row = f"{k[0]}    {k[1]:12s} {int(n):6d}  {100*c[1]/n:5.2f}/{100*c[2]/n:4.2f} | "
        row += "  ".join(f"{100*c[3+3*j]/n:5.2f}/{100*c[4+3*j]/n:4.2f}" for j in range(len(TS)))
        print(row)
    print("engine-move match of the softmax players (humans: see tiers.json):")
    for k in sorted(acc):
        c = acc[k]; n = c[0]
        if n < 300: continue
        print(f"{k[0]}    {k[1]:12s} " + "  ".join(f"t={t:g}: {c[5+3*j]/n:.3f}" for j, t in enumerate(TS)))

if __name__ == '__main__':
    main()
