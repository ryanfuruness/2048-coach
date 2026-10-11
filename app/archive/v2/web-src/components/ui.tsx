import type { ComponentChildren } from 'preact';
import { useEffect, useRef } from 'preact/hooks';
import type { Mode } from '../lib/storage.ts';
import { linkClick } from '../lib/router.ts';

export function Link(p: { href: string; class?: string; children: ComponentChildren; 'aria-current'?: 'page' | undefined; title?: string }) {
  return (
    <a href={p.href} class={p.class} onClick={linkClick} aria-current={p['aria-current']} title={p.title}>
      {p.children}
    </a>
  );
}

const MODES: { id: Mode; label: string; desc: string }[] = [
  { id: 'play', label: 'Play', desc: 'Just the game: no analysis, no warnings' },
  { id: 'coach', label: 'Coach', desc: 'Warns you before costly moves; the analysis stays hidden until you ask' },
  { id: 'analyze', label: 'Analyze', desc: 'Live analysis of every position: best move, every move ranked, the plan' },
];

/** After a pointer click, gives the keys back to the board (arrows play, Space plays the coach's move) without a focus ring. */
export function blurAfterPointer(e: MouseEvent): void {
  if (e.detail > 0) (e.currentTarget as HTMLElement | null)?.blur();
}

export function ModeSwitch(p: { value: Mode; onChange: (m: Mode) => void }) {
  return (
    <div class="segmented modes" role="radiogroup" aria-label="What the coach shows">
      {MODES.map((m) => (
        <button
          type="button"
          role="radio"
          aria-checked={p.value === m.id}
          class={p.value === m.id ? 'on' : ''}
          onClick={(e) => {
            p.onChange(m.id);
            blurAfterPointer(e);
          }}
          title={m.desc}
          key={m.id}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

export const modeDescription = (m: Mode) => MODES.find((x) => x.id === m)!.desc;

/** A modal dialog: focus moves in, Escape closes, the backdrop click closes. */
export function Modal(p: {
  onClose: () => void;
  labelledBy: string;
  describedBy?: string;
  role?: 'dialog' | 'alertdialog';
  class?: string;
  children: ComponentChildren;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const el = ref.current;
    const first = el?.querySelector<HTMLElement>('[data-autofocus]') ?? el?.querySelector<HTMLElement>('button');
    first?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        p.onClose();
      } else if (e.key === 'Tab' && el) {
        const items = [...el.querySelectorAll<HTMLElement>('button, a[href], input, [tabindex]:not([tabindex="-1"])')];
        if (!items.length) return;
        const i = items.indexOf(document.activeElement as HTMLElement);
        if (e.shiftKey && i <= 0) {
          e.preventDefault();
          items[items.length - 1].focus();
        } else if (!e.shiftKey && i === items.length - 1) {
          e.preventDefault();
          items[0].focus();
        }
      }
    };
    window.addEventListener('keydown', key);
    return () => {
      window.removeEventListener('keydown', key);
      prev?.focus?.();
    };
  }, []);
  return (
    <div class={`backdrop ${p.class ? `for-${p.class}` : ''}`} onClick={(e) => e.target === e.currentTarget && p.onClose()} data-no-swipe>
      <div
        ref={ref}
        class={`modal ${p.class ?? ''}`}
        role={p.role ?? 'dialog'}
        aria-modal="true"
        aria-labelledby={p.labelledBy}
        aria-describedby={p.describedBy}
      >
        {p.children}
      </div>
    </div>
  );
}

export function Confirm(p: { title: string; body: string; yes: string; no?: string; onYes: () => void; onNo: () => void }) {
  return (
    <Modal onClose={p.onNo} labelledBy="confirm-title" describedBy="confirm-body" class="confirm">
      <h2 id="confirm-title">{p.title}</h2>
      <p id="confirm-body">{p.body}</p>
      <div class="actions">
        <button type="button" class="btn primary" onClick={p.onYes} data-autofocus>
          {p.yes}
        </button>
        <button type="button" class="btn" onClick={p.onNo}>
          {p.no ?? 'Cancel'}
        </button>
      </div>
    </Modal>
  );
}

export function Stat(p: { label: string; value: ComponentChildren; sub?: ComponentChildren; tone?: string }) {
  return (
    <div class={`stat ${p.tone ?? ''}`}>
      <div class="stat-label">{p.label}</div>
      <div class="stat-value">{p.value}</div>
      {p.sub && <div class="stat-sub">{p.sub}</div>}
    </div>
  );
}

export function Spinner(p: { label?: string }) {
  return <span class="spinner" role="status" aria-label={p.label ?? 'Loading'} />;
}
