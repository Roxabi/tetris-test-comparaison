// Independent end-to-end verification of index.html — written fresh (not the builder's harness).
// Drives a real headless Chromium via Playwright and asserts every DEMANDE.md requirement + bonuses.
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FILE = resolve(__dirname, '..', 'index.html');
const URL = 'file://' + FILE;

const results = [];
const rec = (name, ok, detail = '') => { results.push({ name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); };
const eq = (name, got, want) => rec(name, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)} want ${JSON.stringify(want)}`);
const PIECES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L'];
const sleep = (p, ms) => p.waitForTimeout(ms);

async function main() {
  const browser = await chromium.launch({ headless: true });

  // ── Static source checks (offline / colors) ───────────────────────────────
  const src = readFileSync(FILE, 'utf8');
  rec('static: no external URL (http/https resource)', !/(src|href)\s*=\s*["']https?:/i.test(src) && !/@import|cdn\.|unpkg|jsdelivr|googleapis/i.test(src));
  const colorWant = { I: 'cyan', O: 'yellow', T: 'purple', S: 'green', Z: 'red', J: 'blue', L: 'orange' };
  const colorOk = Object.entries(colorWant).every(([k, v]) => new RegExp(`${k}:\\s*'#[0-9a-f]{3,6}',\\s*//\\s*${v}`, 'i').test(src));
  rec('static: 7 standard piece colors (I cyan…L orange)', colorOk);

  // ── Helpers bound to a page ────────────────────────────────────────────────
  const ctx = await browser.newContext({ colorScheme: 'dark' });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push(String(e)));
  await page.goto(URL);
  await page.waitForFunction(() => !!window.__TETRIS__);

  const S = () => page.evaluate(() => window.__TETRIS__.getState());
  const reset = (o) => page.evaluate(opt => window.__TETRIS__.reset(opt), o || {});
  const setG = (b) => page.evaluate(v => window.__TETRIS__.setGravity(v), b);
  const press = async (k) => { await page.keyboard.press(k); await sleep(page, 15); };

  // 1) prefers-color-scheme: dark context → starts dark
  const themeDark = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  rec('theme: prefers-color-scheme dark → initial dark', themeDark === 'dark', `data-theme=${themeDark}`);

  // 2) Initial state
  await reset({ seed: 1 });
  await setG(false);
  let s = await S();
  rec('init: active piece present & valid type', s.active && PIECES.includes(s.active.type), `active=${s.active && s.active.type}`);
  rec('init: next valid type', PIECES.includes(s.next), `next=${s.next}`);
  rec('init: board is 20×10 all empty', s.board.length === 20 && s.board.every(r => r.length === 10 && r.every(c => c === 0)));
  eq('init: score/level/lines = 0/1/0', [s.score, s.level, s.lines], [0, 1, 0]);
  rec('init: not gameOver, not paused', s.gameOver === false && s.paused === false);

  // 3) Movement — arrows + QWERTY(A/D) + AZERTY(Q/D)
  const xOf = st => st.active.x;
  await reset({ sequence: ['T'] }); await setG(false);
  let x0 = (await S()).active.x;
  await press('ArrowRight'); rec('move: ArrowRight x+1', (await S()).active.x === x0 + 1);
  await press('ArrowLeft'); rec('move: ArrowLeft x-1', (await S()).active.x === x0);
  await press('d'); rec('move: QWERTY D (KeyD) right', (await S()).active.x === x0 + 1);
  await press('a'); rec('move: QWERTY A (KeyA) left', (await S()).active.x === x0);
  await press('q'); rec('move: AZERTY Q (KeyQ) left', (await S()).active.x === x0 - 1);

  // 4) Rotation — CW & CCW via Arrows, W/S, and key z/s fallback
  await reset({ sequence: ['T'] }); await setG(false);
  const rot = async () => (await S()).active.rotation;
  let r0 = await rot();
  await press('ArrowUp'); const rUp = await rot(); rec('rotate: ArrowUp = CW (+1)', rUp === (r0 + 1) % 4, `${r0}->${rUp}`);
  await press('ArrowDown'); rec('rotate: ArrowDown = CCW (back)', (await rot()) === r0);
  await press('w'); rec('rotate: KeyW = CW', (await rot()) === (r0 + 1) % 4);
  await press('s'); rec('rotate: KeyS = CCW', (await rot()) === r0);
  await press('z'); rec('rotate: AZERTY Z (key z) = CW', (await rot()) === (r0 + 1) % 4);
  await press('s'); rec('rotate: key s = CCW', (await rot()) === r0);

  // 5) Hard drop — Space AND Enter lock the piece and spawn a new one
  await reset({ sequence: ['T', 'I', 'O'] }); await setG(false);
  let before = await S();
  const fill = st => st.board.flat().filter(c => c).length;
  await press('Space'); let after = await S();
  rec('drop: Space locks (board filled +4)', fill(after) === 4, `fill=${fill(after)}`);
  rec('drop: new active spawned after Space', after.active && after.active.type === 'I');
  rec('drop: score increased after hard drop', after.score > before.score, `score=${after.score}`);
  await press('Enter'); let after2 = await S();
  rec('drop: Enter also hard-drops (board filled +4 → 8)', fill(after2) === 8, `fill=${fill(after2)}`);

  // 6) Line clear + scoring — pack bottom 2 rows with 5 O-pieces → double (300×lvl)
  async function packDoubleRound() {
    // assumes upcoming 5 pieces are O; gravity off
    for (let i = 0; i < 5; i++) {
      for (let k = 0; k < 7; k++) await press('ArrowLeft');   // slam to left wall
      for (let k = 0; k < i * 2; k++) await press('ArrowRight'); // step to column pair
      await press('Space');
    }
  }
  await reset({ sequence: ['O', 'O', 'O', 'O', 'O'] }); await setG(false);
  const sc0 = await S();
  await packDoubleRound();
  const scD = await S();
  rec('lineclear: 5 O-pieces clear exactly 2 rows (double)', scD.lines === 2, `lines=${scD.lines}`);
  rec('lineclear: board emptied after clear', scD.board.flat().every(c => c === 0));
  rec('lineclear: score jumped ≥300 (double=300×lvl1)', scD.score - sc0.score >= 300, `Δscore=${scD.score - sc0.score}`);
  rec('lineclear: scoring table is 100/300/500/800', /\[0,\s*100,\s*300,\s*500,\s*800\]/.test(src));

  // 7) Level progression — clear 10 lines → level 2; speed table strictly decreasing
  await reset({ sequence: Array(25).fill('O') }); await setG(false);
  for (let round = 0; round < 5; round++) await packDoubleRound();
  const lvlState = await S();
  rec('level: 10 lines cleared → level 2', lvlState.level === 2 && lvlState.lines === 10, `level=${lvlState.level} lines=${lvlState.lines}`);
  const gravTable = (src.match(/GRAVITY_TABLE\s*=\s*\[([\s\S]*?)\]/) || [])[1] || '';
  const nums = gravTable.split(',').map(n => parseInt(n)).filter(n => !isNaN(n));
  // Guideline curve: non-increasing overall, first 10 levels strictly faster, top speed << level 1.
  const nonInc = nums.every((v, i) => i === 0 || v <= nums[i - 1]);
  const firstTenStrict = nums.slice(0, 10).every((v, i) => i === 0 || v < nums[i - 1]);
  rec('level: gravity accelerates with level (faster each level, plateaus at top)', nums.length >= 10 && nonInc && firstTenStrict && nums[nums.length - 1] < nums[0], `[${nums.slice(0, 6).join(',')}…${nums[nums.length - 1]}]`);

  // 8) 7-bag — every 7 consecutive spawns is a permutation of all 7
  await reset({ seed: 7 }); await setG(false);
  const seq = [];
  for (let i = 0; i < 14; i++) {
    const st = await S();
    if (st.gameOver) break;
    seq.push(st.active.type);
    // spread across columns to avoid early stack-out
    for (let k = 0; k < 7; k++) await press('ArrowLeft');
    for (let k = 0; k < (i % 9); k++) await press('ArrowRight');
    await press('Space');
  }
  const bag1 = [...new Set(seq.slice(0, 7))].sort().join('');
  const bag2 = [...new Set(seq.slice(7, 14))].sort().join('');
  rec('7-bag: first 7 spawns = all 7 distinct', bag1 === 'IJLOSTZ', `bag1=${bag1} (${seq.slice(0, 7).join('')})`);
  rec('7-bag: second 7 spawns = all 7 distinct', seq.length >= 14 ? bag2 === 'IJLOSTZ' : true, `bag2=${bag2} (${seq.slice(7, 14).join('')})`);

  // 9) Pause (F4) — toggles + blocks gameplay input while paused
  await reset({ sequence: ['T'] }); await setG(false);
  await press('F4'); rec('pause: F4 → paused', (await S()).paused === true);
  const px = (await S()).active.x;
  await press('ArrowRight'); rec('pause: input ignored while paused', (await S()).active.x === px);
  await press('F4'); rec('pause: F4 again → resumed', (await S()).paused === false);

  // 10) Reset (F2) — clears score & board, spawns fresh piece
  await reset({ seed: 1 }); await setG(false);
  await press('Space'); await press('Space');
  rec('reset: precondition score>0', (await S()).score > 0);
  await press('F2');
  const rs = await S();
  rec('reset: F2 → score 0 & board cleared & active present', rs.score === 0 && rs.board.flat().every(c => c === 0) && !!rs.active);

  // 11) Game over — stack one column until spawn collision, then F2 recovers
  await reset({ seed: 3 }); await setG(false);
  let go = false;
  for (let i = 0; i < 80; i++) { await press('Space'); if ((await S()).gameOver) { go = true; break; } }
  rec('gameover: reachable by stacking', go);
  await press('F2'); rec('gameover: F2 clears game-over state', (await S()).gameOver === false);

  // 12) Hold (C and Shift) + one-hold-per-drop rule
  await reset({ sequence: ['T', 'I', 'O', 'L'] }); await setG(false);
  await press('c');
  let h = await S();
  rec('hold: C stashes current (hold=T), active=next (I)', h.hold === 'T' && h.active.type === 'I', `hold=${h.hold} active=${h.active.type}`);
  await press('c');
  let h2 = await S();
  rec('hold: one-hold-per-drop — 2nd C is a no-op', h2.hold === 'T' && h2.active.type === 'I');
  await press('Space'); // lock I → unlocks hold, spawn O
  await press('Shift');
  let h3 = await S();
  rec('hold: Shift swaps after lock (hold=O, active=T)', h3.hold === 'O' && h3.active.type === 'T', `hold=${h3.hold} active=${h3.active.type}`);

  // 13) preventDefault on system + game keys
  await reset({ sequence: ['T'] });
  const dp = await page.evaluate(async () => {
    const seen = {};
    const codes = ['F2', 'F4', 'Space', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'ArrowRight', 'Enter'];
    const h = e => { if (codes.includes(e.code)) seen[e.code] = e.defaultPrevented; };
    document.addEventListener('keydown', h);
    function fire(code, key) {
      const ev = new KeyboardEvent('keydown', { code, key, bubbles: true, cancelable: true });
      document.dispatchEvent(ev);
    }
    fire('F2', 'F2'); fire('F4', 'F4'); fire('Space', ' '); fire('ArrowLeft', 'ArrowLeft'); fire('ArrowDown', 'ArrowDown');
    document.removeEventListener('keydown', h);
    return seen;
  });
  rec('preventDefault: F2', dp.F2 === true);
  rec('preventDefault: F4', dp.F4 === true);
  rec('preventDefault: Space', dp.Space === true);
  rec('preventDefault: ArrowLeft', dp.ArrowLeft === true);
  rec('preventDefault: ArrowDown', dp.ArrowDown === true);

  // 14) Ghost piece present (renders a landing projection)
  rec('ghost: ghostY() landing projection implemented', /ghostY\s*\(\s*\)/.test(src) && /ghost/i.test(src));

  // 15) Theme toggle button flips light/dark live
  await reset({});
  const t0 = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  await page.click('#theme-btn'); await sleep(page, 30);
  const t1 = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  rec('theme: toggle button flips theme', t0 !== t1 && ['light', 'dark'].includes(t1), `${t0}->${t1}`);

  // 16) prefers-color-scheme light context → starts light
  const lctx = await browser.newContext({ colorScheme: 'light' });
  const lpage = await lctx.newPage();
  await lpage.goto(URL);
  await lpage.waitForFunction(() => !!window.__TETRIS__);
  const lt = await lpage.evaluate(() => document.documentElement.getAttribute('data-theme'));
  rec('theme: prefers-color-scheme light → initial light', lt === 'light', `data-theme=${lt}`);
  await lctx.close();

  // 17) No console / page errors over the whole run
  rec('runtime: zero console/page errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

  // ── Screenshots (visual proof: layout, ghost, both themes) ─────────────────
  await reset({ seed: 5 }); await setG(true);
  await press('ArrowLeft'); await press('ArrowUp'); await sleep(page, 60);
  await page.screenshot({ path: resolve(__dirname, 'shot-dark.png') });
  await page.click('#theme-btn'); await sleep(page, 60);
  await page.screenshot({ path: resolve(__dirname, 'shot-light.png') });

  await browser.close();

  const fails = results.filter(r => !r.ok);
  console.log(`\n──────────────────────────────────────────`);
  console.log(`RESULT: ${results.length - fails.length}/${results.length} passed`);
  if (fails.length) { console.log('FAILURES:'); fails.forEach(f => console.log('  ✗ ' + f.name + (f.detail ? '  — ' + f.detail : ''))); }
  process.exit(fails.length ? 1 : 0);
}

main().catch(e => { console.error('HARNESS ERROR:', e); process.exit(2); });
