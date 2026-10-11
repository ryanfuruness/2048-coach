#!/usr/bin/env python3
"""Workstream review: stage 2 of the player-level study (the 32-playout screen is noise-dominated: near-ties rms 0.14).
Re-measure with 256 CRN playouts (human move model at the position's skill to the next milestone): ALL flagged moves of
the non-expert stretches (key moments, warnings, hints, hard moments, your_cost >= 3%) and a uniform random sample of
N unflagged judged moves (played != reference and played == reference alike). Writes results/review/s2groups/*.bin and
s2groups.tsv; the sample design in results/review/s2_sample.tsv (sid, ply, kind = flagged|random).
usage: review_stage2.py [--n 1000] [--seed 5]"""
import collections, json, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from review_report import tsv, fnum  # noqa: E402
N = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 1000
seed = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 5
rng = random.Random(seed)
moves = [m for m in tsv('results/review/moves.tsv') if m['tier'] != 'expert' and m['judged'] == '1' and int(m['nlegal']) >= 2]
flag = lambda m: m['key'] == '1' or m['warn'] == '1' or m['hint'] == '1' or m['hard'] == '1' or (fnum(m['your_cost']) or 0) >= 0.03
F = [m for m in moves if flag(m)]
U = [m for m in moves if not flag(m)]
S = rng.sample(U, min(N, len(U)))
os.makedirs('results/review/s2groups', exist_ok=True)
skill = {}
groups = collections.defaultdict(list)
with open('results/review/s2_sample.tsv', 'w') as f:
    f.write('sid\tply\tkind\n')
    for kind, xs in (('flagged', F), ('random', S)):
        for m in xs:
            sid, ply = m['sid'], int(m['ply'])
            if sid not in skill:
                skill[sid] = [json.loads(x) for x in open(f'results/review/rev2/{sid}.jsonl').read().splitlines()[:-1]]
            a = skill[sid][ply - 1]
            s = a.get('personal_odds', {}).get('human_skill')
            if s is None: continue
            mr = max(int(c, 16) for c in a['hex'])
            groups[(round(s, 3), mr + 1)].append((sid, ply, a['hex']))
            f.write(f"{sid}\t{ply}\t{kind}\n")
with open('results/review/s2groups.tsv', 'w') as f:
    f.write('group\tskill\tstop_rank\tn\tpositions\n')
    for g, ((s, R), ps) in enumerate(sorted(groups.items())):
        with open(f'results/review/s2groups/s{g:03d}.bin', 'wb') as fb:
            for _, _, hx in ps:
                b = 0
                for c, ch in enumerate(hx): b |= int(ch, 16) << (4 * c)
                fb.write(struct.pack('<Q', b))
        f.write(f"s{g:03d}\t{s}\t{R}\t{len(ps)}\t{','.join(f'{a}:{b}' for a, b, _ in ps)}\n")
print(f"flagged {len(F)}, unflagged {len(U)} (sampled {len(S)}); {len(groups)} groups, {sum(len(v) for v in groups.values())} positions")
