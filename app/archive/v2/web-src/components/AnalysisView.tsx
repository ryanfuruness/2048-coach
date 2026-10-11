import { type Board as BoardT, type DirName, maxRank } from '@shared/rules.ts';
import { coachOf, engineBest } from '../lib/chance.ts';
import { arrowOf, cap, chance, cost, healthOf, nextTile } from '../lib/format.ts';
import { skillLabel } from '../lib/skill.ts';
import type { Analysis } from '../lib/types.ts';
import { MoveRows } from './MoveRows.tsx';

interface Props {
  a: Analysis;
  board: BoardT;
  /** the analysis is of an earlier position, shown while the current one is on its way */
  stale?: boolean;
  /** the move played from this position in the line (marked in the move list) */
  played?: DirName | null;
  /** a button in the verdict that plays the best move */
  onPlayBest?: () => void;
  /** the player's estimated skill (null until a review measured it) */
  skill: number | null;
}

/**
 * Everything the coach says about a position: the best move for you and why, your chance of the next milestone (a
 * player of your level playing on) and what each move does to it, the engine's own odds, the plan.
 */
export function AnalysisView(p: Props) {
  const a = p.a;
  const bestName = coachOf(a);
  const engineName = engineBest(a);
  const ch = a.chance;
  const bestMove = a.moves.find((m) => m.move === bestName);
  const odds = a.odds ? Object.entries(a.odds).sort((x, y) => Number(x[0]) - Number(y[0])) : [];
  const health = healthOf(a);
  const next = nextTile(maxRank(p.board));
  const plan = a.plan_info;
  return (
    <div class={`analysis-body ${p.stale ? 'stale' : ''}`}>
      <div class={`verdict card h-${health}`}>
        {a.game_over ? (
          <p class="verdict-text">Game over: no move is possible on this board.</p>
        ) : (
          <>
            {bestName && (
              <div class="verdict-best">
                <span class="big-arrow" aria-hidden="true">
                  {arrowOf(bestName)}
                </span>
                <div>
                  <span class="verdict-label">{a.judged === false ? 'Suggestion only' : ch ? 'Best move for you' : 'Best move'}</span>
                  <strong>{cap(bestName)}</strong>
                </div>
                {a.judged === false && <span class="tag neutral verdict-tag">Not judged</span>}
                {p.onPlayBest && (
                  <button
                    type="button"
                    class="btn primary small verdict-play"
                    onClick={(e) => {
                      p.onPlayBest!();
                      if (e.detail > 0) (e.currentTarget as HTMLElement).blur();
                    }}
                    title="Play the coach's move (Space)"
                  >
                    Play it <kbd class="on-accent">Space</kbd>
                  </button>
                )}
              </div>
            )}
            {ch ? (
              <>
                {(a.coach_why || bestMove?.reasons[0]) && (
                  <p class="verdict-why">{cap(a.coach_why ?? bestMove!.reasons[0].text)}.</p>
                )}
                <p class="verdict-text">
                  Your chance of reaching <strong>{ch.target}</strong> if you play on: <strong>{chance(ch.now)}</strong>
                  {ch.best - ch.now >= 0.005 ? `, ${chance(ch.best)} with the best move` : ''}.
                  {engineName && bestName && engineName !== bestName ? ` The engine would play ${cap(engineName)} (as good for it).` : ''}
                </p>
              </>
            ) : (
              <p class="verdict-text">{a.summary}</p>
            )}
          </>
        )}
      </div>

      {!a.game_over && (
        <div class="moves-card">
          <h3>Every move</h3>
          <MoveRows
            moves={maxRank(p.board) >= 14 ? a.moves.map(({ find_prob: _f, ...m }) => m) : a.moves}
            best={bestName}
            played={p.played ?? null}
            judged={a.judged !== false}
            nextTile={ch?.target ?? next}
            chanceBest={ch?.best ?? null}
            allReasons
          />
          {ch && (
            <p class="muted small">
              Your chance is for a player at {p.skill === null ? 'an in-between level' : 'your level'} ({skillLabel(ch.skill).toLowerCase()}) who plays on
              from here{p.skill === null ? '; a review of a game you play yourself measures yours' : ''}.
            </p>
          )}
          {a.error_risk !== undefined && !ch && (
            <p class="muted small">
              At your level the move you are likely to make here costs {cost(a.error_risk)} of your chances on average
              {a.hint ? ', so the coach offers a hint in Coach mode.' : '.'}
            </p>
          )}
        </div>
      )}

      {odds.length > 0 && (
        <div class="odds">
          <h3>{ch ? 'If the engine played on' : 'Chances with best play'}</h3>
          <div class="odds-row">
            {odds.map(([t, v]) => (
              <div class="odd" key={t}>
                <span class="odd-tile">{t}</span>
                <span class="odd-p">{chance(v)}</span>
                <span class="odd-bar">
                  <i style={{ width: `${Math.max(2, v * 100)}%` }} />
                </span>
              </div>
            ))}
          </div>
          {a.odds_caveat && <p class="muted small">Odds are less certain here: this formation is unusual for the stage.</p>}
          {ch && (
            <p class="muted small">
              The engine repairs far more than a person can, so its odds stay high. {a.summary}
            </p>
          )}
          {!ch && a.personal_odds && p.skill !== null && (
            <p class="muted small">
              At your level ({skillLabel(p.skill).toLowerCase()}):{' '}
              {Object.entries(a.personal_odds)
                .filter(([k, v]) => /^\d+$/.test(k) && typeof v === 'number')
                .map(([k, v]) => `${k} ${chance(v as number)}`)
                .join(' · ')}
            </p>
          )}
        </div>
      )}

      {a.plan && (
        <div class="plan card">
          <h3>The plan</h3>
          <p>{a.plan}</p>
          {plan?.chain && (
            <p class="muted small">Your chain is outlined in blue on the board{plan.next_cell !== undefined ? '; the cell to build next in green' : ''}.</p>
          )}
        </div>
      )}
    </div>
  );
}
