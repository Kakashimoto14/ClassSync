/* Current local artifact visual capture, with deterministic synthetic time. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = 'docs/production/student-visual-20261030';
const imageRoot = 'C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb';
async function main() {
  const phase = process.argv[2];
  assert(['before', 'after'].includes(phase));
  fs.mkdirSync(base, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  const errors = [], api = [], screenshots = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('request', r => { if (new URL(r.url()).pathname.startsWith('/api/')) api.push(r.url()); });
  await page.clock.setFixedTime(new Date('2026-10-30T08:15:00+08:00'));
  const tag = Date.now();
  const scenes = [
    ['home', '/student/dashboard'],
    ['schedule', '/student/schedule?date=2026-10-30'],
    ['options', '/student/schedule?date=2026-10-30'],
    ['room-detail', '/student/rooms/detail?id=synthetic-student-room-1&date=2026-10-30&schedule=1'],
    ['schedule-rooms', '/student/rooms?schedule=1'],
    ['directory', '/student/rooms'],
    ['find-room', '/student/find-room'],
    ['alerts', '/student/notifications'],
    ['announcements', '/student/announcements'],
  ];
  try {
    await page.goto('http://127.0.0.1:5188/dev/role-preview');
    await page.getByRole('button', { name: 'Open student demo' }).click();
    await page.locator('.student-next h3 button').waitFor();
    for (const width of phase === 'before' ? [390, 1440] : [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const [scene, route] of scenes) {
        if (![390, 1440].includes(width) && !['home', 'schedule'].includes(scene)) continue;
        await page.goto('http://127.0.0.1:5188' + route);
        await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor();
        if (['home', 'schedule-rooms', 'room-detail', 'alerts', 'schedule', 'options'].includes(scene)) {
          await page.locator('[data-published-version]').waitFor();
          await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'));
        }
        if (scene === 'home') await page.locator('.student-next h3 button').waitFor();
        if (scene === 'schedule' || scene === 'options') await page.locator('.ux-agenda-row').first().waitFor();
        if (scene === 'options') await page.getByText('Schedule options', { exact: true }).click();
        await page.evaluate(() => document.fonts.ready);
        if (phase === 'after') assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), scene + ':' + width);
        const file = path.join(imageRoot, `campus-companion-${tag}-${phase}-${scene}-${width}.png`);
        await page.screenshot({ path: file, fullPage: true });
        screenshots.push({ scene, width, file });
      }
    }
    if (phase === 'after') {
      assert.deepEqual(errors, []); assert.deepEqual(api, []);
    }
    fs.writeFileSync(path.join(base, `${phase}-browser.json`), JSON.stringify({ phase, screenshots, errors, api, clock: '2026-10-30T08:15:00+08:00', pass: true }, null, 2));
    console.log(JSON.stringify({ phase, tag, captures: screenshots.length, errors, api }));
  } finally { await browser.close(); }
}
main().catch(e => { console.error(e); process.exitCode = 1; });
