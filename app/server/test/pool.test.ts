// The engine pool with a fake engine: queueing, timeouts, crash recovery.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { EngineBusy, EnginePool, EngineTimeout, EngineUnavailable } from '../src/engine.ts';

const FAKE = fileURLToPath(new URL('./fake-engine.sh', import.meta.url));
const spec = { root: '/tmp', bin: FAKE, args: [], startupTimeoutMs: 5000 };
const until = async (f: () => boolean, ms = 5000) => {
  const t0 = Date.now();
  while (!f()) {
    if (Date.now() - t0 > ms) throw new Error('timeout waiting');
    await new Promise((r) => setTimeout(r, 20));
  }
};

test('answers in order, recovers from crashes and hangs', async (t) => {
  const pool = new EnginePool(1, spec, 4, 3000);
  t.after(() => pool.stop());
  pool.start();
  await until(() => pool.ready);
  const out = await pool.run('a | 1', 2000);
  assert.match(out, /"echo":"a \| 1"/);
  const [x, y] = await Promise.all([pool.run('x', 2000), pool.run('y', 2000)]);
  assert.match(x, /"echo":"x"/);
  assert.match(y, /"echo":"y"/);

  await assert.rejects(pool.run('crash', 2000), EngineUnavailable);
  await until(() => pool.ready);
  assert.match(await pool.run('next one', 2000), /next one/);

  await assert.rejects(pool.run('hang', 300), EngineTimeout);
  await until(() => pool.ready);
  assert.match(await pool.run('later one', 2000), /later one/);
  assert.equal(pool.status().workers[0].restarts, 2);
  pool.stop();
});

test('a full queue is refused instead of growing', async (t) => {
  const pool = new EnginePool(1, spec, 2, 3000);
  t.after(() => pool.stop());
  pool.start();
  await until(() => pool.ready);
  const hang = pool.run('hang', 1000).catch((e) => e);
  const a = pool.run('a', 3000);
  const b = pool.run('b', 3000);
  await assert.rejects(pool.run('c', 3000), EngineBusy);
  assert.ok((await hang) instanceof EngineTimeout);
  assert.match(await a, /"echo":"a"/);
  assert.match(await b, /"echo":"b"/);
  pool.stop();
});
