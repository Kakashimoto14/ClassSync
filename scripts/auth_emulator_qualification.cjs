/* Official pinned Auth server only, owned in-process; no CLI login or cloud lifecycle. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const { randomUUID } = require('node:crypto');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');

function localEmulatorEnvironment(source, root) {
  const environment = { ...source };
  for (const key of Object.keys(environment)) {
    if (/^(FIREBASE|GOOGLE|GCLOUD|CLOUDSDK)_/i.test(key) || /^(https?|all|no)_proxy$/i.test(key)) {
      delete environment[key];
    }
  }
  return { ...environment, NO_PROXY: '*', XDG_CONFIG_HOME: root, APPDATA: root,
    LOCALAPPDATA: root, FIREBASE_CLI_DISABLE_USAGE: 'true', CI: 'true' };
}

function qualificationModule(args) {
  const modes = {
    '--browser': 'scripts.postgres_web_session_qualification',
    '--academic': 'scripts.postgres_academic_provider_qualification',
    '--scheduling': 'scripts.postgres_scheduling_provider_qualification',
    '--publication': 'scripts.postgres_publication_provider_qualification',
    '--student-browser': 'scripts.postgres_student_experience_qualification',
  };
  const selected = args.length === 6 ? 'scripts.postgres_emulator_qualification'
    : args.length === 7 && Object.hasOwn(modes, args[6]) ? modes[args[6]] : undefined;
  if (!selected || args[0] !== '--tools-root' || args[2] !== '--postgres-bin' || args[4] !== '--output') {
    throw new Error('Explicit tools root, PostgreSQL bin and new output required');
  }
  return selected;
}

async function main() {
  const args = process.argv.slice(2);
  const selected = qualificationModule(args);
  const tools = fs.realpathSync(args[1]);
  const output = path.resolve(args[5]);
  if (path.dirname(tools) !== fs.realpathSync(os.tmpdir()) || !/^classsync-auth-tools-[a-f0-9]{32}$/.test(path.basename(tools))) {
    throw new Error('Disposable tools root required');
  }
  if (fs.existsSync(output) || !fs.statSync(path.dirname(output)).isDirectory()) {
    throw new Error('New output file in an existing directory required');
  }
  const modules = path.join(tools, 'node_modules');
  const manifest = JSON.parse(fs.readFileSync(path.join(modules, 'firebase-tools/package.json'), 'utf8'));
  const core = JSON.parse(fs.readFileSync(path.join(modules, '@opentelemetry/core/package.json'), 'utf8'));
  const uuid = JSON.parse(fs.readFileSync(path.join(modules, 'uuid/package.json'), 'utf8'));
  if (manifest.version !== '15.34.1' || core.version !== '2.8.0' || uuid.version !== '11.1.1') {
    throw new Error('Reviewed pinned emulator tool versions required');
  }
  const root = path.join(os.tmpdir(), 'classsync-auth-run-' + randomUUID().replaceAll('-', ''));
  fs.mkdirSync(root);
  console.log('Owned Auth Emulator root: ' + root);
  // Isolate any configstore lookup. No production credentials or account login.
  const isolated = localEmulatorEnvironment(process.env, root);
  for (const key of Object.keys(process.env)) delete process.env[key];
  Object.assign(process.env, isolated);
  // This process owns the Auth server; disallow outbound nonloopback sockets,
  // including metadata endpoints or accidentally configured blocking functions.
  const originalConnect = net.Socket.prototype.connect;
  let deniedOutbound = 0;
  net.Socket.prototype.connect = function (...parameters) {
    const options = net._normalizeArgs(parameters)[0];
    if (options.path || !['127.0.0.1', '::1', 'localhost'].includes(options.host || 'localhost')) {
      deniedOutbound++;
      throw new Error('Nonloopback emulator socket denied');
    }
    return originalConnect.apply(this, parameters);
  };
  const project = 'demo-classsync-' + randomUUID().replaceAll('-', '').slice(0, 12);
  const { createApp } = require(path.join(modules, 'firebase-tools/lib/emulator/auth/server.js'));
  const application = await createApp(project, 2); // Official ERROR single-project mode.
  const server = application.listen(0, '127.0.0.1');
  await new Promise((resolve, reject) => {
    server.once('listening', resolve);
    server.once('error', reject);
  });
  const endpoint = '127.0.0.1:' + server.address().port;
  const marker = { project, endpoint, toolsVersion: manifest.version, authOnly: true };
  let closing;
  const stopAuth = () => {
    if (!closing) {
      server.closeAllConnections();
      closing = new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
    return closing;
  };
  let exitCode;
  try {
    fs.writeFileSync(path.join(root, 'owned-auth.json'), JSON.stringify(marker), { flag: 'wx' });
    const repo = path.resolve(__dirname, '..');
    const child = spawn(path.join(repo, '.venv/Scripts/python.exe'), [
      '-m', selected, '--bin', path.resolve(args[3]),
      '--output', path.join(root, 'postgres-qualification.json'),
    ], {
      cwd: repo, windowsHide: true, stdio: ['ignore', 'pipe', 'inherit'],
      env: { ...process.env, FIREBASE_AUTH_EMULATOR_HOST: endpoint, CLASSSYNC_AUTH_RUN_ROOT: root },
    });
    let controlError;
    const lines = createInterface({ input: child.stdout });
    lines.on('line', (line) => {
      if (line === 'CLASSSYNC_OWNED_AUTH_STOP') {
        stopAuth().then(() => fs.writeFileSync(path.join(root, 'auth-stopped.json'),
          JSON.stringify({ endpoint, stopped: !server.listening }), { flag: 'wx' }))
          .catch((error) => { controlError = error; });
      } else console.log(line);
    });
    exitCode = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('exit', (code) => resolve(code));
    });
    if (controlError) throw controlError;
    if (exitCode !== 0) throw new Error('Owned PostgreSQL/emulator qualification failed');
  } finally {
    await stopAuth();
    net.Socket.prototype.connect = originalConnect;
    const evidence = { ...marker, root, authStopped: !server.listening, childExit: exitCode, deniedOutbound };
    fs.writeFileSync(path.join(root, 'auth-qualification.json'), JSON.stringify(evidence, null, 2), { flag: 'wx' });
  }
  if (deniedOutbound) throw new Error('Unexpected outbound attempt during local emulator qualification');
  const postgres = JSON.parse(fs.readFileSync(path.join(root, 'postgres-qualification.json'), 'utf8'));
  fs.writeFileSync(output, JSON.stringify({ ...marker, root, authStopped: !server.listening, deniedOutbound, postgres }, null, 2) + '\n', { flag: 'wx' });
  console.log('Actual owned Auth Emulator and disposable PostgreSQL stopped; qualification passed.');
}

module.exports = { localEmulatorEnvironment, qualificationModule };
if (require.main === module) {
  main().catch((error) => { console.error(error.message); process.exitCode = 1; });
}
