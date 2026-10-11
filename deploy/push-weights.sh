#!/usr/bin/env bash
# Copy the serving weights (not in git, ~0.9 GB) from this machine to the server. Only changed files are sent.
#   deploy/push-weights.sh root@SERVER
set -euo pipefail
cd "$(dirname "$0")/.."
SERVER=${1:?usage: deploy/push-weights.sh root@SERVER}
# the files the engine opens (checked with strace: resident workers and reviews)
FILES=(weights/best.cfg weights/calib/model.txt weights/calib/personal.txt
       weights/serve/v6c_i16.wp weights/serve/v6c_s0only_i16.wp)
rsync -avR --progress "${FILES[@]}" "$SERVER:/opt/2048-coach/"
ssh "$SERVER" 'chown -R coach:coach /opt/2048-coach/weights'
