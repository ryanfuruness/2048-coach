#!/usr/bin/env python3
"""Theta map of the personal model (workstream hm2; the human-model counterpart of scripts/hm_skillmap.py): the skill
theta that a game review fits (build/analyze --review: maximum likelihood of the played moves under the human move
model, src/human.h, per phase) to the games of the personal model's key-k players (scripts/hm_thetamap.sh) ->
'pthetamap PHASE k1 theta1 k2 theta2 ...' lines (trimmed means over the games with >= 100 moves in the phase). The
analysis then maps a player's own fitted theta to the key whose simulated players move like them (no softmax step).
usage: hm_thetamap.py [--dir results/hm2/thetamap] [--append personal.txt]"""
import glob, json, re, statistics as st, sys, collections

PH = {'up to 512': 0, '1024-2048': 1, '4096-8192': 2, '16384+': 3}

def main():
    d = sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else 'results/hm2/thetamap'
    fits = collections.defaultdict(lambda: collections.defaultdict(list))
    tfits = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in glob.glob(d + '/g_*.txt.json'):
        k = float(re.search(r'g_([0-9.]+)_\d+\.txt\.json', path).group(1))
        try:
            r = json.loads(open(path).read().strip().split('\n')[-1])['review']
        except Exception:
            continue
        for p in r.get('phases', []):
            ph = PH.get(p['phase'])
            if ph is not None and p.get('skill') is not None and p['moves'] >= 100:
                fits[ph][k].append(p['skill'])
                if p.get('skill_t'): tfits[ph][k].append(p['skill_t'])
    lines = []
    print("trimmed mean of the fitted human-model skill theta per phase of the key-k players' games [games; sd; "
          "separation = step to the next key / sd]   (the softmax review t: geometric mean)")
    for ph in sorted(fits):
        pts = []
        keys = sorted(fits[ph], reverse=True)  # weakest first
        rows = []
        for k in keys:
            xs = sorted(fits[ph][k])
            if len(xs) < 5: continue
            cut = len(xs) // 10
            core = xs[cut:len(xs) - cut] if len(xs) - 2 * cut >= 3 else xs
            m = sum(core) / len(core)
            sd = st.pstdev(xs) if len(xs) > 1 else 0.0
            ts = tfits[ph][k]
            tg = (2.718281828 ** (sum(__import__('math').log(t) for t in ts) / len(ts))) if ts else float('nan')
            rows.append((k, m, sd, len(xs), tg))
            pts.append((k, m))
        print(f"phase {ph}:")
        for i, (k, m, sd, n, tg) in enumerate(rows):
            sep = (rows[i + 1][1] - m) / sd if i + 1 < len(rows) and sd > 0 else float('nan')
            print(f"   key {k:<8g} theta {m:+.3f}  sd {sd:.3f}  games {n:3d}  separation to next {sep:5.2f}   t {tg:.4f}")
        # the map must be monotone (theta rises as the key falls): pool adjacent violators
        pts.sort(key=lambda x: -x[0])  # weakest key first: theta should increase
        merged = []
        for k, m in pts:
            merged.append([[k], m, 1])
            while len(merged) >= 2 and merged[-2][1] > merged[-1][1]:
                a, b = merged[-2], merged.pop()
                a[1] = (a[1] * a[2] + b[1] * b[2]) / (a[2] + b[2]); a[0] += b[0]; a[2] += b[2]
        out = []
        for ks, m, _ in merged:
            kk = __import__('math').exp(sum(__import__('math').log(x) for x in ks) / len(ks))
            out.append((kk, m))
        if len(out) >= 2:
            lines.append(f"pthetamap {ph} " + ' '.join(f"{k:.6g} {m:.4f}" for k, m in sorted(out)))
    for l in lines: print(l)
    if '--append' in sys.argv:
        path = sys.argv[sys.argv.index('--append') + 1]
        keep = [l for l in open(path) if not l.startswith('pthetamap')]
        with open(path, 'w') as f:
            f.writelines(keep)
            for l in lines: f.write(l + '\n')
        print(f"appended to {path}")

if __name__ == '__main__':
    main()
