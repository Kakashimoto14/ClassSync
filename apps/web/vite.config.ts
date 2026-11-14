import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { resolveAppMode } from './src/config/app-mode';
import { releaseMetadata } from './config/release-metadata';

export default defineConfig(({ command, mode }) => {
  const values = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const appMode = resolveAppMode({
    command,
    nodeEnv: values.NODE_ENV ?? values.VITE_USER_NODE_ENV,
    mode: values.VITE_CLASSSYNC_MODE,
    rolePreview: values.VITE_ENABLE_ROLE_PREVIEW,
    presentationSample: values.VITE_ENABLE_PRESENTATION_SAMPLE,
    presentationTarget: values.CLASSSYNC_BUILD_TARGET === 'presentation',
  });
  if (command === 'build' && values.CLASSSYNC_BUILD_TARGET === 'connected') {
    if (appMode !== 'institutional' || values.VITE_API_BASE_URL !== '/api/v1') {
      throw new Error('Connected builds require institutional mode and same-origin /api/v1.');
    }
    const required = [
      'VITE_FIREBASE_API_KEY',
      'VITE_FIREBASE_AUTH_DOMAIN',
      'VITE_FIREBASE_PROJECT_ID',
      'VITE_FIREBASE_APP_ID',
    ];
    const missing = required.filter((key) => !values[key]?.trim());
    if (missing.length) throw new Error('Missing connected configuration: ' + missing.join(', '));
    if (
      values.VITE_FIREBASE_PROJECT_ID.startsWith('demo-') ||
      !/^[a-z0-9][a-z0-9.-]*\.[a-z]+$/i.test(values.VITE_FIREBASE_AUTH_DOMAIN) ||
      values.VITE_FIREBASE_AUTH_DOMAIN.toLowerCase().endsWith('.localhost')
    ) {
      throw new Error('Connected builds require a hosted Firebase registration.');
    }
  }
  return {
    define: {
      __CLASSSYNC_APP_MODE__: JSON.stringify(appMode),
      __CLASSSYNC_DEV_SERVER__: JSON.stringify(command === 'serve'),
      // A plain dev launch can display the SaaS entrance without using inherited Auth settings.
      __CLASSSYNC_AUTH_CONFIG_ENABLED__: JSON.stringify(
        command === 'build' || values.VITE_CLASSSYNC_MODE === 'institutional',
      ),
    },
    plugins: [
      react(),
      {
        name: 'classsync-local-startup-guidance',
        configureServer(server) {
          if (appMode === 'institutional' && values.VITE_CLASSSYNC_MODE !== 'institutional') {
            server.config.logger.warn(
              '[ClassSync] Frontend-only session. For local authentication and APIs, run npm run dev:connected from this worktree.',
            );
          }
        },
      },
      {
        name: 'classsync-release-metadata',
        apply: 'build',
        generateBundle() {
          this.emitFile({
            type: 'asset',
            fileName: 'release.json',
            source: JSON.stringify(releaseMetadata(appMode), null, 2) + '\n',
          });
        },
      },
    ],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: process.env.CLASSSYNC_GATEWAY_URL ?? 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
