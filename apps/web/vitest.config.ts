import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Bundle the icon package once instead of loading its many modules per isolated DOM suite.
    deps: { optimizer: { client: { enabled: true, include: ['lucide-react'] } } },
    // Avoid many concurrent jsdom/React trees exhausting presentation laptops.
    maxWorkers: 2,
  },
});
