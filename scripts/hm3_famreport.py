#!/usr/bin/env python3
"""Workstream hm3: report of a playout-family run (scripts/hm3_family.sh): per (key, Q) the outcome rates, the stretch
statistics (scripts/hm3_stretch.py) and the skill readings of the reviewed games (softmax t: trimmed geometric mean
per phase, as hm_skillmap.py; human-model theta: mean per phase), next to the real players' numbers by tier.
usage: hm3_famreport.py DIR [--json OUT]"""
import collections, glob, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hm3_stretch as HS

def tgm(xs):
    xs = sorted(x for x in xs if x and x > 0)
    if not xs: return float('nan')
    k = len(xs) // 10
    xs = xs[k:len(xs) - k] or xs
    return math.exp(sum(math.log(x) for x in xs) / len(xs))

def readings(revdir):
    t = collections.defaultdict(list); th = collections.defaultdict(list); w = collections.defaultdict(list)
    names = {'up to 512': 0, '1024-2048': 1, '4096-8192': 2, '16384+': 3}
    for f in glob.glob(revdir + '/g_*.txt.json'):
        try:
            r = json.load(open(f))['review']
        except Exception:
            continue
        for p in r.get('phases', []):
            ph = names.get(p.get('phase'), None)
            if ph is None or p.get('moves', 0) < 50: continue
            if p.get('skill_t'): t[ph].append(p['skill_t'])
            if p.get('skill') is not None: th[ph].append(p['skill'])
    return {ph: (tgm(t[ph]), sum(th[ph]) / max(1, len(th[ph])), len(t[ph])) for ph in sorted(t)}

def outcomes(tsv):
    fm = {}
    with open(tsv) as f:
        h = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(h, line.rstrip('\n').split('\t')))
            fm[r['game']] = int(r['final_max'])
    n = max(1, len(fm))
    return {T: sum(v >= T for v in fm.values()) / n for T in (512, 1024, 2048, 4096, 8192)}, len(fm)

def main():
    d = sys.argv[1]
    out = {}
    print(f"{'config':18s} {'reach 512 1024 2048 4096 8192':34s} {'readings t/theta by phase':40s}")
    for tsv in sorted(glob.glob(d + '/k*_q*.tsv'), key=lambda p: (float(re.search(r'_q([0-9.]+?)\.tsv', p).group(1)), -float(re.search(r'k([0-9.]+)_', p).group(1)))):
        L = tsv[:-4]
        name = os.path.basename(L)
        oc, ng = outcomes(tsv)
        rd = readings(L + '.rev') if os.path.isdir(L + '.rev') else {}
        rs = '  '.join(f"p{ph}: {t:.3f}/{th:+.2f} ({n})" for ph, (t, th, n) in rd.items())
        print(f"{name:18s} " + ' '.join(f"{oc[T]:.2f}" for T in (512, 1024, 2048, 4096, 8192)) + f" ({ng})   {rs}")
        st = HS.sim('   ' + name, L + '.trace') if os.path.exists(L + '.trace') else {}
        out[name] = dict(outcomes=oc, readings={ph: list(v) for ph, v in rd.items()}, stretch=st)
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'))

if __name__ == '__main__':
    main()
