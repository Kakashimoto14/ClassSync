const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { createRequire } = require('node:module');
const { resolve } = require('node:path');
const { mkdtempSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const net = require('node:net');
const webRequire = createRequire(resolve(__dirname, '../../apps/web/package.json'));

test('Vite blocks denied synthetic files even with raw/import query parameters', async () => {
  const root = mkdtempSync(resolve(tmpdir(), 'classsync-vite-deny-'));
  writeFileSync(resolve(root, 'index.html'), '<!doctype html><title>Owned Vite deny probe</title>');
  writeFileSync(resolve(root, '.env'), 'SYNTHETIC_ONLY=not-a-secret');
  const reservation = net.createServer();
  await new Promise((done) => reservation.listen(0, '127.0.0.1', done));
  const port = reservation.address().port;
  await new Promise((done) => reservation.close(done));
  const { createServer } = await import('vite');
  const server = await createServer({ root, configFile:false, logLevel:'silent',
    server:{host:'127.0.0.1',port,strictPort:true,fs:{allow:[root]}} });
  try {
    await server.listen();
    for (const query of ['?raw','?import&raw','?import&url&inline']) {
      const response = await fetch(`http://127.0.0.1:${port}/.env${query}`);
      assert.equal(response.status,403);
      assert.ok(!(await response.text()).includes('SYNTHETIC_ONLY=not-a-secret'));
    }
  } finally { await server.close(); }
});

test('patched dependency versions are actually installed, not only declared', () => {
  assert.equal(webRequire('vitest/package.json').version, '4.1.12');
  assert.equal(webRequire('@vitest/mocker/package.json').version, '4.1.12');
  assert.equal(webRequire('@grpc/grpc-js/package.json').version, '1.14.5');
  assert.equal(webRequire('postcss-selector-parser/package.json').version, '7.1.6');
  const lock = JSON.parse(readFileSync(resolve(__dirname, '../../package-lock.json'), 'utf8'));
  assert.ok(!Object.keys(lock.packages).some((name) => name.endsWith('/zod')));
  assert.ok(!Object.keys(lock.packages).some((name) => name.endsWith('/tinypool')));
  assert.equal(webRequire('vite/package.json').version, '6.4.5');
  assert.equal(require(resolve(__dirname, '../../node_modules/vite/package.json')).version, '6.4.5');
  for (const [name, entry] of Object.entries(lock.packages)) {
    if (name.endsWith('/vite')) assert.equal(entry.version, '6.4.5');
  }
});

test('Firestore Node module can load with the patched grpc API without connecting', () => {
  const grpc = webRequire('@grpc/grpc-js');
  const metadata = new grpc.Metadata();
  metadata.set('classsync-test', 'local');
  assert.deepEqual(metadata.get('classsync-test'), ['local']);
  assert.equal(grpc.status.OK, 0);
  const firestore = webRequire('firebase/firestore');
  assert.equal(typeof firestore.initializeFirestore, 'function');
});

test('patched selector parser preserves the used Tailwind and nested selector APIs', async () => {
  const parser = webRequire('postcss-selector-parser');
  const classes = [];
  parser((selectors) => selectors.walkClasses((node) => classes.push(node.value)))
    .processSync(':is(.foo, .bar) > [data-state="open"]');
  assert.deepEqual(classes, ['foo', 'bar']);
  const postcss = webRequire('postcss');
  const tailwind = webRequire('tailwindcss');
  const nested = webRequire('postcss-nested');
  const result = await postcss([
    tailwind({ content: [{ raw: '<div class="p-4 hover:bg-rose-500 md:grid"></div>' }] }), nested,
  ]).process('@tailwind utilities; .parent { & > .child { color: red; } }', { from: undefined });
  assert.match(result.css, /\.p-4/);
  assert.match(result.css, /\.parent > \.child/);
  assert.match(result.css, /display: grid/);
});
