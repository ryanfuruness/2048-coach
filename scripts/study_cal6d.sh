#!/bin/bash
# cal6 queue C: once the judge1200 runner of the 16384+ positions is done, the late lapse study at a reduced size
# (G=400 games per lapse policy, then 500 clean checkpoint games; full games cost ~45 s each on the instance).
cd "$(dirname "$0")/.."
until [ -f results/cal6/j1200/judge1200_800_1200.done ]; do sleep 30; done
G=${G:-400} GC=${GC:-500} T=${T:-16} scripts/study_cal6.sh lapse
