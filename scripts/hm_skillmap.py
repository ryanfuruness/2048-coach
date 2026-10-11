#!/usr/bin/env python3
"""Skill map of the human-model players (workstream hm; as scripts/calib_softmap.py for soft:t players): the review's
fitted skill temperature (search values, per phase) of games by human-model players with key t (scripts/hm_personal.sh)
-> 'pskillmap PHASE t_key1 t_fit1 ...' lines for the personal model (the analysis converts a player's reviewed skill to
the model's key before computing personal odds); --append also writes the line "player human".
usage: hm_skillmap.py [--dir results/hm/skillmap2] [--append personal.txt]"""
import glob, json, math, re, statistics as st, sys, collections

PH = {'up to 512': 0, '1024-2048': 1, '4096-8192': 2, '16384+': 3}

def main():
    fits = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in glob.glob((sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else 'results/hm/skillmap') + '/g_*.txt.json'):
        t = float(re.search(r'g_([0-9.]+)_\d+\.txt\.json', path).group(1))
        try:
            r = json.loads(open(path).read().strip().split('\n')[-1])['review']
        except Exception:
            continue
        for p in r.get('phases', []):
            ph = PH.get(p['phase'])
            if ph is not None and p.get('skill_t') and p['moves'] >= 100:
                fits[ph][t].append(p['skill_t'])
    lines = []
    print("trimmed geometric mean of the fitted skill t (review, per phase) of human-model games  [games with >= 100 moves in the phase]")
    for ph in sorted(fits):
        pts = []; cells = []
        for t in sorted(fits[ph], reverse=True):
            xs = fits[ph][t]
            if len(xs) < 3: continue
            # trimmed geometric mean (the review fits t on a 10% grid: medians land on grid points)
            ls = sorted(math.log(x) for x in xs); k = len(ls) // 10
            ls = ls[k:len(ls) - k] or ls
            m = math.exp(sum(ls) / len(ls))
            pts.append((t, m)); cells.append(f"{t:g} -> {m:.4f} [{len(xs)}]")
        print(f"   phase {ph}: " + ';  '.join(cells))
        # the map must be monotone (stronger key -> smaller fitted t): keep the monotone part
        mono = []
        for a, b in sorted(pts):
            if not mono or b > mono[-1][1]: mono.append((a, b))
        if len(mono) >= 2:
            lines.append(f"pskillmap {ph} " + ' '.join(f"{a:g} {b:.5g}" for a, b in mono))
    print('\n'.join(lines))
    if '--append' in sys.argv:
        path = sys.argv[sys.argv.index('--append') + 1]
        keep = [l for l in open(path) if not l.startswith('pskillmap ') and not l.startswith('player ')]
        with open(path, 'w') as f:
            # the playout policy behind the model (calib.h PersonalModel::player; analyze picks the policy and the
            # output field by it): the human move model of src/human.h, key k -> skill s = -ln(100 k)
            f.write('player human\n')
            f.writelines(keep)
            f.write('\n'.join(lines) + '\n')
        print('->', path)

if __name__ == '__main__':
    main()
