#!/usr/bin/env python3
"""Reliability check of the odds model: positions binned by predicted P(reach T) (the model's formula, as in calib.h:
logit = a_T(s) + b_T(s) * u, chain rule over targets not applied) vs the observed share that reached T.
Rows: unbiased engine-future rows (checkpoints, handovers) of the given files, games split by id (test = id % 5 == 0).
usage: calib_check.py MODEL.json FILE.tsv ..."""
import json, math, sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from fit_calib import hats  # noqa: E402

def main():
    m = json.load(open(sys.argv[1]))
    vb = np.array(m['vbar'])
    rows = []
    for path in sys.argv[2:]:
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                if r.get('engine_future') != '1' or r['switch'] not in ('1', '2') or r.get('value') in (None, '', 'nan'):
                    continue
                rows.append((float(r['sum']), int(r['max']), float(r['value']), int(r['final_max'])))
    s = np.log2([r[0] for r in rows]); B = hats(s)
    v = np.array([r[2] for r in rows]); ratio = v / np.maximum(B @ vb, 1)
    # the model's value term (fit_calib.py UMODE; models without the key used the clipped form)
    u = np.log(np.maximum(ratio, 0.01)) if m.get('umode') == 'log' else np.clip(ratio - 1, -0.3, 0.3)
    for T in ('16384', '32768'):
        if T not in m['targets']: continue
        a, b = np.array(m['targets'][T]['a']), np.array(m['targets'][T]['b'])
        sel = np.array([r[1] < int(T) for r in rows])
        z = B @ a + (B @ b) * u
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        y = np.array([float(r[3] >= int(T)) for r in rows])
        print(f"T={T}: {int(sel.sum())} positions")
        edges = [0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 1.01]
        for lo, hi in zip(edges, edges[1:]):
            k = sel & (p >= lo) & (p < hi)
            if k.sum() >= 20:
                se = math.sqrt(max(y[k].mean() * (1 - y[k].mean()), 1e-9) / k.sum())
                print(f"   predicted {lo:4.2f}-{hi:4.2f}: n={int(k.sum()):5d}  mean predicted {p[k].mean():.3f}  observed {y[k].mean():.3f} +- {se:.3f}")

if __name__ == '__main__':
    main()
