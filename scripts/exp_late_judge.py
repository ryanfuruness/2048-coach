#!/usr/bin/env python3
"""Late-position judgment metric for engine candidates (workstream late, 2026-10-06), on positions whose every legal
move was judged by rollouts (build/rollout output: pos, board, max, move, engine_move, q, q_se, ...).
Default set: the random real late positions of results/judge/late300_h1000.tsv + human300_h1000.tsv with a largest
tile >= 8192 (not selected by any engine's claims, so comparing candidates on them is fair).

  exp_late_judge.py prep OUT.txt [--files A.tsv,B.tsv] [--min-max 8192]
        analyze input (one board per line) + OUT.txt.idx (first line: the files; then file index, pos per board)
  exp_late_judge.py report IDX CLAIMS.jsonl ... [--meta META.tsv]
        per candidate and largest tile: Spearman of claimed vs rollout loss (every move vs the candidate's reference
        move), claims > 10% and how many the rollouts refute (< 2 se), the rollout value of the candidate's move vs the
        judged engine's move. With --meta (a TSV with columns hex and played, e.g. results/cal6/xexpert.tsv): the
        player's moves too - verdicts from the rollouts (the judged engine's move vs the played move, as
        dispute_report.py) and the candidate's claims on them.
"""
import json, math, sys, collections
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from exp_late_claims import pearson, ranks, NAME  # noqa: E402

DEFAULT = ['results/judge/late300_h1000.tsv', 'results/judge/human300_h1000.tsv']


def load(files, min_max):
    pos = collections.OrderedDict()
    for fi, path in enumerate(files):
        with open(path) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                if r.get('pos') == 'pos' or int(r['max']) < min_max: continue
                k = (fi, int(r['pos']))
                p = pos.setdefault(k, dict(board=r['board'], max=int(r['max']), eng=r['engine_move'], q={}))
                p['q'][r['move']] = (float(r['q']), float(r['q_se']))
    return pos


def opt(args, name, default):
    return args[args.index(name) + 1] if name in args else default


def main():
    args = sys.argv[1:]
    if args[0] == 'prep':
        files = opt(args, '--files', ','.join(DEFAULT)).split(',')
        pos = load(files, int(opt(args, '--min-max', '8192')))
        with open(args[1], 'w') as f, open(args[1] + '.idx', 'w') as g:
            g.write(','.join(files) + '\n')
            for k, p in pos.items():
                f.write(p['board'] + '\n')
                g.write(f"{k[0]}\t{k[1]}\n")
        return
    lines = open(args[1]).read().splitlines()
    if '\t' in lines[0]:  # old index files without the header line
        files, body = DEFAULT, lines
    else:
        files, body = lines[0].split(','), lines[1:]
    idx = [tuple(int(x) for x in l.split()) for l in body]
    pos = load(files, 0)
    played = {}
    meta = opt(args, '--meta', None)
    if meta:
        with open(meta) as f:
            hdr = f.readline().rstrip('\n').split('\t')
            for line in f:
                r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                played[r['hex']] = NAME.get(r['played'], r['played'])
    paths = [a for a in args[2:] if a.endswith('.jsonl')]
    split = '--split' in args  # groups by player type (PDF player d4Nf6Bg5 vs the rest) instead of by largest tile
    if split:
        from exp_late_claims import group_of
        h2v = dict(l.rstrip('\n').split('\t') for l in open('results/late/hex_video.tsv'))
    print(f"{'candidate':22s} {'group':>6s} {'n':>4s} {'rho':>6s} {'big':>4s} {'bigF':>4s} {'big real':>8s} {'move dq':>14s}"
          + ("   played: refuted>10% confirmed>10%  claim refuted/confirmed" if played else ""))
    for path in paths:
        name = path.rsplit('/', 1)[-1].replace('judge_', '').replace('.jsonl', '')
        acc = collections.defaultdict(lambda: dict(c=[], t=[], big=0, bigf=0, bigt=[], dq=[], n=0, pv=collections.Counter(),
                                                   pc=collections.Counter(), ps=collections.Counter()))
        for k, line in zip(idx, open(path)):
            a = json.loads(line)
            p = pos[k]
            if 'moves' not in a or len(a['moves']) < 2: continue
            vals = {NAME[m['move']]: m['value'] for m in a['moves']}
            lock = {NAME[m['move']] for m in a['moves'] if m.get('breaks_corner')}
            eng = NAME.get(a.get('engine_move') or '', None)
            if eng is not None and a.get('source', 'search') != 'search':
                refm = eng
            else:
                ok = [m for m in vals if m not in lock] or list(vals)
                refm = max(ok, key=lambda m: vals[m])
            ref = vals[refm]
            if refm not in p['q']: continue
            scale = max(1.0, abs(max(x[0] for x in p['q'].values())))
            cl = {m: max(0.0, ref - v) / max(100000.0, abs(ref)) for m, v in vals.items()}
            if split:
                if p['max'] < 16384: continue
                groups = ('all', group_of(h2v.get(p['board'], '')))
            else:
                groups = ('all', '8192' if p['max'] == 8192 else '16384' if p['max'] == 16384 else '32768+')
            for g in groups:
                A = acc[g]
                A['n'] += 1
                for m in vals:
                    if m == refm or m not in p['q']: continue
                    t = (p['q'][refm][0] - p['q'][m][0]) / scale
                    se = math.hypot(p['q'][refm][1], p['q'][m][1]) / scale
                    A['c'].append(cl[m]), A['t'].append(t)
                    if cl[m] > 0.10:
                        A['big'] += 1
                        A['bigf'] += t < 2 * se
                        A['bigt'].append(t)
                if eng in p['q'] and p['eng'] in p['q']:
                    A['dq'].append((p['q'][eng][0] - p['q'][p['eng']][0]) / scale)
                pm, e = played.get(p['board']), p['eng']
                if pm and pm in p['q'] and e in p['q'] and pm != e and pm in cl:
                    (qe, se_), (qp, sp) = p['q'][e], p['q'][pm]
                    s = math.hypot(se_, sp)
                    v = 'confirmed' if qe - qp > 2 * s else ('refuted' if qp >= qe - s else 'unclear')
                    A['pv'][v] += 1
                    A['ps'][v] += cl[pm]
                    if cl[pm] > 0.10: A['pc'][v] += 1
        for g in (('PDF', 'snake', 'all') if split else ('8192', '16384', '32768+', 'all')):
            A = acc[g]
            if not A['n']: continue
            dq = A['dq']
            mq = sum(dq) / max(1, len(dq))
            sq = math.sqrt(sum((x - mq) ** 2 for x in dq) / max(1, len(dq) - 1) / max(1, len(dq)))
            bt = 100 * sum(A['bigt']) / max(1, len(A['bigt']))
            s = (f"{name:22s} {g:>6s} {A['n']:4d} {pearson(ranks(A['c']), ranks(A['t'])):6.3f} {A['big']:4d} {A['bigf']:4d}"
                 f" {bt:7.1f}% {100 * mq:+6.2f}+-{100 * sq:4.2f}%")
            if played:
                pv, pc, ps = A['pv'], A['pc'], A['ps']
                s += (f"   {pc['refuted']:4d}/{pv['refuted']:<4d} {pc['confirmed']:4d}/{pv['confirmed']:<4d}"
                      f"  {100 * ps['refuted'] / max(1, pv['refuted']):5.1f}% / {100 * ps['confirmed'] / max(1, pv['confirmed']):5.1f}%")
            print(s)
    print("rho: Spearman of claimed vs rollout loss over every move != the candidate's reference; big: claims > 10%; bigF:"
          "\nof those, rollout loss < 2 se; big real: their mean rollout loss; move dq: rollout value of the candidate's move"
          "\nminus the judged engine's move (relative). played: the player's move where it differs from the judged engine's,"
          "\nverdict by the rollouts; candidate claims > 10% on refuted (false) and confirmed (true) ones, mean claims.")


if __name__ == '__main__':
    main()
