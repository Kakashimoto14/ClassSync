import { afterEach, expect, it, vi } from 'vitest';
const auth = vi.hoisted(() => ({ user: null as null | { getIdToken: () => Promise<string> } }));
vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('./firebase', () => ({ firebaseApp: {} }));
vi.mock('./env', () => ({ env: { apiBaseUrl: '/api/v1' } }));
vi.mock('firebase/auth', () => ({ getAuth: () => ({ currentUser: auth.user }) }));
import { institutionalRequest } from './institutional-api';
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  auth.user = null;
});
it('shows the publication conflict supplied by the service', async () => {
  auth.user = { getIdToken: vi.fn().mockResolvedValue('synthetic-token') };
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: { error: { message: 'Review the latest published version.' } },
          }),
          { status: 409, headers: { 'content-type': 'application/json' } },
        ),
      ),
  );
  await expect(institutionalRequest('timetables/publish')).rejects.toMatchObject({
    status: 409,
    message: 'Review the latest published version.',
  });
});
it.each([
  'https://external.invalid',
  '//external.invalid',
  'timetables/../auth/me',
  'academic/sandbox/periods',
  'scheduling/\\external',
])('rejects unsafe or sandbox path %s before sending credentials', async (path) => {
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  await expect(institutionalRequest(path)).rejects.toMatchObject({ status: 403 });
  expect(fetcher).not.toHaveBeenCalled();
});
it('bounds a stalled token before a privileged mutation', async () => {
  vi.useFakeTimers();
  auth.user = { getIdToken: () => new Promise(() => {}) };
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  const failure = expect(
    institutionalRequest('timetables/publish', { method: 'POST', body: {} }),
  ).rejects.toThrow('timed out');
  await vi.advanceTimersByTimeAsync(10000);
  await failure;
  expect(fetcher).not.toHaveBeenCalled();
});
it('does not send a mutation after the account changes during token acquisition', async () => {
  let resolveToken!: (token: string) => void;
  auth.user = {
    getIdToken: () =>
      new Promise((resolve) => {
        resolveToken = resolve;
      }),
  };
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  const failure = expect(
    institutionalRequest('timetables/publish', { method: 'POST', body: {} }),
  ).rejects.toThrow('cancelled');
  await vi.waitFor(() => expect(resolveToken).toBeTypeOf('function'));
  auth.user = null;
  resolveToken('old-token');
  await failure;
  expect(fetcher).not.toHaveBeenCalled();
});
it.each(['teacher', 'administrator'] as const)(
  'sends verified identity and %s role hint to the same-origin Gateway and retains denials',
  async (role) => {
    auth.user = { getIdToken: vi.fn().mockResolvedValue('synthetic-token') };
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"error":{"message":"Current access revoked"}}', {
        status: 403,
        headers: { 'content-type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetcher);
    await expect(institutionalRequest('timetables/periods', { role })).rejects.toMatchObject({
      status: 403,
      message: 'Current access revoked',
    });
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/timetables/periods'),
      expect.objectContaining({
        headers: { Authorization: 'Bearer synthetic-token', 'X-ClassSync-Role': role },
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
      }),
    );
  },
);
it('retries one cold-start read but never repeats a mutation', async () => {
  vi.useFakeTimers();
  auth.user = { getIdToken: vi.fn().mockResolvedValue('synthetic-token') };
  const reply = (status: number, body: string) =>
    new Response(body, { status, headers: { 'content-type': 'application/json' } });
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(reply(503, '{"error":{"message":"Waking"}}'))
    .mockResolvedValueOnce(reply(200, '{"data":{"periods":[]}}'));
  vi.stubGlobal('fetch', fetcher);
  const read = institutionalRequest('timetables/periods');
  await vi.advanceTimersByTimeAsync(1500);
  await expect(read).resolves.toEqual({ periods: [] });
  expect(fetcher).toHaveBeenCalledTimes(2);
  fetcher.mockReset().mockResolvedValue(reply(503, '{"error":{"message":"Waking"}}'));
  await expect(
    institutionalRequest('timetables/publish', { method: 'POST', body: {} }),
  ).rejects.toMatchObject({ status: 503 });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
