/* Real local scanner + Auth/Gateway/Scheduling/PostgreSQL. Synthetic fixtures only. */
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
  assert.equal(marker.project, config.project);
  assert.equal(marker.endpoint, config.authEndpoint);
  assert.match(config.gateway, /^http:\/\/127\.0\.0\.1:[0-9]+$/);
  const { chromium } = loadPlaywright();
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
        name: 'owned-connected-auth',
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
    browser = await chromium.launchPersistentContext(path.join(root, 'connected-chrome'), {
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
      const file = path.join(config.imageRoot, `m3-${path.basename(root).slice(-8)}-${name}.png`);
      await page.screenshot({ path: file, fullPage: !name.includes('native200') });
      screenshots.push(file);
    };
    const auth = origin + '/auth/login';
    const nativeChecks = [];
    let zoomHelper;
    const nativeForm = async (name, action) => {
      if (!zoomHelper) {
        const extension = path.join(root, 'connected-zoom');
        fs.mkdirSync(extension);
        fs.writeFileSync(
          path.join(extension, 'manifest.json'),
          JSON.stringify({
            manifest_version: 3,
            name: 'Owned connected zoom',
            version: '1.0',
            permissions: ['tabs'],
            host_permissions: ['http://127.0.0.1/*'],
          }),
        );
        fs.writeFileSync(
          path.join(extension, 'zoom.html'),
          '<!doctype html><title>Owned zoom</title>',
        );
        const cdp = await browser.browser().newBrowserCDPSession();
        const loaded = await cdp.send('Extensions.loadUnpacked', { path: extension });
        zoomHelper = await browser.newPage();
        await zoomHelper.goto(`chrome-extension://${loaded.id}/zoom.html`);
      }
      const setZoom = (factor) =>
        zoomHelper.evaluate(
          async ({ origin, factor }) => {
            const [tab] = await chrome.tabs.query({ url: origin + '/*' });
            await chrome.tabs.setZoom(tab.id, factor);
            return chrome.tabs.getZoom(tab.id);
          },
          { origin, factor },
        );
      assert.equal(await setZoom(2), 2);
      await page.bringToFront();
      await page.waitForFunction(() => devicePixelRatio === 2);
      const layout = await page.evaluate(async () => {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const controls = [...document.querySelectorAll('main input,main select,main textarea')]
          .map((element) => element.getBoundingClientRect())
          .filter((rect) => rect.width > 0);
        return {
          width: innerWidth,
          ratio: devicePixelRatio,
          controls: controls.length,
          clipped: controls.filter((rect) => rect.left < -1 || rect.right > innerWidth + 1).length,
        };
      });
      assert(layout.controls > 0);
      assert.equal(layout.clipped, 0, 'Native zoom clipped form controls');
      nativeChecks.push({ name, ...layout });
      await shot(name + '-native200');
      if (action) await action();
      assert.equal(await setZoom(1), 1);
      await page.waitForFunction(() => devicePixelRatio === 1);
    };
    const login = async (email) => {
      await page.goto(auth);
      await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
      await page.getByLabel('Email', { exact: true }).fill(email);
      await page.getByLabel('Password', { exact: true }).fill('Local-emulator-password-42!');
      await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    };
    const logout = async () => {
      await page.goto(origin + '/auth/account');
      await page.getByRole('button', { name: 'Sign out', exact: true }).click();
      await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
    };

    const password = 'Local-emulator-password-42!';
    const signup = async (email) => {
      await page.goto(auth);
      await page.getByRole('button', { name: 'Sign in', exact: true }).waitFor();
      await page.getByRole('link', { name: 'Create an account', exact: true }).click();
      await page.getByLabel('Email', { exact: true }).fill(email);
      await page.getByLabel('Password', { exact: true }).fill(password);
      await page
        .getByLabel('Confirm password', { exact: true })
        .fill('Local-emulator-password-42!');
      await page.locator('button[type=submit]').click();
      await page.getByRole('button', { name: 'I verified my email', exact: true }).waitFor();
      const codes = await (
        await fetch(`http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`)
      ).json();
      const code = [...codes.oobCodes]
        .reverse()
        .find((item) => item.email === email && item.requestType === 'VERIFY_EMAIL');
      assert(code, 'Actual verification email missing');
      const response = await fetch(
        `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:update?key=synthetic-emulator-key`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oobCode: code.oobCode }),
        },
      );
      assert.equal(response.status, 200);
      const verified = await response.json();
      await page.getByRole('button', { name: 'I verified my email', exact: true }).click();
      return verified.localId;
    };
    const studentEmail = 'connected-student@synthetic.invalid';
    const teacherEmail = 'connected-teacher@synthetic.invalid';
    const studentUid = await signup(studentEmail);
    await page.getByLabel('Student number', { exact: true }).fill('SYN-001');
    await page.getByLabel('Account name', { exact: true }).fill('Synthetic Student');
    await page.getByRole('button', { name: 'Review student record', exact: true }).click();
    await page.getByRole('button', { name: 'Request student access', exact: true }).click();
    await visible('Your request is waiting for university verification.');
    await logout();
    await login(config.adminEmail);
    await page.waitForURL('**/admin/dashboard');
    await page.goto(origin + '/auth/account');
    await visible('Administrator membership verified');
    await page.getByRole('button', { name: 'Load account requests', exact: true }).click();
    await page
      .getByLabel('Identity verification reference', { exact: true })
      .fill('Disposable three-role acceptance control');
    await page.getByRole('button', { name: 'Approve student SYN-001', exact: true }).click();
    await visible('No pending student requests.');
    await page
      .getByLabel('Approved faculty record', { exact: true })
      .selectOption(config.fixture.faculty);
    await page.getByLabel('Approved email', { exact: true }).fill(teacherEmail);
    await page.getByRole('button', { name: 'Create private invitation', exact: true }).click();
    const invitation = await page
      .getByLabel('Private invitation code', { exact: true })
      .inputValue();
    assert(invitation.length > 30);
    await page.goto(origin + '/admin/academic?period=' + config.fixture.period);
    await page
      .getByText('Academic year, semester and instructional calendar', { exact: true })
      .click();
    const calendarSave = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith('/calendar') &&
        response.request().method() === 'PUT',
    );
    await page.getByRole('button', { name: 'Save academic calendar', exact: true }).click();
    assert.equal((await calendarSave).status(), 200);
    await visible('Academic calendar saved. Recheck scheduling readiness before generation.');
    await page.goto(origin + '/admin/schedule-manager/create?period=' + config.fixture.period);
    await visible('Ready for generation');
    await page.getByRole('button', { name: 'Generate Weekly Schedule', exact: true }).click();
    await page
      .getByLabel('Draft title', { exact: true })
      .fill('Disposable connected publication acceptance');
    await page.getByRole('button', { name: 'Save Draft', exact: true }).click();
    await page.getByRole('link', { name: 'Open saved draft', exact: true }).click();
    await page.getByText('Review publication', { exact: true }).click();
    await page.getByRole('button', { name: 'Revalidate for publication', exact: true }).click();
    await page.getByRole('button', { name: 'Publish reviewed timetable', exact: true }).waitFor();
    const publicationResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/timetables/publish',
    );
    await page.getByRole('button', { name: 'Publish reviewed timetable', exact: true }).click();
    const publication = await publicationResponse;
    assert.equal(publication.status(), 200);
    const published = (await publication.json()).data;
    assert.equal(published.revision, 2);
    await page
      .getByRole('status')
      .filter({ hasText: /^published$/ })
      .waitFor();
    await shot('administrator-published');
    await logout();
    const teacherAccount = await fetch(
      `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=synthetic-emulator-key`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: teacherEmail, password, returnSecureToken: true }),
      },
    );
    assert.equal(teacherAccount.status, 200);
    const teacherUid = (await teacherAccount.json()).localId;
    await page.goto(origin + '/auth/teacher-invite');
    await page.getByLabel('Email', { exact: true }).fill(teacherEmail);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.getByRole('button', { name: 'Resend verification email' }).click();
    const codes = await (
      await fetch(`http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`)
    ).json();
    const teacherCode = codes.oobCodes.find(
      (item) => item.email === teacherEmail && item.requestType === 'VERIFY_EMAIL',
    );
    assert(teacherCode, 'Teacher verification email missing');
    const verifiedTeacher = await fetch(
      `http://${config.authEndpoint}/identitytoolkit.googleapis.com/v1/accounts:update?key=synthetic-emulator-key`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ oobCode: teacherCode.oobCode }),
      },
    );
    assert.equal(verifiedTeacher.status, 200);
    await page.getByRole('button', { name: 'I verified my email', exact: true }).click();
    await page.getByLabel('Invitation code', { exact: true }).fill(invitation);
    await page.getByRole('button', { name: 'Accept invitation', exact: true }).click();
    await page.waitForURL('**/teacher/dashboard');
    const projections = {};
    const tokens = {};
    let currentPublishedId = published.id;
    const inspectCalendar = async (role, stage = 'initial') => {
      const responsePromise = page.waitForResponse((response) =>
        new URL(response.url()).pathname.startsWith('/api/v1/timetables/calendar/'),
      );
      await page.goto(origin + `/${role}/schedule?period=${config.fixture.period}&date=2026-10-05`);
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      const data = (await response.json()).data;
      tokens[role] = response.request().headers()['authorization'];
      assert.equal(data.version, currentPublishedId);
      assert.equal(new Set(data.occurrences.map((item) => item.offering_id)).size, 2);
      for (const code of config.fixture.codes) {
        const occurrence = data.occurrences.find((item) => item.subject.code === code);
        assert(occurrence, 'Missing assigned published course');
        await page
          .getByRole('button')
          .filter({ hasText: occurrence.subject.name })
          .first()
          .waitFor();
      }
      projections[role] = {
        version: data.version,
        sessions: data.occurrences
          .map((item) => ({ id: item.id, room: item.room.id, teacher: item.teacher.id }))
          .sort((a, b) => a.id.localeCompare(b.id)),
      };
      await shot(role + '-' + stage + '-published');
      for (const width of [360, 390, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 1000 });
        await shot(role + '-' + stage + '-' + width);
      }
      await page.reload();
      await page
        .getByRole('button')
        .filter({ hasText: data.occurrences[0].subject.name })
        .first()
        .waitFor();
      return data;
    };
    const teaching = await inspectCalendar('teacher');
    const requestedClass = teaching.occurrences[0];
    await page.goto(origin + '/teacher/dashboard?period=' + config.fixture.period);
    await page.locator(`[data-published-version="${currentPublishedId}"]`).waitFor();
    assert(!(await page.locator('body').innerText()).includes('Separate demonstration workflow'));
    await shot('teacher-dashboard');
    const optionsResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/timetables/requests/options',
    );
    await page.goto(
      origin +
        '/teacher/change-requests/new?' +
        new URLSearchParams({
          period: config.fixture.period,
          date: requestedClass.date,
          occurrence: requestedClass.id,
        }),
    );
    const optionsReply = await optionsResponse;
    assert.equal(optionsReply.status(), 200);
    const alternatives = (await optionsReply.json()).data;
    assert(alternatives.rooms.length > 0);
    const proposedRoom = alternatives.rooms[0];
    await page.getByLabel('Proposed classroom', { exact: true }).selectOption(proposedRoom.id);
    await page
      .getByLabel('Reason for change', { exact: true })
      .fill('Disposable classroom change acceptance control');
    await shot('teacher-request-form');
    const requestResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/v1/timetables/requests' &&
        response.request().method() === 'POST',
    );
    await nativeForm('teacher-request', async () => {
      await page.getByRole('button', { name: 'Submit classroom request', exact: true }).focus();
      await page.keyboard.press('Enter');
    });
    const requestReply = await requestResponse;
    assert.equal(requestReply.status(), 201);
    const classroomRequest = (await requestReply.json()).data;
    const originalRequestBody = requestReply.request().postDataJSON();
    await visible('Awaiting review');
    const teacherHeaders = { Authorization: tokens.teacher, 'X-ClassSync-Role': 'teacher' };
    const replay = await page.request.post(origin + '/api/v1/timetables/requests', {
      headers: teacherHeaders,
      data: originalRequestBody,
    });
    assert.equal(replay.status(), 201);
    assert.equal((await replay.json()).data.id, classroomRequest.id);
    const changedReplay = await page.request.post(origin + '/api/v1/timetables/requests', {
      headers: teacherHeaders,
      data: { ...originalRequestBody, reason: 'Different request payload' },
    });
    assert.equal(changedReplay.status(), 409);
    const forbiddenDecision = await page.request.post(
      origin + `/api/v1/timetables/requests/${classroomRequest.id}/decision`,
      {
        headers: teacherHeaders,
        data: { expected_revision: 1, decision: 'approved', note: 'Forged role attempt' },
      },
    );
    assert.equal(forbiddenDecision.status(), 403);
    const foreignClass = await page.request.post(origin + '/api/v1/timetables/requests', {
      headers: teacherHeaders,
      data: {
        ...originalRequestBody,
        idempotency_key: require('node:crypto').randomUUID(),
        occurrence_id: 'unassigned-class:' + requestedClass.date,
      },
    });
    assert.equal(foreignClass.status(), 403);
    await page.goto(origin + '/admin/academic');
    await visible('This page requires your university to grant the matching workspace role.');
    await logout();
    await login(studentEmail);
    await page.waitForURL('**/student/dashboard');
    await inspectCalendar('student');
    assert.deepEqual(projections.student, projections.teacher);
    const initialProjections = JSON.parse(JSON.stringify(projections));
    const forbiddenRead = await page.request.get(
      origin + `/api/v1/timetables/requests/${classroomRequest.id}`,
      { headers: { Authorization: tokens.student, 'X-ClassSync-Role': 'student' } },
    );
    assert.equal(forbiddenRead.status(), 403);
    await page.goto(origin + '/teacher/schedule');
    await visible('This page requires your university to grant the matching workspace role.');
    await logout();
    await login(config.adminEmail);
    await page.waitForURL('**/admin/dashboard');
    await page.goto(origin + '/admin/requests');
    await page
      .getByLabel('Decision note for ' + requestedClass.subject.code, { exact: true })
      .fill('Disposable approval for independent publication review');
    await page.getByRole('button', { name: 'Approve for publication', exact: true }).click();
    await page.getByRole('link', { name: 'Review classroom change', exact: true }).click();
    await page.getByText('Review publication', { exact: true }).click();
    await nativeForm('administrator-review');
    await page.getByRole('button', { name: 'Revalidate for publication', exact: true }).click();
    const changedPublicationResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/timetables/publish',
    );
    const fulfillmentResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
        `/api/v1/timetables/requests/${classroomRequest.id}/fulfill`,
    );
    await page.getByRole('button', { name: 'Publish reviewed timetable', exact: true }).click();
    const changedPublicationReply = await changedPublicationResponse;
    assert.equal(changedPublicationReply.status(), 200);
    const changedPublication = (await changedPublicationReply.json()).data;
    assert.equal(changedPublication.revision, 3);
    currentPublishedId = changedPublication.id;
    const fulfillmentReply = await fulfillmentResponse;
    assert.equal(fulfillmentReply.status(), 200);
    const fulfilled = (await fulfillmentReply.json()).data;
    assert.equal(fulfilled.status, 'fulfilled');
    assert.equal(fulfilled.fulfilled_version, currentPublishedId);
    await shot('administrator-classroom-published');
    await logout();
    await login(teacherEmail);
    await page.waitForURL('**/teacher/dashboard');
    const changedTeaching = await inspectCalendar('teacher', 'changed');
    assert.equal(
      changedTeaching.occurrences.find((item) => item.id === requestedClass.id).room.id,
      proposedRoom.id,
    );
    await page.goto(origin + '/teacher/change-requests');
    await visible('Classroom change published');
    const declineCandidate = await page.request.post(origin + '/api/v1/timetables/requests', {
      headers: teacherHeaders,
      data: {
        ...originalRequestBody,
        publication_id: currentPublishedId,
        proposed_room_id: requestedClass.room.id,
        reason: 'Disposable declined request control',
        idempotency_key: require('node:crypto').randomUUID(),
      },
    });
    assert.equal(declineCandidate.status(), 201);
    const declinedRequestId = (await declineCandidate.json()).data.id;
    await logout();
    await login(studentEmail);
    await page.waitForURL('**/student/dashboard');
    await inspectCalendar('student', 'changed');
    assert.deepEqual(projections.student, projections.teacher);
    await logout();
    await login(config.adminEmail);
    await page.waitForURL('**/admin/dashboard');
    await page.goto(origin + '/admin/requests');
    const declinedCard = page
      .locator('article')
      .filter({ hasText: 'Disposable declined request control' });
    await declinedCard
      .getByLabel('Decision note for ' + requestedClass.subject.code, { exact: true })
      .fill('Declined disposable acceptance control');
    const declinedResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
        `/api/v1/timetables/requests/${declinedRequestId}/decision`,
    );
    await declinedCard.getByRole('button', { name: 'Decline request', exact: true }).click();
    const declinedReply = await declinedResponse;
    assert.equal(declinedReply.status(), 200);
    assert.equal((await declinedReply.json()).data.status, 'rejected');
    await page.goto(
      origin + `/admin/schedule-manager/drafts/${published.draft_id}?source=academic`,
    );
    await page.getByText('Review publication', { exact: true }).click();
    await page.getByRole('button', { name: 'Prepare revised version', exact: true }).click();
    await page.getByText('Holidays and occurrence changes', { exact: true }).click();
    await page.getByRole('button', { name: 'Remove exception', exact: true }).click();
    await page.getByRole('button', { name: 'Revalidate for publication', exact: true }).click();
    const rollbackResponse = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/timetables/publish',
    );
    await page.getByRole('button', { name: 'Publish reviewed timetable', exact: true }).click();
    const rollbackReply = await rollbackResponse;
    assert.equal(rollbackReply.status(), 200);
    const rolledBack = (await rollbackReply.json()).data;
    assert.equal(rolledBack.revision, 4);
    const adminHeaders = {
      Authorization: rollbackReply.request().headers()['authorization'],
      'X-ClassSync-Role': 'administrator',
    };
    for (const role of ['teacher', 'student']) {
      const restoredReply = await page.request.get(
        origin +
          `/api/v1/timetables/calendar/${config.fixture.period}?start=2026-10-05&end=2026-10-11&role=${role}`,
        { headers: { Authorization: tokens[role], 'X-ClassSync-Role': role } },
      );
      assert.equal(restoredReply.status(), 200);
      const restored = (await restoredReply.json()).data;
      assert.equal(restored.version, rolledBack.id);
      assert.equal(
        restored.occurrences.find((item) => item.id === requestedClass.id).room.id,
        requestedClass.room.id,
      );
    }
    await shot('administrator-validated-rollback');
    const academicPath = origin + `/api/v1/academic/periods/${config.fixture.period}`;
    const snapshot = (
      await (await page.request.get(academicPath, { headers: adminHeaders })).json()
    ).data;
    const rules = snapshot.records.find((item) => item.record.kind === 'constraints');
    const rulesPath = academicPath + '/records/constraints/' + rules.record.id;
    const blockedReply = await page.request.put(rulesPath, {
      headers: adminHeaders,
      data: {
        expected_revision: rules.revision,
        record: { ...rules.record, all_intended_offerings_supplied: false },
      },
    });
    assert.equal(blockedReply.status(), 200);
    const blocked = (await blockedReply.json()).data;
    const readinessReply = await page.request.get(
      origin + `/api/v1/scheduling/academic/${config.fixture.period}/readiness`,
      { headers: adminHeaders },
    );
    assert.equal(readinessReply.status(), 200);
    assert.equal((await readinessReply.json()).data.ready, false);
    const blockedGeneration = await page.request.post(
      origin + `/api/v1/scheduling/academic/${config.fixture.period}/generate`,
      { headers: adminHeaders, data: { expected_revision: blocked.period.revision } },
    );
    assert.equal(blockedGeneration.status(), 422);
    const blockedCommand = {
      ...rollbackReply.request().postDataJSON(),
      expected_version: 4,
      expected_academic_revision: blocked.period.revision,
      idempotency_key: require('node:crypto').randomUUID(),
    };
    for (const operation of ['review', 'publish']) {
      const result = await page.request.post(origin + '/api/v1/timetables/' + operation, {
        headers: adminHeaders,
        data: blockedCommand,
      });
      assert(
        [409, 422].includes(result.status()),
        'Incomplete inputs were accepted for publication',
      );
    }
    const blockedRule = blocked.records.find(
      (item) => item.record.id === rules.record.id && item.record.kind === 'constraints',
    );
    assert.equal(
      (
        await page.request.put(rulesPath, {
          headers: adminHeaders,
          data: { expected_revision: blockedRule.revision, record: rules.record },
        })
      ).status(),
      200,
    );
    const history = (
      await (
        await page.request.get(
          origin + `/api/v1/timetables/history/${config.fixture.period}?dataset=institutional`,
          { headers: adminHeaders },
        )
      ).json()
    ).data;
    assert.equal(history.versions.length, 4);
    const mvpFeatures = await require('./mvp_features_browser.cjs')({
      page,
      origin,
      config,
      tokens,
      adminHeaders,
      login,
      logout,
      visible,
      shot,
      nativeForm,
      teacherEmail,
      studentEmail,
    });
    await page.goto(origin + '/auth/account');
    await visible('Administrator membership verified');
    for (const uid of [teacherUid, studentUid]) {
      await page.getByText('Revoke university membership', { exact: true }).click();
      await page.getByLabel('Verified account reference', { exact: true }).fill(uid);
      await page.getByLabel('Current membership revision', { exact: true }).fill('1');
      await page.getByRole('button', { name: 'Revoke university access', exact: true }).click();
      await visible('University membership revoked.');
      await page.getByText('Revoke university membership', { exact: true }).click();
    }
    for (const role of ['teacher', 'student']) {
      const response = await page.request.get(
        origin +
          `/api/v1/timetables/calendar/${config.fixture.period}?start=2026-10-05&end=2026-10-11&role=${role}`,
        {
          headers: { Authorization: tokens[role], 'X-ClassSync-Role': role },
        },
      );
      assert.equal(response.status(), 403, 'Revoked institutional calendar remained accessible');
    }
    for (const role of ['teacher', 'student']) {
      const headers = { Authorization: tokens[role], 'X-ClassSync-Role': role };
      for (const path of ['community/announcements', 'timetables/rooms/' + config.fixture.period])
        assert.equal(
          (await page.request.get(origin + '/api/v1/' + path, { headers })).status(),
          403,
        );
    }
    assert.equal(
      (
        await page.request.get(origin + '/api/v1/timetables/requests', { headers: teacherHeaders })
      ).status(),
      403,
    );
    assert.equal(errors.length, 0, JSON.stringify(errors));
    assert(!statuses.includes(503), 'Unexpected healthy503');
    fs.writeFileSync(
      path.join(root, 'connected-browser-result.json'),
      JSON.stringify(
        {
          flow: 'approved student -> invited teacher -> Administrator readiness/generation/draft/review/publication -> identical authorized projections -> role denial -> revocation',
          projections,
          initialProjections,
          classroomRequest: {
            id: classroomRequest.id,
            status: fulfilled.status,
            fulfilledVersion: fulfilled.fulfilled_version,
            originalRoom: requestedClass.room.id,
            proposedRoom: proposedRoom.id,
          },
          requestReplayProtected: true,
          unassignedClassDenied: true,
          requestRoleIsolation: true,
          requestDeclineQualified: true,
          mvpFeatures,
          rollback: {
            revision: rolledBack.revision,
            version: rolledBack.id,
            bothRoleRoomsRestored: true,
          },
          incompleteReadinessBlockedGenerationReviewPublication: true,
          nativeChecks,
          elapsedMs: Date.now() - started,
          widths: [360, 390, 768, 1024, 1440],
          refreshRestored: true,
          currentRevocationDenied: true,
          crossRoleDenied: true,
          errors,
          statuses,
          screenshots,
          browserPlugin: 'unavailable',
          runtime: 'existing Playwright/Chrome',
          syntheticOnly: true,
          manualScreenReader: 'unverified',
          productionAcceptance: false,
        },
        null,
        2,
      ),
    );
  } catch (error) {
    fs.writeFileSync(
      path.join(root, 'connected-failure-network.json'),
      JSON.stringify({ network, errors }, null, 2),
    );
    if (page && !page.isClosed()) {
      fs.writeFileSync(
        path.join(root, 'connected-failure-dom.txt'),
        await page.locator('body').innerText(),
      );
      await page.screenshot({
        path: path.join(config.imageRoot, `m3-${path.basename(root).slice(-8)}-failure.png`),
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
