#!/usr/bin/env python3
"""Averages weight files with the same layout: OUT = mean of IN files (every stage).

usage: avg_weights.py OUT.w IN1.w IN2.w [...]
"""
import os
import sys
import numpy as np


def main():
    out, *ins = sys.argv[1:]
    with open(ins[0], "rb") as f:
        head = f.read(12)
        magic, plen, nstages = np.frombuffer(head, dtype="<u4")
        pats = f.read(plen)
        pos = f.tell()
    n = (os.path.getsize(ins[0]) - pos) // 4
    srcs = [np.memmap(p, dtype="<f4", mode="r", offset=pos, shape=(n,)) for p in ins]
    with open(out, "wb") as f:
        f.write(head)
        f.write(pats)
        chunk = 1 << 24
        for i in range(0, n, chunk):
            m = min(chunk, n - i)
            acc = np.zeros(m, dtype=np.float64)
            for s in srcs:
                acc += s[i:i + m]
            f.write((acc / len(srcs)).astype("<f4").tobytes())
    print(f"{out}: mean of {len(ins)} files, {nstages} stages")


if __name__ == "__main__":
    main()
