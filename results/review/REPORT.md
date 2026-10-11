# Workstream review: validating game reviews against rollouts (REPORT)

Copied by the coordinator from results/review/report.txt.

```
review workstream notes (validate build/analyze --review on real games), 2026-10-07, newest last

02:50 Setup. scripts/review_select.py: 100 stretches of <= 300 consecutive records of one video (time order, across
  segments; the review bridges gaps of <= 3 moves), stratified by tier and stage, round robin over players, stretches
  with > 10% block-formation positions dropped: novice 15 (S1), intermediate 30 (S1 15, S2 15), strong 30 (S1 9, S2
  11, S3 10), expert 25 (S1 2, S3 4, S4 19); 64 players. results/review/stretches/*.txt, stretches.tsv.
  Reviews on the instance (scripts/review_run.sh, review_run2.sh): build/analyze --preset best --weights
  weights/best_v6b.w --calib <installed model.txt, md5 27387cf6 = cal7's> --personal-model <installed personal.txt,
  md5 9c9a0c0a = hm2's v4>; pass 2 with --skill = the stretch's fitted skill, so every per-move line has find_prob /
  error_risk / hint. 30,929 judged moves; 142 hints, 427 hard moments, 731 warnings (summary counts).
  scripts/review_moments.py -> results/review/moves.tsv (one row per move) and the measured set (pool.bin / pool.tsv,
  1,885 positions): K = the 5 key moments per stretch (500), R = 5 random judged non-key moves per stretch (500),
  W = warned played moves (731), H = hint positions (141), D = hard moments (514; error_risk >= 1% and the best move's
  find_prob < 20%, habits included).
  Truth (scripts/review_roll.sh): E = engine continuing (best_v6b + tables), all moves, 32 CRN playouts, H=1000;
  measured loss of the played move mE = (q_ref - q_played)/max(|q_ref|,100k) against the analysis' own reference move
  (unbiased, as scripts/scorecard_played.py). P = human move model (src/human.h) continuing at the position's playout
  skill (personal_odds.human_skill of its review line: the personal model's key for the fitted skill) until the next
  milestone (largest rank + 1) or death, all moves, 64 CRN playouts; mP = (P_ref - P_played)/P_ref, P = 1 - died,
  positions with P_ref >= 0.1 (1,367 positions below 16384 have a playout skill).
  CAVEAT for P: the human model as a playout player repairs less than real players (hm/hm2: at a real intermediate's
  skill it reaches 2048 in 3% of games) -> mP likely overstates the cost of big errors for real players.
03:05 Descriptive (rev2 summaries; per 100 judged moves): novice 15 stretches, 3,601 moves: kept median 0.83,
  decisive moment in 60% of stretches, warnings 1.25, hints 1.28, hard moments 1.44 (found 12/52), blunders 0.28;
  intermediate 30 / 9,753: kept 0.97, decisive 20%, warnings 3.10, hints 0.47, hard 2.32 (17/226); strong 30 /
  10,175: kept 0.90, decisive 20%, warnings 1.99, hints 0.21, hard 0.97 (14/99); expert 25 / 7,393: kept 0.90,
  decisive 44%, warnings 2.46, hints 0.39, hard 0.68 (10/50), blunders 0.35.
03:10 Player truth (P) done (108 rollout groups, 1,367 positions). Non-expert, mean measured cost of the played move
  as a share of the player's own chances (mP): HINT positions 0.166 (n=68; the hint's error_risk predicted 0.153),
  random moves -0.003 (n=335; error_risk 0.001) -> hints sit exactly where players lose (novice 0.179 vs -0.015,
  intermediate 0.288 vs -0.007; strong: n=14, 0.008 vs 0.009 - no signal). Warned moves 0.072 (P(mP >= 10%) 0.29 vs
  random 0.05), key moments 0.054 (0.23). your_cost (estimate) vs mP by bin: [1-3%) 0.018 vs 0.007, [3-10%) 0.047
  vs 0.081, [10-30%) 0.165 vs 0.401 -> your_cost understates big losses ~2x (caveat: the playout model repairs
  less than real players), Spearman 0.12 (mP is noisy at 64 playouts: random moves P(mP >= 10%) = 0.05).
  WARNINGS IN TABLE POSITIONS are mostly false alarms: 220 of the 731 warnings come from exact-table positions
  (snake k>=6 tables fire from max 512 on); warn_move compares the table real loss (shared lossmap_table: table loss
  0.2% -> 0.9% real) with real_loss(thr) of the value maps (~0.6-0.8%), so table losses of 0.1-0.3% warn. 128 of
  215 such warnings have a table loss < 5% (mean mP 0.006, P(mP >= 10%) 0.13 ~ noise); only table losses >= 30%
  cost clearly (mean mP 0.115, n=12).
03:50 Engine truth, chunks 0-1 (expert + intermediate stretches): EXPERT key moments are real under engine
  continuation: K n=125 mean est 0.052, mean measured mE 0.087, P(mE >= 10%) 0.29 [80% CI 0.24-0.34] vs random moves
  0.016 (18x enrichment); warned moves P(mE >= 3%) 0.54, >= 10% 0.32; Spearman(est, mE) 0.47 on key+random; decisive
  moment (11 stretches) has mE >= 3% in 82%, is the largest measured loss in 36%, median rank 2. Magnitudes: the
  shrunk played-expert map (cal7) UNDERSTATES flagged expert moves: by claim (value loss) on search positions, claim
  20-40% -> est 0.068 vs mE 0.244 (n=22), >= 40% -> 0.276 vs 0.285 (n=12), 10-20% -> 0.015 vs -0.003 (n=27, P(mE >=
  10%) 0.48: very noisy), < 10% -> ~0 vs ~0 (unselected-like). INTERMEDIATE under engine continuation: almost nothing
  is a real loss: K mean est 0.017 vs mE 0.007, P(mE >= 10%) 0.008 (random 0), P(mE >= 3%) 0.12 vs random 0.05,
  Spearman 0.10 -> for non-experts the engine-based "real loss" carries little signal (the engine repairs early
  damage); the player-level truth (your_cost / mP) is where the signal is.
  Launched: chances-curve rollouts (scripts/review_curve.py: target = start rank + 2; 1,502 positions, done) and a
  FULL-COVERAGE player screen (scripts/review_full.py: all 22,160 judged non-expert positions with a playout skill,
  all moves, 32 CRN playouts, human model to the next milestone; scripts/review_roll_full.sh, 12 processes).
04:10 Engine truth complete (1,885 positions). Non-expert, P(mE >= 10%): key moments novice 0.15 / intermediate 0.01
  / strong 0.06 vs random 0.000 (0/375); warned moves 0.27 / 0.02 / 0.08; est vs mE on key+random: [10-30%) 0.203 vs
  0.102 (2x over), [30%+) 0.421 vs 0.441; Spearman 0.24 / 0.12 / 0.14 (expert 0.47). Decisive moment: mE >= 3% in
  novice 5/9, intermediate 1/6, strong 1/6, expert 9/11; largest measured loss of its stretch in 3/9, 1/6, 1/6, 4/11.
  KEY-MOMENT FLOOR: non-expert key moments by weight max(real_loss, your_cost): < 0.01 (29% of them) and 0.01-0.03
  (31%) are noise-level (engine mean mE 0.002; player P(mP >= 10%) 0.10-0.11 ~ noise); 0.03-0.10: player 0.34, mean
  mP 0.058; >= 0.10: 0.82, mean 0.429 -> 60% of the key moments shown to non-experts are trivial moves.
  Full-coverage player screen (32 playouts, 21,107 non-expert moves): noise-dominated (near-ties rms 0.137, P(mP >=
  20%) 0.040 ~ the rate of "big losses" overall 3.1%) -> only bin means are usable: your_cost [3-10%) 0.046 vs mP
  0.122 (n=180), [10-30%) 0.161 vs 0.269 (n=23), < 3% ~0 vs ~0 -> your_cost understates big losses ~2x (playout-model
  caveat). Novices: flags have P(mP >= 20%) 0.37-0.52 vs noise 0.04. Stage 2 launched: 256 playouts on all 1,107
  flagged non-expert moves + 1,000 random unflagged ones (precision / recall / calibration).
04:25 Instance-config check (coordinator's question): every job passed the engine and models explicitly - all 502
  rollout runs log `engine: weights/best_v6b.w` (4 engine-truth chunks with tables, 498 human-model runs); reviews ran
  `analyze --preset best --weights weights/best_v6b.w --calib data/calib/model.txt --personal-model
  data/calib/personal.txt` with the laptop's installed files of 02:47 (md5 27387cf6 / 9c9a0c0a). Nothing to rerun.
04:30 STAGE 2 (256 CRN playouts, human model at the fitted skill to the next milestone; P_ref >= 0.3; noise floor
  near-ties rms 0.040, P(mP >= 20%) 0.000): all 1,107 flagged non-expert moves (744 measured) + 1,000 random unflagged
  (887 measured), weighted to the populations (1,107 flagged, 22,402 unflagged).
  Precision, P(mP >= 20%) [P(mP >= 10%)]: novice key 0.30 [0.47], warn 0.43 [0.64], hint 0.29 [0.33], your_cost >= 3%
  0.38 [0.66], hard 0.10 [0.25], unflagged 0.024 [0.067]; intermediate key 0.01 [0.03], warn 0.02 [0.12], hint 0 (n=8),
  hard 0 [0.03], unflagged 0 [0.008]; strong key 0.01 [0.04], warn 0.01 [0.10], hint 0 (n=14), unflagged 0 [0.012].
  Recall of big losses (mP >= 20%), all non-expert: 0.35 (90% CI 0.20-0.55; 4 unflagged events) - novice 0.36; for
  mP >= 10% 0.23 (novice 0.27, intermediate 0.25, strong 0.14). Share of the total measured loss in flagged moves:
  novice 0.80; intermediate: no net loss to find (signed sums -2.9 flagged, -17.7 unflagged); strong 0.04 (0.5 vs
  12.4: strong players' losses are small and diffuse, not where the flags are). Big player-level losses are rare
  above novice level: ~3 (intermediate) and ~1 (strong) estimated in ~10,000 moves each.
  your_cost calibration (est vs measured mP by your_cost bin): novice [1-3%) 0.017 vs 0.044, [3-10%) 0.045 vs 0.128,
  [10-30%) 0.158 vs 0.407 (understates ~2.5-3x; Spearman 0.49); intermediate [3-10%) 0.040 vs 0.020 (Spearman
  -0.06); strong [3-10%) 0.049 vs 0.013 (Spearman 0.06) -> skill-independent your_cost is right in shape for novices
  only and carries no rank signal for intermediate/strong.
  Decisive moment at the player level: 15 measured, mP >= 10% in 10 (novice 7/7, intermediate 1/4, strong 2/4),
  median 0.187 (review's decisive_loss median 0.120). Alternative "largest your_cost >= 3%" fires in 47 stretches but
  its picks are mostly noise (median mP 0.025; intermediate 1/15 >= 10%) -> keep the engine-based decisive moment.
04:35 CONCLUSIONS - what a player can trust in a review today (best_v6b, model 27387cf6, personal v4)
  TRUST: (1) warnings in search-decided positions (non-expert P(mP >= 10%) 0.37 at 64 playouts vs random 0.05;
  novice 0.64 at 256); (2) the decisive moment when one is shown (engine mE >= 3% in 56-82% for novices/experts,
  player-level mP >= 10% in 10/15); (3) for novices: key moments, warnings, hints, your_cost >= 3% (precision 0.29-0.43
  for losses >= 20% of own chances, 10-18x the unflagged rate; flagged moves hold 80% of the measured loss); (4) for
  experts: key moments and warnings point at real engine-continuation losses (P(mE >= 10%) 0.29 / 0.32 vs random 0.016;
  Spearman est-vs-measured 0.47).
  DO NOT TRUST / CHANGE: (a) warnings in exact-table positions (220 of 731 warnings; P(mP >= 10%) 0.08 ~ random:
  table losses of 0.1-5% trigger them); (b) the 60% of key moments with weight < 0.03 (noise-level); (c) your_cost
  magnitudes (novices lose ~2.5x the estimate, intermediate/strong less; no rank signal above novice level); (d) hints
  and hard moments above novice level (no big losses at hints for intermediate/strong, n=22; hard moments cost
  ~nothing: mean mP -0.004); (e) recall: even for novices the flags catch only ~1/3 of the individual big losses at the
  player level (CI 0.20-0.55) - a review is not a complete list of mistakes; (f) expert magnitudes: the shrunk
  played-expert map understates flagged expert moves (claims 20-40%: est 0.068 vs measured 0.244, n=22).
  PROPOSALS (coordinator applies; cal7 owns the maps):
  P1 src/analyze.cpp:438 (warn_move, table branch; line numbers as of 04:40): before `if (t >= 0) return t >= calib.real_loss(thr,
     map_stage(A.board));` after `if (t >= 0) return t >= 0.10;` (warn only when the exact table itself says >= 10%
     real, i.e. table loss >= ~15%; measured: table loss < 15% -> mean mP 0.00-0.03 ~ noise, >= 30% -> 0.115).
  P2 src/analyze.cpp:1464 (after `if (key.size() > 5) key.resize(5);`): add `key.erase(remove_if(key.begin(),
     key.end(), [&](const KeyMoment& k) { return weight(k) < 0.03; }), key.end());` (needs <algorithm>; show "no key
     moments" when empty). Weight 0.03-0.10: player P(mP >= 10%) 0.34; >= 0.10: 0.82; < 0.03: 0.10 (noise).
  P3 keep the decisive moment as is (engine real loss >= 3% from a healthy position).
  P4 your_cost: refit lossmap_own by skill band (not only by phase) with >= 256-playout truth (results/review/
     stage2_measured.json + roll_s2 are a start: 1,631 positions); until then label it "rough" above novice level.
  P5 hints: restrict to phase 0 (largest tile <= 512) or to fitted skills below the novice/intermediate boundary until
     more data; hard moments: present as "hard-to-find moves" (puzzles), not as errors.
  P6 for cal7: lossmap_played_expert near identity above ~20% claims (flagged expert moves measure 0.24 at claims
     20-40%); the game-level check is dominated by small claims, which stay ~0.
  Files: scripts/review_select.py, review_run.sh, review_run2.sh, review_moments.py, review_roll.sh, review_pools.py,
  review_curve.py, review_roll_curve.sh, review_curve_report.py, review_full.py, review_roll_full.sh,
  review_full_report.py, review_stage2.py, review_roll_s2.sh, review_stage2_report.py, review_report.py; data in
  results/review/ (stretches, rev, rev2, moves.tsv, pool*, roll_e_*.tsv, roll_p, roll_c, roll_f, roll_s2,
  measured.json, full_measured.json, stage2_measured.json, report_tables.txt).
```
