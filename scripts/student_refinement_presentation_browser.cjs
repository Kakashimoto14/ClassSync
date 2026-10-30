/* Browser regression against the local read-only artifact, never a live fallback. */
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
async function main() {
  const phase = process.argv[2];
  assert(['before', 'after'].includes(phase));
  const imageRoot =
    'C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb';
  const tag = Date.now();
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  const errors = [],
    api = [],
    screenshots = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) api.push(request.url());
  });
  await page.clock.setFixedTime(new Date('2026-10-30T08:15:00+08:00'));
  try {
    await page.goto('http://127.0.0.1:5188/dev/role-preview');
    await page.getByRole('button', { name: 'Open student demo' }).click();
    await page.locator('.student-next h3 button').waitFor();
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const file = path.join(imageRoot, `student-refinement-${tag}-${phase}-home-${width}.png`);
      await page.screenshot({ path: file, fullPage: true });
      screenshots.push(file);
    }
    if (phase === 'after') {
      assert.equal(await page.getByRole('combobox').count(), 0);
      assert.equal(await page.locator('.student-agenda-row').count(), 3);
      assert.equal(await page.getByText('In progress', { exact: true }).count(), 1);
      await page.getByRole('link', { name: 'View full schedule' }).first().click();
      for (const width of [360, 390, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.locator('.ux-agenda-row').first().waitFor();
        assert.equal(await page.locator('.ux-agenda-row').count(), 3);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        const file = path.join(
          imageRoot,
          `student-refinement-${tag}-${phase}-schedule-${width}.png`,
        );
        await page.screenshot({ path: file, fullPage: true });
        screenshots.push(file);
      }
      await page.locator('.ux-agenda-row').first().focus();
      await page.keyboard.press('Enter');
      await page.getByRole('dialog').waitFor();
      await page.keyboard.press('Escape');
      assert(
        await page
          .locator('.ux-agenda-row')
          .first()
          .evaluate((node) => node === document.activeElement),
      );
      await page.getByRole('button', { name: 'Next week' }).click();
      assert.equal(new URL(page.url()).searchParams.get('date'), '2026-11-06');
      await page.reload();
      await page.locator('.ux-agenda-row').first().waitFor();
      assert.equal(await page.locator('.ux-agenda-row').count(), 3);
      await page.goBack();
      await page.getByRole('link', { name: 'Sat, Oct 31' }).click();
      await page.getByText('No classes on this day.').waitFor();
      await page.getByRole('button', { name: 'Today', exact: true }).click();
      await page.getByText('Schedule options', { exact: true }).click();
      await page.getByLabel('Calendar view').selectOption('month');
      await page.getByRole('navigation', { name: 'Month dates' }).waitFor();
      await page.getByLabel('Calendar view').selectOption('day');
      assert.equal(await page.locator('.ux-agenda-row').count(), 3);
      await page.goto('http://127.0.0.1:5188/student/rooms?schedule=1');
      await page.getByRole('searchbox', { name: 'Search rooms' }).fill('LAB-201');
      await page.getByRole('heading', { name: 'LAB-201' }).waitFor();
      assert.equal(await page.getByRole('heading', { name: 'LAB-202' }).count(), 0);
      await page.getByRole('link', { name: 'Room details', exact: true }).click();
      await page.reload();
      await page.getByRole('heading', { name: 'LAB-201' }).waitFor();
      await page.goto('http://127.0.0.1:5188/student/notifications');
      await page.getByRole('heading', { name: 'Schedule updates', exact: true }).waitFor();
      await page.getByText('No changes flagged in your current schedule.').waitFor();
    }
    if (phase === 'after') {
      for (const role of ['teacher', 'administrator']) {
        await page.goto('http://127.0.0.1:5188/dev/role-preview');
        await page.getByRole('button', { name: `Open ${role} demo` }).click();
        await page.getByRole('main').getByRole('heading', { level: 1 }).waitFor();
        await page.goto(
          'http://127.0.0.1:5188/' + (role === 'teacher' ? 'teacher/schedule' : 'admin/calendar'),
        );
        await page.locator('.ux-agenda-row').first().waitFor();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      }
    }
    assert.deepEqual(api, []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      `docs/production/local-20261029/student-refinement-${phase}-browser.json`,
      JSON.stringify(
        {
          phase,
          screenshots,
          api,
          errors,
          widths: [360, 390, 768, 1024, 1440],
          clock: '2026-10-30T08:15:00+08:00',
          pass: true,
        },
        null,
        2,
      ),
    );
    console.log(JSON.stringify({ phase, screenshots, pass: true }));
  } finally {
    await browser.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
