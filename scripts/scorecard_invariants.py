#!/usr/bin/env python3
"""Invariants and latency for the scorecard, from scripts/fuzz_check.py answer files (PREFIX.answers.jsonl).

fuzz_check.py was written before the 2026-10-07 analysis features; three of its checks then fire by design:
  no_reason          in block-formation positions the analysis gives no verdicts, so no reasons (answer judged=false)
  real_loss_monotone in table-decided positions the real loss comes from the exact table probabilities (table map),
                     not from the value loss (answer source != search)
  text_not_tile      percentages in the new table reasons ("leaves a 97% chance ...") read as tile values (numbers
                     <= 100 in a text with percentages)
Such issues are counted as by-design; everything else is a real violation. Latency: per-answer wall time without the
first answer (it includes loading the engine), p50 / p99 / max, and the engine's own "ms".
usage: scorecard_invariants.py PREFIX ... (prints one line per prefix; --json OUT writes the numbers)"""
import json, re, sys, collections


def by_design(code, det, ans):
    if not isinstance(ans, dict):
        return False
    if code == 'no_reason' and ans.get('judged') is False:
        return True
    # where an exact table decided, a move the table rates within 2 points of the best needs no reason (analyze explains
    # table positions by the table's chances; fuzz_check.py applies the same rule since 2026-10-07 06:10)
    if code == 'no_reason' and ans.get('source', 'search') != 'search' and ans.get('table_p') is not None:
        mv = det.split()[0] if det else ''
        for m in ans.get('moves', []):
            if m.get('move') == mv and m.get('p') is not None and ans['table_p'] - m['p'] < 0.02:
                return True
    if code == 'real_loss_monotone' and ans.get('source', 'search') != 'search':
        return True
    if code == 'text_not_tile':  # numbers <= 100 in texts with percentages: the new table reasons' chances
        m = re.match(r'\s*(\d+):', det)
        if m and int(m.group(1)) <= 100 and '%' in det:
            return True
    return False


def pct(xs, q):
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))] if xs else float('nan')


def main():
    args = sys.argv[1:]
    out_json = None
    if '--json' in args:
        k = args.index('--json'); out_json = args[k + 1]; del args[k:k + 2]
    res = {}
    for prefix in args:
        real, design, n, status = collections.Counter(), collections.Counter(), 0, collections.Counter()
        wall, eng = [], []
        try:
            lines = open(prefix + '.answers.jsonl').read().splitlines()
        except FileNotFoundError:
            print(f"{prefix}: no answers file"); continue
        for i, line in enumerate(lines):
            r = json.loads(line)
            n += 1
            status[r['status']] += 1
            if i > 0:
                wall.append(1000 * r['secs'])
                if isinstance(r.get('answer'), dict) and r['answer'].get('ms') is not None:
                    eng.append(r['answer']['ms'])
            for code, det in r.get('issues', []):
                if code == 'slow':
                    continue
                (design if by_design(code, det, r.get('answer')) else real)[code] += 1
        # symmetry issues are reported in the summary only (not per answer): read them from there
        try:
            for line in open(prefix + '.summary.txt'):
                m = re.match(r'\s+\S+\s+(sym\w*)\s+(\d+)', line)
                if m: real[m.group(1)] += int(m.group(2))
        except FileNotFoundError:
            pass
        wall.sort(); eng.sort()
        res[prefix] = dict(boards=n, status=dict(status), violations=sum(real.values()), by_code=dict(real),
                           by_design=dict(design), p50=pct(wall, 0.5), p99=pct(wall, 0.99), max=wall[-1] if wall else None,
                           engine_p50=pct(eng, 0.5), engine_p99=pct(eng, 0.99))
        x = res[prefix]
        print(f"{prefix.rsplit('/', 1)[-1]:15s} {n:5d} boards  status {dict(status)}  violations {x['violations']} "
              f"{dict(real) if real else ''}  by design {dict(design) if design else '-'}  |  answer time p50 "
              f"{x['p50']:.1f} ms, p99 {x['p99']:.1f} ms, max {x['max']:.0f} ms (first answer excluded: engine load)")
    if out_json:
        json.dump(res, open(out_json, 'w'), indent=1)


if __name__ == '__main__':
    main()
