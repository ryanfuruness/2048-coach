#!/usr/bin/env python3
"""Dispute metric for late-game engine candidates (workstream late, 2026-10-06).

The 210 expert decisions of results/disputes/expert.bin/.tsv (150 disputes where best_v5bb claimed the expert's move lost
> 10% of the value, 60 controls where the expert played the engine's move), judged by rollouts with the full engine
(results/disputes/expert_h300.tsv: every legal move, 32 playouts, horizon 300 + value bootstrap). A candidate engine
analyses the same boards (build/analyze --stdin, output one JSON line per board); this script compares its claims
(relative value loss of the played move vs the reference move: the table move when a table decided, else the best
corner-lock-allowed move; / max(|ref|, 100000), as analyze/human_disputes) with the rollout truth.

  exp_late_claims.py prep OUT.txt            analyze input lines "played=X | HEX" in idx order
  exp_late_claims.py report CLAIMS.jsonl ... metrics (several files: one per candidate, compared side by side)
"""
import json, math, struct, sys, collections

BIN, TSV, TRUTH = 'results/disputes/expert.bin', 'results/disputes/expert.tsv', 'results/disputes/expert_h300.tsv'
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}


def boards():
    d = open(BIN, 'rb').read()
    out = []
    for i in range(len(d) // 8):
        b = struct.unpack('<Q', d[8 * i:8 * i + 8])[0]
        out.append(''.join('%x' % ((b >> (4 * k)) & 15) for k in range(16)))
    return out


def meta():
    rows = []
    with open(TSV) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            rows.append(dict(zip(hdr, line.rstrip('\n').split('\t'))))
    return rows


def truth():
    q = collections.defaultdict(dict)
    with open(TRUTH) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            q[int(r['pos'])][r['move']] = (float(r['q']), float(r['q_se']))
    return q


def verdicts(rows, q):
    """dispute_report.py's verdicts (fixed: they come from the baseline engine's rollouts) and the rollout values."""
    out = {}
    for r in rows:
        i = int(r['idx'])
        p, e = NAME[r['played']], NAME[r['engine']]
        if i not in q or p not in q[i] or e not in q[i]:
            continue
        best = max(v[0] for v in q[i].values())
        (qp, sp), (qe, se) = q[i][p], q[i][e]
        s = math.sqrt(sp * sp + se * se)
        if p == e:
            v = 'control'
        else:
            loss = qe - qp
            v = 'confirmed' if loss > 2 * s else ('refuted' if loss < 2 * s and qp >= qe - s else 'unclear')
        out[i] = dict(verdict=v, q=q[i], played=p, base=e, scale=max(1.0, abs(best)))
    return out


def tloss(v, ref, m):
    """Rollout loss of move m vs move ref (relative, unbiased: a difference of two estimates, no max) and its se."""
    (qr, sr), (qm, sm) = v['q'][ref], v['q'][m]
    return (qr - qm) / v['scale'], math.sqrt(sr * sr + sm * sm) / v['scale']


def claims(path):
    """Per idx: {move: relative claimed loss}, the reference move (claims are relative to it), the engine move."""
    out = []
    for line in open(path):
        a = json.loads(line)
        if 'moves' not in a or not a['moves']:
            out.append(None)
            continue
        vals = {NAME[m['move']]: m['value'] for m in a['moves']}
        lock = {NAME[m['move']] for m in a['moves'] if m.get('breaks_corner')}
        eng = NAME.get(a.get('engine_move') or '', None)
        if eng is not None and a.get('source', 'search') != 'search':
            refm = eng
        else:
            ok = [m for m in vals if m not in lock] or list(vals)
            refm = max(ok, key=lambda m: vals[m])
        ref = vals[refm]
        rel = {m: max(0.0, ref - v) / max(100000.0, abs(ref)) for m, v in vals.items()}
        out.append(dict(rel=rel, ref=refm, eng=eng, ms=a.get('ms', 0), depth=a.get('depth'), stage=a.get('stage')))
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 3: return float('nan')
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float('nan')


def ranks(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r


PDF_PLAYERS = {'d4Nf6Bg5'}  # plays macroxue's 3x2 block formation (PDF) in the 32768 phase (workstream mx)


def group_of(video, vp={}):
    if not vp:
        try:
            vp.update(l.rstrip('\n').split('\t') for l in open('results/late/video_player.tsv'))
        except FileNotFoundError:
            pass
    return 'PDF' if vp.get(video, '') in PDF_PLAYERS else 'snake'


def report(paths, only=None):
    rows, q = meta(), truth()
    V = verdicts(rows, q)
    if only:
        V = {i: v for i, v in V.items() if group_of(rows[i]['video']) == only}
        print(f"--- {only} player(s) only: {sum(1 for v in V.values() if v['verdict'] != 'control')} disputes,"
              f" {sum(1 for v in V.values() if v['verdict'] == 'control')} controls")
    print(f"{'candidate':24s} {'false>10%':>9s} {'kept>10%':>8s} {'unc>10%':>7s} {'ctl>10%':>7s}  {'claim: refut':>12s} {'unclr':>6s}"
          f" {'confd':>6s} {'ctl':>5s} {'real':>5s} {'r(disp)':>7s} {'rho(all)':>8s} {'big':>4s} {'bigF':>4s} {'move dq':>12s} {'ms':>6s}")
    for path in paths:
        C = claims(path)
        cnt, tot, sm = collections.Counter(), collections.Counter(), collections.Counter()
        dc, dr, allc, allr = [], [], [], []
        big = bigf = 0
        dq = []
        ms = []
        for i, r in enumerate(rows):
            if i >= len(C) or C[i] is None or i not in V: continue
            c, v = C[i], V[i]
            ms.append(c['ms'])
            p = v['played']
            if p not in c['rel'] or c['ref'] not in v['q']: continue
            cl = c['rel'][p]
            tot[v['verdict']] += 1
            sm[v['verdict']] += cl
            if cl > 0.10: cnt[v['verdict']] += 1
            if v['verdict'] != 'control':
                dc.append(cl), dr.append(tloss(v, v['base'], p)[0])
            for m, x in c['rel'].items():  # every move: the claim vs the rollout loss against the same reference move
                if m not in v['q'] or m == c['ref']: continue
                t, se = tloss(v, c['ref'], m)
                allc.append(x), allr.append(t)
                if x > 0.10:
                    big += 1
                    bigf += t < 2 * se
            if c['eng'] in v['q']:  # rollout value of the candidate's move vs the baseline engine's move
                dq.append(-tloss(v, v['base'], c['eng'])[0])
        name = path.rsplit('/', 1)[-1].replace('claims_', '').replace('.jsonl', '')
        rho = pearson(ranks(allc), ranks(allr))
        mq = sum(dq) / max(1, len(dq))
        sq = math.sqrt(sum((x - mq) ** 2 for x in dq) / max(1, len(dq) - 1) / max(1, len(dq)))
        f = lambda k: 100 * sm[k] / max(1, tot[k])
        print(f"{name:24s} {cnt['refuted']:4d}/{tot['refuted']:<4d} {cnt['confirmed']:3d}/{tot['confirmed']:<4d}"
              f" {cnt['unclear']:3d}/{tot['unclear']:<3d} {cnt['control']:3d}/{tot['control']:<3d}"
              f"  {f('refuted'):11.1f}% {f('unclear'):5.1f}% {f('confirmed'):5.1f}% {f('control'):4.1f}%"
              f" {100 * sum(dr) / max(1, len(dr)):4.1f}% {pearson(dc, dr):7.3f} {rho:8.3f} {big:4d} {bigf:4d}"
              f" {100 * mq:+5.2f}+-{100 * sq:4.2f}% {sum(ms) / max(1, len(ms)):6.0f}")
    print("false>10% / kept>10%: refuted (expert right per rollouts) / confirmed disputes the candidate still claims > 10%;"
          "\nclaim: mean claimed loss of the played move per verdict; real: mean rollout loss of the played move vs the"
          "\nbaseline engine's move (150 disputes); r(disp): Pearson r of claim vs real over the disputes; rho(all): Spearman"
          "\nover every (position, move != reference); big: claims > 10%, bigF: of those, rollout loss < 2 se (not real);"
          "\nmove dq: rollout value of the candidate's move minus the baseline engine move's (relative, mean over 210).")


def main():
    if sys.argv[1] == 'prep':
        rows, bs = meta(), boards()
        with open(sys.argv[2], 'w') as f:
            for r, h in zip(rows, bs):
                f.write(f"played={NAME[r['played']]} | {h}\n")
    elif sys.argv[1] == 'report':
        args = sys.argv[2:]
        if '--split' in args:
            args.remove('--split')
            for g in ('PDF', 'snake'):
                report(args, g)
        else:
            report(args)


if __name__ == '__main__':
    main()
