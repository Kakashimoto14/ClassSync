const { spawn } = require('node:child_process');
const { existsSync } = require('node:fs');
const { join } = require('node:path');
const root = join(__dirname, '..');
const local = join(
  root,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
const child = spawn(
  existsSync(local) ? local : 'python',
  [join(__dirname, 'dev.py'), ...process.argv.slice(2)],
  {
    cwd: root,
    stdio: ['pipe', 'inherit', 'inherit'],
    windowsHide: true,
    env: { ...process.env, CLASSSYNC_NODE_RUNTIME: process.execPath },
  },
);
child.on('exit', (code) => process.exit(code ?? 1));
process.on('SIGINT', () => child.stdin.end('stop\n'));
process.on('SIGTERM', () => child.stdin.end('stop\n'));
process.stdin.on('data', (chunk) => {
  if (chunk.toString().trim() === 'stop') child.stdin.end('stop\n');
});
