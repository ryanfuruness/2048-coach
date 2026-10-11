"""How often real players' own moves get each grade, by tier and by the biggest tile (the false-positive check for the
early grading rules). Real positions and the moves played: results/yc/pos_real.tsv; grades from the local app API.
  python3 scripts/real_early_check.py [PER_CELL=150] [--base URL]
"""
import collections, csv, json, random, sys, urllib.request
BASE = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'http://127.0.0.1:8048'
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 150
NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
rng = random.Random(3)
cells = collections.defaultdict(list)
for r in csv.DictReader(open('results/yc/pos_real.tsv'), delimiter='\t'):
    top = 2 ** max(int(c, 16) for c in r['board'])
    stage = '<16' if top < 16 else '16' if top == 16 else '32-64' if top <= 64 else '128-256' if top <= 256 else None
    if stage and r['played'] in 'URDL' and r['played']:
        cells[(r['tier'], stage)].append(r)
res = {}
for key, rows in cells.items():
    rng.shuffle(rows)
    c = collections.Counter()
    for r in rows[:N]:
        body = {'board': r['board']}
        if r['hist']:
            body['hist'] = r['hist'][-20:]
        a = json.load(urllib.request.urlopen(urllib.request.Request(BASE + '/api/analyze', json.dumps(body).encode(), {'Content-Type': 'application/json'}), timeout=60))
        g = next((m.get('grade') for m in a['moves'] if NAME[m['move']] == r['played']), None) or 'none'
        c[g] += 1
    res[key] = c
order = ['best', 'good', 'questionable', 'blunder']
print('| tier | biggest tile | moves | ' + ' | '.join(order) + ' |')
print('|---|---|---|' + '---|' * len(order))
for tier in ['expert', 'strong', 'intermediate', 'novice']:
    for st in ['<16', '16', '32-64', '128-256']:
        c = res.get((tier, st))
        if c:
            n = sum(c.values())
            print(f'| {tier} | {st} | {n} | ' + ' | '.join(f'{100*c[o]/n:.0f}%' for o in order) + ' |')
