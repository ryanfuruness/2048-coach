#!/usr/bin/env python3
"""Workstream review, study 2: the chances curve of each stretch at the player's level. Positions every K plies
(and the two around the review's decisive move), each with every legal first move; the human move model at the
stretch's playout skill continues to the stretch's target (largest rank at the stretch's start + 2) or death, 64 CRN
playouts (build/rollout --human S --stop-rank R --horizon 0). The curve C(t) = P(target) after the move played at ply t.
Writes results/review/cgroups/*.bin and cgroups.tsv (group, skill, stop_rank, n, sid:ply list).
usage: review_curve.py [--k 10]"""
import collections, json, os, struct, sys

K = int(sys.argv[sys.argv.index('--k') + 1]) if '--k' in sys.argv else 10
os.makedirs('results/review/cgroups', exist_ok=True)
groups = collections.defaultdict(list)
for line in open('results/review/stretches.tsv').read().splitlines()[1:]:
    sid = line.split('\t')[0]
    L = [json.loads(x) for x in open(f'results/review/rev2/{sid}.jsonl').read().splitlines()]
    summ, per = L[-1]['review'], L[:-1]
    if not per: continue
    r0 = max(int(c, 16) for c in per[0]['hex'])
    target = r0 + 2
    dec = summ.get('decisive_move')
    plies = set(range(1, len(per) + 1, K))
    if dec: plies |= {dec - 1, dec, dec + 1}
    for ply in sorted(p for p in plies if 1 <= p <= len(per)):
        a = per[ply - 1]
        if not a.get('moves') or a.get('played') is None: continue
        if max(int(c, 16) for c in a['hex']) >= target: break
        s = a.get('personal_odds', {}).get('human_skill')
        if s is None: continue
        groups[(round(s, 3), target)].append((sid, ply, a['hex']))
with open('results/review/cgroups.tsv', 'w') as f:
    f.write('group\tskill\tstop_rank\tn\tpositions\n')
    for g, ((s, R), ps) in enumerate(sorted(groups.items())):
        with open(f'results/review/cgroups/c{g:03d}.bin', 'wb') as fb:
            for _, _, hx in ps:
                b = 0
                for c, ch in enumerate(hx): b |= int(ch, 16) << (4 * c)
                fb.write(struct.pack('<Q', b))
        f.write(f"c{g:03d}\t{s}\t{R}\t{len(ps)}\t{','.join(f'{a}:{b}' for a, b, _ in ps)}\n")
print(len(groups), 'groups,', sum(len(v) for v in groups.values()), 'positions')
