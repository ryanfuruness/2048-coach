#!/usr/bin/env python3
"""Replaces one stage of a multi-stage weight file with a stage from another file.

usage: splice_stage.py BASE.w STAGE SRC.w SRC_STAGE OUT.w
Both files must use the same patterns.
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
    base, stage, src, sstage, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
    (magic, plen, ns, pats), bw, size = open_w(base)
    (_, _, _, spats), sw, _ = open_w(src)
    assert pats == spats, "pattern mismatch"
    chunk = 1 << 24
    with open(out, "wb") as g:
        g.write(np.array([magic, plen, ns], dtype="<u4").tobytes())
        g.write(pats)
        for st in range(ns):
            srcw, off = (sw, sstage * size) if st == stage else (bw, st * size)
            for i in range(0, size, chunk):
                g.write(np.asarray(srcw[off + i: off + min(i + chunk, size)]).tobytes())
    print(f"{out}: stage {stage} from {src} (stage {sstage}), others from {base}")


if __name__ == "__main__":
    main()
