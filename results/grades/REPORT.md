# Move grades (app v3, 2026-10-10)

The user's direction after the first playtest:
- Drop player levels and exact percentages.
- Grade every move as best / good / questionable / blunder.
- A blunder is an obvious mistake the AI would never make, such as taking tiles out of corners for no reason.
- The early game is a free stretch.
- Test every threshold in real situations, especially two sanity checks: a 2048+ tile moved out of its corner, and
  hitting random keys.

## The rule (src/analyze.cpp `grade_moves`)

All of it comes from one analysis at the engine's normal depth (p50 2 ms, p90 4 ms on 2,400 real positions).

**Best**
- The coach's move. That is the corner strategy up to 512 (the human move model at a strong skill, among moves the
  engine rates within 3% and with real loss at most 0.5%), and the engine's move from 1024 on.
- Or any move within 0.5% value loss of it: a depth-5 search picks such moves about 1 time in 4.

**Good:** 0.5-5% value loss (a depth-5 search still picks them 2-16% of the time).

**Questionable**
- Value loss of 5% or more: a depth-5 search picks such moves 2.4% of the time or less early, 1.5% or less later. That
  is "the coach would never play it". From 16384 the line is 10%.
- Or a big tile (at least a quarter of the biggest) pulled off the edge while a fine move avoids it.

**Blunder**: an obvious, named mistake.
- The biggest tile leaves its corner while a fine move keeps it there (not when the move makes a new biggest tile).
- The biggest or second-biggest tile is pulled off the edge while a fine move avoids it.
- 10%+ of the new tiles leave no move, while another move is at least 10 points safer.
- The engine measures a real loss of 10% or more.

A fine move is one with value loss below 5% and no danger. These verdicts read the board, not the engine's value: the
engine repairs a 2048 out of its corner and calls it cheap (real loss 0.6% in the user's example).

**Free stretch:** up to a largest tile of 256 there are no corner or edge verdicts. The rollouts of workstream yc showed
such moves cost nothing there, even for human-like players.

**The coach's %**
- How often the coach would play each move: exp(-value loss / 0.015), normalized.
- The temperature is fitted (maximum likelihood) to which move a depth-5 search prefers on the same 2,400 positions:
  0.015 for both the early and the mid game.
- The coach's move gets the top share.

**Cells:**
- `hint_cells`: where the coach's move acts (its largest merge, else the plan's next cell).
- `fault_cells`: where a flagged move went wrong (the biggest tile's new cell and the corner it left, the cells where a
  new tile ends the game, the big tile off the edge).

## Checks in real situations (scripts/grades_check.py, check.txt)

Data: 250 real positions per largest tile, 60 random-key runs per stage.

| largest tile | A. corner left (another move keeps it): blunder | B. one random key: flagged | C. 15 random keys in a row: flagged, first flag after |
|---|---|---|---|
| 256 | 0/135 (free stretch, by design) | 20% (questionable) | 30%, 3 moves |
| 512 | 149/152 = 98% | 38% | 43%, 3 moves |
| 1024 | 150/150 = 100% | 27% | 41%, 2 moves |
| 2048 | 168/168 = 100% | 36% | 46%, 3 moves |
| 4096 | 164/166 = 99% | 33% | 47%, 2 moves |
| 8192 | 163/164 = 99% | 34% | 42%, 2 moves |

The few corner moves that are not blunders are the engine's own choice (the coach's move is never flagged). A random
key is flagged a third of the time from 512 on: a random key is often one of the two or three harmless directions.

Real players' moves are a reference only; the app has no levels.

| players | moves | best | good | questionable | blunder |
|---|---|---|---|---|---|
| strong | 4,000 | 91% | 7% | 1.8% | 0.23% (about 1 in 430 moves) |
| intermediate | 619 | 77% | 14% | 8% | 0.5% |
| novice | 74 | 62% | 19% | 16% | 2.7% |

The strong players' blunders checked by hand are real:
- an 8192 or 4096 taken out of its corner;
- a 2048 pulled off the edge;
- moves after which a tenth of the new tiles end the game.

The selftest (case 12) pins the user's cases:
- a 2048 out of its corner is a blunder;
- the 2048 next to a 4096 pulled off the edge is one;
- a game-ending move is one, with the deadly cells;
- leaving the corner with a 128 is not flagged;
- the coach's move is best with the top share.

The app's QA journeys replay the same cases in the browser:
- **corner-blunder:** a blunder, and "Warn me" stops it;
- **edge-blunder:** a blunder;
- **random-keys:** 4 of 6 moves flagged, the first right away;
- **free-stretch:** quiet.

## Lessons

- Engine value thresholds alone miss what matters to people: the engine sees almost no loss for a corner break it can
  repair. Structural rules catch it every time and come with a reason.
- Test randomness must be real randomness. A linear congruential generator taken mod 4 pressed the same key 11 times,
  and it looked like the coach missed random play.
