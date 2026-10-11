#!/usr/bin/env python3
"""Odd-but-legal positions for the odds validation (workstream anypos, 2026-10-07): boards a user could enter that look
nothing like human or engine play, per category x stage (largest tile 256 .. 16384), plus sane snake controls.
Real tile ranks (rank r = tile 2^r, 0 = empty), cell 0 = top-left, row by row; every board has a legal move.
usage: anypos_gen.py [--seed S] [--per K] OUT.tsv OUT.bin     (TSV: idx cat stage hex; BIN: engine boards, uint64 LE)"""
import argparse, random, struct, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from fuzz_gen import slide_left, transform  # noqa: E402

PATH = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]  # the snake path from the top-left corner
CORNERS, CENTER = [0, 3, 12, 15], [5, 6, 9, 10]
EDGES = [1, 2, 4, 7, 8, 11, 13, 14]

def nbrs(c):
    r, q = divmod(c, 4)
    return [rr * 4 + qq for rr, qq in ((r - 1, q), (r + 1, q), (r, q - 1), (r, q + 1)) if 0 <= rr < 4 and 0 <= qq < 4]

def legal(b):
    for j in range(4):  # four directions via symmetries: left on rows of transform j
        t = transform(b, [0, 1, 4, 5][j])
        for r in range(4):
            line = t[4 * r:4 * r + 4]
            if slide_left(line)[0] != line:
                return True
    return False

def small(rng, hi):  # a small tile, 2-heavy
    hi = max(1, hi)
    return min(hi, 1 + int(rng.expovariate(1.2)))

def fill(rng, b, cells, k, hi):
    cells = [c for c in cells if b[c] == 0]
    rng.shuffle(cells)
    for c in cells[:k]:
        b[c] = small(rng, hi)

def gen(cat, R, rng):
    b = [0] * 16
    if cat == 'snake':  # control: a sane decreasing chain along the snake from the corner
        k = rng.randint(3, min(8, R - 2))
        r = R
        for i in range(k):
            b[PATH[i]] = r
            r -= 1 if rng.random() < 0.8 else 2
            if r < 2: break
        fill(rng, b, PATH[k:], rng.randint(3, 8), min(6, R - k))
    elif cat == 'center':
        c = rng.choice(CENTER)
        b[c] = R
        for i, n in enumerate(rng.sample(nbrs(c), 3)):
            b[n] = R - 1 - i
        fill(rng, b, range(16), rng.randint(5, 9), min(7, R - 4))
    elif cat == 'edge':
        c = rng.choice(EDGES)
        b[c] = R
        nb = [n for n in nbrs(c) if n in EDGES or n in CORNERS]
        for i, n in enumerate(nb[:2]):
            b[n] = R - 1 - i
        fill(rng, b, range(16), rng.randint(5, 9), min(7, R - 3))
    elif cat == 'two_corners':
        a, z = rng.sample(CORNERS, 2)
        b[a], b[z] = R, R - 1
        for c, r0 in ((a, R - 2), (z, R - 3)):
            n = [x for x in nbrs(c) if b[x] == 0]
            if n and r0 > 1: b[rng.choice(n)] = r0
        fill(rng, b, range(16), rng.randint(5, 9), min(7, R - 4))
    elif cat == 'checker':  # the biggest tile in its corner, 2s and 4s alternating, a few holes
        b[0] = R
        for c in range(1, 16):
            b[c] = 1 + ((c // 4 + c % 4) % 2)
        for c in rng.sample(range(1, 16), rng.randint(2, 5)):
            b[c] = 0
    elif cat == 'full_merges':  # a full board (0-1 empty) with a sane chain and some equal neighbours
        k = rng.randint(4, min(8, R - 1))
        for i in range(k): b[PATH[i]] = max(1, R - i)
        for c in PATH[k:]: b[c] = small(rng, min(6, R - k))
        for _ in range(rng.randint(1, 3)):  # equal pairs
            c = rng.choice(PATH[k:])
            n = rng.choice(nbrs(c))
            if n not in PATH[:k]: b[n] = b[c]
        if rng.random() < 0.5: b[rng.choice(PATH[k:])] = 0
    elif cat == 'scattered':
        cells = rng.sample(range(16), 5)
        for i, c in enumerate(cells): b[c] = max(1, R - i)
        fill(rng, b, range(16), rng.randint(4, 8), min(6, R - 5))
    elif cat == 'reversed':  # a chain along the snake that GROWS away from the corner: the biggest tile inside
        k = rng.randint(4, min(7, R - 1))
        for i in range(k): b[PATH[i]] = R - (k - 1 - i)
        fill(rng, b, PATH[k:], rng.randint(3, 7), min(6, R - k))
    elif cat == 'typewriter':  # decreasing in reading order, every row left to right: the chain breaks at row ends
        k = rng.randint(5, min(9, R - 1))
        for i in range(k): b[i] = R - i
        fill(rng, b, range(k, 16), rng.randint(2, 6), min(5, R - k))
    elif cat == 'sparse':  # a big tile and a handful of small ones
        b[rng.choice(CORNERS if rng.random() < 0.7 else range(16))] = R
        fill(rng, b, range(16), rng.randint(2, 4), 3)
    elif cat == 'heavy_sum':  # far more big tiles than a real game of that largest tile could have
        b[0] = R
        cells = rng.sample(range(1, 16), rng.randint(4, 7))
        for c in cells: b[c] = R - rng.choice((1, 1, 2, 2, 3))
        fill(rng, b, range(16), rng.randint(2, 5), min(5, R - 4))
    elif cat == 'near_corner':  # a sane chain, but the biggest tile one cell away from its corner
        k = rng.randint(3, min(6, R - 2))
        for i in range(k): b[PATH[i + 1]] = R - i
        b[0] = small(rng, 3)
        fill(rng, b, PATH[k + 1:], rng.randint(3, 7), min(6, R - k))
    elif cat == 'twin_max':  # two copies of the biggest tile far apart
        a, z = rng.sample(CORNERS, 2)
        b[a] = b[z] = R
        fill(rng, b, range(16), rng.randint(5, 9), min(6, R - 3))
    elif cat == 'diagonal':  # big tiles along a diagonal
        for i, c in enumerate([0, 5, 10, 15][:rng.randint(3, 4)]): b[c] = R - i
        fill(rng, b, range(16), rng.randint(5, 9), min(6, R - 4))
    elif cat == 'random':
        b[rng.randrange(16)] = R
        for c in range(16):
            if b[c] == 0 and rng.random() < rng.uniform(0.5, 0.9): b[c] = rng.randint(1, R - 1)
    j = rng.randrange(8)  # a random orientation: the odds must not depend on it
    return transform(b, j)

CATS = ['snake', 'center', 'edge', 'two_corners', 'checker', 'full_merges', 'scattered', 'reversed', 'typewriter',
        'sparse', 'heavy_sum', 'random']
NEW_CATS = ['near_corner', 'twin_max', 'diagonal']  # held-out categories (test set only)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--per', type=int, default=6)
    ap.add_argument('--stages', default='8-14')
    ap.add_argument('--with-new', action='store_true', help='add the held-out categories')
    ap.add_argument('out_tsv')
    ap.add_argument('out_bin')
    a = ap.parse_args()
    rng = random.Random(a.seed)
    rows = []
    lo, hi = (int(x) for x in a.stages.split('-'))
    for R in range(lo, hi + 1):  # 256 .. 16384
        for cat in CATS + (NEW_CATS if a.with_new else []):
            got, tries = 0, 0
            while got < a.per and tries < 1000:
                tries += 1
                b = gen(cat, R, rng)
                if max(b) != R or not legal(b) or any(v > 15 for v in b) or (cat != 'twin_max' and b.count(R) > 1): continue
                rows.append((cat, R, b))
                got += 1
    with open(a.out_tsv, 'w') as f, open(a.out_bin, 'wb') as fb:
        f.write('idx\tcat\tstage\thex\n')
        for i, (cat, R, b) in enumerate(rows):
            hx = ''.join('0123456789abcdef'[v] for v in b)
            f.write(f'{i}\t{cat}\t{R}\t{hx}\n')
            x = 0
            for c in range(16): x |= b[c] << (4 * c)
            fb.write(struct.pack('<Q', x))
    print(f'{len(rows)} positions -> {a.out_tsv}, {a.out_bin}', file=sys.stderr)

if __name__ == '__main__':
    main()
