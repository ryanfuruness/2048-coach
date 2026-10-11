#!/usr/bin/env python3
"""cal7: low-end real losses of top-stage moves from REPLICATED paired rollouts (scripts/study_cal7.sh lowend: every
legal move, R replicate runs x 32 playouts, common random numbers across the moves of a run, horizon 1000).

Unlike fit_lossmap2.py (loss vs the best of the noisy rollout means, minus a noise floor), the reference here is FIXED
before the rollouts: the analysis' engine move. Each replicate gives a paired difference d_r = (q_r(engine) -
q_r(move)) / max(100000, |mean q(engine)|), the estimate is the mean over replicates; it is unbiased (no max-selection)
and may be negative (the move is better than the engine's). Points are binned by the analysis' claim dv (relative value
loss vs the engine move, the current engine's values): played moves (-> lossmap_played_expert) and all non-reference
moves (-> lossmap_top). Bands: bootstrap over positions.

usage: judge_lowend_report.py SEL.tsv ROLLOUT_r1.tsv ROLLOUT_r2.tsv ... [--model MODEL.txt] [--analysis CACHE.jsonl]"""
import collections, json, math, random, sys

D = {'U': 'up', 'R': 'right', 'D': 'down', 'L': 'left'}
EDGES = [0, 0.0005, 0.001, 0.003, 0.006, 0.01, 0.02, 0.03, 0.06, 0.1, 0.2, 0.4, 10]

def load_map(path, key):
    for line in open(path):
        p = line.split()
        if p and p[0] == key:
            xs = [float(x) for x in p[1:]]
            return list(zip(xs[0::2], xs[1::2]))

def interp(lm, x):
    if x <= lm[0][0]: return lm[0][1]
    for (x0, y0), (x1, y1) in zip(lm, lm[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, lm[-1][1] * x / max(1e-12, lm[-1][0]))

def main():
    args = sys.argv[1:]
    sel_path = args.pop(0)
    model, cache, runs = 'weights/calib/model.txt', 'results/human_ds_v6b/analysis.jsonl', []
    while args:
        a = args.pop(0)
        if a == '--model': model = args.pop(0)
        elif a == '--analysis': cache = args.pop(0)
        else: runs.append(a)
    sel = []
    with open(sel_path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            sel.append(dict(zip(hdr, line.rstrip('\n').split('\t'))))
    # the analysis' values of every move (claims vs the engine move), from the cache the selection was made from
    want = {r['hex'] for r in sel}
    vals = {}
    for line in open(cache):
        a = json.loads(line)
        if a['hex'] in want and a['hex'] not in vals:
            vals[a['hex']] = {m['move']: m['value'] for m in a['moves']}
    q = collections.defaultdict(dict)  # (pos, move) -> {run: q}
    for k, path in enumerate(runs):
        with open(path) as f:
            h = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(h, line.rstrip('\n').split('\t')))
                q[(int(r['pos']), D[r['move']])][k] = float(r['q'])
    nrun = len(runs)
    pts = []  # (kind, stratum, dv, real, se, pos)
    for i, s in enumerate(sel):
        v = vals.get(s['hex'])
        e = s['engine']
        if not v or e not in v or len(q.get((i, e), {})) < nrun:
            continue
        qe = [q[(i, e)][k] for k in range(nrun)]
        norm = max(100000.0, abs(sum(qe) / nrun))
        vnorm = max(100000.0, abs(v[e]))
        for m in v:
            if m == e or len(q.get((i, m), {})) < nrun:
                continue
            d = [(qe[k] - q[(i, m)][k]) / norm for k in range(nrun)]
            mean = sum(d) / nrun
            sd = math.sqrt(sum((x - mean) ** 2 for x in d) / max(1, nrun - 1))
            dv = max(0.0, v[e] - v[m]) / vnorm
            pts.append(('played' if m == s['played'] else 'other', s['stratum'], dv, mean, sd / math.sqrt(nrun), i,
                        int(s['top'])))
    print(f"{len(sel)} positions, {nrun} replicate runs, {len(pts)} (position, move) points "
          f"({sum(p[0] == 'played' for p in pts)} played moves)")
    lm_top, lm_pe = load_map(model, 'lossmap_top'), load_map(model, 'lossmap_played_expert')
    rnd = random.Random(1)
    for kind, sub in (('played moves (-> lossmap_played_expert)', [p for p in pts if p[0] == 'played']),
                      ('all non-reference moves (-> lossmap_top)', pts),
                      ('  ... of them in 16384 positions', [p for p in pts if p[6] == 16384]),
                      ('  ... of them in 32768+ positions', [p for p in pts if p[6] >= 32768])):
        print(f"\n== {kind}: {len(sub)} points")
        print("   claim bin        n   mean claim   real loss (paired)  80% band (bootstrap over positions)   "
              "installed map (top / played)")
        for lo, hi in zip(EDGES, EDGES[1:]):
            b = [p for p in sub if lo <= p[2] < hi]
            if len(b) < 4:
                continue
            mc = sum(p[2] for p in b) / len(b)
            mr = sum(p[3] for p in b) / len(b)
            byp = collections.defaultdict(list)
            for p in b:
                byp[p[5]].append(p[3])
            keys = list(byp)
            boots = []
            for _ in range(400):
                xs = [x for kk in (rnd.choice(keys) for _ in keys) for x in byp[kk]]
                boots.append(sum(xs) / len(xs))
            boots.sort()
            print(f"   [{lo:6.4f},{hi:6.4f})  {len(b):4d}   {100 * mc:7.2f}%     {100 * mr:7.2f}%          "
                  f"{100 * boots[40]:7.2f}% .. {100 * boots[360]:6.2f}%                 "
                  f"{100 * interp(lm_top, mc):5.2f}% / {100 * interp(lm_pe, mc):5.2f}%")
    # noise check: the mean per-point replicate SE
    se = [p[4] for p in pts]
    print(f"\nmean replicate SE of a point: {100 * sum(se) / max(1, len(se)):.2f}% (one position-move, {nrun} x 32 playouts)")

if __name__ == '__main__':
    main()
