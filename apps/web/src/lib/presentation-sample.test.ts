import { expect, it, vi } from 'vitest';
import { presentationCalendar, presentationData } from './presentation-sample';
it('loads a deterministic versioned synthetic sample without network access or live changes', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch');
  const a = await presentationCalendar('student', 'syn-bsit-3-A', '2026-10-01', '2026-10-31');
  const b = await presentationCalendar('student', 'syn-bsit-3-A', '2026-10-01', '2026-10-31');
  expect(a).toEqual(b);
  expect(a.status).toBe('presentation-sample');
  expect(a.occurrences.length).toBeGreaterThan(0);
  expect(a.occurrences.every((o) => !o.changed && o.room.id.startsWith('synthetic-'))).toBe(true);
  expect(fetcher).not.toHaveBeenCalled();
  fetcher.mockRestore();
});
it('never substitutes another identity and restricts teaching assignments to the selected sample teacher', async () => {
  await expect(
    presentationCalendar('student', 'another-student', '2026-10-01', '2026-10-31'),
  ).rejects.toMatchObject({ status: 422 });
  const sample = await presentationData(),
    teacher = sample.calendar.teachers[0].id;
  const result = await presentationCalendar('teacher', teacher, '2026-10-01', '2026-10-31');
  expect(result.occurrences.every((o) => o.teacher.id === teacher)).toBe(true);
});
it('does not mutate the versioned source while browsing', async () => {
  const a = await presentationData();
  a.calendar.occurrences.length = 0;
  expect((await presentationData()).calendar.occurrences.length).toBeGreaterThan(0);
});
