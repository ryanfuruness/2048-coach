# Analysis API (v0.3, 2026-10-10)

The analysis engine answers one question per request: *what is this position worth and what should I play?* It runs as
`build/analyze` (command line, `--stdin` server mode) or behind `scripts/serve.py` (HTTP).

## Request

HTTP: `POST /analyze` with a JSON body. Server mode: one line per request, `OPTIONS | BOARD` (options optional).

| field | meaning |
|---|---|
| `board` | 4x4 tile values, as `[[2,4,0,0],[...],[...],[...]]`, or a string of 16 tile values (any separators), or 16 hex rank digits (engine encoding, cell 0 = top-left). 0 = empty. Tiles up to 2^30 are accepted (131072 and beyond are fine). |
| `depth` | analysis depth; 0 (default) = the engine's own depth (iterative deepening), 4-5 = deeper and slower; capped at 6. Each request is independent (the search cache is reset per request). |
| `risk` | 1-3: also report what the next random tile can do after each move (search depth for each spawn). |
| `line` | N: a sample continuation of N engine moves (fixed seed per position). |
| `played` | U/R/D/L: the move the player made (echoed back; used by game reviews). |

Command line only: `--chance-model FILE` (your chance, research; off by default) / `--no-chance`, `--personal T` (personal odds for a player of skill T, on the review's softmax scale), `--skill
THETA` (a player's skill on the human move model's scale, the review's `skill`: personal odds plus the per-move
`find_prob`, the position's `error_risk` and `hint`), `--heat` (per-cell value attribution), `--features` (concept
features per move), `--review FILE` (whole game).

## Response

| field | meaning |
|---|---|
| `board` | the position as tile values (real values, also above 32768). |
| `hex` | the engine's internal board (ranks; big tiles may be stored lowered). |
| `stage`, `depth` | the network stage and the search depth used. |
| `engine_move` | the engine's move (`up`/`right`/`down`/`left`), null if the game is over. |
| `source` | what decided it: `search`, `table` (exact endgame table, chains of >= 6 tiles), `layered` (exact table, 5-tile chains), `block` (exact block table, see `formation`). |
| `table_p` | the deciding exact table's success probability (only when a table decided). |
| `formation` | `"block"` when the biggest tiles sit in a 3x2 block in a corner and the largest tile is 16384 or more (the engine plays snakes; see docs/guide.md). |
| `judged` | `false` in block positions that no exact table decides: no `real_loss`, `warn` or `your_cost` there, and the engine's move is a suggestion only. Absent otherwise. |
| `game_over` | true if no move is possible. |
| `odds` | probability of reaching each bigger tile with best play from here: the engine's base rates at this stage, adjusted by the position's value, x the share of next tiles that do not end the game. |
| `odds_caveat` | `true` when the position's formation is unusual for its stage (largest tile 4096+ and big tiles exposed, trapped, scattered or away from their corner): the odds' error there is 2-3x larger. Absent otherwise. |
| `expected_future` | calibrated expected points still to come with best play. |
| `summary` | one-paragraph verdict: the most informative odds vs a typical position at this stage, the best move with its main reason (or the exact table's chance), the move to avoid. |
| `plan` | the chain of big tiles and the next tile it needs (in block positions: the block). Checked on 2,000 real positions: the predicted event happens in 73% of the engine's continuations and 86% of the real players' (16384+: 81% / 86%). |
| `plan_info` | the plan as data: `type` (`merge`, `build`, `grow`, `blocked`, `full`, `single`, `pair`, `no_corner`; see src/explain.h `plan_info`), `corner_cell`, `chain` (cells, 0 = top-left) and `tiles` (real values), `next_cell`, `needs` (the tile to build there), `there` (what is there now), `merges_into` (what the chain's tail becomes). |
| `moves[]` | every legal move (see below). |
| `personal_odds` | with `--personal T`: odds for a human-like player of skill T (`method`: `model` or `playouts`; `human_skill`: the skill s of the human move model (src/human.h) whose games review like T - with an older softmax-based personal model, `soft_temperature` instead). |
| `player_skill` | with `--skill` (or `--personal`, converted): the player's skill on the human move model's scale (higher = stronger; typical: novices -0.8, intermediate and strong players -0.2 to 0). |
| `chance` | your chance (largest tile up to 8192, with weights/calib/chance.hv; docs/guide.md "Your chance"): `target` (the milestone tile: 2048, then each doubling), `now` (from here, with the player's own move probabilities), `best` (with the best move for the player), `skill` (the skill used: `--skill` / the request's skill, floored at the in-between -0.5, which is also the default), `key` (the simulated players' key). |
| `coach_move`, `coach_why` | the coach's move: up to a largest tile of 512 the corner strategy's move (the human move model at a strong skill, with the player's recent moves) among the moves that cost nothing (real loss <= 0.5%, <= 1 point of `chance`), else the engine's reference move; `coach_why` when it differs from the engine's ("keeps your 128 in its corner"). |
| `error_risk` | with a skill: the expected share of the player's own chances of the next tile that the move they make here costs: the sum over the moves of `find_prob` x `your_cost`. Absent where moves are not judged. |
| `hint` | with a skill: true when `error_risk` reaches the phase's threshold - an app would show the engine's move before the player moves (only with a largest tile up to 512, where hints were confirmed on real games; see docs/guide.md). |
| `line` | with `line`: `[{"move", "board"}]`. |
| `played` | echo of the request's `played`. |
| `evals`, `ms` | work done and time taken (all the work, reasons included). |

Per move (`moves[]`):

| field | meaning |
|---|---|
| `move`, `reward` | the direction and the points it scores immediately. |
| `value` | merge reward + expected future reward (network scale; differences between moves are what matter). |
| `loss` | best move's value - this move's value (null for a corner-breaking move the engine distrusts, or where an exact table decided and rates the move differently). |
| `real_loss` | estimated real loss as a share of the expected future score with good play afterwards (staged loss maps fitted on rollouts of real human positions; the exact tables' chances where a table decided). In reviews, the player's own move at 16384+ is judged by what players lose (much less than the engine's continuation suggests). Null where not judged. |
| `real_loss_engine` | reviews only, the played move when it differs: its cost if the engine took over from there (the alternative moves' maps). |
| `warn` | true when an app should warn before this move is committed: the move is a blunder (`grade`). |
| `grade` | the coach's verdict (app v3; results/grades/REPORT.md): `best` (the coach's move, or within 0.5% value loss), `good` (0.5-5%), `questionable` (5%+, 10%+ from 16384, or a big tile pulled off the edge), `blunder` (an obvious, named mistake a fine move avoids: the biggest tile out of its corner, the biggest or second-biggest tile off the edge, 10%+ of new tiles end the game, or a real loss of 10%+). No corner or edge verdicts up to a largest tile of 256. Absent where not judged. |
| `why` | the named reason of a questionable move or a blunder. |
| `pick` | how often the coach would play the move: exp(-value loss / 0.015) normalized (fitted to which move a depth-5 search prefers), the coach's move on top. |
| `hint_cells`, `fault_cells` | cells (0 = top-left): where the coach's move acts on the current board (its largest merge, else the plan's next cell; not used by the app since v3.4); where a flagged move went wrong, on the board after it. |
| `chance`, `chance_loss` | with `--chance-model` (research, workstream yc; not used by the app): the player's chance after this move and the best move's chance minus this one's. |
| `your_cost` | the share of a human-like player's own chances of reaching the next tile that this move gives away (from 16384 on: the real loss). With a known skill (`--skill`, or `--personal T`) it uses the map of the player's skill band (novices: ~3x the default; others: ~0 for small losses). |
| `your_cost_abs` | with personal odds: `your_cost` x the personal odds of the next tile (the absolute drop). |
| `find_prob` | with a skill: the probability that a player of that skill plays this move (the human move model, src/human.h; in reviews with the player's recent moves). |
| `odds` | the odds after this move. |
| `p` | exact endgame / block table success probability after this move (when a table applies). |
| `breaks_corner` | true if the engine's corner lock rules this move out. |
| `reasons[]` | `{code, text}`: for the best move its strengths, for clearly worse moves their weaknesses, strongest first. Codes: `table`, `block`, `danger`, `corner`, `chain`, `chain_len`, `missed_merge`, `exposed`, `center`, `toward_corner`, `trapped`, `edge`, `space`, `merge`, `risk`, `later`, `area`, `shape`. Each reason of a clearly worse move (value loss >= 3%) carries `share` (0-1): the part of the move's loss that removing exactly that defect recovers (counterfactual check in the position; reasons below 0.1 are dropped and the rest sorted by it). Reasons without `share` are unchecked hints. |
| `risk` | with `risk`: `bad_prob` (share of next tiles costing > 5%), the worst spawn (`worst_cell`, `worst_tile`, `worst_prob`, `worst_loss`). |
| `heat` | with `--heat`: 16 numbers, per-cell value of this move's afterstate minus the best move's (where the difference sits). |
| `after` | the board after the move, before the new tile (engine encoding). |

## Game review (`--review FILE`, one board per line)

Moves between consecutive boards are inferred (up to 3 skipped moves per frame pair). Output per move as above, then a
summary (JSON with `--json`): `moves` (judged moves), `match` (share of engine moves), `good` (real loss < 1%),
`accuracy`, `kept` (share of the engine-continuation chances the moves preserved, until the position was lost),
`lost_at`, `decisive_move` / `decisive_loss`, `mean_real_loss`, `inaccuracies` (estimated real loss 1-3%), `mistakes`
(3-10%), `blunders` (>= 10%), `skill_t` (temperature of the softmax player that best explains the moves; lower =
stronger; compare players within a stage only; null without judged choices), `mistakes_at_your_level` (moves costing
>= 3% of the player's own chances of the next tile), `warnings` / `warnings_per_100` (warnings an app would have
shown), `not_judged` (moves in block positions without a deciding table), `skill` (the player's skill on the human move
model's scale: maximum likelihood of the played moves; far more stable than `skill_t`), `hints` / `hints_per_100`
(hints an app would have shown before the move, at the fitted skill), `hard_moments` / `hard_found` /
`hard_found_plies` (risky positions whose best move players at this skill find less than 20% of the time, habits
aside, and how many the player found), `unknown_frames`, `bridged`, `phases[]` (per stage: moves, mistakes,
blunders, kept, skill_t with an 80% interval, skill with an 80% interval) and `key_moments[]` (the 5 largest of real
loss and your cost, with `real_loss`, `your_cost` and reasons).

## Models and data files

| file | what |
|---|---|
| `weights/best_v5.w` | the preset's base networks (5 stages, 2.7 GB float, 1.3 GB in memory as int16) |
| `weights/best.cfg` | engine flags applied on top of the preset (the engine switch, `scripts/switch_engine.sh install`); now `--weights weights/late2/best_v6c.w --leaf-view-max-sum 20480` = best_v6c, the current networks |
| `weights/endgame_big/` | exact k>=6 tables (2.2 GB, loaded into memory by `--preset best`) |
| `weights/endgame_lt/k5r10.lt`, `k5r9.lt` | exact 5-tile-chain tables (88 GB, read from disk; `--preset best`) |
| `weights/pdf/block_e*_r*.lt` | exact block-formation tables (53 GB, read from disk; `--preset best` loads them when every table is complete; used from a 16384 on) |
| `weights/calib/model.txt` | odds model (+ formation correction `ocorr`), loss maps (`lossmap`, `lossmap_late`, `lossmap_top`, `lossmap_table`, and for a player's own moves in reviews `lossmap_played_expert`, `lossmap_table_played`), your-cost maps (`lossmap_own PHASE`, by skill band `own_split`, `lossmap_own_lo/hi PHASE`), warn thresholds (`warn`) (scripts/fit_calib.py, fit_cal7_odds.sh, fit_cal9_odds.sh, fit_lossmap2.py, fit_lossmap_table.py, fit_owncost.py, fit_owncost_skill.py) |
| `weights/calib/chance.hv` | your chance: n-tuple networks for 6 simulated-player keys (0.0005-0.016) x 8 stages, recalibrated (src/hvalue.h; build/hv_tool train / recal; scripts/yc_train_family.sh; results/yc/REPORT.md) |
| `weights/calib/personal.txt` | personal-odds model: `player human` (simulated players = the human move model), the coefficients per key, the skill map (`pskillmap`: review t -> key; scripts/fit_personal.py, hm_skillmap.py), `pthetat` (real players' skill theta <-> review t, scripts/hm_skill_real.py), `pthetamap` (the simulated players' own theta per key, for simulations; scripts/hm_thetamap.py) and the hint thresholds (`phint` per phase) |

`--preset best-notables` runs without the exact tables (1.3 GB RAM; weaker only in 16384+ endgames; block positions
are then not judged).

## Packed networks (cheap serving)

`--packed FILE` loads a packed copy of the networks instead of `--weights` (workstream serve, 2026-10-07; build with
`build/wpack_tool pack weights/late2/best_v6c.w OUT --kind int16 --caps 14,15,15,16,c`, ~8 s; repack after every
engine switch and confirm with `scripts/serve_compare.py` that int16 stays byte-identical):

| file (weights/serve/) | size raw / xz | RAM | answers vs the int16 engine |
|---|---|---|---|
| `v6c_i16.wp` | 753 / 261 MB | 775 MB (vs 1.35 GB), 0.9 s load | byte-identical |
| `v6c_s0only_i16.wp` | 120 / 55 MB | 157 MB | identical for every position without a 16384 and with a tile sum below 20480 (all non-expert positions in the curated data); other positions need the full networks |
| `v6c_i8_q0.995.wp` | 384 / 146 MB | 421 MB | near-identical (odds within 0.016, real loss within 0.0045); early play ~1 point weaker |

Browser/phone candidate: the stage-0-only int16 file (~5 ms per analysis expected in WASM; the portable build without
BMI2 is 2.3x slower than native), with positions beyond its range sent to a server. Server: packed int16 + k6 tables
in RAM, k5 and block tables on ~150 GB of SSD for exact late-endgame grading.
