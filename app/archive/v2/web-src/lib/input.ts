// Input: arrow keys / WASD and swipes (pointer events, so touch, pen and mouse drags all work).
import { useEffect, useRef } from 'preact/hooks';
import type { Dir } from '@shared/rules.ts';

const KEYS: Record<string, Dir> = {
  ArrowUp: 0,
  ArrowRight: 1,
  ArrowDown: 2,
  ArrowLeft: 3,
  w: 0,
  d: 1,
  s: 2,
  a: 3,
  W: 0,
  D: 1,
  S: 2,
  A: 3,
};

export function keyDir(e: KeyboardEvent): Dir | null {
  if (e.metaKey || e.ctrlKey || e.altKey) return null;
  const d = KEYS[e.key];
  return d === undefined ? null : d;
}

function typingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el || !el.tagName) return false;
  return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
}

/**
 * Calls `onDir` for direction keys pressed anywhere on the page (not while typing in a field). The key's default action
 * (scrolling) is prevented unless `onDir` returns false.
 */
export function useDirectionKeys(onDir: (d: Dir, e: KeyboardEvent) => boolean | void, enabled = true): void {
  const cb = useRef(onDir);
  cb.current = onDir;
  useEffect(() => {
    if (!enabled) return;
    const f = (e: KeyboardEvent) => {
      if (typingTarget(e.target)) return;
      const d = keyDir(e);
      if (d === null) return;
      if (cb.current(d, e) !== false) e.preventDefault();
    };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, [enabled]);
}

/** Swipes on an element: a drag of 24+ px fires once, in its dominant direction. */
export function useSwipe(ref: { current: HTMLElement | null }, onDir: (d: Dir) => void): void {
  const cb = useRef(onDir);
  cb.current = onDir;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let start: { x: number; y: number; id: number } | null = null;
    let fired = false;
    const down = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      if ((e.target as HTMLElement).closest('button, a, input, [data-no-swipe]')) return;
      start = { x: e.clientX, y: e.clientY, id: e.pointerId };
      fired = false;
    };
    const moveH = (e: PointerEvent) => {
      if (!start || fired || e.pointerId !== start.id) return;
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
      fired = true;
      cb.current(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 1 : 3) : dy > 0 ? 2 : 0);
    };
    const up = () => {
      start = null;
    };
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointermove', moveH);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('pointermove', moveH);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
    };
  }, [ref]);
}
