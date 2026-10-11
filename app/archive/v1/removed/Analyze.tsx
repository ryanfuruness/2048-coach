import { useEffect, useMemo, useState } from 'preact/hooks';
import { type Board as BoardT, boardCode, canMove, distinctRanks, fromBoardCode, maxRank, parseBoard, tileValue, toValues } from '@shared/rules.ts';
import { Board, type BoardArrow, digitsClass, tileClass } from '../components/Board.tsx';
import { MoveRows } from '../components/MoveRows.tsx';
import { Spinner } from '../components/ui.tsx';
import { analyses, ApiError } from '../lib/api.ts';
import { arrowOf, cap, chance, cost, dirIndex, healthOf, nextTile } from '../lib/format.ts';
import { currentGameId, loadGame, replay } from '../lib/games.ts';
import { useStore, useTitle } from '../lib/hooks.ts';
import { navigate } from '../lib/router.ts';
import { DEFAULT_SKILL, player, skillLabel } from '../lib/skill.ts';
import type { Analysis } from '../lib/types.ts';

const PRESETS: { name: string; board: string; note: string }[] = [
  { name: 'Ordinary 512', board: '0 2 4 8 / 0 0 16 32 / 0 2 64 128 / 2 4 256 512', note: 'A healthy snake in the corner' },
  { name: 'Blocked chain', board: '2 4 8 16 / 0 8 32 64 / 2 4 128 256 / 0 2 512 1024', note: 'A 32 blocks the 1024 chain' },
  { name: 'Near-dead board', board: '2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0', note: 'One wrong move ends the game' },
  { name: 'Unusual formation', board: '0 2 4 0 / 2 0 0 0 / 2048 8192 1024 2 / 2 4096 2 0', note: 'Big tiles in the middle: odds less certain' },
  { name: 'Expert block', board: '2 1024 8192 32768 / 4 64 2048 16384 / 4 8 16 32 / 2 0 8 4', note: 'A 3x2 block: not judged without exact tables' },
  { name: 'Opening', board: '2 0 0 0 / 0 0 0 0 / 0 0 0 0 / 0 0 0 2', note: 'The first move of a game' },
];

const PALETTE = [0, ...Array.from({ length: 17 }, (_, i) => i + 1)];

function boardText(b: BoardT): string {
  const v = toValues(b);
  return [0, 1, 2, 3].map((r) => v.slice(r * 4, r * 4 + 4).join(' ')).join(' / ');
}

function initialBoard(): BoardT {
  const q = new URLSearchParams(location.search).get('board');
  if (q) {
    const b = fromBoardCode(q) ?? parseBoard(q);
    if (b) return b;
  }
  const id = currentGameId();
  const g = id ? loadGame(id) : null;
  if (g && !g.over && g.moves.length > 0) {
    try {
      const bs = replay(g);
      return bs[bs.length - 1];
    } catch {
      /* fall through */
    }
  }
  return parseBoard(PRESETS[0].board)!;
}

export function Analyze() {
  useTitle('Analyze a position · 2048 Coach');
  const me = useStore(player);
  const skill = me.skill ?? DEFAULT_SKILL;
  const [board, setBoard] = useState<BoardT>(initialBoard);
  const [pen, setPen] = useState(1);
  const [deep, setDeep] = useState(false);
  const [text, setText] = useState('');
  const [textError, setTextError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [state, setState] = useState<{ a: Analysis | null; loading: boolean; error: string | null }>({ a: null, loading: false, error: null });

  const tiles = board.filter((v) => v > 0).length;
  const valid = tiles > 0 && distinctRanks(board) <= 15;

  useEffect(() => {
    history.replaceState(null, '', `/analyze?board=${boardCode(board)}`);
    if (!valid) {
      setState({ a: null, loading: false, error: null });
      return;
    }
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    const t = setTimeout(() => {
      analyses.get(board, { skill, depth: deep ? 5 : 0 }).then(
        (a) => live && setState({ a, loading: false, error: null }),
        (e) =>
          live &&
          setState({
            a: null,
            loading: false,
            error: e instanceof ApiError && e.status === 0 ? 'The analysis server cannot be reached. Is it running?' : (e as Error).message,
          }),
      );
    }, 120);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [boardCode(board), deep, skill]);

  const setCell = (cell: number) => {
    const b = board.slice();
    b[cell] = b[cell] === pen ? 0 : pen;
    setBoard(b);
  };

  const loadText = () => {
    const b = parseBoard(text);
    if (!b) return setTextError('Enter 16 tile values (0 for an empty cell), row by row, or 16 hex digits.');
    setTextError(null);
    setBoard(b);
    setText('');
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(boardText(board));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setText(boardText(board));
    }
  };

  const a = state.a;
  const bestName = a && !a.game_over ? (a.moves.find((m) => m.loss === 0)?.move ?? a.engine_move) : null;
  const bestDir = dirIndex(bestName);
  const arrows: BoardArrow[] = bestDir !== -1 ? [{ dir: bestDir, tone: 'best', label: 'best' }] : [];
  const odds = useMemo(() => (a?.odds ? Object.entries(a.odds).sort((x, y) => Number(x[0]) - Number(y[0])) : []), [a]);
  const health = healthOf(a);
  const next = nextTile(maxRank(board));
  const plan = a?.plan_info;
  const playable = valid && canMove(board);

  return (
    <div class="page analyze">
      <div class="page-head">
        <h1>Analyze a position</h1>
        <p class="lead">Set up any board, or paste one. The engine says how good it is, what to play and why.</p>
      </div>
      <div class="analyze-grid">
        <section class="editor" aria-label="Board editor">
          <Board
            board={board}
            arrows={arrows}
            onCell={setCell}
            cellLabel={(i) => `Row ${Math.floor(i / 4) + 1}, column ${(i % 4) + 1}: ${board[i] ? tileValue(board[i]) : 'empty'}. Tap to set ${pen ? tileValue(pen) : 'empty'}.`}
            chain={plan?.chain}
            nextCell={plan?.next_cell}
            label="Board editor"
          />
          <div class="palette" role="radiogroup" aria-label="Tile to place">
            {PALETTE.map((r) => (
              <button
                type="button"
                role="radio"
                aria-checked={pen === r}
                aria-label={r ? `Tile ${tileValue(r)}` : 'Empty (eraser)'}
                class={`pal ${pen === r ? 'on' : ''} ${r ? `${tileClass(r)} ${digitsClass(r)}` : 'eraser'}`}
                onClick={() => setPen(r)}
                key={r}
              >
                {r ? tileValue(r) : '✕'}
              </button>
            ))}
          </div>
          <p class="hint-text">Pick a tile, then tap cells to place it. Tap a cell again to clear it.</p>
          <div class="presets">
            {PRESETS.map((p) => (
              <button type="button" class="chip" key={p.name} title={p.note} onClick={() => setBoard(parseBoard(p.board)!)}>
                {p.name}
              </button>
            ))}
            <button type="button" class="chip" onClick={() => setBoard(new Array(16).fill(0))}>
              Clear
            </button>
          </div>
          <form
            class="paste"
            onSubmit={(e) => {
              e.preventDefault();
              loadText();
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
            {textError && (
              <p class="field-error" role="alert">
                {textError}
              </p>
            )}
          </form>
        </section>

        <section class="analysis" aria-label="Analysis" aria-busy={state.loading}>
          <div class="analysis-actions">
            <button type="button" class="btn primary big" disabled={!playable} onClick={() => navigate(`/?board=${boardCode(board)}`)}>
              Play from here
            </button>
            <label class="toggle">
              <input type="checkbox" checked={deep} onChange={(e) => setDeep((e.target as HTMLInputElement).checked)} />
              <span>Deeper analysis</span>
            </label>
            {state.loading && <Spinner label="Analyzing" />}
          </div>

          {!valid ? (
            <p class="card notice">{tiles === 0 ? 'Place at least one tile to analyze the position.' : 'This board has more than 15 different tiles.'}</p>
          ) : state.error ? (
            <p class="card notice">{state.error}</p>
          ) : !a ? (
            <div class="card notice">
              <Spinner /> Analyzing…
            </div>
          ) : (
            <div class={`analysis-body ${state.loading ? 'stale' : ''}`}>
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
                          <span class="verdict-label">{a.judged === false ? 'Suggestion only' : 'Best move'}</span>
                          <strong>{cap(bestName)}</strong>
                        </div>
                        {a.judged === false && <span class="tag neutral verdict-tag">Not judged</span>}
                      </div>
                    )}
                    <p class="verdict-text">{a.summary}</p>
                  </>
                )}
              </div>

              {odds.length > 0 && (
                <div class="odds">
                  <h2>Chances with best play</h2>
                  <div class="odds-row">
                    {odds.map(([t, p]) => (
                      <div class="odd" key={t}>
                        <span class="odd-tile">{t}</span>
                        <span class="odd-p">{chance(p)}</span>
                        <span class="odd-bar">
                          <i style={{ width: `${Math.max(2, p * 100)}%` }} />
                        </span>
                      </div>
                    ))}
                  </div>
                  {a.odds_caveat && <p class="muted small">Odds are less certain here: this formation is unusual for the stage.</p>}
                  {a.personal_odds && me.skill !== null && (
                    <p class="muted small">
                      At your level ({skillLabel(me.skill).toLowerCase()}):{' '}
                      {Object.entries(a.personal_odds)
                        .filter(([k, v]) => /^\d+$/.test(k) && typeof v === 'number')
                        .map(([k, v]) => `${k} ${chance(v as number)}`)
                        .join(' · ')}
                    </p>
                  )}
                </div>
              )}

              {!a.game_over && (
                <div class="moves-card">
                  <h2>Every move</h2>
                  <MoveRows
                    moves={maxRank(board) >= 14 ? a.moves.map(({ find_prob: _f, ...m }) => m) : a.moves}
                    best={bestName}
                    judged={a.judged !== false}
                    nextTile={next}
                    allReasons
                  />
                  {a.error_risk !== undefined && (
                    <p class="muted small">
                      At your level: the move you are likely to make costs {cost(a.error_risk)} of your chances on average
                      {a.hint ? ', so the coach would offer a hint here.' : '.'}
                    </p>
                  )}
                </div>
              )}

              {a.plan && (
                <div class="plan card">
                  <h2>The plan</h2>
                  <p>{a.plan}</p>
                  {plan?.chain && <p class="muted small">Your chain is outlined in blue on the board{plan.next_cell !== undefined ? '; the cell to build next in green' : ''}.</p>}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
