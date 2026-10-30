import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});
it.each(['presentation', 'institutional'])(
  '%s rejects all live clients before fetch',
  async (mode) => {
    vi.resetModules();
    vi.stubEnv('VITE_CLASSSYNC_MODE', mode);
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const academic = await import('../lib/academic-api');
    const scheduling = await import('../lib/scheduling-api');
    const sample = await import('../lib/sample-calendar-api');
    const publication = await import('../lib/publication-api');
    await expect(academic.listAcademicPeriods()).rejects.toMatchObject({ status: 403 });
    await expect(academic.createAcademicPeriod({} as never)).rejects.toMatchObject({ status: 403 });
    await expect(scheduling.loadSchedulingScenario()).rejects.toMatchObject({ status: 403 });
    await expect(scheduling.generateWeeklySchedule({} as never)).rejects.toMatchObject({
      status: 403,
    });
    await expect(scheduling.saveSchedulingDraft({} as never)).rejects.toMatchObject({
      status: 403,
    });
    await expect(sample.listCalendarSamples()).rejects.toMatchObject({ status: 403 });
    await expect(publication.timetableRequest('periods')).rejects.toMatchObject({ status: 403 });
    await expect(publication.timetableRequest('publish', {})).rejects.toMatchObject({
      status: 403,
    });
    expect(() => publication.subscribeTimetable('events?', vi.fn(), vi.fn())).toThrow();
    const { liveFetch } = await import('./runtime-config');
    await expect(
      liveFetch('/api/v1/academic/sandbox/fixtures', { method: 'POST' }),
    ).rejects.toMatchObject({ status: 403 });
    const { apiGet } = await import('../services/api-client');
    await expect(apiGet('/private')).rejects.toMatchObject({ status: 403 });
    expect(fetcher).not.toHaveBeenCalled();
  },
);
it('ignores browser mode/role inputs when selecting operating capabilities', async () => {
  vi.resetModules();
  vi.stubEnv('VITE_CLASSSYNC_MODE', 'institutional');
  sessionStorage.setItem('VITE_CLASSSYNC_MODE', 'sandbox');
  localStorage.setItem('mode', 'sandbox');
  window.history.replaceState({}, '', '/?mode=sandbox&role=administrator');
  const { capabilities, appMode } = await import('./runtime-config');
  expect(appMode).toBe('institutional');
  expect(capabilities.previewRoles).toBe(false);
  expect(capabilities.liveRequests).toBe(false);
  sessionStorage.clear();
  localStorage.clear();
  window.history.replaceState({}, '', '/');
});
