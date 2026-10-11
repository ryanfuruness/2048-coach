import type { DirName } from '@shared/rules.ts';
import { CLASS_WORDS, arrowOf, because, cap, lossClass, pctShort } from '../lib/format.ts';
import type { Reason } from '../lib/types.ts';

export interface RowMove {
  move: DirName;
  loss: number | null;
  real_loss?: number | null;
  your_cost?: number | null;
  warn?: boolean;
  breaks_corner?: boolean;
  find_prob?: number;
  p?: number;
  reasons: Reason[];
}

interface Props {
  moves: RowMove[];
  best: DirName | null;
  played?: DirName | null;
  judged: boolean;
  /** the tile "your chances" refer to */
  nextTile: number;
  /** show every reason of the best move too (analysis), or only the played move's (review) */
  allReasons?: boolean;
}

function order(m: RowMove, best: DirName | null): number {
  if (m.move === best) return -1;
  return m.real_loss ?? m.loss ?? 1e9;
}

/** Every legal move with what it costs and why: the best move first, then by cost. */
export function MoveRows(p: Props) {
  const rows = [...p.moves].sort((a, b) => order(a, p.best) - order(b, p.best));
  return (
    <ul class="moves" role="list">
      {rows.map((m) => {
        const isBest = m.move === p.best;
        const isPlayed = m.move === p.played;
        const cls = isBest ? null : lossClass(m.real_loss);
        const reasons = p.allReasons || isPlayed || isBest ? m.reasons : [];
        return (
          <li key={m.move} class={`move ${isBest ? 'is-best' : ''} ${isPlayed ? 'is-played' : ''}`}>
            <div class="move-head">
              <span class={`move-dir ${isBest ? 'best' : cls ?? ''}`} aria-hidden="true">
                {arrowOf(m.move)}
              </span>
              <span class="move-name">{cap(m.move)}</span>
              {isBest && <span class="tag best">{p.judged ? 'Best' : 'Suggestion'}</span>}
              {isPlayed && <span class="tag played">Played</span>}
              {!isBest && cls && <span class={`tag ${cls}`}>{CLASS_WORDS[cls]}</span>}
              {m.warn && <span class="tag warn">Coach warns</span>}
              {m.breaks_corner && <span class="tag neutral">Breaks the corner</span>}
              <span class="move-nums">
                {!p.judged ? (
                  <span class="muted">not judged</span>
                ) : isBest ? (
                  <span class="muted">{m.p !== undefined ? `table ${pctShort(m.p)}` : 'no loss'}</span>
                ) : (m.real_loss ?? 0) < 0.001 && (m.your_cost ?? 0) < 0.001 ? (
                  <span class="muted">as good</span>
                ) : (
                  <>
                    <span title="Real loss: the share of the expected future score this move gives up with good play afterwards">
                      −{pctShort(m.real_loss)}
                    </span>
                    {m.your_cost !== undefined && m.your_cost !== null && (
                      <span class="muted" title={`The share of your own chances of reaching ${p.nextTile} that this move gives away`}>
                        {' '}
                        · your chances −{pctShort(m.your_cost)}
                      </span>
                    )}
                  </>
                )}
              </span>
            </div>
            {m.find_prob !== undefined && (
              <div class="move-find">
                <span class="find-bar">
                  <i style={{ width: `${Math.round(m.find_prob * 100)}%` }} />
                </span>
                Played by {Math.round(m.find_prob * 100)}% of players at your level
              </div>
            )}
            {reasons.length > 0 && (
              <ul class="reasons">
                {reasons.map((r, i) => (
                  <li key={i} class={r.share !== undefined ? 'checked' : ''}>
                    {isBest ? `${cap(r.text)}.` : because(r)}
                    {r.share !== undefined && (
                      <span class="share" title="The part of the loss that removing exactly this defect recovers (checked in this position)">
                        {Math.round(Math.min(1, r.share) * 100)}% of the loss
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
