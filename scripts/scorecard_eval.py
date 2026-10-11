#!/usr/bin/env python3
"""Scorecard evaluation (scripts/scorecard.sh): scores one configuration's analyses (results/scorecard/NAME/: judge,
odds and disputes JSON lines from build/analyze with the full engine, the model copy) against the fixed truth sets of
results/scorecard/inputs (scripts/scorecard_prep.py). Everything is measured on what build/analyze outputs, with the
analysis' own reference move (the table move when a table decided, else the best corner-lock-allowed move).

  A. robustness: the engine move significantly worse than the rollout-best move (> 2 combined se), by stage
     (unselected real positions: human300, late300, j1200; all moves judged, 32 playouts, H=1000)
  B. loss maps: the analysis' real_loss of every non-reference move vs the measured rollout loss against the same
     reference move, (q_ref - q_move) / max(|q_ref|, 100000) (unbiased; includes rollout noise), RMSE and calibration
     bins per stratum (early <= 1024, late 2048-8192, top >= 16384 search-decided, table-decided); not-judged moves
     (block formation) counted apart
  C. played-expert map: the analysis' estimate for the PLAYED move in 16384+ expert decisions (cal6's jx + jold, as a
     game review computes it: block abstention, table map, then the played-expert map) vs the measured loss; user-facing
     verdicts (blunder >= 10%, mistake >= 3%) on decisions the rollouts confirm / refute; block player vs snake experts
  D. raw claims on the 210 expert decisions (scripts/exp_late_claims.py's metric): value claims > 10% on refuted /
     confirmed disputes, with the H=300 truth (results/disputes/expert_h300.tsv) and the H=1000 truth (cal6's jold);
     table-aware (source block: p_best - p_move) and abstaining (not judged) unless --plain
  E. late claims on unselected positions (real tile >= 8192): Spearman of claim vs measured loss, claims > 10% refuted
  F. odds: engine-playout truth on real positions (r14, r15, t30 = fit sets of model v6; truth3 = 200 fresh positions
     no model saw), the near-dead board, a fresh board vs the benchmark base rates
usage: scorecard_eval.py NAME [--plain]   (--plain: score as the analysis worked before 2026-10-07: no block
       abstention, value claims everywhere, no table map)"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_late_claims as E  # noqa: E402

I = 'results/scorecard/inputs'
NAME_OF = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
PB = [0, 0.01, 0.03, 0.10, 0.30, 2]


def tsv(path):
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        return [dict(zip(hdr, l.rstrip('\n').split('\t'))) for l in f]


def model_maps(path):
    maps = {}
    for line in open(path):
        p = line.split()
        if p and p[0].startswith('lossmap') and p[0] != 'lossmap_own':
            maps[p[0]] = [float(x) for x in p[1:]]
    return maps


def interp_map(m, x):  # calib.h Calib::interp_map
    n = len(m) // 2
    if x <= m[0]: return m[1]
    for k in range(n - 1):
        x0, y0, x1, y1 = m[2 * k], m[2 * k + 1], m[2 * k + 2], m[2 * k + 3]
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, m[2 * n - 1] * x / max(1e-12, m[2 * n - 2]))


def table_map(maps, played=False):  # calib.h Calib::table_real_loss's map choice (cal7: played-move table map)
    if played and len(maps.get('lossmap_table_played', [])) >= 4: return maps['lossmap_table_played']
    return maps.get('lossmap_table', [])


def stage_map(maps, top, played_expert=False):  # calib.h Calib::real_loss's map choice
    if played_expert and len(maps.get('lossmap_played_expert', [])) >= 4: return maps['lossmap_played_expert']
    if top >= 16384 and len(maps.get('lossmap_top', [])) >= 4: return maps['lossmap_top']
    if top >= 2048 and len(maps.get('lossmap_late', [])) >= 4: return maps['lossmap_late']
    return maps['lossmap']


def ref_move(a):
    """The analysis' reference move (losses are measured against it): loss 0, the engine move on ties."""
    zero = [NAME_OF[m['move']] for m in a.get('moves', []) if m.get('loss') == 0]
    eng = NAME_OF.get(a.get('engine_move') or '', None)
    if eng in zero: return eng
    return zero[0] if zero else None


def rel_value(a, d, r):
    v = {NAME_OF[m['move']]: m['value'] for m in a['moves']}
    return max(0.0, v[r] - v[d]) / max(100000.0, abs(v[r]))


def table_p(a):
    return {NAME_OF[m['move']]: m['p'] for m in a['moves'] if 'p' in m}


def rmse(xs):
    return 100 * math.sqrt(sum((p - y) ** 2 for p, y in xs) / len(xs)) if xs else float('nan')


def bins(xs):
    cells = []
    for b in range(len(PB) - 1):
        c = [(p, y) for p, y in xs if PB[b] <= p < PB[b + 1]]
        if c:
            cells.append(f"[{100 * PB[b]:g}-{100 * PB[b + 1]:g}) n={len(c)} {100 * sum(p for p, _ in c) / len(c):.1f} vs "
                         f"{100 * sum(y for _, y in c) / len(c):.1f}")
    return ';  '.join(cells)


def ranks(xs):
    return E.ranks(xs)


def main():
    name = sys.argv[1]
    plain = '--plain' in sys.argv
    D = f'results/scorecard/{name}'
    maps = model_maps(f'{D}/model.txt')
    pos = tsv(f'{I}/judge_pos.tsv')
    q = collections.defaultdict(dict)
    for r in tsv(f'{I}/judge_truth.tsv'):
        q[int(r['id'])][r['move']] = (float(r['q']), float(r['q_se']))
    A = [json.loads(l) for l in open(f'{D}/judge.jsonl')]
    assert len(A) == len(pos), (len(A), len(pos))
    vp = {}
    try:
        vp.update(l.rstrip('\n').split('\t') for l in open('results/late/video_player.tsv'))
    except FileNotFoundError:
        pass
    group = lambda video: 'block player' if vp.get(video, '') in E.PDF_PLAYERS else 'snake experts'
    stage_of = lambda top: 'early' if top <= 1024 else 'late' if top <= 8192 else 'top'
    print(f"== scorecard evaluation: {name}{' (plain: no block abstention / table-aware claims)' if plain else ''}")
    M = dict(name=name, plain=plain)

    # ---------- A. robustness ----------
    rob = collections.defaultdict(lambda: [0, 0, 0.0])
    for p, a in zip(pos, A):
        if p['set'] not in ('human300', 'late300', 'j1200'): continue
        i = int(p['id']); qs = q[i]
        eng = NAME_OF.get(a.get('engine_move') or '', None)
        if eng not in qs or len(qs) < 2: continue
        b = max(qs, key=lambda m: qs[m][0])
        (qb, sb), (qe, se) = qs[b], qs[eng]
        st = stage_of(int(p['top']))
        for k in (st, 'all'):
            rob[k][0] += 1
            rob[k][1] += eng != b and qb - qe > 2 * math.sqrt(sb * sb + se * se)
            rob[k][2] += (qb - qe) / max(100000.0, abs(qb))
    print("A. robustness (engine move significantly worse than the rollout best, z=2; unselected real positions)")
    M['robustness'] = {k: dict(errors=rob[k][1], n=rob[k][0]) for k in ('early', 'late', 'top', 'all')}
    for k in ('early', 'late', 'top', 'all'):
        n, e, l = rob[k]
        print(f"   {k:6s} {e:3d}/{n:<5d} = {100 * e / max(1, n):4.1f}%   mean rollout shortfall of the engine move "
              f"{100 * l / max(1, n):.2f}% (incl. the max-of-noisy-estimates bias)")

    # ---------- B. loss maps ----------
    pts = collections.defaultdict(list)
    nj_pos = nj_moves = 0
    for p, a in zip(pos, A):
        if p['set'] not in ('human300', 'late300', 'j1200') or not a.get('moves'): continue
        i = int(p['id']); qs = q[i]
        r = ref_move(a)
        if a.get('judged') is False and not plain:
            nj_pos += 1; nj_moves += sum(1 for m in a['moves'] if NAME_OF[m['move']] != r); continue
        if r is None or r not in qs: continue
        top = int(p['top'])
        table = a.get('source', 'search') != 'search'
        for m in a['moves']:
            d = NAME_OF[m['move']]
            if d == r or d not in qs: continue
            pr = m.get('real_loss')
            if pr is None:
                if a.get('judged') is False and plain:  # the start analysis judged block positions like any other
                    pr = interp_map(stage_map(maps, top), rel_value(a, d, r))
                else:
                    continue
            y = (qs[r][0] - qs[d][0]) / max(100000.0, abs(qs[r][0]))
            st = 'table' if table else stage_of(top)
            pts[st].append((pr, y)); pts['all'].append((pr, y))
    print("B. loss maps: estimated real loss vs measured rollout loss against the same reference move (x100), "
          "non-reference moves of unselected real positions")
    for k in ('early', 'late', 'top', 'table', 'all'):
        xs = pts[k]
        if xs:
            print(f"   {k:6s} n={len(xs):5d}  RMSE {rmse(xs):5.2f}  mean est {100 * sum(p for p, _ in xs) / len(xs):5.2f}"
                  f" vs measured {100 * sum(y for _, y in xs) / len(xs):5.2f}")
            print(f"          bins (est vs measured): {bins(xs)}")
    print(f"   not judged (block formation, no deciding table): {nj_pos} positions, {nj_moves} moves")
    M['maps'] = {k: dict(n=len(pts[k]), rmse=rmse(pts[k]), est=100 * sum(p for p, _ in pts[k]) / max(1, len(pts[k])),
                         measured=100 * sum(y for _, y in pts[k]) / max(1, len(pts[k])))
                 for k in ('early', 'late', 'top', 'table', 'all') if pts[k]}
    M['maps']['not_judged_positions'] = nj_pos

    # ---------- C. played-expert map ----------
    cp = collections.defaultdict(list)
    ver = collections.defaultdict(collections.Counter)
    abst = collections.Counter()
    for p, a in zip(pos, A):
        if p['set'] not in ('jx', 'jold') or not a.get('moves'): continue
        top = int(p['top'])
        if top < 16384 or p['unclean'] == '1' or p['played'] in ('-', ''): continue
        i = int(p['id']); qs = q[i]
        d = NAME_OF.get(p['played'])
        r = ref_move(a)
        g = group(p['video'])
        if a.get('judged') is False and not plain:
            abst[g] += 1; continue
        if r is None or d is None or d == r or d not in qs or r not in qs: continue
        tp = table_p(a)
        pr = None
        if not plain and a.get('source', 'search') != 'search' and len(table_map(maps, True)) >= 4 \
                and tp.get(r, 0) > 0 and tp.get(d, -1) >= 0:
            pr = interp_map(table_map(maps, True), max(0.0, (tp[r] - tp[d]) / tp[r]))  # the player's own move
        if pr is None:
            pr = interp_map(stage_map(maps, top, True), rel_value(a, d, r))
        (qr, sr), (qd, sd) = qs[r], qs[d]
        y = (qr - qd) / max(100000.0, abs(qr))
        s = math.sqrt(sr * sr + sd * sd) / max(100000.0, abs(qr))
        v = 'confirmed' if y > 2 * s else ('refuted' if y < 2 * s and y <= s else 'unclear')
        for k in (g, 'all'):
            cp[k].append((pr, y))
            ver[k][(v, 'n')] += 1
            ver[k][(v, 'blunder')] += pr >= 0.10
            ver[k][(v, 'mistake')] += pr >= 0.03
    print("C. played move in 16384+ expert decisions (jx + jold, H=1000; the review's estimate vs measured, x100)")
    for k in ('snake experts', 'block player', 'all'):
        xs = cp[k]
        if not xs: continue
        c = ver[k]
        print(f"   {k:13s} n={len(xs):4d}  RMSE {rmse(xs):5.2f}  mean est {100 * sum(p for p, _ in xs) / len(xs):5.2f} vs "
              f"measured {100 * sum(y for _, y in xs) / len(xs):5.2f}" + (f"   abstained {abst[k]}" if k in abst else ''))
        print(f"          refuted {c[('refuted', 'n')]}: called blunder {c[('refuted', 'blunder')]}, mistake+ "
              f"{c[('refuted', 'mistake')]} (false alarms) | confirmed {c[('confirmed', 'n')]}: called blunder "
              f"{c[('confirmed', 'blunder')]}, mistake+ {c[('confirmed', 'mistake')]} (detections) | unclear "
              f"{c[('unclear', 'n')]}")
        print(f"          bins: {bins(xs)}")
    if abst:
        print(f"   abstained (block formation, no deciding table): {dict(abst)}")
    M['played'] = {k: dict(n=len(cp[k]), rmse=rmse(cp[k]), est=100 * sum(p for p, _ in cp[k]) / max(1, len(cp[k])),
                           measured=100 * sum(y for _, y in cp[k]) / max(1, len(cp[k])),
                           refuted=ver[k][('refuted', 'n')], refuted_blunder=ver[k][('refuted', 'blunder')],
                           refuted_mistake=ver[k][('refuted', 'mistake')], confirmed=ver[k][('confirmed', 'n')],
                           confirmed_blunder=ver[k][('confirmed', 'blunder')],
                           confirmed_mistake=ver[k][('confirmed', 'mistake')], abstained=abst.get(k, 0))
                   for k in ('snake experts', 'block player', 'all') if cp[k]}
    M['claims'] = {}

    # ---------- D. raw claims on the 210 expert decisions ----------
    Dj = [json.loads(l) for l in open(f'{D}/disputes.jsonl')]
    rows = E.meta()

    def claims_of(js):
        out = []
        for a in js:
            if not a.get('moves'):
                out.append(None); continue
            r = ref_move(a)
            if r is None:
                out.append(None); continue
            if not plain and a.get('judged') is False:
                out.append('abstain'); continue
            if not plain and a.get('source') == 'block':
                tp = table_p(a); best = max(tp.values()) if tp else 0
                rel = {d: max(0.0, best - max(0.0, tp.get(d, 0.0))) for d in (NAME_OF[m['move']] for m in a['moves'])}
            else:
                rel = {NAME_OF[m['move']]: rel_value(a, NAME_OF[m['move']], r) for m in a['moves']}
            out.append(dict(rel=rel, ref=r))
        return out
    C = claims_of(Dj)
    jold = {}
    for p in pos:
        if p['set'] == 'jold':
            jold[int(p['pos'])] = q[int(p['id'])]
    print("D. raw claims (value loss of the expert's move vs the reference; table-aware / abstaining unless plain) on the"
          " 210 expert decisions")
    for tname, Q in (('H=300', E.truth()), ('H=1000', jold)):
        V = E.verdicts(rows, Q)
        for g in ('block player', 'snake experts'):
            cnt, tot = collections.Counter(), collections.Counter()
            ab = 0
            for i, r in enumerate(rows):
                if i not in V or i >= len(C) or C[i] is None: continue
                if group(r['video']) != g: continue
                v = V[i]
                if C[i] == 'abstain':
                    ab += 1; tot[v['verdict']] += 1; continue
                c = C[i]['rel'].get(v['played'])
                if c is None: continue
                tot[v['verdict']] += 1
                cnt[v['verdict']] += c > 0.10
            M['claims'][f"{tname} {g}"] = dict(false=cnt['refuted'], refuted=tot['refuted'], kept=cnt['confirmed'],
                                                confirmed=tot['confirmed'], abstained=ab)
            print(f"   {tname:6s} {g:13s} false claims > 10% on refuted {cnt['refuted']:3d}/{tot['refuted']:<3d}  kept on "
                  f"confirmed {cnt['confirmed']:2d}/{tot['confirmed']:<2d}  unclear {cnt['unclear']:2d}/{tot['unclear']:<2d}"
                  f"  controls {cnt['control']}/{tot['control']}  abstained {ab}")

    # ---------- E. late claims on unselected positions ----------
    cl, rl, big, bigf, ab = [], [], 0, 0, 0
    for p, a in zip(pos, A):
        if p['set'] not in ('human300', 'late300', 'j1200') or int(p['top']) < 8192 or not a.get('moves'): continue
        i = int(p['id']); qs = q[i]
        c = claims_of([a])[0]
        if c is None: continue
        if c == 'abstain':
            ab += 1; continue
        r = c['ref']
        if r not in qs: continue
        for d, x in c['rel'].items():
            if d == r or d not in qs: continue
            (qr, sr), (qd, sd) = qs[r], qs[d]
            t = (qr - qd) / max(100000.0, abs(qr)); s = math.sqrt(sr * sr + sd * sd) / max(100000.0, abs(qr))
            cl.append(x); rl.append(t)
            if x > 0.10:
                big += 1; bigf += t < 2 * s
    rho = E.pearson(ranks(cl), ranks(rl))
    M['late_claims'] = dict(moves=len(cl), spearman=rho, big=big, big_not_real=bigf, abstained=ab)
    print(f"E. late claims, unselected real positions with a tile >= 8192: {len(cl)} moves, Spearman claim~real "
          f"{rho:.3f}; claims > 10%: {big}, not real (< 2 se) {bigf} ({100 * bigf / max(1, big):.0f}%); abstained "
          f"positions {ab}")

    # ---------- F. odds ----------
    op = tsv(f'{I}/odds_pos.tsv')
    O = [json.loads(l) for l in open(f'{D}/odds.jsonl')]
    sets = collections.defaultdict(list)
    extra = {}
    for p, a in zip(op, O):
        pr = a.get('odds', {}).get(p['target'])
        if p['set'] in ('neardead', 'fresh'):
            extra[p['set']] = a.get('odds', {}); continue
        if pr is None: continue
        y = float(p['measured'])
        k = 'truth3 (fresh)' if p['set'] == 'truth3' else ('r15+r15b' if p['set'].startswith('r15') else p['set'])
        sets[k].append((pr, y, p['stratum']))
        if p['set'] == 'truth3':
            sets['truth3 ' + ('tight' if 'T' in p['stratum'] else 'typical')].append((pr, y, p['stratum']))
    print("F. odds vs engine-playout truth on real positions (r14 P(16384), r15 P(32768), t30 tight P(16384): fit sets "
          "of model v6; truth3: 200 fresh positions, P(16384); truth4: 160 positions no fit saw, P(32768); P(32768) truth "
          "with best_v6c continuing)")
    for k in ('r14', 'r15+r15b', 'truth4', 't30', 'truth3 (fresh)', 'truth3 tight', 'truth3 typical'):
        xs = sets.get(k)
        if not xs: continue
        mae = sum(abs(p - y) for p, y, _ in xs) / len(xs)
        ll = sum(-(y * math.log(min(max(p, 1e-4), 1 - 1e-4)) + (1 - y) * math.log(1 - min(max(p, 1e-4), 1 - 1e-4)))
                 for p, y, _ in xs) / len(xs)
        M.setdefault('odds', {})[k] = dict(n=len(xs), predicted=sum(p for p, _, _ in xs) / len(xs),
                                           measured=sum(y for _, y, _ in xs) / len(xs), mae=mae, logloss=ll)
        print(f"   {k:15s} n={len(xs):3d}  predicted {sum(p for p, _, _ in xs) / len(xs):.3f} measured "
              f"{sum(y for _, y, _ in xs) / len(xs):.3f}  MAE {mae:.3f}  log-loss {ll:.3f}")
    allp = sets['r14'] + sets['t30'] + sets['truth3 (fresh)']
    print("   reliability P(16384) (r14 + t30 + truth3): " + ';  '.join(
        f"{lo:.2f}-{hi:.2f} n={len(b)} {sum(p for p, _, _ in b) / len(b):.3f} vs {sum(y for _, y, _ in b) / len(b):.3f}"
        for lo, hi in ((0, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01))
        for b in [[x for x in allp if lo <= x[0] < hi]] if len(b) >= 5))
    nd = extra.get('neardead', {})
    print(f"   near-dead board: P(16384) {nd.get('16384')} (measured 0.850, 120 playouts)")
    fr = extra.get('fresh', {})
    M['neardead'] = nd.get('16384'); M['fresh'] = fr
    json.dump(M, open(f'{D}/metrics.json', 'w'), indent=1)
    print("   fresh board (2 tiles): " + ', '.join(f"P({k}) {v}" for k, v in fr.items()) +
          "  [benchmarks: best_v5bb 99.8/99.6/98.7/95.4/59.8% for 2048-32768; best_v6b 95.4% 16384, 62.9% 32768]")


if __name__ == '__main__':
    main()
