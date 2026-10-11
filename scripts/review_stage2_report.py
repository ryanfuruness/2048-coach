#!/usr/bin/env python3
"""Workstream review, stage 2 report: 256-playout player-level truth (human move model at the review-fitted skill,
to the next milestone) for all flagged moves of the non-expert stretches and a uniform random sample of 1000 unflagged
moves (results/review/s2_sample.tsv, roll_s2/*.tsv). mP = (P_ref - P_played)/P_ref, positions with P_ref >= PMIN.
Precision of each flag, the unflagged rate, recall of big losses (flagged true / (flagged true + unflagged rate x
#unflagged)), your_cost calibration (random sample weighted up to the unflagged population), noise floor (near-ties).
usage: review_stage2_report.py [--pmin 0.3]"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_report import tsv, fnum, spearman  # noqa: E402
PMIN = float(sys.argv[sys.argv.index('--pmin') + 1]) if '--pmin' in sys.argv else 0.3
P = collections.defaultdict(dict)
for g in tsv('results/review/s2groups.tsv'):
    keys = g['positions'].split(',')
    for k in range(0, int(g['n']), 100):
        f = f"results/review/roll_s2/{g['group']}_{k}.tsv"
        if not os.path.exists(f) or os.path.getsize(f) == 0: continue
        for r in tsv(f):
            sid, ply = keys[k + int(r['pos'])].split(':')
            P[(sid, int(ply))][r['move']] = 1 - float(r['died'])
kind = {(r['sid'], int(r['ply'])): r['kind'] for r in tsv('results/review/s2_sample.tsv')}
moves = {(m['sid'], int(m['ply'])): m for m in tsv('results/review/moves.tsv')}
allj = [m for m in moves.values() if m['tier'] != 'expert' and m['judged'] == '1' and int(m['nlegal']) >= 2]
yc = lambda m: fnum(m['your_cost']) or 0.0
isflag = lambda m: m['key'] == '1' or m['warn'] == '1' or m['hint'] == '1' or m['hard'] == '1' or yc(m) >= 0.03
rows = []
for k, kd in kind.items():
    q = P.get(k); m = moves.get(k)
    if not q or not m or m['ref'] not in q or m['played'] not in q or q[m['ref']] < PMIN: continue
    r = dict(m); r['mP'] = (q[m['ref']] - q[m['played']]) / q[m['ref']]; r['kind'] = kd; rows.append(r)
print(f"stage 2: {len(rows)} measured (P_ref >= {PMIN}) of {len(kind)} sampled; flagged population {sum(isflag(m) for m in allj)},"
      f" unflagged {sum(not isflag(m) for m in allj)}")
null = [r['mP'] for r in rows if r['kind'] == 'random' and r['played'] != r['ref'] and float(r['value_loss']) < 0.003]
if null:
    print(f"noise floor (random near-ties, n={len(null)}): mean {sum(null) / len(null):+.4f}, rms {math.sqrt(sum(x * x for x in null) / len(null)):.3f},"
          f" P(mP>=10%) {sum(x >= 0.1 for x in null) / len(null):.3f}, P(mP>=20%) {sum(x >= 0.2 for x in null) / len(null):.3f}")
for tier in ('all', 'novice', 'intermediate', 'strong'):
    sel = lambda r: tier == 'all' or r['tier'] == tier
    popF = sum(1 for m in allj if isflag(m) and (tier == 'all' or m['tier'] == tier))
    popU = sum(1 for m in allj if not isflag(m) and (tier == 'all' or m['tier'] == tier))
    R = [r for r in rows if r['kind'] == 'random' and sel(r)]
    Fl = [r for r in rows if r['kind'] == 'flagged' and sel(r)]
    if not R or not Fl: continue
    print(f"\n== {tier}: flagged measured {len(Fl)} (population {popF}), random unflagged measured {len(R)} (population {popU})")
    for thr in (0.10, 0.20):
        ru = sum(r['mP'] >= thr for r in R) / len(R)
        rf = sum(r['mP'] >= thr for r in Fl) / len(Fl)
        tf, tu = rf * popF, ru * popU
        print(f"   big loss = mP >= {thr:.2f}: flagged rate {rf:.3f}, unflagged rate {ru:.4f} -> recall {tf / max(1e-9, tf + tu):.2f}"
              f" (flagged {tf:.0f} vs unflagged {tu:.0f} of an estimated {tf + tu:.0f} big losses in {popF + popU} moves)")
    # share of the total measured loss in flagged moves: signed sums (noise cancels in expectation), weighted up
    tl_f = sum(r['mP'] for r in Fl) / len(Fl) * popF
    tl_u = sum(r['mP'] for r in R) / len(R) * popU
    k_u = sum(r['mP'] >= 0.2 for r in R)
    def binom_hi(k, n, z=1.645):  # Wilson upper bound
        p = k / n; d = 1 + z * z / n
        return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    def binom_lo(k, n, z=1.645):
        p = k / n; d = 1 + z * z / n
        return max(0.0, (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d)
    tf20 = sum(r['mP'] >= 0.2 for r in Fl) / len(Fl) * popF
    lo_rec = tf20 / max(1e-9, tf20 + binom_hi(k_u, len(R)) * popU)
    hi_rec = tf20 / max(1e-9, tf20 + binom_lo(k_u, len(R)) * popU)
    print(f"   share of the total measured loss (signed sums) in flagged moves: {tl_f / max(1e-9, tl_f + tl_u):.2f}"
          f" (flagged {tl_f:.1f}, unflagged {tl_u:.1f}); recall(mP>=20%) 90% CI [{lo_rec:.2f}, {hi_rec:.2f}] ({k_u} unflagged events)")
    print('   flag            n   mean est your_cost  mean mP   P(mP>=10%)  P(mP>=20%)   played=ref')
    for lab, f in (('key', lambda r: r['key'] == '1'), ('warn', lambda r: r['warn'] == '1'), ('hint', lambda r: r['hint'] == '1'),
                   ('hard', lambda r: r['hard'] == '1'), ('your_cost>=3%', lambda r: yc(r) >= 0.03), ('unflagged', None)):
        xs = R if f is None else [r for r in Fl if f(r)]
        if not xs: continue
        mp = [r['mP'] for r in xs]
        print(f"   {lab:14s} {len(xs):4d}   {sum(yc(r) for r in xs) / len(xs):14.3f}  {sum(mp) / len(mp):+8.3f}   {sum(x >= 0.1 for x in mp) / len(mp):9.3f}"
              f"   {sum(x >= 0.2 for x in mp) / len(mp):9.3f}   {sum(r['played'] == r['ref'] for r in xs) / len(xs):9.2f}")
    # your_cost calibration (flagged + random weighted up)
    bins = [0, 0.003, 0.01, 0.03, 0.1, 0.3, 2]
    cells = []
    for lo, hi in zip(bins, bins[1:]):
        num = den = esum = 0.0; n = 0
        for xs, w in ((Fl, popF / len(Fl)), (R, popU / len(R))):
            for r in xs:
                if lo <= yc(r) < hi: num += w * r['mP']; esum += w * yc(r); den += w; n += 1
        if n: cells.append(f"[{lo:g},{hi:g}) n={n}: {esum / den:.3f} vs {num / den:+.3f}")
    print('   your_cost calibration (est vs measured): ' + ';  '.join(cells))
    both = Fl + R
    print(f"   Spearman your_cost ~ mP on flagged+random (played != ref): "
          f"{spearman([yc(r) for r in both if r['played'] != r['ref']], [r['mP'] for r in both if r['played'] != r['ref']]):.3f}")
# decisive moment at the player level
dec = []
for sid in {m['sid'] for m in allj}:
    s = json.loads(open(f'results/review/rev2/{sid}.jsonl').read().splitlines()[-1])['review']
    d = s.get('decisive_move')
    if not d: continue
    r = [x for x in rows if x['sid'] == sid and int(x['ply']) == d]
    if r: dec.append((r[0]['tier'], r[0]['mP'], s.get('decisive_loss')))
if dec:
    print(f"\ndecisive moments measured: {len(dec)}; mP >= 10% in {sum(x[1] >= 0.1 for x in dec)}, >= 20% in {sum(x[1] >= 0.2 for x in dec)};"
          f" median mP {sorted(x[1] for x in dec)[len(dec) // 2]:.3f} (review's decisive_loss median {sorted(x[2] for x in dec)[len(dec) // 2]:.3f})")
json.dump(rows, open('results/review/stage2_measured.json', 'w'))
