#!/usr/bin/env python3
"""Report for build/rollout outputs: how often the engine's move is not the rollout-best move, and what it costs.

usage: judge_report.py FILE.tsv [--z 2.0]
A position counts as an engine error when the rollout value of the best move exceeds the engine move's by more than
z combined standard errors. Loss = rollout best - rollout value of the engine's move (points), averaged over positions.
"""
import sys, math, collections

def main():
    path = sys.argv[1]
    z = float(sys.argv[sys.argv.index('--z') + 1]) if '--z' in sys.argv else 2.0
    pos = collections.defaultdict(list)
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            pos[int(r['pos'])].append(r)
    n = err = 0
    loss_sum = 0.0
    agree_value = 0
    by_max = collections.defaultdict(lambda: [0, 0, 0.0])
    examples = []
    for p, rows in sorted(pos.items()):
        if len(rows) < 2:
            continue
        eng = rows[0]['engine_move']
        er = [r for r in rows if r['move'] == eng]
        if not er:
            continue
        er = er[0]
        best = max(rows, key=lambda r: float(r['q']))
        qb, qe = float(best['q']), float(er['q'])
        se = math.sqrt(float(best['q_se']) ** 2 + float(er['q_se']) ** 2)
        n += 1
        loss = qb - qe
        loss_sum += loss
        bad = best['move'] != eng and loss > z * se
        err += bad
        # does the engine's value ranking agree with the rollout ranking on the best move?
        vbest = max(rows, key=lambda r: float(r['value']))
        agree_value += vbest['move'] == best['move']
        m = int(rows[0]['max'])
        by_max[m][0] += 1
        by_max[m][1] += bad
        by_max[m][2] += loss
        if bad:
            examples.append((loss, p, rows[0]['board'], eng, best['move'], rows))
    print(f"{path}: {n} positions, engine move significantly worse than the rollout best (z={z}): {err} "
          f"({100.0 * err / max(1, n):.1f}%), mean rollout loss of the engine move {loss_sum / max(1, n):,.0f} points, "
          f"value-best = rollout-best {100.0 * agree_value / max(1, n):.1f}%")
    for m in sorted(by_max):
        c, e, l = by_max[m]
        print(f"   max {m:6d}: {c:4d} positions, errors {e:3d} ({100.0 * e / c:5.1f}%), mean loss {l / c:9,.0f}")
    examples.sort(reverse=True)
    for loss, p, board, eng, bm, rows in examples[:8]:
        print(f"\n  pos {p} loss {loss:,.0f}: engine {eng}, rollouts prefer {bm}")
        cells = [int(c, 16) for c in board]
        for r in range(4):
            print('   ' + ''.join(f"{(1 << v) if v else '.':>7}" for v in cells[4 * r:4 * r + 4]))
        for r in sorted(rows, key=lambda r: -float(r['q'])):
            print(f"     {r['move']}: rollout {float(r['q']):10,.0f} +- {float(r['q_se']):7,.0f}  value {float(r['value']):10,.0f}"
                  f"  died {float(r['died']):.2f}")

if __name__ == '__main__':
    main()
