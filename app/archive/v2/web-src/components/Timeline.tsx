import { useLayoutEffect, useMemo, useRef, useState } from 'preact/hooks';
import { tileValue } from '@shared/rules.ts';
import { shareClass } from '../lib/chance.ts';
import { chance, pctShort } from '../lib/format.ts';
import type { Line } from '../lib/line.ts';

interface Props {
  line: Line;
  /** the line's version: redraws when moves or facts change */
  version: number;
  cursor: number;
  onSeek: (k: number) => void;
  disabled?: boolean;
}

const H = 60;
const PAD = 8;
const TOP = 7; // chance area: TOP (100%) .. AREA_B (0%)
const AREA_B = 37;
const TICK_B = 53; // cost ticks rise from here
const BAND_T = 56; // the coach's moves: a band at the bottom
const FAIL_MIN = 0.001;

/**
 * The height of a chance: your chance on a plain scale (0-100%); the engine's odds (16384 and up, where they stay
 * near 100%) on a scale stretched near 100% (log of the chance to fail), as the review graph.
 */
function yChance(p: number, you = true): number {
  if (you) return AREA_B - Math.max(0, Math.min(1, p)) * (AREA_B - TOP);
  const f = Math.max(FAIL_MIN, Math.min(1, 1 - p));
  return TOP + ((Math.log10(f) - Math.log10(FAIL_MIN)) / -Math.log10(FAIL_MIN)) * (AREA_B - TOP);
}

const TICK_H = { inaccuracy: 5, mistake: 10, blunder: 15 } as const;

/**
 * The line as a scrubber: every position from the start (left) to the end of the line (right), with the chance of the
 * next milestone (where an analysis said it), the cost of the player's own moves, the stretches the coach played and
 * the new big tiles. Drag or click to go to a position; with the keyboard: arrows, Page Up/Down, Home/End.
 */
export function Timeline(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  const drag = useRef(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const line = p.line;
  const n = line.n;
  const plotW = Math.max(1, w - 2 * PAD);
  const x = (k: number) => PAD + (n === 0 ? 0 : (k / n) * plotW);
  const kAt = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    return Math.max(0, Math.min(n, Math.round(((clientX - r.left - PAD) / plotW) * n)));
  };

  const drawn = useMemo(() => {
    if (w === 0) return null;
    const buckets = Math.max(1, Math.min(n + 1, Math.floor(plotW / 1.5)));
    const span = (n + 1) / buckets;
    let path = '';
    let area = '';
    let seg: string[] = [];
    const flush = () => {
      if (seg.length > 1) {
        path += 'M' + seg.join('L');
        const x0 = seg[0].split(',')[0];
        const x1 = seg[seg.length - 1].split(',')[0];
        area += `M${x0},${AREA_B}L${seg.join('L')}L${x1},${AREA_B}Z`;
      } else if (seg.length === 1) {
        const [sx, sy] = seg[0].split(',');
        path += `M${Number(sx) - 1},${sy}L${Number(sx) + 1},${sy}`;
      }
      seg = [];
    };
    const ticks: { x: number; h: number; cls: string }[] = [];
    for (let b = 0; b < buckets; b++) {
      const lo = Math.floor(b * span);
      const hi = Math.max(lo + 1, Math.floor((b + 1) * span));
      // the worst chance in the bucket (a dip stays visible on a long line) and the costliest own move
      let pm: number | null = null;
      let pmYou = true;
      let cls: 'blunder' | 'mistake' | 'inaccuracy' | null = null;
      const rank = { inaccuracy: 1, mistake: 2, blunder: 3 } as const;
      for (let k = lo; k < hi && k <= n; k++) {
        const f = line.facts[k];
        if (f && f.p !== null && (pm === null || f.p < pm)) (pm = f.p), (pmYou = !!f.you);
        if (k < n && f && typeof f.loss === 'number' && line.rec.by[k] !== 'c') {
          // the costliest own move: by the share of your chance it gave away (or the engine's real loss)
          const c = shareClass(f.loss, f.you ? 'chance' : 'engine', f.p);
          if (c && (!cls || rank[c] > rank[cls])) cls = c;
        }
      }
      const bx = x(Math.min(n, (lo + hi - 1) / 2));
      if (pm === null) flush();
      else seg.push(`${bx.toFixed(1)},${yChance(pm, pmYou).toFixed(1)}`);
      if (cls) ticks.push({ x: bx, h: TICK_H[cls], cls });
    }
    flush();
    // the stretches the coach played
    const bands: { x0: number; x1: number }[] = [];
    let run = -1;
    for (let k = 0; k <= n; k++) {
      const c = k < n && line.rec.by[k] === 'c';
      if (c && run < 0) run = k;
      if (!c && run >= 0) {
        bands.push({ x0: x(run), x1: Math.max(x(k), x(run) + 2) });
        run = -1;
      }
    }
    // where a new big tile (2048 and up) first appears
    const marks: { x: number; tile: number }[] = [];
    for (let k = 1; k <= n; k++) if (line.tops[k] > line.tops[k - 1] && line.tops[k] >= 11) marks.push({ x: x(k), tile: tileValue(line.tops[k]) });
    return { path, area, ticks, bands, marks };
  }, [p.version, w, n]);

  const cur = x(p.cursor);
  const hk = hover;
  const hf = hk !== null ? line.facts[hk] : undefined;
  const label = (k: number) => (k === 0 ? 'Start' : k === n ? `Move ${k} (end)` : `Move ${k} of ${n}`);

  const onKey = (e: KeyboardEvent) => {
    const step: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -10, PageUp: 10 };
    let to: number | null = null;
    // from the line's own cursor: a second key press can come before the view shows the first
    if (e.key in step) to = p.line.cursor + step[e.key];
    else if (e.key === 'Home') to = 0;
    else if (e.key === 'End') to = n;
    if (to === null) return;
    e.preventDefault();
    e.stopPropagation();
    p.onSeek(Math.max(0, Math.min(n, to)));
  };

  return (
    <div
      class={`timeline ${p.disabled ? 'disabled' : ''}`}
      ref={ref}
      role="slider"
      tabIndex={p.disabled ? -1 : 0}
      aria-label="Position in the line"
      aria-valuemin={0}
      aria-valuemax={n}
      aria-valuenow={p.cursor}
      aria-valuetext={label(p.cursor)}
      aria-disabled={p.disabled || undefined}
      onKeyDown={onKey}
      onPointerDown={(e) => {
        if (p.disabled || n === 0 || (e.pointerType === 'mouse' && e.button !== 0)) return;
        drag.current = true;
        (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        p.onSeek(kAt(e.clientX));
      }}
      onPointerMove={(e) => {
        if (n === 0) return;
        const k = kAt(e.clientX);
        if (e.pointerType === 'mouse' || drag.current) setHover(k);
        if (drag.current) p.onSeek(k);
      }}
      onPointerUp={(e) => {
        drag.current = false;
        if (e.pointerType !== 'mouse') setHover(null);
        // a pointer gives the keys back to the board (arrows play moves again)
        (e.currentTarget as HTMLElement).blur();
      }}
      onPointerCancel={() => {
        drag.current = false;
        setHover(null);
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === 'mouse' && !drag.current) setHover(null);
      }}
    >
      {w > 0 && drawn && (
        <svg width={w} height={H} aria-hidden="true">
          <rect x={PAD} y={TOP} width={plotW} height={AREA_B - TOP} rx={4} class="tl-bg" />
          <line x1={PAD} x2={PAD + plotW} y1={yChance(0.5)} y2={yChance(0.5)} class="tl-grid" />
          <path d={drawn.area} class="tl-area" />
          <path d={drawn.path} class="tl-line" />
          {drawn.marks.map((m, i) => (
            <g key={i}>
              <line x1={m.x} x2={m.x} y1={TOP} y2={AREA_B} class="tl-mark" />
            </g>
          ))}
          <line x1={PAD} x2={PAD + plotW} y1={TICK_B + 0.5} y2={TICK_B + 0.5} class="tl-axis" />
          {drawn.ticks.map((t, i) => (
            <rect key={i} x={t.x - 1.25} y={TICK_B - t.h} width={2.5} height={t.h} rx={1} class={`tl-tick ${t.cls}`} />
          ))}
          {drawn.bands.map((b, i) => (
            <rect key={i} x={b.x0} y={BAND_T} width={Math.max(2, b.x1 - b.x0)} height={H - BAND_T} rx={1.5} class="tl-coach" />
          ))}
          {n > 0 && <rect x={cur} y={TOP} width={Math.max(0, PAD + plotW - cur)} height={H - TOP} class="tl-future" />}
          {hk !== null && <line x1={x(hk)} x2={x(hk)} y1={2} y2={H} class="tl-hover" />}
          <line x1={cur} x2={cur} y1={2} y2={H} class="tl-cursor" />
          <circle cx={cur} cy={TOP - 1} r={5} class="tl-handle" />
        </svg>
      )}
      {w > 0 && drawn && drawn.marks.length > 0 && (
        <div class="tl-marks" aria-hidden="true">
          {drawn.marks
            .filter((m, i, all) => i === all.length - 1 || all[i + 1].x - m.x > 34)
            .map((m, i) => (
              <span key={i} style={{ left: `${m.x}px` }}>
                {m.tile}
              </span>
            ))}
        </div>
      )}
      {hk !== null && (
        <div class="tl-tip" style={{ left: `${Math.min(Math.max(x(hk), 60), Math.max(60, w - 60))}px` }} aria-hidden="true">
          <strong>{label(hk)}</strong>
          {hf && hf.p !== null && (
            <span>
              {hf.you ? 'your chance' : ''}
              {hf.tile ? `${hf.you ? ' of ' : ''}${hf.tile}: ` : ''}
              {chance(hf.p)}
            </span>
          )}
          {hk < n && hf && typeof hf.loss === 'number' && shareClass(hf.loss, hf.you ? 'chance' : 'engine', hf.p) && line.rec.by[hk] !== 'c' && (
            <span>
              next move −{pctShort(hf.loss)}
              {hf.you ? ' of it' : ''}
            </span>
          )}
          {hk < n && line.rec.by[hk] === 'c' && <span>coach</span>}
        </div>
      )}
    </div>
  );
}
