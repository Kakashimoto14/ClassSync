const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { mkdtempSync, readFileSync, readdirSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { resolve, join } = require('node:path');
const { artifactServer } = require('../lib/artifact-server.cjs');

const root = resolve(__dirname, '../..');
const config = JSON.parse(readFileSync(join(root, 'vercel.json'), 'utf8'));
const output = mkdtempSync(join(tmpdir(), 'classsync-p1-artifacts-'));
function build(extra, name, args = []) {
  const env = { ...process.env };
  for (const key of [
    'VITE_CLASSSYNC_MODE',
    'VITE_ENABLE_ROLE_PREVIEW',
    'VITE_ENABLE_PRESENTATION_SAMPLE',
    'CLASSSYNC_BUILD_TARGET',
    'NODE_ENV',
  ])
    delete env[key];
  const result = spawnSync(
    process.execPath,
    [join(root, 'node_modules/vite/bin/vite.js'), 'build', '--outDir', join(output, name), ...args],
    {
      cwd: join(root, 'apps/web'),
      env: { ...env, ...extra },
      encoding: 'utf8',
      timeout: 120000,
    },
  );
  return { ...result, directory: join(output, name) };
}

test('actual Vite builds reject unsafe configuration before emitting artifacts', () => {
  const cases = [
    [{ VITE_CLASSSYNC_MODE: 'sandbox' }],
    [{ VITE_CLASSSYNC_MODE: 'sandbox', NODE_ENV: 'development' }, ['--mode', 'development']],
    [{ VITE_CLASSSYNC_MODE: 'typo' }],
    [{ VITE_ENABLE_ROLE_PREVIEW: 'TRUE' }],
    [{ VITE_ENABLE_ROLE_PREVIEW: 'true', VITE_ENABLE_PRESENTATION_SAMPLE: 'false' }],
    [{ VITE_CLASSSYNC_MODE: 'institutional', VITE_ENABLE_ROLE_PREVIEW: 'true' }],
    [{ CLASSSYNC_BUILD_TARGET: 'presentation', VITE_CLASSSYNC_MODE: 'institutional' }],
    [{ CLASSSYNC_BUILD_TARGET: 'presentation', VITE_ENABLE_PRESENTATION_SAMPLE: 'false' }],
    [{ VERCEL_GIT_COMMIT_SHA: '0'.repeat(40) }],
  ];
  cases.forEach(([env, args], i) => {
    const result = build(env, `rejected-${i}`, args);
    assert.notEqual(result.status, 0, JSON.stringify(env));
    assert.match(
      result.stderr + result.stdout,
      /Sandbox|Invalid VITE|Legacy ClassSync|Contradictory|Institutional|Presentation|Release commit/,
    );
  });
});

for (const [name, env, expected] of [
  ['ordinary', {}, 'institutional'],
  ['presentation', { CLASSSYNC_BUILD_TARGET: 'presentation' }, 'presentation'],
  ['legacy-preview', { VITE_ENABLE_ROLE_PREVIEW: 'true' }, 'presentation'],
])
  test(`${name} production metadata, SPA refresh and static/API boundaries`, async () => {
    const built = build(env, name);
    assert.equal(built.status, 0, built.stderr + built.stdout);
    const release = JSON.parse(readFileSync(join(built.directory, 'release.json'), 'utf8'));
    assert.equal(release.schemaVersion, 1);
    assert.equal(release.appMode, expected);
    assert.equal(release.capabilityVersion, 1);
    assert.match(release.commit, /^[a-f0-9]{40}$/);
    assert.equal(typeof release.uncommittedChanges, 'boolean');
    if (expected === 'presentation') {
      assert.equal(release.mode, 'read-only-presentation');
      assert.equal(release.sampleVersion, 'classsync-presentation-v1');
    }
    const server = artifactServer(built.directory, config);
    await new Promise((done) => server.listen(0, '127.0.0.1', done));
    const origin = `http://127.0.0.1:${server.address().port}`;
    try {
      const html = readFileSync(join(built.directory, 'index.html'), 'utf8');
      for (const path of [
        '/',
        '/auth/login',
        '/dev/role-preview',
        '/dev/design-system',
        '/student/dashboard',
        '/student/schedule',
        '/teacher/dashboard',
        '/teacher/schedule',
        '/admin/dashboard',
        '/admin/calendar',
      ]) {
        for (let refresh = 0; refresh < 2; refresh++) {
          const response = await fetch(origin + path);
          assert.equal(response.status, 200, path);
          assert.equal(await response.text(), html, path);
        }
      }
      for (const path of [
        '/api/missing',
        '/api/v1/timetables/periods',
        '/assets/missing.js',
        '/branding/missing.png',
      ]) {
        const response = await fetch(origin + path);
        assert.equal(response.status, 404, path);
        assert.ok(!response.headers.get('content-type').includes('text/html'));
      }
      const script = readdirSync(join(built.directory, 'assets')).find((p) => p.endsWith('.js'));
      const response = await fetch(origin + '/assets/' + script);
      assert.equal(response.status, 200);
      assert.match(response.headers.get('content-type'), /javascript/);
      assert.notEqual(await response.text(), html);
      for (const asset of [
        '/branding/classsync-logo-assets/classsync-icon-32.png',
        '/branding/classsync-logo-assets/classsync-horizontal-light.png',
        '/fonts/InterVariable.woff2',
        '/manifest.webmanifest',
      ]) {
        const response = await fetch(origin + asset);
        assert.equal(response.status, 200, asset);
        assert.ok(!response.headers.get('content-type').includes('text/html'), asset);
        assert.ok((await response.arrayBuffer()).byteLength > 0, asset);
      }
      for (const method of ['POST', 'PUT', 'DELETE']) {
        const response = await fetch(origin + '/api/v1/timetables/publish', { method });
        assert.equal(response.status, 404, method);
        assert.ok(!response.headers.get('content-type').includes('text/html'));
      }
      assert.deepEqual(await (await fetch(origin + '/release.json')).json(), release);
      console.log(`Verified ${name}: ${built.directory}`);
    } finally {
      await new Promise((done) => server.close(done));
    }
  });
