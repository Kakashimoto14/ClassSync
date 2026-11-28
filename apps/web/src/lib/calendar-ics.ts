// Loaded on demand. Only fields of occurrences already authorized for this viewer are written.
import { calendarEventUid, downloadCalendar, serializeCalendar } from './calendar-export';
import { addDays, type CalendarOccurrence } from './calendar-model';
import type { UserRole } from '../types/ui';

export type CalendarRange = 'day' | 'week' | 'month';

export function exportRange(view: CalendarRange, date: string): [string, string] {
  if (view === 'day') return [date, date];
  if (view === 'week') {
    const monday = addDays(date, -((new Date(date + 'T00:00:00Z').getUTCDay() + 6) % 7));
    return [monday, addDays(monday, 6)];
  }
  const last = new Date(Date.UTC(Number(date.slice(0, 4)), Number(date.slice(5, 7)), 0));
  return [date.slice(0, 7) + '-01', last.toISOString().slice(0, 10)];
}

export function scheduleCalendar(
  records: readonly CalendarOccurrence[],
  role: UserRole,
  view: CalendarRange,
  date: string,
  createdAt?: Date,
) {
  const [start, end] = exportRange(view, date);
  const included = records.filter((item) => item.date >= start && item.date <= end);
  const calendar = serializeCalendar(
    included.map((item) => ({
      uid: calendarEventUid(item.id),
      summary: [item.subject.code, item.subject.name].filter(Boolean).join(' · '),
      startsAt: new Date(item.starts_at),
      endsAt: new Date(item.ends_at),
      location: [item.room.name, item.room.building].filter(Boolean).join(', '),
      description: [
        item.section.name,
        role === 'teacher' ? '' : item.teacher.name,
        item.changed ? 'Schedule changed' : '',
      ]
        .filter(Boolean)
        .join(' · '),
    })),
    { calendarName: 'ClassSync schedule', createdAt },
  );
  return { calendar, count: included.length, filename: `classsync-${start}-to-${end}.ics` };
}

/** Download the range and return how many classes it holds; an empty range downloads nothing. */
export function exportSchedule(
  records: readonly CalendarOccurrence[],
  role: UserRole,
  view: CalendarRange,
  date: string,
) {
  const result = scheduleCalendar(records, role, view, date);
  if (result.count) downloadCalendar(result.filename, result.calendar);
  return result.count;
}
