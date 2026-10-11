# Is the coach's least preferred move worse for a human? (2026-10-11)

The question was whether "Questionable" or "Least preferred" could come from the coach's ranking alone (its lowest %
move), even when the moves are close.

**Data.** The "your chance" ground truth (results/yc), so no new compute:
- 210 real positions, 30 per biggest tile from 64 to 4096.
- 400 simulated-human playouts per legal move, at two skill keys.
- The engine's value loss per move on the same positions.

Script: `scripts/worstmove_check.py`. Table: `table.md`.

| biggest tile | worst-ranked move vs the others, for the human (points) | worst-ranked = the human's worst (picking at random: ~27%) |
|---|---|---|
| 64-256 | -1.5 to +0.2 (noise) | 20-48% |
| 512 | about -4 | 64-79% |
| 1024-2048 | -8 to -19 | 89-100% |
| 4096 | -3 to -10 | 61-86% |

The second-worst move carries nothing at any stage.

**Verdict: no rank-based grade.**
- Early on, the ranking of near-equal moves is noise for a person.
- From 512, where the worst move really is worse, the gap is large (median 10-17%). The value-loss rule already grades
  it Questionable.
- So early grades come from board rules (`src/analyze.cpp` grade_moves; `results/grades/REPORT.md`, the 2026-10-11
  section).
