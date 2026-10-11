// Lighthouse audits (performance, accessibility, best practices, SEO) of the production build served by the app server,
// in the installed Chrome, mobile and desktop. Reports in qa/lighthouse/.
//
//   node qa/run-lighthouse.mjs [--base http://127.0.0.1:8048]
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import { spawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = fileURLToPath(new URL('..', import.meta.url));
const OUT = path.join(APP, 'qa', 'lighthouse');
mkdirSync(OUT, { recursive: true });
const args = process.argv.slice(2);
const BASE = args.includes('--base') ? args[args.indexOf('--base') + 1] : 'http://127.0.0.1:8048';

async function up() {
  try {
    return (await fetch(`${BASE}/api/health`)).ok;
  } catch {
    return false;
  }
}
let server = null;
if (!(await up())) {
  server = spawn('node', ['server/src/index.ts'], { cwd: APP, stdio: 'ignore' });
  for (let i = 0; i < 100 && !(await up()); i++) await new Promise((r) => setTimeout(r, 200));
}

// an explicit Linux profile directory: under WSL, chrome-launcher otherwise derives a Windows temp path and creates it
// as a relative directory in the working directory
const profile = mkdtempSync(path.join(tmpdir(), 'lighthouse-profile-'));
const chrome = await chromeLauncher.launch({
  chromePath: '/usr/bin/google-chrome',
  chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'],
  userDataDir: profile,
});
const pages = [
  ['board', '/'],
  ['position-link', '/?board=0248001235670124'],
  ['how', '/how'],
];
const summary = [];
for (const [name, url] of pages) {
  for (const preset of ['mobile', 'desktop']) {
    const config = preset === 'desktop' ? (await import('lighthouse/core/config/desktop-config.js')).default : undefined;
    const r = await lighthouse(
      BASE + url,
      { port: chrome.port, output: ['html', 'json'], logLevel: 'error', onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'] },
      config,
    );
    const [html, json] = r.report;
    writeFileSync(path.join(OUT, `${name}-${preset}.html`), html);
    writeFileSync(path.join(OUT, `${name}-${preset}.json`), json);
    const lhr = r.lhr;
    const score = (c) => Math.round((lhr.categories[c]?.score ?? 0) * 100);
    const metric = (id) => lhr.audits[id]?.displayValue ?? '';
    const failed = Object.values(lhr.audits)
      .filter((a) => a.score !== null && a.score < 0.9 && a.scoreDisplayMode !== 'informative' && a.scoreDisplayMode !== 'manual' && a.scoreDisplayMode !== 'notApplicable')
      .map((a) => `${a.id} (${a.score})`);
    const row = {
      page: name,
      preset,
      performance: score('performance'),
      accessibility: score('accessibility'),
      bestPractices: score('best-practices'),
      seo: score('seo'),
      fcp: metric('first-contentful-paint'),
      lcp: metric('largest-contentful-paint'),
      tbt: metric('total-blocking-time'),
      cls: metric('cumulative-layout-shift'),
      transfer: metric('total-byte-weight'),
      below90: failed,
    };
    summary.push(row);
    console.log(JSON.stringify(row));
  }
}
await chrome.kill();
rmSync(profile, { recursive: true, force: true });
// under WSL, chrome-launcher may also leave a folder named after the Windows path of the profile in app/
for (const f of readdirSync(APP)) if (f.includes('lighthouse-profile')) rmSync(path.join(APP, f), { recursive: true, force: true });
if (server) server.kill();
writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2));
