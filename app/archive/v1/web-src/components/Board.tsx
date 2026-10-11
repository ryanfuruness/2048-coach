import type { ComponentChildren } from 'preact';
import type { Board as BoardT, Dir } from '@shared/rules.ts';
import { tileValue } from '@shared/rules.ts';
import { type TileView, tilesFromBoard } from './tiles.ts';
import { useEffect, useMemo, useRef } from 'preact/hooks';

export interface BoardArrow {
  dir: Dir;
  tone: 'best' | 'warn' | 'played' | 'same';
  label?: string;
}

interface Props {
  tiles?: TileView[];
  board?: BoardT;
  arrows?: BoardArrow[];
  chain?: number[];
  nextCell?: number;
  onCell?: (cell: number) => void;
  cellLabel?: (cell: number) => string;
  selectedCell?: number;
  shakeKey?: number;
  dim?: boolean;
  label: string;
  class?: string;
  children?: ComponentChildren;
}

const POS = ['top', 'right', 'bottom', 'left'] as const;

export function digitsClass(rank: number): string {
  const n = String(tileValue(rank)).length;
  return `d${Math.min(n, 7)}`;
}

export function tileClass(rank: number): string {
  return rank > 17 ? 't18' : `t${rank}`;
}

function Arrow({ a }: { a: BoardArrow }) {
  const rot = [0, 90, 180, 270][a.dir];
  return (
    <div class={`board-arrow ${POS[a.dir]} ${a.tone}`} aria-hidden="true">
      <svg viewBox="0 0 24 24" width="22" height="22" style={{ transform: `rotate(${rot}deg)` }}>
        <path d="M12 4l7 8h-4.5v8h-5v-8H5z" fill="currentColor" />
      </svg>
      {a.label && <span>{a.label}</span>}
    </div>
  );
}

/** The 4x4 board: animated tiles (or a static board), optional arrows, plan highlights and clickable cells. */
export function Board(p: Props) {
  const tiles = useMemo(() => p.tiles ?? (p.board ? tilesFromBoard(p.board) : []), [p.tiles, p.board]);
  const chain = new Set(p.chain ?? []);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!p.shakeKey || !ref.current || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    ref.current.animate(
      [{ translate: '0' }, { translate: '-6px' }, { translate: '5px' }, { translate: '-3px' }, { translate: '0' }],
      { duration: 260, easing: 'ease-out' },
    );
  }, [p.shakeKey]);
  return (
    <div ref={ref} class={`board ${p.class ?? ''} ${p.dim ? 'dim' : ''}`} role="group" aria-label={p.label}>
      <div class="board-grid" aria-hidden="true">
        {Array.from({ length: 16 }, (_, i) => (
          <div class={`cell ${chain.has(i) ? 'chain' : ''} ${p.nextCell === i ? 'next' : ''}`} key={i} />
        ))}
      </div>
      {tiles.map((t) => (
        <div
          key={t.id}
          class={`tile ${tileClass(t.rank)} ${digitsClass(t.rank)} ${t.kind}`}
          style={{ '--r': Math.floor(t.cell / 4), '--c': t.cell % 4 }}
        >
          <span>{tileValue(t.rank)}</span>
        </div>
      ))}
      {(p.chain?.length || p.nextCell !== undefined) && (
        <div class="board-marks" aria-hidden="true">
          {Array.from({ length: 16 }, (_, i) =>
            chain.has(i) || p.nextCell === i ? (
              <div key={i} class={`mark ${p.nextCell === i ? 'next' : 'chain'}`} style={{ '--r': Math.floor(i / 4), '--c': i % 4 }} />
            ) : null,
          )}
        </div>
      )}
      {p.onCell && (
        <div class="board-hit">
          {Array.from({ length: 16 }, (_, i) => (
            <button
              type="button"
              key={i}
              class={`hit ${p.selectedCell === i ? 'sel' : ''}`}
              style={{ '--r': Math.floor(i / 4), '--c': i % 4 }}
              aria-label={p.cellLabel ? p.cellLabel(i) : `Cell ${i + 1}`}
              onClick={() => p.onCell!(i)}
            />
          ))}
        </div>
      )}
      {p.arrows?.map((a) => <Arrow a={a} key={`${a.dir}-${a.tone}`} />)}
      {p.children}
    </div>
  );
}
