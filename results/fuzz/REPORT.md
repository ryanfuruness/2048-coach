# Workstream fuzz: edge-case and invariant testing of analyze (REPORT)

Copied by the coordinator from results/fuzz/report.txt (the subagent could not create REPORT.md).

```
# fuzz workstream notes (2026-10-06 23:45 start)
23:25 pass1 (laptop, best-notables, 1782 boards incl. 8-symmetry groups): no crash, no invalid JSON, moves/legality/
  rewards/afterstates/odds/loss invariants all hold; issues: ef_negative 355 (calib ratio < 0 at log2 sum >= ~15.9),
  16-distinct-tile boards -> "not a board", all-2048 board 17 s on repeat (TT carry-over makes iterative deepening
  overshoot: depth 4 -> 7 on each repeat). Instance (tables): loss_negative in 181 table-decided positions (search value
  of another move up to 37% above the table move's), k6 on-demand table builds 4.6-5.8 s, tables symmetric (no sym
  issue). Server: depth=99 (capped 8) hangs > 120 s on an open board. Reviews: all odd files fine.
23:35 FIXES (built, selftest 9/9 ok, all targets compile):
  1. engine.h EngineThread: searcher held by unique_ptr + reset_search(); analyze --stdin and CLI boards reset it per
     request (reviews keep it warm, like play). Repeated request of the all-2048 board: depth 4,5,6,7 / up to 17 s
     -> depth 4 / 6 ms every time; open14late with risk=1 after deeper requests 1464 ms -> 3 ms. Cost ~1.3 ms/request
     (1500 requests 21.9 -> 23.9 s). messy.cpp: 2 call sites et->search. -> et->search-> (no behaviour change).
  2. analyze --stdin per-request depth capped at 6 (was 8: depth=99 on an open board hung > 120 s; depth 6 ~0.8 s).
  3. engine.h parse_board: tiles > 2^30 rejected (2^32 indexed map_search_board's rank arrays out of bounds) and long
     digit strings saturate instead of overflowing (signed overflow UB).
  4. explain.h tile(r >= 16): merge results above the search board's ranks now use the display map ("then the whole
     chain merges into a 65536" for a 131072-65536 chain -> 262144).
  5. analyze.cpp: "loss" null (text: n/a) for any move whose value beats the reference (was negative, down to -37% of
     the value scale, in 181 table-decided positions: the table's pick vs a move with a higher search value).
  6. analyze.cpp: "ms" now includes the reasons/summary work (was the search only: 6 ms reported for 2155 ms answers).
23:42 FIX 7. analyze.cpp reasons look-ahead ("a few moves later ..."): fixed depth-3 search instead of the engine's
  budgeted choose(). 200 real positions (instance): max 1669 -> 24 ms, p90 8.4 -> 4.5 ms; look-ahead reasons identical
  in 28/29 cases (depth 2: 23/29). The slow real position (0 2 4 8 / 0 0 128 128 / 2048 256 512 1024 / 2 16384 8192
  4096): 2396 -> 14 ms, same reasons.
FINDING (engine, for late/coordinator): map_search_board picks the LARGEST absent rank as the gap when a 65536+ must be
  lowered; merges below can fill that gap and collide with the lowered tile. Example 16384 . 16384 . / . . 4 2048 /
  . 256 . 4 / 64 65536 . 32: move left -> search afterstate f0002b0082006f50 = the new 32768 AND the 65536 both rank 15
  (equal, "mergeable", two separated top tiles to the network); value(left) future part 128k vs ~146-156k for the
  correctly mapped children; text "merges the two 16384s into a 65536". Fix idea: prefer a gap g with g-1 absent.
23:45 VERIFICATION with all fixes: pass4 (laptop, 2771 new boards incl. 5 symmetry groups per category): real human
  positions answer time p99 1565 -> 22 ms, max 2120 -> 25 ms; all boards p99 945 -> 31 ms, max 3882 -> 45 ms. Instance
  (--preset best, tables): no invariant issue; remaining outliers = on-demand k6 table builds (3.9-5.2 s, first hit of
  a formation; memoised after). Corner-lock flags: 1445 flagged moves, 0 geometry violations, 0 missed.
OPEN (design / other owners):
  - cal6: expected_future < 0 for tile sums >= ~2^15.9 (ratio knot 16 = -0.052): 955 answers in pass1+2. Clamp at 0
    in Calib::future or refit the last knots.
  - cal6 (latent): odds_of / summary base / personal odds use the SEARCH board's max tile and tile sum: with a 65536
    target in a model, a real-65536 board (search max 32768) would get P(65536) < 1. Use the real max tile.
  - cal6/coordinator: in table-decided positions real_loss ignores the table: a move with p 0.41 vs the table move's
    0.73 shows real_loss 0 (value-based, clamped). Candidate: real loss = (p_ref - p_move) / p_ref there.
  - engine (late): 65536 merge collision in map_search_board (see FINDING above).
  - engine (late): iterative deepening counts only new leaf evals, so a warm table makes it overshoot (fixed for
    analyze by resetting per request; still present in rollouts: the same first boards recur across playouts and get
    deeper searches -> slightly stronger continuations on repeats).
  - k6 on-demand table builds: 4-5 s on the first hit of a formation (server warm-up or persisting built tables).
  - 16 distinct tiles (a full board 2..65536 or 4..131072: always game over) -> "not a board"; empty board -> game
    over; "-2" parsed as 2; rewards/values of lowered (65536+) boards are on the search scale (understated).
23:50 DONE. pass5 (laptop, boards1 with depth=5 risk=2 line=20 --personal 0.03): no invariant issue (heavy options up
  to 4.3 s). rv3 (final binary): server answered all 45 malformed/edge lines with one JSON line each and kept serving;
  13 odd review files (repeats, undos, gaps, new game, garbage, empty, unparseable frame, 65536 merge, 131072) all exit
  0 with sane summaries. Nothing left running (laptop and ~/2048_fuzz idle).
```
