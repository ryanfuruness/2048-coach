import { useEffect, useState } from 'preact/hooks';

export function useStore<T>(store: { get: () => T; subscribe: (f: (v: T) => void) => () => void }): T {
  const [v, setV] = useState(store.get());
  useEffect(() => {
    setV(store.get());
    const off = store.subscribe(setV);
    return () => {
      off();
    };
  }, [store]);
  return v;
}

export function useMedia(query: string): boolean {
  const [m, setM] = useState(() => matchMedia(query).matches);
  useEffect(() => {
    const mq = matchMedia(query);
    const f = () => setM(mq.matches);
    mq.addEventListener('change', f);
    f();
    return () => mq.removeEventListener('change', f);
  }, [query]);
  return m;
}

export function useTitle(title: string): void {
  useEffect(() => {
    document.title = title;
  }, [title]);
}
