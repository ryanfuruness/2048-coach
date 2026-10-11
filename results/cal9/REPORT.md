# Workstream cal9: odds refit for best_v6c (REPORT)

Copied by the coordinator from results/cal9/report.txt.

```
cal9 notes (odds refit for best_v6c), 2026-10-07 - newest last
07:15 Jobs on the instance (~/2048_cal9, explicit v6c flags `--weights weights/late2/best_v6c.w --leaf-view-max-sum
  20480`; scripts/study_cal9.sh all, 7 jobs x 20 threads): P(32768) truth with v6c continuing on cal6's truth_r15 (120)
  and truth2_r15 (60) and cal7's held-out truth4 (160) real 16384-phase positions (32 playouts to 32768 or death);
  v6c lapse games (lapse16c / lapse32 / lapse32b, 800 each) + 800 clean checkpoint games, seed 901 (cal7's protocol).
  Fit: scripts/fit_cal9_odds.sh (base rates from v6c's 1000-game benchmark logs results/bench/late2_v6c + the s901
  rows; real slopes as cal7: r14 / t30 for 8192 / 16384 (unchanged by v6c: it differs only at sums >= 20480), r15 with
  v6c truth for 32768; truth4 held out).
07:35 Data done (instance ~25 min): v6c truth P(32768) on the same real 16384-phase positions as v6b's: truth_r15
  0.589 (v6b 0.589), truth2_r15 0.562 (0.556), truth4 0.606 (0.590) - v6c converts real 16384-phase positions only
  ~0-1.6 points better; lapse / clean checkpoint games s901: 46,959 rows. Benchmark (results/bench/late2_v6c, 1000
  games): 2048 0.998, 4096 0.996, 8192 0.987, 16384 0.954, 32768 0.640, 65536 0.001.
07:45 Full refit (scripts/fit_cal9_odds.sh -> results/calib/model_v10_odds.txt; fit log results/cal9/fit.log): base
  rates from the v6c benchmark + s901 rows; 8192 / 16384 slopes refit on real positions (player CV 16384 LL 0.304 ->
  0.287; 8192 0.181 -> 0.145); 32768 synthetic slopes kept (the real refit loses out of sample: 0.645 -> 0.703, 6
  players); 65536 target dropped (base rate 0.000, log-loss no better than a constant; as cal7). The FULL candidate
  (new vbar + all targets) is WORSE on real positions: held-out truth4 (v6c continuing) LL 0.718 -> 0.760, MAE 0.139 ->
  0.145 (tight lT4 0.841 -> 0.922: v6c's higher values at sums ~20-30k raise vbar by 4-11% at knots 14-15 and the
  steeper 32768 slope 2.04 -> 2.47 pushes real tight positions lower), r15 sets LL 0.629 -> 0.644, and its early
  base rates drift from the benchmark (2048 / 4096 0.996 / 0.993 vs 0.998 / 0.996).
07:55 Hybrids (installed model + parts of the refit), on v6c truth (P(32768); P(16384) and lower are unchanged by
  construction) and the fresh board (benchmark 0.640):
    model                                          truth4 (held out) LL / MAE / mean   r15 sets LL / MAE / mean   fresh P(32768)
    installed (cal7 v7)                            0.718 / 0.139 / 0.542 (meas 0.606)   0.629 / 0.130 / 0.552 (0.580)   0.609
    H1 new 32768 intercepts at knots <= 8192       0.718 / 0.139 / 0.542                0.629 / 0.130 / 0.552           0.632
    H2 new 32768 intercepts at all knots           0.710 / 0.138 / 0.569                0.627 / 0.133 / 0.579           0.632
    H3 new vbar + new 32768 line                   0.760 / 0.145 / 0.522                0.644 / 0.136 / 0.529           0.632
  -> H2 (installed vbar, slopes and all other targets; target 32768 intercepts and the expected-future ratio line from
  the v6c refit). Odd boards (anypos set A, truth with v6b continuing): neutral overall (two doublings MAE 0.052 ->
  0.053, LL 0.263 = 0.263), slightly more confident on odd 16384 boards (next doubling LL 0.624 -> 0.650; those carry
  odds_caveat); the formation correction still helps under H2 (without ocorr: next doubling LL 0.450 vs 0.395, two
  doublings 0.280 vs 0.263) -> kept unchanged. Expected future from the fresh board 560,539 -> 577,073 (v6c's mean
  score 586,082). INSTALLED weights/calib/model.txt = results/calib/model_v10_cal9.txt (md5 6a2ba392; previous
  results/calib/model_before_cal9.txt = a4a87be0; only the ratio line and the target 32768 intercepts differ); analyze
  --selftest 0 failures. Scorecard final_cal9 running.
08:15 Scorecard final_cal9 (results/scorecard/final_cal9.txt; compare: results/scorecard/compare_final_cal9.txt = start /
  final_v6c / final_cal9): everything identical to final_v6c except the 32768 odds: fresh board P(32768) 0.609 ->
  0.632 (v6c benchmark 0.640); the scorecard's "r15+r15b" row moves 0.134 / 0.618 -> 0.145 / 0.624, BUT its truth is
  cal6's (results/cal6/truth/truth_r15 + truth2_r15, measured with best_v5 continuing, which converts these positions
  4-6 points worse than v6b / v6c): on the same positions with v6c continuing (results/cal9/truth/) the installed
  model scores LL 0.629 -> 0.627 and its mean prediction moves 0.552 -> 0.579 (measured 0.580); held-out truth4 LL
  0.718 -> 0.710. Suggestion (scorecard owner / coordinator): point scorecard_prep.py's r15 / r15b truth at the
  installed engine's truth (results/cal9/truth/truth_r15.tsv, truth2_r15.tsv) and add truth4 (results/cal7/truth4.tsv +
  results/cal9/truth/truth4_r15.tsv) as a held-out P(32768) set. Robustness, maps, expert claims, personal odds, game
  check (R 2.4), tiers, invariants: unchanged. Nothing left running on the instance (~/2048_cal9 idle).
```
