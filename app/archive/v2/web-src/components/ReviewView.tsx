import { useEffect, useMemo, useState } from 'preact/hooks';
import { type HumanCost, points as pts, shareClass } from '../lib/chance.ts';
import { CLASS_WORDS, arrowOf, cap, chance, int, pctShort, share } from '../lib/format.ts';
import type { Line } from '../lib/line.ts';
import { skillLabel } from '../lib/skill.ts';
import { type OwnSummary, ownSummary } from '../lib/summary.ts';
import { REVIEW_MAX, type ReviewState } from '../lib/workbench.ts';
import { EvalGraph, type GraphPoint } from './EvalGraph.tsx';
import { Spinner, Stat } from './ui.tsx';

interface Props {
  line: Line;
  version: number;
  review: ReviewState;
  /** how many plies of the review still match the line */
  valid: number;
  current: boolean;
  onRun: () => void;
  onJump: (pos: number) => void;
}

/** The review of the line on the board: how it went, the player's key moments, the level. */
export function ReviewView(p: Props) {
  const { line, review } = p;
  const r = review.result && review.result.lineId === line.id ? review.result : undefined;
  const sum = useMemo<OwnSummary | null>(() => (r ? ownSummary(r, line.rec.by, p.valid) : null), [r, p.valid, p.version]);
  const points = useMemo<GraphPoint[]>(() => {
    const pts: GraphPoint[] = [];
    for (let k = 0; k <= line.n; k++) {
      const f = line.facts[k];
      const coach = k < line.n && line.rec.by[k] === 'c';
      pts.push({ p: f?.p ?? null, tile: f?.tile || null, loss: k < line.n && f && typeof f.loss === 'number' ? (coach ? 0 : f.loss) : null, you: !!f?.you });
    }
    if (line.n > 0 && line.over(line.n))
      pts[line.n] = { p: 0, tile: [...pts].reverse().find((q) => q.tile !== null)?.tile ?? null, loss: null, you: !!line.facts[line.n - 1]?.you };
    return pts;
  }, [p.version]);
  const coachRanges = useMemo(() => {
    const out: { from: number; to: number }[] = [];
    let run = -1;
    for (let k = 0; k <= line.n; k++) {
      const c = k < line.n && line.rec.by[k] === 'c';
      if (c && run < 0) run = k;
      if (!c && run >= 0) {
        out.push({ from: run, to: k });
        run = -1;
      }
    }
    return out;
  }, [p.version]);
  const [table, setTable] = useState(false);

  if (line.n === 0)
    return (
      <div class="review-empty card">
        <p>
          <strong>Nothing to review yet.</strong> Play some moves (or let the coach play): the review shows how the game went, your key moments and your level.
        </p>
      </div>
    );

  const running = review.running && review.running.lineId === line.id ? review.running : undefined;
  const hasGraph = points.some((q) => q.p !== null);
  const start = r?.start ?? Math.max(0, line.n - REVIEW_MAX);

  return (
    <div class="review-body">
      {!r && !running && (
        <div class="card review-cta">
          <p>
            <strong>Review this game.</strong> The engine checks every move of the line ({int(line.n)} so far): what each cost, why, and what was better. It takes
            about {Math.max(1, Math.round((300 + line.n * 0.7) / 1000))} s.
          </p>
          <button type="button" class="btn primary" onClick={p.onRun}>
            Review the game <kbd class="on-accent">R</kbd>
          </button>
        </div>
      )}
      {running && <ReviewProgress moves={running.moves.length} startedAt={running.startedAt} update={Boolean(r)} />}
      {review.error && !running && (
        <div class="card notice">
          <p>{review.error}</p>
          <button type="button" class="btn small" onClick={p.onRun}>
            Try again
          </button>
        </div>
      )}
      {r && !p.current && !running && (
        <div class="card notice review-stale">
          <p>
            The line changed since this review{p.valid > 0 ? `: it still covers moves ${start + 1}–${start + p.valid}` : ''}.
          </p>
          <button type="button" class="btn small primary" onClick={p.onRun}>
            Update the review
          </button>
        </div>
      )}
      {r && start > 0 && <p class="muted small">This line is long: the review covers its last {int(r.moves.length)} moves.</p>}

      {sum && sum.own === 0 && (
        <div class="card notice">
          <p>
            The coach played {sum.coach === sum.covered ? 'every move' : 'the judged moves'} of this stretch, and a review grades your own moves. Take over
            somewhere (step back and play a move yourself), then review again.
          </p>
        </div>
      )}
      {sum && sum.own > 0 && <Summary sum={sum} onJump={p.onJump} />}

      {hasGraph && (
        <section class="card graph-card" aria-label="Eval graph">
          <div class="card-head">
            <h3>How the game went</h3>
            {sum && (
              <button type="button" class="btn small ghost" onClick={() => setTable((t) => !t)} aria-pressed={table}>
                {table ? 'Show graph' : 'Show as table'}
              </button>
            )}
          </div>
          {table && sum ? (
            <CostTable line={line} onPick={p.onJump} />
          ) : (
            <EvalGraph
              points={points}
              current={line.cursor}
              onPick={p.onJump}
              keyMoments={sum ? sum.keyMoments.map((m) => m.pos) : []}
              decisive={sum?.decisive?.pos}
              coach={coachRanges}
            />
          )}
          {!sum && <p class="muted small">The curve shows the positions analyzed so far; a review fills in the rest and marks your key moments.</p>}
        </section>
      )}

      {sum && sum.own > 0 && (
        <section class="keymoments" aria-label="Key moments">
          <h3>Key moments</h3>
          {sum.keyMoments.length === 0 ? (
            <p class="muted">
              {sum.byChance
                ? 'No mistakes: none of your moves gave away a tenth of your chance or more.'
                : 'No move of yours cost 3% or more: smaller differences are within the noise of the measurements.'}
            </p>
          ) : (
            <ol>
              {sum.keyMoments.map((m) => (
                <li key={m.pos}>
                  <button type="button" class={`km ${line.cursor === m.pos ? 'on' : ''}`} onClick={() => p.onJump(m.pos)}>
                    <span class="km-ply">Move {m.pos + 1}</span>
                    <span class="km-moves">
                      played {arrowOf(m.played)} {cap(m.played)}
                      {m.better && m.better !== m.played ? ` · better ${arrowOf(m.better)} ${cap(m.better)}` : ''}
                    </span>
                    <span class="km-cost">
                      {costText(m.cost)}
                      {m.pos === sum.decisive?.pos ? <span class="tag warn">decisive</span> : null}
                    </span>
                    {m.why && <span class="km-why">{cap(m.why.split('; ')[0])}.</span>}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      {sum && sum.summary.phases.length > 0 && sum.levelApplies && (
        <details class="card phases">
          <summary>Details by phase</summary>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Phase</th>
                  <th>Moves</th>
                  <th>Mistakes</th>
                  <th>Blunders</th>
                  <th>Kept</th>
                  <th>Skill</th>
                </tr>
              </thead>
              <tbody>
                {sum.summary.phases.map((ph) => (
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
          </div>
          <p class="muted small">
            Hints an app would have shown: {sum.summary.hints} ({sum.summary.hints_per_100.toFixed(1)} per 100 moves). Hard moments (best move found by fewer
            than 20% of players at your level): {sum.summary.hard_moments}, you found {sum.summary.hard_found}.
            {r ? ` Reviewed in ${(r.data.engine.ms / 1000).toFixed(1)} s.` : ''}
          </p>
        </details>
      )}
    </div>
  );
}

function Summary({ sum, onJump }: { sum: OwnSummary; onJump: (pos: number) => void }) {
  const s = sum.summary;
  return (
    <>
      <section class="stats" aria-label="Summary">
        <Stat label="Good moves" value={sum.own ? share(sum.good) : '–'} sub={sum.byChance ? 'not an inaccuracy or worse for you' : 'moves costing under 1%'} />
        <Stat label="Accuracy" value={sum.own ? sum.accuracy.toFixed(1) : '–'} sub="100 = every move as good as the best" />
        <Stat
          label="Decisive moment"
          value={sum.decisive ? `Move ${sum.decisive.pos + 1}` : 'None'}
          sub={
            sum.decisive ? (
              <button type="button" class="linklike" onClick={() => onJump(sum.decisive!.pos)}>
                {costText(sum.decisive.cost)} · show it
              </button>
            ) : (
              'no mistake of yours'
            )
          }
          tone={sum.decisive ? 'warn' : 'good'}
        />
        <Stat
          label="Your level"
          value={sum.levelApplies ? skillLabel(s.skill) : '–'}
          sub={
            !sum.levelApplies
              ? 'measured on games you play yourself'
              : s.skill !== undefined
                ? `skill ${s.skill.toFixed(2)} (higher is stronger)`
                : 'needs 50+ moves below 16384'
          }
        />
      </section>
      <p class="facts">
        {sum.coach > 0 && (
          <>
            You played {int(sum.own)} of these moves and the coach {int(sum.coach)}; only yours count.{' '}
          </>
        )}
        {sum.mistakes + sum.blunders + sum.inaccuracies === 0
          ? 'No inaccuracies, mistakes or blunders. '
          : `${sum.inaccuracies} inaccurac${sum.inaccuracies === 1 ? 'y' : 'ies'}, ${sum.mistakes} mistake${sum.mistakes === 1 ? '' : 's'}, ${sum.blunders} blunder${sum.blunders === 1 ? '' : 's'}. `}
        {sum.notJudged ? `${sum.notJudged} moves in the block formation are not judged. ` : ''}
        {sum.byChance ? 'Your chance kept' : 'Chances kept'}: {chance(sum.kept)}.
      </p>
    </>
  );
}

/** A key moment's cost: points of your chance ("−7 pts of your chance of 2048"), else the engine's real loss. */
function costText(c: HumanCost): string {
  if (c.kind === 'chance' && c.abs !== null) return `${pts(-c.abs)}${c.target ? ` (${c.target})` : ''}`;
  return `−${pctShort(c.rel)}`;
}

function CostTable({ line, onPick }: { line: Line; onPick: (pos: number) => void }) {
  const rows: { k: number; loss: number }[] = [];
  for (let k = 0; k < line.n; k++) {
    const f = line.facts[k];
    if (line.rec.by[k] !== 'c' && f && typeof f.loss === 'number' && shareClass(f.loss, f.you ? 'chance' : 'engine', f.p)) rows.push({ k, loss: f.loss });
  }
  if (!rows.length) return <p class="muted table-empty">No inaccuracies, mistakes or blunders of yours.</p>;
  return (
    <div class="table-wrap">
      <table class="cost-table">
        <thead>
          <tr>
            <th>Move</th>
            <th>Played</th>
            <th>Best</th>
            <th>Cost</th>
            <th>Your chance before</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ k, loss }) => {
            const f = line.facts[k]!;
            const cls = shareClass(loss, f.you ? 'chance' : 'engine', f.p);
            const played = line.moveAt(k);
            return (
              <tr key={k} onClick={() => onPick(k)}>
                <td>
                  <button type="button" class="linklike" onClick={() => onPick(k)}>
                    {k + 1}
                  </button>
                </td>
                <td>
                  {arrowOf(played === -1 ? null : played)} {played === -1 ? '' : cap(['up', 'right', 'down', 'left'][played])}
                </td>
                <td>{f.best === -1 ? '–' : `${arrowOf(f.best)} ${cap(['up', 'right', 'down', 'left'][f.best])}`}</td>
                <td>
                  {pctShort(loss)}
                  {f.you ? ' of your chance' : ''}
                  {cls ? <span class={`tag ${cls}`}>{CLASS_WORDS[cls]}</span> : null}
                </td>
                <td>{f.p !== null ? `${f.tile}: ${chance(f.p)}` : '–'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ReviewProgress({ moves, startedAt, update }: { moves: number; startedAt: number; update: boolean }) {
  const est = 300 + moves * 0.7;
  const [t, setT] = useState(Date.now() - startedAt);
  useEffect(() => {
    const id = setInterval(() => setT(Date.now() - startedAt), 100);
    return () => clearInterval(id);
  }, [startedAt]);
  const pct = Math.min(95, (t / est) * 90);
  return (
    <div class="card review-progress" aria-live="polite">
      <div class="review-progress-head">
        <Spinner label="Reviewing" />
        <span>
          {update ? 'Updating the review' : 'Reviewing'}: {int(moves)} move{moves === 1 ? '' : 's'}…
        </span>
      </div>
      <div class="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label="Review progress">
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
