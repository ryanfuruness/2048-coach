#!/usr/bin/env python3
"""Coach test, step 1: start positions from the curated human set (results/human_ds/analysis.jsonl).

Kinds of start position (stage groups by the largest tile: S1 128-512, S2 1024-2048, S3 4096-8192):
  tight    the engine's value is well below the stage's typical (value / vbar(sum) < 0.75; vbar of weights/calib/model.txt)
  after    right after a real mistake of the player (the previous move's estimated real loss >= 3%, installed maps)
  control  ordinary positions (ratio >= 0.9, the previous move was not a mistake)
Also: the positions BEFORE those mistakes (for mode first: what the mistake costs at the player's own level), the
human outcome of every position (did the player's game reach the next milestone? censored when the video ends
first), and all usable positions with their played move (for fitting the players' t by maximum likelihood).

Writes results/coach/: starts.tsv (id hex played; all kinds), starts_meta.tsv, before.tsv (+ meta), fit_in.tsv,
human_outcomes.tsv.  usage: coach_select.py [--seed 1] [--n S1:40,40,20 ...] [--stats]"""
import json, math, random, sys, collections
import numpy as np
import os
OUT = os.environ.get('COACH_DIR', 'results/coach')  # output directory (replications: another directory)

KN = None
def load_model(path='weights/calib/model.txt'):
    m = {}
    for line in open(path):
        p = line.split()
        if p: m[p[0]] = p[1:]
    knots = [float(x) for x in m['knots']]
    vbar = [float(x) for x in m['vbar']]
    maps = {}
    for k in ('lossmap', 'lossmap_late', 'lossmap_top', 'lossmap_played_expert'):
        if k not in m: continue  # lossmap_top: models from 2026-10-07 on (positions with a 16384+)
        xs = [float(x) for x in m[k]]
        maps[k] = list(zip(xs[0::2], xs[1::2]))
    return knots, vbar, maps

def stage_map(maps, top):
    """The engine's loss map for a position with largest tile `top`, as build/analyze picks it (calib.h real_loss)."""
    if top >= 16384 and 'lossmap_top' in maps: return maps['lossmap_top']
    return maps['lossmap_late'] if top >= 2048 else maps['lossmap']

def hats(s, knots):
    s = min(max(s, knots[0]), knots[-1])
    B = [0.0] * len(knots)
    for k in range(len(knots)):
        if k > 0 and knots[k - 1] <= s <= knots[k]:
            B[k] = (s - knots[k - 1]) / (knots[k] - knots[k - 1])
        if k + 1 < len(knots) and knots[k] <= s < knots[k + 1]:
            B[k] = (knots[k + 1] - s) / (knots[k + 1] - knots[k])
    if s >= knots[-1]: B[-1] = 1.0
    return B

def interp(lm, x):
    if x <= lm[0][0]: return lm[0][1]
    for (x0, y0), (x1, y1) in zip(lm, lm[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, lm[-1][1] * x / max(1e-12, lm[-1][0]))

def group_of(top):
    if 128 <= top <= 512: return 'S1'
    if 1024 <= top <= 2048: return 'S2'
    if 4096 <= top <= 8192: return 'S3'
    return None

DIRS = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def main():
    args = sys.argv[1:]
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1
    sizes = {'S1': (40, 40, 20), 'S2': (40, 40, 20), 'S3': (24, 24, 12)}
    for a in args:
        if a.startswith('S') and ':' in a:
            g, v = a.split(':'); sizes[g] = tuple(int(x) for x in v.split(','))
    knots, vbar, maps = load_model()
    recs = []
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        if not a.get('moves'): continue
        vals = {DIRS[m['move']]: m['value'] for m in a['moves']}
        em = DIRS.get(a['engine_move']) if a.get('engine_move') else None
        pl = DIRS.get(a.get('played'))
        tiles = [v for row in a['board'] for v in row]
        top, tot = max(tiles), sum(tiles)
        if em is None or em not in vals: continue
        ref = vals[em]
        value = ref
        ratio = value / max(1.0, float(np.dot(hats(math.log2(max(tot, 4)), knots), vbar)))
        rl = None
        certain = a.get('observed', True) and not a.get('maybe_two_moves') and not a.get('rest_ambiguous')
        if pl in vals:
            rel = max(0.0, ref - vals[pl]) / max(100000.0, abs(ref))
            lm = maps['lossmap_played_expert'] if top >= 16384 else stage_map(maps, top)
            rl = interp(lm, rel)
        recs.append(dict(video=a['video'], seg=a['segment'], ply=a['ply'], hex=a['hex'], top=top, sum=tot,
                         tier=a['tier'], player=a['player'], played=pl, em=em, ratio=ratio, rl=rl, certain=certain,
                         observed=a.get('observed', True), tiles=tiles))
    print(f"{len(recs)} positions", file=sys.stderr)
    # games: per video in (segment, ply) order; a new game starts when the tile sum collapses
    byv = collections.defaultdict(list)
    for i, r in enumerate(recs): byv[r['video']].append(i)
    for v, ix in byv.items():
        ix.sort(key=lambda i: (recs[i]['seg'], recs[i]['ply']))
        g, prev = 0, None
        for i in ix:
            s = recs[i]['sum']
            if prev is not None and (s < 0.5 * prev or (s <= 16 and prev > 64)): g += 1
            recs[i]['game'] = (v, g); prev = s
        # outcomes: next milestone (2x top) and the one after (4x top); failed if a later game exists in the video
        games = collections.defaultdict(list)
        for i in ix: games[recs[i]['game']].append(i)
        last_game = max(gg for (_, gg) in games)
        for (vv, gg), gi in games.items():
            ended = gg < last_game
            # running maximum from the end
            suffix_max = [0] * (len(gi) + 1)
            for j in range(len(gi) - 1, -1, -1): suffix_max[j] = max(suffix_max[j + 1], recs[gi[j]]['top'])
            for j, i in enumerate(gi):
                later = suffix_max[j + 1]
                for key, mult in (('h1', 2), ('h2', 4)):
                    tgt = recs[i]['top'] * mult
                    recs[i][key] = 1 if later >= tgt else (0 if ended else -1)
                recs[i]['ended'] = ended
                recs[i]['prev'] = gi[j - 1] if j > 0 and recs[gi[j - 1]]['seg'] == recs[i]['seg'] and \
                    recs[gi[j - 1]]['ply'] == recs[i]['ply'] - 1 else None
    # kinds
    for r in recs:
        r['group'] = group_of(r['top'])
        p = recs[r['prev']] if r.get('prev') is not None else None
        r['after'] = p is not None and p['certain'] and p['rl'] is not None and p['rl'] >= 0.03
        r['clean_prev'] = p is not None and p['rl'] is not None and p['rl'] < 0.01
    if '--stats' in args:
        c = collections.Counter()
        for r in recs:
            if not r['group'] or not r['observed']: continue
            c[(r['group'], 'all', r['tier'])] += 1
            if r['ratio'] < 0.75: c[(r['group'], 'tight', r['tier'])] += 1
            if r['after']: c[(r['group'], 'after', r['tier'])] += 1
        for k in sorted(c): print(k, c[k])
        ho = collections.Counter((r['group'], r['tier'], r['h1']) for r in recs if r['group'])
        for k in sorted(ho): print('outcome', k, ho[k])
        return
    rng = random.Random(seed)
    # --exclude META.tsv: leave out the positions of an earlier set (replications on fresh positions)
    excl = set()
    if '--exclude' in args:
        excl = set(l.split('\t')[0] for l in open(args[args.index('--exclude') + 1]))
    chosen = []
    for g in ('S1', 'S2', 'S3'):
        for kind, n in zip(('tight', 'after', 'control'), sizes[g]):
            if kind == 'tight': ok = lambda r: r['ratio'] < 0.75 and not r['after']
            elif kind == 'after': ok = lambda r: r['after']
            else: ok = lambda r: r['ratio'] >= 0.9 and r['clean_prev']
            cand = [i for i, r in enumerate(recs) if r['group'] == g and r['observed'] and ok(r) and
                    f"{r['video']}:{r['seg']}:{r['ply']}" not in excl]
            # spread over tiers and players: round-robin over tiers, at most 3 per player, one per game stretch of
            # 100 plies
            bytier = collections.defaultdict(list)
            for i in cand: bytier[recs[i]['tier']].append(i)
            for t in bytier: rng.shuffle(bytier[t])
            used_pl, used_stretch, pick = collections.Counter(), set(), []
            tiers = sorted(bytier)
            while len(pick) < n and any(bytier[t] for t in tiers):
                for t in tiers:
                    while bytier[t]:
                        i = bytier[t].pop()
                        r = recs[i]
                        st = (r["game"], r["ply"] // 50)
                        if used_pl[r["player"]] >= 5 or st in used_stretch: continue
                        used_pl[r['player']] += 1; used_stretch.add(st); pick.append(i)
                        break
                    if len(pick) >= n: break
            print(f"{g} {kind}: {len(pick)} of {len(cand)} candidates; tiers "
                  f"{dict(collections.Counter(recs[i]['tier'] for i in pick))}", file=sys.stderr)
            chosen += [(i, kind) for i in pick]
    rid = lambda r: f"{r['video']}:{r['seg']}:{r['ply']}"
    with open(f'{OUT}/starts.tsv', 'w') as f, open(f'{OUT}/starts_meta.tsv', 'w') as fm:
        f.write('id\thex\tplayed\n')
        fm.write('id\tkind\tgroup\ttier\tplayer\ttop\tsum\tratio\tplayed\tengine\tprev_rl\th1\th2\n')
        for i, kind in chosen:
            r = recs[i]
            f.write(f"{rid(r)}\t{r['hex']}\t{r['played'] or '-'}\n")
            p = recs[r['prev']] if r.get('prev') is not None else None
            fm.write(f"{rid(r)}\t{kind}\t{r['group']}\t{r['tier']}\t{r['player']}\t{r['top']}\t{r['sum']}\t"
                     f"{r['ratio']:.4f}\t{r['played']}\t{r['em']}\t{p['rl'] if p and p['rl'] is not None else ''}\t"
                     f"{r['h1']}\t{r['h2']}\n")
    # the positions before the chosen mistakes (mode first: the mistake's cost at the player's own level)
    with open(f'{OUT}/before.tsv', 'w') as f, open(f'{OUT}/before_meta.tsv', 'w') as fm:
        f.write('id\thex\tplayed\n')
        fm.write('id\tgroup\ttier\tplayer\ttop\tsum\tratio\tplayed\tengine\trl\th1\n')
        for i, kind in chosen:
            if kind != 'after': continue
            p = recs[recs[i]['prev']]
            f.write(f"{rid(p)}\t{p['hex']}\t{p['played']}\n")
            fm.write(f"{rid(p)}\t{group_of(p['top'])}\t{p['tier']}\t{p['player']}\t{p['top']}\t{p['sum']}\t"
                     f"{p['ratio']:.4f}\t{p['played']}\t{p['em']}\t{p['rl']:.5f}\t{p['h1']}\n")
    # ordinary positions for mode first (every first move continued by the players and the engine: "at your level")
    taken = set(i for i, _ in chosen)
    with open(f'{OUT}/firstpool.tsv', 'w') as f, open(f'{OUT}/firstpool_meta.tsv', 'w') as fm:
        f.write('id\thex\tplayed\n')
        fm.write('id\tgroup\ttier\tplayer\ttop\tsum\tratio\tplayed\tengine\trl\n')
        for g, n in (('S1', 60), ('S2', 60), ('S3', 30)):
            cand = [i for i, r in enumerate(recs) if r['group'] == g and r['observed'] and r['certain'] and
                    r['rl'] is not None and i not in taken]
            rng.shuffle(cand)
            used_pl = collections.Counter()
            k = 0
            for i in cand:
                r = recs[i]
                if used_pl[r['player']] >= 4: continue
                used_pl[r['player']] += 1; k += 1
                f.write(f"{rid(r)}\t{r['hex']}\t{r['played']}\n")
                fm.write(f"{rid(r)}\t{g}\t{r['tier']}\t{r['player']}\t{r['top']}\t{r['sum']}\t{r['ratio']:.4f}\t"
                         f"{r['played']}\t{r['em']}\t{r['rl']:.5f}\n")
                if k >= n: break
    # every real mistake of the set (the position before it; for soft-only mode first): written only with --mistakes
    if '--mistakes' in args:
        with open(f'{OUT}/mistakes.tsv', 'w') as f, open(f'{OUT}/mistakes_meta.tsv', 'w') as fm:
            f.write('id\thex\tplayed\n')
            fm.write('id\tgroup\ttier\tplayer\ttop\tsum\tratio\tplayed\tengine\trl\th1\n')
            for r in recs:
                g = group_of(r['top'])
                if not g or not r['certain'] or r['rl'] is None or r['rl'] < 0.03: continue
                f.write(f"{rid(r)}\t{r['hex']}\t{r['played']}\n")
                fm.write(f"{rid(r)}\t{g}\t{r['tier']}\t{r['player']}\t{r['top']}\t{r['sum']}\t{r['ratio']:.4f}\t"
                         f"{r['played']}\t{r['em']}\t{r['rl']:.5f}\t{r['h1']}\n")
        return
    # a bigger ordinary set for soft-only mode first (cheap 1-ply continuations; "at your level" maps), disjoint from
    # the others; written only with --big (keeps the earlier files of a run unchanged)
    if '--big' in args:
        pool_ids = set(l.split('\t')[0] for l in open(f'{OUT}/firstpool.tsv'))
        rng2 = random.Random(seed + 7)
        with open(f'{OUT}/firstbig.tsv', 'w') as f, open(f'{OUT}/firstbig_meta.tsv', 'w') as fm:
            f.write('id\thex\tplayed\n')
            fm.write('id\tgroup\ttier\tplayer\ttop\tsum\tratio\tplayed\tengine\trl\n')
            for g, n in (('S1', 200), ('S2', 200), ('S3', 200)):
                cand = [i for i, r in enumerate(recs) if r['group'] == g and r['observed'] and r['certain'] and
                        r['rl'] is not None and i not in taken and rid(r) not in pool_ids]
                rng2.shuffle(cand)
                used_pl = collections.Counter()
                k = 0
                for i in cand:
                    r = recs[i]
                    if used_pl[r['player']] >= 12: continue
                    used_pl[r['player']] += 1; k += 1
                    f.write(f"{rid(r)}\t{r['hex']}\t{r['played']}\n")
                    fm.write(f"{rid(r)}\t{g}\t{r['tier']}\t{r['player']}\t{r['top']}\t{r['sum']}\t{r['ratio']:.4f}\t"
                             f"{r['played']}\t{r['em']}\t{r['rl']:.5f}\n")
                    if k >= n: break
        return
    with open(f'{OUT}/fit_in.tsv', 'w') as f, open(f'{OUT}/fit_meta.tsv', 'w') as fm:
        f.write('id\thex\tplayed\n')
        fm.write('id\tgroup\ttier\tplayer\ttop\n')
        for r in recs:
            if not r['certain'] or r['played'] is None or r['top'] > 32768: continue
            f.write(f"{rid(r)}\t{r['hex']}\t{r['played']}\n")
            fm.write(f"{rid(r)}\t{group_of(r['top']) or '-'}\t{r['tier']}\t{r['player']}\t{r['top']}\n")
    with open(f'{OUT}/human_outcomes.tsv', 'w') as f:
        f.write('id\thex\tgroup\ttier\tplayer\ttop\tratio\th1\th2\tended\n')
        for r in recs:
            if r['group'] and r['observed']:
                f.write(f"{rid(r)}\t{r['hex']}\t{r['group']}\t{r['tier']}\t{r['player']}\t{r['top']}\t{r['ratio']:.4f}\t"
                        f"{r['h1']}\t{r['h2']}\t{int(r['ended'])}\n")

if __name__ == '__main__':
    main()
