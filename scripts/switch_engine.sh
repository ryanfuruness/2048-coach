#!/bin/bash
# Switch the analysis engine to new late-game networks and refit what depends on their values (cal6's REFIT RECIPE,
# results/cal6/REPORT.md, reduced to what a late-stage change touches: every candidate so far replaces networks used
# only from the 16384 phase on, so only positions with a 16384+ are revalued in effect; the early maps come out the
# same and serve as a check).
#
#   scripts/switch_engine.sh prepare NAME "ENGINE FLAGS"   revalue the rollout truth with the new engine on the instance
#                                                          (~/2048_integ, T threads, default 8), refit the maps, write
#                                                          the candidate model results/calib/model_NAME.txt and the
#                                                          report results/integ/switch_NAME.txt (installs nothing)
#   scripts/switch_engine.sh refit NAME "ENGINE FLAGS"     steps 2-4 again from prepare's re-valued files (laptop only)
#   scripts/switch_engine.sh install NAME "ENGINE FLAGS"   weights/best.cfg <- the flags (preset best/best-notables of
#                                                          every tool then load the new networks), the candidate model
#                                                          -> weights/calib/model.txt (old one kept), selftest, tiers
# e.g. scripts/switch_engine.sh prepare v6 "--weights weights/best_v6.w"
#
# prepare, step by step:
#  1. instance: push + build analyze; copy the judge truth there (human300, late300 = results/judge; judge1200, xexpert,
#     jold = results/cal6) and the table boards; judge_revalue.py re-values every judged board with the new engine
#     (the rollout truth stays: measured with best_v5's continuation); the table positions are re-analysed for their
#     per-move table p
#  2. laptop: fit_lossmap2.py --no-block (block-formation positions excluded: the engine does not judge them) ->
#     early / late / top / played-expert maps with a 5-fold held-out comparison against the installed model;
#     fit_lossmap_table.py -> the table map
#  3. odds: the value term of the odds model is log(value / vbar(sum)); the new networks may value 16384-phase positions
#     on another scale, so vbar's knots from log2 sum 14 on are scaled by the median value ratio new / old of the
#     re-valued 16384+ positions (scripts/switch_vscale.py; the base rates stay best_v5's - the 32768 rate differs by
#     < 2 points for best_v6; a full odds refit is cal6's recipe steps 1-2)
#  4. warn line: the 16384+ threshold drops to the late level (0.05): the new networks' claims for snake experts are
#     close to the real losses (late, 2026-10-07: claims 10-15% -> 13% real, 20-30% -> 28%)
# The personal model (weights/calib/personal.txt) belongs to workstream hm and is not touched.
set -e
cd "$(dirname "$0")/.."
CMD=$1; NAME=$2; E=$3
[ -z "$CMD" ] || [ -z "$NAME" ] || [ -z "$E" ] && { sed -n 2,30p "$0"; exit 1; }
T=${T:-8}
OUT=results/integ/switch_$NAME.txt
R=results/integ/reval_$NAME

if [ "$CMD" = prepare ]; then
  echo "== prepare $NAME: $E ($(date))" | tee $OUT
  scripts/aws/ws.sh build integ build/analyze > /dev/null
  for f in results/judge/human300_h1000.tsv results/judge/late300_h1000.tsv; do scripts/aws/ws.sh put integ $f data/judge/ > /dev/null; done
  for d in j1200 jx jold; do scripts/aws/ws.sh put integ results/cal6/$d data/ > /dev/null; done  # -> data/<d>/
  scripts/aws/ws.sh put integ results/cal6/table_boards.txt data/ > /dev/null
  scripts/aws/ws.sh put integ scripts/judge_revalue.py scripts/ > /dev/null
  echo "   revaluing on the instance ($T threads)..." | tee -a $OUT
  # one re-valuing job per group and per quarter of judge1200's chunks (T threads: 8 jobs)
  scripts/aws/ws.sh run integ "rm -rf $R; mkdir -p $R; ulimit -s unlimited;
    (python3 scripts/judge_revalue.py $R/judge '$E' data/judge/human300_h1000.tsv data/judge/late300_h1000.tsv) &
    for k in 0 1 2 3; do (python3 scripts/judge_revalue.py $R/j1200_\$k '$E' \$(ls data/j1200/judge1200_*.tsv | awk \"NR % 4 == \$k\")) & done
    (python3 scripts/judge_revalue.py $R/jx '$E' data/jx/xexpert_*.tsv) &
    (python3 scripts/judge_revalue.py $R/jold '$E' data/jold/expert_*.tsv) &
    (./build/analyze --preset best $E --stdin < data/table_boards.txt > $R/table.jsonl 2> /dev/null) &
    wait; for k in 0 1 2 3; do mv $R/j1200_\$k/* $R/judge/; rmdir $R/j1200_\$k; done
    echo \"   re-valued files: \$(ls $R/judge $R/jx $R/jold | grep -c tsv) (expected 53), table positions: \$(wc -l < $R/table.jsonl)\"" | tee -a $OUT
  scripts/aws/ws.sh pull integ integ/reval_$NAME > /dev/null
fi
if [ "$CMD" = prepare ] || [ "$CMD" = refit ]; then  # refit: steps 2-4 again from the re-valued files of a prepare
  [ -f $R/table.jsonl ] || { echo "no re-valued files in $R: run prepare"; exit 1; }
  [ "$CMD" = refit ] && echo "== refit $NAME: $E ($(date))" | tee $OUT
  P=""; for f in $R/jx/*.tsv $R/jold/*.tsv; do P="$P played:$f"; done
  cp weights/calib/model.txt results/calib/model_$NAME.txt
  echo "== loss maps (block positions excluded), held-out vs the installed model" | tee -a $OUT
  # only the top and played-expert maps are replaced: the early and late positions' values do not change with late-game
  # networks (their held-out errors are printed as a check; the installed maps were fitted on all of the data)
  python3 scripts/fit_lossmap2.py --no-block --boot 100 --boot-players --heldout --compare weights/calib/model.txt \
    --only lossmap_top,lossmap_played_expert --model results/calib/model_$NAME.txt $R/judge/*.tsv $P 2>&1 | tee -a $OUT
  echo "== table map" | tee -a $OUT
  python3 scripts/fit_lossmap_table.py $R/table.jsonl --model results/calib/model_$NAME.txt $R/judge/late300_h1000.tsv \
    $R/judge/judge1200_*.tsv $R/jx/xexpert_*.tsv 2>&1 | tee -a $OUT
  echo "== odds value scale" | tee -a $OUT
  python3 scripts/switch_vscale.py results/calib/model_$NAME.txt results/judge/late300_h1000.tsv $R/judge/late300_h1000.tsv \
    results/cal6/j1200 $R/judge results/cal6/jx $R/jx 2>&1 | tee -a $OUT
  sed -i 's/^warn .*/warn 0.15 0.05 0.05 0.05/' results/calib/model_$NAME.txt
  grep -q '^warn ' results/calib/model_$NAME.txt || echo "warn 0.15 0.05 0.05 0.05" >> results/calib/model_$NAME.txt
  echo "candidate model: results/calib/model_$NAME.txt (installs nothing; next: $0 install $NAME \"$E\")" | tee -a $OUT
elif [ "$CMD" = install ]; then
  [ -f results/calib/model_$NAME.txt ] || { echo "run prepare first"; exit 1; }
  cp weights/calib/model.txt results/calib/model_before_$NAME.txt
  [ -f weights/best.cfg ] && cp weights/best.cfg results/calib/best_cfg_before_$NAME.txt
  printf '# engine switch %s (%s): network flags applied on top of preset best / best-notables (engine.h)\n%s\n' \
    "$NAME" "$(date +%F)" "$E" > weights/best.cfg
  cp results/calib/model_$NAME.txt weights/calib/model.txt
  ./build/analyze --preset best-notables --selftest
  python3 scripts/human_tiers.py
  echo "installed $NAME (old model: results/calib/model_before_$NAME.txt; undo: rm weights/best.cfg and copy it back)"
else
  sed -n 2,30p "$0"; exit 1
fi
