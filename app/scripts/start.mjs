// One command for the local app: checks the engine, builds the web app when its sources changed, starts the server.
//   npm start            (from app/)    ->  http://127.0.0.1:8048
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = fileURLToPath(new URL('..', import.meta.url));
const ROOT = path.resolve(process.env.ENGINE_ROOT || path.join(APP, '..'));
const bin = path.join(ROOT, process.env.ENGINE_BIN || 'build/analyze');

const port = process.env.PORT || '8048';
const host = process.env.HOST || '127.0.0.1';
try {
  const r = await fetch(`http://${host === '0.0.0.0' ? '127.0.0.1' : host}:${port}/api/health`, { signal: AbortSignal.timeout(1500) });
  if (r.status === 200 || r.status === 503) {
    console.log(`2048 Coach is already running: http://127.0.0.1:${port}/  (stop it with "npm run stop")`);
    process.exit(0);
  }
} catch {
  /* nothing is listening: start */
}

if (!existsSync(bin)) {
  console.error(`The engine is not built (${bin}).\nBuild it first:  (cd ${ROOT} && make -j8)`);
  process.exit(1);
}
const probe = spawnSync(bin, ['--stdin-player', '--help-probe'], { encoding: 'utf8' });
if (/unknown option --stdin-player/.test(probe.stderr ?? '')) {
  console.error('This build of build/analyze lacks the app flags (--stdin-player, --review-moves); see app/engine-patch/README.md, then run make -j8.');
  process.exit(1);
}
if (!existsSync(path.join(APP, 'node_modules', 'vite'))) {
  console.log('Installing the app dependencies (npm install)...');
  const r = spawnSync('npm', ['install', '--no-audit', '--no-fund'], { cwd: APP, stdio: 'inherit', env: { ...process.env, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: '1' } });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

function newest(dir) {
  let t = 0;
  for (const f of readdirSync(dir)) {
    const p = path.join(dir, f);
    const s = statSync(p);
    t = Math.max(t, s.isDirectory() ? newest(p) : s.mtimeMs);
  }
  return t;
}
const dist = path.join(APP, 'web', 'dist', 'index.html');
const srcTime = Math.max(newest(path.join(APP, 'web', 'src')), newest(path.join(APP, 'web', 'public')), newest(path.join(APP, 'shared')), statSync(path.join(APP, 'web', 'index.html')).mtimeMs);
if (!existsSync(dist) || statSync(dist).mtimeMs < srcTime || process.argv.includes('--build')) {
  console.log('Building the web app...');
  const r = spawnSync('npm', ['run', 'build'], { cwd: APP, stdio: 'inherit' });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

const server = spawn(process.execPath, [path.join(APP, 'server', 'src', 'index.ts')], {
  cwd: APP,
  stdio: 'inherit',
  env: { ...process.env, LOG_REQUESTS: process.env.LOG_REQUESTS ?? '0' },
});
const PIDFILE = path.join(APP, '.server.pid');
writeFileSync(PIDFILE, String(server.pid));
setTimeout(() => {
  if (server.exitCode === null) console.log(`\n  2048 Coach is running:  http://127.0.0.1:${port}/\n  (Ctrl+C or "npm run stop" stops the server and its engine)\n`);
}, 1500);
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(sig, () => server.kill('SIGTERM'));
server.on('exit', (code) => {
  rmSync(PIDFILE, { force: true });
  process.exit(code ?? 0);
});
