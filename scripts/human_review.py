#!/usr/bin/env python3
"""Batch review of human games: every decision (board + the move the player made) of the human-data pipeline's
WORK/out/<video>.decisions.jsonl files is analyzed by build/analyze (server mode), then summarized per video: agreement
with the engine, value losses, large losses (> 10% of the position's value: the size the judge study found to be real
losses), and the skill temperature (max likelihood of the played moves under exp(-relative loss / t)).

usage: human_review.py DECISIONS_DIR [--out results/human] [--preset best-notables] [--max-per-video N] [--only-observed]
The analysis lines are cached in OUT/analysis.jsonl (delete it to recompute)."""
import json, math, os, subprocess, sys, glob, collections

def tiles_of(hexboard):
    return ' '.join(str(1 << int(c, 36)) if c != '0' else '0' for c in hexboard)

def main():
    args = sys.argv[1:]
    src = args.pop(0)
    out, preset, maxper, only_obs = 'results/human', 'best-notables', 0, False
    while args:
        a = args.pop(0)
        if a == '--out': out = args.pop(0)
        elif a == '--preset': preset = args.pop(0)
        elif a == '--max-per-video': maxper = int(args.pop(0))
        elif a == '--only-observed': only_obs = True
    os.makedirs(out, exist_ok=True)
    recs = []
    import gzip
    if src.endswith('.jsonl.gz') or src.endswith('.jsonl'):
        files = [src]  # the curated dataset (dataset_build/positions.jsonl.gz): player and tier per record
    else:
        files = sorted(glob.glob(os.path.join(src, '*.decisions.jsonl')))
    for f in files:
        n = 0
        opener = gzip.open if f.endswith('.gz') else open
        for line in opener(f, 'rt'):
            r = json.loads(line)
            if only_obs and not r.get('observed'):
                continue
            if r.get('undone'):
                continue
            recs.append(r)
            n += 1
            if maxper and n >= maxper:
                break
    cache = os.path.join(out, 'analysis.jsonl')
    if not os.path.exists(cache):
        inp = ''.join(f"played={r['move']} | {tiles_of(r['board'])}\n" for r in recs)
        env = dict(os.environ, MALLOC_ARENA_MAX='2')
        res = subprocess.run(['bash', '-c', f'ulimit -s unlimited; ./build/analyze --preset {preset} --stdin'],
                             input=inp, capture_output=True, text=True, env=env)
        lines = res.stdout.strip().split('\n')
        if len(lines) != len(recs):
            sys.exit(f"analysis returned {len(lines)} lines for {len(recs)} decisions")
        with open(cache, 'w') as f:
            for r, l in zip(recs, lines):
                a = json.loads(l)
                a['video'], a['ply'], a['segment'] = r['video'], r['ply'], r.get('segment')
                a['observed'] = bool(r.get('observed'))
                for k in ('think_s', 'maybe_two_moves', 'rest_ambiguous', 'gap', 'player', 'tier'):
                    if k in r: a[k] = r[k]
                f.write(json.dumps(a) + '\n')
    # streaming: one line at a time, only small per-video tuples are kept (the cache is several hundred MB)
    per = collections.defaultdict(list)
    skipped = collections.Counter()
    rec_iter = iter(recs)
    for line in open(cache):
        a = json.loads(line)
        r = next(rec_iter, None)
        if r is not None and 'observed' not in a:  # older caches: attach the record flags (same order)
            a['observed'] = bool(r.get('observed'))
            for k in ('maybe_two_moves', 'rest_ambiguous'):
                if r.get(k): a[k] = True
        if a.get('game_over') or 'played' not in a or len(a['moves']) < 1:
            continue
        if not a.get('observed', True) or a.get('maybe_two_moves') or a.get('rest_ambiguous'):
            skipped['inferred or ambiguous'] += 1
            continue
        best = max(m['value'] for m in a['moves'])
        rel = {m['move']: (best - m['value']) / max(100000.0, abs(best)) for m in a['moves']}
        top = max(max(row) for row in a['board'])
        per[a['video']].append((rel, a['played'], a['engine_move'], top))
    print('skipped:', dict(skipped))
    quality = {}
    for f in glob.glob(os.path.join(src, '*.summary.json')):
        q = json.load(open(f))
        quality[q['vid']] = q
    summary = []
    for vid, xs in per.items():
        ch = []
        match = big = 0
        loss = 0.0
        top = 0
        for rel, p, eng, tp in xs:
            if p not in rel:
                continue
            match += p == eng
            loss += rel[p]
            big += rel[p] > 0.10
            top = max(top, tp)
            if len(rel) >= 2:
                ch.append((rel, p, tp))
        n = len(ch)
        if n == 0:
            continue
        def fit(cs):
            bt, bll = None, -1e300
            t = 0.0003
            while t <= 1.0 and cs:
                ll = sum(-r[p] / t - math.log(sum(math.exp(-v / t) for v in r.values())) for r, p in cs)
                if ll > bll:
                    bll, bt = ll, t
                t *= 1.1
            return bt
        bt = fit([(r, p) for r, p, _ in ch])
        early = [(r, p) for r, p, tp in ch if tp <= 2048]
        bt_early = fit(early) if len(early) >= 50 else None
        q = quality.get(vid, {})
        summary.append(dict(video=vid, decisions=len(xs), max_tile=top, match=round(match / len(xs), 4),
                            mean_rel_loss=round(loss / len(xs), 5), big_losses_per_1000=round(1000 * big / len(xs), 2),
                            skill_t=round(bt, 5), skill_t_early=round(bt_early, 5) if bt_early else None,
                            early_n=len(early), explained=q.get('explained_share'), gaps=q.get('gap_share'),
                            segments=q.get('segments')))
    summary.sort(key=lambda d: d['skill_t'])
    json.dump(summary, open(os.path.join(out, 'summary.json'), 'w'), indent=1)
    print(f"{sum(len(x) for x in per.values())} decisions summarized, {len(summary)} videos")
    print(f"{'video':14s} {'moves':>6s} {'max':>7s} {'match':>6s} {'mean loss':>9s} {'>10%/1000':>9s} {'skill t':>8s}"
          f" {'t<=2048':>8s} {'(n)':>5s} {'explained':>9s} {'gaps':>5s} {'segs':>5s}")
    for d in summary:
        print(f"{d['video']:14s} {d['decisions']:6d} {d['max_tile']:7d} {100 * d['match']:5.1f}% "
              f"{100 * d['mean_rel_loss']:8.3f}% {d['big_losses_per_1000']:9.2f} {d['skill_t']:8.4f}"
              f" {d['skill_t_early'] if d['skill_t_early'] else '-':>8} {d['early_n']:5d}"
              f" {d['explained'] if d['explained'] is not None else '-':>9} {d['gaps'] if d['gaps'] is not None else '-':>5}"
              f" {d['segments'] if d['segments'] is not None else '-':>5}")

if __name__ == '__main__':
    main()
