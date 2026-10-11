#!/bin/bash
# cal6 queue D (after the r15 truth run): more soft:t games for the skill map (phases 2-3 were thin), then 60 more
# 16384-phase real positions for the 32768 odds truth (truth2_r15).
cd "$(dirname "$0")/.."
ulimit -s unlimited
export MALLOC_ARENA_MAX=2
T=${T:-16}
until [ -s results/cal6/truth/truth_r15.tsv ]; do sleep 30; done
D=results/cal6/softmap
for t in 0.003 0.01 0.02; do
  [ -s $D/trace2_$t.txt ] || ./build/messy --preset best-notables --policy "soft:t=$t" --games 48 --per-game 0 \
    --threads $T --seed 78 --trace $D/trace2_$t.txt --out $D/games2_$t > $D/games2_$t.log 2>&1
  awk -v p="$D/g_${t}_b" 'BEGIN{n=0} /^$/{n++; next} {print > (p n ".txt")}' $D/trace2_$t.txt
  ls $D/g_${t}_b*.txt | xargs -P $T -I{} sh -c '[ -s {}.json ] || ./build/analyze --preset best-notables --review {} --json 2>/dev/null | tail -1 > {}.json'
done
echo done > $D/done2
f=results/cal6/truth/truth2_r15.tsv
[ -s $f ] || ./build/rollout --preset best --pool results/cal6/truth2_r15.bin --playouts 32 --horizon 0 \
  --stop-rank 15 --moves engine --threads $T --seed 6 --out $f.tmp > ${f%.tsv}.log 2>&1 && mv $f.tmp $f
echo done > results/cal6/queueD.done
