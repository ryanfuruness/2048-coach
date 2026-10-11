#!/usr/bin/env python3
"""Per-tier summary of the curated human dataset (dataset_build, analysed by human_review.py into
results/human_ds/analysis.jsonl): per player (YouTube channel - the dataset's unit of independence), the match rate,
best-or-good share, inaccuracies / mistakes / blunders per 100 moves (estimated real loss with best play, loss maps of
weights/calib/model.txt), mistakes per 100 moves at the player's own level (your cost >= 3%: the model's lossmap_own,
as build/analyze), warnings per 100 moves (the model's warn thresholds) and the share of moves in block-formation
positions that the analysis does not judge (left out of everything else); then medians over the players of each tier.
Undone and inferred moves skipped.
usage: human_tiers.py [--model weights/calib/model.txt] [--personal weights/calib/personal.txt] [--out tiers.json]
                      [results/human_ds/analysis.jsonl]
(with a skill map in the personal model, the player's fitted t is converted to the soft player's before the skill maps)"""
import json, math, sys, collections, statistics as st
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from block_detect import block_position  # noqa: E402

def load_map(path, key):
    maps = {}
    for line in open(path):
        p = line.split()
        if p and p[0] == key:
            if key == 'plossmap':
                xs = [float(x) for x in p[2:]]
                maps[float(p[1])] = list(zip(xs[0::2], xs[1::2]))
            else:
                xs = [float(x) for x in p[1:]]
                maps[None] = list(zip(xs[0::2], xs[1::2]))
    return maps

def interp(lm, x):
    if x <= lm[0][0]: return lm[0][1]
    for (x0, y0), (x1, y1) in zip(lm, lm[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, lm[-1][1] * x / max(1e-12, lm[-1][0]))

def personal(pm, t, x):
    ts = sorted(pm)
    if t <= ts[0]: return interp(pm[ts[0]], x)
    if t >= ts[-1]: return interp(pm[ts[-1]], x)
    for a, b in zip(ts, ts[1:]):
        if a <= t <= b:
            w = (math.log(t) - math.log(a)) / (math.log(b) - math.log(a))
            return (1 - w) * interp(pm[a], x) + w * interp(pm[b], x)

def fit_t(ch):
    bt, bll, t = None, -1e300, 0.0003
    while t <= 1.0:
        ll = sum(-r[p] / t - math.log(sum(math.exp(-v / t) for v in r.values())) for r, p in ch)
        if ll > bll: bll, bt = ll, t
        t *= 1.1
    return bt

def main():
    args = sys.argv[1:]
    model, pers, out_json = 'weights/calib/model.txt', 'weights/calib/personal.txt', 'results/human_ds/tiers.json'
    rest = []
    while args:
        a = args.pop(0)
        if a == '--model': model = args.pop(0)
        elif a == '--personal': pers = args.pop(0)
        elif a == '--out': out_json = args.pop(0)
        else: rest.append(a)
    path = rest[0] if rest else 'results/human_ds/analysis.jsonl'
    lm = load_map(model, 'lossmap')[None]
    lml = load_map(model, 'lossmap_late').get(None, lm)          # positions with a tile >= 2048
    lme = load_map(model, 'lossmap_played_expert').get(None, lml)  # played moves, tile >= 16384
    # table-decided positions (analysis caches made with tables): the player's move is judged by the exact success
    # probabilities, through lossmap_table_played if the model has one (cal7), else lossmap_table - as analyze
    ltab = load_map(model, 'lossmap_table_played').get(None) or load_map(model, 'lossmap_table').get(None)
    pm = load_map(pers, 'plossmap')
    # as build/analyze (2026-10-07): your cost (share of the player's own chances of the next tile, lossmap_own per
    # phase), warn thresholds per phase, block-formation positions (real 16384+) not judged
    own, warn = {}, [0.15, 0.05, 0.05, 0.30]
    for line in open(model):
        p = line.split()
        if p and p[0] == 'lossmap_own':
            xs = [float(x) for x in p[2:]]
            own[int(p[1])] = list(zip(xs[0::2], xs[1::2]))
        elif p and p[0] == 'warn' and len(p) == 5:
            warn = [float(x) for x in p[1:]]
    smap = {}
    for line in open(pers):
        p = line.split()
        if p and p[0] == 'pskillmap':
            smap[int(p[1])] = list(zip([float(x) for x in p[2::2]], [float(x) for x in p[3::2]]))
    def soft_t(t, ph):
        ks = [k for k in smap if k <= ph]
        if not ks or t <= 0: return t
        m = smap[max(ks)]
        if t <= m[0][1]: return m[0][0] * t / m[0][1]
        for (s0, f0), (s1, f1) in zip(m, m[1:]):
            if t <= f1:
                w = (math.log(t) - math.log(f0)) / (math.log(f1) - math.log(f0))
                return math.exp((1 - w) * math.log(s0) + w * math.log(s1))
        return m[-1][0] * t / m[-1][1]
    per = collections.defaultdict(list)
    tier_of = {}
    unjudged = collections.Counter()
    for line in open(path):
        a = json.loads(line)
        if a.get('game_over') or 'played' not in a or len(a['moves']) < 2: continue
        if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'): continue
        vals = {m['move']: m['value'] for m in a['moves']}
        if a['played'] not in vals or a['engine_move'] not in vals: continue
        ref = vals[a['engine_move']]
        rel = {k: max(0.0, ref - v) / max(100000.0, abs(ref)) for k, v in vals.items()}
        top = max(max(row) for row in a['board'])
        if block_position([x for row in a['board'] for x in row]):  # the engine does not judge block positions
            unjudged[a.get('player', a['video'])] += 1
            continue
        tl = None
        if ltab and a.get('source', 'search') != 'search':
            pp = {m['move']: m.get('p') for m in a['moves']}
            pr, pd = pp.get(a['engine_move']), pp.get(a['played'])
            if pr is not None and pr > 0 and pd is not None and pd >= 0:
                tl = 0.0 if a['played'] == a['engine_move'] else max(0.0, (pr - pd) / pr)
        per[a.get('player', a['video'])].append((rel, a['played'], a['engine_move'], top, tl))
        tier_of[a.get('player', a['video'])] = a.get('tier', '?')
    rows = collections.defaultdict(list)
    for pl, xs in per.items():
        if len(xs) < 200: continue
        n = len(xs)
        t = fit_t([(r, p) for r, p, _, _, _ in xs])
        # the analysis' maps: early / late by the position's largest tile, the expert map for a player's own move in
        # 16384+ positions; losses at the player's level only below 16384 (the skill maps do not reach further)
        real = [interp(ltab, tl) if tl is not None else interp(lme if tp >= 16384 else lml if tp >= 2048 else lm, r[p])
                for r, p, _, tp, tl in xs]
        ph_of = lambda tp: 0 if tp <= 512 else 1 if tp <= 2048 else 2 if tp <= 8192 else 3
        # your cost: the own-chances map of the phase (16384+: the real loss), as analyze's your_cost
        mine = [interp(own[ph_of(tp)], r[p]) if ph_of(tp) in own else x for (r, p, _, tp, _), x in zip(xs, real)]
        warns = sum(r[p] >= warn[ph_of(tp)] for r, p, _, tp, _ in xs)
        rows[tier_of[pl]].append(dict(
            player=pl, n=n, t=t, match=sum(p == e for _, p, e, _, _ in xs) / n,
            good=sum(x < 0.01 for x in real) / n, inacc=100 * sum(0.01 <= x < 0.03 for x in real) / n,
            mist=100 * sum(0.03 <= x < 0.10 for x in real) / n, blun=100 * sum(x >= 0.10 for x in real) / n,
            mine=100 * sum(x >= 0.03 for x in mine) / n, warn=100 * warns / n,
            unjudged=100 * unjudged[pl] / (n + unjudged[pl])))
    print("tier          players  moves   match  best/good  inacc/100  mist/100  blund/100  own-level/100  warn/100  "
          "not judged  skill t")
    out = {}
    for tier in ('novice', 'intermediate', 'strong', 'expert'):
        xs = rows.get(tier)
        if not xs: continue
        med = lambda k: st.median(x[k] for x in xs)
        out[tier] = {k: med(k) for k in ('match', 'good', 'inacc', 'mist', 'blun', 'mine', 'warn', 'unjudged', 't')}
        out[tier]['players'] = len(xs)
        print(f"{tier:13s} {len(xs):6d} {sum(x['n'] for x in xs):7d}  {100 * med('match'):5.1f}%   {100 * med('good'):6.1f}%"
              f"   {med('inacc'):8.2f}  {med('mist'):8.2f}  {med('blun'):8.2f}   {med('mine'):12.2f}  {med('warn'):8.2f}"
              f"  {med('unjudged'):8.2f}%  {med('t'):.4f}")
    json.dump(out, open(out_json, 'w'), indent=1)

if __name__ == '__main__':
    main()
