#!/usr/bin/env python3
"""Averages one stage over several weight files (same patterns, same stage count).

usage: avg_stages.py [--skip-value V] OUT.w STAGE IN1.w IN2.w ...   (other stages copied from IN1)
  --skip-value V: a weight still exactly at V (the optimistic initial value: never trained in that network) is left out
                  of its average (averaging an untouched 5000 with trained values would keep rare patterns optimistic)

An n-tuple network is linear in its weights, so the network with averaged weights computes exactly the mean of the
networks' values: a free ensemble (same evaluation cost). Meaningful for networks on the same value scale (same recipe,
different seeds).
"""
import sys
import numpy as np


def open_w(path):
    with open(path, "rb") as f:
        magic, plen, ns = np.frombuffer(f.read(12), dtype="<u4")
        pats = f.read(plen)
        pos = f.tell()
    size = len(pats.split()) * 16 ** 6
    return (magic, plen, ns, pats), np.memmap(path, dtype="<f4", mode="r", offset=pos, shape=(ns * size,)), size


def main():
    args = sys.argv[1:]
    skip = None
    if args[0] == "--skip-value":
        skip = float(args[1])
        args = args[2:]
    out, stage, ins = args[0], int(args[1]), args[2:]
    hdrs, ws = [], []
    for p in ins:
        h, w, size = open_w(p)
        hdrs.append(h)
        ws.append(w)
    magic, plen, ns, pats = hdrs[0]
    assert all(h[3] == pats and h[2] == ns for h in hdrs), "pattern or stage-count mismatch"
    chunk = 1 << 24
    with open(out, "wb") as g:
        g.write(np.array([magic, plen, ns], dtype="<u4").tobytes())
        g.write(pats)
        for st in range(ns):
            off = st * size
            for i in range(0, size, chunk):
                j = min(i + chunk, size)
                if st == stage:
                    acc = np.zeros(j - i, dtype=np.float64)
                    cnt = np.zeros(j - i, dtype=np.float64)
                    for w in ws:
                        x = np.asarray(w[off + i: off + j], dtype=np.float64)
                        m = np.ones(j - i) if skip is None else (x != skip)
                        acc += x * m
                        cnt += m
                    avg = np.where(cnt > 0, acc / np.maximum(cnt, 1), skip if skip is not None else 0.0)
                    g.write(avg.astype("<f4").tobytes())
                else:
                    g.write(np.asarray(ws[0][off + i: off + j]).tobytes())
    print(f"{out}: stage {stage} = mean of {len(ins)} files")


if __name__ == "__main__":
    main()
