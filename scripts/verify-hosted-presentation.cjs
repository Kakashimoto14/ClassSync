const { writeFileSync } = require('node:fs');
const { createHash } = require('node:crypto');

const applicationPaths = [
  '/',
  '/auth/login',
  '/student/dashboard',
  '/student/schedule',
  '/teacher/dashboard',
  '/teacher/schedule',
  '/admin/dashboard',
  '/admin/calendar',
  '/dev/role-preview',
  '/dev/design-system',
];
const paths = [
  ...applicationPaths,
  '/release.json',
  '/fonts/InterVariable.woff2',
  '/branding/classsync-logo-assets/classsync-icon-32.png',
  '/manifest.webmanifest',
  '/api/v1/timetables/periods',
  '/assets/p1-missing.js',
  '/p1-unknown',
];

async function verifyHosted(origin, expectedSha) {
  const read = (path) => fetch(origin + path, {
    signal: AbortSignal.timeout(15000),
    redirect: 'manual',
  });
  const homepage = await read('/');
  const html = await homepage.text();
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((match) => match[1]);
  const results = [];
  let release = null;
  for (const path of [...paths, ...assets]) {
    try {
      const response = await read(path);
      const body = Buffer.from(await response.arrayBuffer());
      if (path === '/release.json' && response.ok) {
        try {
          release = JSON.parse(body.toString('utf8'));
        } catch {
          release = null;
        }
      }
      results.push({
        path,
        status: response.status,
        contentType: response.headers.get('content-type'),
        cacheControl: response.headers.get('cache-control'),
        etag: response.headers.get('etag'),
        vercelId: response.headers.get('x-vercel-id'),
        bytes: body.length,
        sha256: createHash('sha256').update(body).digest('hex'),
        identity: /^(text\/|application\/(json|javascript|manifest\+json))/.test(
          response.headers.get('content-type') || '',
        )
          ? body.toString('utf8', 0, Math.min(120, body.length)).replace(/\s+/g, ' ')
          : null,
      });
    } catch (error) {
      results.push({ path, error: String(error) });
    }
  }
  const failed = [];
  if (!/^[a-f0-9]{40}$/i.test(expectedSha || '')) failed.push('approved-commit-required');
  if (!assets.some((path) => path.endsWith('.js'))) failed.push('application-javascript-required');
  if (!assets.some((path) => path.endsWith('.css'))) failed.push('application-stylesheet-required');
  const responseFor = (path) => results.find((entry) => entry.path === path);
  const shellHash = createHash('sha256').update(html).digest('hex');
  for (const path of applicationPaths) {
    const entry = responseFor(path);
    if (
      entry?.status !== 200 ||
      !entry.contentType?.startsWith('text/html') ||
      entry.sha256 !== shellHash
    ) failed.push(path);
  }
  const manifest = responseFor('/release.json');
  if (
    manifest?.status !== 200 ||
    !manifest.contentType?.includes('application/json') ||
    release?.schemaVersion !== 1 ||
    release?.mode !== 'read-only-presentation' ||
    release?.appMode !== 'presentation' ||
    release?.capabilityVersion !== 1 ||
    release?.sampleVersion !== 'classsync-presentation-v1' ||
    !/^[a-f0-9]{40}$/i.test(release?.commit || '') ||
    (expectedSha && release?.commit !== expectedSha) ||
    release?.uncommittedChanges !== false
  )
    failed.push('/release.json');
  const staticFiles = [
    ['/fonts/InterVariable.woff2', 'font/woff2'],
    ['/branding/classsync-logo-assets/classsync-icon-32.png', 'image/png'],
    ['/manifest.webmanifest', 'application/manifest+json'],
    ...assets.map((path) => [path, path.endsWith('.css') ? 'text/css' : 'application/javascript']),
  ];
  for (const [path, type] of staticFiles) {
    const entry = responseFor(path);
    if (entry?.status !== 200 || !entry.contentType?.startsWith(type)) failed.push(path);
  }
  for (const path of ['/api/v1/timetables/periods', '/assets/p1-missing.js', '/p1-unknown']) {
    const entry = responseFor(path);
    if (entry?.status !== 404 || entry.contentType?.includes('text/html')) failed.push(path);
  }
  const evidence = { origin, expectedSha: expectedSha || null, release, failed, results };
  return evidence;
}

async function main() {
  const origin = process.argv[2] || 'https://class-sync-bhiv.vercel.app';
  const evidence = await verifyHosted(origin, process.argv[4]);
  const { failed, release, results } = evidence;
  if (process.argv[3]) writeFileSync(process.argv[3], JSON.stringify(evidence, null, 2) + '\n');
  console.log(
    JSON.stringify(
      {
        origin,
        failed,
        release,
        responses: results.map(({ path, status, contentType }) => ({ path, status, contentType })),
      },
      null,
      2,
    ),
  );
  if (failed.length || results.some((entry) => entry.error)) process.exitCode = 1;
}

module.exports = { verifyHosted };
if (require.main === module)
  main().catch((error) => {
    console.error(error);
    process.exitCode = 2;
  });
