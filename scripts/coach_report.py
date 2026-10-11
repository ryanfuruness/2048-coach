#!/usr/bin/env python3
"""Coach test report (inputs: results/coach/advice_S*.tsv, first_*.tsv from scripts/coach_run.sh, metadata from
scripts/coach_select.py). Means are over positions (each position's playout mean first), standard errors over
positions; differences are paired by position (common random numbers).
  advice   P(next milestone) per stage group x start kind x player t x condition, hints shown / moves changed per
           playout and per 100 moves, gain over playing alone and share of the gap to the engine closed, hint
           efficiency (gain per hint) and the best condition for a budget of hints
  first    "at your level": for every first move, P(milestone) when the player (or the engine) continues; the drop
           against the engine's move, by value-loss bin, and for the players' real mistakes
usage: coach_report.py [--advice] [--first] [--prefix advice] [--json results/coach/summary.json]"""
import json, math, sys, collections, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coach_select import load_model, stage_map, interp, DIRS  # noqa: E402

R = os.environ.get('COACH_DIR', 'results/coach')

def read_tsv(path):
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) == len(hdr): yield dict(zip(hdr, p))

def mean_se(xs):
    xs = np.asarray(xs, float)
    if len(xs) == 0: return float('nan'), float('nan')
    return float(xs.mean()), float(xs.std(ddof=1) / math.sqrt(len(xs))) if len(xs) > 1 else 0.0

def advice(out, prefix='advice'):
    meta = {r['id']: r for r in read_tsv(f'{R}/starts_meta.tsv')}
    # per (id, t, cond): playouts
    acc = collections.defaultdict(lambda: np.zeros(7))  # n, r1, r2, moves, shown, changed, died
    groups_seen = set()
    for g in ('S1', 'S2', 'S3'):
        path = f'{R}/{prefix}_{g}.tsv'
        if not os.path.exists(path): continue
        groups_seen.add(g)
        for r in read_tsv(path):
            a = acc[(r['id'], r['t'], r['cond'])]
            a += [1, int(r['reached1']), int(r['reached2']), int(r['moves']), int(r['shown']), int(r['changed']),
                  int(r['died'])]
    # complete cells only: a position counts for a (t, cond) when all its playouts are in (partial runs)
    full = collections.defaultdict(float)
    for (i, t, c), a in acc.items(): full[(meta[i]['group'], t, c)] = max(full[(meta[i]['group'], t, c)], a[0])
    per = collections.defaultdict(dict)  # (group, kind, t) -> cond -> {id: stats}; engine under t='0'
    for (i, t, c), a in acc.items():
        m = meta[i]
        if a[0] < full[(m['group'], t, c)]: continue
        st = dict(p1=a[1] / a[0], p2=a[2] / a[0], moves=a[3] / a[0], shown=a[4] / a[0], changed=a[5] / a[0])
        for kind in (m['kind'], 'all'):
            per[(m['group'], kind, t)].setdefault(c, {})[i] = st
    summary = {}
    ts = sorted({t for (_, _, t) in per if t != '0'}, key=float)
    for g in sorted(groups_seen):
        for kind in ('tight', 'after', 'control', 'all'):
            eng = per.get((g, kind, '0'), {}).get('engine', {})
            for t in ts:
                cells = per.get((g, kind, t), {})
                alone = cells.get('alone', {})
                if not alone: continue
                print(f"\n== {g} {kind}  player t={t}  ({len(alone)} positions)   P(next milestone) [P(2nd)]")
                print(f"   {'condition':18s} {'P':>6s} {'+-':>5s}  {'gain':>6s} {'+-':>5s}  {'gap':>5s}  "
                      f"{'hints':>6s} {'changed':>7s} {'/100mv':>6s}  {'gain/hint':>9s}  moves")
                ids_eng = set(eng)
                rows = []
                for c in ['alone', 'engine'] + sorted(k for k in cells if k not in ('alone',)):
                    d = eng if c == 'engine' else cells.get(c, {})
                    ids = sorted(set(d) & set(alone))
                    if not ids: continue
                    p = [d[i]['p1'] for i in ids]
                    gain = [d[i]['p1'] - alone[i]['p1'] for i in ids]
                    gap_ids = [i for i in ids if i in ids_eng]
                    gap_num = sum(d[i]['p1'] - alone[i]['p1'] for i in gap_ids)
                    gap_den = sum(eng[i]['p1'] - alone[i]['p1'] for i in gap_ids)
                    shown = np.mean([d[i]['shown'] for i in ids]); changed = np.mean([d[i]['changed'] for i in ids])
                    moves = np.mean([d[i]['moves'] for i in ids])
                    pm, pse = mean_se(p); gm, gse = mean_se(gain)
                    per100 = 100 * shown / max(1e-9, moves)
                    eff = gm / shown if shown > 0 else float('nan')
                    p2 = np.mean([d[i]['p2'] for i in ids])
                    gap = gap_num / gap_den if gap_den > 0 else float('nan')
                    if c == 'engine':
                        shown, changed, per100, eff = float('nan'), float('nan'), 100.0, float('nan')
                    print(f"   {c:18s} {pm:6.3f} {pse:5.3f}  {gm:+6.3f} {gse:5.3f}  {gap:5.2f}  {shown:6.1f} {changed:7.1f} "
                          f"{per100:6.1f}  {eff:9.4f}  {moves:6.0f}  [{p2:.3f}]")
                    rows.append(dict(cond=c, n=len(ids), p=pm, p_se=pse, gain=gm, gain_se=gse, gap=gap, hints=shown,
                                     changed=changed, per100=per100, gain_per_hint=eff, moves=moves, p2=p2))
                summary[f"{g}/{kind}/{t}"] = rows
                # Pareto frontier over (hints per playout, P): the best condition for each budget of hints
                pts = sorted((r['hints'] if r['cond'] != 'alone' else 0.0, -r['p'], r['cond']) for r in rows
                             if r['cond'] != 'engine')
                front, bestp = [], -1
                for h, mp, c in pts:
                    if -mp > bestp + 1e-9: front.append(f"{c} ({h:.1f} hints, {-mp:.3f})"); bestp = -mp
                print("   frontier: " + " -> ".join(front))
    return summary

def first(out):
    knots, vbar, maps = load_model()
    # engine values per move for the positions (value loss bins)
    ids = set()
    metas = {}
    SOURCES = [('firstbig', ['big', 'bigstruct']), ('firstpool', ['pool']), ('before', ['before']),
               ('mistakes', ['mistakes', 'mistakesstruct'])]
    for name, _ in SOURCES:
        if os.path.exists(f'{R}/{name}_meta.tsv'):
            for r in read_tsv(f'{R}/{name}_meta.tsv'):
                ids.add(r['id']); metas.setdefault(r['id'], {})[name] = dict(r, src=name)
    vals = {}
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        rid = f"{a['video']}:{a['segment']}:{a['ply']}"
        if rid not in ids: continue
        v = {DIRS[m['move']]: m['value'] for m in a['moves']}
        em = DIRS[a['engine_move']]
        ref = v[em]
        top = max(x for row in a['board'] for x in row)
        lm = stage_map(maps, top)
        vals[rid] = dict(em=em, rel={d: max(0.0, ref - x) / max(100000.0, abs(ref)) for d, x in v.items()},
                         top=top, lm=lm)
    acc = collections.defaultdict(lambda: np.zeros((4, 2)))  # (src, id, cont) -> per move [n, r1]
    for src, names in SOURCES:
      for name in names:
        path = f'{R}/first_{name}.tsv'
        if not os.path.exists(path): continue
        for r in read_tsv(path):
            # structured players (--structured 0.5) are labelled s<t>
            a = acc[(src, r['id'], ('s' + r['cont']) if name.endswith('struct') else r['cont'])]
            for k, d in enumerate('URDL'):
                x = int(r[f'r1_{d}'])
                if x >= 0: a[k] += [1, x]
    conts_all = sorted({c for (_, _, c) in acc}, key=lambda c: (c.startswith('s'), float(c.lstrip('s'))))
    BINS = [0, 0.01, 0.03, 0.1, 0.3, 10]
    res = {}
    print("\n== At your level: drop in P(next milestone) against the engine's move, when the player continues")
    print("   (value loss = the analysis' relative value loss of the move; real loss = installed map, engine continuing)")
    for src, _ in SOURCES:
        conts = [c for c in conts_all if any(k[0] == src and k[2] == c for k in acc)]
        if not conts: continue
        print(f"\n-- {src} positions" + (" (the move each player actually played was a real mistake >= 3%)" if src in ('before', 'mistakes') else ""))
        for g in ('S1', 'S2', 'S3', 'all'):
            rows = collections.defaultdict(lambda: collections.defaultdict(list))  # bin -> cont -> drops
            base = collections.defaultdict(lambda: collections.defaultdict(list))  # bin -> cont -> P(engine move)
            played_drop = collections.defaultdict(list)
            maprl = collections.defaultdict(list)
            for (sr, i, c), a in acc.items():
                m = metas.get(i, {}).get(src)
                if sr != src or not m or (g != 'all' and m['group'] != g) or i not in vals: continue
                V = vals[i]
                ek = 'URDL'.index(V['em'])
                if a[ek][0] == 0: continue
                pe = a[ek][1] / a[ek][0]
                for k, d in enumerate('URDL'):
                    if a[k][0] == 0 or k == ek or d not in V['rel']: continue
                    drop = pe - a[k][1] / a[k][0]
                    x = V['rel'][d]
                    b = next(j for j in range(len(BINS) - 1) if BINS[j] <= x < BINS[j + 1])
                    rows[b][c].append(drop)
                    base[b][c].append(pe)
                    if c == conts[0]: maprl[b].append(interp(V['lm'], x))
                    if d == m['played']: played_drop[c].append(drop)
            if not rows: continue
            print(f"   {g}: value-loss bin     n  " + "  ".join(f"{('engine' if c == '0' else ('struct t=' + c[1:]) if c.startswith('s') else 't=' + c):>28s}" for c in conts)
                  + "   map real loss")
            for b in sorted(rows):
                n = len(rows[b][conts[0]])
                cells = []
                for c in conts:
                    mu, se = mean_se(rows[b][c])
                    pb = float(np.mean(base[b][c])) if base[b][c] else float('nan')
                    rel = mu / pb if pb > 0 else float('nan')
                    cells.append(f"{mu:+.3f}+-{se:.3f} ({rel:+.2f} of {pb:.2f})")
                    res[f"{src}/{g}/{BINS[b]}-{BINS[b+1]}/{c}"] = dict(n=len(rows[b][c]), drop=mu, se=se, base=pb, rel=rel)
                print(f"      [{BINS[b]:.2f},{BINS[b+1]:.2f})  {n:5d}  " + "  ".join(f"{x:>28s}" for x in cells)
                      + f"   {np.mean(maprl[b]):.3f}")
            if src in ('before', 'mistakes') and played_drop:
                print(f"      the players' own mistakes: " + "  ".join(
                    f"{('engine' if c == '0' else 't=' + c)}: {mean_se(played_drop[c])[0]:+.3f}+-{mean_se(played_drop[c])[1]:.3f}"
                    for c in conts if played_drop[c]))
    return res

def main():
    args = sys.argv[1:]
    do_a = '--first' not in args or '--advice' in args
    do_f = '--advice' not in args or '--first' in args
    out = {}
    prefix = args[args.index('--prefix') + 1] if '--prefix' in args else 'advice'
    if do_a: out['advice'] = advice(out, prefix)
    if do_f: out['first'] = first(out)
    if '--json' in args:
        json.dump(out, open(args[args.index('--json') + 1], 'w'), indent=1)

if __name__ == '__main__':
    main()
