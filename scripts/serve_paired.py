#!/usr/bin/env python3
"""Paired comparison of build/play logs (same starts and seeds): reach rate of a tile sum, game by game.
usage: serve_paired.py STOP_SUM REF.log,REF2.log,... CAND.log,CAND2.log,...  (lists matched by position)"""
import re, sys, math

def games(f, stop):
    g = {}
    for line in open(f):
        m = re.match(r'game\s+(\d+)\s+score\s+(\d+)\s+max\s+(\d+).*sum\s+(\d+)', line)
        if m:
            g[int(m.group(1))] = (int(m.group(2)), int(m.group(4)) >= stop)
    return g

def main():
    stop = int(sys.argv[1])
    refs, cands = sys.argv[2].split(','), sys.argv[3].split(',')
    d, ra, rb, same, sa, sb = [], 0, 0, 0, 0, 0
    for fr, fc in zip(refs, cands):
        a, b = games(fr, stop), games(fc, stop)
        for i in sorted(set(a) & set(b)):
            d.append(int(b[i][1]) - int(a[i][1]))
            ra += a[i][1]; rb += b[i][1]; same += a[i] == b[i]; sa += a[i][0]; sb += b[i][0]
    n = len(d); m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    print(f"{n} paired games: reference {100 * ra / n:.2f}%  candidate {100 * rb / n:.2f}%  paired diff {100 * m:+.2f} "
          f"+- {100 * sd / math.sqrt(n):.2f} points; identical games {same}; mean score {sa / n:,.0f} vs {sb / n:,.0f}")

if __name__ == '__main__':
    main()
