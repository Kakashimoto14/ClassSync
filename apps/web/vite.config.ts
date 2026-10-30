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
  return {
    define: { __CLASSSYNC_APP_MODE__: JSON.stringify(appMode) },
    plugins: [
      react(),
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
