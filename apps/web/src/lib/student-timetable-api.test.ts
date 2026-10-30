import { afterEach, expect, it, vi } from 'vitest';
const auth = vi.hoisted(() => ({ user: null as null | { getIdToken: () => Promise<string> } }));
vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('./firebase', () => ({ firebaseApp: {} }));
vi.mock('./env', () => ({ env: { apiBaseUrl: '/api/v1' } }));
vi.mock('firebase/auth', () => ({ getAuth: () => ({ currentUser: auth.user }) }));
import { studentTimetableRequest } from './student-timetable-api';
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  auth.user = null;
});
it('times out a stalled token refresh before starting a request', async () => {
  vi.useFakeTimers();
  const token = vi.fn(() => new Promise<string>(() => {}));
  auth.user = { getIdToken: token };
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  const result = expect(studentTimetableRequest('periods')).rejects.toThrow('timed out');
  await vi.advanceTimersByTimeAsync(10000);
  await result;
  expect(fetcher).not.toHaveBeenCalled();
});
it.each(['publish', 'sandbox/periods', 'history/p', 'calendar/../publish', '//external'])(
  'rejects non-Student-read endpoint %s before network',
  async (path) => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    await expect(studentTimetableRequest(path)).rejects.toMatchObject({ status: 403 });
    expect(fetcher).not.toHaveBeenCalled();
  },
);
it('requires identity and sends current role/token to the Gateway without credentials', async () => {
  const fetcher = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ data: { periods: [] } }), {
      headers: { 'content-type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetcher);
  await expect(studentTimetableRequest('periods')).rejects.toMatchObject({ status: 401 });
  expect(fetcher).not.toHaveBeenCalled();
  auth.user = { getIdToken: vi.fn().mockResolvedValue('owned-token') };
  await expect(studentTimetableRequest('periods')).resolves.toEqual({ periods: [] });
  expect(fetcher).toHaveBeenCalledWith(
    expect.stringContaining('/api/v1/timetables/periods'),
    expect.objectContaining({
      headers: { Authorization: 'Bearer owned-token', 'X-ClassSync-Role': 'student' },
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
    }),
  );
});
it('retains server denial and never replaces it with data', async () => {
  auth.user = { getIdToken: vi.fn().mockResolvedValue('owned-token') };
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response('{"error":{}}', {
        status: 403,
        headers: { 'content-type': 'application/json' },
      }),
    ),
  );
  await expect(studentTimetableRequest('calendar/p')).rejects.toMatchObject({ status: 403 });
});
