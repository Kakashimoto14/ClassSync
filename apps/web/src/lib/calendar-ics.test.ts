import { expect, it } from 'vitest';
import { exportRange, scheduleCalendar } from './calendar-ics';
import type { CalendarOccurrence } from './calendar-model';

const occurrence = (date: string): CalendarOccurrence => ({
  id: `owned-assignment:${date}`,
  assignment_id: 'owned-assignment',
  offering_id: 'owned-offering',
  date,
  starts_at: `${date}T08:00:00+08:00`,
  ends_at: `${date}T09:30:00+08:00`,
  changed: false,
  subject: { id: 's', code: 'TEST101', name: 'Invented seminar' },
  section: { id: 'a', name: 'Invented section' },
  teacher: { id: 't', name: 'Invented instructor' },
  room: { id: 'r', name: 'Control room', building: 'Control building', floor: null },
});

it('bounds the selected day, week and month', () => {
  expect(exportRange('day', '2026-11-11')).toEqual(['2026-11-11', '2026-11-11']);
  expect(exportRange('week', '2026-11-15')).toEqual(['2026-11-09', '2026-11-15']);
  expect(exportRange('month', '2026-02-11')).toEqual(['2026-02-01', '2026-02-28']);
});

it('writes only the occurrences inside the selected range, in UTC', () => {
  const records = [occurrence('2026-11-09'), occurrence('2026-11-16')];
  const result = scheduleCalendar(records, 'student', 'week', '2026-11-11', new Date(0));
  expect(result.count).toBe(1);
  expect(result.filename).toBe('classsync-2026-11-09-to-2026-11-15.ics');
  expect(result.calendar).toContain('DTSTART:20261109T000000Z');
  expect(result.calendar).not.toContain('20261116');
  expect(result.calendar).toContain('SUMMARY:TEST101 · Invented seminar');
  expect(result.calendar).toContain('Invented instructor');
  const teacher = scheduleCalendar(records, 'teacher', 'month', '2026-11-11', new Date(0));
  expect(teacher.count).toBe(2);
  expect(teacher.calendar).not.toContain('Invented instructor');
});
