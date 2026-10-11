import type { DirName } from '@shared/rules.ts';
import { arrowOf, cap } from '../lib/format.ts';
import { shortWhy } from '../lib/grades.ts';
import type { MoveInfo } from '../lib/types.ts';
import { Modal } from './ui.tsx';

interface Props {
  move: MoveInfo;
  best: DirName;
  onTake: () => void;
  onAnyway: () => void;
  onCancel: () => void;
}

/** The coach stops you just before a blunder: what is wrong with it and the better move, one tap either way. */
export function WarnSheet(p: Props) {
  const why = shortWhy(p.move.why);
  return (
    <Modal onClose={p.onCancel} labelledBy="warn-title" describedBy="warn-body" role="alertdialog" class="warn">
      <div class="warn-head">
        <div class="warn-badge" aria-hidden="true">
          !
        </div>
        <h2 id="warn-title">
          {arrowOf(p.move.move)} {cap(p.move.move)} is a blunder
        </h2>
      </div>
      {why && <p id="warn-body">{cap(why)}.</p>}
      <div class="actions">
        <button type="button" class="btn primary" onClick={p.onTake} data-autofocus>
          {arrowOf(p.best)} Play {cap(p.best)}
        </button>
        <button type="button" class="btn" onClick={p.onAnyway}>
          Play {cap(p.move.move)} anyway
        </button>
      </div>
      <p class="keys-hint">
        <kbd>{arrowOf(p.best)}</kbd> the coach's move · <kbd>{arrowOf(p.move.move)}</kbd> yours · <kbd>Esc</kbd> back
      </p>
    </Modal>
  );
}
