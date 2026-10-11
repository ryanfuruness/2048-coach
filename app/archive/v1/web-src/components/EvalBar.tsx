import { type Health, HEALTH_WORDS, chance } from '../lib/format.ts';

interface Props {
  /** chance of reaching the milestone tile with best play from here (engine odds), null when unknown */
  p: number | null;
  tile: number | null;
  health: Health;
  /** waiting for the analysis of the current position (the value shown is the previous estimate) */
  pending?: boolean;
  /** the coach could not reach the server */
  offline?: boolean;
  /** "not judged" (block formation) or no odds in this phase */
  note?: string | null;
  /** the same chance for a player of the player's level (personal odds), when known */
  yours?: number | null;
  vertical?: boolean;
}

const SHORT: Record<Health, string> = { good: 'Typical', warning: 'A bit worse', critical: 'In trouble', unknown: '' };

/** The eval bar: the chance of the next milestone tile, as a meter whose color says how healthy the position is. */
export function EvalBar(p: Props) {
  const v = p.p === null ? null : Math.max(0, Math.min(1, p.p));
  const label = p.tile ? `Chance of ${p.tile}` : 'Chance of the next tile';
  const aria = v === null ? `${label}: not available` : `${label} with best play: ${chance(v)}`;
  const hasYours = p.yours !== null && p.yours !== undefined;
  const sub = p.offline
    ? 'Coach offline: play on'
    : p.note
      ? p.note
      : v === null
        ? 'Waiting for the coach…'
        : hasYours
          ? `With best play · at your level ${chance(p.yours)}`
          : `With best play from here${p.health !== 'unknown' ? ` · ${HEALTH_WORDS[p.health]}` : ''}`;
  return (
    <div
      class={`evalbar ${p.vertical ? 'vertical' : ''} h-${p.offline ? 'unknown' : p.health} ${p.pending ? 'pending' : ''}`}
      role="meter"
      aria-label={aria}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={v === null ? undefined : Math.round(v * 1000) / 10}
      title="The engine's chance of reaching the tile if it played on from here"
    >
      {p.vertical ? (
        <div class="evalbar-head">
          <span class="evalbar-value">{v === null ? '–' : chance(v)}</span>
          <span class="evalbar-label">{p.tile ? `to reach ${p.tile}` : 'next tile'}</span>
        </div>
      ) : (
        <div class="evalbar-head">
          <span class="evalbar-label">{label}</span>
          <span class="evalbar-value">{v === null ? '–' : chance(v)}</span>
        </div>
      )}
      <div class="evalbar-track">
        <div class="evalbar-fill" style={{ [p.vertical ? 'height' : 'width']: `${v === null ? 0 : Math.max(2, v * 100)}%` }} />
        {hasYours && <div class="evalbar-yours" style={{ [p.vertical ? 'bottom' : 'left']: `${Math.max(0, Math.min(100, p.yours! * 100))}%` }} />}
      </div>
      {p.vertical ? (
        <div class="evalbar-sub">
          {p.offline || p.note || v === null ? (
            <span>{sub}</span>
          ) : (
            <>
              {p.health !== 'unknown' && <span class={`health-pill h-${p.health}`}>{SHORT[p.health]}</span>}
              {hasYours && <span class="yours-line">You: {chance(p.yours)}</span>}
            </>
          )}
        </div>
      ) : (
        <div class="evalbar-sub">{sub}</div>
      )}
    </div>
  );
}
