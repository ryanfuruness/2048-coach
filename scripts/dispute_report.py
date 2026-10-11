#!/usr/bin/env python3
"""Report for the human-dispute judge: for decisions where the engine claimed a large loss for the player's move
(human_disputes.py) and for control decisions, the rollout values of the player's move and the engine's move.
A dispute is CONFIRMED when the engine's move beats the player's by more than 2 standard errors in the rollouts,
REFUTED when the player's move is at least as good (rollout loss below 2 se), with the claimed vs rollout loss.
usage: dispute_report.py DISPUTES.tsv ROLLOUT.tsv"""
import sys, math, collections
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}

def main():
    meta = {}
    with open(sys.argv[1]) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            meta[int(r['idx'])] = r
    q = collections.defaultdict(dict)
    with open(sys.argv[2]) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            q[int(r['pos'])][r['move']] = (float(r['q']), float(r['q_se']), float(r['died']))
    groups = collections.defaultdict(lambda: collections.Counter())
    rel = collections.defaultdict(list)
    for i, m in meta.items():
        if i not in q:
            continue
        p, e = NAME[m['played']], NAME[m['engine']]
        if p not in q[i] or e not in q[i]:
            continue
        (qp, sp, dp), (qe, se, de) = q[i][p], q[i][e]
        s = math.sqrt(sp * sp + se * se)
        best = max(v[0] for v in q[i].values())
        g = m['group']
        if p == e:
            groups[g]['same move'] += 1
            continue
        loss = qe - qp
        verdict = 'confirmed' if loss > 2 * s else ('refuted' if loss < 2 * s and qp >= qe - s else 'unclear')
        groups[g][verdict] += 1
        rel[g].append((float(m['claimed_loss']), loss / max(1.0, abs(best)), int(m['max']), verdict))
    for g, c in groups.items():
        print(f"{g}: {dict(c)}")
        xs = rel[g]
        if xs:
            cl = sum(x[0] for x in xs) / len(xs)
            rl = sum(x[1] for x in xs) / len(xs)
            print(f"   mean claimed relative loss {100 * cl:.1f}%, mean rollout relative loss {100 * rl:.1f}%")
            by = collections.defaultdict(list)
            for x in xs:
                by[x[2]].append(x)
            for t in sorted(by):
                ys = by[t]
                conf = sum(1 for y in ys if y[3] == 'confirmed')
                print(f"   max tile {t:6d}: {len(ys):4d} disputes, confirmed {conf:4d}, claimed {100 * sum(y[0] for y in ys) / len(ys):5.1f}%"
                      f", rollout {100 * sum(y[1] for y in ys) / len(ys):5.1f}%")

if __name__ == '__main__':
    main()
