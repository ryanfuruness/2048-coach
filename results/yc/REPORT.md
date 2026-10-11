# Workstream yc: your chance (2026-10-10)

The user's first playtest found two problems with the app:

1. **No reaction to bad play.** However badly they played, even random moves early on, the chance of 2048 stayed near
   100%. Warnings only came on the final game-ending move. With a 4096, moving it out of the corner was not flagged and
   still showed 98% for 8192.
2. **Unintuitive early recommendations.** The engine's suggested opening moves do not care where the biggest tile is.

The root cause of both is that every number was the engine's: what the engine would make of the position if it took
over. That includes the personal odds, which were a function of the engine's value. The engine repairs almost anything
early on. The fix is an evaluation by a human-like player's own continuation, plus a legible coach's move in the
opening.

## 1. Ground truth: what moves do to a human player's chance

Positions: 210 real positions (scripts/yc_select.py: 30 per largest tile from 64 to 4096; half of them have a move
that keeps the biggest tile in its corner and one that does not).

Rollouts: src/hv_tool.cpp `first`, 400 playouts per legal move. The player is the simulated human player of the
personal odds (src/hplayer.h: the human move model plus care in danger), at keys 0.016 (the app's default level) and
0.007 (intermediate/strong). Playouts run to the milestone (2048, then each doubling). The best move is chosen on half
the playouts and measured on the other half, so the numbers carry no selection bias.

| largest tile | chance (key .007 / .016) | best corner-keeping minus best corner-leaving move | engine keeps the corner |
|---|---|---|---|
| 64 | 0.78 / 0.37 | -1.5 / -0.6 points (noise) | 5 of 19 |
| 128 | 0.78 / 0.37 | +0.9 / +0.5 | 5 of 17 |
| 256 | 0.80 / 0.40 | +3.2 / +1.6 | 10 of 22 |
| 512 | 0.82 / 0.46 | +5.9 / +4.5 | 20 of 21 |
| 1024 | 0.89 / 0.69 | +7.3 / +10.5 | 20 of 20 |
| 2048 (P 4096) | 0.74 / 0.42 | +19.8 / +16.8 | 25 of 25 |
| 4096 (P 8192) | 0.25 / 0.06 | +8.7 / +3.3 | 25 of 25 |

For the engine all of these moves cost about 0 real loss. On average the engine's own move costs a human nothing at any
stage (-1.4 to +2.1 points, within noise). It just looks arbitrary up to 256.

A random game backs up finding 1 for the very early game. Positions from 76 random moves (up to a 64 tile, boards
nearly full at moves 70-76) were measured with 600 playouts per move. The simulated players kept their chance of
2048: 0.34-0.39 at key .016 and 0.91-0.93 at key .0013, the same as from the opening. Early messes are cleaned up.
What matters is the corner from about 256 on, and not letting the board fill.

## 2. The model: TD evaluation of the player's own chance

Code and files:

- src/hvalue.h: the networks.
- src/hv_tool.cpp `train` / `recal` / `eval` / `calib`.
- scripts/yc_train_family.sh: trains every key.
- weights/calib/chance.hv: 6 keys, 63 MB.

Network:

- Per key and stage (the afterstate's largest tile: up to 64, then 128 through 8192), a logistic n-tuple network.
- Five 4-tuples (rows and 2x2 squares, 8 symmetries) plus 6 global tables:
  - corner distance x empty cells
  - chain length
  - exposed cells
  - trapped tiles
  - big tiles off the edge
  - merges

Training:

- TD with lambda-returns: lambda 0.95, horizon 64.
- Every afterstate moves toward the expected value of the next one under the player's own move probabilities.
- Side samples: 25% of the moves also train a non-chosen move's afterstate, so bad moves are covered.
- Games start 50% from the initial board and 50% from 79,000 real positions with the players' real last 20 moves.
- 100M updates per key, about 5 min on 16 threads.
- Then a recalibration per stage (sigmoid(a + b z)) on 2,000 games per key, 70% of them from real positions.

The chance after a move is multiplied by the share of new tiles that do not end the game. The networks see only the
afterstate and under-rated a game-ending move on a full board (15% instead of 2%).

Dead ends:

- TD(0) with random exploratory moves: about 0.1-0.3 too low. The exploration polluted the player's habits.
- lambda 1 with clipped returns: far too high.
- 5-tuples: no gain at 60M updates.

Against the ground truth (keys .016 and .007, 210 positions):

- Mean chance within 0.01-0.03 at every stage.
- Between positions: correlation 0.86-0.99 from 512 up.
- Within a position, each move's deviation from the mean of its position's moves, model vs rollouts: correlation
  0.864 overall, 0.91-0.95 at 2048-4096. Rollout noise (SE about 2.5 points per move) caps this.
- The corner differences are reproduced. At 2048: model 15.6-18.4 points, rollouts 19.0-20.6.

## 3. Real games

Data: 83,000 positions of 237 games, 43 of which end in an observed death (scripts/yc_real.py, yc_real_report.py).

| tier (key) | your chance from here (mean) | observed reach | AUC |
|---|---|---|---|
| intermediate (.007) | 0.805 | 0.829 | 0.76 (milestone 4096: 0.87) |
| strong (.003) | 0.523 | 0.700 | 0.93 |

The model is pessimistic for strong players, as the personal odds were.

Does the played move's cost carry information beyond the position? A logistic fit of the outcome on logit(chance
before the move) plus the move's cost in logit units gives -1.18 [-2.22, -0.44] (game-clustered bootstrap). A
calibrated cost would sit at about -1. So moves the model calls costly are followed by worse real outcomes.

Rates per 100 real moves at the default level (key .016; intermediate / strong players' moves):

| class | rule | per 100 moves |
|---|---|---|
| inaccuracy | 5% of your chance and 2 points | 7.5 / 5.1 |
| mistake | 10% of your chance and 2 points | 2.4 / 3.0 |
| blunder | 25% of your chance and 4 points | 0.14 / 0.47 |
| warning | 20% of your chance and 2 points | 0.33 / 1.6 |

The coach study found one or two warnings per 100 moves the most efficient amount.

## 4. What the engine and the app do with it

Engine: `build/analyze` loads weights/calib/chance.hv by default. Up to a largest tile of 8192 it adds:

- `chance` {target, now, best, skill, key};
- `chance` and `chance_loss` per move;
- `warn` by the chance rule (20% and 2 points; elsewhere the old rule).

The skill is the player's, floored at the app's default of -0.5. Novice-level simulated players never reach 2048,
real novices rarely do, and a chance of 0 everywhere says nothing about their moves.

`coach_move` and `coach_why`:

- Up to 512: the move of the human move model at skill 0.5, using the player's recent moves. That is the corner
  strategy: biggest tile in its corner, the edge line, three directions.
- It is picked among moves with real loss at most 0.5% and at most 1 point of your chance.
- From 1024 on: the engine's move.
- The selftest checks it (case 12).

App, "your chance" everywhere:

- the eval bar, with a mark for the engine's odds and the last move's cost in points;
- the verdict under the board, with your chance before and after the move;
- the move list;
- the warning sheet;
- the timeline and the review graph, both on a plain scale;
- the review's classes, decisive moment and key moments.

Space, the board's arrow and autoplay play `coach_move`. In the opening, a corner-leaving move that costs nothing
measurable gets a note instead of a grade: "Left the corner · Right keeps it · costs from 256 on".

The user's two scenarios, with the full engine:

- **A 4096 snake, Down pulls the 4096 out of its corner.** Your chance of 8192 drops from 12% to 0.4% at the default
  level, and from 95% to 57% at a strong level (skill 0). Both get a warning. The engine's real loss is 6%.
- **The same with a 2048.** Your chance of 4096 drops from 81% to 16%; the engine says 0.6%.
- **Opening (128 64 16 4 / 8 4 2 . / 2 ...).** The engine plays Down, taking the 128 out of its corner. The coach plays
  Right ("keeps your 128 in its corner").

## Open

- **Weak players and the 2048 target.** For players whose chance of 2048 is near 0 (novices), the next doubling would
  be the informative target. That needs networks for that target (stages up to 512).
- **A live skill within the game.** It would let "your chance" reflect a run of poor play: "if you keep playing like
  this". It needs the weak-player target above to show anything below the default level.
- **Strong players.** The model is pessimistic for them, as the personal odds were.
- **Size.** Quantizing the networks to int16 would halve the file (63 MB of float32 now).
