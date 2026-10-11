// Stops the server started by "npm start" (it stops its engine process too).
import { existsSync, readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PIDFILE = path.join(fileURLToPath(new URL('..', import.meta.url)), '.server.pid');
if (!existsSync(PIDFILE)) {
  console.log('No server started by "npm start" is recorded (app/.server.pid).');
  process.exit(0);
}
const pid = Number(readFileSync(PIDFILE, 'utf8'));
try {
  process.kill(pid, 'SIGTERM');
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 100));
    try {
      process.kill(pid, 0);
    } catch {
      break;
    }
  }
  console.log(`Stopped the 2048 Coach server (pid ${pid}).`);
} catch {
  console.log(`The recorded server (pid ${pid}) was not running.`);
}
rmSync(PIDFILE, { force: true });
