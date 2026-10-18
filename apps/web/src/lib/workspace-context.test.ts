import { beforeEach, expect, it } from 'vitest';
import { defaultPeriod, periodLabel, readWorkspace, rememberWorkspace } from './workspace-context';
beforeEach(() => sessionStorage.clear());
it('isolates roles and expires context with the preview session', () => {
  const startedAt = Date.now() - 1000;
  sessionStorage.setItem(
    'classsync.preview.v1',
    JSON.stringify({ version: 1, role: 'student', startedAt }),
  );
  rememberWorkspace('student', {
    period: 'p',
    identity: 'a',
    mode: 'published',
    draft: '',
    date: '2026-10-20',
  });
  expect(readWorkspace('student').period).toBe('p');
  expect(readWorkspace('teacher').period).toBe('');
  sessionStorage.setItem(
    'classsync.preview.v1',
    JSON.stringify({ version: 1, role: 'student', startedAt: startedAt + 1 }),
  );
  expect(readWorkspace('student').identity).toBe('');
});
it('prefers an existing published scope but respects a valid explicit selection', () => {
  const list = [
    { id: 'unpublished', title: 'Sample', revision: 0 },
    { id: 'published', title: 'Sample', revision: 3 },
  ];
  expect(defaultPeriod(list)).toBe('published');
  expect(defaultPeriod(list, 'unpublished')).toBe('unpublished');
  expect(
    periodLabel({
      id: 'p',
      title: 'S2B entered review period',
      calendar: {
        academic_year: '2026-2027',
        semester: 'first',
        effective_start: '2026-10-01',
        effective_end: '2026-12-31',
      },
    }),
  ).toBe('AY 2026-2027 · 1st Semester — Sample');
});
