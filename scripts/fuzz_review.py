#!/usr/bin/env python3
"""Robustness of `analyze --review` and of the --stdin server against odd input (workstream fuzz, 2026-10-06).
Review: synthetic games (random-ish play with real spawns) turned into odd frame sequences - clean, repeated frames,
undos, skipped frames (gaps of 2-6 moves), a new game in the middle, garbage lines, empty / one-board / identical files,
unparseable boards, a 32768+32768 merge (65536 appears mid-game), a long game. Each runs `analyze --review F --json`
with a timeout; checks: exit 0, the last line is the review JSON, counts and shares in range.
Server: malformed lines sent to one `analyze --stdin` process, each followed by a valid board; the process must answer
every line with one JSON line (an error object for non-boards) and survive.
usage: fuzz_review.py OUTDIR [--analyze build_fuzz/analyze] [--preset best-notables]"""
import argparse, json, os, random, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuzz_gen import move, legal, text  # noqa: E402

def spawn(b, rng):
    e = [i for i, v in enumerate(b) if not v]
    if not e: return b
    b = list(b); b[rng.choice(e)] = 1 if rng.random() < 0.9 else 2
    return b

def game(rng, n, start=None):
    """Frames of a game: a corner-ish policy (prefers down/left/right, up when forced) with real spawns."""
    b = start or spawn(spawn([0] * 16, rng), rng)
    frames = [b]
    for _ in range(n):
        leg = legal(b)
        if not leg: break
        pref = [d for d in (2, 3, 1, 0) if d in leg]
        d = pref[0] if rng.random() < 0.8 else rng.choice(leg)
        b = spawn(move(b, d)[0], rng)
        frames.append(b)
    return frames

def write(path, lines):
    with open(path, 'w') as f:
        for l in lines: f.write(l + '\n')

def review_cases(rng, outdir):
    g = game(rng, 300)
    T = lambda fr: [text(b) for b in fr]
    cases = {}
    cases['clean'] = T(g)
    cases['repeated'] = [t for t in T(g) for _ in range(2)]
    und = T(g)
    for k in (40, 80, 120):
        und.insert(k + 1, und[k - 1])  # back one frame (undo), then the game continues from the later frame
    cases['undo'] = und
    gap, i = [], 0
    while i < len(g):
        gap.append(text(g[i])); i += rng.randint(1, 6)
    cases['gaps'] = gap
    cases['newgame'] = T(g[:150]) + T(game(rng, 100))
    garb = []
    for t in T(g):
        garb.append(t)
        if rng.random() < 0.2: garb.append(rng.choice(['', 'garbage', '1 2 3', '0 ' * 17, 'NaN', '\x00\x01', '|||', 'ffffffffffffffffff']))
    cases['garbage'] = garb
    cases['empty'] = []
    cases['one'] = [text(g[0])]
    cases['identical'] = [text(g[10])] * 50
    cases['unparseable_mid'] = T(g[:50]) + ['65536 32768 16384 8192 / 4096 2048 1024 512 / 256 128 64 32 / 16 8 4 2'] + T(g[50:100])
    # 32768 + 32768 merge mid-game: a late board with two 32768s next to each other
    late = [15, 15, 13, 12, 9, 10, 11, 8, 1, 2, 3, 0, 0, 1, 0, 0]
    cases['merge65536'] = T(game(rng, 80, start=late))
    big = [16, 15, 14, 13, 9, 10, 11, 12, 1, 2, 3, 0, 0, 1, 0, 0]
    cases['big131072'] = T(game(rng, 80, start=big))
    cases['long'] = T(game(rng, 3000))
    paths = {}
    for k, v in cases.items():
        p = os.path.join(outdir, f'review_{k}.txt'); write(p, v); paths[k] = p
    return paths

def check_review(name, p, cmd, timeout):
    t0 = time.time()
    try:
        r = subprocess.run(cmd + ['--review', p, '--json'], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [f'{name}: TIMEOUT after {timeout} s'], time.time() - t0
    secs = time.time() - t0
    iss = []
    if r.returncode != 0: iss.append(f'{name}: exit code {r.returncode} stderr {r.stderr[-300:]!r}')
    lines = [l for l in r.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
    bad = 0
    for l in lines:
        try: json.loads(l)
        except Exception: bad += 1
    if bad: iss.append(f'{name}: {bad} invalid JSON lines')
    if not lines or '"review"' not in lines[-1]:
        iss.append(f'{name}: no review summary line'); return iss, secs
    try:
        rv = json.loads(lines[-1])['review']
    except Exception as e:
        iss.append(f'{name}: summary not JSON: {lines[-1][:200]}'); return iss, secs
    n = rv['moves']
    for k in ('match', 'good', 'kept'):
        if not (0 <= rv[k] <= 1): iss.append(f'{name}: {k}={rv[k]} out of [0, 1]')
    if not (0 <= rv['accuracy'] <= 100): iss.append(f"{name}: accuracy {rv['accuracy']}")
    if rv['inaccuracies'] + rv['mistakes'] + rv['blunders'] > n: iss.append(f'{name}: classes exceed moves')
    if sum(ph['moves'] for ph in rv.get('phases', [])) != n: iss.append(f'{name}: phase moves != moves')
    for km in rv.get('key_moments', []):
        if not (0 <= km['real_loss'] <= 1): iss.append(f"{name}: key moment real_loss {km['real_loss']}")
        if km['ply'] < 1 or km['ply'] > n: iss.append(f"{name}: key moment ply {km['ply']} of {n}")
    if 'lost_at' in rv and not (1 <= rv['lost_at'] <= n): iss.append(f"{name}: lost_at {rv['lost_at']}")
    if 'decisive_move' in rv and not (1 <= rv['decisive_move'] <= n): iss.append(f"{name}: decisive {rv['decisive_move']}")
    per_move = len(lines) - 1
    if per_move != n: iss.append(f'{name}: {per_move} move lines vs moves {n}')
    return iss + [f"{name}: ok-info moves {n}, unknown {rv['unknown_frames']}, bridged {rv['bridged']}, {secs:.1f} s"], secs

SERVER_LINES = [
    '', '   ', '|', '||', '| |', 'depth=abc | {B}', 'depth=99 | {B}', 'depth=-3 | {B}', 'risk=9 | {B}', 'risk=-1 | {B}',
    'line=100000 | {B}', 'line=-5 | {B}', 'played=Z | {B}', 'played= | {B}', 'played=up | {B}', 'foo=bar | {B}',
    'depth = 4 | {B}', 'a | b | {B}', '-2 4 0 0 / 0 0 0 0 / 0 0 0 0 / 0 0 0 0', '2.5 4 0 0 / 0 0 0 0 / 0 0 0 0 / 0 0 0',
    '3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '2 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    '2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '4294967296 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    '1099511627776 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '4611686018427387904 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    '9223372036854775808 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '99999999999999999999999 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    '18446744073709551616 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0', '2147483648 2 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    'ffffffffffffffff', 'FFFFFFFFFFFFFFFF', 'gggggggggggggggg', '0000000000000000', '123456789abcdef0',
    '[[2,4,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,2]]', '{"board":[[2,4,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,2]]}',
    '2 ' * 100000, '\x00\x01\x02 2 4', 'é 2 4 ü', '0x2 0x4 0 0 0 0 0 0 0 0 0 0 0 0 0 0',
    '65536 32768 16384 8192 / 4096 2048 1024 512 / 256 128 64 32 / 16 8 4 2',
    '2 2 2 2 / 2 2 2 2 / 2 2 2 2 / 2 2 2 2', '0 0 0 0 / 0 0 0 0 / 0 0 0 0 / 0 0 0 0',
]

def server_test(cmd, timeout):
    valid = '2 4 8 16 / 0 0 0 32 / 0 0 2 64 / 0 0 0 128'
    p = subprocess.Popen(cmd + ['--stdin'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    iss, info = [], []
    import select
    def ask(line):
        p.stdin.write((line + '\n').encode('utf-8', 'surrogateescape')); p.stdin.flush()
        t0 = time.time(); buf = b''
        while not buf.endswith(b'\n'):
            r, _, _ = select.select([p.stdout], [], [], max(0.01, timeout - (time.time() - t0)))
            if not r: return None, time.time() - t0
            c = os.read(p.stdout.fileno(), 1 << 20)
            if not c: return 'DEAD', time.time() - t0
            buf += c
        return buf.decode('utf-8', 'replace').strip(), time.time() - t0
    for raw in SERVER_LINES:
        line = raw.replace('{B}', valid)
        out, secs = ask(line)
        label = repr(raw[:60])
        if out is None: iss.append(f'server: TIMEOUT on {label}'); p.kill(); return iss, info
        if out == 'DEAD': iss.append(f'server: process died on {label}'); return iss, info
        if '\n' in out: iss.append(f'server: several lines for {label}')
        try:
            j = json.loads(out.splitlines()[0])
            kind = 'error' if 'error' in j else ('game_over' if j.get('game_over') else f"move {j.get('engine_move')} depth {j.get('depth')} board {j.get('board')}")
            info.append(f'{label} -> {kind} ({1000 * secs:.0f} ms)')
        except Exception:
            iss.append(f'server: invalid JSON for {label}: {out[:120]!r}')
        out2, _ = ask(valid)
        if out2 in (None, 'DEAD'): iss.append(f'server: no answer to a valid board after {label}'); return iss, info
    p.stdin.close(); p.wait()
    return iss, info

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--analyze', default='build_fuzz/analyze')
    ap.add_argument('--preset', default='best-notables')
    ap.add_argument('--timeout', type=float, default=600)
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    cmd = [a.analyze, '--preset', a.preset]
    rng = random.Random(5)
    out = []
    if a.only in ('', 'server'):
        iss, info = server_test(cmd, 120)
        out += ['== server'] + iss + ['   ' + x for x in info]
    if a.only in ('', 'review'):
        paths = review_cases(rng, a.outdir)
        out.append('== review')
        for name, p in paths.items():
            iss, secs = check_review(name, p, cmd, a.timeout)
            out += iss
    with open(os.path.join(a.outdir, 'review_server.txt'), 'w') as f: f.write('\n'.join(out) + '\n')
    print('\n'.join(out))

if __name__ == '__main__':
    main()
