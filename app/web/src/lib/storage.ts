// Everything the app remembers lives in this browser's localStorage: settings and the line on the board (compactly:
// start board + moves + new tiles + who moved, ~3 characters per move). No accounts.

const PREFIX = 'tc.';

export function readJson<T>(key: string, fallback: T): T {
  try {
    const s = localStorage.getItem(PREFIX + key);
    return s ? (JSON.parse(s) as T) : fallback;
  } catch {
    return fallback;
  }
}

/** Writes a value; on a full storage it calls `makeRoom` once (e.g. drop old games) and retries. */
export function writeJson(key: string, value: unknown, makeRoom?: () => boolean): boolean {
  const s = JSON.stringify(value);
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      localStorage.setItem(PREFIX + key, s);
      return true;
    } catch {
      if (!makeRoom || !makeRoom()) return false;
    }
  }
  return false;
}

export function remove(key: string): void {
  try {
    localStorage.removeItem(PREFIX + key);
  } catch {
    /* ignore */
  }
}

// ---- a tiny observable store for app-wide state ----
export function createStore<T>(initial: T) {
  let value = initial;
  const subs = new Set<(v: T) => void>();
  return {
    get: () => value,
    set(next: T) {
      value = next;
      subs.forEach((f) => f(value));
    },
    subscribe(f: (v: T) => void) {
      subs.add(f);
      return () => subs.delete(f);
    },
  };
}

export interface Settings {
  /** the coach at all: grades, the best-move arrow, the move list, highlights and warnings (off: just the game) */
  coach: boolean;
  /** with the coach off, still grade each move under the board (play yourself, open the coach when curious) */
  grades: boolean;
  /** the coach's move before you move: the arrow on the board and the move list */
  hints: boolean;
  /** stop before a blunder */
  warn: boolean;
  /** mark the cells where the action is */
  highlights: boolean;
  /** say why for each move (and the plan) */
  explain: boolean;
  /** the engine's odds of the next tiles, in the move list */
  odds: boolean;
  /** autoplay speed (index into SPEEDS) */
  speed: 0 | 1 | 2 | 3;
}

// v2 stored a mode (play / coach / analyze), v1 a coach setting (off / warn / best)
const saved = readJson<Partial<Settings> & { mode?: string; coach?: unknown }>('settings', {});
const legacyMode = typeof saved.coach === 'string' ? (saved.coach === 'off' ? 'play' : 'analyze') : saved.mode;
export const settings = createStore<Settings>({
  coach: typeof saved.coach === 'boolean' ? saved.coach : legacyMode !== 'play',
  grades: saved.grades ?? false,
  hints: saved.hints ?? legacyMode !== 'coach',
  warn: saved.warn ?? legacyMode === 'coach',
  highlights: saved.highlights ?? false,
  explain: saved.explain ?? false,
  odds: saved.odds ?? false,
  speed: saved.speed ?? 2,
});
settings.subscribe((s) => writeJson('settings', s));

export function updateSettings(patch: Partial<Settings>): void {
  settings.set({ ...settings.get(), ...patch });
}
