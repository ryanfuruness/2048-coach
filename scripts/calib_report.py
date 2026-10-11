#!/usr/bin/env python3
"""Calibration report for build/messy --values outputs: does the engine's value (expected future points) predict the
engine's actual future score, and how do milestone probabilities depend on it - on clean vs messy positions?

usage: calib_report.py FILE.tsv [FILE.tsv ...]
Rows used: positions whose future is played by the engine alone - every row of a pure-engine file, and in handover files
the handover rows (switch = 1) plus rows sampled after the handover (phase >= 1).
"""
import sys, math, collections

def load(path):
    rows = []
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            rows.append(r)
    return rows

def engine_rows(rows, pure):
    out = []
    for r in rows:
        if 'value' not in r or r['value'] in ('nan', ''):
            continue
        if 'engine_future' in r:
            if r['engine_future'] == '1':
                out.append(r)
        elif pure or r['switch'] == '1' or int(r['phase']) >= 1:
            out.append(r)
    return out

def summarize(name, rows):
    if not rows:
        print(f"{name}: no rows"); return
    fut = [float(r['final_score']) - float(r['score']) for r in rows]
    val = [float(r['value']) for r in rows]
    n = len(rows)
    mf, mv = sum(fut) / n, sum(val) / n
    cov = sum((a - mf) * (b - mv) for a, b in zip(fut, val)) / n
    vf = sum((a - mf) ** 2 for a in fut) / n
    vv = sum((b - mv) ** 2 for b in val) / n
    corr = cov / math.sqrt(vf * vv) if vf > 0 and vv > 0 else float('nan')
    se = math.sqrt(vf / n)
    print(f"\n== {name}: {n} positions  mean future {mf:,.0f} (+- {se:,.0f})  mean value {mv:,.0f}  "
          f"ratio {mf / mv:.3f}  corr {corr:.3f}")
    # by stage of the game (max tile at the position)
    by = collections.defaultdict(list)
    for r, a, b in zip(rows, fut, val):
        by[int(r['max'])].append((a, b, int(r['final_max'])))
    print("   max tile    n   mean future   mean value  ratio   P(>=4096) P(>=8192) P(>=16384) P(>=32768)")
    for m in sorted(by):
        xs = by[m]
        k = len(xs)
        f = sum(x[0] for x in xs) / k
        v = sum(x[1] for x in xs) / k
        ps = [sum(1 for x in xs if x[2] >= t) / k for t in (4096, 8192, 16384, 32768)]
        print(f"   {m:7d} {k:5d} {f:13,.0f} {v:12,.0f} {f / v if v else float('nan'):6.3f}   " +
              "  ".join(f"{p:8.3f}" for p in ps))

def main():
    for path in sys.argv[1:]:
        rows = load(path)
        pure = all(r['phase'] == '0' for r in rows) and all(r['switch'] == '0' for r in rows)
        if 'engine_future' in rows[0]:
            pure = all(r['engine_future'] == '1' for r in rows)
        er = engine_rows(rows, pure)
        summarize(path + (" (engine games)" if pure else " (engine after handover)"), er)
        if not pure:
            summarize(path + " handover positions only", [r for r in er if r['switch'] == '1'])

if __name__ == '__main__':
    main()
