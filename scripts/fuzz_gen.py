#!/usr/bin/env python3
"""Edge-case positions for the analysis engine (workstream fuzz, 2026-10-06): random legal boards at all densities,
full / one-move / game-over boards, only 2s or 4s, several big tiles, the biggest tile off its corner at 16384+,
formations in every orientation, 65536 / 131072 tiles and very large sums, impossible boards, table formations
(k5/k6 snakes), real human positions as controls. Boards are real tile ranks (rank r = tile 2^r, 0 = empty), cell 0 =
top-left, row by row.
usage: fuzz_gen.py [--seed S] [--n N] [--sym-groups G] [--tables] [--human FILE] > boards.jsonl
Each line: {"cat": category, "ranks": [16 ints], "group": id of its symmetry group or -1, "sym": 0-7}"""
import argparse, json, random

# ---- board helpers (real ranks, no 4-bit limit) ----
def rows(b): return [b[4 * r:4 * r + 4] for r in range(4)]

def slide_left(line):
    """2048 rule on one line of ranks: returns (new line, reward in points)."""
    t = [v for v in line if v]
    out, rew, i = [], 0, 0
    while i < len(t):
        if i + 1 < len(t) and t[i] == t[i + 1]:
            out.append(t[i] + 1); rew += 1 << (t[i] + 1); i += 2
        else:
            out.append(t[i]); i += 1
    return out + [0] * (4 - len(out)), rew

def transform(b, j):
    """The 8 symmetries: j & 1 mirrors left-right, j & 2 mirrors top-bottom, j & 4 transposes (applied last)."""
    out = [0] * 16
    for r in range(4):
        for c in range(4):
            rr, cc = r, c
            if j & 1: cc = 3 - cc
            if j & 2: rr = 3 - rr
            if j & 4: rr, cc = cc, rr
            out[rr * 4 + cc] = b[r * 4 + c]
    return out

DIRS = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}  # up right down left as (dr, dc)
def map_dir(d, j):
    dr, dc = DIRS[d]
    if j & 1: dc = -dc
    if j & 2: dr = -dr
    if j & 4: dr, dc = dc, dr
    return [k for k, v in DIRS.items() if v == (dr, dc)][0]

def move(b, d):
    """(after, reward) for direction d (0 up, 1 right, 2 down, 3 left) on real ranks."""
    out = [0] * 16
    rew = 0
    for i in range(4):
        if d in (1, 3):
            idx = [i * 4 + k for k in range(4)]
        else:
            idx = [k * 4 + i for k in range(4)]
        if d in (1, 2): idx = idx[::-1]
        line, rw = slide_left([b[k] for k in idx])
        rew += rw
        for k, v in zip(idx, line): out[k] = v
    return out, rew

def legal(b): return [d for d in range(4) if move(b, d)[0] != b]

def text(b):
    return " / ".join(" ".join(str(1 << v if v else 0) for v in b[4 * r:4 * r + 4]) for r in range(4))

# ---- generators ----
def rand_board(rng, k, top):
    b = [0] * 16
    for c in rng.sample(range(16), k):
        b[c] = max(1, min(top, int(rng.expovariate(1.0 / max(1, top / 3))) + 1))
    return b

def no_merge_full(rng, top, base=1):
    """Full board without equal neighbours (game over) from random ranks."""
    for _ in range(1000):
        b = [0] * 16
        ok = True
        for c in range(16):
            r, k = c // 4, c % 4
            opts = [v for v in range(base, top + 1)
                    if not (k > 0 and b[c - 1] == v) and not (r > 0 and b[c - 4] == v)]
            if not opts: ok = False; break
            b[c] = rng.choice(opts)
        if ok: return b
    return None

def snake(ranks, j=0):
    """Ranks along the snake path from the top-left corner (orientation j applied)."""
    path = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]
    b = [0] * 16
    for p, v in enumerate(ranks): b[path[p]] = v
    return transform(b, j)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--n', type=int, default=40, help='boards per random category')
    ap.add_argument('--sym-groups', type=int, default=4, help='boards per category that get all 8 symmetries')
    ap.add_argument('--tables', action='store_true', help='only the table-formation categories (instance)')
    ap.add_argument('--human', default='results/human_ds/analysis.jsonl')
    a = ap.parse_args()
    rng = random.Random(a.seed)
    cats = {}
    def add(cat, b):
        if b is not None: cats.setdefault(cat, []).append(list(b))

    if not a.tables:
        for k in range(1, 17):  # density: 1 tile to full, small and big ranks
            for _ in range(a.n // 4):
                add(f'density{k:02d}', rand_board(rng, k, rng.choice([6, 11, 15])))
        for _ in range(a.n):  # full boards with merges (2 or 4 legal moves), random ranks
            add('full', [rng.randint(1, 12) for _ in range(16)])
        for _ in range(a.n):  # exactly one legal move: top row empty, the rest full without merges, rotated
            b = no_merge_full(rng, rng.choice([8, 12, 15]))
            if b:
                b[0:4] = [0, 0, 0, 0]
                b = transform(b, rng.randrange(8))
                add('onemove', b)
        for _ in range(a.n):  # single empty cell in a full, merge-free board (moves into that cell only)
            b = no_merge_full(rng, rng.choice([8, 12, 15]))
            if b:
                b[rng.randrange(16)] = 0
                add('onehole', b)
        for _ in range(a.n):
            add('gameover', no_merge_full(rng, rng.choice([5, 9, 13, 15])))
        add('gameover', [1, 2, 3, 4, 8, 7, 6, 5, 9, 10, 11, 12, 16, 15, 14, 13])  # 16 distinct tiles 2..65536
        add('gameover', [2, 3, 4, 5, 9, 8, 7, 6, 10, 11, 12, 13, 17, 16, 15, 14])  # 4..131072
        for _ in range(a.n // 2):
            k = rng.randint(1, 16)
            b = [0] * 16
            for c in rng.sample(range(16), k): b[c] = 1
            add('only2', b)
            b = [0] * 16
            for c in rng.sample(range(16), k): b[c] = 2
            add('only4', b)
        add('only2', [1] * 16); add('only4', [2] * 16)
        for top in (14, 15, 16, 17):  # several big tiles: pairs adjacent and apart, plus clutter
            for _ in range(a.n // 4):
                b = rand_board(rng, rng.randint(2, 12), 9)
                c1, c2 = rng.sample(range(16), 2)
                b[c1] = b[c2] = top
                add(f'bigpair{1 << top}', b)
            b = [0] * 16; b[0] = b[1] = top; b[5] = 3
            add(f'bigpair{1 << top}', b)
        for top in (14, 15, 16):  # the biggest tile off its corner (corner lock territory)
            for _ in range(a.n // 2):
                b = rand_board(rng, rng.randint(4, 14), top - 2)
                c = rng.choice([1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14])
                b[c] = top
                add(f'offcorner{1 << top}', b)
            for _ in range(a.n // 4):  # in its corner but every legal move breaks it
                b = no_merge_full(rng, top - 1)
                if b:
                    b[0] = top
                    b[1:4] = [0, 0, 0] if rng.random() < 0.5 else b[1:4]
                    b[4] = 0
                    add(f'lockonly{1 << top}', b)
        for top in (16, 17, 18, 20):  # 65536+ and very large sums
            for _ in range(a.n // 4):
                ranks = list(range(top, top - rng.randint(3, 9), -1))
                b = snake(ranks, rng.randrange(8))
                for c in range(16):
                    if not b[c] and rng.random() < 0.5: b[c] = rng.randint(1, 5)
                add(f'huge{1 << top}', b)
        for v in (11, 15, 16, 17):  # impossible: all tiles equal
            add('allsame', [v] * 16)
        add('allsame', [11] * 15 + [0])
        for _ in range(a.n // 2):  # formations: snake of k big tiles in a random orientation + clutter
            k = rng.randint(3, 8)
            top = rng.randint(10, 15)
            b = snake(list(range(top, top - k, -1)), rng.randrange(8))
            for c in range(16):
                if not b[c] and rng.random() < 0.4: b[c] = rng.randint(1, 4)
            add('formation', b)
        # human controls
        try:
            hs = []
            with open(a.human) as f:
                for i, line in enumerate(f):
                    if i % 37: continue
                    x = json.loads(line)
                    bd = x['board'] if isinstance(x['board'], list) else json.loads(x['board'])
                    hs.append([v.bit_length() - 1 if v else 0 for row in bd for v in row])
            for b in rng.sample(hs, min(len(hs), a.n * 2)): add('human', b)
        except FileNotFoundError:
            pass
    # table formations (k5: 5-tile chain from 32768 or 16384 down; k6+: longer chains) + clutter
    for top in (15, 14):
        for k in (5, 6, 7, 8):
            for _ in range(max(1, a.n // 8)):
                b = snake(list(range(top, top - k, -1)), 0)
                for c in range(16):
                    if not b[c] and rng.random() < 0.5: b[c] = rng.randint(1, 6)
                add(f'table_k{k}_{1 << top}', b)

    out = []
    gid = 0
    for cat, bs in cats.items():
        nsym = a.sym_groups if not cat.startswith('table') else len(bs)
        for i, b in enumerate(bs):
            if i < nsym:
                for j in range(8):
                    out.append({'cat': cat, 'ranks': transform(b, j), 'group': gid, 'sym': j})
                gid += 1
            else:
                out.append({'cat': cat, 'ranks': b, 'group': -1, 'sym': 0})
    for x in out: print(json.dumps(x))

if __name__ == '__main__':
    main()
