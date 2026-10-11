#!/usr/bin/env python3
"""Fits the "your cost" map of the analysis (Calib::own_cost, model line `lossmap_own PHASE x1 y1 x2 y2 ...`): the
share of a human-like player's OWN chances of the next milestone that a move costs, against the engine's move, as a
function of the move's relative value loss, per phase of the game (0: largest tile up to 512, 1: 1024-2048, 2:
4096-8192; analyze's skill_phase).

Data: the coach workstream's "first" runs (src/coach.cpp --mode first; results/coach/first_*.tsv with the position
metadata *_meta.tsv): for every legal first move of a real human position, the share of playouts in which the player
(softmax players t = 0.003-0.1 and the "structured" players) reaches the next milestone when it continues. The cost of
move d = (P(engine's move) - P(d)) / P(engine's move), pooled within a value-loss bin as sum of drops / sum of bases
(robust where P is small); 80% bootstrap bands over positions. The coach found the share nearly skill-independent
(results/coach/REPORT.md), so skills are pooled. The map is made monotone (weighted pool-adjacent-violators over the bins) and starts at (0, 0).

usage: fit_owncost.py [--boot 200] [--model weights/calib/model.txt] [--out results/integ/owncost.txt]"""
import argparse, collections, json, os, random
import numpy as np

R = 'results/coach'
DIRS = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
SOURCES = [('firstbig', ['big', 'bigstruct']), ('firstpool', ['pool']), ('before', ['before']),
           ('mistakes', ['mistakes', 'mistakesstruct'])]
BINS = [0.01, 0.03, 0.06, 0.10, 0.15, 0.20, 0.30, 0.45, 0.70, 10.0]
GROUPS = {'S1': 0, 'S2': 1, 'S3': 2}


def read_tsv(path):
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            yield dict(zip(hdr, line.rstrip('\n').split('\t')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boot', type=int, default=200)
    ap.add_argument('--out', default='results/integ/owncost.txt')
    a = ap.parse_args()
    metas = {}
    for name, _ in SOURCES:
        p = f'{R}/{name}_meta.tsv'
        if os.path.exists(p):
            for r in read_tsv(p):
                metas.setdefault(r['id'], {})[name] = r
    # relative value losses of every move (the analysis' definition), from the human-data analysis
    rel = {}
    for line in open('results/human_ds/analysis.jsonl'):
        x = json.loads(line)
        rid = f"{x['video']}:{x['segment']}:{x['ply']}"
        if rid not in metas: continue
        v = {DIRS[m['move']]: m['value'] for m in x['moves']}
        em = DIRS[x['engine_move']]
        ref = v[em]
        rel[rid] = (em, {d: max(0.0, ref - y) / max(100000.0, abs(ref)) for d, y in v.items()})
    # per (source, position, continuation): per move [playouts, reached]
    acc = collections.defaultdict(lambda: np.zeros((4, 2)))
    for src, names in SOURCES:
        for name in names:
            p = f'{R}/first_{name}.tsv'
            if not os.path.exists(p): continue
            for r in read_tsv(p):
                if r['cont'] == '0': continue  # the engine's own continuation: that is the real-loss map's job
                c = ('s' if name.endswith('struct') else '') + r['cont']
                q = acc[(src, r['id'], c)]
                for k, d in enumerate('URDL'):
                    y = int(r[f'r1_{d}'])
                    if y >= 0: q[k] += [1, y]
    # samples per phase: (position id, bin, drop, base)
    samples = collections.defaultdict(list)
    for (src, i, c), q in acc.items():
        m = metas.get(i, {}).get(src)
        if not m or i not in rel or m['group'] not in GROUPS: continue
        em, rl = rel[i]
        ek = 'URDL'.index(em)
        if q[ek][0] == 0: continue
        pe = q[ek][1] / q[ek][0]
        for k, d in enumerate('URDL'):
            if k == ek or q[k][0] == 0 or d not in rl: continue
            x = rl[d]
            if x < BINS[0]: continue
            b = next(j for j in range(len(BINS) - 1) if BINS[j] <= x < BINS[j + 1])
            samples[GROUPS[m['group']]].append((i, b, x, pe - q[k][1] / q[k][0], pe))
    rng = random.Random(1)
    lines, report = [], []
    for ph in sorted(samples):
        S = samples[ph]
        ids = sorted({s[0] for s in S})
        by_id = collections.defaultdict(list)
        for s in S: by_id[s[0]].append(s)

        def binstats(rows):
            num, den, xs = (collections.defaultdict(float) for _ in range(3))
            n = collections.Counter()
            for _, b, x, drop, pe in rows:
                num[b] += drop; den[b] += pe; xs[b] += x; n[b] += 1
            return {b: (xs[b] / n[b], num[b] / den[b] if den[b] > 0 else 0.0, n[b]) for b in n}
        est = binstats(S)
        boots = collections.defaultdict(list)
        for _ in range(a.boot):
            rows = [s for j in (rng.choice(ids) for _ in ids) for s in by_id[j]]
            for b, (_, y, _) in binstats(rows).items(): boots[b].append(y)
        report.append(f"phase {ph} ({['<=512', '1024-2048', '4096-8192'][ph]}): {len(ids)} positions, {len(S)} move/player pairs")
        keep = [b for b in sorted(est) if est[b][2] >= 20]  # too few pairs for a knot otherwise
        # weighted pool-adjacent-violators: a non-decreasing fit of the bin means (weights = pairs per bin)
        blocks = []  # [sum w*y, sum w, bins]
        for b in keep:
            blocks.append([est[b][1] * est[b][2], est[b][2], [b]])
            while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
                w = blocks.pop()
                blocks[-1][0] += w[0]; blocks[-1][1] += w[1]; blocks[-1][2] += w[2]
        fit = {b: max(0.0, blk[0] / blk[1]) for blk in blocks for b in blk[2]}
        pts = [(0.0, 0.0)]
        for b in keep:
            x, y, n = est[b]
            lo, hi = np.percentile(boots[b], [10, 90]) if boots[b] else (y, y)
            pts.append((x, fit[b]))
            report.append(f"   value loss {BINS[b]:.2f}-{BINS[b + 1]:.2f} (mean {x:.3f}, n={n:5d}): own chances lost {y:+.3f}"
                          f" [80%: {lo:+.3f} {hi:+.3f}] -> knot {fit[b]:.3f}")
        lines.append(f"lossmap_own {ph} " + " ".join(f"{x:.4f} {y:.4f}" for x, y in pts))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        f.write("\n".join(report) + "\n\n" + "\n".join(lines) + "\n")
    print("\n".join(report))
    print("\n".join(lines))


if __name__ == '__main__':
    main()
