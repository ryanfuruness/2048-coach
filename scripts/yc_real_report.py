#!/usr/bin/env python3
"""Workstream yc: your chance on real games. Joins scripts/yc_real.py positions with build/hv_tool eval output (per
position and key: each legal move's chance q and the position's chance v) and the engine's analysis
(results/human_ds/analysis.jsonl: real loss of the played move).
  1. outcome prediction (milestone reached later; censored excluded): log-loss, AUC, mean predicted vs observed, per
     tier, at the key given per tier
  2. the played move's chance loss (best q - q[played]): warning / class rates per 100 moves per tier
  3. does the played move's chance loss predict the outcome beyond the chance before the move? (logistic fit of the
     outcome on logit v and the loss terms, game-clustered bootstrap) - vs the engine's real loss
usage: yc_real_report.py POS.tsv EVAL.tsv KEYMAP (e.g. novice=0.02,intermediate=0.008,strong=0.004)"""
import collections, csv, json, math, random, sys

pos_file, ev_file, keymap = sys.argv[1], sys.argv[2], dict(kv.split('=') for kv in sys.argv[3].split(','))
P = {r['id']: r for r in csv.DictReader(open(pos_file), delimiter='\t')}
Q = collections.defaultdict(dict)
V = {}
for r in csv.DictReader(open(ev_file), delimiter='\t'):
    if r['move'] == '-': V[(r['id'], r['key'])] = float(r['q'])
    else: Q[(r['id'], r['key'])][r['move']] = float(r['q'])
eng = {}
D = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
for l in open('results/human_ds/analysis.jsonl'):
    a = json.loads(l)
    k = f"{a['video']}:{a.get('segment', 0)}:{a['ply']}"
    if k in P:
        pl = D.get(a.get('played') or '', None)
        rl = next((m.get('real_loss') for m in a['moves'] if D[m['move']] == pl), None)
        eng[k] = rl

def auc(ps, ys):
    pos = [p for p, y in zip(ps, ys) if y]; neg = [p for p, y in zip(ps, ys) if not y]
    if not pos or not neg: return float('nan')
    allv = sorted([(p, 1) for p in pos] + [(p, 0) for p in neg])
    rank, i, rs = 0.0, 0, 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]: j += 1
        r = (i + j + 1) / 2
        rs += r * sum(1 for t in allv[i:j] if t[1])
        i = j
    return (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

rows = []
for pid, p in P.items():
    key = keymap.get(p['tier'])
    if not key or (pid, key) not in V: continue
    q = Q[(pid, key)]
    if p['played'] not in q: continue
    best = max(q.values())
    loss = best - q[p['played']]
    rows.append(dict(id=pid, tier=p['tier'], game=p['game'], ms=int(p['milestone']), y=int(p['outcome']), v=V[(pid, key)],
                     best=best, loss=loss, rel=loss / best if best > 1e-9 else 0.0, rl=eng.get(pid)))
print('1. outcome prediction (your chance from here at the tier key; censored excluded)')
for tier in sorted(set(r['tier'] for r in rows)):
    rs = [r for r in rows if r['tier'] == tier and r['y'] >= 0]
    if not rs: continue
    ll = -sum(math.log(max(1e-6, r['v'] if r['y'] else 1 - r['v'])) for r in rs) / len(rs)
    print(f"  {tier:12s} key {keymap[tier]:6s} n {len(rs):6d} games {len(set(r['game'] for r in rs)):3d}  mean pred {sum(r['v'] for r in rs)/len(rs):.3f}"
          f"  observed {sum(r['y'] for r in rs)/len(rs):.3f}  log-loss {ll:.3f}  AUC {auc([r['v'] for r in rs], [r['y'] for r in rs]):.3f}")
    for ms in sorted(set(r['ms'] for r in rs)):
        s = [r for r in rs if r['ms'] == ms]
        if len(s) >= 200:
            print(f"      milestone {ms:5d}: n {len(s):6d}  pred {sum(r['v'] for r in s)/len(s):.3f}  obs {sum(r['y'] for r in s)/len(s):.3f}  AUC {auc([r['v'] for r in s], [r['y'] for r in s]):.3f}")
print('2. the played move\'s chance loss: share of moves and per 100 moves')
for tier in sorted(set(r['tier'] for r in rows)):
    rs = [r for r in rows if r['tier'] == tier]
    n = len(rs)
    def per100(f): return 100 * sum(1 for r in rs if f(r)) / n
    print(f"  {tier:12s} n {n:6d}  loss>=1pt {per100(lambda r: r['loss'] >= 0.01):5.2f}  >=2pt {per100(lambda r: r['loss'] >= 0.02):5.2f}"
          f"  >=5pt {per100(lambda r: r['loss'] >= 0.05):5.2f}  | rel>=3% {per100(lambda r: r['rel'] >= 0.03 and r['loss'] >= 0.005):5.2f}"
          f"  rel>=10% {per100(lambda r: r['rel'] >= 0.10 and r['loss'] >= 0.01):5.2f}  rel>=20%&2pt {per100(lambda r: r['rel'] >= 0.2 and r['loss'] >= 0.02):5.2f}"
          f"  rel>=25%&3pt {per100(lambda r: r['rel'] >= 0.25 and r['loss'] >= 0.03):5.2f}  | engine real loss>=3% {per100(lambda r: (r['rl'] or 0) >= 0.03):5.2f}")

# 3. logistic regression with game-clustered bootstrap
def logit(p): p = min(1 - 1e-4, max(1e-4, p)); return math.log(p / (1 - p))
def fit(data, feats):
    w = [0.0] * (len(feats) + 1)
    for it in range(40):
        g = [0.0] * len(w); H = [[0.0] * len(w) for _ in w]
        for r in data:
            x = [1.0] + [f(r) for f in feats]
            z = sum(a * b for a, b in zip(w, x)); p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            for i in range(len(w)):
                g[i] += (r['y'] - p) * x[i]
                for j in range(len(w)): H[i][j] += p * (1 - p) * x[i] * x[j]
        for i in range(len(w)): H[i][i] += 1e-6
        # solve H d = g
        n = len(w); M = [H[i][:] + [g[i]] for i in range(n)]
        for c in range(n):
            piv = max(range(c, n), key=lambda r_: abs(M[r_][c])); M[c], M[piv] = M[piv], M[c]
            for r_ in range(n):
                if r_ != c and M[c][c] != 0:
                    fac = M[r_][c] / M[c][c]
                    for k in range(c, n + 1): M[r_][k] -= fac * M[c][k]
        d = [M[i][n] / M[i][i] if M[i][i] else 0 for i in range(n)]
        w = [a + b for a, b in zip(w, d)]
        if max(abs(x) for x in d) < 1e-6: break
    return w
known = [r for r in rows if r['y'] >= 0 and r['tier'] in ('intermediate', 'strong', 'novice') and 0.002 < r['v'] < 0.998]
print('3. outcome ~ logit(chance before) + the played move\'s cost (all tiers, known outcomes):', len(known), 'positions')
feats = [lambda r: logit(r['v']), lambda r: logit(r['best']) - logit(max(1e-4, r['best'] - r['loss'])),
         lambda r: -math.log(max(1e-4, 1 - (r['rl'] or 0)))]
names = ['logit v', 'chance cost (logit)', 'engine real loss (-log(1-rl))']
w = fit(known, feats)
games = sorted(set(r['game'] for r in known)); byg = collections.defaultdict(list)
for r in known: byg[r['game']].append(r)
rng = random.Random(1); boots = []
for b in range(30):
    samp = [r for g in (rng.choice(games) for _ in games) for r in byg[g]]
    boots.append(fit(samp, feats))
for i, nm in enumerate(['intercept'] + names):
    xs = sorted(bb[i] for bb in boots)
    print(f"   {nm:32s} {w[i]:+.3f}  [{xs[1]:+.3f}, {xs[-2]:+.3f}]")
