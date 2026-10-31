/* Owned local fixture only. No product emulator switch or cloud access. */
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const assert = require('node:assert/strict');
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const root = fs.realpathSync(config.root);
  const evidenceTag = path.basename(root);
  const viteVersion = require('vite/package.json').version;
  assert(/^classsync-auth-run-[a-f0-9]{32}$/.test(path.basename(root)));
  const marker = JSON.parse(fs.readFileSync(path.join(root, 'owned-auth.json'), 'utf8'));
  assert.equal(marker.project, config.project);
  assert.equal(marker.endpoint, config.authEndpoint);
  assert(config.project.startsWith('demo-'));
  assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(config.gateway));
  const repo = path.resolve(__dirname, '..');
  Object.assign(process.env, {
    VITE_CLASSSYNC_MODE: 'institutional',
    VITE_ENABLE_ROLE_PREVIEW: 'false',
    VITE_ENABLE_PRESENTATION_SAMPLE: 'false',
    VITE_API_BASE_URL: '/api/v1',
    VITE_FIREBASE_API_KEY: 'synthetic-emulator-key',
    VITE_FIREBASE_AUTH_DOMAIN: config.project + '.firebaseapp.com',
    VITE_FIREBASE_PROJECT_ID: config.project,
    VITE_FIREBASE_STORAGE_BUCKET: config.project + '.appspot.com',
    VITE_FIREBASE_MESSAGING_SENDER_ID: '1234567890',
    VITE_FIREBASE_APP_ID: 'synthetic-emulator-app',
    CLASSSYNC_GATEWAY_URL: config.gateway,
  });
  delete process.env.CLASSSYNC_BUILD_TARGET;
  process.chdir(path.join(repo, 'apps/web'));
  const { createServer } = await import('vite');
  const reservation = net.createServer();
  await new Promise((resolve, reject) => {
    reservation.once('error', reject);
    reservation.listen(0, '127.0.0.1', resolve);
  });
  const port = reservation.address().port;
  await new Promise((resolve) => reservation.close(resolve));
  const vite = await createServer({
    root: path.join(repo, 'apps/web'),
    configFile: path.join(repo, 'apps/web/vite.config.ts'),
    server: { host: '127.0.0.1', port, strictPort: true },
    logLevel: 'error',
    plugins: [
      {
        name: 'owned-student-emulator',
        enforce: 'pre',
        transform(code, id) {
          if (id.replaceAll('\\', '/').endsWith('/src/lib/firebase.ts'))
            return {
              code:
                code +
                `\nimport {getAuth as qaAuth,connectAuthEmulator as qaConnect} from 'firebase/auth';if(firebaseApp)qaConnect(qaAuth(firebaseApp),${JSON.stringify('http://' + config.authEndpoint)},{disableWarnings:true});`,
              map: null,
            };
        },
      },
    ],
  });
  let browser, page;
  let phase = 'healthy';
  const runtimeErrors = [],
    consoleErrors = [],
    apiStatuses = [],
    screenshots = [];
  const imageRoot =
    'C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb';
  try {
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    console.log('Owned Student frontend: ' + origin + ' · Vite ' + viteVersion);
    // Prepare Vite's initial module transform before measuring browser interactions.
    assert((await fetch(origin + '/src/main.tsx', { signal: AbortSignal.timeout(30000) })).ok);
    browser = await chromium.launchPersistentContext(path.join(root, 'student-chrome'), {
      channel: 'chrome',
      headless: true,
      viewport: { width: 1440, height: 1000 },
      ignoreDefaultArgs: ['--disable-extensions'],
      args: ['--enable-unsafe-extension-debugging'],
    });
    await browser.route('**/*', (route) =>
      ['127.0.0.1', 'localhost', '[::1]'].includes(new URL(route.request().url()).hostname) ||
      route.request().url().startsWith('chrome-extension:')
        ? route.continue()
        : route.abort(),
    );
    page = await browser.newPage();
    page.on('pageerror', (error) => runtimeErrors.push(error.message));
    page.on('console', (message) => {
      if (
        message.type() === 'error' &&
        !/Failed to load resource:.*(?:401|403|503|ERR_INTERNET_DISCONNECTED)|ERR_INTERNET_DISCONNECTED/.test(
          message.text(),
        )
      )
        consoleErrors.push(message.text());
    });
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/'))
        apiStatuses.push({
          at: Date.now(),
          phase,
          method: response.request().method(),
          url: response.url(),
          path: new URL(response.url()).pathname,
          status: response.status(),
          requestId: response.headers()['x-request-id'],
        });
    });
    const control = async (action) => {
      assert(/^http:\/\/127\.0\.0\.1:\d+\/fixture$/.test(config.control));
      const response = await fetch(config.control, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Owned-Fixture': config.nonce },
        body: JSON.stringify({ action }),
      });
      assert.equal(response.status, 200);
    };
    const text = (name) => page.getByText(name, { exact: true }).waitFor();
    const shot = async (name) => {
      const file = path.join(imageRoot, `p4-stability-${evidenceTag}-${name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      screenshots.push(file);
    };
    await page.goto(origin + '/student/dashboard', { waitUntil: 'domcontentloaded' });
    await text('Signed out');
    await page.getByLabel('University email').fill(config.email);
    await page.getByLabel('Password', { exact: true }).fill(config.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await text('Student membership verified');
    await page.getByRole('button', { name: 'Check Teacher access' }).click();
    await text('Current membership required');
    await page.getByRole('button', { name: 'Check Student access' }).click();
    await text('Student membership verified');
    await page.getByRole('link', { name: 'Open Student workspace' }).click();
    await page.getByRole('heading', { name: 'Your next class' }).waitFor();
    await page.locator('.student-next h3 button').waitFor();
    assert((await page.title()).includes('ClassSync'));
    assert.equal(new URL(page.url()).pathname, '/student/dashboard');
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
    assert(
      (await page.locator('[data-published-version]').getAttribute('data-published-version'))
        .length > 0,
    );
    assert.equal(await page.getByText('Sample preview', { exact: false }).count(), 0);
    const className = await page.locator('.student-next h3 button').innerText();
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await shot('student-after-' + width);
    }
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    const lastAction = await page.getByRole('link', { name: 'Browse rooms' }).boundingBox();
    const bottomBar = await page
      .getByRole('navigation', { name: 'Mobile navigation' })
      .boundingBox();
    assert(lastAction && bottomBar && lastAction.y + lastAction.height <= bottomBar.y);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.locator('.student-next h3 button').focus();
    await page.keyboard.press('Enter');
    await page.getByRole('dialog').waitFor();
    await page.keyboard.press('Escape');
    assert(
      await page
        .locator('.student-next h3 button')
        .evaluate((node) => node === document.activeElement),
    );
    await page.locator('.student-next h3 button').click();
    await page.getByRole('link', { name: 'Open Room Details' }).click();
    assert(new URL(page.url()).searchParams.get('id'));
    await page.getByRole('link', { name: 'Back to Rooms' }).waitFor();
    await page.reload();
    await page.getByRole('link', { name: 'Back to Rooms' }).waitFor();
    await page.goBack();
    await page.locator('.student-next h3 button').waitFor();
    await page.getByRole('link', { name: 'Browse rooms' }).click();
    await page.getByRole('heading', { name: 'Rooms', exact: true }).waitFor();
    await page
      .getByText('Rooms in your selected schedule. Physical availability is not confirmed.', {
        exact: true,
      })
      .first()
      .waitFor();
    assert((await page.locator('.student-room-card').count()) > 0);
    assert.equal(await page.getByText('PRRC 101', { exact: true }).count(), 0);
    await page.getByRole('button', { name: 'All rooms', exact: true }).click();
    await page.getByRole('heading', { name: 'Room directory unavailable' }).waitFor();
    assert.equal(await page.getByText('PRRC 101', { exact: true }).count(), 0);
    await page.getByRole('button', { name: 'My rooms', exact: true }).click();
    await page.locator('.student-room-card').first().waitFor();
    await page.goBack();
    await page.getByRole('heading', { name: 'Room directory unavailable' }).waitFor();
    await page.goBack();
    await page.locator('.student-room-card').first().waitFor();
    await page.goBack();
    await page.locator('.student-next h3 button').waitFor();
    await page.goForward();
    await page.getByRole('heading', { name: 'Rooms', exact: true }).waitFor();
    await page.goto(origin + '/student/schedule');
    await page
      .locator('[data-published-version]')
      .filter({ has: page.locator('.ux-agenda-row') })
      .waitFor();
    await page.reload();
    await page
      .locator('[data-published-version]')
      .filter({ has: page.locator('.ux-agenda-row') })
      .waitFor();
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await shot('schedule-after-' + width);
    }
    await page.getByRole('button', { name: 'Next week' }).click();
    const nextDate = new URL(page.url()).searchParams.get('date');
    assert(nextDate);
    await page.reload();
    await page
      .getByRole('link', {
        name: new Intl.DateTimeFormat('en', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          timeZone: 'UTC',
        }).format(new Date(nextDate + 'T00:00:00Z')),
      })
      .waitFor();
    await page.getByRole('button', { name: 'Previous week' }).click();
    await page.getByRole('button', { name: 'Today', exact: true }).click();
    await page.goto(origin + '/student/notifications');
    await page.getByRole('heading', { name: 'Schedule updates', exact: true }).waitFor();
    await page
      .getByText('Notifications are not available. Check your schedule for changes.')
      .waitFor();
    await page.goto(origin + '/student/dashboard');
    await page.locator('.student-next h3 button').waitFor();
    await browser.setOffline(true);
    await text('You are offline');
    assert.equal(await page.locator('.student-next').count(), 0);
    await shot('offline');
    await browser.setOffline(false);
    await page.locator('.student-next h3 button').waitFor();
    let release;
    const held = new Promise((resolve) => {
      release = resolve;
    });
    await page.route('**/api/v1/timetables/**', async (route) => {
      await held;
      await route.continue();
    });
    await page.reload();
    await page.getByText('Loading your timetable…', { exact: true }).waitFor();
    await shot('loading');
    release();
    await page.unrouteAll({ behavior: 'wait' });
    await page.locator('.student-next h3 button').waitFor();
    phase = 'intentional-outage';
    await control('outage');
    await page.reload();
    await page.getByRole('heading', { name: 'Your timetable is unavailable' }).waitFor();
    assert.equal(await page.locator('.student-next').count(), 0);
    await shot('unavailable');
    await control('recover');
    phase = 'healthy';
    await page.getByRole('button', { name: 'Try again' }).click();
    await page.locator('.student-next h3 button').waitFor();
    await page.route('**/api/v1/timetables/**', (route) =>
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: '{"error":{"message":"Owned denial"}}',
      }),
    );
    await page.reload();
    await page.getByRole('heading', { name: 'Your schedule is not accessible' }).waitFor();
    assert.equal(await page.locator('.student-next').count(), 0);
    await shot('denied');
    await page.unroute('**/api/v1/timetables/**');
    await page.reload();
    await page.locator('.student-next h3 button').waitFor();
    await control('revoke');
    await page.reload();
    await text('Current membership required');
    assert.equal(await page.locator('.student-next').count(), 0);
    await shot('membership-revoked');
    await control('activate');
    await page.getByRole('button', { name: 'Check Student access' }).click();
    await page.locator('.student-next h3 button').waitFor();
    await control('unassign');
    await page.reload();
    // An unassigned identity has no visible period; a restored formerly-selected
    // period can also receive an actual projection403. Both must hide classes.
    await page
      .getByRole('heading', {
        name: /^(No schedule available yet|Your schedule is not accessible)$/,
      })
      .waitFor();
    assert.equal(await page.locator('.student-next').count(), 0);
    await shot('unassigned');
    await control('assign');
    await page.reload();
    await page.locator('.student-next h3 button').waitFor();
    // Actual Chrome origin zoom; neither CSS zoom nor device-scale emulation.
    const extension = path.join(root, 'student-zoom');
    fs.mkdirSync(extension);
    fs.writeFileSync(
      path.join(extension, 'manifest.json'),
      JSON.stringify({
        manifest_version: 3,
        name: 'Owned Student zoom',
        version: '1.0',
        permissions: ['tabs'],
        host_permissions: ['http://127.0.0.1/*'],
      }),
    );
    fs.writeFileSync(path.join(extension, 'zoom.html'), '<!doctype html><title>Owned zoom</title>');
    const cdp = await browser.browser().newBrowserCDPSession();
    const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
    const zoom = await browser.newPage();
    await zoom.goto(`chrome-extension://${loaded.id}/zoom.html`);
    const zoomFactor = await zoom.evaluate(async (origin) => {
      const tabs = await chrome.tabs.query({ url: origin + '/student/dashboard' });
      await chrome.tabs.setZoom(tabs[0].id, 2);
      return chrome.tabs.getZoom(tabs[0].id);
    }, origin);
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 2);
    await page.locator('.student-next h3 button').waitFor();
    assert.equal(zoomFactor, 2);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const nativePixels = await (
      await browser.newCDPSession(page)
    ).send('Page.captureScreenshot', { captureBeyondViewport: false });
    const zoomFile = path.join(imageRoot, `p4-stability-${evidenceTag}-student-native-200.png`);
    fs.writeFileSync(zoomFile, Buffer.from(nativePixels.data, 'base64'));
    screenshots.push(zoomFile);
    await page.goto(origin + '/student/schedule');
    await page.locator('.ux-agenda-row').first().waitFor();
    assert(
      await page.evaluate(
        () => devicePixelRatio === 2 && document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    const schedulePixels = await (
      await browser.newCDPSession(page)
    ).send('Page.captureScreenshot', { captureBeyondViewport: false });
    const scheduleZoomFile = path.join(
      imageRoot,
      `p4-stability-${evidenceTag}-schedule-native-200.png`,
    );
    fs.writeFileSync(scheduleZoomFile, Buffer.from(schedulePixels.data, 'base64'));
    screenshots.push(scheduleZoomFile);
    await page.goto(origin + '/student/dashboard');
    await page.locator('.student-next h3 button').waitFor();
    await zoom.evaluate(async (origin) => {
      for (const tab of await chrome.tabs.query({ url: origin + '/*' }))
        await chrome.tabs.setZoom(tab.id, 1);
    }, origin);
    await zoom.close();
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.getByRole('button', { name: 'Open navigation menu' }).click();
    await page.getByRole('dialog').waitFor();
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await text('Signed out');
    await page.goto(origin + '/student/dashboard');
    await text('Signed out');
    assert.equal(await page.locator('.student-next').count(), 0);
    await page.getByLabel('University email').fill('student-4@synthetic.invalid');
    await page.getByLabel('Password', { exact: true }).fill(config.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await text('Current membership required');
    assert.equal(await page.locator('.student-next').count(), 0);
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await text('Signed out');
    assert.deepEqual(
      apiStatuses.filter((r) => r.status === 503 && r.phase !== 'intentional-outage'),
      [],
    );
    assert.deepEqual(runtimeErrors, []);
    assert.deepEqual(consoleErrors, []);
    fs.writeFileSync(
      path.join(root, 'student-browser-result.json'),
      JSON.stringify(
        {
          actualAuthGatewayPostgres: true,
          viteVersion,
          syntheticFixture: true,
          widths: [360, 390, 768, 1024, 1440],
          mobileBottomNavigationClearance: true,
          nativeZoom: zoomFactor,
          className,
          apiStatuses,
          runtimeErrors,
          consoleErrors,
          screenshots,
          manualScreenReader: 'unverified',
          outageAndDenial:
            'real stopped Scheduling endpoint503/recovery; injected403 and audited PG revocation/unassignment',
          productionAcceptance: false,
        },
        null,
        2,
      ),
    );
    console.log('Student browser journey passed');
  } catch (error) {
    if (page) {
      console.error('API statuses:', JSON.stringify(apiStatuses));
      console.error(
        'Request details:',
        await page
          .locator('.student-panel details')
          .textContent()
          .catch(() => 'none'),
      );
      await page
        .screenshot({
          path: path.join(imageRoot, `p4-stability-${evidenceTag}-failure.png`),
          fullPage: true,
        })
        .catch(() => {});
      console.error(
        await page
          .locator('body')
          .innerText()
          .catch(() => ''),
      );
    }
    throw error;
  } finally {
    if (browser) await browser.close();
    await vite.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
