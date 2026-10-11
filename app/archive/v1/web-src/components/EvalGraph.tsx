import { useLayoutEffect, useRef, useState } from 'preact/hooks';
import { CLASS_WORDS, chance, lossClass, pctShort } from '../lib/format.ts';

export interface GraphPoint {
  /** chance of the milestone tile before this move (engine odds), null where the engine gives none */
  p: number | null;
  tile: number | null;
  /** the move's real loss (0-1), null where not judged */
  loss: number | null;
}

interface Props {
  points: GraphPoint[];
  current: number;
  onPick: (k: number) => void;
  keyMoments: number[];
  decisive?: number;
}

const TOP_H = 132;
const GAP = 14;
const BOT_H = 64;
const AXIS_H = 22;
const LEFT = 42;
const RIGHT = 10;
const PAD_T = 18;
const FAIL_MIN = 0.001;
const CHANCE_TICKS = [0.999, 0.99, 0.9, 0.5];

/**
 * Two panels on one move axis (one measure each, no second y-scale): the chance of the next milestone tile before
 * every move, and what each move cost (real loss), colored by class.
 */
export function EvalGraph(p: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [hover, setHover] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(260, el.clientWidth)));
    ro.observe(el);
    setW(Math.max(260, el.clientWidth));
    return () => ro.disconnect();
  }, []);

  const n = p.points.length;
  const plotW = w - LEFT - RIGHT;
  const x = (k: number) => LEFT + (n <= 1 ? plotW / 2 : (k / (n - 1)) * plotW);
  // the chance on a scale stretched near 100% (log of the chance to fail): the engine's odds sit at 99%+ for most of a
  // game and the drops that matter (99.9% -> 99% -> 90%) would be invisible on a linear scale
  const yTop = (v: number) => {
    const f = Math.max(FAIL_MIN, Math.min(1, 1 - v));
    return PAD_T + ((Math.log10(f) - Math.log10(FAIL_MIN)) / -Math.log10(FAIL_MIN)) * (TOP_H - PAD_T);
  };
  const botY0 = TOP_H + GAP;
  const maxLoss = Math.max(0.05, ...p.points.map((q) => q.loss ?? 0));
  const yLoss = (v: number) => botY0 + BOT_H - (Math.min(v, maxLoss) / maxLoss) * BOT_H;
  const H = TOP_H + GAP + BOT_H + AXIS_H;

  // the chance line, broken where the engine gives no odds
  let path = '';
  let area = '';
  let seg: string[] = [];
  const flush = () => {
    if (seg.length) {
      path += 'M' + seg.join('L');
      const first = seg[0].split(',')[0];
      const last = seg[seg.length - 1].split(',')[0];
      area += `M${first},${TOP_H}L${seg.join('L')}L${last},${TOP_H}Z`;
    }
    seg = [];
  };
  p.points.forEach((q, k) => {
    if (q.p === null) return flush();
    if (k > 0 && p.points[k - 1].tile !== q.tile && seg.length) flush(); // a new milestone starts a new segment
    seg.push(`${x(k).toFixed(1)},${yTop(q.p).toFixed(1)}`);
  });
  flush();

  const milestones: { k: number; tile: number }[] = [];
  p.points.forEach((q, k) => {
    if (q.tile !== null && k > 0 && p.points[k - 1].tile !== null && p.points[k - 1].tile !== q.tile) milestones.push({ k, tile: p.points[k - 1].tile! });
  });

  const barW = Math.max(1, Math.min(8, plotW / Math.max(n, 1) - (n > 150 ? 0 : 1)));
  const ticks = niceTicks(n);
  const pick = (clientX: number) => {
    const r = wrap.current!.getBoundingClientRect();
    const k = Math.round(((clientX - r.left - LEFT) / plotW) * (n - 1));
    return Math.max(0, Math.min(n - 1, k));
  };
  const hv = hover ?? null;
  const hp = hv !== null ? p.points[hv] : null;
  const cls = hp ? lossClass(hp.loss) : null;
  const tipLeft = hv !== null ? Math.min(Math.max(x(hv) - 90, 0), w - 180) : 0;

  return (
    <div class="graph" ref={wrap}>
      {w > 0 && (
      <svg
        width={w}
        height={H}
        role="img"
        aria-label={`Chance of the next milestone tile and the cost of each of the ${n} moves`}
        onPointerMove={(e) => setHover(pick(e.clientX))}
        onPointerLeave={() => setHover(null)}
        onClick={(e) => p.onPick(pick(e.clientX))}
      >
        {/* grid and axes */}
        {CHANCE_TICKS.map((v) => (
          <g key={v}>
            <line x1={LEFT} x2={w - RIGHT} y1={yTop(v)} y2={yTop(v)} class="g-grid" />
            <text x={LEFT - 6} y={yTop(v) + 4} class="g-tick" text-anchor="end">
              {Math.round(v * 1000) / 10}%
            </text>
          </g>
        ))}
        <line x1={LEFT} x2={w - RIGHT} y1={botY0 + BOT_H} y2={botY0 + BOT_H} class="g-axis" />
        <text x={LEFT - 6} y={botY0 + 10} class="g-tick" text-anchor="end">
          −{pctShort(maxLoss)}
        </text>
        <text x={LEFT + 4} y={botY0 + 10} class="g-panel">
          Cost of each move
        </text>
        {ticks.map((t) => (
          <text key={t} x={x(t)} y={H - 6} class="g-tick" text-anchor="middle">
            {t + 1}
          </text>
        ))}
        {milestones.map((m) => (
          <g key={m.k}>
            <line x1={x(m.k)} x2={x(m.k)} y1={PAD_T - 4} y2={TOP_H} class="g-milestone" />
            <text x={x(m.k) + 4} y={PAD_T - 6} class="g-mlabel">
              {m.tile} ✓
            </text>
          </g>
        ))}
        <path d={area} class="g-area" />
        <path d={path} class="g-line" />
        {/* the cost of each move */}
        {p.points.map((q, k) => {
          if (q.loss === null || q.loss < 0.002) return null;
          const c = lossClass(q.loss) ?? 'small';
          const y = yLoss(q.loss);
          return <rect key={k} x={x(k) - barW / 2} y={y} width={barW} height={Math.max(1.5, botY0 + BOT_H - y)} rx={barW >= 6 ? 2 : 0} class={`g-bar ${c}`} />;
        })}
        {p.keyMoments.map((k) =>
          p.points[k] ? <circle key={`km${k}`} cx={x(k)} cy={yLoss(p.points[k].loss ?? 0) - 7} r={4.5} class={`g-key ${k === p.decisive ? 'decisive' : ''}`} /> : null,
        )}
        {p.decisive !== undefined && p.points[p.decisive] && (
          <text x={Math.min(Math.max(x(p.decisive), LEFT + 30), w - RIGHT - 30)} y={botY0 - 2} class="g-mlabel" text-anchor="middle">
            decisive
          </text>
        )}
        {/* the selected move */}
        {p.current < n && <line x1={x(p.current)} x2={x(p.current)} y1={PAD_T - 6} y2={botY0 + BOT_H} class="g-cursor" />}
        {hv !== null && <line x1={x(hv)} x2={x(hv)} y1={PAD_T - 6} y2={botY0 + BOT_H} class="g-hover" />}
        {hv !== null && hp?.p !== null && hp && <circle cx={x(hv)} cy={yTop(hp.p!)} r={4.5} class="g-dot" />}
      </svg>
      )}
      {hp && hv !== null && (
        <div class="g-tip" style={{ left: `${tipLeft}px` }}>
          <strong>Move {hv + 1}</strong>
          <span>
            {hp.tile ? `${hp.tile}: ` : ''}
            {hp.p === null ? 'no odds' : chance(hp.p)}
          </span>
          <span>
            {hp.loss === null ? 'not judged' : `cost ${pctShort(hp.loss)}`}
            {cls ? ` · ${CLASS_WORDS[cls]}` : ''}
          </span>
        </div>
      )}
      <div class="g-legend" aria-hidden="true">
        <span>
          <i class="lk line" /> Chance of the next milestone with best play (scale stretched near 100%)
        </span>
        <span>
          <i class="lk inaccuracy" /> Inaccuracy 1-3%
        </span>
        <span>
          <i class="lk mistake" /> Mistake 3-10%
        </span>
        <span>
          <i class="lk blunder" /> Blunder 10%+
        </span>
      </div>
    </div>
  );
}

function niceTicks(n: number): number[] {
  if (n <= 1) return [0];
  const step = [10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000].find((s) => n / s <= 6) ?? 10000;
  const out: number[] = [0];
  for (let t = step; t < n; t += step) out.push(t - 1);
  return out;
}
