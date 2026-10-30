const { spawnSync } = require('node:child_process');
const { join } = require('node:path');

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
    CLASSSYNC_BUILD_TARGET: 'presentation',
  },
});
if (build.status !== 0) process.exit(build.status ?? 1);
