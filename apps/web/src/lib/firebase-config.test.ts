import { beforeEach, expect, it, vi } from 'vitest';
const sdk = vi.hoisted(() => ({ getApps: vi.fn(), initializeApp: vi.fn() }));
vi.mock('firebase/app', () => sdk);
import { configuredFirebase } from './firebase-config';
const config = {
  apiKey: 'test-key',
  authDomain: 'test.invalid',
  projectId: 'test-project',
  storageBucket: 'test-bucket',
  messagingSenderId: 'test-sender',
  appId: 'test-app',
};
beforeEach(() => {
  vi.clearAllMocks();
  sdk.getApps.mockReturnValue([]);
});
it('keeps absent/incomplete configuration distinct without initializing a misleading app', () => {
  expect(configuredFirebase({}).status).toBe('not-configured');
  expect(configuredFirebase({ projectId: 'test-project' }).status).toBe('incomplete');
  expect(sdk.initializeApp).not.toHaveBeenCalled();
});
it('reuses the existing registration across module reloads', () => {
  const app = { name: '[DEFAULT]', options: config };
  sdk.getApps.mockReturnValue([app]);
  expect(configuredFirebase(config).app).toBe(app);
  expect(sdk.initializeApp).not.toHaveBeenCalled();
});
it('does not initialize a second application on a project/app mismatch', () => {
  sdk.getApps.mockReturnValue([{ name: '[DEFAULT]', options: { ...config, projectId: 'other' } }]);
  expect(configuredFirebase(config).status).toBe('configuration-mismatch');
  expect(sdk.initializeApp).not.toHaveBeenCalled();
});
it('keeps an SDK initialization failure non-fatal for the read-only presentation', () => {
  sdk.initializeApp.mockImplementationOnce(() => {
    throw new Error('Invalid configuration');
  });
  expect(configuredFirebase(config)).toMatchObject({
    app: undefined,
    status: 'initialization-failed',
  });
});
