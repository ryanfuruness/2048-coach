import { useEffect, useMemo, useState } from 'preact/hooks';
import { type Board as BoardT, type Dir, maxRank, tileValue } from '@shared/rules.ts';
import { Board, type BoardArrow } from '../components/Board.tsx';
import { EvalGraph, type GraphPoint } from '../components/EvalGraph.tsx';
import { MoveRows } from '../components/MoveRows.tsx';
import { Link, Stat } from '../components/ui.tsx';
import { ApiError } from '../lib/api.ts';
import { CLASS_WORDS, arrowOf, because, cap, chance, dirIndex, int, lossClass, milestone, nextTile, pctShort, relTime, share } from '../lib/format.ts';
import { type GameRecord, loadGame, replay } from '../lib/games.ts';
import { useTitle } from '../lib/hooks.ts';
import { useDirectionKeys } from '../lib/input.ts';
import { cachedReview, reviewGame } from '../lib/reviews.ts';
import type { Route } from '../lib/router.ts';
import { skillLabel } from '../lib/skill.ts';
import type { ReviewPly, ReviewResult } from '../lib/types.ts';

function playedMove(p: ReviewPly) {
  return p.moves.find((m) => m.move === p.played);
}

export function Review({ route }: { route: Route }) {
  const id = route.name === 'review' ? route.id : '';
  useTitle('Game review · 2048 Coach');
  const game = useMemo<GameRecord | null>(() => loadGame(id), [id]);
  const boards = useMemo<BoardT[]>(() => (game ? replay(game) : []), [game]);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [k, setK] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [table, setTable] = useState(false);

  useEffect(() => {
    if (!game) return;
    setError(null);
    const cached = cachedReview(game.id, game.moves.length);
    const p = cached ?? reviewGame(game.id, { partial: !game.over });
    let live = true;
    p.then(
      (r) => {
        if (!live) return;
        setReview(r);
        const s = r.summary;
        const start = s.decisive_move ?? s.key_moments[0]?.ply ?? 1;
        setK(Math.min(r.plies.length - 1, Math.max(0, start - 1)));
      },
      (e) => live && setError(e instanceof ApiError && e.status === 429 ? 'Too many reviews at once. Try again in a few seconds.' : (e as Error).message),
    );
    return () => {
      live = false;
    };
  }, [game, attempt]);

  const n = review?.plies.length ?? 0;
  const keyPlies = useMemo(() => (review ? review.summary.key_moments.map((m) => m.ply - 1).sort((a, b) => a - b) : []), [review]);
  const step = (d: number) => setK((x) => Math.max(0, Math.min(n, x + d)));
  const jumpKey = (dir: 1 | -1) => {
    const list = dir > 0 ? keyPlies.filter((x) => x > k) : keyPlies.filter((x) => x < k).reverse();
    if (list.length) setK(list[0]);
  };
  useDirectionKeys(
    (d: Dir, e) => {
      if (e.key.length === 1) return false; // letters (WASD) keep their normal meaning here
      if (d === 3) e.shiftKey ? jumpKey(-1) : step(-1);
      else if (d === 1) e.shiftKey ? jumpKey(1) : step(1);
      else return false; // up/down scroll the page
    },
    Boolean(review),
  );
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key === 'Home') setK(0);
      else if (e.key === 'End') setK(n);
    };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, [n]);

  const points = useMemo<GraphPoint[]>(() => {
    if (!review) return [];
    const pts: GraphPoint[] = review.plies.map((p) => {
      const ms = milestone(p.odds);
      const pm = playedMove(p);
      return { p: ms?.p ?? null, tile: ms?.tile ?? null, loss: p.judged === false ? null : pm?.move === p.best ? 0 : (pm?.real_loss ?? null) };
    });
    // a finished game: the final position, where the milestone it did not reach has no chance left
    if (game?.over && pts.length) pts.push({ p: 0, tile: [...pts].reverse().find((q) => q.tile !== null)?.tile ?? null, loss: null });
    return pts;
  }, [review, game]);

  if (!game)
    return (
      <div class="page narrow">
        <h1>Game not found</h1>
        <p class="lead">This game is not in this browser's history. Games are stored only on the device you played them on.</p>
        <Link href="/history" class="btn">
          Your history
        </Link>
      </div>
    );

  const s = review?.summary;
  const ply = review && k < n ? review.plies[k] : null;
  const board = boards[Math.min(k, boards.length - 1)];
  const pm = ply ? playedMove(ply) : undefined;
  const arrows: BoardArrow[] = [];
  if (ply) {
    const pd = dirIndex(ply.played);
    const bd = dirIndex(ply.best);
    if (pd !== -1 && pd === bd) arrows.push({ dir: pd, tone: 'same', label: 'best' });
    else {
      if (pd !== -1) arrows.push({ dir: pd, tone: lossClass(pm?.real_loss) ? 'warn' : 'played', label: 'you' });
      if (bd !== -1) arrows.push({ dir: bd, tone: 'best', label: 'best' });
    }
  }
  const cls = ply && pm && ply.played !== ply.best ? lossClass(pm.real_loss) : null;
  const next = nextTile(maxRank(board));
  const plan = ply?.plan_info;

  return (
    <div class="page review">
      <div class="page-head">
        <Link href="/history" class="back">
          ← History
        </Link>
        <h1>Game review</h1>
        <p class="lead">
          {relTime(game.startedAt)} · {int(game.score)} points · best tile {tileValue(game.maxRank)} · {game.moves.length} moves
          {game.origin === 'position' ? ' · from a set-up position' : ''}
          {!game.over ? ' · still in progress' : ''}
        </p>
      </div>

      {!review && !error && <ReviewLoading moves={game.moves.length} board={boards[boards.length - 1]} />}
      {error && (
        <div class="card notice">
          <p>{error}</p>
          <button type="button" class="btn" onClick={() => setAttempt((a) => a + 1)}>
            Try again
          </button>
        </div>
      )}

      {review && s && (
        <>
          <section class="stats" aria-label="Summary">
            <Stat label="Best or good moves" value={share(s.good)} sub="moves costing under 1%" />
            <Stat label="Accuracy" value={s.accuracy.toFixed(1)} sub="100 = every move as good as the best" />
            <Stat
              label="Decisive moment"
              value={s.decisive_move ? `Move ${s.decisive_move}` : 'None'}
              sub={
                s.decisive_move ? (
                  <button type="button" class="linklike" onClick={() => setK(s.decisive_move! - 1)}>
                    cost {pctShort(s.decisive_loss)} · show it
                  </button>
                ) : (
                  'no costly move from a healthy position'
                )
              }
              tone={s.decisive_move ? 'warn' : 'good'}
            />
            <Stat
              label="Your level"
              value={skillLabel(s.skill)}
              sub={s.skill !== undefined ? `skill ${s.skill.toFixed(2)} (higher is stronger)` : 'needs 50+ moves below 16384'}
            />
          </section>
          <p class="facts">
            {s.mistakes + s.blunders === 0 && s.inaccuracies === 0
              ? 'No inaccuracies, mistakes or blunders. '
              : `${s.inaccuracies} inaccurac${s.inaccuracies === 1 ? 'y' : 'ies'}, ${s.mistakes} mistake${s.mistakes === 1 ? '' : 's'}, ${s.blunders} blunder${s.blunders === 1 ? '' : 's'}. `}
            {s.warnings === 0 ? 'None of the moves you played would get a warning from the coach' : `The coach flags ${s.warnings} of the moves you played`}
            {game.coach.warnings
              ? ` (during the game it warned you ${game.coach.warnings === 1 ? 'once' : `${game.coach.warnings} times`} and you took ${game.coach.warningsTaken === 1 ? 'its suggestion once' : `${game.coach.warningsTaken} suggestions`})`
              : ''}
            .{s.not_judged ? ` ${s.not_judged} moves in the block formation are not judged.` : ''} Chances kept: {chance(s.kept)}.
          </p>

          <section class="card graph-card" aria-label="Eval graph">
            <div class="card-head">
              <h2>How the game went</h2>
              <button type="button" class="btn small ghost" onClick={() => setTable((t) => !t)} aria-pressed={table}>
                {table ? 'Show graph' : 'Show as table'}
              </button>
            </div>
            {table ? (
              <CostTable review={review} onPick={setK} />
            ) : (
              <EvalGraph points={points} current={k} onPick={setK} keyMoments={keyPlies} decisive={s.decisive_move ? s.decisive_move - 1 : undefined} />
            )}
          </section>

          <section class="stepper" aria-label="Move by move">
            <div class="stepper-board">
              <Board board={board} arrows={arrows} label={k < n ? `Position before move ${k + 1}` : 'Final position'} chain={plan?.chain} nextCell={plan?.next_cell} />
              <div class="step-controls">
                <button type="button" class="btn small" onClick={() => setK(0)} aria-label="First move" disabled={k === 0}>
                  ⏮
                </button>
                <button type="button" class="btn small" onClick={() => step(-1)} aria-label="Previous move" disabled={k === 0}>
                  ◀
                </button>
                <span class="step-pos" aria-live="polite">
                  {k < n ? `Move ${k + 1} of ${n}` : 'Final position'}
                </span>
                <button type="button" class="btn small" onClick={() => step(1)} aria-label="Next move" disabled={k === n}>
                  ▶
                </button>
                <button type="button" class="btn small" onClick={() => setK(n)} aria-label="Final position" disabled={k === n}>
                  ⏭
                </button>
              </div>
              <input
                type="range"
                class="step-range"
                min={0}
                max={n}
                value={k}
                onInput={(e) => setK(Number((e.target as HTMLInputElement).value))}
                aria-label="Move"
              />
              <div class="step-keys">
                <button type="button" class="btn small ghost" onClick={() => jumpKey(-1)} disabled={!keyPlies.some((x) => x < k)}>
                  ← Previous key moment
                </button>
                <button type="button" class="btn small ghost" onClick={() => jumpKey(1)} disabled={!keyPlies.some((x) => x > k)}>
                  Next key moment →
                </button>
              </div>
              <p class="keys-hint">
                <kbd>←</kbd> <kbd>→</kbd> step · <kbd>Shift</kbd>+<kbd>←</kbd>/<kbd>→</kbd> key moments
              </p>
            </div>
            <div class="stepper-info">
              {ply && pm ? (
                <>
                  <div class="ply-head">
                    <h2>
                      Move {k + 1}: you played {arrowOf(ply.played)} {cap(ply.played)}
                    </h2>
                    {ply.judged === false ? (
                      <span class="tag neutral">Not judged</span>
                    ) : ply.played === ply.best ? (
                      <span class="tag best">Best move</span>
                    ) : cls ? (
                      <span class={`tag ${cls}`}>{CLASS_WORDS[cls]}</span>
                    ) : (
                      <span class="tag good">Good</span>
                    )}
                  </div>
                  {ply.judged === false ? (
                    <p class="ply-verdict">
                      The block formation: the engine plays a different formation, so it does not judge moves here. Its suggestion was {arrowOf(ply.best)}{' '}
                      {cap(ply.best ?? '')}.
                    </p>
                  ) : ply.played === ply.best ? (
                    <p class="ply-verdict">That is the engine's move too.</p>
                  ) : (
                    <p class="ply-verdict">
                      The engine preferred{' '}
                      <strong>
                        {arrowOf(ply.best)} {cap(ply.best ?? '')}
                      </strong>
                      . Your move cost {pctShort(pm.real_loss)} of the expected score with good play afterwards
                      {pm.your_cost !== undefined && pm.your_cost !== null ? ` and about ${pctShort(pm.your_cost)} of your chances of reaching ${next}` : ''}.
                      {pm.warn ? ' The coach would have warned you before this move.' : ''}
                    </p>
                  )}
                  {pm.reasons.length > 0 && ply.played !== ply.best && <p class="ply-why">{because(pm.reasons[0])}</p>}
                  <MoveRows moves={ply.moves} best={ply.best} played={ply.played} judged={ply.judged !== false} nextTile={next} />
                  <details class="ply-more">
                    <summary>The position in words</summary>
                    <p>{ply.summary}</p>
                    {ply.plan && <p class="muted">{ply.plan}</p>}
                  </details>
                </>
              ) : (
                <div class="ply-head">
                  <h2>{game.over ? 'Final position: no move left' : 'Current position'}</h2>
                  <p class="muted">
                    {int(game.score)} points, best tile {tileValue(game.maxRank)}.
                  </p>
                </div>
              )}
            </div>
          </section>

          <section class="keymoments" aria-label="Key moments">
            <h2>Key moments</h2>
            {s.key_moments.length === 0 ? (
              <p class="muted">No move cost 3% or more: smaller differences are within the noise of the measurements.</p>
            ) : (
              <ol>
                {s.key_moments.map((m) => (
                  <li key={m.ply}>
                    <button type="button" class={`km ${k === m.ply - 1 ? 'on' : ''}`} onClick={() => setK(m.ply - 1)}>
                      <span class="km-ply">Move {m.ply}</span>
                      <span class="km-moves">
                        played {arrowOf(m.played)} {cap(m.played)} · best {arrowOf(m.engine === '-' ? null : m.engine)} {m.engine === '-' ? '' : cap(m.engine)}
                      </span>
                      <span class="km-cost">
                        −{pctShort(Math.max(m.real_loss, m.your_cost))}
                        {m.ply === s.decisive_move ? <span class="tag warn">decisive</span> : null}
                      </span>
                      {m.why && <span class="km-why">{cap(m.why.split('; ')[0])}.</span>}
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {s.phases.length > 0 && (
            <details class="card phases">
              <summary>Details by phase</summary>
              <table>
                <thead>
                  <tr>
                    <th>Phase</th>
                    <th>Moves</th>
                    <th>Mistakes</th>
                    <th>Blunders</th>
                    <th>Chances kept</th>
                    <th>Skill</th>
                  </tr>
                </thead>
                <tbody>
                  {s.phases.map((ph) => (
                    <tr key={ph.phase}>
                      <td>{ph.phase}</td>
                      <td>{ph.moves}</td>
                      <td>{ph.mistakes}</td>
                      <td>{ph.blunders}</td>
                      <td>{chance(ph.kept)}</td>
                      <td>{ph.skill !== undefined ? ph.skill.toFixed(2) : '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p class="muted small">
                Hints an app would have shown: {s.hints} ({s.hints_per_100.toFixed(1)} per 100 moves). Hard moments (best move found by fewer than 20% of players at
                your level): {s.hard_moments}, you found {s.hard_found}. Reviewed in {(review.engine.ms / 1000).toFixed(1)} s.
              </p>
            </details>
          )}
        </>
      )}
    </div>
  );
}

function ReviewLoading({ moves, board }: { moves: number; board: BoardT }) {
  const est = 300 + moves * 0.7;
  const [t, setT] = useState(0);
  useEffect(() => {
    const t0 = performance.now();
    const id = setInterval(() => setT(performance.now() - t0), 100);
    return () => clearInterval(id);
  }, []);
  const pct = Math.min(95, (t / est) * 90);
  return (
    <div class="review-loading">
      <Board board={board} label="Final position" dim />
      <div>
        <h2>
          Reviewing {moves} move{moves === 1 ? '' : 's'}…
        </h2>
        <p class="muted">The engine checks every move: what it cost, why, and what was better.</p>
        <div class="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label="Review progress">
          <i style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

function CostTable({ review, onPick }: { review: ReviewResult; onPick: (k: number) => void }) {
  const rows = review.plies
    .map((p, i) => ({ p, i, pm: playedMove(p) }))
    .filter(({ p, pm }) => p.judged !== false && p.played !== p.best && (pm?.real_loss ?? 0) >= 0.01);
  if (!rows.length) return <p class="muted table-empty">No move cost 1% or more.</p>;
  return (
    <div class="table-wrap">
      <table class="cost-table">
        <thead>
          <tr>
            <th>Move</th>
            <th>Played</th>
            <th>Best</th>
            <th>Cost</th>
            <th>Your chances</th>
            <th>Chance before</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ p, i, pm }) => {
            const ms = milestone(p.odds);
            return (
              <tr key={i} onClick={() => onPick(i)}>
                <td>
                  <button type="button" class="linklike" onClick={() => onPick(i)}>
                    {i + 1}
                  </button>
                </td>
                <td>
                  {arrowOf(p.played)} {cap(p.played)}
                </td>
                <td>
                  {arrowOf(p.best)} {cap(p.best ?? '')}
                </td>
                <td>{pctShort(pm?.real_loss)}</td>
                <td>{pm?.your_cost !== undefined && pm?.your_cost !== null ? `−${pctShort(pm.your_cost)}` : '–'}</td>
                <td>{ms ? `${ms.tile}: ${chance(ms.p)}` : '–'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
