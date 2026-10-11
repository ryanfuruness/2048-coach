#!/usr/bin/env python3
"""Select human decisions where the engine claims a large loss (relative value loss above --min-loss) for a rollout
judge: are these real mistakes of the player, or positions the engine misjudges (e.g. an expert's formation)? Also a
control sample of decisions where the player matched the engine. Writes OUT.bin (pool for build/rollout, the engine's
search boards) and OUT.tsv (index, video, ply, played move, engine move, claimed relative loss, max tile, group).

usage: human_disputes.py OUT [--analysis results/human/analysis.jsonl] [--min-loss 0.10] [--min-tile 0] [--max N]
       [--control N]"""
import json, random, struct, sys

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    path, min_loss, min_tile, mx, control = 'results/human/analysis.jsonl', 0.10, 0, 200, 100
    while args:
        a = args.pop(0)
        if a == '--analysis': path = args.pop(0)
        elif a == '--min-loss': min_loss = float(args.pop(0))
        elif a == '--min-tile': min_tile = int(args.pop(0))
        elif a == '--max': mx = int(args.pop(0))
        elif a == '--control': control = int(args.pop(0))
    disputes, agree = [], []
    for line in open(path):
        a = json.loads(line)
        if a.get('game_over') or 'played' not in a or len(a['moves']) < 2:
            continue
        if a.get('observed') is False or a.get('maybe_two_moves') or a.get('rest_ambiguous'):
            continue
        top = max(max(r) for r in a['board'])
        if top < min_tile:
            continue
        vals = {m['move']: m['value'] for m in a['moves']}
        if a['played'] not in vals or a['engine_move'] not in vals:
            continue
        # the claim is relative to the engine's own move (the cache predates the corner-lock-aware reference)
        best = vals[a['engine_move']]
        rel = {k: max(0.0, best - v) / max(100000.0, abs(best)) for k, v in vals.items()}
        rec = (a['hex'], a['video'], a['ply'], a['played'], a['engine_move'], rel[a['played']], top)
        if rel[a['played']] > min_loss:
            disputes.append(rec)
        elif a['played'] == a['engine_move']:
            agree.append(rec)
    random.seed(7)
    if len(disputes) > mx:
        disputes = random.sample(disputes, mx)
    agree = random.sample(agree, min(control, len(agree)))
    with open(out + '.bin', 'wb') as fb, open(out + '.tsv', 'w') as ft:
        ft.write('idx\tvideo\tply\tplayed\tengine\tclaimed_loss\tmax\tgroup\n')
        for i, (rec, grp) in enumerate([(r, 'dispute') for r in disputes] + [(r, 'control') for r in agree]):
            h = rec[0]
            b = 0
            for k, c in enumerate(h):
                b |= int(c, 16) << (4 * k)
            fb.write(struct.pack('<Q', b))
            ft.write(f"{i}\t{rec[1]}\t{rec[2]}\t{rec[3]}\t{rec[4]}\t{rec[5]:.4f}\t{rec[6]}\t{grp}\n")
    print(f"{len(disputes)} disputed decisions (claimed loss > {min_loss:.0%}), {len(agree)} controls -> {out}.bin/.tsv")

if __name__ == '__main__':
    main()
