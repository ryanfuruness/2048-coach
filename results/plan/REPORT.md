# Workstream plan: is the plan right? (REPORT)

Copied by the coordinator from results/plan/report.txt.

```
Workstream plan: is the plan right? (2026-10-07 04:10-~06:00 +04)

METHOD
- 2,000 real positions from results/human_ds_v6b/analysis.jsonl, stratified by plan type x stage (80 per cell; types
  merge / build / grow / blocked / single / no_corner / block; stages <=512, 1024-2048, 4096-8192, 16384+), with the
  players' own continuations (same video segment, up to 600 plies; scripts/plan_study.py sample) and the engine's
  continuations (best_v6b + tables, analyze "line=200" requests chained to each plan's horizon; 1,804 positions without
  a 65536+ tile; 30 shards on the instance, results/plan/run1/).
- Operational check per plan type (scripts/plan_lib.py events2): merge -> the chain absorbs a tile equal to its end
  within 10 moves; build/grow -> the needed tile appears in the NAMED cell or the chain absorbs it within ~3x the moves
  needed (10..600); blocked -> the blocker leaves the named cell; no_corner -> the biggest tile reaches a corner within 30
  moves; single -> the tile next to the corner grows within 200 moves with the corner kept; pair -> the same with the
  biggest tile staying next to the corner. Location precision (scripts/plan_location.py): when the chain's end has 2+
  candidate cells and the needed tile appears next to it, the share appearing first in the named cell. Consistency with
  the best move: does the engine's best move make the merge the plan names.
- Refactor first: ex::plan_info (structured plan) + ex::plan (text); text identical on 3,000/3,000 stored positions.

FINDINGS (before the fixes)
1. Where the plan types are checkable, players follow them: merge 0.98, build 0.89, grow 0.93, blocked 0.98 (all
   tiers; strong 0.97-1.00, intermediate 0.87-0.98, experts 0.77-0.99). The engine agrees less: merge 0.73, build 0.75,
   grow 0.68 (grow at 16384+ 0.53: mostly the 600-move horizon cap, 0.79 with an uncapped horizon), blocked 0.96.
2. Merge plans contradicted the best move: the plan said "Merge the X in W into it" while the engine's best move made
   that merge in only 35-56% of merge positions by stage (players' moves 69-85%); the engine otherwise waited (18-26%),
   merged the pair away from the chain (4-30%) or did something else.
3. <=512: the engine does not play the plan's corner strategy: its best move takes the plan's corner tile out of its
   corner in 31% of positions (players 2%; from 1024 on <= 1.3%); anchor kept after the horizon 36-40% (players 95-99%).
4. 16384+ "Get your biggest tile into a corner" was WRONG for the experts' pair shape (32768 next to a corner holding
   the 16384: 63 of 80 sampled 16384+ no_corner positions, all the block player): players move it to a corner 3%, the
   engine 13% - both build the twin 16384 instead.
5. 65536 boards: the plan cut stragglers on the engine's compressed ranks (65536 -> 4096 looked like a 3-rank gap): it
   chained the 65536 to a far smaller tile and claimed false completions ("the tail merges into a 16384, which completes
   your chain below the 65536") - 69 of 2,000 sampled positions, 3.5% of 16384+ ones.
6. "single" ("line up the next biggest tiles next to it", 19k positions) was vague, and the orientation was chosen by
   the uncut chain length, so a real chain in the other direction was missed (~2% of positions).
7. Location: of two possible cells next to the chain's end, the engine built first in the named one 50%, players 61%;
   when the off-path neighbour held a bigger head start the engine built there 63% (players 55%); an off-path equal tile
   (an available merge) was ignored.
8. Tight boards are not a problem: engine agreement by empty cells 0-2: 0.89, 3-5: 0.80, 6+: 0.65.

FIXES (src/explain.h plan_info / plan; src/analyze.cpp plan_text / plan_json)
- real ranks for the straggler cut, the collapse and the completion clauses (display_rank);
- the orientation with the longest chain AFTER the cut (tie with one tile: the bigger tile next to the corner);
- "single": names the chain running next to the corner ("Keep the 65536 in the top-right corner; your chain
  4096-1024-128-64-16-8 runs next to it. Grow the 4 in ... into an 8: ...") or the tile to build up ("... and build up
  the 64 next to it (bottom row, second column) toward a 1024");
- "pair" type: "Your 32768 sits next to the top-right corner, where your 16384 is: once the 16384 doubles, the two
  merge. Build up the 128 in the second row, right edge next to it into a 16384." (+ chain steps when there is a chain);
- off-path neighbour of the chain's end: an equal tile -> merge; a bigger head start than the small tile in the path
  cell -> grow there (an EMPTY path cell keeps the snake continuation: switching there did not help);
- merge only as an instruction when the best move makes it, else "The 64 in the top row, third column can merge into
  it (the engine prefers down first)" (the engine then merges into the chain within 10 moves 51%, within 30 moves 98%);
- <=512, when the best move takes the corner tile out: "This early the engine does not mind leaving the corner (its
  best move, left, does)." (players keep the corner 98% there: the plan stays the human strategy);
- JSON "plan_info": type, step, chain cells + tiles, corner_cell, next_cell, needs, there, merges_into, biggest_cell
  (for an app to highlight cells; docs/api.md not updated - coordinator);
- selftest section 11 (4 checks: pair shape, 65536 real-rank cut, no false completion, merge consistency): 0 failures.

AFTER (same continuations; results/plan/eval2_v3.txt; old = the previous plan logic)
                            engine old -> new            players old -> new
  all checkable plans       0.69 -> 0.73 (n 1,573/1,597)  0.79 -> 0.86 (n 1,434/1,462)
  16384+                    0.60 -> 0.81                  0.57 -> 0.86
  <=512 / 1024-2048 / 4096-8192: 0.57 -> 0.60 / 0.77 -> 0.74 / 0.80 -> 0.79 (engine), players 0.83/0.85/0.92 unchanged
  pair (new)                pair:single 1.00 (40)          0.85 (59)
  single with a chain next to the corner: engine 0.76-0.87, players 0.69-1.00 by step
  location precision        0.50 -> 0.59 (353/425)        0.61 -> 0.67 (311/398)
  merge vs best move        imperative contradicted the best move in 175 of 336 merge plans -> never (191 phrased "can
                            merge ... (the engine prefers X first)", 174 "Merge ...")
- Changed texts on 4,000 random positions: 1,422 (single with a chain 496, off-path cell 326, single named tile 138,
  pair 128, merge-wait 123, early-corner note 103, other orientation 84, 65536 completion fix 71); examples in
  results/plan/examples.json and compare_final.txt.
- Fuzz: both board sets (4,553 boards) rerun: no plan issues (scripts/fuzz_check.py taught the pair / single / wait
  phrasings); only the known 16-distinct-tile "not a board" x2 and the known 65536 rank-collision reason x1.

OPEN
- no_corner at <=8192 ("Get your biggest tile into a corner"): within 30 moves the engine does it 5-52%, players 13-43%
  - standard advice but rarely what happens next; a better plan for the mid-edge biggest tile is open.
- build/grow location is still ~40% elsewhere (both cells work for merging); "blocked" check is weak (the blocker
  usually moves anyway).
- The block-formation plan line (results/pdf) was not evaluated (block positions are judged by the block tables).
```
