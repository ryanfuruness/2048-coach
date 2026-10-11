#!/usr/bin/env python3
"""Skill map: the review's fitted skill temperature (search values, per phase) of games by softmax players soft:t (the
personal-odds skill model: 1-ply network values), from scripts/calib_softmap.sh. Prints the median fitted t per phase
for each soft t and writes 'pskillmap PHASE t_soft1 t_fit1 t_soft2 t_fit2 ...' lines (phase 0..3 = up to 512,
1024-2048, 4096-8192, 16384+) for weights/calib/personal.txt: the analysis converts a player's fitted t (per phase)
to the soft player that plays like them before using the personal model.
usage: calib_softmap.py [--append personal.txt]"""
import glob, json, re, statistics as st, sys, collections

PH = {'up to 512': 0, '1024-2048': 1, '4096-8192': 2, '16384+': 3}

def main():
    fits = collections.defaultdict(lambda: collections.defaultdict(list))
    games = collections.Counter()
    for path in glob.glob('results/cal6/softmap/g_*.txt.json'):
        t = float(re.search(r'g_([0-9.]+)_b?\d+\.txt\.json', path).group(1))
        try:
            r = json.loads(open(path).read().strip().split('\n')[-1])['review']
        except Exception:
            continue
        games[t] += 1
        for p in r.get('phases', []):
            ph = PH.get(p['phase'])
            if ph is not None and p.get('skill_t') and p['moves'] >= 100:
                fits[ph][t].append(p['skill_t'])
    lines = []
    print("median fitted skill t (review, per phase) of soft:t games  [games with >= 100 moves in the phase]")
    for ph in sorted(fits):
        pts = []
        cells = []
        for t in sorted(fits[ph]):
            xs = fits[ph][t]
            if len(xs) < 3: continue
            m = st.median(xs)
            pts.append((t, m))
            cells.append(f"soft {t:g} -> {m:.4f} [{len(xs)}]")
        print(f"   phase {ph}: " + ';  '.join(cells))
        if len(pts) >= 2:
            lines.append(f"pskillmap {ph} " + ' '.join(f"{a:g} {b:.5g}" for a, b in pts))
    print('\n'.join(lines))
    if '--append' in sys.argv:
        path = sys.argv[sys.argv.index('--append') + 1]
        keep = [l for l in open(path) if not l.startswith('pskillmap ')]
        with open(path, 'w') as f:
            f.writelines(keep)
            f.write('\n'.join(lines) + '\n')
        print('->', path)

if __name__ == '__main__':
    main()
