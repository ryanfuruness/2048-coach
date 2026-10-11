#!/bin/bash
# Run ON the instance after setup_remote.sh and push.sh: build everything, then recompute the k5 layered tables
# (60 + 27.5 GB) and check them against fingerprints of the laptop's copies (first and last 64 MB).
#   scripts/aws/ssh.sh 'cd 2048 && nohup scripts/aws/remote_init.sh > init.log 2>&1 &'
set -e
cd ~/2048
make -j"$(nproc)" all 2>&1 | grep -E "error|warning" || true
mkdir -p weights/endgame_lt results
T=$(nproc)
solve() {  # name k rank caps md5_head md5_tail
  local f=weights/endgame_lt/$1.lt
  if [ ! -f weights/endgame_lt/$1.done ]; then
    ./build/layered --k $2 --rank $3 --caps $4 --out $f --threads $T > results/$1_solve.log 2>&1
    touch weights/endgame_lt/$1.done
  fi
  local h t
  h=$(head -c 67108864 $f | md5sum | cut -d' ' -f1)
  t=$(tail -c 67108864 $f | md5sum | cut -d' ' -f1)
  if [ "$h" = "$5" ] && [ "$t" = "$6" ]; then echo "$1: OK ($(stat -c %s $f) bytes)"
  else echo "$1: MISMATCH head $h tail $t"; exit 1; fi
}
solve k5r10 5 10 9,9,8,8,8,9,9,7,7,7,7 f71af0a34cff9def9fe4536f798670c0 6204883ac384c6ee4af7e3d1225fdd05
solve k5r9 5 9 8,8,7,7,7,8,8,7,7,7,7 4796680b43435a43c5ab651e2ab50398 7cc10cfca5900e661cfdb31b87ad11ee
echo "init done: $(date)"
