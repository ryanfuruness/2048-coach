// The board: play 2048 with the coach beside you. Every move gets the coach's grade (best, good, questionable,
// blunder); undo and redo move through the game. The coach is the panel beside the board (below it on a phone): one
// switch turns it all on or off, and options show its move, explain the moves, warn before blunders and highlight
// the tiles that matter; it can also play on from any position.
import { useEffect, useRef, useState } from 'preact/hooks';
import {
  type Board as BoardT,
  type Dir,
  type DirName,
  DIR_NAMES,
  Sfc32,
  boardCode,
  canMove,
  cryptoRng,
  dirFromName,
  distinctRanks,
  fromBoardCode,
  isLegal,
  parseBoard,
  tileValue,
} from '@shared/rules.ts';
import { Board, type BoardArrow, type CellMark } from '../components/Board.tsx';
import { Editor } from '../components/Editor.tsx';
import { Menu } from '../components/Menu.tsx';
import { MoveList, OddsCards } from '../components/MoveList.tsx';
import { ReviewSheet, gameCounts } from '../components/ReviewSheet.tsx';
import { type TileView, settle, tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { Modal, OptionRow, Spinner, Switch, blurAfterPointer } from '../components/ui.tsx';
import { WarnSheet } from '../components/WarnSheet.tsx';
import { analyses, analyzeKey, ApiError } from '../lib/api.ts';
import { arrowOf, cap, int } from '../lib/format.ts';
import { GRADE_WORDS, coachOf, isFlagged, shortWhy } from '../lib/grades.ts';
import { useStore, useTitle } from '../lib/hooks.ts';
import { useDirectionKeys, useSwipe } from '../lib/input.ts';
import { type Author, Line, bestScore, loadLineRecord, newGameBoard } from '../lib/line.ts';
import { navigate } from '../lib/router.ts';
import { settings, updateSettings } from '../lib/storage.ts';
import type { Analysis, MoveInfo } from '../lib/types.ts';
import { SPEEDS, type Speed, type Until, Workbench } from '../lib/workbench.ts';

interface Prompt {
  pos: string;
  dir: Dir;
  move: MoveInfo;
  best: Dir;
}

/** The line at page load: a position from the URL (?board=...&seed=...), else the saved line, else a new game. */
function initialWorkbench(speed: Speed): Workbench {
  const q = new URLSearchParams(location.search);
  const seed = q.get('seed');
  const rng = seed !== null && /^\d{1,15}$/.test(seed) ? Sfc32.fromNumber(Number(seed)) : cryptoRng();
  const boardParam = q.get('board');
  if (location.pathname !== '/' || location.search) history.replaceState(null, '', '/');
  const saved = loadLineRecord();
  let line: Line | null = null;
  if (boardParam) {
    const b = fromBoardCode(boardParam) ?? parseBoard(boardParam);
    if (b && b.some((v) => v > 0) && distinctRanks(b) <= 15) line = Line.fresh(b, 'position', rng);
  }
  if (!line && seed === null && saved) {
    try {
      line = new Line(saved, rng);
    } catch {
      /* a damaged record: start over */
    }
  }
  const fromUrl = line === null || boardParam !== null;
  if (!line) line = Line.fresh(newGameBoard(rng), 'new', rng);
  const wb = new Workbench(line, speed);
  // a link replaced the line on the board: it can be restored
  if (fromUrl && saved && saved.moves.length > 0 && saved.id !== line.id) wb.replaced = { rec: saved, what: 'new', dropped: 0, at: Date.now() };
  wb.scheduleSave(0);
  return wb;
}

function Icon({ d, size = 20 }: { d: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path d={d} fill="currentColor" />
    </svg>
  );
}
const ICONS = {
  start: 'M5 5h2.5v14H5zM19 5.5v13L8.5 12z',
  back: 'M17 5.5v13L6.5 12z',
  forward: 'M7 5.5v13L17.5 12z',
  end: 'M16.5 5H19v14h-2.5zM5 5.5l10.5 6.5L5 18.5z',
  dots: 'M5 10.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm7 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm7 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3z',
  speed: 'M12 4a9 9 0 00-9 9c0 2 .6 3.8 1.7 5.3l1.6-1.2A7 7 0 015 13a7 7 0 0114 0c0 1.5-.5 2.9-1.3 4.1l1.6 1.2A9 9 0 0012 4zm4.2 4.4l-5 5.6a1.5 1.5 0 102.1 2.1l3.6-6.9z',
};

function isTyping(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  return !!el && !!el.tagName && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
}

const STOPS: { label: string; until: Until; title: string }[] = [
  { label: '10', until: 10, title: 'The coach plays 10 moves' },
  { label: '100', until: 100, title: 'The coach plays 100 moves' },
  { label: 'Next tile', until: 'tile', title: 'The coach plays until the next bigger tile' },
  { label: '∞', until: 'stop', title: 'The coach plays until you stop it (P)' },
];

export function Dojo() {
  useTitle('2048 Coach');
  const st = useStore(settings);

  const wbRef = useRef<Workbench | null>(null);
  if (!wbRef.current) wbRef.current = initialWorkbench(st.speed);
  const wb = wbRef.current;
  const line = wb.line;

  // workbench events mark the view dirty; it renders once per frame (fast autoplay plays several moves a frame)
  const [, setTick] = useState(0);
  const raf = useRef(0);
  const schedule = () => {
    if (!raf.current) raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      setTick((t) => t + 1);
    });
  };

  // the tiles on the board: animated from move to move; a board they do not show is drawn as it is
  const anim = useRef<{ code: string; tiles: TileView[] }>({ code: boardCode(line.board()), tiles: tilesFromBoard(line.board(), 'new') });
  const settleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [promptSt, setPrompt] = useState<Prompt | null>(null);
  const [edit, setEdit] = useState<{ board: BoardT; pen: number } | null>(null);
  const [shake, setShake] = useState(0);
  const [toast, setToast] = useState<{ text: string; id: number } | null>(null);
  const [help, setHelp] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [waitingShown, setWaitingShown] = useState(false);
  const [announce, setAnnounce] = useState('');
  const waiting = useRef(false);
  const bestRef = useRef(bestScore());
  const lastShown = useRef<Analysis | null>(null);

  const showToast = (text: string) => setToast({ text, id: Date.now() });

  useEffect(
    () =>
      wb.subscribe((e) => {
        const L = wb.line;
        if (e.type === 'move') {
          const from = e.res.from;
          if (e.animate && anim.current.code === boardCode(L.boards[from])) {
            anim.current = { code: boardCode(L.board()), tiles: tilesAfterMove(anim.current.tiles, e.res.result.steps, e.res.result.board, e.res.spawn) };
            if (settleTimer.current) clearTimeout(settleTimer.current);
            settleTimer.current = setTimeout(() => {
              anim.current = { ...anim.current, tiles: settle(anim.current.tiles) };
              schedule();
            }, 140);
          }
          const grew = L.tops[from + 1] > L.tops[from];
          const fast = wb.auto.on && SPEEDS[wb.auto.speed].ms < 300;
          if (grew && L.tops[from + 1] >= 10 && !fast) showToast(`${tileValue(L.tops[from + 1])}!`);
          if (e.by === 'u') setAnnounce(`Moved ${DIR_NAMES[L.moveAt(from) as Dir]}. Score ${L.score()}.${L.over() ? ' Game over.' : ''}`);
          bestRef.current = Math.max(bestRef.current, L.score());
        } else if (e.type === 'line') {
          setPrompt(null);
        } else if (e.type === 'auto') {
          if (!wb.auto.on && wb.auto.message) showToast(wb.auto.message);
        }
        schedule();
      }),
    [wb],
  );

  // save on leaving the page (autoplay saves are coalesced)
  useEffect(() => {
    const f = () => wb.flush();
    window.addEventListener('pagehide', f);
    document.addEventListener('visibilitychange', f);
    return () => {
      window.removeEventListener('pagehide', f);
      document.removeEventListener('visibilitychange', f);
    };
  }, [wb]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);

  // the offer to restore a replaced line stays for 9 s
  const rep = wb.replaced;
  useEffect(() => {
    if (!rep) return;
    const t = setTimeout(() => wb.dismissReplaced(), Math.max(0, 9000 - (Date.now() - rep.at)));
    return () => clearTimeout(t);
  }, [rep]);

  // ---- what is on the board ----
  const k = line.cursor;
  const n = line.n;
  const board = line.board();
  const over = line.over();
  const posKey = `${line.id}:${k}:${n}`;
  const prompt = promptSt && promptSt.pos === posKey ? promptSt : null;
  const coachOn = st.coach;
  /** grades under the board: with the coach, or on their own with the coach off */
  const gradesOn = coachOn || st.grades;
  const hintsOn = coachOn && st.hints;
  const warnOn = coachOn && st.warn;
  const hlOn = coachOn && st.highlights;
  wb.wantAnalysis = gradesOn;
  const autoOn = wb.auto.on;
  const fastAuto = autoOn && SPEEDS[wb.auto.speed].ms < 300;

  const code = boardCode(board);
  if (anim.current.code !== code) anim.current = { code, tiles: tilesFromBoard(board) };

  // the analysis of the position on the board, and of the one before (the last move's grade)
  const a0 = edit ? undefined : wb.peek();
  if (a0) lastShown.current = a0;
  const prevA = !edit && k > 0 ? wb.peek(k - 1) : undefined;

  // ask for the analysis of the position once the cursor rests on it (moves prefetch their own)
  useEffect(() => {
    if (!gradesOn || autoOn || edit || wb.peek()) return;
    const t = setTimeout(() => wb.analyze().catch(() => {}), 60);
    return () => clearTimeout(t);
  }, [posKey, gradesOn, autoOn, edit !== null]);
  // and of the position before it (the grade of the move that led here), e.g. after stepping through the game
  useEffect(() => {
    if (!gradesOn || autoOn || edit || k === 0 || wb.peek(k - 1)) return;
    const t = setTimeout(() => wb.analyze(k - 1).catch(() => {}), 120);
    return () => clearTimeout(t);
  }, [posKey, gradesOn, autoOn, edit !== null]);

  // ---- the editor's own analysis ----
  const editOk = edit !== null && edit.board.some((v) => v > 0) && distinctRanks(edit.board) <= 15;
  const editKey = edit ? analyzeKey(edit.board, {}) : '';
  const [editState, setEditState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  useEffect(() => {
    if (!edit || !editOk) return;
    if (analyses.peek(editKey)) return setEditState({ loading: false, error: null });
    let live = true;
    setEditState({ loading: true, error: null });
    const t = setTimeout(() => {
      analyses.get(edit.board, {}).then(
        () => live && setEditState({ loading: false, error: null }),
        (e) =>
          live &&
          setEditState({
            loading: false,
            error: e instanceof ApiError && e.status === 0 ? 'The coach cannot be reached.' : (e as Error).message,
          }),
      );
    }, 120);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [editKey, editOk]);
  const editA = edit && editOk ? analyses.peek(editKey) : undefined;

  // ---- actions ----
  const commit = (d: Dir, by: Author) => {
    const res = wb.play(d, by);
    if (!res) return;
    setPrompt(null);
  };

  const attempt = async (d: Dir) => {
    if (edit || help || reviewOpen) return;
    if (wb.auto.on) return wb.stopAuto();
    if (prompt) {
      if (d === prompt.best) takeSuggestion();
      else if (d === prompt.dir) playAnyway();
      return;
    }
    if (waiting.current) return; // a move is waiting for the coach's verdict
    const L = wb.line;
    if (L.over() || !isLegal(L.board(), d)) return setShake((s) => s + 1);
    if (warnOn) {
      // the coach judges before the move goes through: wait for its verdict on this position (usually there already)
      let a = wb.peek();
      if (!a) {
        const at = `${L.id}:${L.cursor}:${L.n}`;
        waiting.current = true;
        const spin = setTimeout(() => setWaitingShown(true), 120);
        try {
          a = await Promise.race([wb.analyze(), new Promise<undefined>((r) => setTimeout(() => r(undefined), 2000))]);
        } catch {
          a = undefined;
        }
        clearTimeout(spin);
        waiting.current = false;
        setWaitingShown(false);
        if (`${wb.line.id}:${wb.line.cursor}:${wb.line.n}` !== at) return;
      }
      if (a && !a.game_over) {
        const m = a.moves.find((x) => x.move === DIR_NAMES[d]);
        const b = coachOf(a);
        if (m?.grade === 'blunder' && b && b !== m.move) {
          wb.line.rec.coach.warnings++;
          setPrompt({ pos: `${wb.line.id}:${wb.line.cursor}:${wb.line.n}`, dir: d, move: m, best: dirFromName(b) as Dir });
          return;
        }
      }
    }
    commit(d, 'u');
  };
  const takeSuggestion = () => {
    if (!prompt) return;
    wb.line.rec.coach.warningsTaken++;
    commit(prompt.best, 'c');
  };
  const playAnyway = () => prompt && commit(prompt.dir, 'u');

  /** Plays the coach's move (waiting for the analysis if it is not here yet); nothing with the coach off. */
  const playBest = async () => {
    if (edit || prompt || help || !settings.get().coach) return;
    if (wb.auto.on) return wb.stopAuto();
    const L = wb.line;
    if (L.over()) return setShake((s) => s + 1);
    const at = posKey;
    let a = wb.peek();
    if (!a) {
      try {
        a = await wb.analyze();
      } catch {
        return showToast('The coach is offline.');
      }
    }
    if (`${wb.line.id}:${wb.line.cursor}:${wb.line.n}` !== at) return;
    const b = coachOf(a);
    if (b) commit(dirFromName(b) as Dir, 'c');
  };
  const playMove = (name: DirName) => {
    const d = dirFromName(name);
    if (d === -1) return;
    const a = wb.peek();
    if (a && coachOf(a) === name) commit(d, 'c');
    else void attempt(d);
  };

  const back = (steps = 1) => {
    if (edit) return;
    wb.stopAuto();
    setPrompt(null);
    wb.seek(wb.line.cursor - steps);
  };
  const forward = (steps = 1) => {
    if (edit) return;
    wb.stopAuto();
    setPrompt(null);
    if (steps === 1) wb.forward();
    else wb.seek(wb.line.cursor + steps);
  };
  const seek = (to: number) => {
    if (edit) return;
    wb.stopAuto();
    setPrompt(null);
    wb.seek(to);
  };
  const startAuto = (until: Until) => {
    if (edit) return;
    setPrompt(null);
    if (wb.line.over()) return setShake((s) => s + 1);
    wb.startAuto(until);
  };
  const toggleAuto = () => (wb.auto.on ? wb.stopAuto() : settings.get().coach ? startAuto('stop') : undefined);
  const setSpeed = (s: Speed) => {
    wb.setSpeed(s);
    updateSettings({ speed: s });
  };
  const newGame = () => {
    setEdit(null);
    wb.newLine(newGameBoard(cryptoRng()), 'new', 'new');
  };
  const startEdit = () => {
    wb.stopAuto();
    setPrompt(null);
    setEdit({ board: wb.line.board().slice(), pen: 1 });
  };
  const finishEdit = () => {
    if (!edit || !editOk) return;
    wb.newLine(edit.board, 'position', 'edit');
    setEdit(null);
  };
  const openReview = () => {
    const s = settings.get();
    if (wb.line.n === 0 || !(s.coach || s.grades)) return;
    setReviewOpen(true);
    // grade the moves the live analyses did not (e.g. a fast stretch): one batch over the whole game
    if (gameCounts(wb.line).unknown > 0) void wb.runReview();
  };
  const jumpTo = (pos: number) => {
    setReviewOpen(false);
    // the board shows the position after the move, so the line under it reads that move's grade
    seek(Math.min(wb.line.n, pos + 1));
  };
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(`${location.origin}/?board=${boardCode(edit ? edit.board : board)}`);
      showToast('Link copied');
    } catch {
      showToast('Copying is not allowed here.');
    }
  };

  // ---- keyboard ----
  useDirectionKeys((d) => void attempt(d), !edit && !help && !reviewOpen);
  const swipeRef = useRef<HTMLDivElement>(null);
  useSwipe(swipeRef, (d) => void attempt(d));
  const keyRef = useRef<(e: KeyboardEvent) => void>(() => {});
  keyRef.current = (e: KeyboardEvent) => {
    if (e.defaultPrevented || isTyping(e.target) || help || reviewOpen) return;
    if (document.querySelector('.backdrop')) return; // a dialog takes its own keys
    const key = e.key;
    if (e.ctrlKey || e.metaKey) {
      if (key === 'z' || key === 'Z') {
        e.preventDefault();
        if (e.shiftKey) forward();
        else back();
      } else if (key === 'y') {
        e.preventDefault();
        forward();
      }
      return;
    }
    if (e.altKey) return;
    const onControl = (e.target as HTMLElement | null)?.closest?.('button, a, select, summary');
    if (edit) {
      if (key === 'Escape') setEdit(null);
      else if (key === 'Enter' && !onControl) finishEdit();
      return;
    }
    switch (key) {
      case ' ':
      case 'Enter':
        if (onControl || !settings.get().coach) return;
        e.preventDefault();
        void playBest();
        return;
      case 'z':
      case 'Backspace':
        e.preventDefault();
        return back();
      case 'Z':
        e.preventDefault();
        return back(10);
      case 'x':
        e.preventDefault();
        return forward();
      case 'X':
        e.preventDefault();
        return forward(10);
      case 'Home':
        e.preventDefault();
        return seek(0);
      case 'End':
        e.preventDefault();
        return seek(wb.line.n);
      case 'p':
      case 'P':
        e.preventDefault();
        return toggleAuto();
      case 'c':
      case 'C':
        return updateSettings({ coach: !settings.get().coach });
      case 'h':
      case 'H':
        return updateSettings({ coach: true, hints: !(settings.get().coach && settings.get().hints) });
      case 'e':
      case 'E':
        return startEdit();
      case 'r':
      case 'R':
        return openReview();
      case '?':
        return setHelp(true);
      case 'Escape':
        if (wb.auto.on) wb.stopAuto();
        return;
    }
  };
  useEffect(() => {
    const f = (e: KeyboardEvent) => keyRef.current(e);
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, []);

  // ---- the coach's view ----
  const bestName = a0 && !a0.game_over ? coachOf(a0) : null;
  const bestDir = bestName ? (dirFromName(bestName) as Dir) : null;
  const playedHere = k < n ? (line.moveAt(k) as Dir) : null;
  // the last move: its grade, the better move and where it went wrong
  const lastDir = k > 0 ? (line.moveAt(k - 1) as Dir) : null;
  const lastMove = lastDir !== null && prevA ? prevA.moves.find((m) => m.move === DIR_NAMES[lastDir]) : undefined;
  const lastFact = k > 0 ? line.facts[k - 1] : undefined;
  const lastGrade = lastMove ? (prevA?.judged === false ? null : (lastMove.grade ?? null)) : lastFact?.grade;
  const lastBetter = prevA ? coachOf(prevA) : lastFact && lastFact.best !== -1 ? DIR_NAMES[lastFact.best] : null;

  const arrows: BoardArrow[] = [];
  if (!edit && !over && prompt) arrows.push({ dir: prompt.dir, tone: 'warn' }, { dir: prompt.best, tone: 'best' });
  else if (!edit && !over && !fastAuto && hintsOn && bestDir !== null) {
    if (playedHere !== null && playedHere !== bestDir) {
      const g = a0?.moves.find((m) => m.move === DIR_NAMES[playedHere])?.grade ?? line.facts[k]?.grade;
      arrows.push({ dir: playedHere, tone: isFlagged(g) ? 'warn' : 'played', label: line.author(k) === 'c' ? 'coach' : 'played' });
    }
    arrows.push({
      dir: bestDir,
      tone: playedHere === bestDir ? 'same' : 'best',
      label: playedHere === bestDir ? 'played ✓' : undefined,
      onClick: autoOn ? undefined : () => commit(bestDir, 'c'),
      title: `Play ${bestName} (Space)`,
    });
  }

  // highlights: where the last move went wrong, until the next move (no green "where the coach's move acts": its plan
  // cell matched what the coach then did 40% of the time, its merges are plain to see; results/plancell/REPORT.md)
  const marks: CellMark[] = [];
  if (hlOn && !edit && !fastAuto && isFlagged(lastGrade)) for (const c of lastMove?.fault_cells ?? []) marks.push({ cell: c, tone: 'fault' });

  // ---- the grade of the last move, in one line under the board ----
  const gradeLine = () => {
    if (!gradesOn || edit) return null;
    if (lastDir === null) return n === 0 ? <span class="muted">Make a move: the coach grades it here.</span> : null;
    const who = line.author(k - 1);
    const head = (
      <>
        <span class="gl-dir">
          {arrowOf(lastDir)} {cap(DIR_NAMES[lastDir])}
        </span>
        {who === 'c' && <span class="grade coach">coach</span>}
      </>
    );
    if (who === 'c') return head;
    if (lastGrade === undefined) return null;
    if (lastGrade === null) return <span class="grade">Not judged</span>;
    const undo = isFlagged(lastGrade) && k === n && (
      <button type="button" class="btn small gl-undo" onClick={(e) => (back(), blurAfterPointer(e))}>
        Undo
      </button>
    );
    // the coach off: just the grade; "Why?" opens the coach, whose line then says why and what it would play
    if (!coachOn)
      return (
        <>
          <span class="gl-main">
            <span class={`grade ${lastGrade}`}>{GRADE_WORDS[lastGrade]}</span>
            {isFlagged(lastGrade) && (
              <button type="button" class="linklike gl-why-open" onClick={(e) => (updateSettings({ coach: true }), blurAfterPointer(e))}>
                Why?
              </button>
            )}
          </span>
          {undo}
        </>
      );
    // a best move needs no more words than its grade
    if (lastGrade === 'best') return <span class="grade best">{GRADE_WORDS.best}</span>;
    const why = isFlagged(lastGrade) || (st.explain && lastGrade === 'good') ? shortWhy(lastMove?.why ?? lastMove?.reasons.find((r) => r.code !== 'later' && r.code !== 'shape')?.text) : '';
    return (
      <>
        <span class="gl-main">
          <span class={`grade ${lastGrade}`}>{GRADE_WORDS[lastGrade]}</span>
          {why && <span class="gl-why">{cap(why)}</span>}
          {lastBetter && lastBetter !== DIR_NAMES[lastDir] && (
            <span class="gl-better" title={`The coach would play ${lastBetter}`}>
              Coach:{' '}
              <b>
                {arrowOf(lastBetter)} {cap(lastBetter)}
              </b>
            </span>
          )}
        </span>
        {undo}
      </>
    );
  };

  // ---- the coach: the panel beside the board ----
  const panelA = edit ? editA : hintsOn && !fastAuto ? (a0 ?? lastShown.current ?? undefined) : undefined;
  const moves = !coachOn ? null : edit && !editOk ? (
    <p class="muted small">{edit.board.some((v) => v > 0) ? 'More than 15 different tiles.' : 'Place some tiles.'}</p>
  ) : edit && editState.error ? (
    <p class="muted small">{editState.error}</p>
  ) : !edit && !hintsOn ? null : fastAuto ? (
    <p class="muted small">The coach is playing…</p>
  ) : panelA ? (
    <MoveList
      a={panelA}
      stale={edit ? editState.loading : !a0}
      played={!edit && playedHere !== null ? DIR_NAMES[playedHere] : null}
      onPlay={edit || autoOn || over ? undefined : playMove}
      explain={st.explain}
    />
  ) : wb.offline ? (
    <p class="muted small">The coach is offline.</p>
  ) : (
    <p class="muted small">
      <Spinner label="Thinking" />
    </p>
  );
  const oddsA = edit ? editA : (a0 ?? lastShown.current ?? undefined);
  const odds = coachOn && !fastAuto && oddsA?.odds && Object.keys(oddsA.odds).length > 0 && !oddsA.game_over ? oddsA.odds : null;

  // ---- layout ----
  // "+N" floats up from the score after a forward move that merged tiles
  const prevScore = useRef({ id: line.id, k, score: line.score(), gain: null as null | { id: number; v: number } });
  {
    const ps = prevScore.current;
    const sc = line.score();
    if (ps.id !== line.id || ps.k !== k) {
      ps.gain = ps.id === line.id && k === ps.k + 1 && sc > ps.score ? { id: (ps.gain?.id ?? 0) + 1, v: sc - ps.score } : null;
      Object.assign(ps, { id: line.id, k, score: sc });
    }
  }
  const gain = fastAuto ? null : prevScore.current.gain;
  const counts = over && gradesOn ? gameCounts(line) : null;
  const scores = (
    <div class="scores">
      <div class="score-box">
        <span class="score-label">Score</span>
        <span class="score-value">{int(line.score())}</span>
        {gain && (
          <span class="score-gain" key={gain.id} aria-hidden="true">
            +{int(gain.v)}
          </span>
        )}
      </div>
      <div class="score-box">
        <span class="score-label">Best</span>
        <span class="score-value">{int(Math.max(bestRef.current, line.score()))}</span>
      </div>
      <button type="button" class="btn small new-game" onClick={(e) => (newGame(), blurAfterPointer(e))}>
        New game
      </button>
      <Menu
        label="More"
        button={<Icon d={ICONS.dots} />}
        items={[
          { label: 'Review your moves', hint: 'R', onSelect: openReview, disabled: n === 0 || !gradesOn },
          { label: edit ? 'Stop editing' : 'Set up a position', hint: 'E', onSelect: () => (edit ? setEdit(null) : startEdit()) },
          { label: 'Copy a link to this position', onSelect: () => void copyLink() },
          { label: 'Keyboard shortcuts', hint: '?', onSelect: () => setHelp(true) },
          { label: 'How it works', onSelect: () => navigate('/how') },
        ]}
      />
    </div>
  );

  const transport = (
    <div class="transport" role="group" aria-label="Move through the game">
      <button type="button" class="btn small icon" onClick={(e) => (seek(0), blurAfterPointer(e))} disabled={k === 0 || !!edit} title="Start (Home)" aria-label="Start">
        <Icon d={ICONS.start} />
      </button>
      <button type="button" class="btn small icon" onClick={(e) => (back(), blurAfterPointer(e))} disabled={k === 0 || !!edit} title="Back (Z)" aria-label="Back one move">
        <Icon d={ICONS.back} />
      </button>
      <span class="tp-pos" aria-live="polite">
        {k === 0 ? 'Start' : `Move ${int(k)}`}
        {n > 0 && k < n && <small> / {int(n)}</small>}
      </span>
      <button type="button" class="btn small icon" onClick={(e) => (forward(), blurAfterPointer(e))} disabled={k === n || !!edit} title="Forward (X)" aria-label="Forward one move">
        <Icon d={ICONS.forward} />
      </button>
      <button type="button" class="btn small icon" onClick={(e) => (seek(n), blurAfterPointer(e))} disabled={k === n || !!edit} title="End (End)" aria-label="End">
        <Icon d={ICONS.end} />
      </button>
    </div>
  );

  const autoplay = (
    <div class={`autoplay ${autoOn ? 'running' : ''}`} role="group" aria-label="The coach plays">
      <span class="ap-label">The coach plays</span>
      {autoOn ? (
        <button type="button" class="btn small primary ap-stop" onClick={(e) => (wb.stopAuto(), blurAfterPointer(e))} title="Stop (P or Esc)">
          Stop · {int(wb.auto.played)}
        </button>
      ) : (
        <div class="ap-buttons">
          <button type="button" class="btn small" onClick={(e) => (void playBest(), blurAfterPointer(e))} disabled={over || !!edit} title="The coach's move (Space)">
            1
          </button>
          {STOPS.map((s) => (
            <button type="button" class="btn small" key={s.label} onClick={(e) => (startAuto(s.until), blurAfterPointer(e))} disabled={over || !!edit} title={s.title}>
              {s.label}
            </button>
          ))}
        </div>
      )}
      <Menu
        label="Speed"
        class="ap-speed"
        button={<Icon d={ICONS.speed} size={18} />}
        items={SPEEDS.map((s, i) => ({ label: `${wb.auto.speed === i ? '✓ ' : ''}${s.title}`, onSelect: () => setSpeed(i as Speed) }))}
      />
    </div>
  );

  const coachPanel = (
    <aside class={`panel coach ${coachOn ? 'on' : 'off'}`} aria-label="Coach">
      <div class="coach-head">
        <div>
          <h2 id="coach-title">Coach</h2>
          <p class="coach-sub">{coachOn ? 'Grades every move you make.' : st.grades ? 'Off: you play, it only grades.' : 'Off: just the game.'}</p>
        </div>
        <Switch big on={coachOn} onChange={(v) => updateSettings({ coach: v })} label="Coach" title="The coach on or off (C)" />
      </div>
      {!coachOn && (
        <div class="options" role="group" aria-label="With the coach off">
          <OptionRow
            label="Grades only"
            desc="Best, Good, Questionable or Blunder under the board. Open the coach when you want to know why."
            on={st.grades}
            onChange={(v) => updateSettings({ grades: v })}
          />
        </div>
      )}
      {coachOn && (
        <>
          <div class="options" role="group" aria-label="What the coach shows">
            <OptionRow label="Best move" desc="The coach's move and every move's grade" on={st.hints} onChange={(v) => updateSettings({ hints: v })} title="H" />
            <OptionRow label="Explain" desc="Why each move is good or bad, and the plan" on={st.explain} onChange={(v) => updateSettings({ explain: v })} />
            <OptionRow label="Warn me" desc="Stop me before a blunder" on={st.warn} onChange={(v) => updateSettings({ warn: v })} />
            <OptionRow label="Highlights" desc="Marks the tiles where a move went wrong" on={st.highlights} onChange={(v) => updateSettings({ highlights: v })} />
          </div>
          {moves}
          {odds && (
            <div class="odds-box">
              <button type="button" class="linklike odds-toggle" aria-expanded={st.odds} onClick={(e) => (updateSettings({ odds: !st.odds }), blurAfterPointer(e))}>
                Engine odds
              </button>
              {st.odds && <OddsCards odds={odds} />}
            </div>
          )}
          {!edit && autoplay}
        </>
      )}
    </aside>
  );

  const restoreToast = rep && (
    <div class="toast with-action" role="status">
      <span>{rep.what === 'branch' ? `${int(rep.dropped)} moves replaced.` : rep.what === 'edit' ? 'New position.' : 'New game.'}</span>
      <button type="button" class="toast-action" onClick={() => wb.restore()}>
        Undo
      </button>
      <button type="button" class="toast-close" aria-label="Dismiss" onClick={() => wb.dismissReplaced()}>
        ✕
      </button>
    </div>
  );

  return (
    <div class={`dojo with-panel ${edit ? 'editing' : ''}`}>
      <section class="bench" aria-label="Board">
        {scores}
        <div class="board-row" ref={swipeRef}>
          {edit ? (
            <Board
              board={edit.board}
              onCell={(cell) => {
                const b = edit.board.slice();
                b[cell] = b[cell] === edit.pen ? 0 : edit.pen;
                setEdit({ ...edit, board: b });
              }}
              cellLabel={(i) =>
                `Row ${Math.floor(i / 4) + 1}, column ${(i % 4) + 1}: ${edit.board[i] ? tileValue(edit.board[i]) : 'empty'}. Tap to set ${edit.pen ? tileValue(edit.pen) : 'empty'}.`
              }
              label="Board editor"
              class="main-board editing"
            />
          ) : (
            <Board
              tiles={anim.current.tiles}
              arrows={arrows}
              marks={marks}
              shakeKey={shake}
              label={`Game board, ${k === 0 ? 'start' : `after move ${k}`}. Score ${line.score()}.`}
              class="main-board"
            >
              {waitingShown && (
                <div class="board-wait" role="status" aria-label="The coach is thinking">
                  <Spinner />
                </div>
              )}
              {over && (
                <div class="board-over" data-no-swipe>
                  <div class="over-card">
                    <h2>Game over</h2>
                    <p>
                      {int(line.score())} points · best tile {tileValue(line.tops[k])}
                    </p>
                    {counts && (counts.blunder > 0 || counts.questionable > 0) && (
                      <p class="over-counts">
                        {counts.blunder > 0 && (
                          <span class="grade blunder">
                            {counts.blunder} blunder{counts.blunder === 1 ? '' : 's'}
                          </span>
                        )}
                        {counts.questionable > 0 && <span class="grade questionable">{counts.questionable} questionable</span>}
                      </p>
                    )}
                    <div class="over-actions">
                      <button type="button" class="btn primary" onClick={(e) => (back(), blurAfterPointer(e))}>
                        Undo
                      </button>
                      {gradesOn && (
                        <button type="button" class="btn" onClick={openReview}>
                          Review
                        </button>
                      )}
                      <button type="button" class="btn" onClick={(e) => (newGame(), blurAfterPointer(e))}>
                        New game
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </Board>
          )}
        </div>
        {edit ? (
          <>
            <div class="edit-bar">
              <button type="button" class="btn primary" disabled={!editOk || !canMove(edit.board)} onClick={finishEdit}>
                Play from here
              </button>
              <button type="button" class="btn" onClick={() => setEdit(null)}>
                Cancel
              </button>
            </div>
            <Editor board={edit.board} onBoard={(b) => setEdit({ ...edit, board: b })} pen={edit.pen} onPen={(r) => setEdit({ ...edit, pen: r })} />
          </>
        ) : (
          <>
            <div class="grade-line" aria-live="polite">
              {gradesOn && (
                <div class="gl-body" key={`${line.id}:${k}`} data-k={k}>
                  {gradeLine()}
                </div>
              )}
            </div>
            {transport}
          </>
        )}
      </section>

      {coachPanel}

      {prompt && <WarnSheet move={prompt.move} best={DIR_NAMES[prompt.best]} onTake={takeSuggestion} onAnyway={playAnyway} onCancel={() => setPrompt(null)} />}
      {reviewOpen && <ReviewSheet line={line} review={wb.review} onJump={jumpTo} onClose={() => setReviewOpen(false)} />}
      {help && <Shortcuts onClose={() => setHelp(false)} />}
      {restoreToast}
      {toast && !rep && (
        <div class="toast" role="status" key={toast.id}>
          {toast.text}
        </div>
      )}
      <div class="sr-only" aria-live="polite">
        {announce}
      </div>
    </div>
  );
}

const SHORTCUTS: [string, string][] = [
  ['← ↑ → ↓ or W A S D', 'move (swipe on a phone)'],
  ['Space', "the coach's move"],
  ['Z / X', 'back / forward (Shift: ten)'],
  ['Home / End', 'start / end'],
  ['P', 'the coach plays on / stops'],
  ['C', 'coach on / off'],
  ['H', 'best move on / off'],
  ['R', 'review your moves'],
  ['E', 'set up a position'],
];

function Shortcuts({ onClose }: { onClose: () => void }) {
  return (
    <Modal onClose={onClose} labelledBy="keys-title" class="shortcuts">
      <h2 id="keys-title">Keyboard shortcuts</h2>
      <dl class="keys">
        {SHORTCUTS.map(([key, v]) => (
          <div key={key}>
            <dt>
              <kbd>{key}</kbd>
            </dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <div class="actions">
        <button type="button" class="btn" onClick={onClose} data-autofocus>
          Close
        </button>
      </div>
    </Modal>
  );
}
