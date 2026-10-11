"""Grades of random play from a new game (the QA finding "random keys get Best 82 of 88"), via the local app API.
Each game: random legal moves from the opening until the game ends or 400 moves; every move is graded as the app would
(the analysis of the position before it). Prints grade shares by the biggest tile on the board before the move, and
how the whole game would look in the review (the coach's own moves are not involved here).
  python3 scripts/random_play_check.py [GAMES=12] [--base URL]
"""
import collections, json, random, sys, urllib.request
BASE = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else 'http://127.0.0.1:8048'
G = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 12
# the board helpers of scripts/grades_check.py
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

def spawn(b, rng):
    e = [i for i, x in enumerate(b) if x == 0]
    b = list(b); b[rng.choice(e)] = 2 if rng.random() < 0.1 else 1; return b

def hexb(b): return ''.join('0123456789abcdef'[x] for x in b)

def post(body):
    r = urllib.request.Request(BASE + '/api/analyze', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(r, timeout=60))

NAME = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
rng = random.Random(7)
by_stage = collections.defaultdict(collections.Counter)
games = []
for g in range(G):
    b = spawn(spawn([0] * 16, rng), rng)
    hist = ''
    counts = collections.Counter()
    for i in range(400):
        legal = [d for d in 'URDL' if apply(b, d) != b]
        if not legal:
            break
        a = post({'board': hexb(b), **({'hist': hist[-20:]} if hist else {})})
        d = rng.choice(legal)
        grade = next((m.get('grade') for m in a['moves'] if NAME[m['move']] == d), None) or 'not judged'
        top = 2 ** max(b)
        stage = '<32' if top < 32 else '32-256' if top <= 256 else '512+'
        by_stage[stage][grade] += 1
        counts[grade] += 1
        b = spawn(apply(b, d), rng)
        hist += d
    games.append(counts)
order = ['best', 'good', 'questionable', 'blunder', 'not judged']
print('| biggest tile | moves | ' + ' | '.join(order) + ' |')
print('|---|---|' + '---|' * len(order))
for st in ['<32', '32-256', '512+']:
    c = by_stage[st]; n = sum(c.values())
    if n:
        print(f'| {st} | {n} | ' + ' | '.join(f'{100*c[o]/n:.0f}%' for o in order) + ' |')
print()
for i, c in enumerate(games):
    print(f'game {i+1}: {sum(c.values())} moves: ' + ', '.join(f'{c[o]} {o}' for o in order if c[o]))
