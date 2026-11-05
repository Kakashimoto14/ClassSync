import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  listAcademicPeriods,
  loadCurriculumCatalog,
  checkAcademicReadiness,
  generateAcademicSchedule,
} from './academic-api';
import { listSchedulingDrafts, validateWeeklySchedule } from './scheduling-api';

vi.mock('../config/runtime-config', () => ({
  appMode: 'institutional',
  requireLiveCapability: vi.fn(),
}));
vi.mock('./firebase', () => ({ firebaseApp: {} }));
vi.mock('firebase/auth', () => ({ getAuth: () => ({ currentUser: connectedUser }) }));
const connectedUser = vi.hoisted(() => ({
  getIdToken: vi.fn().mockResolvedValue('synthetic-test-token'),
}));
const fetcher = vi.fn();
beforeEach(() => {
  fetcher.mockReset();
  fetcher.mockImplementation(
    async () =>
      new Response(JSON.stringify({ data: {} }), {
        headers: { 'content-type': 'application/json' },
      }),
  );
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => vi.unstubAllGlobals());
it('routes connected curriculum, period and readiness requests with authorization', async () => {
  await listAcademicPeriods();
  await loadCurriculumCatalog();
  await checkAcademicReadiness('period');
  await generateAcademicSchedule('period', 12);
  expect(fetcher.mock.calls.map((c) => c[0])).toEqual([
    expect.stringMatching(/\/academic\/periods$/),
    expect.stringMatching(/\/academic\/curriculum-catalog$/),
    expect.stringMatching(/\/scheduling\/academic\/period\/readiness$/),
    expect.stringMatching(/\/scheduling\/academic\/period\/generate$/),
  ]);
  expect(
    fetcher.mock.calls.every((c) => c[1].headers.Authorization === 'Bearer synthetic-test-token'),
  ).toBe(true);
});
it('uses existing protected draft and validator routes without sandbox fallback', async () => {
  await listSchedulingDrafts(0, 'academic');
  await validateWeeklySchedule({} as Parameters<typeof validateWeeklySchedule>[0], []);
  expect(fetcher.mock.calls[0][0]).toMatch(/\/scheduling\/drafts\?/);
  expect(fetcher.mock.calls[1][0]).toMatch(/\/scheduling\/validate$/);
  expect(fetcher.mock.calls.every((c) => !c[0].includes('/sandbox/'))).toBe(true);
});
