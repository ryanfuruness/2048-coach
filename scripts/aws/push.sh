#!/bin/bash
# Copy the code and data to the instance.
#   push.sh code   - sources, scripts, Makefile, notes (seconds)
#   push.sh core   - code + the best player (weights/best_v5.w) + the k6 tables (~4.8 GB): enough for analysis,
#                    calibration and rollout studies
#   push.sh all    - core + training files (s0cpu + checkpoint, OTD networks, stage files, pools; ~10 GB more)
# The k5 layered tables (88 GB) are NOT copied: scripts/aws/remote_init.sh recomputes and verifies them there.
cd "$(dirname "$0")"; . ./env.sh
ID=$(instance_id); IP=$(instance_ip "$ID")
[ -z "$IP" ] && { echo "no running instance"; exit 1; }
LEVEL=${1:-core}
cd ../..
RS="rsync -az --info=progress2 -e \"ssh $SSH_OPTS\""
eval $RS --exclude '*.o' --exclude '*.tmp' src scripts Makefile NOTES.md README.md viewer ubuntu@$IP:2048/
[ "$LEVEL" = code ] && exit 0
cd weights
eval $RS --relative best_v5.w endgame_big ubuntu@$IP:2048/weights/
[ "$LEVEL" = core ] && exit 0
find . -name '*.bin' > /tmp/push_pools.txt
eval $RS --files-from=- . ubuntu@$IP:2048/weights/ <<LIST
tup/s0cpu.w
tup/s0cpu.ckpt
expseed/s6.w
expsplit/b4s2.w
expotd/t18.w
expotd/t21.w
expcpu/start.w
LIST
eval $RS --files-from=/tmp/push_pools.txt . ubuntu@$IP:2048/weights/
