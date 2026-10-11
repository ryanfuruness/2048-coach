#!/usr/bin/env python3
"""Workstream review: split results/review/pool.tsv into rollout groups for the player-level truth (human move model
continuing at the stretch's playout skill = personal_odds.human_skill of the position's review line, playouts until the
next milestone = the position's largest rank + 1 in engine encoding, or death). Writes results/review/pgroups/G.bin
and results/review/pgroups.tsv (group, skill, stop_rank, n, first pool index ...)."""
import json, os, struct, collections
os.makedirs('results/review/pgroups', exist_ok=True)
pool = [l.split('\t') for l in open('results/review/pool.tsv').read().splitlines()[1:]]
cache = {}
groups = collections.defaultdict(list)
for pos, sid, ply, hx, top, sets in pool:
    if sid not in cache:
        cache[sid] = [json.loads(x) for x in open(f'results/review/rev2/{sid}.jsonl').read().splitlines()[:-1]]
    a = cache[sid][int(ply) - 1]
    s = a.get('personal_odds', {}).get('human_skill')
    if s is None: continue
    mr = max(int(c, 16) for c in hx)
    groups[(round(s, 3), mr + 1)].append((int(pos), hx))
with open('results/review/pgroups.tsv', 'w') as f:
    f.write('group\tskill\tstop_rank\tn\tpositions\n')
    for g, ((s, R), ps) in enumerate(sorted(groups.items())):
        with open(f'results/review/pgroups/g{g:03d}.bin', 'wb') as fb:
            for _, hx in ps:
                b = 0
                for c, ch in enumerate(hx): b |= int(ch, 16) << (4 * c)
                fb.write(struct.pack('<Q', b))
        f.write(f"g{g:03d}\t{s}\t{R}\t{len(ps)}\t{','.join(str(p) for p, _ in ps)}\n")
print(len(groups), 'groups,', sum(len(v) for v in groups.values()), 'positions')
