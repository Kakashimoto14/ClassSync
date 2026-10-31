const fs = require('node:fs');
const assert = require('node:assert/strict');
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root =
  'C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb';
(async () => {
  const phase = process.argv[2] || 'before';
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  const errors = [],
    shots = [],
    apiRequests = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
  });
  await page.clock.setFixedTime(new Date('2026-10-30T08:15:00+08:00'));
  try {
    await page.goto('http://127.0.0.1:5188/dev/role-preview');
    await page.getByRole('button', { name: 'Open student demo' }).click();
    for (const width of phase === 'before' ? [390, 1440] : [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 950 });
      await page.goto('http://127.0.0.1:5188/student/rooms?date=2026-10-30');
      await page.getByRole('heading', { level: 1 }).waitFor();
      if (phase !== 'before') {
        await page.getByRole('link', { name: 'View LAB-201 details' }).waitFor();
        assert.equal(await page.locator('.student-room-card').count(), 3);
        await page.getByRole('button', { name: 'All rooms', exact: true }).click();
        await page.waitForFunction(
          () => document.querySelectorAll('.student-room-card').length === 59,
        );
        assert.equal(await page.locator('.student-room-card').count(), 59);
        await page.getByRole('searchbox').fill('VGA');
        await page.waitForFunction(
          () => document.querySelectorAll('.student-room-card').length === 1,
        );
        assert.equal(await page.locator('.student-room-card').count(), 1);
        await page.getByRole('button', { name: 'Clear search' }).click();
        await page.getByRole('button', { name: 'Labs', exact: true }).click();
        await page.getByText('Lab information is not confirmed').waitFor();
        await page.getByRole('button', { name: 'My rooms', exact: true }).click();
        await page.getByRole('link', { name: 'View LAB-201 details' }).waitFor();
      }
      const file = `${root}/rooms-${phase}-${width}.png`;
      await page.screenshot({ path: file, fullPage: true });
      shots.push(file);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      if (phase !== 'before') {
        if ([390, 1440].includes(width)) {
          await page.getByRole('button', { name: 'All rooms', exact: true }).click();
          await page.waitForFunction(
            () => document.querySelectorAll('.student-room-card').length === 59,
          );
          const directory = `${root}/rooms-directory-${width}.png`;
          await page.screenshot({ path: directory });
          shots.push(directory);
          await page.getByRole('button', { name: 'My rooms', exact: true }).click();
          await page.getByRole('link', { name: 'View LAB-201 details' }).waitFor();
        }
        await page.getByRole('link', { name: 'View LAB-201 details' }).click();
        await page.getByRole('heading', { name: 'LAB-201', exact: true }).waitFor();
        if ([390, 1440].includes(width)) {
          const detail = `${root}/rooms-detail-${width}.png`;
          await page.screenshot({ path: detail });
          shots.push(detail);
        }
        const schedule = new URL(
          await page.getByRole('link', { name: 'Back to Schedule' }).getAttribute('href'),
          page.url(),
        );
        assert.equal(schedule.searchParams.get('date'), '2026-10-30');
        await page.reload();
        await page.getByRole('heading', { name: 'LAB-201', exact: true }).waitFor();
        await page
          .getByRole('button', { name: /Advanced Database Systems/ })
          .first()
          .click();
        await page.getByRole('dialog').waitFor();
        await page.keyboard.press('Escape');
        await page.getByRole('link', { name: 'Back to Rooms' }).click();
        await page.getByRole('link', { name: 'View LAB-201 details' }).waitFor();
      }
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(apiRequests, []);
    fs.writeFileSync(
      `docs/production/student-rooms-20261030/browser-${phase}.json`,
      JSON.stringify({ shots, errors, apiRequests }, null, 2),
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
