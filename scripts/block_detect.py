#!/usr/bin/env python3
"""The block-formation detector of src/block.h (blk::block_formation with the defaults k=4, gap=6, core_gap=3,
moves_ahead=0), for the Python fits: the 4 biggest tiles (with multiplicity) in one 3x2 block touching a corner, the
4th at most 6 ranks below the biggest; or the 3 biggest in a 2x2 square at a corner, the 3rd at most 3 ranks below.
build/analyze uses it only for boards with a real 16384 or more (block_position in src/analyze.cpp).
usage (test): block_detect.py "TILES..." -> True / False"""
import math, sys

PLACEMENTS = [(0, 1, 2, 4, 5, 6), (1, 2, 3, 5, 6, 7), (8, 9, 10, 12, 13, 14), (9, 10, 11, 13, 14, 15),
              (0, 1, 4, 5, 8, 9), (4, 5, 8, 9, 12, 13), (2, 3, 6, 7, 10, 11), (6, 7, 10, 11, 14, 15)]
SQUARES = [(0, 1, 4, 5), (2, 3, 6, 7), (8, 9, 12, 13), (10, 11, 14, 15)]


def ranks_of_tiles(tiles):
    """16 tile values (0 = empty) -> ranks (2 -> 1, 4 -> 2, ...)"""
    return [int(round(math.log2(t))) if t else 0 for t in tiles]


def block_placement(r, k=4, gap=6):
    s = sorted(r, reverse=True)
    if s[k - 1] <= 0 or s[k - 1] < s[0] - gap:
        return -1
    for p, cells in enumerate(PLACEMENTS):
        t = sorted((r[c] for c in cells), reverse=True)
        if t[:k] == s[:k]:
            return p
    return -1


def block_core(r, core_gap=3):
    s = sorted(r, reverse=True)
    if core_gap < 0 or s[2] <= 0 or s[2] < s[0] - core_gap:
        return False
    return any(sorted((r[c] for c in q), reverse=True)[:3] == s[:3] for q in SQUARES)


def block_formation(r):
    """r: 16 real ranks (cell 0 = top-left)"""
    return block_placement(r) >= 0 or block_core(r)


def block_position(tiles):
    """As build/analyze: the detector, only with a real 16384 or more on the board."""
    return max(tiles) >= 16384 and block_formation(ranks_of_tiles(tiles))


if __name__ == '__main__':
    tiles = [int(x) for x in sys.argv[1].replace('/', ' ').split()]
    print(block_position(tiles))
