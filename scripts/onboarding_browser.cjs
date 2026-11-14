/* Actual synthetic Auth/Gateway/PostgreSQL account UI. Browser plugin unavailable. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const loadPlaywright = require('./qualification_playwright.cjs');

async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const root = fs.realpathSync(config.root);
  assert.equal(path.dirname(root), fs.realpathSync(os.tmpdir()));
  assert.match(path.basename(root), /^classsync-auth-run-[a-f0-9]{32}$/);
  const marker = JSON.parse(fs.readFileSync(path.join(root, 'owned-auth.json'), 'utf8'));
  assert.equal(marker.endpoint, config.authEndpoint);
  assert.equal(marker.project, config.project);
  assert.match(config.gateway, /^http:\/\/127\.0\.0\.1:[0-9]+$/);
  const preview = config.preview === true;
  const persistent = preview && config.persistent === true;
  const supervisor = Number(process.env.CLASSSYNC_DEV_SUPERVISOR_PID);
  if (persistent) assert(Number.isSafeInteger(supervisor) && supervisor > 0);
  assert.match(config.project, /^demo-classsync-[a-f0-9]{12}$/);
  assert.match(config.authEndpoint, /^127\.0\.0\.1:[0-9]+$/);
  const repo = path.resolve(__dirname, '..');
  Object.assign(process.env, {
    VITE_CLASSSYNC_MODE: 'institutional',
    VITE_CLASSSYNC_SYNTHETIC_PREVIEW: preview ? 'true' : 'false',
    VITE_CLASSSYNC_PRESENTATION_URL: preview
      ? (process.env.VITE_CLASSSYNC_PRESENTATION_URL ?? '')
      : 'https://presentation.synthetic.invalid/',
    VITE_ENABLE_ROLE_PREVIEW: 'false',
    VITE_ENABLE_PRESENTATION_SAMPLE: 'false',
    VITE_API_BASE_URL: '/api/v1',
    VITE_FIREBASE_API_KEY: persistent
      ? 'synthetic-emulator-key-' + config.project
      : 'synthetic-emulator-key',
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
    server: {
      host: '127.0.0.1',
      port: persistent ? Number(process.env.CLASSSYNC_DEV_PORT) : preview ? 5191 : 0,
      strictPort: preview,
    },
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
    if (preview) {
      const stop = path.join(root, 'stop-preview');
      console.log(`Connected synthetic preview: ${origin}/`);
      console.log(
        `Auth Emulator: http://${config.authEndpoint} (verification codes: /emulator/v1/projects/${config.project}/oobCodes)`,
      );
      console.log(`API through Vite: ${origin}/api/v1`);
      console.log(
        `Verification and reset links: http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`,
      );
      if (persistent) {
        console.log(
          `Synthetic credentials and record IDs: ${path.join(root, 'dev-accounts.json')}`,
        );
        console.log('Type stop and press Enter to shut down this session.');
      } else {
        console.log(
          `Synthetic Admin: ${config.adminEmail} | Teacher: browser-faculty@synthetic.invalid | Student record: SYN-001`,
        );
      }
      console.log(`Alternate stop command: New-Item -ItemType File -Path "${stop}"`);
      const deadline = persistent ? Infinity : Date.now() + 600_000;
      while (!fs.existsSync(stop) && Date.now() < deadline) {
        if (persistent) {
          try {
            process.kill(supervisor, 0);
          } catch {
            break;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      fs.writeFileSync(
        path.join(root, 'onboarding-browser-result.json'),
        JSON.stringify({ preview: true }),
      );
      return;
    }
    const { chromium } = loadPlaywright();
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
    const verify = async (email, nextAction = 'Review student record') => {
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
      await page.getByRole('button', { name: nextAction, exact: true }).waitFor();
    };
    const signout = async () => {
      await page.getByRole('button', { name: 'Sign out', exact: true }).click();
      await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
    };
    const login = async (email, password = 'Local-emulator-password-42!') => {
      await page.getByRole('heading', { name: 'Welcome back', exact: true }).waitFor();
      await page.getByLabel('Email', { exact: true }).fill(email);
      await page.getByLabel('Password', { exact: true }).fill(password);
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    };
    const entries = [
      ['/', 'Welcome back'],
      ['/auth/login', 'Welcome back'],
      ['/auth/signup', 'Create your account'],
      ['/auth/forgot-password', 'Reset your password'],
      ['/auth/verify', 'Welcome back'],
      ['/auth/student-onboarding', 'Welcome back'],
      ['/auth/teacher-invite', 'Welcome back'],
    ];
    for (const [route, title] of entries) {
      await page.goto(origin + route);
      await page.getByRole('heading', { name: title, exact: true }).waitFor();
      assert.equal(await page.locator('.connected-entrance').count(), 1);
      for (const role of ['Student', 'Teacher', 'Admin'])
        assert.equal(await page.getByRole('button', { name: role, exact: true }).count(), 0);
    }
    await page.goto(origin + '/');
    await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
    assert.equal(
      await page.getByRole('link', { name: 'Explore the sample workspace' }).getAttribute('href'),
      'https://presentation.synthetic.invalid/',
    );
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const form = await page.getByRole('button', { name: 'Sign in', exact: true }).boundingBox();
      assert(
        form && form.y + form.height < 900 && form.height >= 44,
        'Sign-in must fit the first viewport',
      );
      assert(
        await page
          .locator('.entrance-preview')
          .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
        'Illustrative schedule must fit',
      );
      await shot('entrance-' + width);
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    assert.equal(
      await page.locator('.entrance-preview').evaluate((el) => getComputedStyle(el).animationName),
      'none',
    );
    assert.equal(
      await page
        .getByRole('button', { name: 'Sign in', exact: true })
        .evaluate((el) => getComputedStyle(el).transitionDuration),
      '0s',
    );
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.getByRole('heading', { name: 'Welcome back' }).focus();
    await page.keyboard.press('Tab');
    assert(
      await page
        .getByLabel('Email', { exact: true })
        .evaluate((el) => el === document.activeElement),
    );
    await page.keyboard.press('Tab');
    assert(
      await page
        .getByLabel('Password', { exact: true })
        .evaluate((el) => el === document.activeElement),
    );
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    assert.equal(await page.getByLabel('Password', { exact: true }).getAttribute('type'), 'text');
    await page.keyboard.press('Enter');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    assert.equal(
      await page.getByLabel('Email', { exact: true }).getAttribute('aria-describedby'),
      'entrance-email-error',
    );
    await login('unknown@synthetic.invalid', 'Invalid-password-42!');
    await page.getByText(/We could not sign you in/).waitFor();
    assert.equal(
      await page.getByLabel('Password', { exact: true }).inputValue(),
      'Invalid-password-42!',
    );
    await page.getByRole('link', { name: 'Create an account', exact: true }).click();
    await page.waitForURL('**/auth/signup');
    const studentEmail = 'browser-student@synthetic.invalid';
    await page.getByLabel('Email', { exact: true }).fill(studentEmail);
    await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
    await page.getByLabel('Confirm password', { exact: true }).fill('Local-emulator-password-42!');
    await page.locator('button[type=submit]').click();
    await page.waitForURL('**/auth/verify');
    await page.getByRole('button', { name: 'I verified my email', exact: true }).waitFor();
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('verify-' + width);
    }
    await verify(studentEmail);
    await page.waitForURL('**/auth/student-onboarding');
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await shot('student-claim-' + width);
    }
    await page.getByLabel('Student number', { exact: true }).fill('browser-student');
    await page.getByLabel('Account name', { exact: true }).fill('Synthetic Student');
    await page.getByRole('button', { name: 'Review student record', exact: true }).click();
    await page.getByRole('button', { name: 'Request student access', exact: true }).click();
    await page
      .getByText(/awaiting university verification|waiting for university verification/)
      .waitFor();
    await page.reload();
    await page.getByText(/awaiting university verification/).waitFor();
    await shot('restored-pending');
    await signout();
    await login(config.adminEmail);
    await page.waitForURL('**/admin/dashboard');
    await page.goto(origin + '/auth/account');
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
    await page.getByRole('link', { name: 'Forgot password?', exact: true }).click();
    await page.getByLabel('Email', { exact: true }).fill(studentEmail);
    await page.getByRole('button', { name: 'Send reset link', exact: true }).click();
    await page.getByText(/check your email for the next steps/).waitFor();
    const recovery = await fetch(
      `http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`,
    ).then((response) => response.json());
    assert(
      recovery.oobCodes.some(
        (code) => code.email === studentEmail && code.requestType === 'PASSWORD_RESET',
      ),
    );
    await page.getByRole('link', { name: 'Back to sign in', exact: true }).click();
    await page.goto(
      origin +
        '/auth/login?returnTo=' +
        encodeURIComponent('https://untrusted.invalid/admin/dashboard'),
    );
    await login(studentEmail);
    await page.waitForURL(origin + '/student/dashboard');
    await page.reload();
    await page.locator('.app-shell').waitFor();
    await page.goto(origin + '/admin/dashboard');
    await page.getByRole('heading', { name: 'University access unavailable' }).waitFor();
    assert.equal(await page.getByRole('heading', { name: 'University accounts' }).count(), 0);
    await page.goto(origin + '/auth/account');
    await visible('Student membership verified');
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'expired_token' } }),
      }),
    );
    await page.reload();
    await visible('Session expired');
    await page.unroute('**/api/v1/auth/me');
    await signout();
    const teacherEmail = 'browser-faculty@synthetic.invalid';
    const provisionedTeacher = await fetch(
      `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=synthetic-emulator-key`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: teacherEmail, password: 'Local-emulator-password-42!' }),
      },
    );
    assert.equal(provisionedTeacher.status, 200);
    await page.goto(origin + '/auth/teacher-invite');
    await page.waitForURL(
      (url) =>
        url.pathname === '/auth/login' &&
        url.searchParams.get('returnTo') === '/auth/teacher-invite',
    );
    await login(teacherEmail);
    await page.getByRole('button', { name: 'Resend verification email', exact: true }).click();
    await page
      .getByText('Verification email requested. Check your inbox.', { exact: true })
      .waitFor();
    await verify(teacherEmail, 'Accept invitation');
    await page.waitForURL((url) => url.pathname === '/auth/teacher-invite');
    await page.getByLabel('Invitation code', { exact: true }).fill(token);
    await page.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await page.waitForURL('**/teacher/dashboard');
    await page.goto(origin + '/student/dashboard');
    await page.getByRole('heading', { name: 'University access unavailable' }).waitFor();
    await page.goto(origin + '/auth/account');
    await visible('Teacher membership verified');
    await page.getByRole('button', { name: 'Sign out', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL((url) => url.pathname === '/auth/login');
    await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
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
    await shot('entrance-native200');
    assert(
      await page
        .getByRole('heading', { name: 'Welcome back' })
        .evaluate((el) => document.activeElement === el),
    );
    const unexpectedErrors = errors.filter(
      (message) => !/Failed to load resource.*(?:403|401|400|ERR_FAILED)/.test(message),
    );
    assert.equal(unexpectedErrors.length, 0, JSON.stringify(unexpectedErrors));
    assert(!statuses.includes(503), 'Unexpected healthy 503');
    fs.writeFileSync(
      path.join(root, 'onboarding-browser-result.json'),
      JSON.stringify(
        {
          browserPlugin: 'unavailable',
          runtime: 'existing Playwright/Chrome',
          flow: 'signup -> verify -> claim -> admin approve -> recovery -> restored Student -> invited Teacher -> logout',
          origin,
          entries,
          widths: [360, 390, 768, 1024, 1440],
          nativeZoom: factor,
          reducedMotion: true,
          safeReturn: true,
          expiredSession: true,
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
