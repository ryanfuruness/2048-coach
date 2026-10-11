#!/usr/bin/env python3
"""Staged loss maps from rollout judges on REAL human positions, with bootstrap confidence bands and a held-out check.

Each judged position is looked up in results/human_ds/analysis.jsonl by its engine board (hex) to get its real largest
tile, tier, player and played move (the rollout's own max column shows the engine's lowered board). Per position: dv =
relative value loss of each move vs the best value (the analysis' measure), dq = its rollout loss vs the best rollout
value (both / max(|best|, 100000)). Maps = isotonic regression of dq on dv over log-spaced bins, minus the noise floor
(the lowest bin's dq: the max over noisy rollout values is biased up), as scripts/fit_lossmap.py.

Stages (real largest tile): early <= 1024, late 2048-8192, top >= 16384 (and late2 = all >= 2048, the installed
two-stage form). The played-expert map uses only the PLAYED move of positions with a real tile >= 16384 (disputes,
claim-stratified decisions and the random top positions).

usage: fit_lossmap2.py [--boot N [--boot-players]] [--model OUT.txt] [--heldout] [--compare MODEL.txt] [played:]ROLLOUT.tsv ...
  --boot-players: the bands resample whole players (positions of one player are correlated; wider, honest bands)
  A chunked judge output is FILE_<start>.tsv: its pos column is offset by <start> (judge_cal6.sh naming).
  played:FILE marks selected decisions (disputes, claim-stratified samples): used only for the played-expert map.
  --model OUT.txt writes lossmap / lossmap_late / lossmap_top / lossmap_played_expert lines into OUT.txt (replacing).
  --heldout: 5-fold by video: mean squared error of predicted vs rollout real loss for the new maps and for the maps in
             --compare MODEL.txt (default weights/calib/model.txt).
  --only KEY,...: with --model, write only these maps (e.g. lossmap_top,lossmap_played_expert after a late-game
             network change, which leaves the early and late values as they were)
  --no-block: leave out positions in the block formation (scripts/block_detect.py = src/block.h, real 16384+): there
             the engine's claims carry no information (build/analyze does not judge them), so they must not shape the
             top and played-expert maps.
  --fixed-ref: (cal7) measure each move's rollout loss against a FIXED reference, the move with the best value (the
             analysis' reference), dq = (q_ref - q) / max(100000, |q_ref|), unclipped, instead of against the best of
             the noisy rollout means minus a noise floor: unbiased (no max-selection), so no floor is subtracted; the
             reference's own point is left out. The max-over-moves measure inflates the low end of the maps."""
import collections, json, math, random, re, sys, zlib
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from block_detect import block_position  # noqa: E402

EDGES = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.4, 10]

def load_lookup():
    look = {}
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        if a['hex'] in look:
            continue
        top = max(max(r) for r in a['board'])
        look[a['hex']] = (top, a.get('tier', '?'), a.get('player', a['video']), a['video'], a.get('played'),
                          bool(a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone')),
                          block_position([x for r in a['board'] for x in r]))
    return look

def load_positions(specs, look):
    """-> list of positions: dict(key, top, tier, player, video, played, unclean, moves={dir: (value, q, q_se)})"""
    pos = collections.OrderedDict()
    for spec in specs:
        played_only = spec.startswith('played:')  # selected decisions (disputes): only for the played-move map
        path = spec[len('played:'):] if played_only else spec
        m = re.search(r'_(\d{5})\.tsv$', path)
        off = int(m.group(1)) if m else 0
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                key = (re.sub(r'_\d{5}\.tsv$', '', path), int(r['pos']) + off)
                if key not in pos:
                    info = look.get(r['board'])
                    if info is None:
                        continue
                    top, tier, player, video, played, unclean, block = info
                    if block and NO_BLOCK:
                        continue
                    pos[key] = dict(key=key, top=top, tier=tier, player=player, video=video, played=played,
                                    unclean=unclean, engine=r['engine_move'], moves={}, played_only=played_only)
                d = {'U': 'up', 'R': 'right', 'D': 'down', 'L': 'left'}[r['move']]
                pos[key]['moves'][d] = (float(r['value']), float(r['q']), float(r['q_se']))
    out = [p for p in pos.values() if len(p['moves']) >= 2]
    for p in out:
        vb = max(v for v, _, _ in p['moves'].values())
        if FIXED_REF:
            ref = max(p['moves'], key=lambda d: p['moves'][d][0])
            qr = p['moves'][ref][1]
            p['pts'] = {d: ((vb - v) / max(100000.0, abs(vb)), (qr - q) / max(100000.0, abs(qr)))
                        for d, (v, q, _) in p['moves'].items() if d != ref}
            continue
        qb = max(q for _, q, _ in p['moves'].values())
        p['pts'] = {d: ((vb - v) / max(100000.0, abs(vb)), max(0.0, (qb - q) / max(100000.0, abs(qb))))
                    for d, (v, q, _) in p['moves'].items()}
    return out

def fit(pts, min_n=5):
    """isotonic map from (dv, dq) points -> knots [(x, y)] with the noise floor subtracted"""
    xs, ys, ns = [], [], []
    for lo, hi in zip(EDGES, EDGES[1:]):
        b = [p for p in pts if lo <= p[0] < hi]
        if len(b) < min_n:
            continue
        xs.append(sum(p[0] for p in b) / len(b)); ys.append(sum(p[1] for p in b) / len(b)); ns.append(len(b))
    blocks = [[y, n, [x]] for x, y, n in zip(xs, ys, ns)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            y = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (blocks[i][1] + blocks[i + 1][1])
            blocks[i] = [y, blocks[i][1] + blocks[i + 1][1], blocks[i][2] + blocks[i + 1][2]]
            del blocks[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    knots = [(x, y) for y, n, bx in blocks for x in bx]
    floor = 0.0 if FIXED_REF else (knots[0][1] if knots else 0.0)
    return [(0.0, 0.0)] + [(x, max(0.0, y - floor)) for x, y in knots]

def interp(knots, x):
    if not knots:
        return 0.0
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / max(1e-12, x1 - x0)
    return min(1.0, knots[-1][1] * x / max(1e-12, knots[-1][0]))

def pts_of(positions, played_only=False):
    out = []
    for p in positions:
        if played_only:
            if p['played'] in p['pts'] and not p['unclean']:
                out.append(p['pts'][p['played']])
        else:
            out.extend(p['pts'].values())
    return out

NO_BLOCK = '--no-block' in sys.argv  # leave out block-formation positions (real 16384+)
FIXED_REF = '--fixed-ref' in sys.argv  # rollout loss vs the reference move (unbiased), no noise floor
BOOT_BY_PLAYER = '--boot-players' in sys.argv  # resample whole players (the independent units) instead of positions

def boot_bands(positions, played_only, n_boot, grid):
    rnd = random.Random(1)
    curves = []
    byp = collections.defaultdict(list)
    for p in positions:
        byp[p['player']].append(p)
    players = sorted(byp)
    for _ in range(n_boot):
        if BOOT_BY_PLAYER:
            smp = [p for _ in players for p in byp[players[rnd.randrange(len(players))]]]
        else:
            smp = [positions[rnd.randrange(len(positions))] for _ in positions]
        k = fit(pts_of(smp, played_only))
        curves.append([interp(k, x) for x in grid])
    bands = []
    for j in range(len(grid)):
        v = sorted(c[j] for c in curves)
        bands.append((v[int(0.1 * len(v))], v[int(0.9 * len(v)) - 1]))
    return bands

def read_model_maps(path):
    maps = {}
    for line in open(path):
        p = line.split()
        if p and p[0].startswith('lossmap') and p[0] != 'lossmap_s':
            xs = [float(x) for x in p[1:]]
            maps[p[0]] = list(zip(xs[0::2], xs[1::2]))
    return maps

STAGES = [('early', 'lossmap', lambda t: t <= 1024), ('late', 'lossmap_late', lambda t: 2048 <= t <= 8192),
          ('top', 'lossmap_top', lambda t: t >= 16384), ('late2', 'lossmap_late2', lambda t: t >= 2048)]

def predict(maps, p, d, three_stage):
    x = p['pts'][d][0]
    if p['top'] >= 16384 and d == p['played'] and 'lossmap_played_expert' in maps:
        return interp(maps['lossmap_played_expert'], x)
    if p['top'] <= 1024:
        return interp(maps['lossmap'], x)
    if three_stage and p['top'] >= 16384 and 'lossmap_top' in maps:
        return interp(maps['lossmap_top'], x)
    return interp(maps['lossmap_late'], x)

def main():
    args = sys.argv[1:]
    n_boot, model, heldout, compare, only = 0, None, False, 'weights/calib/model.txt', None
    while args and args[0].startswith('--'):
        a = args.pop(0)
        if a == '--boot': n_boot = int(args.pop(0))
        elif a == '--model': model = args.pop(0)
        elif a == '--heldout': heldout = True
        elif a == '--compare': compare = args.pop(0)
        elif a == '--only': only = set(args.pop(0).split(','))
        elif a in ('--boot-players', '--no-block', '--fixed-ref'): pass
    look = load_lookup()
    positions = load_positions(args, look)
    print(f"{len(positions)} judged positions ({sum(len(p['moves']) for p in positions)} position-moves) from "
          f"{len(set(p['player'] for p in positions))} players")
    grid = [0.003, 0.01, 0.03, 0.06, 0.1, 0.15, 0.2, 0.3, 0.45, 0.65]
    lines = {}
    for name, key, sel in STAGES + [('played_expert', 'lossmap_played_expert', None)]:
        if name == 'played_expert':
            ps = [p for p in positions if p['top'] >= 16384]
            pts = pts_of(ps, True)
        else:
            ps = [p for p in positions if sel(p['top']) and not p['played_only']]
            pts = pts_of(ps)
        if len(ps) < 20:
            continue
        k = fit(pts)
        lines[key] = k
        print(f"== {name}: {len(ps)} positions, {len(pts)} points, {len(set(p['player'] for p in ps))} players")
        bands = boot_bands(ps, name == 'played_expert', n_boot, grid) if n_boot else None
        cnt = [sum(1 for x, _ in pts if x >= g) for g in grid]
        for j, g in enumerate(grid):
            if g > max(x for x, _ in pts) * 1.05:
                break
            band = f"  (80% band {100 * bands[j][0]:5.2f} - {100 * bands[j][1]:5.2f})" if bands else ''
            print(f"   value loss {100 * g:5.1f}%  ->  real loss {100 * interp(k, g):6.2f}%{band}   [{cnt[j]} points >= x]")
    if model:
        if only:
            lines = {k: v for k, v in lines.items() if k in only}
        keep = []
        try:
            keep = [l for l in open(model) if not any(l.startswith(k + ' ') for k in lines)]
        except FileNotFoundError:
            pass
        with open(model, 'w') as f:
            f.writelines(keep)
            for key in ('lossmap', 'lossmap_late', 'lossmap_top', 'lossmap_played_expert'):
                if key in lines:
                    f.write(key + ' ' + ' '.join(f"{x:.5g} {y:.5g}" for x, y in lines[key]) + '\n')
        print('maps ->', model)
    if heldout:
        old = read_model_maps(compare)
        folds = lambda p: zlib.crc32(p['video'].encode()) % 5  # deterministic (Python's hash() is salted per run)
        res = collections.defaultdict(lambda: [0.0, 0])
        cal = collections.defaultdict(lambda: [0.0, 0.0, 0])  # (map, stage, bin) -> sum pred, sum obs - floor, n
        PB = [0, 0.01, 0.03, 0.1, 0.3, 2]
        for f in range(5):
            train = [p for p in positions if folds(p) != f]
            test = [p for p in positions if folds(p) == f]
            new = {}
            for name, key, sel in STAGES:
                new[key] = fit(pts_of([p for p in train if sel(p['top']) and not p['played_only']]))
            new['lossmap_played_expert'] = fit(pts_of([p for p in train if p['top'] >= 16384], True))
            new2 = dict(new); new2['lossmap_late'] = new['lossmap_late2']
            # noise floor per stage on the training fold (mean rollout loss of moves within 0.1% of the best value)
            fl = {}
            for stage, sel in (('early', lambda t: t <= 1024), ('late', lambda t: 2048 <= t <= 8192),
                               ('top', lambda t: t >= 16384)):
                z = [y for p in train if sel(p['top']) for x, y in p['pts'].values() if x < 0.001]
                fl[stage] = 0.0 if FIXED_REF else sum(z) / max(1, len(z))
            fl['played_expert'] = fl['top']
            for p in test:
                for d, (x, y) in p['pts'].items():
                    stage = 'early' if p['top'] <= 1024 else 'late' if p['top'] <= 8192 else 'top'
                    if d == p['played'] and p['top'] >= 16384 and not p['unclean']:
                        stage = 'played_expert'
                    elif p['played_only']:
                        continue
                    # the compared model is 3-stage when it has a top map (cal7: it was always scored 2-stage, i.e.
                    # with its late map in 16384+ positions)
                    for mname, mp, three in (('installed', old, 'lossmap_top' in old), ('new 2-stage', new2, False),
                                             ('new 3-stage', new, True)):
                        pr = predict(mp, p, d, three)
                        e = (pr - (y - fl[stage])) ** 2
                        res[(mname, stage)][0] += e; res[(mname, stage)][1] += 1
                        res[(mname, 'all')][0] += e; res[(mname, 'all')][1] += 1
                        b = max(i for i in range(len(PB) - 1) if pr >= PB[i])
                        c = cal[(mname, stage, b)]; c[0] += pr; c[1] += y - fl[stage]; c[2] += 1
        print("== held-out (5 folds by video): root mean squared error of the estimated real loss (x100)")
        for stage in ('early', 'late', 'top', 'played_expert', 'all'):
            row = '  '.join(f"{m} {100 * math.sqrt(res[(m, stage)][0] / max(1, res[(m, stage)][1])):6.3f}"
                            for m in ('installed', 'new 2-stage', 'new 3-stage'))
            print(f"   {stage:13s} n={res[('installed', stage)][1]:5d}   {row}")
        print("== held-out calibration: mean predicted vs mean measured real loss (rollout loss - noise floor), by "
              "predicted bin (x100)")
        for stage in ('early', 'late', 'top', 'played_expert'):
            for m in ('installed', 'new 2-stage', 'new 3-stage'):
                cells = []
                for b in range(len(PB) - 1):
                    c = cal[(m, stage, b)]
                    if c[2]:
                        cells.append(f"[{100 * PB[b]:g}-{100 * PB[b + 1]:g}) n={c[2]} {100 * c[0] / c[2]:.2f} vs "
                                     f"{100 * c[1] / c[2]:.2f}")
                print(f"   {stage:13s} {m:12s} " + ';  '.join(cells))

if __name__ == '__main__':
    main()
