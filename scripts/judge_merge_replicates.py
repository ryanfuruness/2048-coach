#!/usr/bin/env python3
"""cal7: merge replicate rollout runs of the same pool (same --moves, different --seed) into one judge TSV: per
(pos, move) the playout-weighted mean q, its standard error from the replicates' spread, n summed; other columns from
the first run. usage: judge_merge_replicates.py OUT.tsv RUN1.tsv RUN2.tsv ..."""
import collections, math, sys

def main():
    out, runs = sys.argv[1], sys.argv[2:]
    rows, qs, hdr = collections.OrderedDict(), collections.defaultdict(list), None
    for path in runs:
        with open(path) as f:
            h = f.readline().rstrip('\n').split('\t')
            hdr = hdr or h
            for line in f:
                r = dict(zip(h, line.rstrip('\n').split('\t')))
                k = (r['pos'], r['move'])
                rows.setdefault(k, r)
                qs[k].append((float(r['q']), int(r['n'])))
    with open(out, 'w') as f:
        f.write('\t'.join(hdr) + '\n')
        for k, r in rows.items():
            xs = qs[k]
            n = sum(m for _, m in xs)
            mean = sum(q * m for q, m in xs) / n
            sd = math.sqrt(sum((q - mean) ** 2 for q, _ in xs) / max(1, len(xs) - 1))
            r = dict(r, q=f"{mean:.1f}", q_se=f"{sd / math.sqrt(len(xs)):.1f}", n=str(n))
            f.write('\t'.join(r[c] for c in hdr) + '\n')
    print(f"{len(rows)} (pos, move) rows from {len(runs)} runs -> {out}")

if __name__ == '__main__':
    main()
