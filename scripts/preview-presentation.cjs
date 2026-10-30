const { readFileSync, existsSync } = require('node:fs');
const { resolve } = require('node:path');
const project = resolve(__dirname, '..');
const config = JSON.parse(readFileSync(resolve(project, 'vercel.json'), 'utf8'));
const root = resolve(
  process.env.CLASSSYNC_PRESENTATION_DIST || resolve(project, config.outputDirectory),
);
const port = Number(process.env.CLASSSYNC_PRESENTATION_PORT || 5188);
if (!existsSync(resolve(root, 'index.html')))
  throw new Error('Build first: npm run build:presentation');
if (
  !existsSync(resolve(root, 'release.json')) ||
  JSON.parse(readFileSync(resolve(root, 'release.json'), 'utf8')).mode !== 'read-only-presentation'
)
  throw new Error('This is not the presentation artifact. Run npm run build:presentation first.');
const { artifactServer } = require('./lib/artifact-server.cjs');
const server = artifactServer(root, config);
server.on('error', (e) => {
  console.error(`Presentation preview failed: ${e.message}. No alternate port was started.`);
  process.exit(1);
});
server.listen(port, '127.0.0.1', () =>
  console.log(`Production artifact; Vercel-config route emulation: http://127.0.0.1:${port}`),
);
