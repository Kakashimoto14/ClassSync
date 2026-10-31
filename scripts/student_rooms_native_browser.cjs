/* Actual Chrome origin zoom and keyboard clearance against the local presentation. */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'classsync-student-zoom-focus-'));
  const extension = path.join(root, 'extension');
  fs.mkdirSync(extension);
  fs.writeFileSync(
    path.join(extension, 'manifest.json'),
    JSON.stringify({
      manifest_version: 3,
      name: 'Owned local zoom focus QA',
      version: '1.0',
      permissions: ['tabs'],
      host_permissions: ['http://127.0.0.1/*'],
    }),
  );
  fs.writeFileSync(
    path.join(extension, 'zoom.html'),
    '<!doctype html><title>Owned zoom focus</title>',
  );
  const context = await chromium.launchPersistentContext(path.join(root, 'profile'), {
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    ignoreDefaultArgs: ['--disable-extensions'],
    args: ['--enable-unsafe-extension-debugging'],
  });
  const page = await context.newPage();
  await page.clock.setFixedTime(new Date('2026-10-30T08:15:00+08:00'));
  const checks = [];
  try {
    await page.goto('http://127.0.0.1:5188/dev/role-preview');
    await page.getByRole('button', { name: 'Open student demo' }).click();
    await page.locator('.student-next h3 button').waitFor();
    const cdp = await context.browser().newBrowserCDPSession();
    const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
    const zoom = await context.newPage();
    await zoom.goto(`chrome-extension://${loaded.id}/zoom.html`);
    await zoom.evaluate(async () => {
      for (const tab of await chrome.tabs.query({ url: 'http://127.0.0.1:5188/*' }))
        await chrome.tabs.setZoom(tab.id, 2);
    });
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 2);
    async function clearance(locator, control) {
      assert(await locator.evaluate((node) => node === document.activeElement));
      const box = await locator.boundingBox();
      const nav = await page.getByRole('navigation', { name: 'Mobile navigation' }).boundingBox();
      assert(box.y >= 0 && box.y + box.height <= nav.y, JSON.stringify({ control, box, nav }));
      checks.push({ control, box, nav, fullyVisible: true });
    }
    await page.goto('http://127.0.0.1:5188/student/rooms?date=2026-10-30');
    await page.getByRole('link', { name: 'View LAB-201 details' }).waitFor();
    await page.getByRole('searchbox').focus();
    await page.keyboard.press('Tab');
    await clearance(
      page.getByRole('button', { name: 'My rooms', exact: true }),
      'My rooms category',
    );
    await page.getByRole('link', { name: 'View AVR-101 details' }).focus();
    await clearance(
      page.getByRole('link', { name: 'View AVR-101 details' }),
      'Last assigned room details',
    );
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    const viewport = await page.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      scrollY,
      visual: {
        height: visualViewport.height,
        offsetTop: visualViewport.offsetTop,
        pageTop: visualViewport.pageTop,
        scale: visualViewport.scale,
      },
      header: document.querySelector('.topbar').getBoundingClientRect().toJSON(),
      active: document.activeElement.getBoundingClientRect().toJSON(),
    }));
    // Scrolled native-zoom surface captures were misaligned. Capture the top viewport;
    // focused last-card clearance remains recorded separately above at the same zoom.
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForFunction(() => scrollY === 0);
    await page.screenshot({
      path: 'C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb/rooms-native-200.png',
    });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    fs.writeFileSync(
      'docs/production/student-rooms-20261030/native-focus.json',
      JSON.stringify(
        {
          nativeZoom: 2,
          devicePixelRatio: await page.evaluate(() => devicePixelRatio),
          checks,
          viewport,
          pass: true,
        },
        null,
        2,
      ),
    );
    console.log('Native 200% keyboard focus clears fixed navigation on Rooms.');
  } finally {
    await context.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
