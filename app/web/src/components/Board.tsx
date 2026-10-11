import type { ComponentChildren } from 'preact';
import type { Board as BoardT, Dir } from '@shared/rules.ts';
import { tileValue } from '@shared/rules.ts';
import { type TileView, tilesFromBoard } from './tiles.ts';
import { useEffect, useMemo, useRef } from 'preact/hooks';

export interface BoardArrow {
  dir: Dir;
  tone: 'best' | 'warn' | 'played' | 'same';
  label?: string;
  /** makes the arrow a button (e.g. play the coach's move) */
  onClick?: () => void;
  title?: string;
}

/** A highlighted cell: where a move went wrong. */
export interface CellMark {
  cell: number;
  tone: 'fault';
}

interface Props {
  tiles?: TileView[];
  board?: BoardT;
  arrows?: BoardArrow[];
  marks?: CellMark[];
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

const DIR_WORDS = ['up', 'right', 'down', 'left'];

function Arrow({ a }: { a: BoardArrow }) {
  const rot = [0, 90, 180, 270][a.dir];
  const body = (
    <>
      <svg viewBox="0 0 24 24" width="22" height="22" style={{ transform: `rotate(${rot}deg)` }} aria-hidden="true">
        <path d="M12 4l7 8h-4.5v8h-5v-8H5z" fill="currentColor" />
      </svg>
      {a.label && <span>{a.label}</span>}
    </>
  );
  if (a.onClick)
    return (
      <button
        type="button"
        class={`board-arrow ${POS[a.dir]} ${a.tone} clickable`}
        onClick={(e) => {
          a.onClick!();
          if (e.detail > 0) (e.currentTarget as HTMLElement).blur();
        }}
        title={a.title}
        aria-label={[a.label, a.title ?? `play ${DIR_WORDS[a.dir]}`].filter(Boolean).join(': ')}
      >
        {body}
      </button>
    );
  return (
    <div class={`board-arrow ${POS[a.dir]} ${a.tone}`} aria-hidden="true">
      {body}
    </div>
  );
}

/** The 4x4 board: animated tiles (or a static board), optional arrows, highlighted cells and clickable cells. */
export function Board(p: Props) {
  const tiles = useMemo(() => p.tiles ?? (p.board ? tilesFromBoard(p.board) : []), [p.tiles, p.board]);
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
          <div class="cell" key={i} />
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
      {p.marks && p.marks.length > 0 && (
        <div class="board-marks" aria-hidden="true">
          {p.marks.map((m) => (
            <div key={`${m.tone}${m.cell}`} class={`mark ${m.tone}`} style={{ '--r': Math.floor(m.cell / 4), '--c': m.cell % 4 }} />
          ))}
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
