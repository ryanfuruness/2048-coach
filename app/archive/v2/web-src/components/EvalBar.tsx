import { type Health, HEALTH_WORDS, chance } from '../lib/format.ts';
import { points } from '../lib/chance.ts';

interface Props {
  /** your chance of the milestone tile from here (or the engine's odds when there is no chance), null when unknown */
  p: number | null;
  tile: number | null;
  /** p is your chance (a player of your level playing on); false: the engine's odds (largest tile 16384 and up) */
  you: boolean;
  /** the engine's odds of the same tile, shown next to yours */
  engine?: number | null;
  /** what the last move cost you (points of chance, <= 0), when it cost something */
  lastCost?: number | null;
  /** your level in words */
  level?: string;
  health: Health;
  /** waiting for the analysis of the current position (the value shown is the previous estimate) */
  pending?: boolean;
  /** the coach could not reach the server */
  offline?: boolean;
  /** "not judged" (block formation) or no odds in this phase */
  note?: string | null;
  vertical?: boolean;
}

const SHORT: Record<Health, string> = { good: 'Typical', warning: 'A bit worse', critical: 'In trouble', unknown: '' };

/**
 * The eval bar: your chance of the next milestone tile if you play on yourself (a player of your level), with what the
 * last move cost and the engine's own odds beside it. From 16384 on (no human-like players get there) the engine's
 * odds, colored by how healthy the position is.
 */
export function EvalBar(p: Props) {
  const v = p.p === null ? null : Math.max(0, Math.min(1, p.p));
  const label = p.you ? (p.tile ? `Your chance of ${p.tile}` : 'Your chance') : p.tile ? `Chance of ${p.tile}` : 'Chance of the next tile';
  const aria = v === null ? `${label}: not available` : `${label}: ${chance(v)}`;
  const cost = p.lastCost !== null && p.lastCost !== undefined && p.lastCost <= -0.005 ? p.lastCost : null;
  const engine = p.engine !== null && p.engine !== undefined ? p.engine : null;
  const health = p.you ? 'you' : p.offline ? 'unknown' : p.health;
  const sub = p.offline
    ? 'Coach offline: play on'
    : p.note
      ? p.note
      : v === null
        ? 'Waiting for the coach…'
        : p.you
          ? `If you play on${p.level ? ` (${p.level.toLowerCase()})` : ''}${engine !== null ? ` · engine ${chance(engine)}` : ''}`
          : `With best play from here${p.health !== 'unknown' ? ` · ${HEALTH_WORDS[p.health]}` : ''}`;
  const title = p.you
    ? 'How often a player of your level reaches the tile from here, playing on themselves (the engine would repair far more)'
    : "The engine's chance of reaching the tile if it played on from here";
  return (
    <div
      class={`evalbar ${p.vertical ? 'vertical' : ''} h-${health} ${p.pending ? 'pending' : ''}`}
      role="meter"
      aria-label={aria}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={v === null ? undefined : Math.round(v * 1000) / 10}
      title={title}
    >
      {p.vertical ? (
        <div class="evalbar-head">
          <span class="evalbar-value">{v === null ? '–' : chance(v)}</span>
          <span class="evalbar-label">{p.tile ? `${p.you ? 'you reach' : 'to reach'} ${p.tile}` : 'next tile'}</span>
        </div>
      ) : (
        <div class="evalbar-head">
          <span class="evalbar-label">{label}</span>
          {cost !== null && (
            <span class="evalbar-delta" title="What your last move cost">
              {points(cost)}
            </span>
          )}
          <span class="evalbar-value">{v === null ? '–' : chance(v)}</span>
        </div>
      )}
      <div class="evalbar-track">
        <div class="evalbar-fill" style={{ [p.vertical ? 'height' : 'width']: `${v === null ? 0 : Math.max(2, v * 100)}%` }} />
        {p.you && engine !== null && (
          <div class="evalbar-engine" title={`The engine: ${chance(engine)}`} style={{ [p.vertical ? 'bottom' : 'left']: `${Math.max(0, Math.min(100, engine * 100))}%` }} />
        )}
      </div>
      {p.vertical ? (
        <div class="evalbar-sub">
          {p.offline || p.note || v === null ? (
            <span>{sub}</span>
          ) : p.you ? (
            <>
              {cost !== null && <span class="evalbar-delta">{points(cost)}</span>}
              {engine !== null && <span class="yours-line">Engine {chance(engine)}</span>}
            </>
          ) : (
            p.health !== 'unknown' && <span class={`health-pill h-${p.health}`}>{SHORT[p.health]}</span>
          )}
        </div>
      ) : (
        <div class="evalbar-sub">{sub}</div>
      )}
    </div>
  );
}
