import { expect, it } from 'vitest';
import { nextClass, studentOccurrence, timeRange } from './student-presentation';
import data from '../data/presentation-timetable.v1.json';

const records = data.calendar.occurrences;
it('selects ongoing, adjacent next, afternoon and tomorrow with a controlled Manila clock', () => {
  const at = (time: string) => nextClass(records, Date.parse(time));
  expect(records.filter((item) => item.date === '2026-10-30')).toHaveLength(3);
  expect(at('2026-10-30T08:15:00+08:00')?.subject.name).toBe('Advanced Database Systems');
  expect(at('2026-10-30T09:30:00+08:00')?.subject.name).toBe('Application Development');
  expect(at('2026-10-30T12:00:00+08:00')?.starts_at).toBe('2026-10-30T13:00:00+08:00');
  expect(at('2026-10-26T18:00:00+08:00')?.date).toBe('2026-10-27');
  expect(records.filter((item) => item.date === '2026-10-31')).toHaveLength(0);
  expect(at('2026-12-31T23:00:00+08:00')).toBeUndefined();
});
it('formats readable times without changing the Manila instant', () => {
  expect(timeRange('2026-10-30T00:00:00Z', '2026-10-30T01:30:00Z')).toBe('8:00–9:30 AM');
  expect(timeRange('2026-10-30T11:00:00+08:00', '2026-10-30T13:00:00+08:00')).toBe(
    '11:00 AM–1:00 PM',
  );
});
it('does not polish internal identifiers into fabricated academic names', () => {
  const original = records[0];
  const item = studentOccurrence({
    ...original,
    subject: { id: 'subject-b', code: 'subject-b', name: 'User entered practice' },
  });
  expect(item.subject).toEqual({ id: 'subject-b', code: '', name: 'Subject details unavailable' });
  expect(original.subject.name).toBe('Application Development');
});
