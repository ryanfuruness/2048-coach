# Lab notebook — read this first after a context reset

**GOAL CHANGED 2026-10-06 (user): be the "Stockfish of 2048"** — an analysis engine for human players: evaluate ANY
position (messy human ones first) with calibrated odds (next big tile / 32768 / 65536), rank all moves with the loss vs the
best, show the plan, review whole games (mistakes, accuracy), explain moves in plain words, cheap to serve (small server
or browser). Excellence on messy human positions beats SOTA score: sacrifice score for robustness if needed. Quick SOTA
wins are a bonus, no grinding. Build on OUR engine (macroxue's GPL engine only as a reference to check moves against).
Don't commit to timelines (the user wants fast autonomous progress, day and night).

## START HERE (state 2026-10-06)

* **APP PHASE (since 2026-10-07; read app/README.md, app/DECISIONS.md (v2 section first), app/qa/REPORT.md,
  app/engine-patch/README.md).** "2048 Coach" v2, the WORKBENCH (2026-10-10, after the user's first test feedback),
  runs locally: `cd app && npm start` -> http://localhost:8048 (stop: `npm run stop`). One screen: board + eval bar +
  verdict line + transport (undo Z / redo X / start / end, "play the coach's move" Space) + timeline scrubber (chance
  curve, cost ticks, coach stretches) + autoplay (P; 1/s, 3/s, 10/s, full speed; until stopped / next tile / 100
  moves) on the left; panel with modes Analyze (default) / Coach (v1 warnings + hints) / Play and tabs Analysis / Review
  (of the whole line; the coach's moves are left out). Editor on the board (E). History, separate Review/Analyze
  screens removed (v1 archived in app/archive/v1/). Line model app/web/src/lib/line.ts, controller workbench.ts.
  Server: new `POST /api/autoplay` (batches of the analysis' best moves; ~150 moves/s here, WSL pipe-bound), analysis
  rate limit 200/s. Checks: `npm test`, `npm run test:engine` (server stopped), `npm run qa` (15 Playwright journeys,
  screenshots in app/qa/screens/ - look at them with the Read tool), `npm run lighthouse` (cleans its own stray
  profile folder now). PLAYTESTING started 2026-10-10 (log: app/qa/PLAYTEST.md); the big hill climb: "how do we make
  this useful to humans". v3 (2026-10-10, second playtest round): the app is built around the coach's GRADES (best /
  good / questionable / blunder from src/analyze.cpp grade_moves: engine value-loss lines 0.5% / 5% from a depth-5
  agreement study + structural blunders: corner, edge, danger, big loss; free stretch up to 256; results/grades/), a
  much simpler screen (four toggles, one grade line, move list with the coach's %, engine odds hidden), no levels, no
  "your chance" in the app (chance.hv off by default), Deeper/timeline/review tab/eval bar cut (app/DECISIONS.md v3,
  v2 archived in app/archive/v2/). Earlier, v2.1 (2026-10-10, after the first findings: odds/warnings did not react to human mistakes,
  early coach moves made no sense): YOUR CHANCE = a human-like player's own chance of the next milestone (TD-trained
  n-tuple networks over the personal-odds simulated players, weights/calib/chance.hv, src/hvalue.h, src/hplayer.h,
  build/hv_tool; results/yc/REPORT.md) drives the bar, grades, warnings, timeline, review; the coach's move
  (`coach_move`) is the corner strategy up to 512, the engine's from 1024. Open: next-doubling target for weak players +
  live in-game skill. The user also still has their own improvement ideas to share. Ideas offered
  to them: variation tree, "your chance" as the main bar, guess-the-move drills from their own key moments, spawn
  control in the editor, in-browser autoplay (WASM) for a public server. Deferred until the user decides: server /
  private preview on AWS (~$40-90/month), domain, final name; the LLM explanation layer. AWS: nothing running.
* **STATE AFTER THE 24-HOUR RUN (2026-10-07 ~07:05; details in the log entries of 2026-10-06 21:50 - 2026-10-07,
  results/<workstream>/REPORT.md, the workstream table in results/WORKSTREAMS.md).**
  - **Engine: best_v6c** (weights/best.cfg = `--weights weights/late2/best_v6c.w --leaf-view-max-sum 20480`, applied by
    every tool's `--preset best` / `best-notables` ON THE LAPTOP; the instance's shared weights dir has no best.cfg):
    best_v5 + OTD stage 3 (t21) + OTD stage B (bo_2) + OTD stage 1 (s1o_3) with the leaf view below 20480. 1000-game
    benchmark 586,082 +- 6,569, 16384 95.4%, 32768 64.0%, 65536 0.1% (best_v5bb: 559,754 / 95.4 / 59.8). Stage 4 is
    never used (root downgrade). Exact tables: k6 (RAM), k5 layered (88 GB), NEW block tables (weights/pdf, 53 GB,
    own code; 3x2 corner block formation of strong players).
  - **Analysis engine v0.2** (docs/guide.md, docs/api.md; build/analyze, scripts/serve.py): odds v7 + formation
    correction + `odds_caveat`; loss maps early / late / top + table maps + review maps for players' OWN moves
    (game-consistent at 16384+); block formation: table-judged or abstained; per move `warn`, `your_cost` (by skill band
    when the skill is known), `find_prob`, `real_loss_engine` (reviews); per position `error_risk` / `hint` (up to
    512); reasons checked counterfactually in the position (`share`, sorted, unfaithful ones dropped); `plan` +
    `plan_info` (validated: the predicted event happens in 73% of engine / 86% of player continuations); reviews with
    the human-model skill (below 16384), key moments >= 3%, decisive moment, warnings, hints, hard moments; personal
    odds v5 (human move model + care in danger). Installed: weights/calib/model.txt (md5 6a2ba392, cal9) and personal.txt
    (v5b; hints only up to 512). Selftest 16+ checks pass; fuzz invariants clean (2 known 16-distinct-tile boards,
    the 65536 rank collision); latency p50 / p99 ~1.5 / 13 ms with tables.
  - **Scorecard** (scripts/scorecard.sh NAME "FLAGS" MODEL PERSONAL ANALYSIS; results/scorecard/compare_final_v6c.txt):
    start of the run -> now: odds MAE on 200 fresh real positions 0.100 -> 0.066 (P(16384); P(32768) on 160 held-out
    16384-phase positions unchanged, 0.136 -> 0.137); loss-map RMSE 13.0 -> 11.7; block
    player's false > 10% claims 67/85 -> 5/85 (+32 abstained); snake experts 22/27 -> 12/27 (10/12 real kept);
    personal odds vs real outcomes AUC 0.77 -> 0.88, log-loss 0.65 -> 0.32; game-level check R 3.5 -> 2.4;
    robustness unchanged (engine move clearly worse in ~0.9% of real positions = noise level).
  - **Validated findings:** advice helps (coach: a warning just before a bad move is the most efficient; 1-2 per 100
    moves close 42-90% of the gap to the engine); reviews: for novices what is flagged is real (30-43% big losses vs
    2.4% random), recall ~1/3; the decisive moment holds; experts' small engine-claimed losses are not real for them
    (the engine undervalues their positions and plays them worse), big ones partly; personal odds still pessimistic
    for strong players (0.66 vs 0.83); odds on odd formations from 4096 are over-confident (caveat flag).
  - **Serving** (workstream serve): `--packed` networks - packed int16 = byte-identical answers at 775 MB RAM; a
    stage-0-only file (55 MB download, 157 MB RAM) answers every non-expert position identically -> browser/phone
    build + a server for 16384+ positions (weights/serve/, build/wpack_tool; repack after each engine switch).
  - **Open / next:** the app phase (LLM explanation layer on the checked reasons: say "mainly because" for share >=
    0.5); a block-formation PLAYER (multi-day; macroxue's edge); 65536 odds (the engine never builds it);
    your_cost for intermediate vs strong (skill does not separate them); the "get your biggest tile into a corner"
    plan below 8192; GPL: macroxue's sources/extracts live OUTSIDE the tree (/home/ryanf/projects/2048-macroxue-judge).
* **[DONE 2026-10-07 08:16, see STATE AFTER THE 24-HOUR RUN] 24-HOUR PLAN (user, 2026-10-06 21:15): the user upgraded AWS to Paid; instance launched with a 24 h cap; the user
  delegated three decisions to me and wants an ambitious 24 h push on the CORE ENGINE (the app comes later).**
  - AWS: **i-063910223f0247831, hpc7a.96xlarge** (hpc8a had no capacity), 192 physical AMD EPYC 9R14 cores, 740 GB RAM,
    ~$7.20/h, us-east-2b, IP <ip> (changes on stop/start). **CAP: user-data scheduled `shutdown -h +1440` at
    first boot + instance-initiated-shutdown-behavior=stop -> the instance STOPS at ~21:15 +04 on 2026-10-07** (disk
    kept; never reboot it - that would cancel the scheduled shutdown; check with `cat /run/systemd/shutdown/scheduled`).
    Setup done 21:16: setup_remote, code pushed (~/2048), `scripts/aws/remote_init.sh` building + recomputing the k5
    tables (k5r10 at 66% after 53 s; log ~/2048/init.log, fingerprint check at the end), weights uploading from the
    laptop (`push.sh core` then `push.sh all`, logs results/aws_push_core.log / aws_push_all.log, ~25 MB/s).
    Use `scripts/aws/ssh.sh 'cmd'`; `push.sh code` after source changes; `start_stop.sh status`. Results produced on
    the instance must be copied back (rsync from ubuntu@IP:2048/results/...) before the cap.
  - **Decisions (mine, delegated by the user):** (1) LLM explanation layer: DEFER to the app phase (presentation layer
    over still-moving structured outputs; needs its own faithfulness evaluation; the API key stays unused). (2) Do NOT
    build on macroxue's code (GPL-3.0 would bind any distributed build, e.g. browser/WASM; our calibration, robustness
    evidence and explanations are tied to our engine) but DO use it as an independent judge: build it on the instance
    and evaluate the expert disputes / expert positions (does it side with the experts where ours does not?). If it
    clearly does, reimplementing its ideas (PDF formation + plan tables) in our engine is the follow-up project.
    (3) YES to the "bad position -> do recommendations help a player recover?" (coach) test: the direct test of the
    product's value, cheap with softmax players, and it informs the app (how much advice, which moments).
  - **24 h ambition: make the analysis engine trustworthy at EVERY level including experts, and prove its advice helps
    players.** Workstreams:
    A. Expert-level late game (headline research bet, instance-heavy): independent judge (macroxue) on the 150 expert
       disputes + random expert positions; quick fixes tested on the instance (16384-phase whole-phase test = 700 real
       starts ~minutes on 192 cores; 32768-phase test; full 1000-game benchmark ~30 min): exposed-cells leaf penalty
       (laptop test running: results/expexposed/eval.log, baseline 64.14%), deeper late search (budget/depth), late
       networks retrained with expert positions as start pools (CPU trainer --pool, TD 0.1 -> 0.01 -> 0.001, never a
       fresh TC tail), combinations. Metrics: 16384-phase conversion > 64.1%, 32768-phase conversion up, dispute
       refutation rate down; stretch: a new best player (1000-game benchmark).
    B. Coach test: from real bad human positions (curated set; low value or right after a mistake), softmax player
       alone vs + engine advice (every move / only when its move would lose >= X% / top-k moments) vs the engine alone;
       outcome P(next milestone); also defines "at your level" properly (drop in the player's own milestone odds).
    C. Calibration at scale: bigger calibration study (handovers incl. late game) -> odds v6 with reliability checks;
       bigger real-human judge (1000+ positions, all moves, H=1000) -> final staged loss maps with confidence;
       recompute benchmarks; personal odds v2.
    Organisation: main thread = coordinator (owns NOTES.md, merges subagent reports, watches the cap, copies results
    back); subagents per workstream with file ownership (A: search.h/play.cpp/train.cpp + scripts/exp_late_*; B: new
    src/coach.cpp + scripts/coach_*; C: scripts/fit_*/calib.h/study_*), separate build dirs (`make BUILD=build_X`) and
    separate instance work dirs (~/2048_X with weights symlinked); instance cores split ~A 128 / C 48 / B 16; on the
    laptop only ONE table-loading engine process at a time (7.7 GB RAM). Each subagent writes results/<stream>/REPORT.md.
* **State 2026-10-06 ~15:00 (week 1, day 1):** analysis engine v0 works end to end; details in the 2026-10-06 log
  entries at the end. Built: `src/engine.h` (shared engine; `--preset best|best-notables`), `build/analyze` (summary
  verdict, moves ranked with values / losses / estimated real loss, calibrated odds (weights/calib/model.txt, loaded by
  default) x next-tile survival, table p, plan, validated reasons incl. risk and value attribution, `--risk`, `--line`,
  `--heat`, `--personal T` (fast model weights/calib/personal.txt when present, else playouts), `--review` with gap
  bridging + skill + key moments, `--stdin` with per-request options incl. `played=`), `scripts/serve.py` (HTTP API),
  `build/messy` (human-like positions; softmax players `soft:t=`; handovers; lapses "@+N"; `--checkpoints`;
  `--trace`), `build/rollout` (judge; `--stop-rank`), explain.h, calib.h (odds, loss map, personal model), fit scripts
  (fit_calib, fit_lossmap, fit_personal), human tools (human_review, human_think, human_skill_stages,
  human_disputes, dispute_report).
  Findings: (1) robustness: engine move = rollout-best within noise on 214 human-like positions; (2) engine odds for
  human-like positions = stage base rates (nothing else predicts the engine's outcome; it repairs damage) x survival
  of the next tile (validated on a near-dead board: 0.842 vs 0.850 measured); (3) value losses of 1-10% are only
  0.2-0.8% real -> review classes use a fitted loss map; (4) personal odds (skill t) DO vary by position (IQR 0.44-0.78
  vs engine 0.997) -> the useful evaluation bar for typical players; (5) explanations: concepts validated on 14k
  human position-moves (chain, exposed cells, center, corner, trapped; merges/free cells NOT predictive); 75% of real
  human mistakes get a specific reason; (6) human data (176k decisions, 113 videos): skill measure works within a
  stage; (7) serving: 1.5 ms per analysis at engine depth, 35 ms at depth 5, 1.3 GB RAM without tables.
  AWS: HPC quota 192 GRANTED, but launch blocked: account on the Free plan -> the USER must upgrade to the Paid plan
  (notified 14:35). Then `scripts/aws/launch.sh hpc8a.96xlarge`.
  Laptop queue tonight (each waits for the previous; one table-loading process at a time): study_calib2.sh (lapse8,
  lapse16, lapse16b) -> judge_horizon.sh (H=1000 loss map) -> study_calib3.sh (500 clean games at checkpoints) ->
  study_disputes.sh (expert disputes judged by rollouts). In parallel when RAM allows: human recompute (fixed engine)
  -> study_personal.sh (soft:t games for the personal-odds model).
  UPDATE ~19:15: odds model v5 + loss maps fitted on 300 RANDOM REAL human positions (results/judge/human300_*,
  robustness 1/300) INSTALLED in weights/calib/model.txt (lossmap early <= 1024, lossmap_late >= 2048,
  lossmap_played_expert from the expert disputes); tier benchmarks recomputed (results/human_ds/tiers.json).
  Expert disputes: the engine undervalues experts' late-game choices (150 claims > 10% -> 12 confirmed); all-player
  disputes: for non-experts the claims are largely real. "At your level" losses are EXPERIMENTAL (skill-level maps on
  real positions are noisy; a weak player's later play dominates any single move).
  Running overnight: scripts/judge_night2.sh -> late300 judge (300 more late real positions, strong/expert tiers,
  H=1000): then refit lossmap_late on human300 + late300 (command at the end of results/judge/night2.out) and rerun
  scripts/human_tiers.py.
  Still blocked: AWS Paid plan (user). Ask the user: LLM explanation layer (API key), app/hosting timing.
  Next research candidate: learn the late game from experts (IDEA entry in the log).
* **Secrets:** `.env` in the project dir holds the user's Anthropic API key (for the later explanation/chat feature).
  Never print it, never copy it into logs, scripts' output or other files, never commit it. Don't use it until the
  explanation work starts.
* **AWS (set up 2026-10-06):** IAM user `claude-2048`, account <account-id>, region us-east-2; policies AmazonEC2FullAccess
  + ServiceQuotasFullAccess only (no IAM/Budgets: the user created the monthly budget with email alerts in the console).
  CLI v2 at `~/.local/bin/aws`, credentials in ~/.aws (never print them). Created: key pair `claude-2048` (ed25519,
  `~/.ssh/claude-2048.pem`), security group `<security-group>` (SSH from the user's IP only - if SSH times out, the
  home IP changed: re-authorize port 22 for the new IP), subnet us-east-2b `<subnet>` (the only AZ with
  hpc8a), AMI Ubuntu 24.04 `ami-0fa99aa8f97f9e30b`. vCPU quotas: Standard (L-1216C47A) 16 -> 192 requested by the user
  (CASE_OPENED); HPC (L-F7808C92) 0 -> 192 requested by me (PENDING). Check: `aws service-quotas
  list-requested-service-quota-change-history-by-quota --service-code ec2 --quota-code L-F7808C92` (or L-1216C47A).
  Scripts in `scripts/aws/`: `launch.sh [hpc8a.96xlarge|m8a.48xlarge]` (1 TB gp3 root, kept on stop), `ssh.sh [cmd]`,
  `start_stop.sh start|stop|status`, `setup_remote.sh` (run on the instance: build tools), `push.sh` (code + ~15 GB of
  weights/pools/k6 tables; the 88 GB k5 tables are recomputed there with build/layered). Launch with hpc8a (~$7.92/h) if
  the HPC quota is approved, else m8a.48xlarge (~$11.69/h). Stop the instance whenever nothing is queued. Option to
  raise with the user: run Claude Code on the instance for 24/7 autonomy (one-time login by the user there).
* **Why the big machine:** calibration/robustness studies need many playouts (~6 h per study here vs ~30 min on 192
  cores), training on broader position distributions is ~10x faster, and 7.7 GB RAM here allows only one job at a time.
* **Week-1 work plan (no fixed timeline; in this order):**
  1. Human data from the other chat: parse into (board, move) sequences; it is the test set for "works on human positions".
  2. Messy-position generator: imperfect policies (epsilon-random moves, greedy 1-ply, shallow noisy search, other corners
     and formations, broken chains, mid-game junk) + positions from the human data.
  3. Calibration study: from N positions per category, playouts with the engine's own fast policy -> true P(next big tile),
     P(32768), P(reach sum X); compare with network values (fit value -> probability maps per stage/phase) and with exact
     table P where tables apply.
  4. Robustness: move quality of the current networks (best_v5: table players, no-table d2 11.0%) vs the stand-alone
     stronger OTD networks (expotd/t18, t21: 17.7%) on messy positions (loss in playout success vs a deep reference).
     If needed, retrain on messy-position distributions (CPU trainer, `--pool` of messy positions; TD 0.1 -> 0.01 schedule;
     never a fresh-TC tail) — prime big-machine job.
  5. Analysis library v0 (C++ core + JSON CLI/API): per move value, calibrated odds, loss vs best; plan (principal line);
     game review (accuracy, mistakes/blunders); simple reasons from n-tuple attribution (networks are linear in their
     weights: a value difference splits exactly into pattern contributions -> concepts such as "chain intact", "tile
     trapped under the chain", "no space next to the merge target") plus counterfactual spawns.
  6. Serving check: portable build without PEXT (ARM/WASM), compressed weights (half the weights are never trained; int8),
     tables from SSD at the root only, latency per analysis; report strength in this "serving config" (4 cores, 16 GB).
* **Old SOTA queues** (scripts/exp_queue14.sh, exp_queue15.sh, exp_queue13.sh): optional now. Worth keeping because they
  improve stand-alone network quality: exp_otdB.sh (TD schedule for stage B) and exp_queue15.sh (TD annealing of the
  early-game network). Low priority: lt-boot, table-free combos, c12 + TD 0.01.
* **What we know that matters for the new goal** (details in the log): our late networks are table players (no tables:
  3.4/11.0/19.4/23.9% conversion at d1-d4 vs Guei's 35/60/69/73%); the decaying TD schedule (OTD) gives far better
  stand-alone networks at equal full-player strength; build-up deaths are formation breaks the network misjudges (depth
  does not fix them); exact tables give calibrated probabilities in endgames (k5r10 P ~ realized success); the snake
  formation limits the final phase (~70% vs macroxue's ~84%).

### Previous goal (until 2026-10-05): beat every published result

Goal: a 2048 player that beats every published result. Targets (1000 games unless noted):

| Player | Avg score | 16384 | 32768 | 65536 |
|---|---|---|---|---|
| macroxue/2048-ai depth 8 (heuristic expectimax + DP lookup tables) | 711,769 | 98.7% | 80.5% | 3.5% |
| macroxue depth 5 / depth 3 | 660,650 / 493,058 | 95.6 / 81.4% | 74.8 / 52.5% | 2.7 / 1.3% |
| Guei et al. 2022 (OTD+TC n-tuple, 6-ply, 100 games) | 625,377 | 98.8% | 72.0% | — |
| **ours, best so far: best_v6c** (`results/bench/late2_v6c`, 2026-10-07: best_v6b + OTD stage 1 s1o_3, leaf view < 20480) | **586,082 ± 6,569** | 95.4% | 64.0% | 0.1% |
| ours, best_v6b (`results/bench/late_v6bo2`, 2026-10-07: best_v5 with OTD stage 3 t21 + OTD stage B bo_2) | 572,948 ± 6,552 | 95.4% | 62.9% | 0% |
| ours, best_v5bb (`results/bench/best_v5bb_1000`, best_v5 + budgeted stage B and second half) | 559,754 ± 6,552 | 95.4% | 59.8% | 0% |
| ours, best_v5b (`results/bench/best_v5b_1000`, best_v5 + budgeted second half) | 558,272 ± 6,546 | 95.4% | 60.2% | 0% |
| ours, best_v5 (`results/bench/best_v5_1000`) | 552,742 ± 6,481 | 95.4% | 59.8% | 0.1% |
| ours, best_v4 (`results/bench/best_v4_1000`) | 549,281 ± 6,532 | 95.4% | 57.6% | 0.1% |
| ours, best_v3 (`results/bench/best_v3_1000`) | 547,525 ± 6,475 | 95.4% | 57.4% | 0% |
| ours, best_v2 (`results/bench/best_v2_1000`) | 524,809 ± 6,477 | 94.9% | 52.7% | 0% |
| ours, v11c + 4M second half (`results/bench/v11c_e4_1000`) | 506,542 ± 6,610 | 94.9% | 48.8% | 0.1% |
| ours, v11c (`results/bench/v11c1000`) | 488,691 ± 6,260 | 94.9% | 45.5% | 0% |
| ours, m1q + tables (`results/bench/m1q_eg1000`) | 466,748 ± 6,051 | 95.0% | 40.8% | 0% |
| ours before (`results/bench/hybrid_rd1000`) | 460,857 ± 5,458 | 96.5% | 37.0% | 0% |

## How the best player is run

```
# current best (best_v5, 2026-10-04): weights/best_v5.w = 5 stages [s0cpu, exph1 e4 (unused: leaves < 24576 go to
# s0cpu via the leaf view), stage-B seed 2 4M (weights/expsplit/b4s2.w), second half seed 6 (weights/expseed/s6.w), OI]
./build/play --weights weights/best_v5.w --stages "sum:20480/14,24576,28672,36864" --quantize --depth 4 \
  --stage-depth 3,4,4,4,4 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 \
  --endgame-dir weights/endgame_big --endgame-nosave \
  --endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 \
  --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 --lt-view \
  --leaf-view 14 6 --leaf-view-max-sum 24576
# (ulimit -s unlimited; MALLOC_ARENA_MAX=2; ~4.5 GB RAM)
```
Older (best_v3):
```
# current best (best_v3, 2026-10-03): 5 stages = s0cpu early game, exph1 e4 first half below 24576 (but leaves there
# are valued by s0cpu through the leaf view), stage B b3 for [24576, 28672), exps e4 second half, rest; k=5 table
# (the benchmark ran before the move-mapping fix, i.e. k5r10 only in the 16384 phase; add the k5r9 group too)
./build/play --weights weights/expsplit/b3_play.w --stages "sum:20480/14,24576,28672,36864" --quantize --depth 4 \
  --stage-depth 3,4,4,4,4 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 \
  --endgame-dir weights/endgame_big --endgame-nosave \
  --endgame-lt weights/endgame_lt/k5r10.lt --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 \
  --endgame-lt weights/endgame_lt/k5r9.lt --lt-k 5 --lt-rank 9 --lt-caps 8,8,7,7,7,8,8,7,7,7,7 --lt-min 0.5 \
  --leaf-view 14 6 --leaf-view-max-sum 24576
# (ulimit -s unlimited; benchmark: scripts/bench.sh NAME WEIGHTS STAGES 1000 100 14 [options], ~25 min)
```
Previous best (best_v2):
```
# current best (best_v2): early game s0cpu (d3), dedicated first half exph1 e4 (4M episodes, d4), second half
# exps e4 (4M episodes, d4); the 16384 phase starts when the 16384 forms
./build/play --weights weights/exps/best_v2.w --stages "sum:20480/14,28672,36864" --quantize --depth 4 \
  --stage-depth 3,4,4,4 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2 --endgame-min 0.5 \
  --endgame-dir weights/endgame
# (ulimit -s unlimited first: the table DP recurses deeply)
```
Older best (before the corner lock):
```
./build/play --weights weights/v6/vB.w --stages sum:20480,36864 --quantize \
  --ens-weights weights/v5/b6.w --ens-stages sum:20480,28672,36864,45056,53248,61440 \
  --ens-mode replace --ens-from-stage 1 --depth 3 --stage-depth 3,2,2 \
  --ens-stage-depth 3,3,2,2,2,2,2 --root-downgrade 15
# 1000-game benchmark in resumable chunks: scripts/bench.sh NAME WEIGHTS STAGES 1000 100 16 [play opts]
```
(vB stage 0 = CPU-trained early game `weights/tup/s0cpu.w`; from tile sum 20480 on, the v5 network b6
replaces it; boards with a 32768 are searched in a downgraded view so the 16384-phase networks apply.)

## Where the games are lost (the whole gap to SOTA) — UPDATED 2026-10-05

* Current best converts the 16384 phase at ~63-64% (whole-phase test from 700 real 16384 formations: 64.1%), macroxue d8 ~82%.
* **Build-up (sum < 31744): we lose 15.7% of games, macroxue 2.8% (d8) / 5.8% (d5)** (their outputs/2048b.d*, binned by
  death sum; `scripts/death_bins.sh LOG` for ours). Stage B (24576-28672) alone: 6.6% vs 1.0%/0.6%. These deaths are
  formation breaks in network-played positions (snake broken at its turn into row 2, junk tiles; tables rarely apply:
  `scripts/death_structure.py`). Deeper search does NOT reduce them for our networks (deep stage B, d3->d4 without
  tables), a snake-order penalty does not either -> the networks' evaluation is systematically wrong there.
* **Final phase (k5r10 territory, sum >= 31744): ~25% of arrivals die vs ~16% for macroxue at every depth.** The k5r10
  table plays it near-optimally (caps never bind; handover P is 0.6-0.8 for 94% of games) -> formation-limited (their top
  rows are column pairs, ours a snake).
* **Our late networks are table players**: without tables the best networks convert 3.4/11.0/19.4/23.9% at d1-d4 (Guei
  et al.'s table-free nets 35.4/59.8/68.9/72.9%). The GPU trainer's over-training damage is a trainer artifact (CPU
  training does not degrade), but CPU TC training plateaus at ~4M episodes too; seeds share their errors (ensembles do
  nothing); annealing, lambda > 0.5, tight 2-ply, forward pruning all fail. Open: table-free training, side branches,
  exact-table bootstrapping, Guei-style OTD (queues expq12, exp_otd).

### Older notes (2026-10-01)
* 96.5% reach 16384, only 37% reach 32768: the **16384 phase converts at ~38%** vs ~82% for macroxue.
* Of 595 benchmark games that died with max 16384: 81 died in the first half (sum 20480-28672),
  **469 in the second half (28672-36864), 320 of them at sum 30720-32768** (building the last
  pieces before the 32768 merge). Death boards show big tiles on both sides of the 16384, e.g.
  edge line `[8192 2048 4096 16384]` or `[8192 16384 4096 2048]`.
* **Root cause found (2026-10-01): every network moves the 16384 out of its corner.** In the first
  half it merges along the edge *away* from the corner (`[16384 4096 2048 2048] -> [_ 16384 4096 4096]`),
  129 of 139 games; the 8192 ends up in the corner, the 16384 beside it, and later big tiles grow on
  the far side of the 16384. (The init-0 lineage instead builds the 8192 in the far corner.)
* macroxue keeps the big tiles locked in the corner block and solves "build the next tile in the
  remaining cells" exactly with dynamic programming (studied their GPL source in
  `$CLAUDE_JOB_DIR/tmp/mx`; do not copy code — reimplement the idea). Their small tables at depth 3:
  37.8% 32768; big tables at depth 3: 52.5%; so the tables are worth a lot.

## Current line of work

1. **v11 = corner lock** (`scripts/pipeline_v11.sh`, running since 2026-10-01 22:21, logs `results/v11/`):
   `--corner-lock 14` in gpu_train and play: moves that take the max tile (>= 16384) out of its corner
   are skipped unless every move does. Forcing the old (unlocked) network to obey the lock at play
   time breaks it (first half 79% -> 0.7%), so the 16384 phase is retrained under the lock:
   m1 (whole phase [20480,36864), fresh optimistic, 14M episodes) -> m1q (2-ply 25%) -> pool2q at sum
   28672 -> s2 (second half, fresh optimistic, 12M) -> s2q -> `weights/v11/final.w` (stages
   `sum:20480,28672,36864`). Compare against the unlocked baselines below; then full games with
   `--corner-lock 14 --root-downgrade 15`.
2. **DP endgame tables** (`src/endgame.h`, tool `build/endgame`, play `--endgame 6 [--endgame-min 0.1]`):
   snake path (row 0 L->R, row 1 R->L, ...) from the max-tile corner in any of the 8 orientations;
   the first k >= 6 path cells hold a strictly decreasing chain, all other cells <= chain end r;
   the table (k, r) gives P(make a rank-r tile next to the chain end without moving the chain) and
   the best move, by memoised expectimax computed on demand (thread-safe, one mutex). Sizes: k=8 r=7:
   1.3M entries/12 MB/0.3 s, P~0.78 from near-empty free cells; k=7 r=8: 13M/114 MB/3.5 s, P~0.73;
   k=6 r=9 (10 free cells, build a 512): 184M/1.46 GB/73 s, P~0.68. `build/endgame --selftest`
   checks all 8 orientations; `--verify K R STARTS SIMS` confirms the DP by simulation (k=8 r=7:
   table 0.526 vs simulated 0.526). v9's (displaced) formation never matches (0% table moves).
   **v11's corner-locked network plays snakes**: at tile sum 29696-32767, 68-95% of positions are
   table-ready (k>=6), vs 0% for v9. Using tables for every snake ending HURTS (m1@10M d2: 30.0% ->
   22.5%; the sub-game objective ignores the position after a partial collapse); with
   `--endgame-full` (only chains whose ranks fall by exactly one, so success = full collapse into
   32768) it HELPS: d2 30.0% -> 36.4% (min p 0.1) / 37.1% (min p 0.5); d3 35.4% -> 40.7%; table moves
   ~2.3% of all moves.

3. **Tables in the training loop** (`gpu_train --endgame-dir weights/endgame --endgame-min 0.5
   --endgame-full 2`): the GPU loads the saved tables (`snake_k6_r8.egt` 0.64 GB, `snake_k6_r9.egt`
   1.13 GB; fill them with CPU play `--endgame-dir`, which saves on exit) and plays the table move in
   endings with a known entry, so the network learns the combined player's values.
   `scripts/pipeline_v11b.sh`: s2/s2q (second half) from m1q's formations with tables in the loop.
   Coverage: 700 more CPU games added only 3 MB of entries, so the tables are nearly saturated.
   Other findings: depth 4 with lock + tables = depth 3 (42.5%), no longer harmful; table values at
   search leaves (`--endgame-leaf C`) ~+1 point (noise); k=5 tables (11 free cells) do not fit in
   4 GB even with snake-shaped caps. First-half losses (16% of games) are mostly a formation error:
   second row built from the corner side (`[16384 8192 2048 1024]/[512 256 64 16]`) instead of
   snaking back under the 1024.

## Baselines to compare against (pool evaluations: `scripts/eval_pool.sh W STAGES POOL N THREADS OUT opts`)

Crossing rates, i.e. % of games from the pool that reach the stop sum:
| Network | from | to | d1 | d2 | d3 | d4 |
|---|---|---|---|---|---|---|
| v6 s1q1 (whole 16384 phase, unlocked) | v6/pool1 (sum 20480) | 36864 | 9.3% | 33.6% | | |
| v9 final first half (= v6 s1q1) | v6/pool1 | 28672 | | 79.3% | | |
| same, **corner lock at play time only** | v6/pool1 | 28672 | | 0.7% | | |
| v9 final second half (s2q) | v9/pool2g (28672) | 36864 | 30% | 46-48% | 50.5-53.8% | 31% |
| v10 a1 first half (fresh OI vs v9 s2) | v6/pool1 | 28672 | 36.8% | 63.3% | 65.0% | |
| v11 m1 @10M (corner lock, whole phase) | v6/pool1 | 36864 | | 30.0% | 35.4% | |
| same + tables `--endgame 6 --endgame-full --endgame-min 0.5` | v6/pool1 | 36864 | | 37.1% | 40.7% | |
| b6 (init-0, whole phase) | v6/pool1 | 36864 | | 30.4% | 35.7% | 27.9% |

## Findings (what worked, what did not)

Worked: Matsuzaki 8x6 tuples (`012456 456789 012345 234569 01259a 345678 134567 01489a`) >> our
screened tuples; tile-sum stages; pools of stage-entry positions + stop-at-boundary bootstrapping;
optimistic init (V=320k) for late stages (only way they learn the 32768 merge); 2-ply policy on
25-50% of training moves (makes optimistic nets usable under search); root downgrading after 32768
(+3%); per-stage search depth; CPU-trained early game s0cpu.

Did not work: heuristic shaping (nneonneo, snake); ensembles of different networks (scale
mismatch); teacher-student; 3% exploration; TC-forget; full (100%) 2-ply curriculum; a dedicated
32768-phase optimistic stage; refining an earlier stage against a trained later stage (s1b
collapsed); first half trained against an optimistic second half (overvalues unseen formations ->
far-corner builds); **deeper search for optimistic nets: depth 4 is much worse than depth 3**
(31% vs 50.5% on v9's second half), and zeroing barely-trained weights (`neutralize.py --min-a
1e4` or `1e5`) does not change that (50.5%/30%, 50.7%/31.4%).

## Gotchas

* **DISK: WSL crashed twice (2026-10-02 19:37, 10-03 12:25) because the Windows C: drive filled up** (929 GB, 12 GB
  free): the WSL disk image (`C:\Users\furun\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc\
  LocalState\ext4.vhdx`, 707 GB, NOT sparse, never shrinks) grows when WSL writes to never-used space. 10-03: with the
  user's OK, deleted 126 obsolete .ckpt files (200 GB; kept tup/s0cpu, exps/e4, exph1/e4, expcpu/s2, exp2p/e3,
  expsplit/b3). Freed space IS reused (a 2 GB test write did not grow the image), so ~230 GB can be written before
  C: is at risk again. Check `df -h /` (Linux used must stay well below 707 GB) and `df -h /mnt/c` before big writes;
  delete temporary weight files; evals use `--endgame-nosave` (no 2.3 GB table rewrite per run).
* **WEIGHTS CLEANUP 2026-10-04 (user-approved, C: was full)**: deleted 199 superseded weight/checkpoint files (394 GB);
  weights/ went 493 -> 127 GB. Kept (list in results/weights_kept_2026-10-04.txt): best_v5.w, exps/best_v2.w,
  tup/s0cpu.w+ckpt, exph1/e4.w+ckpt, exps/e4.w+ckpt, expseed/s2,s5,s6.w, expsplit/b3.w+ckpt, expsplit/b4s2.w,
  expcpu/start.w, s2.w+ckpt, v11c/final.w, exp32br/e4.w, exprp/real.w, mix.w, expearly/e4,e8,e12.w, all endgame tables
  (weights/endgame, endgame_big, endgame_lt) and all 58 pools (*.bin). Everything else referenced in older notes or scripts
  (v3-v14, exps1, expsplit2, b3_play.w, best_v3/v4 files, ...) is gone; results stay in results/. Rebuild 5-stage players
  with scripts/splice_stage.py / select_stages.py from the kept stage files.
* WSL exports `NAME=GamingLaptop`: never use `NAME` as a script variable (pipeline_v11 uses `RUN`).
* `pkill -f`/`pgrep -f` patterns match your own shell; look up PIDs first, kill by number separately.
* Only one big GPU job at a time (8 GB card; two jobs thrash). CPU evals (14 threads) are fine
  alongside one GPU job.
* Editing a RUNNING queue script: only insert/change text AFTER the line bash is executing. Changing the length of a line
  bash has already passed (e.g. the header of a for loop it is inside) shifts the file under bash's saved offset ->
  "command not found" / syntax error and the queue dies (exp_queue12 died this way 2026-10-05 03:36; its tail moved to
  exp_queue13.sh). Safer: write a new script that waits for the old one.
* Binaries are built to `*.tmp` and renamed (Makefile), so rebuilding doesn't disturb running jobs.
  Do not edit a running pipeline script in place with `sed -i` (bash reads scripts lazily).
* Weight files are 2 GB per 4 stages; checkpoints (.ckpt = w, e, a per weight) 1.6 GB per stage.
* The laptop must not sleep (training pauses; clock jumps in logs are sleeps).

## Log (newest last)

* 2026-10-01 21:14 v10 a1: first half fresh OI vs v9's stage 2 -> far-corner formations (0/281
  adjacent): v9 stage 2 overvalues never-seen formations. Stopped.
* 2026-10-01 22:00 v10 b1: same vs neutralized v9 stage 2. Stopped at 5M (corner finding).
* 2026-10-01 22:21 v11 started (corner lock).
* 2026-10-01 23:00 endgame tables implemented and verified; full-collapse tables +5-7 points on m1@10M.
  `--endgame-full 2` (also one missing rank, tail collapses into the gap): d3 41.4% vs 40.7% (noise),
  table moves 6.6%.
* 2026-10-01 23:25 FULL GAMES, s0cpu early + m1@10M (`$CLAUDE_JOB_DIR/tmp/m1_10M_full.w`, stages
  sum:20480,36864), `--depth 3 --corner-lock 14 --root-downgrade 15 --endgame 6 --endgame-full 2
  --endgame-min 0.5`, 210 games: **464,184 +- 13,863, 16384 94.3%, 32768 41.0%** (best benchmark:
  460,857 / 96.5% / 37.0%). Parity already, with an under-trained single-stage phase network.
  Another 280 games (seed 999, recorded in `$CLAUDE_JOB_DIR/tmp/m1full_games.txt`): 478,332 +- 11,351,
  96.8% / 43.9%. Where they are lost (`build/endgame --query 1` gives table p for boards on stdin):
  96/280 games never reach a gapless table-ready position (1 of them reaches 32768): network losses
  in the first half (46) and second half before the full chain; 184/280 do, with first table p
  mostly 0.6-0.8 and 64-68% success (~= p). So P(32768) ~= 0.66 x 0.67. Levers: better play before
  the takeover (more games reach it, with higher p) and earlier takeover (bigger tables, k=5 with
  snake-shaped caps, est. 0.4-1 GB reachable).
* 2026-10-02 00:18 m1q done (whole phase, lock, 2-ply 25%): d3 + tables 45.95% (420 games, pool1 ->
  36864). Full games s0cpu + m1q (`weights/v11/m1q_full.w`, seed 999, 280 games): 469,470 +- 11,384,
  97.1% / 40.4% (games reaching 32768 average 672,703; the others 331,952 -> to beat 711,769 we
  need ~85% 32768 AND ~780k average in those games, i.e. a much stronger 32768 phase too).
* GPU tables verified: m1q 1-ply on pool2q second halves, no learning: 25.7% -> 39.6% stage exit
  with tables (17% table moves).
* 2026-10-02 00:20 v11b started (second half with tables in the loop): at 2M episodes 29.9% stage
  exit / 43.1% 32768 (v9's s2 without tables: 0% at 2M, plateau 27.3% after 9-12M) -> tables in the
  loop speed up and raise learning dramatically. Next: v11c = whole phase (m1) with tables in the
  loop too (tables also apply to the first half's final collapse [14 12 11 10 9 8] -> 8192).
* 2026-10-02 00:55 **1000-game benchmark s0cpu + m1q, lock, RD, tables** (`results/bench/m1q_eg1000`,
  `weights/v11/m1q_full.w sum:20480,36864 --quantize --depth 3 --corner-lock 14 --root-downgrade 15
  --endgame 6 --endgame-full 2 --endgame-min 0.5 --endgame-dir weights/endgame`): 466,748 +- 6,051,
  16384 95.0%, 32768 40.8% (new best, small margin). Early game check (700 games to sum 20480, d3):
  92.1% without tables, 91.6% with (no harm); the early game loses ~8% of games before 20480 —
  another lever (macroxue reaches 16384 in 98.7%).
* Early game (s0cpu, stage 0 = sum < 20480): depth 4 = depth 3 (92.9% vs 92.1% reach sum 20480);
  corner lock in the early game hurts (lock 13: 84.4%, lock 12: 83.4%; the network was not trained
  with it). Early losses in the 1000-game benchmark: 3.7% die while building the 16384 (max 8192),
  3.1% right after it forms (sum 16384-20480: leftover tiles of the collapse scattered, sometimes
  the 16384 forms off the corner so the lock does not apply). Fix later with the same recipe as the
  16384 phase: a stage from sum ~16384 (or the 8192 phase) with optimistic init, lock, tables.
* 2026-10-02 00:54 v11b s2 done: plateau 47.0% stage exit (1-ply + tables, v9: 27.3%); s2q started.
* Stage specs can now say `S/R` = "tile sum >= S or a tile of rank >= R exists" (StageFn in
  search.h and the GPU's stage_of), e.g. `sum:20480/14,28672,36864`: stage 1 starts the moment the
  16384 forms. v11c uses it (pool16 = first position with a 16384, from the early network's greedy
  play); evaluate v11c with `ST4=sum:20480/14,28672,36864 scripts/eval_v11.sh ...`.
* PLAN v12 (after v11c): the 8192 phase with the same recipe — stages
  `sum:10240/13,20480/14,28672,36864` (stage 1 = from the 8192's formation to the 16384's), pool of
  first positions with an 8192, fresh optimistic, `--corner-lock 13`, tables in the loop,
  bootstrapping at the 16384 from v11c's phase network (consider neutralizing its untrained weights).
  Goal: the early game loses ~7% of games (3.7% building the 16384, 3.1% just after); macroxue
  reaches 16384 in 98.7%.
* 2026-10-02 01:30 **v11b eval**: second half from pool2q: d2 57.9%, d3 63.1% (v9: 50.5-53.8%). But
  full games (280, seed 999): 475,223 +- 11,519, 97.1% / 42.1% (m1q alone, same seeds: 469,470 /
  40.4%). **Distribution shift**: on positions from real depth-3 play at sum 28672
  (`weights/v11b/pool2real.bin`, 1147 positions), v11b's s2q gets 56.7% vs m1q 53.2% (only +3.5;
  +13 on its own training pool). The networks generalize poorly off their training starts -> pools
  should come from (or close to) the real play policy. Full-game breakdown: 97% reach 16384 x 75%
  first half (m1q from pool1 at d3: 81.9%; full games lose 22% there) x 57% second half = 42%.
* **Real-start benchmark for the 16384 phase**: `weights/v11c/pool16real.bin` = 2886 positions at the
  moment the 16384 forms in depth-3 play (s0cpu early game). v11b's player (`weights/v11b/final.w`,
  stages sum:20480,28672,36864, d3, lock, tables) from there to sum 36864: **47.2% +- 0.9** (first
  half 80.1%, second half 59.0%). This is the number to beat (macroxue's ~82% conversion needs
  ~95% x 86%).
* Table threshold at play time must match training: v11b real-start phase test with
  `--endgame-min 0` 45.4%, `0.5` 47.2%, `0.75` 33.1% (the network trained with tables at p >= 0.5
  never learned those positions itself).
* 2026-10-02 ~02:50 RUNNING: v11c m1 (whole phase from the 16384's formation, tables in the loop;
  started exiting at ~8.5M episodes, 7.6% stage exit at 10M) -> m1q -> a watcher stops
  `pipeline_v11c.sh` after m1q -> `scripts/pipeline_v11c2.sh` (launched automatically): pool2real =
  m1q's real depth-3 first halves from `weights/v11c/pool16real.bin` (4 passes), pool2mix = pool2q +
  real x k (30% real), then s2/s2q on the mixed pool -> `weights/v11c/final.w`
  (stages `sum:20480/14,28672,36864`). Evaluate on pool16real (real-start phase test, v11b: 47.2%)
  and full games; then 1000-game benchmark if better.
* Depth-3 baseline on the first 1400 real starts (games 0-1399, default seed): first half 81.1%,
  second half 56.3%, whole 45.7%. Depth 4 in the first half (`--stage-depth 3,4,3,3`): whole 37.9%
  -> depth 4 hurts the (optimistic) first-half network badly; stay at depth 3.
* 2026-10-02 04:10 v11c m1q (whole phase with tables, from the 16384's formation): first half from
  real starts 80.0% (11,544 games) = v11's 80.1% -> tables in the loop do not help the first half.
  First-half losses (1000 recorded games): 2.7% cleanup right after the 16384 (sum < 20480), 6.6%
  while building the 8192 (20480-24576), 2% after it (24576-26624), 7.1% at 26624-28672 = building
  the 4096 with [16384 8192 2048 1024] in place (snake usually right, chain with TWO gaps -> no
  table; free rows clog). Idea: move the second-half boundary earlier (to the 8192's formation,
  sum 24576) so the stronger table-trained network covers it, or 3 sub-stages; and/or allow
  2-gap chains when the gaps would be filled exactly by the collapse.
* `--endgame-full N` now allows N-1 one-rank gaps. Real-start phase test (v11b player): full 3 (two
  gaps) 45.6% vs full 2 47.2% -> partial collapses that leave a gap stay harmful; keep 2.
* Rejected: network-valued tables (exits valued by the network instead of 1, so partial collapses
  would be judged by the position they leave). Network values depend on the actual chain, so a
  table cannot be shared per (k, r) as probability tables are: one table per distinct chain,
  0.6-1.1 GB each -> does not fit in 7 GB; for the full collapse it would pick ~the same moves.
* QUEUE (automatic): v11c2 -> (done: weights/v11c/final.w) -> eval ($CLAUDE_JOB_DIR/tmp/eval_v11c.sh:
  real-start phase test seed 999 [v11b 46.8%] + 280 full games seed 999 [v11b 475,223 / 42.1%];
  results in results/v11c/eval/) and, on the GPU, `scripts/pipeline_v12.sh` (8192 phase: stages
  `sum:10240/13,20480/14` for training, pool8 = first positions with an 8192, corner lock 13,
  tables with `--endgame-min-rank 7`, bootstrap from v11c's first half with never-trained weights
  neutralized; output `weights/v12/final.w`, 5 stages `sum:10240/13,20480/14,28672,36864`, play
  with `--corner-lock 13`).
* Rejected: chain lock in search (`--chain-lock K --chain-min-rank R`: skip moves that pull a snake
  chain tile (rank >= R) out of its cell). Real-start test, v11b player, seed 999: chain lock 4
  (tiles >= 1024) 37.5% vs 46.8% without (a version counting any decreasing run as chain: 0%).
* 2026-10-02 05:30 **v11c eval**: real-start phase test (seed 999) 46.0% (first half 81.5%, second half
  56.5%) vs v11b 46.8% (80.1/59.0) -> mixing real positions into the second half's pool did NOT
  help. But full games (280, seed 999): **511,130 +- 11,746, 96.8% / 48.6%** (v11b same seeds 475,223 /
  42.1%) -> 1000-game benchmark running (results/bench/v11c1000).
* Rejected: ensembles of two similarly trained second halves (v11b + v11c, mean) and depth 4.
  Second half from pool2real: d3 single 58.7%, d3 ensemble 55.5%, d4 single 55.8%, d4 ensemble 53.3%.
* QUEUE (automatic, $CLAUDE_JOB_DIR/tmp/after_v12.sh): when v12 is done -> GPU `scripts/exp_depth.sh`
  (T1: v11c s2q + 1M episodes `--train-all-root`, T2: + 1M episodes 2-ply on 100%; then depth 3 vs 4
  on weights/v11b/pool2real.bin, results/expd/log) and CPU v12 eval (results/v12/eval: early game
  700 games seed 4321 [s0cpu 92.1% to sum 20480], full games 280 seed 999 [v11c 511,130 / 48.6%]).
* 2026-10-02 06:10 **1000-game benchmark v11c** (`results/bench/v11c1000`): **488,691 +- 6,260, 16384
  94.9%, 32768 45.5%** = new best (+22k, +4.7 points over m1q + tables).
* Rejected: probability cutoff to make depth 4 useful (second half, 600 real positions): d3 57.7%,
  d4 + prob-cut 0.01 57.2%, d4 + prob-cut 0.002 53.2%.
* gpu_train `--skip-lower`: stages below the trained one are not loaded onto the GPU (episodes all
  start from the pool, and stages never decrease); saving copies them from --load. Lets 5-stage
  files train next to ~2 GB of tables.
* QUEUE (automatic, $CLAUDE_JOB_DIR/tmp/after_expd.sh): when weights/expd/t2.w exists -> GPU
  `scripts/pipeline_v13.sh` (second half split at 32768: new stage [28672,32768) fresh OI + lock +
  tables, bootstrap from v11c's second half with never-trained weights neutralized, pool =
  weights/v11c/pool2mix.bin; player weights/v13/final.w, stages `sum:20480/14,28672,32768,36864`)
  -> CPU eval (results/v13/eval: real-start phase seed 999 [v11c 46.0%], 280 full games seed 999
  [v11c 511,130 / 48.6%]).
* v11c benchmark, where the 1000 games die (494 died with max 16384): cleanup after the 16384 3.0%,
  building the 8192 (20480-26624) 9.0%, building the 4096 (26624-28672) 6.7%, 28672-30720 4.6%,
  **30720-32768 18.4%** (building 2048/1024/512 into the snake before the tables; v13's target),
  32768-34816 7.7% (table-played collapse). Typical death: snake mostly right, free region clogged
  with small tiles; some are one-gap table-ready positions handed over with low p.
* 2026-10-02 06:20 **Guei et al. 2022, details** (arXiv 2111.11090, read the PDF): 2-stage 8x6 network
  (stage 2 = every state with a 16384, played to game over), **100M full episodes per stage** (200M
  total, 66 h on a 20-thread Xeon, lock-free sequential updates), OTD (TD, alpha 0.1 -> 0.01 at 50%
  -> 0.001 at 75%) then TC fine-tuning for the last 10%; V_init 320k. Results: 1-ply 412,785 / 85.4% /
  30.2%; 3-ply (~our depth 2) 563,316 / 96.9% / 57.9%; 5-ply (~our depth 3) 608,679 / 97.8% / 67.4%;
  6-ply 625,377 / 98.8% / 72.0%. Their networks are far stronger than ours at equal depth and still
  gain from depth. We train ~10x less, and **our GPU trainer's batched update averages the errors of
  a weight touched c times per round (one update instead of c)**: shared chain features learn up
  to c x slower than rare ones -> plausible cause of early plateaus, poor generalization (distribution
  shift) and depth fragility. `gpu_train --update-scale mean|sum|capK|sqrt` added (log prints c).
* QUEUE (automatic, $CLAUDE_JOB_DIR/tmp/after_v12b.sh, replaces after_v12.sh): when v12 is done ->
  GPU `scripts/exp_upd.sh` (4M-episode second halves with mean/sum/cap8/sqrt; then real-start phase
  tests; results/expu/log) then `scripts/exp_depth.sh`, then v13 (after_expd.sh); CPU v12 eval.
* 2026-10-02 06:50 **v12 FAILED**: the 8192-phase network (fresh OI, lock 13, tables; 1-ply training
  stage exit ~81%) is worse than s0cpu under depth-3 search: early game to sum 20480 88.3% vs 92.1%;
  full games (280, seed 999) 475,135 / **16384 88.6%** / 32768 43.9% vs v11c 511,130 / 96.8% / 48.6%.
  Do not use weights/v12. Note: s0cpu is a zero-initialised network and gains from depth; the
  optimistic ones do not.
* Update-rule experiment: measured c (feature updates per distinct weight per round) = 4.0 -> 6.1
  during second-half training; the mean variant reproduces v11c's s2 curve.
* IDEA (high priority): a zero-initialised 16384-phase network with corner lock + tables in the
  loop. Optimism was needed only to escape the far-corner/displaced formation trap, which the lock
  now prevents; zero-init networks are robust to deeper search (s0cpu: d2 85.7% -> d3 96.4%).
* QUEUE (current, $CLAUDE_JOB_DIR/tmp/after_expu.sh; supersedes after_v12b/after_expd): exp_upd
  training (GPU, running) -> pick the update rule with the best 4M stage exit (must beat mean by
  > 1 point) -> `UPD=<rule> scripts/pipeline_v14.sh` (zero-init whole phase, lock, tables; then
  depth 2/3/4 tests on 1400 real starts, results/v14/pipeline.log) -> `scripts/pipeline_v13.sh` ->
  v13 eval (results/v13/eval) + `scripts/exp_depth.sh`. exp_upd's own real-start phase tests run on
  the CPU after its training (results/expu/log). OI baseline for v14: v11c m1q at d2/d3/d4 on the
  same 1400 starts (running in background).
* Rejected: amplified batched updates. `--update-scale sum` and `cap8` diverge immediately (episodes
  die in a few hundred moves, avg ~5k): with optimistic init the early errors are ~-270k and c-fold
  steps overshoot faster than TC can damp them. `mean` (the existing rule) is what keeps the
  32768-games-in-flight trainer stable. (A sequential-like regime would need fewer games in flight.)
* OI whole-phase network (v11c m1q, lock + tables) from 1400 real starts, seed 999: d2 35.1%, d3
  41.8%, **d4 43.2%** -> with the corner lock and tables, depth 4 no longer hurts this network.
* QUEUE (current, $CLAUDE_JOB_DIR/tmp/after_v13.sh; after_expu.sh was stopped after it started v13,
  because v14's first try failed: `gpu_train --no-learn` never saves, so the base file is now made
  with `neutralize.py --fresh 2 --value 5000`): v13 (GPU, running since 06:56) -> v13 eval (CPU,
  results/v13/eval) and GPU `pipeline_v14.sh` then `exp_depth.sh`.
* v11c with depth 4 in the first half (`--stage-depth 3,4,3,3`), 1400 real starts: first 80.4 / second
  58.6 / whole 47.1% vs d3 81.2 / 58.4 / 47.4% -> no effect.
* **Sequential vs batched training** (hypothesis: the GPU's averaged batch updates -> networks that
  rely on rare features, generalize poorly, degrade with depth; s0cpu, the one network that gains
  from depth, was CPU-trained; v12's GPU 8192 phase lost to it). The CPU trainer (Hogwild,
  sequential, backward TD(lambda) sweeps; ~4M moves/s) now has `--corner-lock`, `--endgame-dir`
  (lock-free lookup only via eg::Snake::peek), `--endgame-min`, `--endgame-full`.
  `scripts/exp_cpu.sh` (running since 07:27): second half from fresh OI on the CPU, 4M episodes
  (2-stage file weights/expcpu/start.w, stages "sum:36864"; tables weights/endgame_big = r8+r9
  symlinks to save RAM), then depth 3 vs 4 on weights/v11b/pool2real.bin vs the GPU's 4M-episode
  equivalent (weights/expu/mean.w). results/expcpu/log.
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_v13.sh, relaunched): v13 done -> GPU v14 then exp_depth; CPU waits for
  exp_cpu to finish, then the v13 eval.
* 2026-10-02 07:55 **exp_cpu result**: sequential CPU training learns ~2x faster per episode (32768 in
  45% of episodes at 750k vs ~2M on the GPU) but reaches the same plateau (~54%). Second half from
  real positions (weights/v11b/pool2real.bin, 1147, seed 31): CPU 4M episodes d3 57.6% / **d4 60.0%**;
  GPU 4M episodes (weights/expu/mean.w) d3 57.2% / **d4 59.7%** -> the training method does NOT
  matter; but **4M-episode networks gain from depth 4**, while v11b's fully trained s2q (12M + 2-ply
  curriculum) degrades (d3 58.7%, d4 55.8%). Depth fragility comes with longer training or with the
  curriculum (being measured: v11b s2.w = 12M without curriculum at d3/d4). At depth 4 the 4M
  networks already beat the fully trained one at depth 3.
* 2026-10-02 08:10 **KEY FINDING: greedy over-training destroys search strength.** Same setup and pool
  (v11c second half), real positions (pool2real), d3 / d4: 4M episodes 57.2% / 59.7%; 12M episodes
  48.1% / 37.1% (the 1-ply training metric only moved 44.6% -> 47.8%). v11b's s2 (12M) 46.3 / 35.4;
  with the 2-ply curriculum (s2q) 58.7 / 55.8 (the curriculum repairs part of it). This is why our
  late networks degraded with depth. -> train shorter / find the best length per stage and use
  depth 4. `scripts/exp_snap.sh` (running): second half snapshots at 1,2,3,4,5,6,8M episodes + a
  2-ply curriculum from 4M; `scripts/exp_snap_eval.sh` evaluates each as v11c's second half at d3/d4
  on 600 real positions (results/exps/eval.log).
* v13 eval: real-start phase 45.9% (v11c 46.0%), full games 512,472 / 96.8% / 51.1% (v11c 511,130 /
  48.6%) -> no clear gain from splitting the second half (both its networks are 12M+ episodes,
  i.e. overtrained by the new finding).
* v14 stopped at 6.5M: zero-init learns slowly (stage exit 4.5%) and never reaches table endings.
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_exps.sh): exp_snap training done -> GPU `scripts/exp_snap1.sh`
  (whole-phase/first-half network, v11c's m1 recipe with --skip-lower, snapshots at 8,9,10,11,12,14M);
  after exp_snap's evals -> CPU `scripts/exp_snap1_eval.sh` (first half from 700 real starts at d3/d4
  per snapshot plus v11c's m1q as `base`; results/exps1/eval.log).
* 2026-10-02 08:50 **Training-length curve, second half** (weights/exps/eN.w, v11c recipe, evaluated as v11c's
  second half on 600 real positions, d3 / d4): 2M 54.5/56.8, **3M 58.0/60.0, 4M 58.0/60.5**, 5M
  56.3/57.7, 6M 56.5/52.2, 8M 52.8/45.2 (12M, other subset: 48.1/37.1). Peak at 3-4M episodes, then a
  steep decline, worst at depth 4. All our late-stage networks so far were trained 12-14M episodes.
* 2026-10-02 09:00 **Full games, v11c with the 4M second half at depth 4** (`weights/exps/v11c_e4.w`, stages
  `sum:20480/14,28672,36864`, `--depth 4 --stage-depth 3,3,4,4`, lock, RD, tables), 280 games seed 999:
  **523,686 +- 11,731, 96.8% / 54.6%** (v11c same seeds 511,130 / 48.6%).
* 2-ply curriculum continued from the 4M second half (e4q, +1.5M at 25% 2-ply): d3 59.0 / d4 60.3 vs e4
  58.0 / 60.5 -> no gain, no harm (unlike more 1-ply training).
* 2026-10-02 09:55 **1000-game benchmark, v11c + 4M second half at depth 4** (`results/bench/v11c_e4_1000`):
  **506,542 +- 6,610, 16384 94.9%, 32768 48.8%, 65536 0.1% (first one; max 1,137,340)** = new best.
* First-half baseline (v11c m1q, 14M + curriculum), 700 real starts to sum 28700: d3 81.0%, d4 77.9%
  (depth 4 hurts it; snapshots of the first half are training: exp_snap1).
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_exps1.sh): exp_snap1 training done -> GPU `scripts/exp_explore.sh`
  (second half with 3% and 6% exploration, snapshots 3/4/6M); after exp_snap1's evals -> CPU
  `scripts/exp_explore_eval.sh` (d4 on 600 real positions; results/expx/eval.log). Running on the
  CPU now: depth 5 vs 4 for the 4M second half on 300 real positions.
* Depth 5 for the 4M second half (300 real positions): d4 58.3%, d5 57.0% (+-2.9; 6.5x slower) -> stay at d4.
* Weight averaging of the 3M/4M/5M second-half snapshots (`scripts/avg_weights.py`): d4 60.5% = e4 alone.
* exp_snap1 note: the whole-phase OI run's takeoff varies between runs; this one dipped deeper (avg 50k at
  6M vs 95k for v11c's m1) and has not taken off by 9M (first-half snapshots e8/e9: 0% to 28700).
  Extend the snapshots if the takeoff comes after ~12M.
* First-half snapshots (exps1, whole-phase OI run; first half from 700 real starts to sum 28700, d3/d4;
  v11c's m1q baseline 81.0 / 77.9): e8 0/0, e9 -, e10 0.6/0.4, e11 38.3/31.3, e12 67.0 (takeoff at ~11M).
  QUEUE ($CLAUDE_JOB_DIR/tmp/after_exps1b.sh): exps1 training done -> GPU `exp_snap1b.sh` (15, 16, 18M) then
  `exp_explore.sh`; CPU `exp_snap1b_eval.sh` then `exp_explore_eval.sh`.
* First-half snapshots, continued (d3/d4, 700 real starts): e14 **74.0 / 72.3**, e15 ? / 67.4, e16 71.1 / 63.1,
  e18 72.6 / ? -> peak ~3M after takeoff (14M here), below v11c's m1q (81.0 / 77.9: 14M + curriculum, from
  a run that took off ~2.5M earlier). QUEUE ($CLAUDE_JOB_DIR/tmp/after_expx.sh): after exp_explore ->
  `scripts/exp_snap1q.sh` (2-ply curriculum on e14 and e18) and `exp_snap1q_eval.sh`.
* Rejected: exploration (3% / 6% random moves, Watkins cut) in second-half training: episodes die from the
  random moves (avg ~14k vs ~90k, stage exit 0%), nothing is learned. Late-game positions are too tight.
* Rejected (again): ensemble mean of two 4M second halves (GPU + CPU trained): d4 57.2% vs 60.5% alone.
* Gotcha: play `--endgame-dir` saves tables back on exit (atomic rename) -> it replaces symlinks with
  copies; weights/endgame_big = symlinks to r8/r9 (re-link if they turn into files). Two networks + all
  tables (~4.5 GB) got OOM-killed next to the GPU trainer: use weights/endgame_big for big CPU jobs.
* Network strength vs Guei at 1-ply (full games, 1400, seed 77): v11c_e4 without tables 83.7% 16384 / 1.0%
  32768 (our late networks rely on the tables they were trained with); with tables + lock 334,455 /
  84.9% / 19.7%. Guei 2-stage 1-ply (no tables): 412,785 / 85.4% / 30.2% -> their networks are clearly
  stronger. Differences: their learning rule (TD alpha 0.1 -> 0.01 -> 0.001, TC only for the last 10%;
  ours TC throughout) and full-game episodes from the 16384 (ours stop at stage boundaries).
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_snap1q.sh): after the first-half curriculum training -> GPU
  `scripts/exp_otd.sh` (second half with TD alpha 0.1 (4M) -> 0.01 (2M) -> 0.001 (1M), snapshots a2 a4
  b6 c7, evaluated at d3/d4 on 600 real positions after exp_snap1q_eval; results/expo/eval.log).
* The 2-ply curriculum on whole-phase snapshots is slow (~67 min per 1.5M); e18q skipped
  (weights/exps1/e18q.w is a symlink to e18.w, so its "e18q" eval = e18).
* Current best's losses (v11c_e4, 1000 games): cleanup after the 16384 3.0%, first half 15.7% (same network as
  v11c), second half 27.4% (28672-30720 4.0, 30720-32768 14.8 (v11c 18.4), 32768-34816 8.6).
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_otd.sh): after exp_otd's training -> `scripts/exp_h1.sh` (dedicated
  first half, fresh OI, bootstrap from the 4M second half with never-trained weights zeroed, snapshots
  1/2/3/4/6M; first half evaluated as v11c_e4's stage 1 from 700 real starts, d3/d4; results/exph1).
* 2026-10-02 12:15 **First half: snapshot + curriculum** — exps1 e14 (14M whole-phase episodes, ~3M after
  takeoff) + 1.5M 2-ply curriculum (e14q): first half from 700 real starts **d3 81.0 / d4 83.6** (e14 alone
  74.0 / 72.3; v11c m1q 81.0 / 77.9). The curriculum matters for this network, and with it depth 4 helps.
  New candidate `weights/exps/best_v1.w` = v11c_e4 with stage 1 = e14q, `--stage-depth 3,4,4,4`.
* Rejected: plain TD with Guei's rate schedule for the second half (alpha 0.1 x4M -> 0.01 x2M -> 0.001 x1M):
  1-ply stage exit 6-10%, d3/d4 6-9% (TC: 58-60%) -> far too slow at our training lengths; keep TC.
* **best_v1 is broken in full games**: v11c_e4 with stage 1 = exps1 e14q (first half 83.6% at d4 when e14q.w
  is evaluated alone) gives 330,155 / 16384 90.0% / 32768 0.0% (280 games). Stages verified correct by
  checksum. Suspect: e14q never learned to complete the whole phase (stage exit ~0-2%), so its values
  near sum 28672 (and near the 16384's formation, where s0cpu's search sees stage-1 leaves) are
  miscalibrated vs its neighbours. Diagnosing from real starts (bsgpfsuik).
* **ROOT CAUSE of best_v1's failure**: from real starts, 83% reach sum 28700 but 0% reach 36864. The exps1 run
  (late takeoff) learned the FAR-CORNER formation for the 8192 under the corner lock: the 16384 stays in its
  corner but the 8192 is built at the other end of the same edge with 2048/1024 between them (e.g. column
  [8192 1024 2048 16384]); the second half (trained on v11c's snake formations) gets 0% from there.
  Lessons: (1) OI runs can settle on different formations (v11c's m1 happened to learn the snake);
  (2) **evaluate first-half candidates through the whole phase** (to 36864, with the real second half),
  never only to 28672 — reaching the sum says nothing about the formation.
* Whole-phase test from 700 real starts (seed 999), current best v11c_e4: **52.6%** (stage depths 3,3,4,4),
  48.7% (3,4,4,4). Dedicated first half (exph1, bootstraps from e4): e2 37.4% (3,3,4,4); e3/e4/e6 in
  results/exph1/eval2.log. Curriculum on exph1 e4 running (`scripts/exp_h1q.sh` -> weights/exph1/e4q.w).
* 2026-10-02 13:30 **Dedicated first half works** (exph1: [16384 formation, 28672), fresh OI, lock, tables,
  bootstrapping from the 4M second half with never-trained weights zeroed). Whole phase from 700 real
  starts, stage depths 3,3,4,4 / 3,4,4,4: e2 37.4/41.6, e3 50.7/53.9, **e4 55.1/58.0**, e6 52.7/54.4
  (current best's first half: 52.6/48.7). Peak again at ~4M. Candidate `weights/exps/best_v2.w` =
  v11c_e4 with stage 1 = exph1 e4, `--stage-depth 3,4,4,4` (280-game check running; curriculum on e4
  training: weights/exph1/e4q.w).
* best_v2 280 full games (seed 999): 524,891 +- 12,176, 96.8% / 50.7% (v11c_e4 same seeds 523,686 / 54.6%) —
  conflicts with the whole-phase test (58.0 vs 52.6); 1000-game benchmark running (results/bench/best_v2_1000).
* QUEUE ($CLAUDE_JOB_DIR/tmp/after_h1q.sh): after the exph1 e4 curriculum -> `scripts/exp_s2n.sh` (collect where
  best_v2's new first half reaches 28672 (GPU, no-learn), mix 2:1 with the old pool, retrain the second half
  from fresh OI to 3/4/5M; weights/exps2n/eN.w). Then evaluate whole phase with exph1 e4 (or e4q) first half.
* QUEUES (2026-10-02 13:45): GPU: exph1 e4 curriculum -> `exp_s2n.sh` (second half on the new first half's
  positions) -> `exp_v12b.sh` (8192 phase with snapshots, bootstrap from exph1 e4, lock 13). CPU:
  best_v2 1000-game benchmark -> `scripts/eval_queue1.sh` (results/evalq1/eval.log: h1q whole phase,
  s2n e3/e4/e5 with exph1 e4, then `exp_v12b_eval.sh` -> results/exp12b/eval.log).
* 2026-10-02 14:00 **1000-game benchmark best_v2** (`results/bench/best_v2_1000`): **524,809 +- 6,477, 16384 94.9%,
  32768 52.7%** = new best.
* The 2-ply curriculum HURTS a network stopped at its peak: dedicated first half e4 + 1.5M curriculum (e4q)
  whole phase 51.1 (d4) / 45.7 (d3) vs e4 alone 58.0 / 55.1. (It helped e14, a whole-phase network past its
  peak.) Rule: train to the peak, no curriculum.
* Second half retrained on the new first half's positions (exps2n, pool 2/3 GPU 1-ply positions from exph1 e4
  + 1/3 old pool2mix): whole phase e3 54.0, e4 54.1, e5 52.4 vs 58.0 with the old 4M second half (pool2mix =
  v11c m1q's positions + 30% real d3 positions) -> keep exps/e4; real positions in the pool seem to matter.
* QUEUES (14:40): GPU: exp_v12b (8192 phase, to 6M) -> `scripts/exp_split.sh` (first half split at 24576: stage
  B [24576,28672) bootstrapping from the 4M second half, snapshots b2/b3/b4/b6; pool24 from best_v2's first
  half). CPU: eval_queue1 (now exp_v12b_eval: from scratch to 28700, results/exp12b/eval.log) ->
  `exp_split_eval.sh` (B snapshots through the whole phase, results/expsplit/eval.log; baseline 58.0%).
* exp_split: stage B [24576,28672) trained (b2/b3/b4/b6; 1-ply stage exit b4 83.2%, b6 84.0%); stage A
  [16384f, 24576) training against b4 (`scripts/exp_split_a.sh`, pool16 + 30% real; snapshots a2/a3/a4/a6).
  Evaluate A+B together through the whole phase once both exist (B alone: `exp_split_eval.sh`, queued).
* Rejected again: an optimistic 8192-phase network (exp_v12b, even at its peak): from scratch to 28700, e2 d3 74.1 /
  d4 76.0, e3 d3 74.1 vs 81.9% with s0cpu's early game. The CPU-trained zero-init early game stays.
* exp_split B (with exph1 e4 below 24576, the 4M second half above 28672), whole phase from 700 real starts:
  b2 58.0, b3 59.4, b4/b6 pending (baseline 58.0). Stage A done (a6 1-ply exit 47.3%); A+B eval queued
  (`exp_split_eval_a.sh`). GPU (15:32): `scripts/exp_split2.sh` = second half split at 32768 (C2 then C1,
  snapshots c*/d* in weights/expsplit2).
* best_v2's losses (1000 games): cleanup 1.8% (v11c_e4 3.0), first half 11.3% (15.7), second half 29.1% of all
  games = 35.6% of the games entering it (28672-30720 4.3, **30720-32768 17.5**, 32768-34816 7.3). The second
  half converts ~64% (same as before); it is now the main loss -> exp_split2 (C1/C2).
* exp_split A+B (A [16384f,24576) trained against b4): a2 0.9, a3 10.1, a4 44.4 (a6 pending) vs 58.0 -> A takes
  off slowly; the dedicated first half stays. exp_split2 trained (C2 c2..c6 exit 79-81%, C1 d2..d6 exit ~63%);
  eval queued (`exp_split2_eval.sh`: d2/d3/d4/d6 + c4 with exph1 e4, results/expsplit2/eval.log).
* Seed search (16:13): `scripts/exp_seeds2.sh` trains the 4M second half with seeds 2/3/4 (weights/expseed/sN.w);
  evaluate each through the whole phase (OI runs vary a lot between seeds).
* a6+b4: 51.0% -> splitting the first half at 24576 rejected. C1/C2 split: d2+c4 56.4% (others pending).
* QUEUES (16:40): GPU second-half seeds (exp_seeds2) -> first-half seeds (`exp_seeds1.sh`, weights/expseed/hN.w);
  CPU: exp_split2_eval -> `exp_seeds2_eval.sh` -> `exp_seeds1_eval.sh` (results/expseed/eval.log; best_v2 58.0%).
* C1/C2 split: d2 56.4, d3 56.7, d4 58.3 (+c4) vs 58.0 -> splitting the second half does not help either; per-stage
  capacity is not the limit now.
* QUEUE: after the first-half seeds -> GPU `scripts/exp_lowrate.sh` (4M second half continued with TC alpha 0.3 / 0.1
  for +1M/+2M: can a lower rate after the peak keep improving?) -> CPU `exp_lowrate_eval.sh` (results/explr).
* C1 at 6M (d6+c4): 41.6% (overtrained). Second-half seeds (4M each, whole phase): s2 59.3, s3 57.6 (original 58.0)
  -> seed variation ~noise for the second half.
* Second-half seeds complete: s2 59.3, s3 57.6, s4 54.7 (original 58.0).
* QUEUE: after exp_lowrate -> `scripts/exp_2ply.sh` (second half trained with the 2-ply policy on ALL moves from
  scratch, snapshots 2/3/4M, ~2 h; results/exp2p/eval.log).
* **First-half seeds: formation is a lottery.** h2 14.0%, h3 13.6% over the whole phase (training exits 58.4 / 53.1%
  look fine) -> they learned a bad (far-corner) formation; the original exph1 e4 (seed 1) is a lucky good run.
  h4 57.0% (good formation) -> ~2 of 4 OI first-half runs learn the snake.
  Needed: a training-time constraint that makes the first half learn the snake reliably (e.g. the second-largest
  tile >= 4096/8192 must stay next to the max tile).
* Rejected: lower TC rate after the peak (4M second half + 1M/2M at alpha 0.3 / 0.1): whole phase 57.6 / 57.4 / 56.6
  / (a1_2 not run) vs 58.0.
* **macroxue's losses by tile-sum range** (their outputs/2048b.d*, final boards): d3: <16384 18.6%, cleanup 3.7, first
  half 10.5, 28672-30720 2.9, 30720-32768 6.4, >=32768 (collapse) 5.4; d8: 1.3 / 0.2 / **0.8** / 1.1 / 8.3 / 7.8.
  Ours (best_v2): 5.1 / 1.8 / 11.3 / 4.3 / 17.5 / 7.3. Depth fixes their first half; their tables (5-6 locked tiles,
  rank caps, up to 27 GB) make their second half convert ~83% from sum 30720 at any depth; ours converts 68%.
  Our conversion to 32768 from a full chain 16384..2048 / ..1024 / ..512: 69.3 / 73.4 / 77.2% (760/718/674 games).
* **Leaf view** (`play --leaf-view TOP GAP [--leaf-view-max-sum S] [--leaf-view-safe]`): leaves holding a tile >= TOP
  are evaluated in their downgraded view (16384 -> 8192 ...), so the early-game network s0cpu values 16384-phase
  boards; the search runs on real boards. Whole phase from 700 real starts: view everywhere 11.3% (the view
  distorts: two tiles just below the gap look like they merge into the lowered chain end, so real progress
  looks worse); view only in the first half (sum < 28672) **58.3%** = best_v2 58.0: first-half deaths 92 -> 67
  (sum < 24576: 43 -> 23) but the second half converts worse (66.8 -> 64.5%). `--leaf-view-safe` picks a gap
  with at most one tile just below it. Round 2 (scripts/exp_leafview2.sh): safe gap in the first half 57.1% (same
  first-half deaths), safe view everywhere 0.6% (second half dies), **view only while building the 8192 (sum < 24576)
  59.9%** (deaths < 24576: 43 -> 25; 24576-28672 49 -> 62; second half 202 -> 194). Candidate option:
  `--leaf-view 14 6 --leaf-view-max-sum 24576`.
* **Layered exact DP** (`src/layered.h`, tool `build/layered`): the free cells' tile sum grows only by spawns, so a
  sub-game can be solved layer by layer (largest sum first, two layers in memory) over ALL configurations within
  per-cell rank caps, written to disk (uint16 per state, combinatorial rank inside each layer; play reads single
  entries with pread). Verified: k=8 r=8 reproduces all 560,755 memoised entries exactly (P and move). Speed
  ~1.5M states/s/thread. Queued: **k=5 r=10** (chain 16384..1024, build a 1024 next to it; free caps in path order
  9,9,8,8,8,9,9,7,7,7,7 = cells 6,5 512, 4/8/9 256, 10/11 512, row 3 128): 2.98e10 states, ~60 GB in
  weights/endgame_lt/k5r10.lt. Play: `--endgame-lt FILE --lt-k 5 --lt-rank 10 --lt-caps ... --lt-min P` (used
  when p >= P and above the k>=6 tables' p; real boards with max tile <= 16384 only).
* 2026-10-03 **k=5 table works**: whole phase from 700 real starts, best_v2 + `--endgame-lt weights/endgame_lt/k5r10.lt
  --lt-k 5 --lt-rank 10 --lt-caps 9,9,8,8,8,9,9,7,7,7,7 --lt-min 0.5`: **60.1%** (58.0 without; table plays 1.2% of moves;
  deaths at 31744-32768 90 -> 79, collapse 60 -> 55); lt-min 0.3: 59.0. (Runs logged as PARTIAL used the table before
  its layers below sum 448 existed -> ignore.) Real positions with the chain: P ~ 0.7-0.8. The table is matched on the
  REAL board (play: lt_shape) for any chain from the max tile ending at 1024 at path cell 4 with at most one missing rank,
  e.g. [32768 8192 4096 2048 1024] in the 32768 phase (the root view would distort it).
  Solver resume: `layered ... --resume T` (layers above T complete in the file; verified byte-identical).
  Building k5r9 (caps 8,8,7,7,7,8,8,7,7,7,7; 1.38e10 states, 27.5 GB): first half's 8192/4096 builds ([16384 4096 2048
  1024 512], [16384 8192 2048 1024 512]) and the early game's [8192 4096 2048 1024 512]. Play takes several tables:
  repeat `--endgame-lt F --lt-k K --lt-rank R --lt-caps C` groups.
* 32768-phase test (new): weights/pool32k.bin = 1878 boards at the moment the 32768 formed (benchmarks best_v2,
  v11c_e4, v11c, m1q_eg); play 500 of them to game over (scripts/exp_queue4.sh p32). Ours: games reaching 32768 average
  699k and reach final sum >= 57344 in 36%; macroxue's: 796k and 74% -> the 32768 phase decides the average score.
* Whole phase, 700 real starts (results/expq3): k5 + leaf view 59.9; **vb3** (5-stage `weights/expsplit/b3_play.w`, stages
  `sum:20480/14,24576,28672,36864`, depths 3,4,4,4,4, leaf view < 24576) 61.0; **k5vb3** (+ k5r10) **61.7%** = best.
  Deaths (of 700) best_v2 / k5vb3: <24576 43/23, 24576-28672 49/50, 28672-30720 37/22, 30720-31744 15/25,
  31744-32768 90/92, >=32768 60/56. First half at depth 5 (best_v2): 57.3% (first-half deaths 92 -> 82, second half
  worse; 6x slower) -> rejected, our first half does not gain from depth like macroxue's heuristic does.
* k5r9 solved (27.5 GB, validated). CPU trainer (`build/train`) now takes `--endgame-lt` groups too (policy plays the
  layered table's move when p >= --lt-min and above the k>=6 tables'). Queued: scripts/exp_queue6.sh (both tables,
  best_v3 1000-game benchmark, 32768-phase tests, second-half seeds s2/s5/s6/s7 and stage-B seeds in the best config,
  budgeted deepening, early game with k5r9), then scripts/exp_cpuk5.sh (second half trained with k5r10 in the loop).
  GPU: scripts/exp_seqgpu.sh (second half with 2048 games in flight to 12M: does the over-training decline shrink?).
* **BUG (fixed 2026-10-03 22:00) in the layered-table move mapping** (lt::suggest): the table's afterstate carries the
  table's own chain ranks, so it was compared with the real afterstate as whole boards -> no match unless the real chain
  IS the canonical chain. Effect: k5r10 worked only for [16384 8192 4096 2048 1024] (all 16384-phase results above are
  valid), never in the 32768 phase; k5r9 never played (k5both_vb3 = k5vb3 exactly, 61.71%). Fixed: compare free cells +
  the real chain unmoved. The best_v3 1000-game benchmark ran with the old binary (= k5r10 in the 16384 phase only).
  k5r9 on real first-half positions ([16384 4096 2048 1024 512] etc., 145k positions in 200 games): P ~ 0.97-0.99.
* **best_v3 1000 games: 547,525 +- 6,475, 16384 95.4%, 32768 57.4%** (best_v2 524,809 / 94.9 / 52.7). Deaths of 1000
  (best_v2 -> best_v3): early 51 -> 46, cleanup 18 -> 6, 8192-build 45 -> 33, 4096-build 68 -> 65, 28672-30720 43 -> 41,
  30720-31744 33 -> 40, 31744-32768 142 -> 124, collapse 73 -> 71. Games reaching 32768: avg 706k, sum >= 49152 67%,
  >= 57344 41% (macroxue 89% / 74%). Death boards in the 4096-build: long chains with the free rows clogged by small
  tiles, and 3/12 with the 16384 pushed out of its corner (lock only blocks it when another move exists).
* With the fixed mapping, k5r9 plays 3.9% of moves (P ~ 0.98 there) but changes nothing: whole phase 60.6% (k5r10 only
  61.7%; first-half deaths identical) -> it takes over positions the network already wins and ignores the board it
  leaves behind. Keep k5r9 out of the 16384 phase (early-game test pending).
* 32768-phase test (500 positions at the 32768's formation -> game over; score gained / sum >= 49152 / >= 57344):
  base 255,966 / 65.8% / 43.2%; + k5 tables (real-board match) 257,366 / 68.2 / 43.6; + k6 tables matched on the real
  board (--endgame-real) 213,977 / 48.0 / 24.8 = much worse: during each build the real chain has a structural gap at
  the top (e.g. [32768 16384 _ 4096 ...]) which uses up full=2's single allowed gap; the root view lowers the top tiles
  and absorbs it. -> keep view matching for k6; `--lt-view` (layered tables on the view) being tested.
* 32768-phase part B as a real-board network (scripts/exp_p32b.sh; pool = pool2mix relabeled one rank up =
  weights/pool32C.bin, [32768 16384 + small] at sum 53248; play with 7 stages and `--root-downgrade-skip 49152 57344`):
  trained (e4 stage exit 52.6%), evaluation queued. Part C (scripts/exp_p32c.sh) training.
* `--lt-view` (layered tables matched on the root view, only differs in the 32768 phase): 32768-phase test 264,682 /
  69.4% / 48.0% (+ first 65536 in that test) vs real-board match 257,366 / 68.2 / 43.6 -> adopt --lt-view.
* Rejected: heuristic shaping at play time (leaf = network + w * nneonneo heuristic): w 0.05 59.3%, w 0.2 44.4% (vs
  60.6%); it wrecks the first half (s0cpu-view leaves) and helps the second half only within noise.
* 32768-phase real-board networks: part C (scripts/exp_p32c.sh: pool = second-half positions when the 4096 appears,
  relabeled, weights/pool32D.bin; e4 stage exit 57.5%) and part D (scripts/exp_p32d.sh: [61440, 65536), the 2048 build +
  collapse into 65536; pool weights/pool32E.bin). Helpers moved to scripts/: relabel_pool.py, pool_at_32768.py,
  death_boards.py, chain_conversion.py, count_states.py.
* Rejected: a gradient line heuristic (macroxue-style evaluation, reimplemented: `play --gradient MODE MINRANK MAXSUM
  DEPTH PROBCUT`, root-switched searcher) for the first half: from 700 real starts to 28672, plain rows d6 28.6%, d4
  7.1%, snake rows 0% (network ~87%). Their heuristic fits their gradient/PDF block, not our snake positions.
* Rejected for now: 32768-phase part D as a network (exp_p32d: [32768 16384 8192 4096] + build the 2048 -> 65536):
  stage exit 0% at 4M (episodes die fast; macroxue completes it in ~4% of its 32768 games).
* Second-half seed s2 in the best config (both tables): 62.3% vs e4 60.6% (also 59.3 vs 58.0 before) -> candidate.
* Second-half seeds in the best config (both tables, whole phase, 700 real starts): e4 60.6, s2 62.3, s5 62.7, **s6 63.0**,
  s7 61.4 -> e4 was the weakest; best_v4 candidate = `weights/best_v4.w` (b3 player with stage 3 = weights/expseed/s6.w).
* 32768 phase: the --lt-view gain came from k5r9 (plays ~7.6% of 32768-phase moves through the view: 264,682 / 69.4 /
  48.0 with both tables vs 257,424 / 68.2 / 43.6 with k5r10 alone, view or real). Per-table rank range: `--lt-ranks LO HI`
  after an --endgame-lt group (largest real tile rank). best_v4 uses k5r9 only with a 32768 (`--lt-ranks 15 15`).
* Many-stage players (7-8 stages, 1.9-2.2 GB quantized) + tables need `ulimit -v 6800000` and `MALLOC_ARENA_MAX=2`
  (5 GB virtual -> std::bad_alloc). The quantized loader already streams.
* Stage-B seeds (with e4, both tables): b3 60.6, b3s2 61.9, b4s2 62.1, b3s3 60.7, b4s3 62.0. best_v4 (b3 + s6, k5r9 only
  with a 32768, --lt-view) whole phase 60.9% vs b3 + s6 with k5r9 everywhere 63.0%; with e4 the k5r9 sign was opposite
  (60.6 on vs 61.7 off) -> **these 1-2 point differences are noise** (700 starts = +-1.85 each). Decide by 1000-game
  benchmarks (+-1.56 on the 32768 rate) or 2886-start tests (+-0.9); only accumulated changes are measurable.
  best_v5 = weights/best_v5.w (b4s2 + s6), k5r9 everywhere + --lt-view; benchmarks of v4 and v5 queued.
* **Rejected: real-board networks for the 32768 phase's parts B/C** (relabeled pools): part B with play_e4 = 0.4% reach
  57344 (view: 44.6%); B+C same. Trained only on relabeled pool positions (4M episodes, OI), it meets real part-B boards
  whose features were never visited (optimistic 5000/weight) and the search chases them. Would need pools of real
  positions. 32768-phase test best_v4: 260,924 / 68.8 / 44.6 / 27.4% (sums 49152 / 57344 / 61440).
* **best_v4 1000 games: 549,281 +- 6,532, 95.4% / 57.6% / 65536 0.1%** (first benchmark 65536, max 1,353,404) = best_v3
  within noise: the s6 second half and --lt-view made no measurable difference in full games.
* **Over-training is NOT caused by batch averaging**: second half with 2048 games in flight (c ~ 2 instead of 4-6), as v11c's
  second half on 600 real positions d3/d4: 4M 18.5/9.8, 8M 11.5/2.2, 12M 3.0/0.2 (32768 games: 58.0/60.5, 52.8/45.2,
  ~48/37) -> far worse and degrading faster. Testing 65536 games in flight (scripts/exp_bigbatch.sh).
* Early game: k5r9 never applies (0.01% of moves; the early network's formation is not a strict snake): 95.71% reach
  16384 with or without it (1400 games from scratch, best_v5 config).
* Real-position pools from benchmark records: `scripts/pool_from_records.py OUT LO HI STEP REQRANK DIRS` ->
  weights/pool2_real3k.bin (40.7k second-half positions from best_v3/v4/v5 games), weights/poolB_real3k.bin (stage B);
  second halves trained on them: scripts/exp_realpool.sh, evaluated in exp_queue8.
* **Budgeted deepening in the second half helps**: `--stage-depth 3,4,4,8,4 --min-depth 4 --budget 20000` (iterative
  deepening from 4 while the predicted leaf count stays under 20000; tight boards go deeper) on the b3+e4 config with both
  tables: **63.7%** vs 60.6% at fixed depth 4 (2.3 vs 0.85 ms/move, avg depth 4.2); deaths 30720-31744 18 -> 10,
  31744-32768 97 -> 80. Queued: budget 60k, budget also in stage B, and best_v5 + budget 1000-game benchmark (best_v5b).
* TD-decay second half (plain TD, alpha 1.0/0.3/0.1/0.03): 1-ply stage exit 14.9 / 31.1 / 37.3 / 36.5% at 4/8/12/20M
  (TC: ~47% at 12M) -> plateaus lower; search evals in exp_queue8.
* Rejected: second half trained with the 2-ply policy on all moves from scratch (exp_2ply), best_v2 config whole phase:
  2M 50.1, 3M 53.9, 4M 56.9% (1-ply-trained 4M: 58.0).
* Budget 60k in the second half: 63.0% (20k: 63.7%) -> 20k is enough.
* **Budgeted deepening in stage B too** (`--stage-depth 3,4,8,8,4 --min-depth 4 --budget 20000`): 64.7% (second half only
  63.7, fixed d4 60.6); 4096-build deaths 50 -> 35; 4.0 ms/move. Benchmarks best_v5b (budget 2nd half) and best_v5bb
  (budget B + 2nd half) queued in exp_queue7.
* Rejected: 65536 games in flight (second half): 0% stage exit at 4M and 8M (twice the averaging -> half the updates per
  weight; the optimistic net never takes off). With 2048 games it learns but is far worse -> 32768 is the sweet spot.
* GPU early-game network (zero init, scripts/exp_early_gpu.sh, snapshots 4/8/12M) training as an s0cpu alternative.
* best_v5b (best_v5 + `--stage-depth 3,4,4,8,4 --min-depth 4 --budget 20000`) 1000 games: 558,272 +- 6,546, 95.4 / 60.2%
  (best_v5 552,742 / 59.8). Same seeds -> identical games until the second half, so this is ~paired: +4 games of ~870
  entering it; the whole-phase test's +3.1 points was mostly noise.
* best_v5bb (budget in stage B + second half, 3.3 ms/move) 1000 games: 1000 games  mean 559754 +- 6552  median 621204  max 840312  min 13600; reached  32768:  59.80% +- 1.55  (598) -> same as best_v5b within noise.
* Results 2026-10-04 morning (whole phase, 700 real starts unless noted):
  - Rejected: plain TD with decaying rate (exp_tddecay, 4/8/12M as v11c's second half, 600 positions d3/d4): 24.2/18.3,
    24.0/10.5, 22.8/11.5 (TC 4M: 58.0/60.5) -> far worse under search.
  - Rejected: second half trained on the CPU with k5r10 in the loop (exp_cpuk5): 61.4% vs 61.3% without (same recipe).
  - best_v5 config whole phase 64.1% (1.24 ms/move); stage 1 (s0cpu-view 8192 build) at depth 5: 62.6% -> no gain.
  - Early game depth 4 instead of 3: 95.50% vs 95.71% reach 16384 (1400 games) -> no gain.
  - Budgeted deepening in every stage from depth 3 (budall_20k): 64.6% vs 64.7% for stage B + second half only.
  - k6r10 table solved (weights/endgame_lt/k6r10.lt, 6.6 GB, caps 9,9,8,8,9,9,7,7,7,7): for the 65536 collapse
    [32768 16384 8192 4096 2048 1024] + build 1024; must be matched on the REAL board (needs a per-table real/view flag).
  - 32768-phase part B trained from real positions (exp_p32b_real: weights/exp32br/e4.w, stage exit 54.9%;
    7-stage player weights/exp32br/play_e4.w) - NOT yet evaluated.
* **PAUSED 2026-10-04 11:10** (all jobs stopped so the user can free space on C:, which hit 0 bytes; WSL will be shut
  down). Pending, in order of value:
  1. 32768-phase test of the real-pool part-B network: p32mem p32_v5 vs p32_v5_breal (exp_queue8.sh step 5; needs
     ulimit -v 6800000 and MALLOC_ARENA_MAX=2; use --root-downgrade-skip 49152 57344).
  2. Second halves trained from real positions (weights/exprp/real.w, mix.w) as stage 3 of best_v5 (exp_queue8 step 4).
  3. Probability-cut budget test (exp_queue8 step 6: budpc_20k vs bud_20k_ref).
  4. GPU early-game network snapshots weights/expearly/e4/e8/e12 (1-ply 16384 rate 68/74/73% vs s0cpu 83.5%) - likely
     weaker; evaluate the early game from scratch if worth it.
  5. k6r10 with real-board matching in the 32768 phase (65536 rate).
  Re-run a queue script to resume (they skip finished steps by their logs); check `df -h /` and `df -h /mnt/c` first.
* **RESUMED 2026-10-04 12:30** after the user compacted the WSL disk: C: 442 GB free, the WSL image is 235 GB and now
  SPARSE (space freed inside WSL returns to Windows automatically). New play option `--lt-real` (per table group:
  matched on the real board even with --lt-view; for k6r10). Queues: scripts/exp_queue9.sh (32768 phase: best_v5bb vs
  real-pool part B vs + k6r10; real-pool second halves; budget + prob cut; GPU early-game nets; tight-board 2-ply second
  halves) and GPU scripts/exp_tight2ply.sh (second half with 2-ply only when <= 4 / <= 3 empty cells).
* 32768-phase test (500 positions at the 32768's formation -> game over), best_v5bb settings: 269,148 / 71.6 / 49.2 /
  31.8% (sums 49152 / 57344 / 61440) = best so far for that phase (best_v4 260,924 / 68.8 / 44.6 / 27.4). Real-board part-B
  network trained on REAL positions (weights/exp32br/e4.w): 244,221 / 71.6 / 32.0 / 20.6 -> rejected again; the view with
  the 16384-phase networks plays part B better than a dedicated 4M-episode network.
* k6r10 (65536 collapse, real-board match via `--lt-real`, even with precedence over view tables): never plays - it
  matches, but P is ~0.0-0.07 for typical [32768 16384 8192 4096 2048 1024] positions (building a 1024 in 10 capped cells
  is very hard), below --lt-min 0.5. 46 of 598 32768-games reach that chain. Dead end with these caps.
* best_v5bb settings whole phase (700 real starts): 62.6% (best_v5 without budget: 64.1%) -> in the 16384 phase the budget
  is noise-level; its gain is in the 32768 phase (32768-phase test 269,148 / 71.6 / 49.2 vs 260,924 / 68.8 / 44.6).
* **Search-bootstrapped training ("distillation")**, new: `play --dump-train FILE LO HI` appends (root afterstate, searched
  value = expected future reward after depth-1 more expectimax plies with the tables) for every searched move whose
  afterstate tile sum is in [LO, HI); `build/distill --load IN.w --stage S --data FILES --out OUT.w --alpha A --epochs E`
  fits that stage by plain SGD. First run (exp_queue9 step 2b): data from best_v5 playing the whole phase from the held-out
  real starts 701-2886 (weights/pool16real_rest.bin), second-half afterstates only; s6 fitted with alpha 0.05 / 0.02 (1
  epoch) and 0.05 (2 epochs); evaluated as stage 3 of best_v5 on starts 1-700 (best_v5: 64.1%). If it helps: iterate.
* **Breakthrough hunt (2026-10-04 evening; user: 'time to look for breakthroughs').**
  - Expert iteration, round 1 (root afterstates only, 5.2M samples from best_v5 on held-out starts): fitting s6 to the
    searched values HURTS: alpha 0.05 -> 53.3%, 0.02 -> 54.7% (vs 64.1%). Diagnosis: searched values are systematically
    +8-15k (4-6%) above the network's in every sum bin (better policy + expectimax max-bias); fitting only the played
    states inflates them against the off-path positions the search compares. (Same mechanism likely behind greedy
    over-training.) Fixes under test (scripts/exp_queue10.sh): `distill --center 512` (remove the mean bias per tile-sum
    bin) and TreeStrap data (`play --dump-tree RATE`: also interior chance nodes of each search).
  - GPU depth-2 TreeStrap: `gpu_train --policy-depth 2 --train-all-root` (every candidate move's afterstate trained
    toward its 2-ply backup): scripts/exp_allroot.sh (e4 fine-tune +1M; from scratch 4M with 2-ply on <= 6 empty).
  - Monte Carlo playouts for close decisions: `play --rollouts N H CLOSE MINSTAGE` (when the search's best two root values
    differ by < CLOSE*|best| in stage >= MINSTAGE, re-rank the close moves by N greedy playouts of H moves + value at the
    end; separate RNG stream so games stay paired).
  - Centered root-only fit: 52.9%; TreeStrap round 1 (28M samples: root + ~5% interior chance nodes, centered, alpha
    0.02): 53.1% -> search-bootstrapped fitting in any of these forms degrades the network (vs 64.1%). Interior targets
    are biased even more (+10-18k). Likely the Q-learning-style overestimation loop: each max selects leaves the network
    overvalues, fitting to those backups entrenches the errors.
  - Optimism measured (e4.ckpt): 59% of the second half's weights never updated (still 5000/feature = optimistic), 88%
    with |error| sum <= 1e6 (mean w 4689); well-trained weights average ~1400 (median 2300) -> a position made of
    unvisited features is valued ~320k vs ~220k on the played path: the search is pulled toward the unexplored.
    `scripts/neutral_mean.py IN STAGE CKPT OUT MAX_A` sets barely-trained weights to their tuple's trained mean.
  - **Optimism refuted**: e4 with barely-trained weights set to their tuple mean (|error| sum <= 1e4: 60% of weights, <= 1e5:
    70%) plays IDENTICAL games to each other (62.29% d4, 63.57% d5) and one game off the original e4 (62.14% d4) -> the
    untouched optimistic weights are never consulted in real search trees (they belong to tile patterns that do not
    occur). Over-training damage has another cause. (Depth 5 in the second half: +1.3, only 2.0 ms/move.)
  - **Outcome predictability (diagnostic)**: 38k second-half positions (sum 28672-32768) from best_v5bb games, every 40th
    move: the network's 1-ply value predicts "this game reaches 32768" with AUC 0.54 only (base rate 0.73); empty cells,
    distinct small tiles, tiny tiles, chain length, max free tile: AUC ~0.50-0.54, adding them to the value: 0.54. Positions
    on the played path look alike in their eventual success; outcomes are decided by future spawns and many small
    decisions -> gains must come from slightly better local decisions everywhere (what depth gives macroxue), and long
    playouts will be dominated by outcome noise.
  - Rejected: Monte Carlo playouts for close decisions (32 playouts x 200 moves, close < 0.5%): 47.1% vs 64.1%; 18.8% of
    moves were checked and 541k overridden: the playout estimates are dominated by outcome noise (see AUC 0.54).
  - GPU depth-2 TreeStrap from scratch (all-root on <= 6 empty): 8% stage exit at 4M (barely learns); e4 + 1M all-root
    fine-tune evaluation queued.
  - New: value-based forward pruning `play --vprune F` (interior chance nodes whose afterstate value is below F x the
    root's best afterstate value become leaves, so the budget deepens plausible lines; macroxue's "pass score" idea with
    the network). Tests vp90 / vp95 / vp95 with budget 60k queued in exp_queue10.
  - Rejected: value-based forward pruning (stage B + second half, budget 20k, max depth 8): vp90 60.1%, vp95 58.1% (avg
    depth 5.0 vs 4.4; same budget without pruning 62.6%) -> deeper effective search does not fix the network's errors.
    Budget + probability cut 0.0005: 60.1%.
  - Heuristic-only engine in our framework (macroxue-style line heuristic, fixed top-left corner, 4 levels, prob cut
    1/128, no tables, from scratch): most games end at 4096-8192. Their strength comes from tables + plans that apply
    to any "regular" corner block (tuple10/tuple11 in their tuple.h: 5-6 fixed top-left cells of ANY ranks, 10-11 free
    cells, exact P of reaching the next anchor tile, used at the root whenever P > 0.1), not from the heuristic alone.
  - Re-read of macroxue's numbers: at 4 levels (their depth 3, big tables) they convert 16384->32768 at 64.5% (= ours
    at 4.4 levels, 62.7%); one more level gives them 76.1% (their depth 4, 0.5 ms/move), 8 levels 81.6%. Guei et al.'s
    network (no tables, no lock, 2 stages, 100M episodes per stage) converts at 68.9% with 3 move levels and 72.9% at
    6-ply -> **their networks are better than ours and still gain from depth**; ours stop gaining after ~4 levels and
    lose search strength when trained past ~4M episodes. Training quality/volume is the lead to follow.
  - exp_cpulong2 (CPU, 2026-10-04 21:00): the CPU trainer runs the second half at ~5.9M moves/s (4M episodes in 27 min,
    5x the GPU's speed with tables in the loop) -> Guei-scale training (100M episodes) would take ~12 h per stage.
    Continue the CPU 4M second half to 6/8/12/16/24M, each evaluated as v11c's second half on pool600 (seed 31) at
    d3/d4 (GPU snapshots: 4M 58.0/60.5, 6M 56.5/52.2, 8M 52.8/45.2). CPU c4: 56.2 / 59.5.
  - **The over-training damage is a GPU-trainer artifact**: CPU snapshots d3/d4: c4 56.2/59.5, c6 57.5/58.0, c8 57.8/59.8
    (GPU 8M: 52.8/45.2). But the CPU network also stops improving (1-ply in-training 32768 rate 54.1 -> 54.7 -> 54.8%):
    TC has converged. c12 57.8/58.3 (1-ply 55.4%): flat; stopped there. Guei-style OTD (decaying TD rate, TC only at the
    end) queued as scripts/exp_otd.sh, after an annealing test (c12 + plain TD alpha 0.001 / 0.01 for 4M: is the plateau
    noise-limited?) and a depth-scaling diagnostic without tables (scripts/exp_queue11.sh, results/expq11/eval.log).
  - GPU `--tc-mean` (TC accumulators take each round's mean error, consistent with the mean step; hypothesis: summed
    accumulators anneal common weights' rates while they move c x less -> frozen under-trained): takes off ~0.5M episodes
    later, 1-ply stage exit 43.4% at 4M, 47.5% at 8M (standard: 46.0% at 4M). **Rejected**: d3/d4 g4 57.3/57.2, g6
    57.7/58.0, g8 54.2/54.8, g12 52.2/44.7 -> degrades like the standard GPU trainer. The TC accounting is not the cause;
    the batched/synchronous GPU regime itself is. Use the GPU only for <= 4M-episode recipe tests, the CPU for long runs.
  - GPU lambda tests (s6 recipe, seed 6, 4M): lambda 0.8 / horizon 8 learns much faster early (stage exit 36% at 1.5M vs
    6%) but ends lower at 1-ply (38.3% vs 46.0%); lambda 0.95 / horizon 16: peaks at 17.9% (2.5M) then declines (15.3%
    at 4M) -> higher lambda is worse at 1-ply. **Rejected**: whole phase as stage 3 of best_v5: l80 40.7%, l95 1.4% (s6
    64.1%) -> more Monte-Carlo-like targets wreck search strength; lambda 0.5 / horizon 3 stays.
  - Annealing: c12 + plain TD alpha 0.001 for 4M (TD mode 7.2M moves/s): d3/d4 57.5/57.2 (c12 57.8/58.3) -> the plateau is
    not noise-limited (consistent with the ensemble result: systematic errors). c12 + TD 0.01 for 4M: 58.5/60.3 (1-ply
    in-training 53.8% vs 55.4%) -> +2 at d4, at the noise edge; moving toward TD's fixed point may help search a little.
  - Calibration (`train --lt-calib`, c12, no k6 tables, 3000 episodes): 1188 k5r10 handovers, mean P 0.68, MC return from
    the handover ~ 200,828 + 131,872 * P. Note: without the k6 tables in the loop c12's in-training 32768 rate is 28% (55%
    with them) -> the network leans heavily on the tables in the final phase.
  - **Handover quality hardly varies**: 3141 first-k5r10 states (c12, 8000 episodes): P at handover is in [0.6, 0.8) for
    94% of them (mean 0.68); success (return > 100k) by P decile 0.64 / 0.68 / 0.71 for P 0.5-0.6 / 0.6-0.7 / 0.7-0.8;
    corr(P, return) 0.034, corr(network value before handover, return) 0.018. The configuration at handover is nearly
    always the same quality -> better pre-handover play cannot raise P much; the final phase (~25% of games reaching it
    die) is limited by the sub-game itself (a 1024 must be built exactly in a goal cell of a cramped 11-cell region), i.e.
    by the formation. Pre-handover deaths (sum < 31744): 110 of 700 whole-phase games (15.7%); after: 141 (20%: 81 at
    31744-32768, 60 with sum >= 32768 but no 32768 tile).
  - Rejected: **free ensembles** (n-tuple nets are linear in their weights, so averaging same-recipe seeds' weights =
    the mean of their values at no extra cost; scripts/avg_stages.py [--skip-value 5000]): second half = mean of s6, s2,
    s5, e4 as stage 3 of best_v5: 63.29% (also when weights still at 5000 are left out of each average: 63.29%, same
    games) vs s6 alone 64.1%. 34% of weights are trained in all 4 seeds, 52% in none. The seeds' errors are shared
    (systematic), not training noise -> no gain from averaging; seed farm (scripts/exp_seedfarm.sh) stopped.
  - New: **side-branch training** (`train --branch P L`, CPU): with probability P per step, train a branch that starts at
    a random non-chosen candidate afterstate and follows L greedy moves, by its own backward TD(lambda) sweep (bootstrapped
    from the policy's next value); the episode itself stays greedy. Trains the off-policy positions a search compares
    with on-policy targets (no max-bias, unlike TreeStrap/distillation; unlike exploration it does not derail episodes).
    Default off = identical training to before. Test br10 (P 0.1, L 8, second half as CPU c4) in exp_queue12.
    Also in gpu_train (`--branch P L`, device helper greedy_choice; 4.5M main moves/s instead of 14M): gbr10 = s6 recipe
    + branches (seed 6). Bug found and fixed on the way: the batched-gradient `touched` list was sized for <= 2 updates per
    game-step, branches overflowed it (now sized for them, and excess first-touches are dropped). Even fixed, the GPU run
    never takes off from OI (0% stage exit at 2.5M; the s6 run takes off at 1.5M) - branch targets bootstrapped from
    still-optimistic values cancel the main trajectory's decrease in the batched mean. Stopped; the CPU br10 learns
    normally (32768 rate 46.3% at 1M).
  - **Rejected: side-branch training** (CPU br10, P 0.1, L 8, otherwise c4's recipe): 1-ply in-training 48.5% at 4M (c4
    54.1%); v11c protocol d3/d4 53.3/59.0 (c4 56.2/59.5) -> training the off-policy alternatives does not make the network a
    better leaf evaluator. In the full player (whole phase, stage 3 of best_v5) however: br10 64.43% vs the same recipe
    without branches (CPU c4) 61.71% and s6 64.14% (paired; the difference is in the final phase, 20.7 vs 23.6 deaths)
    -> +2.7 over its own baseline, ~1 sigma; not established. (CPU c4 in the full player is 2.4 below the GPU s6.)
  - Queue (results/expq11, results/expq12): annealing c12 + TD 0.001/0.01 -> depth scaling without tables (d1-d4) ->
    br10, CPU c4 in best_v5, tight-2-ply m4/m3, lambda l80/l95, --lt-min 0.05 -> OTD (24M) -> c8/c12 in best_v5.
  - **KEY COMPARISON: where macroxue loses its 16384-phase games** (their outputs/2048b.d*, final boards with max 16384,
    binned by tile sum, % of all 1000 games):
    | sum at death | <24576 | 24576-28672 | 28672-30720 | 30720-31744 | 31744-32768 | >=32768 (no 32768) |
    |---|---|---|---|---|---|---|
    | macroxue d3 | 8.2 | 6.0 | 2.9 | 1.8 | 4.6 | 5.4 |
    | macroxue d5 | 2.5 | 1.0 | 1.3 | 1.0 | 7.3 | 7.7 |
    | macroxue d8 | 0.4 | 0.6 | 1.1 | 0.7 | 7.6 | 7.8 |
    | ours (best_v5 whole phase, 700 starts at the 16384) | 3.3 | 6.6 | 4.1 | 1.7 | 11.6 | 8.6 |
    -> **the gap is the build-up before the final 1024 (sum < 31744): we lose 15.7%, they lose 2.8% at d8 (5.8% at d5)**;
    the final phase is comparable (they lose 15.4%, we 20.2%). Their deep heuristic search almost never dies while
    building the 8192/4096/2048 into the formation; ours dies there like their depth 3 does (18.9%). Stage B (4096 build)
    is the worst: 6.6% vs 1.0%/0.6%. The lever is play quality in the build-up (search depth/evaluation), not endgame tables.
  - **RAW NETWORK QUALITY (depth scaling without tables, best_v5 networks, lock + root downgrade + leaf view kept, whole
    phase from 700 real 16384 formations)**: d1 3.4%, d2 11.0%, d3 19.4%, d4 23.9% (Guei et al.'s table-free network converts
    35.4 / 59.8 / 68.9% at 1/2/3 move levels; ours with tables at d4: 64.1%). Deaths at d1: <24576 19.6, stage B 25.9,
    28672-30720 19.1, 30720-31744 11.7, final 20.3 (86% of the games reaching 31744 die there without the tables). Our
    late networks are table players: trained with the k>=6 tables in the loop (which cover most proper-snake positions
    of stage B and the second half), they never learned those positions, and they are weak in every sub-phase alone.
    Guei's networks learned everything. At d4, deaths without / with tables: <24576 3.4 / 3.3, stage B 9.4 / 6.6,
    28672-30720 14.3 / 4.1, 30720-31744 11.9 / 1.7, final 37.1 / 20.1 -> the k>=6 tables carry 28672-31744; the first half
    and stage B are mostly network play (and are where macroxue d5 loses only 2.5 / 1.0).
    -> test table-free training (CPU and GPU, queue12) and Guei's OTD table-free
    (exp_otd.sh changed to train without tables; evaluated raw and in the full player).
  - Rejected: second half trained with the 2-ply policy in tight positions (exp_tight2ply, GPU 4M, seed 6 like s6):
    2-ply when <= 4 empty: 55.4% whole phase vs s6 64.1%; when <= 3 empty: 60.3% (28672-30720 deaths 11.1 / 5.4 vs 4.1).
  - GPU table-free second half (s6 recipe minus tables): takes off later (stage exit 0% at 2M, 26% at 4M, 34% at 6M,
    1-ply without tables; in-training 32768 rate 38.5% vs ~28% for table-trained c12 played without k6 tables); 8M 34.8%,
    12M 35.1% (plateau). Table-free stage B on the GPU (exp_gntb.sh, bootstrapping from g8nt): 1-ply stage exit (no tables)
    b4nt 71.6, b6nt 77.9, b8nt 80.1%; seed 3: bx8nt 79.6, bx12nt 80.4, bx16nt 80.7% (table-trained b4s2: 83.0% with tables;
    the table-trained stage B without tables at d1 succeeds ~68%).
  - CPU table-free second half from OI (n4) did NOT take off in 4M episodes (avg 20k, 32768 0.1%; the GPU run took off at
    ~3M): without tables the OI network must learn the final phase itself before episodes reach the boundary bonus.
  - GPU table-free whole-phase network (exp_whole_nt.sh, from the 16384 formation to view sum 36864): 0% stage exit at 4M
    (episodes long, avg 100k, but no 32768 yet); 8M still 0% -> stopped: without tables (and without a boundary close by)
    the OI network never discovers the final collapse. CPU n8 (n4 + 4M): 4.4% 32768 in training - too weak to test.
  - Instead: table-free FINE-TUNING of table-trained networks (CPU c12.ckpt + 4M without tables = c12nt; GPU e4.ckpt + 2M /
    4M = e4nt2 / e4nt4), evaluated raw (notab d2) and in the full player (queue12). **CPU c12nt collapsed** (in training
    avg 10k / 210 moves from the first 1M on; notab d2 0%, full player 0%): sequential TC updates from the network's
    table-less failures wreck it. The GPU fine-tune does not collapse (e4nt2 at 1M: 1-ply stage exit 30.8% without tables).
  - **Raw quality does not carry over to the full player**: GPU table-free g8nt as stage 3 of best_v5: no tables at d2
    29.9% (s6 11.0%; second-half deaths 28672-30720 9.7 vs 14.6, 30720-31744 4.6 vs 11.1, final 27.1 vs 34.6), but in the
    full player (tables, d4) 61.6% vs 64.1%. The table-trained network is adapted to table-assisted play; a better
    stand-alone network loses there. CPU n8 (barely took off): no tables d2 5.7%, full player 15.4%.
    g12nt (GPU damage past 8M): no tables d2 22.3%, full player 59.0%.
  - The k5r10 caps never bind (scripts/k5_capbind.py on best_v5bb's 1000 games): of 357,798 positions after a game's first
    k5r10 match, 96.3% are table positions, 3.5% have no chain match (mostly the collapse after a win), 0.17% exceed a cap
    and those are all the goal itself (1024 in goal cell 6). Relaxed-cap tables would not help; the final phase is played
    table-optimally and its ~70% success is set by the formation. Macroxue's final-phase deaths look the same as ours (top
    two rows full of big tiles, bottom rows clogged building the last 64/128) but their top rows are column pairs
    ([16384 8192 1024 256 / 4096 2048 512 128]), ours a snake ([16384 8192 4096 2048 / 128 256 512 1024]).
  - Layered-table threshold: --lt-min 0.05 60.0% (final-phase deaths 24.1 vs 20.1), 0.8 63.4%, 0.5 (current) 64.1% -> keep
    0.5; below P 0.5 the network's search beats the table's sub-game-optimal move (it can leave the sub-game).
  - Build-up deaths are formation breaks, not table failures (scripts/death_structure.py LO HI, best_v5bb 1000 games):
    stage B (24576-28672) 54 deaths: max tile in its corner in 53, but a snake chain >= 6 (table territory) in only 5;
    chains of 1-4 cells in 47 (the snake breaks at its turn into the second row) with 5-9 tiles <= 8 on the board.
    28672-31744: 59 deaths, chain >= 6 in 21, chain 3-4 in 27. The network fails to keep the snake ordered while building
    the next big tile; macroxue's deep search rarely does (stage B 1.0% at d5).
  - Rejected: deep search in stage B (`--stage-depth 3,4,8,4,4 --min-depth 5 --budget 200000`, 12.5 ms/move): stopped after
    209 paired games: stage-B deaths 15 vs 11 (ref), successes 127 vs 129. Unlike macroxue's heuristic (build-up deaths
    18.9% -> 5.8% from depth 3 to 5), our network's build-up play does not improve with depth (also without tables: d3
    38.6% vs d4 39.0% build-up deaths) -> its errors there are systematic: it overvalues positions that are heading for a
    broken snake. Next: a pessimistic snake-order leaf penalty (`play --snake-pen W K LO HI`, macroxue's inversion penalty
    T(r) = r * 2^r along our snake path; w 1/4/16 on view sums 24576-31744 in queue12). **Rejected**: w 1: 61.7% (stage B
    deaths 7.7 vs 6.6) - the crude penalty also punishes healthy build-up shapes (holes where the next tile grows).
  - Rejected: early game with lock 13 (s0cpu GPU-fine-tuned with lock 13 + k>=6 tables, +1M/+2M): reach 16384 91.5% /
    92.1% vs 95.71% (best_v5, 1400 games from scratch).
  - Cleanup 2026-10-05 02:20: deleted tonight's rejected weights (weights/explam, exptm, expens: 11 GB).
  - k5r10 P for hand-made handovers (`build/layered ... --query`): nearly empty free region (one 2) 0.47; two 2s 0.58;
    a 512 next to the chain end 0.48; 512 + row [256 128 64 32] 0.66; full sub-snake 512..2 0.25. Our real handovers
    (P 0.6-0.8, mean 0.68) are already good: building a 1024 into this goal from 11 cells is inherently ~50-70%. The
    snake's safe moves (up always, right always, left only with cell 6 occupied) push tiles toward the goal cell, so the
    goal placement is natural; relaxing caps would not change much. Macroxue's final phase (84%) uses a different 2-D
    plan structure (LinePlan builds row 2 left->right under row 1, BlockPlan/tuple tables with anchor+pair goals).
  - **Night of 2026-10-04/05, summary so far**: no new best player. Established: (1) GPU over-training damage is a GPU-
    trainer artifact, CPU TC plateaus at ~4M; (2) the gap to macroxue is the build-up (15.7% vs 2.8% deaths, formation
    breaks in network-played positions, not fixed by depth/penalties) plus a final phase that is ~70% inherently in our
    snake sub-game (theirs ~84% via 2-D plans); (3) our late networks are table players: table-free networks are far
    better alone (d2 no tables 29.9 vs 11.0%) but worse in the full player (61.6 vs 64.1%). Rejected: ensembles, TD
    annealing, lambda > 0.5, tight 2-ply, forward pruning, deep stage B, snake penalty, early lock, table thresholds,
    table-free / whole-phase training, CPU table-free fine-tuning (collapses); side branches ~neutral (64.4 vs s6 64.1).
  - Cross-check: k5r10 P of [16384 8192 4096 2048 / 128 256 512 1024] + a 2 at (2,0) (= the last step, build a 128 in the
    two free rows) is 0.7818 = macroxue's snake8 number (78.2%) exactly; their PDF (2x3 block + 2 tiles in row 3, L-shaped
    free region) gets 81.2% for that step. ~3 points per step compounding over the 3-4 steps of the final phase would explain
    most of our ~70% vs their ~84% final phase, and more in the 32768 phase (65536 step: PDF 17.3% vs snake 12.5%).
    -> The formation (PDF instead of snake) is the identified structural lever for the endgame; a switch means new tables
    (generalized fixed-cell layered DP with anchor goals), a block lock and retrained late networks (multi-day project).
  - Early deaths (best_v5bb, 46 of 1000 before the 16384): 30 at max 8192 with sum >= 14336 (the 16384's final build) -
    s0cpu often builds the second row in the gradient direction ([1024 2048 4096 8192 / 16 64 256 512]: row 2's big end
    under row 1's big end), which cannot collapse into the 8192; so k5r9 rarely applies in the early game.
  - New `build/layered --path c0,...,c15` (chain order of the cells; default the 4-wide snake). A 3-wide snake with column 3
    as a free buffer (0,1,2,6,5,4,8,9,10,14,13,12,15,11,7,3 - my first reading of macroxue's PDF) is much WORSE for the last
    step (k8r7, build a 128 in 8 cells): mean P 0.13-0.47 vs 0.78 for our snake (the chain rows with a free column-3 cell
    forbid right moves). Their PDF is not a plain path: column pairs ([16384 4096 1024 / 8192 2048 512 / 256 128]) whose
    merges need repositioning moves handled by their plans. Replicating it is a research project of its own.
    (Worked-out collapse of [16384 4096 1024 / 8192 2048 512 / 256 128 . .]: 128 at (2,2) -> left x2 -> 512 at (2,0);
    right (blocked at (2,3)) -> 512 at (2,2) -> up -> 1024 at (1,2) -> up -> 2048 at (0,2) -> down -> (1,2) -> left ->
    4096 at (1,1) -> up -> 8192 at (0,1) -> down -> (1,1) -> left -> 16384 at (1,0) -> up -> 32768: merges alternate
    vertical/horizontal inside the 2x3 block while the L-shaped free region (column 3 + bottom rows) absorbs spawns.)
  - OTD (exp_otd.sh, with tables, TD from OI): t12 (alpha 0.1, 12M): in-training 1-ply 32768 rate 43.4% (TC c12 ~55%);
    v11c protocol d3/d4 54.5/55.0 (TC c4 56.2/59.5); full player 61.0% (s6 64.1, CPU c4 61.7); no tables d2 9.7%.
    t18 (+6M at alpha 0.01): in-training 55.0% (= TC); v11c d3/d4 58.0/59.3 (c12 57.8/58.3); **full player 63.57%** (s6
    64.14, CPU TC c4 61.71) with second-half build-up deaths 28672-30720 2.4 vs 4.1; **no tables d2 17.6% (s6 11.0%)** ->
    the decaying TD schedule gives a better stand-alone network that is as good inside the full player (first recipe
    tonight that does not trade one for the other). t21 (+3M at 0.001): in-training 56.6% (TC plateau 55.4%), v11c d3/d4
    57.3/59.2, full player 63.29%, no tables d2 17.7% -> same as t18. TC segment (t24tc) next; 32768-phase test of t21
    queued (exp_p32otd.sh) - the view-played 32768 phase may profit more from better stand-alone play. t24tc (+3M TC with
    fresh accumulators) HURTS: in-training 47.2%, v11c 54.0/56.8, full player 59.9% (no tables d2 20.3%) - fresh TC rates
    (1.0) shake the annealed weights; no TC tail. **OTD verdict**: TD 0.1 -> 0.01 (-> 0.001) gives a second half equal to
    the best GPU seed in the full player (63.3-63.6 vs 64.1; the same-length CPU TC run c4: 61.7) with far better
    stand-alone play (no tables d2 17.7 vs 11.0) - the recipe to use for long CPU training; stage B next (exp_otdB.sh).
  - Queue: scripts/exp_queue14.sh (after queue11) = scripts/exp_otdB.sh (same schedule for stage B, 3-stage file, the
    second half to bootstrap from read from results/sh_for_stageB.txt, default s6) then scripts/exp_queue13.sh.
* **PAUSED 2026-10-05 ~06:40** (user shuts the laptop). All queues and jobs stopped; nothing is half-written except the
  interrupted logs listed here (they are redone on resume because they lack their summary line). Pending, in order:
  1. `scripts/exp_queue14.sh` = 32768-phase test of the OTD second half t21 (`scripts/exp_p32otd.sh t21`), then stage B with
     the TD schedule (`scripts/exp_otdB.sh $(cat results/sh_for_stageB.txt)`, default s6; switch the file to
     weights/expotd/t21.w if t21 wins the 32768-phase test), then `scripts/exp_queue13.sh` (table-free stage B with s6,
     c12 + TD 0.01 in the full player, lt-boot vs k5loop).
  2. `scripts/exp_queue15.sh` (TD annealing of the early-game network s0cpu + early test).
  (queue11 finished: CPU TC snapshots in the full player p5_c8 64.00%, p5_c12 62.86%, vs s6 64.14%.)
  Resume: `nohup scripts/exp_queue14.sh > results/expq14_run.out 2>&1 &` and `nohup scripts/exp_queue15.sh >
  results/expq15_run.out 2>&1 &` (queue15 waits for queue14; finished steps are skipped). Check `df -h / /mnt/c` first.
* NEXT after exp_snap1: build the best player = s0cpu + first half at its best length + e4 second half
  (stage depths per the snapshot tests), 280-game check then 1000-game benchmark.
* Ideas queued: `--train-all-root` (never tested: train every root move's afterstate toward its
  2-ply backup; may make nets robust to deeper search); network-valued DP (goal states valued by
  the network instead of 1) so tables also help partial collapses in the first half; hybrid
  table+network policy during training so the network learns to steer into table endings.
* **2026-10-06 WEEK 1 STARTED (new goal: analysis engine).** AWS quotas still CASE_OPENED (both) at 12:15. Human data:
  the other chat downloads expert YouTube games into ../2048-human-data (videos/, frames/ and out/ still empty) -> boards
  will come from video frames (expect gaps between frames; review mode must tolerate them).
  New code (all use the same engine as play; `src/engine.h` = EngineConfig/Engine/EngineThread, `preset_best` = the
  best_v5bb settings, `--preset best-notables` = same without tables (1.4 GB RAM instead of 3.6 GB)):
  - `build/analyze` (src/analyze.cpp): per-move values (points: reward + expected future reward, expectimax at the
    engine's own depth), loss vs best, the engine's move and what decided it (search / table / layered), table success
    probability per move where an exact table applies (k5 layered: `lt_move_values`; k>=6: Snake::after_value), plan
    text, reasons per move (src/explain.h: corner, chain, trapped small tiles, big tile in the middle, free cells,
    merges), `--risk D` spawn risk per move (share of new tiles costing > 5%, worst spawn), `--json`, `--stdin` (one
    board per line -> one JSON line; server mode), `--review FILE` (consecutive boards; moves inferred; match rate, mean
    loss, inaccuracies/mistakes/blunders by relative loss 0.5/2/5% - placeholder until calibrated units exist).
    Boards: 16 tile values in any separators, or 16 hex ranks. Load 17 s (weights + k6 tables), then 1-170 ms/position.
  - `build/messy` (src/messy.cpp): imperfect-policy games -> positions (pool .bin + .tsv with outcomes). Policies random,
    greedy, corner (beginner home-corner), heur, net (1-ply), engine; `:eps=` random moves, `:second=` second choice;
    phases "P1@LO-HI,P2" (switch at a random tile sum); `--record-switch` records the handover position (its outcome =
    the engine's outcome from a messy position); `--values` adds the engine's analysis. Beginner policies reach 128-512;
    1-ply net with 10% random moves dies at 128-512 (random moves are much more fatal than human mistakes).
  - `build/rollout` (src/rollout.cpp): rollout judge - per (position, move) K playouts (common random numbers across the
    moves) of up to H engine moves + the network value at the cut-off; ground truth for move quality on messy positions.
  - Portable build: `bb::pext_nib` / `bb::nth_bit` replace _pext_u64/_pdep_u64 when __BMI2__ is not defined (ARM, WASM,
    Zen 2 where PEXT is microcoded); `g++ -march=x86-64-v2` builds analyze fine.
  - Calibration pilot running: `scripts/calib_pilot.sh` (60 games each: clean engine games, net eps 3% / second 15% /
    beginner corner / greedy handing over to the engine at a random sum) -> results/calib/pilot_*.tsv;
    report: `scripts/calib_report.py results/calib/pilot_*.tsv`.
  - Engine speed inside messy: ~16 ms/move/thread with 16 threads (benchmark: 3.3 ms/move with 14 threads) - check why.
  - GOTCHA (cost 30 min today): `pgrep -f PATTERN` wait loops match the harness's `bash -c` wrapper of the command that
    launched them, because the wrapper's command line contains the whole command text (including the pattern inside a
    sed or the script name) and stays alive as the job's parent. Use done-files / pid files, or launch with
    `setsid nohup ... & disown`. Also: only ONE engine process with tables (3.7 GB) fits next to normal work in 7.7 GB;
    a concurrent analyze test got the pilot's process OOM-killed.
  - Pilot 1 lessons: noise policies die far earlier than expected (1-ply net + 3% random moves, or 15% second-best
    moves: max 64-1024; beginner corner/greedy die at sum ~300-600, so a handover at 300-1500 rarely happens). New policy
    `soft:t=T` (move chosen with probability ~ exp(-relative 1-ply loss / T)): t=0.03 reaches 512-2048, t=0.01 512-8192,
    t=0.003 mostly 4096-8192 within 6000 moves -> a realistic skill ladder. Pilot 2 (scripts/calib_pilot2.sh) uses it.
  - Calibration, clean engine games (60, matches the benchmark: 98.3% 16384, 55% 32768, 531k): the network's value is
    calibrated on average (future/value 0.98) but NOT per stage: future/value 1.31 / 1.26 / 0.95 / 0.54 at max tile
    4096 / 8192 / 16384 / 32768 (the value is the 1-ply training policy's expectation; in the 32768 phase the root view's
    16384-phase value is ~2x the real future) -> raw values cannot be shown as scores/odds; calibrate by stage.
  - Engine base odds from the 1000 best_v5bb benchmark games, P(reach T | alive at tile sum s): 16384 95.4% from the
    start (99.1% at s=16384), 32768 59.8% at the start, 63.1% at 20480, 69.5% at 28672, 72.6% at 30720.
  - Review mode: `infer_path` bridges up to --max-gap (3) moves between frames (paths scored by spawn values 0.9/0.1;
    tile-sum pruning); fixed parse_board treating "0 0 0 2 ..." as hex. A 300-move game: all frames understood; every
    2nd frame dropped -> 310 moves inferred (a few gaps explained by more 2-spawns than real), every 4th -> 304.
  - Bellman-residual proxy (cheap, no playouts; analyze --depth 1/2/3 on pilot-1 positions, best-notables): relative
    |V(d2) - V(d1)| of the d2-best move, median / p90: clean engine positions 0.07% / 1.9%; 1-ply-net noise positions
    0.11-0.12% / 2.1-2.4%; beginner corner 0.82% / 7.4%; greedy 0.36% / 6.9% -> the network is 4-10x less self-consistent
    on beginner positions. Best move changes d1->d2 in 38% (clean) .. 50% (corner) of positions, d2->d3 33% .. 41%
    (many near-ties) -> analysis should search deeper than the engine plays when time allows.
  - analyze: `--depth D` is now the ANALYSIS depth (it was swallowed by the engine's --depth: the first Bellman run
    compared identical values).
  - New: src/calib.h + scripts/fit_calib.py (odds model: logit P(T) = a_T(s) + b_T(s) u, u = value / vbar(s) - 1,
    hat functions on log2 tile sum; expected future = ratio(s) * value); `analyze --calib MODEL.txt` prints odds and
    calibrated expected future points. scripts/select_positions.py (TSV rows -> pool .bin), scripts/study_calib.sh and
    scripts/study_judge.sh (big-machine studies), scripts/exp_messytrain.sh (robustness fine-tune of s0cpu with half
    of the episodes from messy pools, TD 0.01 -> 0.001; only if the judge shows a weakness), scripts/aws/remote_init.sh
    (build + recompute and fingerprint-check the k5 tables on the instance), push.sh levels code/core/all.
  - **Judge pilot (rollout, K=16 playouts x H=100 engine moves + value, best-notables)**, 60 beginner positions (pilot-1
    corner/greedy games, max >= 32): the engine's move is significantly worse (z > 2) than the rollout-best move in 1/60
    positions (loss 1,062 of ~355k = 0.3%); mean rollout loss of the engine move 961 points (~0.3%, mostly the max-over-
    noise bias; se per move 200-1000). -> no sign of misplay on beginner positions despite the larger Bellman residuals.
    Values there are ~15% below the rollout returns (consistent with the stage calibration ratio > 1). For the AWS
    study use K >= 64 and H 500-1000 (delayed consequences; less reliance on the bootstrap value).
  - Clean judge pilot (same settings, 60 engine positions max 128-8192): 0/60 significant errors, mean loss 567 (noise
    floor) -> beginner positions (1/60, 961) are not measurably worse at this resolution.
  - Pilot 2 handovers (softmax players -> engine): future/value at max tile 128-1024 ~1.6-1.7 for messy AND clean
    positions (the early network value is the 1-ply policy's ~335k vs the engine's ~550k) -> a stage effect, not a
    messy-position effect. Engine odds from intermediate-human positions (t=0.03, max 128-1024) P(32768) 46-64% ~ base
    rate 60% (n ~ 40, +-8): the engine repairs early messes; corr(value, future) on handovers ~0 -> early odds will be ~
    base rates; position-specific odds must come from mid/late structure. Some handovers from max-2048 positions die
    before 16384 (P 0.67-0.88).
  - PRODUCT IDEA: personal odds - fit the player's softmax temperature t to their moves (max likelihood of the played
    moves under exp(-relative loss / t)), then odds under a soft:t player (playouts with the 1-ply soft policy are cheap,
    or a calibrated model per t): "players at your level reach 4096 from here 35% of the time". Engine odds stay as the
    Stockfish-style "with best play" number.
  - analyze: `--line N` sample continuation (the engine's next N moves under random tiles, fixed seed per position);
    stdin protocol accepts per-request options "depth=4 risk=1 line=10 | BOARD"; no plan text below a 32 tile.
  - **Skill estimate + personal odds (new, working):** review mode fits the temperature t of the soft:t player (max
    likelihood of the played moves under exp(-relative loss / t), grid over t). Validation on traced soft:t games
    (`messy --trace FILE`, review with --depth 1 to match the generator's 1-ply losses): true 0.003 / 0.01 / 0.03 / 0.1
    -> fitted 0.0030 / 0.0093 / 0.032 / 0.091. `analyze --personal T [--personal-playouts N --threads K]`: share of N
    soft:T playouts (shared `soft_move` in engine.h) reaching the next 4 tiles; 200 playouts 0.1-0.6 s on 4 threads.
    Example [0 2 4 2 / 0 4 16 8 / 2 8 32 64 / 4 16 128 512]: t=0.003 1024/2048/4096/8192 = 98/94.5/83.5/57%, t=0.01
    93/69/42/10.5%, t=0.03 82.5/34.5/6/0%.
  - KNOWN RISK for expert analysis: the engine is a snake/corner-lock player; expert humans may use other formations
    (e.g. macroxue-style 2-D blocks, which the old research found stronger in the final phase). Network values and
    rollout judgments (our engine continues) may then be biased against a valid human style. Irrelevant below ~8192
    (the engine is far stronger than such players); check on the expert video games when they arrive (disagreement
    clusters by formation).
  - Pilot 2 complete (60 games per category; results/calib/p2_*.tsv). Beginner handovers (corner/greedy -> engine at max
    32-256, n=56/57): engine P(32768) 50-83% (~ base rate 60%), a few early deaths (one before 4096); future/value 1.73-
    1.78. -> early damage from beginner or intermediate play is almost fully repairable by the engine.
  - First odds model on all pilot data (results/calib/model_pilot.{json,txt}, 861 positions): expected-future ratio by
    tile sum 64:1.78 256:1.72 1024:1.58 4096:1.35 8192:1.57 16384:1.38 24834:0.87 32768:0.89 49667:0.47; logistic odds
    barely beat a constant in-sample (T=32768 log-loss 0.674 vs 0.691; T=4096/8192 overfit) -> needs the AWS-scale data
    (and stronger regularization / held-out evaluation in fit_calib.py).
  - **Serving check (scripts/serving_bench.sh, 210 pilot positions, single thread, laptop):** best-notables (no tables)
    at the engine's depth mean 1.5 ms (p90 3.1, max 45), depth 4 mean 3.1 ms, depth 5 mean 35 ms (p90 81, max 134), peak
    RSS 1.3 GB; with tables (best) engine depth 1.7 ms, depth 5 28 ms, RSS 3.5 GB (k6 tables in RAM, k5 on disk), rare
    cold-table spikes (depth 4 max 1.19 s: on-demand k6 DP). Portable build (no PEXT): 3.2 ms vs 1.5 ms (~2x slower). ->
    a small 2-4 core server with 4-8 GB RAM (+90 GB disk for the k5 tables) serves deep analyses at tens per second.
    Not yet: HTTP wrapper, weight compression (stage 1 of best_v5 is never read: -268 MB; untrained weights).
  - fit_calib.py now holds out whole games (game id hash % 5) and picks the ridge strength by held-out log-loss; pilot:
    T=8192 0.200 vs constant 0.209, 16384 0.248 vs 0.258, 32768 0.6865 vs 0.6872 (n too small).
  - **Value loss vs real loss (scripts/judge_loss_fit.py; judged early positions: p2_corner H200 + pilot beginner/clean
    H100, 176 positions, every legal move):** relative value loss -> mean relative rollout loss: 0-0.1%: 0.21% (noise
    floor), 0.1-0.3%: 0.21%, 0.3-1%: 0.93%, 1-3%: 0.16% (!), 3-10%: 0.95%, 10-30%: 10.6%, >30%: 51.6%. -> the analysis
    OVERSTATES moderate losses ~5x (the engine repairs that damage within a few hundred moves); only >10% value losses
    are real. The review's mistake classes must use a calibrated loss (isotonic map value loss -> real loss, per stage,
    fitted on judge data); early-game numbers only so far (mid/late damage is less repairable - check soft003).
  - Judge p2 (K=32, H=200, full engine): corner handovers 1/56 significant errors (loss 139 = 0.04%), mean loss 776
    (noise floor); early positions run fast (~1 min per category).
  - explain.h: merges ("merges the two 256s into a 512", from rank counts), home edge kept full / gap opened ("leaves a
    gap in your top row where a new small tile can land"), plan says "merge the 32 in ... into it" when the needed tile
    is already next to the chain's end, articles ("an 8").
  - **Judge pilot complete (results/judge/p2_*_h200.tsv, K=32, H=200, full engine with tables; handover positions of
    pilot 2):** significant engine errors (z > 2) corner 1/56, greedy 3/57, soft003 0/33, soft01 1/27, soft03 0/41 =
    5/214 (2.3%, about the false-positive rate of z > 2 over ~3 compared moves) -> NO measurable robustness gap on
    human-like positions; robustness retraining (exp_messytrain.sh) not needed unless the AWS-scale judge says otherwise.
    Value loss -> real loss on all 334 judged positions: 0-0.1%: 0.21, 0.1-0.3%: 0.19, 0.3-1%: 0.55, 1-3%: 0.20,
    3-10%: 0.79, 10-30%: 6.5, >30%: 52.8 (% of the best rollout value).
  - **Human data has arrived (work in progress by the other chat, read-only for us):**
    ../2048-human-data/work/out/<video>.decisions.jsonl - one record per decision: video, segment, ply, board (hex,
    cell 0 first, ranks; g/h = 65536/131072), board_u64 (= our board_t), move (U/R/D/L), observed (false = inferred over
    a skipped frame), spawn, t, think_s (time before the move), undone/maybe_two_moves/rest_ambiguous/gap flags; plus
    <video>.summary.json (quality: explained_share, gap_share, four_share, think-time percentiles). 13:20: 67 videos,
    147,798 decisions (141,993 observed, 251 undone), max tiles 256 .. 131072 (21 videos end at 1024; 7 at 65536, 1 at
    131072). Pipeline in ../2048-human-data/pipeline (frames -> tile clusters -> labels -> boards -> move chains).
  - analyze --stdin: per-request option `played=U` (echoed as "played"). scripts/human_review.py DIR: analyzes every
    decision (best-notables, cached in results/human/analysis.jsonl) and summarizes per video (match with the engine,
    mean relative value loss, losses > 10% per 1000 moves, skill temperature). Test on 40 decisions per video: t from
    0.0003 (32768-level players) to 0.011 (players who reach 32).
  - **Human data, first full review (results/human/analysis_v0_147k.jsonl = 147,547 decisions of 65 videos, best-
    notables; summary printed by scripts/human_review.py):** match with the engine 30-70%; 1024-level players: match
    37-47%, mean relative value loss 0.55-1.3%, skill t 0.035-0.076; 4096-8192 players: 50-61%, 0.2-0.5%, t 0.02-0.04;
    32768+ players (good-quality videos): 53-58%, 0.5-1.5%, t 0.06-0.15 (WORSE than mid players: late positions are
    harder - larger value gaps between moves - so per-video t is confounded by stage; added t on positions <= 2048
    only). Data quality varies a lot per video (pipeline summary: explained_share 0.11-1.0, some videos with thousands
    of segments, e.g. BcynGyiqBvE 4762 segments / 3205 glitches / 61% gaps -> its 10% big-loss rate is mostly unreal
    boards). Fixes: losses normalized by max(|best value|, 100k) (near-dead positions made relative losses explode:
    438%); inferred (observed=false) and ambiguous decisions to be skipped (cache now stores segment and flags; the
    other chat is still adding videos: 176k decisions at 13:45 -> recompute running, redo when the data is final).
  - Study s201 (laptop, G=250): clean games 93.2% 16384 / 58.0% 32768 / 553,520 (= benchmark within noise). Category
    `late` (engine with 5% second-best moves until sum 16000-34000) FAILED: those games end at 2048-8192 (median 4096),
    1 handover in 250 -> second-best moves are often terrible; replaced by "lapse" categories (scripts/study_calib2.sh:
    clean engine, then a softmax lapse "@+300" or "@+600", then the engine; new relative switch syntax "@+N").
  - **Loss map in the product:** scripts/fit_lossmap.py (isotonic regression of the judge's rollout loss on the
    relative value loss, noise floor 0.21% subtracted; appends "lossmap x y ..." to a model .txt). Pilot map (1182
    position-moves): value loss 0.6% -> real 0.14%, 1.8% -> 0.14%, 5.7% -> 0.58%, 15% -> 4.8%, 28% -> 12.9%, 71% ->
    70%. analyze --calib with a lossmap: per move "real_loss" (JSON) / "(real ~x%)" (text); review classes by estimated
    real loss: inaccuracy 1-3%, mistake 3-10%, blunder > 10% (relative losses normalized by max(|best|, 100k)). Odds are
    made monotone in T (Calib::odds). results/calib/model_pilot.txt = pilot odds + pilot loss map (odds unreliable).
  - Review output (analyze --review): accuracy (lichess formula 103.17 exp(-0.04354 x real loss %) - 3.17, mean over
    moves), the 5 key moments (largest estimated real loss, with reasons), JSON summary line with --json. Accuracy
    saturates (99.4% for a soft:0.03 synthetic player: most 2048 moves do not matter) -> mistakes/blunders/key moments
    and the skill estimate carry the information; rethink accuracy on real human games.
  - Think time vs move quality (human_think.py, v0 cache, losses normalized by max(|best|, 100k)): match 43-54% and
    mean value loss 1.1-1.4% in every think-time bin; losses > 10% most frequent after 1.2-3 s thinks (43 per 1000 vs
    19-29 elsewhere: hard positions) -> no strong think-time effect.
  - Human recompute (results/human/analysis.jsonl, 175,336 decisions of 113 videos at 14:05; 22,551 inferred/ambiguous
    decisions skipped in the stats). **Skill by stage (scripts/human_skill_stages.py):** at <=512 everyone plays loose
    (t 0.04-0.13 even for 4096-8192 players; beginners who end <= 256: 0.26-0.99); in 1k-2k positions players who end at
    1024 have median t ~0.04, players who reach 4096-8192 ~0.02 (0.007-0.06) -> the measure ranks players correctly
    WITHIN a stage; >=16k positions give larger t (0.024-0.26; long expert videos with poor data quality at the top) ->
    report skill per stage against a population reference ("in the 1024-2048 phase you play like a typical 8192
    player"), never one number across stages.
  - Study s201 soft001 handovers (t=0.001 human-like, handover at sum 4000-30000, 141 positions at max 4096-16384):
    engine P(32768) 59.6-63.5% (~ base rate), P(16384) from 8192-level handovers 92.3% (base ~97%), corr(value,
    future) 0.30 -> mid-game human-like damage is mostly repaired too; odds will be near the stage base rates with
    modest position-specific adjustments.
  - GOTCHA again (3rd time today): never `pgrep -f PATTERN` in a wait loop whose own command text contains PATTERN; wait
    on files (done-files, report lines) instead.
  - **Sampling bias found:** messy's random per-game samples (uniform over a game's moves) over-represent short,
    failing games among early positions (a game that dies at 2048 puts all its samples below 4096, a long one ~1):
    s201_clean had 48 of 527 rows below 4096 from 3 games that never reached 4096 -> fitted "P(4096)" 0.937 instead
    of ~0.996. Fix: `messy --checkpoints S1,S2,...` (kind 2 in the 'switch' column: each game's first position at
    tile sum >= S_i: each game counts once per stage) and fit_calib.py uses only handovers (1) and checkpoints (2)
    unless --use-random. Odds model v1 (results/calib/model_v1.*) was fit with the biased rows: superseded.
  - Laptop queue (each waits for the previous): study_calib.sh s201 part 1 (running) -> study_calib2.sh (lapse8,
    lapse16, lapse16b) -> judge_horizon.sh (H=1000 re-judge of the p2 positions, loss map at both horizons) ->
    study_calib3.sh (s301: 500 clean engine games at 29 tile-sum checkpoints). ~5 h from 14:15.
  - Explanations checked on real human blunders (good-quality videos, value loss 12-60%) -> fixes: (1) BUG: losses
    were measured against the best raw value even when the corner lock forbids that move (a human who played the
    engine's own move got a "19% blunder"); now the reference is the best lock-allowed move (or the table's move),
    and distrusted corner-breaking moves with a higher raw value show "loss n/a"; (2) new reason "misses merging the
    two 512s (they are no longer next to each other)"; (3) fallback for clearly worse moves (>= 3% value loss) with no
    concept-level reason: "the engine's look-ahead prefers X: the position after it keeps better long-term chances".
    Open: expert disagreements like 64-merges into the corner of a 32768 top row (engine: -15% value, real ~5%) may be
    the snake-formation bias -> the dispute judge will tell.
  - Population skill reference: results/human/skill_reference.json (median t per stage by the video's largest tile);
    <=512: 128: 0.99, 256: 0.61, 512: 0.22, 1024: 0.069; stronger groups noisy (2-35 videos each).
  - **Explanation validity study (analyze --features: concept features of each afterstate; 5760 human positions,
    14,357 (position, worse move) pairs):** correlation of concept deltas (move - reference) with the relative value
    loss: chain length -0.51, chain collapse -0.44, exposed cells next to big tiles +0.42, big tiles in the center
    +0.40, corner distance +0.33, corner -0.33, trapped small tiles +0.30; free cells -0.05, merges available +0.01,
    merge rank -0.05 (NOT predictive). Joint linear fit R^2 0.36. -> dropped the "fewer merges" reasons (spurious),
    free-cells reason only for a difference >= 3, reasons ordered by predictive strength.
  - Explanation coverage on 174 real human mistakes (est. real loss >= 3%, median 5.4%): specific reasons for 45%
    (after: new concepts corner distance "keeps your biggest tile further from a corner", exposed cells "opens space
    next to your big tiles where a new small tile can get stuck", chain length "lines up fewer of your big tiles in
    order", and a search-based risk reason "riskier: 45% of the possible new tiles leave you clearly worse off, vs 5%
    after left"), the rest get the honest fallback "the engine's look-ahead prefers X". Next lever: compare the
    engine's continuations after both moves, or an LLM over the structured data (later, with the user's key).
  - **AWS 14:30: HPC quota L-F7808C92 is now 192 (granted; the request still shows CASE_OPENED). Launch FAILED:
    "InvalidParameterCombination: The specified instance type is not eligible for Free Tier"** -> the account is on
    AWS's Free plan (accounts since 2025 choose Free or Paid plan); only free-tier instance types can run until the
    USER upgrades the account to the Paid plan in the console (Billing and Cost Management -> upgrade plan). Asked the
    user. launch.sh now uses a 500 GB root volume (was 1 TB). Retry `scripts/aws/launch.sh hpc8a.96xlarge` after the
    upgrade.
  - **Odds model v2 (weights/calib/model.txt = results/calib/model_v2.txt; analyze loads it by default, --no-calib
    to skip):** base rates pinned by virtual checkpoints from the 1000 best_v5bb benchmark games (`fit_calib.py
    --base-log LOG`: every game adds a row per tile sum it passed, at u = 0); ONE value slope per target (>= 0: a
    better value never lowers the odds; per-knot slopes overfit 725 handover rows and even flipped sign); vbar with a
    tiny ridge only (the strong one shrank sparse knots -> inflated odds of 69-92% for 32768 on a fresh board); odds
    made consistent by the chain rule in Calib::odds (P(T_k) <= P(T_k-1) x base conditional at that sum: the smaller
    target's model sees immediate danger, the bigger target's slope is weak because its outcome is mostly luck).
    Check: fresh board 99.8/99.5/98.7/95.4/59.7% for 2048..32768 (benchmark 99.8/99.6/98.7/95.4/59.8); clean 2048
    snake 32768 59.5%; messy 512 position 16384 87%, 32768 54%; nearly dead board (1 empty, no merges) 16384 44%,
    32768 28%. Slopes: 8192 1.56, 16384 4.55, 32768 0.19 (held-out log-loss 0.052 vs 0.053, 0.167 vs 0.180, 0.661
    vs 0.658). Refit with the s201 lapse + s301 checkpoint data tonight.
  - **Value attribution (Evaluator::attribute in search.h):** per-cell split of the network value (every pattern
    instance's weight shared equally by the real cells it reads; cells sum exactly to the network value: 293580.3 vs
    293580.2). `analyze --heat`: per-move map of (move - reference) attribution (UI heat map). Used for a new reason
    when no concept fires: the 2x2 area with the largest deficit, named by its biggest (relevant) tiles: "weakens the
    bottom-left area around your 256 and 32: that is where the engine's evaluation drops most" (only when the 1-ply
    attribution total agrees with the loss and the area holds > half of it). Coverage of real human mistakes (>= 3%):
    specific reasons 75% (area 30%, exposed 16%, trapped 9%, center 9%, risk 8%, ...), generic fallback 25%.
  - HTTP API: `python3 scripts/serve.py [--port 8048] [--workers N] [--preset best-notables|best]`: resident analyze
    --stdin worker(s); POST /analyze {"board": [[...]] | "tiles" | "hex", "depth", "risk", "line", "played"} -> the
    analysis JSON; GET /health. Tested end to end (odds, real loss, reasons, risk; bad input -> 400).
  - Risk reasons now computed for every clearly worse move (>= 3% value loss) and placed first when the gap in bad-tile
    share is >= 30 points; when the bad tiles end the game: "the next tile ends the game in 90% of cases (vs 10% after
    down)". Coverage of real mistakes unchanged at 75% (risk now in 20% of them).
  - analyze: "summary" (JSON) / "summary:" (text): one-paragraph verdict = the most informative target's odds vs the
    stage's base rate ("in trouble compared with a typical position at this stage"), best move + its main reason, the
    move to avoid (est. real loss >= 10%) + its main reason. All reasons are verb phrases now ("is riskier: ...", "lets
    the next tile end the game in 90% of cases (vs 10% after down)", "gives up long-term chances: the engine's
    look-ahead prefers X"). Example: "With best play from here, the 16384 tile comes 44% of the time (in trouble ...).
    Best move: down. Avoid right: it lets the next tile end the game in 90% of cases (vs 10% after down)."
  - **Odds model v3 (now weights/calib/model.txt) + survival adjustment, validated on a near-dead board:** v3 = all
    s201 part-1 handovers + pilot handovers (~930 real rows) + the benchmark virtual checkpoints; the value slopes
    shrink with more data (16384: 0.16, 32768: 0.02; v2's 4.55 came from a few positions): for human-like positions the
    engine's odds barely depend on the value beyond the stage. Near-dead boards are rare in that data, so analyze now
    multiplies the odds by the survival share after the move (1 - share of next tiles that end the game; one spawn
    enumeration at depth 1). Ground truth for [2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 .] (1 empty, no merges):
    120 engine playouts (rollout --stop-rank 14, 30 copies of the position for parallelism): P(2048) 0.875, P(8192)
    0.875, P(16384) 0.850 +- 0.033; v3 + survival: 0.898 / 0.886 / 0.842 (v2 said 16384: 0.44). Fresh board v3: 16384
    93.6%, 32768 57.7% (true 95.4 / 59.8: beginner handovers pull the low-sum intercepts down - at equal value they do
    a bit worse; a messiness feature beyond value would fix it).
  - rollout: `--stop-rank R` (playouts end once a tile of rank >= R exists); parallelism is over (position, move) tasks
    - duplicate a single position N times for parallel playouts.
  - **Big-tile fix (65536+ boards, e.g. the expert videos):** to_search_board clamps ranks it cannot fit (131072 and
    65536 both became 32768 -> a different, mergeable position!) and the analysis printed the lowered tile values.
    New `map_search_board` (game.h): lowers min_gap down to rank 1 when needed (never clamps; fails only with > 15
    distinct ranks) and returns the inverse rank map; parse_board keeps it (g_display_rank) and every displayed tile
    (board, plan, reasons, summary) uses it. Engine boards in JSON ("hex", "after") stay in search ranks. play.cpp
    still uses to_search_board (the engine itself never meets a 131072 in practice).
  - Review skill estimate now uses the floored loss normalization (max(|best|, 100k)), like human_review.py.
  - **Do board concepts predict the engine's outcome? (scripts/feat_odds_test.py, 1039 handover rows of s201 part 1 +
    p2):** held-out log-loss, base (stage bins) / + value u / + concepts (corner, chain length, exposed, trapped,
    corner distance): T=8192 0.0589 / 0.0590 / 0.0620; 16384 0.1841 / 0.1834 / 0.1844; 32768 0.6829 / 0.6829 / 0.6907
    -> NOTHING beyond the stage base rate predicts the engine's outcome from human-like positions (it repairs the
    damage; luck decides). Handovers do succeed a few points less than clean engine positions at the same stage (e.g.
    32768 ~55% vs 60%), but no feature tells which. => odds = stage base rate (between clean and human-handover rates)
    x survival of the next tile; the value slope stays small. Check the late-game lapse data (structural damage in the
    16384 phase may be predictable).
  - **Personal odds discriminate positions, engine odds do not (25 clean engine positions vs 25 soft03 handovers, max
    256-1024; analyze --personal 0.01, 200 playouts):** personal P(4x current max) clean mean 0.624 (quartiles 0.47 /
    0.69 / 0.78), messy 0.597 (0.44 / 0.65 / 0.71); engine odds 0.997 for all. -> for typical players the meaningful
    "evaluation bar" is personal odds at their (estimated) skill; engine odds are the "with best play" reference and
    matter late in the game or near death. PRODUCT: show both; personal odds need a faster estimator than playouts
    (0.1-0.6 s per position on 4 threads is fine for one position, too slow for whole-game graphs: fit a model like
    the engine's odds model on soft:t playout data per t).
  - Fast personal odds (in place, waiting for data): scripts/fit_personal.py (per temperature t of the soft:t player:
    logit P(the player reaches T) = a_{t,T}(s) + b_{t,T} u, the player's own vbar; prints held-out log-loss with and
    without u), PersonalModel in calib.h (interpolates in log t, logit space), analyze loads weights/calib/personal.txt
    if present and then answers --personal T instantly (x the next-tile survival); --personal-playouts N forces
    playouts. Data: scripts/study_personal.sh (1000 soft:t games per t in {0.003, 0.01, 0.03, 0.1}, checkpoints +
    values; waits for the human recompute because of RAM).
  - The engine's move has a strength reason in 83% of 300 human positions (mostly edge kept full 77%, corner 58%,
    merge 18%); in 12% no alternative is clearly worse.
  - Review: "chances kept" = product over moves of (1 - estimated real loss) (JSON "kept"). Synthetic soft:t games:
    accuracy 99.9 / 99.4 / 98.4% vs kept 65.8 / 1.1 / 0.0% for t = 0.003 / 0.03 / 0.1 -> discriminates where accuracy
    saturates; harsh for games that end in death (the fatal last moves count) -> for human games report it per phase or
    up to the point where the position became lost (TODO when reviewing real games).
  - lapse8 (s201, 227 handovers after a ~140-move t=0.01 lapse in the 8192 phase): engine P(16384) 95-96% (base ~97-
    98%), P(32768) 51-61% (base ~61%); held-out log-loss base / +u / +features: 16384 0.2514 / 0.2503 / 0.2667, 32768
    0.6636 / 0.6631 / 0.6746 -> again nothing beyond the stage predicts the engine's outcome.
  - **Personal-odds model fitted (weights/calib/personal.txt = results/personal/model.txt; scripts/study_personal.sh
    took only ~5 min: 1000 games per t, 6.9k-15.5k checkpoint positions):** held-out log-loss with and without the
    value u is IDENTICAL for every t and target -> also for human-like players, among positions they actually reach,
    the outcome is decided by future play and luck; the stage (tile sum) carries the information. CORRECTION: the
    earlier "personal odds discriminate positions (IQR 0.44-0.78)" compared positions at different stages (target =
    4x the max tile) -> a stage effect, not position quality. => personal odds = per-skill base rates by stage x
    next-tile survival (+ the small value slope). Fast model vs 300 playouts: [0 2 4 2/0 4 16 8/2 8 32 64/4 16 128 512]
    t=0.003 97.4/92.6/78.4/53.0 vs 98.3/94.3/82.7/53.3; t=0.03 76.4/36.1/5.9/0.6 vs 80.7/35.3/5.0/0.0; 2048 snake t=0.003
    91.6/61.3/21.2 vs 88.0/60.3/20.0; t=0.03 4096 32.7 vs 23.3 (largest gap). Base rates of the soft players from the
    start: t=0.003 reaches 4096 ~83%, 8192 ~59%, 16384 ~22%; t=0.01: 2048 69%, 4096 40%, 8192 9%; t=0.03: 1024 63%,
    2048 33%, 4096 7%; t=0.1: 512 48%, 1024 16%.
  - Human recompute with the fixed engine: results/human/analysis.jsonl (175,336 lines, 345 MB, complete). The
    summary step of human_review.py loads everything into Python (several GB) -> killed it to protect the study's
    RAM; make the summary streaming before rerunning it.
  - **Human data, corrected (fixed engine: lock-aware reference, real big tiles; observed decisions only; 60 videos
    with explained_share >= 0.9 and >= 300 decisions; medians per level of the video's largest tile):**
    <=512 (6 videos): match 35.5%, mean value loss 1.79%, losses > 10% 32 per 1000 moves; 1024 (30): 41.0%, 0.89%, 7.4;
    2048-4096 (12): 50.2%, 0.60%, 11.5; 8192-16384 (8): 53.5%, 0.34%, 5.5; 32768+ (4): 55.0%, 0.83%, 20.1 -> monotone
    in level except the top group's larger losses (late-game difficulty and/or formation bias: dispute judge tonight).
    human_review.py's summary now streams the cache (memory-light).
  - lapse16 (211 handovers in the 16384 phase after a ~140-move t=0.01 lapse): engine P(32768) 61.6% (base at sums
    20k-30k ~63-73%); held-out log-loss base / +u / +features 0.7015 / 0.7011 / 0.6890 (chain length coef +0.53) -> a
    first hint that structure predicts late-game outcomes, not significant at n=213. lapse16b (t=0.03, +600) next.
  - **Real game reviews (scripts/human_to_boards.py VIDEO -> analyze --review):** UZERpmBP6Mo (1024-level, 1019 moves):
    skill t 0.043 (phase <=512 0.069, 1024-2048 0.016), 22 inaccuracies, 2 mistakes, 0 blunders, kept 38% (43% / 88% by
    phase), key moments with reasons ("weakens the top-left area around your 256 and 32"). olW4JczF6-M (#3 leaderboard
    expert, 741k, 32768; video covers 4115 moves of the 16384+ phase): t 0.057, 24 mistakes, 4 blunders, the biggest
    in the final collapse (move 4089 "moves your biggest tile (32768) out of its corner; pulls the 32768 out of your
    chain"), kept 0.3% (dominated by the end) -> TODO: compute "kept" only until the position is lost (e.g. value
    below a few % of the stage's typical value) and report the decisive moment instead.
  - `analyze --selftest`: 9 invariants (parsing incl. the "0 0 0 2" ambiguity and nonsense, 65536+ mapping without
    clamping + real display, 2-move gap bridging, attribution sum = network value, legal engine move and lock-aware
    reference, dead board, monotone survival-scaled odds) - all pass. Run it after every change to the library.
  - docs/api.md: the analysis API (request options, every response field, review summary, model files). Weakness
    reasons are now shown only for moves with >= 2% value loss (near-equal moves got misleading reasons like "leaves
    fewer free cells" for a 0.1% difference).
  - lapse16b (t=0.03 lapse of +600 sum, ~270 moves, in the 16384 phase): only 121 of 250 games survived the lapse; the
    survivors' engine P(32768) 62.8% (base); corr(value, future) 0.41; held-out log-loss on lapse16+16b (334 rows)
    base 0.6443, +u 0.6345, +features 0.6442 -> late-game damage IS partly predictable from the value (not from the
    concepts). fit_calib.py now fits two value slopes (sum < 16384 / >= 16384); test fit with all lapse data: T=32768
    early 0.19, late 0.46; T=16384 early 0.25. Final v4 after the checkpoint run.
  - **Formation check (expert videos vs engine):** 6 clean expert videos (max >= 16384, explained >= 0.9), 20,769
    positions with a tile >= 4096: biggest tile in a corner 99%, snake chain >= 4 tiles 98%, top-4 tiles as a corner
    2x2 block (PDF-like) 0%; engine games: 99% / 97% / 1% -> experts play the same snake formation as the engine; the
    formation-bias risk does not apply to this data. Their larger measured losses are late-game difficulty or real
    mistakes (dispute judge tonight separates the two).
  - Review: "best or good moves" = share of moves with estimated real loss < 1% (1024-level UZERpmBP6Mo: 97.6% while
    matching the engine on 44.2%) - the friendlier and more accurate headline than the match rate.
  - Review: "decisive moment" = the largest estimated real loss made from a still-healthy position (best value >= half
    the stage's typical value): expert olW4JczF6-M move 4089 (36.9%: the 32768 leaves its corner, the collapse
    starts); 1024-level UZERpmBP6Mo move 180 (4.6%). JSON: decisive_move, decisive_loss. End-to-end throughput with
    all features: ~2.6 ms per analysis (300 analyses in 0.78 s after an 11 s load, best-notables, shared CPU).
  - Horizon check (partial: p2 corner + greedy, 407 position-moves): value losses up to ~5% -> real loss ~0 at H=200
    AND at H=1000 (noise floors 0.13% / 0.46%) -> the repair finding holds at the longer horizon for beginner
    positions; engine errors 0/56, 1/57 at H=1000.
  - Population skill comparison deferred: the per-stage reference (weights/calib/skill_reference.txt) is monotone only
    in the earliest stage (<=512: 128 0.99, 256 0.61, 512 0.22, 1024 0.069); later groups are small and noisy (1k-2k:
    1024 0.032, 2048 0.047, 4096 0.035, 8192 0.022) -> needs more videos or an isotonic fit of log t vs log final tile.
  - Plan v2 (explain.h plan()): the chain stops before small stragglers (tile < 8 or >= 4 ranks below the previous
    chain tile); the next path cell decides the advice: equal tile -> "merge", empty -> "build an X in the empty ...",
    smaller tile -> "grow the 2 in the second row, left edge into a 32", bigger tile -> "the 256 in ... blocks it:
    merge it away or rebuild the chain around it". Limitation: one snake path (2-D blocks, e.g. a 16384 under the
    32768, are not described). Summaries of 32768-phase positions carry no odds (the model has no 65536 target; the
    engine's 65536 rate ~0.1% is below what top humans reach - do not show engine odds there to experts).
  - **Horizon check, mid-game (p2 soft003, 116 position-moves, max up to 16384): real losses SHRINK with the horizon:**
    value loss 6.7% -> real 0.76% (H=200) vs 0.37% (H=1000); 17% -> 4.7% vs 2.5%; 31% -> 11.7% vs 7.3% (the engine
    repairs more given more moves; the H=200 bootstrap value still carries the network's overstated damage) -> refit
    the loss map on the H=1000 data (longest horizon = closest to the true outcome). Engine errors at H=1000: 0/33.
  - Population benchmarks for reviews (scripts/human_benchmarks.py -> results/human/benchmarks.json; medians per
    player level, per 100 moves, H=200 loss map): <=512: best/good 94.0%, inaccuracies 3.42, mistakes 2.46, blunders
    0.59; 1024: 97.5 / 1.87 / 0.41 / 0.04; 2048-4096: 98.7 / 0.91 / 0.33 / 0.14; 8192-16384: 99.0 / 0.72 / 0.26 / 0.11;
    32768+: 98.2 / 0.83 / 0.67 / 0.19 (late-game difficulty). Recompute after the H=1000 loss map.
  - **Horizon judge complete (5 categories, 214 positions, 757 position-moves):** loss map H=200 vs H=1000: value loss
    5.7% -> real 0.27 / 0.24%; 14.9% -> 3.7 / 2.4%; 26% -> 7.1 / 3.6%; 78% -> 75.5 / 76.2% (deaths are deaths; mid-size
    damage is ~half as costly at the longer horizon). Engine errors at H=1000: 1/214 (0.5%). The H=1000 map is now in
    weights/calib/model.txt (copy: results/calib/model_v3_h1000.txt).
  - Fix: review mode kept only the LAST board's display map (games that reach 65536 would show earlier big tiles with
    the final board's map) -> per-frame display maps. (A frame pair across the moment a 65536 forms can still fail to
    connect: the two frames use different search encodings - rare, one pair per game.)
  - rollout `--soft T`: playouts by the softmax player instead of the engine ("losses at that skill level");
    scripts/judge_personal.sh (p2 positions, H=1000, t = 0.003 / 0.01 / 0.03) running.
  - **Losses at the player's level (judge_personal.sh: p2 positions, H=1000, softmax playouts):** value loss 5.75% ->
    real 0.24% (engine continues) vs 0.69% (t=0.003), 2.92% (t=0.01), 2.28% (t=0.03); 14.9% -> 2.4% (engine) vs 5.7%
    (t=0.003); 26% -> 3.6% vs 14.9% -> weaker players cannot repair what the engine shrugs off. Maps stored as
    "plossmap T x y ..." in weights/calib/personal.txt (PersonalModel::real_loss interpolates in log t); the review
    reports each key moment's loss at the fitted skill ("est. real loss 2.3% (at your level ~4.3%)") and "mistakes at
    your level" (UZERpmBP6Mo: 7 vs 0 with the engine map).
  - **CURATED HUMAN DATASET (final deliverable of the other chat, 13:37): ../2048-human-data/dataset_build/** -
    README.md, positions.jsonl.gz (131,366 positions of 99 videos / 80 players; fields as the decisions files + `player`
    (YouTube channel = unit of independence) + `tier` (novice < 1024, intermediate 1024-2048, strong 4096-8192, expert
    >= 16384)), games.jsonl.gz (9,050 replayable stretches, viewer move encoding), videos.json (all 140 videos, verdicts),
    unverified/ (10 possibly-bot streams, kept apart). Excluded: AI runs (two 131072 runs at 4-5 moves/s - likely the
    noisy "experts" BcynGyiqBvE / t3G7lstK8c0 of my earlier per-video stats), AI-assisted "2048 Analyze" play, chat-
    played streams, filmed screens. Every move re-verified by an independent rules implementation. README advice:
    split/weight by player (d4Nf6Bg5 = 23% of positions), human moves are context not ground truth, some versions
    spawn 4s 15-20%. USE THIS for all human statistics from now on: human_review.py accepts the .jsonl.gz directly
    (cache results/human_ds/analysis.jsonl); scripts/human_tiers.py = per-tier medians over players.
  - **Loss map by stage (H=1000 judge):** positions with max <= 1024 (608 position-moves): value loss 10-20% -> real
    1.5%, 20-40% -> ~0 (n=11); max >= 2048 (149): 10-20% -> 3.9%, 20-40% -> 6.7% -> later positions repair less.
    weights/calib/model.txt now has `lossmap` (fit on max <= 1024) and `lossmap_late` (max >= 2048; used by analyze for
    positions with a real tile of 2048 or more); fit_lossmap.py --max-tile LO HI --key NAME. The late map rests on
    149 points: a prime AWS job (judge many late positions).
  - Review: per-phase skill with a bootstrap 80% interval (60 resamples of the phase's moves; likelihood terms cached on
    the t grid): UZERpmBP6Mo <=512 t 0.0686 (0.062-0.083), 1024-2048 0.0164 (0.012-0.020). JSON skill_t_80.
  - **Curated dataset, per tier (scripts/human_tiers.py -> results/human_ds/tiers.json; medians over players with >=
    200 moves; staged H=1000 loss maps):** novice (11 players, 4,540 moves): match 34.4%, best/good 97.7%, inaccuracies
    1.48 / mistakes 0.00 / blunders 0.54 per 100, mistakes at own level 5.50 per 100, t 0.347; intermediate (38, 37,827):
    42.8%, 99.8%, 0.19 / 0.00 / 0.00, own level 0.92, t 0.045; strong (13, 28,687): 53.8%, 99.8%, 0.15 / 0.00 / 0.05,
    0.62, t 0.032; expert (7, 43,145): 56.1%, 98.7%, 0.74 / 0.07 / 0.27, 2.27, t 0.083 -> clean progression novice ->
    strong; experts lose more (they play the consequential 16384+ phase; their whole-game t is stage-confounded and
    the own-level map is extrapolated beyond t=0.03). Dispute judge (expert claims) now runs on this data.
  - Engine claims of > 10% value loss on the curated set: novice 4.69% of decisions, intermediate 1.71%, strong 0.75%,
    expert 2.39% (late-game positions; some in a 65536 game, which the engine evaluates through its lowered view - a
    regime it never reaches itself: the dispute judge decides).
  - **Odds model v4 (results/calib/model_v4.*; NOT installed yet):** + 500 clean games at 29 checkpoints (s301: 94.8% /
    55.4% for 16384 / 32768) + all lapse handovers; value term clipped to +-0.3 (Calib::kUClip = UCLIP in fit_calib.py);
    slopes 16384 early 4.73 / late 1.92, 32768 early 0.66 / late 2.57; held-out log-loss 32768 0.6452 vs constant
    0.6561, 16384 0.1836 vs 0.1856; reliability (scripts/calib_check.py): 16384 predicted 0.959 / observed 0.954 (7161
    positions); 32768 0.584 / 0.564 (8369), 0.664 / 0.625 (2440) -> a few points high in the bulk. BUT the near-dead
    board (measured 85.0%) gets 74.6% (v3: 84.6%): the strong early value slope reads "tight" as "doomed". analyze now
    feeds the odds model the mean value of the SURVIVING spawns (danger counted once, via survival) - did not change
    this board. Decision by data: scripts/odds_truth.sh queued (30 tight human positions x 120 engine playouts to
    16384; compare with scripts/odds_truth_report.py results/calib/model_v3_h1000_staged.txt results/calib/model_v4.txt).
    v3 stays installed until then.
  - Look-ahead reasons ("later"): for a clearly worse move without a concept reason, the engine plays 6 moves after
    both moves (4 seeds, same random tiles) and the validated concept with the largest average difference names it:
    "a few moves later your chain is typically shorter (3 vs 5 tiles)" / "... more cells next to your big tiles are
    open" / "... big tiles tend to drift into the middle" / "... small tiles tend to get stuck between big ones" /
    "... your biggest tile usually ends up out of its corner". Coverage on real human mistakes (est. real loss >= 1%,
    staged H=1000 maps, 147 cases): specific reasons 83% (area 24%, risk 24%, exposed 14%, later 11%, ...), generic
    fallback 17%.
  - Latency with all reasons: typical positions ~15 ms, positions with clearly bad alternatives ~200 ms (risk +
    look-ahead per bad move; shared CPU). Reviews compute the expensive reasons only for the played move
    (reason_only): a 1019-move review takes ~1 s after the 11 s load.
  - Review key moments are ranked by max(loss with best play, loss at the player's level) and show both: for a
    1024-level player the moves that hurt THEM ("est. real loss 1.1% (at your level ~4.3%)"), not only engine-level
    losses (which the gentle early-game map makes rare).
  - rollout parallelism: one task = (position, move) with all K playouts -> slow late-game tasks leave a long tail
    (expert disputes: 10 of 16 threads busy after 1 h). TODO: split tasks into playout chunks.
  - rollout: work items are now chunks of 8 playouts per (position, move) task, merged into the task's sums (fixes
    the long single-threaded tail; used by the queued late judge and tight-position truth runs).
  - **EXPERT DISPUTES (curated data; 150 expert decisions in 16384+ positions where the engine claimed > 10% value loss
    vs its own move; 32 playouts x 300 moves with the full engine incl. tables, ~1 h):** refuted 105 (the expert's move
    as good in rollouts), unclear 33, confirmed 12 (8%). Mean claimed relative value loss 21.6% vs mean rollout loss
    1.8%; by max tile 16384: 18.2% -> -1.3% (27), 32768: 22.4% -> 1.8% (100), 65536: 21.8% -> 5.2% (23). -> in late
    expert positions raw value losses are ~10x overstated, more than the general overstatement of the loss map
    (late map: 16-28% value loss -> 3.9-6.7% real): the engine partly misjudges experts' late-game choices (formation
    is the same snake, so it is late-game judgment). Never call an expert move a blunder on value alone: the staged
    loss map handles most of it; refit lossmap_late tonight (judge_late.sh) and consider an expert-specific
    discount or flagging such claims as "the engine is unsure here".
  - **Expert disputes by claim size:** claimed 10-20% value loss: 101 disputes, 2% confirmed, real loss of the
    expert's move -1.1% (the expert's choice is slightly BETTER on average); 20-40%: 33, 12%, 4.2%; 40%+: 16, 38%,
    15.4%. Yet over ALL moves of the same expert positions, value losses translate into LARGER real losses than in
    synthetic late positions (H=300: 29% -> 12%, 64% -> 45%) -> late expert positions are critical, but the engine
    undervalues exactly the moves experts choose (consistent with top humans reaching 65536, our engine ~0.1%).
    -> `lossmap_played_expert 0 0 0.15 0 0.28 0.042 0.55 0.154 1 0.6` in weights/calib/model.txt, used in reviews for
    the PLAYED move in positions with a real tile >= 16384. Expert olW4JczF6-M now: best/good 99.9%, decisive moment
    move 4089 (32768 out of its corner, est. 12%), key moments = the final collapse. Product rule: in expert territory
    the engine is an opinion, not a judge; only very large claims are mistakes. ("At your level" for experts uses a
    stage-confounded t outside the fitted personal maps (0.003-0.03): not meaningful yet.)
  - **IDEA (top candidate for the next research phase, ties analysis quality to SOTA):** learn the late game from the
    experts. Rollouts showed experts' late-game choices are usually right where the engine disagrees (claimed 10-20%
    -> expert move slightly better), top humans reach 65536 (7 videos) where the engine reaches it ~0.1%. Options:
    (a) characterise the disagreements (which concepts/patterns experts choose that the engine undervalues); (b) an
    expert-move prior in the late-game search (n-tuple policy net trained on 43k expert positions, or a value
    correction fitted on the dispute data); (c) test by playouts whether following expert-like choices raises the
    engine's 32768-phase conversion (the old research's weak spot: ~70% final phase vs macroxue ~84%). Needs the big
    machine for the playout tests.
  - Queue reordered 18:10: study_disputes.sh (mid group running) -> odds_truth.sh (tight30, ~1 h: decides v3 vs v4)
    -> judge_late.sh (330 late positions x all moves x 32 x 1000 moves with tables: ~4-5 h overnight).
  - **All-player disputes (150 claims > 10%, all tiers, H=300):** refuted 99, confirmed 24, unclear 27; claimed 20.7%
    -> real 5.8%; by max tile: 256-512 18% -> 6-7%, 1024 24% -> 9%, 2048 24% -> 11%, 4096 33% -> 20%, 8192 21% -> 10%,
    16384 20% -> 6%, 32768 20% -> -0.8% (experts right again), 65536 22% -> 15%. -> for NON-experts the engine's big
    claims are largely real, and real losses on real human positions are several times what the early map (fitted on
    synthetic handover positions) predicts (24% -> ~1%) - only partly the H=300 vs 1000 difference: synthetic positions
    are easier to repair. => calibrate the loss maps on REAL human positions: scripts/judge_human.sh (300 random
    curated positions stratified by tier, all moves, H=1000, full engine) replaces judge_late.sh in tonight's queue
    (after odds_truth.sh).
  - **Tight-position truth (scripts/odds_truth.sh: 30 random tight human positions, value < 75% of the stage's typical,
    sums 500-8000, 120 engine playouts each to 16384):** measured P(16384) mean 0.878 (0.19-0.97). v3: MAE 0.068,
    log-loss 0.384; v4 (clipped value term): 0.102, 0.375 - both nearly constant across positions (v3 ~0.94, v4
    ~0.83): the +-0.3 clip maps every tight position to the same u. The truth is strongly nonlinear (u -0.3..-0.6 ->
    0.85-0.97; -0.81 -> 0.65; -0.95 -> 0.19). **v5 = log(value ratio) term (ratio floored at 1%; fit_calib.py
    --umode-log, "umode 1" in the model, Calib::umode): MAE 0.058, log-loss 0.352 (best on both)**; slopes 16384
    early 0.39, 32768 early 0.24 / late 1.30; held-out 32768 0.6738 vs constant 0.6809. Checks: fresh board
    99.8/99.2/97.0/93.9/58.2 (bench 99.8/99.6/98.7/95.4/59.8), near-dead 16384 82.3% (measured 85.0), reliability
    16384 0.944 vs 0.949 and 0.963 vs 0.967, 32768 0.585 vs 0.561, 0.645 vs 0.620, 0.766 vs 0.800.
    INSTALLED: weights/calib/model.txt = results/calib/model_v5.txt (+ staged H=1000 loss maps + expert played map).
  - Expert disputes, concepts of the expert's move minus the engine's move (preliminary): refuted (expert right,
    n=105): exposed cells next to big tiles -0.27, chain +0.11, merge rank +0.11, rest ~0 -> experts keep big tiles
    better covered than the engine's late-game choice; confirmed (expert wrong, n=12): chain -1.00 (the expert broke the
    chain). Small average differences -> late-game expert judgment is subtle; candidate engine fix to test: a
    late-game term for exposed cells next to big tiles (earlier snake-order penalties failed in the build-up phase).
  - Review: "at your level" losses use the skill of the move's phase (phase_t; the whole-game t mixes stages) and are
    not given in the 16384+ phase (the skill maps come from softmax players who never get there).
  - **Judge on 300 random REAL human positions (curated set, stratified by tier, all moves, H=1000, full engine;
    results/judge/human300_h1000.tsv, ~45 min):** engine move significantly worse in 1/300 (0.3%) -> robustness holds
    on the real distribution. Loss maps on real positions: early (max <= 1024): value loss <= 13% -> ~0 real, 27.7% ->
    6.0% (synthetic p2 map: ~1.1%); late (>= 2048): 0.6% -> 0.09%, 1.8-6% -> 1.36%, 14.5% -> 5.75%, 29% -> 12.6%,
    63% -> 70.7% (synthetic: 16% -> 3.9%, 28% -> 6.7%) -> real human positions repair less than synthetic ones.
    INSTALLED in weights/calib/model.txt (lossmap, lossmap_late from human300; lossmap_played_expert kept); the v5 file
    with the synthetic maps is results/calib/model_v5_synthmaps.txt, with the human maps model_v5_humanmaps.txt.
    Tier benchmarks with the staged maps (human_tiers.py now applies early / late / expert-played maps like analyze):
    novice best/good 98.1%, inaccuracies 0.49 / mistakes 0.63 / blunders 0.26 per 100; intermediate 99.9%, 0.11 /
    0.00 / 0.00; strong 96.6%, 2.99 / 0.37 / 0.09 (small late-game value losses of 2-6% cost ~1.4% on real positions:
    plausible but based on ~400 late position-moves - firm up with a bigger late judge); expert 99.4%, 0.27 / 0.21 /
    0.19.
  - **Skill-level loss maps on REAL positions (human300, softmax continuations, H=1000):** t=0.003: 5.9% -> 1.7%,
    14% -> 5.1%, 29% -> 19%, 63% -> 71% (sensible); t=0.01: 5.9% -> 0.0%, 14% -> 1.3%, 29% -> 14%, 63% -> 48%; t=0.03:
    flat ~3% for every loss >= 0.6% (noise). CONCEPTUAL ISSUE: a weak player's outcome is dominated by their own later
    mistakes, so any single move's RELATIVE loss shrinks with weakness - true but useless for teaching and unstable.
    Kept the synthetic plossmaps in weights/calib/personal.txt; "at your level" is EXPERIMENTAL (docs/guide.md).
    Better definition for later: the drop in the player's own odds of their next milestone (personal odds before vs
    after the move, from soft:t playouts or the personal model with a move-dependent value term).
  - **late300 judge (300 more real late positions, strong/expert tiers, max >= 2048, all moves, H=1000, full engine):**
    engine errors 2/300 (0.7%) -> robustness holds in late human positions. Late map refit on human300 + late300 (all
    late real positions): 0.55% -> 0.37%, 1.8-5.8% -> 1.53%, 14.5% -> 3.47%, 29% -> 13.8%, 65% -> 68.7%; INSTALLED
    (weights/calib/model.txt lossmap_late; copy results/calib/model_v5_humanmaps.txt).
  - Quick SOTA test from the expert finding (scripts/exp_exposed.sh -> results/expexposed/eval.log): play
    `--exposed-pen W LO HI` (Evaluator::exposed_pen: leaf -= W x empty cells next to a big tile, view tile sums
    12288-65536), best_v5 full player, 700 real 16384-formation starts (weights/exps1/pool700.bin) to sum 36864, seed
    999 (baseline 64.14%), W = 0 / 2000 / 6000.
- **2026-10-06 21:50: 24-hour run started.** Instance i-063910223f0247831 ready at 21:20 (k5r10/k5r9 recomputed and
  fingerprint-checked "OK", all weights pushed, cap scheduled: poweroff ~21:15 +04 Oct 7). Four workstreams run as
  background subagents with their own instance dirs (~/2048_X, weights symlinked to ~/2048/weights), laptop build dirs
  (build_X) and file ownership; rules and the table in results/WORKSTREAMS.md; helper scripts/aws/ws.sh
  (push|build|put|pull|run X). mx (32 cores): macroxue as an independent judge of the expert disputes; late (96):
  late-game engine fixes + expert-start retraining (metrics: false claims on expert disputes, 16384/32768-phase
  conversion); coach (16): does advice help human-like players recover; cal6 (48): real-human judge x1200, odds v6,
  personal odds v2 validated on real outcomes. Reports: results/<ws>/REPORT.md (merged here by the coordinator).
  Laptop exposed-cells test: W=0 64.14%, W=2000 62.43% (no gain).
  Exposed-cells test final: W=0 64.14%, W=2000 62.43%, W=6000 61.14% (+-1.8) -> the penalty HURTS monotonically in the
  16384 phase; dropped (the experts' "fewer exposed cells" is not a missing leaf term).
- **COACH TEST DONE (2026-10-06 23:30, workstream coach; full report results/coach/REPORT.md):** engine advice helps
  human-like players recover, and the best form is a WARNING just before a bad move (the player's intended move loses
  >= X -> it is replaced by the engine's move). 249 real start positions (tight / after a real mistake / control;
  S1 128-512, S2 1024-2048, S3 4096-8192) + a 302-position replication (all numbers within ~0.04); softmax players
  t=0.003-0.1 matched to the tiers by the rate of >=15% moves (t=0.1 ~ novices, 0.03 ~ intermediates, 0.003-0.01 ~
  strong) + a "structured" player; outcome P(next doubling), common random numbers. Warnings dominate hints at every
  skill (S1 t=0.1: alone 0.52, engine 0.92, warn>=0.15 at 2.2/100 moves 0.83, best hint policy 0.74); 1-2 warnings
  per 100 moves close 42-74% / 60-90% of the gap to the engine; late thresholds must be lower (0.02-0.05 vs 0.15
  early); 50% compliance -> half the gain; recovery after real mistakes: S2 t=0.03 alone 0.41 -> warn 0.83 -> engine
  0.92. Real players would see 0-0.4 warnings/100 moves (median intermediate/strong), novices 2.7, experts in 16384+
  1.0 (mostly false alarms today -> off/high threshold there until the late-game fix). "At your level" = share of the
  player's own chances lost; nearly skill-independent: <3% value loss ~0, 3-10% 0-3%, 10-30% 6-12% (engine map
  4-6%), >=30% 41-52% (engine map 30-37%) -> report it as ~1.3-1.5 x the engine map, times the player's own odds.
  Note for cal6: S1 big real mistakes cost 0.29 of P(next milestone) under the engine's continuation vs the early
  map's 0.11. Code: src/coach.cpp (build/coach, modes advice/first/fit), scripts/coach_*.
- **MACROXUE JUDGE DONE (2026-10-07 00:00, workstream mx; results/mx/REPORT.md, for_late.txt):** macroxue built on
  the instance (driver outside our tree, GPL: /home/ryanf/projects/2048-macroxue-judge; validated: reproduces its
  published game 2001 exactly; d4 160 games 589,699 / 91.9 / 68.1%). 105 of the 150 expert disputes are ONE player
  (d4Nf6Bg5, 61% of all expert 16384+ positions) who plays macroxue's PDF block formation (6 biggest tiles in a 3x2
  corner block) in the 32768 phase: claimed 21.0% -> real -1.0% with macroxue continuing (ours -2.1%); where
  macroxue's exact block tables decide, the expert's move is table-optimal in 97%, ours in 80%, and OUR MOVE BREAKS
  THE FORMATION in 16%. Snake experts' 45 disputes: claimed 23.0% -> real +6.5% (macroxue) / +11.0% (ours): real but
  2-3x overstated (the installed played-expert map is right for them). The two judges agree (of our 12 confirmed
  macroxue confirms 6; of our 105 refuted it refutes 89). Formation specialists: from the same 300 random expert
  positions, death within 1000 moves: snake experts' positions ours 16.7% vs macroxue 50.7%; PDF player at 32768 ours
  75.6% vs macroxue 46.7%. macroxue on OUR phase tests: 16384 phase d4 70.6%, d6 78.0% (ours 64.1%); 32768 phase sum
  >= 57344 d4 63.2%, d6 70.4% (ours 48.0%); it rebuilds its block from our starts, exact block tables make 54-67% of
  its late moves. => (1) analysis: detect the block formation, no/strongly discounted claims there; (2) follow-up
  (started 00:10 as workstream pdf, clean-room on our eg/lt table code): exact block tables in our engine -> expected
  to remove ~70% of expert disputes and gain +6-14 points (16384 phase), +15-22 (32768 phase).
- late (interim, results/late/report.txt): stage 3 = OTD network weights/expotd/t21.w ("best_v6") halves false
  claims on the disputes (45/105 vs 83-92), better-calibrated claims on UNSELECTED late positions (Spearman 0.701 vs
  0.663), 1000-game benchmark 565,970 / 95.4 / 61.5% vs best_v5bb 559,754 / 95.4 / 59.8 (paired +6,216 +- 4,217,
  32768 +1.70 +- 0.95). Deeper search / bigger budget: helps only on the selected disputes, 15-18x cost -> not the fix.
  Default switch to best_v6 waits for cal6's data collection (maps/odds need a refit for the new values).
- late update 00:30: weights/best_v6.w created (laptop + instance, md5 prefix 004a8625724e; preset_best unchanged).
  Dispute claims split by player type (claims > 10% on refuted disputes): snake experts base 19/24 -> t21 9/24 with
  all 8 confirmed kept, unselected snake positions Spearman 0.777 -> 0.815 (t21 claims fit for warnings to snake
  experts); PDF player 64/81 -> 36/81 but claim-vs-real r ~ 0 for EVERY network -> abstain in block positions until
  the block tables exist (detector requested from workstream pdf; analyze wiring by the coordinator). Expert-pool
  training with a clean 2-fold split by video: no gain (the earlier gain was test-video leakage) -> DROPPED. Running:
  two longer OTD second halves (u0, u1: ensemble), OTD stage B on top of best_v6, candidates on cal6's 400-position
  H=1000 expert judge.
- pdf update 00:50: block-formation detector src/block.h (header-only): `blk::block_formation(b, moves_ahead=0,
  real_rank=nullptr, k=4, gap=6)` = the 4 biggest tiles (with duplicates) in one 3x2 corner block (8 placements), 4th
  biggest >= max/64. On mx's labelled positions: PDF player disputes 93/105, random 41/183 (by max tile: 8192 34%,
  16384 27%, 32768 57%, 65536 3.7% - snake-like again at 65536), controls 13/37; snake experts 1/45, 1/117, 0/23
  (precision 147/149; the 2 hits are block-shaped); other experts in the curated set 0.0-0.3%; strong tier 4.0% at
  8192 (short chains in a corner block) -> fire only at real max >= 16384; our engine's positions: pool700 0/700,
  pool32k 0/1878, pool16real_rest 0/2186, replayed best_v5+t21 games 1.0%. moves_ahead=1 adds no recall.
  -> analyze: abstain from mistake claims in block positions (wiring after cal6 returns: it is editing analyze.cpp).
- **FUZZ QA DONE (2026-10-07 01:00, workstream fuzz; results/fuzz/REPORT.md):** ~4,500 boards in 48 categories (all
  densities, one-move / dead boards, only 2s / 4s, several big tiles, max off-corner at 16384+, 65536/131072 tiles,
  impossible boards, k5-k8 table formations in all 8 symmetries, real positions), 5 laptop passes + 3 instance passes
  with tables, --stdin with 45 malformed lines, 13 odd review files (scripts/fuzz_gen.py, fuzz_check.py,
  fuzz_review.py). Clean: no crashes / invalid JSON / illegal moves; odds, real losses, personal odds and risk in range
  and monotone; every worse move has a reason; corner-lock flags exact; SYMMETRY holds (also in table formations).
  FIXED: (1) repeated requests got deeper and slower (warm search cache fools the depth control; up to 17 s) ->
  EngineThread::reset_search() per request (identical answers, ~6 ms); (2) depth=8 requests hung -> per-request depth
  capped at 6; (3) tiles >= 2^32 overflowed map_search_board / the parser -> rejected above 2^30; (4) plan text above
  the top rank ("merges into a 65536" for 131072-65536 -> 262144); (5) negative losses in table-decided positions ->
  "n/a"; (6) `ms` now includes the reasons; (7) the look-ahead reason uses a fixed depth-3 search (p99 1,565 -> 22 ms
  on real positions). Worst-case latency now: 45 ms (no tables, default options), 3.9-5.2 s the first time a k>=6
  table formation is built on demand. OPEN (relayed): cal6 - expected_future < 0 above sum ~2^15.9, odds use the
  lowered board's max/sum (latent for a 65536 target), real_loss ignores table p in table positions; late -
  map_search_board can map a merge result and a lowered 65536 to the same rank (wrong values for such moves), depth
  control still deepens with a warm cache in play/rollout/messy; minor - 16 distinct tiles -> "not a board", empty
  board -> "game over", "-2" parsed as 2, serve.py docstring says depth 0-8.
- pdf interim 01:05: block tables built on the instance (52 GB, weights/pdf/), validation passed; with the tables at
  the root, claims > 10% on the PDF player's refuted disputes 64/81 -> 26/81. Death-rate playouts and a strength
  screen queued (results/pdf/report.txt).
- cal6 interim (00:00, results/cal6/report.txt; wrapping up after its 200-turn limit): judge1200 done (1200 new real
  positions: early/mid/top 400 each, all moves, H=1000): robustness 12/1200 = 1.0% (noise level). fit_calib.py was
  NON-DETERMINISTIC (Python's salted hash() for the train/test split: 16384 early slope 0.39 vs 2.2-3.5 in reruns) ->
  crc32 ids + 5-fold CV by game. Real-position odds truth: v5 fine except TIGHT 4096-8192 positions (measured
  P(16384) 0.765 vs predicted 0.943) -> band slopes refit on real positions (CV by player): 16384 log-loss 0.354 ->
  0.285, MAE 0.072 -> 0.052; 8192 0.177 -> 0.142; 32768 kept. Loss maps -> 3 stages (early <= 1024, late 2048-8192,
  top >= 16384; calib.h lossmap_top): held-out RMSE x100 early 5.37 -> 3.45 (the old early map gave 14% where
  big blunders measure ~71%; confirms coach's note), late 5.82 -> 5.42, top 19.0 -> 18.4; top map with 80% player-
  bootstrap band: 10% -> 5.6% (4.2-8.9), 20% -> 14.4%, 30% -> 25.5%, 45% -> 45.7%, 65% -> 72.6%. Personal: the soft:t
  model transfers to real positions (MAE 0.04-0.12); review-t vs soft-t scale map added; on 83 real games with known
  outcomes: log-loss 0.622 -> 0.503, AUC 0.77 -> 0.85 (absolute levels not checkable: videos are selected for
  success). Expert disputes x400 (H=1000): claimed 23.6% -> real 10.4%, strongly player-dependent: block player
  21.6% -> 1.3%, BloodyMe77 20.8% -> 16.3% (claims real), others 18.6-33% -> 4.8-21.8%; a played-expert map refit does
  not beat the installed lenient map -> keep it; the discount is formation-specific.
- **CAL6 DONE (2026-10-07 00:10; results/cal6/REPORT.md incl. the REFIT RECIPE for a new engine):** INSTALLED
  weights/calib/model.txt = results/calib/model_v6_cal6.txt (+ .json): odds v6 (synthetic base rates, 3 value-slope
  bands, 8192/16384 slopes refit on real positions, 32768 synthetic), loss maps in 3 stages (early <= 1024, late
  2048-8192, top >= 16384), a TABLE map (table-decided positions: real loss from the exact table probabilities),
  the lenient played-expert map kept; weights/calib/personal.txt = personal_v2.txt (v1 + skill map: review-fitted t
  -> matching soft player). Old: results/calib/model_v5_installed_before_cal6.txt, personal_v1_installed_before_cal6.txt.
  Fixed (fuzz issues): expected_future clamped >= 0; odds/personal odds use the REAL max tile and tile sum; table-aware
  real_loss. Held-out: odds on 200 fresh real positions P(16384) MAE 0.100 -> 0.066, log-loss 0.442 -> 0.311 (tight
  4096-8192: v5 0.944, v6 0.789, measured 0.769); P(8192) 0.052 -> 0.041. Maps RMSE x100 (5 folds by video, 2,200
  positions, 80 players): early 5.37 -> 3.45, late 5.82 -> 5.42, top 19.0 -> 18.4; table map 13.7 vs 14.5 value map
  (411 move pairs). Strong-tier benchmark now best/good 99.6% (was 96.2%), inaccuracies 0.36/100 (was 3.68): the old
  late map overstated 2048-8192 losses. Personal (83 real games with known outcome, 2x milestone): log-loss 0.62 ->
  0.50, Brier 0.22 -> 0.16, AUC 0.77 -> 0.85; still pessimistic for intermediate/strong (0.68 vs 0.94 observed) and
  optimistic for novices; absolute levels not checkable on success-selected videos. Robustness 12/1200 (1.0%).
  Still running on the instance: jold (the old 150 disputes at H=1000, 2 x 16 threads, results/cal6/jold/; then
  scripts/judge_horizon_disputes.py). TODO: coach scripts use lossmap_late for 16384+ (not lossmap_top); the refit
  recipe (scripts/judge_revalue.py) runs once the final engine is chosen.
- late on fuzz issue (big-tile rank collision): real but unreachable in practice - flags `--map-safe` (game.h
  g_map_safe_gap) + `--root-view-safe` (EngineConfig root_safe, search.h downgrade_view_safe_all) + `--leaf-view-safe`
  (Evaluator view_safe), all default OFF; on the fuzz board they remove the collision (move left -> up), but on 800
  real curated positions (500 with 65536+, 300 with 32768) 0 boards mapped differently, 0 engine moves / claims
  changed (the collision needs two tiles just below an empty rank next to the lowered top tile). Defaults kept.
- late 00:45: claims vs real losses on cal6's 400-position H=1000 expert judge (outside block positions): best_v6
  (t21) is nearly CALIBRATED (claim 5-10% -> real 5.5%, 10-15% -> 13.0%, 15-20% -> 14.6%, 20-30% -> 28.0%, 30-45%
  -> 28.3%, 45%+ -> 48.2%); best_v5 overstates (10-15% -> 7%, 20-30% -> 16%, 30-45% -> 17.5%); inside block positions
  no relation. -> with v6 the lenient lossmap_played_expert would HIDE real expert mistakes: refit near-identity for
  v6 (block excluded) at the engine switch (relayed to integ).
- **pdf 01:00 (results/pdf/report.txt):** detector v2 (src/block.h, signature compatible; + 3 biggest in a corner
  2x2 square with the 3rd >= max/8, core_gap=-1 disables): block player 97/105 disputes, snake experts unchanged
  (1/45, 1/117, 0/23), engine late positions 1.0%, other experts <= 0.3% -> use at real max >= 16384. EXACT BLOCK
  TABLES (own code on the layered solver): 12 tables (block's smallest tile at cell 6 or 4, goals 64-1024), 52 GB,
  ~5 min to solve on 32 threads; validated (table play = table probabilities +-0.01; equal to macroxue's values
  where both solve the same sub-game, e.g. .792/.713/.793 vs .787/.709/.788); cover 47% of the block player's 32768
  positions, 0-0.1% elsewhere. Flags (default off): --block-tables DIR --block-min P (EngineConfig, play; a block
  table moves only when no snake table decided; source "block"; analyze fills per-move p). False claims (> 10%,
  refuted by macroxue playouts) on the block player's 105 disputes: base 82, t21 45, base+tables 32, t21+tables 19,
  + detector abstention ~13. Play from the block player's positions (death within 1000 moves): max 32768 75.6% ->
  65.2% (macroxue 46.7%), max 16384 35% -> 16%. Laptop copy of the tables building into weights/pdf/. Strength
  screen running (pool700: block tables; gradient search + block tables at 16384+; without snake tables).
- late 01:10: final engine = best_v6 unless "v6b" (v6 + OTD stage B = weights/late/bo_*.w as stage 2) confirms by
  ~02:30-03:00: claims equal to v6's, 16384-phase test +1.38 +- 0.63 points vs v6 (1307/2100 paired games so far);
  1000-game benchmark (paired with best_v5bb and v6) + 32768-phase test running. The t21+u0 ensemble (judgment only)
  is a later option. integ refits once for the chosen engine.
- **INTEG DONE (2026-10-07 00:40; results/integ/REPORT.md):** analysis engine v0.2 (docs/guide.md, docs/api.md v0.2,
  README analysis section). (1) Block formation: real max >= 16384 and blk::block_formation -> judged by the block
  tables when one decides (source "block", table map, table reasons "leaves a 33% chance to build the tile your block
  needs next (exact table; 100% after left)"), else NOT judged ("formation":"block", "judged":false, real_loss /
  your_cost null, no warnings, summary caveat; reviews skip such moves and report not_judged). `--preset best` loads
  weights/pdf when complete (block_min 0.5, EngineConfig::block_from 14). (2) Coach: per-move `warn` (model line
  `warn`: value-loss thresholds 0.15 up to 512, 0.05 for 1024-8192, 0.30 at 16384+ until the switch); `your_cost` =
  share of the player's own chances of the next tile (lossmap_own per phase, scripts/fit_owncost.py on the coach's
  playouts: 12% value loss -> 3.5/5.4/7.8% by phase, 36% -> 17/21/29%), `your_cost_abs` with --personal; reviews:
  warnings per 100 moves (novice game 3.0, coach measured 2.7), mistakes_at_your_level (your_cost >= 3%); the
  experimental skill maps are gone. Installed weights/calib/model.txt = results/calib/model_v6b_integ.txt (cal6's
  model + warn + lossmap_own). (3) Engine switch prepared: weights/best.cfg (flags applied by preset_best when
  present) + scripts/switch_engine.sh prepare|refit|install NAME "FLAGS" (revalue the rollout truth on the instance,
  refit with block positions excluded, rescale vbar's 16384+ knots, warn 16384+ -> 0.05); prepared for v6
  (results/calib/model_v6.txt, not installed): held-out top map error 21.2 -> 17.6 (the installed top map is badly
  lenient with v6 values: predicts 3-10% where 25.5% is measured), played-expert 11.2 -> 10.4; the v6 played-expert
  fit is near identity at 10-15% and flatter above (20% -> 16%, 30% -> 19%, 45% -> 24%; late's bins said 28% / 48%,
  ~20 positions per bin) -> keep the cross-validated fit. (5) rollout / messy reset the search per playout / game.
  jold horizon check on the old 150 disputes: H=300 105/33/12 refuted/unclear/confirmed, real 2.5%; H=1000
  112/17/21, real 4.7% (per-decision correlation 0.63). Selftest 12/12; fuzz recheck clean.
- **NEW BEST PLAYER best_v6b (late, 2026-10-07 00:50): best_v5 with stage 3 = weights/expotd/t21.w (OTD second half)
  and stage 2 = weights/late/bo_2.w (OTD stage B trained against t21); same settings (preset_best).**
  weights/best_v6b.w (md5 prefix e907c0a49207, laptop + instance). 1000-game benchmark (paired seeds,
  results/bench/late_v6bo2): 572,948 +- 6,552, 16384 95.4%, 32768 62.9% vs best_v5bb 559,754 / 95.4 / 59.8 (paired:
  score +13.2k +- 5.0k, 32768 +3.10 +- 1.16 points); vs v6: +7.0k +- 3.2k, +1.40 +- 0.71 (840/1000 games
  identical); 16384-phase test +0.95 +- 0.50 vs v6; claims identical to v6's (stage 3 is the same). => final engine
  of the 24 h run; switch started 00:51 (scripts/switch_engine.sh prepare v6b, log results/integ/switch_v6b.log).
- **ENGINE SWITCHED to best_v6b (2026-10-07 00:56):** `scripts/switch_engine.sh install v6b "--weights
  weights/best_v6b.w"` -> weights/best.cfg (flags applied on top of preset best / best-notables by every tool),
  weights/calib/model.txt = results/calib/model_v6b.txt (old: results/calib/model_before_v6b.txt; undo: rm
  weights/best.cfg and copy it back). Refit (results/integ/switch_v6b.log; 53 judge files re-valued, 2,184 positions,
  80 players; block positions excluded): top map held-out RMSE x100 20.5 -> 17.8 (by bin: predicted 5.6 vs measured
  5.3 in [3-10), the old map predicted 5.3 vs 26.0), played-expert 11.2 -> 10.4 (now near identity: 10% -> 9.1%, 15%
  -> 14.9%, 20% -> 16.2%, 30% -> 19.0%, 45% -> 24.0%; the old lenient map predicted 2.0 vs 15.8 measured in [1-3)),
  all 11.1 -> 10.0; early / late maps unchanged (their networks did not change); table map refit (table loss 15% ->
  real 10%, 29% -> 20%, 66% -> 39%); odds: vbar knots from log2 sum 14.6 on scaled x1.036-1.044 (median value ratio
  new / old 1.04); warn 16384+ threshold 0.30 -> 0.05. Selftest 15/15. Tier table needs the human dataset re-valued
  with v6b (running: results/human_ds_v6b, laptop, best-notables + best.cfg).
- Human dataset re-valued with v6b (results/human_ds_v6b/analysis.jsonl, 130,579 decisions, 12 min on the laptop;
  tiers in results/human_ds_v6b/tiers.json): novice 98.1% best/good, 0.63 / 0.29 / 0.54 inacc / mist / blund per 100,
  warn 1.94/100; intermediate 99.9%, 0.09/0/0, warn 1.15; strong 99.6%, 0.36/0/0.05, warn 1.15; EXPERT 88.8%,
  8.51 / 1.54 / 1.14, warn 1.97 (was 99.4% with the lenient played-expert map). OPEN QUESTION: the expert numbers fail
  a compounding sanity check (1+ blunders >= 10% per 100 moves over thousands of 16384+ moves would leave no chances,
  yet these experts reach 32768/65536) -> the low end of the top / played-expert maps (value loss 0.3-3% -> real
  0.5-2.7%) sits near the rollout noise floor (1.71%) and/or real losses do not compound like probabilities; the
  scorecard workstream checks "chances kept" vs achieved outcomes per game. Treat expert-tier rates as provisional.
- hm 01:05: personal v3 INSTALLED (weights/calib/personal.txt = results/calib/personal_v3.txt; old v2 kept as
  personal_v2_installed_before_hm.txt): personal odds from playouts of a fitted HUMAN MOVE MODEL (src/human.h,
  conditional logit: value-loss spline + concept / death / direction-habit features + lapses; skill s) instead of the
  softmax player. Real outcomes (scripts/calib_personal_real.py, game bootstrap 90%): 2x milestone log-loss 0.497 ->
  0.425 [-0.122, -0.029], AUC 0.850 -> 0.865; 4x: 0.964 -> 0.685 [-0.376, -0.185], AUC 0.61 -> 0.75. Coordinator:
  PersonalModel reads `player human|soft`; analyze's --personal-playouts fallback plays hm::move at s = -ln(100 k)
  (structure skill min(s, 0.4)); JSON personal_odds.human_skill replaces soft_temperature. Check on a 512 position at
  T=0.05: playouts 0.953/0.797/0.281/0.047 vs model 0.948/0.736/0.270/0.025.
- 01:15: cal7 started (odds refit for v6b with fresh v6b data; expert puzzle: low end of the top / played-expert maps
  measured with 128-256 playouts per move).
- **HUMAN MODEL DONE (2026-10-07 01:20, workstream hm; results/hm/REPORT.md):** conditional-logit human move model
  (src/human.h; fit scripts/hm_*; 114,970 clean decisions, 80 players, one skill per player): held-out players
  (5 folds, skill from the first half of each test player's moves) 0.764 nats/decision vs softmax 1.010 (-24%). The
  gain is structure + habits: losing the corner, pulling the edge line off its wall, big tiles off the edge, death
  after the next tile, merge size; the value term flattens above ~3% loss; intermediate+ players almost never press
  one direction (median share 0.0-0.3% although legal 99% of the time; per game, not per player: "not pressed in
  the last 20 moves" captures it). Weak spot: 16384+ (predicts 3-4 >=15% moves per 100 vs 1.4-2.6 observed); refit on
  v6b late values pending. As a playout player: structure skill capped at min(s, 0.4) (the fitted skill compounds
  errors on its own boards); softmax players are NOT human-like (never hold the corner below 1024 vs humans
  0.74-0.88; 4.7 vs 17.7 moves losing >=3% per 100). Personal v3 (12 keys x 1000 games, skill map from 200 reviewed
  games per key): real games 2x log-loss 0.497 -> 0.425, AUC 0.850 -> 0.865; 4x 0.964 -> 0.685, AUC 0.614 -> 0.749;
  per tier 2x observed / v2 / v3: novice 0.585 / 0.733 / 0.642, intermediate 0.957 / 0.705 / 0.801, strong 0.831 /
  0.524 / 0.577 (still pessimistic for intermediate/strong - partly video selection; novices slightly optimistic).
  Caveat: the phase-0 skill map is steep (reviewed t 0.055-0.09 spans most middle keys). COACH RERUN with the human
  model: conclusions hold (warnings most efficient everywhere; e.g. tight early positions, mid key: alone 0.670,
  warn >= 0.15 at 1.7/100 moves 0.935, engine 0.996); NEW: a hint triggered by the human model's own expected loss
  is nearly as efficient as a warning for mid/strong players -> an app can say "you are likely to go wrong here"
  without seeing the intended move. Next (not done): skill estimated by the human model itself (new skill-map
  format), "how likely a player at your level finds this move" in analyze, late-game refit on v6b values.
- **SCORECARD DONE (2026-10-07 01:35; results/scorecard/REPORT.md, compare.txt; scripts/scorecard.sh NAME "FLAGS"
  MODEL PERSONAL [ANALYSIS]):** one regression suite over every truth set, "start" (21:00: best_v5, model_v5_humanmaps,
  personal v1) vs "now" (01:34: best_v6b, model_v6b, personal v3). Better now: odds on 200 fresh real positions MAE
  0.100 -> 0.066 (tight 0.128 -> 0.079); loss-map RMSE x100 13.0 -> 11.7 (early 6.4 -> 4.2; partly in-sample); raw
  claims > 10% false on refuted expert disputes: block player 67/85 -> 6/85 (+32 abstained), snake experts 22/27 ->
  12/27 with 10/12 confirmed kept; personal odds vs real outcomes 2x log-loss 0.648 -> 0.434, AUC 0.770 -> 0.864 (4x
  1.379 -> 0.656, AUC 0.616 -> 0.807); robustness unchanged 15 -> 16 of 1,800 (noise level); latency p50 2.8 ms, p99 25
  ms (tables: 1.6 / 26 ms). WORSE now: experts' own moves at 16384+ - GAME-LEVEL CHECK FAILS: in experts' 16384
  stretches (all reached 32768) median chances kept 1.0% (R 93; start 81%, R 3.5); on UNSELECTED positions played
  moves with claims 0.3-10% measure ~0 real loss in every stage (1-3% -> -0.1 +- 0.6, 3-10% -> -3.3 +- 1.2); only
  selected big claims follow the near-identity map; Bellman drift: the next position's value recovers 35-55% of a
  played move's claimed loss (estimation error); snake-expert blunder calls: false alarms 8/229 -> 46/175, detections
  22/54 -> 45/52. -> cal7 refits PLAYED-move maps on played moves with the unbiased measure (hard shrink at 16384+,
  table map too), acceptance = game check R ~1-3 with and without tables. Also: fit_lossmap2.py --compare ignored
  lossmap_top (integ's "top 20.5 -> 17.8" was the late map); block-table moves that break the block get no reason
  (11/450 positions; TODO); GPL source extracts found in results/mx/ were MOVED out of the tree
  (/home/ryanf/projects/2048-macroxue-judge/src_extracts/).
- **LATE DONE (2026-10-07 01:45; results/late/REPORT.md, 172 lines):** final engine best_v6b (= best_v5 + stage 3
  t21 + stage 2 bo_2; weights/best_v6.w, best_v6b.w on laptop + instance). Claims > 10% (false = refuted / kept =
  confirmed): cal6's H=1000 expert judge, snake experts: best_v5bb 96/202 false, 40/42 kept -> v6/v6b 46/202, 38/42;
  150 disputes: snake 19/24 -> 9/24 (8/8 kept), PDF player 64/81 -> 36/81. Strength vs best_v5bb (paired): 1000 games
  +13.2k +- 5.0k, 32768 +3.1 +- 1.2 points; 32768-phase test score +7.4k +- 1.8k (vs v6 +4.2k +- 1.3k); 16384-phase
  63.6% (+0.95 +- 0.50 vs v6). Negative: exposed-cells penalty; deeper analysis search (depth 6: -13% false claims at
  ~15x cost, 60 vs 4 ms: optional deep mode at most); expert start pools (clean split: no gain); longer OTD run and
  t21+u0 averaging (no better than t21). Instance weights/late/ (53 GB) = mostly negative results; kept: bo_2.w (+
  pools; pull_all.sh copies only these). Shared code (additions only): engine.h --exposed-pen + view flags, game.h
  g_map_safe_gap, search.h downgrade_view_safe_all.
- **HM2 DONE (2026-10-07 ~02:30; results/hm2/REPORT.md):** analyze with `--skill THETA` (or `--personal T`,
  converted): per move `find_prob` (human move model: how likely a player of that skill plays it; reviews use the
  recent moves), `player_skill`, per position `error_risk` = sum find_prob x your_cost and `hint` (error_risk >= the
  phase threshold, chosen with a new coach condition risk:R with human-model players from the coach's real starts:
  <= 512: 0.05 (gap closed 63-82%, 1.3-3.1 hints/100, gain/hint 0.06-0.12 vs warnings 0.10-0.16); 1024-2048: 0.08
  (23-47%, 0.8-2.8/100, 0.04-0.09 vs 0.07-0.10); 4096-8192: 0.08 (12-20%, weak); none at 16384+). Real players would
  get ~2.7 hints/100 (median novice), ~0 (intermediate/strong; up to ~10 for a few). Reviews: hints, hints_per_100,
  hard_moments (error risk >= 1% and the best move found < 20% by players of that skill; real players meet 0.2-6 per
  100 moves and find 2-28%) and hard_found. Skill by the human model (`skill`, per phase, 80% CI): split-half
  reliability 0.84 / 0.81 / 0.87 / 0.75 (phases 0-3) vs softmax t -0.05 / 0.59 / 0.12 / 0.60; same tier separation.
  Mapping theta directly to the personal key FAILED (simulated players at a real intermediate's theta reach 2048 in
  3% of games: they compound errors real players repair) -> theta -> t (log-linear, phases 0-1) -> the existing skill
  map; out of fold vs reviewed t: 2x log-loss 0.262 vs 0.292, 4x 0.482 vs 0.542 (both n.s.; at least as good, far
  more reliable). INSTALLED weights/calib/personal.txt = results/calib/personal_v4_hm2.txt (pthetat, pthetamap,
  phint lines; v3 kept as personal_v3_installed_before_hm2.txt). Late refit on v6b values: the engine's SEARCH loss as
  the late value input (held-out log-loss at sums >= 20480 0.799 -> 0.769; >=15% moves at 16384+ predicted 3.06/100 vs
  observed 1.50, was 4.03); wv_late used only where analyze passes search losses (playouts unchanged). Selftest 16/16.
- Coordinator 02:05: block-table positions now explain block-breaking moves ("breaks your block: the exact tables no
  longer apply after it (up keeps a 100% chance to build the tile your block needs next)"; scorecard's 11/450 missing
  reasons); losses unchanged (value-map fallback). calib.h lossmap_table_played + table_real_loss(.., played) hook for
  cal7 (played moves in table positions in reviews). Selftest 16/16.
- pdf 02:50, stretch assessment (results/pdf/report.txt section 10): a BLOCK-FORMATION PLAYER (block lock + block
  tables in TD training, synthesised block starts) is ~2 h of engineering but a multi-day project in iterations;
  chance to beat v6b's 63.6% 16384-phase rate within ~12 h ~5-10% (the test starts from snakes and the tables value
  only a completed block, not the conversion; our snake play beats macroxue in snake positions; today's two cheap
  block-play probes failed: gradient + tables 12%, block lock 47%) -> NOT run in this window. For analysis, block
  positions are handled (tables where they apply, abstention elsewhere: ~13/105 false claims left). Running: v6b +
  block tables (p >= 0.5) safety check on the phase tests (3 seeds ph16 + p32, paired with late's v6b runs).
- **CAL7 DONE (2026-10-07 ~03:00; results/cal7/REPORT.md): EXPERT PUZZLE RESOLVED + odds v7 for best_v6b.**
  INSTALLED weights/calib/model.txt = results/calib/model_v7_cal7.txt (md5 27387cf6; previous model_before_cal7.txt).
  (1) The low end of the old top / played-expert maps was a MEASUREMENT ARTIFACT (always comparing with the luckiest
  of several noisy rollout means): re-measured on 200 unselected top-stage decisions with 128 playouts against a FIXED
  reference move, played moves rated up to 3% worse cost ~0%. (2) From ~6% claims, an expert's move costs about the
  claim when the ENGINE continues (6-10% -> 6.7%, 10-20% -> 11.4%), but these losses do NOT compound for the expert
  (they would leave a median 19% of the chances in 16384 stretches all of which reached 32768; the next position's
  value recovers 35-55% of the claim): the engine undervalues the expert's position and then plays it worse than the
  expert - the loss measures the engine taking over, not the player. (3) New review maps for a player's OWN 16384+
  moves: lossmap_played_expert 0 below a 10% claim, 20% -> 2%, 30% -> 5%, 45% -> 12%, and the same shape as
  lossmap_table_played (table positions); alternative moves keep the measured top map (low end zeroed); warn
  threshold at 16384+ 0.05 -> 0.20. Acceptance (scorecard rerun, results/scorecard/now.txt, compare.txt): experts'
  16384 stretches R 93 -> 2.5 (kept 0.010 -> 0.66; full engine + tables R 3.09, kept 0.54; start of night R 3.5);
  snake-expert blunder calls false alarms 46/175 -> 8/175, detections 45/52 -> 19/52 (by design: own cost, not the
  engine's continuation); drift check passes; expert tier best/good 88.8% -> 99.3%, inacc/mist/blund 8.51/1.54/1.14 ->
  0.36/0.14/0.10 per 100. (4) Odds v7: base rates from v6b's 1000-game benchmark + 2,898 new v6b games, 8192/16384
  slopes refit on real positions, 32768 synthetic; P(32768) truth with v6b continuing +4 to +6 points vs v5 on the
  same positions; held-out (160 new 16384-phase positions, results/cal7/truth4) log-loss 0.764 -> 0.737, MAE 0.148 ->
  0.145; fresh board P(32768) 0.592 -> 0.609 (benchmark 0.629); no 65536 target (0 of 3,898 v6b games reached it).
  Open: tight 16384-phase positions still pessimistic (0.39 vs 0.47; only 6 players reach 16384). Fixed
  fit_lossmap2.py --heldout --compare (always scored two-stage) + new --fixed-ref (unbiased) mode.
- Coordinator 03:10: reviews add `real_loss_engine` for the played move when it differs from real_loss (its cost if
  the engine took over: the alternative moves' maps), as cal7 suggested; docs/guide.md + api.md updated for cal7's
  expert maps and the 16384+ warn threshold 0.20. Selftest 16/16.
- **HM3 DONE (2026-10-07 ~04:00; results/hm3/REPORT.md): personal odds v5 INSTALLED** (weights/calib/personal.txt =
  results/calib/personal_v5_hm3.txt; previous personal_v4_installed_before_hm3.txt). Diagnosis: not move-level care
  (danger terms do not improve held-out move log-loss: 0.7636 vs 0.7642-0.7648) but STRETCH behaviour: simulated
  players reach <= 2 empty cells 1.5-4x as often as real ones and recover to 4+ empty cells within 10 moves far less
  often (0.33-0.51 vs 0.72 for real intermediates at <= 512); on 1,661 real tight positions the model at the tier's
  skill recovers 0.10-0.17 less often than the real players did. Fix = care in danger in the playout policy (messy
  human policy :dq= :de= :dm=): on boards with <= 2 empty cells, the best depth-2 move that keeps the largest tile in
  its corner (the plain engine move destroys the human structure), with probability q(key) = 1 for keys <= 0.015, 0
  for keys >= 0.02 (planning for novice-level keys collapses AUC). v5 vs v4 on real outcomes (game-clustered 90%):
  2x log-loss 0.426 -> 0.328 [-0.143, -0.055], 4x 0.594 -> 0.472 [-0.198, -0.051], AUC 0.864 -> 0.879; review path
  (theta -> t): -0.043 / -0.164, AUC 0.819 -> 0.867 / 0.844 -> 0.897. Calibration 2x: intermediate 0.80 -> 0.87 (obs
  0.96), strong 0.58 -> 0.66 (0.83); 4x strong 0.42 -> 0.52 (0.76); novices 0.642 -> 0.613 (0.585; log-loss +0.04 /
  +0.13 n.s., all from one game). Caveat: the ramp was chosen on the validating games. Coordinator: PersonalModel
  reads `pplan LO HI DE DM` (plan_q), analyze's --personal-playouts fallback plays care in danger like messy (checked:
  playouts vs model 1.00/0.94/0.77/0.33 vs 0.98/0.95/0.71/0.25 on a 512 board at T=0.03); guide updated. Option not
  taken: key_of_theta via the direct theta map (same overall gain, better novice calibration 0.62 vs 0.68; obs 0.58).
- PITFALL 04:15 (anypos): the instance's shared ~/2048/weights has no best.cfg and no calib/ (both were installed on
  the laptop only) -> instance jobs with plain `--preset best` ran best_v5, and analyze there had no maps unless
  given --calib. Checked: scorecard "now", integ's revalue, cal7's v6b truth and late2's play runs pass explicit
  weights; asked review and late2 to verify their instance jobs. Push best.cfg + calib to the instance after the
  running jobs end.
- **REVIEW VALIDATION DONE (2026-10-07 ~04:45; results/review/REPORT.md):** 100 real stretches (<= 300 moves, 64
  players, 4 tiers, block stretches excluded), reviewed with best_v6b + installed models; truth: engine playouts
  (32 x H=1000, 1,885 positions) and the human move model at the player's skill to the next tile (256 playouts on all
  1,107 flagged moves + 1,000 random ones; rms noise 0.04). Non-expert ("big loss" = >= 20% of the player's own
  chances): novices - key moments 30% big losses, warnings 43% (unflagged 2.4%), flagged moves hold 80% of the
  measured loss, but recall ~1/3 of the individual big losses [0.20-0.55]; intermediate/strong - big losses ~3 and ~1
  per 10,000 moves, flags find ~none; your_cost vs measured (3-10% bin): novice 4.5 vs 12.8%, intermediate 4.0 vs
  2.0%, strong 4.9 vs 1.3% (rank corr 0.49 / -0.06 / 0.06) -> rough above novice level. Warnings in exact-table
  positions were false alarms (220/731 warnings; 8% cost >= 10% = the random rate; table losses of 0.1-5% triggered
  them); 60% of key moments < 3% weight = noise; the decisive moment holds (10/15 real >= 10%, novices 7/7); hints
  work for novices only; hard moments cost ~0 (-0.4%). Experts (engine truth): key moments / warnings real (29% /
  32% lose >= 10% vs 1.6% random, Spearman 0.47), decisive moment real (>= 3%) in 9/11, but claims of 20-40% are
  shown ~7% vs 24% measured with the engine continuing. APPLIED by the coordinator: (P1) table-position warnings
  need the table's own real loss >= 10%; (P2) key moments below 3% weight dropped; (P5) hints only up to 512
  (personal.txt phint 0.05 -1 -1 -1 = results/calib/personal_v5b_review.txt; previous personal_v5_before_review.txt);
  guide: "what a review can be trusted for". Open: (P4) your_cost by skill band (256-playout truth in
  results/review/stage2_measured.json); (P6) expert played-move map closer to the engine-continuation loss above ~20%
  claims, checked against the game-level R.
- **CAL8 DONE (2026-10-07 ~05:10; results/cal8/report.txt):** (P4) your_cost by skill band on the review's
  256-playout player-level truth (1,183 non-reference moves): novices (human-model skill theta < -0.5) measure ~3x
  the phase map (10-15% value loss -> 14.8% vs map 3.5%; 25-40% -> 34.7% vs 12.6%), the upper band ~0 up to 15% in
  phase 0 (theta separates novices from the rest, not intermediate from strong: medians both -0.14); held-out by
  player RMSE x100 8.20 -> 7.70, bias on >= 3% estimates -0.029 -> -0.003, rank corr 0.14 -> 0.28 (truth playouts lack
  care in danger: upper bounds). model.txt (results/calib/model_v9_cal8.txt; previous model_before_cal8.txt) gained
  own_split -0.5, lossmap_own_lo 0, lossmap_own_hi 0/1/2; coordinator wired them in (Calib::own_cost(x, phase, theta),
  analyze your_cost uses player_theta: --skill or --personal T; reviews without --skill keep the phase map; check: a
  10% move at a 512 board costs 4.1% at theta -1.0, 0 at theta 0.5, 1.0% without a skill). (P6) the expert played-move
  map's top end: raising it (30% -> 8-10%) passes the game check only with a shrunk table-played map, adds false
  alarms and no detections; R rests on 5 stretches (+-0.7) -> KEPT cal7's map; the 20-40% gap is the engine-takeover
  loss, reported as real_loss_engine. Out of scope: experts' 4096-8192 stretches show R 17 under the late map (4
  stretches) - the late map may be inflated for experts' own moves below 16384 too.
- late2 05:15 (interim): annealed stage 0 (OTD continuation of s0cpu) gives no gain in the 16384 phase: 62.81% vs
  v6b 63.62% (2,100 paired games, -0.81 +- 1.02) -> rejected for play and analysis. OTD stage 1 training (to be tested
  with the leaf view off, since stage-1 leaves are normally valued by s0cpu) finishes ~05:25.
- **PLAN VALIDATION DONE (2026-10-07 ~04:50; results/plan/REPORT.md):** 2,000 real positions (80 per plan type x
  stage), predicted event checked in the engine's continuation (best_v6b + tables, 1,804 positions) and the real
  player's. Found: "merge the X into it" contradicted the best move in 175/336 merge positions (engine merged 35-56%);
  up to 512 the engine's best move leaves the plan's corner in 31% (players 2%); the experts' "pair" shape (32768 next
  to a corner holding a 16384) got "get your biggest tile into a corner" (done 3% by players); 65536 boards read the
  compressed ranks ("completes your chain below the 65536", 3.5% of 16384+); "single" was vague; the named cell was
  right only 50% (engine) / 61% (players). Fixed (explain.h ex::plan_info + text; real tile values for the cut and
  claims; orientation = longest chain after the cut; new "pair" plan; off-path equal tile -> merge, bigger head start
  -> grow there; merges are orders only when the best move makes them, else "can merge into it (the engine prefers
  down first)" - merged within 30 moves 98%; early-corner note up to 512). After: predicted event happens engine 0.69
  -> 0.73, players 0.79 -> 0.86 (16384+: 0.60 -> 0.81 / 0.57 -> 0.86); needed tile first in the named cell 0.50 ->
  0.59 / 0.61 -> 0.67. New JSON `plan_info` (documented in api.md). Fuzz recheck clean. Open: "get your biggest tile
  into a corner" below 8192 rarely happens within 30 moves; ~40% of builds use the other cell next to the chain end;
  "blocked" is weak.
- **ANYPOS DONE (2026-10-07 ~05:20; results/anypos/REPORT.md):** odds on odd-but-legal boards (set A 504 boards, 12
  categories x 7 stages; set B 300 boards incl. 3 unseen categories; truth 64 best_v6b playouts per board to the next
  1-2 doublings; 790 real truth positions as the no-harm check). MAE installed odds, sane vs odd formations: <= 1024
  <= 0.006 / <= 0.017; 2048 0.008 / 0.064; 4096 0.014 / 0.151; 8192 0.036 / 0.290; 16384 0.110 / 0.367 -> up to 2048
  every shape is fine (the engine repairs it); from 4096 odd shapes are OVER-predicted (8192 "center" 0.86 vs 0.38
  measured, "two corners" 0.96 vs 0.29; 16384 "scattered" P(32768) 0.41 vs 0.005): the late networks never see broken
  late formations. A steeper value term would fix odd boards but worsens real tight positions -> dropped. Formation
  correction (ocorr lines: exposed cells beyond 2, biggest tile 2+ steps from its corner on a crowded board, stranded
  big tiles; zero in the range real games occupy): set A leave-category-out MAE 0.096 -> 0.087, real positions
  unchanged (0.094), set B 0.101 -> 0.098. Main deliverable: `odds_caveat` (from a real 4096: 3+ exposed cells, 2+
  trapped tiles, biggest 2+ steps from its corner with <= 6 empty, stranded big tiles, from 8192 biggest out of its
  corner): fires on 86% of odd boards >= 4096, 12% of sane ones, 18% of real truth positions (flagged MAE 0.168 vs
  0.077). INSTALLED model.txt = results/calib/model_v8_anypos.txt (+ ocorr; previous model_before_anypos.txt);
  coordinator applied results/anypos/anypos_odds.patch (calib.h ocorr / shape_shift, analyze odds_caveat + JSON +
  summary sentence "Odds are less certain here: this formation is unusual for the stage."); verified on
  01201000bda11c10: P(16384) / P(32768) 0.855 / 0.305 -> 0.61 / 0.104 (measured 0.36 / 0.23), caveat true.
- **EXPL DONE (2026-10-07 ~05:45; results/expl/REPORT.md): reasons are now checked per position.** 1,000 real
  positions -> 646 worse moves (real loss >= 3%; corner-lock moves apart), 3,251 reasons; counterfactual edit per
  reason (remove exactly the stated defect in the afterstate, re-evaluate at depth 2, depth 3 as a check) vs placebo
  edits. Before: chain_len / danger / "lets the next tile end the game" near-complete (median share 0.9-1.0); corner /
  chain / "is riskier" partial (~0.36); trapped = placebo (0.25 vs 0.25); missed_merge barely above placebo; exposed /
  center / toward_corner often wrong (0.12-0.19, the edit makes it WORSE in 36-39%); the first reason was the biggest
  cause in only 44% ("is riskier" first 321 times, chain_len never). Fix (src/expl.h, analyze reasons()): every reason
  of a move with >= 3% value loss must recover >= 10% of the loss in that position or is dropped, the rest sorted by
  share (JSON "share"); "trapped" removed; fallback order area -> later -> shape. After: 3.4 reasons per move (was
  4.6); first reason median share 0.46 -> 0.62 (>= half of the loss in 68%, was 45%), biggest cause in 93% at depth 3
  (was 43%); edits that worsen 0-2%; engine playout check (32 x 300 moves, CRN): first reason median share 0.70 ->
  0.82, explains >= half 65% -> 74%; latency p90 28.7 -> 15.6 ms, p99 317 -> 199 ms. Weak spot: "center" as first
  reason (6 pairs, median -0.69 in play). No missing concept. ALSO FOUND: the anypos odds correction was NOT
  symmetric (far_of breaks ties between equal big tiles by cell order: a board and its mirror gave P(16384) 0.071 vs
  0.026) -> coordinator: far_sym = min of far_of over the 8 symmetries (fuzz recheck on both board sets: sym_odds 0,
  only the known "16 distinct tiles = not a board").
- Coordinator 06:00: reviews no longer report the human-model skill from 16384+ moves (an expert's late-game reading
  came out below a novice's: the move model over-predicts big late errors and the engine misjudges strong players'
  late moves); the whole-game skill uses moves below 16384 only (>= 50). Sample outputs for the user:
  results/samples/ (README.md, positions.txt, review_{nov00,int01,str01,exp01}.txt).
- **FINAL SCORECARD (2026-10-07 06:15; results/scorecard/final.txt, compare_final.txt = start vs final):**
  robustness 15 -> 16 of 1,800 (noise level); loss-map RMSE x100 13.0 -> 11.7 (early 6.4 -> 4.2, late 6.9 -> 6.3, top
  19.2 -> 17.3); raw claims > 10% false on refuted expert disputes: block player 67/85 -> 6/85 (+32 abstained), snake
  experts 22/27 -> 12/27 (10/12 confirmed kept); snake-expert review blunder calls: false alarms 8/229 -> 8/175,
  detections 22/54 -> 19/52; odds on 200 fresh real positions MAE 0.100 -> 0.066, log-loss 0.442 -> 0.311 (tight
  0.128 -> 0.079); fresh board P(32768) 0.582 -> 0.609 (benchmark 0.629); personal odds vs real outcomes 2x log-loss
  0.648 -> 0.324, AUC 0.770 -> 0.880, mean predicted vs observed 0.554 -> 0.752 (0.870 observed); 4x 1.379 -> 0.472,
  AUC 0.616 -> 0.827; game-level check (experts' 16384 stretches) R 3.5 -> 2.5; tiers best/good novice 98.1%,
  intermediate 99.9%, strong 96.2 -> 99.6%, expert 99.4 -> 99.3%; invariants 0/5 (the known 16-distinct-tile boards
  and the 65536 rank collision) with and without tables; latency p50 / p99 with tables 1.9 / 27.9 -> 1.5 / 18.1 ms.
  (fuzz_check.py / scorecard_invariants.py: in table-decided positions a move within 2 table points of the best needs
  no reason - analyze explains such positions by the table.)
- **PDF DONE (2026-10-07 06:30; results/pdf/REPORT.md):** block tables safe in the final engine at p >= 0.5: v6b
  16384 phase 63.62 -> 63.67% (paired +0.05 +- 0.25), 32768 phase 272,731 -> 273,029 points (+298 +- 724); at p >= 0
  they slightly hurt our own play (61.57 vs 62.57%, one seed). Death within 1000 moves from the block player's 32768
  positions 75.6% -> 66.9% (macroxue 46.7%). On unselected block-player positions, claims on the expert's own move
  18 -> 7 of 183. The tables' verdicts agree with macroxue's in all 74 table-decided disputes where it finds a
  significant difference. Failed: gradient heuristic + block tables (12% vs macroxue 70.6%), block lock (47%).
  Block-formation player NOT recommended in this window (5-10% chance in 12 h; multi-day project). For v6c: one
  16384-phase seed of v6c + block tables paired with late2's run would confirm neutrality (block-table moves were
  0.08-0.16% of our moves; watch for drift into block shapes).
- **NEW BEST PLAYER best_v6c (late2, 2026-10-07 06:45; results/late2/REPORT.md):** = best_v6b with stage 1 = OTD
  network weights/late2/s1o_3.w (optimistic init, TD 0.1 x 12M -> 0.01 x 6M -> 0.001 x 3M, tables in the loop,
  corner lock 14, starts weights/v11c/pool16.bin, bootstrapping from bo_2) AND the leaf view limited to sums below
  20480. Flags on top of preset_best: `--weights weights/late2/best_v6c.w --leaf-view-max-sum 20480` (md5 prefix
  95c6bf08e114, laptop + instance; built by splice_stage.py weights/best_v6b.w 1 weights/late2/s1o_3.w 0 ...).
  1000-game benchmark (paired with v6b, results/bench/late2_v6c): 586,082 +- 6,569, 16384 95.4%, 32768 64.0%, 65536
  0.1% (one game, 1,313,348 points) vs v6b 572,948 / 95.4 / 62.9; paired score +13,134 +- 3,569, 32768 +1.10 +- 0.71
  (811 of 1000 games identical); 1.55 ms/move. 16384 phase 64.90% vs 63.62% (+1.29 +- 0.60; with the leaf view OFF the
  new stage 1 LOSES ~1.2 points); 32768 phase score +3,106 +- 1,608. Claims unchanged or marginally better (disputes
  false > 10% 27 vs 28/105; expert judge false calls 54 vs 57/257, confirmed 39/47 both). v6c + block tables p >= 0.5:
  +0.29 +- 0.40 (700 paired games), block-table moves 0.14% -> neutral. Findings: STAGE 4 IS NEVER USED (4.05M
  replayed moves of v6b's benchmark: 7 moves; the root downgrade sends the whole 32768 phase to stages 0-3: stage 0
  18%, stage 3 37% of 32768+ moves) and stage 1 was unused before (the leaf view handed its leaves to s0cpu); stage 0
  annealing (TD <= 0.003 safe, 0.01 wrecks it) gives nothing in play (-0.04 +- 0.53 early, -0.81 +- 1.02 16384 phase)
  and early claims do not depend on the network (below ~30% value loss the rollouts measure ~0 whatever the network).
- **ENGINE SWITCHED to best_v6c (2026-10-07 06:50):** weights/best.cfg = `--weights weights/late2/best_v6c.w
  --leaf-view-max-sum 20480`. The model is UNCHANGED (md5 a4a87be0 = model_v8_anypos + cal8 lines; copy
  results/calib/model_v6c.txt; previous model_before_v6c.txt): switch_engine.sh prepare v6c re-valued the 53 judge
  files with v6c (results/integ/switch_v6c.log), but the installed top map is better held-out than a refit (17.26 vs
  17.89), the played-expert map is cal7's game-consistent one by design (a refit would undo it), and v6c's values
  differ from v6b's by <= 2% (vbar knot 15.0: x1.018; the script's factors are relative to the judge files' best_v5
  values, so applying them to the v6b-fitted model would double-scale) -> refit not applied
  (results/calib/model_v6c_refit_unused.txt). CAUTION for future switches: scripts/switch_engine.sh refits
  lossmap_played_expert and resets the warn line - do not run its refit blindly after cal7's maps. Human dataset
  re-valued with v6c running (results/human_ds_v6c) -> tiers and the final scorecard again.
- Final scorecard for v6c (results/scorecard/final_v6c.txt, compare_final_v6c.txt = start / final(v6b) / final_v6c):
  equal or marginally better than v6b everywhere (block-player false claims 6 -> 5 of 85; r15 odds MAE 0.138 -> 0.134;
  game check R 2.4; latency with tables p99 18.1 -> 13.2 ms); tiers on results/human_ds_v6c identical to v6b's
  (novice 98.1%, intermediate 99.9%, strong 99.6%, expert 99.3% best/good). 07:15: workstream serve started
  (compressed networks for cheap serving).
- **CAL9 DONE (2026-10-07 ~07:45; results/cal9/REPORT.md): odds for best_v6c.** New v6c data: P(32768) truth with
  v6c continuing on 340 real 16384-phase positions (truth4's 160 held out; v6c converts them only slightly better than
  v6b: 0.606 vs 0.590 on truth4) + 3,200 checkpoint games + v6c's benchmark. The FULL refit was worse held-out (truth4
  log-loss 0.718 -> 0.760: v6c values sums 20-30k 4-11% higher, raising the typical-value baseline; early base rates
  drifted) -> not installed. INSTALLED a hybrid: the current model + v6c's 32768 base rates at every stage + the
  expected-future line (weights/calib/model.txt = results/calib/model_v10_cal9.txt, md5 6a2ba392; previous
  model_before_cal9.txt a4a87be0): truth4 log-loss 0.718 -> 0.710, mean predicted 0.542 -> 0.569 (measured 0.606);
  other real sets 0.629 -> 0.627, predicted 0.552 -> 0.579 (measured 0.580); fresh board P(32768) 0.609 -> 0.632
  (benchmark 0.640); expected future from a fresh board 560k -> 577k (mean score 586k); P(16384) and lower and the
  near-dead board unchanged; no 65536 target (fit no better than a constant); the formation correction still helps
  (next-doubling log-loss 0.395 vs 0.450 without). Scorecard prep: r15/r15b now use cal9's v6c truth, truth4 added
  as a held-out P(32768) set (scripts/scorecard_prep.py / eval / compare); scorecards start / final_v6c / final_cal9
  re-run (results/scorecard/compare_final_cal9.txt).
- Rescored with v6c truth (results/scorecard/compare_final_cal9.txt: start / final_v6c / final_cal9): P(32768) on
  real 16384-phase positions - r15+r15b (fit sets) MAE / log-loss 0.163 / 0.711 -> 0.130 / 0.629 -> 0.133 / 0.627;
  truth4 (160 positions no fit saw) 0.136 / 0.684 -> 0.138 / 0.702 -> 0.137 / 0.694 = NO held-out improvement in
  P(32768) since the start (only 6 players reach 16384; the P(16384) gains are real: truth3 0.100 -> 0.066). Fresh
  board P(32768) 0.582 -> 0.609 -> 0.632 (v6c benchmark 0.640). Everything else unchanged by cal9.
- **SERVE DONE (2026-10-07 ~08:15; results/serve/REPORT.md):** only 30.8% of best_v6c's 671M weights were ever
  trained (stage 4 entirely untrained = one constant); stages 1-2 never use rank 15 and stage 0's rank-14 entries are
  never read (the leaf view lowers 16384s below sum 20480) -> re-indexed bases 14/15/15/16 (caps must follow actual
  lookups: tightening stage 3 to 15 changes answers). Packed formats (src/wpack.h, build/wpack_tool, engine flag
  `--packed FILE`, Evaluator::pnet; defaults unchanged): packed int16 753 MB (261 MB xz), 775 MB RAM (vs 1.35 GB), 0.9
  s load (vs 5.0), BYTE-IDENTICAL answers on 3,460 positions; int8 with escapes 384 / 146 MB, odds within 0.016, real
  loss within 0.0045, 6 of 12,131 warnings flip, play -0.48 +- 1.09 (16384 phase) / -1.14 +- 0.59 (early); stage-0-only
  int16 120 / 55 MB, 157 MB RAM: identical answers for every position without a 16384 and with sum < 20480 = 100% of
  novice / intermediate / strong positions in the curated data (experts 4.4%). Portable build (no BMI2) 2.3x slower.
  Recommendation: browser/phone = stage-0-only int16 (55 MB download, ~5 ms in WASM) + server for 16384+ positions;
  server = packed int16 + k6 in RAM (+ k5 / block tables on ~150 GB SSD). Repack after every engine switch
  (`build/wpack_tool pack weights/late2/best_v6c.w OUT --kind int16 --caps 14,15,15,16,c`) and verify with
  scripts/serve_compare.py. Packs in weights/serve/.
- **2026-10-07 08:16: INSTANCE STOPPED (all work done, everything pulled: scripts/aws/pull_all.sh at 08:13).**
  i-063910223f0247831 stopped after ~11 h of the 24 h cap (~$80 of compute instead of ~$173); the 500 GB EBS root
  volume is kept (k5 tables, block tables, 53 GB of negative-result networks in ~/2048/weights/late, workstream
  dirs ~/2048_*) at ~$40/month - delete it if not needed (or start again: scripts/aws/start_stop.sh start; NOTE the
  24 h auto-shutdown was a first-boot user-data command and does NOT re-arm on a restart; the IP changes; the shared
  weights dir there has no best.cfg / calib). Samples regenerated with the final engine (results/samples/).
- **2026-10-07 ~09:55: AWS cleaned up (user approved):** instance i-063910223f0247831 (hpc7a.96xlarge, "2048-research")
  TERMINATED and its 500 GB root volume vol-09dbc9d919d652fd1 DELETED. Verified in us-east-2: no instances, volumes,
  snapshots or Elastic IPs left -> no AWS charges. Kept (free): IAM user claude-2048, key pair claude-2048, security
  group <security-group> (SSH from the user's IP), the HPC vCPU quota (192). A new research machine = 
  scripts/aws/launch.sh (+ setup_remote.sh, push.sh, remote_init.sh recomputes the k5 tables; push weights/pdf or
  rebuild with build/block_tool). Next phase: the APP (app/, started 2026-10-07 ~09:50); the user provides domain,
  hosting budget and name after v1 is built; LLM explanations deferred.
- **APP v1 BUILT (2026-10-07 ~11:20; app/README.md, app/DECISIONS.md, app/qa/REPORT.md, app/engine-patch/README.md):**
  "2048 Coach", local only (`cd app && npm start` -> http://127.0.0.1:8048/). Preact + Vite front-end (~19 KB JS gzip,
  Lighthouse 100 x4 on all pages), Node server without runtime deps (one resident `build/analyze --preset best-notables
  --packed weights/serve/v6c_i16.wp --stdin --stdin-player` worker, 775 MB, restart on crash/timeout; reviews as
  short-lived `--review --review-moves` processes; validation, size limits, per-IP rate limits). Screens: Play
  (landing; eval bar = engine odds of the next milestone; coach Off / Warn me (default) / Best move; warnings
  intercept warn=true moves with the cost, the main checked reason and the better move; opening hints; game over ->
  review), Review (summary cards, eval graph + cost panel, step-through, key moments, not-judged block positions),
  Analyze (palette editor, presets, paste, full analysis, plan on the board, play from here), History (localStorage),
  How it works; dark mode. Engine change (flag-guarded, defaults byte-identical, selftest passes): `--stdin-player`
  (per-request `skill=`, `hist=`) and `--review-moves` (reviews use the known moves; without it 0.7% of board pairs
  are ambiguous). QA: 12 Playwright journeys on the installed Chrome (phone 390x844 touch + desktop 1440x900), no
  console/network errors; 20 vitest + 13 node tests (client rules = engine rules on 3,000 boards); speed: analysis p50
  5 ms, one worker 260/s; review of 295 moves ~0.5 s. Gaps: engine odds sit near 100% for most casual games (personal
  odds would be the more useful main number - candidate for the polish pass), emulated Chrome only, no 16384+ review
  end to end, no undo / sharing.
- **APP v2 "WORKBENCH" (2026-10-10; app/DECISIONS.md v2 section, app/qa/REPORT.md):** the user's feedback on v1: undo
  (also after game over), the coach playing at various speeds (zoom to a late game / see how it plays on), sliding back
  through the game with the forward history replaced by new moves, accepting the coach's move without the arrow keys,
  Play + Analyze together, no history: "a very active dojo with on-the-fly analysis and experimentation". Built: one
  screen (app/web/src/screens/Dojo.tsx) on a line model (lib/line.ts: moves + new tiles + who moved + cursor + compact
  facts, 8 chars/position in localStorage; following the recorded move replays it, another move replaces the
  continuation; 9 s restore toast for 8+ replaced moves, new game, edited position) and a controller (lib/workbench.ts:
  analyses, autoplay, review). Modes Analyze / Coach / Play; verdict line with Undo after each move; clickable best-move
  arrow; timeline slider; autoplay per move below full speed, server batches at full speed (`POST /api/autoplay`, 24
  moves, the analysis' reference move = the panel's best move, client-chosen seed, every move checked); review in the
  panel counts only the player's moves (lib/summary.ts, the engine's formulas; level only with 90%+ own moves);
  editor on the board; shortcuts (`?`). Speed: Chrome fetch ~4.6 ms + engine ~3 ms + WSL pipe ~4 ms per analysis ->
  ~65 moves/s per-request, ~150/s batched (a Linux server would be engine-bound, ~300/s). QA: 15 journeys clean,
  Lighthouse desktop 100 x4, phone 97-99/100/100/100 (fixed a scrollbar-induced CLS 0.43-0.67 with
  scrollbar-gutter: stable + a self-scrolling panel); 34 web + 15 server tests pass (engine tests included).


## 2026-10-10 YOUR CHANCE (workstream yc, results/yc/REPORT.md; app v2.1)
The user's first playtest:

- **Finding 1.** The engine's odds of about 100% and its warnings did not react to bad human moves (a 4096 out of its
  corner: no warning, 98% for 8192).
- **Finding 2.** The coach's early moves ignore the corner.
- **Root cause.** Every number is engine-relative, including the personal odds (a function of the engine's value).

Ground truth (src/hv_tool.cpp `first`):

- Rollouts of the simulated human players (src/hplayer.h = messy's pFF policy: human model + care in danger) from 210
  real positions, 400 playouts per move.
- The corner is worth about 0 points at 64-128, 2-3 at 256, 5-6 at 512, 7-10 at 1024 and 17-20 at 2048, while the
  engine says 0.
- The engine keeps the corner in only 5/19, 5/17 and 10/22 positions at 64/128/256; from 512 on it does by itself.
- Its moves cost humans about 0 on average.
- 76 random moves from the start do not lower a human's chance of 2048 (600 playouts per move).

Model:

- Logistic n-tuple networks per key and stage (src/hvalue.h).
- TD lambda 0.95 with expected targets under the player's move probabilities, side samples 25%, no exploration (it
  polluted the habit features: -0.1 to -0.3 bias), 50% starts from 79k real positions with the players' histories.
- 100M updates per key (5 min, 16 threads) and a per-stage recalibration (`recal`).
- The chance after a move is multiplied by the survival share of the next tile (game-ending moves were under-rated).
- 6 keys, 0.0005-0.016; 0.02 dropped (the chance's skill is floored at the default -0.5).

Validation:

- Against the rollouts: means within 0.01-0.03; within-position move correlation 0.864.
- Real games (83k positions, 237 games): AUC 0.76 for intermediate players, 0.93 for strong ones. It is pessimistic
  for strong players (0.52 vs 0.70).
- The played move's chance cost predicts real outcomes beyond the position: -1.18 [-2.22, -0.44].

Thresholds:

- Inaccuracy 5% / 2 points, mistake 10% / 2 points, blunder 25% / 4 points.
- Warnings at 20% and 2 points: 0.3-1.6 per 100 real moves at the default level.

Engine (analyze):

- `chance` {target, now, best, skill, key}, plus `chance` and `chance_loss` per move.
- `warn` by the chance rule.
- `coach_move` / `coach_why`: up to 512, the human model at skill 0.5 among moves with real loss at most 0.5% and at
  most 1 point of chance; else the engine's move.
- `--chance-model` / `--no-chance`; selftest case 12.

Server: autoplay plays `coach_move`; reviews take `skill`; slimPly passes the chance fields.

App:

- lib/chance.ts (costs and classes); the bar shows your chance plus a mark for the engine's odds and the last move's
  cost; the verdict line, move list, warning sheet, timeline (plain scale), review graph and review summary (all
  client-side by your chance) use it.
- The How page is rewritten.
- An opening "Left the corner" habit note.

Tests: 37 web, 15 server, QA 15/15.

Files: src/hplayer.h, src/hvalue.h, src/hv_tool.cpp (Makefile target hv_tool), scripts/yc_*.py,
scripts/yc_train_family.sh, results/yc/ (gt1, fam1, REPORT.md), weights/calib/chance.hv.

## 2026-10-10 APP v3: GRADES (results/grades/REPORT.md, app/DECISIONS.md v3)

The user's second round:
- Simplify drastically: no player levels, no exact percentages.
- Grade moves as blunder / questionable / good-not-best; blunders are obvious mistakes such as taking tiles out of
  corners.
- Toggles instead of modes; one toggle hides it all.
- Real-time coach; much less text.
- Test thresholds in real situations: a 2048+ corner break and random keys must trigger.

Engine:
- `grade_moves`, per move: `grade`, `why`, `pick`, `hint_cells`, `fault_cells`.
- `warn` = the move is a blunder; the coach's generic "why" is gone.
- The your-chance model is off by default; selftest case 12 holds the sanity cases.
- Value-loss lines from a study comparing the default depth with depth 5 on 2,400 real positions: within 0.5% the deeper
  search picks the move about 1 time in 4; from 5% on, 2.4% or less early and 1.5% or less later. The pick temperature
  0.015 is fitted on the same data.
- Latency: p50 2 ms, p90 4 ms, p99 52 ms at the default depth; depth 5 is p50 123 ms, so Deeper was cut.

Checks (scripts/grades_check.py):
- corner breaks: 98-100% blunders from 512 on;
- random keys: 41-47% flagged, the first after 2-3 moves;
- strong players: 0.23% blunders (4,000 moves).
- A broken LCG in the QA journey (same key 11 times) once looked like a miss; it now uses xorshift.

App:
- Rewritten Dojo, plus MoveList, ReviewSheet, grades.ts; facts = the coach's move and the played grade (2 characters
  per position, fv 3).
- Removed: EvalBar, Timeline, EvalGraph, ReviewView, AnalysisView, MoveRows, chance/summary/skill.
- CSS 2443 -> about 1700 lines; JS 64 KB.
- Tests: 37 web, 15 server; QA 17/17; Lighthouse 100 everywhere.

## 2026-10-10 APP v3.1: THE COACH PANEL (app/DECISIONS.md v3.1)

The user's third round:
- Space played with the coach off.
- "Coach plays" belongs at the bottom of the right panel.
- The Coach toggle should be prominent and tied to the panel.
- Reasons as an option.
- Highlights' description was lost.
- Odds as cards with a bar.

Done:
- Panel header with a big Coach switch; off folds the panel.
- Option rows with descriptions: Best move / Explain (new: per-move reasons + plan) / Warn me / Highlights.
- OddsCards; the autoplay row at the bottom of the panel.
- Space and P are guarded with the coach off.

Checks: QA 17/17.

- **2026-10-11: public repo.** https://github.com/ryanfuruness/2048-coach (MIT, branch main). Commits use the GitHub
  noreply email (repo-local git config).
  - Left out by `.gitignore`: `.env` and keys, `weights/` (the serving files go in a GitHub Release at deploy time),
    `build*/`, run outputs (`results/` keeps `*.md`), and `data/` (the YouTube human-games dataset, by the user's
    choice).
  - AWS resource IDs were redacted. The live values are in `scripts/aws/env.local.sh`, which is not committed.
  - Commit and push as the deployment proceeds.
- **2026-10-11: LIVE at https://2048coach.com.**
  - Server: netcup VPS (EPYC Genoa, 4 GB, US East), Caddy + systemd. Domain at Porkbun.
  - Everything is in `deploy/` (README, setup.sh, push-weights.sh, the unit, the Caddyfile).
  - Checked live: the 19 journeys, Lighthouse, a reboot, and that a spoofed X-Forwarded-For is ignored.
  - Open: AAAA records (IPv6 untested), a snapshot, uptime monitoring.
