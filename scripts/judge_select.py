#!/usr/bin/env python3
"""Select real human positions (curated set, analysed by human_review.py) for rollout judges, balanced over players
(round robin over the players of each stratum: no channel dominates, e.g. d4Nf6Bg5 = 23% of the set), excluding
positions already judged. Writes OUT.bin (pool for build/rollout: the engine's search boards) and OUT.tsv (idx,
stratum, tier, player, video, ply, real max tile, hex, played move, engine move, the analysis' relative value loss of
the played move, flags).

usage: judge_select.py OUT [--analysis results/human_ds/analysis.jsonl] [--exclude FILE.bin ...] [--seed S]
         (--strata NAME:LO:HI:N[,...] | --claims NAME:LO_TILE:CLAIM_LO:CLAIM_HI:N[,...])
  --strata   random positions whose real largest tile is in [LO, HI] (all moves get judged)
  --claims   decisions whose played move the analysis rates CLAIM_LO <= relative loss < CLAIM_HI below the engine's
             move, in positions with a real tile >= LO_TILE (disputes: claims > 10%); only clean decisions (observed,
             not undone, not ambiguous)"""
import collections, json, random, struct, sys

def rel_claim(a):
    vals = {m['move']: m['value'] for m in a['moves']}
    if a.get('played') not in vals or a.get('engine_move') not in vals:
        return None
    best = vals[a['engine_move']]
    return max(0.0, best - vals[a['played']]) / max(100000.0, abs(best))

def board_of(h):
    b = 0
    for k, c in enumerate(h):
        b |= int(c, 16) << (4 * k)
    return b

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    path, excl, seed, strata, claims = 'results/human_ds/analysis.jsonl', [], 23, [], []
    while args:
        a = args.pop(0)
        if a == '--analysis': path = args.pop(0)
        elif a == '--exclude':
            while args and not args[0].startswith('--'): excl.append(args.pop(0))
        elif a == '--seed': seed = int(args.pop(0))
        elif a == '--strata':
            for s in args.pop(0).split(','):
                n, lo, hi, k = s.split(':'); strata.append((n, float(lo), float(hi), int(k)))
        elif a == '--claims':
            for s in args.pop(0).split(','):
                n, lt, clo, chi, k = s.split(':'); claims.append((n, float(lt), float(clo), float(chi), int(k)))
    seen = set()
    for p in excl:
        data = open(p, 'rb').read()
        for i in range(0, len(data), 8):
            seen.add(struct.unpack('<Q', data[i:i + 8])[0])
    cand = collections.defaultdict(lambda: collections.defaultdict(list))  # stratum -> player -> records
    for line in open(path):
        a = json.loads(line)
        if a.get('game_over') or len(a['moves']) < 2 or a.get('observed') is False:
            continue
        if board_of(a['hex']) in seen:
            continue
        top = max(max(r) for r in a['board'])
        c = rel_claim(a)
        clean = not (a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'))
        rec = dict(tier=a.get('tier', '?'), player=a.get('player', a['video']), video=a['video'], ply=a['ply'],
                   top=top, hex=a['hex'], played=a.get('played', '-'), engine=a.get('engine_move', '-'),
                   claim=c if c is not None else -1, clean=int(clean))
        for n, lo, hi, _ in strata:
            if lo <= top <= hi:
                cand[n][rec['player']].append(rec)
        for n, lt, clo, chi, _ in claims:
            if top >= lt and c is not None and clean and clo <= c < chi:
                cand[n][rec['player']].append(rec)
    rnd = random.Random(seed)
    picked, used = [], set()
    for n, *_, k in [(s[0], s[3]) for s in strata] + [(c[0], c[4]) for c in claims]:
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
        print(f"{n}: {len(got)} picked of {tot} candidates, {len(players)} players; tiers "
              f"{dict(collections.Counter(r['tier'] for r in got))}")
        picked += [(n, r) for r in got]
    with open(out + '.bin', 'wb') as f:
        for _, r in picked:
            f.write(struct.pack('<Q', board_of(r['hex'])))
    with open(out + '.tsv', 'w') as f:
        f.write('idx\tstratum\ttier\tplayer\tvideo\tply\ttop\thex\tplayed\tengine\tclaim\tclean\n')
        for i, (n, r) in enumerate(picked):
            f.write(f"{i}\t{n}\t{r['tier']}\t{r['player']}\t{r['video']}\t{r['ply']}\t{r['top']}\t{r['hex']}\t"
                    f"{r['played']}\t{r['engine']}\t{r['claim']:.5f}\t{r['clean']}\n")
    print(f"{len(picked)} positions -> {out}.bin / .tsv")

if __name__ == '__main__':
    main()
