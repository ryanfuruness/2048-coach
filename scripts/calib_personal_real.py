#!/usr/bin/env python3
"""Personal odds vs what real players achieved (curated human games): for each decision with a largest tile T0 <= 8192,
did the same player, in the same game, go on to reach 2 x T0 (and 4 x T0)? Compared with the personal-odds model at
the player's own skill t (softmax temperature fitted by maximum likelihood to the player's moves in that phase, as the
game review does) and with the engine's odds.

Games: a video's records in time order, split where the tile sum drops (new game). Outcome known: the game reached
the target (1), or it ended in an observed death before (0): the board after the game's last recorded move and spawn
has no legal move. Otherwise censored (the video ends or cuts while the game is alive; also abandoned games):
excluded, and the censored share is reported - videos of record attempts are more often kept to the end when they go
well, so the known-outcome sample can be biased in either direction.

usage: calib_personal_real.py [--model weights/calib/personal.txt] [--engine-model weights/calib/model.txt]
                              [--out results/cal6/personal_real.tsv]"""
import collections, gzip, json, math, sys

PHASES = [(0, 512), (1024, 2048), (4096, 8192), (16384, 1 << 30)]

def phase_of(top):
    return next(i for i, (lo, hi) in enumerate(PHASES) if lo <= top <= hi)

# ---- 2048 rules (ranks, 16 cells, cell 0 top-left) ----
def slide(r):
    nz = [x for x in r if x]; out = []; i = 0
    while i < len(nz):
        if i + 1 < len(nz) and nz[i] == nz[i + 1]: out.append(nz[i] + 1); i += 2
        else: out.append(nz[i]); i += 1
    return out + [0] * (4 - len(out))

def apply(b, d):
    g = [b[i * 4:(i + 1) * 4] for i in range(4)]
    if d == 'L': g = [slide(r) for r in g]
    elif d == 'R': g = [slide(r[::-1])[::-1] for r in g]
    elif d == 'U':
        cols = [slide([g[i][c] for i in range(4)]) for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    else:
        cols = [slide([g[i][c] for i in range(4)][::-1])[::-1] for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    return sum(g, [])

def can_move(b):
    return any(apply(b, d) != b for d in 'URDL')

def survival(after):
    empty = [i for i, x in enumerate(after) if x == 0]
    if not empty: return 1.0
    dead = 0.0
    for c in empty:
        for r, pr in ((1, 0.9), (2, 0.1)):
            nb = list(after); nb[c] = r
            if not can_move(nb): dead += pr / len(empty)
    return 1.0 - dead

def parse(h):
    return [0 if c == '0' else 16 if c == 'g' else 17 if c == 'h' else int(c, 16) for c in h]

# ---- models ----
KN = None
def hats(s, knots):
    s = min(max(s, knots[0]), knots[-1]); B = [0.0] * len(knots)
    for k in range(len(knots)):
        if k > 0 and knots[k - 1] <= s <= knots[k]: B[k] = (s - knots[k - 1]) / (knots[k] - knots[k - 1])
        if k + 1 < len(knots) and knots[k] <= s <= knots[k + 1]: B[k] = max(B[k], (knots[k + 1] - s) / (knots[k + 1] - knots[k]))
    return B

class Personal:
    def __init__(self, path):
        self.knots, self.vbar, self.coef, self.skill = None, {}, collections.defaultdict(dict), {}
        for line in open(path):
            p = line.split()
            if not p: continue
            if p[0] == 'pknots': self.knots = [float(x) for x in p[1:]]
            elif p[0] == 'pvbar': self.vbar[float(p[1])] = [float(x) for x in p[2:]]
            elif p[0] == 'personal': self.coef[float(p[1])][int(p[2])] = [float(x) for x in p[3:]]
            elif p[0] == 'pskillmap': self.skill[int(p[1])] = [float(x) for x in p[2:]]
    def soft_t(self, t_fit, ph):
        """the soft player whose review-fitted skill in phase ph is t_fit (pskillmap; log-log interpolation,
        proportional beyond the ends; identity without a map)"""
        m = self.skill.get(ph) or (self.skill[max(k for k in self.skill if k <= ph)] if any(k <= ph for k in self.skill) else None)
        if not m or t_fit <= 0: return t_fit
        pts = list(zip(m[0::2], m[1::2]))
        if t_fit <= pts[0][1]: return pts[0][0] * t_fit / pts[0][1]
        for (s0, f0), (s1, f1) in zip(pts, pts[1:]):
            if t_fit <= f1:
                w = (math.log(t_fit) - math.log(f0)) / (math.log(f1) - math.log(f0))
                return math.exp((1 - w) * math.log(s0) + w * math.log(s1))
        return pts[-1][0] * t_fit / pts[-1][1]
    def prob_at(self, t, T, s, v):
        w = self.coef[t].get(T)
        if w is None: return None
        B = hats(math.log2(max(s, 2)), self.knots)
        vb = max(1.0, sum(a * b for a, b in zip(B, self.vbar[t])))
        z = sum(a * b for a, b in zip(B, w)) + w[len(self.knots)] * (v / vb - 1.0)
        return 1 / (1 + math.exp(-max(-30, min(30, z))))
    def odds(self, t, max_tile, s, v):
        ts = sorted(self.coef)
        hi = next((x for x in ts if x >= t), None)
        if hi is None: lo = hi = ts[-1]
        elif hi == ts[0] or hi == t: lo = hi
        else: lo = ts[ts.index(hi) - 1]
        w = 0.0 if lo == hi else (math.log(t) - math.log(lo)) / (math.log(hi) - math.log(lo))
        w = min(1, max(0, w))
        out = {}
        for T in sorted(self.coef[lo]):
            if T <= max_tile: continue
            pl, ph = self.prob_at(lo, T, s, v), self.prob_at(hi, T, s, v)
            if pl is None or ph is None: continue
            lg = lambda p: math.log(min(1 - 1e-6, max(1e-6, p)) / (1 - min(1 - 1e-6, max(1e-6, p))))
            out[T] = 1 / (1 + math.exp(-((1 - w) * lg(pl) + w * lg(ph))))
        run = 1.0
        for T in sorted(out): out[T] = run = min(out[T], run)
        return out

def fit_t(ch):
    bt, bll, t = None, -1e300, 0.0003
    while t <= 1.0:
        ll = sum(-r[p] / t - math.log(sum(math.exp(-v / t) for v in r.values())) for r, p in ch)
        if ll > bll: bll, bt = ll, t
        t *= 1.1
    return bt

def main():
    args = sys.argv[1:]
    mpath, out, smap = 'weights/calib/personal.txt', 'results/cal6/personal_real.tsv', None
    while args:
        a = args.pop(0)
        if a == '--model': mpath = args.pop(0)
        elif a == '--out': out = args.pop(0)
        elif a == '--skillmap': smap = args.pop(0)
    pm = Personal(mpath)
    if smap:
        pm.skill = Personal(smap).skill
    use_map = bool(pm.skill)
    print(f"skill map: {'applied (' + str(sorted(pm.skill)) + ')' if use_map else 'none (fitted t used as the soft t)'}")
    rec = {}
    for line in gzip.open('../2048-human-data/dataset_build/positions.jsonl.gz', 'rt'):
        a = json.loads(line)
        rec[(a['video'], a['segment'], a['ply'])] = a
    ana = {}
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        ana[(a['video'], a['segment'], a['ply'])] = a
    # games
    byv = collections.defaultdict(list)
    for k, a in rec.items(): byv[a['video']].append(a)
    game_of, games = {}, []
    for v, rs in byv.items():
        rs.sort(key=lambda a: (a.get('t') or 0, a['segment'], a['ply']))
        prev, cur = None, []
        for a in rs:
            s = sum(1 << x for x in parse(a['board']) if x)
            if prev is not None and (s < prev - 64 or (s <= 16 and prev > 64)):
                games.append(cur); cur = []
            cur.append(a); prev = s
        games.append(cur)
    ginfo = []
    for gi, g in enumerate(games):
        tops = [max(parse(a['board'])) for a in g]
        last = g[-1]; b = parse(last['board']); nb = apply(b, last['move'])
        dead = None
        if last.get('spawn'):
            nb[last['spawn'][0]] = 1 if last['spawn'][1] == 2 else 2
            dead = not can_move(nb)
        # suffix max of the tile reached from each record on (the final board included)
        fin = max(max(nb), tops[-1])
        suf = [0] * len(g); m = fin
        for i in range(len(g) - 1, -1, -1):
            m = max(m, tops[i]); suf[i] = m
        ginfo.append(dict(dead=dead, video=g[0]['video'], player=g[0]['player'], tier=g[0]['tier'], n=len(g)))
        for i, a in enumerate(g):
            game_of[(a['video'], a['segment'], a['ply'])] = (gi, 1 << suf[i])  # largest tile reached from here on
    # skill per player and phase
    ch = collections.defaultdict(list)
    for k, a in ana.items():
        if a.get('observed') is False or a.get('undone') or a.get('maybe_two_moves') or a.get('rest_ambiguous'): continue
        vals = {m['move']: m['value'] for m in a['moves']}
        if len(vals) < 2 or a.get('played') not in vals or a['engine_move'] not in vals: continue
        ref = vals[a['engine_move']]
        rel = {d: max(0.0, ref - v) / max(100000.0, abs(ref)) for d, v in vals.items()}
        top = max(max(r) for r in a['board'])
        ch[(a['player'], phase_of(top))].append((rel, a['played']))
    tfit = {k: fit_t(v) for k, v in ch.items() if len(v) >= 100}
    rows = []
    cens = collections.Counter()
    for k, a in ana.items():
        if k not in game_of or a.get('observed') is False: continue
        cells = [x for r in a['board'] for x in r]
        top = max(cells)
        if top > 8192 or top < 64 or len(a['moves']) < 1: continue
        t = tfit.get((a['player'], phase_of(top)))
        if t is None: continue
        gi, reach = game_of[k]
        dead = ginfo[gi]['dead']
        best = max(a['moves'], key=lambda m: m['value'])
        after = parse(best['after'])
        sv = survival(after)
        s = sum(cells)
        po = pm.odds(pm.soft_t(t, phase_of(top)) if use_map else t, top, s, best['value'])
        eo = a.get('odds', {})
        for mult in (2, 4):
            T = top * mult
            if reach >= T: y = 1
            elif dead: y = 0
            else:
                cens[mult] += 1; continue
            cens[('known', mult)] += 1
            p = po.get(T)
            if p is None: continue
            rows.append((ginfo[gi]['player'], ginfo[gi]['tier'], gi, top, T, mult, t, p * sv, eo.get(str(T)), y))
    with open(out, 'w') as f:
        f.write('player\ttier\tgame\ttop\ttarget\tmult\tt\tpersonal\tengine\treached\n')
        for r in rows:
            f.write('\t'.join(str(x) for x in r) + '\n')
    print(f"{len(games)} games, {sum(1 for g in ginfo if g['dead'])} end in an observed death; "
          f"skills fitted for {len(tfit)} player-phases")
    for mult in (2, 4):
        kn, ce = cens[('known', mult)], cens[mult]
        print(f"target {mult}x the position's tile: outcome known for {kn} positions, censored {ce} "
              f"({100 * ce / max(1, kn + ce):.0f}%)")
    for mult in (2, 4):
        rs = [r for r in rows if r[5] == mult]
        if not rs: continue
        print(f"== {mult}x: {len(rs)} positions, {len(set(r[2] for r in rs))} games; mean personal {sum(r[7] for r in rs) / len(rs):.3f}, "
              f"observed {sum(r[9] for r in rs) / len(rs):.3f}")
        edges = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.97, 1.01]
        for lo, hi in zip(edges, edges[1:]):
            b = [r for r in rs if lo <= r[7] < hi]
            if len(b) < 20: continue
            eng = [r[8] for r in b if r[8] is not None]
            print(f"   personal {lo:4.2f}-{hi:4.2f}: n={len(b):6d} games={len(set(r[2] for r in b)):3d}  mean predicted "
                  f"{sum(r[7] for r in b) / len(b):.3f}  observed {sum(r[9] for r in b) / len(b):.3f}"
                  + (f"  (engine odds {sum(eng) / len(eng):.3f})" if eng else ''))
        for tier in ('novice', 'intermediate', 'strong', 'expert'):
            b = [r for r in rs if r[1] == tier]
            if len(b) < 20: continue
            eng = [r[8] for r in b if r[8] is not None]
            print(f"   {tier:12s}: n={len(b):6d} games={len(set(r[2] for r in b)):3d}  personal {sum(r[7] for r in b) / len(b):.3f}"
                  f"  observed {sum(r[9] for r in b) / len(b):.3f}" + (f"  engine {sum(eng) / len(eng):.3f}" if eng else ''))
        for top in sorted(set(r[3] for r in rs)):
            b = [r for r in rs if r[3] == top]
            if len(b) < 20: continue
            print(f"   tile {top:5d}: n={len(b):6d} games={len(set(r[2] for r in b)):3d}  personal {sum(r[7] for r in b) / len(b):.3f}"
                  f"  observed {sum(r[9] for r in b) / len(b):.3f}")

if __name__ == '__main__':
    main()
