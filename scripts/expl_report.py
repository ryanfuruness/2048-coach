#!/usr/bin/env python3
"""Faithfulness of the analysis' reasons per reason type (workstream expl): build/expl_tool's counterfactual edits.

share = gain / L0: the part of the move's loss against the reference move that the edit removing the stated defect
recovers (1 = the whole loss); placebo share: the same kind of edit somewhere unrelated. Pairs where the tool's own
evaluation does not find the move worse (L0 <= 1% of the value scale) are left out.

usage: expl_report.py PREFIX [--tool FILE] [--out FILE]   (reads PREFIX_tool.out or FILE, PREFIX_reasons.tsv)"""
import sys, statistics as st, collections

def main():
    a = sys.argv[1:]
    pre = a.pop(0)
    out, tool = None, None
    while a:
        k = a.pop(0)
        if k == '--out': out = a.pop(0)
        elif k == '--tool': tool = a.pop(0)
    meta = {}
    for l in list(open(pre + '_reasons.tsv'))[1:]:
        p = l.rstrip('\n').split('\t')
        meta[f'{p[0]}_{p[1]}'] = dict(pair=p[0], rank=int(p[1]), code=p[2], stage=int(p[3]), tier=p[4],
                                     real=float(p[5]), rel=float(p[6]), text=p[7], lock=len(p) > 8 and p[8] == '1')
    rows = []
    hdr = None
    for l in open(tool or pre + '_tool.out'):
        p = l.rstrip('\n').split('\t')
        if hdr is None:
            hdr = p
            continue
        r = dict(zip(hdr, p))
        if r['id'] not in meta:
            continue
        m = meta[r['id']]
        r.update(m)
        r['L0'], r['gain'], r['placebo'] = float(r['L0']), float(r['gain']), float(r['placebo'])
        r['ok'] = r['ok'] == '1'
        rows.append(r)
    lines = []
    P = lambda s: lines.append(s)
    by = collections.defaultdict(list)
    skipped = collections.Counter()
    nlock = len(set(r['pair'] for r in rows if r['lock']))
    rows = [r for r in rows if not r['lock']]  # corner-lock moves: the engine distrusts their values (loss n/a)
    for r in rows:
        if not r['ok']:
            skipped[(r['code'], r['note'])] += 1
            continue
        if r['L0'] <= 1000:
            skipped[(r['code'], 'tool finds no loss')] += 1
            continue
        r['share'] = max(-2.0, min(2.0, r['gain'] / r['L0']))
        r['pshare'] = max(-2.0, min(2.0, r['placebo'] / r['L0']))
        by[r['code']].append(r)
    P(f'{len(set(r["pair"] for r in rows))} (position, move) pairs, {len(rows)} reasons; testable {sum(len(v) for v in by.values())}'
      f' (left out: {nlock} corner-lock moves, whose values the engine does not trust)')
    P('')
    P('reason          n  first | share of the loss the edit recovers: median  >=50%  <=0 | placebo median  >=50% | edit > placebo')
    order = sorted(by, key=lambda c: -len(by[c]))
    for c in order:
        v = by[c]
        sh = [r['share'] for r in v]
        ps = [r['pshare'] for r in v]
        first = sum(r['rank'] == 0 for r in v)
        P(f'{c:14s} {len(v):4d} {first:5d} |   {st.median(sh):6.2f}  {sum(x >= 0.5 for x in sh) / len(v):5.2f}  '
          f'{sum(x <= 0 for x in sh) / len(v):4.2f} |   {st.median(ps):6.2f}  {sum(x >= 0.5 for x in ps) / len(v):5.2f} |   '
          f'{sum(r["gain"] > r["placebo"] for r in v) / len(v):5.2f}')
    P('')
    P('by stage (all testable reasons): stage  n  median share  >=50%  placebo median')
    for s in range(4):
        v = [r for c in by for r in by[c] if r['stage'] == s]
        if v:
            P(f'   {s}  {len(v):5d}  {st.median([r["share"] for r in v]):6.2f}  {sum(r["share"] >= 0.5 for r in v) / len(v):5.2f}'
              f'  {st.median([r["pshare"] for r in v]):6.2f}')
    P('')
    P('first-listed reason vs the others:')
    for k, name in ((0, 'first'), (1, 'later')):
        v = [r for c in by for r in by[c] if (r['rank'] == 0) == (k == 0)]
        if v:
            P(f'   {name:6s} n={len(v):5d}  median share {st.median([r["share"] for r in v]):5.2f}  >=50% '
              f'{sum(r["share"] >= 0.5 for r in v) / len(v):4.2f}')
    # rank check: pairs with >= 2 testable reasons - is the first listed the one that recovers most?
    pairs = collections.defaultdict(list)
    for c in by:
        for r in by[c]:
            pairs[r['pair']].append(r)
    multi = [sorted(v, key=lambda r: r['rank']) for v in pairs.values() if len(v) >= 2]
    if multi:
        top = sum(max(v, key=lambda r: r['gain']) is v[0] for v in multi)
        P(f'rank check: {len(multi)} pairs with >= 2 testable reasons; the first listed recovers most in {top} '
          f'({top / len(multi):.2f}; chance {st.mean(1 / len(v) for v in multi):.2f})')
        best_code = collections.Counter(max(v, key=lambda r: r['gain'])['code'] for v in multi)
        first_code = collections.Counter(v[0]['code'] for v in multi)
        P('   most-recovering code: ' + ', '.join(f'{c} {n}' for c, n in best_code.most_common()))
        P('   first-listed code:    ' + ', '.join(f'{c} {n}' for c, n in first_code.most_common()))
    # coverage: pairs where some reason recovers >= 50%
    cov = [max(r['share'] for r in v) for v in pairs.values()]
    if cov:
        P(f'pairs with at least one testable reason: {len(cov)}; best reason recovers >= 50% in '
          f'{sum(x >= 0.5 for x in cov) / len(cov):.2f}, >= 25% in {sum(x >= 0.25 for x in cov) / len(cov):.2f}')
    P('')
    P('not testable / not built: ' + ', '.join(f'{c}: {n} ({note})' for (c, note), n in skipped.most_common(12)))
    txt = '\n'.join(lines)
    print(txt)
    if out:
        open(out, 'w').write(txt + '\n')

if __name__ == '__main__':
    main()
