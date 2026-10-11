#!/usr/bin/env python3
"""The same expert disputes judged at two horizons: results/disputes/expert_h300.tsv (H=300, 2026-10-06) vs the cal6
re-judge at H=1000 (results/cal6/jold/expert_*.tsv). Per decision: the rollout loss of the player's move vs the
engine's move (relative to max(|best|, 100000), as the loss maps), verdicts (confirmed: the engine's move better by
> 2 se; refuted: the player's move within 1 se or better), by claim bin.
usage: judge_horizon_disputes.py"""
import collections, glob, math, re

NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def load_q(paths):
    q = collections.defaultdict(dict)
    for p in paths:
        m = re.search(r'_(\d{5})\.tsv$', p)
        off = int(m.group(1)) if m else 0
        with open(p) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                q[int(r['pos']) + off][r['move']] = (float(r['q']), float(r['q_se']))
    return q

def main():
    meta = {}
    with open('results/disputes/expert.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            meta[int(r['idx'])] = r
    qs = {'H=300': load_q(['results/disputes/expert_h300.tsv']),
          'H=1000': load_q(sorted(glob.glob('results/cal6/jold/expert_*.tsv')))}
    res = collections.defaultdict(list)
    for i, m in meta.items():
        if m['group'] != 'dispute':
            continue
        p, e = NAME[m['played']], NAME[m['engine']]
        row = {}
        for h, q in qs.items():
            if i not in q or p not in q[i] or e not in q[i]:
                break
            (qp, sp), (qe, se) = q[i][p], q[i][e]
            best = max(v[0] for v in q[i].values())
            s = math.sqrt(sp * sp + se * se)
            v = 'confirmed' if qe - qp > 2 * s else 'refuted' if qp >= qe - s else 'unclear'
            row[h] = ((qe - qp) / max(100000.0, abs(best)), v)
        else:
            res['all'].append((float(m['claimed_loss']), row))
    xs = res['all']
    print(f"{len(xs)} disputes judged at both horizons")
    for h in qs:
        c = collections.Counter(r[h][1] for _, r in xs)
        print(f"   {h:6s}: {dict(c)}; mean real loss {100 * sum(r[h][0] for _, r in xs) / len(xs):.1f}% "
              f"(claimed {100 * sum(c for c, _ in xs) / len(xs):.1f}%)")
    for lo, hi in ((0.10, 0.20), (0.20, 0.40), (0.40, 9)):
        b = [(c, r) for c, r in xs if lo <= c < hi]
        if b:
            print(f"   claims {100 * lo:.0f}-{100 * hi if hi < 9 else 999:.0f}%: n={len(b):3d}  " + '  '.join(
                f"{h} real {100 * sum(r[h][0] for _, r in b) / len(b):5.1f}% (confirmed {sum(r[h][1] == 'confirmed' for _, r in b)})"
                for h in qs))
    a = [r['H=300'][0] for _, r in xs]; b = [r['H=1000'][0] for _, r in xs]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    corr = cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    print(f"   per-decision correlation of the two horizons' real losses: {corr:.2f}")

if __name__ == '__main__':
    main()
