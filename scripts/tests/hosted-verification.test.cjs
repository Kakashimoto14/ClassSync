const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { verifyHosted } = require('../verify-hosted-presentation.cjs');

const commit = 'a'.repeat(40);
async function fixture(run, { assets = true, dirty = false, brokenPath, redirectPath } = {}) {
  const server = createServer((req, res) => {
    const path = req.url;
    let type = 'text/html',
      status = 200,
      body = assets
        ? '<script src="/assets/app.js"></script><link href="/assets/app.css" rel="stylesheet">'
        : '<main>Not an application bundle</main>';
    if (path === '/release.json') {
      type = 'application/json';
      body = JSON.stringify({
        schemaVersion: 1,
        mode: 'read-only-presentation',
        appMode: 'presentation',
        capabilityVersion: 1,
        sampleVersion: 'classsync-presentation-v1',
        commit,
        uncommittedChanges: dirty,
      });
    } else if (
      path.startsWith('/api/') ||
      path === '/assets/p1-missing.js' ||
      path === '/p1-unknown'
    ) {
      status = 404;
      type = 'text/plain';
      body = 'NOT_FOUND';
    } else if (path === '/fonts/InterVariable.woff2') type = 'font/woff2';
    else if (path.endsWith('.png')) type = 'image/png';
    else if (path.endsWith('.webmanifest')) type = 'application/manifest+json';
    else if (path.endsWith('.js')) type = 'application/javascript';
    else if (path.endsWith('.css')) type = 'text/css';
    if (path === brokenPath) body = '<main>Login required or application unavailable</main>';
    if (path === redirectPath) {
      status = 302;
      res.setHeader('Location', '/');
    }
    res.writeHead(status, { 'Content-Type': type });
    res.end(body);
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  try {
    await run(`http://127.0.0.1:${server.address().port}`);
  } finally {
    await new Promise((done) => server.close(done));
  }
}

test('hosted gate requires an independently supplied approved commit', async () => {
  await fixture(async (origin) => {
    const result = await verifyHosted(origin);
    assert.ok(result.failed.includes('approved-commit-required'));
  });
});
test('hosted gate rejects a different deployed commit', async () => {
  await fixture(async (origin) => {
    assert.ok((await verifyHosted(origin, 'b'.repeat(40))).failed.includes('/release.json'));
  });
});
test('hosted gate rejects a metadata-only HTML shell without JS and CSS', async () => {
  await fixture(
    async (origin) => {
      const result = await verifyHosted(origin, commit);
      assert.ok(result.failed.includes('application-javascript-required'));
      assert.ok(result.failed.includes('application-stylesheet-required'));
    },
    { assets: false },
  );
});
test('hosted gate rejects dirty release metadata', async () => {
  await fixture(
    async (origin) => {
      assert.ok((await verifyHosted(origin, commit)).failed.includes('/release.json'));
    },
    { dirty: true },
  );
});
test('hosted HTTP gate accepts matching clean metadata and route/static/API boundaries', async () => {
  await fixture(async (origin) => {
    const result = await verifyHosted(origin, commit);
    assert.deepEqual(result.failed, []);
    assert.ok(result.results.every((entry) => !entry.error));
  });
});

for (const brokenPath of ['/student/dashboard', '/student/schedule', '/teacher/dashboard', '/admin/calendar'])
  test(`hosted gate rejects a different HTML shell at ${brokenPath}`, async () => {
    await fixture(async (origin) => {
      assert.ok((await verifyHosted(origin, commit)).failed.includes(brokenPath));
    }, { brokenPath });
  });

test('hosted gate rejects deep-link redirects even to the valid application shell', async () => {
  await fixture(async (origin) => {
    assert.ok((await verifyHosted(origin, commit)).failed.includes('/teacher/schedule'));
  }, { redirectPath: '/teacher/schedule' });
});
