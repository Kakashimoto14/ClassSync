import { afterEach, expect, it, vi } from 'vitest';
import { listCalendarSamples, loadSampleCalendar } from './sample-calendar-api';
afterEach(() => vi.unstubAllGlobals());
it('discovers only server-approved samples across pages without loading draft snapshots', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ data: { drafts: [{ id: 'one' }], has_more: true } }), {
        headers: { 'content-type': 'application/json' },
      }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ data: { drafts: [{ id: 'two' }], has_more: false } }), {
        headers: { 'content-type': 'application/json' },
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  expect(await listCalendarSamples()).toEqual([{ id: 'one' }, { id: 'two' }]);
  expect(fetcher.mock.calls[1][0]).toContain('offset=1');
  expect(fetcher.mock.calls.every((c) => c[0].includes('/calendar-samples?'))).toBe(true);
});
it('preserves permission failure status and distinguishes a network outage', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ error: { message: 'Not permitted' } }), {
          status: 403,
          headers: { 'content-type': 'application/json' },
        }),
      ),
  );
  await expect(loadSampleCalendar('sample', '')).rejects.toMatchObject({
    status: 403,
    message: 'Not permitted',
  });
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(listCalendarSamples()).rejects.toThrow(
    'Could not reach the sample timetable service',
  );
});
