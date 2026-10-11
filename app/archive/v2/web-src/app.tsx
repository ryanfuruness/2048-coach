import type { ComponentType } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { Link } from './components/ui.tsx';
import { type Route, useRoute } from './lib/router.ts';
import { Dojo } from './screens/Dojo.tsx';

type Lazy = ComponentType<{ route: Route }>;
const loaders: Record<string, () => Promise<Lazy>> = {
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

export function App() {
  const route = useRoute();
  // preload the explainer once the board is on screen, so the link opens at once
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
          <Link href="/" class={route.name === 'play' ? 'on' : ''} aria-current={route.name === 'play' ? 'page' : undefined}>
            Board
          </Link>
          <Link href="/how" class={route.name === 'how' ? 'on' : ''} aria-current={route.name === 'how' ? 'page' : undefined}>
            How it works
          </Link>
        </nav>
      </header>
      <main id="main" class="main">
        {route.name === 'play' ? <Dojo /> : <LazyScreen route={route} />}
      </main>
    </div>
  );
}
