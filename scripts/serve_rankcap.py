#!/usr/bin/env python3
"""Rank caps of a float n-tuple weight file (workstream serve): for each stage, the largest tile rank (nibble) that
any TRAINED entry (value != the table's initial value) uses in any of its 6 cells, and the share of trained entries
that a cap R (all nibbles < R) would keep. Re-indexing a stage's tables in base R instead of 16 is lossless when every
trained entry fits. usage: serve_rankcap.py WEIGHTS.w"""
import sys, struct
import numpy as np

def main():
    path = sys.argv[1]
    with open(path, 'rb') as f:
        magic, plen, nst = struct.unpack('<III', f.read(12))
        pats = f.read(plen).decode().split()
    per = 16 ** len(pats[0])
    w = np.memmap(path, dtype='<f4', mode='r', offset=12 + plen, shape=(nst, len(pats), per))
    idx = np.arange(per, dtype=np.uint32)
    # max nibble of every index (6 nibbles)
    mx = np.zeros(per, dtype=np.uint8)
    for k in range(len(pats[0])):
        mx = np.maximum(mx, ((idx >> (4 * k)) & 0xF).astype(np.uint8))
    print(f"{path}: {nst} stages, {len(pats)} patterns")
    for s in range(nst):
        hist = np.zeros(16, dtype=np.int64)
        for p in range(len(pats)):
            t = np.asarray(w[s, p])
            vals, cnt = np.unique(t[::97], return_counts=True)
            init = vals[np.argmax(cnt)]
            tr = t != init
            hist += np.bincount(mx[tr], minlength=16)
        n = hist.sum()
        if n == 0:
            print(f"  stage {s}: untrained"); continue
        top = int(np.nonzero(hist)[0].max())
        cum = np.cumsum(hist) / n
        caps = '  '.join(f"R={r}: {100 * cum[r - 1]:.4f}%" for r in range(max(10, top - 3), top + 2) if r <= 16)
        print(f"  stage {s}: max nibble of a trained entry = {top} (lossless cap R = {top + 1}); trained entries kept "
              f"by cap R: {caps}; entries with nibble {top}: {hist[top]:,}")

if __name__ == '__main__':
    main()
