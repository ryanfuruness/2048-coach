#!/usr/bin/env python3
"""Loss map for table-decided positions: in positions where an exact endgame table decided the engine's move, a move's
real loss is estimated from the exact success probabilities instead of the network values: x = (p_ref - p_move) /
p_ref (p = the table's success probability after the move, ref = the engine's move), mapped to the rollout real loss
by isotonic regression ('lossmap_table' line; build/analyze uses it when both moves have a table p). The table loss
alone overstates the real loss (failing the table's sub-goal is partly repaired: 29% -> ~20%, 66% -> ~39%) but
through this map it beats the value-based map (5-fold by video RMSE 13.7 vs 14.5, 411 pairs, 2026-10-07).

Inputs: build/analyze --preset best --stdin JSON lines for the judged table positions (per-move "p"), and the judge
rollout TSVs (results/judge/late300_h1000.tsv, results/cal6/j1200, results/cal6/jx).
usage: fit_lossmap_table.py ANALYSIS.jsonl [--model OUT.txt] ROLLOUT.tsv ..."""
import collections, json, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import fit_lossmap2 as F  # noqa: E402

def main():
    args = sys.argv[1:]
    jl, model = args.pop(0), None
    if args and args[0] == '--model':
        args.pop(0); model = args.pop(0)
    ana = {}
    for line in open(jl):
        a = json.loads(line); ana[a['hex']] = a
    rows = collections.defaultdict(dict)
    for path in args:
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                if r['source'] == 'search':
                    continue
                d = {'U': 'up', 'R': 'right', 'D': 'down', 'L': 'left'}[r['move']]
                rows[(path, r['pos'], r['board'])][d] = float(r['q'])
    pts, base = [], []
    for (_, _, b), mv in rows.items():
        a = ana.get(b)
        if not a or len(mv) < 2:
            continue
        pm = {m['move']: m.get('p') for m in a['moves']}
        eng = a.get('engine_move')
        if eng not in pm or pm[eng] is None or pm[eng] <= 0:
            continue
        qb = max(mv.values())
        for d, q in mv.items():
            if pm.get(d) is None:
                continue
            dq = max(0.0, (qb - q) / max(100000.0, abs(qb)))
            if d == eng:
                base.append(dq)  # the engine's own move: the noise floor of the rollout loss
            else:
                pts.append((max(0.0, (pm[eng] - pm[d]) / pm[eng]), dq))
    floor = sum(base) / max(1, len(base))
    knots = F.fit([(x, max(0.0, y - floor)) for x, y in pts], min_n=3)
    line = 'lossmap_table ' + ' '.join(f"{x:.5g} {y:.5g}" for x, y in knots)
    print(f"{len(pts)} (table position, move) pairs; noise floor {100 * floor:.2f}% (engine's own move)")
    for x, y in knots:
        print(f"   table loss {100 * x:6.2f}%  ->  real loss {100 * y:6.2f}%")
    if model:
        keep = [l for l in open(model) if not l.startswith('lossmap_table ')]
        with open(model, 'w') as f:
            f.writelines(keep); f.write(line + '\n')
        print('->', model)
    else:
        print(line)

if __name__ == '__main__':
    main()
