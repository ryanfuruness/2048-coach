#!/usr/bin/env python3
"""Workstream review: the full-coverage player-level screen (results/review/roll_f/*.tsv, fgroups.tsv) joined with
every reviewed move (results/review/moves.tsv). mP = (P_ref - P_played) / P_ref (P = reach the next milestone with
the human move model at the review-fitted skill continuing; 32 CRN playouts), positions with P_ref >= 0.1, non-expert.
Reports: your_cost calibration on ALL moves; concentration of the measured loss in the review's flags (key moments,
warnings, hints, hard moments); recall of big losses; the decisive moment's rank among all moves of its stretch.
Noise: near-ties (value loss < 0.3%, played != reference) are ~0 in truth; their mP spread is the noise floor.
usage: review_full_report.py"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_report import tsv, fnum, spearman  # noqa: E402

P = collections.defaultdict(dict)
for g in tsv('results/review/fgroups.tsv'):
    keys = g['positions'].split(',')
    n = int(g['n'])
    for k in range(0, n, 400):
        f = f"results/review/roll_f/{g['group']}_{k}.tsv"
        if not os.path.exists(f) or os.path.getsize(f) == 0: continue
        for r in tsv(f):
            sid, ply = keys[k + int(r['pos'])].split(':')
            P[(sid, int(ply))][r['move']] = 1 - float(r['died'])
moves = [m for m in tsv('results/review/moves.tsv') if m['tier'] != 'expert']
rows = []
for m in moves:
    q = P.get((m['sid'], int(m['ply'])))
    if not q or m['ref'] not in q or m['played'] not in q or q[m['ref']] < 0.1 or m['judged'] != '1': continue
    m = dict(m); m['mP'] = (q[m['ref']] - q[m['played']]) / q[m['ref']]; m['Pref'] = q[m['ref']]
    rows.append(m)
print(f"measured moves: {len(rows)} of {len(moves)} non-expert reviewed moves")
null = [r['mP'] for r in rows if r['played'] != r['ref'] and float(r['value_loss']) < 0.003]
sd = math.sqrt(sum(x * x for x in null) / max(1, len(null)))
print(f"noise floor (near-ties, n={len(null)}): mean mP {sum(null) / len(null):+.4f}, rms {sd:.3f}, P(mP >= 10%) "
      f"{sum(x >= 0.10 for x in null) / len(null):.3f}, P(mP >= 20%) {sum(x >= 0.20 for x in null) / len(null):.3f}")
yc = lambda r: fnum(r['your_cost'])
print('\nyour_cost calibration on ALL moves (mean your_cost vs mean measured mP by your_cost bin)')
bins = [0, 0.003, 0.01, 0.03, 0.1, 0.3, 2]
for tier in ('all', 'novice', 'intermediate', 'strong'):
    xs = [r for r in rows if (tier == 'all' or r['tier'] == tier) and yc(r) is not None]
    cells = []
    for lo, hi in zip(bins, bins[1:]):
        b = [r for r in xs if lo <= yc(r) < hi]
        if b: cells.append(f"[{lo:g},{hi:g}) n={len(b)}: {sum(yc(r) for r in b) / len(b):.3f} vs {sum(r['mP'] for r in b) / len(b):+.3f}")
    print(f"  {tier:12s} " + ';  '.join(cells))
    print(f"  {'':12s} sum your_cost {sum(yc(r) for r in xs):.1f} vs sum mP {sum(r['mP'] for r in xs):.1f} over {len(xs)} moves;"
          f" Spearman (played != ref) {spearman([yc(r) for r in xs if r['played'] != r['ref']], [r['mP'] for r in xs if r['played'] != r['ref']]):.3f}")
print('\nWhere the measured loss sits: share of the total positive mP (moves with mP >= 5%, beyond the noise) and of big losses')
for tier in ('all', 'novice', 'intermediate', 'strong'):
    xs = [r for r in rows if tier == 'all' or r['tier'] == tier]
    tot = sum(r['mP'] for r in xs if r['mP'] >= 0.05)
    big = [r for r in xs if r['mP'] >= 0.20]
    out = []
    for lab, f in (('key', lambda r: r['key'] == '1'), ('warn', lambda r: r['warn'] == '1'),
                   ('hint', lambda r: r['hint'] == '1'), ('hard', lambda r: r['hard'] == '1'),
                   ('any flag', lambda r: r['key'] == '1' or r['warn'] == '1' or r['hint'] == '1'),
                   ('your_cost>=3%', lambda r: (yc(r) or 0) >= 0.03)):
        sel = [r for r in xs if f(r)]
        share = sum(r['mP'] for r in sel if r['mP'] >= 0.05) / max(1e-9, tot)
        rec = sum(1 for r in big if f(r)) / max(1, len(big))
        prec = sum(1 for r in sel if r['mP'] >= 0.20) / max(1, len(sel))
        out.append(f"{lab} {len(sel) / len(xs) * 100:.1f}% of moves: loss share {share:.2f}, recall(mP>=20%) {rec:.2f}, precision {prec:.2f}")
    print(f"  {tier:12s} total {tot:.1f}, big losses {len(big)} ({len(big) / len(xs) * 100:.2f}% of moves)")
    for o in out: print(f"      {o}")
print('\nDecisive moment vs all measured moves of its stretch (rank of its mP; top-5 share)')
dec = {}
for sid in {r['sid'] for r in rows}:
    s = json.loads(open(f'results/review/rev2/{sid}.jsonl').read().splitlines()[-1])['review']
    if 'decisive_move' in s: dec[sid] = s['decisive_move']
for tier in ('novice', 'intermediate', 'strong'):
    ranks, mps, nmv = [], [], []
    for sid, d in dec.items():
        xs = [r for r in rows if r['sid'] == sid]
        if not xs or xs[0]['tier'] != tier: continue
        dr = [r for r in xs if int(r['ply']) == d]
        if not dr: continue
        order = sorted(xs, key=lambda r: -r['mP'])
        ranks.append([int(r['ply']) for r in order].index(d) + 1); mps.append(dr[0]['mP']); nmv.append(len(xs))
    if ranks:
        ranks.sort()
        print(f"  {tier:12s} {len(ranks)} stretches: decisive move's mP median {sorted(mps)[len(mps) // 2]:.3f}; rank median {ranks[len(ranks) // 2]}"
              f" of ~{sum(nmv) // len(nmv)} moves; in the top 5: {sum(x <= 5 for x in ranks)}/{len(ranks)}; mP >= 10%: {sum(x >= 0.1 for x in mps)}/{len(mps)}")
json.dump(rows, open('results/review/full_measured.json', 'w'))
