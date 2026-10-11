#!/usr/bin/env python3
"""Merge chunked rollout judge outputs (judge_cal6.sh: PREFIX_<start>.tsv, pos relative to the chunk) into one TSV
with pool-relative positions, for the single-file tools (judge_report.py, dispute_report.py).
usage: judge_merge.py OUT.tsv CHUNK.tsv ..."""
import re, sys

def main():
    out, files = sys.argv[1], sorted(sys.argv[2:], key=lambda p: int(re.search(r'_(\d{5})\.tsv$', p).group(1)))
    hdr = None
    with open(out, 'w') as f:
        for p in files:
            off = int(re.search(r'_(\d{5})\.tsv$', p).group(1))
            lines = open(p).read().rstrip('\n').split('\n')
            if hdr is None:
                hdr = lines[0]; f.write(hdr + '\n')
            for l in lines[1:]:
                c = l.split('\t'); c[0] = str(int(c[0]) + off); f.write('\t'.join(c) + '\n')
    print(f"{len(files)} chunks -> {out}")

if __name__ == '__main__':
    main()
