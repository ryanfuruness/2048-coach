# Coach workstream: does engine advice help players recover? (2026-10-06, finished ~23:30 +04)

Written by the coordinator from the workstream's final message (the subagent could not create the file itself).

**Conclusion:** engine advice clearly helps human-like players recover. The best way to give it is a **warning just
before a bad move**. A few warnings per 100 moves close most of the gap to the engine.

**Replication:** a fresh sample of 302 start positions with different seeds (results/coach/rep2/) reproduced every
number to within about 0.04.

## Setup

- **Start positions:** 249 real positions from the curated set (`scripts/coach_select.py`), plus 302 for the
  replication. Three kinds:
  - **tight:** value < 0.75 × the stage's typical value;
  - **after:** right after a real mistake of ≥ 3%;
  - **control:** ordinary positions.
- **Stages:** S1 = max tile 128–512, S2 = 1024–2048, S3 = 4096–8192.
- **Players:**
  - the 1-ply softmax player (`soft_move`) at t = 0.003 / 0.01 / 0.03 / 0.1;
  - a "structured" player that plays the engine's move with probability 0.5.
- **Outcome:** reaching the next tile doubling. Common random numbers (the same spawns) across conditions.
- **Advice conditions** (thresholds are relative value losses):
  - **warn ≥ X:** the player's intended move loses ≥ X, so it is replaced by the engine's move;
  - **expected-loss hint ≥ Y:** the player's expected loss ≥ Y, so the engine's move is shown;
  - **stakes hint ≥ Y:** the second-best move loses ≥ Y, so the engine's move is shown.
- **Matching the players to human skill.** A maximum-likelihood fit to human moves gives t ≈ 0.05–0.1 for typical
  humans, but it is dominated by harmless near-ties. Matching instead on how often players make moves that lose ≥ 15%:

  | softmax player | matches | ≥15% moves per 100: model vs human |
  |---|---|---|
  | t = 0.1 | novices | S1: 2.2 vs 2.95 |
  | t = 0.03 | intermediates | S1: 0.4 vs 0.44 |
  | t = 0.003–0.01 | strong players | S2: 0.3–0.4 vs 0.28 |

- **Caveat:** softmax players do worse over a whole stretch than real humans with the same move-level statistics.
  Human outcomes in the dataset cannot fix this, because videos are selected for success. Policy rankings should
  transfer better than absolute gains.

## Results

1. **Warnings dominate hints.** Warnings give the best trade-off between help and number of interventions, at every
   skill, in all strata, for both player models. Example, S1 at t = 0.1 (alone 0.52, engine 0.92):

   | policy | interventions per 100 moves | P(next milestone) |
   |---|---|---|
   | warn ≥ 0.15 | 2.2 warnings | 0.83 |
   | expected-loss hint ≥ 0.1 | 2.8 hints | 0.74 |
   | stakes hint ≥ 0.3 | 4.1 hints | 0.65 |

   Hints shown before the player moves are wasted when the player would have played well anyway: the stakes hint
   shows 10–70 hints per stretch but changes only 1–9 moves.

2. **Share of the gap to the engine closed by warnings:**

   | stratum | player | alone → engine | 1 warning / 100 moves | 2 / 100 | 5 / 100 |
   |---|---|---|---|---|---|
   | S1 | novice-like | 0.52 → 0.92 | 56% | 73% | 89% |
   | S1 | intermediate-like | 0.75 → 0.92 | 74% | 90% | |
   | S2 | intermediate-like | 0.47 → 0.95 | 42% | 60% | 87% |
   | S2 | strong-like | 0.68 → 0.95 | 58% | 79% | |
   | S3 | strong-like | 0.34–0.50 → 0.82 | 34–67% | 54–80% | |

   - The late game is lost through many small errors, so the warning threshold should fall from ~0.15 early to
     0.02–0.05 late.
   - Capped warnings (first 1 or 3 per stretch): each ≥0.15 warning is worth about +0.05 to +0.15 in
     P(next milestone), and the first is worth as much as the later ones.
   - At 50% compliance, about half the gain.

3. **Recovery works.** From positions right after a real mistake (S2, t = 0.03): alone 0.41; warnings at ≥0.05
   (3.5 per 100 moves) 0.83; engine 0.92. Even the engine reaches only 0.77–0.92 after a real mistake: the damage
   is lasting.

4. **How often real players would be warned** (≥0.15 threshold, real games; `report_human_rates.txt`):
   - median intermediate and strong players: 0–0.4 per 100 moves;
   - novices in S1: 2.7;
   - experts at 16384+: 1.0. Most of these are probably false alarms (the dispute finding), so warnings should be
     off for experts in 16384+, or use a higher threshold, until the late-game fix lands.

5. **"At your level" is now well defined.** The cost of a move as a share of the player's own chances barely
   depends on skill (600 ordinary positions, 414 real mistakes, both player models):

   | value loss | share of own chances lost | installed engine map |
   |---|---|---|
   | < 3% | ~0 | |
   | 3–10% | 0–3% | |
   | 10–30% | 6–12% | 4–6% |
   | ≥ 30% | 41–52% (structured player 33–51%) | 30–37% |

   - In absolute probability, the cost is this share × the player's own odds. That is why the old absolute skill maps
     shrank for weak players.
   - Recommendation for `analyze`: report "this move costs about X% of your chances", with X ≈ the engine map × 1.3–1.5
     (players repair less than the engine).

**Note for the calibration workstream (cal6):** in S1, the engine's own continuation after real big mistakes loses
0.29 in P(next milestone), while the early loss map gives 0.11. This is a different measure (next milestone, not
expected score), but the early map may be too lenient for big losses.

## Files

- **Code:** `src/coach.cpp`, built by `make` (in `all`). Modes: advice / first / fit; options `--structured` and
  hint caps `:kN`.
- **Scripts:** `coach_select.py` (`--seed --exclude --big --mistakes`, output dir `COACH_DIR`), `coach_fit_t.py`,
  `coach_match_t.py`, `coach_human_rates.py`, `coach_report.py`, `coach_run.sh`, `coach_run3.sh`, `coach_run4.sh`.
- **Data (results/coach/):**
  - advice: `advice_S1-3.tsv`;
  - capped hints: `budget_S1-2.tsv`;
  - structured player: `struct_S1-2.tsv`;
  - single-move cost runs: `first_{before,pool,big,bigstruct,mistakes,mistakesstruct}.tsv`;
  - reports: `report_*.txt` and `summary_*.json`;
  - replication: `rep2/`.
