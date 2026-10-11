#!/usr/bin/env python3
"""Copies the weights of a human model file (scripts/hm_export.py output) into the defaults of src/human.h.
usage: hm_sync_header.py MODEL.txt [src/human.h]"""
import re, sys
FEATS = ["corner", "corner_lost", "chain_len", "chain_drop", "exposed", "trapped", "big_off_edge", "corner_dist",
         "merges_next", "empty", "moved", "merge", "merge_size", "death", "line_toward", "line_away", "perp_away"]
def main():
    src, hdr = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'src/human.h')
    ws, wh = {}, {}
    for line in open(src):
        p = line.split()
        if not p: continue
        if p[0] == 'wv': kn, wv = p[1::2], p[2::2]
        elif p[0] == 'ws': ws[p[1]] = p[2]
        elif p[0] == 'wh': wh[p[1]] = p[2]
        elif p[0] == 'eps': eps = p[1]
        elif p[0] == 'gab': ga, gb = p[1], p[2]
    s = open(hdr).read()
    s = re.sub(r'double knots\[6\] = \{[^}]*\};', 'double knots[6] = {' + ', '.join(kn) + '};', s)
    s = re.sub(r'double wv\[6\] = \{[^}]*\};', 'double wv[6] = {' + ', '.join(wv) + '};', s)
    body = ', '.join(ws[f] for f in FEATS)
    s = re.sub(r'double ws\[kNumFeat\] = \{[^}]*\};', 'double ws[kNumFeat] = {' + body + '};', s, flags=re.S)
    s = re.sub(r'double w_repeat = [^;]*;', f"double w_repeat = {wh['repeat']}, w_alternate = {wh['alternate']}, "
               f"w_recent_share = {wh.get('recent_share', '0.0')}, w_unused = {wh.get('unused', '0.0')};", s)
    s = re.sub(r'double eps = [^;]*;', f'double eps = {eps};', s)
    s = re.sub(r'double ga = [^,]*, gb = [^;]*;', f'double ga = {ga}, gb = {gb};', s)
    open(hdr, 'w').write(s)
if __name__ == '__main__':
    main()
