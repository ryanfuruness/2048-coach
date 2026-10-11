"""Is the coach's least preferred move worse for a human? (2026-10-11, a check before grading by rank)

Uses the "your chance" ground truth (results/yc): 210 real positions, 400 playouts per legal move of the simulated human
player (keys .016 = casual default, .007 = stronger), with common random numbers, and the engine's per-move value loss
(loss_rel) for the same positions. Per position: the human chance after each move; is the engine's worst-ranked move
also worse for the human, and by how much?
  python3 scripts/worstmove_check.py
"""
import collections, csv, json, math

pos = {r['id']: r for r in csv.DictReader(open('results/yc/pos_gt1.tsv'), delimiter='\t')}
eng = {json.loads(l)['id']: json.loads(l) for l in open('results/yc/gt1_engine.jsonl')}
acc = collections.defaultdict(lambda: collections.defaultdict(list))
for r in csv.DictReader(open('results/yc/gt1.tsv'), delimiter='\t'):
    for d in 'URDL':
        v = int(r['r_' + d])
        if v >= 0:
            acc[(r['id'], r['key'])][d].append(v)

rows = collections.defaultdict(list)
for (pid, key), mv in acc.items():
    e = eng.get(pid)
    if not e or len(mv) < 3:
        continue
    board = pos[pid]['board']
    top = 2 ** max(int(c, 16) for c in board)
    p = {d: sum(v) / len(v) for d, v in mv.items()}
    lr = {d: e['moves'][d]['loss_rel'] for d in mv if d in e['moves'] and e['moves'][d]['loss_rel'] is not None}
    if len(lr) < 3:
        continue
    order = sorted(lr, key=lambda d: lr[d])  # engine's preference, best first
    worst, second = order[-1], order[-2]
    others = [d for d in order if d != worst]
    spread = lr[worst] - lr[order[0]]
    human_worst = min(p, key=p.get)
    rows[(key, top)].append(dict(
        gap_worst=p[worst] - sum(p[d] for d in others) / len(others),
        gap_second=p[second] - sum(p[d] for d in order if d not in (worst, second)) / (len(order) - 2),
        hit=worst == human_worst, n=len(order), spread=spread))

print('| key | biggest tile | positions | engine-worst move vs the others (points) | engine-worst = human-worst | (chance level) | 2nd-worst vs the rest | engine spread (median) |')
print('|---|---|---|---|---|---|---|---|')
for key in ('0.016', '0.007'):
    for top in sorted({t for k, t in rows if k == key}):
        xs = rows[(key, top)]
        g = [x['gap_worst'] for x in xs]
        mean = sum(g) / len(g)
        se = math.sqrt(sum((v - mean) ** 2 for v in g) / (len(g) - 1) / len(g))
        g2 = [x['gap_second'] for x in xs]
        hit = sum(x['hit'] for x in xs) / len(xs)
        chance = sum(1 / x['n'] for x in xs) / len(xs)
        sp = sorted(x['spread'] for x in xs)[len(xs) // 2]
        print(f"| {key} | {top} | {len(xs)} | {100*mean:+.1f} ± {100*se:.1f} | {100*hit:.0f}% | {100*chance:.0f}% | {100*sum(g2)/len(g2):+.1f} | {100*sp:.1f}% |")
