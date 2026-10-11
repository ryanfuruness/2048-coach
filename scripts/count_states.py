def counts(caps, smax):
    cnt = [0]*(smax//2+1); cnt[0] = 1
    for c in caps:
        new = [0]*(smax//2+1)
        for s, v in enumerate(cnt):
            if not v: continue
            new[s] += v
            for r in range(1, c+1):
                t = s + (1 << r)//2
                if t <= smax//2: new[t] += v
        cnt = new
    return cnt
# k5 free cells: row1: 4,5,6 ; row2: 8,9,10,11 ; row3: 12..15
for label, caps in [("all 9", [9]*11),
                    ("near-goal 9, mid 8, row3 7", [8,9,9, 8,8,9,9, 7,7,7,7]),
                    ("near-goal 9, rest 8", [8,9,9, 8,8,9,9, 8,8,8,8]),
                    ("6,11:9 ; 5,10:9 ; others 8 ; row3 7 except 15:8", [8,9,9, 8,8,9,9, 7,7,7,8]),
                    ("macroxue-like tight", [8,9,9, 8,8,8,9, 7,7,7,7])]:
    for smax in (1536, 2048, 2560):
        c = counts(caps, smax)
        print("%-50s sum<=%d: %.3g states, max layer %.3g" % (label, smax, sum(c), max(c)))
