"""Does the coach follow the plan's next cell? (a sanity check before labelling it on the board, 2026-10-10)

For real positions (results/yc/pos_real.tsv, biggest tile >= 64) with a plan next cell (src/explain.h plan_info), the
app's coach plays 64 moves (POST /api/autoplay, the local server). We follow the chain's end tile (the tile the plan
cell must match) and record what happens first:
  plan    the end tile doubles by merging with the tile coming from the plan cell
  other   it doubles by merging with a tile from another cell
  broken  the end tile or the corner tile moves away without doubling
  none    nothing within 64 moves
For "plan" we also note whether the partner was grown in place (the plan cell held a tile for the last 5 moves before
the merge) or slid in at the end.
  python3 scripts/plancell_check.py [N] [--base URL]
"""
import collections, csv, json, random, sys, urllib.request

BASE = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'http://127.0.0.1:8048'
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1500
H = 64
random.seed(1)


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def line_cells(d, line):
    # the cells of one line in move order (first = the edge tiles move toward); d: 0 up, 1 right, 2 down, 3 left
    return [i * 4 + line if d == 0 else line * 4 + (3 - i) if d == 1 else (3 - i) * 4 + line if d == 2 else line * 4 + i
            for i in range(4)]


def move(b, d):
    """b: list of 16 ranks. Returns (new board, merges [(src_a, src_b, target)], moved {src: dst})."""
    out = [0] * 16
    merges, moved = [], {}
    for line in range(4):
        cells = line_cells(d, line)
        slot, pend, pend_cell = 0, -1, -1
        for c in cells:
            v = b[c]
            if not v:
                continue
            if pend == v:
                out[cells[slot]] = v + 1
                merges.append((pend_cell, c, cells[slot]))
                moved[pend_cell] = moved[c] = cells[slot]
                slot += 1
                pend = -1
            else:
                if pend >= 0:
                    out[cells[slot]] = pend
                    moved[pend_cell] = cells[slot]
                    slot += 1
                pend, pend_cell = v, c
        if pend >= 0:
            out[cells[slot]] = pend
            moved[pend_cell] = cells[slot]
    return out, merges, moved


def rank_of(tile):
    return int(tile).bit_length() - 1


rows = [r for r in csv.DictReader(open('results/yc/pos_real.tsv'), delimiter='\t')]
cand = []
for r in rows:
    b = [int(ch, 16) for ch in r['board']]
    if max(b) >= 6 and len(r['board']) == 16:
        cand.append(r)
random.shuffle(cand)

DIRS = 'URDL'
recs = []
tried = 0
for r in cand:
    if len(recs) >= N:
        break
    tried += 1
    body = {'board': r['board']}
    if r['hist']:
        body['hist'] = r['hist'][-20:]
    a = post('/api/analyze', body)
    if a.get('game_over') or a.get('judged') is False:
        continue
    p = a.get('plan_info') or {}
    step = p.get('step') or p.get('type')
    if step not in ('build', 'grow', 'merge', 'blocked') or 'next_cell' not in p or not p.get('chain'):
        continue
    b = [int(ch, 16) for ch in r['board']]
    end, corner, nxt = p['chain'][-1], p['chain'][0], p['next_cell']
    need = rank_of(p['needs'])
    if b[end] != need:
        continue
    coach = a.get('coach_move')
    green = next((m.get('hint_cells') for m in a['moves'] if m['move'] == coach), None)
    # the horizon grows with the tile the plan needs (~2.2 points of tile sum per move): 64 moves to 1,200
    horizon = int(min(1200, max(H, 1.5 * (1 << need) / 2.2 + 40)))
    top = max(b)
    out, t_ev, partner, inplace = 'none', None, None, None
    hist_next = []  # the plan cell's tile before each move
    cur = b[:]
    endc, cornc = end, corner
    hist = (r['hist'] or '')[-20:]
    i = 0
    done = False
    while i < horizon and not done:
        req = {'board': ''.join('%x' % v for v in cur), 'n': min(64, horizon - i), 'seed': random.randrange(1 << 30)}
        if hist:
            req['hist'] = hist
        ap = post('/api/autoplay', req)
        if not ap['moves']:
            break
        for mc, sc in zip(ap['moves'], ap['spawns']):
            d = DIRS.index(mc)
            hist_next.append(cur[nxt])
            nb, merges, moved = move(cur, d)
            assert nb != cur, 'an autoplay move did not change the board'
            i += 1
            hit = next((m for m in merges if endc in (m[0], m[1])), None)
            if hit:
                other = hit[1] if hit[0] == endc else hit[0]
                out = 'plan' if other == nxt else 'other'
                t_ev, partner = i, other
                if out == 'plan':
                    last = hist_next[-5:]
                    inplace = len(last) >= 5 and all(v > 0 for v in last)
                done = True
                break
            if moved.get(endc, endc) != endc or moved.get(cornc, cornc) != cornc:
                out, t_ev, done = 'broken', i, True
                break
            k = int(sc, 32)
            assert nb[k % 16] == 0, 'a new tile on a full cell'
            nb[k % 16] = 2 if k >= 16 else 1
            cur = nb
            hist = (hist + mc)[-20:]
        if ap['over']:
            break
    stage = '64-256' if top <= 8 else '512-1024' if top <= 10 else '2048+'
    recs.append(dict(step=step, stage=stage, need=1 << need, out=out, t=t_ev, partner=partner, inplace=inplace,
                     green_is_plan=green == [nxt], tier=r['tier']))
    if len(recs) % 100 == 0:
        print(len(recs), 'positions', file=sys.stderr)

json.dump(recs, open('results/plancell/records.json', 'w'))


def table(key):
    lines = []
    groups = collections.defaultdict(list)
    for x in recs:
        groups[x[key]].append(x)
    lines.append(f'| {key} | n | plan | other | broken | none | plan: grown in place | median moves to plan |')
    lines.append('|---|---|---|---|---|---|---|---|')
    for g in sorted(groups, key=str):
        xs = groups[g]
        c = collections.Counter(x['out'] for x in xs)
        n = len(xs)
        pl = [x for x in xs if x['out'] == 'plan']
        ip = sum(1 for x in pl if x['inplace'])
        ts = sorted(x['t'] for x in pl)
        med = ts[len(ts) // 2] if ts else '-'
        lines.append(f"| {g} | {n} | {100*c['plan']/n:.0f}% | {100*c['other']/n:.0f}% | {100*c['broken']/n:.0f}% | "
                     f"{100*c['none']/n:.0f}% | {100*ip/max(1,len(pl)):.0f}% | {med} |")
    return '\n'.join(lines)


rep = [f'# Plan cell check ({len(recs)} positions of {tried} tried; the coach plays up to 1,200 moves, by the tile needed)', '',
       '## By plan step', table('step'), '', '## By stage (biggest tile)', table('stage'), '',
       '## By the tile the plan cell needs', table('need'), '',
       '## Positions where the plan cell is what turns green today', table('green_is_plan'), '']
open('results/plancell/check.md', 'w').write('\n'.join(rep))
print('\n'.join(rep))
