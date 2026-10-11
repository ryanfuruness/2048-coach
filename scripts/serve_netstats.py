#!/usr/bin/env python3
"""Per stage and pattern statistics of a float n-tuple weight file (workstream serve, 2026-10-07): the share of
entries still at their initial value (the most common value of the table, exactly), value ranges and percentiles of
the trained entries, and how much an 8-bit quantization (uniform per table, or a 256-level codebook per table) would
move the trained values.
usage: serve_netstats.py WEIGHTS.w [--sample N]"""
import sys, struct
import numpy as np

def open_net(path):
    with open(path, 'rb') as f:
        magic, plen, nst = struct.unpack('<III', f.read(12))
        assert magic == 0x32303438, 'bad weight file'
        pats = f.read(plen).decode().split()
    off = 12 + plen
    per = 16 ** len(pats[0])
    w = np.memmap(path, dtype='<f4', mode='r', offset=off, shape=(nst, len(pats), per))
    return pats, nst, w

def main():
    path = sys.argv[1]
    pats, nst, w = open_net(path)
    print(f"{path}: {nst} stages x {len(pats)} patterns x {w.shape[2]:,} entries ({w.size * 4 / 1e9:.2f} GB float)")
    print("stage pat  init_value  untouched  trained  min_trained  max_trained  |w-init| p50   p99    max   "
          "int8_uniform_rms  int8_codebook_rms (relative to the trained values' rms)")
    tot_trained = 0
    for s in range(nst):
        st_tr = 0
        for p in range(len(pats)):
            t = np.asarray(w[s, p])
            vals, cnt = np.unique(t[::97], return_counts=True)  # mode estimate on a sample
            init = vals[np.argmax(cnt)]
            tr = t[t != init]
            n_tr = tr.size
            st_tr += n_tr
            if n_tr:
                d = np.abs(tr - init)
                rms = float(np.sqrt(np.mean(tr.astype(np.float64) ** 2)))
                # uniform int8 over the table's range (symmetric), and a 256-level quantile codebook
                m = float(np.max(np.abs(tr)))
                sc = m / 127.0 if m > 0 else 1.0
                qu = np.clip(np.rint(tr / sc), -127, 127) * sc
                eu = float(np.sqrt(np.mean((qu - tr).astype(np.float64) ** 2)))
                qs = np.quantile(tr[:: max(1, n_tr // 2000000)], np.linspace(0, 1, 256))
                idx = np.clip(np.searchsorted(qs, tr), 1, 255)
                lo, hi = qs[idx - 1], qs[idx]
                qc = np.where(np.abs(tr - lo) <= np.abs(hi - tr), lo, hi)
                ec = float(np.sqrt(np.mean((qc - tr).astype(np.float64) ** 2)))
                print(f"{s:5d} {p:3d} {init:11.3f} {100 * (1 - n_tr / t.size):8.2f}% {n_tr:10,d} {tr.min():12.1f} "
                      f"{tr.max():12.1f} {np.percentile(d, 50):8.1f} {np.percentile(d, 99):8.1f} {d.max():8.1f} "
                      f"{eu / rms:12.5f} {ec / rms:16.5f}")
            else:
                print(f"{s:5d} {p:3d} {init:11.3f}  100.00%          0")
        tot_trained += st_tr
        print(f"  stage {s}: trained entries {st_tr:,} of {w.shape[1] * w.shape[2]:,} ({100 * st_tr / (w.shape[1] * w.shape[2]):.1f}%)")
    print(f"all: trained {tot_trained:,} of {w.size:,} ({100 * tot_trained / w.size:.1f}%)")

if __name__ == '__main__':
    main()
