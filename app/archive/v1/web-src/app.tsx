import type { ComponentType } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { Link } from './components/ui.tsx';
import { type Route, useRoute } from './lib/router.ts';
import { Play } from './screens/Play.tsx';

type Lazy = ComponentType<{ route: Route }>;
const loaders: Record<string, () => Promise<Lazy>> = {
  review: () => import('./screens/Review.tsx').then((m) => m.Review as Lazy),
  analyze: () => import('./screens/Analyze.tsx').then((m) => m.Analyze as Lazy),
  history: () => import('./screens/History.tsx').then((m) => m.History as Lazy),
  how: () => import('./screens/How.tsx').then((m) => m.How as Lazy),
};
const loaded: Record<string, Lazy> = {};

function LazyScreen({ route }: { route: Route }) {
  const [, force] = useState(0);
  const C = loaded[route.name];
  useEffect(() => {
    if (C) return;
    let live = true;
    loaders[route.name]().then((m) => {
      loaded[route.name] = m;
      if (live) force((x) => x + 1);
    });
    return () => {
      live = false;
    };
  }, [route.name]);
  return C ? <C route={route} /> : <div class="screen-loading" aria-busy="true" />;
}

const NAV = [
  { name: 'play', href: '/', label: 'Play', icon: 'M5 5h6v6H5zM13 5h6v6h-6zM5 13h6v6H5zM13 13h6v6h-6z' },
  { name: 'analyze', href: '/analyze', label: 'Analyze', icon: 'M10.5 4a6.5 6.5 0 015.2 10.4l4.4 4.4-1.4 1.4-4.4-4.4A6.5 6.5 0 1110.5 4zm0 2a4.5 4.5 0 100 9 4.5 4.5 0 000-9z' },
  { name: 'history', href: '/history', label: 'History', icon: 'M12 4a8 8 0 11-7.4 5H7a6 6 0 101.8-2.2L11 9H4V2l2.3 2.3A8 8 0 0112 4zm-1 4h2v4.6l3 1.8-1 1.7-4-2.4z' },
  { name: 'how', href: '/how', label: 'How it works', short: 'Learn', icon: 'M12 3a9 9 0 110 18 9 9 0 010-18zm0 2a7 7 0 100 14 7 7 0 000-14zm-1 9h2v2h-2zm1-7a3.2 3.2 0 012.2 5.5c-.7.6-1.2 1-1.2 1.5h-2c0-1.3.9-2 1.6-2.6.5-.4.6-.7.6-1.2a1.2 1.2 0 00-2.4 0H9A3 3 0 0112 7z' },
];

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d={d} fill="currentColor" />
    </svg>
  );
}

export function App() {
  const route = useRoute();
  const active = route.name === 'review' ? 'history' : route.name;
  // preload the other screens once the game is on screen, so navigation is instant
  useEffect(() => {
    const t = setTimeout(() => Object.values(loaders).forEach((l) => l().catch(() => {})), 1500);
    return () => clearTimeout(t);
  }, []);
  return (
    <div class={`shell route-${route.name}`}>
      <a class="skip" href="#main">
        Skip to content
      </a>
      <header class="topbar">
        <Link href="/" class="brand" title="2048 Coach">
          <span class="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span class="brand-name">
            2048 <b>Coach</b>
          </span>
        </Link>
        <nav class="topnav" aria-label="Main">
          {NAV.map((n) => (
            <Link href={n.href} class={active === n.name ? 'on' : ''} aria-current={active === n.name ? 'page' : undefined} key={n.name}>
              {n.label}
            </Link>
          ))}
        </nav>
      </header>
      <main id="main" class="main">
        {route.name === 'play' ? <Play /> : <LazyScreen route={route} />}
      </main>
      <nav class="tabbar" aria-label="Main">
        {NAV.map((n) => (
          <Link href={n.href} class={active === n.name ? 'on' : ''} aria-current={active === n.name ? 'page' : undefined} key={n.name}>
            <Icon d={n.icon} />
            <span>{n.short ?? n.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
