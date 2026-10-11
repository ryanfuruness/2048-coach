#!/usr/bin/env python3
"""Merges per-game lines of `play` logs (without --quiet) into one summary.

usage: summarize.py chunk0.log [chunk1.log ...]
"""
import math
import re
import sys

PAT = re.compile(r"^game\s+\d+\s+score\s+(\d+)\s+max\s+(\d+)\s+moves\s+(\d+)\s+([\d.]+)s\s+([\d.]+) ms/move")


def main():
    scores, maxes, moves, secs = [], [], [], []
    for path in sys.argv[1:]:
        for line in open(path):
            m = PAT.match(line)
            if m:
                scores.append(int(m.group(1)))
                maxes.append(int(m.group(2)))
                moves.append(int(m.group(3)))
                secs.append(float(m.group(4)))
    n = len(scores)
    if not n:
        print("no games")
        return
    mean = sum(scores) / n
    sd = math.sqrt(sum((s - mean) ** 2 for s in scores) / (n - 1)) if n > 1 else 0
    srt = sorted(scores)
    print(f"{n} games  mean {mean:.0f} +- {sd / math.sqrt(n):.0f}  median {srt[n // 2]}  max {srt[-1]}  min {srt[0]}")
    print(f"avg moves {sum(moves) / n:.0f}  avg {1000 * sum(secs) / sum(moves):.2f} ms/move")
    for t in (2048, 4096, 8192, 16384, 32768, 65536, 131072):
        c = sum(1 for x in maxes if x >= t)
        if c == 0 and t > 32768:
            break
        p = c / n
        print(f"  reached {t:6d}: {100 * p:6.2f}% +- {100 * math.sqrt(p * (1 - p) / n):.2f}  ({c})")


if __name__ == "__main__":
    main()
