#!/usr/bin/env python3
"""Workstream review: the moves of the reviewed stretches (results/review/rev2/*.jsonl, per-move lines with
find_prob / error_risk / hint at the stretch's fitted skill; summary with key_moments) -> one row per judged move
(results/review/moves.tsv) and the positions to measure with rollouts (results/review/pool.bin + pool.tsv):
  K = the review's key moments (5 per stretch), R = 5 random judged moves per stretch (not key moments),
  W = moves the review would have warned before, H = hint positions, D = hard moments (error_risk >= 1% and the best
  move's find_prob < 20%: the review's definition, here with habits included).
usage: review_moments.py [--rev results/review/rev2] [--seed 11]"""
import glob, json, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard_eval import NAME_OF, ref_move  # noqa: E402

DIRS = 'URDL'


def main():
    args = sys.argv[1:]
    rev, seed = 'results/review/rev2', 11
    while args:
        a = args.pop(0)
        if a == '--rev': rev = args.pop(0)
        elif a == '--seed': seed = int(args.pop(0))
    meta = {}
    for line in open('results/review/stretches.tsv').read().splitlines()[1:]:
        f = line.split('\t'); meta[f[0]] = f
    rng = random.Random(seed)
    rows, pool = [], {}
    for path in sorted(glob.glob(f'{rev}/*.jsonl')):
        sid = os.path.basename(path)[:-6]
        L = [json.loads(x) for x in open(path).read().splitlines()]
        summ = L[-1]['review']; per = L[:-1]
        keyp = {k['ply']: k for k in summ.get('key_moments', [])}
        cand = []
        for i, a in enumerate(per):
            ply = i + 1
            if not a.get('moves') or a.get('played') is None: continue
            pl = NAME_OF.get(a['played']); r = ref_move(a)
            mv = {NAME_OF[m['move']]: m for m in a['moves']}
            if pl not in mv or r is None: continue
            m = mv[pl]
            fp = {d: mv[d].get('find_prob') for d in mv}
            top = max(max(row) for row in a['board'])
            judged = a.get('judged', True) is not False and m.get('real_loss') is not None
            row = dict(sid=sid, tier=meta[sid][1], player=meta[sid][2], stage=meta[sid][7], ply=ply, hex=a['hex'],
                       top=top, played=pl, engine=NAME_OF.get(a.get('engine_move') or '', '-'), ref=r,
                       source=a.get('source', 'search'), nlegal=len(mv), judged=int(judged),
                       real_loss=m.get('real_loss'), your_cost=m.get('your_cost'), value_loss=None,
                       warn=int(bool(m.get('warn'))), hint=int(bool(a.get('hint'))), error_risk=a.get('error_risk'),
                       fp_played=fp.get(pl), fp_ref=fp.get(r), key=int(ply in keyp))
            v = {d: mv[d]['value'] for d in mv}
            row['value_loss'] = max(0.0, v[r] - v[pl]) / max(100000.0, abs(v[r]))
            row['hard'] = int(row['error_risk'] is not None and row['error_risk'] >= 0.01 and
                              row['fp_ref'] is not None and row['fp_ref'] < 0.2)
            rows.append(row)
            if judged and len(mv) >= 2 and not row['key']: cand.append(row)
        for row in rng.sample(cand, min(5, len(cand))): row['rand'] = 1
    for row in rows:
        row.setdefault('rand', 0)
        sets = ''.join(c for c, f in (('K', row['key']), ('R', row['rand']), ('W', row['warn'] and row['judged']),
                                      ('H', row['hint']), ('D', row['hard'])) if f)
        row['sets'] = sets
        if sets and row['nlegal'] >= 2: pool[(row['sid'], row['ply'])] = row
    cols = ['sid', 'tier', 'player', 'stage', 'ply', 'hex', 'top', 'played', 'engine', 'ref', 'source', 'nlegal',
            'judged', 'real_loss', 'your_cost', 'value_loss', 'warn', 'hint', 'error_risk', 'fp_played', 'fp_ref',
            'key', 'rand', 'hard', 'sets']
    with open('results/review/moves.tsv', 'w') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows: f.write('\t'.join('' if r[c] is None else str(r[c]) for c in cols) + '\n')
    P = sorted(pool.values(), key=lambda r: (r['sid'], r['ply']))
    with open('results/review/pool.bin', 'wb') as fb, open('results/review/pool.tsv', 'w') as ft:
        ft.write('pos\tsid\tply\thex\ttop\tsets\n')
        for i, r in enumerate(P):
            b = 0
            for c, ch in enumerate(r['hex']): b |= int(ch, 16) << (4 * c)
            fb.write(struct.pack('<Q', b))
            ft.write(f"{i}\t{r['sid']}\t{r['ply']}\t{r['hex']}\t{r['top']}\t{r['sets']}\n")
    from collections import Counter
    c = Counter()
    for r in P:
        for s in r['sets']: c[s] += 1
    print(len(rows), 'moves;', len(P), 'pool positions;', dict(c))


if __name__ == '__main__':
    main()
