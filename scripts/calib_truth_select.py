#!/usr/bin/env python3
"""Real human positions for the odds ground truth (engine playouts from the position to a target tile or death):
strata by largest tile and tightness (value ratio = the analysis' best move value / vbar(tile sum) of the odds model,
< RATIO = tight), balanced over players (round robin), positions whose engine board needs no lowering (largest tile
<= 32768, no duplicated tile >= 2048 ... i.e. the hex ranks equal the real ranks). Writes OUT_<group>.bin per stop rank
group and OUT.tsv (idx within its group, group, stratum, tier, player, video, ply, real sum, max, value, ratio, hex).

usage: calib_truth_select.py OUT [--model results/calib/model_v5.json] [--ratio 0.8] [--exclude FILE.bin ...]
         [--analysis results/human_ds/analysis.jsonl]
         --strata NAME:GROUP:MAXLO:MAXHI:tight|typical|any:N[,...]"""
import collections, json, math, random, struct, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from fit_calib import hats  # noqa: E402

def board_of(h):
    b = 0
    for k, c in enumerate(h):
        b |= int(c, 16) << (4 * k)
    return b

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    model, ratio_cut, excl, strata, seed = 'results/calib/model_v5.json', 0.8, [], [], 7
    analysis = 'results/human_ds/analysis.jsonl'  # cal7: --analysis CACHE (values of the engine being calibrated)
    while args:
        a = args.pop(0)
        if a == '--model': model = args.pop(0)
        elif a == '--ratio': ratio_cut = float(args.pop(0))
        elif a == '--seed': seed = int(args.pop(0))
        elif a == '--analysis': analysis = args.pop(0)
        elif a == '--exclude':
            while args and not args[0].startswith('--'): excl.append(args.pop(0))
        elif a == '--strata':
            for s in args.pop(0).split(','):
                n, g, lo, hi, kind, k = s.split(':'); strata.append((n, g, int(lo), int(hi), kind, int(k)))
    vb = np.array(json.load(open(model))['vbar'])
    seen = set()
    for p in excl:
        data = open(p, 'rb').read()
        seen.update(struct.unpack('<Q', data[i:i + 8])[0] for i in range(0, len(data), 8))
    cand = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(analysis):
        a = json.loads(line)
        if a.get('game_over') or len(a['moves']) < 2 or a.get('observed') is False:
            continue
        cells = [x for r in a['board'] for x in r]
        top = max(cells)
        if top > 32768 or board_of(a['hex']) in seen:
            continue
        ranks = [0 if x == 0 else int(math.log2(x)) for x in cells]
        if ''.join('%x' % r for r in ranks) != a['hex']:
            continue  # lowered engine board
        s = sum(cells)
        v = max(m['value'] for m in a['moves'])
        ratio = v / max(1.0, float(hats(np.array([math.log2(s)])) @ vb))
        rec = dict(tier=a.get('tier', '?'), player=a.get('player', a['video']), video=a['video'], ply=a['ply'], sum=s,
                   top=top, value=v, ratio=ratio, hex=a['hex'])
        for n, g, lo, hi, kind, k in strata:
            if lo <= top <= hi and (kind == 'any' or (kind == 'tight') == (ratio < ratio_cut)):
                cand[n][rec['player']].append(rec)
    rnd = random.Random(seed)
    groups = collections.defaultdict(list)
    used = set()
    for n, g, lo, hi, kind, k in strata:
        players = sorted(cand[n]); rnd.shuffle(players)
        for p in players: rnd.shuffle(cand[n][p])
        got, i = [], 0
        while len(got) < k and any(cand[n][p] for p in players):
            p = players[i % len(players)]; i += 1
            while cand[n][p]:
                r = cand[n][p].pop()
                if r['hex'] not in used:
                    used.add(r['hex']); got.append(r); break
        print(f"{n} ({g}): {len(got)} of {sum(len(v) for v in cand[n].values()) + len(got)} candidates, "
              f"{len(players)} players, mean ratio {np.mean([r['ratio'] for r in got]) if got else 0:.3f}")
        groups[g] += [(n, r) for r in got]
    with open(out + '.tsv', 'w') as f:
        f.write('idx\tgroup\tstratum\ttier\tplayer\tvideo\tply\tsum\tmax\tvalue\tratio\thex\n')
        for g, rs in groups.items():
            with open(f"{out}_{g}.bin", 'wb') as fb:
                for i, (n, r) in enumerate(rs):
                    fb.write(struct.pack('<Q', board_of(r['hex'])))
                    f.write(f"{i}\t{g}\t{n}\t{r['tier']}\t{r['player']}\t{r['video']}\t{r['ply']}\t{r['sum']}\t{r['top']}\t"
                            f"{r['value']:.1f}\t{r['ratio']:.4f}\t{r['hex']}\n")
            print(f"group {g}: {len(rs)} positions -> {out}_{g}.bin")

if __name__ == '__main__':
    main()
