#!/usr/bin/env python3
"""Workstream hm3: stretch statistics of play, from boards alone (comparable between real players and simulated ones).
Per stage (largest tile <= 512, 1024-2048, 4096-8192):
  tight      share of positions with <= 2 empty cells (after the spawn)
  vtight     share with <= 1 empty cell
  escape10   from a tight position: P(>= 4 empty cells within the next 10 moves)
  corner     share of positions with the largest tile in a corner
  regain20   after the largest tile leaves its corner: P(back in a corner within 20 moves)
  empty      mean empty cells
  deaths/1k  observed game ends without a legal move per 1000 moves (real games: only where the end is recorded)
Real players: results/human_ds_v6b/analysis.jsonl (consecutive plies of a video segment; a new game where the tile sum
drops), by tier. Simulated: messy traces (one board per line, games separated by blank lines).
usage: hm3_stretch.py --real [ANALYSIS.jsonl]  |  hm3_stretch.py LABEL TRACE [LABEL TRACE ...]"""
import collections, json, sys

def stage_of(mx):
    return 0 if mx <= 512 else 1 if mx <= 2048 else 2 if mx <= 8192 else 3

def can_move(b):
    for i in range(16):
        if b[i] == 0: return True
        if i % 4 < 3 and b[i] == b[i + 1]: return True
        if i < 12 and b[i] == b[i + 4]: return True
    return False

CORNERS = (0, 3, 12, 15)

def game_stats(games, acc):
    """games: lists of boards (16 tile values), consecutive moves; the last board's game ended there if `dead`"""
    for boards, dead in games:
        n = len(boards)
        emp = [sum(1 for x in b if x == 0) for b in boards]
        mx = [max(b) for b in boards]
        corner = [max(b) in [b[c] for c in CORNERS] for b in boards]
        for i in range(n):
            st = stage_of(mx[i])
            if st > 2 or mx[i] < 64: continue
            a = acc[st]
            a['n'] += 1; a['empty'] += emp[i]; a['corner'] += corner[i]
            if emp[i] <= 2:
                a['tight'] += 1
                if i + 10 < n or (dead and i + 10 >= n):
                    a['esc_n'] += 1
                    a['esc'] += any(e >= 4 for e in emp[i + 1:i + 11])
            if emp[i] <= 1: a['vtight'] += 1
            if i > 0 and corner[i - 1] and not corner[i] and mx[i] >= 64:
                if i + 20 < n or dead:
                    a['lost'] += 1
                    a['regain'] += any(corner[i + 1:i + 21])
        if dead and boards:
            st = stage_of(mx[-1])
            if st <= 2: acc[st]['deaths'] += 1

def report(label, acc):
    out = []
    for st in range(3):
        a = acc[st]
        if a['n'] < 200: out.append(f"{'-':>44s}"); continue
        out.append(f"t{a['tight'] / a['n']:.3f} vt{a['vtight'] / a['n']:.3f} esc{a['esc'] / max(1, a['esc_n']):.2f}"
                   f" c{a['corner'] / a['n']:.2f} rg{a['regain'] / max(1, a['lost']):.2f} e{a['empty'] / a['n']:.1f}"
                   f" d{1000 * a['deaths'] / a['n']:.2f}")
    print(f"{label:24s} " + ' | '.join(out), flush=True)
    return {st: {k: v for k, v in acc[st].items()} for st in range(3)}

def new_acc():
    return {st: collections.Counter() for st in range(3)}

def real(path):
    recs = collections.defaultdict(list)
    with open(path) as f:
        for line in f:
            a = json.loads(line)
            b = [x for row in a['board'] for x in row]
            recs[(a['video'], a.get('segment', 0))].append((a['ply'], b, a.get('tier', '?'), a.get('player', '?')))
    by_tier = collections.defaultdict(new_acc)
    for key, rs in recs.items():
        rs.sort()
        games, cur, last_ply, last_sum, tier = [], [], None, None, rs[0][2]
        for ply, b, t, p in rs:
            s = sum(b)
            if cur and (ply != last_ply + 1 or s < last_sum):
                games.append((cur, False)); cur = []
            cur.append(b); last_ply, last_sum = ply, s
        if cur: games.append((cur, not can_move(cur[-1])))
        game_stats(games, by_tier[tier])
    res = {}
    for tier in ('novice', 'intermediate', 'strong', 'expert'):
        if tier in by_tier: res[tier] = report('real ' + tier, by_tier[tier])
    return res

def sim(label, path):
    games, cur = [], []
    def flush():
        if cur:
            bs = []
            for h in cur:
                bs.append([0 if c == '0' else 1 << int(c, 16) if c not in 'gh' else 1 << (16 if c == 'g' else 17) for c in h])
            games.append((bs, not can_move(bs[-1])))
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                flush(); cur = []
                continue
            cur.append(line.split()[0] if ' ' in line else line)
    flush()
    acc = new_acc()
    game_stats(games, acc)
    return report(label, acc)

if __name__ == '__main__':
    print(f"{'':24s} " + f"{'<= 512':^44s}" + ' | ' + f"{'1024-2048':^44s}" + ' | ' + f"{'4096-8192':^44s}")
    if sys.argv[1] == '--real':
        res = real(sys.argv[2] if len(sys.argv) > 2 else 'results/human_ds_v6b/analysis.jsonl')
        json.dump(res, open('results/hm3/stretch_real.json', 'w'))
    else:
        args = sys.argv[1:]
        for i in range(0, len(args), 2): sim(args[i], args[i + 1])
