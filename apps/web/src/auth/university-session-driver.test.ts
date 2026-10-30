// @vitest-environment node
import { beforeEach, expect, it, vi } from 'vitest';
import { loadUniversitySessionDriver } from './university-session-driver';

const sdk = vi.hoisted(() => ({
  mode: 'institutional',
  base: '/api/v1',
  app: {} as object | null,
  auth: { currentUser: { uid: 'uid-a' } as { uid: string } | null },
  observe: vi.fn(),
  signOut: vi.fn(),
  getAuth: vi.fn(),
}));
vi.mock('../config/runtime-config', () => ({
  get appMode() {
    return sdk.mode;
  },
}));
vi.mock('../lib/env', () => ({
  env: {
    get apiBaseUrl() {
      return sdk.base;
    },
  },
}));
vi.mock('../lib/firebase', () => ({
  get firebaseApp() {
    return sdk.app;
  },
}));
vi.mock('firebase/auth', () => ({
  getAuth: (...args: unknown[]) => {
    sdk.getAuth(...args);
    return sdk.auth;
  },
  onIdTokenChanged: sdk.observe,
  signOut: sdk.signOut,
}));
const membership = {
  uid: 'uid-a',
  tenant_id: 'tenant-a',
  role: 'student',
  student_id: 'student-a',
  membership_revision: 2,
};
let request: ReturnType<typeof vi.fn>;
const user = { uid: 'uid-a', getIdToken: vi.fn() };
beforeEach(() => {
  vi.clearAllMocks();
  sdk.mode = 'institutional';
  sdk.base = '/api/v1';
  sdk.app = {};
  sdk.auth.currentUser = { uid: 'uid-a' };
  vi.stubGlobal('window', { location: { origin: 'http://127.0.0.1:5173' } });
  vi.stubGlobal('navigator', { onLine: true });
  user.getIdToken.mockResolvedValue('opaque-sdk-token');
  request = vi.fn().mockResolvedValue(Response.json({ data: membership }));
  vi.stubGlobal('fetch', request);
});

it.each(['presentation', 'sandbox'])(
  'does not initialize identity SDK or fetch in %s mode',
  async (mode) => {
    sdk.mode = mode;
    expect(await loadUniversitySessionDriver()).toBeNull();
    expect(sdk.getAuth).not.toHaveBeenCalled();
    expect(request).not.toHaveBeenCalled();
  },
);
it('preserves missing Firebase as unavailable without fake identity', async () => {
  sdk.app = null;
  expect(await loadUniversitySessionDriver()).toBeNull();
  expect(sdk.getAuth).not.toHaveBeenCalled();
});
it('uses only current server membership with explicit safe request options', async () => {
  const driver = (await loadUniversitySessionDriver())!;
  const signal = new AbortController().signal;
  expect(await driver.lookup(user, 'student', signal)).toEqual(membership);
  expect(request).toHaveBeenCalledWith(
    'http://127.0.0.1:5173/api/v1/auth/me',
    expect.objectContaining({
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
      signal,
      headers: { Authorization: 'Bearer opaque-sdk-token', 'X-ClassSync-Role': 'student' },
    }),
  );
});
it.each([
  [401, 'invalid_token', 'denied'],
  [403, 'membership_denied', 'denied'],
  [403, 'role_selection_required', 'role-required'],
  [503, 'membership_unavailable', 'unavailable'],
])('maps HTTP%s/%s to %s without provider error details', async (status, code, issue) => {
  request.mockResolvedValue(
    Response.json({ error: { code, message: 'private sentinel' } }, { status: status as number }),
  );
  const driver = (await loadUniversitySessionDriver())!;
  await expect(driver.lookup(user, undefined, new AbortController().signal)).rejects.toMatchObject({
    issue,
  });
});
it.each([
  '//attacker.invalid/api',
  'http://attacker.invalid/api',
  'https://user:secret@example.invalid/api',
  '/api?redirect=elsewhere',
  '/api#fragment',
  'api/v1',
])('rejects unsafe API base %s before SDK use', async (base) => {
  sdk.base = base;
  await expect(loadUniversitySessionDriver()).rejects.toMatchObject({ issue: 'unavailable' });
  expect(sdk.getAuth).not.toHaveBeenCalled();
  expect(request).not.toHaveBeenCalled();
});
it('rejects a backslash-normalized external origin on an HTTPS page', async () => {
  vi.stubGlobal('window', { location: { origin: 'https://classsync.invalid' } });
  sdk.base = String.raw`/\attacker.invalid/api`;
  await expect(loadUniversitySessionDriver()).rejects.toMatchObject({ issue: 'unavailable' });
  expect(sdk.getAuth).not.toHaveBeenCalled();
});
it('does not send a token once its identity changes during token retrieval', async () => {
  user.getIdToken.mockImplementationOnce(async () => {
    sdk.auth.currentUser = { uid: 'uid-b' };
    return 'old-token';
  });
  const driver = (await loadUniversitySessionDriver())!;
  await expect(driver.lookup(user, undefined, new AbortController().signal)).rejects.toMatchObject({
    issue: 'denied',
  });
  expect(request).not.toHaveBeenCalled();
});
it('rejects stale identity after server response even before the observer callback', async () => {
  request.mockImplementationOnce(async () => {
    sdk.auth.currentUser = null;
    return Response.json({ data: membership });
  });
  const driver = (await loadUniversitySessionDriver())!;
  await expect(driver.lookup(user, undefined, new AbortController().signal)).rejects.toMatchObject({
    issue: 'denied',
  });
});
it('rejects HTML fallback and wrong response UID', async () => {
  const driver = (await loadUniversitySessionDriver())!;
  request.mockResolvedValueOnce(
    new Response('<html>fallback</html>', { headers: { 'content-type': 'text/html' } }),
  );
  await expect(driver.lookup(user, undefined, new AbortController().signal)).rejects.toMatchObject({
    issue: 'unavailable',
  });
  request.mockResolvedValueOnce(Response.json({ data: { ...membership, uid: 'another' } }));
  await expect(driver.lookup(user, undefined, new AbortController().signal)).rejects.toMatchObject({
    issue: 'unavailable',
  });
});
