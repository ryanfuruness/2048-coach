// Development: the API server (engine pool) and the Vite dev server with hot reload; Vite proxies /api to the server.
//   npm run dev   ->  http://127.0.0.1:5173
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = fileURLToPath(new URL('..', import.meta.url));
const procs = [
  spawn(process.execPath, [path.join(APP, 'server', 'src', 'index.ts')], { cwd: APP, stdio: 'inherit', env: { ...process.env, LOG_REQUESTS: process.env.LOG_REQUESTS ?? '0' } }),
  spawn('npx', ['vite', '--config', 'web/vite.config.ts'], { cwd: APP, stdio: 'inherit' }),
];
const stop = () => procs.forEach((p) => p.kill('SIGTERM'));
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, stop);
for (const p of procs) p.on('exit', () => (stop(), process.exit(0)));
