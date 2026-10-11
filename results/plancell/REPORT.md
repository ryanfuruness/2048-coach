# Does the coach follow the plan cell? (2026-10-10)

The question: is it worth labelling the plan's next cell on the board, e.g. "build an 8 here"? Today that cell is the
green highlight whenever the coach's move makes no merge of 8 or more.

**Method.** `scripts/plancell_check.py`. 1,200 real positions with a biggest tile of 64 or more and a plan next cell.
From each, the app's coach plays on through the local API: 64 moves, up to 1,200 when the plan needs a big tile. We
follow the chain's end tile and record what happens first. Tables: `check.md`. Records: `records.json`.

| step | n | doubles via the plan cell | doubles via another cell | chain end or corner moves first | nothing |
|---|---|---|---|---|---|
| merge (equal tile already there) | 117 | 92% | 2% | 6% | 0% |
| grow (smaller tile there) | 796 | 45% | 21% | 29% | 5% |
| build (cell empty) | 91 | 37% | 14% | 43% | 5% |
| blocked (bigger tile there) | 196 | 8% | 57% | 34% | 1% |

- **Today's green in the plan case** agrees with what the coach then does 40% of the time. It goes elsewhere 24% of the
  time, and the chain moves first 31% of the time.
- **Biggest tile 64-256:** the plan cell is followed 25% of the time, and the chain moves first 64% of the time. The
  coach's corner-strategy opening reshapes freely.
- **Caveat: "moves first" overstates disruption.** It counts a chain that shifts once and comes back. Among positions
  where the end tile does double, the plan cell wins about 2:1 for grow and build.

**Verdict.**
- An instruction label ("build an 8 here") would be wrong more often than right. The cell is right only when it is
  obvious (merge).
- Today's unlabelled green has the same problem.
- "Blocked" is a real, non-obvious state: the coach almost never goes through the blocked cell.
