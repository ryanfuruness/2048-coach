#!/usr/bin/env python3
"""Regression check of the plan text: re-analyse a sample of the stored positions of results/human_ds_v6b/analysis.jsonl
with build/analyze and compare the "plan" strings (the refactor into ex::plan_info must keep the text identical).
usage: plan_textcheck.py [N] [--seed S]"""
import json, random, subprocess, sys

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    rows = []
    with open('results/human_ds_v6b/analysis.jsonl') as f:
        for line in f:
            rows.append(line)
    random.seed(7)
    sample = [json.loads(x) for x in random.sample(rows, n)]
    inp = ''.join(' '.join(str(v) for r in a['board'] for v in r) + '\n' for a in sample)
    out = subprocess.run(['./build/analyze', '--preset', 'best-notables', '--stdin', '--json'], input=inp,
                         capture_output=True, text=True).stdout.splitlines()
    diff = 0
    for a, line in zip(sample, out):
        b = json.loads(line)
        if b.get('plan', '') != a.get('plan', ''):
            diff += 1
            if diff <= 10:
                print('DIFF', a['hex'], '\n  old:', a.get('plan'), '\n  new:', b.get('plan'))
    print(f'{len(out)} positions, {diff} plan texts differ')

if __name__ == '__main__':
    main()
