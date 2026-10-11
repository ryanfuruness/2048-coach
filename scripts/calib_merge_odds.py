#!/usr/bin/env python3
"""Replace the odds lines (knots, umode, vbar, ratio, target) of a full model with those of an odds-only fit, keeping
every other line (loss maps, warn, own-cost maps, the formation correction ocorr, ...) as it is (workstream cal9).
usage: calib_merge_odds.py FULL_MODEL.txt ODDS.txt OUT.txt"""
import sys

ODDS_KEYS = ('knots', 'umode', 'vbar', 'ratio', 'target')

def main():
    full, odds, out = sys.argv[1:4]
    new = [l for l in open(odds) if l.split() and l.split()[0] in ODDS_KEYS]
    keys = {l.split()[0] for l in new}
    assert {'knots', 'vbar', 'ratio', 'target'} <= keys, f"odds file lacks lines: {keys}"
    old = open(full).read().splitlines(keepends=True)
    knots_old = next((l.split()[1:] for l in old if l.split() and l.split()[0] == 'knots'), None)
    knots_new = next(l.split()[1:] for l in new if l.split()[0] == 'knots')
    if knots_old != knots_new:  # ocorr lines are per knot
        print(f"warning: knots differ ({knots_old} vs {knots_new}): ocorr lines may no longer match", file=sys.stderr)
    kept = [l for l in old if not (l.split() and l.split()[0] in ODDS_KEYS)]
    with open(out, 'w') as f:
        f.writelines(new + kept)
    print(f"{out}: {len(new)} odds lines from {odds} + {len(kept)} other lines from {full}")

if __name__ == '__main__':
    main()
