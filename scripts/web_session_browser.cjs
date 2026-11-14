/* Browser QA client. The product never imports this emulator transport fixture. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('./qualification_playwright.cjs')();
const net = require('node:net');
const { validateFixture } = require('./lib/web-session-fixture.cjs');

async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const repo = path.resolve(__dirname, '..');
  const root = validateFixture(config);
  const helperRoot = path.join(repo, 'var', 'web-session-' + path.basename(root));
  fs.mkdirSync(helperRoot);
  const helper = path.join(helperRoot, 'identity-helper.js');
  fs.writeFileSync(helper, `import {getAuth,signInWithEmailAndPassword} from 'firebase/auth';
import {firebaseApp} from '/src/lib/firebase.ts';
export async function signin(email,password){return (await signInWithEmailAndPassword(getAuth(firebaseApp),email,password)).user.uid;}
export async function token(){return getAuth(firebaseApp).currentUser.getIdToken();}
`, { flag: 'wx' });
  Object.assign(process.env, {
    VITE_CLASSSYNC_MODE: 'institutional', VITE_ENABLE_ROLE_PREVIEW: 'false',
    VITE_ENABLE_PRESENTATION_SAMPLE: 'false', VITE_API_BASE_URL: '/api/v1',
    VITE_FIREBASE_API_KEY: 'synthetic-emulator-key',
    VITE_FIREBASE_AUTH_DOMAIN: config.project + '.firebaseapp.com',
    VITE_FIREBASE_PROJECT_ID: config.project,
    VITE_FIREBASE_STORAGE_BUCKET: config.project + '.appspot.com',
    VITE_FIREBASE_MESSAGING_SENDER_ID: '1234567890', VITE_FIREBASE_APP_ID: 'synthetic-emulator-app',
    CLASSSYNC_GATEWAY_URL: config.gateway,
  });
  delete process.env.CLASSSYNC_BUILD_TARGET;
  process.chdir(path.join(repo, 'apps/web'));
  const reservation = net.createServer();
  await new Promise((resolve, reject) => { reservation.once('error', reject); reservation.listen(0, '127.0.0.1', resolve); });
  const port = reservation.address().port;
  await new Promise((resolve) => reservation.close(resolve));
  const { createServer } = await import('vite');
  const vite = await createServer({
    root: path.join(repo, 'apps/web'), configFile: path.join(repo, 'apps/web/vite.config.ts'),
    server: { host: '127.0.0.1', port, strictPort: true }, logLevel: 'error',
    plugins: [{ name: 'owned-auth-emulator-transport', enforce: 'pre', transform(code, id) {
      if (id.replaceAll('\\', '/').endsWith('/src/lib/firebase.ts')) return {
        code: code + `\nimport {getAuth as __qaAuth,connectAuthEmulator as __qaConnect} from 'firebase/auth';
if(firebaseApp)__qaConnect(__qaAuth(firebaseApp),${JSON.stringify('http://' + config.authEndpoint)},{disableWarnings:true});`, map: null,
      };
    } }],
  });
  let browser, page;
  const pending = new Set();
  const runtimeErrors = [], unexpectedConsole = [], blockedExternal = [], apiStatuses = [], screenshots = [];
  try {
    await vite.listen();
    const origin = `http://127.0.0.1:${vite.httpServer.address().port}`;
    browser = await chromium.launchPersistentContext(path.join(root, 'owned-chrome-profile'), {
      channel: 'chrome', headless: true, viewport: null,
      ignoreDefaultArgs: ['--disable-extensions'],
      args: ['--window-size=1440,1000', '--enable-unsafe-extension-debugging'],
    });
    const context = browser;
    await context.route('**/*', (route) => {
      const url = new URL(route.request().url());
      if (url.protocol === 'chrome-extension:') return route.continue();
      if (['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) return route.continue();
      blockedExternal.push({ host: url.hostname, type: route.request().resourceType() });
      return route.abort();
    });
    page = await context.newPage();
    await page.setViewportSize({ width: 1440, height: 1000 });
    page.on('request', (request) => pending.add(request));
    page.on('requestfinished', (request) => pending.delete(request));
    page.on('requestfailed', (request) => pending.delete(request));
    page.on('pageerror', (error) => runtimeErrors.push(error.message));
    page.on('console', (message) => {
      if (message.type() !== 'error') return;
      const url = message.location().url;
      if (url.includes('/api/v1/auth/me') || /fonts\.(googleapis|gstatic)\.com/.test(url)) return;
      unexpectedConsole.push(message.text());
    });
    page.on('response', (response) => { if (response.url().endsWith('/api/v1/auth/me')) apiStatuses.push(response.status()); });
    const text = (value) => page.getByText(value, { exact: true }).waitFor({ state: 'visible', timeout: 15000 });
    const control = async (action, uid) => {
      const response = await fetch(config.control, { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Owned-Fixture': config.nonce },
        body: JSON.stringify({ action, uid }) });
      assert.equal(response.status, 200, 'Owned fixture control failed');
    };
    const shot = async (label) => {
      assert.match(await page.title(), /ClassSync/);
      assert.equal(await page.locator('vite-error-overlay').count(), 0);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
      const file = path.join(root,
        `p3a-session-${path.basename(root).slice(-8)}-${label}-${page.viewportSize().width}.png`);
      await page.screenshot({ path: file, fullPage: true }); screenshots.push(file);
    };
    const helperUrl = '/@fs/' + helper.replaceAll('\\', '/');
    const auth = origin + '/auth/login';
    const account = origin + '/auth/account';
    const signedOut = () => page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
    const recheck = () => page.evaluate(() => window.dispatchEvent(new Event('focus')));
    const retry = () => page.getByRole('button', { name: 'Retry access check' }).click();
    const firebase = async (action, body) => {
      const response = await fetch(
        `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:${action}?key=synthetic-emulator-key`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
      );
      assert.equal(response.status, 200);
      return response.json();
    };
    const signin = async (name) => {
      const email = `${name}@synthetic.invalid`;
      const password = 'Local-emulator-password-42!';
      const identity = await firebase('signUp', { email, password, returnSecureToken: true });
      await firebase('sendOobCode', { requestType: 'VERIFY_EMAIL', idToken: identity.idToken });
      const codes = await (await fetch(`http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`)).json();
      const code = codes.oobCodes.find(item => item.email === email && item.requestType === 'VERIFY_EMAIL');
      assert(code, 'Synthetic verification code missing');
      await firebase('update', { oobCode: code.oobCode });
      return page.evaluate(async ({ url, email, password }) => (await import(url)).signin(email, password),
        { url: helperUrl, email, password });
    };
    await page.goto(auth);
    await signedOut(); await shot('before-signed-out');
    const uid = await signin('multi-workspace');
    await text('University access is not active');
    await control('register', uid);
    await retry();
    await text('Choose a workspace'); await shot('role-choice');
    assert.equal(await page.getByRole('button', { name: 'Administrator', exact: true }).count(), 0);
    await page.getByRole('button', { name: 'Student', exact: true }).click();
    await text('Student membership verified');
    for (const width of [360, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 }); await shot('student-verified');
    }
    await page.setViewportSize({ width: 390, height: 1000 });
    let release;
    const held = new Promise((resolve) => { release = resolve; });
    let once = true;
    await page.route(origin + '/api/v1/auth/me', async (route) => {
      if (once) { once = false; await held; }
      await route.continue();
    });
    const teacher = page.getByRole('button', { name: 'Teacher', exact: true });
    await teacher.focus(); await teacher.press('Enter'); await text('Checking university access');
    assert.equal(await teacher.count(), 0);
    await shot('checking-keyboard'); release();
    await text('Teacher membership verified');
    assert(await page.getByRole('region', { name: 'University access' }).evaluate(el => el === document.activeElement));
    await page.unroute(origin + '/api/v1/auth/me'); await shot('teacher-verified');
    const token = await page.evaluate(async (url) => (await import(url)).token(), helperUrl);
    const denied = await page.request.get(origin + '/api/v1/auth/me', {
      headers: { Authorization: 'Bearer ' + token, 'X-ClassSync-Role': 'administrator' },
    });
    assert.equal(denied.status(), 403); await shot('denied');
    await control('student-only', uid);
    await recheck(); await text('University access is not active');
    await retry(); await page.waitForURL('**/student/dashboard');
    await page.goto(account); await text('Student membership verified');
    await control('outage');
    await recheck(); await text('Access check unavailable'); await shot('database-unavailable');
    await control('recover');
    await retry(); await text('Student membership verified');
    await context.setOffline(true); await text('You are offline'); await shot('offline');
    assert.equal(await page.getByText('Student membership verified', { exact: true }).count(), 0);
    await context.setOffline(false); await text('Student membership verified');
    await control('revoke', uid);
    await recheck(); await text('University access is not active');
    await control('activate', uid);
    await retry(); await page.waitForURL('**/student/dashboard');
    await page.reload(); await page.locator('.app-shell').waitFor();
    assert.equal(await page.getByText('Sample preview', { exact: false }).count(), 0);
    await page.goto(account); await text('Student membership verified');
    await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await signedOut();
    assert(await page.getByRole('heading', { name: 'Welcome back' }).evaluate(el => document.activeElement === el));
    const administrator = await signin('single-administrator'); await text('University access is not active');
    await control('administrator', administrator);
    await retry(); await page.waitForURL('**/admin/dashboard');
    await page.goto(account); await text('Administrator membership verified'); await shot('administrator-verified');
    assert.equal(await page.getByRole('button', { name: 'Teacher', exact: true }).count(), 0);
    const extension = path.join(root, 'owned-zoom-extension');
    fs.mkdirSync(extension);
    fs.writeFileSync(path.join(extension, 'manifest.json'), JSON.stringify({ manifest_version: 3,
      name: 'Owned local access-panel zoom check', version: '1.0', permissions: ['tabs'],
      host_permissions: ['http://127.0.0.1/*'] }), { flag: 'wx' });
    fs.writeFileSync(path.join(extension, 'zoom.html'), '<!doctype html><title>Owned QA zoom</title>', { flag: 'wx' });
    const nativePage = await context.newPage();
    await nativePage.goto(account);
    await nativePage.getByText('Administrator membership verified', { exact: true }).waitFor();
    const metrics = () => nativePage.evaluate(() => ({ innerWidth, dpr: devicePixelRatio,
      visualScale: visualViewport.scale, cssZoom: getComputedStyle(document.documentElement).zoom }));
    const beforeZoom = await metrics();
    const cdp = await context.browser().newBrowserCDPSession();
    const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
    const zoomControl = await context.newPage();
    await zoomControl.goto(`chrome-extension://${loaded.id}/zoom.html`);
    const nativeZoom = await zoomControl.evaluate(async (target) => {
      const tabs = await chrome.tabs.query({ url: target + '/auth/account' });
      for (const tab of tabs) await chrome.tabs.setZoom(tab.id, 2);
      return chrome.tabs.getZoom(tabs[0].id);
    }, origin);
    await nativePage.bringToFront();
    await nativePage.waitForFunction(() => devicePixelRatio === 2);
    const afterZoom = await metrics();
    assert.equal(nativeZoom, 2); assert.equal(beforeZoom.dpr, 1);
    assert.equal(afterZoom.dpr, 2); assert.equal(afterZoom.visualScale, 1); assert.equal(afterZoom.cssZoom, '1');
    assert(afterZoom.innerWidth <= beforeZoom.innerWidth * 0.51);
    assert(await nativePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const openAdmin = nativePage.getByRole('link', { name: 'Open Administrator workspace' });
    await openAdmin.focus(); await openAdmin.press('Enter');
    await nativePage.waitForURL('**/admin/dashboard');
    await nativePage.goto(account);
    await nativePage.getByText('Administrator membership verified', { exact: true }).waitFor();
    const zoomScreenshot = path.join(root,
      `p3a-session-${path.basename(root).slice(-8)}-native-200-percent.png`);
    // Native zoom doubles physical pixels; Playwright's CSS-sized screenshot clips them.
    const nativePixels = await (await context.newCDPSession(nativePage)).send('Page.captureScreenshot', {
      captureBeyondViewport: false,
    });
    fs.writeFileSync(zoomScreenshot, Buffer.from(nativePixels.data, 'base64'), { flag: 'wx' });
    screenshots.push(zoomScreenshot);
    const panelBounds = await nativePage.getByRole('region', { name: 'ClassSync account access' }).evaluate((panel) => {
      const bounds = panel.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right, viewport: innerWidth };
    });
    assert(panelBounds.left >= 0 && panelBounds.right <= panelBounds.viewport);
    const zoomEvidence = { nativeZoom, before: beforeZoom, after: afterZoom, keyboard: true, noOverflow: true,
      panelBounds, method: 'Owned Chrome extension tabs.setZoom/getZoom; no CSS zoom or device emulation' };
    // Chrome zoom is origin-wide: restore it before resuming the independent 390px checks.
    await zoomControl.evaluate(async (target) => {
      for (const tab of await chrome.tabs.query({ url: target + '/*' })) await chrome.tabs.setZoom(tab.id, 1);
    }, origin);
    await nativePage.close(); await zoomControl.close();
    await page.bringToFront();
    await page.waitForFunction(() => devicePixelRatio === 1);
    await text('Administrator membership verified');
    await control('stop-auth');
    await recheck(); await text('Access check unavailable'); await shot('identity-unavailable');
    await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await signedOut(); await shot('after-sign-out');
    assert.deepEqual(runtimeErrors, []); assert.deepEqual(unexpectedConsole, []);
    assert(blockedExternal.every((entry) => /fonts\.(googleapis|gstatic)\.com/.test(entry.host)), 'Unexpected nonloopback browser request');
    assert(apiStatuses.includes(200) && apiStatuses.includes(403) && apiStatuses.includes(503));
    const result = { widths: [360, 390, 768, 1024, 1440], actualFirebaseEmulatorAndCurrentPostgres: true,
      threeRolesAndDeniedAccess: true, keyboardFocusPreserved: true, revocationAndOutageRecovery: true,
      sdkRefreshAndSignOut: true, runtimeErrors, unexpectedConsole, blockedExternal, apiStatuses, screenshots,
      zoomEvidence, manualScreenReader: 'unverified', productionAcceptance: false };
    fs.writeFileSync(path.join(root, 'browser-result.json'), JSON.stringify(result, null, 2), { flag: 'wx' });
    console.log('Real browser session lifecycle verified');
  } catch (error) {
    const failure = { message: error.message, pending: [...pending].map((request) => {
      const url = new URL(request.url()); return url.origin + url.pathname;
    }), runtimeErrors, unexpectedConsole, blockedExternal, apiStatuses };
    if (page && !page.isClosed()) {
      failure.visibleText = await page.locator('body').innerText().catch(() => 'unavailable');
      const file = path.join(root,
        `p3a-session-${path.basename(root).slice(-8)}-failure.png`);
      await page.screenshot({ path: file, fullPage: true }).catch(() => {});
      failure.screenshot = file;
    }
    fs.writeFileSync(path.join(root, 'browser-failure.json'), JSON.stringify(failure, null, 2), { flag: 'wx' });
    throw error;
  } finally {
    if (browser) await browser.close();
    await vite.close();
  }
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
