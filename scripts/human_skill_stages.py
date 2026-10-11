#!/usr/bin/env python3
"""Skill by stage: the softmax temperature t of each video's players, fitted separately on positions of each stage
(largest tile <= 512, 1024-2048, 4096-8192, >= 16384), so that players are compared on the same kind of positions
(late positions have larger value gaps between moves, which confounds a single per-video t).
usage: human_skill_stages.py [results/human/analysis.jsonl] [--min N]"""
import json, math, sys, collections

STAGES = [(0, 512, '<=512'), (1024, 2048, '1k-2k'), (4096, 8192, '4k-8k'), (16384, 1 << 20, '>=16k')]

def fit(cs):
    bt, bll = None, -1e300
    t = 0.0003
    while t <= 1.0:
        ll = sum(-r[p] / t - math.log(sum(math.exp(-v / t) for v in r.values())) for r, p in cs)
        if ll > bll:
            bll, bt = ll, t
        t *= 1.1
    return bt

def main():
    args = sys.argv[1:]
    path = args[0] if args and not args[0].startswith('--') else 'results/human/analysis.jsonl'
    mn = int(args[args.index('--min') + 1]) if '--min' in args else 100
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    top = collections.Counter()
    for line in open(path):
        a = json.loads(line)
        if a.get('game_over') or 'played' not in a or len(a['moves']) < 2:
            continue
        if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous'):
            continue
        best = max(m['value'] for m in a['moves'])
        rel = {m['move']: (best - m['value']) / max(100000.0, abs(best)) for m in a['moves']}
        if a['played'] not in rel:
            continue
        mx = max(max(r) for r in a['board'])
        top[a['video']] = max(top[a['video']], mx)
        for lo, hi, name in STAGES:
            if lo <= mx <= hi:
                per[a['video']][name].append((rel, a['played']))
    print(f"{'video':14s} {'max':>7s} " + ' '.join(f"{n:>13s}" for _, _, n in STAGES))
    rows = []
    for vid, st in per.items():
        cells = []
        for _, _, name in STAGES:
            cs = st.get(name, [])
            cells.append(f"{fit(cs):.4f} ({len(cs):5d})" if len(cs) >= mn else f"{'-':>13s}")
        rows.append((top[vid], vid, cells))
    for mx, vid, cells in sorted(rows):
        print(f"{vid:14s} {mx:7d} " + ' '.join(f"{c:>13s}" for c in cells))
    # population reference: per stage, the median t of players grouped by the largest tile their video reached
    ref = {}
    print("\nmedian t per stage by the players' final tile (n videos):")
    for _, _, name in STAGES:
        groups = collections.defaultdict(list)
        for vid, st in per.items():
            cs = st.get(name, [])
            if len(cs) >= mn:
                groups[top[vid]].append(fit(cs))
        ref[name] = {str(k): sorted(v)[len(v) // 2] for k, v in groups.items() if len(v) >= 2}
        print(f"  {name:6s}: " + '  '.join(f"{k}: {sorted(v)[len(v) // 2]:.4f} ({len(v)})" for k, v in sorted(groups.items())))
    json.dump(ref, open('results/human/skill_reference.json', 'w'), indent=1)

if __name__ == '__main__':
    main()
