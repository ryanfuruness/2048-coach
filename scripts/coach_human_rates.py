#!/usr/bin/env python3
"""Coach test on real games: how often would the guard (warn when the move the player is about to make loses >= X of
the position's value by the engine's analysis) speak for REAL players? Per tier and stage group, warnings per 100
moves at each threshold, from results/human_ds/analysis.jsonl (certain moves only), with a 90% interval over players.
usage: coach_human_rates.py"""
import json, collections, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coach_select import group_of, DIRS  # noqa: E402

XS = [0.02, 0.05, 0.15, 0.4]
per = collections.defaultdict(lambda: np.zeros(1 + len(XS)))  # (group, tier, player) -> n, warnings per X
for line in open('results/human_ds/analysis.jsonl'):
    a = json.loads(line)
    if not a.get('observed', True) or a.get('maybe_two_moves') or a.get('rest_ambiguous') or not a.get('engine_move'): continue
    tiles = [v for row in a['board'] for v in row]
    g = group_of(max(tiles)) or ('S4' if max(tiles) >= 16384 else None)
    if g is None: continue
    vals = {DIRS[m['move']]: m['value'] for m in a['moves']}
    pl, em = DIRS.get(a['played']), DIRS[a['engine_move']]
    if pl not in vals or em not in vals: continue
    best = max(vals.values()) if max(tiles) < 16384 else vals[em]
    rel = max(0.0, best - vals[pl]) / max(100000.0, abs(best))
    c = per[(g, a['tier'], a['player'])]
    c[0] += 1
    for j, x in enumerate(XS): c[1 + j] += rel >= x
cells = collections.defaultdict(list)
for (g, tier, pl), c in per.items():
    if c[0] >= 100: cells[(g, tier)].append(c)
print("warnings per 100 moves if the app warned on moves losing >= X of the value (median player [10%-90%])")
print("group tier          players  moves   " + "  ".join(f"X={x:<4g}" + " " * 13 for x in XS))
for k in sorted(cells):
    cs = np.array(cells[k])
    rates = 100 * cs[:, 1:] / cs[:, :1]
    tot = 100 * cs[:, 1:].sum(0) / cs[:, 0].sum()
    print(f"{k[0]}    {k[1]:12s} {len(cs):5d} {int(cs[:, 0].sum()):7d}   " + "  ".join(
        f"{np.median(rates[:, j]):5.2f} [{np.percentile(rates[:, j], 10):4.2f}-{np.percentile(rates[:, j], 90):5.2f}]" for j in range(len(XS)))
        + "   pooled " + " ".join(f"{x:.2f}" for x in tot))
