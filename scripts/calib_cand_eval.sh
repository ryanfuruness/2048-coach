#!/bin/bash
# cal7: score a candidate model's maps on the scorecard's truth sets without re-running the engine: the analyses of the
# "now" configuration (results/scorecard/now: judge, disputes, odds with the full engine) are reused - the scorecard
# recomputes every real loss from the model's maps. -> results/scorecard/cand_NAME/eval.txt (+ played.txt)
# usage: calib_cand_eval.sh NAME MODEL.txt
set -e
cd "$(dirname "$0")/.."
N=cand_$1; D=results/scorecard/$N; mkdir -p $D
for f in judge.jsonl disputes.jsonl odds.jsonl; do ln -sf ../now/$f $D/$f; done
cp $2 $D/model.txt
python3 scripts/scorecard_eval.py $N > $D/eval.txt
python3 scripts/scorecard_played.py $N > $D/played.txt
grep -A3 "C\. " $D/eval.txt | head -12
