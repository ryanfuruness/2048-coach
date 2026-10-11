import { useState } from 'preact/hooks';
import { type Board as BoardT, parseBoard, toValues } from '@shared/rules.ts';
import { digitsClass, tileClass } from './Board.tsx';
import { tileValue } from '@shared/rules.ts';

export const PRESETS: { name: string; board: string; note: string }[] = [
  { name: 'Ordinary 512', board: '0 2 4 8 / 0 0 16 32 / 0 2 64 128 / 2 4 256 512', note: 'A healthy snake in the corner' },
  { name: 'Blocked chain', board: '2 4 8 16 / 0 8 32 64 / 2 4 128 256 / 0 2 512 1024', note: 'A 32 blocks the 1024 chain' },
  { name: 'Near-dead board', board: '2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0', note: 'One wrong move ends the game' },
  { name: 'Unusual formation', board: '0 2 4 0 / 2 0 0 0 / 2048 8192 1024 2 / 2 4096 2 0', note: 'Big tiles in the middle: odds less certain' },
  { name: 'Expert block', board: '2 1024 8192 32768 / 4 64 2048 16384 / 4 8 16 32 / 2 0 8 4', note: 'A 3x2 block: not judged without exact tables' },
  { name: 'Late game', board: '2 4 2 0 / 16 8 4 2 / 256 512 64 32 / 16384 8192 4096 2048', note: 'A long chain from 16384' },
  { name: 'Opening', board: '2 0 0 0 / 0 0 0 0 / 0 0 0 0 / 0 0 0 2', note: 'The first move of a game' },
];

const PALETTE = [0, ...Array.from({ length: 17 }, (_, i) => i + 1)];

export function boardText(b: BoardT): string {
  const v = toValues(b);
  return [0, 1, 2, 3].map((r) => v.slice(r * 4, r * 4 + 4).join(' ')).join(' / ');
}

interface Props {
  board: BoardT;
  onBoard: (b: BoardT) => void;
  pen: number;
  onPen: (r: number) => void;
}

/** The position editor's tools (the board itself is the main board): tile palette, sample positions, paste and copy. */
export function Editor(p: Props) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => {
    const b = parseBoard(text);
    if (!b) return setError('Enter 16 tile values (0 for an empty cell), row by row, or 16 hex digits.');
    setError(null);
    p.onBoard(b);
    setText('');
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(boardText(p.board));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setText(boardText(p.board));
    }
  };

  return (
    <div class="editor-tools">
      <div class="palette" role="radiogroup" aria-label="Tile to place">
        {PALETTE.map((r) => (
          <button
            type="button"
            role="radio"
            aria-checked={p.pen === r}
            aria-label={r ? `Tile ${tileValue(r)}` : 'Empty (eraser)'}
            class={`pal ${p.pen === r ? 'on' : ''} ${r ? `${tileClass(r)} ${digitsClass(r)}` : 'eraser'}`}
            onClick={() => p.onPen(r)}
            key={r}
          >
            {r ? tileValue(r) : '✕'}
          </button>
        ))}
      </div>
      <p class="hint-text">Pick a tile, then tap cells to place it. Tap a cell again to clear it.</p>
      <div class="presets">
        {PRESETS.map((s) => (
          <button type="button" class="chip" key={s.name} title={s.note} onClick={() => p.onBoard(parseBoard(s.board)!)}>
            {s.name}
          </button>
        ))}
        <button type="button" class="chip" onClick={() => p.onBoard(new Array(16).fill(0))}>
          Clear
        </button>
      </div>
      <form
        class="paste"
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
      >
        <label for="board-text">Paste a board</label>
        <div class="paste-row">
          <input
            id="board-text"
            type="text"
            inputMode="text"
            autoComplete="off"
            spellcheck={false}
            placeholder="2 4 8 16 / 0 0 2 32 / …"
            value={text}
            onInput={(e) => setText((e.target as HTMLInputElement).value)}
          />
          <button type="submit" class="btn small">
            Load
          </button>
          <button type="button" class="btn small ghost" onClick={copy}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        {error && (
          <p class="field-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
