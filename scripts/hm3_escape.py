#!/usr/bin/env python3
"""Workstream hm3: escape from danger on REAL boards. Real tight positions (<= 2 empty cells; largest tile <= 512 or
1024-2048) of the curated human games, with the player's previous moves and what the player achieved (>= 4 empty cells
within the next 10 moves); the same positions played on by build/hm3_tool policies (human move model at a skill, with or
without care in danger) -> model escape rate vs the real one, by tier and stage.
usage: hm3_escape.py build [N_PER_GROUP]            -> results/hm3/escape_in.tsv (+ escape_real.tsv)
       hm3_escape.py run LABEL "hm3_tool options"   -> results/hm3/escape_LABEL.tsv
       hm3_escape.py report LABEL ...                (model vs real by tier x stage)"""
import collections, json, random, subprocess, sys

DIRS = {'up': 0, 'right': 1, 'down': 2, 'left': 3}

def stage_of(mx):
    return 0 if mx <= 512 else 1 if mx <= 2048 else 2

def build(nper):
    recs = collections.defaultdict(list)
    with open('results/human_ds_v6b/analysis.jsonl') as f:
        for line in f:
            a = json.loads(line)
            b = [x for row in a['board'] for x in row]
            recs[(a['video'], a.get('segment', 0))].append((a['ply'], b, a['hex'], a.get('played'), a.get('tier', '?')))
    cand = collections.defaultdict(list)
    for key, rs in recs.items():
        rs.sort(key=lambda r: r[0])
        # consecutive runs of plies within one game
        runs, cur = [], []
        for r in rs:
            if cur and (r[0] != cur[-1][0] + 1 or sum(r[1]) < sum(cur[-1][1])): runs.append(cur); cur = []
            cur.append(r)
        if cur: runs.append(cur)
        for run in runs:
            emp = [sum(1 for x in r[1] if x == 0) for r in run]
            for i, r in enumerate(run):
                if emp[i] > 2 or i + 10 >= len(run): continue
                st = stage_of(max(r[1]))
                if st > 1 or max(r[1]) < 64: continue
                hist = [DIRS[x[3]] for x in run[max(0, i - 20):i] if x[3] in DIRS]
                esc = any(e >= 4 for e in emp[i + 1:i + 11])
                cand[(r[4], st)].append((f"{key[0]}:{key[1]}:{r[0]}", r[2], hist, esc))
    random.seed(5)
    with open('results/hm3/escape_in.tsv', 'w') as f, open('results/hm3/escape_real.tsv', 'w') as g:
        for (tier, st), xs in sorted(cand.items()):
            random.shuffle(xs)
            for pid, hx, hist, esc in xs[:nper]:
                f.write(f"{tier}|{st}|{pid}\t{hx}\t{len(hist)}\t{' '.join(map(str, hist))}\n")
                g.write(f"{tier}|{st}|{pid}\t{int(esc)}\n")
            print(tier, st, len(xs), 'real escape %.3f' % (sum(x[3] for x in xs) / max(1, len(xs))))

def run(label, opts):
    with open('results/hm3/escape_in.tsv') as f, open(f'results/hm3/escape_{label}.tsv', 'w') as g:
        subprocess.run(['./build/hm3_tool', '--preset', 'best-notables', '--human-model', 'results/hm/human_model_v2.txt'] +
                       opts.split(), stdin=f, stdout=g, check=True)

def report(labels):
    real = {}
    for line in open('results/hm3/escape_real.tsv'):
        k, v = line.split('\t'); real[k] = int(v)
    groups = sorted({tuple(k.split('|')[:2]) for k in real})
    print(f"{'group':18s} {'n':>5s} {'real':>6s} " + ' '.join(f"{l:>14s}" for l in labels))
    data = {}
    for l in labels:
        d = {}
        for line in open(f'results/hm3/escape_{l}.tsv'):
            k, e, dd = line.rstrip('\n').split('\t'); d[k] = (float(e), float(dd))
        data[l] = d
    for g in groups:
        ks = [k for k in real if tuple(k.split('|')[:2]) == g]
        row = f"{g[0][:12] + ' s' + g[1]:18s} {len(ks):5d} {sum(real[k] for k in ks) / len(ks):6.3f} "
        for l in labels:
            xs = [data[l][k] for k in ks if k in data[l]]
            row += f" {sum(x[0] for x in xs) / max(1, len(xs)):6.3f} d{sum(x[1] for x in xs) / max(1, len(xs)):5.3f}"
        print(row)

if __name__ == '__main__':
    if sys.argv[1] == 'build': build(int(sys.argv[2]) if len(sys.argv) > 2 else 400)
    elif sys.argv[1] == 'run': run(sys.argv[2], sys.argv[3])
    else: report(sys.argv[2:])
