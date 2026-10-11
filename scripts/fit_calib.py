#!/usr/bin/env python3
"""Fit the odds model from build/messy --values outputs (positions whose future the engine played alone).

For each target tile T: logit P(reach T) = a_T(s) + b_T(s) * u, over positions without T yet, where s = log2(tile sum),
u = value / vbar(s) - 1 (the position's value relative to the mean value of clean engine positions at that tile sum),
and a_T, b_T are piecewise linear in s (hat functions on fixed knots). Also the expected future score:
E[future] = c(s) * value (piecewise-linear ratio). Writes a JSON model for build/analyze --calib.

usage: fit_calib.py OUT.json [--clean FILE.tsv ...] [--base-log PLAY.log ...] FILE.tsv ...
--clean files define vbar(s) (default: files whose name contains 'clean').
--base-log: build/play logs of the engine from fresh games ("game ... max M ... sum S" lines); every game adds one
virtual checkpoint row per tile sum it passed below each target (value = vbar(s), i.e. u = 0), which pins the base rates
P(reach T | alive at sum s) without the sampling bias of random per-game positions.
"""
import sys, json, math, zlib
import numpy as np

KNOTS = [6, 8, 10, 12, 13, 14, 14.6, 15, 15.6, 16]  # log2 tile sum: 64 .. 65536
USE_RANDOM = '--use-random' in sys.argv
UCLIP = 0.3  # must match Calib::kUClip in src/calib.h
# value term: 'clip' = ratio - 1 clipped to +-UCLIP; 'log' = log(ratio) with the ratio floored at 1% (mild for moderate
# deficits, steep for extreme ones: the tight-position truth showed a strongly nonlinear effect)
UMODE = 'log' if '--umode-log' in sys.argv else 'clip'
def utrans(ratio):
    if UMODE == 'log':
        return np.log(np.maximum(ratio, 0.01))
    return np.clip(ratio - 1.0, -UCLIP, UCLIP)
TARGETS = [11, 12, 13, 14, 15, 16]                  # 2048 .. 65536
# value-slope bands: cut points in log2 tile sum between knots (--slope-bands 12,14 = 3 bands: < 4096, 4096-16384, >= 16384)
BANDS = [float(x) for x in sys.argv[sys.argv.index('--slope-bands') + 1].split(',')] if '--slope-bands' in sys.argv else [14.0]

def load(path, allow_random=False):
    rows = []
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            if 'value' not in r or r['value'] in ('nan', ''):
                continue
            ef = r.get('engine_future')
            if ef is not None:
                if ef != '1':
                    continue
            elif not (r['switch'] == '1' or int(r['phase']) >= 1 or 'clean' in path):
                continue
            # only unbiased rows: handovers (switch 1) and checkpoints (2); random per-game samples (0) over-represent
            # short, failing games among early positions (use --use-random to include them anyway)
            if r['switch'] == '0' and not (USE_RANDOM or allow_random):
                continue
            rows.append((float(r['sum']), int(r['max']), float(r['value']), float(r['final_score']) - float(r['score']),
                         int(r['final_max']), zlib.crc32(f"{path}:{r['game']}".encode())))  # deterministic game id
    return rows

def hats(s):
    """Hat-function basis on KNOTS at log2 sums s (array) -> matrix (n, len(KNOTS))."""
    s = np.clip(s, KNOTS[0], KNOTS[-1])
    B = np.zeros((len(s), len(KNOTS)))
    for k in range(len(KNOTS)):
        if k > 0:
            m = (s >= KNOTS[k - 1]) & (s <= KNOTS[k])
            B[m, k] = (s[m] - KNOTS[k - 1]) / (KNOTS[k] - KNOTS[k - 1])
        if k + 1 < len(KNOTS):
            m = (s >= KNOTS[k]) & (s < KNOTS[k + 1])
            B[m, k] = (KNOTS[k + 1] - s[m]) / (KNOTS[k + 1] - KNOTS[k])
    B[s >= KNOTS[-1], -1] = 1.0
    return B

def ridge_ls(X, y, lam=1e-3):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)

def logistic(X, y, lam=1.0, iters=50):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        z = np.clip(X @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        g = X.T @ (p - y) + lam * w
        H = (X * (p * (1 - p))[:, None]).T @ X + lam * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-6:
            break
    return w

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    clean, files, base_logs = [], [], []
    while args:
        a = args.pop(0)
        if a == '--clean': clean.append(args.pop(0))
        elif a == '--base-log': base_logs.append(args.pop(0))
        elif a in ('--use-random', '--umode-log'): pass
        elif a == '--slope-bands': args.pop(0)
        else: files.append(a)
    if not clean:
        clean = [f for f in files if 'clean' in f]
    crow = [r for f in clean for r in load(f, allow_random=True)]  # vbar: mean values (the sampling bias hardly matters)
    rows = [r for f in files for r in load(f)]
    print(f"{len(rows)} positions ({len(crow)} clean)")
    # vbar(s): least squares of value on the hat basis over clean positions
    cs = np.log2([r[0] for r in crow]); cv = np.array([r[2] for r in crow])
    vb = ridge_ls(hats(cs), cv, lam=1.0)  # tiny ridge: only against singularity (sparse knots must not shrink to 0)
    # virtual checkpoints from fresh-game logs: (sum, max = 0 so every target counts, value = vbar, future 0, final max)
    CPS = [64, 128, 256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 10240, 12288, 14336, 16384, 18432, 20480, 22528,
           24576, 26624, 28672, 30720]
    nb = 0
    for path in base_logs:
        for line in open(path):
            if not line.startswith('game '):
                continue
            t = line.split()
            fmx, fsum = int(t[t.index('max') + 1]), int(t[t.index('sum') + 1])
            for c in CPS:
                if fsum >= c:
                    vb_c = float(hats(np.log2([c])) @ vb)
                    rows.append((float(c), 0, vb_c, 0.0, fmx, -1))
                    nb += 1
    if nb:
        print(f"{nb} virtual checkpoint rows from {len(base_logs)} logs")
    s = np.log2([r[0] for r in rows]); v = np.array([r[2] for r in rows])
    fut = np.array([r[3] for r in rows]); mx = np.array([r[1] for r in rows]); fm = np.array([r[4] for r in rows])
    B = hats(s)
    vbar = B @ vb
    # the value's relative deviation, clipped: a modest adjustment; acute danger (a value near 0 because the next tile
    # may end the game) is handled by the survival factor in build/analyze and must not be counted twice
    u = utrans(v / np.maximum(vbar, 1.0))
    # future score ratio c(s): future ~ c(s) * value
    real = np.array([r[5] != -1 for r in rows])
    X = B[real] * v[real][:, None]
    c = ridge_ls(X, fut[real], lam=1e-6 * float(np.sum(v[real] * v[real])))
    c = np.maximum(c, 0.0)  # a negative ratio (sparse last knot) would make the expected future negative
    model = {'knots': KNOTS, 'vbar': vb.tolist(), 'future_ratio': c.tolist(), 'targets': {}, 'umode': UMODE}
    print("future ratio c(s) at knots:", ' '.join(f"{2 ** k:.0f}:{x:.2f}" for k, x in zip(KNOTS, c)))
    gid = np.array([r[5] for r in rows])
    test = (gid % 5) == 0  # whole games held out (positions of one game share their outcome)
    for t in TARGETS:
        m = mx < (1 << t)
        if m.sum() < 20:
            continue
        y = (fm >= (1 << t)).astype(float)
        if y[m].min() == y[m].max():
            continue
        # base rates a_T(s) per knot, value slopes b_T: one per band of knots (default: below tile sum 16384 and from
        # 16384 on - late damage is less repairable; --slope-bands 12,14: also a band for 4096-16384), interpolated by
        # the hat functions exactly as build/analyze does (slope(s) = B(s) . b); constrained >= 0
        band_of = [sum(k >= c for c in BANDS) for k in KNOTS]
        nb_ = len(BANDS) + 1
        Xt = np.hstack([B] + [(u * B[:, [i for i, b in enumerate(band_of) if b == j]].sum(axis=1))[:, None]
                              for j in range(nb_)])
        tr, te = m & ~test, m & test

        def logloss(w, sel):
            p = 1 / (1 + np.exp(-np.clip(Xt[sel] @ w, -30, 30)))
            return float(-np.mean(y[sel] * np.log(np.maximum(p, 1e-9)) + (1 - y[sel]) * np.log(np.maximum(1 - p, 1e-9))))
        def fitw(sel, lam):
            w = logistic(Xt[sel], y[sel], lam=lam)
            neg = [k for k in range(len(KNOTS), Xt.shape[1]) if w[k] < 0]
            if neg:  # negative slopes are refit as 0
                keep = [i for i in range(Xt.shape[1]) if i not in neg]
                w0 = logistic(Xt[sel][:, keep], y[sel], lam=lam)
                w = np.zeros(Xt.shape[1]); w[keep] = w0
            return w
        # regularisation by 5-fold cross-validation over whole games (a single random split made the choice, and with
        # it the value slopes, unstable between runs)
        best = None
        for lam in (0.1, 1, 10, 100):
            lls = []
            for fold in range(5):
                te_f = m & ((gid % 5) == fold) & (gid != -1)
                tr_f = m & ~te_f
                if tr_f.sum() < 10 or te_f.sum() < 5 or y[tr_f].min() == y[tr_f].max():
                    continue
                lls.append((logloss(fitw(tr_f, lam), te_f), te_f.sum()))
            if not lls:
                break
            ll = sum(a * n for a, n in lls) / sum(n for _, n in lls)
            if best is None or ll < best[0]:
                best = (ll, lam)
        lam = best[1] if best else 10.0
        # cross-validated baselines on the same folds: a constant rate, and the base rates without the value term
        cv = {'const': [0.0, 0], 'base': [0.0, 0]}
        for fold in range(5):
            te_f = m & ((gid % 5) == fold) & (gid != -1)
            tr_f = m & ~te_f
            if tr_f.sum() < 10 or te_f.sum() < 5 or y[tr_f].min() == y[tr_f].max():
                continue
            pc = min(max(y[tr_f].mean(), 1e-6), 1 - 1e-6)
            cv['const'][0] += float(-np.sum(y[te_f] * math.log(pc) + (1 - y[te_f]) * math.log(1 - pc))); cv['const'][1] += te_f.sum()
            wb = logistic(B[tr_f], y[tr_f], lam=lam)
            pb = 1 / (1 + np.exp(-np.clip(B[te_f] @ wb, -30, 30)))
            cv['base'][0] += float(-np.sum(y[te_f] * np.log(np.maximum(pb, 1e-9)) + (1 - y[te_f]) * np.log(np.maximum(1 - pb, 1e-9))))
            cv['base'][1] += te_f.sum()
        w = fitw(m, lam)
        a = w[:len(KNOTS)]
        b = np.array([w[len(KNOTS) + band_of[i]] for i in range(len(KNOTS))])  # per-knot slopes for the C++ side
        base = y[m].mean()
        bt = y[te].mean() if te.sum() else base
        ll0 = float(-(bt * math.log(max(base, 1e-9)) + (1 - bt) * math.log(max(1 - base, 1e-9))))
        model['targets'][str(1 << t)] = {'a': a.tolist(), 'b': b.tolist()}
        held = (f"5-fold log-loss {best[0]:.4f} vs base rates only {cv['base'][0] / max(1, cv['base'][1]):.4f}, constant "
                f"{cv['const'][0] / max(1, cv['const'][1]):.4f} (lambda {lam:g})") if best else "too few for held-out"
        sl = ' / '.join(f"{w[len(KNOTS) + j]:.2f}" for j in range(nb_))
        print(f"  T={1 << t:6d}: {int(m.sum())} positions, base rate {base:.3f}, value slopes (bands {BANDS}) {sl}, {held}")
    json.dump(model, open(out, 'w'), indent=1)
    # the same model as plain text for build/analyze --calib (one array per line)
    with open(out.rsplit('.', 1)[0] + '.txt', 'w') as f:
        f.write('knots ' + ' '.join(map(str, KNOTS)) + '\n')
        f.write(f"umode {1 if UMODE == 'log' else 0}\n")
        f.write('vbar ' + ' '.join(f"{x:.6g}" for x in model['vbar']) + '\n')
        f.write('ratio ' + ' '.join(f"{x:.6g}" for x in model['future_ratio']) + '\n')
        for t, ab in model['targets'].items():
            f.write(f"target {t} " + ' '.join(f"{x:.6g}" for x in ab['a'] + ab['b']) + '\n')
    print("model ->", out, "and", out.rsplit('.', 1)[0] + '.txt')

if __name__ == '__main__':
    main()
