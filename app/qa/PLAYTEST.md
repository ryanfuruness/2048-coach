# Playtest log

Newest last. Each entry: what the playtester saw, what it means for "useful to humans", what changed.

## 2026-10-10, first session (the user, a strong player)

### 1. The odds don't react to bad play

**Observation.**
- However badly they played, even random moves early on, the chance of 2048 and beyond stayed near 100%.
- Warnings only came on the final, game-destroying move.
- With a 4096, moving it out of its corner was not flagged, and the bar still showed 98% for 8192.

**Diagnosis.** Every number was the engine's: its odds if it took over, its real loss, warnings and personal odds
built on its value. The engine repairs almost anything early on, so a move that is costly for a person is free for it.

**Change.** "Your chance" is now the main evaluation. Measurements are in results/yc/REPORT.md.
- **What it is.** The chance that a player of your level, playing on, reaches the next milestone. It comes from
  simulated human-like players.
- **Where it shows.** The bar, the grades, the warnings, the timeline and the review.
- **Your 4096 case.** Your chance of 8192 drops from 95% to 57% at a strong level (from 12% to 0.4% at the default
  level), with a warning. The engine's real loss is 6%.
- **The same with a 2048.** Your chance of 4096 drops from 81% to 16%.

**Still true.** Random moves in the first ~70 moves (tiles up to 64) don't lower even a simulated human's chance. The
600-game rollouts from those positions agree with the model, so the bar stays put there.
- A corner-leaving move that costs nothing yet now gets a note: "Left the corner · → Right keeps it · costs from 256
  on".
- From 256 on such moves are graded (2-3 points at 256, 17-20 points with a 2048).

**Open.** A live skill within the game, so "your chance" reflects a run of poor play. It needs a next-doubling target
for weak players first.

### 2. The coach's early moves make no sense to a person

**Observation.** Accepting the coach's suggestions early on gives unintuitive moves. It doesn't care where the biggest
tile is or about getting it into a corner. Later, from 2048 on, the coach is helpful.

**Diagnosis.**
- Measured with rollouts: in corner positions the engine keeps the biggest tile in its corner in only 5 of 19 positions
  at 64, 5 of 17 at 128 and 10 of 22 at 256.
- From 512 on it keeps the corner itself: 20 of 21, then all of them.
- Its early moves cost a human nothing on average; they just look arbitrary.

**Change.** This was the user's own suggestion: separate concerns.
- Up to 512 the coach plays the corner strategy: the move of the human move model at a strong skill, using your recent
  moves.
- It picks only among moves that cost nothing.
- From 1024 on it plays the engine's move.
- The analysis says why ("keeps your 128 in its corner") and names the engine's preference.

## 2026-10-10, second round: simplify around the grades

**Feedback.**
- Too noisy: too much text, too many options and diagrams.
- Drop player levels and exact percentages; the AI's percentages are the only ones that matter, and not as a big bar.
- Grade moves as blunder, questionable, or good but not optimal.
- Toggles instead of mode tabs, plus one toggle to hide it all.
- "Deeper" was unclear.
- The coach must keep up in real time.
- Highlights should be optional and only where the action is.
- Keep "coach plays N moves" and the move percentages.
- Be wary of thresholds that never trigger: a 2048+ tile out of its corner and random keys must.

**Changes (app v3; DECISIONS.md, results/grades/REPORT.md).**
- **Grades:** best / good / questionable / blunder. Blunders come from board rules with named reasons.
- **Sanity checks:**
  - the 2048 snake moved Down: "Blunder · Takes your 2048 out of its corner", and Warn me stops it;
  - the 4096 snake moved Down: "Blunder · pulls your 2048 off the edge";
  - random keys at 512 and up: 41-47% flagged, the first after 2-3 moves.
- **Free stretch:** up to 256, not graded for the corner.
- **Screen:** board, one grade line, undo/redo, coach plays 1/10/100/next tile/∞, four toggles, a move list (grade + %).
  The engine's odds are behind a link.
- **Real time:** 2 ms per verdict. With Warn me on, a move waits for the verdict if needed. Deeper removed.

**Note.** A test bug looked like "random keys are not flagged": its random-number generator pressed the same key 11
times. The QA journey now uses a proper generator.

## 2026-10-10, third round: the coach panel

**Feedback.**
- Space still played with the coach off.
- Move "coach plays" to the bottom of the right panel.
- The coach toggle should be prominent and clearly tied to the panel.
- The reasons for each move could come back as an option.
- Highlights lost its description.
- Engine odds deserve cards with a bar.

**Changes (v3.1, DECISIONS.md).**
- The panel is the coach: a big switch in its header folds it.
- Space and P do nothing with the coach off (checked in the coach-toggles journey).
- Options are rows with one-line descriptions, plus Explain (reasons and the plan).
- Odds are cards with bars; "the coach plays" is at the bottom of the panel.
