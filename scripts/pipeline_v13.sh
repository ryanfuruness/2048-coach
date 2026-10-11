#!/bin/bash
# v13: more capacity where the second half loses most games. The second half [28672, 36864) is
# split at 32768: [28672, 32768) is the network-played stretch (building the 2048/1024/512 into the
# snake: most second-half deaths are at sum 30720-32768) and gets its own network; [32768, 36864)
# keeps v11c's second-half network (mostly table-played endings). The new stage bootstraps at 32768
# from v11c's trained second half (never-trained weights neutralized), starts from v11c's mixed
# pool at 28672, and trains with the tables in the loop.
set -e
cd "$(dirname "$0")/.."
RUN=${RUN:-v13}  # (not NAME: WSL sets NAME to the host name)
SRC=${SRC:-weights/v11c/final.w}      # 4 stages, sum:20480/14,28672,36864
SRCCK=${SRCCK:-weights/v11c/s2q.ckpt} # TC accumulators of SRC's stage 2
POOL=${POOL:-weights/v11c/pool2mix.bin}
EG=${EG:-weights/endgame}
INIT=${INIT:-320000}
S_GAMES=${S_GAMES:-12000000}
Q_GAMES=${Q_GAMES:-1500000}
ST5="sum:20480/14,28672,32768,36864"
W=weights/$RUN
L=results/$RUN
mkdir -p "$W" "$L"
T=./build/gpu_train
NPOOL=$(( $(stat -c %s $POOL) / 8 ))
COMMON="--stop-at-boundary --tc --alpha 1.0 --lambda 0.5 --horizon 3 --games 32768 --save-every 2000000 --corner-lock 14 --endgame-dir $EG --endgame-min 0.5 --endgame-full 2 --endgame-min-rank 7 --skip-lower --pool $POOL --pool-last $NPOOL"
phase() { echo "[$(date '+%F %T')] $*" | tee -a "$L/pipeline.log"; }
run() {
  local n=$1 d=$2
  shift 2
  [ -f "$W/$n.w" ] && return 0
  phase "$n: $d"
  $T "$@" --save "$W/$n.w.part" --checkpoint "$W/$n.ckpt" > "$L/$n.log" 2>&1
  mv "$W/$n.w.part" "$W/$n.w"
}
if [ ! -f $W/init5.w ]; then
  python3 scripts/select_stages.py $SRC $W/init5.tmp.w 0,1,2,2,3   # [early, first half, new, end, rest]
  python3 scripts/neutralize.py $W/init5.tmp.w $W/init5.w 3:$SRCCK
  rm -f $W/init5.tmp.w
fi
run s2a "[28672,32768), fresh optimistic, lock, tables, bootstrap from v11c's second half ($S_GAMES games)" \
  --load $W/init5.w --stages $ST5 --train-stage 2 --fresh 2 --init $INIT $COMMON --log 500000 --episodes $S_GAMES
run s2aq "[28672,32768), 2-ply on 25% of the moves ($Q_GAMES games)" --load $W/s2a.w --stages $ST5 --train-stage 2 \
  --resume $W/s2a.ckpt --tc-decay 0.1 $COMMON --log 100000 --policy-depth 2 --policy-mix 0.25 --episodes $Q_GAMES
# the player: neutralized weights were only for training; stage 3 back to v11c's second half as is
if [ ! -f $W/final.w ]; then
  python3 scripts/splice_stage.py $W/s2aq.w 3 $SRC 2 $W/final.w
fi
phase "done: $W/final.w ($ST5; play with --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir $EG)"
