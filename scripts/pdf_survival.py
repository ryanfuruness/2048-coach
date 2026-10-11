#!/usr/bin/env python3
"""Death within 1000 moves from mx's 300 random expert positions (results/mx/random300.*), our full engine before
(results/mx/random300_ours_h1000.tsv) vs with the block tables (results/pdf/random300_blk_h1000.tsv), by player
group and max tile; plus how often the block tables decided the first move. usage: pdf_survival.py [after.tsv]"""
import sys, collections

def load_tsv(path, ids):
    out = {}
    with open(path) as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            out[ids[int(r['pos'])]] = r
    return out

def main():
    after = sys.argv[1] if len(sys.argv) > 1 else 'results/pdf/random300_blk_h1000.tsv'
    pos = {}
    with open('results/mx/positions.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for line in f:
            r = dict(zip(hdr, line.rstrip('\n').split('\t')))
            pos[r['id']] = r
    ids = [l.strip() for l in open('results/mx/random300.ids')]
    A = load_tsv('results/mx/random300_ours_h1000.tsv', ids)
    B = load_tsv(after, ids)
    g = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0, 0])
    for i in ids:
        if i not in A or i not in B: continue
        r = pos[i]
        grp = 'block player' if r['player'] == 'd4Nf6Bg5' else 'snake experts'
        for k in (grp, f"{grp} max {r['max']}"):
            s = g[k]
            s[0] += 1; s[1] += float(A[i]['died']); s[2] += float(B[i]['died'])
            s[3] += B[i]['source'] == 'block'
            s[4] += float(B[i]['died']) < float(A[i]['died']) - 0.15
            s[5] += float(A[i]['died']) < float(B[i]['died']) - 0.15
    print("| positions | n | died before | died with block tables | first move by a block table | clearly better | clearly worse |")
    print("|---|---|---|---|---|---|---|")
    for k in sorted(g):
        n, a, b, t, bt, wo = g[k]
        print(f"| {k} | {n} | {a / n:.3f} | {b / n:.3f} | {t} | {bt} | {wo} |")

if __name__ == '__main__':
    main()
