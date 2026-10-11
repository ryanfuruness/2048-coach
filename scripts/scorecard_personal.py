#!/usr/bin/env python3
"""Personal-odds metrics for the scorecard: from calib_personal_real.py's per-position rows (real players' outcomes in
the curated games: did the player reach 2x / 4x the position's largest tile, outcome observed) the log-loss, Brier
score and AUC of the personal odds (at the player's fitted skill) and of the engine odds, mean predicted vs observed
(overall and by tier); and the mean MAE over the skill levels of calib_pers_report.py (soft-player playouts from real
positions). Note: videos are selected for success (a tier is the largest tile the player reached), so absolute levels
are biased; the ranking (AUC) is the cleaner number.
usage: scorecard_personal.py NAME   (reads results/scorecard/NAME/personal_real.tsv, personal_soft.txt; writes
       personal.json there)"""
import collections, json, math, re, sys


def auc(ps, ys):
    pos = [p for p, y in zip(ps, ys) if y == 1]
    neg = [p for p, y in zip(ps, ys) if y == 0]
    if not pos or not neg: return float('nan')
    allv = sorted([(p, 1) for p in pos] + [(p, 0) for p in neg])
    # rank-sum with ties averaged
    ranks, i = {}, 0
    r = [0.0] * len(allv)
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]: j += 1
        for k in range(i, j + 1): r[k] = (i + j) / 2 + 1
        i = j + 1
    sp = sum(rk for rk, (_, y) in zip(r, allv) if y == 1)
    return (sp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def scores(ps, ys):
    ll = sum(-(y * math.log(min(max(p, 1e-4), 1 - 1e-4)) + (1 - y) * math.log(1 - min(max(p, 1e-4), 1 - 1e-4)))
             for p, y in zip(ps, ys)) / len(ps)
    br = sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)
    return dict(n=len(ps), predicted=sum(ps) / len(ps), observed=sum(ys) / len(ys), logloss=ll, brier=br, auc=auc(ps, ys))


def main():
    name = sys.argv[1]
    D = f'results/scorecard/{name}'
    rows = []
    with open(f'{D}/personal_real.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            rows.append(dict(zip(hdr, line.rstrip('\n').split('\t'))))
    out = {}
    for mult in ('2', '4'):
        rs = [r for r in rows if r['mult'] == mult]
        if not rs: continue
        ys = [int(r['reached']) for r in rs]
        pers = scores([float(r['personal']) for r in rs], ys)
        pers['games'] = len(set(r['game'] for r in rs))
        eng_rows = [r for r in rs if r['engine'] not in ('None', '')]
        eng = scores([float(r['engine']) for r in eng_rows], [int(r['reached']) for r in eng_rows]) if eng_rows else None
        tiers = {}
        for t in ('novice', 'intermediate', 'strong', 'expert'):
            b = [r for r in rs if r['tier'] == t]
            if len(b) >= 20:
                tiers[t] = dict(n=len(b), predicted=sum(float(r['personal']) for r in b) / len(b),
                                observed=sum(int(r['reached']) for r in b) / len(b))
        out[mult + 'x'] = dict(personal=pers, engine=eng, tiers=tiers)
        print(f"real outcomes, {mult}x the tile: {pers['n']} positions, {pers['games']} games; personal odds: predicted "
              f"{pers['predicted']:.3f} vs observed {pers['observed']:.3f}, log-loss {pers['logloss']:.3f}, Brier "
              f"{pers['brier']:.3f}, AUC {pers['auc']:.3f}" + (f" | engine odds: log-loss {eng['logloss']:.3f}, AUC "
                                                                  f"{eng['auc']:.3f}" if eng else ''))
        print("   by tier (predicted vs observed): " + ', '.join(f"{t} {v['predicted']:.2f}/{v['observed']:.2f}"
                                                                for t, v in tiers.items()))
    soft = collections.defaultdict(list)
    target = None
    try:
        for line in open(f'{D}/personal_soft.txt'):
            m = re.match(r'== (\d)x', line)
            if m: target = m.group(1) + 'x'
            m = re.search(r't=(\S+)\s+n=\s*(\d+).*MAE ([\d.]+) LL ([\d.]+)', line)
            if m and target: soft[target].append((float(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4))))
    except FileNotFoundError:
        pass
    for tg, xs in soft.items():
        n = sum(x[1] for x in xs)
        mae = sum(x[1] * x[2] for x in xs) / n
        ll = sum(x[1] * x[3] for x in xs) / n
        out.setdefault('soft', {})[tg] = dict(n=n, mae=mae, logloss=ll)
        print(f"soft-player playouts from real positions, {tg}: {n} (position, t) pairs, MAE {mae:.3f}, log-loss {ll:.3f}")
    json.dump(out, open(f'{D}/personal.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
