#!/usr/bin/env python3
"""Writes a weight file made of selected stages of another one.

usage: select_stages.py IN.w OUT.w S0,S1,...   (stage i of OUT = stage S_i of IN)
"""
import sys
import numpy as np


def main():
    src, dst, sel = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")]
    with open(src, "rb") as f:
        magic, plen, ns = np.frombuffer(f.read(12), dtype="<u4")
        pats = f.read(plen)
        pos = f.tell()
    size = len(pats.split()) * 16 ** 6
    w = np.memmap(src, dtype="<f4", mode="r", offset=pos, shape=(ns * size,))
    chunk = 1 << 24
    with open(dst, "wb") as g:
        g.write(np.array([magic, plen, len(sel)], dtype="<u4").tobytes())
        g.write(pats)
        for st in sel:
            assert 0 <= st < ns
            for i in range(0, size, chunk):
                g.write(np.asarray(w[st * size + i: st * size + min(i + chunk, size)]).tobytes())
    print(f"{dst}: stages {sel} of {src}")


if __name__ == "__main__":
    main()
