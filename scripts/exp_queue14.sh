#!/bin/bash
# After queue11: (1) Guei-style TD schedule for stage B (exp_otdB.sh; the second half it bootstraps from is read from
# results/sh_for_stageB.txt when it starts: s6 unless the OTD second half proves better), then (2) exp_queue13.sh (lt-boot,
# c12 + TD 0.01, table-free stage B combos).
cd "$(dirname "$0")/.."
while ps -eo args | grep -q "^/bin/bash scripts/exp_queue11.sh"; do sleep 60; done
scripts/exp_p32otd.sh t21   # does the OTD second half's better stand-alone play help the 32768 phase (view play)?
scripts/exp_otdB.sh "$(cat results/sh_for_stageB.txt)"
scripts/exp_queue13.sh
