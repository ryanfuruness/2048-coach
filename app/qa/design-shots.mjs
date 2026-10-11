// Design review screenshots: the key states of the app at desktop and phone size, light and dark.
//   node qa/design-shots.mjs OUTDIR [--base URL]
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
const OUT = process.argv[2] ?? 'qa/design';
const BASE = process.argv.includes('--base') ? process.argv[process.argv.indexOf('--base') + 1] : 'http://127.0.0.1:8048';
mkdirSync(OUT, { recursive: true });
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };
const DESKTOP = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const LAPTOP = { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 };
const SNAKE = 'ba98356712100000';
const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
async function page(dev, scheme = 'light', settings) {
  const ctx = await b.newContext({ ...dev, colorScheme: scheme });
  if (settings) await ctx.addInitScript((s) => localStorage.setItem('tc.settings', JSON.stringify(s)), settings);
  return ctx.newPage();
}
const ready = (p) => p.waitForSelector('.movelist li', { timeout: 8000 }).catch(() => {});
const shot = async (p, n, full = false) => { await p.waitForTimeout(500); await p.screenshot({ path: path.join(OUT, n), fullPage: full }); };
const S = (o) => ({ coach: true, hints: true, warn: false, highlights: false, explain: false, odds: false, speed: 'normal', ...o });

let p = await page(DESKTOP); await p.goto(BASE + '/?seed=3'); await ready(p); await shot(p, 'd-start.png');
for (const k of ['ArrowLeft', 'ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown']) { await p.keyboard.press(k); await p.waitForTimeout(150); }
await p.waitForTimeout(500); await shot(p, 'd-moves.png');
p = await page(DESKTOP, 'light', S({ highlights: true, explain: true, odds: true })); await p.goto(BASE + `/?board=${SNAKE}&seed=1`); await ready(p);
await p.locator('summary, button', { hasText: /engine odds/i }).first().click().catch(() => {}); await p.waitForTimeout(300); await shot(p, 'd-explain.png');
await p.keyboard.press('ArrowDown'); await p.waitForTimeout(800); await shot(p, 'd-blunder.png');
p = await page(DESKTOP, 'light', S({ warn: true })); await p.goto(BASE + `/?board=${SNAKE}&seed=1`); await ready(p);
await p.keyboard.press('ArrowDown'); await p.waitForSelector('.modal', { timeout: 5000 }).catch(() => {}); await p.waitForTimeout(300); await shot(p, 'd-warn.png');
p = await page(DESKTOP, 'light', S({ coach: false })); await p.goto(BASE + '/?seed=3'); await p.waitForTimeout(800); await shot(p, 'd-off.png');
p = await page(LAPTOP, 'light', S({ explain: true })); await p.goto(BASE + `/?board=${SNAKE}&seed=1`); await ready(p); await shot(p, 'l-explain.png');
p = await page(DESKTOP, 'dark', S({ highlights: true, explain: true })); await p.goto(BASE + `/?board=${SNAKE}&seed=1`); await ready(p); await p.keyboard.press('ArrowDown'); await p.waitForTimeout(800); await shot(p, 'd-dark.png');
await p.keyboard.press('r'); await p.waitForTimeout(800); await shot(p, 'd-dark-review.png');
p = await page(PHONE); await p.goto(BASE + '/?seed=3'); await ready(p); await shot(p, 'p-start.png'); await shot(p, 'p-start-full.png', true);
p = await page(PHONE, 'dark', S({ explain: true })); await p.goto(BASE + `/?board=${SNAKE}&seed=1`); await ready(p); await shot(p, 'p-dark-full.png', true);
p = await page(DESKTOP); await p.goto(BASE + '/how'); await p.waitForTimeout(500); await shot(p, 'd-how.png');
await b.close();
