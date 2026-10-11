#!/bin/bash
# Copy every workstream's results (and new weights under weights/<ws>/) back from the research machine.
# Run before the instance's 24 h cap (stops ~21:15 +04 on 2026-10-07). Safe to repeat (rsync).
cd "$(dirname "$0")"; . ./env.sh
ID=$(instance_id); IP=$(instance_ip "$ID")
[ -z "$IP" ] || [ "$IP" = None ] && { echo "no running instance (id: $ID)"; exit 1; }
cd ../..
RS="rsync -az -e \"ssh $SSH_OPTS\""
for X in mx late coach cal6 pdf fuzz; do
  mkdir -p results/$X
  eval $RS ubuntu@$IP:2048_$X/results/$X/ results/$X/ && echo "results/$X: ok" || echo "results/$X: FAILED"
done
# new weights worth keeping (the rest of weights/late is negative results; weights/pdf was rebuilt on the laptop with
# matching fingerprints, so it is NOT copied: 50 GB)
mkdir -p weights/late
eval $RS --include "'bo_2.w'" --include "'*.bin'" --include "'*.tsv'" --exclude "'*'" ubuntu@$IP:2048/weights/late/ weights/late/ \
  && echo "weights/late (bo_2.w + pools): ok" || echo "weights/late: FAILED"
for X in hm:hm hm2:hm2 cal7:cal7 score:scorecard integ:integ late2:late2 review:review hm3:hm3 anypos:anypos plan:plan expl:expl cal8:cal8 serve:serve; do  # results of the later workstreams (dir:subdir)
  D=${X%%:*}; S=${X##*:}
  mkdir -p results/$S
  eval $RS ubuntu@$IP:2048_$D/results/$S/ results/$S/ 2>/dev/null && echo "results/$S: ok" || echo "results/$S: (none)"
done
date
