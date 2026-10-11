#!/usr/bin/env python3
"""Block-formation detector (workstream late, for analyze's abstention in PDF positions): True when the 6 largest
tiles of the board (ranks, cell 0 = top-left; ties broken toward bigger) fill a 3x2 or 2x3 rectangle in a corner -
macroxue's Perimeter Defense Formation as the PDF player builds it (mx's "block6"). Report: the detector on cal6's
expert judge (claims of the given candidates split by block6 / not) and its agreement with the player label.
usage: exp_late_block6.py report IDX META.tsv CLAIMS.jsonl ..."""
import sys, json, math, collections
sys.path.insert(0, __file__.rsplit('/', 1)[0])

RECTS = []
for r0, c0, h, w in [(0, 0, 2, 3), (0, 0, 3, 2), (0, 1, 2, 3), (0, 2, 3, 2), (1, 0, 3, 2), (2, 0, 2, 3), (1, 2, 3, 2),
                     (2, 1, 2, 3)]:
    RECTS.append(frozenset((r0 + i) * 4 + c0 + j for i in range(h) for j in range(w)))


def block6(ranks):
    order = sorted(range(16), key=lambda c: -ranks[c])
    top = order[:6]
    if ranks[top[-1]] == 0 or (len(order) > 6 and ranks[order[6]] == ranks[top[-1]] and ranks[top[-1]] >= 9):
        pass  # ties at the 6th place: still test the 6 chosen cells
    return frozenset(top) in RECTS


def main():
    from exp_late_judge import load, NAME
    import csv
    idx_path, meta = sys.argv[2], sys.argv[3]
    lines = open(idx_path).read().splitlines()
    files, body = lines[0].split(','), lines[1:]
    idx = [tuple(int(x) for x in l.split()) for l in body]
    pos = load(files, 0)
    player = {r['hex']: (r['player'], r['played']) for r in csv.DictReader(open(meta), delimiter='\t')}
    conf = collections.Counter()
    for k in idx:
        b = pos[k]['board']
        conf[(player.get(b, ('?',))[0] == 'd4Nf6Bg5', block6([int(c, 16) for c in b]))] += 1
    print("PDF player x block6 detector:", dict(conf))
    for path in sys.argv[4:]:
        acc = collections.defaultdict(lambda: collections.Counter())
        for k, line in zip(idx, open(path)):
            a = json.loads(line)
            p = pos[k]
            if 'moves' not in a or len(a['moves']) < 2: continue
            g = 'block6' if block6([int(c, 16) for c in p['board']]) else 'other'
            vals = {NAME[m['move']]: m['value'] for m in a['moves']}
            lock = {NAME[m['move']] for m in a['moves'] if m.get('breaks_corner')}
            eng = NAME.get(a.get('engine_move') or '', None)
            refm = eng if (eng and a.get('source', 'search') != 'search') else max([m for m in vals if m not in lock] or list(vals), key=lambda m: vals[m])
            ref = vals[refm]
            pm = NAME.get(player.get(p['board'], ('', ''))[1], None)
            e = p['eng']
            if pm and pm in p['q'] and e in p['q'] and pm != e and pm in vals:
                (qe, se_), (qp, sp) = p['q'][e], p['q'][pm]
                s = math.hypot(se_, sp)
                v = 'confirmed' if qe - qp > 2 * s else ('refuted' if qp >= qe - s else 'unclear')
                cl = max(0.0, ref - vals[pm]) / max(100000.0, abs(ref))
                acc[g][v] += 1
                if cl > 0.10: acc[g][v + '>10'] += 1
        name = path.rsplit('/', 1)[-1].replace('.jsonl', '')
        for g in ('block6', 'other'):
            A = acc[g]
            print(f"{name:14s} {g:7s} played moves: refuted {A['refuted']:3d} (claimed > 10%: {A['refuted>10']:3d}), "
                  f"confirmed {A['confirmed']:3d} ({A['confirmed>10']:3d}), unclear {A['unclear']:3d} ({A['unclear>10']:3d})")


if __name__ == '__main__':
    main()
