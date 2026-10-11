#!/usr/bin/env python3
"""Think time vs move quality in the human games (results/human/analysis.jsonl from human_review.py): per think-time
bin, the share of moves that match the engine, the mean relative value loss and the rate of large losses (> 10%).
Long thinks happen in hard positions, so this is descriptive, not causal.
usage: human_think.py [results/human/analysis.jsonl]"""
import json, sys, collections
path = sys.argv[1] if len(sys.argv) > 1 else 'results/human/analysis.jsonl'
bins = [0, 0.15, 0.3, 0.6, 1.2, 3, 10, 1e9]
acc = collections.defaultdict(lambda: [0, 0, 0.0, 0])
for line in open(path):
    a = json.loads(line)
    if a.get('game_over') or 'played' not in a or 'think_s' not in a or not a['moves']:
        continue
    if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous'):
        continue
    best = max(m['value'] for m in a['moves'])
    rel = {m['move']: (best - m['value']) / max(100000.0, abs(best)) for m in a['moves']}
    if a['played'] not in rel:
        continue
    t = a['think_s']
    for i in range(len(bins) - 1):
        if bins[i] <= t < bins[i + 1]:
            x = acc[i]
            x[0] += 1; x[1] += a['played'] == a['engine_move']; x[2] += rel[a['played']]; x[3] += rel[a['played']] > 0.1
            break
print("  think time        moves   match   mean loss   >10% per 1000")
for i in range(len(bins) - 1):
    n, m, l, b = acc[i]
    if n:
        hi = f"{bins[i + 1]:.2f}s" if bins[i + 1] < 1e8 else "  ..."
        print(f"  [{bins[i]:5.2f}s, {hi:>6s}) {n:7d}  {100 * m / n:5.1f}%   {100 * l / n:7.3f}%   {1000 * b / n:8.2f}")
