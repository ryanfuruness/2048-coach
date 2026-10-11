#!/usr/bin/env python3
"""cal7: an unbiased sample of top-stage human decisions (real largest tile >= 16384, block formation excluded, clean
decisions) stratified by the CURRENT engine's claim for the played move (relative value loss vs the engine move, from
an analysis cache made with that engine), round robin over players. For the low-end measurement of lossmap_top /
lossmap_played_expert with many paired playouts (fixed reference = the engine move, common random numbers).

usage: judge_lowend_select.py OUT [--analysis results/human_ds_v6b/analysis.jsonl] [--seed S]
         [--strata NAME:CLAIM_LO:CLAIM_HI:N,...]   (default: ctl 0-0.0005 40, a 0.001-0.003 30, b 0.003-0.01 40,
                                                     c 0.01-0.03 40, d 0.03-0.1 30, e 0.1-1 20)
writes OUT.bin (engine boards) and OUT.tsv (idx, stratum, tier, player, video, ply, top, hex, played, engine, claim)."""
import collections, json, random, struct, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from block_detect import block_position  # noqa: E402

def board_of(h):
    b = 0
    for k, c in enumerate(h):
        b |= int(c, 16) << (4 * k)
    return b

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    path, seed = 'results/human_ds_v6b/analysis.jsonl', 7
    strata = [('ctl', 0, 0.0005, 40), ('a', 0.001, 0.003, 30), ('b', 0.003, 0.01, 40), ('c', 0.01, 0.03, 40),
              ('d', 0.03, 0.1, 30), ('e', 0.1, 1.0, 20)]
    while args:
        a = args.pop(0)
        if a == '--analysis': path = args.pop(0)
        elif a == '--seed': seed = int(args.pop(0))
        elif a == '--strata':
            strata = []
            for s in args.pop(0).split(','):
                n, lo, hi, k = s.split(':'); strata.append((n, float(lo), float(hi), int(k)))
    cand = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(path):
        a = json.loads(line)
        if a.get('game_over') or len(a['moves']) < 2 or a.get('observed') is False:
            continue
        if a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'):
            continue
        top = max(max(r) for r in a['board'])
        if top < 16384:
            continue
        if block_position([x for r in a['board'] for x in r]):
            continue
        vals = {m['move']: m['value'] for m in a['moves']}
        if a.get('played') not in vals or a.get('engine_move') not in vals:
            continue
        best = vals[a['engine_move']]
        c = max(0.0, best - vals[a['played']]) / max(100000.0, abs(best))
        rec = dict(tier=a.get('tier', '?'), player=a.get('player', a['video']), video=a['video'], ply=a['ply'],
                   top=top, hex=a['hex'], played=a['played'], engine=a['engine_move'], claim=c)
        for n, lo, hi, _ in strata:
            if lo <= c < hi:
                cand[n][rec['player']].append(rec)
    rnd = random.Random(seed)
    picked, used = [], set()
    for n, lo, hi, k in strata:
        players = sorted(cand[n])
        for p in players:
            rnd.shuffle(cand[n][p])
        rnd.shuffle(players)
        got, i = [], 0
        while len(got) < k and any(cand[n][p] for p in players):
            p = players[i % len(players)]; i += 1
            while cand[n][p]:
                r = cand[n][p].pop()
                if r['hex'] not in used:
                    used.add(r['hex']); got.append(r); break
        tot = sum(len(v) for v in cand[n].values()) + len(got)
        print(f"{n} [{lo}, {hi}): {len(got)} picked of {tot} candidates, {len(players)} players; "
              f"tops {dict(collections.Counter(r['top'] for r in got))}")
        picked += [(n, r) for r in got]
    with open(out + '.bin', 'wb') as f:
        for _, r in picked:
            f.write(struct.pack('<Q', board_of(r['hex'])))
    with open(out + '.tsv', 'w') as f:
        f.write('idx\tstratum\ttier\tplayer\tvideo\tply\ttop\thex\tplayed\tengine\tclaim\n')
        for i, (n, r) in enumerate(picked):
            f.write(f"{i}\t{n}\t{r['tier']}\t{r['player']}\t{r['video']}\t{r['ply']}\t{r['top']}\t{r['hex']}\t"
                    f"{r['played']}\t{r['engine']}\t{r['claim']:.5f}\n")
    print(f"{len(picked)} positions -> {out}.bin / .tsv")

if __name__ == '__main__':
    main()
