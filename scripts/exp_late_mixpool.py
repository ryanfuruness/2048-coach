#!/usr/bin/env python3
"""Mixed start pool: BASE.bin + EXTRA.bin repeated so that a share F of uniform draws comes from EXTRA.
usage: exp_late_mixpool.py BASE.bin EXTRA.bin F OUT.bin"""
import sys
import numpy as np
base = np.fromfile(sys.argv[1], dtype='<u8')
extra = np.fromfile(sys.argv[2], dtype='<u8')
f = float(sys.argv[3])
reps = max(1, int(round(f / (1 - f) * len(base) / len(extra))))
out = np.concatenate([base] + [extra] * reps)
out.tofile(sys.argv[4])
print(f"{len(base)} + {reps} x {len(extra)} = {len(out)} boards, extra share {reps * len(extra) / len(out):.3f}")
