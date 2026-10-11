import type { ComponentChildren } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';

export interface MenuItem {
  label: string;
  hint?: string;
  onSelect: () => void;
  disabled?: boolean;
}

/** A small menu behind a button: arrow keys move between the items, Escape or a click outside closes it. */
export function Menu(p: { label: string; button: ComponentChildren; items: MenuItem[]; class?: string }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const items = () => [...(wrap.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? [])];
    items()[0]?.focus();
    const down = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
        btn.current?.focus();
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        const list = items();
        const i = list.indexOf(document.activeElement as HTMLElement);
        list[(i + (e.key === 'ArrowDown' ? 1 : list.length - 1)) % list.length]?.focus();
      } else if (e.key === 'Tab') setOpen(false);
      else if (e.key.startsWith('Arrow')) e.stopPropagation();
    };
    document.addEventListener('pointerdown', down);
    wrap.current?.addEventListener('keydown', key);
    const el = wrap.current;
    return () => {
      document.removeEventListener('pointerdown', down);
      el?.removeEventListener('keydown', key);
    };
  }, [open]);
  return (
    <div class={`menu ${p.class ?? ''}`} ref={wrap}>
      <button
        ref={btn}
        type="button"
        class="btn small menu-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={p.label}
        title={p.label}
        onClick={(e) => {
          setOpen((o) => !o);
          if (e.detail > 0 && open) (e.currentTarget as HTMLElement).blur();
        }}
      >
        {p.button}
      </button>
      {open && (
        <div class="menu-list" role="menu" aria-label={p.label}>
          {p.items.map((it) => (
            <button
              type="button"
              role="menuitem"
              key={it.label}
              disabled={it.disabled}
              onClick={() => {
                setOpen(false);
                it.onSelect();
              }}
            >
              <span>{it.label}</span>
              {it.hint && <kbd>{it.hint}</kbd>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
