# 24-hour run: workstream rules (coordinator: main thread; written 2026-10-06 21:45 +04)

Instance i-063910223f0247831 (hpc7a.96xlarge, 192 cores, 740 GB) STOPS by itself at ~21:15 +04 on 2026-10-07
(= 17:15 UTC, the instance's clock). Never stop, start, reboot or relaunch it; never launch other instances.

| ws | what | instance dir | cores | laptop build dir | owns (may edit) |
|---|---|---|---|---|---|
| mx | macroxue as an independent judge of expert positions | ~/2048_mx (+ ~/macroxue) | 32 | build_mx | scripts/mx_*, results/mx/ |
| late | expert-level late game: engine fixes, late networks | ~/2048_late | 96 | build_late | src/search.h, src/play.cpp, src/train.cpp, scripts/exp_late_*, scripts/bench*.sh, results/late/, weights/late/ |
| coach | does advice help players recover? | ~/2048_coach | 16 | build_coach | src/coach.cpp (new), its Makefile target, scripts/coach_*, results/coach/ |
| cal6 | calibration at scale | ~/2048_cal6 | 48 | build_cal6 | src/calib.h, calibration parts of src/analyze.cpp, scripts/fit_*, scripts/calib_*, scripts/study_*, scripts/judge_*, scripts/human_tiers.py, weights/calib/, results/cal6/ |

Rules for every workstream:
1. Shared code (src/engine.h, board.h, ntuple.h, game.h, explain.h, messy.cpp, rollout.cpp, ...): additions only (new
   functions, new flags). Default behaviour must stay exactly as it is: the other workstreams build from the same tree
   and calibrate / judge with the default engine. Keep the build green: after editing a shared header, build at once
   (`make -j8 BUILD=build_<ws> <targets>`). Never edit a file you do not own without a strong reason; never edit
   NOTES.md, docs/ or README.md (the coordinator merges your REPORT into them).
2. Report: results/<ws>/REPORT.md, dated entries, newest last, concise, with the numbers (+- errors) and file paths
   needed to reproduce. Update it after every finished experiment, so nothing is lost if you are interrupted.
3. Laptop (20 threads, 7.7 GB RAM, shared by all): code, builds, quick tests, Python analyses. At most ONE engine
   process of yours at a time, never one that loads the tables (no `--preset best`, no endgame tables): heavy runs
   belong on the instance. <= 6 threads for laptop jobs.
4. Instance: `scripts/aws/ws.sh push|build|put|pull|run <ws> ...` (see the script header). Weights are shared via the
   symlink ~/2048_<ws>/weights -> ~/2048/weights (networks, k6 tables, the 88 GB k5 tables, pools): read-only, except
   new files under weights/<ws>/. Write outputs under ~/2048_<ws>/results/<ws>/ and pull them back
   (`ws.sh pull <ws> <ws>`) after each finished experiment. Stay within your core share (sum of --threads of your
   running jobs). Long jobs: `nohup ... > log 2>&1 &`; wait with background until-loops / Monitor on files, never
   `pgrep -f` a pattern that occurs in your own command line. If SSH times out, the user's home IP probably changed:
   add the new IP (curl -s https://checkip.amazonaws.com) to port 22 of security group <security-group>.
5. Secrets: never print or copy .env or ~/.aws.
6. Return to the coordinator when your plan is done, when you need a decision only the coordinator/user can make, or
   after ~6 hours, whichever comes first. Jobs may keep running when you return: say what runs, where its output goes
   and what to do with it. Final message: <= 30 lines with the key numbers and paths; details stay in REPORT.md.

Changes (coordinator):
- 23:35: coach FINISHED (results/coach/REPORT.md); its 16 cores -> late (share 108).
- 23:40: new workstream fuzz (4 cores, ~/2048_fuzz; owns scripts/fuzz_*, results/fuzz/; surgical bug fixes in the
  non-calibration parts of src/analyze.cpp, src/explain.h, src/engine.h): edge-case and invariant testing of analyze.
- Subagents may be refused when writing REPORT.md: notes go to results/<ws>/report.txt, the coordinator writes REPORT.md.
- 00:10: mx FINISHED (results/mx/REPORT.md, for_late.txt): 105/150 expert disputes are ONE player playing the 3x2
  block formation (PDF) -> our claims false there; macroxue's edge = exact block tables. New workstream pdf (32 cores,
  ~/2048_pdf; owns src/block.h-style new files, scripts/pdf_*, results/pdf/, weights/pdf/, additions to endgame.h /
  layered.h, a flag-guarded root hook in engine.h choose() and play.cpp next to the snake suggest). CLEAN-ROOM: never
  read macroxue's sources.
- 00:10: cal6 FINISHED (installed odds v6 + 3-stage maps + table map, personal v2; its jold recheck still runs on
  32 instance cores in ~/2048_cal6).
- 00:20: new workstreams:
  integ (8 cores, ~/2048_integ): owns src/analyze.cpp (all), src/calib.h, src/explain.h, scripts/serve.py, docs/,
  README analysis section, weights/calib/model.txt + the fitting pipeline (scripts/fit_*, judge_*), rollout.cpp and
  the reset in messy.cpp (after jold); block abstention/table claims, coach warnings + your_cost, block tables in the
  preset, the engine switch + refit (on the coordinator's word), docs.
  hm (24 cores now, +32 after jold, ~/2048_hm): human move model; owns scripts/hm_*, results/hm/, src/human.h,
  additions to coach.cpp / messy.cpp, weights/calib/personal.txt.
- 00:56: engine switched to best_v6b (weights/best.cfg + refit model.txt). integ FINISHED.
- 01:00: new workstream scorecard (16 cores, ~/2048_score; owns scripts/scorecard*, results/scorecard/; read-only
  elsewhere): one regression suite over all truth sets, "start" (v5, 21:00) vs "now" (v6b).
- 01:15: new workstream cal7 (100 cores, ~/2048_cal7): owns weights/calib/model.txt + the calibration pipeline
  (fit_*, calib_*, study_*, judge_*, switch_*); full odds refit for v6b with fresh data; the expert puzzle (low end of
  the top / played-expert maps with 128-256 playouts per move). src/calib.h and src/analyze.cpp: coordinator.
  hm installed personal v3 (human move model; "player human" line; analyze's playout fallback uses src/human.h).
- 01:20: hm FINISHED (personal v3 installed). 01:25: new workstream hm2 (40 cores, ~/2048_hm2): owns src/human.h,
  scripts/hm_*, weights/calib/personal.txt, and (for find_prob / error_risk / hint / human-model skill) additions in
  src/analyze.cpp and the PersonalModel part of src/calib.h; not model.txt (cal7).
- 01:45: late FINISHED (best_v6b final). 01:50: new workstream late2 (60 -> 90 cores, ~/2048_late2): owns
  src/train.cpp, src/play.cpp, src/search.h, scripts/exp_late2_*, results/late2/, weights/late2/; OTD stage 4 (32768
  phase) against v6b, then an OTD early network as an analysis experiment.
- 02:55: hm2 FINISHED (find_prob / error_risk / hint / human-model skill in analyze; personal v4). New workstreams:
  review (50 cores, ~/2048_review; owns scripts/review_*, results/review/; read-only elsewhere): validate game reviews
  against rollouts. hm3 (50 cores, ~/2048_hm3; owns src/human.h, scripts/hm_*, hm3_*, weights/calib/personal.txt):
  a human playout model that repairs like humans; personal odds v5. pdf: block-player stretch NOT run (5-10% chance).
- 03:00: cal7 FINISHED (odds v7, expert review maps). 04:00: hm3 FINISHED (personal v5: care in danger).
- 04:10: new workstreams: anypos (100 cores, ~/2048_anypos; owns scripts/anypos_*, results/anypos/, the ODDS lines
  of weights/calib/model.txt): odds on odd-but-legal positions. plan (30 cores, ~/2048_plan; owns scripts/plan_*,
  results/plan/, ex::plan() in explain.h, the plan output in analyze.cpp): is the plan right?
- 04:15 PITFALL (found by anypos): the instance's shared ~/2048/weights has NO best.cfg and NO calib/ -> on the
  instance `--preset best` = best_v5 and analyze runs without odds/maps unless jobs pass `--weights
  weights/best_v6b.w` and `--calib FILE` / `--personal-model FILE` explicitly. Do that in every instance job. The
  coordinator will push best.cfg + calib to the shared dir once the running jobs have finished.
- 04:45: review FINISHED (P1, P2, P5 applied by the coordinator). 04:50: new workstream cal8 (laptop, <= 8 instance
  cores): owns the loss-map / warn lines of model.txt (anypos owns the odds lines) + fit scripts; your_cost by skill
  band (P4) and the expert played-move map's top end within the game-level check (P6).
- 04:50: plan FINISHED (plan_info, fixed plans). 05:10: cal8 FINISHED (your_cost by skill band wired in).
- 05:00: new workstream expl (30 cores, ~/2048_expl; owns scripts/expl_*, results/expl/, the reasons code in
  explain.h (compare / strengths / concepts) and reasons() in analyze.cpp except the block/table branch): are the
  reasons faithful (counterfactual edits per reason type)?
- 05:45 expl FINISHED; 06:30 pdf FINISHED; 06:45 late2 FINISHED (best_v6c); 06:50 engine switched to best_v6c.
- 07:15: new workstream serve (laptop + 16 instance cores, ~/2048_serve; owns scripts/serve_*, results/serve/, new
  packed-weights files; flag-guarded additions in ntuple.h / engine.h): compressed networks for cheap serving.
- 07:10: new workstream cal9 (150 cores, ~/2048_cal9; owns the ODDS lines of model.txt + cal7's odds pipeline):
  odds refit for best_v6c with fresh v6c games and v6c-continuation truth.
