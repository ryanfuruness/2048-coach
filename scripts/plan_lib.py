#!/usr/bin/env python3
"""Plan study helpers (workstream plan, 2026-10-07): a Python port of src/explain.h's chain_of / plan_info on
real-rank boards (16 ints, rank = log2 tile, 0 = empty, cell 0 = top-left, row by row), and the operational checks of
what each plan type predicts, applied to a continuation (a list of boards after the position, one per move).

Plan types (as ex::Plan): no_corner, single, merge, build, grow, blocked, full; "block" for block positions (analyze's
block plan line; real max >= 16384)."""
import math

PATH = [0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12]
CORNERS = (0, 3, 12, 15)


def path_cell(j, p):
    c = PATH[p]
    rr, cc = c // 4, c % 4
    if j & 1:
        cc = 3 - cc
    if j & 2:
        rr = 3 - rr
    if j >= 4:
        rr, cc = cc, rr
    return rr * 4 + cc


def ranks_of_tiles(rows):
    """[[2,4,0,0],...] (tile values) -> 16 ranks."""
    return [int(math.log2(v)) if v else 0 for r in rows for v in r]


def ranks_of_hex(h):
    """engine hex (16 base-16/36 digits, cell 0 first) -> 16 ranks (exact for boards without lowered tiles)."""
    return [int(c, 36) for c in h]


def chain_of(b):
    mx = max(b)
    best = None
    best_next = -1
    if not mx:
        return {'orient': -1, 'len': 0, 'cells': [], 'ranks': []}
    for j in range(8):
        if b[path_cell(j, 0)] != mx:
            continue
        cells, ranks, prev = [], [], 99
        for p in range(16):
            v = b[path_cell(j, p)]
            if v == 0 or v >= prev:
                break
            cells.append(path_cell(j, p))
            ranks.append(v)
            prev = v
        nxt = b[path_cell(j, len(cells))] if len(cells) < 16 else 0
        if best is None or len(cells) > best['len'] or (len(cells) == best['len'] and nxt > best_next):
            best = {'orient': j, 'len': len(cells), 'cells': cells, 'ranks': ranks}
            best_next = nxt
    return best or {'orient': -1, 'len': 0, 'cells': [], 'ranks': []}


def plan_info(b):
    P = {'type': '', 'len': 0}
    if max(b) < 5:
        return P
    ch = chain_of(b)
    P['chain'] = ch
    if ch['len'] == 0:
        P['type'] = 'no_corner'
        return P
    r = ch['ranks']
    n = 1
    while n < ch['len'] and r[n] >= 3 and r[n - 1] - r[n] < 4:
        n += 1
    P['len'] = n
    P['end'] = r[n - 1]
    P['cells'] = ch['cells'][:n]
    P['ranks'] = r[:n]
    P['corner'] = ch['cells'][0]
    if n == 1:
        P['type'] = 'single'
        return P
    nc = path_cell(ch['orient'], n) if n < 16 else -1
    P['next_cell'] = nc
    if nc < 0:
        P['type'] = 'full'
        return P
    there = b[nc]
    P['there'] = there
    P['type'] = 'merge' if there == P['end'] else 'build' if there == 0 else 'grow' if there < P['end'] else 'blocked'
    return P


def val(r):
    return (1 << r) if r else 0


def horizon(P):
    """Moves within which the plan's predicted event should happen (about 3x the moves needed to build the missing
    tile at ~2.2 tile-sum per move, 10..600)."""
    t = P['type']
    if t == 'merge':
        return 10
    if t in ('build', 'grow'):
        need = val(P['end']) - val(P.get('there', 0))
        return int(min(600, max(10, 3 * need / 2.2)))
    if t == 'blocked':
        return int(min(600, max(10, 2 * val(P['there']) / 2.2)))
    if t == 'no_corner':
        return 30
    if t == 'single':
        return 60
    return 100


def in_corner(b):
    mx = max(b)
    return any(b[c] == mx for c in CORNERS)


def events(P, b0, seq):
    """Operational checks of plan P (from board b0) on the continuation seq (boards after each move; may be shorter
    than the horizon). Returns a dict: 'n' moves available, 'H' horizon, and per check True / False / None (censored:
    the continuation ended before the horizon without the event)."""
    H = horizon(P)
    t = P['type']
    out = {'n': len(seq), 'H': H, 'type': t}
    win = seq[:H]
    full = len(seq) >= H

    def first(pred):
        for k, b in enumerate(win):
            if pred(b):
                return k + 1
        return None

    def verdict(k):
        return True if k is not None else (False if full else None)

    if t in ('merge', 'build', 'grow', 'blocked', 'single', 'full'):
        corner, r0 = P['corner'], P['ranks'][0]
        # the anchor: the corner keeps a tile at least as big as the chain's first tile, at the horizon (or the end)
        last = win[-1] if win else b0
        out['anchor'] = (last[corner] >= r0) if (full or win) else None
    if t in ('merge', 'build', 'grow'):
        cells, end, nc = P['cells'], P['end'], P['next_cell']
        s0 = sum(val(b0[c]) for c in cells)
        # the chain absorbs a tile equal to its end (the end tile merged into the chain: the chain cells' sum grows by
        # at least the end tile's value)
        k_merge = first(lambda b: sum(val(b[c]) for c in cells) >= s0 + val(end))
        out['chain_grew'] = verdict(k_merge)
        out['t_merge'] = k_merge
        if t != 'merge':
            # the named tile appears in the named cell (or the chain absorbed it already)
            k_built = first(lambda b: b[nc] == end)
            k_loc = min([k for k in (k_built, k_merge) if k is not None], default=None)
            out['built_there'] = verdict(k_loc)
            out['t_built'] = k_loc
    if t == 'blocked':
        nc, there = P['next_cell'], P['there']
        k_clear = first(lambda b: b[nc] != there)
        out['cleared'] = verdict(k_clear)
        cells, end = P['cells'], P['end']
        s0 = sum(val(b0[c]) for c in cells)
        out['chain_grew'] = verdict(first(lambda b: sum(val(b[c]) for c in cells) >= s0 + val(end)))
    if t == 'no_corner':
        out['to_corner'] = verdict(first(in_corner))
    if t == 'single':
        out['lined_up'] = verdict(first(lambda b: plan_info(b).get('len', 0) >= 2 and in_corner(b)))
    return out


def main_check(t):
    """the main verdict per plan type (what the sentence asks for)."""
    return {'merge': 'chain_grew', 'build': 'built_there', 'grow': 'built_there', 'blocked': 'cleared',
            'no_corner': 'to_corner', 'single': 'lined_up'}.get(t)


# ---- checks on plan_info dicts (analyze's JSON "plan_info": tiles as values, cells 0-15) --------------------------
def rk(v):
    return int(math.log2(v)) if v else 0


def old_info(b):
    """the OLD plan (the Python port of the pre-2026-10-07 ex::plan, on real ranks) as a plan_info dict."""
    P = plan_info(b)
    t = P['type']
    if not t:
        return {'type': 'none'}
    if t == 'no_corner':
        return {'type': 'no_corner'}
    d = {'type': t, 'step': t, 'corner_cell': P['corner'], 'chain': P['cells'], 'tiles': [1 << r for r in P['ranks']]}
    if 'next_cell' in P and P['next_cell'] >= 0:
        d.update(next_cell=P['next_cell'], needs=1 << P['end'], there=val(P['there']))
    elif t == 'single':  # the old text: "line up the next biggest tiles next to it" -> the cell next to the corner
        c1 = path_cell(P['chain']['orient'], 1)
        d.update(next_cell=c1, there=val(b[c1]))
    return d


def horizon2(I):
    step = I.get('step', I['type'])
    if step == 'merge':
        return 10
    if step in ('build', 'grow'):
        need = I['needs'] - I.get('there', 0)
        return int(min(600, max(10, 3 * need / 2.2)))
    if step == 'blocked':
        return int(min(600, max(10, 2 * I['there'] / 2.2)))
    if step == 'no_corner' or I['type'] == 'no_corner':
        return 30
    if step == 'single':
        return 200
    return 100


def events2(I, b0, seq):
    """checks of plan_info I from real-rank board b0 on continuation seq. Main verdict 'main' per type:
    merge -> the chain absorbs a tile equal to its end; build/grow -> the needed tile appears in the named cell (or the
    chain absorbs it); blocked -> the blocker leaves the named cell; no_corner -> the biggest tile reaches a corner;
    single (no chain next to the corner) -> the tile next to the corner grows while the corner tile stays; pair adds:
    the biggest tile stays next to the corner. 'anchor': the corner keeps its tile (or a bigger one) at the horizon."""
    t = I['type']
    step = I.get('step', t)
    H = horizon2(I)
    win = seq[:H]
    full = len(seq) >= H
    out = {'H': H, 'n': len(seq)}

    def first(pred):
        for k, b in enumerate(win):
            if pred(b):
                return k + 1
        return None

    def verdict(k):
        return True if k is not None else (False if full else None)

    if t in ('none', 'block', 'full'):
        return out
    if t == 'no_corner':
        out['main'] = verdict(first(in_corner))
        return out
    cc = I['corner_cell']
    r0 = b0[cc]
    last = win[-1] if win else b0
    out['anchor'] = last[cc] >= r0 if (full or win) else None
    keep_pair = (lambda b: True)
    if t == 'pair':
        bc, br = I['biggest_cell'], b0[I['biggest_cell']]
        keep_pair = lambda b: b[bc] >= br or b[cc] > r0
    if step in ('merge', 'build', 'grow', 'blocked'):
        cells, end, nc = I['chain'], rk(I['needs']), I['next_cell']
        s0 = sum(val(b0[c]) for c in cells)
        k_merge = first(lambda b: sum(val(b[c]) for c in cells) >= s0 + val(end))
        if step == 'merge':
            out['main'] = verdict(k_merge)
        elif step in ('build', 'grow'):
            k_built = first(lambda b: b[nc] == end)
            ks = [k for k in (k_built, k_merge) if k is not None]
            out['main'] = verdict(min(ks) if ks else None)
        else:
            there = rk(I['there'])
            out['main'] = verdict(first(lambda b: b[nc] != there))
    elif step == 'single':
        nc, v1 = I['next_cell'], rk(I.get('there', 0))
        out['main'] = verdict(first(lambda b: b[nc] > v1 and b[cc] >= r0 and keep_pair(b)))
    return out
