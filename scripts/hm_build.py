#!/usr/bin/env python3
"""Human move model (workstream hm), step 1: the fitting data set.
Reads the curated human positions analysed by build/analyze (results/human_ds/analysis.jsonl), keeps the clean decisions
(the filters of human_tiers.py), runs build_hm/hm_tool for the 1-ply values (soft_move's scale) and concept features of
every afterstate, and writes results/hm/data.npz:
  per position i: player, tier, video, ply, prev1/prev2 (the player's previous two moves, -1 unknown), played (0-3 =
  U R D L), real max tile and tile sum, max tile cell (real board), think time;
  per (i, d): legal, reward, q (1-ply value), loss1 (relative 1-ply loss, soft_move's scale (best - q) / max(1, |best|)),
  q2 / loss2 (2-ply: expectation over the spawn of the best reply's 1-ply value; same scale), death (share of spawns
  with no reply),
  losss (relative search loss, analyze's scale), concept features of the afterstate and of the position (d = -1).
usage: [HM_DIR=results/hm] [HM_TOOL=./build_hm/hm_tool] hm_build.py [analysis.jsonl] [out.npz]"""
import json, math, os, subprocess, sys
import numpy as np

DIRS = {'up': 0, 'right': 1, 'down': 2, 'left': 3}
FEATS = ['max_rank', 'corner', 'chain_len', 'chain_ranks', 'empty', 'merges', 'trapped', 'big_off_edge', 'corner_dist',
         'exposed', 'moved']

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'results/human_ds/analysis.jsonl'
    out = sys.argv[2] if len(sys.argv) > 2 else 'results/hm/data.npz'
    os.makedirs('results/hm', exist_ok=True)
    recs = []
    with open(src) as f:
        for line in f:
            a = json.loads(line)
            if a.get('game_over') or a.get('played') not in DIRS or len(a['moves']) < 2: continue
            if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'):
                continue
            vals = {DIRS[m['move']]: m['value'] for m in a['moves']}
            if DIRS[a['played']] not in vals: continue
            b = a['board']
            tiles = [b[r][c] for r in range(4) for c in range(4)]
            mx = max(tiles)
            # the cell of the biggest tile nearest a corner (ties: first)
            cells = [c for c in range(16) if tiles[c] == mx]
            def cdist(c):
                r, k = divmod(c, 4)
                return min(r, 3 - r) + min(k, 3 - k)
            mcell_real = min(cells, key=cdist)
            # direction classes are computed on the engine's board (as the C++ policy sees it): biggest tile, nearest
            # corner (ties: first cell), row/column sums from the hex ranks
            hr = [int(ch, 16) for ch in a['hex']]
            hmx = max(hr)
            mcell = min([c for c in range(16) if hr[c] == hmx], key=cdist)
            ref = vals.get(DIRS.get(a.get('engine_move'), -1), max(vals.values()))
            losss = [float('nan')] * 4
            for d, v in vals.items(): losss[d] = max(0.0, ref - v) / max(100000.0, abs(ref))
            recs.append(dict(id=f"{a['video']}:{a['segment']}:{a['ply']}", video=a['video'], seg=a['segment'],
                             ply=a['ply'], player=a.get('player', a['video']), tier=a.get('tier', '?'),
                             played=DIRS[a['played']], hex=a['hex'], mx=mx, sum=sum(tiles), mcell=mcell,
                             think=a.get('think_s', float('nan')), gap=a.get('gap', 0) or 0, losss=losss,
                             ranks=hr))
    print(len(recs), 'clean decisions', file=sys.stderr)
    # previous moves of the same player in the same segment (consecutive plies only)
    by = {(r['video'], r['seg'], r['ply']): r['played'] for r in recs}
    for r in recs:
        r['prev1'] = by.get((r['video'], r['seg'], r['ply'] - 1), -1)
        r['prev2'] = by.get((r['video'], r['seg'], r['ply'] - 2), -1) if r['prev1'] >= 0 else -1
    work = os.environ.get('HM_DIR', 'results/hm')  # work files (hm2: results/hm2 with HM_TOOL=./build_hm2/hm_tool)
    tool_in = f'{work}/positions.tsv'
    with open(tool_in, 'w') as f:
        f.write('id\thex\n')
        for r in recs: f.write(f"{r['id']}\t{r['hex']}\n")
    feat_path = f'{work}/feat.tsv'
    if not os.path.exists(feat_path) or os.path.getmtime(feat_path) < os.path.getmtime(tool_in):
        with open(tool_in) as fi, open(feat_path, 'w') as fo:
            subprocess.run([os.environ.get('HM_TOOL', './build_hm/hm_tool'), '--preset', 'best-notables'], stdin=fi,
                           stdout=fo, check=True)
    idx = {r['id']: i for i, r in enumerate(recs)}
    n = len(recs)
    q = np.full((n, 4), np.nan); rew = np.zeros((n, 4)); F = np.full((n, 5, len(FEATS)), np.nan)
    q2 = np.full((n, 4), np.nan); death = np.full((n, 4), np.nan)
    with open(feat_path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            p = line.rstrip('\n').split('\t')
            i = idx.get(p[0])
            if i is None: continue
            d = int(p[1])
            F[i, d + 1] = [float(x) for x in p[4:4 + len(FEATS)]]
            if d >= 0:
                q[i, d] = float(p[3]); rew[i, d] = float(p[2])
                q2[i, d] = float(p[4 + len(FEATS)]); death[i, d] = float(p[5 + len(FEATS)])
    legal = ~np.isnan(q)
    best = np.nanmax(q, axis=1)
    loss1 = (best[:, None] - q) / np.maximum(1.0, np.abs(best))[:, None]
    best2 = np.nanmax(q2, axis=1)
    loss2 = (best2[:, None] - q2) / np.maximum(1.0, np.abs(best2))[:, None]
    losss = np.array([r['losss'] for r in recs])
    players = sorted(set(r['player'] for r in recs))
    pid = {p: k for k, p in enumerate(players)}
    tiers = ['novice', 'intermediate', 'strong', 'expert']
    np.savez_compressed(out, loss1=loss1, loss2=loss2, death=death, q2=q2, losss=losss, legal=legal, q=q, reward=rew, F=F, feats=np.array(FEATS),
                        played=np.array([r['played'] for r in recs]), prev1=np.array([r['prev1'] for r in recs]),
                        prev2=np.array([r['prev2'] for r in recs]), mx=np.array([r['mx'] for r in recs]),
                        tsum=np.array([r['sum'] for r in recs]), mcell=np.array([r['mcell'] for r in recs]),
                        ranks=np.array([r['ranks'] for r in recs], dtype=np.int8),
                        think=np.array([r['think'] for r in recs], dtype=float),
                        player=np.array([pid[r['player']] for r in recs]), players=np.array(players),
                        tier=np.array([tiers.index(r['tier']) if r['tier'] in tiers else -1 for r in recs]),
                        video=np.array([r['video'] for r in recs]), ply=np.array([r['ply'] for r in recs]),
                        seg=np.array([r['seg'] for r in recs]), ids=np.array([r['id'] for r in recs]))
    # consistency: the played move must be legal in the tool's view
    bad = (~legal[np.arange(n), [r['played'] for r in recs]]).sum()
    print(f"saved {out}: {n} positions, {len(players)} players; played move illegal in the tool's board: {bad}",
          file=sys.stderr)

if __name__ == '__main__':
    main()
