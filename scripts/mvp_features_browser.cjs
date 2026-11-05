/* Synthetic-only extension of the owned connected qualification. */
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

module.exports = async function qualifyFeatures({
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
}) {
  const api = origin + '/api/v1/community/announcements';
  const headers = (role) =>
    role === 'administrator'
      ? adminHeaders
      : {
          Authorization: tokens[role],
          'X-ClassSync-Role': role,
        };
  const directories = {};
  for (const role of ['student', 'teacher', 'administrator']) {
    const reply = await page.request.get(
      origin + '/api/v1/timetables/rooms/' + config.fixture.period,
      { headers: headers(role) },
    );
    assert.equal(reply.status(), 200);
    const data = (await reply.json()).data;
    assert.equal(data.rooms.length, 2);
    for (const room of data.rooms)
      assert.deepEqual(
        Object.keys(room).sort(),
        [
          'id',
          'name',
          'building',
          'floor',
          'location',
          'room_type',
          'capacity',
          'equipment',
        ].sort(),
      );
    directories[role] = data.rooms.map((room) => room.id).sort();
    const other = await page.request.get(origin + '/api/v1/timetables/rooms/' + randomUUID(), {
      headers: headers(role),
    });
    assert.equal(other.status(), 403);
  }
  assert.deepEqual(directories.student, directories.teacher);
  const title = 'Disposable university notice';
  await page.goto(origin + '/admin/announcements');
  await page.getByText('Create announcement', { exact: true }).click();
  await page.getByLabel('Title', { exact: true }).fill(title);
  await page
    .getByLabel('Message', { exact: true })
    .fill('Synthetic announcement for connected qualification.');
  const createResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/v1/community/announcements' &&
      response.request().method() === 'POST',
  );
  await nativeForm('m4-announcement', async () => {
    await page.getByRole('button', { name: 'Publish announcement', exact: true }).focus();
    await page.keyboard.press('Enter');
  });
  const createdReply = await createResponse;
  assert.equal(createdReply.status(), 201);
  const created = (await createdReply.json()).data;
  await page.getByRole('heading', { name: title, exact: true }).waitFor();
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await shot('m4-administrator-notices-' + width);
  }
  for (const role of ['student', 'teacher']) {
    const reply = await page.request.get(api, { headers: headers(role) });
    assert.equal(reply.status(), 200);
    assert((await reply.json()).data.announcements.some((item) => item.id === created.id));
    assert.equal(
      (
        await page.request.post(api, {
          headers: headers(role),
          data: {
            title: 'Unauthorized control',
            body: 'Invented text',
            audience: [role],
          },
        })
      ).status(),
      403,
    );
  }
  await page.getByRole('button', { name: 'Edit ' + title, exact: true }).click();
  await page.getByLabel('Message', { exact: true }).fill('Updated synthetic notice for Teachers.');
  await page.getByLabel('Students', { exact: true }).uncheck();
  const editResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith('/' + created.id),
  );
  await page.getByRole('button', { name: 'Save announcement', exact: true }).click();
  const editedReply = await editResponse;
  assert.equal(editedReply.status(), 200);
  const edited = (await editedReply.json()).data;
  assert.equal(edited.revision, 2);
  assert.equal(
    (
      await page.request.patch(api + '/' + created.id, {
        headers: adminHeaders,
        data: { title, body: 'Stale overwrite', audience: ['student'], expected_revision: 1 },
      })
    ).status(),
    409,
  );
  const students = await page.request.get(api, { headers: headers('student') });
  assert(!(await students.json()).data.announcements.some((item) => item.id === created.id));
  const teacherOnly = await page.request.get(api, { headers: headers('teacher') });
  assert((await teacherOnly.json()).data.announcements.some((item) => item.id === created.id));
  await logout();
  await login(teacherEmail);
  await visible('Teacher membership verified');
  await page.goto(origin + '/teacher/profile');
  await page.getByLabel('Account name', { exact: true }).fill('Synthetic Faculty Account');
  const profileResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/identitytoolkit.googleapis.com/v1/accounts:update'),
  );
  await page.getByRole('button', { name: 'Save account name', exact: true }).click();
  const profileReply = await profileResponse;
  assert.equal(profileReply.status(), 200);
  assert.equal((await profileReply.json()).displayName, 'Synthetic Faculty Account');
  await page.waitForFunction(
    () => document.querySelector('#account-display-name')?.value === 'Synthetic Faculty Account',
  );
  await page.reload();
  await page.getByLabel('Account name', { exact: true }).waitFor();
  assert.equal(
    await page.getByLabel('Account name', { exact: true }).inputValue(),
    'Synthetic Faculty Account',
  );
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await shot('m4-teacher-profile-' + width);
  }
  await page.getByRole('button', { name: 'Send password reset email', exact: true }).click();
  await visible('Password recovery requested. Check your email for the next steps.');
  const codes = await (
    await fetch(`http://${config.authEndpoint}/emulator/v1/projects/${config.project}/oobCodes`)
  ).json();
  assert(
    codes.oobCodes.some(
      (item) => item.email === teacherEmail && item.requestType === 'PASSWORD_RESET',
    ),
  );
  await page.goto(origin + `/teacher/find-room?period=${config.fixture.period}&date=2026-10-05`);
  await page
    .getByRole('link', { name: /^Room details for/ })
    .first()
    .waitFor();
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await shot('m4-teacher-rooms-' + width);
  }
  await page
    .getByRole('link', { name: /^Room details for/ })
    .first()
    .click();
  await page.getByRole('heading', { name: 'Location and facilities', exact: true }).waitFor();
  assert.equal(new URL(page.url()).searchParams.get('period'), config.fixture.period);
  await shot('m4-teacher-room-detail');
  await page.goto(origin + '/teacher/announcements');
  await page.getByText('Updated synthetic notice for Teachers.', { exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: /^Archive / }).count(), 0);
  await logout();
  await login(studentEmail);
  await visible('Student membership verified');
  await page.goto(
    origin + `/student/rooms?period=${config.fixture.period}&date=2026-10-05&category=all`,
  );
  await page
    .getByRole('link', { name: /^View .* details$/ })
    .first()
    .waitFor();
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await shot('m4-student-directory-' + width);
  }
  await page.goto(origin + '/student/announcements');
  await visible('No announcements yet.');
  await logout();
  await login(config.adminEmail);
  await visible('Administrator membership verified');
  await page.goto(origin + '/admin/announcements');
  const archiveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'DELETE' &&
      new URL(response.url()).pathname.endsWith('/' + created.id),
  );
  await page.getByRole('button', { name: 'Archive ' + title, exact: true }).click();
  assert.equal((await archiveResponse).status(), 200);
  await visible('No announcements yet.');
  assert.equal(
    (
      await page.request.patch(api + '/' + created.id, {
        headers: adminHeaders,
        data: { title, body: 'Archived overwrite', audience: ['student'], expected_revision: 3 },
      })
    ).status(),
    409,
  );
  return {
    roomDirectories: directories,
    audienceCrudAndArchive: true,
    staleRevisionDenied: true,
    teacherProfileRestore: true,
    actualPasswordResetEmail: true,
    nativeNoticeSubmission: true,
  };
};
