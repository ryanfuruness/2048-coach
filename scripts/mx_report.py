#!/usr/bin/env python3
"""Workstream mx report: macroxue's 2048-ai as an independent judge of expert positions.

Inputs (results/mx/): positions.tsv (mx_tasks.py), eval_d*.out (judge E lines), play_*.out (judge P lines),
features.jsonl (our analyze --features on the same boards), and our rollout truth for the disputes
(results/disputes/expert_h300.tsv, verdicts as in dispute_report.py).

usage: mx_report.py [--eval results/mx/eval_d8.out ...] [--play results/mx/play_d4_h3000.out ...]
       mx_report.py --all    (every section on the standard files of the 2026-10-06 run)"""
import json, math, sys, collections

NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def load_positions():
    rows = {}
    with open('results/mx/positions.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            r['claimed'] = float(r['claimed'])
            r['max'] = int(r['max'])
            rows[r['id']] = r
    return rows

def load_eval(path):
    out = {}
    for line in open(path):
        p = line.rstrip('\n').split('\t')
        if not p or p[0] != 'E':
            continue
        e = dict(id=p[1], frame=p[2], src=p[3], move=p[4], value=float(p[5]), t=float(p[-1]), moves={})
        for x in p[6:-1]:
            q = x.split(':')
            if len(q) == 3:
                e['moves'][q[0]] = (float(q[1]), float(q[2]))  # (tuple prob or nan, search score)
        out[e['id']] = e
    return out

def mx_loss(e, mv):
    """macroxue's own relative shortfall of move mv vs its choice: tuple probabilities when a lookup table decided,
    else heuristic search scores (relative to |best|)."""
    if mv not in e['moves'] or e['move'] not in e['moves']:
        return None
    if e['src'].startswith('tuple'):
        b, v = e['moves'][e['move']][0], e['moves'][mv][0]
        if math.isnan(b) or math.isnan(v):
            return None
        return max(0.0, b - v)
    b, v = e['moves'][e['move']][1], e['moves'][mv][1]
    return max(0.0, b - v) / max(1.0, abs(b))

def our_truth():
    """our rollout verdicts on the disputes (as in scripts/dispute_report.py)"""
    meta = {}
    with open('results/disputes/expert.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            meta[int(r['idx'])] = r
    q = collections.defaultdict(dict)
    with open('results/disputes/expert_h300.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            q[int(r['pos'])][r['move']] = (float(r['q']), float(r['q_se']), float(r['died']))
    out = {}
    for i, m in meta.items():
        p, e = NAME[m['played']], NAME[m['engine']]
        if i not in q or p not in q[i] or e not in q[i] or p == e:
            continue
        (qp, sp, dp), (qe, se, de) = q[i][p], q[i][e]
        s = math.sqrt(sp * sp + se * se)
        best = max(v[0] for v in q[i].values())
        loss = qe - qp
        verdict = 'confirmed' if loss > 2 * s else ('refuted' if loss < 2 * s and qp >= qe - s else 'unclear')
        out[f"d{i}"] = dict(verdict=verdict, rel=loss / max(1.0, abs(best)), died_p=dp, died_e=de)
    return out

def pct(a, n):
    return f"{100 * a / n:5.1f}%" if n else "    -"

def agreement(pos, ev, label):
    print(f"\n## Move agreement ({label}): macroxue's move vs the expert's and our engine's")
    truth = our_truth()
    groups = collections.defaultdict(list)
    for i, e in ev.items():
        r = pos[i]
        groups[r['group']].append((r, e))
        groups[f"{r['group']} max {r['max']}"].append((r, e))
        if r['group'] == 'dispute' and i in truth:
            groups[f"dispute, ours {truth[i]['verdict']}"].append((r, e))
    print("| group | n | mx = expert | mx = our engine | mx = neither | expert = our engine | lookup-table share |")
    print("|---|---|---|---|---|---|---|")
    for g in sorted(groups, key=lambda s: (s.split()[0], s)):
        xs = groups[g]
        n = len(xs)
        a = sum(e['move'] == r['played'] for r, e in xs)
        b = sum(e['move'] == r['engine'] for r, e in xs)
        c = sum(e['move'] not in (r['played'], r['engine']) for r, e in xs)
        d = sum(r['played'] == r['engine'] for r, e in xs)
        t = sum(e['src'].startswith('tuple') for r, e in xs)
        print(f"| {g} | {n} | {pct(a, n)} | {pct(b, n)} | {pct(c, n)} | {pct(d, n)} | {pct(t, n)} |")
    # where the expert and our engine disagree (random positions), whom does macroxue side with?
    xs = [(r, e) for r, e in groups['random'] if r['played'] != r['engine']]
    if xs:
        n = len(xs)
        a = sum(e['move'] == r['played'] for r, e in xs)
        b = sum(e['move'] == r['engine'] for r, e in xs)
        print(f"\nRandom expert positions where the expert and our engine disagree: n={n}, macroxue sides with the expert"
              f" {pct(a, n)}, with our engine {pct(b, n)}, neither {pct(n - a - b, n)}")
        for lo, hi in ((0, 0.01), (0.01, 0.03), (0.03, 0.10), (0.10, 9)):
            ys = [(r, e) for r, e in xs if lo <= r['claimed'] < hi]
            if ys:
                m = len(ys)
                print(f"   our claimed loss {lo:4.0%}-{hi:4.0%}: n={m:3d}, mx = expert {pct(sum(e['move'] == r['played'] for r, e in ys), m)},"
                      f" mx = engine {pct(sum(e['move'] == r['engine'] for r, e in ys), m)}")
    # macroxue's own claimed loss of the expert's move in the disputes
    ys = [(r, e, mx_loss(e, r['played'])) for r, e in groups['dispute']]
    ys = [y for y in ys if y[2] is not None]
    if ys:
        tup = [y for y in ys if y[1]['src'].startswith('tuple')]
        srch = [y for y in ys if not y[1]['src'].startswith('tuple')]
        print(f"\nDisputes, macroxue's own shortfall of the expert's move: lookup-decided n={len(tup)}"
              + (f" mean {sum(y[2] for y in tup) / len(tup):.3f} (probability points)" if tup else "")
              + f"; search-decided n={len(srch)}"
              + (f", share below 10% of the heuristic score {pct(sum(y[2] < 0.10 for y in srch), len(srch))}" if srch else ""))
    tm = [e['t'] for e in ev.values()]
    print(f"\n(time per analysis: mean {sum(tm) / len(tm):.2f} s, max {max(tm):.2f} s)")

def load_play(paths):
    runs = collections.defaultdict(list)
    for path in paths:
        for line in open(path):
            p = line.rstrip('\n').split('\t')
            if not p or p[0] != 'P' or len(p) < 10 or p[4] == 'illegal':
                continue
            snaps = [tuple(int(v) for v in s.split(':')) for s in p[10:13]]
            runs[(p[1], p[2])].append(dict(seed=int(p[3]), moves=int(p[4]), dead=int(p[5]), gain=int(p[6]),
                                           start=int(p[7]), maxr=int(p[8]), sum=int(p[9]), snaps=snaps))
    return runs

def mean_se(xs):
    n = len(xs)
    if n == 0:
        return float('nan'), float('nan')
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / max(1, n - 1)
    return m, math.sqrt(v / n)

def playouts(pos, runs, label):
    print(f"\n## Playouts with macroxue continuing ({label})")
    truth = our_truth()
    rows = []
    for i, r in pos.items():
        if r['group'] != 'dispute':
            continue
        a, b = runs.get((i, r['played'])), runs.get((i, r['engine']))
        if not a or not b:
            continue
        sa = {x['seed']: x for x in a}
        sb = {x['seed']: x for x in b}
        seeds = sorted(set(sa) & set(sb))
        if len(seeds) < 4:
            continue
        res = dict(id=i, max=r['max'], claimed=r['claimed'], n=len(seeds), truth=truth.get(i, {}).get('verdict', '?'),
                   our_rel=truth.get(i, {}).get('rel', float('nan')))
        # survival differences (engine move minus expert move; positive = the engine's move survives more)
        for k, h in enumerate((300, 1000, 3000)):
            d = [((sb[s]['snaps'][k][0] == 1) - (sa[s]['snaps'][k][0] == 1)) for s in seeds
                 if sa[s]['snaps'][k][0] >= 0 and sb[s]['snaps'][k][0] >= 0]
            res[f'dsurv{h}'] = mean_se(d)
            res[f'surv_e{h}'] = mean_se([float(sb[s]['snaps'][k][0] == 1) for s in seeds if sb[s]['snaps'][k][0] >= 0])[0]
            res[f'surv_p{h}'] = mean_se([float(sa[s]['snaps'][k][0] == 1) for s in seeds if sa[s]['snaps'][k][0] >= 0])[0]
        res['dgain'] = mean_se([sb[s]['gain'] - sa[s]['gain'] for s in seeds])
        res['gain_e'] = mean_se([sb[s]['gain'] for s in seeds])[0]
        res['gain_p'] = mean_se([sa[s]['gain'] for s in seeds])[0]
        res['dmax'] = mean_se([(sb[s]['maxr'] > sb[s]['start']) - (sa[s]['maxr'] > sa[s]['start']) for s in seeds])
        rows.append(res)
    if not rows:
        print("no complete dispute playouts")
        return rows
    def verdict(m, se):
        if m > 2 * se and m > 0:
            return 'confirmed'
        if m < 2 * se and m <= se:
            return 'refuted'
        return 'unclear'
    for key, name in (('dsurv1000', 'survival after 1000 moves'), ('dsurv3000', 'survival after 3000 moves'),
                      ('dgain', 'score gained to the end / horizon')):
        c = collections.Counter()
        cross = collections.Counter()
        for x in rows:
            m, se = x[key]
            if math.isnan(m):
                continue
            v = verdict(m, se if se > 0 else 1e-9)
            c[v] += 1
            cross[(x['truth'], v)] += 1
        n = sum(c.values())
        print(f"\nmacroxue verdicts by {name} (engine move better by > 2 se = confirmed): n={n} {dict(c)}")
        print("| our rollouts \\ macroxue | confirmed | unclear | refuted |")
        print("|---|---|---|---|")
        for t in ('confirmed', 'unclear', 'refuted'):
            print(f"| {t} | {cross[(t, 'confirmed')]} | {cross[(t, 'unclear')]} | {cross[(t, 'refuted')]} |")
    for h in (300, 1000, 3000):
        se_ = [x[f'surv_e{h}'] for x in rows if not math.isnan(x[f'surv_e{h}'])]
        sp_ = [x[f'surv_p{h}'] for x in rows if not math.isnan(x[f'surv_p{h}'])]
        if se_:
            print(f"mean survival after {h} moves: our engine's move {sum(se_) / len(se_):.3f}, expert's move {sum(sp_) / len(sp_):.3f} (n={len(se_)})")
    g = [x['dgain'][0] for x in rows]
    print(f"mean score gained: engine's move {sum(x['gain_e'] for x in rows) / len(rows):.0f}, expert's move "
          f"{sum(x['gain_p'] for x in rows) / len(rows):.0f}; mean difference {sum(g) / len(g):.0f}")
    by = collections.defaultdict(list)
    for x in rows:
        by[x['max']].append(x)
    for t in sorted(by):
        ys = by[t]
        print(f"   max {t}: n={len(ys)}, survival@1000 engine {sum(y['surv_e1000'] for y in ys) / len(ys):.3f} vs expert "
              f"{sum(y['surv_p1000'] for y in ys) / len(ys):.3f}; gain diff {sum(y['dgain'][0] for y in ys) / len(ys):.0f}")
    return rows

FEATS = ('exposed', 'chain', 'corner', 'corner_dist', 'trapped', 'center', 'empty', 'merges', 'merge_rank', 'chain_ranks')

def load_features():
    out = {}
    ids = [line.split('\t')[0] for line in open('results/mx/positions.tsv')][1:]
    for i, line in zip(ids, open('results/mx/features.jsonl')):
        a = json.loads(line)
        out[i] = {NAME[m['move']]: m.get('features', {}) for m in a['moves']}
    return out

def feature_diffs(pos, ev, label):
    """concept features of the expert's afterstate minus our engine's, by whom macroxue sides with"""
    feats = load_features()
    truth = our_truth()
    groups = collections.defaultdict(list)
    for i, e in ev.items():
        r = pos[i]
        if r['played'] == r['engine'] or i not in feats:
            continue
        f = feats[i]
        if r['played'] not in f or r['engine'] not in f:
            continue
        d = {k: f[r['played']].get(k, 0) - f[r['engine']].get(k, 0) for k in FEATS}
        side = 'mx=expert' if e['move'] == r['played'] else ('mx=engine' if e['move'] == r['engine'] else 'mx=other')
        groups[f"{r['group']} {side}"].append(d)
        if r['group'] == 'dispute' and i in truth:
            groups[f"dispute ours-{truth[i]['verdict']}"].append(d)
    print(f"\n## Concept features, expert's afterstate minus our engine's ({label})")
    print("| group | n | " + " | ".join(FEATS) + " |")
    print("|---|---|" + "---|" * len(FEATS))
    for g in sorted(groups):
        xs = groups[g]
        n = len(xs)
        cells = []
        for k in FEATS:
            m = sum(x[k] for x in xs) / n
            cells.append(f"{m:+.0f}" if k == 'chain_ranks' else f"{m:+.2f}")
        print(f"| {g} | {n} | " + " | ".join(cells) + " |")

PDF_PLAYER = 'd4Nf6Bg5'  # the one expert in the curated set who plays the Perimeter Defense Formation (3x2 block)

def player_group(r):
    return 'PDF player' if r['player'] == PDF_PLAYER else 'snake experts'

def formation(ranks):
    """snake4: the 4 biggest tiles fill an edge line in order from the corner; block6: the 6 biggest fill a 3x2 corner
    block (macroxue's PDF); else corner-other / off-corner (by the biggest tile's cell)"""
    rk = [int(x) for x in ranks.split(',')] if isinstance(ranks, str) else ranks
    g = [rk[4 * i:4 * i + 4] for i in range(4)]
    vals = sorted([v for v in rk if v > 0], reverse=True)
    for t in range(8):
        h = [row[:] for row in g]
        if t & 1: h = [row[::-1] for row in h]
        if t & 2: h = h[::-1]
        if t & 4: h = [list(x) for x in zip(*h)]
        top = h[0]
        if top[0] == vals[0] and top[0] > top[1] > top[2] > top[3] and sorted(top, reverse=True) == vals[:4]:
            return 'snake4'
        blk = [h[0][0], h[0][1], h[0][2], h[1][0], h[1][1], h[1][2]]
        if sorted(blk, reverse=True) == vals[:6] and h[0][0] == vals[0]:
            return 'block6'
    return 'corner-other' if any(rk[c] == vals[0] for c in (0, 3, 12, 15)) else 'off-corner'

def formations(pos):
    print("\n## Formations (by group, player type, max tile)")
    c = collections.defaultdict(collections.Counter)
    for i, r in pos.items():
        c[f"{r['group']} {player_group(r)} max {r['max']}"][formation(r['ranks'])] += 1
    for k in sorted(c):
        print(f"   {k:38s} {dict(c[k])}")
    truth = our_truth()
    c2 = collections.defaultdict(list)
    for i, r in pos.items():
        if r['group'] == 'dispute' and i in truth:
            c2[(player_group(r), formation(r['ranks']))].append((r['claimed'], truth[i]['rel'], truth[i]['verdict']))
    print("   disputes, our rollout truth by player type and formation:")
    for k in sorted(c2):
        xs = c2[k]
        n = len(xs)
        v = collections.Counter(x[2] for x in xs)
        print(f"      {k[0]:14s} {k[1]:13s} n={n:3d} claimed {100 * sum(x[0] for x in xs) / n:5.1f}% rollout "
              f"{100 * sum(x[1] for x in xs) / n:+6.1f}% {dict(v)}")

def pairwise(pos, ev, label):
    """macroxue's preference between the expert's and our engine's move (table probabilities when a lookup table
    decided, else search scores relative to the best; ties within 1 point / 1%) and table optimality of each side"""
    print(f"\n## macroxue's pairwise preference, expert's move vs our engine's ({label})")
    truth = our_truth()
    c = collections.defaultdict(collections.Counter)
    opt = collections.defaultdict(collections.Counter)
    for i, e in ev.items():
        r = pos[i]
        table = e['src'].startswith('tuple')
        if table:
            best = max((v[0] for v in e['moves'].values() if not math.isnan(v[0])), default=0)
            if best > 0:
                for who, mv in (('engine', r['engine']), ('expert', r['played'])):
                    v = e['moves'].get(mv)
                    if v is None or math.isnan(v[0]):
                        continue
                    cls = 'optimal' if v[0] >= best - 0.01 else ('breaks (<half of best)' if v[0] < 0.5 * best else 'suboptimal')
                    opt[f"{r['group']} {who}"][cls] += 1
        if r['played'] == r['engine']:
            continue
        ma, mb = e['moves'].get(r['played']), e['moves'].get(r['engine'])
        if ma is None or mb is None:
            continue
        if table:
            if math.isnan(ma[0]) or math.isnan(mb[0]):
                continue
            gap = ma[0] - mb[0]
        else:
            gap = (ma[1] - mb[1]) / max(1.0, abs(max(v[1] for v in e['moves'].values())))
        lab = 'tie' if abs(gap) < 0.01 else ('expert' if gap > 0 else 'engine')
        keys = [r['group'], f"{r['group']} {'table' if table else 'search'}", f"{r['group']} {player_group(r)}"]
        if r['group'] == 'dispute' and i in truth:
            keys.append(f"dispute, our rollouts {truth[i]['verdict']}")
        for k in keys:
            c[k][lab] += 1
    print("| positions (expert's move != our engine's) | n | macroxue prefers the expert's | prefers our engine's | tie |")
    print("|---|---|---|---|---|")
    for k in sorted(c):
        n = sum(c[k].values())
        print(f"| {k} | {n} | {pct(c[k]['expert'], n)} | {pct(c[k]['engine'], n)} | {pct(c[k]['tie'], n)} |")
    print("\nPositions decided by macroxue's exact PDF lookup tables: each side's move vs the table's best")
    for k in sorted(opt):
        n = sum(opt[k].values())
        print(f"   {k:16s} n={n:3d} " + ', '.join(f"{a} {pct(b, n)}" for a, b in sorted(opt[k].items())))

def judged_by_group(pos, runs, group, label):
    """real loss of the expert's move vs our engine's under macroxue's continuation (score gained to the end, CRN pairs),
    by player type; for the disputes also our own rollout judge (results/disputes/expert_h300.tsv)"""
    truth = our_truth()
    out = collections.defaultdict(list)
    for i, r in pos.items():
        if r['group'] != group or r['played'] == r['engine']:
            continue
        a, b = runs.get((i, r['played'])), runs.get((i, r['engine']))
        if not a or not b:
            continue
        sa = {x['seed']: x for x in a}
        sb = {x['seed']: x for x in b}
        seeds = sorted(set(sa) & set(sb))
        m, se = mean_se([sb[s]['gain'] - sa[s]['gain'] for s in seeds])
        ge = sum(sb[s]['gain'] for s in seeds) / len(seeds)
        gp = sum(sa[s]['gain'] for s in seeds) / len(seeds)
        v = 'engine better' if m > 2 * se and m > 0 else ('expert better' if m < -2 * se else 'no significant difference')
        rec = dict(claimed=r['claimed'], rel=m / max(ge, gp, 100000.0), v=v, ours=truth.get(i, {}).get('rel', float('nan')),
                   ov=truth.get(i, {}).get('verdict'))
        for k in (player_group(r), 'all',
                  'claimed <1%' if r['claimed'] < 0.01 else ('claimed 1-10%' if r['claimed'] < 0.10 else 'claimed >=10%')):
            out[k].append(rec)
    print(f"\n## Real loss of the expert's move vs our engine's, macroxue continuing ({group}, {label})")
    for k in sorted(out):
        xs = out[k]
        n = len(xs)
        c = collections.Counter(x['v'] for x in xs)
        line = (f"   {k:16s} n={n:3d} claimed {100 * sum(x['claimed'] for x in xs) / n:5.1f}%, real (macroxue) "
                f"{100 * sum(x['rel'] for x in xs) / n:+6.2f}% {dict(c)}")
        ys = [x for x in xs if x['ov']]
        if ys:
            line += (f"; our rollouts {100 * sum(x['ours'] for x in ys) / len(ys):+6.1f}% "
                     f"{dict(collections.Counter(x['ov'] for x in ys))}")
        print(line)

def survival_both(pos, mx_path, ours_path, ids_path):
    """death within 1000 moves from the same random expert positions: macroxue (its own moves, depth 4) vs our full
    engine (its own move, then itself; build/rollout --moves engine --horizon 1000)"""
    ids = [l.strip() for l in open(ids_path)]
    ours = {}
    hdr = None
    for line in open(ours_path):
        p = line.rstrip('\n').split('\t')
        if hdr is None:
            hdr = p
            continue
        r = dict(zip(hdr, p))
        ours[ids[int(r['pos'])]] = float(r['died'])
    mx = {i: sum(x['snaps'][1][0] == 0 for x in xs) / len(xs) for (i, mv), xs in load_play([mx_path]).items()}
    g = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
    for i in ids:
        if i not in ours or i not in mx:
            continue
        r = pos[i]
        for k in (player_group(r), f"{player_group(r)} max {r['max']}"):
            s = g[k]
            s[0] += 1
            s[1] += ours[i]
            s[2] += mx[i]
            s[3] += ours[i] < mx[i] - 0.15
            s[4] += mx[i] < ours[i] - 0.15
    print("\n## Who plays which formation better: death within 1000 moves from the same 300 random expert positions")
    print("| positions | n | our engine | macroxue d4 | ours clearly better | macroxue clearly better |")
    print("|---|---|---|---|---|---|")
    for k in sorted(g):
        n, o, m, a, b = g[k]
        print(f"| {k} | {n} | {o / n:.3f} | {m / n:.3f} | {a} | {b} |")

def phase_tests(paths):
    print("\n## macroxue on our phase tests")
    for path in paths:
        try:
            rows = [l.rstrip('\n').split('\t') for l in open(path)]
        except FileNotFoundError:
            continue
        rows = [r for r in rows if r and r[0] == 'P' and len(r) > 10]
        if not rows:
            continue
        n = len(rows)
        sums = [int(r[9]) for r in rows]
        gain = [int(r[6]) for r in rows]
        line = f"   {path}: n={n}"
        for t in (36864, 49152, 57344):
            k = sum(x >= t for x in sums)
            p = k / n
            line += f"; sum >= {t}: {100 * p:.2f}% +- {100 * math.sqrt(p * (1 - p) / n):.2f}"
        m, se = mean_se(gain)
        print(line + f"; score gained {m:.0f} +- {se:.0f}")

def phase_detail(path, target):
    """for playouts with the final board and the move-source counts (driver fields 15-16): which formation macroxue
    ends in (games that reached the target tile sum vs games that died) and how many of its moves came from the exact
    lookup tables"""
    try:
        rows = [l.rstrip('\n').split('\t') for l in open(path)]
    except FileNotFoundError:
        return
    rows = [r for r in rows if r and r[0] == 'P' and len(r) >= 16]
    if not rows:
        return
    print(f"\n## Formation and move sources ({path})")
    for lab, sel in (('reached', lambda r: int(r[9]) >= target), ('died', lambda r: int(r[9]) < target)):
        xs = [r for r in rows if sel(r)]
        if not xs:
            continue
        c = collections.Counter(formation([int(ch, 32) for ch in r[14]]) for r in xs)
        t11 = sum(int(r[15].split(':')[0]) for r in xs)
        t10 = sum(int(r[15].split(':')[1]) for r in xs)
        se = sum(int(r[15].split(':')[2]) for r in xs)
        tot = max(1, t11 + t10 + se)
        print(f"   {lab:8s} n={len(xs):4d} final formation {dict(c)}; moves from tuple11 {100 * t11 / tot:.1f}%, "
              f"tuple10 {100 * t10 / tot:.1f}%, search {100 * se / tot:.1f}%")

def main():
    args = sys.argv[1:]
    if args == ['--all']:
        R = 'results/mx/'
        pos = load_positions()
        formations(pos)
        ev = load_eval(R + 'eval_d8.out')
        agreement(pos, ev, 'depth 8')
        pairwise(pos, ev, 'depth 8')
        feature_diffs(pos, ev, 'depth 8')
        runs = load_play([R + 'play_d4_h100000.out'])
        playouts(pos, runs, 'disputes, depth 4, to the end')
        judged_by_group(pos, runs, 'dispute', 'depth 4')
        judged_by_group(pos, load_play([R + 'playR_d4_h100000.out']), 'random', 'depth 4')
        survival_both(pos, R + 'fromR_d4.out', R + 'random300_ours_h1000.tsv', R + 'random300.ids')
        phase_tests([R + 'pool700_d4.out', R + 'pool700_d4b.out', R + 'pool700_d6.out', R + 'pool32k500_d4.out',
                     R + 'pool32k500_d6.out', R + 'fresh2_d4.out'])
        phase_detail(R + 'pool700_d4b.out', 36864)
        phase_detail(R + 'pool32k500_d6.out', 57344)
        return
    evals, plays = [], []
    while args:
        a = args.pop(0)
        if a == '--eval': evals.append(args.pop(0))
        elif a == '--play': plays.append(args.pop(0))
    pos = load_positions()
    for p in evals:
        ev = load_eval(p)
        agreement(pos, ev, p)
        feature_diffs(pos, ev, p)
    if plays:
        playouts(pos, load_play(plays), ', '.join(plays))

if __name__ == '__main__':
    main()
