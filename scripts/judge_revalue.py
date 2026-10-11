#!/usr/bin/env python3
"""Re-value judged positions with another engine, keeping the rollout truth: replaces the 'value' and 'engine_move'
columns of rollout judge TSVs (build/rollout output) with build/analyze's values for the same boards, so that the
loss maps can be refit for a new network without rerunning the playouts (the real losses stay those measured with
the old engine's continuation). Writes OUTDIR/<same file name>.
usage: judge_revalue.py OUTDIR "ENGINE FLAGS" ROLLOUT.tsv ...   (run where the engine's files are, e.g. the instance)"""
import json, os, subprocess, sys

def main():
    outdir, engine, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(outdir, exist_ok=True)
    for path in files:
        lines = open(path).read().rstrip('\n').split('\n')
        hdr = lines[0].split('\t'); h = {k: i for i, k in enumerate(hdr)}
        rows = [l.split('\t') for l in lines[1:]]
        boards = sorted(set(r[h['board']] for r in rows))
        out = subprocess.run(['bash', '-c', f'ulimit -s unlimited; ./build/analyze --preset best {engine} --no-calib --stdin'],
                             input=''.join(b + '\n' for b in boards), capture_output=True, text=True).stdout.strip().split('\n')
        val = {}
        for b, line in zip(boards, out):
            a = json.loads(line)
            val[b] = ({m['move'][0].upper(): m['value'] for m in a['moves']}, (a.get('engine_move') or '-')[0].upper())
        with open(os.path.join(outdir, os.path.basename(path)), 'w') as f:
            f.write(lines[0] + '\n')
            for r in rows:
                v, em = val[r[h['board']]]
                if r[h['move']] in v:
                    r[h['value']] = f"{v[r[h['move']]]:.1f}"; r[h['engine_move']] = em
                f.write('\t'.join(r) + '\n')
        print(path, '->', outdir)

if __name__ == '__main__':
    main()
