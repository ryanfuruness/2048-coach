// Visual QA: scripted user journeys through the app (v3: the coach's grades) in headless Chrome (the installed
// /usr/bin/google-chrome), with screenshots in qa/screens/ and console errors per journey in qa/results.json. The
// user's sanity checks are journeys of their own: a 2048 taken out of its corner is a blunder (and stops you with
// "Warn me"), pulling the 2048 next to a 4096 off the edge is one, random keys get flagged within a few moves, and the
// first stretch of a game (largest tile up to 256) stays quiet.
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
// a 2048 snake along the top row: Down takes the 2048 out of its corner
const SNAKE_2048 = 'ba98356712100000';
// a 4096 snake: Down pulls the 2048 next to the 4096 off the edge
const SNAKE_4096 = 'cba9467823101000';
// an opening with the 128 in its corner: Down leaves the corner (free this early)
const OPEN_128 = '7642321010000000';
// a real position whose chain is blocked: the 128 sits where the 2048-1024-256-64 chain needs a 64
const BLOCKED = '01761268045a322b';
// a roomy 2048 position for random keys
const ROOMY_2048 = 'b975234010000000';

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
/** The coach's verdict on this position is on screen (the move list, or with the list off the grade line's data). */
const coachReady = (page) => page.waitForSelector('.movelist:not(.stale)', { timeout: 15000 });
/** The grade under the board ("" when none is shown yet). */
const gradeNow = (page) => page.evaluate(() => document.querySelector('.grade-line .grade')?.textContent ?? '');
const gradeLineText = (page) => page.evaluate(() => document.querySelector('.grade-line')?.textContent ?? '');
/** Waits until the line under the board grades move k. */
const graded = (page, k) =>
  page.waitForFunction(
    (k) => {
      return !!document.querySelector(`.grade-line .gl-body[data-k="${k}"] .grade`);
    },
    k,
    { timeout: 15000 },
  );
/** The cursor and the game's length, from the move counter ("Move 12 / 40", "Move 40", "Start"). */
const posInfo = (page) =>
  page.evaluate(() => {
    const t = document.querySelector('.tp-pos')?.textContent ?? '';
    const m = t.match(/Move ([\d,]+)(?:\s*\/\s*([\d,]+))?/);
    if (!m) return { cursor: 0, n: Number((t.match(/\/\s*([\d,]+)/) ?? [])[1]?.replace(/,/g, '') ?? 0) };
    const c = Number(m[1].replace(/,/g, ''));
    return { cursor: c, n: m[2] ? Number(m[2].replace(/,/g, '')) : c };
  });
const toggle = (page, label) => page.locator('.panel.coach').getByRole('switch', { name: label, exact: true }).click();
const toggleOn = (page, label) => page.locator('.panel.coach').getByRole('switch', { name: label, exact: true }).getAttribute('aria-checked');

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

await journey('first-visit', async (open) => {
  for (const [dev, tag] of [
    [PHONE, 'phone'],
    [DESKTOP, 'desktop'],
  ]) {
    const page = await open(dev);
    await page.goto(BASE + '/?seed=3', { waitUntil: 'networkidle' });
    await coachReady(page);
    if ((await toggleOn(page, 'Coach')) !== 'true' || (await toggleOn(page, 'Best move')) !== 'true') throw new Error('the coach and its best move are not on by default');
    if ((await toggleOn(page, 'Warn me')) !== 'false' || (await toggleOn(page, 'Highlights')) !== 'false') throw new Error('warnings or highlights are on by default');
    for (const gone of ['.evalbar', '.timeline', '.tabs', '.modes', '.odds-cards', '.plan-line'])
      if (await page.locator(gone).count()) throw new Error(`${gone} is still on the screen`);
    const rows = await page.locator('.mv').count();
    if (rows < 2) throw new Error(`the move list has ${rows} rows`);
    if ((await page.locator('.mv .mv-pct').first().textContent())?.match(/^\d+%$/) === null) throw new Error('no percentage in the move list');
    if (await page.locator('text=of players').count()) throw new Error('"of players" is still shown');
    if ((await page.locator('.board-arrow.best').count()) !== 1) throw new Error('no best-move arrow');
    await shot(page, `01-first-visit-${tag}.png`);
  }
  return 'coach and best move on, warnings and highlights off; no eval bar, timeline, tabs or engine odds; the move list with grades and %; the best-move arrow';
});

await journey('corner-blunder', async (open) => {
  // the user's sanity check: a 2048 taken out of its corner is a blunder, and "Warn me" stops it
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${SNAKE_2048}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(page);
  const down = page.locator('.mv', { hasText: 'Down' });
  if (!(await down.locator('.grade.blunder').count())) throw new Error(`Down is listed as ${await down.locator('.grade').textContent()}`);
  await page.keyboard.press('ArrowDown');
  await graded(page, 1);
  const g = await gradeNow(page);
  const text = await gradeLineText(page);
  if (g !== 'Blunder' || !/takes your 2048 out of its corner/i.test(text)) throw new Error(`graded "${text}"`);
  await shot(page, '02-corner-blunder-desktop.png');
  // Undo, then with "Warn me" the same move is stopped before it happens
  await page.getByRole('button', { name: 'Undo', exact: true }).first().click();
  await toggle(page, 'Warn me');
  await coachReady(page);
  await page.keyboard.press('ArrowDown');
  await page.waitForSelector('.modal.warn', { timeout: 5000 });
  const title = await page.locator('#warn-title').textContent();
  const body = await page.locator('#warn-body').textContent();
  if (!/Down is a blunder/.test(title ?? '') || !/2048 out of its corner/.test(body ?? '')) throw new Error(`warning: ${title} / ${body}`);
  await shot(page, '02-corner-warning-desktop.png');
  await page.keyboard.press('ArrowRight'); // the coach's move
  await page.waitForSelector('.modal.warn', { state: 'detached', timeout: 5000 });
  const { cursor } = await posInfo(page);
  if (cursor !== 1) throw new Error(`after taking the suggestion the game is at move ${cursor}`);
  await toggle(page, 'Warn me');
  return 'Down from a 2048 snake: listed and graded "Blunder · Takes your 2048 out of its corner"; with Warn me the move is stopped and the coach\'s Right taken';
});

await journey('edge-blunder', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + `/?board=${SNAKE_4096}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(page);
  await swipe(page, 'down');
  await graded(page, 1);
  const text = await gradeLineText(page);
  if ((await gradeNow(page)) !== 'Blunder' || !text.includes('2048 off the edge')) throw new Error(`graded "${text}"`);
  await shot(page, '03-edge-blunder-phone.png');
  return 'Down from a 4096 snake pulls the 2048 off the edge: "Blunder"';
});

await journey('random-keys', async (open) => {
  // the user's other sanity check: hitting random keys with a 2048 on the board gets flagged within a few moves
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${ROOMY_2048}&seed=7`, { waitUntil: 'networkidle' });
  await coachReady(page);
  let x = 2463534242; // xorshift32: random keys, the same every run
  const rnd = () => {
    x ^= x << 13;
    x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5;
    x >>>= 0;
    return x;
  };
  const keys = ['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft'];
  const grades = [];
  for (let i = 0; i < 14; i++) {
    const before = (await posInfo(page)).cursor;
    let moved = false;
    for (let tries = 0; tries < 4 && !moved; tries++) {
      await page.keyboard.press(keys[rnd() % 4]);
      await page.waitForTimeout(60);
      moved = (await posInfo(page)).cursor > before;
    }
    if (!moved) break;
    await graded(page, before + 1);
    grades.push(await gradeNow(page));
  }
  const flagged = grades.filter((g) => g === 'Questionable' || g === 'Blunder').length;
  const first = grades.findIndex((g) => g === 'Questionable' || g === 'Blunder');
  await shot(page, '04-random-keys-desktop.png');
  if (flagged < 3 || first < 0 || first > 5) throw new Error(`random keys: ${grades.join(', ')}`);
  return `14 random keys from a 2048 position: ${flagged} flagged (${grades.join(', ')}); the first after ${first + 1} moves`;
});

await journey('early-corner', async (open) => {
  // early on, leaving the corner is questionable (a habit), not a blunder: Warn me does not stop it
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${OPEN_128}&seed=2`, { waitUntil: 'networkidle' });
  await coachReady(page);
  const bests = await page.locator('.mv .grade.best').count();
  if (bests !== 1) throw new Error(`${bests} moves listed as Best (only the coach's should be)`);
  await toggle(page, 'Warn me');
  await page.keyboard.press('ArrowDown');
  await graded(page, 1);
  if (await page.locator('.modal.warn').count()) throw new Error('Warn me stopped an early corner move');
  const g = await gradeNow(page);
  const t = await gradeLineText(page);
  if (g !== 'Questionable' || !/128 out of its corner/.test(t)) throw new Error(`leaving the corner with a 128: "${t}"`);
  await toggle(page, 'Warn me');
  return `one Best in the list; Down from a 128 opening: "${t}", no warning`;
});

await journey('coach-toggles', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${SNAKE_2048}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(page);
  // highlights: nothing before a move (no green), then where a blunder went wrong
  await toggle(page, 'Highlights');
  if (await page.locator('.mark').count()) throw new Error('cells highlighted before any move');
  await page.keyboard.press('ArrowDown');
  await graded(page, 1);
  await page.waitForSelector('.mark.fault', { timeout: 5000 });
  const faults = await page.locator('.mark.fault').count();
  if (faults < 1 || faults > 3) throw new Error(`${faults} fault cells highlighted`);
  await shot(page, '05-highlights-desktop.png');
  await toggle(page, 'Highlights');
  // best move off: no arrow, no list, but the grade stays
  await toggle(page, 'Best move');
  if (await page.locator('.board-arrow.best').count()) throw new Error('the arrow stays with Best move off');
  if (await page.locator('.movelist').count()) throw new Error('the move list stays with Best move off');
  if (!(await gradeNow(page))) throw new Error('the grade went with Best move off');
  await toggle(page, 'Best move');
  // explain: every move's reason and the plan
  await toggle(page, 'Explain');
  await page.waitForSelector('.plan-line, .mv.g-best .mv-why', { timeout: 5000 });
  const whys = await page.locator('.mv-why').count();
  if (whys < 1) throw new Error('Explain shows no reasons');
  await shot(page, '05-explain-desktop.png');
  await toggle(page, 'Explain');
  // coach off: just the game - the panel folds to its switch and the "Grades only" option, Space and P do nothing
  await toggle(page, 'Coach');
  for (const sel of ['.grade-line .grade', '.board-arrow', '.movelist', '.mark', '.ap-buttons'])
    if (await page.locator(sel).count()) throw new Error(`${sel} is shown with the coach off`);
  if ((await page.locator('.panel.coach .option').count()) !== 1) throw new Error('the folded panel should offer only "Grades only"');
  const at = (await posInfo(page)).cursor;
  await page.keyboard.press(' ');
  await page.keyboard.press('p');
  await page.waitForTimeout(500);
  if ((await posInfo(page)).cursor !== at) throw new Error('Space or P played with the coach off');
  await shot(page, '05-coach-off-desktop.png');
  await toggle(page, 'Coach');
  // the engine's odds: hidden until asked, then cards with a bar
  await coachReady(page);
  if (await page.locator('.odds-cards').count()) throw new Error('engine odds shown by default');
  await page.getByRole('button', { name: 'Engine odds' }).click();
  await page.waitForSelector('.odds-cards .odds-card .oc-bar', { timeout: 3000 });
  await shot(page, '05-engine-odds-desktop.png');
  await page.getByRole('button', { name: 'Engine odds', expanded: true }).click();
  return 'Highlights: none before a move, then 1-3 fault cells after a blunder; Best move off hides the arrow and the list, not the grade; Explain adds reasons and the plan; Coach off folds the panel and Space/P do nothing; engine odds as cards behind a link';
});

await journey('blocked-chain', async (open) => {
  // with Explain, a blocked chain is a warning instead of the plan
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${BLOCKED}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(page);
  if (await page.locator('.plan-line').count()) throw new Error('a plan line without Explain');
  await toggle(page, 'Explain');
  await page.waitForSelector('.plan-line.blocked', { timeout: 5000 });
  const t = (await page.locator('.plan-line.blocked').textContent()) ?? '';
  if (!/^Chain blocked\. The 128 in the top row, third column blocks your chain/.test(t)) throw new Error(`warning: "${t}"`);
  await shot(page, '05-blocked-chain-desktop.png');
  await toggle(page, 'Explain');
  return `Explain on a blocked chain: "${t}"`;
});

await journey('grades-only', async (open) => {
  // play yourself: the coach off, only the grade under the board; "Why?" opens the coach
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${SNAKE_2048}&seed=1`, { waitUntil: 'networkidle' });
  await toggle(page, 'Coach');
  await toggle(page, 'Grades only');
  if ((await toggleOn(page, 'Grades only')) !== 'true') throw new Error('Grades only did not switch on');
  if (await page.locator('.movelist, .board-arrow').count()) throw new Error('move list or arrow shown with the coach off');
  await page.keyboard.press('ArrowDown');
  await graded(page, 1);
  if ((await gradeNow(page)) !== 'Blunder') throw new Error(`graded ${await gradeNow(page)}`);
  if (/corner|Coach:/.test(await gradeLineText(page))) throw new Error(`the coach-off line says more than the grade: "${await gradeLineText(page)}"`);
  await shot(page, '05-grades-only-desktop.png');
  await page.getByRole('button', { name: 'Why?' }).click();
  await page.waitForSelector('.movelist', { timeout: 5000 });
  const text = await gradeLineText(page);
  if (!/2048 out of its corner/i.test(text) || !/Coach:/.test(text)) throw new Error(`after Why?: "${text}"`);
  // a best move: only its grade
  await page.getByRole('button', { name: 'Undo', exact: true }).first().click();
  await coachReady(page);
  await page.keyboard.press('ArrowRight');
  await graded(page, 1);
  const best = await gradeLineText(page);
  if (best.trim() !== 'Best') throw new Error(`a best move's line: "${best}"`);
  return 'coach off + Grades only: no list or arrow, Down graded "Blunder" with nothing else; Why? opens the coach with the reason and its move; a best move shows just "Best"';
});

await journey('keyboard-undo', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=11', { waitUntil: 'networkidle' });
  await coachReady(page);
  const keys = ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight'];
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press(keys[i % 4]);
    await page.waitForTimeout(25);
  }
  await page.waitForTimeout(400);
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press(' ');
    await page.waitForTimeout(150);
  }
  const p1 = await posInfo(page);
  await page.keyboard.press('z');
  await page.keyboard.press('z');
  await page.keyboard.press('z');
  await page.keyboard.press('x');
  await page.waitForTimeout(200);
  const p2 = await posInfo(page);
  if (p2.cursor !== p1.cursor - 2 || p2.n !== p1.n) throw new Error(`undo/redo: ${JSON.stringify(p1)} -> ${JSON.stringify(p2)}`);
  await coachReady(page);
  await shot(page, '06-stepped-back-desktop.png');
  const before = await posInfo(page);
  await page.locator('.board-arrow.best, .board-arrow.same').first().click();
  await page.waitForTimeout(300);
  const after = await posInfo(page);
  if (after.cursor !== before.cursor + 1) throw new Error('the arrow did not play');
  return `30 arrow moves + 5 coach moves (Space), Z x3 + X (at ${p2.cursor} of ${p2.n}), the arrow plays the coach's move`;
});

await journey('swipe-phone', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + '/?seed=5', { waitUntil: 'networkidle' });
  await coachReady(page);
  const dirs = ['down', 'left', 'down', 'right', 'down', 'left', 'up', 'left'];
  for (let i = 0; i < 16; i++) {
    await swipe(page, dirs[i % dirs.length]);
    await page.waitForTimeout(120);
  }
  const { cursor } = await posInfo(page);
  if (cursor < 10) throw new Error(`only ${cursor} moves from 16 swipes`);
  await page.waitForTimeout(400);
  await shot(page, '07-swipe-phone.png');
  await shot(page, '07-swipe-phone-full.png', true);
  return `${cursor} moves from 16 swipes`;
});

await journey('autoplay', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=21', { waitUntil: 'networkidle' });
  await coachReady(page);
  await page.locator('.ap-buttons').getByRole('button', { name: '10', exact: true }).click();
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 20000 });
  await page.waitForTimeout(200);
  const p10 = await posInfo(page);
  if (p10.cursor !== 10) throw new Error(`"10" played ${p10.cursor} moves`);
  await page.locator('.ap-buttons').getByRole('button', { name: '100', exact: true }).click();
  await page.waitForSelector('.autoplay.running', { timeout: 5000 });
  await shot(page, '08-autoplay-running-desktop.png');
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 60000 });
  await page.waitForTimeout(200);
  const p100 = await posInfo(page);
  if (p100.cursor !== 110) throw new Error(`"100" ended at move ${p100.cursor}`);
  await page.locator('.ap-buttons').getByRole('button', { name: 'Next tile', exact: true }).click();
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 60000 });
  await page.keyboard.press('p');
  await page.waitForSelector('.autoplay.running', { timeout: 5000 });
  await page.waitForTimeout(800);
  await page.keyboard.press('Escape');
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 5000 });
  await coachReady(page);
  await shot(page, '08-autoplay-stopped-desktop.png');
  return `"10" plays 10 moves, "100" 100 more, "Next tile" stops by itself, P starts and Esc stops (now at move ${(await posInfo(page)).cursor})`;
});

await journey('branch-restore', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=31', { waitUntil: 'networkidle' });
  await coachReady(page);
  await page.locator('.ap-buttons').getByRole('button', { name: '100', exact: true }).click();
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 60000 });
  for (let i = 0; i < 50; i++) await page.keyboard.press('z');
  await page.waitForTimeout(300);
  await coachReady(page);
  const at = await posInfo(page);
  const other = await page.evaluate(() => {
    const played = document.querySelector('.mv.played .mv-name')?.textContent?.toLowerCase();
    const names = [...document.querySelectorAll('.mv .mv-name')].map((e) => e.textContent?.toLowerCase());
    return names.find((x) => x && x !== played) ?? null;
  });
  if (!other) throw new Error('no other move to play');
  await page.locator('.mv', { hasText: new RegExp(`^.?${other[0].toUpperCase()}${other.slice(1)}`) }).locator('.mv-row').click();
  await page.waitForSelector('.toast.with-action', { timeout: 5000 });
  await shot(page, '09-branch-toast-desktop.png');
  await page.locator('.toast-action').click();
  await page.waitForTimeout(300);
  const back = await posInfo(page);
  if (back.n !== 100 || back.cursor !== at.cursor) throw new Error(`restore: ${JSON.stringify(at)} -> ${JSON.stringify(back)}`);
  return `100 coach moves, back 50, a different move from the list replaced 50; "Undo" in the toast restored them (${back.cursor}/${back.n})`;
});

await journey('review', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${ROOMY_2048}&seed=7`, { waitUntil: 'networkidle' });
  await coachReady(page);
  // a few coach moves, a blunder-ish stretch of random keys, then the review
  await page.locator('.ap-buttons').getByRole('button', { name: '10', exact: true }).click();
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 20000 });
  const keys = ['ArrowUp', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowUp'];
  for (const k of keys) {
    await page.keyboard.press(k);
    await page.waitForTimeout(150);
  }
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'More' }).click();
  await page.getByRole('menuitem', { name: /Review your moves/ }).click();
  await page.waitForSelector('.modal.review-sheet', { timeout: 5000 });
  await page.waitForFunction(() => !document.querySelector('.review-sheet .spinner'), null, { timeout: 30000 });
  const counts = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.review-sheet .count')].map((c) => [c.querySelector('span')?.textContent, Number(c.querySelector('strong')?.textContent)])));
  const own = Object.values(counts).reduce((a, b) => a + b, 0);
  if (own < 5 || own > 8) throw new Error(`the review counts ${own} own moves: ${JSON.stringify(counts)}`);
  await page.waitForTimeout(400);
  await shot(page, '10-review-desktop.png');
  const items = await page.locator('.flagged .fl').count();
  if (items > 0) {
    await page.locator('.flagged .fl').first().click();
    await page.waitForSelector('.modal.review-sheet', { state: 'detached', timeout: 3000 });
    await page.waitForTimeout(300);
    const g = await gradeNow(page);
    if (g !== 'Questionable' && g !== 'Blunder') throw new Error(`jumped to a move graded "${g}"`);
  }
  return `10 coach moves + 8 own keys: review counts ${JSON.stringify(counts)} (the coach's left out); ${items} flagged to revisit, a click jumps there`;
});

await journey('game-over', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + `/?board=${NEAR_DEAD}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(page);
  await swipe(page, 'right');
  await page.waitForSelector('.board-over', { timeout: 10000 });
  await page.waitForTimeout(400);
  await shot(page, '11-game-over-phone.png');
  await page.locator('.over-actions').getByRole('button', { name: 'Undo' }).click();
  await page.waitForSelector('.board-over', { state: 'detached', timeout: 5000 });
  await coachReady(page);
  return 'Right on a near-dead board ends the game; the game-over card offers Undo, Review, New game; Undo goes back';
});

await journey('editor', async (open) => {
  const page = await open(PHONE);
  await page.goto(BASE + '/?seed=5', { waitUntil: 'networkidle' });
  await coachReady(page);
  await swipe(page, 'down');
  await page.waitForTimeout(150);
  await swipe(page, 'left');
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: 'More' }).click();
  await page.getByRole('menuitem', { name: /Set up a position/ }).click();
  await page.getByRole('button', { name: 'Clear' }).click();
  const place = async (value, cells) => {
    await page.getByRole('radio', { name: `Tile ${value}`, exact: true }).click();
    for (const c of cells) await page.locator('.board-hit .hit').nth(c).click();
  };
  await place(1024, [15]);
  await place(512, [14]);
  await place(256, [13]);
  await place(64, [12]);
  await place(8, [9]);
  await place(2, [0, 6]);
  await page.waitForSelector('.movelist:not(.stale)', { timeout: 10000 });
  await shot(page, '12-editor-phone.png');
  await page.getByRole('button', { name: 'Play from here' }).click();
  await page.waitForSelector('.toast.with-action', { timeout: 5000 });
  await coachReady(page);
  const tiles = await page.locator('.main-board .tile').count();
  if (tiles !== 7) throw new Error(`Play from here shows ${tiles} tiles`);
  return 'the menu opens the editor on the board; tiles placed with the palette get the coach\'s move list; Play from here starts there (the old game restorable)';
});

await journey('not-judged-block', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + `/?board=${BLOCK}`, { waitUntil: 'networkidle' });
  await coachReady(page);
  const t = await page.locator('.movelist').textContent();
  if (!t?.includes('Not judged')) throw new Error(`block formation: ${t}`);
  return 'an expert block formation: the moves are "Not judged"';
});

await journey('offline', async (open) => {
  const page = await open(PHONE);
  await page.route('**/api/**', (r) => r.abort('connectionrefused'));
  await page.goto(BASE + '/?seed=8', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(500);
  for (const d of ['down', 'left', 'down', 'right']) {
    await swipe(page, d);
    await page.waitForTimeout(150);
  }
  const { cursor } = await posInfo(page);
  if (cursor < 3) throw new Error(`only ${cursor} moves offline`);
  await page.waitForSelector('text=The coach is offline', { timeout: 5000 });
  await page.locator('.ap-buttons').getByRole('button', { name: '10', exact: true }).click();
  await page.waitForSelector('.toast', { timeout: 5000 });
  await shot(page, '13-offline-phone.png');
  return `${cursor} moves offline; the panel says "The coach is offline"; autoplay stops with a message`;
});

await journey('persistence', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=41', { waitUntil: 'networkidle' });
  await coachReady(page);
  await page.locator('.ap-buttons').getByRole('button', { name: '100', exact: true }).click();
  await page.waitForSelector('.autoplay:not(.running)', { timeout: 60000 });
  for (let i = 0; i < 7; i++) await page.keyboard.press('z');
  await page.waitForTimeout(1800);
  const before = await posInfo(page);
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(300);
  const after = await posInfo(page);
  if (after.cursor !== before.cursor || after.n !== before.n) throw new Error(`reload: ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
  // a v2 line (old facts) still opens, and the old settings become toggles
  await page.evaluate(() => {
    const r = JSON.parse(localStorage.getItem('tc.line'));
    delete r.fv;
    r.facts = '1100000000'.repeat(4);
    localStorage.setItem('tc.line', JSON.stringify(r));
    localStorage.setItem('tc.settings', JSON.stringify({ mode: 'coach', speed: 1, until: 'stop', seenIntro: true }));
  });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(300);
  const v2 = await posInfo(page);
  if (v2.n !== before.n) throw new Error('the v2 line did not open');
  if ((await toggleOn(page, 'Warn me')) !== 'true' || (await toggleOn(page, 'Best move')) !== 'false') throw new Error('v2 "Coach" mode did not become Warn me without Best move');
  return `a reload keeps the game (${after.cursor}/${after.n}); a v2 line with old facts opens; v2 Coach mode opens as Warn me without Best move`;
});

await journey('shortcuts-how-dark', async (open) => {
  const page = await open(DESKTOP);
  await page.goto(BASE + '/?seed=3', { waitUntil: 'networkidle' });
  await coachReady(page);
  await page.keyboard.press('?');
  await page.waitForSelector('.modal.shortcuts', { timeout: 3000 });
  await shot(page, '14-shortcuts-desktop.png');
  await page.keyboard.press('Escape');
  await page.waitForSelector('.modal.shortcuts', { state: 'detached', timeout: 3000 });
  await page.keyboard.press('c');
  if ((await toggleOn(page, 'Coach')) !== 'false') throw new Error('C did not turn the coach off');
  await page.keyboard.press('c');
  await page.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(page, '15-how-desktop.png', true);
  const phone = await open(PHONE, { colorScheme: 'dark' });
  await phone.goto(BASE + `/?board=${SNAKE_2048}&seed=1`, { waitUntil: 'networkidle' });
  await coachReady(phone);
  await swipe(phone, 'down');
  await graded(phone, 1);
  await shot(phone, '16-dark-phone.png');
  await phone.goto(BASE + '/how', { waitUntil: 'networkidle' });
  await shot(phone, '15-how-phone.png', true);
  return '? opens the shortcuts, Esc closes them; C toggles the coach; How on desktop and phone; dark phone with a blunder';
});

await browser.close();
if (server) server.kill();
const resultsFile = path.join(APP, 'qa', 'results.json');
let merged = results;
if (ONLY) {
  try {
    const old = JSON.parse(readFileSync(resultsFile, 'utf8')).results ?? [];
    merged = [...old.filter((r) => !results.some((x) => x.name === r.name)), ...results];
  } catch {
    /* no earlier results */
  }
}
writeFileSync(resultsFile, JSON.stringify({ at: new Date().toISOString(), base: BASE, results: merged }, null, 2));
const clean = results.filter((r) => r.ok && !r.errors.length).length;
console.log(`\n${clean}/${results.length} journeys clean`);
process.exit(clean === results.length ? 0 : 1);
