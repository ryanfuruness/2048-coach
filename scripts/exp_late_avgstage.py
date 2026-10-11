#!/usr/bin/env python3
"""Weight-averaged stage (an n-tuple network is linear in its weights, so averaging two networks' weights averages their
values: a two-network ensemble at the cost of one). Stage STAGE of BASE.w becomes (1 - W) * BASE[STAGE] + W * SRC[SRC_STAGE].
usage: exp_late_avgstage.py BASE.w STAGE SRC.w SRC_STAGE W OUT.w"""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from splice_stage import open_w  # noqa: E402

base, stage, src, sstage, w, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
(magic, plen, ns, pats), bw, size = open_w(base)
(_, _, _, spats), sw, _ = open_w(src)
assert pats == spats, "pattern mismatch"
chunk = 1 << 24
with open(out, "wb") as g:
    g.write(np.array([magic, plen, ns], dtype="<u4").tobytes())
    g.write(pats)
    for st in range(ns):
        for i in range(0, size, chunk):
            a = np.asarray(bw[st * size + i: st * size + min(i + chunk, size)])
            if st == stage:
                b = np.asarray(sw[sstage * size + i: sstage * size + min(i + chunk, size)])
                a = ((1 - w) * a + w * b).astype("<f4")
            g.write(a.tobytes())
print(f"{out}: stage {stage} = {1 - w:g} x {base} + {w:g} x {src} (stage {sstage})")
