# Workstream mx: macroxue as an independent judge of expert positions (REPORT)

Copied by the coordinator from results/mx/report.txt (the subagent could not create REPORT.md). Material for the late
workstream: results/mx/for_late.txt.

```
Workstream mx: macroxue's 2048-ai as an independent judge of expert positions (2026-10-06 21:50 - 23:50 +04)

QUESTION: where our engine calls an expert's late-game move a big mistake, does a stronger late-game engine side with
the expert?  ANSWER: yes for the one PDF-formation expert who causes 70% of the disputes (claims false), partly for
snake experts (claims real but 2-3x too large). Our engine is a snake specialist that collapses in PDF positions.

SETUP
- macroxue/2048-ai (commit fee3359) built on the instance as ~/macroxue/2048b (BIG tables; tuple_moves.11b 15.8 GB +
  .10a 1.35 GB generated in 17 min). GPL-3.0: a separate tool; the driver that includes its sources is kept OUTSIDE
  our tree (/home/ryanf/projects/2048-macroxue-judge/judge.cc, built on the instance as ~/macroxue/judge).
- Driver validated: reproduces macroxue's published game 2001 exactly (29,758 moves, 839,936) through its native
  loop and through our playout path with rand(); 160 games at depth 4 with our RNG: 589,699 +- 18,522, 16384 91.9%,
  32768 68.1% (published d4: 625,898 / 92.9 / 70.7).
- Positions (results/mx/positions.tsv): 150 expert disputes + 60 controls (results/disputes/expert.*; real tiles
  from results/human_ds/analysis.jsonl) + 300 random expert-tier positions with a tile >= 16384.
- Measurements: depth-8 analysis (eval_d8.out); 32 CRN playouts per move with macroxue (depth 4) continuing to game
  over (play_d4_h100000.out, playR_d4_h100000.out); both engines from the same 300 random positions, 1000 moves
  (fromR_d4.out, random300_ours_h1000.tsv); macroxue on our phase tests (pool700_d4/d4b/d6.out,
  pool32k500_d4/d6.out). Scripts: scripts/mx_tasks.py, mx_run.sh, mx_queue1-4.sh, mx_report.py
  (`python3 scripts/mx_report.py --all` regenerates every table). For workstream late: results/mx/for_late.txt.

FINDINGS
1. The disputes are one player. 105 of the 150 disputes come from d4Nf6Bg5, who plays macroxue's Perimeter Defense
   Formation (PDF: the 6 biggest tiles in a 3x2 corner block) in the 32768 phase; this player is 61% of all expert
   16384+ positions in the curated set. Disputes in 3x2-block positions: 63 (42%) vs 11% of random expert positions.
2. PDF player's disputes (105): claimed 21.0% -> real loss with macroxue continuing -1.0% (94 no significant
   difference, 10 expert better, 1 engine better); our own rollouts -2.1%. Depth 8: macroxue prefers the expert's
   move 23%, ours 6%, tie 71%. Where its exact PDF tables decide (70 disputes): the expert's move is table-optimal in
   97%, ours in 80%, and OURS BREAKS THE FORMATION (p < half the best) in 16% (results/mx/pdf_breaks.tsv); there our
   own rollouts show the expert's move 25% better.
3. Snake experts' disputes (45): claimed 23.0% -> real +6.5% (macroxue, 8 engine better) / +11.0% (our rollouts, 8
   confirmed); depth 8: macroxue prefers our engine 38%, the expert 7%, tie 56%. Claims are directionally right,
   2-3x too large (consistent with the installed lossmap_played_expert).
4. Judges agree: of our 12 confirmed disputes macroxue's playouts confirm 6 (5 refuted); of our 105 refuted it
   refutes 89 (3 confirmed). Depth-8 pairwise: confirmed -> prefers ours 58%; refuted -> prefers the expert 25%, ours 10%.
5. Random expert positions (300): expert != our engine in 44%, mostly tiny claims (93 of 133 < 1%); with macroxue
   continuing 126/133 show no significant difference; claims >= 10% (n=8): claimed 29.8%, real -13.7%. In the PDF
   player's 32768-phase positions our engine rates 17.5% of the expert's moves >= 3% worse (snake experts: 2.7%).
6. Who plays which formation (death within 1000 moves from the same 300 random expert positions): snake experts'
   positions ours 16.7% vs macroxue d4 50.7% (ours clearly better in 80, macroxue in 2); PDF player at max 32768 ours
   75.6% vs macroxue 46.7% (macroxue better in 34, ours 5); PDF player at max 65536 (mostly snake again) ours 7.2% vs
   29.8%. -> macroxue is a weak judge in snake positions; our engine collapses in PDF positions.
7. macroxue on OUR phase tests (identical starts): 16384 phase (pool700 -> sum 36864): d4 70.6 +- 1.7%, d6 78.0 +-
   1.6% vs ours 64.1 +- 1.8%. 32768 phase (pool32k first 500 -> game over): d4 309,815 +- 5,861 gained, sum >= 49152
   83.8%, >= 57344 63.2%; d6 331,088 +- 6,152 / 87.4% / 70.4% vs ours 264,682 / 69.4% / 48.0%. From our starts it
   rebuilds its block (final boards block6 in 482/494 successes); 54% (16384 phase) and 59-67% (32768 phase) of its
   moves come from the exact tuple11 PDF table, 1-2% tuple10, the rest search. Depth 4 runs ~2,650 moves/s per core.
8. What it values that ours does not: (a) the PDF block instead of the snake (2-D gradient heuristic: rows AND
   columns descending to one corner, x12 per inversion, bonus for equal neighbours); (b) exact PDF tables deciding
   most late moves (its own analysis: PDF beats the snake by 1.5-5 points per build: 99.1 vs 97.7, 81.2 vs 78.2,
   17.3 vs 12.5%); (c) a formation-broken cutoff in search. Where it sides with the expert, the expert's afterstate
   has fewer exposed cells next to big tiles (-0.29). Our earlier heuristic-only reimplementation (`play --gradient`)
   failed for lack of the tables.

RECOMMENDATIONS
- Analysis engine now: detect the PDF block (6 biggest tiles in a 3x2 corner block) and transitions in the 32768
  phase; there the engine is not a judge (no mistake claims, or a much stronger discount than
  lossmap_played_expert); keep the snake claims with the current shrink.
- Follow-up project (strongest lever for both analysis and SOTA): exact PDF tables in OUR engine (own code, the same
  DP as our snake tables: 3x2 block fixed, next tile built in the L-region; macroxue's take 15.8 + 1.35 GB at 2 bytes
  per entry) and a late-game route through them (optionally a PDF formation switch in the 16384 phase). Expected:
  removes ~70% of expert disputes and the 16% formation-breaking recommendations in PDF positions; strength from our
  own starts +6 (d4) to +14 (d6) points in the 16384 phase and +15 to +22 points (sum >= 57344) in the 32768 phase,
  i.e. toward macroxue's 80.5% 32768 rate.
- Expert start pools for late-network training are mostly PDF positions of one player; TD with our policy learns the
  value of our (collapsing) play there, so do not expect it to fix PDF judgment.

CAVEATS: 32 CRN playouts per move (score to game over is noisy, SE ~10-20k: only large differences resolve); the PDF
findings rest on one player's positions (105 disputes, 183 random positions); macroxue is the right judge for PDF
positions, our own rollouts for snake positions.
```
