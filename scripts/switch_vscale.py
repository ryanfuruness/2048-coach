#!/usr/bin/env python3
"""Engine switch, odds part (scripts/switch_engine.sh): the odds model's value term is log(value / vbar(sum)) and its
expected future points are ratio(sum) x value, both fitted on the old engine's values. New late-game networks may value
the same positions on another scale. This compares the best move's value per judged position, old (the judge TSVs, the
old engine) vs new (the same positions re-valued by judge_revalue.py), for positions with a tile sum of 16384 or more,
and scales the model's vbar knots at log2 sum >= 14 by the median ratio new / old (per knot where >= 30 positions fall
next to it, else the overall median) and ratio knots by its inverse, in place.
usage: switch_vscale.py MODEL.txt OLD NEW [OLD NEW ...]   (OLD/NEW: a judge TSV or a directory of them, same names)"""
import collections, math, os, statistics, sys


def best_values(path):
    best = {}
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            k = r['board']
            v = float(r['value'])
            if k not in best or v > best[k][0]:
                best[k] = (v, float(r['sum']))
    return best


def files(old, new):
    if os.path.isdir(old):
        for n in sorted(os.listdir(new)):
            if n.endswith('.tsv') and os.path.exists(os.path.join(old, n)):
                yield os.path.join(old, n), os.path.join(new, n)
    else:
        yield old, new


def main():
    model, pairs = sys.argv[1], sys.argv[2:]
    ratios = []  # (log2 sum, log ratio)
    for i in range(0, len(pairs), 2):
        for fo, fn in files(pairs[i], pairs[i + 1]):
            bo, bn = best_values(fo), best_values(fn)
            for k, (vo, s) in bo.items():
                if k in bn and s >= 16384 and vo > 1000 and bn[k][0] > 1000:
                    ratios.append((math.log2(s), math.log(bn[k][0] / vo)))
    lines = open(model).read().rstrip('\n').split('\n')
    get = {l.split()[0]: i for i, l in enumerate(lines) if l.strip()}
    knots = [float(x) for x in lines[get['knots']].split()[1:]]
    vbar = [float(x) for x in lines[get['vbar']].split()[1:]]
    ratio = [float(x) for x in lines[get['ratio']].split()[1:]]
    if len(ratios) < 30:
        print(f"only {len(ratios)} positions with a 16384+ re-valued: model unchanged")
        return
    overall = statistics.median(r for _, r in ratios)
    print(f"{len(ratios)} positions with a tile sum >= 16384: median value ratio new / old {math.exp(overall):.4f} "
          f"(log {overall:+.4f}; quartiles {math.exp(statistics.quantiles([r for _, r in ratios], n=4)[0]):.4f} - "
          f"{math.exp(statistics.quantiles([r for _, r in ratios], n=4)[2]):.4f})")
    for j, kn in enumerate(knots):
        if kn < 14:
            continue
        lo = knots[j - 1] if j > 0 else kn - 1
        hi = knots[j + 1] if j + 1 < len(knots) else kn + 1
        near = [r for s, r in ratios if lo < s < hi]
        f = statistics.median(near) if len(near) >= 30 else overall
        print(f"   knot {kn:5.2f}: {len(near):4d} positions nearby, scale vbar x {math.exp(f):.4f}, ratio / {math.exp(f):.4f}")
        vbar[j] *= math.exp(f)
        ratio[j] /= math.exp(f)
    lines[get['vbar']] = 'vbar ' + ' '.join(f"{x:.6g}" for x in vbar)
    lines[get['ratio']] = 'ratio ' + ' '.join(f"{x:.6g}" for x in ratio)
    open(model, 'w').write('\n'.join(lines) + '\n')
    print('model ->', model)


if __name__ == '__main__':
    main()
