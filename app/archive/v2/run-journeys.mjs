// Visual QA: scripted user journeys through the workbench in headless Chrome (the installed /usr/bin/google-chrome),
// with screenshots in qa/screens/ and console errors per journey in qa/results.json.
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
// a near-dead board: Right is a costly move (the coach warns), Down keeps the game alive; with seed 1, Right ends it
const NEAR_DEAD = '1241356247932180';
// an expert's 3x2 block formation (32768 phase): without the exact tables the engine does not judge it
const BLOCK = '1adf26be23451032';

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
  page.waitForFunction(
    () => {
      const v = document.querySelector('.evalbar-value');
      return v && v.textContent && v.textContent !== '–' && !document.querySelector('.evalbar.pending');
    },
    null,
    { timeout: 15000 },
  );
const analysisReady = (page) => page.waitForSelector('.verdict:not(.stale), .analysis-body:not(.stale) .verdict', { timeout: 15000 });
/** The line's length and the cursor, from the timeline slider. */
const lineAt = (page) =>
  page.evaluate(() => {
    const s = document.querySelector('.timeline');
    return { cursor: Number(s?.getAttribute('aria-valuenow')), n: Number(s?.getAttribute('aria-valuemax')) };
  });
const setMode = (page, label) => page.locator('.modes').getByRole('radio', { name: label, exact: true }).click();

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

/** Plays like a casual corner player until the game is over: down or left when possible, right when stuck, up last. */
async function playToEnd(page, { delay = 0, maxMoves = 3000 } = {}) {
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < maxMoves * 4; i++) {
    if (await page.locator('.board-over').count()) return;
    const order = rnd() < 0.08 ? ['ArrowRight', 'ArrowUp', 'ArrowDown', 'ArrowLeft'] : rnd() < 0.5 ? ['ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowUp'] : ['ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowUp'];
    const before = (await lineAt(page)).n;
    for (const k of order) {
      await page.keyboard.press(k);
      if (delay) await page.waitForTimeout(delay);
      if (await page.locator('.board-over').count()) return;
      if ((await lineAt(page)).n !== before) break;
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
    await analysisReady(page);
    const mode = await page.locator('.modes [aria-checked="true"]').textContent();
    if (mode !== 'Analyze') throw new Error(`default mode is ${mode}`);
    const tiles = await page.locator('.main-board .tile').count();
    if (tiles !== 2) throw new Error(`a new game shows ${tiles} tiles`);
    if (!(await page.locator('.intro').count())) throw new Error('no welcome note');
    await page.waitForTimeout(300);
    await shot(page, file);
  }
  return 'mode "Analyze", 2 tiles, eval bar and the best move from the first analysis, welcome note';
});

await journey('keyboard-desktop', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=2048', { waitUntil: 'networkidle' });
  await analysisReady(page);
  const seq = ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowLeft'];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press(seq[i % seq.length]);
    await page.waitForTimeout(30);
  }
  const own = (await lineAt(page)).n;
  if (own < 25) throw new Error(`only ${own} moves registered`);
  // Space plays the coach's move (5 times), Z takes back, X steps forward again
  for (let i = 0; i < 5; i++) {
    await analysisReady(page);
    await page.keyboard.press('Space');
    await page.waitForTimeout(120);
  }
  const after = await lineAt(page);
  if (after.n !== own + 5) throw new Error(`Space played ${after.n - own} coach moves, not 5`);
  if (!(await page.locator('.last-move .tag.played', { hasText: 'coach' }).count())) throw new Error('the last move is not marked as the coach move');
  for (let i = 0; i < 3; i++) await page.keyboard.press('z');
  await page.keyboard.press('x');
  await page.waitForTimeout(300);
  const back = await lineAt(page);
  if (back.cursor !== after.n - 2 || back.n !== after.n) throw new Error(`after 3 undos and 1 redo: ${JSON.stringify(back)}`);
  await analysisReady(page);
  await page.waitForTimeout(300);
  await shot(page, '02-keyboard-desktop.png');
  // clicking the best-move arrow on the board plays it
  await page.keyboard.press('End');
  await analysisReady(page);
  await page.locator('.board-arrow.clickable').click();
  await page.waitForTimeout(200);
  const clicked = await lineAt(page);
  if (clicked.n !== after.n + 1) throw new Error('clicking the arrow did not play the move');
  return `${own} moves by arrow keys, 5 coach moves with Space, undo/redo with Z/X (at move ${back.cursor} of ${back.n}), arrow click plays`;
});

await journey('swipe-phone', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + '/?seed=77', { waitUntil: 'networkidle' });
  await evalReady(page);
  const dirs = ['down', 'left', 'down', 'right', 'down', 'left', 'up', 'left', 'down', 'right', 'down', 'left', 'down', 'left', 'right', 'down', 'left', 'down', 'right', 'down'];
  for (const d of dirs) {
    await swipe(page, d);
    await page.waitForTimeout(120);
  }
  const { n } = await lineAt(page);
  if (n < 12) throw new Error(`only ${n} of ${dirs.length} swipes moved`);
  await page.getByRole('button', { name: 'Back one move' }).click();
  await page.getByRole('button', { name: 'Back one move' }).click();
  await page.waitForTimeout(400);
  const at = await lineAt(page);
  if (at.cursor !== n - 2) throw new Error(`back twice: cursor ${at.cursor} of ${n}`);
  await evalReady(page);
  await page.waitForTimeout(300);
  await shot(page, '03-swipe-phone.png');
  await shot(page, '03-swipe-phone-full.png', true);
  return `${n} moves from ${dirs.length} swipes (illegal swipes shake the board); the back button steps back`;
});

await journey('coach-warning', async (open) => {
  const out = [];
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(`${BASE}/?board=${NEAR_DEAD}&seed=3`, { waitUntil: 'networkidle' });
    await setMode(page, 'Coach');
    await evalReady(page);
    if (tag === 'phone') await swipe(page, 'right');
    else await page.keyboard.press('ArrowRight');
    await page.waitForSelector('.modal.warn', { timeout: 5000 });
    await page.waitForTimeout(350);
    await shot(page, `04-warning-${tag}.png`);
    const title = await page.locator('#warn-title').textContent();
    await page.locator('.modal.warn .btn.primary').click();
    await page.waitForTimeout(400);
    if (await page.locator('.board-over').count()) throw new Error('taking the suggestion ended the game');
    out.push(`${tag}: "${title}"`);
  }
  return out.join('; ');
});

await journey('game-over-undo', async (open) => {
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(`${BASE}/?board=${NEAR_DEAD}&seed=1`, { waitUntil: 'networkidle' });
    await evalReady(page);
    await page.keyboard.press('ArrowRight');
    await page.waitForSelector('.board-over', { timeout: 5000 });
    await page.waitForTimeout(800);
    await shot(page, `05-game-over-${tag}.png`);
    await page.locator('.over-card').getByRole('button', { name: /Undo/ }).click();
    await page.waitForTimeout(300);
    if (await page.locator('.board-over').count()) throw new Error('undo left the game over');
    const at = await lineAt(page);
    if (at.cursor !== 0 || at.n !== 1) throw new Error(`after undo: ${JSON.stringify(at)}`);
    await page.waitForSelector('.played .tag.blunder', { timeout: 10000 });
    await page.waitForTimeout(300);
    await shot(page, `05-after-undo-${tag}.png`);
  }
  return 'Right ends the game; the game-over card offers Undo, which goes back to the position, with the move marked as a blunder';
});

await journey('autoplay', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=4242', { waitUntil: 'networkidle' });
  await analysisReady(page);
  // one move a second
  await page.keyboard.press('1');
  await page.keyboard.press('p');
  await page.waitForTimeout(2600);
  await page.keyboard.press('p');
  const slow = (await lineAt(page)).n;
  if (slow < 2 || slow > 4) throw new Error(`1/s played ${slow} moves in 2.6 s`);
  // full speed for 5 s
  await page.keyboard.press('4');
  const t0 = Date.now();
  await page.keyboard.press('p');
  await page.waitForTimeout(2500);
  await shot(page, '06-autoplay-running-desktop.png');
  await page.waitForTimeout(2500);
  await page.keyboard.press('p');
  const dt = (Date.now() - t0) / 1000;
  const fast = (await lineAt(page)).n - slow;
  if (fast < 200) throw new Error(`full speed played only ${fast} moves in ${dt.toFixed(1)} s`);
  // until the next tile: stops on its own
  await page.locator('select.until').selectOption('tile');
  const target = await page.locator('select.until option[value="tile"]').textContent();
  await page.keyboard.press('p');
  await page.waitForFunction(() => !document.querySelector('.autoplay.running'), null, { timeout: 120000 });
  const toast = await page.locator('.toast').textContent().catch(() => '');
  await analysisReady(page);
  await page.waitForTimeout(400);
  await shot(page, '06-autoplay-stopped-desktop.png');
  return `1/s: ${slow} moves in 2.6 s; full speed: ${fast} moves in ${dt.toFixed(1)} s (${Math.round(fast / dt)}/s); "${target.trim()}" stopped by itself ("${toast}")`;
});

await journey('scrub-branch-restore', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=777', { waitUntil: 'networkidle' });
  await analysisReady(page);
  await page.keyboard.press('4');
  await page.keyboard.press('p');
  await page.waitForTimeout(2500);
  await page.keyboard.press('p');
  const { n } = await lineAt(page);
  // drag the timeline to about the middle
  const box = await page.locator('.timeline').boundingBox();
  await page.mouse.move(box.x + box.width * 0.8, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(300);
  const mid = await lineAt(page);
  if (Math.abs(mid.cursor - n / 2) > n * 0.05 + 2) throw new Error(`dragged to ${mid.cursor} of ${n}`);
  await page.waitForSelector('.played', { timeout: 5000 });
  await analysisReady(page);
  await page.waitForTimeout(300);
  await shot(page, '07-scrubbed-desktop.png');
  // a move other than the line's replaces the continuation; the toast brings it back
  const next = await page.locator('.played strong').textContent();
  const keys = { Up: 'ArrowUp', Right: 'ArrowRight', Down: 'ArrowDown', Left: 'ArrowLeft' };
  for (const [word, key] of Object.entries(keys)) {
    if (next.includes(word)) continue;
    await page.keyboard.press(key);
    await page.waitForTimeout(250);
    if ((await lineAt(page)).n !== n) break;
  }
  await page.waitForSelector('.toast.with-action', { timeout: 5000 });
  await page.waitForTimeout(300);
  await shot(page, '07-branch-toast-desktop.png');
  const branched = await lineAt(page);
  await page.locator('.toast-action').click();
  await page.waitForTimeout(300);
  const restored = await lineAt(page);
  if (restored.n !== n || restored.cursor !== mid.cursor) throw new Error(`restore gave ${JSON.stringify(restored)}, expected n ${n} at ${mid.cursor}`);
  // the same on a phone: a tap on the timeline jumps
  const phone = await open(PHONE);
  await phone.goto(BASE + '/?seed=778', { waitUntil: 'networkidle' });
  await evalReady(phone);
  await phone.locator('.auto-toggle').click();
  await phone.waitForTimeout(3000);
  await phone.locator('.auto-toggle').click();
  const pb = await phone.locator('.timeline').boundingBox();
  await phone.touchscreen.tap(pb.x + pb.width * 0.3, pb.y + pb.height / 2);
  await phone.waitForTimeout(400);
  const pt = await lineAt(phone);
  if (pt.cursor >= pt.n) throw new Error('a tap on the timeline did not move the cursor');
  await evalReady(phone);
  await phone.waitForTimeout(300);
  await shot(phone, '07-scrubbed-phone.png');
  return `line of ${n} moves; dragged to ${mid.cursor}; a different move left ${branched.n} moves; restored ${restored.n}; phone tap to ${pt.cursor} of ${pt.n}`;
});

await journey('review', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=31337', { waitUntil: 'networkidle' });
  await analysisReady(page);
  // the coach opens (40 moves), then the player plays on until the end
  await page.keyboard.press('4');
  await page.locator('select.until').selectOption('moves');
  await page.keyboard.press('p');
  await page.waitForFunction(() => !document.querySelector('.autoplay.running'), null, { timeout: 60000 });
  await page.keyboard.press('Shift+Z');
  await page.keyboard.press('Shift+Z');
  await page.keyboard.press('Shift+Z');
  await page.keyboard.press('Shift+Z');
  await page.keyboard.press('Shift+Z');
  await page.keyboard.press('Shift+Z');
  await page.waitForTimeout(200);
  await playToEnd(page, { delay: 25 });
  const { n } = await lineAt(page);
  await page.waitForTimeout(500);
  await page.locator('.over-card').getByRole('button', { name: 'Review' }).click();
  await page.waitForSelector('.panel .stats', { timeout: 60000 });
  await page.waitForTimeout(700);
  const facts = await page.locator('.panel .facts').textContent();
  if (!/only yours count/.test(facts)) throw new Error(`the review does not separate the coach's moves: "${facts}"`);
  await shot(page, '08-review-desktop.png');
  await shot(page, '08-review-desktop-full.png', true);
  const km = page.locator('.km').first();
  let jumped = 'no key moment';
  if (await km.count()) {
    await km.click();
    await page.waitForTimeout(400);
    jumped = `key moment -> position ${(await lineAt(page)).cursor}`;
    await shot(page, '08-review-key-moment-desktop.png');
  }
  const state = await page.context().storageState();
  const phone = await open(PHONE, { storageState: state });
  await phone.goto(BASE + '/', { waitUntil: 'networkidle' });
  await phone.locator('.tabs').getByRole('tab', { name: /Review/ }).click();
  await phone.locator('.review-cta .btn, .panel .stats').first().waitFor({ timeout: 10000 });
  if (await phone.locator('.review-cta .btn').count()) await phone.locator('.review-cta .btn').click();
  await phone.waitForSelector('.panel .stats', { timeout: 60000 });
  await phone.waitForTimeout(500);
  await phone.locator('.panel').scrollIntoViewIfNeeded();
  await shot(phone, '08-review-phone.png');
  await shot(phone, '08-review-phone-full.png', true);
  return `${n} moves (40 by the coach); review: "${facts.trim().slice(0, 120)}…"; ${jumped}`;
});

await journey('editor', async (open) => {
  for (const [dev, tag] of [
    [DESKTOP, 'desktop'],
    [PHONE, 'phone'],
  ]) {
    const page = await open(dev);
    await page.goto(BASE + '/?seed=5', { waitUntil: 'networkidle' });
    await evalReady(page);
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowLeft');
    if (tag === 'desktop') await page.keyboard.press('e');
    else {
      await page.getByRole('button', { name: 'More' }).click();
      await page.getByRole('menuitem', { name: /Set up a position/ }).click();
    }
    await page.getByRole('button', { name: 'Clear' }).click();
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
    await page.waitForTimeout(500);
    await shot(page, `09-editor-${tag}.png`);
    await page.fill('#board-text', '2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0');
    await page.getByRole('button', { name: 'Load' }).click();
    // the pasted board's analysis: your chance of the 2048 milestone (its largest tile is 512)
    await page.waitForFunction(() => document.querySelector('.verdict-text')?.textContent?.includes('Your chance of reaching 2048'), null, { timeout: 10000 });
    await page.getByRole('button', { name: 'Play from here' }).click();
    await page.waitForSelector('.toast.with-action', { timeout: 5000 });
    await evalReady(page);
    const tiles = await page.locator('.main-board .tile').count();
    if (tiles !== 15) throw new Error(`Play from here shows ${tiles} tiles`);
    await page.waitForTimeout(300);
    await shot(page, `09-play-from-here-${tag}.png`);
    // this position is tricky at the default level: in Coach mode the coach offers a hint
    await setMode(page, 'Coach');
    await page.waitForSelector('.hint-chip', { timeout: 5000 });
    await page.locator('.hint-chip').click();
    await page.waitForSelector('.board-arrow.best', { timeout: 5000 });
    await page.waitForTimeout(300);
    await shot(page, `09-hint-open-${tag}.png`);
  }
  return 'E (desktop) or the menu (phone) opens the editor on the board; palette taps build a position with live analysis; a pasted board plays from here (old line restorable); Coach mode offers the opening hint';
});

await journey('not-judged-block', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(`${BASE}/?board=${BLOCK}`, { waitUntil: 'networkidle' });
  await analysisReady(page);
  await page.waitForTimeout(300);
  const txt = await page.locator('.panel').textContent();
  if (!/Not judged/.test(txt)) throw new Error('the block position is not shown as not judged');
  await shot(page, '10-not-judged-desktop.png');
  return 'block formation shows "Not judged" and the engine move as a suggestion';
});

await journey('offline', async (open) => {
  // the analysis server is unreachable: the game stays playable, the coach says it is offline
  const page = await open(PHONE);
  await page.route('**/api/**', (r) => r.abort('connectionrefused'));
  await page.goto(BASE + '/?seed=99', { waitUntil: 'domcontentloaded' });
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown']) {
    await page.keyboard.press(k);
    await page.waitForTimeout(80);
  }
  await page.waitForFunction(() => document.querySelector('.evalbar-sub')?.textContent?.includes('offline'), null, { timeout: 5000 });
  const { n } = await lineAt(page);
  if (n < 3) throw new Error(`only ${n} moves without the server`);
  await page.locator('.auto-toggle').click();
  await page.waitForFunction(() => /offline/.test(document.querySelector('.toast')?.textContent ?? ''), null, { timeout: 8000 });
  await shot(page, '11-offline-phone.png');
  return `${n} moves played with the server unreachable; the eval bar says "Coach offline"; autoplay stops with "The coach is offline"`;
});

await journey('persistence', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=606', { waitUntil: 'networkidle' });
  await analysisReady(page);
  await page.keyboard.press('4');
  await page.keyboard.press('p');
  await page.waitForTimeout(1500);
  await page.keyboard.press('p');
  for (let i = 0; i < 7; i++) await page.keyboard.press('z');
  await page.waitForTimeout(300);
  const before = await lineAt(page);
  await page.waitForTimeout(200);
  await page.reload({ waitUntil: 'networkidle' });
  const after = await lineAt(page);
  if (after.n !== before.n || after.cursor !== before.cursor) throw new Error(`after a reload ${JSON.stringify(after)} instead of ${JSON.stringify(before)}`);
  // a game in progress from app v1 opens on the workbench
  const v1 = await open(DESKTOP);
  await v1.addInitScript(() => {
    if (localStorage.getItem('tc.line')) return;
    localStorage.setItem('tc.current', JSON.stringify('v1game'));
    localStorage.setItem(
      'tc.g.v1game',
      JSON.stringify({ v: 1, id: 'v1game', startedAt: 1, updatedAt: 1, start: '1001000000000000', moves: 'DLD', spawns: '012', score: 4, maxRank: 2, over: false, origin: 'new', coach: { warnings: 0, warningsTaken: 0, hints: 0, hintsOpened: 0 } }),
    );
    localStorage.setItem('tc.settings', JSON.stringify({ coach: 'warn', seenIntro: true }));
  });
  await v1.goto(BASE + '/', { waitUntil: 'networkidle' });
  const imported = await lineAt(v1);
  if (imported.n !== 3 || imported.cursor !== 3) throw new Error(`the v1 game came in as ${JSON.stringify(imported)}`);
  const mode = await v1.locator('.modes [aria-checked="true"]').textContent();
  return `reload keeps the line (${after.n} moves, cursor ${after.cursor}); a v1 game in progress opens as the line (3 moves), v1 "Warn me" opens as ${mode}`;
});

await journey('shortcuts-a11y', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=808', { waitUntil: 'networkidle' });
  await analysisReady(page);
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight']) await page.keyboard.press(k);
  await page.keyboard.press('?');
  await page.waitForSelector('.modal.shortcuts');
  await page.waitForTimeout(300);
  await shot(page, '12-shortcuts-desktop.png');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);
  if (await page.locator('.modal.shortcuts').count()) throw new Error('Escape did not close the shortcuts');
  // the timeline is a slider: focused, the arrow keys move along the line instead of playing
  const before = await lineAt(page);
  await page.locator('.timeline').focus();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(200);
  const after = await lineAt(page);
  if (after.n !== before.n || after.cursor !== before.cursor - 2) throw new Error(`slider keys: ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
  return `"?" opens the shortcuts, Escape closes them; the focused timeline takes the arrow keys (${before.cursor} -> ${after.cursor})`;
});

await journey('how', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(page, '13-how-desktop.png');
  const phone = await open(PHONE);
  await phone.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(phone, '13-how-phone.png');
});

await journey('dark-mode', async (open) => {
  const page = await open(PHONE, { colorScheme: 'dark' });
  await page.goto(BASE + '/?seed=5', { waitUntil: 'networkidle' });
  await evalReady(page);
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowLeft']) {
    await page.keyboard.press(k);
    await page.waitForTimeout(60);
  }
  await page.keyboard.press('z');
  await evalReady(page);
  await page.waitForTimeout(300);
  await shot(page, '14-dark-phone.png');
  const d = await open(DESKTOP, { colorScheme: 'dark' });
  await d.goto(BASE + '/?seed=6', { waitUntil: 'networkidle' });
  await analysisReady(d);
  for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowRight']) {
    await d.keyboard.press(k);
    await d.waitForTimeout(40);
  }
  await d.keyboard.press('4');
  await d.keyboard.press('p');
  await d.waitForTimeout(1500);
  await d.keyboard.press('p');
  await d.keyboard.press('r');
  await d.waitForSelector('.panel .stats', { timeout: 60000 });
  await d.waitForTimeout(500);
  await shot(d, '14-dark-review-desktop.png');
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
// a partial run (--only) keeps the other journeys' last results
const merged = ONLY ? [...prev.filter((p) => !results.some((r) => r.name === p.name)), ...results] : results;
writeFileSync(path.join(APP, 'qa', 'results.json'), JSON.stringify(merged, null, 2));
const failed = results.filter((r) => !r.ok || r.errors.length);
console.log(`\n${results.length - failed.length}/${results.length} journeys clean`);
process.exit(failed.length ? 1 : 0);
