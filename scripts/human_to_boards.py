#!/usr/bin/env python3
"""One video of the human-data pipeline -> a board sequence for analyze --review (tile values, one board per line;
a blank line between segments, which the review skips as a frame pair it cannot connect).
usage: human_to_boards.py DECISIONS.jsonl [--max N] > game.txt"""
import json, sys
mx = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 0
prev_seg, n = None, 0
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get('undone'):
        continue
    if prev_seg is not None and r['segment'] != prev_seg:
        print()
    prev_seg = r['segment']
    print(' '.join(str(1 << int(c, 36)) if c != '0' else '0' for c in r['board']))
    n += 1
    if mx and n >= mx:
        break
