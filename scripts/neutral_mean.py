#!/usr/bin/env python3
"""Sets barely-trained weights of one stage to their tuple's mean trained value ("neutral" instead of optimistic).

usage: neutral_mean.py IN.w STAGE CKPT OUT.w MAX_A [TRAINED_A]
Weights whose TC |error| sum (from CKPT, the stage's checkpoint) is <= MAX_A are set to the mean value of the same
tuple's weights whose |error| sum exceeds TRAINED_A (default 1e6). Optimistic initialisation leaves most weights
untouched at 5000/feature; a search then prefers positions made of unvisited features.
"""
import sys
import numpy as np

src, stage, ckpt, out, max_a = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], float(sys.argv[5])
trained_a = float(sys.argv[6]) if len(sys.argv) > 6 else 1e6
with open(src, 'rb') as f:
    magic, plen, ns = np.frombuffer(f.read(12), dtype='<u4')
    pats = f.read(plen)
    hdr = 12 + plen
ntup = len(pats.split())
tsize = 16 ** 6
size = ntup * tsize
w = np.fromfile(src, dtype='<f4', offset=hdr)
assert len(w) == ns * size
ck = np.memmap(ckpt, dtype='<f4', mode='r')
assert len(ck) == 3 * size
st = w[stage * size:(stage + 1) * size]
for t in range(ntup):
    sl = slice(t * tsize, (t + 1) * tsize)
    a = np.asarray(ck[2::3][sl])
    ws = st[sl]
    good = a > trained_a
    mean = float(ws[good].mean()) if good.any() else 0.0
    low = a <= max_a
    ws[low] = mean
    print(f"tuple {t}: {good.mean()*100:5.1f}% trained (mean {mean:8.1f}), {low.mean()*100:5.1f}% set to it")
w[stage * size:(stage + 1) * size] = st
with open(out, 'wb') as f:
    f.write(np.array([magic, plen, ns], dtype='<u4').tobytes())
    f.write(pats)
    w.tofile(f)
print("wrote", out)
