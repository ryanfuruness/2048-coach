#!/usr/bin/env python3
"""Fit the personal-odds model: for softmax players of temperature t (build/messy soft:t games recorded at tile-sum
checkpoints with --values), logit P(the player reaches T) = a_{t,T}(s) + b_{t,T} * u, s = log2 tile sum (hat
functions), u = value / vbar(s) - 1 with vbar from the same player's positions. Unlike the engine's odds, the value
is expected to matter: weaker players cannot repair damage. Prints held-out log-loss with and without u and writes a
text model for build/analyze (one 'personal T_TEMP TARGET a... b' line per pair, 'pknots' and 'pvbar T_TEMP ...').

usage: fit_personal.py OUT.txt results/personal/soft_*.tsv"""
import sys, math, re
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from fit_calib import hats, logistic, ridge_ls, KNOTS  # noqa: E402

def load(path):
    rows = []
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            if r.get('switch') != '2' or r.get('value') in (None, '', 'nan'):
                continue
            rows.append((float(r['sum']), int(r['max']), float(r['value']), int(r['final_max']),
                         hash((path, r['game'])) & 0xffff))
    return rows

def main():
    out = sys.argv[1]
    lines = ['pknots ' + ' '.join(map(str, KNOTS))]
    for path in sys.argv[2:]:
        t = float(re.search(r"(?:soft|hum)_([0-9.]+)\.tsv", path).group(1))  # soft:t players, or the human model (hm)
        rows = load(path)
        if len(rows) < 100:
            continue
        s = np.log2([r[0] for r in rows]); v = np.array([r[2] for r in rows])
        B = hats(s)
        vb = ridge_ls(B, v, lam=1.0)
        u = v / np.maximum(B @ vb, 1.0) - 1.0
        mx = np.array([r[1] for r in rows]); fm = np.array([r[3] for r in rows]); gid = np.array([r[4] for r in rows])
        test = gid % 5 == 0
        lines.append(f"pvbar {t:g} " + ' '.join(f"{x:.6g}" for x in vb))
        print(f"t={t:g}: {len(rows)} checkpoint positions, {len(set(gid))} games")
        for T in (128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768):
            m = mx < T
            y = (fm >= T).astype(float)
            if m.sum() < 50 or y[m].min() == y[m].max():
                continue
            res = {}
            for name, X in (('base', B), ('base+u', np.hstack([B, u[:, None]]))):
                w = logistic(X[m & ~test], y[m & ~test], lam=3.0)
                p = 1 / (1 + np.exp(-np.clip(X[m & test] @ w, -30, 30)))
                yt = y[m & test]
                res[name] = float(-np.mean(yt * np.log(np.maximum(p, 1e-9)) + (1 - yt) * np.log(np.maximum(1 - p, 1e-9))))
            w = logistic(np.hstack([B, u[:, None]])[m], y[m], lam=3.0)
            lines.append(f"personal {t:g} {T} " + ' '.join(f"{x:.6g}" for x in w[:-1]) + f" {max(0.0, w[-1]):.6g}")
            print(f"   T={T:6d}: n={int(m.sum())}, rate {y[m].mean():.3f}, held-out log-loss base {res['base']:.4f}, "
                  f"+u {res['base+u']:.4f}, slope {w[-1]:.2f}")
    open(out, 'w').write('\n'.join(lines) + '\n')
    print('model ->', out)

if __name__ == '__main__':
    main()
