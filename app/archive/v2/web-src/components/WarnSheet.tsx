import type { DirName } from '@shared/rules.ts';
import type { HumanCost } from '../lib/chance.ts';
import { arrowOf, because, cap, chance, cost } from '../lib/format.ts';
import type { MoveInfo } from '../lib/types.ts';
import { Modal } from './ui.tsx';

interface Props {
  /** what the move costs you (your chance where the analysis has it) */
  cost?: HumanCost | null;
  move: MoveInfo;
  best: DirName;
  bestReason?: string;
  /** the tile "your chances" refer to: the next doubling of the largest tile */
  nextTile: number;
  onTake: () => void;
  onAnyway: () => void;
  onCancel: () => void;
}

/** The coach's warning just before a costly move: what it costs, why, and the better move - one tap either way. */
export function WarnSheet(p: Props) {
  const yc = p.move.your_cost ?? p.move.real_loss ?? null;
  const c = p.cost && p.cost.kind === 'chance' && p.cost.best !== null && p.cost.after !== null ? p.cost : null;
  // only a checked cause (with its share of the loss) is worth a sentence in a warning; unchecked hints are not
  const main = p.move.reasons.find((r) => r.share !== undefined && r.code !== 'later' && r.code !== 'shape');
  return (
    <Modal onClose={p.onCancel} labelledBy="warn-title" describedBy="warn-body" role="alertdialog" class="warn">
      <div class="warn-head">
        <div class="warn-badge" aria-hidden="true">
          !
        </div>
        <h2 id="warn-title">
          Wait: {arrowOf(p.move.move)} {cap(p.move.move)} is a costly move
        </h2>
      </div>
      <p id="warn-body">
        {(p.move.real_loss ?? 0) >= 0.8 ? (
          <>
            It will very likely <strong>end your game</strong>.
          </>
        ) : c ? (
          <>
            It lowers your chance of reaching <strong>{p.nextTile}</strong> from <strong>{chance(c.best)}</strong> to{' '}
            <strong>{chance(c.after)}</strong>.
          </>
        ) : (
          <>
            It gives away <strong>{cost(yc)}</strong> of your chances to reach <strong>{p.nextTile}</strong>.
          </>
        )}
        {main ? ` ${because(main)}` : ''}
      </p>
      <div class="warn-suggest">
        <span class="warn-arrow" aria-hidden="true">
          {arrowOf(p.best)}
        </span>
        <span>
          <strong>Try {cap(p.best)} instead</strong>
          {p.bestReason ? `: it ${p.bestReason}.` : '.'}
        </span>
      </div>
      <div class="actions">
        <button type="button" class="btn primary" onClick={p.onTake} data-autofocus>
          {arrowOf(p.best)} Play {cap(p.best)}
        </button>
        <button type="button" class="btn" onClick={p.onAnyway}>
          Play {cap(p.move.move)} anyway
        </button>
      </div>
      <p class="keys-hint">
        <kbd>{arrowOf(p.best)}</kbd> takes the suggestion · <kbd>{arrowOf(p.move.move)}</kbd> plays yours · <kbd>Esc</kbd> goes back
      </p>
    </Modal>
  );
}
