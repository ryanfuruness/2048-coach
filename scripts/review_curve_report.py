#!/usr/bin/env python3
"""Workstream review, study 2 (player level): the chances curve C(t) = P(reach the stretch's target | the move played
at ply t, then the human move model at the stretch's skill), from results/review/roll_c/*.tsv + cgroups.tsv; the cost
of the review's decisive move at the player's level, mPdec = (P_ref - P_played)/P_ref at that ply (same position: no
spawn luck); and where the stretch's chances fell (10-ply windows of the curve).
usage: review_curve_report.py"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard_eval import NAME_OF, ref_move  # noqa: E402
from review_report import tsv  # noqa: E402

meta = {l.split('\t')[0]: l.split('\t') for l in open('results/review/stretches.tsv').read().splitlines()[1:]}
cur = collections.defaultdict(dict)   # sid -> ply -> {move: P}
for g in tsv('results/review/cgroups.tsv'):
    f = f"results/review/roll_c/{g['group']}.tsv"
    if not os.path.exists(f) or os.path.getsize(f) == 0: continue
    keys = g['positions'].split(',')
    for r in tsv(f):
        sid, ply = keys[int(r['pos'])].split(':')
        cur[sid].setdefault(int(ply), {})[r['move']] = 1 - float(r['died'])
res = collections.defaultdict(list)
for sid, pts in cur.items():
    L = open(f'results/review/rev2/{sid}.jsonl').read().splitlines()
    summ = json.loads(L[-1])['review']; per = L[:-1]
    tier = meta[sid][1]
    C = {}
    for ply, P in pts.items():
        a = json.loads(per[ply - 1]); pl = NAME_OF.get(a['played'])
        if pl in P: C[ply] = (P[pl], P, ref_move(a), pl)
    plies = sorted(C)
    if len(plies) < 3: continue
    grid = [p for p in plies if (p - 1) % 10 == 0]
    drops = [(C[a][0] - C[b][0], a, b) for a, b in zip(grid, grid[1:])]
    dec = summ.get('decisive_move')
    d = dict(sid=sid, tier=tier, start=C[plies[0]][0], end=C[plies[-1]][0], n=len(grid), dec=dec,
             maxdrop=max(drops)[0] if drops else None)
    if dec and dec in C:
        Pd, P, ref, pl = C[dec]
        if ref in P and P[ref] >= 0.1:
            d['mPdec'] = (P[ref] - P[pl]) / P[ref]
            d['dec_abs'] = P[ref] - P[pl]
            win = [x for x in drops if x[1] < dec <= x[2]]
            d['dec_window_drop'] = win[0][0] if win else None
            d['dec_in_maxwin'] = bool(win) and win[0][0] == max(drops)[0]
            d['rank_window'] = sorted([x[0] for x in drops], reverse=True).index(win[0][0]) + 1 if win else None
    res[tier].append(d)
print('tier          stretches  C(start)  C(end)  with decisive  decisive cost mP (median)  abs drop (mean)  '
      'in the 10-ply window with the largest curve drop  median window rank')
for t in ('novice', 'intermediate', 'strong', 'expert'):
    xs = res[t]
    if not xs: continue
    dd = [x for x in xs if 'mPdec' in x]
    mp = sorted(x['mPdec'] for x in dd)
    ranks = sorted(x['rank_window'] for x in dd if x.get('rank_window'))
    print(f"{t:12s} {len(xs):9d}  {sum(x['start'] for x in xs) / len(xs):8.3f} {sum(x['end'] for x in xs) / len(xs):7.3f}"
          f"  {len(dd):13d}  {mp[len(mp) // 2] if mp else float('nan'):24.3f}  {sum(x['dec_abs'] for x in dd) / max(1, len(dd)):15.3f}"
          f"  {sum(x['dec_in_maxwin'] for x in dd)}/{len(dd)}{'':37s}  {ranks[len(ranks) // 2] if ranks else '-'} of ~{sum(x['n'] for x in dd) // max(1, len(dd))}")
# share of the stretch's total chance drop explained by the decisive move (stretches whose curve fell >= 0.2)
for t in ('novice', 'intermediate', 'strong', 'expert'):
    xs = [x for x in res[t] if x['start'] - x['end'] >= 0.2]
    if not xs: continue
    with_dec = [x for x in xs if 'mPdec' in x]
    sh = sorted(x['dec_abs'] / (x['start'] - x['end']) for x in with_dec)
    print(f"  {t}: {len(xs)} stretches whose chances fell >= 0.2; {len(with_dec)} have a decisive moment; its share of the"
          f" fall: median {sh[len(sh) // 2] if sh else float('nan'):.2f}")
json.dump(res, open('results/review/curve.json', 'w'))
