#!/usr/bin/env python3
"""Workstream late2: early/mid-game judgment metric for engine candidates on unselected real positions whose every legal
move was judged by rollouts (results/judge/human300_h1000.tsv + results/cal6/j1200/judge1200_*.tsv, H=1000).
Like exp_late_judge.py (same claim definition: relative value loss vs the candidate's reference move, max(|ref|,
100k) floor; rollout loss vs the same reference, scaled by the position's best rollout value), grouped by the largest
tile: <=512, 1024, 2048-8192, all. Extra: a binned calibration of claims vs rollout losses.
  exp_late2_judge.py prep OUT.txt [--max-max 8192]          boards + OUT.txt.idx
  exp_late2_judge.py report IDX CLAIMS.jsonl ...
"""
import json, math, sys, collections, glob
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from exp_late_claims import pearson, ranks, NAME  # noqa: E402

FILES = ['results/judge/human300_h1000.tsv'] + sorted(glob.glob('results/cal6/j1200/judge1200_*.tsv'))


def load(files, max_max):
    pos = collections.OrderedDict()
    for fi, path in enumerate(files):
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                if r.get('pos') == 'pos' or int(r['max']) > max_max: continue
                k = (fi, int(r['pos']))
                p = pos.setdefault(k, dict(board=r['board'], max=int(r['max']), eng=r['engine_move'], q={}))
                p['q'][r['move']] = (float(r['q']), float(r['q_se']))
    return pos


def group(mx):
    return '<=512' if mx <= 512 else '1024' if mx == 1024 else '2048-8192'


def main():
    args = sys.argv[1:]
    if args[0] == 'prep':
        mm = int(args[args.index('--max-max') + 1]) if '--max-max' in args else 8192
        pos = load(FILES, mm)
        with open(args[1], 'w') as f, open(args[1] + '.idx', 'w') as g:
            g.write(','.join(FILES) + '\n')
            for k, p in pos.items():
                f.write(p['board'] + '\n')
                g.write(f"{k[0]}\t{k[1]}\n")
        return
    lines = open(args[1]).read().splitlines()
    files, idx = lines[0].split(','), [tuple(int(x) for x in l.split()) for l in lines[1:]]
    pos = load(files, 1 << 20)
    print(f"{'candidate':18s} {'group':>9s} {'pos':>5s} {'moves':>6s} {'rho':>6s} {'>3%':>5s} {'>3%F':>5s} {'>10%':>5s} {'>10%F':>5s}"
          f" {'move dq':>13s}   calibration: claim bin -> mean rollout loss (n)")
    for path in [a for a in args[2:] if a.endswith('.jsonl')]:
        name = path.rsplit('/', 1)[-1].replace('early_', '').replace('.jsonl', '')
        acc = collections.defaultdict(lambda: dict(c=[], t=[], n=0, b3=0, f3=0, b10=0, f10=0, dq=[], bins=collections.defaultdict(list)))
        for k, line in zip(idx, open(path)):
            a = json.loads(line)
            p = pos[k]
            if 'moves' not in a or len(a['moves']) < 2: continue
            vals = {NAME[m['move']]: m['value'] for m in a['moves']}
            eng = NAME.get(a.get('engine_move') or '', None)
            refm = eng if (eng is not None and a.get('source', 'search') != 'search') else max(vals, key=lambda m: vals[m])
            ref = vals[refm]
            if refm not in p['q']: continue
            scale = max(1.0, abs(max(x[0] for x in p['q'].values())))
            for g in ('all', group(p['max'])):
                A = acc[g]
                A['n'] += 1
                for m in vals:
                    if m == refm or m not in p['q']: continue
                    c = max(0.0, ref - vals[m]) / max(100000.0, abs(ref))
                    t = (p['q'][refm][0] - p['q'][m][0]) / scale
                    se = math.hypot(p['q'][refm][1], p['q'][m][1]) / scale
                    A['c'].append(c), A['t'].append(t)
                    if c > 0.03: A['b3'] += 1; A['f3'] += t < 2 * se
                    if c > 0.10: A['b10'] += 1; A['f10'] += t < 2 * se
                    b = 0 if c < 0.01 else 1 if c < 0.03 else 2 if c < 0.10 else 3 if c < 0.30 else 4
                    A['bins'][b].append(t)
                if eng in p['q'] and p['eng'] in p['q']:
                    A['dq'].append((p['q'][eng][0] - p['q'][p['eng']][0]) / scale)
        for g in ('<=512', '1024', '2048-8192', 'all'):
            A = acc[g]
            if not A['n']: continue
            dq = A['dq']; mq = sum(dq) / max(1, len(dq))
            sq = math.sqrt(sum((x - mq) ** 2 for x in dq) / max(1, len(dq) - 1) / max(1, len(dq)))
            cal = '  '.join(f"{['<1', '1-3', '3-10', '10-30', '30+'][b]}%: {100 * sum(v) / len(v):5.1f} ({len(v)})"
                            for b, v in sorted(A['bins'].items()))
            print(f"{name:18s} {g:>9s} {A['n']:5d} {len(A['c']):6d} {pearson(ranks(A['c']), ranks(A['t'])):6.3f} {A['b3']:5d}"
                  f" {A['f3']:5d} {A['b10']:5d} {A['f10']:5d} {100 * mq:+6.2f}+-{100 * sq:4.2f}%   {cal}")
    print("rho: Spearman claim vs rollout loss (every move != the candidate's reference); >3% / >10%: claims above; F: of"
          "\nthose, rollout loss < 2 se (not confirmed); move dq: rollout value of the candidate's move minus the judged"
          "\nengine's (best_v5) move; calibration: mean rollout loss (%) per claim bin.")


if __name__ == '__main__':
    main()
