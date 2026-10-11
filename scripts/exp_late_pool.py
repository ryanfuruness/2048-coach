#!/usr/bin/env python3
"""Expert start pools for late-network training (workstream late, 2026-10-06). From the curated human positions
(results/human_ds/analysis.jsonl: 'hex' = the engine's search board, 'tier'), the positions with a real tile >= 16384 of
the given tiers are mapped to the board the engine actually evaluates at the root: downgrade_view(b, 15, 5) (search.h;
a 32768-phase board seen as a 16384-phase one). Each view goes to the pool of the network stage that evaluates it
(view tile sum: stage B [24576, 28672), second half [28672, 36864)); others (< 24576: the early-game network through
the leaf view; >= 36864) are counted only.
usage: exp_late_pool.py OUT_PREFIX [--tiers expert,strong]   -> OUT_PREFIX_b.bin, OUT_PREFIX_sh.bin (uint64 boards)"""
import json, struct, sys, collections


def downgrade_view(r, top=15, min_gap=5):
    while True:
        mx = max(r)
        if mx < top:
            return r
        present = set(r)
        gap = next((k for k in range(mx - 1, min_gap - 1, -1) if k not in present), -1)
        if gap < 0:
            return r
        r = [v - 1 if v > gap else v for v in r]


def main():
    out = sys.argv[1]
    tiers = {'expert'}
    if '--tiers' in sys.argv:
        tiers = set(sys.argv[sys.argv.index('--tiers') + 1].split(','))
    pools = collections.defaultdict(list)
    seen = set()
    cnt = collections.Counter()
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        if a.get('tier') not in tiers or a.get('game_over'):
            continue
        if max(max(row) for row in a['board']) < 16384:
            continue
        r = [int(c, 16) for c in a['hex']]
        v = downgrade_view(r)
        s = sum(1 << x for x in v if x)
        key = 'b' if 24576 <= s < 28672 else 'sh' if 28672 <= s < 36864 else 'lo' if s < 24576 else 'hi'
        cnt[key] += 1
        b = sum(x << (4 * i) for i, x in enumerate(v))
        if key in ('b', 'sh') and b not in seen:
            seen.add(b)
            pools[key].append(b)
    for k, bs in pools.items():
        with open(f'{out}_{k}.bin', 'wb') as f:
            for b in bs:
                f.write(struct.pack('<Q', b))
    print(f"positions by view stage: {dict(cnt)}; unique boards written: " +
          ", ".join(f"{k} {len(v)} -> {out}_{k}.bin" for k, v in pools.items()))


if __name__ == '__main__':
    main()
