#!/usr/bin/env python3
"""Block-formation detector variants (relaxed: no max-in-corner requirement) on mx's labeled positions and on our
engine's own late positions (replayed from results/bench/late_t21/games*.txt)."""
import sys, collections, random
sys.path.insert(0, 'scripts')
from pdf_detect import sym, move, load, BLOCK6

def topk_in_block(b, k, mind):
    tk = sorted(b, reverse=True)[:k]
    if tk[-1] < tk[0] - mind: return False
    for j in range(8):
        s = sym(b, j)
        if sorted((s[c] for c in BLOCK6), reverse=True)[:k] == tk: return True
    return False

def detect(b, k, mind, moves):
    if topk_in_block(b, k, mind): return True
    if moves:
        for d in range(4):
            a = move(b, d)
            if a != b and topk_in_block(a, k, mind): return True
    return False

def replay(path, ngames, every, min_rank):
    out = []
    for gi, line in enumerate(open(path)):
        if gi >= ngames: break
        p = line.split()
        start, rec = p[3], p[4] if len(p) > 4 else ''
        b = ['0123456789abcdefghijklmnopqrstuv'.index(c) for c in start]
        n = 0
        for i in range(0, len(rec) - 2, 3):
            d = 'URDL'.index(rec[i]); c = int(rec[i + 1], 16); t = 1 if rec[i + 2] == '2' else 2
            b = move(b, d); b[c] = t; n += 1
            if n % every == 0 and max(b) >= min_rank: out.append(list(b))
    return out

def main():
    rows = load()
    eng = []
    for f in range(10):
        eng += replay(f'results/bench/late_t21/games{f}.txt', 6, 25, 14)
    random.seed(1); random.shuffle(eng); eng = eng[:3000]
    print(f"engine late positions (max >= 16384): {len(eng)}")
    for k in (4, 5, 6):
        for mind in (6, 8, 10):
            for mv in (0, 1):
                c = collections.Counter(); n = collections.Counter()
                for d in rows:
                    key = ('PDF' if d['player'] == 'd4Nf6Bg5' else 'snake', d['group'])
                    n[key] += 1; c[key] += detect(d['b'], k, mind, mv)
                e = sum(detect(b, k, mind, mv) for b in eng)
                print(f"k{k} mind{mind:2d} mv{mv}: " + '  '.join(f"{a[:3]}/{g[:4]} {c[(a, g)]:3d}/{n[(a, g)]}" for a, g in sorted(n))
                      + f"   engine {e}/{len(eng)} ({100 * e / len(eng):.1f}%)")

if __name__ == '__main__':
    main()
