#!/usr/bin/env python3
"""Skill of real players by the human move model (workstream hm2) vs the softmax review statistic: per player and
phase, theta = maximum likelihood of the played moves under the human move model (src/human.h weights,
results/hm/human_model_v2.txt; the same grid as build/analyze's review: -3..3 step 0.025) and t = the softmax review
temperature (search losses, analyze's grid). Compares (1) split-half reliability (first vs second half of a player's
moves in the phase), (2) separation of the tiers (Spearman with the tier order, eta^2), (3) personal odds on real
outcomes (as scripts/calib_personal_real.py: did the same player in the same game reach 2x / 4x the tile?) with the
personal model's key from theta (theta map) vs from t (skill map), on the same positions, game-clustered bootstrap.
usage: hm_skill_real.py --personal MODEL.txt [--out results/hm2/skill_real]"""
import collections, gzip, json, math, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit
import calib_personal_real as cpr

TGRID = np.array([-3.0 + 0.025 * g for g in range(241)])
SGRID = []
t = 0.0003
while t <= 1.0: SGRID.append(t); t *= 1.1
SGRID = np.array(SGRID)

def load_model(path):
    M = dict(ws={}, wh={})
    for line in open(path):
        p = line.split()
        if not p or p[0].startswith('#'): continue
        if p[0] == 'wv': M['wv'] = np.array([float(x) for x in p[2::2]])
        elif p[0] == 'ws': M['ws'][p[1]] = float(p[2])
        elif p[0] == 'wh': M['wh'][p[1]] = float(p[2])
        elif p[0] == 'eps': M['eps'] = float(p[1])
        elif p[0] == 'gab': M['ga'], M['gb'] = float(p[1]), float(p[2])
    return M

def thetamap(path):
    m = {}
    for line in open(path):
        p = line.split()
        if p and p[0] == 'pthetamap':
            xs = [float(x) for x in p[2:]]
            m[int(p[1])] = sorted(zip(xs[1::2], [math.log(k) for k in xs[0::2]]))
    return m

def key_of_theta(tm, theta, ph):
    phs = [q for q in tm if q <= ph] or sorted(tm)
    pts = tm[max(phs)] if any(q <= ph for q in tm) else tm[min(tm)]
    if theta <= pts[0][0]: return math.exp(pts[0][1])
    if theta >= pts[-1][0]: return math.exp(pts[-1][1])
    for (a, la), (b, lb) in zip(pts, pts[1:]):
        if theta <= b:
            w = (theta - a) / max(1e-12, b - a)
            return math.exp((1 - w) * la + w * lb)
    return math.exp(pts[-1][1])

def loglik_grid(Vw, Sw, Hw, legal, played, eps, ga, gb):
    """(n, len(TGRID)) log-likelihood of the played move at every theta of the grid"""
    n = len(played)
    out = np.empty((n, len(TGRID)), dtype=np.float32)
    nl = legal.sum(1)
    for g, th in enumerate(TGRID):
        z = np.exp(th) * Vw + np.exp(ga + gb * th) * Sw + Hw
        z = np.where(legal, z, -1e30)
        z = z - z.max(1, keepdims=True)
        e = np.exp(z) * legal
        p = (1 - eps) * e / e.sum(1, keepdims=True) + eps / nl[:, None]
        out[:, g] = np.log(np.maximum(1e-300, p[np.arange(n), played]))
    return out

def soft_grid(L, legal, played):
    n = len(played)
    out = np.empty((n, len(SGRID)), dtype=np.float32)
    for g, t in enumerate(SGRID):
        z = np.where(legal, -L / t, -1e30)
        z = z - z.max(1, keepdims=True)
        lz = np.log((np.exp(z) * legal).sum(1))
        out[:, g] = z[np.arange(n), played] - lz
    return out

def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])

def main():
    args = sys.argv[1:]
    pmodel = args[args.index('--personal') + 1] if '--personal' in args else 'weights/calib/personal.txt'
    out = args[args.index('--out') + 1] if '--out' in args else 'results/hm2/skill_real'
    D = dict(np.load('results/hm/data.npz'))
    R = np.load('results/hm/recent.npz'); D['_recent'] = (R['cnt'], R['hl'])
    B = hm_fit.build(D, 'full_tied_death_recent')
    M = load_model('results/hm/human_model_v2.txt')
    names_v, names_s, names_h = B['names']
    Vw = B['V'] @ M['wv']
    Sw = B['S'] @ np.array([M['ws'][k] for k in names_s])
    Hw = B['H'] @ np.array([M['wh'][k] for k in names_h])
    legal, played = B['legal'], B['played']
    L = np.nan_to_num(D['losss'], nan=0.0)
    ok = legal.sum(1) >= 2
    phase = np.where(D['mx'] <= 512, 0, np.where(D['mx'] <= 2048, 1, np.where(D['mx'] <= 8192, 2, 3)))
    print(f"{ok.sum()} decisions with >= 2 legal moves; computing the likelihood grids...", flush=True)
    HG = loglik_grid(Vw, Sw, Hw, legal, played, M['eps'], M['ga'], M['gb'])
    SG = soft_grid(L, legal, played)
    players = D['players']
    order = np.lexsort((D['ply'], D['seg'], D['video']))
    groups = collections.defaultdict(list)
    for i in order:
        if ok[i]: groups[(int(D['player'][i]), int(phase[i]))].append(i)
    tiers = {}
    for i in range(len(played)): tiers[int(D['player'][i])] = int(D['tier'][i])
    est = {}
    rel_th, rel_t = [], []
    for (pl, ph), idx in groups.items():
        if len(idx) < 100: continue
        idx = np.array(idx)
        th = TGRID[HG[idx].sum(0).argmax()]; tt = SGRID[SG[idx].sum(0).argmax()]
        est[(pl, ph)] = (th, tt, len(idx))
        if len(idx) >= 200:
            a, b = idx[:len(idx) // 2], idx[len(idx) // 2:]
            rel_th.append((TGRID[HG[a].sum(0).argmax()], TGRID[HG[b].sum(0).argmax()], ph))
            rel_t.append((math.log(SGRID[SG[a].sum(0).argmax()]), math.log(SGRID[SG[b].sum(0).argmax()]), ph))
    print("\n== split-half reliability (first vs second half of a player's moves in the phase; Pearson / Spearman)")
    for ph in range(4):
        x = [r for r in rel_th if r[2] == ph]; y = [r for r in rel_t if r[2] == ph]
        if len(x) < 5: continue
        ra = np.corrcoef([r[0] for r in x], [r[1] for r in x])[0, 1]; rs = spearman([r[0] for r in x], [r[1] for r in x])
        ta = np.corrcoef([r[0] for r in y], [r[1] for r in y])[0, 1]; ts = spearman([r[0] for r in y], [r[1] for r in y])
        print(f"   phase {ph}: {len(x):3d} player-phases   theta {ra:.3f} / {rs:.3f}    log t {ta:.3f} / {ts:.3f}")
    print("\n== tier separation per phase (Spearman of the skill with the tier order novice < intermediate < strong < "
          "expert, sign so that + = stronger; eta^2 = between-tier share of the variance)")
    tier_names = {}
    for ph in range(4):
        ks = [k for k in est if k[1] == ph]
        if len(ks) < 8: continue
        tier = np.array([tiers[k[0]] for k in ks])
        th = np.array([est[k][0] for k in ks]); lt = np.array([-math.log(est[k][1]) for k in ks])
        def eta2(x):
            m = x.mean(); tot = ((x - m) ** 2).sum()
            btw = sum(((x[tier == g].mean() - m) ** 2) * (tier == g).sum() for g in set(tier.tolist()))
            return btw / max(1e-12, tot)
        print(f"   phase {ph}: {len(ks):3d} players   theta: Spearman {spearman(th, tier):+.3f} eta2 {eta2(th):.3f}   "
              f"-log t: Spearman {spearman(lt, tier):+.3f} eta2 {eta2(lt):.3f}")
        for g in sorted(set(tier.tolist())):
            print(f"        tier {g}: n={int((tier == g).sum()):3d}  theta median {np.median(th[tier == g]):+.3f}   "
                  f"t median {math.exp(-np.median(lt[tier == g])):.4f}")
    # the softmax t predicted from theta (per phase, OLS of log t on theta over the player-phases; out of fold by
    # player, 5 folds): a reliable skill reading mapped onto the scale the personal model's skill map was built on
    plist = sorted({k[0] for k in est})
    fold = {pl: i % 5 for i, pl in enumerate(plist)}
    that = {}
    coefs = {}
    foldc = {}  # (phase, fold) -> the fold's coefficients; phases with < 30 player-phases use phase 1's (as analyze)
    for ph in range(4):
        ks = [k for k in est if k[1] == ph]
        if len(ks) < 8: continue
        X = np.array([est[k][0] for k in ks]); Y = np.array([math.log(est[k][1]) for k in ks])
        A = np.vstack([np.ones_like(X), X]).T
        c_fwd = np.linalg.lstsq(A, Y, rcond=None)[0]
        c_rev = np.linalg.lstsq(np.vstack([np.ones_like(Y), Y]).T, X, rcond=None)[0]  # theta = c + d log t
        coefs[ph] = np.concatenate([c_fwd, c_rev])
        for f in range(5):
            tr = np.array([fold[k[0]] != f for k in ks])
            if tr.sum() < 5: continue
            foldc[(ph, f)] = np.linalg.lstsq(A[tr], Y[tr], rcond=None)[0]
    for k, v in est.items():
        ph = k[1] if sum(1 for q in est if q[1] == k[1]) >= 30 else 1
        c = foldc.get((ph, fold[k[0]]))
        if c is not None: that[k] = math.exp(c[0] + c[1] * v[0])
    print("\n== log t = a + b theta and theta = c + d log t per phase (all players): " +
          ", ".join(f"phase {ph} (n={sum(1 for k in est if k[1] == ph)}): a {c[0]:+.3f} b {c[1]:+.3f} c {c[2]:+.3f} d {c[3]:+.3f}"
                    for ph, c in sorted(coefs.items())))
    with open(out + '_thetat.txt', 'w') as f:  # phases with >= 30 player-phases (analyze: the nearest lower phase else)
        for ph, c in sorted(coefs.items()):
            if sum(1 for q in est if q[1] == ph) >= 30: f.write(f"pthetat {ph} {c[0]:.4f} {c[1]:.4f} {c[2]:.4f} {c[3]:.4f}\n")
    # personal odds on real outcomes, key from theta vs from t, same positions
    tm = thetamap(pmodel)
    pm = cpr.Personal(pmodel)
    pname = {i: str(n) for i, n in enumerate(players)}
    by_name = {(pname[k[0]], k[1]): v + (that.get(k),) for k, v in est.items()}
    rec = {}
    for line in gzip.open('../2048-human-data/dataset_build/positions.jsonl.gz', 'rt'):
        a = json.loads(line)
        rec[(a['video'], a['segment'], a['ply'])] = a
    byv = collections.defaultdict(list)
    for k, a in rec.items(): byv[a['video']].append(a)
    games = []
    for v, rs in byv.items():
        rs.sort(key=lambda a: (a.get('t') or 0, a['segment'], a['ply']))
        prev, cur = None, []
        for a in rs:
            s = sum(1 << x for x in cpr.parse(a['board']) if x)
            if prev is not None and (s < prev - 64 or (s <= 16 and prev > 64)):
                games.append(cur); cur = []
            cur.append(a); prev = s
        games.append(cur)
    game_of, ginfo = {}, []
    for gi, g in enumerate(games):
        tops = [max(cpr.parse(a['board'])) for a in g]
        last = g[-1]; b = cpr.parse(last['board']); nb = cpr.apply(b, last['move'])
        dead = None
        if last.get('spawn'):
            nb[last['spawn'][0]] = 1 if last['spawn'][1] == 2 else 2
            dead = not cpr.can_move(nb)
        fin = max(max(nb), tops[-1]); suf = [0] * len(g); m = fin
        for i in range(len(g) - 1, -1, -1):
            m = max(m, tops[i]); suf[i] = m
        ginfo.append(dict(dead=dead, player=g[0]['player'], tier=g[0]['tier']))
        for i, a in enumerate(g): game_of[(a['video'], a['segment'], a['ply'])] = (gi, 1 << suf[i])
    rows = []
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        k = (a['video'], a['segment'], a['ply'])
        if k not in game_of or a.get('observed') is False: continue
        cells = [x for r in a['board'] for x in r]; top = max(cells)
        if top > 8192 or top < 64 or len(a['moves']) < 1: continue
        ph = cpr.phase_of(top)
        e = by_name.get((a['player'], ph))
        if e is None: continue
        th, tt, _, tth = e
        if tth is None: continue
        gi, reach = game_of[k]; dead = ginfo[gi]['dead']
        best = max(a['moves'], key=lambda m: m['value'])
        sv = cpr.survival(cpr.parse(best['after'])); s = sum(cells)
        po_t = pm.odds(pm.soft_t(tt, ph), top, s, best['value'])
        po_h = pm.odds(key_of_theta(tm, th, ph), top, s, best['value']) if tm else {}
        po_x = pm.odds(pm.soft_t(tth, ph), top, s, best['value'])
        for mult in (2, 4):
            T = top * mult
            if reach >= T: y = 1
            elif dead: y = 0
            else: continue
            pt, ph_, px = po_t.get(T), po_h.get(T), po_x.get(T)
            if pt is None or ph_ is None or px is None: continue
            rows.append((gi, ginfo[gi]['tier'], mult, pt * sv, ph_ * sv, y, px * sv, k))
    with open(out + '_rows.tsv', 'w') as f:  # per position-target predictions (hm3: model comparisons on common rows)
        f.write('video\tsegment\tply\tmult\tgame\ttier\ty\tp_t\tp_theta\tp_tt\n')
        for r in rows:
            f.write(f"{r[7][0]}\t{r[7][1]}\t{r[7][2]}\t{r[2]}\t{r[0]}\t{r[1]}\t{r[5]}\t{r[3]:.5f}\t{r[4]:.5f}\t{r[6]:.5f}\n")
    print(f"\n== personal odds on real outcomes ({len(rows)} position-targets): key from t (skill map) vs from theta "
          f"(theta map); game-clustered bootstrap of the log-loss difference (theta - t)")
    rng = np.random.default_rng(1)
    for mult in (2, 4):
        rs = [r for r in rows if r[2] == mult]
        if not rs: continue
        g = np.array([r[0] for r in rs]); y = np.array([r[5] for r in rs], float)
        pt = np.clip(np.array([r[3] for r in rs]), 1e-6, 1 - 1e-6); ph_ = np.clip(np.array([r[4] for r in rs]), 1e-6, 1 - 1e-6)
        px = np.clip(np.array([r[6] for r in rs]), 1e-6, 1 - 1e-6)
        llt = -(y * np.log(pt) + (1 - y) * np.log(1 - pt)); llh = -(y * np.log(ph_) + (1 - y) * np.log(1 - ph_))
        llx = -(y * np.log(px) + (1 - y) * np.log(1 - px))
        games_u = np.unique(g); diffs = []
        gi_idx = {x: np.where(g == x)[0] for x in games_u}
        for _ in range(400):
            pick = rng.choice(games_u, len(games_u))
            ii = np.concatenate([gi_idx[x] for x in pick])
            diffs.append((llh[ii].mean() - llt[ii].mean(), llx[ii].mean() - llt[ii].mean()))
        lo, hi = np.percentile([d[0] for d in diffs], [5, 95])
        xlo, xhi = np.percentile([d[1] for d in diffs], [5, 95])
        def auc(p):
            o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
            n1 = y.sum(); n0 = len(y) - n1
            return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / max(1, n1 * n0)
        print(f"   {mult}x: n={len(rs)} games={len(games_u)} observed {y.mean():.3f}   t: mean {pt.mean():.3f} "
              f"log-loss {llt.mean():.3f} Brier {((pt - y) ** 2).mean():.3f} AUC {auc(pt):.3f}   theta: mean {ph_.mean():.3f} "
              f"log-loss {llh.mean():.3f} Brier {((ph_ - y) ** 2).mean():.3f} AUC {auc(ph_):.3f}   diff {llh.mean() - llt.mean():+.3f} "
              f"[{lo:+.3f}, {hi:+.3f}]")
        print(f"      t predicted from theta (out of fold): mean {px.mean():.3f} log-loss {llx.mean():.3f} Brier "
              f"{((px - y) ** 2).mean():.3f} AUC {auc(px):.3f}   diff vs t {llx.mean() - llt.mean():+.3f} [{xlo:+.3f}, {xhi:+.3f}]")
        for tier in ('novice', 'intermediate', 'strong', 'expert'):
            sel = np.array([r[1] == tier for r in rs])
            if sel.sum() < 50: continue
            print(f"      {tier:12s} n={int(sel.sum()):6d} observed {y[sel].mean():.3f}  t {pt[sel].mean():.3f} "
                  f"(ll {llt[sel].mean():.3f})  theta {ph_[sel].mean():.3f} (ll {llh[sel].mean():.3f})  "
                  f"t(theta) {px[sel].mean():.3f} (ll {llx[sel].mean():.3f})")
    with open(out + '_est.tsv', 'w') as f:
        f.write('player\ttier\tphase\ttheta\tt\tn\n')
        for (pl, ph), (th, tt, n) in sorted(est.items()):
            f.write(f"{pname[pl]}\t{tiers[pl]}\t{ph}\t{th:.3f}\t{tt:.5f}\t{n}\n")

if __name__ == '__main__':
    main()
