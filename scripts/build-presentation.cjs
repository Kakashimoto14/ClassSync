const { spawnSync } = require('node:child_process');
const { join } = require('node:path');
const { writeFileSync, readFileSync } = require('node:fs');

// Explicit release target. Ordinary `npm run build` keeps its existing defaults.
const root = join(__dirname, '..');
const result = spawnSync(
  process.execPath,
  [join(root, 'node_modules/typescript/bin/tsc'), '--noEmit'],
  { cwd: join(root, 'apps/web'), stdio: 'inherit' },
);
if (result.status !== 0) process.exit(result.status ?? 1);
const build = spawnSync(process.execPath, [join(root, 'node_modules/vite/bin/vite.js'), 'build'], {
  cwd: join(root, 'apps/web'),
  stdio: 'inherit',
  env: {
    ...process.env,
    VITE_ENABLE_ROLE_PREVIEW: 'true',
    VITE_ENABLE_PRESENTATION_SAMPLE: 'true',
  },
});
if (build.status !== 0) process.exit(build.status ?? 1);
const sha = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' });
const status = spawnSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' });
const sample = JSON.parse(
  readFileSync(join(root, 'apps/web/src/data/presentation-timetable.v1.json'), 'utf8'),
);
writeFileSync(
  join(root, 'apps/web/dist/release.json'),
  JSON.stringify(
    {
      schemaVersion: 1,
      mode: 'read-only-presentation',
      sampleVersion: sample.metadata.version,
      commit: process.env.VERCEL_GIT_COMMIT_SHA || (sha.status === 0 ? sha.stdout.trim() : null),
      uncommittedChanges: status.status === 0 ? Boolean(status.stdout.trim()) : null,
    },
    null,
    2,
  ) + '\n',
);
