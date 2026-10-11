#!/usr/bin/env python3
"""The player's own move vs the alternatives on the rollout truth (scorecard): for every judged position, each
non-reference move's claimed value loss x = (v_ref - v)/max(|v_ref|, 100k) and its measured loss with the engine
continuing, (q_ref - q)/max(|q_ref|, 100k) (unbiased: a difference of two rollout means against the analysis' own
reference move, no max-over-moves bias, no noise-floor subtraction), by claim bucket, split into the move the player
PLAYED and the OTHER moves; with the configuration's map estimate (all-move stage map, and the played-expert map for
played moves from a real 16384). Sets: unselected positions (human300, late300, j1200) and the selected expert decisions
(jx + jold: played moves only). Table-decided and not-judged positions are left out (their real loss is not
value-based).
usage: scorecard_played.py NAME [--plain]"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorecard_eval import tsv, ref_move, rel_value, NAME_OF, interp_map, stage_map, model_maps  # noqa: E402

B = [0, 0.003, 0.01, 0.03, 0.1, 0.3, 10]


def main():
    name = sys.argv[1]
    plain = '--plain' in sys.argv
    D = f'results/scorecard/{name}'
    maps = model_maps(f'{D}/model.txt')
    pos = tsv('results/scorecard/inputs/judge_pos.tsv')
    q = collections.defaultdict(dict)
    for r in tsv('results/scorecard/inputs/judge_truth.tsv'):
        q[int(r['id'])][r['move']] = (float(r['q']), float(r['q_se']))
    A = [json.loads(l) for l in open(f'{D}/judge.jsonl')]
    acc = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
    for p, a in zip(pos, A):
        if not a.get('moves') or a.get('source', 'search') != 'search': continue
        if a.get('judged') is False and not plain: continue
        sel = p['set'] in ('jx', 'jold')
        if sel and (p['unclean'] == '1' or int(p['top']) < 16384): continue
        i = int(p['id']); qs = q[i]; r = ref_move(a)
        if r is None or r not in qs: continue
        top = int(p['top']); st = 'early' if top <= 1024 else 'late' if top <= 8192 else 'top'
        pl = NAME_OF.get(p['played'])
        scale = max(100000.0, abs(qs[r][0]))
        for m in a['moves']:
            d = NAME_OF[m['move']]
            if d == r or d not in qs: continue
            kind = 'played' if d == pl else 'other'
            if sel and kind != 'played': continue
            x = rel_value(a, d, r)
            est = interp_map(stage_map(maps, top, played_expert=(kind == 'played' and top >= 16384)), x)
            y = (qs[r][0] - qs[d][0]) / scale
            v = (qs[r][1] ** 2 + qs[d][1] ** 2) / scale ** 2
            b = max(k for k in range(len(B) - 1) if x >= B[k])
            grp = ('experts (jx+jold)' if sel else st)
            for key in ((grp, kind, b), (('all unselected' if not sel else grp), kind, b)):
                c = acc[key]; c[0] += 1; c[1] += x; c[2] += est; c[3] += y; c[4] += v
    print("player's move vs the alternatives: per claim bucket n, mean claim, map estimate, measured loss +- se (x100)")
    for grp in ('early', 'late', 'top', 'all unselected', 'experts (jx+jold)'):
        for kind in ('played', 'other'):
            cells = []
            for b in range(len(B) - 1):
                c = acc.get((grp, kind, b))
                if not c or c[0] < 5: continue
                n = c[0]
                cells.append(f"[{100 * B[b]:g}-{100 * B[b + 1]:g}) n={n} {100 * c[1] / n:.1f} -> map {100 * c[2] / n:.1f} | "
                             f"real {100 * c[3] / n:+.1f}+-{100 * math.sqrt(c[4]) / n:.1f}")
            if cells:
                print(f"   {grp:17s} {kind:6s} " + ';  '.join(cells))


if __name__ == '__main__':
    main()
