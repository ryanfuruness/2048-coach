#!/usr/bin/env python3
"""Workstream review: full-coverage player-level screen. Every judged move with >= 2 legal moves of the NON-expert
stretches (positions below 16384 with a playout skill), all first moves, human move model at the position's playout
skill to the next milestone (largest rank + 1) or death. Writes results/review/fgroups/*.bin + fgroups.tsv
(group, skill, stop_rank, n, sid:ply list)."""
import collections, json, os, struct
os.makedirs('results/review/fgroups', exist_ok=True)
meta = {l.split('\t')[0]: l.split('\t') for l in open('results/review/stretches.tsv').read().splitlines()[1:]}
groups = collections.defaultdict(list)
for sid, m in meta.items():
    if m[1] == 'expert': continue
    for ply, line in enumerate(open(f'results/review/rev2/{sid}.jsonl').read().splitlines()[:-1], 1):
        a = json.loads(line)
        if not a.get('moves') or a.get('played') is None or len(a['moves']) < 2: continue
        s = a.get('personal_odds', {}).get('human_skill')
        if s is None: continue
        mr = max(int(c, 16) for c in a['hex'])
        groups[(round(s, 3), mr + 1)].append((sid, ply, a['hex']))
with open('results/review/fgroups.tsv', 'w') as f:
    f.write('group\tskill\tstop_rank\tn\tpositions\n')
    for g, ((s, R), ps) in enumerate(sorted(groups.items())):
        with open(f'results/review/fgroups/f{g:03d}.bin', 'wb') as fb:
            for _, _, hx in ps:
                b = 0
                for c, ch in enumerate(hx): b |= int(ch, 16) << (4 * c)
                fb.write(struct.pack('<Q', b))
        f.write(f"f{g:03d}\t{s}\t{R}\t{len(ps)}\t{','.join(f'{a}:{b}' for a, b, _ in ps)}\n")
print(len(groups), 'groups,', sum(len(v) for v in groups.values()), 'positions')
