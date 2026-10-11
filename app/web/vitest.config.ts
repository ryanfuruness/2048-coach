import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('..', import.meta.url)),
  resolve: {
    alias: { '@shared': fileURLToPath(new URL('../shared', import.meta.url)) },
  },
  test: {
    include: ['shared/**/*.test.ts', 'web/src/**/*.test.ts', 'web/src/**/*.test.tsx'],
    environment: 'node',
    testTimeout: 60000,
  },
});
