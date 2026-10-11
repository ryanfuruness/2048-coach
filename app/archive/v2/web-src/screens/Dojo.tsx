// The workbench: one screen to play, analyze and review. The board shows one position of the line; undo, redo and the
// timeline move through the line, any move from an earlier position starts a new continuation, the coach can play
// from any position at a chosen speed, and the panel analyzes whatever is on the board (or reviews the whole line).
import { useEffect, useRef, useState } from 'preact/hooks';
import {
  type Board as BoardT,
  type Dir,
  DIR_NAMES,
  Sfc32,
  boardCode,
  canMove,
  cryptoRng,
  dirFromName,
  distinctRanks,
  fromBoardCode,
  isLegal,
  maxRank,
  parseBoard,
  tileValue,
} from '@shared/rules.ts';
import { AnalysisView } from '../components/AnalysisView.tsx';
import { Board, type BoardArrow } from '../components/Board.tsx';
import { Editor, boardText } from '../components/Editor.tsx';
import { EvalBar } from '../components/EvalBar.tsx';
import { Menu } from '../components/Menu.tsx';
import { ReviewView } from '../components/ReviewView.tsx';
import { type TileView, settle, tilesAfterMove, tilesFromBoard } from '../components/tiles.ts';
import { Timeline } from '../components/Timeline.tsx';
import { Link, Modal, ModeSwitch, Spinner, blurAfterPointer, modeDescription } from '../components/ui.tsx';
import { WarnSheet } from '../components/WarnSheet.tsx';
import { analyses, analyzeKey, ApiError } from '../lib/api.ts';
import { type HumanCost, coachOf, cornerHabit, costClass, costOf, points, shareClass } from '../lib/chance.ts';
import { CLASS_WORDS, arrowOf, because, cap, chance, healthOf, int, milestone, nextTile, pctShort } from '../lib/format.ts';
import { useMedia, useStore, useTitle } from '../lib/hooks.ts';
import { useDirectionKeys, useSwipe } from '../lib/input.ts';
import { type Author, Line, bestScore, loadLineRecord, newGameBoard } from '../lib/line.ts';
import { DEFAULT_SKILL, player, skillLabel } from '../lib/skill.ts';
import { type Mode, settings, updateSettings } from '../lib/storage.ts';
import type { Analysis, MoveInfo } from '../lib/types.ts';
import { SPEEDS, type Speed, UNTIL_MOVES, type Until, Workbench, bestOf } from '../lib/workbench.ts';

interface Prompt {
  dir: Dir;
  move: MoveInfo;
  best: Dir;
  bestReason?: string;
  nextTile: number;
}

type Tab = 'analysis' | 'review';

/** The line at page load: a position from the URL (?board=...&seed=...), else the saved line, else a new game. */
function initialWorkbench(skill: number, speed: Speed, until: Until): Workbench {
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
  const wb = new Workbench(line, skill, speed, until);
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
  play: 'M7 5v14l12-7z',
  pause: 'M6.5 5h4v14h-4zM13.5 5h4v14h-4z',
  dots: 'M5 10.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm7 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3zm7 0a1.5 1.5 0 110 3 1.5 1.5 0 010-3z',
  edit: 'M4 17.2V20h2.8l8.3-8.3-2.8-2.8zM19.7 7.3a1 1 0 000-1.4l-1.6-1.6a1 1 0 00-1.4 0l-1.3 1.3 2.8 2.8z',
};

/**
 * What the eval bar shows for an analysis: your chance of the milestone (from here, or after move m), else the engine's
 * odds of the next milestone (largest tile 16384 and up, or an older server).
 */
function barValue(a: Analysis, m?: MoveInfo): { tile: number; p: number; you: boolean } | null {
  if (a.chance) return { tile: a.chance.target, p: m && typeof m.chance === 'number' ? m.chance : a.chance.now, you: true };
  const ms = milestone(m?.odds) ?? milestone(a.odds);
  return ms ? { ...ms, you: false } : null;
}

function isTyping(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  return !!el && !!el.tagName && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
}

export function Dojo() {
  useTitle('2048 Coach · play, analyze, review');
  const st = useStore(settings);
  const me = useStore(player);
  const skill = me.skill ?? DEFAULT_SKILL;
  const wide = useMedia('(min-width: 960px)');
  const mode: Mode = st.mode;

  const wbRef = useRef<Workbench | null>(null);
  if (!wbRef.current) wbRef.current = initialWorkbench(skill, st.speed, st.until);
  const wb = wbRef.current;
  wb.skill = skill;
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

  const [tab, setTab] = useState<Tab>('analysis');
  // a warning and a hint belong to the position they were made for (pos: line id, cursor and length)
  const [promptSt, setPrompt] = useState<(Prompt & { pos: string }) | null>(null);
  const [hintSt, setHint] = useState<{ pos: string; state: 'offered' | 'open' } | null>(null);
  const [reveal, setReveal] = useState<string | null>(null);
  const [deep, setDeep] = useState(false);
  const [edit, setEdit] = useState<{ board: BoardT; pen: number } | null>(null);
  const [shake, setShake] = useState(0);
  const [toast, setToast] = useState<{ text: string; id: number } | null>(null);
  const [announce, setAnnounce] = useState('');
  const [help, setHelp] = useState(false);
  // updated on every move without a render of their own (fast autoplay plays several moves a frame)
  const provisional = useRef<{ tile: number; p: number; you: boolean } | null>(null);
  const bestRef = useRef(bestScore());
  const lastShown = useRef<{ a: Analysis; board: BoardT } | null>(null);
  const panelRef = useRef<HTMLElement>(null);
  const pickedByPointer = useRef(0);

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
          // while the next analysis is on its way, the eval bar shows what the last one said about this move
          const prev = wb.peek(from);
          const m = prev?.moves.find((x) => x.move === DIR_NAMES[L.moveAt(from) as Dir]);
          provisional.current = prev ? barValue(prev, m) : null;
          const grew = L.tops[from + 1] > L.tops[from];
          const fast = wb.auto.on && SPEEDS[wb.auto.speed].ms < 300;
          if (grew && L.tops[from + 1] >= 9 && !fast) showToast(`New tile: ${tileValue(L.tops[from + 1])}`);
          if (e.by === 'u') setAnnounce(`Moved ${DIR_NAMES[L.moveAt(from) as Dir]}. Score ${L.score()}.${L.over() ? ' Game over.' : ''}`);
          bestRef.current = Math.max(bestRef.current, L.score());
        } else if (e.type === 'line') {
          setPrompt(null);
          setHint(null);
          provisional.current = null;
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
    const t = setTimeout(() => setToast(null), 2600);
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
  const hint = hintSt && hintSt.pos === posKey ? hintSt.state : 'none';
  const revealed = reveal === `${line.id}:${k}`;
  const showAnalysis = mode === 'analyze' || revealed;
  const needAnalysis = mode !== 'play' || revealed;
  wb.wantAnalysis = needAnalysis;
  const autoOn = wb.auto.on;
  const fastAuto = autoOn && SPEEDS[wb.auto.speed].ms < 300;

  const code = boardCode(board);
  if (anim.current.code !== code) anim.current = { code, tiles: tilesFromBoard(board) };

  // the analysis of the position on the board, once it is here (never one of another position)
  const a0 = edit ? undefined : wb.peek();
  const aDeep = edit || !deep ? undefined : wb.peek(k, 5);
  const shownNow = aDeep ?? a0;
  if (shownNow) lastShown.current = { a: shownNow, board };
  const shown = shownNow ?? (lastShown.current && !edit ? lastShown.current.a : undefined);
  const stale = !shownNow;

  // ask for the analysis of the position once the cursor rests on it (moves prefetch their own)
  useEffect(() => {
    if (!needAnalysis || autoOn || edit || wb.peek()) return;
    const t = setTimeout(() => wb.analyze().catch(() => {}), 80);
    return () => clearTimeout(t);
  }, [posKey, needAnalysis, skill, autoOn, edit !== null]);
  useEffect(() => {
    if (!deep || !showAnalysis || autoOn || edit || over || wb.peek(k, 5)) return;
    const t = setTimeout(() => wb.analyze(k, 5).catch(() => {}), 150);
    return () => clearTimeout(t);
  }, [posKey, deep, showAnalysis, skill, autoOn, edit !== null]);

  // opening hints (Coach mode): offered where players at this level often go wrong
  useEffect(() => {
    if (mode === 'coach' && a0?.hint && !over && !autoOn && hint === 'none' && k === n) {
      setHint({ pos: posKey, state: 'offered' });
      line.rec.coach.hints++;
    }
  }, [posKey, a0, mode, autoOn]);

  // ---- the editor's own analysis ----
  const editOk = edit !== null && edit.board.some((v) => v > 0) && distinctRanks(edit.board) <= 15;
  const editOpts = { skill, depth: deep ? 5 : 0 };
  const editKey = edit ? analyzeKey(edit.board, editOpts) : '';
  const [editState, setEditState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  useEffect(() => {
    if (!edit || !editOk) return;
    if (analyses.peek(editKey)) return setEditState({ loading: false, error: null });
    let live = true;
    setEditState({ loading: true, error: null });
    const t = setTimeout(() => {
      analyses.get(edit.board, editOpts).then(
        () => live && setEditState({ loading: false, error: null }),
        (e) =>
          live &&
          setEditState({
            loading: false,
            error: e instanceof ApiError && e.status === 0 ? 'The analysis server cannot be reached. Is it running?' : (e as Error).message,
          }),
      );
    }, 120);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [editKey, editOk]);
  const editA = edit && editOk ? analyses.peek(editKey) : undefined;
  if (editA) lastShown.current = { a: editA, board: edit!.board };

  // ---- actions ----
  const commit = (d: Dir, by: Author) => {
    const res = wb.play(d, by);
    if (!res) return;
    setPrompt(null);
    setHint(null);
    if (!settings.get().seenIntro) updateSettings({ seenIntro: true });
  };

  const attempt = (d: Dir) => {
    if (edit || help) return;
    if (wb.auto.on) return wb.stopAuto();
    if (prompt) {
      if (d === prompt.best) takeSuggestion();
      else if (d === prompt.dir) playAnyway();
      return;
    }
    const L = wb.line;
    if (L.over() || !isLegal(L.board(), d)) return setShake((s) => s + 1);
    const following = L.cursor < L.n && L.moveAt(L.cursor) === d;
    const a = wb.peek();
    if (mode === 'coach' && !following && a && a.judged !== false && !a.game_over) {
      const m = a.moves.find((x) => x.move === DIR_NAMES[d]);
      const b = bestOf(a);
      if (m?.warn && b && b !== m.move) {
        L.rec.coach.warnings++;
        setPrompt({
          pos: posKey,
          dir: d,
          move: m,
          best: dirFromName(b) as Dir,
          bestReason: a.coach_why ?? a.moves.find((x) => x.move === b)?.reasons[0]?.text,
          nextTile: a.chance?.target ?? nextTile(maxRank(L.board())),
        });
        return;
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

  /** Plays the coach's move (waiting for the analysis if it is not here yet). */
  const playBest = async () => {
    if (edit || prompt || help) return;
    if (wb.auto.on) return wb.stopAuto();
    const L = wb.line;
    if (L.over()) return setShake((s) => s + 1);
    const at = posKey;
    let a = wb.peek();
    if (!a) {
      try {
        a = await wb.analyze();
      } catch {
        return showToast('The coach is offline: no move to play.');
      }
    }
    if (`${wb.line.id}:${wb.line.cursor}:${wb.line.n}` !== at) return;
    const b = bestOf(a);
    if (b) commit(dirFromName(b) as Dir, 'c');
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
  const toggleAuto = () => {
    if (edit) return;
    setPrompt(null);
    if (wb.auto.on) wb.stopAuto();
    else if (wb.line.over()) setShake((s) => s + 1);
    else wb.startAuto();
  };
  const setSpeed = (s: Speed) => {
    wb.setSpeed(s);
    updateSettings({ speed: s });
  };
  const setUntil = (u: Until) => {
    wb.setUntil(u);
    updateSettings({ until: u });
  };
  const toggleReveal = () => {
    if (mode === 'analyze') return;
    setReveal((r) => (r === `${wb.line.id}:${wb.line.cursor}` ? null : `${wb.line.id}:${wb.line.cursor}`));
  };
  const newGame = () => {
    setEdit(null);
    wb.newLine(newGameBoard(cryptoRng()), 'new', 'new');
    setTab('analysis');
  };
  const startEdit = () => {
    wb.stopAuto();
    setPrompt(null);
    setEdit({ board: wb.line.board().slice(), pen: 1 });
    setTab('analysis');
  };
  const finishEdit = () => {
    if (!edit || !editOk) return;
    wb.newLine(edit.board, 'position', 'edit');
    setEdit(null);
  };
  const openReview = (run = true) => {
    setTab('review');
    if (run) void wb.runReview();
    if (!wide) requestAnimationFrame(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  const jumpTo = (pos: number) => {
    seek(pos);
    if (!wide) window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const copyText = async (text: string, done: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast(done);
    } catch {
      showToast('Copying is not allowed here.');
    }
  };

  // ---- keyboard ----
  useDirectionKeys((d) => attempt(d), !edit && !help);
  const keyRef = useRef<(e: KeyboardEvent) => void>(() => {});
  keyRef.current = (e: KeyboardEvent) => {
    if (e.defaultPrevented || isTyping(e.target) || help) return;
    if (document.querySelector('.backdrop')) return; // the warning sheet takes its own keys
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
    const onControl = (e.target as HTMLElement | null)?.closest?.('button, a, select, summary, [role="slider"], [role="tab"]');
    if (edit) {
      if (key === 'Escape') setEdit(null);
      else if (key === 'Enter' && !onControl) finishEdit();
      return;
    }
    switch (key) {
      case ' ':
      case 'Enter':
        if (onControl) return;
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
      case '1':
      case '2':
      case '3':
      case '4':
        return setSpeed((Number(key) - 1) as Speed);
      case 'h':
      case 'H':
        return toggleReveal();
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
  const swipeRef = useRef<HTMLDivElement>(null);
  useSwipe(swipeRef, (d) => attempt(d));

  // ---- the coach's view of the position ----
  const a = a0;
  const ea = edit ? editA : a;
  // a finished game has no odds left: the bar shows the milestone it was playing for, at 0%
  const lastTile = !edit && over && k > 0 ? line.facts[k - 1]?.tile || null : null;
  // without an analysis here yet (e.g. during fast autoplay): what the last one said, or the line's facts
  const fk = line.facts[k] ?? (k > 0 ? line.facts[k - 1] : undefined);
  const factMs = fk && fk.p !== null && fk.tile ? { tile: fk.tile, p: fk.p, you: !!fk.you } : null;
  const lastFact = k > 0 ? line.facts[k - 1] : undefined;
  const ms = ea
    ? (barValue(ea) ?? (ea.game_over && lastTile ? { tile: lastTile, p: 0, you: !!lastFact?.you } : null))
    : edit
      ? null
      : (provisional.current ?? factMs);
  const evalP = ea ? (ms?.p ?? (ea.game_over ? 0 : null)) : (ms?.p ?? null);
  const notJudged = ea?.judged === false;
  // the engine's odds of the same tile, beside your chance
  const engineP = ea && ms?.you ? (ea.odds?.[String(ms.tile)] ?? null) : null;
  // what the move that led here cost (points of your chance)
  const prevA = !edit && k > 0 ? wb.peek(k - 1) : undefined;
  const prevCost = prevA ? costOf(prevA, DIR_NAMES[line.moveAt(k - 1) as Dir]) : null;
  const lastCost = prevCost && prevCost.kind === 'chance' && prevCost.abs !== null ? -prevCost.abs : null;
  const bestName = a && !a.game_over ? bestOf(a) : null;
  const bestDir = bestName ? (dirFromName(bestName) as Dir) : null;
  const playedHere = k < n ? (line.moveAt(k) as Dir) : null;
  const arrows: BoardArrow[] = [];
  if (!edit && !over && !fastAuto) {
    if (prompt) arrows.push({ dir: prompt.dir, tone: 'warn' }, { dir: prompt.best, tone: 'best' });
    else if (showAnalysis && bestDir !== null) {
      if (playedHere !== null && playedHere !== bestDir) {
        const f = line.facts[k];
        const c = a ? costOf(a, DIR_NAMES[playedHere]) : null;
        const bad = c ? costClass(c) : f ? shareClass(f.loss, f.you ? 'chance' : 'engine', f.p) : null;
        arrows.push({ dir: playedHere, tone: bad ? 'warn' : 'played', label: line.author(k) === 'c' ? 'coach' : 'played' });
      }
      arrows.push({
        dir: bestDir,
        tone: playedHere === bestDir ? 'same' : 'best',
        label: playedHere === bestDir ? 'best ✓' : 'best',
        onClick: autoOn ? undefined : () => commit(bestDir, 'c'),
        title: `Play ${bestName} (Space)`,
      });
    } else if (mode === 'coach' && hint === 'open' && bestDir !== null) arrows.push({ dir: bestDir, tone: 'best', onClick: () => commit(bestDir, 'c'), title: `Play ${bestName}` });
  }
  const plan = showAnalysis && !fastAuto ? (edit ? editA?.plan_info : shownNow?.plan_info) : edit ? editA?.plan_info : undefined;

  const evalNote = notJudged ? 'Block formation: not judged by the engine' : ea && !ea.odds && !ea.game_over ? 'No odds at this stage' : null;
  const evalBar = (vertical: boolean) =>
    (mode !== 'play' || edit) && (
      <EvalBar
        vertical={vertical}
        p={evalP}
        tile={ms?.tile ?? null}
        you={ms?.you ?? false}
        engine={engineP}
        lastCost={lastCost}
        level={me.skill === null ? 'level not measured yet' : skillLabel(ea?.chance?.skill ?? me.skill)}
        health={ea ? healthOf(ea) : 'unknown'}
        pending={!ea && (edit ? editOk : !over)}
        offline={wb.offline}
        note={evalNote}
      />
    );

  // ---- the last move, in one line under the board ----
  const lastMove = () => {
    if (edit) return <span class="muted">Editing the position: pick a tile below and tap cells.</span>;
    if (k === 0) return <span class="muted">{n > 0 ? 'Start of the line.' : 'Make a move, or let the coach play (P).'}</span>;
    const d = line.moveAt(k - 1) as Dir;
    const f = line.facts[k - 1];
    const who = line.author(k - 1);
    const head = (
      <>
        <span class="lm-n">Move {k}</span>
        <span class="lm-dir" aria-hidden="true">
          {arrowOf(d)}
        </span>
        <span class="lm-name">{cap(DIR_NAMES[d])}</span>
        {who === 'c' && <span class="tag played">coach</span>}
      </>
    );
    if (mode === 'play' && !revealed) return head;
    if (who === 'c' || !f || f.loss === undefined) return head;
    if (f.loss === null) return (
      <>
        {head}
        <span class="tag neutral">not judged</span>
      </>
    );
    // the analysis of the position the move was played from says exactly what it cost (the fact keeps only a share)
    const c = prevCost;
    const better = prevA ? coachOf(prevA) : f.best !== -1 ? DIR_NAMES[f.best] : null;
    const isBest = better === DIR_NAMES[d] || (c ? c.rel < 0.001 : f.loss < 0.001);
    const cls = isBest ? null : c ? costClass(c) : shareClass(f.loss, f.you ? 'chance' : 'engine', f.p);
    const detail = costDetail(c);
    // in the opening a corner-leaving move costs nothing measurable yet: name the habit instead of grading it
    const habit = !cls && !isBest && !!better && cornerHabit(line.boards[k - 1], d, dirFromName(better));
    if (habit)
      return (
        <>
          {head}
          <span class="tag neutral" title={`Your biggest tile left its corner. This early it costs almost nothing; from 256 on it does.${detail ? ` ${detail}.` : ''}`}>
            Left the corner
          </span>
          <span class="lm-best">
            {arrowOf(better)} {cap(better!)} keeps it · costs from 256 on
          </span>
        </>
      );
    if (!cls)
      return (
        <>
          {head}
          <span class="tag good" title={detail ?? undefined}>
            {isBest ? 'Best' : 'Good'}
          </span>
        </>
      );
    return (
      <>
        {head}
        <span class={`tag ${cls}`} title={detail ?? undefined}>
          {CLASS_WORDS[cls]} {costTag(c, f.loss)}
        </span>
        {better && better !== DIR_NAMES[d] && (
          <span class="lm-best">
            {arrowOf(better)} {cap(better)} was better
          </span>
        )}
        {k === n && (
          <button type="button" class="linklike lm-undo" onClick={(e) => (back(), blurAfterPointer(e))}>
            Undo
          </button>
        )}
      </>
    );
  };

  // ---- the move played from this position in the line ----
  const playedCard = () => {
    if (playedHere === null || edit) return null;
    const name = DIR_NAMES[playedHere];
    const who = line.author(k);
    const f = line.facts[k];
    const pm = shownNow?.moves.find((m) => m.move === name);
    const bestHere = shownNow ? bestOf(shownNow) : f && f.best !== -1 ? DIR_NAMES[f.best] : null;
    const judged = shownNow ? shownNow.judged !== false : f?.loss !== null;
    const c = shownNow ? costOf(shownNow, name) : null;
    const cls =
      judged && bestHere && name !== bestHere ? (c ? costClass(c) : shareClass(typeof f?.loss === 'number' ? f.loss : null, f?.you ? 'chance' : 'engine', f?.p)) : null;
    const detail = costDetail(c);
    const spoil = mode === 'analyze' || revealed;
    return (
      <div class="played card">
        <div class="played-head">
          <span class={`move-dir ${cls ?? (bestHere === name ? 'best' : '')}`} aria-hidden="true">
            {arrowOf(name)}
          </span>
          <div>
            <span class="verdict-label">Next in the line · move {k + 1}</span>
            <strong>
              {who === 'c' ? 'The coach' : 'You'} played {cap(name)}
            </strong>
          </div>
          {mode === 'play' && !revealed ? null : !judged ? (
            <span class="tag neutral">Not judged</span>
          ) : bestHere === name ? (
            <span class="tag best">Best move</span>
          ) : cls ? (
            <span class={`tag ${cls}`}>
              {CLASS_WORDS[cls]} {costTag(c, f?.loss)}
            </span>
          ) : bestHere ? (
            <span class="tag good">Good</span>
          ) : null}
        </div>
        {cls && spoil && bestHere && (
          <p>
            {detail ? `${detail}. ` : ''}Better:{' '}
            <strong>
              {arrowOf(bestHere)} {cap(bestHere)}
            </strong>
            {pm?.reasons[0] ? `. ${because(pm.reasons[0])}` : '.'}
          </p>
        )}
        {cls && !spoil && (
          <p>
            A better move was there. Find it, or{' '}
            <button type="button" class="linklike" onClick={toggleReveal}>
              show the analysis
            </button>
            .
          </p>
        )}
        <p class="muted small">Play a different move to try another line from here, or step forward (X).</p>
      </div>
    );
  };

  // ---- the analysis tab ----
  const analysisTab = () => {
    if (edit)
      return (
        <div class="tab-body">
          <div class="pos-head">
            <h2>Your position {editState.loading && <Spinner label="Analyzing" />}</h2>
            <label class="toggle small-toggle" title="Search deeper (slower)">
              <input type="checkbox" checked={deep} onChange={(e) => setDeep((e.target as HTMLInputElement).checked)} />
              <span>Deeper</span>
            </label>
          </div>
          {!editOk ? (
            <p class="card notice">{edit.board.some((v) => v > 0) ? 'This board has more than 15 different tiles.' : 'Place at least one tile to analyze the position.'}</p>
          ) : editState.error ? (
            <p class="card notice">{editState.error}</p>
          ) : editA ? (
            <AnalysisView a={editA} board={edit.board} stale={editState.loading} skill={me.skill} />
          ) : lastShown.current ? (
            <AnalysisView a={lastShown.current.a} board={lastShown.current.board} stale skill={me.skill} />
          ) : (
            <div class="card notice">
              <Spinner /> Analyzing…
            </div>
          )}
        </div>
      );
    const head = (
      <div class="pos-head">
        <h2>{k === 0 ? (line.rec.origin === 'position' ? 'Set-up position' : 'Start of the game') : `After move ${k}`}</h2>
        {showAnalysis && !over && (
          <label class="toggle small-toggle" title="Search deeper (slower)">
            <input type="checkbox" checked={deep} onChange={(e) => setDeep((e.target as HTMLInputElement).checked)} />
            <span>Deeper</span>
          </label>
        )}
      </div>
    );
    const intro = !st.seenIntro && n === 0 && line.rec.origin === 'new' && (
      <div class="intro card">
        <p>
          <strong>Welcome!</strong> {wide ? 'Use the arrow keys' : 'Swipe on the board'} to play. The coach analyzes every position as you go: take back any move
          (Z), let the coach play on (P), or set up your own position (E). No sign-up needed.
        </p>
      </div>
    );
    let body;
    if (fastAuto) {
      body = (
        <div class="coach-card card auto-card">
          <p>
            <strong>The coach is playing</strong> at {SPEEDS[wb.auto.speed].label === 'Max' ? 'full speed' : SPEEDS[wb.auto.speed].label}
            {wb.auto.until === 'tile' ? ` until the ${int(2 ** wb.auto.targetRank)} tile` : wb.auto.until === 'moves' ? ` for ${UNTIL_MOVES} moves` : ''}. The
            analysis comes back when it stops.
          </p>
          <button type="button" class="btn small primary" onClick={(e) => (wb.stopAuto(), blurAfterPointer(e))}>
            Stop <kbd class="on-accent">P</kbd>
          </button>
        </div>
      );
    } else if (showAnalysis) {
      body = shown ? (
        <AnalysisView
          a={shown}
          board={shownNow ? board : (lastShown.current?.board ?? board)}
          stale={stale}
          played={playedHere !== null ? DIR_NAMES[playedHere] : null}
          onPlayBest={!autoOn && !stale && !over ? () => void playBest() : undefined}
          skill={me.skill}
        />
      ) : wb.offline ? (
        <p class="card notice">The analysis server cannot be reached. You can keep playing; the analysis comes back with the server.</p>
      ) : (
        <div class="card notice">
          <Spinner /> Analyzing…
        </div>
      );
    } else if (mode === 'coach') {
      body = (
        <div class="coach-card card">
          {hint === 'offered' ? (
            <button type="button" class="hint-chip" onClick={() => (setHint({ pos: posKey, state: 'open' }), line.rec.coach.hintsOpened++)}>
              <span aria-hidden="true">?</span> Tricky position · want a hint?
            </button>
          ) : hint === 'open' && bestName ? (
            <p>
              <span class="pill best">
                {arrowOf(bestName)} {cap(bestName)}
              </span>{' '}
              {a?.moves.find((m) => m.move === bestName)?.reasons[0] ? `${a.moves.find((m) => m.move === bestName)!.reasons[0].text}.` : 'is the move to play here.'}
            </p>
          ) : (
            <p>The coach stops you before a costly move, offers hints in tricky opening positions and grades each move after you make it.</p>
          )}
          <button type="button" class="btn small" onClick={(e) => (toggleReveal(), blurAfterPointer(e))}>
            Show the analysis <kbd>H</kbd>
          </button>
        </div>
      );
    } else {
      body = (
        <div class="coach-card card">
          <p>The analysis is off: just the game. Undo, the timeline and the coach's autoplay still work.</p>
          <button type="button" class="btn small" onClick={(e) => (toggleReveal(), blurAfterPointer(e))}>
            Show the analysis <kbd>H</kbd>
          </button>
        </div>
      );
    }
    return (
      <div class="tab-body">
        {intro}
        {head}
        {playedCard()}
        {body}
        {revealed && mode !== 'analyze' && (
          <button type="button" class="linklike hide-analysis" onClick={toggleReveal}>
            Hide the analysis
          </button>
        )}
      </div>
    );
  };

  const reviewValid = wb.reviewValidPlies();
  const reviewBadge = wb.review.running ? 'running' : wb.review.result && wb.review.result.lineId === line.id ? (wb.reviewCurrent() ? 'done' : 'stale') : null;
  const nextT = nextTile(line.tops[k]);

  // ---- layout ----
  const scores = (
    <div class="scores">
      <div class="score-box">
        <span class="score-label">Score</span>
        <span class="score-value">{int(line.score())}</span>
      </div>
      <div class="score-box">
        <span class="score-label">Best</span>
        <span class="score-value">{int(Math.max(bestRef.current, line.score()))}</span>
      </div>
      {wide && (
        <button type="button" class={`btn small icon-text ${edit ? 'on' : ''}`} onClick={(e) => (edit ? setEdit(null) : startEdit(), blurAfterPointer(e))} title="Set up a position (E)">
          <Icon d={ICONS.edit} size={18} /> {edit ? 'Editing' : 'Edit'}
        </button>
      )}
      <button type="button" class="btn small new-game" onClick={(e) => (newGame(), blurAfterPointer(e))}>
        New game
      </button>
      <Menu
        label="More"
        button={<Icon d={ICONS.dots} />}
        items={[
          { label: edit ? 'Stop editing' : 'Set up a position', hint: 'E', onSelect: () => (edit ? setEdit(null) : startEdit()) },
          { label: 'Review the game', hint: 'R', onSelect: () => openReview(), disabled: n === 0 },
          { label: 'Copy the position', onSelect: () => void copyText(boardText(edit ? edit.board : board), 'Position copied') },
          { label: 'Copy a link to this position', onSelect: () => void copyText(`${location.origin}/?board=${boardCode(edit ? edit.board : board)}`, 'Link copied') },
          { label: 'Keyboard shortcuts', hint: '?', onSelect: () => setHelp(true) },
        ]}
      />
    </div>
  );

  const transport = (
    <div class="transport">
      <div class="tp-nav" role="group" aria-label="Move through the line">
        <button type="button" class="btn small icon" onClick={(e) => (seek(0), blurAfterPointer(e))} disabled={k === 0 || !!edit} title="Start of the line (Home)" aria-label="Start of the line">
          <Icon d={ICONS.start} />
        </button>
        <button type="button" class="btn small icon" onClick={(e) => (back(), blurAfterPointer(e))} disabled={k === 0 || !!edit} title="Back one move (Z)" aria-label="Back one move">
          <Icon d={ICONS.back} />
        </button>
        <span class="tp-pos" aria-live="polite">
          {k === 0 ? 'Start' : `Move ${int(k)}`}
          {n > 0 && <small> / {int(n)}</small>}
        </span>
        <button type="button" class="btn small icon" onClick={(e) => (forward(), blurAfterPointer(e))} disabled={k === n || !!edit} title="Forward one move (X)" aria-label="Forward one move">
          <Icon d={ICONS.forward} />
        </button>
        <button type="button" class="btn small icon" onClick={(e) => (seek(n), blurAfterPointer(e))} disabled={k === n || !!edit} title="End of the line (End)" aria-label="End of the line">
          <Icon d={ICONS.end} />
        </button>
      </div>
      <button
        type="button"
        class="btn small primary tp-best"
        onClick={(e) => (void playBest(), blurAfterPointer(e))}
        disabled={over || !!edit || autoOn}
        title="Play the coach's move (Space)"
      >
        {showAnalysis && bestName ? (
          <>
            Play {arrowOf(bestName)} {cap(bestName)}
          </>
        ) : (
          'Coach move'
        )}
        {wide && <kbd class="on-accent">Space</kbd>}
      </button>
    </div>
  );

  const autoplay = (
    <div class={`autoplay ${autoOn ? 'running' : ''}`}>
      <button
        type="button"
        class={`btn small ${autoOn ? 'primary' : ''} auto-toggle`}
        aria-pressed={autoOn}
        onClick={(e) => (toggleAuto(), blurAfterPointer(e))}
        disabled={!!edit || (over && !autoOn)}
        title="The coach plays its moves (P)"
      >
        <Icon d={autoOn ? ICONS.pause : ICONS.play} size={18} />
        {autoOn ? 'Stop' : 'Coach plays'}
        {wide && <kbd class={autoOn ? 'on-accent' : ''}>P</kbd>}
      </button>
      <div class="segmented speeds" role="radiogroup" aria-label="Autoplay speed">
        {SPEEDS.map((s, i) => (
          <button
            type="button"
            role="radio"
            aria-checked={wb.auto.speed === i}
            class={wb.auto.speed === i ? 'on' : ''}
            key={s.label}
            title={`${s.title} (${i + 1})`}
            onClick={(e) => (setSpeed(i as Speed), blurAfterPointer(e))}
          >
            {s.label}
          </button>
        ))}
      </div>
      <select
        class="until"
        aria-label="When the coach stops"
        value={wb.auto.until}
        onPointerDown={() => (pickedByPointer.current = Date.now())}
        onChange={(e) => {
          setUntil((e.target as HTMLSelectElement).value as Until);
          // chosen with a pointer: the arrow keys play moves again (with the keyboard, the select keeps them)
          if (Date.now() - pickedByPointer.current < 30000) (e.currentTarget as HTMLElement).blur();
        }}
      >
        <option value="stop">until you stop it</option>
        <option value="tile">until the {autoOn ? int(2 ** wb.auto.targetRank) : int(nextT)} tile</option>
        <option value="moves">for {UNTIL_MOVES} moves</option>
      </select>
    </div>
  );

  const restoreToast = rep && (
    <div class="toast with-action" role="status">
      <span>
        {rep.what === 'branch'
          ? `New line: ${int(rep.dropped)} moves of the old one were replaced.`
          : rep.what === 'edit'
            ? 'New position on the board.'
            : 'New game on the board.'}
      </span>
      <button type="button" class="toast-action" onClick={() => wb.restore()}>
        {rep.what === 'branch' ? 'Restore them' : 'Restore the old line'}
      </button>
      <button type="button" class="toast-close" aria-label="Dismiss" onClick={() => wb.dismissReplaced()}>
        ✕
      </button>
    </div>
  );

  return (
    <div class={`dojo mode-${mode} ${edit ? 'editing' : ''}`}>
      <section class="bench" aria-label="Board">
        {scores}
        {!wide && evalBar(false)}
        <div class="board-row" ref={swipeRef}>
          {wide && evalBar(true)}
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
              chain={plan?.chain}
              nextCell={plan?.next_cell}
              label="Board editor"
              class="main-board editing"
            />
          ) : (
            <Board
              tiles={anim.current.tiles}
              arrows={arrows}
              shakeKey={shake}
              chain={plan?.chain}
              nextCell={plan?.next_cell}
              label={`Game board, ${k === 0 ? 'start' : `after move ${k}`}. Score ${line.score()}.`}
              class="main-board"
            >
              {over && (
                <div class="board-over" data-no-swipe>
                  <div class="over-card">
                    <h2>Game over</h2>
                    <p>
                      {int(line.score())} points · best tile {tileValue(line.tops[k])} · {int(k)} move{k === 1 ? '' : 's'}
                    </p>
                    <div class="over-actions">
                      <button type="button" class="btn primary" onClick={(e) => (back(), blurAfterPointer(e))}>
                        Undo <kbd class="on-accent">Z</kbd>
                      </button>
                      <button type="button" class="btn" onClick={() => openReview()}>
                        Review
                      </button>
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
        {edit && (
          <>
            <div class="edit-bar">
              <button type="button" class="btn primary" disabled={!editOk || !canMove(edit.board)} onClick={finishEdit}>
                Play from here
              </button>
              <button type="button" class="btn" onClick={() => setEdit(null)}>
                Cancel
              </button>
              {wide && <span class="muted small">Enter · Esc</span>}
            </div>
            <Editor board={edit.board} onBoard={(b) => setEdit({ ...edit, board: b })} pen={edit.pen} onPen={(r) => setEdit({ ...edit, pen: r })} />
          </>
        )}
        {!edit && (
          <>
            <div class="last-move" aria-live="polite">
              {lastMove()}
            </div>
            {transport}
            <Timeline line={line} version={line.version} cursor={k} onSeek={seek} />
            {autoplay}
          </>
        )}
      </section>

      <aside class="panel" ref={panelRef} aria-label="Analysis and review">
        <div class="panel-top">
          <ModeSwitch value={mode} onChange={(m) => (updateSettings({ mode: m }), setReveal(null))} />
          <p class="mode-desc">{modeDescription(mode)}</p>
        </div>
        <div class="tabs" role="tablist" aria-label="Panel">
          <button type="button" role="tab" id="tab-analysis" aria-controls="tabpanel" aria-selected={tab === 'analysis'} class={tab === 'analysis' ? 'on' : ''} onClick={(e) => (setTab('analysis'), blurAfterPointer(e))}>
            {edit ? 'Position' : 'Analysis'}
          </button>
          <button type="button" role="tab" id="tab-review" aria-controls="tabpanel" aria-selected={tab === 'review'} class={tab === 'review' ? 'on' : ''} onClick={(e) => (openReview(false), blurAfterPointer(e))} disabled={!!edit}>
            Review
            {reviewBadge === 'running' && <Spinner label="Reviewing" />}
            {reviewBadge === 'stale' && <span class="dot" title="The line changed since the review" />}
          </button>
        </div>
        <div id="tabpanel" role="tabpanel" aria-labelledby={tab === 'analysis' ? 'tab-analysis' : 'tab-review'}>
          {tab === 'analysis' || edit ? (
            analysisTab()
          ) : (
            <ReviewView line={line} version={line.version} review={wb.review} valid={reviewValid} current={wb.reviewCurrent()} onRun={() => void wb.runReview()} onJump={jumpTo} />
          )}
        </div>
        <p class="panel-foot">
          <Link href="/how">How the coach works</Link> · <button type="button" class="linklike" onClick={() => setHelp(true)}>Keyboard shortcuts</button>
        </p>
      </aside>

      {prompt && (
        <WarnSheet
          cost={costOf(wb.peek() ?? { moves: [prompt.move] }, prompt.move.move)}
          move={prompt.move}
          best={DIR_NAMES[prompt.best]}
          bestReason={prompt.bestReason}
          nextTile={prompt.nextTile}
          onTake={takeSuggestion}
          onAnyway={playAnyway}
          onCancel={() => setPrompt(null)}
        />
      )}
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

/** A cost as a tag's number: points of your chance, or the engine's real loss. */
function costTag(c: HumanCost | null, share: number | null | undefined): string {
  if (c && c.kind === 'chance' && c.abs !== null) return points(-c.abs);
  const rel = c ? c.rel : share;
  return typeof rel === 'number' ? `−${pctShort(rel)}` : '';
}

/** "your chance of 2048: 62% → 55%" for a cost by your chance. */
function costDetail(c: HumanCost | null): string | null {
  if (!c || c.kind !== 'chance' || c.best === null || c.after === null) return null;
  return `Your chance of ${c.target}: ${chance(c.best)} → ${chance(c.after)}`;
}

const SHORTCUTS: [string, string][] = [
  ['← ↑ → ↓ or W A S D', 'move (swipe on a phone)'],
  ['Space or Enter', "play the coach's move"],
  ['Z or Backspace', 'back one move (Shift+Z: ten)'],
  ['X', 'forward one move (Shift+X: ten)'],
  ['Home / End', 'start / end of the line'],
  ['P', 'the coach plays on / stops'],
  ['1 2 3 4', 'autoplay speed'],
  ['H', 'show the analysis (Play and Coach modes)'],
  ['E', 'set up a position'],
  ['R', 'review the game'],
  ['Esc', 'stop the coach, leave the editor'],
];

function Shortcuts({ onClose }: { onClose: () => void }) {
  return (
    <Modal onClose={onClose} labelledBy="keys-title" class="shortcuts">
      <h2 id="keys-title">Keyboard shortcuts</h2>
      <dl class="keys">
        {SHORTCUTS.map(([k, v]) => (
          <div key={k}>
            <dt>
              <kbd>{k}</kbd>
            </dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p class="muted small">Going back and playing a different move starts a new line from there; the old continuation can be restored right after.</p>
      <div class="actions">
        <button type="button" class="btn primary" onClick={onClose} data-autofocus>
          Got it
        </button>
      </div>
    </Modal>
  );
}
