#!/usr/bin/env python3
"""cal7: MODEL.txt + map lines from OVERRIDE.txt (same keys replaced, new keys appended) -> OUT.txt
usage: calib_merge_maps.py MODEL.txt OVERRIDE.txt OUT.txt"""
import sys
model, over, out = sys.argv[1:4]
new = [l for l in open(over) if l.strip()]
keys = {l.split()[0] for l in new}
keep = [l for l in open(model) if l.split() and l.split()[0] not in keys]
open(out, 'w').writelines(keep + new)
print(f"{out}: {len(keep)} lines kept, {len(new)} replaced/added ({', '.join(sorted(keys))})")
