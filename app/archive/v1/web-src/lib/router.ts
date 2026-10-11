// A tiny path router: /, /review/:id, /analyze, /history, /how.
import { useEffect, useState } from 'preact/hooks';

export type Route =
  | { name: 'play' }
  | { name: 'review'; id: string; ply?: number }
  | { name: 'analyze' }
  | { name: 'history' }
  | { name: 'how' };

export function parseRoute(path: string): Route {
  const p = path.replace(/\/+$/, '') || '/';
  const m = /^\/review\/([A-Za-z0-9_-]{1,40})$/.exec(p);
  if (m) return { name: 'review', id: m[1] };
  if (p === '/analyze') return { name: 'analyze' };
  if (p === '/history') return { name: 'history' };
  if (p === '/how') return { name: 'how' };
  return { name: 'play' };
}

const listeners = new Set<() => void>();

export function navigate(to: string, opts: { replace?: boolean } = {}): void {
  const url = new URL(to, location.href);
  if (url.pathname + url.search === location.pathname + location.search) return;
  if (opts.replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
  listeners.forEach((f) => f());
  window.scrollTo(0, 0);
}

export function useRoute(): Route {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const f = () => setPath(location.pathname);
    listeners.add(f);
    window.addEventListener('popstate', f);
    return () => {
      listeners.delete(f);
      window.removeEventListener('popstate', f);
    };
  }, []);
  return parseRoute(path);
}

/** Click handler for in-app links: keeps modifier-clicks (new tab) working. */
export function linkClick(e: MouseEvent): void {
  const a = (e.currentTarget as HTMLAnchorElement | null) ?? null;
  if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  navigate(a.getAttribute('href') ?? '/');
}
