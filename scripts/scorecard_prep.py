#!/usr/bin/env python3
"""Scorecard inputs (workstream scorecard, 2026-10-07): collects every truth set of the 2026-10-06/07 studies into
fixed input files, so that any engine / model configuration can be scored on exactly the same positions
(scripts/scorecard.sh). Run once (re-run only when truth sets are added).

Writes results/scorecard/inputs/:
  judge_pos.tsv, judge_in.txt, judge_truth.tsv  rollout-judged real positions (every legal move, 32 playouts, H=1000):
      human300, late300 (results/judge), j1200 (results/cal6/j1200) = unselected positions, all moves; jx (cal6's
      expert decisions, results/cal6/jx) and jold (the 150 old expert disputes + 60 controls, results/cal6/jold) =
      selected decisions, used for the played move only. Real tiles, tier, player, played move from
      results/human_ds/analysis.jsonl (lookup by the engine board, as scripts/fit_lossmap2.py).
  odds_pos.tsv, odds_in.txt   real positions with engine-playout truth (cal6): r14 (P(16384)), r15 + r15b + truth4 (P(32768), best_v6c continuing),
      t30 (tight, P(16384)), truth3 (200 fresh positions no model was fitted on, P(16384)); plus the near-dead board
      (P(16384) measured 0.850, 120 playouts) and a fresh board (2 tiles; compared with the benchmark base rates).
  disputes_in.txt   the 210 expert decisions of results/disputes/expert.bin (scripts/exp_late_claims.py prep)."""
import collections, glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from block_detect import block_position  # noqa: E402

OUT = 'results/scorecard/inputs'

def lookup():
    look = {}
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        if a['hex'] in look:
            continue
        cells = [x for r in a['board'] for x in r]
        look[a['hex']] = dict(tiles=cells, top=max(cells), tier=a.get('tier', '?'), player=a.get('player', a['video']),
                              video=a['video'], played=a.get('played') or '-',
                              unclean=int(bool(a.get('maybe_two_moves') or a.get('rest_ambiguous') or a.get('undone'))),
                              block=int(block_position(cells)))
    return look

def judge(look):
    sets = [('human300', ['results/judge/human300_h1000.tsv'], 0), ('late300', ['results/judge/late300_h1000.tsv'], 0),
            ('j1200', sorted(glob.glob('results/cal6/j1200/judge1200_*.tsv')), 0),
            ('jx', sorted(glob.glob('results/cal6/jx/xexpert_*.tsv')), 1),
            ('jold', sorted(glob.glob('results/cal6/jold/expert_*.tsv')), 1)]
    pos, truth = collections.OrderedDict(), []
    miss = collections.Counter()
    for name, files, played_only in sets:
        for path in files:
            m = re.search(r'_(\d{5})\.tsv$', path)
            off = int(m.group(1)) if m else 0
            with open(path) as f:
                hdr = f.readline().rstrip('\n').split('\t')
                for line in f:
                    r = dict(zip(hdr, line.rstrip('\n').split('\t')))
                    key = (name, int(r['pos']) + off)
                    if key not in pos:
                        info = look.get(r['board'])
                        if info is None:
                            miss[name] += 1
                            continue
                        pos[key] = dict(info, hex=r['board'], played_only=played_only, id=len(pos))
                    truth.append((pos[key]['id'], r['move'], r['q'], r['q_se']))
    with open(f'{OUT}/judge_pos.tsv', 'w') as f, open(f'{OUT}/judge_in.txt', 'w') as g:
        f.write('id\tset\tpos\thex\ttop\ttier\tplayer\tvideo\tplayed\tunclean\tblock\tplayed_only\n')
        for (name, p), d in pos.items():
            f.write(f"{d['id']}\t{name}\t{p}\t{d['hex']}\t{d['top']}\t{d['tier']}\t{d['player']}\t{d['video']}\t"
                    f"{d['played']}\t{d['unclean']}\t{d['block']}\t{d['played_only']}\n")
            g.write(' '.join(str(x) for x in d['tiles']) + '\n')
    with open(f'{OUT}/judge_truth.tsv', 'w') as f:
        f.write('id\tmove\tq\tq_se\n')
        for row in truth:
            f.write('\t'.join(str(x) for x in row) + '\n')
    c = collections.Counter(k[0] for k in pos)
    print(f"judge: {len(pos)} positions {dict(c)}, {len(truth)} (position, move) truths; not in the human data: {dict(miss)}")

def odds():
    specs = [('r14', '16384', 'results/cal6/truth.tsv', 'results/cal6/truth/truth_r14.tsv', 'r14'),
             # P(32768) truth with the INSTALLED engine continuing (best_v6c, workstream cal9; the earlier cal6 runs
             # used best_v5, which converts these positions 4-6 points worse); truth4 = 160 positions no fit saw
             ('r15', '32768', 'results/cal6/truth.tsv', 'results/cal9/truth/truth_r15.tsv', 'r15'),
             ('r15b', '32768', 'results/cal6/truth2.tsv', 'results/cal9/truth/truth2_r15.tsv', 'r15'),
             ('truth4', '32768', 'results/cal7/truth4.tsv', 'results/cal9/truth/truth4_r15.tsv', 'r15'),
             ('t30', '16384', 'results/cal6/tight30_sel.tsv', 'results/cal6/tight30_truth.tsv', 't30'),
             ('truth3', '16384', 'results/cal6/truth3.tsv', 'results/cal6/truth/truth3_r14.tsv', 'r14')]
    rows = []
    for name, T, selp, rolp, g in specs:
        sel = [l.rstrip('\n').split('\t') for l in open(selp)]
        h = {k: i for i, k in enumerate(sel[0])}
        pos = {int(r[h['idx']]): r for r in sel[1:] if r[h['group']] == g}
        rol = [l.rstrip('\n').split('\t') for l in open(rolp)]
        hh = {k: i for i, k in enumerate(rol[0])}
        for r in rol[1:]:
            i = int(r[hh['pos']])
            if i in pos:
                s = pos[i]
                rows.append((name, s[h['stratum']], s[h['hex']], T, float(r[hh['p' + T]]), int(r[hh['n']]),
                             s[h['player']] if 'player' in h else '?'))
    rows.append(('neardead', 'neardead', '1241356247932180', '16384', 0.850, 120, '-'))
    rows.append(('fresh', 'fresh', '1100000000000000', '32768', -1.0, 0, '-'))
    with open(f'{OUT}/odds_pos.tsv', 'w') as f, open(f'{OUT}/odds_in.txt', 'w') as g:
        f.write('id\tset\tstratum\thex\ttarget\tmeasured\tn\tplayer\n')
        for i, r in enumerate(rows):
            f.write(f"{i}\t" + '\t'.join(str(x) for x in r) + '\n')
            g.write(r[2] + '\n')
    print(f"odds: {len(rows)} positions {dict(collections.Counter(r[0] for r in rows))}")

def disputes():
    subprocess.run([sys.executable, 'scripts/exp_late_claims.py', 'prep', f'{OUT}/disputes_in.txt'], check=True)
    print(f"disputes: {sum(1 for _ in open(f'{OUT}/disputes_in.txt'))} decisions")

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    judge(lookup())
    odds()
    disputes()
