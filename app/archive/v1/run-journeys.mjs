// Visual QA: scripted user journeys in headless Chrome (the installed /usr/bin/google-chrome), with screenshots in
// qa/screens/ and console errors per journey in qa/results.json.
//
//   node qa/run-journeys.mjs [--base http://127.0.0.1:8048] [--only name,name]
//
// Starts the app server (node server/src/index.ts) if nothing answers at --base.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const APP = fileURLToPath(new URL('..', import.meta.url));
const SHOTS = path.join(APP, 'qa', 'screens');
mkdirSync(SHOTS, { recursive: true });
const args = process.argv.slice(2);
const BASE = args.includes('--base') ? args[args.indexOf('--base') + 1] : 'http://127.0.0.1:8048';
const ONLY = args.includes('--only') ? args[args.indexOf('--only') + 1].split(',') : null;

const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };
const DESKTOP = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
// a near-dead board: Right is a costly move (the coach warns), Down keeps the game alive
const NEAR_DEAD = '1241356247932180';

async function serverUp() {
  try {
    return (await fetch(`${BASE}/api/health`)).ok;
  } catch {
    return false;
  }
}

let server = null;
if (!(await serverUp())) {
  server = spawn('node', ['server/src/index.ts'], { cwd: APP, stdio: 'ignore' });
  for (let i = 0; i < 100 && !(await serverUp()); i++) await new Promise((r) => setTimeout(r, 200));
}

const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const results = [];

async function journey(name, fn) {
  if (ONLY && !ONLY.includes(name)) return;
  const errors = [];
  const t0 = Date.now();
  const contexts = [];
  const open = async (device, opts = {}) => {
    const ctx = await browser.newContext({ ...device, ...opts });
    contexts.push(ctx);
    const page = await ctx.newPage();
    page.on('console', (m) => {
      if (m.type() === 'error' && !(name === 'offline' && /Failed to load resource|ERR_CONNECTION_REFUSED/.test(m.text()))) errors.push(`console.error: ${m.text()}`);
    });
    page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
    page.on('requestfailed', (r) => {
      if (name !== 'offline') errors.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`);
    });
    page.on('response', (r) => {
      if (r.status() >= 400) errors.push(`HTTP ${r.status()}: ${r.url()}`);
    });
    return page;
  };
  let ok = true;
  let note = '';
  try {
    note = (await fn(open)) ?? '';
  } catch (e) {
    ok = false;
    note = String(e?.stack ?? e);
  }
  for (const c of contexts) await c.close();
  results.push({ name, ok, ms: Date.now() - t0, errors, note });
  console.log(`${ok && !errors.length ? 'PASS' : ok ? 'WARN' : 'FAIL'} ${name} (${Date.now() - t0} ms)${errors.length ? `\n  ${errors.join('\n  ')}` : ''}${note ? `\n  ${note}` : ''}`);
}

const shot = (page, file, full = false) => page.screenshot({ path: path.join(SHOTS, file), fullPage: full });
const evalReady = (page) =>
  page.waitForFunction(() => {
    const v = document.querySelector('.evalbar-value');
    return v && v.textContent && v.textContent !== '–' && !document.querySelector('.evalbar.pending');
  }, null, { timeout: 15000 });
const moveCount = (page) => page.evaluate(() => JSON.parse(localStorage.getItem('tc.games') || '[]')[0]?.moves ?? 0);

async function swipe(page, dir) {
  const client = await page.context().newCDPSession(page);
  const box = await page.locator('.main-board').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const d = 110;
  const [dx, dy] = { up: [0, -d], right: [d, 0], down: [0, d], left: [-d, 0] }[dir];
  await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: cx, y: cy }] });
  for (let i = 1; i <= 6; i++)
    await client.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: cx + (dx * i) / 6, y: cy + (dy * i) / 6 }] });
  await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await client.detach();
}

/**
 * Plays until the game is over like a casual corner player: down or left when possible, right when stuck, up as the
 * last resort, and a random legal-looking move now and then. Warnings are answered alternately (take / play anyway).
 */
async function playToEnd(page, { delay = 0, maxMoves = 3000 } = {}) {
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const count = () => page.evaluate(() => JSON.parse(localStorage.getItem('tc.games') || '[]')[0]?.moves ?? 0);
  let warnings = 0;
  let moves = await count();
  for (let i = 0; i < maxMoves * 4; i++) {
    if (await page.locator('.board-over').count()) return warnings;
    if (await page.locator('.modal.warn').count()) {
      warnings++;
      await page.locator('.modal.warn .btn').nth(warnings % 2 ? 0 : 1).click();
      moves = await count();
      continue;
    }
    const order = rnd() < 0.08 ? ['ArrowRight', 'ArrowUp', 'ArrowDown', 'ArrowLeft'] : rnd() < 0.5 ? ['ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowUp'] : ['ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowUp'];
    for (const k of order) {
      await page.keyboard.press(k);
      if (delay) await page.waitForTimeout(delay);
      if ((await page.locator('.modal.warn').count()) || (await page.locator('.board-over').count())) break;
      const now = await count();
      if (now !== moves) {
        moves = now;
        break;
      }
    }
  }
  throw new Error('the game did not end');
}

await journey('first-visit', async (open) => {
  for (const [dev, file] of [
    [PHONE, '01-first-visit-phone.png'],
    [DESKTOP, '01-first-visit-desktop.png'],
  ]) {
    const page = await open(dev);
    await page.goto(BASE + '/', { waitUntil: 'networkidle' });
    await evalReady(page);
    const mode = await page.locator('.segmented [aria-checked="true"]').textContent();
    if (mode !== 'Warn me') throw new Error(`default coach mode is ${mode}`);
    const tiles = await page.locator('.main-board .tile').count();
    if (tiles !== 2) throw new Error(`a new game shows ${tiles} tiles`);
    await shot(page, file);
  }
  return 'default coach "Warn me", 2 tiles, eval bar filled from the first analysis';
});

await journey('keyboard-desktop', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=2048', { waitUntil: 'networkidle' });
  await evalReady(page);
  const seq = ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowLeft'];
  for (let i = 0; i < 60; i++) {
    if (await page.locator('.modal.warn').count()) await page.locator('.modal.warn .btn.primary').click();
    await page.keyboard.press(seq[i % seq.length]);
    await page.waitForTimeout(40);
  }
  await evalReady(page);
  await page.waitForTimeout(300);
  const n = await moveCount(page);
  if (n < 30) throw new Error(`only ${n} moves registered`);
  await shot(page, '02-keyboard-desktop.png');
  await page.getByRole('radio', { name: 'Best move' }).click();
  await page.waitForSelector('.board-arrow.best', { timeout: 10000 });
  await page.waitForTimeout(300);
  await shot(page, '02-best-move-desktop.png');
  return `${n} moves by keyboard; "Best move" shows the arrow`;
});

await journey('swipe-phone', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + '/?seed=77', { waitUntil: 'networkidle' });
  await evalReady(page);
  const dirs = ['down', 'left', 'down', 'right', 'down', 'left', 'up', 'left', 'down', 'right', 'down', 'left', 'down', 'left', 'right', 'down', 'left', 'down', 'right', 'down'];
  for (const d of dirs) {
    if (await page.locator('.modal.warn').count()) await page.locator('.modal.warn .btn.primary').click();
    await swipe(page, d);
    await page.waitForTimeout(120);
  }
  await evalReady(page);
  await page.waitForTimeout(300);
  const n = await moveCount(page);
  if (n < 12) throw new Error(`only ${n} of ${dirs.length} swipes moved`);
  await shot(page, '03-swipe-phone.png');
  return `${n} moves from ${dirs.length} swipes (illegal swipes shake the board)`;
});

await journey('warning', async (open) => {
  const out = [];
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(`${BASE}/?board=${NEAR_DEAD}&seed=3`, { waitUntil: 'networkidle' });
    await evalReady(page);
    if (tag === 'phone') await swipe(page, 'right');
    else await page.keyboard.press('ArrowRight');
    await page.waitForSelector('.modal.warn', { timeout: 5000 });
    await page.waitForTimeout(350);
    await shot(page, `04-warning-${tag}.png`);
    const title = await page.locator('#warn-title').textContent();
    await page.locator('.modal.warn .btn.primary').click();
    await page.waitForTimeout(400);
    const over = await page.locator('.board-over').count();
    if (over) throw new Error('taking the suggestion ended the game');
    if (tag === 'phone') {
      await evalReady(page);
      await shot(page, '04-after-warning-phone.png');
    }
    out.push(`${tag}: "${title}"`);
  }
  return out.join('; ');
});

await journey('game-over', async (open) => {
  // the debug board: Right ends the game here with this seed (the new tile is a 2)
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(`${BASE}/?board=${NEAR_DEAD}&seed=1`, { waitUntil: 'networkidle' });
    await page.getByRole('radio', { name: 'Off' }).click();
    await page.keyboard.press('ArrowRight');
    for (let i = 0; i < 20 && !(await page.locator('.board-over').count()); i++) await page.keyboard.press(['ArrowDown', 'ArrowLeft', 'ArrowUp', 'ArrowRight'][i % 4]);
    await page.waitForSelector('.board-over', { timeout: 5000 });
    await page.waitForTimeout(700);
    await shot(page, `05-game-over-${tag}.png`);
  }
  return 'near-dead debug board (?board=...&seed=1) -> game over overlay with "Review this game"';
});

let reviewState = null;
await journey('full-game-review', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=31337', { waitUntil: 'networkidle' });
  await evalReady(page);
  const warnings = await playToEnd(page, { delay: 45 });
  const n = await moveCount(page);
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Review this game' }).click();
  await page.waitForSelector('.stats', { timeout: 30000 });
  await page.waitForTimeout(600);
  await shot(page, '06-review-desktop.png');
  await shot(page, '06-review-desktop-full.png', true);
  // step through with the arrow keys, then jump to the key moments
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Shift+ArrowLeft');
  await page.waitForTimeout(300);
  await page.locator('.stepper').scrollIntoViewIfNeeded();
  await shot(page, '06-review-step-desktop.png');
  const pos = await page.locator('.step-pos').textContent();
  reviewState = await page.context().storageState();
  const url = page.url();
  // the same review on a phone
  const phone = await open(PHONE, { storageState: reviewState });
  await phone.goto(url, { waitUntil: 'networkidle' });
  await phone.waitForSelector('.stats', { timeout: 30000 });
  await phone.waitForTimeout(500);
  await shot(phone, '06-review-phone.png');
  await shot(phone, '06-review-phone-full.png', true);
  await phone.locator('.stepper').scrollIntoViewIfNeeded();
  await phone.locator('.step-controls button[aria-label="Next move"]').click();
  await phone.waitForTimeout(250);
  await shot(phone, '06-review-step-phone.png');
  return `${n} moves played (coach on, ${warnings} warnings answered); review opened; stepped to "${pos}"`;
});

await journey('editor-play-from-here', async (open) => {
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(BASE + '/analyze', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Clear' }).click();
    // build a position: 1024 in the corner, a chain, a few small tiles
    const place = async (value, cells) => {
      await page.getByRole('radio', { name: `Tile ${value}`, exact: true }).click();
      for (const c of cells) await page.locator('.board-hit .hit').nth(c).click();
    };
    await place(1024, [15]);
    await place(512, [14]);
    await place(256, [13]);
    await place(64, [12]);
    await place(32, [8]);
    await place(8, [9]);
    await place(4, [10, 3]);
    await place(2, [0, 11, 6]);
    await page.waitForSelector('.verdict', { timeout: 10000 });
    await page.waitForTimeout(400);
    await shot(page, `07-editor-${tag}.png`);
    if (tag === 'desktop') await shot(page, '07-editor-desktop-full.png', true);
    // paste a board string, then play from it
    await page.fill('#board-text', '2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0');
    await page.getByRole('button', { name: 'Load' }).click();
    await page.waitForFunction(() => document.querySelector('.verdict-text')?.textContent?.includes('16384'), null, { timeout: 10000 });
    await page.getByRole('button', { name: 'Play from here' }).click();
    await page.waitForSelector('.main-board');
    await evalReady(page);
    const tiles = await page.locator('.main-board .tile').count();
    if (tiles !== 15) throw new Error(`Play from here shows ${tiles} tiles`);
    await page.waitForTimeout(300);
    await shot(page, `07-play-from-here-${tag}.png`);
    // this position is tricky at the default level: the coach offers a hint, which shows the best move
    await page.waitForSelector('.hint-chip', { timeout: 5000 });
    await page.locator('.hint-chip').click();
    await page.waitForSelector('.board-arrow.best', { timeout: 5000 });
    await page.waitForTimeout(300);
    await shot(page, `07-hint-open-${tag}.png`);
  }
  return 'palette taps build a board; paste "2 4 16 2 / ..." loads; Play from here starts the coached game; the opening hint is offered and opens';
});

await journey('not-judged-block', async (open) => {
  // an expert's 3x2 block formation (32768 phase): without the exact tables the engine does not judge it
  const page = await open(DESKTOP);
  await page.goto(BASE + '/analyze?board=1adf26be23451032', { waitUntil: 'networkidle' });
  await page.waitForSelector('.verdict', { timeout: 10000 });
  await page.waitForTimeout(300);
  const txt = await page.locator('.analysis').textContent();
  if (!/Not judged/.test(txt)) throw new Error('the block position is not shown as not judged');
  await shot(page, '11-not-judged-desktop.png');
  return 'block formation shows "Not judged" and the engine move as a suggestion';
});

await journey('offline', async (open) => {
  // the analysis server is unreachable: the game must stay playable, the coach says it is offline
  const page = await open(PHONE);
  await page.route('**/api/**', (r) => r.abort('connectionrefused'));
  await page.goto(BASE + '/?seed=99', { waitUntil: 'domcontentloaded' });
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown']) {
    await page.keyboard.press(k);
    await page.waitForTimeout(80);
  }
  await page.waitForFunction(() => document.querySelector('.evalbar-sub')?.textContent?.includes('offline'), null, { timeout: 5000 });
  const n = await moveCount(page);
  if (n < 3) throw new Error(`only ${n} moves without the server`);
  await shot(page, '12-offline-phone.png');
  return `${n} moves played with the server unreachable; the eval bar says "Coach offline"`;
});

await journey('history', async (open) => {
  if (!reviewState) return 'skipped (needs the full-game journey)';
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev, { storageState: reviewState });
    await page.goto(BASE + '/history', { waitUntil: 'networkidle' });
    await page.waitForSelector('.game-item');
    await page.waitForTimeout(300);
    await shot(page, `08-history-${tag}.png`);
  }
  return 'history lists the played games with their review summary';
});

await journey('how', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(page, '09-how-desktop.png');
  const phone = await open(PHONE);
  await phone.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(phone, '09-how-phone.png');
});

await journey('dark-mode', async (open) => {
  const page = await open(PHONE, { colorScheme: 'dark' });
  await page.goto(BASE + '/?seed=5', { waitUntil: 'networkidle' });
  await evalReady(page);
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowLeft']) {
    await page.keyboard.press(k);
    await page.waitForTimeout(60);
  }
  await evalReady(page);
  await page.waitForTimeout(300);
  await shot(page, '10-dark-play-phone.png');
  if (reviewState) {
    const d = await open(DESKTOP, { colorScheme: 'dark', storageState: reviewState });
    const id = JSON.parse(reviewState.origins[0].localStorage.find((x) => x.name === 'tc.games').value).find((g) => g.review)?.id;
    if (id) {
      await d.goto(`${BASE}/review/${id}`, { waitUntil: 'networkidle' });
      await d.waitForSelector('.stats', { timeout: 30000 });
      await d.waitForTimeout(500);
      await shot(d, '10-dark-review-desktop.png');
    }
  }
});

await browser.close();
if (server) server.kill();
const prev = (() => {
  try {
    return JSON.parse(readFileSync(path.join(APP, 'qa', 'results.json'), 'utf8'));
  } catch {
    return [];
  }
})();
const merged = [...prev.filter((p) => !results.some((r) => r.name === p.name)), ...results];
writeFileSync(path.join(APP, 'qa', 'results.json'), JSON.stringify(merged, null, 2));
const failed = results.filter((r) => !r.ok || r.errors.length);
console.log(`\n${results.length - failed.length}/${results.length} journeys clean`);
process.exit(failed.length ? 1 : 0);
