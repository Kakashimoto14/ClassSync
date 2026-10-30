const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

function validateFixture(config) {
  assert.equal(typeof config.root, 'string');
  const root = path.resolve(config.root);
  assert.equal(path.dirname(root), fs.realpathSync(os.tmpdir()));
  assert.match(path.basename(root), /^classsync-auth-run-[a-f0-9]{32}$/);
  assert.equal(fs.realpathSync(root), root, 'No redirected fixture root');
  const marker = JSON.parse(fs.readFileSync(path.join(root, 'owned-auth.json'), 'utf8'));
  assert.equal(marker.authOnly, true);
  assert.match(config.project, /^demo-classsync-[a-f0-9]{12}$/);
  assert.equal(config.project, marker.project);
  assert.equal(config.authEndpoint, marker.endpoint);
  assert.match(config.authEndpoint, /^127\.0\.0\.1:[0-9]+$/);
  const local = (value, pathname) => {
    assert.equal(typeof value, 'string');
    const url = new URL(value);
    assert.equal(url.protocol, 'http:');
    assert.equal(url.hostname, '127.0.0.1');
    assert.ok(Number(url.port) > 1024 && Number(url.port) <= 65535);
    assert.equal(url.pathname, pathname);
    assert.equal(url.username + url.password + url.search + url.hash, '');
    assert.equal(value, url.origin + (pathname === '/' ? '' : pathname));
  };
  local('http://' + config.authEndpoint, '/');
  local(config.gateway, '/');
  local(config.control, '/fixture');
  assert.match(config.nonce, /^[a-f0-9]{32}$/);
  return root;
}
module.exports = { validateFixture };
