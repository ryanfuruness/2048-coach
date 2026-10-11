# Engine changes for the app (src/analyze.cpp)

Two small options, each behind its own command-line flag. Without the flags `build/analyze` behaves exactly as before:
verified byte-for-byte (timing field `ms` aside) on stdin analyses and on a full game review, and
`build/analyze --selftest` passes (0 failures, with `--preset best-notables --packed weights/serve/v6c_i16.wp` and
with the default preset).

Files here:

- `app-flags.diff`: the complete change (`diff -u analyze.cpp.orig src/analyze.cpp`, 125 lines with context).
- `analyze.cpp.orig`, `analyze.bin.orig`: the source and the binary before the change (for comparisons).

Rebuild after applying: `make -j8` (only `build/analyze` is rebuilt, ~20 s).

## 1. `--stdin-player`: the player's skill and recent moves per request

**Why the app needs it.** Hints, `error_risk`, `find_prob`, the skill-banded `your_cost` and the personal odds all
depend on the player's skill, which differs between players and changes as the app learns it. In `--stdin` mode the
skill was a command-line option (`--skill`), fixed for the life of the process, and the human move model's move
history was always empty. The alternative, one resident engine per skill value, costs 775 MB each.

**What it does.** With the flag, a request line may carry two more options before the `|`:

```
skill=-0.5 hist=LLDRDL | 0 2 4 8 0 0 16 32 0 2 64 128 2 4 256 512
```

- `skill=THETA`: as `--skill THETA`, for this line only (clamped to the human model's grid, -3 to 3; non-numbers are
  ignored). The next line starts again from the command-line value.
- `hist=MOVES`: the player's recent moves, oldest first (`U R D L`, either case), pushed into the human model's history
  (`hm::History`, which keeps the last 20) exactly as a review fills it.

Without the flag both keys are ignored, as any unknown key was before.

**Checks.** (a) Without the flag, lines with `skill=`/`hist=` give output identical to the original binary. (b) With the
flag, `skill=-0.8 | BOARD` gives output identical to `--skill -0.8` for the same boards. (c) A `skill=` line followed by
a plain line: the plain line's output is identical to the original binary's. (d) For 30 positions of a real game,
`skill=-0.5 hist=<previous 20 moves>` reproduces the review's `find_prob`, `error_risk` and `hint` (run with
`--review ... --skill -0.5`) exactly.

**Code.** `main()`: one flag variable and its parsing; in the `--stdin` loop: save `human_theta` before the loop and
restore it per line, parse the two keys when the flag is set, and push `hist` into `cur_hist` after it is cleared.

## 2. `--review-moves`: reviews take the moves the player made

**Why the app needs it.** `--review FILE` infers the move between two consecutive boards. With exact boards that is
usually unique, but not always: when two moves leave afterstates that differ only by where one small tile sits, the new
random tile can make both explain the next board. On 64,591 moves of simulated corner-strategy games, 0.7% of the
board pairs were explained by two moves (17 of the 3,000 moves of an engine game). `infer_path` then takes the first
direction in up/right/down/left order, so about half of these moves were attributed to the wrong move: their loss,
reasons, warnings and the skill fit were computed for a move the player never made (possibly flagged as a blunder).
The app knows every move exactly, so it passes them.

**What it does.** With the flag, a line of the review file may end with the move played from that board, after a
space: `BOARD U` (`U R D L`). If that move followed by one new tile leads to the next board (`move_explains`), it is
used as the step; otherwise (or without a move) the frames are inferred as before. The board part of the line is read
as before (16 hex digits or 16 tile values).

**Checks.** (a) Without the flag, the review of `results/review/stretches/nov00.txt` is identical to the original
binary's, and a file with appended moves gives the same output as without them. (b) With the flag, on a 3,000-move
engine game whose ambiguous moves were deliberately given as the *other* explaining move, exactly those 17 plies
change their `played` move; all other plies keep it.

**Code.** A helper `move_explains(a, d, b)` next to `infer_path`; in the review: an optional trailing move token is read
from each line (and blanked before `parse_board`), kept in `seq_move`, and used instead of `infer_path` when it
explains the frame pair.

## How the app server uses them

- Resident workers: `build/analyze --preset best-notables --packed weights/serve/v6c_i16.wp --stdin --stdin-player`.
- Reviews: `build/analyze --preset best-notables --packed <light or full> --review FILE --json --max-gap 1 --review-moves`
  (`--max-gap 1`: consecutive boards are always one move apart, so no multi-move bridging is ever considered). The
  server also checks that every given move leads to the next board before it calls the engine, and that the engine
  reports the same `played` move for every ply.
