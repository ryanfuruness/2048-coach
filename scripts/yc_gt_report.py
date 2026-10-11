#!/usr/bin/env python3
"""Workstream yc: report on the human-chance ground truth (build/hv_tool first output) joined with the engine's analysis
(scripts/yc_engine.py) and the positions file (scripts/yc_select.py).
usage: yc_gt_report.py POS.tsv GT.tsv ENGINE.jsonl"""
import collections, csv, json, math, sys

def slide(r):
    nz = [x for x in r if x]; out = []; i = 0
    while i < len(nz):
        if i + 1 < len(nz) and nz[i] == nz[i + 1]: out.append(nz[i] + 1); i += 2
        else: out.append(nz[i]); i += 1
    return out + [0] * (4 - len(out))

def apply(b, d):
    g = [b[i * 4:(i + 1) * 4] for i in range(4)]
    if d == 'L': g = [slide(r) for r in g]
    elif d == 'R': g = [slide(r[::-1])[::-1] for r in g]
    elif d == 'U':
        cols = [slide([g[i][c] for i in range(4)]) for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    else:
        cols = [slide([g[i][c] for i in range(4)][::-1])[::-1] for c in range(4)]; g = [[cols[c][i] for c in range(4)] for i in range(4)]
    return sum(g, [])

def corner(b):
    m = max(b)
    return any(b[c] == m for c in (0, 3, 12, 15))

pos_file, gt_file, eng_file = sys.argv[1:4]
P = {r['id']: r for r in csv.DictReader(open(pos_file), delimiter='\t')}
E = {j['id']: j for j in map(json.loads, open(eng_file))}
acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))  # (id,key) -> d -> [succ, n]
pairs = collections.defaultdict(list)  # (id,key) -> list of tuples r per playout
accA = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))  # even playouts (selection)
accB = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))  # odd playouts (evaluation)
for r in csv.DictReader(open(gt_file), delimiter='\t'):
    k = (r['id'], r['key'])
    half = accA if int(r['k']) % 2 == 0 else accB
    row = {}
    for d in 'URDL':
        x = int(r['r_' + d])
        if x >= 0:
            acc[k][d][0] += x; acc[k][d][1] += 1; row[d] = x
            half[k][d][0] += x; half[k][d][1] += 1
    pairs[k].append(row)

played_of = {}
# the move the real player made at this position: from human_ds (video:ply)
for l in open('results/human_ds/analysis.jsonl'):
    j = json.loads(l)
    key = j['video'] + ':' + str(j['ply'])
    if key in P:
        played_of[key] = (j.get('played') or '?')[0].upper()

by = collections.defaultdict(list)
for (pid, key), mv in acc.items():
    p = P[pid]
    b = [int(c, 16) for c in p['board']]
    top = 1 << max(b)
    q = {d: s / n for d, (s, n) in mv.items()}
    best = max(q, key=q.get)
    e = E[pid]
    em = e['engine_move']
    # paired SE of q[best] - q[d] for the engine move
    def diff_se(d1, d2):
        xs = [r[d1] - r[d2] for r in pairs[(pid, key)] if d1 in r and d2 in r]
        n = len(xs); m = sum(xs) / n
        v = sum((x - m) ** 2 for x in xs) / max(1, n - 1)
        return m, math.sqrt(v / n)
    keeps = {d: corner(apply(b, d)) for d in q}
    rec = dict(id=pid, key=key, top=top, set=p['set'], q=q, best=best, engine=em, played=played_of.get(pid),
               keeps=keeps, corner_now=corner(b), eng=e)
    if em in q:
        rec['eng_cost'], rec['eng_cost_se'] = diff_se(best, em) if em != best else (0.0, 0.0)
        qa = {d: s / n for d, (s, n) in accA[(pid, key)].items()}
        qb = {d: s / n for d, (s, n) in accB[(pid, key)].items()}
        ba = max(qa, key=qa.get)
        rec['eng_cost_cv'] = qb[ba] - qb[em]  # best chosen on half A, cost measured on half B (no selection bias)
        rec['best_cv_keeps'] = keeps[ba]
        ka = [d for d in qa if keeps[d]]; la = [d for d in qa if not keeps[d]]
        if ka and la:
            bk = max(ka, key=qa.get); bl = max(la, key=qa.get)
            rec['keep_leave_cv'] = qb[bk] - qb[bl]
    by[(top, key)].append(rec)

print('per largest tile and key: mean chance (best move for the human); human cost of the engine move; share of')
print('positions where the engine move is clearly worse for the human (cost > 2 SE and > 2%); corner-relevant subset:')
print('chance(best corner-keeping move) - chance(best corner-leaving move), share where the human-best keeps the corner,')
print('share where the ENGINE move keeps it')
for (top, key) in sorted(by):
    rs = by[(top, key)]
    qb = sum(r['q'][r['best']] for r in rs) / len(rs)
    ec = [r['eng_cost_cv'] for r in rs if 'eng_cost_cv' in r]
    clear = [r for r in rs if 'eng_cost' in r and r['eng_cost'] > max(0.02, 2 * r['eng_cost_se'])]
    cr = [r for r in rs if r['corner_now'] and any(r['keeps'].values()) and not all(r['keeps'].values())]
    dk = []
    hb_keep = eng_keep = 0
    for r in cr:
        if 'keep_leave_cv' in r: dk.append(r['keep_leave_cv'])
        hb_keep += r.get('best_cv_keeps', r['keeps'][r['best']])
        eng_keep += r['keeps'].get(r['engine'], False)
    print(f"{top:5d} key {key:6s} n {len(rs):3d}  chance {qb:.3f}  eng cost {sum(ec)/max(1,len(ec)):.3f}  clear {len(clear):2d}/{len(ec)}"
          f"  | corner-rel {len(cr):2d}: keep-leave {sum(dk)/max(1,len(dk)):+.3f}  best keeps {hb_keep}/{len(cr)}  engine keeps {eng_keep}/{len(cr)}")
print()
print('examples: largest engine-move costs for the human')
allr = [r for rs in by.values() for r in rs if 'eng_cost' in r]
allr.sort(key=lambda r: -r['eng_cost'])
for r in allr[:25]:
    qs = ' '.join(f"{d}{'*' if r['keeps'][d] else ''}:{r['q'][d]:.2f}" for d in 'URDL' if d in r['q'])
    rl = {d: r['eng']['moves'].get(d, {}).get('real_loss') for d in r['q']}
    print(f"{r['top']:5d} {r['key']:6s} {r['id']:18s} {P[r['id']]['board']} best {r['best']} engine {r['engine']} played {r['played']}"
          f"  cost {r['eng_cost']:.3f}±{r['eng_cost_se']:.3f} | {qs} | engine real loss {rl}")
