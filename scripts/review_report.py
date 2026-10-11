#!/usr/bin/env python3
"""Workstream review: does build/analyze --review point at the moments that really decided a game?
Inputs: results/review/moves.tsv (review_moments.py), pool.tsv, roll_e_*.tsv (engine continuing, all moves, 32 CRN
playouts, H=1000), roll_p/*.tsv + pgroups.tsv (human move model continuing at the position's playout skill until the
next milestone or death, 64 CRN playouts), rev2/*.jsonl summaries (decisive moment).
Measured losses (unbiased, against the analysis' own reference move ref, as scripts/scorecard_played.py):
  engine truth  mE = (q_ref - q_played) / max(|q_ref|, 100k)
  player truth  mP = (P_ref - P_played) / P_ref, P = 1 - died (reach the next milestone), positions with P_ref >= 0.1
usage: review_report.py [--out results/review/report_tables.txt]"""
import collections, glob, json, math, os, random, sys

GROUPS = [('non-expert', ('novice', 'intermediate', 'strong')), ('novice', ('novice',)),
          ('intermediate', ('intermediate',)), ('strong', ('strong',)), ('expert', ('expert',))]


def tsv(path):
    L = open(path).read().splitlines()
    h = L[0].split('\t')
    return [dict(zip(h, l.split('\t'))) for l in L[1:] if l]


def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def spearman(xs, ys):
    n = len(xs)
    if n < 5: return float('nan')
    def ranks(v):
        o = sorted(range(n), key=lambda i: v[i]); r = [0.0] * n; i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]: j += 1
            for k in range(i, j + 1): r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    a, b = ranks(xs), ranks(ys)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float('nan')


def boot_ci(vals, f, n=500, seed=1):
    rng = random.Random(seed)
    if len(vals) < 5: return (float('nan'), float('nan'))
    st = sorted(f([rng.choice(vals) for _ in vals]) for _ in range(n))
    return st[int(0.1 * n)], st[int(0.9 * n)]


def main():
    out_path = 'results/review/report_tables.txt'
    if '--out' in sys.argv: out_path = sys.argv[sys.argv.index('--out') + 1]
    out = open(out_path, 'w')
    def P(*a):
        s = ' '.join(str(x) for x in a); print(s); out.write(s + '\n')
    moves = tsv('results/review/moves.tsv')
    pool = tsv('results/review/pool.tsv')
    key_of = {(r['sid'], int(r['ply'])): r for r in moves}
    pos_of = {int(p['pos']): (p['sid'], int(p['ply'])) for p in pool}
    # engine truth
    qE = collections.defaultdict(dict)
    nchunks = 0
    for f in sorted(glob.glob('results/review/roll_e_*.tsv')):
        nchunks += 1
        L = tsv(f)
        # rollout positions are numbered within the chunk: offset = --skip; recover it from the board order
        for r in L: qE[(f, int(r['pos']))][r['move']] = (float(r['q']), float(r['q_se']), float(r['died']))
    # map chunk-local positions to pool indices: chunks are consecutive slices of pool.bin
    N = len(pool); C = (N + 3) // 4
    E = {}
    for (f, lp), d in qE.items():
        k = int(f.rsplit('_', 1)[1].split('.')[0])
        E[k * C + lp] = d
    # player truth
    Pt = {}
    pg = tsv('results/review/pgroups.tsv')
    for g in pg:
        f = f"results/review/roll_p/{g['group']}.tsv"
        if not os.path.exists(f) or os.path.getsize(f) == 0: continue
        idx = [int(x) for x in g['positions'].split(',')]
        for r in tsv(f):
            Pt.setdefault(idx[int(r['pos'])], {})[r['move']] = 1 - float(r['died'])
    P(f"engine-truth positions: {len(E)} of {N} (chunks {nchunks}); player-truth positions: {len(Pt)}")
    # per pool position: the measured losses of the played move
    rows = []
    for i, (sid, ply) in pos_of.items():
        m = key_of[(sid, ply)]
        r = dict(m)
        r['mE'] = r['mP'] = None
        ref, pl = m['ref'], m['played']
        if i in E and ref in E[i] and pl in E[i]:
            qr = E[i][ref][0]
            r['mE'] = (qr - E[i][pl][0]) / max(100000.0, abs(qr))
            r['mE_best'] = (max(v[0] for v in E[i].values()) - E[i][pl][0]) / max(100000.0, abs(qr))
        if i in Pt and ref in Pt[i] and pl in Pt[i] and Pt[i][ref] >= 0.1:
            r['mP'] = (Pt[i][ref] - Pt[i][pl]) / Pt[i][ref]
            r['P_ref'] = Pt[i][ref]
        rows.append(r)
    nj = collections.Counter((m['sid']) for m in moves if m['judged'] == '1')
    est = lambda r: fnum(r['real_loss'])

    # ---------------- Study 1: key moments vs random moments, engine truth
    P('\n== 1. Key moments vs random moments (engine continuing; measured mE = unbiased loss vs the reference move) ==')
    P('group          set  n     mean est  mean mE   P(mE>=3%)  P(mE>=10%)   [80% CI of P(mE>=10%)]')
    for gname, tiers in GROUPS:
        for s in ('K', 'R', 'W'):
            xs = [r for r in rows if s in r['sets'] and r['tier'] in tiers and r['mE'] is not None and r['judged'] == '1']
            if not xs: continue
            me = [r['mE'] for r in xs]
            lo, hi = boot_ci(me, lambda v: sum(x >= 0.10 for x in v) / len(v))
            P(f"{gname:14s} {s:3s} {len(xs):5d}   {sum(est(r) or 0 for r in xs) / len(xs):7.3f}  {sum(me) / len(me):7.3f}"
              f"   {sum(x >= 0.03 for x in me) / len(me):8.3f}   {sum(x >= 0.10 for x in me) / len(me):8.3f}     [{lo:.3f}, {hi:.3f}]")
    P('\nRecall of big losses (mE >= 10%): key-moment hits / (hits + random-move rate x non-key judged moves), per group')
    for gname, tiers in GROUPS:
        sids = {r['sid'] for r in rows if r['tier'] in tiers}
        K = [r for r in rows if 'K' in r['sets'] and r['tier'] in tiers and r['mE'] is not None and r['judged'] == '1']
        R = [r for r in rows if 'R' in r['sets'] and r['tier'] in tiers and r['mE'] is not None]
        if not K or not R: continue
        for thr in (0.03, 0.10):
            hits = sum(r['mE'] >= thr for r in K)
            rate = sum(r['mE'] >= thr for r in R) / len(R)
            nonkey = sum(nj[s] for s in sids) - len(K)
            miss = rate * nonkey
            P(f"  {gname:14s} thr {thr:.2f}: key hits {hits}/{len(K)} (precision {hits / len(K):.2f}), random rate {rate:.4f}"
              f" x {nonkey} non-key moves = {miss:.1f} missed -> recall {hits / max(1e-9, hits + miss):.2f}")
    P('\nRank correlation (Spearman) of the review estimate (real_loss) with mE')
    for gname, tiers in GROUPS:
        for sets, lab in (('KR', 'key+random'), ('R', 'random only')):
            xs = [r for r in rows if any(c in r['sets'] for c in sets) and r['tier'] in tiers and r['mE'] is not None
                  and r['judged'] == '1' and est(r) is not None]
            if len(xs) < 5: continue
            P(f"  {gname:14s} {lab:12s} n={len(xs):4d}  rho = {spearman([est(r) for r in xs], [r['mE'] for r in xs]):.3f}"
              f"   (value loss: {spearman([float(r['value_loss']) for r in xs], [r['mE'] for r in xs]):.3f})")
    P('\nCalibration of the estimate on key+random moves (mean est vs mean mE by est bin)')
    bins = [0, 0.003, 0.01, 0.03, 0.1, 0.3, 2]
    for gname, tiers in (GROUPS[0], GROUPS[4]):
        xs = [r for r in rows if ('K' in r['sets'] or 'R' in r['sets']) and r['tier'] in tiers and r['mE'] is not None
              and r['judged'] == '1' and est(r) is not None]
        cells = []
        for lo, hi in zip(bins, bins[1:]):
            b = [r for r in xs if lo <= est(r) < hi]
            if b: cells.append(f"[{lo:g},{hi:g}) n={len(b)} {sum(est(r) for r in b) / len(b):.3f} vs {sum(r['mE'] for r in b) / len(b):.3f}")
        P(f"  {gname}: " + ';  '.join(cells))

    # ---------------- Study 2: decisive moment
    P('\n== 2. Decisive moment ==')
    dec = {}
    for f in glob.glob('results/review/rev2/*.jsonl'):
        sid = os.path.basename(f)[:-6]
        s = json.loads(open(f).read().splitlines()[-1])['review']
        if 'decisive_move' in s: dec[sid] = s['decisive_move']
    for gname, tiers in GROUPS:
        ok = tot = top1 = 0; ranks = []; okP = totP = 0
        for sid in {r['sid'] for r in rows if r['tier'] in tiers}:
            meas = [r for r in rows if r['sid'] == sid and r['mE'] is not None and r['judged'] == '1']
            if sid not in dec or not meas: continue
            d = [r for r in meas if int(r['ply']) == dec[sid]]
            if not d: continue
            tot += 1
            order = sorted(meas, key=lambda r: -r['mE'])
            rk = [int(r['ply']) for r in order].index(dec[sid]) + 1
            ranks.append(rk); top1 += rk == 1; ok += d[0]['mE'] >= 0.03
            measP = [r for r in rows if r['sid'] == sid and r['mP'] is not None]
            dP = [r for r in measP if int(r['ply']) == dec[sid]]
            if dP:
                totP += 1
                okP += max(measP, key=lambda r: r['mP'])['ply'] == dP[0]['ply']
        if tot:
            P(f"  {gname:14s} stretches with a decisive moment {tot}: its mE >= 3% in {ok} ({ok / tot:.0%}); it is the"
              f" largest measured loss of the stretch's {sum(1 for _ in ranks)} in {top1} ({top1 / tot:.0%}); median rank"
              f" {sorted(ranks)[len(ranks) // 2]}; player truth: the largest mP in {okP}/{totP}")
    P('  stretches without a decisive moment (no loss >= 3% from a healthy position):',
      sum(1 for f in glob.glob('results/review/rev2/*.jsonl') if os.path.basename(f)[:-6] not in dec))

    # ---------------- Study 3: player level
    P('\n== 3. Player level (human move model continuing at the review-fitted skill; mP = share of own chances lost) ==')
    P('group          set  n     mean your_cost  mean mP   P(mP>=3%)  P(mP>=10%)  played=ref')
    for gname, tiers in GROUPS[:4]:
        for s in ('H', 'D', 'W', 'K', 'R'):
            xs = [r for r in rows if s in r['sets'] and r['tier'] in tiers and r['mP'] is not None]
            if not xs: continue
            mp = [r['mP'] for r in xs]
            yc = [fnum(r['your_cost']) or 0 for r in xs]
            P(f"{gname:14s} {s:3s} {len(xs):5d}   {sum(yc) / len(yc):10.3f}  {sum(mp) / len(mp):8.3f}   {sum(x >= 0.03 for x in mp) / len(mp):8.3f}"
              f"   {sum(x >= 0.10 for x in mp) / len(mp):8.3f}   {sum(r['played'] == r['ref'] for r in xs) / len(xs):.2f}")
    P('\nyour_cost calibration (key+random+warn+hint+hard; mean your_cost vs mean mP by your_cost bin), non-expert')
    xs = [r for r in rows if r['tier'] != 'expert' and r['mP'] is not None and fnum(r['your_cost']) is not None]
    cells = []
    for lo, hi in zip(bins, bins[1:]):
        b = [r for r in xs if lo <= fnum(r['your_cost']) < hi]
        if b: cells.append(f"[{lo:g},{hi:g}) n={len(b)} {sum(fnum(r['your_cost']) for r in b) / len(b):.3f} vs {sum(r['mP'] for r in b) / len(b):.3f}")
    P('  ' + ';  '.join(cells))
    P(f"  Spearman your_cost ~ mP: {spearman([fnum(r['your_cost']) for r in xs], [r['mP'] for r in xs]):.3f} (n={len(xs)})")
    P('\nHints: expected error at the hint position (error_risk) vs the measured cost of what the player did')
    for gname, tiers in GROUPS[:4]:
        H = [r for r in rows if 'H' in r['sets'] and r['tier'] in tiers and r['mP'] is not None]
        R = [r for r in rows if 'R' in r['sets'] and r['tier'] in tiers and r['mP'] is not None]
        if H and R:
            P(f"  {gname:14s} hints n={len(H)}: mean mP {sum(r['mP'] for r in H) / len(H):.3f} (error_risk {sum(fnum(r['error_risk']) or 0 for r in H) / len(H):.3f});"
              f" random n={len(R)}: mean mP {sum(r['mP'] for r in R) / len(R):.3f} (error_risk {sum(fnum(r['error_risk']) or 0 for r in R) / len(R):.3f})")
    json.dump([{k: v for k, v in r.items()} for r in rows], open('results/review/measured.json', 'w'))
    out.close()


if __name__ == '__main__':
    main()
