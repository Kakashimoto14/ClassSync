const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const test = require('node:test');
const { validateFixture } = require('../lib/web-session-fixture.cjs');

test('browser fixture accepts only its marked synthetic loopback services', () => {
  const root = path.join(fs.realpathSync(os.tmpdir()), 'classsync-auth-run-' + randomUUID().replaceAll('-', ''));
  fs.mkdirSync(root);
  const marker = { authOnly: true, project: 'demo-classsync-123456abcdef', endpoint: '127.0.0.1:54321' };
  fs.writeFileSync(path.join(root, 'owned-auth.json'), JSON.stringify(marker), { flag: 'wx' });
  const config = { root, project: marker.project, authEndpoint: marker.endpoint,
    gateway: 'http://127.0.0.1:54322', control: 'http://127.0.0.1:54323/fixture', nonce: 'a'.repeat(32) };
  assert.equal(validateFixture(config), root);
  for (const patch of [
    { root: os.tmpdir() }, { project: 'real-project' }, { nonce: '' },
    { authEndpoint: 'example.com:54321' }, { gateway: 'https://example.com' },
    { gateway: 'http://127.0.0.1:80' }, { gateway: 'http://127.0.0.1:54322?secret=x' },
    { gateway: 'http://user@127.0.0.1:54322' }, { control: 'http://127.0.0.1:54323/other' },
    { control: 'http://127.0.0.1:54323/fixture#ignored' },
    { control: 'http://127.0.0.1:54323/fixture?x=1' },
  ]) assert.throws(() => validateFixture({ ...config, ...patch }));
  // No recursive cleanup: retain the tiny marked fixture as disposable evidence.
});
