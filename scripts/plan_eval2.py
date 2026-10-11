#!/usr/bin/env python3
"""Before/after evaluation of the plan (workstream plan): the OLD plans (scripts/plan_lib.py port) and the NEW plans
(build/analyze's plan_info, run now on the sampled positions) checked on the same continuations (the engine's:
results/plan/run1/engine_*.jsonl; the players': results/plan/sample.jsonl). Also the merge plans' consistency with
the engine's best move. usage: plan_eval2.py [--new-info results/plan/info_new.jsonl]"""
import collections, glob, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_lib as pl
STAGES = ('<=512', '1024-2048', '4096-8192', '16384+')


def main():
    info_path = 'results/plan/info_new.jsonl'
    if '--new-info' in sys.argv:
        info_path = sys.argv[sys.argv.index('--new-info') + 1]
    recs = {}
    for l in open('results/plan/sample.jsonl'):
        r = json.loads(l)
        recs[r['id']] = r
    if not os.path.exists(info_path):
        ids = sorted(recs)
        inp = ''.join(' '.join(str(v) for row in recs[i]['board'] for v in row) + '\n' for i in ids)
        out = subprocess.run(['./build/analyze', '--preset', 'best-notables', '--stdin', '--json'], input=inp,
                             capture_output=True, text=True).stdout.splitlines()
        with open(info_path, 'w') as f:
            for i, line in zip(ids, out):
                a = json.loads(line)
                f.write(json.dumps({'id': i, 'plan': a.get('plan', ''), 'plan_info': a.get('plan_info'),
                                    'engine_move': a.get('engine_move')}) + '\n')
    new = {json.loads(l)['id']: json.loads(l) for l in open(info_path)}
    eng = {}
    for fn in glob.glob('results/plan/run1/engine_*.jsonl'):
        for l in open(fn):
            e = json.loads(l)
            eng[e['id']] = [pl.ranks_of_hex(h) for h in e['boards']]
    rows = collections.defaultdict(list)
    for i, r in recs.items():
        if r['type'] == 'block':
            continue
        I_old, I_new = pl.old_info(r['ranks']), new[i]['plan_info']
        for ver, I in (('old', I_old), ('new', I_new)):
            key = I['type'] if I['type'] not in ('single', 'pair') else I['type'] + ':' + I.get('step', I['type'])
            for grp, seq in (('engine', eng.get(i)), ('players', r['human'])):
                if seq is None:
                    continue
                ev = pl.events2(I, r['ranks'], seq)
                if 'main' in ev:
                    rows[(ver, grp, key, r['stage'])].append(ev['main'])
                    rows[(ver, grp, 'ALL', r['stage'])].append(ev['main'])
    def fmt(v):
        v = [x for x in v if x is not None]
        return f'{sum(v) / len(v):5.2f} ({len(v):3d})' if v else '     -     '
    keys = sorted({k[2] for k in rows})
    for grp in ('engine', 'players'):
        print(f'\n== {grp} continuation: share of plans whose predicted event happened within the horizon (n)')
        print('   ' + ' ' * 26 + ''.join(f'{s:>14s}' for s in STAGES) + '           all')
        for k in keys:
            for ver in ('old', 'new'):
                cells = [rows[(ver, grp, k, s)] for s in STAGES]
                if not any(cells):
                    continue
                line = f'   {k:18s} {ver:4s} ' + ''.join(f'   {fmt(c)}' for c in cells)
                print(line + f'   {fmt([x for c in cells for x in c])}')
    # merge plans vs the engine's best move: does the best move make the plan's merge?
    print('\n== merge plans: the engine\'s best move makes the merge the plan names (old: always phrased "Merge ...")')
    cnt = collections.Counter()
    for i, r in recs.items():
        p = new[i]['plan']
        if 'Merge the' in p and 'into it' in p:
            cnt['new: "Merge ..." (best move makes it)'] += 1
        elif 'can merge into it (the engine prefers' in p:
            cnt['new: "can merge ... (the engine prefers X first)"'] += 1
    for k, v in cnt.items():
        print(f'   {k}: {v}')


if __name__ == '__main__':
    main()
