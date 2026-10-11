#!/usr/bin/env python3
"""Neutralises never-trained weights of optimistically initialised stages, for search.

usage: neutralize.py IN.w OUT.w STAGE:CKPT [STAGE:CKPT ...] [--value V] [--min-a A] [--fresh S,S,...]

Optimistic initialisation leaves every weight that training never touched at its
initial value. A greedy (1-ply) player rarely meets such weights, but a search
evaluates many hypothetical boards and is drawn toward exactly those overvalued,
unexplored configurations. For each STAGE:CKPT pair, weights whose TC accumulator
|error| sum is 0 in the checkpoint (never updated) are set to V (default 0); with
--min-a A, also the weights whose |error| sum is below A (barely trained: still close
to their optimistic initial value).
Stages listed in --fresh (never trained at all) are set to V entirely.
"""
import sys
import numpy as np

HDR_MAGIC = 0x32303438


def main():
    args = sys.argv[1:]
    value = 0.0
    min_a = 0.0
    fresh = set()
    if "--min-a" in args:
        i = args.index("--min-a")
        min_a = float(args[i + 1])
        del args[i:i + 2]
    if "--value" in args:
        i = args.index("--value")
        value = float(args[i + 1])
        del args[i:i + 2]
    if "--fresh" in args:
        i = args.index("--fresh")
        fresh = {int(x) for x in args[i + 1].split(",") if x}
        del args[i:i + 2]
    src, dst, *pairs = args
    ckpts = {int(p.split(":", 1)[0]): p.split(":", 1)[1] for p in pairs}
    with open(src, "rb") as f:
        magic, plen, nstages = np.frombuffer(f.read(12), dtype="<u4")
        assert magic == HDR_MAGIC
        pats = f.read(plen)
        data_pos = f.tell()
    npat = len(pats.split())
    stage_size = npat * 16 ** 6  # all patterns are 6-tuples here
    for p in pats.split():
        assert len(p) == 6, "only 6-tuples supported"
    w = np.memmap(src, dtype="<f4", mode="r", offset=data_pos, shape=(nstages * stage_size,))
    with open(dst, "wb") as out:
        out.write(np.array([magic, plen, nstages], dtype="<u4").tobytes())
        out.write(pats)
        chunk = 1 << 24
        for st in range(nstages):
            ck = None
            if st in ckpts:
                ck = np.memmap(ckpts[st], dtype="<f4", mode="r", shape=(stage_size, 3))
            changed = 0
            for i in range(0, stage_size, chunk):
                n = min(chunk, stage_size - i)
                x = np.array(w[st * stage_size + i: st * stage_size + i + n])
                if st in fresh:
                    x[:] = value
                    changed += n
                elif ck is not None:
                    a = ck[i:i + n, 2]
                    mask = (a == 0) | (a < min_a)
                    x[mask] = value
                    changed += int(mask.sum())
                out.write(x.astype("<f4").tobytes())
            if changed:
                print(f"stage {st}: {changed} of {stage_size} weights set to {value}")


if __name__ == "__main__":
    main()
