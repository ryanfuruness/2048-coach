#!/bin/bash
# Full-engine analysis (exact tables incl. the block tables) of every curated human position with a real 16384+ tile
# (results/scorecard/inputs/human16k_in.txt, keys in human16k_keys.tsv), for the scorecard's game-level check: the
# human dataset's analysis (scripts/human_review.py) runs without tables (best-notables). Instance, 12 shards.
# usage: scorecard_human16k.sh NAME "ENGINE FLAGS"  -> results/scorecard/NAME/human16k.jsonl (same order as the input)
set -e
cd "$(dirname "$0")/.."
NAME=$1; E=$2; D=results/scorecard/$NAME
scripts/aws/ws.sh put score results/scorecard/inputs results/scorecard/ > /dev/null
scripts/aws/ws.sh run score "cd ~/2048_score && mkdir -p $D && rm -f $D/h16k.done && ulimit -s unlimited &&
  split -n l/12 -d results/scorecard/inputs/human16k_in.txt $D/h16k_in. &&
  (for k in \$(ls $D/h16k_in.* | sed 's/.*\.//'); do (./build/analyze --preset best $E --calib $D/model.txt --stdin < $D/h16k_in.\$k > $D/h16k.\$k.jsonl 2>/dev/null) & done; wait;
   cat \$(ls $D/h16k.*.jsonl | sort) > $D/human16k.jsonl; rm -f $D/h16k_in.* $D/h16k.*.jsonl; echo done > $D/h16k.done) > /dev/null 2>&1 &"
until scripts/aws/ws.sh run score "test -f $D/h16k.done" 2> /dev/null; do sleep 20; done
scripts/aws/ws.sh pull score scorecard/$NAME > /dev/null
wc -l $D/human16k.jsonl
