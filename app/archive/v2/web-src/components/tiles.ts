// Tile views for the animated board: every tile keeps its id while it slides; two merging tiles slide onto the same
// cell as "ghosts" (removed after the animation) under the new merged tile, which pops; the new random tile appears.
import type { Board, SlideStep, Spawn } from '@shared/rules.ts';

export type TileKind = 'idle' | 'new' | 'merged' | 'ghost';

export interface TileView {
  id: number;
  rank: number;
  cell: number;
  kind: TileKind;
}

let nextId = 1;

export function tilesFromBoard(board: Board, kind: TileKind = 'idle'): TileView[] {
  const out: TileView[] = [];
  board.forEach((rank, cell) => {
    if (rank) out.push({ id: nextId++, rank, cell, kind });
  });
  return out;
}

export function tilesAfterMove(prev: TileView[], steps: SlideStep[], after: Board, spawn: Spawn | null): TileView[] {
  const byCell = new Map<number, TileView>();
  for (const t of prev) if (t.kind !== 'ghost') byCell.set(t.cell, t);
  const out: TileView[] = [];
  const merged = new Set<number>();
  for (const s of steps) {
    const t = byCell.get(s.from);
    if (!t) continue;
    if (s.merged) {
      out.push({ ...t, cell: s.to, kind: 'ghost' });
      if (!merged.has(s.to)) {
        merged.add(s.to);
        out.push({ id: nextId++, rank: after[s.to], cell: s.to, kind: 'merged' });
      }
    } else out.push({ ...t, cell: s.to, kind: 'idle' });
  }
  if (spawn) out.push({ id: nextId++, rank: spawn.rank, cell: spawn.cell, kind: 'new' });
  return out;
}

/** Drops the ghosts and settles the animation states (after the slide). */
export function settle(tiles: TileView[]): TileView[] {
  return tiles.filter((t) => t.kind !== 'ghost');
}
