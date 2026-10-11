#!/usr/bin/env python3
"""Invariant checks of build/analyze on fuzz_gen.py positions (workstream fuzz, 2026-10-06).
Runs `analyze --stdin` (one process, restarted after a crash or a hang), sends every board (optionally with per-line
options), and checks each answer:
  valid JSON, no crash / hang, answer time; the move list = the legal moves (own 2048 rules on real tiles), game over iff
  no legal move, the engine move legal, rewards and afterstates (boards up to 32768), odds in [0, 1], non-increasing in
  the target and only for targets above the real biggest tile, losses >= 0 (or null) and consistent with the values,
  real_loss in [0, 1] and non-decreasing in the loss, expected_future >= 0, no NaN / inf, percentages in texts in
  [0, 100], a reason for every clearly worse move, tile values named in texts are powers of two and plausible, the
  summary's best move = the reference move; per symmetry group (the 8 rotations / reflections): the same status,
  values, odds, depth, source and the correspondingly transformed engine move (up to near-ties).
usage: fuzz_check.py BOARDS.jsonl OUT_PREFIX [--analyze build_fuzz/analyze] [--preset best-notables] [--opts 'risk=1']
       [--timeout 60] [--limit N]
Writes OUT_PREFIX.answers.jsonl (board + answer + issues) and OUT_PREFIX.summary.txt."""
import argparse, json, math, os, re, select, subprocess, sys, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuzz_gen import legal, move, map_dir, text  # noqa: E402

NAMES = ['up', 'right', 'down', 'left']

class Engine:
    def __init__(self, cmd, timeout):
        self.cmd, self.timeout, self.p = cmd, timeout, None
        self.restarts = 0
    def start(self):
        self.p = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  bufsize=0)
        self.buf = b''
    def ask(self, line):
        """Returns (status, text, seconds): status ok / timeout / crash."""
        if self.p is None or self.p.poll() is not None:
            if self.p is not None: self.restarts += 1
            self.start()
        t0 = time.time()
        try:
            self.p.stdin.write((line + '\n').encode('utf-8', 'surrogateescape'))
            self.p.stdin.flush()
        except BrokenPipeError:
            self.p = None
            return 'crash', '', time.time() - t0
        while b'\n' not in self.buf:
            left = self.timeout - (time.time() - t0)
            if left <= 0:
                self.p.kill(); self.p.wait(); self.p = None
                return 'timeout', '', time.time() - t0
            r, _, _ = select.select([self.p.stdout], [], [], left)
            if not r: continue
            chunk = os.read(self.p.stdout.fileno(), 1 << 20)
            if not chunk:
                rc = self.p.wait(); self.p = None
                return 'crash', f'exit {rc}', time.time() - t0
            self.buf += chunk
        out, self.buf = self.buf.split(b'\n', 1)
        return 'ok', out.decode('utf-8', 'replace'), time.time() - t0
    def close(self):
        if self.p and self.p.poll() is None:
            self.p.stdin.close(); self.p.wait()

def nonfinite(x):
    if isinstance(x, float): return not math.isfinite(x)
    if isinstance(x, dict): return any(nonfinite(v) for v in x.values())
    if isinstance(x, list): return any(nonfinite(v) for v in x)
    return False

def hex_of(b):
    return ''.join('0123456789abcdef'[v] for v in b)

PCT = re.compile(r'(-?\d+(?:\.\d+)?)%')
TILE_WORDS = re.compile(r'\b(?:the|a|an|your|two|chain|into a|into an)\s+(-?\d+)s?\b')

CELL_ROWS = {'top': 0, 'second': 1, 'third': 2, 'bottom': 3}
def cell_index(name):
    """Inverse of explain.h cell_name: 'top-left corner', 'second row, left edge', 'third row, second column'."""
    m = re.match(r'(top|bottom)-(left|right) corner$', name)
    if m: return CELL_ROWS[m.group(1)] * 4 + (0 if m.group(2) == 'left' else 3)
    m = re.match(r'(top|second|third|bottom) row, (left|right) edge$', name)
    if m: return CELL_ROWS[m.group(1)] * 4 + (0 if m.group(2) == 'left' else 3)
    m = re.match(r'(top|second|third|bottom) row, (second|third) column$', name)
    if m: return CELL_ROWS[m.group(1)] * 4 + (1 if m.group(2) == 'second' else 2)
    return None

def check_texts(x, j):
    """Semantic checks of the plan, summary and reasons against the board (real tiles)."""
    iss = []
    b = x['ranks']
    if not isinstance(j, dict) or 'moves' not in j: return iss
    tiles = [1 << v if v else 0 for v in b]
    mx = max(tiles)
    moves = {m['move']: m for m in j['moves']}
    after = {NAMES[d]: move(b, d)[0] for d in legal(b)}
    empties = {k: sum(1 for v in a if not v) for k, a in after.items()}
    pl = j.get('plan', '')
    for m in re.finditer(r'(Build an? (\d+) in the empty|Merge the (\d+) in the|Grow the (\d+) in the) ([a-z ,-]+?) (next to|into)', pl):
        c = cell_index(m.group(5))
        if c is None: iss.append(('plan_cell_name', pl[:160])); continue
        if m.group(2) and tiles[c] != 0: iss.append(('plan_cell', f'not empty: {pl[:160]}'))
        if m.group(3) and tiles[c] != int(m.group(3)): iss.append(('plan_cell', f'merge tile absent: {pl[:160]}'))
        if m.group(4) and tiles[c] != int(m.group(4)): iss.append(('plan_cell', f'grow tile absent: {pl[:160]}'))
    m = re.search(r'The (\d+) in the ([a-z ,-]+?) blocks it', pl)
    if m:
        c = cell_index(m.group(2))
        if c is None or tiles[c] != int(m.group(1)): iss.append(('plan_cell', f'blocker absent: {pl[:160]}'))
    head = mx  # the chain's first tile: the biggest, or in the "pair" shape the corner tile next to it (plan study)
    m = re.match(r'Your (\d+) sits next to the ([a-z ,-]+?), where your (\d+) is', pl)
    if m:
        c = cell_index(m.group(2))
        if int(m.group(1)) != mx or int(m.group(3)) * 2 != mx or c is None or tiles[c] != int(m.group(3)) or \
           not any(0 <= n < 16 and tiles[n] == mx for n in (c - 4, c + 4) + ((c - 1,) if c % 4 else ()) + ((c + 1,) if c % 4 < 3 else ())):
            iss.append(('plan_cell', f'pair shape absent: {pl[:160]}'))
        head = int(m.group(3))
    for m in re.finditer(r'(?:The (\d+) in the ([a-z ,-]+?) can merge into it|[Bb]uild up the (\d+) (?:in the ([a-z ,-]+?) next to it|next to it \(([a-z ,-]+?)\)))', pl):
        t, where = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4) or m.group(5))
        c = cell_index(where)
        if c is None or tiles[c] != int(t): iss.append(('plan_cell', f'named tile absent: {pl[:160]}'))
    m = re.search(r'runs from the ([a-z ,-]+?)\.', pl)
    if m:
        c = cell_index(m.group(1))
        if c is None or tiles[c] != head: iss.append(('plan_cell', f'chain start not the biggest tile: {pl[:160]}'))
    m = re.search(r'Keep the (\d+) in the ([a-z ,-]+?)(?: and|;)', pl)
    if m:
        c = cell_index(m.group(2))
        if c is None or tiles[c] != int(m.group(1)): iss.append(('plan_cell', f'keep-tile absent: {pl[:160]}'))
    m = re.search(r'merges into an? (\d+)', pl)
    if m and int(m.group(1)) > 2 * mx: iss.append(('plan_merge_size', pl[:160]))
    for k, mv in moves.items():
        a = after.get(k)
        if a is None: continue
        ta = [1 << v if v else 0 for v in a]
        for r in mv.get('reasons', []):
            t = r['text']
            mm = re.match(r'merges the two (\d+)s into an? (\d+)', t)
            if mm:
                xv, yv = int(mm.group(1)), int(mm.group(2))
                if yv != 2 * xv: iss.append(('reason_merge', t))
                elif ta.count(yv) <= tiles.count(yv) or tiles.count(xv) < 2: iss.append(('reason_merge', f'{k}: {t}'))
            mm = re.match(r'leaves fewer free cells \((\d+) vs (\d+)\)', t)
            if mm and int(mm.group(1)) != empties[k]: iss.append(('reason_space', f'{k}: {t} (empty after {empties[k]})'))
            mm = re.match(r'keeps the most free cells \((\d+)\)', t)
            if mm and int(mm.group(1)) != empties[k]: iss.append(('reason_space', f'{k}: {t} (empty after {empties[k]})'))
            mm = re.search(r'biggest tile \((\d+)\)', t)
            if mm and int(mm.group(1)) not in (mx, max(ta)): iss.append(('reason_biggest', f'{k}: {t}'))
            mm = re.match(r'pulls the (\d+) out of your chain \(([a-z ,-]+)\)', t)
            if mm:
                c = cell_index(mm.group(2))
                if c is None or tiles[c] != int(mm.group(1)): iss.append(('reason_chain_cell', f'{k}: {t}'))
            mm = re.search(r'\(vs \d+% after (\w+)\)', t)
            if mm and mm.group(1) not in moves: iss.append(('reason_ref_move', f'{k}: {t}'))
    sm = re.search(r'Avoid (\w+)', j.get('summary', ''))
    if sm:
        av = moves.get(sm.group(1))
        if av is None or sm.group(1) == j.get('engine_move') or (av.get('real_loss') is not None and av['real_loss'] < 0.1):
            iss.append(('summary_avoid', j['summary'][:200]))
    return iss

def check_answer(x, st, txt, secs):
    """Issues of one answer (list of (code, detail))."""
    b = x['ranks']
    iss = []
    if st != 'ok':
        return [(st, txt)], None
    try:
        j = json.loads(txt, parse_constant=lambda c: float('nan'))
    except Exception as e:
        return [('invalid_json', txt[:200])], None
    if nonfinite(j): iss.append(('nonfinite', txt[:200]))
    nz = [v for v in b if v]
    distinct = len(set(nz))
    if 'error' in j:
        iss.append(('error', f"{j['error']} (distinct {distinct}, max rank {max(nz) if nz else 0})"))
        return iss, j
    leg = legal(b)
    real_max = max(b)
    moves = {m['move']: m for m in j.get('moves', [])}
    if sorted(NAMES.index(k) for k in moves) != leg: iss.append(('moves_mismatch', f'{sorted(moves)} vs {[NAMES[d] for d in leg]}'))
    go = bool(j.get('game_over'))
    if go != (not leg): iss.append(('gameover_mismatch', f'game_over={go}, legal={leg}'))
    em = j.get('engine_move')
    if leg and em not in [NAMES[d] for d in leg]: iss.append(('engine_illegal', f'{em}'))
    if not leg and em is not None: iss.append(('engine_on_dead', f'{em}'))
    # rewards / afterstates on boards the search board holds exactly (no rank above 15)
    if real_max <= 15:
        for d in leg:
            m = moves.get(NAMES[d])
            if not m: continue
            a, rw = move(b, d)
            if max(a) <= 15:
                if m['reward'] != rw: iss.append(('reward_mismatch', f"{NAMES[d]} {m['reward']} vs {rw}"))
                if m.get('after') != hex_of(a): iss.append(('after_mismatch', f"{NAMES[d]} {m.get('after')} vs {hex_of(a)}"))
    # odds
    def check_odds(o, where):
        prev = 1.0
        for k in sorted(o, key=int):
            p = o[k]
            if not (isinstance(p, (int, float)) and 0 <= p <= 1): iss.append(('odds_range', f'{where} {k}:{p}'))
            if int(k) <= (1 << real_max): iss.append(('odds_reached', f'{where} target {k} <= real max {1 << real_max}'))
            if isinstance(p, (int, float)) and p > prev + 1e-9: iss.append(('odds_monotone', f'{where} {o}'))
            prev = p if isinstance(p, (int, float)) else prev
    if 'odds' in j: check_odds(j['odds'], 'position')
    for k, m in moves.items():
        if 'odds' in m: check_odds(m['odds'], k)
    ef = j.get('expected_future')
    if ef is not None and ef < 0: iss.append(('ef_negative', f'{ef}'))
    # losses
    vals = {k: m['value'] for k, m in moves.items() if m.get('value') is not None}
    if moves:
        zero = [k for k, m in moves.items() if m.get('loss') is not None and abs(m['loss']) < 0.05]
        best = None
        for k, m in moves.items():
            if m.get('loss') is not None and m['loss'] < -0.05: iss.append(('loss_negative', f"{k} {m['loss']}"))
            if m.get('real_loss') is not None and not (0 <= m['real_loss'] <= 1): iss.append(('real_loss_range', f"{k} {m['real_loss']}"))
        if not zero: iss.append(('no_reference', f'{[(k, m.get("loss")) for k, m in moves.items()]}'))
        else:
            ref = vals.get(zero[0])
            for k, m in moves.items():
                if m.get('loss') is not None and ref is not None and abs((ref - m['value']) - m['loss']) > 0.2 + 1e-6 * abs(ref):
                    iss.append(('loss_inconsistent', f"{k}: loss {m['loss']} vs {ref - m['value']}"))
        rl = sorted((m['loss'], m['real_loss']) for m in moves.values() if m.get('loss') is not None and m.get('real_loss') is not None)
        for (l0, r0), (l1, r1) in zip(rl, rl[1:]):
            if r1 < r0 - 1e-4: iss.append(('real_loss_monotone', f'{rl}'))
        # a reason for every clearly worse move (relative value loss >= 3%, not a corner-breaking move); block positions
        # that no table decides are not judged (analyze: "judged": false, no verdicts by design)
        if zero and ref is not None and j.get('judged') is not False:
            for k, m in moves.items():
                if m.get('loss') is None or m.get('breaks_corner'): continue
                rel = max(0.0, m['loss']) / max(100000.0, abs(ref))
                # where an exact table decided, the table's verdict counts (analyze grades and explains those moves by
                # the table's success chances; a move the table rates within 2 points of the best needs no reason)
                if j.get('source', 'search') != 'search' and m.get('p') is not None and j.get('table_p') is not None \
                        and j['table_p'] - m['p'] < 0.02:
                    continue
                if rel >= 0.03 and not m.get('reasons'): iss.append(('no_reason', f'{k} rel {rel:.3f}'))
        # summary's best move
        sm = re.search(r'Best move: (\w+)', j.get('summary', ''))
        if sm and moves.get(sm.group(1), {}).get('loss') not in (None, 0.0) and abs(moves[sm.group(1)]['loss']) > 0.05:
            iss.append(('summary_best', f"{sm.group(1)} loss {moves[sm.group(1)]['loss']}"))
    # texts: percentages and tile values
    texts = [j.get('summary', ''), j.get('plan', '')] + [r['text'] for m in moves.values() for r in m.get('reasons', [])]
    tiles_on_board = {1 << v for v in b if v}
    for t in texts:
        for p in PCT.findall(t):
            if not (0 <= float(p) <= 100): iss.append(('pct_range', t[:160]))
        t_nt = re.sub(r'the \d+ tile comes', '', t)  # odds targets may exceed the board's tiles
        for v in TILE_WORDS.findall(t_nt):
            v = int(v)
            if v <= 1 or v & (v - 1):
                if not re.search(rf'\b{v} (tiles|of|%)', t): iss.append(('text_not_tile', f'{v}: {t[:160]}'))
            elif v > 4 << real_max: iss.append(('text_tile_too_big', f'{v}: {t[:160]}'))
    pl = j.get('plan', '')
    mk = re.match(r'Keep the (\d+) in', pl)
    if mk and int(mk.group(1)) != 1 << real_max: iss.append(('plan_wrong_max', pl[:160]))
    mc = re.match(r'Your chain ([\d-]+) runs', pl)
    if mc:
        ch = [int(v) for v in mc.group(1).split('-')]
        if any(v not in tiles_on_board for v in ch) or any(a <= c for a, c in zip(ch, ch[1:])):
            iss.append(('plan_bad_chain', pl[:160]))
    for m in moves.values():
        for r in m.get('reasons', []):
            if not r.get('text') or not r.get('code'): iss.append(('empty_reason', str(r)))
    if j.get('ms', 0) > 2000: iss.append(('slow', f"{j.get('ms')} ms"))
    iss += check_texts(x, j)
    return iss, j

def sym_check(group):
    """group: list of (record, answer json) for the 8 symmetries; issues for the group."""
    iss = []
    base = [g for g in group if g[0]['sym'] == 0]
    if not base or base[0][1] is None: return iss
    x0, j0 = base[0]
    for x, j in group:
        s = x['sym']
        if s == 0: continue
        if j is None:
            iss.append(('sym_status', f'sym {s}: no answer')); continue
        if ('error' in j) != ('error' in j0) or bool(j.get('game_over')) != bool(j0.get('game_over')):
            iss.append(('sym_status', f'sym {s}')); continue
        if 'error' in j: continue
        if j.get('depth') != j0.get('depth'): iss.append(('sym_depth', f"sym {s}: depth {j.get('depth')} vs {j0.get('depth')}"))
        if j.get('source') != j0.get('source'): iss.append(('sym_source', f"sym {s}: {j.get('source')} vs {j0.get('source')}"))
        if (j.get('table_p') is None) != (j0.get('table_p') is None) or \
           (j.get('table_p') is not None and abs(j['table_p'] - j0['table_p']) > 1e-3):
            iss.append(('sym_table_p', f"sym {s}: {j.get('table_p')} vs {j0.get('table_p')}"))
        m0 = {mm['move']: mm for mm in j0.get('moves', [])}
        m1 = {mm['move']: mm for mm in j.get('moves', [])}
        scale = max([1000.0] + [abs(mm['value']) for mm in m0.values() if mm.get('value') is not None])
        worst = 0.0
        for d0 in range(4):
            a, b = m0.get(NAMES[d0]), m1.get(NAMES[map_dir(d0, s)])
            if (a is None) != (b is None):
                iss.append(('sym_moves', f'sym {s}: {NAMES[d0]}')); continue
            if a is None: continue
            if a.get('value') is not None and b.get('value') is not None:
                worst = max(worst, abs(a['value'] - b['value']) / scale)
            if (a.get('p') is None) != (b.get('p') is None) or (a.get('p') is not None and abs(a['p'] - b['p']) > 1e-3):
                iss.append(('sym_move_p', f"sym {s}: {NAMES[d0]} p {a.get('p')} vs {b.get('p')}"))
            if bool(a.get('breaks_corner')) != bool(b.get('breaks_corner')):
                iss.append(('sym_lock', f'sym {s}: {NAMES[d0]}'))
        if worst > 1e-3: iss.append(('sym_value', f'sym {s}: max relative value difference {worst:.4f}'))
        # engine move: the mapped move must be equivalent (value within 0.1% of the base's engine move)
        e0, e1 = j0.get('engine_move'), j.get('engine_move')
        if e0 and e1:
            d1 = [d for d in range(4) if NAMES[map_dir(d, s)] == e1][0]
            if NAMES[d1] != e0:
                va, vb = m0.get(e0, {}).get('value'), m0.get(NAMES[d1], {}).get('value')
                if va is None or vb is None or abs(va - vb) / scale > 1e-3:
                    iss.append(('sym_engine_move', f'sym {s}: {e1} (= base {NAMES[d1]}) vs base {e0}, values {va} / {vb}'))
        o0, o1 = j0.get('odds', {}), j.get('odds', {})
        if set(o0) != set(o1) or any(abs(o0[k] - o1[k]) > 0.002 for k in o0):
            iss.append(('sym_odds', f'sym {s}: {o1} vs {o0}'))
    return iss

def report(a, recs_n, restarts, counts, examples, times):
    with open(a.out + '.summary.txt', 'w') as f:
        f.write(f'{recs_n} boards, opts "{a.opts}", engine restarts {restarts}\n')
        by_code = collections.Counter()
        for (cat, code), n in counts.items(): by_code[code] += n
        f.write('issues by code: ' + ', '.join(f'{c} {n}' for c, n in by_code.most_common()) + '\n')
        f.write('issues by category/code:\n')
        for (cat, code), n in sorted(counts.items()): f.write(f'  {cat:24s} {code:20s} {n}\n')
        f.write('examples:\n')
        for code, ex in examples.items():
            for e in ex: f.write(f'  {code}: {e}\n')
        times.sort(key=lambda t: -t[0])
        ws = [t[0] for t in times]
        if ws:
            f.write(f'answer time: median {1000 * sorted(ws)[len(ws) // 2]:.1f} ms, p99 {1000 * sorted(ws)[int(0.99 * (len(ws) - 1))]:.1f} ms, max {1000 * ws[0]:.1f} ms\n')
        for t in times[:8]: f.write(f'  slowest: {1000 * t[0]:.1f} ms (engine ms {t[1]}) [{t[2]}] {t[3]}\n')
    print(open(a.out + '.summary.txt').read())

def recheck(a):
    counts = collections.Counter()
    examples = collections.defaultdict(list)
    groups = collections.defaultdict(list)
    times = []
    n = 0
    for line in open(a.out + '.answers.jsonl'):
        r = json.loads(line)
        x, j = r['rec'], r['answer']
        st = r['status']
        txt = json.dumps(j) if j is not None else ''
        iss, j2 = check_answer(x, st, txt, r['secs'])
        n += 1
        times.append((r['secs'], (j or {}).get('ms') if isinstance(j, dict) else None, x['cat'], text(x['ranks'])))
        for code, det in iss:
            counts[(x['cat'], code)] += 1
            if len(examples[code]) < 6: examples[code].append(f"[{x['cat']}] {text(x['ranks'])} :: {det}")
        if x['group'] >= 0: groups[x['group']].append((x, j2))
    for g in groups.values():
        for code, det in sym_check(g):
            counts[(g[0][0]['cat'], code)] += 1
            if len(examples[code]) < 6: examples[code].append(f"[{g[0][0]['cat']}] {text(g[0][0]['ranks'])} :: {det}")
    report(a, n, 0, counts, examples, times)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('boards'); ap.add_argument('out')
    ap.add_argument('--analyze', default='build_fuzz/analyze')
    ap.add_argument('--preset', default='best-notables')
    ap.add_argument('--opts', default='')
    ap.add_argument('--timeout', type=float, default=60)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--extra', default='', help='extra analyze flags')
    ap.add_argument('--recheck', action='store_true', help='re-run the checks on OUT_PREFIX.answers.jsonl (no engine)')
    a = ap.parse_args()
    if a.recheck:
        return recheck(a)
    recs = [json.loads(l) for l in open(a.boards)]
    if a.limit: recs = recs[:a.limit]
    cmd = [a.analyze, '--preset', a.preset, '--stdin'] + (a.extra.split() if a.extra else [])
    eng = Engine(cmd, a.timeout)
    counts = collections.Counter()
    examples = collections.defaultdict(list)
    groups = collections.defaultdict(list)
    times = []
    with open(a.out + '.answers.jsonl', 'w') as fo:
        for i, x in enumerate(recs):
            line = (a.opts + ' | ' if a.opts else '') + text(x['ranks'])
            st, txt, secs = eng.ask(line)
            iss, j = check_answer(x, st, txt, secs)
            ms = j.get('ms') if isinstance(j, dict) else None
            times.append((secs, ms, x['cat'], text(x['ranks'])))
            for code, det in iss:
                counts[(x['cat'], code)] += 1
                if len(examples[code]) < 6: examples[code].append(f"[{x['cat']}] {text(x['ranks'])} :: {det}")
            if x['group'] >= 0: groups[x['group']].append((x, j))
            fo.write(json.dumps({'rec': x, 'status': st, 'secs': round(secs, 4), 'answer': j, 'issues': iss}) + '\n')
            if (i + 1) % 200 == 0:
                print(f'{i + 1}/{len(recs)} done, issues so far {sum(counts.values())}', file=sys.stderr, flush=True)
    eng.close()
    for g in groups.values():
        for code, det in sym_check(g):
            counts[(g[0][0]['cat'], code)] += 1
            if len(examples[code]) < 6: examples[code].append(f"[{g[0][0]['cat']}] {text(g[0][0]['ranks'])} :: {det}")
    report(a, len(recs), eng.restarts, counts, examples, times)

if __name__ == '__main__':
    main()
