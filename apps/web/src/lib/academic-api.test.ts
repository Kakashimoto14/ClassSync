import { afterEach, expect, it, vi } from 'vitest';
import { createAcademicPeriod, listAcademicPeriods } from './academic-api';

afterEach(() => vi.unstubAllGlobals());

it('coalesces concurrent period-list requests without caching completed data', async () => {
  const response = () =>
    new Response(JSON.stringify({ data: { periods: [] } }), {
      headers: { 'Content-Type': 'application/json' },
    });
  const request = vi.fn().mockImplementation(async () => response());
  vi.stubGlobal('fetch', request);

  await expect(Promise.all([listAcademicPeriods(), listAcademicPeriods()])).resolves.toEqual([
    { periods: [] },
    { periods: [] },
  ]);
  expect(request).toHaveBeenCalledOnce();

  await listAcademicPeriods();
  expect(request).toHaveBeenCalledTimes(2);
});

it('words a failed read differently from an unconfirmed save', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(listAcademicPeriods()).rejects.toThrow(/^Couldn't load/);
  await expect(createAcademicPeriod({ title: 'Term', include_cdm_catalog: false })).rejects.toThrow(
    'No save or generation was confirmed.',
  );
});
