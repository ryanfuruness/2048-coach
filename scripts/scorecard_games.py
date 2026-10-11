#!/usr/bin/env python3
"""Game-level consistency of the per-move real losses (scorecard, 2026-10-07): do the analysis' estimated real losses
of the moves real players made compound into what those players actually achieved?

For every game of the curated set (../2048-human-data/dataset_build/positions.jsonl.gz, split into games where the tile
sum drops, as scripts/calib_personal_real.py) and every milestone stretch (from the first position with largest tile M
to the first with 2M = success, or to an observed death = failure; stretches whose video ends first are censored and
left out), the analysis' "chances kept" = product over the player's moves of (1 - estimated real loss), with the real
losses computed as a game review does (reference move = loss 0; the stage maps by the real largest tile; the
played-expert map for the player's own move from a real 16384 on; moves in block-formation positions not judged
unless --plain; inferred / undone / ambiguous moves skipped).

Test: if the real losses were exact expected relative losses of the engine-continuation chances V (engine odds of 2M),
W_t = V_t / kept_t would be a martingale and E[success / kept] = E[V_0] (V_0 = the engine odds of 2M at the stretch's
start). So R = sum over successful stretches of 1 / kept, divided by the sum of V_0 over all known stretches, should be
about 1 (somewhat above 1 because videos are selected for success and experts can beat the engine's own odds); R >> 1
means the per-move losses are inflated or do not compound like probabilities.

usage: scorecard_games.py --analysis results/human_ds_v6b/analysis.jsonl --model weights/calib/model.txt [--plain]
                          [--out results/scorecard/NAME/games.json] [--maps-override FILE (lossmap lines replacing the
                          model's: candidate corrections)]"""
import collections, gzip, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard_eval import model_maps, interp_map, stage_map, table_map, ref_move, NAME_OF  # noqa: E402
from calib_personal_real import parse  # noqa: E402

BUCKETS = [0, 0.003, 0.01, 0.03, 0.10, 0.30, 10]


def main():
    args = sys.argv[1:]
    opt = {'--analysis': 'results/human_ds_v6b/analysis.jsonl', '--model': 'weights/calib/model.txt', '--out': None,
           '--maps-override': None, '--full16k': None}
    plain = False
    while args:
        a = args.pop(0)
        if a == '--plain': plain = True
        else: opt[a] = args.pop(0)
    maps = model_maps(opt['--model'])
    if opt['--maps-override']:
        maps.update(model_maps(opt['--maps-override']))
    # games from the dataset records
    rec = []
    for line in gzip.open('../2048-human-data/dataset_build/positions.jsonl.gz', 'rt'):
        a = json.loads(line)
        rec.append((a['video'], a['segment'], a['ply'], a.get('t') or 0, a['board'], a['move'], a.get('spawn'),
                    a['player'], a['tier']))
    byv = collections.defaultdict(list)
    for r in rec: byv[r[0]].append(r)
    games = []
    for v, rs in byv.items():
        rs.sort(key=lambda r: (r[3], r[1], r[2]))
        prev, cur = None, []
        for r in rs:
            s = sum(1 << x for x in parse(r[4]) if x)
            if prev is not None and (s < prev - 64 or (s <= 16 and prev > 64)):
                games.append(cur); cur = []
            cur.append(r); prev = s
        games.append(cur)
    need = {(r[0], r[1], r[2]) for g in games for r in g}
    ana = {}
    for line in open(opt['--analysis']):
        a = json.loads(line)
        k = (a['video'], a['segment'], a['ply'])
        if k not in need: continue
        unclean = a.get('observed') is False or a.get('undone') or a.get('maybe_two_moves') or a.get('rest_ambiguous')
        top = max(max(r) for r in a['board'])
        mv = [dict(move=m['move'], value=m['value'], loss=m.get('loss'), reward=m.get('reward', 0), p=m.get('p'))
              for m in (a.get('moves') or [])]
        ana[k] = (mv, a.get('played'), a.get('engine_move'), top, a.get('odds') or {},
                  a.get('judged'), bool(unclean), a.get('source', 'search'))
    if opt['--full16k']:  # full-engine analyses (exact tables) of the 16384+ positions replace the table-less ones
        keys = [l.rstrip('\n').split('\t') for l in open('results/scorecard/inputs/human16k_keys.tsv')]
        nrep = 0
        for (v, sg, ply), line in zip(keys, open(opt['--full16k'])):
            k = (v, int(sg), int(ply))
            if k not in ana: continue
            a = json.loads(line)
            old = ana[k]
            mv = [dict(move=m['move'], value=m['value'], loss=m.get('loss'), reward=m.get('reward', 0), p=m.get('p'))
                  for m in (a.get('moves') or [])]
            ana[k] = (mv, old[1], a.get('engine_move'), old[3], a.get('odds') or {}, a.get('judged'), old[6],
                      a.get('source', 'search'))
            nrep += 1
        print(f"full-engine analyses for {nrep} positions with a real 16384+ ({opt['--full16k']})")
    stats = collections.defaultdict(lambda: dict(known=0, succ=0, cens=0, v0=0.0, inv=0.0, inv_cap=0.0, kept_succ=[], nll=0.0,
                                                 moves=0, judged=0, notjudged=0, skipped=0,
                                                 bucket=collections.Counter(), bucket_n=collections.Counter()))
    for g in games:
        tops = [max(parse(r[4])) for r in g]  # ranks
        last = g[-1]
        b = parse(last[4])
        from calib_personal_real import apply, can_move
        nb = apply(b, last[5])
        dead = None
        if last[6]:
            nb[last[6][0]] = 1 if last[6][1] == 2 else 2
            dead = not can_move(nb)
        final_top = max(max(nb), tops[-1])
        tier = g[0][8]
        for mr in range(8, 16):  # M = 256 .. 32768
            try:
                i = next(k for k, t in enumerate(tops) if t == mr)
            except StopIteration:
                continue
            j = next((k for k in range(i + 1, len(g)) if tops[k] > mr), None)
            if j is None:
                if final_top > mr: y = 1; j = len(g)
                elif dead: y = 0; j = len(g)
                else:
                    stats[(tier, 1 << mr)]['cens'] += 1; continue
            else:
                y = 1
            first = ana.get((g[i][0], g[i][1], g[i][2]))
            if first is None: continue
            v0 = first[4].get(str(1 << (mr + 1)))
            if v0 is None: continue
            st = stats[(tier, 1 << mr)]
            nll = 0.0
            for k in range(i, j):
                a = ana.get((g[k][0], g[k][1], g[k][2]))
                st['moves'] += 1
                if a is None or a[6] or not a[0] or a[1] is None:
                    st['skipped'] += 1; continue
                moves, played, eng, top, odds, judged, _, source = a
                if judged is False and not plain:
                    st['notjudged'] += 1; continue
                A = dict(moves=moves, engine_move=eng)
                r = ref_move(A)
                d = NAME_OF.get(played) if played in NAME_OF else (played if played in 'URDL' else None)
                if r is None or d is None: st['skipped'] += 1; continue
                vals = {NAME_OF[m['move']]: m['value'] for m in moves}
                if d not in vals: st['skipped'] += 1; continue
                x = 0.0 if d == r else max(0.0, vals[r] - vals[d]) / max(100000.0, abs(vals[r]))
                pp = {NAME_OF[m['move']]: m.get('p') for m in moves}
                if d == r:
                    L = 0.0
                elif not plain and source != 'search' and len(table_map(maps, True)) >= 4 and \
                        (pp.get(r) or 0) > 0 and pp.get(d) is not None and pp[d] >= 0:
                    # analyze's table rule for the player's own move (lossmap_table_played when the model has one)
                    L = interp_map(table_map(maps, True), max(0.0, (pp[r] - pp[d]) / pp[r]))
                else:
                    L = interp_map(stage_map(maps, top, played_expert=top >= 16384), x)
                L = min(L, 0.999999)
                st['judged'] += 1
                nll += -math.log(1 - L)
                bi = max(q for q in range(len(BUCKETS) - 1) if x >= BUCKETS[q])
                st['bucket'][bi] += -math.log(1 - L); st['bucket_n'][bi] += 1
            kept = math.exp(-nll)
            st['known'] += 1; st['succ'] += y; st['v0'] += v0; st['nll'] += nll
            if y:
                st['inv'] += 1 / max(kept, 1e-12); st['inv_cap'] += 1 / max(kept, 0.01); st['kept_succ'].append(kept)
    out = {}
    print(f"game-level check: {opt['--analysis']} with {opt['--model']}{' + ' + opt['--maps-override'] if opt['--maps-override'] else ''}"
          f"{' (plain)' if plain else ''}")
    print(f"{'tier':12s} {'M':>6s} {'known':>5s} {'cens':>4s} {'succ%':>6s} {'V0':>5s} {'R(cap)':>9s} {'kept|succ p50':>13s} "
          f"{'p10':>6s} {'<0.1':>5s} {'-ln kept/100mv':>14s}  share of -ln(kept) by value loss of the played move "
          f"(<0.3% / 0.3-1 / 1-3 / 3-10 / 10-30 / 30+ %)")
    for tier in ('novice', 'intermediate', 'strong', 'expert'):
        for M in (256, 512, 1024, 2048, 4096, 8192, 16384, 32768):
            st = stats.get((tier, M))
            if not st or st['known'] < 3: continue
            ks = sorted(st['kept_succ'])
            R = st['inv_cap'] / max(1e-9, st['v0'])  # 1 / kept capped at 100 (kept floored at 0.01): robust to one stretch
            p50 = ks[len(ks) // 2] if ks else float('nan')
            p10 = ks[len(ks) // 10] if ks else float('nan')
            low = sum(1 for k in ks if k < 0.1) / max(1, len(ks))
            tot = sum(st['bucket'].values())
            share = ' / '.join(f"{100 * st['bucket'][q] / tot:.0f}" if tot > 0 else '-' for q in range(len(BUCKETS) - 1))
            rate = 100 * st['nll'] / max(1, st['judged'])
            print(f"{tier:12s} {M:6d} {st['known']:5d} {st['cens']:4d} {100 * st['succ'] / st['known']:5.1f}% "
                  f"{st['v0'] / st['known']:5.2f} {R:9.2f} {p50:13.3f} {p10:6.3f} {100 * low:4.0f}% {rate:14.3f}  {share}"
                  f"   (judged {st['judged']}, not judged {st['notjudged']}, skipped {st['skipped']})")
            out[f"{tier} {M}"] = dict(known=st['known'], censored=st['cens'], success=st['succ'] / st['known'],
                                      v0=st['v0'] / st['known'], R=R, kept_succ_p50=p50, kept_succ_p10=p10,
                                      kept_succ_below_0_1=low, nll_per_100_moves=rate, judged=st['judged'],
                                      not_judged=st['notjudged'],
                                      share_by_bucket=[st['bucket'][q] / tot if tot > 0 else 0 for q in range(len(BUCKETS) - 1)])
    # Bellman drift along the players' own paths: the claimed value loss of each played move, (V_t - v_played) in
    # points, against what the next position's value says, e = V_{t+1} - (v_played - reward_played): the spawn's luck,
    # zero on average if the values are consistent along the path. If the later values systematically recover the
    # claimed losses (mean e > 0, comparable to the mean claim), the per-move claims are not real losses in the engine's
    # own terms: recovered share = mean e / mean claim (0 = the claims stick, 1 = fully recovered).
    drift = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])  # n, sum claim, sum e, sum e^2, sum claim>0 n
    for g in games:
        for k in range(len(g) - 1):
            r0, r1 = g[k], g[k + 1]
            if r1[1] != r0[1] or r1[2] != r0[2] + 1: continue
            a0, a1 = ana.get((r0[0], r0[1], r0[2])), ana.get((r1[0], r1[1], r1[2]))
            if a0 is None or a1 is None or a0[6] or a1[6] or not a0[0] or not a1[0] or a0[1] is None: continue
            if (a0[5] is False) and not plain: continue
            v0 = {m['move']: m for m in a0[0]}
            if a0[1] not in v0: continue
            r0m, r1m = ref_move(dict(moves=a0[0], engine_move=a0[2])), ref_move(dict(moves=a1[0], engine_move=a1[2]))
            if r0m is None or r1m is None: continue
            V0 = next(m['value'] for m in a0[0] if NAME_OF[m['move']] == r0m)  # the reference move's value
            V1 = next(m['value'] for m in a1[0] if NAME_OF[m['move']] == r1m)
            pm = v0[a0[1]]
            scale = max(100000.0, abs(V0))
            claim = max(0.0, V0 - pm['value']) / scale
            e = (V1 - (pm['value'] - (pm.get('reward') or 0))) / scale
            top = a0[3]
            st = 'early' if top <= 1024 else 'late' if top <= 8192 else 'top'
            for key in ((g[0][8], st), ('all', st)):
                d = drift[key]; d[0] += 1; d[1] += claim; d[2] += e; d[3] += e * e; d[4] += claim > 0.01
            cb = 0 if claim <= 0 else max(q for q in range(len(BUCKETS) - 1) if claim >= BUCKETS[q]) + 1
            for key in ((g[0][8], st, cb), ('all', st, cb)):
                d = drift[key]; d[0] += 1; d[1] += claim; d[2] += e; d[3] += e * e
    print("Bellman drift along the players' paths (consecutive analysed moves): mean claimed value loss of the played move"
          " vs the mean recovery e of the next position's value, both / max(|V|, 100k), x100")
    for tier in ('novice', 'intermediate', 'strong', 'expert', 'all'):
        for st in ('early', 'late', 'top'):
            d = drift.get((tier, st))
            if not d or d[0] < 50: continue
            n, sc, se, se2, nbig = d
            me = se / n; sd = math.sqrt(max(0.0, se2 / n - me * me)); sem = sd / math.sqrt(n)
            print(f"   {tier:12s} {st:5s} n={n:6d}  mean claim {100 * sc / n:6.3f}  mean e {100 * me:+6.3f} +- {100 * sem:.3f}"
                  f"  recovered share {me / (sc / n) if sc > 0 else float('nan'):5.2f}  (moves claimed > 1%: {100 * nbig / n:.1f}%)")
            out[f"drift {tier} {st}"] = dict(n=n, claim=sc / n, e=me, e_se=sem, recovered=me / (sc / n) if sc > 0 else None)
            cells = []
            for cb, lab in enumerate(('best', '<0.3', '0.3-1', '1-3', '3-10', '10-30', '30+')):
                d = drift.get((tier, st, cb))
                if not d or d[0] < 20: continue
                n2, sc2, se2_, se22, _ = d
                m2 = se2_ / n2; s2 = math.sqrt(max(0.0, se22 / n2 - m2 * m2)) / math.sqrt(n2)
                cells.append(f"{lab}: n={n2} claim {100 * sc2 / n2:.2f} e {100 * m2:+.2f}+-{100 * s2:.2f}")
                out[f"drift {tier} {st} {lab}"] = dict(n=n2, claim=sc2 / n2, e=m2, e_se=s2)
            print('        by claim (%): ' + ';  '.join(cells))
    if opt['--out']:
        json.dump(out, open(opt['--out'], 'w'), indent=1)


if __name__ == '__main__':
    main()
