const { chromium } = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { artifactServer } = require('../../../scripts/lib/artifact-server.cjs');
const { verifyHosted } = require('../../../scripts/verify-hosted-presentation.cjs');
const { resolve } = require('node:path');
const { writeFileSync } = require('node:fs');
const assert = require('node:assert/strict');
const config = require('../../../vercel.json');

(async () => {
  const server = artifactServer(resolve('apps/web/dist'), config);
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  let browser;
  const evidence = { origin: `http://127.0.0.1:${server.address().port}`, journeys: [] };
  try {
    const http = await verifyHosted(evidence.origin, '39200a4f2ef3ec7557bc3c86127e674e260ca4fc');
    // A dirty local candidate must never pass the clean-release requirement.
    assert.deepEqual(http.failed, ['/release.json']);
    evidence.http = http;
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    for (const width of [360, 390, 768, 1024, 1440]) {
      for (const role of ['student', 'teacher', 'administrator']) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
        const page = await context.newPage();
        const errors = [], api = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
        page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) api.push(request.url()); });
        await page.goto(evidence.origin + '/dev/role-preview');
        await page.getByRole('button', { name: `Open ${role} demo`, exact: true }).click();
        const prefix = role === 'administrator' ? 'admin' : role;
        await page.waitForURL(`**/${prefix}/dashboard`);
        const heading = { student: 'Your day', teacher: 'Your teaching day',
          administrator: 'Scheduling overview' }[role];
        await page.getByRole('heading', { level: 1, name: heading, exact: true }).waitFor();
        await page.reload();
        await page.getByRole('heading', { level: 1, name: heading, exact: true }).waitFor();
        assert.equal(await page.getByRole('heading', { level: 1 }).innerText(), heading);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        assert.deepEqual(errors, []);
        assert.deepEqual(api, []);
        let screenshot = null;
        if ((width === 390 && role === 'student') || (width === 1440 && role === 'administrator')) {
          screenshot = `C:/Users/lenovo/.codex/visualizations/2026/10/25/01a17489-5bf8-7c93-adb1-44b9f3722009/p3a-web-session-${role}-${width}.png`;
          await page.screenshot({ path: screenshot, fullPage: false });
        }
        evidence.journeys.push({ role, width, title: await page.title(), heading, url: page.url(), refresh: true, overflow: false, errors, api, screenshot });
        await context.close();
      }
    }
  } finally {
    await browser?.close();
    await new Promise(done => server.close(done));
    writeFileSync(resolve(__dirname, 'p3a-web-session-browser.json'), JSON.stringify(evidence, null, 2) + '\n');
  }
  console.log(`${evidence.journeys.length} role/width journeys passed; dirty release correctly rejected`);
})().catch(error => { console.error(error); process.exitCode = 1; });


