# Workstream serve: packed networks and serving profiles (REPORT)

Copied by the coordinator from results/serve/report.txt.

```
Workstream serve: how small can the analysis engine get without changing its answers? (2026-10-07 07:15-, laptop +
16 instance cores; engine = best_v6c: weights/late2/best_v6c.w --leaf-view-max-sum 20480)

1. THE NETWORKS (scripts/serve_netstats.py -> results/serve/netstats_v6c.txt, serve_rankcap.py -> rankcap_v6c.txt)
- 5 stages x 8 six-cell patterns x 16^6 entries = 671M entries (2.68 GB float, 1.34 GB int16 in RAM).
- Trained (entry != the table's initial value): stage 0 40.9%, 1 32.3%, 2 35.2%, 3 45.8%, stage 4 0.0% (best_v6c's
  stage 4 was never trained: all 134M entries = 5000; late2: the root downgrade sends the 32768 phase to stages 0-3)
  -> 30.8% of all entries are trained.
- Tile ranks used by trained entries: stages 1-2 never use rank 15 (32768); stage 0 uses rank 14 (31% of its trained
  entries) but its LOOKUPS never do (the leaf view lowers every 16384 below sum 20480); stage 3 needs rank 15.
- Weights are heavy-tailed (stage 0: p50 |w| ~350, p99 ~8,000, max ~200,000) -> uniform int8 over the full range
  loses the bulk (rms error 11-29% of the trained values), quantile/Lloyd codebooks lose the tails (tried, dropped).

2. PACKED FORMAT (src/wpack.h, src/wpack_tool.cpp -> build/wpack_tool; engine flag --packed FILE in EngineConfig,
   Evaluator::pnet; defaults unchanged)
- an untrained stage = one constant; each stage's tables re-indexed in base R (index of 6 nibbles in base R instead
  of 16; nibbles >= R answered by the stage's initial value without a table): caps 14 / 15 / 15 / 16 / const for
  best_v6c (14^6 = 45%, 15^6 = 68% of 16^6);
- values: int16 = exactly nt::load_quantized's int16 values (bit-identical engine), or int8 = (w - init) / step per
  table (step = the 99.5% quantile of the trained |w - init| / 127) with the larger 0.5% stored exactly as escapes
  (code -128, found through a 65,536-bucket index per table).
- pack: wpack_tool pack weights/late2/best_v6c.w OUT.wp --kind int16|int8 --caps 14,15,15,16,c [--esc-q 0.995]
  (8 s); check vs the engine's int16 evaluation: wpack_tool check IN.w OUT.wp; float file for build/play: unpack.

  variant                     file (raw / gzip -6 / xz -6)   RAM (RSS, analyze)   load     tables
  reference int16 (--weights)  2,684 MB float              1,350 MB             5.0 s    1,342 MB
  packed int16                 753 / 314 / 261 MB          775 MB               0.9 s    753 MB
  packed int8 (q 0.995)        384 / 166 / 146 MB          421 MB               0.3 s    384 MB
  packed int8, stage 0 only    62 / 35 / 31 MB             101 MB               0.1 s    62 MB
  (int8 q 0.98: 407 MB; q 0.95: 452 MB - more escapes, more precise, slower)

3. ANSWERS vs the reference int16 engine (scripts/serve_compare.py; results/serve/boards.txt = 2,000 real positions
   from results/human_ds_v6c stratified by largest tile (<=512 / 1024-2048 / 4096-8192 / 16384 / 32768+, 400 each)
   + 1,518 fuzz boards; 3,460 non-terminal; best-notables preset + frozen models results/serve/model.txt,
   personal.txt; results/serve/compare_packed.txt)
  variant         move agree (all / gap>=0.1%)  |rel. value loss diff| mean/p99/max  real_loss max  odds max  warn flips  ms p50 / p99
  packed int16    100% / 100%                   0 / 0 / 0 (answers byte-identical)    0              0         0/12131     1.53 / 30.6 (ref 1.28 / 25.4)
  int8 q0.995     88.1% / 100%                  0.00021 / 0.00136 / 0.00439          0.0045         0.016     6           1.78 / 41.0
  int8 q0.98      89.9% / 100%                  0.00013 / 0.00087 / 0.00266          0.0032         0.008     1           3.04 / 83.2
  int8 q0.95      92.1% / 100%                  0.00008 / 0.00064 / 0.00181          0.0024         0.003     1           5.58 / 160
  -> every int8 move change is between moves within 0.1% of each other (equally good); differences are far below
     the measurement noise of the truth sets (rollout noise floor ~1.7%, odds MAE vs truth 0.066).
- Rank caps that cut looked-up entries DO change answers: stage 3 at 15 -> 98.2% agreement, real_loss max 0.42
  (results/serve: caps tested 14,15,15,15 and 15,15,15,15); stage 0 at 14 alone: identical.
- Stage-0-only int8 vs full int8 on the 1,200 real positions with a largest tile <= 8192: identical answers (no
  lookup reaches stages 1-3). 100% of the novice / intermediate / strong positions in the curated data are stage 0
  (no 16384, tile sum < 20480); experts 4.4%; all positions 63.7%.
- Portable build (x86-64 baseline, no BMI2/AVX: make ... CXXFLAGS="-O3 -march=x86-64 ..."): same answers (one
  near-tie move of 1,200), p50 3.08 ms / p99 78 ms vs 1.33 / 30.8 native (2.3x) - a WASM build would be ~1.5-2x
  slower again (~5 ms p50); no emscripten toolchain on the laptop, not built.
- Exact tables (full engine) vs none (best-notables), 2,000 real positions: largest tile <= 8192 - tables decide 50 of
  1,200 (4.2%), move agreement 98.2% (100% at gap >= 0.1%), real_loss mean diff 0.0003 / p99 0.0002 but max 0.31 and
  your_cost p99 0.039 (table-decided positions are graded by the table there), 5 warn flips of 4,224; 16384+ -
  tables decide 114 of 800 (k6 48, k5 43, block 23), agreement 95.5% (100% at gap >= 0.1%), odds p99 0.055 / max
  0.42, real_loss p99 0.0087 / max 0.20. Full engine RSS 2.56 GB, 24.6 s to load.

4. STRENGTH (int8 q0.995 unpacked to a float file -> build/play, late's / late2's protocols, paired seeds vs v6c's own
   runs in results/late2; results/serve/ph16_*, early_*; scripts/serve_ph16.sh, serve_early.sh)
  - 16384 phase (700 real 16384 starts -> sum 36864, seeds 999/1001/1002): int8 64.43% vs int16 64.90%, paired
    -0.48 +- 1.09 points over 2,100 games (527 identical), mean score 236,015 vs 236,780 -> no measurable loss.
  - early game (empty board -> sum 20480, seeds 4321/4322; v6c's stage 0 = v6b's, reference late2's early_v6b logs):
    int8 94.07% vs 95.21%, paired -1.14 +- 0.59 points over 2,800 games (1.9 sigma); reach 16384 95.50 vs 95.71%
    (seed 4321). A finer int8 step (q 0.98, more escapes) is not better: -1.71 +- 0.88 (seed 4321).
    -> int8 errors (~100-200 points per evaluation in stage 0, where values are small) shift choices among
       near-equal moves; over ~9,000 moves of a game that costs ~1 point of conversion. Harmless for analysis (each
       answer changes only among moves within 0.1% of each other), but int16 is the safe default.
  - int16 packs are bit-identical (same evaluations -> same play), no strength test needed.

5. SERVING PROFILES
  profile                 networks                    tables                     RAM        disk / download     latency p50 / p99 (real positions)   answers vs full engine
  full (research server)  int16 1.34 GB (5 s load)    k6 2.2 GB RAM + k5 88 GB    ~3.7 GB    ~144 GB              1.4 / 13 ms (scorecard, tables)       reference
                                                      + block 53 GB on disk
  server, same answers    packed int16 753 MB (0.9 s) same                        ~3.0 GB    ~142 GB              +20% (index mapping)                  bit-identical
  small server            packed int16 753 MB         k6 only (2.2 GB)            ~3.0 GB    3 GB                 same                                  differs only where k5/block tables decide
                                                                                                                                                           (66 of 800 real 16384+ positions)
  1-GB server             packed int8 384 MB          none                        ~0.45 GB   384 MB (146 MB xz)   1.8 / 41 ms                           no-table + int8 differences (below)
  browser / phone         int16 stage 0 only 120 MB   none                        ~0.16 GB   120 MB (55 MB xz)    native 1.3 / 31; portable 3.1 / 78;   identical to the int16 engine on every
                                                                                                                  WASM est. ~5 / 150 ms                 position without a 16384 (sum < 20,000)
  browser, ultra-light    int8 stage 0 only 62 MB     none                        ~0.1 GB    62 MB (31 MB xz)     same                                  identical to the int8 engine there
                                                                                                                                                           (int8: ~1 point weaker in play, see 4)
  - no tables vs the full engine (2,000 real positions): <= 8192: 4.2% table-decided, move agreement 98.2% (100% where
    the moves differ by >= 0.1%), real_loss mean diff 0.0003 (max 0.31 in table positions), 5 warn flips of 4,224;
    16384+: 14% table-decided, odds p99 diff 0.055.
  - int8 vs int16: move changes only between moves within 0.1% of each other; value-loss diff p99 0.14%, max 0.44%;
    real_loss max 0.0045; odds max 0.016 (one position of 3,460; p99 0.001); 6 warn flips of 12,131.
  - WASM needs: emscripten (not installed here), the non-BMI2 pext fallback (exists in board.h; the portable build is
    2.3x slower natively), single-threaded search (analyze's personal-odds playouts use threads: use the model
    method), a 62 MB fetch cached in IndexedDB, memory far below the 4 GB WASM32 limit. Positions with a 16384 or a
    tile sum >= 20,000 must go to a server (the stage-0-only file holds stages 1-3 as constants: their values would
    be wrong; searches from roots below 20,000 never reach them).

6. RECOMMENDATION FOR THE APP PHASE
  - Two tiers: (1) the in-browser/phone engine = stage-0 int16 pack (55 MB xz download, ~0.16 GB RAM, ~5 ms per
    analysis in WASM, answers bit-identical to the research engine without tables): every position of novice /
    intermediate / strong players (100% of theirs in the curated data), offline and free to serve; (2) a small
    server for positions with a 16384 (or a tile sum >= 20,000) and expert reviews = packed int16 (bit-identical,
    44% less RAM, 5x faster load) + k6 tables in RAM, + k5 / block tables on a ~150 GB SSD if exact late-endgame
    grading matters (they decide ~8% of real 16384+ positions).
  - int16 packing everywhere (no answer risk). int8 halves the size again (31 MB xz client file) with near-identical
    answers (near-tie move changes, <= 0.5% value-loss changes) but measurably weaker play (~1 point in the early
    game): only if the download size really matters.
  - The exact tables are the only part that cannot go to the client; without them, 4% of early positions (chains
    of 6+ tiles from 512 on) are graded by values instead of exact table chances.
  - The rank caps depend on the engine config (the leaf view keeps 16384s out of stage 0): repack after every engine
    switch (wpack_tool pack, 8 s) and re-run scripts/serve_compare.py against the int16 engine before shipping; the
    packed int16 must come out byte-identical.

7. FILES
- code: src/wpack.h (PackedNet: constant / int16 / int8+escape stages, base-R re-indexing, bucketed escapes,
  weight() for the per-cell attribution), src/wpack_tool.cpp (build/wpack_tool pack|unpack|check; Makefile target),
  src/search.h (Evaluator::pnet, used by operator(), nstages(), patterns(), attribute()), src/engine.h
  (EngineConfig::packed, flag --packed FILE, Engine::load). Defaults unchanged: the default build's values on 200
  real positions equal the 06:50 analysis (0 differ); all targets build; analyze --selftest 0 failures (also with
  --packed).
- scripts: serve_netstats.py, serve_rankcap.py, serve_compare.py (select / run / diff), serve_paired.py,
  serve_ph16.sh, serve_early.sh (instance).
- packed networks (laptop, weights/serve/): v6c_i16.wp (753 MB, bit-identical), v6c_i8_q0.995.wp (384 MB),
  v6c_s0only_i16.wp (120 MB, browser), v6c_s0only_i8.wp (62 MB); remake any in ~8 s with
  `build/wpack_tool pack weights/late2/best_v6c.w OUT --kind int16 --caps 14,15,15,16,c` (stage-0-only: caps 14,c,c,c,c).
- data: results/serve/ (boards.txt, ans_*.jsonl, compare_packed.txt, netstats_v6c.txt, rankcap_v6c.txt, ph16_*,
  early_* logs).
```
