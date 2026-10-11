# Workstream integ: analysis integration (REPORT)

Copied by the coordinator from results/integ/report.txt.

```
integ notes (2026-10-07), newest last
00:45 Coordinator note for task 4 (switch to best_v6): late measured on cal6's H=1000 expert judge (400 positions,
  outside block positions) that v6 claims are close to real (5-10% -> 5.5%, 10-15% -> 13.0%, 15-20% -> 14.6%, 20-30%
  -> 28.0%, 30-45% -> 28.3%, 45%+ -> 48.2%; v5 overstates: 10-15% -> 7%, 20-30% -> 16%, 30-45% -> 17.5%) -> at the
  switch: refit lossmap_played_expert from late's numbers (near identity >= 10%, block positions excluded), refit the
  top map (cal6 recipe), warn threshold for 16384+ snake positions down to the late level. Until then: v5 maps.
00:50 your_cost map: scripts/fit_owncost.py (coach "first" runs, soft + structured players, pooled; weighted PAV):
  share of the player's own chances of the next milestone lost, by value loss (phase 0 / 1 / 2): 0.12 -> 3.5 / 5.4 /
  7.8%, 0.24 -> 8.9 / 10.2 / 13.9%, 0.36 -> 16.5 / 21.0 / 28.8%, 0.53 -> 35 / 52 / 53%, 0.9 -> 91 / 95 / 85%.
00:55 pdf update: detector v2 (block.h, default core_gap = 3; recall 93 -> 97/105, no new false hits) is picked up
  through the defaults; pdf is building the block tables into the laptop's weights/pdf/ (no table-loading analyze on
  the laptop until it reports done; block-table tests on the instance).
01:20 Task 1+2 done in analyze (laptop selftest 12/12): block positions (blk::block_formation at real 16384+) without a
  deciding table -> "judged":false, real_loss/your_cost null, no warnings, only a "block" suggestion note, block plan
  text, summary caveat; reviews skip them ("not_judged"). With block tables (source "block"): table-graded real loss
  (cal6's table map), table-only reasons ("the exact table gives it a 96% chance to build the tile your block needs
  next (vs 100% after down)"); snake-table positions get the table reason first. Per move "warn" (thresholds per phase
  in the model's "warn" line: 0.15 / 0.05 / 0.05 / 0.30) and "your_cost" (lossmap_own; 16384+ and table positions:
  the real loss); "your_cost_abs" with personal odds; reviews: warnings, warnings_per_100, mistakes_at_your_level =
  your_cost >= 3% (replaces the experimental skill maps), key moments carry your_cost. Model installed:
  weights/calib/model.txt = results/calib/model_v6b_integ.txt (cal6's v6 + lossmap_own + warn).
  Tests: novice game (400 moves, S1-S2): 12 warnings (3.0/100; coach's real novice rate 2.7), 28 mistakes at your level
  vs 3 real-loss mistakes; block player's 32768 segment (201 moves): without tables all 201 not judged; with the
  instance's block tables 187 judged (98.9% best/good, 1 table-verified blunder: 33% vs 100%), 14 not judged.
  Task 3: preset best loads weights/pdf when complete (every table with its .done marker; laptop: still being built ->
  off), block_min 0.5, new EngineConfig::block_from = 14 (block tables only with a 16384+; default 0 keeps pdf's
  flags unchanged).
01:30 Task 5 done: rollout resets the search per playout and per start analysis; messy per game and per --values
  analysis (smoke-tested). jold (cal6's H=1000 re-judge of the old 150 expert disputes) finished: H=300 refuted 105 /
  unclear 33 / confirmed 12, real 2.5%; H=1000 112 / 17 / 21, real 4.7% (claimed 21.6%); by claim 10-20%: -0.2% ->
  3.0%, 20-40%: 4.3% -> 3.7%, 40%+: 15.4% -> 17.1%; per-decision correlation of the horizons 0.63
  (results/integ/jold_horizon.txt).
00:35 Docs: docs/guide.md (v0.2: odds v6 with held-out numbers, the 3-stage + table loss maps, block formation,
  your cost, warnings, personal odds v2 + skill map + its known pessimism, reviews, speed/limits), docs/api.md (new
  fields formation/judged/warn/your_cost/your_cost_abs, source "block", reason codes table/block/later, review fields,
  weights/best.cfg, block tables, model keys), README analysis section rewritten, serve.py docstring.
  Engine switch prepared: EngineConfig::preset_best applies weights/best.cfg (engine flags, e.g. "--weights
  weights/best_v6.w") when present; scripts/switch_engine.sh prepare|install NAME "FLAGS" (revalue on the instance,
  fit_lossmap2.py --no-block with held-out, table map, odds value-scale check scripts/switch_vscale.py, warn 16384+ ->
  0.05; install writes best.cfg + model + selftest + tiers). fit_lossmap2.py: --no-block (scripts/block_detect.py =
  src/block.h, 300/300 agreement with analyze) and deterministic folds (crc32; was Python's salted hash()).
  Finding (v5 values, block positions excluded): the played-expert data say claims 10% -> 6% real, 15% -> 10%; the
  installed lenient map (<= 15% -> 0) was shaped by the block player's refuted disputes -> too lenient for snake
  experts; refit at the switch (coordinator: keep v5 maps until then).
00:55 Switch prepared for best_v6 (results/integ/prepare_v6.log, refit_v6.log; candidate results/calib/model_v6.txt,
  NOT installed): 53 judge files (2,184 non-block positions, 80 players) re-valued with best_v6 on the instance in
  ~15 min; only lossmap_top / lossmap_played_expert / lossmap_table / vbar+ratio (knots >= 15.6, x1.03-1.04) / warn
  change (early and late values are identical with late-game networks). Held-out (5 folds by video, block excluded,
  v6 values): top RMSE installed map 21.2 -> new 17.6, played-expert 11.2 -> 10.4, all 11.4 -> 9.9; calibration of
  the installed top map with v6 values: predicted 3-10% -> measured 25.5%, 10-30% -> 45.7% (badly lenient); new map:
  4.7% / 18.5% (calibrated). New played-expert map: 10% -> 8.9%, 15% -> 14.6%, 20% -> 16.2%, 30% -> 19.3%, 45% ->
  24.1% (installed v5 map: <= 15% -> 0). Table map unchanged (table chances do not depend on the networks).
  Fuzz re-check with the new analyze (boards1 1782 + boards2 2771 with risk=1, best-notables): only the 2 known
  "not a board" (16 distinct tiles) and 1 known reason text with a 65536 rank collision (late's --map-safe issue);
  symmetry clean; the checker now skips "judged": false answers for the reason check (scripts/fuzz_check.py).
01:05 human_tiers.py now as analyze: block positions not judged (left out), own-level mistakes = your cost >= 3%
  (lossmap_own), warnings per 100 (warn line). Current model: novice best/good 98.1%, 0.63 / 0.29 / 0.54 per 100,
  own-level 3.4/100, warnings 1.9/100; intermediate 99.9%, 0.09 / 0 / 0, 0.77, 1.15; strong 99.6%, 0.36 / 0 / 0.05,
  1.01, 1.15; expert 99.4%, 0.27 / 0.14 / 0.14, 0.34, 0.27 (block share median 0.1%). serve.py smoke test ok (health,
  new fields, block position, bad board -> error).
01:25 Played-expert map for v6 (my refit, isotonic, block excluded, all played 16384+ data incl. xexpert/jold/random
  top positions): 10% -> 8.9%, 15% -> 14.6%, 20% -> 16.2% (80% band 13.3-18.3), 30% -> 19.3% (15.4-22.0), 45% -> 24.1%
  (20.2-28.0). Direct bins on cal6's xexpert alone (v6 claims, non-block): 10-15% -> 14%, 15-20% -> 13-18%, 20-30% ->
  19%, 30-45% -> 3-21% (n=17-19), 45%+ -> 39-43% (n=20-23). late's table (20-30% -> 28%, 45%+ -> 48%) is higher above
  20%: n ~ 20 per bin and a different reference (the candidate's move vs the best rollout value), within noise. Near
  identity for 10-20% as the coordinator asked; flatter above (data-driven). Kept as fitted.
  Task 5 (repeat of the coordinator's note): already done at 01:30 (see above).
```
