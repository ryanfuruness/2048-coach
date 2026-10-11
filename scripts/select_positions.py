#!/usr/bin/env python3
"""Select positions from build/messy TSV files into a pool .bin (8-byte boards, cell 0 in the low nibble).
usage: select_positions.py OUT.bin [--where 'EXPR'] [--max N] [--seed S] FILE.tsv ...
EXPR is a Python expression over the row's columns (as numbers where possible), e.g. "switch == 1 and max >= 256".
With --max, a uniform random subset of the matching rows is kept (file order otherwise preserved)."""
import sys, random, struct

def main():
    args = sys.argv[1:]
    out = args.pop(0)
    where, mx, seed = 'True', None, 1
    files = []
    while args:
        a = args.pop(0)
        if a == '--where': where = args.pop(0)
        elif a == '--max': mx = int(args.pop(0))
        elif a == '--seed': seed = int(args.pop(0))
        else: files.append(a)
    rows = []
    for path in files:
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                vals = line.rstrip('\n').split('\t')
                r = {}
                for k, v in zip(hdr, vals):
                    try: r[k] = int(v)
                    except ValueError:
                        try: r[k] = float(v)
                        except ValueError: r[k] = v
                r['board'] = vals[hdr.index('board')]
                if eval(where, {}, r):
                    rows.append(r['board'])
    if mx is not None and len(rows) > mx:
        random.seed(seed)
        keep = sorted(random.sample(range(len(rows)), mx))
        rows = [rows[i] for i in keep]
    with open(out, 'wb') as f:
        for h in rows:
            b = 0
            for i, c in enumerate(h):
                b |= int(c, 16) << (4 * i)
            f.write(struct.pack('<Q', b))
    print(f"{len(rows)} positions -> {out}")

if __name__ == '__main__':
    main()
