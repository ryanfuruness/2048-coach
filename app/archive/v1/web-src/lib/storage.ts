// Everything the app remembers lives in this browser's localStorage: settings, the player's estimated skill and the
// history of games (each game compactly: start board + moves + spawns, ~2 characters per move). No accounts.

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

export type CoachMode = 'off' | 'warn' | 'best';

export interface Settings {
  coach: CoachMode;
  seenIntro: boolean;
}

export const settings = createStore<Settings>({ coach: 'warn', seenIntro: false, ...readJson<Partial<Settings>>('settings', {}) });
settings.subscribe((s) => writeJson('settings', s));
