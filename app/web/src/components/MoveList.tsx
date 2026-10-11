import type { DirName } from '@shared/rules.ts';
import { arrowOf, cap, chance } from '../lib/format.ts';
import { GRADE_WORDS, coachOf, shortWhy } from '../lib/grades.ts';
import type { Analysis, MoveInfo } from '../lib/types.ts';

interface Props {
  a: Analysis;
  /** the move played from this position in the game (when you stepped back) */
  played?: DirName | null;
  /** the analysis is of an earlier position, shown while the current one is on its way */
  stale?: boolean;
  /** plays a move (a click on its row) */
  onPlay?: (d: DirName) => void;
  /** say why for every move, and the plan */
  explain: boolean;
}

/** The reason shown under a move: a blunder's always; with "Explain" every move's (the coach's move: what it does). */
function reasonOf(a: Analysis, m: MoveInfo, coach: DirName | null, explain: boolean): string {
  if (m.grade === 'blunder') return shortWhy(m.why);
  if (!explain) return '';
  if (m.move === coach) return a.coach_why ?? m.reasons.find((r) => r.code !== 'later' && r.code !== 'shape')?.text ?? '';
  if (m.why) return shortWhy(m.why);
  const r = m.reasons.find((x) => x.code !== 'later' && x.code !== 'shape');
  return r ? shortWhy(r.text) : '';
}

/** The plan in at most two sentences, without the engine's asides (its corner habits are the coach's business). */
function planText(plan: string | undefined): string {
  if (!plan) return '';
  const sentences = plan.match(/[^.]+(?:\.(?=\s|$))?/g) ?? [];
  return sentences
    .map((x) => x.trim())
    .filter((x) => x && !/engine/i.test(x))
    .slice(0, 2)
    .join(' ');
}

/** A blocked chain (a bigger tile in the cell the chain needs next), as a warning: the engine's sentence about it.
 * The coach almost never goes through that cell (results/plancell/REPORT.md), so it is worth knowing. */
function blockedText(a: Analysis): string {
  const p = a.plan_info;
  if ((p?.step ?? p?.type) !== 'blocked' || !p?.there || !p.needs) return '';
  const s = (a.plan ?? '').match(/[^.]*\bblocks it\b[^.]*\./)?.[0]?.trim();
  return s ? s.replace(/\bblocks it\b/, 'blocks your chain') : `A ${p.there} sits where your chain needs a ${p.needs}.`;
}

/** Every legal move with the coach's grade and how often the coach would play it. */
export function MoveList(p: Props) {
  const a = p.a;
  if (a.game_over) return null;
  const coach = coachOf(a);
  const blocked = blockedText(a);
  const rows = [...a.moves].sort((x, y) => (x.move === coach ? -1 : y.move === coach ? 1 : (y.pick ?? 0) - (x.pick ?? 0)));
  return (
    <div class={`movelist ${p.stale ? 'stale' : ''}`}>
      {p.explain && blocked ? (
        <p class="plan-line blocked">
          <strong>Chain blocked.</strong> {blocked}
        </p>
      ) : (
        p.explain && planText(a.plan) && <p class="plan-line">{planText(a.plan)}</p>
      )}
      <ul role="list">
        {rows.map((m) => {
          const pct = Math.round((m.pick ?? 0) * 100);
          const why = reasonOf(a, m, coach, p.explain);
          return (
            <li key={m.move} class={`mv ${m.grade ? `g-${m.grade}` : ''} ${m.move === p.played ? 'played' : ''}`}>
              <button
                type="button"
                class="mv-row"
                onClick={(e) => {
                  p.onPlay?.(m.move);
                  if (e.detail > 0) (e.currentTarget as HTMLElement).blur();
                }}
                disabled={!p.onPlay}
                title={`Play ${m.move}`}
              >
                <span class="mv-arrow" aria-hidden="true">
                  {arrowOf(m.move)}
                </span>
                <span class="mv-name">{cap(m.move)}</span>
                {m.grade ? <span class={`grade ${m.grade}`}>{GRADE_WORDS[m.grade]}</span> : <span class="grade">Not judged</span>}
                <span class="mv-bar" aria-hidden="true">
                  <i style={{ width: `${Math.max(pct, 1)}%` }} />
                </span>
                <span class="mv-pct" title="How often the coach would play this move">
                  {pct}%
                </span>
              </button>
              {why && <p class="mv-why">{cap(why)}.</p>}
            </li>
          );
        })}
      </ul>
      {p.explain && <p class="muted small mv-note">The % is how often the coach would play the move.</p>}
    </div>
  );
}

/** The engine's odds of reaching each bigger tile if it played on from here, as cards with a bar. */
export function OddsCards({ odds }: { odds: Record<string, number> }) {
  const rows = Object.entries(odds).sort((x, y) => Number(x[0]) - Number(y[0]));
  return (
    <div class="odds-cards" title="How often the engine reaches each tile if it plays on from here">
      {rows.map(([t, v]) => (
        <div class="odds-card" key={t}>
          <span class="oc-tile">{t}</span>
          <span class="oc-p">{chance(v)}</span>
          <span class="oc-bar" aria-hidden="true">
            <i style={{ width: `${Math.max(2, v * 100)}%` }} />
          </span>
        </div>
      ))}
    </div>
  );
}
