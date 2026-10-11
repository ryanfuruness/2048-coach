#!/usr/bin/env python3
"""Two-fold split by video for training on expert positions without contaminating the tests (workstream late,
2026-10-06). Every curated expert video with a 16384+ position contains some test position (disputes, judge sets,
cal6's xexpert), so: videos -> folds A/B (greedy, balanced by expert position count); a network trained on fold A's
expert views is evaluated only on fold B's test positions and vice versa ("cross-fit" claims files).

  exp_late_folds.py split OUT_PREFIX       -> OUT_PREFIX_{A,B}_sh.bin (expert root views per fold, second-half range),
                                              OUT_PREFIX_folds.tsv (video -> fold)
  exp_late_folds.py merge FOLDS.tsv SET IDX_OR_- OUT.jsonl CLAIMS_TRAINED_A.jsonl CLAIMS_TRAINED_B.jsonl
        SET = claims (the 210 disputes; IDX '-') or judge (IDX = the judge .idx): each line from the network that did
        NOT train on the position's video (positions of unknown video: from A's file).
"""
import csv, json, struct, sys, collections
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from exp_late_pool import downgrade_view  # noqa: E402


def hex2vid():
    m = {}
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        m.setdefault(a['hex'], a['video'])
    return m


def split(out):
    per = collections.defaultdict(list)
    for line in open('results/human_ds/analysis.jsonl'):
        a = json.loads(line)
        if a.get('tier') != 'expert' or a.get('game_over') or max(max(r) for r in a['board']) < 16384:
            continue
        v = downgrade_view([int(c, 16) for c in a['hex']])
        s = sum(1 << x for x in v if x)
        if 28672 <= s < 36864:
            per[a['video']].append(sum(x << (4 * i) for i, x in enumerate(v)))
    fold, size = {}, {'A': 0, 'B': 0}
    for vid, bs in sorted(per.items(), key=lambda kv: -len(kv[1])):
        f = 'A' if size['A'] <= size['B'] else 'B'
        fold[vid] = f
        size[f] += len(bs)
    for f in 'AB':
        seen = set()
        with open(f'{out}_{f}_sh.bin', 'wb') as g:
            for vid, bs in per.items():
                if fold[vid] != f: continue
                for b in bs:
                    if b not in seen:
                        seen.add(b)
                        g.write(struct.pack('<Q', b))
        print(f"fold {f}: {sum(1 for v in fold.values() if v == f)} videos, {len(seen)} unique views -> {out}_{f}_sh.bin")
    # every video of the curated set gets a fold (videos without expert 16384+ positions: alternate)
    allv = sorted({json.loads(l)['video'] for l in open('results/human_ds/analysis.jsonl')})
    k = 0
    with open(f'{out}_folds.tsv', 'w') as g:
        for v in allv:
            if v not in fold:
                fold[v] = 'AB'[k % 2]
                k += 1
            g.write(f"{v}\t{fold[v]}\n")


def merge(folds_path, kind, idx_path, out, ca, cb):
    fold = dict(l.rstrip('\n').split('\t') for l in open(folds_path))
    if kind == 'claims':
        vids = [r['video'] for r in csv.DictReader(open('results/disputes/expert.tsv'), delimiter='\t')]
    else:
        sys.path.insert(0, __file__.rsplit('/', 1)[0])
        from exp_late_judge import load, DEFAULT
        lines = open(idx_path).read().splitlines()
        files, body = (DEFAULT, lines) if '\t' in lines[0] else (lines[0].split(','), lines[1:])
        pos = load(files, 0)
        h2v = hex2vid()
        vids = [h2v.get(pos[tuple(int(x) for x in l.split())]['board'], '') for l in body]
    la, lb = open(ca).read().splitlines(), open(cb).read().splitlines()
    n = collections.Counter()
    with open(out, 'w') as g:
        for i, v in enumerate(vids):
            # trained on A -> use for positions of fold B
            src = la if fold.get(v) == 'B' else lb if fold.get(v) == 'A' else la
            n[fold.get(v, '?')] += 1
            g.write(src[i] + '\n')
    print(f"{out}: positions by fold {dict(n)}")


if __name__ == '__main__':
    if sys.argv[1] == 'split':
        split(sys.argv[2])
    else:
        merge(*sys.argv[2:8])
