# Relabel pool positions one rank up for the tiles >= MINR (e.g. 16384-phase positions -> 32768-phase positions):
# [16384 8192 + small] -> [32768 16384 + small]. Keeps only boards whose relabeled ranks fit (<= 15) and whose small
# tiles stay below MINR.
import sys, numpy as np
src, dst, minr = sys.argv[1], sys.argv[2], int(sys.argv[3])
a = np.fromfile(src, dtype='<u8')
cells = np.stack([(a >> np.uint64(4 * i)) & np.uint64(0xF) for i in range(16)], axis=1).astype(np.int64)
up = np.where(cells >= minr, cells + 1, cells)
ok = (up.max(axis=1) <= 15)
up = up[ok]
out = np.zeros(len(up), dtype=np.uint64)
for i in range(16): out |= (up[:, i].astype(np.uint64) << np.uint64(4 * i))
out.tofile(dst)
sums = (np.where(up > 0, 1 << up, 0)).sum(axis=1)
print(f"{src}: {len(a)} -> {len(out)} positions, sum min/median/max {sums.min()}/{int(np.median(sums))}/{sums.max()}")
print("max-rank histogram:", np.bincount(up.max(axis=1), minlength=16)[13:])
