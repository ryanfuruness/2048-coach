#!/bin/bash
# The analysis scorecard (workstream scorecard, 2026-10-07): how trustworthy is the analysis engine? One repeatable run
# per configuration on fixed truth sets (scripts/scorecard_prep.py -> results/scorecard/inputs: 2,410 rollout-judged real
# positions, 632 positions with odds truth, the 210 expert decisions, fuzz boards), compared side by side with
# scripts/scorecard_compare.py.
#
# usage: scripts/scorecard.sh NAME "ENGINE FLAGS" MODEL PERSONAL [HUMAN_ANALYSIS.jsonl]
#   ENGINE FLAGS   network/table flags on top of --preset best / best-notables (always give --weights explicitly:
#                  the preset applies weights/best.cfg); e.g. "--weights weights/best_v6b.w"
#   MODEL          odds + loss-map model (weights/calib/model.txt or a versioned copy in results/calib/)
#   PERSONAL       personal-odds model
#   HUMAN_ANALYSIS the human dataset analysed with this engine (scripts/human_review.py; default
#                  results/human_ds/analysis.jsonl) for the tier benchmarks and the game-level check
#   PLAIN=1        score the configuration as the analysis worked before 2026-10-07 (no block-formation abstention or
#                  table-aware claims): for configurations that predate those features
#   FORCE=1        redo the instance and fuzz parts (otherwise reused when present)
# The model files are copied into results/scorecard/NAME/ first and only the copies are used (installed files may
# change while it runs). -> results/scorecard/NAME.txt (+ NAME/: raw outputs, metrics.json, invariants.json,
# personal.json, games.json, tiers.json). Instance part: ~/2048_score (~7 processes, ~1 min).
set -e
cd "$(dirname "$0")/.."
NAME=$1; E=$2; M0=$3; P0=$4; H=${5:-results/human_ds/analysis.jsonl}
[ -z "$P0" ] && { sed -n 2,21p "$0"; exit 1; }
D=results/scorecard/$NAME; mkdir -p $D
[ "$FORCE" = 1 ] && rm -f $D/remote.done $D/notables_fuzz.summary.txt
cp $M0 $D/model.txt; cp $P0 $D/personal.txt
M=$D/model.txt; P=$D/personal.txt
{ echo "$NAME | engine: $E | model: $M0 | personal: $P0 | human analysis: $H | plain: ${PLAIN:-0} | $(date)";
  md5sum $M0 $P0 | sed 's/^/  md5 /'; } > $D/config.txt
# 1. instance: analyses with the exact tables (judge positions, odds truth, disputes, latency + invariants with tables)
if [ ! -f $D/remote.done ]; then
  scripts/aws/ws.sh build score build/analyze > /dev/null
  scripts/aws/ws.sh put score results/scorecard/inputs results/scorecard/ > /dev/null
  scripts/aws/ws.sh put score $M $D/ > /dev/null
  scripts/aws/ws.sh put score $P $D/ > /dev/null
  scripts/aws/ws.sh run score "rm -f $D/remote.done; nohup bash scripts/scorecard_remote.sh $NAME '$E' $M $P > /dev/null 2>&1 &"
  sleep 5
  until scripts/aws/ws.sh run score "test -f $D/remote.done" 2> /dev/null; do sleep 20; done
  scripts/aws/ws.sh pull score scorecard/$NAME > /dev/null
fi
# 2. laptop: invariants + latency without tables (best-notables; one engine process at a time on the laptop)
if [ ! -f $D/notables_fuzz.summary.txt ]; then
  flock results/scorecard/laptop.lock python3 scripts/fuzz_check.py results/scorecard/inputs/latency_real.jsonl \
    $D/notables_real --analyze ./build/analyze --extra "$E --calib $M --personal-model $P" > /dev/null 2> $D/notables_real.err
  flock results/scorecard/laptop.lock python3 scripts/fuzz_check.py results/scorecard/inputs/fuzz_boards.jsonl \
    $D/notables_fuzz --analyze ./build/analyze --extra "$E --calib $M --personal-model $P" > /dev/null 2> $D/notables_fuzz.err
fi
python3 scripts/scorecard_invariants.py $D/notables_real $D/notables_fuzz $D/tables_real $D/tables_fuzz \
  --json $D/invariants.json > $D/invariants.txt
# 3. personal odds (real players' outcomes; soft-player playouts only meaningful for softmax-based models), tiers,
#    the game-level check, the truth-set evaluation
python3 scripts/calib_personal_real.py --model $P --engine-model $M --out $D/personal_real.tsv > $D/personal_real.txt 2>&1 || true
python3 scripts/calib_pers_report.py --model $P > $D/personal_soft.txt 2>&1 || true
python3 scripts/scorecard_personal.py $NAME > $D/personal.txt.out 2>&1 || true
python3 scripts/human_tiers.py --model $M --personal $P --out $D/tiers.json $H > $D/tiers.txt 2>&1 || true
python3 scripts/scorecard_games.py --analysis $H --model $M ${PLAIN:+--plain} --out $D/games.json > $D/games.txt 2>&1 || true
python3 scripts/scorecard_eval.py $NAME ${PLAIN:+--plain} > $D/eval.txt
python3 scripts/scorecard_played.py $NAME ${PLAIN:+--plain} > $D/played.txt
{ cat $D/config.txt; echo; cat $D/eval.txt; echo;
  echo "== the player's own move vs the alternatives (scorecard_played.py)"; cat $D/played.txt; echo;
  echo "== game-level consistency (scorecard_games.py): do the per-move real losses compound into what players achieved?";
  cat $D/games.txt; echo;
  echo "== personal odds vs real players' outcomes (calib_personal_real.py rows; scorecard_personal.py)"; cat $D/personal.txt.out; echo;
  echo "== tier benchmarks (human_tiers.py, medians over players)"; cat $D/tiers.txt; echo;
  echo "== invariants and latency (fuzz_check.py answers; scorecard_invariants.py)"; cat $D/invariants.txt
} > results/scorecard/$NAME.txt
echo "-> results/scorecard/$NAME.txt"
