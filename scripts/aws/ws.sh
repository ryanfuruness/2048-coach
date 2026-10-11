#!/bin/bash
# Per-workstream work directories on the research machine (24-hour plan, 2026-10-06): ~/2048_X has its own copy of the
# code, its own build and results; weights are shared (symlink to ~/2048/weights: networks, k6 tables, the 88 GB k5
# tables, pools).
#   ws.sh push X               copy the laptop's src, scripts, Makefile to ~/2048_X (creates it, links the weights)
#   ws.sh build X [targets]    push, then make -j there (default: all)
#   ws.sh put X PATH [DEST]    copy a laptop file or directory (relative to the project, or absolute) to ~/2048_X/DEST
#                              (default DEST: the same relative path; absolute PATHs go to ~/2048_X/data/)
#   ws.sh pull X SUBDIR        copy ~/2048_X/results/SUBDIR back to the laptop's results/SUBDIR
#   ws.sh run X 'command'      run a command in ~/2048_X (non-interactive; use nohup ... & for long jobs)
cd "$(dirname "$0")"; . ./env.sh
ID=$(instance_id); IP=$(instance_ip "$ID")
[ -z "$IP" ] || [ "$IP" = None ] && { echo "no running instance (id: $ID)"; exit 1; }
CMD=$1; X=$2; shift 2
[ -z "$X" ] && { echo "usage: ws.sh push|build|put|pull|run X ..."; exit 1; }
D=2048_$X
cd ../..
RS="rsync -az -e \"ssh $SSH_OPTS\""
case $CMD in
  push|build)
    ssh $SSH_OPTS ubuntu@$IP "mkdir -p $D/results && { [ -e $D/weights ] || ln -s ~/2048/weights $D/weights; }"
    eval $RS --exclude "'*.o'" --exclude "'*.tmp'" src scripts Makefile ubuntu@$IP:$D/ || exit 1
    if [ $CMD = build ]; then
      ssh $SSH_OPTS ubuntu@$IP "cd $D && make -j32 BUILD=build ${*:-all} 2>&1 | grep -E 'error|Error' ; ls -la build | tail -n +2 | wc -l"
    fi ;;
  put)
    SRC=$1; DEST=$2
    if [ -z "$DEST" ]; then case $SRC in /*) DEST=data/ ;; *) DEST=$(dirname "$SRC")/ ;; esac; fi
    ssh $SSH_OPTS ubuntu@$IP "mkdir -p $D/$DEST"
    eval $RS "$SRC" ubuntu@$IP:$D/$DEST ;;
  pull)
    SUB=$1; [ -z "$SUB" ] && { echo "usage: ws.sh pull X SUBDIR"; exit 1; }
    mkdir -p "results/$SUB"
    eval $RS ubuntu@$IP:$D/results/$SUB/ "results/$SUB/" ;;
  run)
    ssh $SSH_OPTS ubuntu@$IP "cd $D && $*" ;;
  *) echo "unknown command $CMD"; exit 1 ;;
esac
