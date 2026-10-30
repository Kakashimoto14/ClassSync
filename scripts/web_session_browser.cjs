/* Browser QA client. The product never imports this emulator transport fixture. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const net = require('node:net');
const { validateFixture } = require('./lib/web-session-fixture.cjs');

async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const repo = path.resolve(__dirname, '..');
  const root = validateFixture(config);
  const helperRoot = path.join(repo, 'var', 'web-session-' + path.basename(root));
  fs.mkdirSync(helperRoot);
  const helper = path.join(helperRoot, 'identity-helper.js');
  fs.writeFileSync(helper, `import {getAuth,signInAnonymously} from 'firebase/auth';
import {firebaseApp} from '/src/lib/firebase.ts';
export async function signin(){return (await signInAnonymously(getAuth(firebaseApp))).user.uid;}
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
      const file = path.join('C:/Users/lenovo/.codex/visualizations/2026/10/25/01a17489-5bf8-7c93-adb1-44b9f3722009',
        `p3a-session-${path.basename(root).slice(-8)}-${label}-${page.viewportSize().width}.png`);
      await page.screenshot({ path: file, fullPage: true }); screenshots.push(file);
    };
    const signin = async () => page.evaluate(async (url) => (await import(url)).signin(),
      '/@fs/' + helper.replaceAll('\\', '/'));
    await page.goto(origin + '/auth/login');
    await text('Signed out'); await shot('before-signed-out');
    const uid = await signin();
    await text('Current membership required');
    await control('register', uid);
    await page.getByRole('button', { name: 'Retry access check' }).click();
    await text('Choose a role to verify'); await shot('role-choice');
    await page.getByRole('button', { name: 'Check Student access' }).click();
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
    const teacher = page.getByRole('button', { name: 'Check Teacher access' });
    await teacher.focus(); await teacher.press('Enter'); await text('Checking university access');
    assert(await teacher.evaluate((button) => document.activeElement === button));
    await shot('checking-keyboard'); release();
    await text('Teacher membership verified');
    assert(await teacher.evaluate((button) => document.activeElement === button));
    await page.unroute(origin + '/api/v1/auth/me'); await shot('teacher-verified');
    await page.getByRole('button', { name: 'Check Administrator access' }).click();
    await text('Current membership required'); await shot('denied');
    await page.getByRole('button', { name: 'Check Teacher access' }).click(); await text('Teacher membership verified');
    await control('student-only', uid);
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Current membership required');
    await page.getByRole('button', { name: 'Check Student access' }).click(); await text('Student membership verified');
    await control('outage');
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Access check unavailable'); await shot('database-unavailable');
    await control('recover');
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Student membership verified');
    await context.setOffline(true); await text('You are offline'); await shot('offline');
    assert.equal(await page.getByText('Student membership verified', { exact: true }).count(), 0);
    await context.setOffline(false); await text('Student membership verified');
    await control('revoke', uid);
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Current membership required');
    await control('activate', uid);
    await page.getByRole('button', { name: 'Check Student access' }).click(); await text('Student membership verified');
    await page.reload(); await text('Student membership verified');
    await page.goto(origin + '/student/dashboard'); await text('University access unavailable');
    assert.equal(await page.getByText('Sample preview', { exact: false }).count(), 0);
    await page.goto(origin + '/auth/login'); await text('Student membership verified');
    await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await text('Signed out');
    assert(await page.getByRole('region', { name: 'University access' }).evaluate((element) => document.activeElement === element));
    const administrator = await signin(); await text('Current membership required');
    await control('administrator', administrator);
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Administrator membership verified'); await shot('administrator-verified');
    await page.getByRole('button', { name: 'Check Student access' }).click(); await text('Current membership required');
    await page.getByRole('button', { name: 'Check Administrator access' }).click(); await text('Administrator membership verified');
    const extension = path.join(root, 'owned-zoom-extension');
    fs.mkdirSync(extension);
    fs.writeFileSync(path.join(extension, 'manifest.json'), JSON.stringify({ manifest_version: 3,
      name: 'Owned local access-panel zoom check', version: '1.0', permissions: ['tabs'],
      host_permissions: ['http://127.0.0.1/*'] }), { flag: 'wx' });
    fs.writeFileSync(path.join(extension, 'zoom.html'), '<!doctype html><title>Owned QA zoom</title>', { flag: 'wx' });
    const nativePage = await context.newPage();
    await nativePage.goto(origin + '/auth/login');
    await nativePage.getByText('Administrator membership verified', { exact: true }).waitFor();
    const metrics = () => nativePage.evaluate(() => ({ innerWidth, dpr: devicePixelRatio,
      visualScale: visualViewport.scale, cssZoom: getComputedStyle(document.documentElement).zoom }));
    const beforeZoom = await metrics();
    const cdp = await context.browser().newBrowserCDPSession();
    const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
    const zoomControl = await context.newPage();
    await zoomControl.goto(`chrome-extension://${loaded.id}/zoom.html`);
    const nativeZoom = await zoomControl.evaluate(async (target) => {
      const tabs = await chrome.tabs.query({ url: target + '/auth/login' });
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
    const nativeTeacher = nativePage.getByRole('button', { name: 'Check Teacher access' });
    await nativeTeacher.focus(); await nativeTeacher.press('Enter');
    await nativePage.getByText('Current membership required', { exact: true }).waitFor();
    assert(await nativeTeacher.evaluate((button) => document.activeElement === button));
    const zoomScreenshot = path.join('C:/Users/lenovo/.codex/visualizations/2026/10/25/01a17489-5bf8-7c93-adb1-44b9f3722009',
      `p3a-session-${path.basename(root).slice(-8)}-native-200-percent.png`);
    // Native zoom doubles physical pixels; Playwright's CSS-sized screenshot clips them.
    const nativePixels = await (await context.newCDPSession(nativePage)).send('Page.captureScreenshot', {
      captureBeyondViewport: false,
    });
    fs.writeFileSync(zoomScreenshot, Buffer.from(nativePixels.data, 'base64'), { flag: 'wx' });
    screenshots.push(zoomScreenshot);
    const panelBounds = await nativePage.locator('[aria-label="University access"]').evaluate((panel) => {
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
    await page.getByRole('button', { name: 'Retry access check' }).click(); await text('Access check unavailable'); await shot('identity-unavailable');
    await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await text('Signed out'); await shot('after-sign-out');
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
      const file = path.join('C:/Users/lenovo/.codex/visualizations/2026/10/25/01a17489-5bf8-7c93-adb1-44b9f3722009',
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
