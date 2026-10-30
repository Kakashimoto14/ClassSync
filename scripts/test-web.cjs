const { spawnSync } = require('node:child_process');
const { resolve } = require('node:path');

// Use the qualified direct invocation and working directory on Windows as well as CI.
// A bounded whole-run timeout fails the command; it never skips or retries a test.
// Honor the app configuration's two-worker cap and default per-file isolation.
const result = spawnSync(
  process.execPath,
  [resolve(__dirname, '../node_modules/vitest/vitest.mjs'), 'run', '--pool=threads',
    '--reporter=verbose', ...process.argv.slice(2)],
  { cwd: resolve(__dirname, '../apps/web'), encoding: 'utf8', timeout: 300000,
    maxBuffer: 16 * 1024 * 1024 },
);
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
if (result.error) console.error(result.error);
process.exitCode = result.status ?? 1;
