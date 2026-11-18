/* Official pinned Auth server only, owned in-process; no CLI login or cloud lifecycle. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const net = require('node:net');
const { randomUUID } = require('node:crypto');
const { spawn, spawnSync } = require('node:child_process');
const { createInterface } = require('node:readline');

function localEmulatorEnvironment(source, root) {
  const environment = { ...source };
  for (const key of Object.keys(environment)) {
    if (
      /^(FIREBASE|GOOGLE|GCLOUD|CLOUDSDK|COURSE|GEMINI)_/i.test(key) ||
      /^(https?|all|no)_proxy$/i.test(key)
    ) {
      delete environment[key];
    }
  }
  return {
    ...environment,
    NO_PROXY: '*',
    XDG_CONFIG_HOME: root,
    APPDATA: root,
    LOCALAPPDATA: root,
    FIREBASE_CLI_DISABLE_USAGE: 'true',
    CI: 'true',
  };
}

function qualificationModule(args) {
  const modes = {
    '--browser': 'scripts.postgres_web_session_qualification',
    '--academic': 'scripts.postgres_academic_provider_qualification',
    '--scheduling': 'scripts.postgres_scheduling_provider_qualification',
    '--publication': 'scripts.postgres_publication_provider_qualification',
    '--student-browser': 'scripts.postgres_student_experience_qualification',
    '--onboarding': 'scripts.postgres_onboarding_qualification',
    '--onboarding-browser': 'scripts.postgres_onboarding_browser_qualification',
    '--scanner-browser': 'scripts.postgres_registration_browser_qualification',
    '--connected-browser': 'scripts.postgres_connected_browser_qualification',
    '--postman': 'scripts.postgres_postman_qualification',
    '--firestore-slice': 'scripts.postgres_firestore_access_qualification',
  };
  const selected =
    args.length === 6
      ? 'scripts.postgres_emulator_qualification'
      : args.length === 7 && Object.hasOwn(modes, args[6])
        ? modes[args[6]]
        : undefined;
  if (
    !selected ||
    args[0] !== '--tools-root' ||
    args[2] !== '--postgres-bin' ||
    args[4] !== '--output'
  ) {
    throw new Error('Explicit tools root, PostgreSQL bin and new output required');
  }
  return selected;
}

function pinnedTools(root) {
  try {
    return [
      ['firebase-tools', '15.34.1'],
      ['@opentelemetry/core', '2.8.0'],
      ['uuid', '11.1.1'],
    ].every(
      ([name, version]) =>
        JSON.parse(fs.readFileSync(path.join(root, 'node_modules', name, 'package.json'), 'utf8'))
          .version === version,
    );
  } catch {
    return false;
  }
}

async function developmentArguments(repo) {
  if (process.platform !== 'win32' || process.versions.node.split('.')[0] !== '22')
    throw new Error('Connected development requires Windows SSPI and Node.js 22.');
  const temp = fs.realpathSync(os.tmpdir());
  const candidates = process.env.CLASSSYNC_AUTH_TOOLS_ROOT
    ? [process.env.CLASSSYNC_AUTH_TOOLS_ROOT]
    : fs
        .readdirSync(temp, { withFileTypes: true })
        .filter(
          (entry) => entry.isDirectory() && /^classsync-auth-tools-[a-f0-9]{32}$/.test(entry.name),
        )
        .map((entry) => path.join(temp, entry.name));
  const tools = candidates.find(pinnedTools);
  if (!tools)
    throw new Error(
      'Missing pinned Auth Emulator tools. See docs/infrastructure/local-connected-development.md.',
    );
  const pg =
    process.env.CLASSSYNC_POSTGRES_BIN ??
    (process.env.Path ?? process.env.PATH ?? '')
      .split(path.delimiter)
      .find((dir) => dir && fs.existsSync(path.join(dir, 'pg_ctl.exe')));
  if (
    !pg ||
    !['initdb', 'pg_ctl', 'psql', 'pg_dump', 'pg_restore'].every((file) =>
      fs.existsSync(path.join(pg, file + '.exe')),
    )
  )
    throw new Error(
      'Install PostgreSQL for Windows and add its bin to PATH or set CLASSSYNC_POSTGRES_BIN.',
    );
  const python = path.join(repo, '.venv/Scripts/python.exe');
  if (!fs.existsSync(python))
    throw new Error('Missing worktree .venv. Follow local-connected-development.md.');
  if (!fs.existsSync(path.join(repo, 'node_modules/vite/package.json')))
    throw new Error('Missing frontend dependencies. Run npm ci in the feature worktree.');
  const rawPort = process.env.CLASSSYNC_DEV_PORT ?? '5191';
  if (!/^\d+$/.test(rawPort) || Number(rawPort) < 1024 || Number(rawPort) > 65535)
    throw new Error('CLASSSYNC_DEV_PORT must be a TCP port from 1024 to 65535.');
  const probe = net.createServer();
  await new Promise((resolve, reject) => {
    probe.once('error', () =>
      reject(new Error(`Port ${rawPort} is occupied. Set CLASSSYNC_DEV_PORT to a free port.`)),
    );
    probe.listen(Number(rawPort), '127.0.0.1', resolve);
  });
  await new Promise((resolve) => probe.close(resolve));
  const pythonPath = ['packages/api-contracts', 'packages/persistence']
    .map((dir) => path.join(repo, dir))
    .join(path.delimiter);
  const ready = spawnSync(
    python,
    [
      '-c',
      'import sys; assert sys.version_info[:2] == (3, 12); import fastapi, firebase_admin, uvicorn, httpx, pytest, psycopg, alembic, ortools, classync_persistence',
    ],
    {
      env: { ...process.env, PYTHONPATH: pythonPath },
      stdio: 'ignore',
      timeout: 15000,
    },
  );
  if (ready.status !== 0)
    throw new Error(
      'The worktree .venv must use Python 3.12 with the locked backend dependencies installed.',
    );
  const receipts = path.join(repo, 'var', 'connected-dev');
  fs.mkdirSync(receipts, { recursive: true });
  return {
    args: [
      '--tools-root',
      tools,
      '--postgres-bin',
      pg,
      '--output',
      path.join(receipts, randomUUID() + '.json'),
      '--connected-browser',
    ],
    env: {
      PYTHONPATH: pythonPath,
      CLASSSYNC_DEV_PORT: rawPort,
      CLASSSYNC_ONBOARDING_PREVIEW: 'true',
      CLASSSYNC_PERSISTENT_DEV: 'true',
      CLASSSYNC_DEV_SUPERVISOR_PID: String(process.pid),
    },
  };
}

async function main() {
  const repo = path.resolve(__dirname, '..');
  const requested = process.argv.slice(2);
  const development =
    requested.length === 1 && requested[0] === '--development'
      ? await developmentArguments(repo)
      : null;
  const args = development?.args ?? requested;
  const selected = qualificationModule(args);
  const tools = fs.realpathSync(args[1]);
  const output = path.resolve(args[5]);
  if (
    path.dirname(tools) !== fs.realpathSync(os.tmpdir()) ||
    !/^classsync-auth-tools-[a-f0-9]{32}$/.test(path.basename(tools))
  ) {
    throw new Error('Disposable tools root required');
  }
  if (fs.existsSync(output) || !fs.statSync(path.dirname(output)).isDirectory()) {
    throw new Error('New output file in an existing directory required');
  }
  const modules = path.join(tools, 'node_modules');
  const manifest = JSON.parse(
    fs.readFileSync(path.join(modules, 'firebase-tools/package.json'), 'utf8'),
  );
  if (!pinnedTools(tools)) {
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
      closing = new Promise((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    }
    return closing;
  };
  let exitCode;
  try {
    fs.writeFileSync(path.join(root, 'owned-auth.json'), JSON.stringify(marker), { flag: 'wx' });
    const stop = () => fs.writeFileSync(path.join(root, 'stop-preview'), '');
    const terminal = development ? createInterface({ input: process.stdin }) : null;
    terminal?.on('line', (line) => {
      if (line.trim() === 'stop') stop();
    });
    if (development) {
      process.on('SIGINT', stop);
      process.on('SIGTERM', stop);
    }
    const child = spawn(
      path.join(repo, '.venv/Scripts/python.exe'),
      [
        '-m',
        selected,
        '--bin',
        path.resolve(args[3]),
        '--output',
        path.join(root, 'postgres-qualification.json'),
      ],
      {
        cwd: repo,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'inherit'],
        env: {
          ...process.env,
          CLASSSYNC_PERSISTENT_DEV: 'false',
          ...development?.env,
          FIREBASE_AUTH_EMULATOR_HOST: endpoint,
          CLASSSYNC_AUTH_RUN_ROOT: root,
        },
      },
    );
    let controlError;
    const lines = createInterface({ input: child.stdout });
    lines.on('line', (line) => {
      if (line === 'CLASSSYNC_OWNED_AUTH_STOP') {
        stopAuth()
          .then(() =>
            fs.writeFileSync(
              path.join(root, 'auth-stopped.json'),
              JSON.stringify({ endpoint, stopped: !server.listening }),
              { flag: 'wx' },
            ),
          )
          .catch((error) => {
            controlError = error;
          });
      } else console.log(line);
    });
    try {
      exitCode = await new Promise((resolve, reject) => {
        child.once('error', reject);
        child.once('exit', (code) => resolve(code));
      });
    } finally {
      if (development) stop();
      terminal?.close();
      if (development) {
        process.removeListener('SIGINT', stop);
        process.removeListener('SIGTERM', stop);
      }
    }
    if (controlError) throw controlError;
    if (exitCode !== 0) throw new Error('Owned PostgreSQL/emulator qualification failed');
  } finally {
    await stopAuth();
    net.Socket.prototype.connect = originalConnect;
    const evidence = {
      ...marker,
      root,
      authStopped: !server.listening,
      childExit: exitCode,
      deniedOutbound,
    };
    fs.writeFileSync(
      path.join(root, 'auth-qualification.json'),
      JSON.stringify(evidence, null, 2),
      { flag: 'wx' },
    );
  }
  if (deniedOutbound)
    throw new Error('Unexpected outbound attempt during local emulator qualification');
  const postgres = JSON.parse(
    fs.readFileSync(path.join(root, 'postgres-qualification.json'), 'utf8'),
  );
  fs.writeFileSync(
    output,
    JSON.stringify(
      { ...marker, root, authStopped: !server.listening, deniedOutbound, postgres },
      null,
      2,
    ) + '\n',
    { flag: 'wx' },
  );
  console.log(
    development
      ? 'Connected development stopped. Auth and the disposable PostgreSQL server are offline.'
      : 'Actual owned Auth Emulator and disposable PostgreSQL stopped; qualification passed.',
  );
}

module.exports = {
  localEmulatorEnvironment,
  qualificationModule,
  pinnedTools,
  developmentArguments,
};
if (require.main === module) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
