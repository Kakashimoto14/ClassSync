/* Actual synthetic Auth/Gateway/PostgreSQL account UI. Browser plugin unavailable. */
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
  assert.equal(marker.endpoint, config.authEndpoint);
  assert.equal(marker.project, config.project);
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
        name: 'owned-onboarding-emulator',
        enforce: 'pre',
        transform(code, id) {
          if (id.replaceAll('\\', '/').endsWith('/src/lib/firebase.ts'))
            return {
              code:
                code +
                `\nimport {getAuth as __auth,connectAuthEmulator as __connect} from 'firebase/auth';
if(firebaseApp)__connect(__auth(firebaseApp),${JSON.stringify('http://' + config.authEndpoint)},{disableWarnings:true});`,
              map: null,
            };
        },
      },
    ],
  });
  let browser, page;
  const screenshots = [],
    errors = [],
    external = [],
    statuses = [];
  try {
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    const profile = path.join(root, 'onboarding-chrome');
    browser = await chromium.launchPersistentContext(profile, {
      channel: 'chrome',
      headless: true,
      viewport: { width: 1440, height: 1000 },
      ignoreDefaultArgs: ['--disable-extensions'],
      args: ['--enable-unsafe-extension-debugging'],
    });
    await browser.route('**/*', (route) => {
      const url = new URL(route.request().url());
      if (
        url.protocol === 'chrome-extension:' ||
        ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
      )
        return route.continue();
      external.push(url.hostname);
      return route.abort();
    });
    page = await browser.newPage();
    const pending = new Set();
    page.on('request', (request) => pending.add(request.url()));
    page.on('requestfinished', (request) => pending.delete(request.url()));
    page.on('requestfailed', (request) => pending.delete(request.url()));
    page.on('console', (entry) => {
      if (entry.type() === 'error') errors.push(entry.text());
    });
    process.on('exit', () => {
      fs.writeFileSync(
        path.join(root, 'onboarding-network-diagnostic.json'),
        JSON.stringify(
          {
            pending: [...pending].map((url) => new URL(url).pathname),
            errors,
          },
          null,
          2,
        ),
      );
    });
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/auth/')) statuses.push(response.status());
    });
    const visible = (text) => page.getByText(text, { exact: true }).waitFor({ timeout: 15000 });
    const shot = async (name) => {
      assert.match(await page.title(), /ClassSync/);
      assert.equal(await page.locator('vite-error-overlay').count(), 0);
      assert(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        'Horizontal overflow',
      );
      const file = path.join(config.imageRoot, `m1-${path.basename(root).slice(-8)}-${name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      screenshots.push(file);
    };
    const verify = async (email) => {
      const response = await fetch(
        `http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`,
      );
      const { oobCodes } = await response.json();
      const code = [...oobCodes]
        .reverse()
        .find((x) => x.email === email && x.requestType === 'VERIFY_EMAIL');
      assert(code, 'UI must request actual verification email');
      const update = await fetch(
        `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:update?key=synthetic-emulator-key`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oobCode: code.oobCode }),
        },
      );
      assert.equal(update.status, 200);
      await page.getByRole('button', { name: 'I verified my email', exact: true }).click();
      await page.getByRole('button', { name: 'Request student access', exact: true }).waitFor();
    };
    const signout = async () => {
      await page.getByRole('button', { name: 'Sign out', exact: true }).click();
      await visible('Signed out');
    };
    const login = async (email) => {
      await page.getByRole('button', { name: 'Existing account', exact: true }).click();
      await page.getByLabel('University email', { exact: true }).fill(email);
      await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    };
    await page.goto(origin + '/auth/login');
    await visible('Signed out');
    await page.getByRole('button', { name: 'Create account', exact: true }).first().click();
    const studentEmail = 'browser-student@synthetic.invalid';
    await page.getByLabel('University email', { exact: true }).fill(studentEmail);
    await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
    await page.locator('button[type=submit]').click();
    await page.getByRole('button', { name: 'I verified my email', exact: true }).waitFor();
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('verify-' + width);
    }
    await verify(studentEmail);
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('student-claim-' + width);
    }
    await page.getByLabel('Student number', { exact: true }).fill('browser-student');
    await page.getByRole('button', { name: 'Request student access', exact: true }).click();
    await page
      .getByText(/awaiting university verification|waiting for university verification/)
      .waitFor();
    await page.reload();
    await page.getByText(/awaiting university verification/).waitFor();
    await shot('restored-pending');
    await signout();
    await login(config.adminEmail);
    await visible('Administrator membership verified');
    await page.getByRole('button', { name: 'Load account requests', exact: true }).click();
    await page
      .getByLabel('Identity verification reference', { exact: true })
      .fill('Synthetic authorized browser identity verification');
    await page
      .getByRole('button', { name: 'Approve student browser-student', exact: true })
      .click();
    await visible('No pending student requests.');
    await page
      .getByLabel('Approved faculty record', { exact: true })
      .selectOption('browser-faculty');
    await page
      .getByLabel('Approved email', { exact: true })
      .fill('browser-faculty@synthetic.invalid');
    await page.getByRole('button', { name: 'Create private invitation', exact: true }).click();
    const token = await page.getByLabel('Private invitation code', { exact: true }).inputValue();
    assert(token.length >= 40);
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('admin-invitation-' + width);
    }
    await signout();
    await login(studentEmail);
    await visible('Student membership verified');
    await page.reload();
    await visible('Student membership verified');
    await signout();
    await page.getByRole('button', { name: 'Create account', exact: true }).first().click();
    await page
      .getByLabel('University email', { exact: true })
      .fill('browser-faculty@synthetic.invalid');
    await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
    await page.locator('button[type=submit]').click();
    await page.getByRole('button', { name: 'I verified my email', exact: true }).waitFor();
    await verify('browser-faculty@synthetic.invalid');
    await page.getByText('Have a Teacher invitation?', { exact: true }).click();
    await page.getByLabel('Invitation code', { exact: true }).fill(token);
    await page.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await visible('Teacher membership verified');
    await shot('teacher-accepted');
    // Native Chrome origin zoom, not a CSS transform or device-scale substitution.
    const extension = path.join(root, 'onboarding-zoom');
    fs.mkdirSync(extension);
    fs.writeFileSync(
      path.join(extension, 'manifest.json'),
      JSON.stringify({
        manifest_version: 3,
        name: 'Owned onboarding zoom',
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
      const [tab] = await chrome.tabs.query({ url: origin + '/auth/login*' });
      await chrome.tabs.setZoom(tab.id, 2);
      return chrome.tabs.getZoom(tab.id);
    }, origin);
    assert.equal(factor, 2);
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 2);
    await shot('native200');
    await page.getByRole('button', { name: 'Sign out', exact: true }).focus();
    await page.keyboard.press('Enter');
    await visible('Signed out');
    assert(
      await page
        .getByRole('region', { name: 'University access' })
        .evaluate((el) => document.activeElement === el),
    );
    const unexpectedErrors = errors.filter(
      (message) => !/Failed to load resource.*(?:403|400|ERR_FAILED)/.test(message),
    );
    assert.equal(unexpectedErrors.length, 0, JSON.stringify(unexpectedErrors));
    assert(!statuses.includes(503), 'Unexpected healthy 503');
    fs.writeFileSync(
      path.join(root, 'onboarding-browser-result.json'),
      JSON.stringify(
        {
          browserPlugin: 'unavailable',
          runtime: 'existing Playwright/Chrome',
          flow: 'signup -> verify -> claim -> admin approve -> restored Student -> invited Teacher -> logout',
          widths: [360, 390, 768, 1024, 1440],
          nativeZoom: factor,
          screenshots,
          errors,
          statuses,
          manualScreenReader: 'unverified',
          cloudQualified: false,
        },
        null,
        2,
      ),
    );
  } catch (error) {
    if (page && !page.isClosed()) {
      fs.writeFileSync(
        path.join(root, 'onboarding-failure-dom.txt'),
        await page.locator('body').innerText(),
      );
      await page.screenshot({
        path: path.join(config.imageRoot, `m1-${path.basename(root).slice(-8)}-failure.png`),
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
