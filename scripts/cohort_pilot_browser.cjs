/* Synthetic API-render fixture only. PostgreSQL acceptance is a separate qualifier. */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
async function main() {
  const root = path.resolve(__dirname, '..');
  const out = path.join(root, 'docs/production/cohort-pilot-20261031');
  const fixture = JSON.parse(fs.readFileSync(path.join(out, 'browser-fixture.json'), 'utf8'));
  const catalog = JSON.parse(
    fs.readFileSync(
      path.join(root, 'packages/api-contracts/classync_contracts/catalogs/curriculum-review.json'),
      'utf8',
    ),
  );
  catalog.program_ids = {
    BSIT: 'bsit',
    BSCPE: 'bscpe',
    'BS ENTREP': 'bse',
    'BSBA HRM': 'bsba-hrm',
    BECED: 'beed-eced',
    'BEED GENERALIST': 'beed-gen',
    'BSED SCIENCE': 'bsed-sci',
    'BTLED ICT': 'btled-ict',
  };
  Object.assign(process.env, {
    VITE_CLASSSYNC_MODE: 'sandbox',
    VITE_ENABLE_ROLE_PREVIEW: 'true',
    VITE_ENABLE_PRESENTATION_SAMPLE: 'false',
    VITE_API_BASE_URL: '/api/v1',
  });
  delete process.env.CLASSSYNC_BUILD_TARGET;
  process.chdir(path.join(root, 'apps/web'));
  const { createServer } = await import('vite');
  const vite = await createServer({
    root: path.join(root, 'apps/web'),
    configFile: path.join(root, 'apps/web/vite.config.ts'),
    server: { host: '127.0.0.1', port: 0, strictPort: true },
    logLevel: 'error',
  });
  let browser;
  const errors = [],
    screenshots = [],
    consoleMessages = [],
    blockedExternal = [];
  try {
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'classsync-cohort-browser-'));
    browser = await chromium.launchPersistentContext(profile, {
      channel: 'chrome',
      headless: true,
      viewport: { width: 1440, height: 1000 },
      ignoreDefaultArgs: ['--disable-extensions'],
      args: ['--enable-unsafe-extension-debugging'],
    });
    await browser.addInitScript(() =>
      sessionStorage.setItem(
        'classsync.preview.v1',
        JSON.stringify({ version: 1, role: 'administrator', startedAt: Date.now() }),
      ),
    );
    await browser.route('**/*', async (route) => {
      const url = new URL(route.request().url());
      if (url.protocol === 'chrome-extension:') return route.continue();
      if (url.hostname !== '127.0.0.1') {
        blockedExternal.push(url.origin);
        return route.abort();
      }
      if (!url.pathname.startsWith('/api/')) return route.continue();
      const endpoint = url.pathname;
      let data;
      if (endpoint.endsWith('/curriculum-catalog')) data = catalog;
      else if (endpoint.endsWith('/periods')) data = { periods: [fixture.period] };
      else if (endpoint.endsWith('/periods/' + fixture.period.id)) data = fixture;
      else if (endpoint.endsWith('/readiness'))
        data = {
          period: fixture.period,
          ready: false,
          issues: [
            {
              severity: 'blocking',
              code: 'curriculum_unreviewed',
              message: 'Unreviewed source: Registrar confirmation required.',
            },
          ],
          inputs: null,
          programs: 1,
          subjects: 27,
          sections: 4,
          faculty: 81,
          assigned_faculty: 81,
          offerings: 27,
          eligible_resources: 4,
        };
      else
        return route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: { message: 'No synthetic route fixture' } }),
        });
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ data }) });
    });
    const page = await browser.newPage();
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => {
      if (['error', 'warning'].includes(m.type()))
        consoleMessages.push({ level: m.type(), text: m.text() });
    });
    await page.goto(origin + '/admin/subjects?period=' + fixture.period.id, {
      waitUntil: 'domcontentloaded',
      timeout: 15000,
    });
    await page.getByRole('button', { name: 'Add Subject', exact: true }).click();
    assert.match(await page.title(), /ClassSync/i);
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
    const version = catalog.versions.find((v) => v.program === 'BSIT' && v.entry_cohort === '2024');
    const course = catalog.courses.find(
      (c) => c.curriculum_version_id === version.id && c.subject_code === 'ITIASE1',
    );
    await page
      .getByRole('combobox', { name: 'Curriculum source', exact: true })
      .selectOption(version.id);
    await page.getByRole('combobox', { name: 'Exact curriculum course' }).selectOption(course.id);
    assert.equal(
      await page.getByRole('textbox', { name: 'Subject code', exact: true }).inputValue(),
      'ITIASE1',
    );
    assert.equal(
      await page.getByRole('spinbutton', { name: 'Required weekly contact minutes' }).inputValue(),
      '',
    );
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page
        .getByRole('group', { name: 'Versioned curriculum review' })
        .scrollIntoViewIfNeeded();
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        'horizontal overflow at ' + width,
      );
      const file = path.join(out, `admin-curriculum-${width}.png`);
      await page.screenshot({ path: file });
      screenshots.push(file);
    }
    await page.getByRole('combobox', { name: 'Curriculum source', exact: true }).focus();
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement?.tagName), 'SELECT');
    const extension = path.join(profile, 'zoom');
    fs.mkdirSync(extension);
    fs.writeFileSync(
      path.join(extension, 'manifest.json'),
      JSON.stringify({
        manifest_version: 3,
        name: 'Owned cohort zoom',
        version: '1.0',
        permissions: ['tabs'],
        host_permissions: ['http://127.0.0.1/*'],
      }),
    );
    fs.writeFileSync(
      path.join(extension, 'zoom.html'),
      '<!doctype html><title>Owned cohort zoom</title>',
    );
    const cdp = await browser.browser().newBrowserCDPSession();
    const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
    const zoom = await browser.newPage();
    await zoom.goto(`chrome-extension://${loaded.id}/zoom.html`);
    const factor = await zoom.evaluate(async (origin) => {
      const tabs = await chrome.tabs.query({ url: origin + '/admin/subjects*' });
      await chrome.tabs.setZoom(tabs[0].id, 2);
      return chrome.tabs.getZoom(tabs[0].id);
    }, origin);
    assert.equal(factor, 2);
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 2);
    await page
      .getByRole('combobox', { name: 'Curriculum source', exact: true })
      .evaluate((element) => element.scrollIntoView({ block: 'center' }));
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    assert(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      'native200 overflow',
    );
    const zoomImage = path.join(out, 'admin-curriculum-native200.png');
    await page.screenshot({ path: zoomImage, fullPage: true });
    screenshots.push(zoomImage);
    const zoomSource = path.join(out, 'admin-curriculum-native200-source.png');
    await page
      .getByRole('group', { name: 'Versioned curriculum review' })
      .screenshot({ path: zoomSource });
    screenshots.push(zoomSource);
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.getByRole('button', { name: 'Validate Readiness' }).click();
    await page.getByText('Affected records and validation details', { exact: true }).click();
    await page.getByText('Unreviewed source: Registrar confirmation required.').waitFor();
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(out, 'browser-evidence.json'),
      JSON.stringify(
        {
          status: 'PASS',
          mode: 'synthetic API-render fixture',
          browser_plugin: 'not available; regular Playwright',
          widths: [360, 390, 768, 1024, 1440],
          native_zoom: factor,
          keyboard: true,
          exact_code: 'ITIASE1',
          minutes_left_empty: true,
          readiness_blocker: true,
          page_errors: errors,
          console_messages: consoleMessages,
          blocked_external: blockedExternal,
          screenshots,
          connected_pg_http: false,
        },
        null,
        2,
      ),
    );
    console.log(
      'Admin synthetic rendered catalog/selection/readiness PASS; five widths/native200/keyboard',
    );
  } finally {
    if (browser) await browser.close();
    await vite.close();
  }
}
main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
