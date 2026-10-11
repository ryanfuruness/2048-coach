#!/usr/bin/env python3
"""Fit the map from the analysis' relative value loss of a move to its real relative loss (rollout judge data), by
isotonic regression on log-spaced bins; appends a 'lossmap x1 y1 x2 y2 ...' line to a calibration model .txt (or
prints it). The analysis then reports each move's estimated real loss, and the review classifies mistakes by it.
usage: fit_lossmap.py [--model MODEL.txt] [--max-tile LO HI] [--key lossmap|lossmap_late] ROLLOUT.tsv ...
--max-tile keeps positions whose largest tile is in [LO, HI]; --key names the model line (lossmap_late: the map
build/analyze uses for positions with a tile of 2048 or more)."""
import sys, collections, math

def main():
    args = sys.argv[1:]
    model, key, lo_t, hi_t = None, 'lossmap', 0, 1 << 30
    while args and args[0].startswith('--'):
        a = args.pop(0)
        if a == '--model': model = args.pop(0)
        elif a == '--key': key = args.pop(0)
        elif a == '--max-tile': lo_t, hi_t = int(args.pop(0)), int(args.pop(0))
    pos = collections.defaultdict(list)
    for path in args:
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                if not lo_t <= int(r['max']) <= hi_t:
                    continue
                pos[(path, r['pos'])].append(r)
    pts = []
    for rows in pos.values():
        vb = max(float(r['value']) for r in rows)
        qb = max(float(r['q']) for r in rows)
        for r in rows:
            dv = (vb - float(r['value'])) / max(100000.0, abs(vb))
            dq = max(0.0, (qb - float(r['q'])) / max(100000.0, abs(qb)))
            pts.append((dv, dq))
    edges = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.4, 10]
    xs, ys, ns = [], [], []
    for lo, hi in zip(edges, edges[1:]):
        b = [p for p in pts if lo <= p[0] < hi]
        if len(b) < 5:
            continue
        xs.append(sum(p[0] for p in b) / len(b)); ys.append(sum(p[1] for p in b) / len(b)); ns.append(len(b))
    # pool adjacent violators (non-decreasing), weighted by counts
    blocks = [[y, n, [x]] for x, y, n in zip(xs, ys, ns)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            y = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (blocks[i][1] + blocks[i + 1][1])
            blocks[i] = [y, blocks[i][1] + blocks[i + 1][1], blocks[i][2] + blocks[i + 1][2]]
            del blocks[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    knots = []
    for y, n, bx in blocks:
        for x in bx:
            knots.append((x, y))
    # the best move's rollout loss is not 0 (the max over noisy estimates): subtract that noise floor
    floor = knots[0][1] if knots else 0.0
    knots = [(0.0, 0.0)] + [(x, max(0.0, y - floor)) for x, y in knots]
    ns = [0] + ns
    line = key + ' ' + ' '.join(f"{x:.5g} {y:.5g}" for x, y in knots)
    print(f"{len(pts)} (position, move) points; noise floor {100 * floor:.2f}% subtracted")
    for x, y in knots:
        print(f"   value loss {100 * x:7.2f}%  ->  real loss {100 * y:6.2f}%")
    if model:
        with open(model) as f:
            lines = [l for l in f if not l.startswith(key + ' ')]
        with open(model, 'w') as f:
            f.writelines(lines)
            f.write(line + '\n')
        print('appended to', model)
    else:
        print(line)

if __name__ == '__main__':
    main()
