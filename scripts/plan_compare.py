#!/usr/bin/env python3
"""Old (stored in results/human_ds_v6b/analysis.jsonl) vs new (build/analyze now) plan texts on a random sample:
how many changed, by old -> new plan type, with examples. usage: plan_compare.py [N] [--examples K]"""
import collections, json, random, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_study import text_type

def ntype(p):
    if p.startswith('Your ') and 'sits next to the' in p:
        return 'pair'
    if 'can merge into it (the engine prefers' in p:
        return 'merge(wait)'
    if p.startswith('Keep the') and 'build up the' in p:
        return 'single(named)'
    if p.startswith('Keep the') and '; your chain' in p:
        return 'single(subchain)'
    return text_type(p)

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    k_ex = int(sys.argv[sys.argv.index('--examples') + 1]) if '--examples' in sys.argv else 2
    rows = open('results/human_ds_v6b/analysis.jsonl').readlines()
    random.seed(11)
    sample = [json.loads(x) for x in random.sample(rows, n)]
    inp = ''.join(' '.join(str(v) for r in a['board'] for v in r) + '\n' for a in sample)
    out = subprocess.run(['./build/analyze', '--preset', 'best-notables', '--stdin', '--json'], input=inp,
                         capture_output=True, text=True).stdout.splitlines()
    ch = collections.Counter(); ex = collections.defaultdict(list)
    for a, line in zip(sample, out):
        b = json.loads(line)
        old, new = a.get('plan', ''), b.get('plan', '')
        if old != new:
            key = (text_type(old), ntype(new))
            ch[key] += 1
            if len(ex[key]) < k_ex:
                ex[key].append((a['board'], old, new))
    print(f'{len(out)} positions, {sum(ch.values())} plan texts changed')
    for key, c in ch.most_common():
        print(f'  {key[0]:10s} -> {key[1]:14s} {c}')
        for board, old, new in ex[key]:
            print('      board', board)
            print('      old:', old)
            print('      new:', new)

if __name__ == '__main__':
    main()
