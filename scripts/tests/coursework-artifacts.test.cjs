const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const root = resolve(__dirname, '../..');
const read = (name) => JSON.parse(readFileSync(resolve(root, 'docs/api', name), 'utf8'));

test('Postman defaults contain no token and cannot execute cloud mutations without approval', () => {
  const collection = read('ClassSync.postman_collection.json');
  const environment = read('ClassSync.postman_environment.json');
  const values = Object.fromEntries(environment.values.map((item) => [item.key, item.value]));
  assert.equal(values.id_token, '');
  assert.equal(values.approved_cloud_qualification, 'false');
  assert.equal(values.approved_disposable_qualification, 'false');
  assert.equal(values.approved_synthetic_journey, 'false');
  assert(collection.item[0].item.every((item) => item.request.method === 'GET'));
  const guard = new Function('pm', collection.item[1].event[0].script.exec.join('\n'));
  let skipped = 0;
  const denied = (entries) => ({ environment: { get: (name) => entries[name] },
    variables: { get: (name) => entries[name] }, execution: { skipRequest: () => { skipped++; } } });
  assert.throws(() => guard(denied(values)), /Approved cloud/);
  assert.equal(skipped, 1);
  const localGuard = new Function('pm', collection.item[2].event[0].script.exec.join('\n'));
  assert.throws(() => localGuard(denied(values)), /Disposable qualification/);
  assert.equal(skipped, 2);
  const approved = { ...values, approved_disposable_qualification: 'true', base_url: 'https://example.test', auth_emulator_url: 'http://127.0.0.1:9099' };
  assert.throws(() => localGuard(denied(approved)), /Owned loopback/);
  assert.equal(skipped, 3);
  const override = denied({ ...approved, base_url: 'http://127.0.0.1:9098' });
  override.variables.get = (name) => name === 'base_url' ? 'http://127.0.0.2:9098' : approved[name];
  assert.throws(() => localGuard(override), /Owned loopback/);
  assert.equal(skipped, 4);
  for (const folder of collection.item) for (const item of folder.item) {
    for (const event of item.event) assert.doesNotThrow(() => new Function('pm', event.script.exec.join('\n')));
  }
});

test('Postman preference mutation serializes a numeric revision and generation precondition', () => {
  const collection = read('ClassSync.postman_collection.json');
  const item = collection.item[1].item.find((item) => item.request.method === 'PATCH');
  const body = JSON.parse(item.request.body.raw.replaceAll('{{preference_revision}}', '2')
    .replaceAll('{{preference_generation}}', '00000000-0000-4000-8000-000000000001'));
  assert.equal(body.expected_revision, 2);
  assert.equal(body.expected_generation, '00000000-0000-4000-8000-000000000001');
  assert.equal(body.compact, true);
});
