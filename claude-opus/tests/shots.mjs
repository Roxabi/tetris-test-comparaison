import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
const __d = dirname(fileURLToPath(import.meta.url));
const URL = 'file://' + resolve(__d, '..', 'index.html');
const b = await chromium.launch({ headless: true });
for (const scheme of ['dark', 'light']) {
  const ctx = await b.newContext({ colorScheme: scheme, viewport: { width: 1100, height: 720 } });
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.waitForFunction(() => !!window.__TETRIS__);
  await p.evaluate(() => window.__TETRIS__.reset({ seed: 5 }));
  // drop a couple pieces so there are locked blocks + ghost visible
  await p.keyboard.press('ArrowLeft'); await p.keyboard.press('Space');
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(400);
  await p.screenshot({ path: resolve(__d, `clean-${scheme}.png`) });
  await ctx.close();
}
await b.close();
console.log('done');
