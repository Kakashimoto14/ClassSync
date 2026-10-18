import { afterEach, expect, it, vi } from 'vitest';
import { subscribeTimetable } from './publication-api';

afterEach(() => vi.unstubAllGlobals());

it('accepts ordered server versions, ignores duplicates and refetches on resume', async () => {
  let stream: ReadableStreamDefaultController<Uint8Array>;
  const response = {
    ok: true,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body: new ReadableStream<Uint8Array>({
      start(controller) {
        stream = controller;
      },
    }),
  };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
  const version = vi.fn();
  const connected = vi.fn();
  const stop = subscribeTimetable(
    'sandbox/events/period?start=2026-10-01&end=2026-10-31',
    version,
    connected,
  );
  await vi.waitFor(() => expect(connected).toHaveBeenCalledWith(true));
  const encode = new TextEncoder();
  for (const sequence of [2, 2, 1, 3])
    stream!.enqueue(encode.encode(`event: schedule-version\ndata: {"sequence":${sequence}}\n\n`));
  await vi.waitFor(() => expect(version.mock.calls).toEqual([[2], [3]]));
  window.dispatchEvent(new Event('online'));
  expect(version).toHaveBeenLastCalledWith(3);
  stop();
  const count = version.mock.calls.length;
  window.dispatchEvent(new Event('online'));
  expect(version).toHaveBeenCalledTimes(count);
  stream!.close();
});
