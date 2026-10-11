import { DIR_NAMES, type Dir } from '@shared/rules.ts';
import { arrowOf, cap, int } from '../lib/format.ts';
import { GRADE_WORDS, type GradeName, shortWhy } from '../lib/grades.ts';
import type { Line } from '../lib/line.ts';
import type { ReviewState } from '../lib/workbench.ts';
import { Modal, Spinner } from './ui.tsx';

interface Props {
  line: Line;
  review: ReviewState;
  onJump: (pos: number) => void;
  onClose: () => void;
}

/** Your moves' grades in this game (the coach's own moves left out), and the questionable ones and blunders to revisit. */
export function gameCounts(line: Line): Record<GradeName, number> & { unknown: number } {
  const c = { best: 0, good: 0, questionable: 0, blunder: 0, unknown: 0 };
  for (let k = 0; k < line.n; k++) {
    if (line.author(k) === 'c') continue;
    const g = line.facts[k]?.grade;
    if (g) c[g]++;
    else if (g === undefined) c.unknown++;
  }
  return c;
}

export function ReviewSheet(p: Props) {
  const { line } = p;
  const c = gameCounts(line);
  const r = p.review.result && p.review.result.lineId === line.id ? p.review.result : undefined;
  const running = p.review.running && p.review.running.lineId === line.id;
  const flagged: { k: number; grade: GradeName; why: string }[] = [];
  for (let k = 0; k < line.n; k++) {
    const g = line.facts[k]?.grade;
    if (line.author(k) === 'c' || (g !== 'blunder' && g !== 'questionable')) continue;
    const ply = r && k >= r.start && k - r.start < r.data.plies.length ? r.data.plies[k - r.start] : undefined;
    const why = ply?.moves.find((m) => m.move === ply.played)?.why;
    flagged.push({ k, grade: g, why: shortWhy(why) });
  }
  return (
    <Modal onClose={p.onClose} labelledBy="review-title" class="review-sheet">
      <h2 id="review-title">Your moves</h2>
      <div class="counts">
        {(['blunder', 'questionable', 'good', 'best'] as const).map((g) => (
          <div class={`count g-${g}`} key={g}>
            <strong>{int(c[g])}</strong>
            <span>{GRADE_WORDS[g]}</span>
          </div>
        ))}
      </div>
      {running && (
        <p class="muted small">
          <Spinner label="Grading" /> Grading the rest of the game…
        </p>
      )}
      {flagged.length === 0 ? (
        !running && <p class="muted">No questionable moves or blunders.</p>
      ) : (
        <ol class="flagged">
          {flagged.map((f) => {
            const d = line.moveAt(f.k) as Dir;
            return (
              <li key={f.k}>
                <button type="button" class={`fl g-${f.grade}`} onClick={() => p.onJump(f.k)}>
                  <span class="fl-n">Move {f.k + 1}</span>
                  <span class="fl-dir">
                    {arrowOf(d)} {cap(DIR_NAMES[d])}
                  </span>
                  <span class={`grade ${f.grade}`}>{GRADE_WORDS[f.grade]}</span>
                  {f.why && <span class="fl-why">{cap(f.why)}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}
      <div class="actions">
        <button type="button" class="btn" onClick={p.onClose} data-autofocus>
          Close
        </button>
      </div>
    </Modal>
  );
}
