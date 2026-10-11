#!/usr/bin/env python3
"""Does a packed (or otherwise reduced) analysis engine give the same answers as the reference? (workstream serve)

  serve_compare.py select OUT.txt [--n 2000]
      a fixed position set: real positions from results/human_ds_v6c/analysis.jsonl stratified by largest tile
      (<= 512, 1024-2048, 4096-8192, 16384, 32768+; tiers mixed) + every 3rd fuzz board (results/fuzz/boards*.jsonl),
      one 16-value board per line (written once; reuse it for every comparison)
  serve_compare.py run BOARDS.txt OUT.jsonl -- ANALYZE_ARGS...
      runs `ANALYZE_ARGS --stdin --json` on the boards (one process), one JSON answer per line, with the wall time
  serve_compare.py diff REF.jsonl CAND.jsonl [--label NAME]
      engine-move agreement (all, and where the reference's best move is >= 0.1% / 1% better than the second),
      relative value-loss differences, real_loss / odds / warn / your_cost differences, latency (engine ms)."""
import gzip, json, random, subprocess, sys, time, collections

def tiles(board):
    return ' '.join(str(x) for row in board for x in row)

def select(out, n):
    rng = random.Random(20261007)
    strata = collections.defaultdict(list)
    def stratum(top):
        return 0 if top <= 512 else 1 if top <= 2048 else 2 if top <= 8192 else 3 if top <= 16384 else 4
    for line in open('results/human_ds_v6c/analysis.jsonl'):
        a = json.loads(line)
        if a.get('game_over') or not a.get('moves'):
            continue
        top = max(max(r) for r in a['board'])
        s = strata[stratum(top)]
        # reservoir sample per stratum
        s.append(tiles(a['board'])) if len(s) < 4 * n else None
    boards = []
    per = n // 5
    for k in range(5):
        xs = strata[k]
        rng.shuffle(xs)
        boards += xs[:per]
    fz = 0
    for f in ('results/fuzz/boards1.jsonl', 'results/fuzz/boards2.jsonl'):
        for i, line in enumerate(open(f)):
            if i % 3:
                continue
            r = json.loads(line)['ranks']
            boards.append(' '.join(str(1 << x) if x else '0' for x in r))
            fz += 1
    with open(out, 'w') as o:
        for b in boards:
            o.write(b + '\n')
    print(f"{len(boards)} boards ({len(boards) - fz} real, {fz} fuzz) -> {out}")

def run(boards, out, args):
    p = subprocess.Popen(args + ['--stdin', '--json'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, bufsize=1)
    n = 0
    t_start = time.time()
    with open(out, 'w') as o:
        for line in open(boards):
            b = line.strip()
            t0 = time.time()
            p.stdin.write(b + '\n'); p.stdin.flush()
            ans = p.stdout.readline()
            dt = time.time() - t0
            try:
                a = json.loads(ans)
            except Exception:
                a = {'error': ans.strip()[:200]}
            o.write(json.dumps({'board': b, 'secs': dt, 'answer': a}) + '\n')
            n += 1
    p.stdin.close(); p.wait()
    print(f"{n} answers -> {out} ({time.time() - t_start:.0f} s)")

def moves_of(a):
    return {m['move']: m for m in a.get('moves', [])}

def rel_losses(a):
    ms = moves_of(a)
    ref = a.get('engine_move')
    if not ms or ref not in ms:
        return {}
    best = ms[ref]['value']
    return {k: max(0.0, best - m['value']) / max(100000.0, abs(best)) for k, m in ms.items()}

def diff(ref_f, cand_f, label):
    R = [json.loads(l) for l in open(ref_f)]
    C = [json.loads(l) for l in open(cand_f)]
    assert len(R) == len(C), 'different position sets'
    agree = n = 0
    gap_agree = collections.Counter(); gap_n = collections.Counter()
    d_rel, d_real, d_odds, d_yc = [], [], [], []
    warn_flip = warn_n = 0
    ms_r, ms_c = [], []
    for r, c in zip(R, C):
        a, b = r['answer'], c['answer']
        if 'error' in a or 'error' in b or a.get('game_over') or b.get('game_over'):
            continue
        n += 1
        same = a.get('engine_move') == b.get('engine_move')
        agree += same
        # the reference's gap between its best and second-best move (relative value)
        rl = rel_losses(a)
        others = sorted(v for k, v in rl.items() if k != a.get('engine_move'))
        gap = others[0] if others else 1.0
        for thr in (0.001, 0.01):
            if gap >= thr:
                gap_n[thr] += 1; gap_agree[thr] += same
        cl = rel_losses(b)
        for k in rl:
            if k in cl:
                d_rel.append(abs(rl[k] - cl[k]))
        ma, mb = moves_of(a), moves_of(b)
        for k in ma:
            if k not in mb:
                continue
            x, y = ma[k].get('real_loss'), mb[k].get('real_loss')
            if x is not None and y is not None:
                d_real.append(abs(x - y))
            x, y = ma[k].get('your_cost'), mb[k].get('your_cost')
            if x is not None and y is not None:
                d_yc.append(abs(x - y))
            if 'warn' in ma[k] and 'warn' in mb[k]:
                warn_n += 1; warn_flip += bool(ma[k]['warn']) != bool(mb[k]['warn'])
        oa, ob = a.get('odds') or {}, b.get('odds') or {}
        for t in oa:
            if t in ob:
                d_odds.append(abs(oa[t] - ob[t]))
        if a.get('ms') is not None: ms_r.append(a['ms'])
        if b.get('ms') is not None: ms_c.append(b['ms'])
    def st(xs):
        if not xs:
            return 'n/a'
        xs = sorted(xs)
        return f"mean {sum(xs) / len(xs):.5f}, p99 {xs[int(0.99 * (len(xs) - 1))]:.5f}, max {xs[-1]:.5f}"
    def pct(xs, q):
        xs = sorted(xs); return xs[int(q * (len(xs) - 1))] if xs else float('nan')
    print(f"== {label}: {n} positions")
    print(f"  engine move agreement: {100 * agree / max(1, n):.2f}%  (reference gap >= 0.1%: "
          f"{100 * gap_agree[0.001] / max(1, gap_n[0.001]):.2f}% of {gap_n[0.001]}; >= 1%: "
          f"{100 * gap_agree[0.01] / max(1, gap_n[0.01]):.2f}% of {gap_n[0.01]})")
    print(f"  |relative value loss difference|: {st(d_rel)}")
    print(f"  |real_loss difference|:           {st(d_real)}")
    print(f"  |odds difference|:                {st(d_odds)}")
    print(f"  |your_cost difference|:           {st(d_yc)}")
    print(f"  warn flags flipped: {warn_flip} of {warn_n}")
    print(f"  engine ms per analysis: reference p50 {pct(ms_r, 0.5):.2f} / p99 {pct(ms_r, 0.99):.1f}; "
          f"candidate p50 {pct(ms_c, 0.5):.2f} / p99 {pct(ms_c, 0.99):.1f}")

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == 'select':
        n = int(a[a.index('--n') + 1]) if '--n' in a else 2000
        select(a[1], n)
    elif a[0] == 'run':
        k = a.index('--')
        run(a[1], a[2], a[k + 1:])
    elif a[0] == 'diff':
        label = a[a.index('--label') + 1] if '--label' in a else a[2]
        diff(a[1], a[2], label)

if __name__ == '__main__':
    main()
