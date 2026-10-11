# Workstream expl: are the reasons faithful? (REPORT)

Copied by the coordinator from results/expl/report.txt.

```
Workstream expl: are the analysis' reasons the real cause of a move's loss? (2026-10-07 05:00-, +04)

METHOD (scripts/expl_select.py, expl_build.py, expl_report.py; src/expl.h, src/expl_tool.cpp, make build/expl_tool)
- Sample: 1000 real positions (results/human_ds_v6b, curated set; stratified stage x tier; search-decided, not block)
  with a clearly worse move (per position the played move when it qualifies); re-analysed with the current analyze
  (--preset best = best_v6b): 708 (position, move) pairs with estimated real loss >= 3%, 3,251 reasons (4.6 per move).
  62 pairs are corner-lock moves at 16384+ (the engine distrusts their values: loss n/a) -> reported apart; 646 pairs.
- Counterfactual per reason: d's afterstate edited to remove exactly the stated defect, tiles conserved where possible
  (corner: the biggest tile swapped back into the corner it keeps after the reference move; chain: the lost chain tile
  swapped back into its cell; chain_len: the reference's chain order restored by swaps; exposed: each extra exposed
  cell gets the tile the reference has there, moved in from its nearest copy; center: the big middle tile swapped to
  the edge next to it; toward_corner: the biggest tile to the nearest corner; missed_merge: the two tiles merged; edge:
  the home-edge gap filled from the tile the reference keeps there; danger / space: the smallest tile(s) removed;
  trapped: the trapped small tiles removed; risk: the move made only as risky as the reference, i.e. the mass of its
  deadly / clearly bad next tiles reduced to the reference's share; area: the named 2x2 area copied from the
  reference's afterstate). Re-evaluated: afterstate value = mean over the spawns of the best move value at depth 2
  (and depth 3 as a check). share = recovered value / the move's loss. Placebo: the same kind of edit somewhere
  unrelated (the same tile to a random cell, the same filling at random cells, a random swap, random spawns).

BEFORE (fixed order, all concept reasons; 646 pairs, 2,956 reasons; results/expl/report_before.txt, depth 3:
report_before_d3.txt): share of the loss the edit recovers, median / >= 50% / edit makes it WORSE (<= 0) / placebo
median / edit beats placebo:
  chain_len  0.96 / 0.89 / 0.04 / -0.78 / 0.98      danger      0.91 / 0.91 / 0.00 /  0.35 / 0.98
  risk_dead  0.96 / 0.75 / 0.00 /  0.24 / 1.00      area        1.01 / 0.79 / 0.17 /  0.30 / 0.83
  risk_bad   0.37 / 0.34 / 0.00 /  0.00 / 0.99      chain       0.36 / 0.27 / 0.04 / -0.60 / 0.96
  corner     0.36 / 0.24 / 0.02 / -0.70 / 0.98      missed_merge 0.36 / 0.31 / 0.10 / 0.28 / 0.59
  edge       0.29 / 0.24 / 0.08 /  0.00 / 0.93      trapped     0.25 / 0.22 / 0.01 /  0.25 / 0.54  <- = placebo
  exposed    0.19 / 0.31 / 0.37 / -0.09 / 0.77      center      0.14 / 0.10 / 0.39 / -0.59 / 0.74
  toward_corner 0.12 / 0.21 / 0.36 / -0.14 / 0.67
  -> every type beats its placebo except trapped (removing the trapped small tiles recovers exactly as much as removing
  other small tiles: the effect is free cells, not trapping) and missed_merge (0.36 vs 0.28 for merging another pair);
  exposed / center / toward_corner make the position WORSE in 36-39% of their cases (the defect is not there in a way
  that costs anything). Ranking: the first-listed reason recovers most in only 44% of multi-reason pairs (chance 0.22)
  - the static order puts risk_bad first in 321 pairs (its share median 0.37) and never lists chain_len (0.96) first.
  First-listed reason: median share 0.46, >= 50% in 0.45. Depth 3 gives the same picture (0.45 / 0.44, rank 0.43).

FIX (src/analyze.cpp reasons(), src/expl.h, src/explain.h):
  1. Every reason of a clearly worse move (value loss >= 3%, the moves that get the expensive reasons) is checked in the
     position itself: the edit (xp::fix; risk: the reweighting) must recover >= 10% of the move's loss (depth-2
     values, the same evaluator), else the reason is dropped; the rest are ordered by that share. JSON: each checked
     reason carries "share" (0-1: how much of the loss removing that defect recovers). Moves with 2-3% value loss and
     reviews' non-played moves keep the cheap unchecked reasons (no "share"); corner-lock moves keep "moves your
     biggest tile out of its corner" (the engine's rule; their values are not trusted).
  2. "trapped" is no longer a reason (explain.h compare(): not specific, see above).
  3. Fallback order area -> later -> shape (was later -> area -> shape): the area reason recovers the whole loss in the
     median case (79% >= half), "a few moves later ..." cannot be checked by an edit.
  Cost: none measurable - on the 1000 sample positions (--preset best) analysis time p50 1.1 -> 1.3 ms, p90 28.7 ->
  15.6 ms, p99 317 -> 199 ms (the look-ahead fallback now runs less often); fuzz board set p50 3.0 ms, p99 26 ms.

AFTER (results/expl/report_after.txt, depth 3: report_after_d3.txt): 2,132 reasons (3.4 per move, was 4.6);
  first-listed reason: median share 0.62 (depth 3: 0.65), >= 50% in 0.68 (0.68); the first listed recovers most in
  100% of multi-reason pairs at the checking depth (by construction) and 93% at depth 3 (was 44%); edits that make it
  worse: 0-2% for every checked type (exposed 37% -> 0-1%, center 39% -> 0-2%, toward_corner 36% -> 0%); exposed's
  median share 0.19 -> 0.55. First-listed codes now: risk_bad 159 (was 335), corner 179, exposed 131 (41), chain_len 42
  (0), area 38 (24), danger 36, chain 21 (44), center 20, toward_corner 17. Pairs whose best reason recovers >= 50%:
  0.68 (unchanged: the fix reorders and prunes, it adds no new cause).

OUTCOME CHECK (independent of the checking evaluator; scripts/expl_roll_report.py, results/expl/roll.out): the engine
  plays on from the reference / the move's / the edited afterstate (32 playouts with common random numbers, 300
  moves + the network value at the horizon, best_v6b; instance ~/2048_expl, 30 cores, 8 min); pairs where the playouts
  confirm the loss (> 2 SE) and the first reason is a board edit (risk reasons cannot be played out as an edit):
  before: 98 pairs, median share 0.70, >= 50% in 0.65, edit hurts in 0.12, pooled 0.69;
  after: 201 pairs, median share 0.82, >= 50% in 0.74, edit hurts in 0.06, pooled 0.80;
  the 32 pairs whose first reason changed: median share 0.52 -> 0.98, the new first reason recovers more in 69%.
  Weak spot: "center" as the first reason (6 pairs) recovers nothing in actual play (median -0.69) although the depth-2
  check passed - small n, but center is the least reliable type; candidate: require share >= 0.3 for it.

EXAMPLES (first reason before -> after, share recovered at depth 2):
  pair 190 (expert, 4096 stage): "is riskier: 50% of the possible new tiles leave you clearly worse off" (0.03) ->
    "moves your biggest tile (4096) out of its corner" (all of it)
  pair 270 (strong, 1024-2048): "is riskier: 33% of ..." (0.02) -> "opens space next to your big tiles where a new small
    tile can get stuck" (1.00)
  pair 359 (intermediate): "pulls the 64 out of your chain (top-left corner)" (0.00) -> "lines up fewer of your big
    tiles in order (a chain of 3 vs 5)" (0.66)
  pair 340 (expert): "opens space next to your big tiles ..." (-2.13: filling that space is WORSE) -> "is riskier: 27%
    of the possible new tiles leave you clearly worse off" (0.56)
  still weak after (53 of 620 first reasons recover < 25%): e.g. "pulls the 32 out of your chain" (0.20), "is riskier:
    45% ..." (0.15) - partial causes; the loss is spread over the whole structure.

FOR THE LANGUAGE-MODEL LAYER (what is safe to verbalise):
  - A reason WITH "share" was checked in this position: say "mainly because ..." for share >= 0.5 (the first reason in
    68% of cases), "partly because ..." for 0.1-0.5; never present a lower-ranked reason as the main cause.
  - Near-complete explanations: chain_len, danger, risk "lets the next tile end the game" (median 0.9-1.0).
  - "area" is a location, not a concept ("the trouble is in the bottom-left, around your 256"): faithful (median 1.0).
  - "later" / "shape" are not causal claims: only "the engine's look-ahead prefers X".
  - Reasons without "share" (value loss 2-3%, reviews' non-played moves) are unchecked hints, not causes.
  - Corner-lock moves (16384+): the reason is the engine's rule, not a measured cost.
  - Do not invent causes from merge counts, free-cell counts or "trapped" tiles (not predictive / not specific).

NOT FOUND: a missing concept. Probing the 52 pairs no reason explains (>= 25%) with single-cell restorations points
  mostly at the arrangement of the second-tier big tiles away from the biggest one (19 of 52), not at one clean
  concept; the area reason covers those as a location.

OUT OF SCOPE, for the coordinator: the odds model installed at 05:09 (results/calib/model_v8_anypos.txt) is NOT
  symmetric: "4096 16 8 2 / 256 16 128 4 / 4096 32 16 4096 / 2048 32 512 2048" and its mirror image give P(16384) 0.071
  vs 0.026 (model_before_anypos: 0.114 both); fuzz_check now reports sym_odds on 6 + 32 boards (none before).

FILES: src/expl.h (new: the edits, xp::fix), src/expl_tool.cpp (new; Makefile target build/expl_tool), src/explain.h
  (Reason.share; no "trapped" reason), src/analyze.cpp (risk_gain, the check + ordering in reasons(), area before
  later, "share" in the JSON); scripts/expl_select.py, expl_build.py, expl_report.py, expl_roll_report.py;
  results/expl/ (sample*, after*, roll.*, probe.*, report_before*.txt, report_after*.txt, fuzz/). build/analyze
  --selftest 0 failures; fuzz_check on boards1/2: no reason issues (only the known error / reason_merge + the sym_odds
  above); latency fuzz p50 2.9-3.3 ms, p99 29-33 ms.
```
