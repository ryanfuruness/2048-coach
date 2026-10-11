#!/bin/bash
# Deaths of a whole-phase play log (games stopping at sum 36864) binned by tile sum, in % of all games.
# usage: scripts/death_bins.sh LOG [LOG...]
for f in "$@"; do
  awk -v name="$(basename $f .log)" '/^game / {n++; s=$NF; if (s >= 36864) next;
      if (s<24576) b=1; else if (s<28672) b=2; else if (s<30720) b=3; else if (s<31744) b=4; else if (s<32768) b=5; else b=6; c[b]++}
    END {printf "%-22s n=%4d  <24576 %4.1f  24576-28672 %4.1f  28672-30720 %4.1f  30720-31744 %4.1f | 31744-32768 %4.1f  >=32768 %4.1f | pre %4.1f post %4.1f\n",
      name, n, 100*c[1]/n, 100*c[2]/n, 100*c[3]/n, 100*c[4]/n, 100*c[5]/n, 100*c[6]/n, 100*(c[1]+c[2]+c[3]+c[4])/n, 100*(c[5]+c[6])/n}' "$f"
done
