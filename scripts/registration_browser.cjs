/* Real local scanner + Auth/Gateway/Scheduling/PostgreSQL. Synthetic fixtures only. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {
  chromium,
} = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const root = fs.realpathSync(config.root);
  assert.equal(path.dirname(root), fs.realpathSync(os.tmpdir()));
  assert.match(path.basename(root), /^classsync-auth-run-[a-f0-9]{32}$/);
  const marker = JSON.parse(fs.readFileSync(path.join(root, 'owned-auth.json'), 'utf8'));
  assert.equal(marker.project, config.project);
  assert.equal(marker.endpoint, config.authEndpoint);
  assert.match(config.gateway, /^http:\/\/127\.0\.0\.1:[0-9]+$/);
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
  const vite = await createServer({
    root: path.join(repo, 'apps/web'),
    configFile: path.join(repo, 'apps/web/vite.config.ts'),
    server: { host: '127.0.0.1', port: 0, strictPort: false },
    logLevel: 'error',
    plugins: [
      {
        name: 'owned-scanner-auth',
        enforce: 'pre',
        transform(code, id) {
          if (id.replaceAll('\\', '/').endsWith('/src/lib/firebase.ts'))
            return {
              code:
                code +
                `\nimport {getAuth as __auth,connectAuthEmulator as __connect} from 'firebase/auth';if(firebaseApp)__connect(__auth(firebaseApp),${JSON.stringify('http://' + config.authEndpoint)},{disableWarnings:true});`,
              map: null,
            };
        },
      },
    ],
  });
  let browser, page;
  const errors = [],
    statuses = [],
    screenshots = [];
  const network = [];
  const started = Date.now();
  const describeRequest = (request) => ({
    path: new URL(request.url()).pathname,
    type: request.resourceType(),
    elapsedMs: Date.now() - started,
  });
  try {
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    browser = await chromium.launchPersistentContext(path.join(root, 'scanner-chrome'), {
      channel: 'chrome',
      headless: true,
      viewport: { width: 1440, height: 1000 },
      ignoreDefaultArgs: ['--disable-extensions'],
      args: ['--enable-unsafe-extension-debugging'],
    });
    await browser.route('**/*', (route) => {
      const url = new URL(route.request().url());
      return url.protocol === 'chrome-extension:' ||
        ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
        ? route.continue()
        : route.abort();
    });
    page = await browser.newPage();
    page.on('request', (request) =>
      network.push({ event: 'request', ...describeRequest(request) }),
    );
    page.on('requestfinished', (request) =>
      network.push({ event: 'finished', ...describeRequest(request) }),
    );
    page.on('requestfailed', (request) =>
      network.push({
        event: 'failed',
        ...describeRequest(request),
        reason: request.failure()?.errorText,
      }),
    );
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/')) statuses.push(response.status());
    });
    const visible = (text) => page.getByText(text, { exact: true }).waitFor({ timeout: 15000 });
    const shot = async (name) => {
      await page.evaluate(() => window.scrollTo(0, 0));
      assert.match(await page.title(), /ClassSync/);
      assert.equal(await page.locator('vite-error-overlay').count(), 0);
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        'Horizontal overflow',
      );
      const file = path.join(config.imageRoot, `m2-${path.basename(root).slice(-8)}-${name}.png`);
      await page.screenshot({ path: file, fullPage: name !== 'native200' });
      screenshots.push(file);
    };
    const auth = origin + '/auth/login';
    const login = async (email) => {
      await page.goto(auth);
      await visible('Signed out');
      await page.getByRole('button', { name: 'Existing account', exact: true }).click();
      await page.getByLabel('University email', { exact: true }).fill(email);
      await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    };
    const logout = async () => {
      await page.goto(auth);
      await page.getByRole('button', { name: 'Sign out', exact: true }).click();
      await visible('Signed out');
    };
    const email = 'scanner-student@synthetic.invalid';
    await page.goto(auth);
    await visible('Signed out');
    await page.getByRole('button', { name: 'Create account', exact: true }).first().click();
    await page.getByLabel('University email', { exact: true }).fill(email);
    await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
    await page.locator('button[type=submit]').click();
    await page.getByRole('button', { name: 'I verified my email', exact: true }).waitFor();
    let code;
    const deadline = Date.now() + 5000;
    while (!code && Date.now() < deadline) {
      const data = await (
        await fetch(`http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`)
      ).json();
      code = [...data.oobCodes]
        .reverse()
        .find((item) => item.email === email && item.requestType === 'VERIFY_EMAIL');
      if (!code) await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert(code, 'Actual verification email was not requested');
    const verification = await fetch(
      `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:update?key=synthetic-emulator-key`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ oobCode: code.oobCode }),
      },
    );
    assert.equal(verification.status, 200);
    await page.getByRole('button', { name: 'I verified my email', exact: true }).click();
    await page.getByRole('link', { name: 'Scan registration form', exact: true }).click();
    await page
      .getByLabel('Choose a PDF or clear photo')
      .setInputFiles(path.join(root, 'synthetic-registration.pdf'));
    await page.getByLabel('Student number', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Student number', { exact: true }).inputValue(), 'SYN-001');
    const scanUrl = page.url();
    await page.getByLabel('Program', { exact: true }).fill(config.fixture.program);
    await page.getByLabel('Year level', { exact: true }).fill(String(config.fixture.year_level));
    for (let i = 0; i < 2; i++)
      await page.getByLabel('Course code', { exact: true }).nth(i).fill(config.fixture.codes[i]);
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('Your university must verify your student record before classes can be matched.');
    assert.equal(await page.getByRole('link', { name: 'View verified schedule' }).count(), 0);
    await page.getByRole('button', { name: 'Request student verification', exact: true }).click();
    await page
      .getByRole('status')
      .filter({ hasText: 'Your student record request is awaiting university verification.' })
      .waitFor();
    await logout();
    await login(config.adminEmail);
    await visible('Administrator membership verified');
    await page.getByRole('button', { name: 'Load account requests', exact: true }).click();
    await page
      .getByLabel('Identity verification reference', { exact: true })
      .fill('Disposable scanner identity verification control');
    await page.getByRole('button', { name: 'Approve student SYN-001', exact: true }).click();
    await visible('No pending student requests.');
    await logout();
    await login(email);
    await visible('Student membership verified');
    await page.goto(scanUrl);
    await page.getByLabel('Course code', { exact: true }).first().waitFor();
    assert.equal(
      await page.getByLabel('Course code', { exact: true }).first().inputValue(),
      config.fixture.codes[0],
    );
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('Your verified classes');
    assert((await page.locator('body').innerText()).includes('BSIT 1A')); // Raw document section2 was not converted to BSIT2A.
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('matched-' + width);
    }
    await page.getByLabel('Semester', { exact: true }).selectOption('second');
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('No authorized published enrollment was found for this academic term.');
    assert.equal(await page.getByRole('link', { name: 'View verified schedule' }).count(), 0);
    await page.getByLabel('Semester', { exact: true }).selectOption('first');
    await page.getByLabel('Course code', { exact: true }).first().fill('UNMATCHED');
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('Verification or matching needed');
    assert.equal(await page.getByRole('link', { name: 'View verified schedule' }).count(), 0);
    await page.getByLabel('Course code', { exact: true }).first().fill(config.fixture.codes[0]);
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('Your verified classes');
    const timetableResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname.startsWith('/api/v1/timetables/calendar/'),
    );
    await page.getByRole('link', { name: 'View verified schedule', exact: true }).click();
    await page.waitForURL('**/student/schedule?**');
    const timetable = await timetableResponse;
    assert.equal(timetable.status(), 200);
    const published = (await timetable.json()).data;
    assert(published.version, 'Missing published version');
    for (const code of config.fixture.codes) {
      const occurrence = published.occurrences.find((item) => item.subject.code === code);
      assert(occurrence, 'Verified offering missing from actual timetable: ' + code);
      await page.getByRole('button').filter({ hasText: occurrence.subject.name }).first().waitFor();
    }
    await page.getByText('Loading your schedule…', { exact: true }).waitFor({ state: 'hidden' });
    await shot('actual-published-timetable');
    await page.goto(scanUrl);
    await page.getByLabel('Student number', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Delete temporary scan', exact: true }).click();
    await visible('Your temporary scan was deleted.');
    await page
      .getByLabel('Choose a PDF or clear photo')
      .setInputFiles(path.join(root, 'synthetic-registration.png'));
    await page.getByLabel('Course code', { exact: true }).first().waitFor();
    assert.equal(await page.getByLabel('Student number', { exact: true }).inputValue(), 'SYN-OOI');
    await page.getByLabel('Student number', { exact: true }).fill('SYN-001');
    await page.getByLabel('Year level', { exact: true }).fill('1');
    for (let i = 0; i < 2; i++)
      await page.getByLabel('Course code', { exact: true }).nth(i).fill(config.fixture.codes[i]);
    await page.getByRole('button', { name: 'Find my classes', exact: true }).click();
    await visible('Your verified classes');
    await shot('ocr-corrected');
    const extension = path.join(root, 'scanner-zoom');
    fs.mkdirSync(extension);
    fs.writeFileSync(
      path.join(extension, 'manifest.json'),
      JSON.stringify({
        manifest_version: 3,
        name: 'Owned scanner zoom',
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
    const factor = await zoom.evaluate(async (origin) => {
      const [tab] = await chrome.tabs.query({ url: origin + '/student/registration-scanner*' });
      await chrome.tabs.setZoom(tab.id, 2);
      return chrome.tabs.getZoom(tab.id);
    }, origin);
    assert.equal(factor, 2);
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 2);
    const zoomLayout = await page.evaluate(async () => {
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return {
        width: innerWidth,
        ratio: devicePixelRatio,
        clipped: [
          ...document.querySelectorAll(
            '.registration-scanner input, .registration-scanner select, .registration-scanner button, .registration-scanner fieldset',
          ),
        ]
          .map((element) => element.getBoundingClientRect())
          .filter((rect) => rect.width && (rect.left < -1 || rect.right > innerWidth + 1)).length,
      };
    });
    assert.equal(zoomLayout.clipped, 0, 'Scanner controls clipped at native200');
    await shot('native200');
    await page.getByRole('button', { name: 'Delete temporary scan', exact: true }).focus();
    await page.keyboard.press('Enter');
    await visible('Your temporary scan was deleted.');
    assert.equal(errors.length, 0, JSON.stringify(errors));
    assert(!statuses.includes(503), 'Unexpected healthy503');
    fs.writeFileSync(
      path.join(root, 'registration-browser-result.json'),
      JSON.stringify(
        {
          browserPlugin: 'unavailable',
          runtime: 'existing Playwright/Chrome',
          flow: 'signup -> private PDF scan -> corrections -> pending verification -> Admin approval -> published matching -> real timetable -> local photo OCR correction',
          widths: [360, 390, 768, 1024, 1440],
          nativeZoom: factor,
          zoomLayout,
          wrongTermDenied: true,
          unmatchedPending: true,
          manualCorrectionsRestored: true,
          temporaryScansDeleted: true,
          errors,
          statuses,
          screenshots,
          manualScreenReader: 'unverified',
          productionAcceptance: false,
        },
        null,
        2,
      ),
    );
  } catch (error) {
    fs.writeFileSync(
      path.join(root, 'registration-failure-network.json'),
      JSON.stringify({ network, errors }, null, 2),
    );
    if (page && !page.isClosed()) {
      fs.writeFileSync(
        path.join(root, 'registration-failure-dom.txt'),
        await page.locator('body').innerText(),
      );
      await page.screenshot({
        path: path.join(config.imageRoot, `m2-${path.basename(root).slice(-8)}-failure.png`),
        fullPage: true,
      });
    }
    throw error;
  } finally {
    await browser?.close();
    await vite.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
