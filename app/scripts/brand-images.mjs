// Renders the link-preview image and the app icons from qa/brand/*.html into web/public/ (run after changing them).
//   node scripts/brand-images.mjs
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
const at = (p) => new URL(p, import.meta.url);
const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const shot = async (html, size, scale, out) => {
  const page = await b.newPage({ viewport: size, deviceScaleFactor: scale });
  await page.goto(at(html).href);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: fileURLToPath(at(out)) });
  await page.close();
};
await shot('../qa/brand/og.html', { width: 1200, height: 630 }, 1, '../web/public/og.png');
// full-bleed square icons (iOS and Android round the corners themselves)
await shot('../qa/brand/icon.html', { width: 512, height: 512 }, 180 / 512, '../web/public/apple-touch-icon.png');
await shot('../qa/brand/icon.html', { width: 512, height: 512 }, 192 / 512, '../web/public/icon-192.png');
await shot('../qa/brand/icon.html', { width: 512, height: 512 }, 1, '../web/public/icon-512.png');
await b.close();
