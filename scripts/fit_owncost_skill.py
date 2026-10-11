#!/usr/bin/env python3
"""Skill-banded "your cost" maps (workstream cal8, 2026-10-07): the share of a player's own chances of the next tile
that a move costs, as a function of its relative value loss, by skill band (the human move model's theta, as reviews
fit it) x phase (0: largest tile <= 512, 1: 1024-2048, 2: 4096-8192).
Truth: the review workstream's player-level measurements (results/review/stage2_measured.json: 256 CRN playouts of
the human move model at the stretch's fitted skill, to the next tile; flagged moves + random unflagged ones), the
stretch skills in results/review/skills.tsv. Fit: monotone (isotonic, weighted) means of the measured share on a value
loss grid per band x phase; bins without data fall back to the installed phase map (marked). Validation: K folds by
player (held-out RMSE / rank correlation vs the installed phase-only map; unweighted and with population weights =
1 / inclusion probability of flagged vs random moves).
usage: fit_owncost_skill.py [--split -0.4] [--folds 5] [--write MODEL.txt]"""
import json, math, sys, random, collections

GRID = [0.0, 0.01, 0.03, 0.06, 0.10, 0.15, 0.25, 0.40, 0.60, 1.0]

def load_model_own(path):
    own = {}
    for line in open(path):
        p = line.split()
        if p and p[0] == 'lossmap_own': own[int(p[1])] = [float(x) for x in p[2:]]
    return own

def interp(m, x):
    xs, ys = m[0::2], m[1::2]
    if x <= xs[0]: return ys[0]
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]: return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / max(1e-12, xs[i + 1] - xs[i])
    return min(1.0, ys[-1] * x / max(1e-12, xs[-1]))

def phase_of(top):
    t = int(top)
    return 0 if t <= 512 else 1 if t <= 2048 else 2 if t <= 8192 else 3

def load_rows():
    d = json.load(open('results/review/stage2_measured.json'))
    sk = {a: float(b) for a, b in (l.split() for l in open('results/review/skills.tsv'))}
    nflag = sum(1 for x in d if x['kind'] == 'flagged'); nrand = sum(1 for x in d if x['kind'] != 'flagged')
    # inclusion probabilities (stage2_tables.txt: flagged population 1107, unflagged 22402)
    w = {'flagged': 1107 / max(1, nflag), 'random': 22402 / max(1, nrand)}
    rows = []
    for x in d:
        th = sk.get(x['sid'])
        if th is None or x['played'] == x['ref']: continue  # the reference move costs 0 by definition
        ph = phase_of(x['top'])
        if ph > 2: continue
        rows.append(dict(th=th, vl=float(x['value_loss']), ph=ph, mP=float(x['mP']), player=x['player'],
                         tier=x['tier'], w=w['flagged' if x['kind'] == 'flagged' else 'random']))
    return rows

def isotonic(ys, ws):
    # pool-adjacent-violators, non-decreasing
    blocks = [[y, w, 1] for y, w in zip(ys, ws)]
    out = []
    for b in blocks:
        out.append(b)
        while len(out) > 1 and out[-2][0] > out[-1][0]:
            y2, w2, n2 = out.pop(); y1, w1, n1 = out.pop()
            out.append([(y1 * w1 + y2 * w2) / (w1 + w2), w1 + w2, n1 + n2])
    res = []
    for y, w, n in out: res += [y] * n
    return res

def fit_band(rows, default_map, min_n=6):
    """Monotone map on GRID: bin means (bins between grid points, value at the bin's mean x), pooled; returns
    (map list x1 y1 ..., list of extrapolated grid points)."""
    pts = []  # (x, mean, weight)
    for lo, hi in zip(GRID, GRID[1:]):
        b = [r for r in rows if lo <= r['vl'] < hi]
        if len(b) >= min_n:
            mx = sum(r['vl'] for r in b) / len(b)
            pts.append((mx, max(0.0, sum(r['mP'] for r in b) / len(b)), len(b)))
    if not pts: return None, []
    ys = isotonic([p[1] for p in pts], [p[2] for p in pts])
    xs = [p[0] for p in pts]
    m = [0.0, 0.0]
    for x, y in zip(xs, ys):
        if x > m[-2] + 1e-9: m += [round(x, 4), round(y, 4)]
    # beyond the data: the installed phase map, but never below the fitted end (monotone)
    last_x, last_y = m[-2], m[-1]
    extra = []
    for x in GRID:
        if x > last_x + 0.02:
            y = max(last_y, interp(default_map, x))
            m += [x, round(y, 4)]; extra.append(x); last_y = y
    return m, extra

def predict(maps, default, r, split):
    band = 0 if r['th'] < split else 1
    m = maps.get((band, r['ph']))
    return interp(m if m else default[r['ph']], r['vl'])

def spearman(a, b):
    def ranks(v):
        idx = sorted(range(len(v)), key=lambda i: v[i]); rk = [0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[idx[j + 1]] == v[idx[i]]: j += 1
            for k in range(i, j + 1): rk[idx[k]] = (i + j) / 2
            i = j + 1
        return rk
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float('nan')

def main():
    args = sys.argv[1:]
    split, folds, write = -0.4, 5, None
    while args:
        a = args.pop(0)
        if a == '--split': split = float(args.pop(0))
        elif a == '--folds': folds = int(args.pop(0))
        elif a == '--write': write = args.pop(0)
    default = load_model_own('weights/calib/model.txt')
    rows = load_rows()
    print(f"{len(rows)} measured moves (played != reference, phases 0-2); skill split theta {split}")
    # held-out by player
    players = sorted(set(r['player'] for r in rows))
    random.Random(7).shuffle(players)
    fold_of = {p: i % folds for i, p in enumerate(players)}
    pred_new, pred_old, truth, wts, bands, tiers = [], [], [], [], [], []
    for f in range(folds):
        tr = [r for r in rows if fold_of[r['player']] != f]
        te = [r for r in rows if fold_of[r['player']] == f]
        maps = {}
        for band in (0, 1):
            for ph in (0, 1, 2):
                sel = [r for r in tr if (0 if r['th'] < split else 1) == band and r['ph'] == ph]
                m, _ = fit_band(sel, default[ph])
                if m: maps[(band, ph)] = m
        for r in te:
            pred_new.append(predict(maps, default, r, split)); pred_old.append(interp(default[r['ph']], r['vl']))
            truth.append(r['mP']); wts.append(r['w']); bands.append(0 if r['th'] < split else 1); tiers.append(r['tier'])
    def rmse(p, sel=None, weighted=False):
        idx = [i for i in range(len(truth)) if sel is None or sel(i)]
        if not idx: return float('nan')
        w = [wts[i] if weighted else 1.0 for i in idx]
        return math.sqrt(sum(wi * (p[i] - truth[i]) ** 2 for wi, i in zip(w, idx)) / sum(w))
    def bias(p, sel):
        idx = [i for i in range(len(truth)) if sel(i)]
        return sum(p[i] - truth[i] for i in idx) / max(1, len(idx)), len(idx)
    print("held-out (5 folds by player): RMSE x100, installed phase map -> skill-banded")
    for name, sel in [('all', None), ('novice-band', lambda i: bands[i] == 0), ('upper band', lambda i: bands[i] == 1),
                      ('novice tier', lambda i: tiers[i] == 'novice'), ('intermediate', lambda i: tiers[i] == 'intermediate'),
                      ('strong', lambda i: tiers[i] == 'strong')]:
        print(f"   {name:13s} {100 * rmse(pred_old, sel):6.2f} -> {100 * rmse(pred_new, sel):6.2f}   (population-weighted "
              f"{100 * rmse(pred_old, sel, True):6.2f} -> {100 * rmse(pred_new, sel, True):6.2f})")
    for name, sel in [('flagged-size moves (est >= 3%)', lambda i: pred_old[i] >= 0.03)]:
        bo, n = bias(pred_old, sel); bn, _ = bias(pred_new, sel)
        print(f"   mean (estimate - measured) on {name}: n={n} installed {bo:+.3f}, banded {bn:+.3f}")
    print(f"   Spearman estimate ~ measured: installed {spearman(pred_old, truth):.3f}, banded {spearman(pred_new, truth):.3f}")
    for band in (0, 1):
        idx = [i for i in range(len(truth)) if bands[i] == band]
        if idx:
            print(f"   band {band}: Spearman installed {spearman([pred_old[i] for i in idx], [truth[i] for i in idx]):.3f}, "
                  f"banded {spearman([pred_new[i] for i in idx], [truth[i] for i in idx]):.3f} (n={len(idx)})")
    # final maps on all data
    print("final maps (all data):")
    lines = [f"own_split {split}"]
    for band in (0, 1):
        for ph in (0, 1, 2):
            sel = [r for r in rows if (0 if r['th'] < split else 1) == band and r['ph'] == ph]
            m, extra = fit_band(sel, default[ph])
            if not m:
                print(f"   band {band} phase {ph}: no data (n={len(sel)}) -> the phase map is used"); continue
            key = 'lossmap_own_lo' if band == 0 else 'lossmap_own_hi'
            lines.append(f"{key} {ph} " + ' '.join(f"{v:.4f}" for v in m))
            print(f"   band {band} phase {ph} (n={len(sel)}): " + ' '.join(f"{m[i]:.3f}->{m[i+1]:.3f}" for i in range(0, len(m), 2))
                  + (f"   [extrapolated from the phase map at x >= {extra[0]}]" if extra else ''))
    if write:
        with open(write, 'a') as f:
            for l in lines: f.write(l + '\n')
        print(f"appended {len(lines)} lines to {write}")
    else:
        print('\n'.join(lines))

if __name__ == '__main__':
    main()
