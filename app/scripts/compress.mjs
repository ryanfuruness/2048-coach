// Precompresses the web build (brotli and gzip copies next to each text asset) so the server can send them as is.
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';

const DIST = fileURLToPath(new URL('../web/dist', import.meta.url));
const TEXT = /\.(html|js|mjs|css|svg|json|webmanifest|txt)$/;
let n = 0;
let saved = 0;
function walk(dir) {
  for (const f of readdirSync(dir)) {
    const p = path.join(dir, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (TEXT.test(f) && statSync(p).size > 512) {
      const buf = readFileSync(p);
      const br = brotliCompressSync(buf, { params: { [constants.BROTLI_PARAM_QUALITY]: 11 } });
      const gz = gzipSync(buf, { level: 9 });
      writeFileSync(p + '.br', br);
      writeFileSync(p + '.gz', gz);
      n++;
      saved += buf.length - br.length;
    }
  }
}
walk(DIST);
console.log(`precompressed ${n} files (brotli saves ${(saved / 1024).toFixed(0)} KB)`);
