import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import {
  type Board as BoardT,
  type Dir,
  type DirName,
  type Rng,
  DIR_NAMES,
  Sfc32,
  cryptoRng,
  dirFromName,
  isLegal,
  maxRank,
  parseBoard,
  fromBoardCode,
  tileValue,
} from '@shared/rules.ts';
import { Board, type BoardArrow } from '../components/Board.tsx';
import { EvalBar } from '../components/EvalBar.tsx';
import { type TileView, settle, tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { CoachModes, Confirm, Link, modeDescription } from '../components/ui.tsx';
import { WarnSheet } from '../components/WarnSheet.tsx';
import { analyses, analyzeKey, ApiError } from '../lib/api.ts';
import { arrowOf, cap, healthOf, int, milestone, nextTile } from '../lib/format.ts';
import {
  type GameRecord,
  bestScore,
  currentGameId,
  loadGame,
  newRecord,
  playMove,
  rememberBest,
  replay,
  saveGame,
  setCurrentGame,
} from '../lib/games.ts';
import { useMedia, useStore, useTitle } from '../lib/hooks.ts';
import { useDirectionKeys, useSwipe } from '../lib/input.ts';
import { reviewGame } from '../lib/reviews.ts';
import { navigate } from '../lib/router.ts';
import { DEFAULT_SKILL, player } from '../lib/skill.ts';
import { settings } from '../lib/storage.ts';
import type { Analysis, MoveInfo } from '../lib/types.ts';

interface Prompt {
  dir: Dir;
  move: MoveInfo;
  best: Dir;
  bestReason?: string;
  nextTile: number;
}

interface Session {
  game: GameRecord;
  boards: BoardT[];
  rng: Rng;
}

/** The reference move of an analysis: the one losses are measured against (loss 0), else the engine's move. */
export function bestOf(a: Analysis): DirName | null {
  return a.moves.find((m) => m.loss === 0)?.move ?? a.engine_move;
}

function startSession(board: BoardT, origin: 'new' | 'position', rng: Rng): Session {
  const game = newRecord(board, origin);
  setCurrentGame(game.id);
  return { game, boards: [board], rng };
}

function newGameBoard(rng: Rng): BoardT {
  const b: BoardT = new Array(16).fill(0);
  for (let k = 0; k < 2; k++) {
    const empty = b.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0);
    const cell = empty[Math.min(empty.length - 1, Math.floor(rng.next() * empty.length))];
    b[cell] = rng.next() < 0.1 ? 2 : 1;
  }
  return b;
}

/** The session at page load: a position from the URL (?board=...&seed=...), else the unfinished game, else a new one. */
function initialSession(): Session {
  const q = new URLSearchParams(location.search);
  const seed = q.get('seed');
  const rng: Rng = seed !== null && /^\d{1,15}$/.test(seed) ? Sfc32.fromNumber(Number(seed)) : cryptoRng();
  const boardParam = q.get('board');
  if (boardParam !== null || seed !== null) history.replaceState(null, '', '/');
  if (boardParam) {
    const b = fromBoardCode(boardParam) ?? parseBoard(boardParam);
    if (b && b.some((v) => v > 0)) return startSession(b, 'position', rng);
  }
  if (seed === null) {
    const id = currentGameId();
    const g = id ? loadGame(id) : null;
    if (g && !g.over) {
      try {
        return { game: g, boards: replay(g), rng };
      } catch {
        /* a damaged record: start over */
      }
    }
  }
  return startSession(newGameBoard(rng), 'new', rng);
}

export function Play() {
  useTitle('2048 Coach · play smarter');
  const { coach, seenIntro } = useStore(settings);
  const me = useStore(player);
  const skill = me.skill ?? DEFAULT_SKILL;
  const wide = useMedia('(min-width: 960px)');

  const session = useRef<Session | null>(null);
  if (!session.current) session.current = initialSession();
  const s = session.current;
  const g = s.game;
  const board = s.boards[s.boards.length - 1];

  const [, setVersion] = useState(0);
  const rerender = () => setVersion((v) => v + 1);
  const [tiles, setTiles] = useState<TileView[]>(() => tilesFromBoard(board, 'new'));
  const [, setArrived] = useState(0); // re-render when an analysis arrives (analyses live in the shared cache)
  const [provisional, setProvisional] = useState<{ tile: number; p: number } | null>(null);
  const [offline, setOffline] = useState(false);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [hint, setHint] = useState<'none' | 'offered' | 'open'>('none');
  const [shake, setShake] = useState(0);
  const [confirmNew, setConfirmNew] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [announce, setAnnounce] = useState('');
  const [best, setBest] = useState(() => bestScore());

  const hist = g.moves.slice(-20);
  const opts = useMemo(() => ({ skill, hist }), [skill, hist]);
  const key = analyzeKey(board, opts);

  // the analysis of the position on the board, if it has arrived (never one of an earlier position)
  const analysis = coach === 'off' ? null : (analyses.peek(key) ?? null);

  // prefetch the analysis of every new position as soon as it appears (never waited for)
  useEffect(() => {
    if (coach === 'off' || g.over || analyses.peek(key)) return;
    let live = true;
    analyses.get(board, opts).then(
      () => {
        if (!live) return;
        setArrived((n) => n + 1);
        setOffline(false);
      },
      (e) => {
        if (live && e instanceof ApiError && (e.status === 0 || e.status >= 500)) setOffline(true);
      },
    );
    return () => {
      live = false;
    };
  }, [key, coach]);

  // opening hints: offered (not forced) where players at this level often go wrong
  useEffect(() => {
    if (analysis?.hint && coach === 'warn' && !g.over && hint === 'none') {
      setHint('offered');
      g.coach.hints++;
    }
  }, [analysis, coach]);

  // the slide animation ends: drop the merged tiles' ghosts
  useEffect(() => {
    if (!tiles.some((t) => t.kind === 'ghost')) return;
    const t = setTimeout(() => setTiles((ts) => settle(ts)), 140);
    return () => clearTimeout(t);
  }, [tiles]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  const commit = (d: Dir, a: Analysis | null) => {
    const before = s.boards[s.boards.length - 1];
    const res = playMove(g, before, d, s.rng);
    if (!res) return;
    s.boards.push(res.board);
    // ask for the next position's analysis right away, before the render (the effect below picks the request up)
    if (coach !== 'off' && !g.over) analyses.get(res.board, { skill, hist: g.moves.slice(-20) }).catch(() => {});
    setTiles((prev) => tilesAfterMove(prev, res.result.steps, res.result.board, res.spawn));
    const m = a?.moves.find((x) => x.move === DIR_NAMES[d]);
    const ms = milestone(m?.odds);
    setProvisional(ms ?? (provisionalOf(a) ?? null));
    setPrompt(null);
    setHint('none');
    saveGame(g, res.board);
    rememberBest(g.score);
    if (!settings.get().seenIntro) settings.set({ ...settings.get(), seenIntro: true });
    setBest((b) => Math.max(b, g.score));
    const grew = maxRank(res.board) > maxRank(before);
    if (grew && maxRank(res.board) >= 9) setToast(`New tile: ${tileValue(maxRank(res.board))}`);
    setAnnounce(`Moved ${DIR_NAMES[d]}. Score ${g.score}.${g.over ? ' Game over.' : ''}`);
    if (g.over) reviewGame(g.id).catch(() => {});
    else if (player.get().skill === null && g.moves.length >= 120 && (g.moves.length - 120) % 200 === 0)
      reviewGame(g.id, { partial: true }).catch(() => {}); // a first skill reading, mid-game
    rerender();
  };

  const attempt = (d: Dir) => {
    if (confirmNew) return;
    if (prompt) {
      if (d === prompt.best) takeSuggestion();
      else if (d === prompt.dir) playAnyway();
      return;
    }
    if (g.over) return;
    if (!isLegal(board, d)) {
      setShake((k) => k + 1);
      return;
    }
    const a = analyses.peek(key) ?? null; // the analysis only counts if it is already here
    if (coach === 'warn' && a && a.judged !== false && !a.game_over) {
      const m = a.moves.find((x) => x.move === DIR_NAMES[d]);
      const b = bestOf(a);
      if (m?.warn && b && b !== m.move) {
        g.coach.warnings++;
        setPrompt({
          dir: d,
          move: m,
          best: dirFromName(b) as Dir,
          bestReason: a.moves.find((x) => x.move === b)?.reasons[0]?.text,
          nextTile: nextTile(maxRank(board)),
        });
        return;
      }
    }
    commit(d, a);
  };

  const takeSuggestion = () => {
    if (!prompt) return;
    g.coach.warningsTaken++;
    commit(prompt.best, analyses.peek(key) ?? null);
  };
  const playAnyway = () => prompt && commit(prompt.dir, analyses.peek(key) ?? null);

  useDirectionKeys((d) => attempt(d));
  const swipeRef = useRef<HTMLDivElement>(null);
  useSwipe(swipeRef, (d) => attempt(d));

  const startNew = (b?: BoardT) => {
    const rng = cryptoRng();
    session.current = startSession(b ?? newGameBoard(rng), b ? 'position' : 'new', rng);
    setTiles(tilesFromBoard(session.current.boards[0], 'new'));
    setProvisional(null);
    setPrompt(null);
    setHint('none');
    setConfirmNew(false);
    setAnnounce('New game.');
    rerender();
  };
  const askNew = () => (g.moves.length > 0 && !g.over ? setConfirmNew(true) : startNew());

  // what the coach shows
  const a = analysis;
  const ms = a ? milestone(a.odds) : provisional;
  const evalP = a ? (ms?.p ?? null) : (provisional?.p ?? null);
  const notJudged = a?.judged === false;
  const yours = a && ms && me.skill !== null ? personalOf(a, ms.tile) : null;
  const bestName = a && !a.game_over ? bestOf(a) : null;
  const bestDir = bestName ? (dirFromName(bestName) as Dir) : null;
  const bestReason = bestName ? a!.moves.find((m) => m.move === bestName)?.reasons[0] : undefined;
  const showBest = !g.over && bestDir !== null && (coach === 'best' || hint === 'open');
  const arrows: BoardArrow[] = [];
  if (prompt) arrows.push({ dir: prompt.dir, tone: 'warn' }, { dir: prompt.best, tone: 'best' });
  else if (showBest) arrows.push({ dir: bestDir!, tone: 'best' });

  const scores = (
    <div class="scores">
      <div class="score-box">
        <span class="score-label">Score</span>
        <span class="score-value">{int(g.score)}</span>
      </div>
      <div class="score-box">
        <span class="score-label">Best</span>
        <span class="score-value">{int(Math.max(best, g.score))}</span>
      </div>
      <button type="button" class="btn new-game" onClick={askNew}>
        New game
      </button>
    </div>
  );
  const intro = !seenIntro && g.moves.length === 0 && g.origin === 'new';

  const evalNote = notJudged
    ? 'Block formation: not judged by the engine'
    : a && !a.odds && !a.game_over
      ? 'No odds at this stage'
      : null;

  return (
    <div class={`play ${coach === 'off' ? 'coach-off' : ''}`}>
      <section class="play-main" ref={swipeRef} aria-label="Game">
        {!wide && scores}
        {coach !== 'off' && !wide && (
          <EvalBar p={evalP} tile={ms?.tile ?? null} health={a ? healthOf(a) : 'unknown'} pending={!a && !g.over} offline={offline} note={evalNote} yours={yours} />
        )}
        <div class="board-row">
          {coach !== 'off' && wide && (
            <EvalBar vertical p={evalP} tile={ms?.tile ?? null} health={a ? healthOf(a) : 'unknown'} pending={!a && !g.over} offline={offline} note={evalNote} yours={yours} />
          )}
          <Board tiles={tiles} arrows={arrows} shakeKey={shake} label={`Game board. Score ${g.score}.`} class="main-board">
            {g.over && (
              <div class="board-over" data-no-swipe>
                <div class="over-card">
                  <h2>Game over</h2>
                  <p>
                    {g.origin === 'position' ? 'From a set-up position · ' : `${int(g.score)} points · `}best tile {tileValue(g.maxRank)} · {g.moves.length}{' '}
                    {g.moves.length === 1 ? 'move' : 'moves'}
                  </p>
                  <button type="button" class="btn primary big" onClick={() => navigate(`/review/${g.id}`)}>
                    Review this game
                  </button>
                  <button type="button" class="btn" onClick={() => startNew()}>
                    New game
                  </button>
                </div>
              </div>
            )}
          </Board>
        </div>
        <p class="controls-hint">{wide ? 'Use the arrow keys (or WASD) to play.' : 'Swipe on the board to play.'}</p>
      </section>

      <aside class="coach-panel" aria-label="Coach">
        {wide && scores}
        {wide && (
          <div class="panel-head">
            <h2>Coach</h2>
            <span class="panel-sub">{modeDescription(coach)}</span>
          </div>
        )}
        <CoachModes value={coach} onChange={(m) => settings.set({ ...settings.get(), coach: m })} />
        <div class="coach-line" aria-live="polite">
          {intro ? (
            <p>
              <strong>Welcome!</strong> {wide ? 'Use the arrow keys' : 'Swipe'} to merge equal tiles. I will warn you before a big mistake. No sign-up needed.
            </p>
          ) : g.over ? (
            <p>The game is over. Review it to see your key moments.</p>
          ) : coach === 'off' ? (
            <p>The coach is off. Your game is still saved, so you can review it afterwards.</p>
          ) : offline ? (
            <p class="muted">The analysis server is not reachable right now. Keep playing; the coach will be back.</p>
          ) : coach === 'best' ? (
            bestName ? (
              <p>
                <span class="pill best">
                  {arrowOf(bestName)} {cap(bestName)}
                </span>{' '}
                {notJudged ? 'is only a suggestion here (block formation).' : bestReason ? `${bestReason.text}.` : 'is the best move here.'}
              </p>
            ) : (
              <p class="muted">Thinking…</p>
            )
          ) : hint === 'offered' ? (
            <button type="button" class="hint-chip" onClick={() => (setHint('open'), g.coach.hintsOpened++)}>
              <span aria-hidden="true">?</span> Tricky position · want a hint?
            </button>
          ) : hint === 'open' && bestName ? (
            <p>
              <span class="pill best">
                {arrowOf(bestName)} {cap(bestName)}
              </span>{' '}
              {bestReason ? `${bestReason.text}.` : 'is the move to play here.'}
            </p>
          ) : (
            <p>
              I will stop you before a big mistake. <span class="muted">Hints appear in tricky opening positions.</span>
            </p>
          )}
        </div>
        <div class="panel-actions">
          {g.moves.length >= 20 && !g.over && (
            <Link href={`/review/${g.id}`} class="btn small">
              Review so far
            </Link>
          )}
          <Link href="/how" class="btn small ghost">
            How the coach works
          </Link>
        </div>
        {wide && (
          <dl class="session-stats">
            <div>
              <dt>Moves</dt>
              <dd>{g.moves.length}</dd>
            </div>
            <div>
              <dt>Warnings</dt>
              <dd>
                {g.coach.warnings}
                {g.coach.warnings ? <small> ({g.coach.warningsTaken} taken)</small> : null}
              </dd>
            </div>
            <div>
              <dt>Your level</dt>
              <dd>{me.skill === null ? <small>after your first review</small> : me.skill.toFixed(2)}</dd>
            </div>
          </dl>
        )}
      </aside>

      {prompt && (
        <WarnSheet
          move={prompt.move}
          best={DIR_NAMES[prompt.best]}
          bestReason={prompt.bestReason}
          nextTile={prompt.nextTile}
          onTake={takeSuggestion}
          onAnyway={playAnyway}
          onCancel={() => setPrompt(null)}
        />
      )}
      {confirmNew && (
        <Confirm
          title="Start a new game?"
          body="Your current game is saved in your history, so you can still review it."
          yes="New game"
          onYes={() => startNew()}
          onNo={() => setConfirmNew(false)}
        />
      )}
      {toast && (
        <div class="toast" role="status">
          {toast}
        </div>
      )}
      <div class="sr-only" aria-live="polite">
        {announce}
      </div>
    </div>
  );
}

function provisionalOf(a: Analysis | null) {
  return a ? milestone(a.odds) : null;
}

/** Personal odds of the milestone tile (for a player of the estimated skill), when the model gives them. */
function personalOf(a: Analysis, tile: number): number | null {
  const po = a.personal_odds;
  if (!po) return null;
  const v = po[String(tile)];
  return typeof v === 'number' ? v : null;
}

