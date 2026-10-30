import type { CalendarData, CalendarOccurrence } from './calendar-model';

// Display names never replace stable IDs used by authorization or navigation.
export function displayName(value: string | null | undefined, id: string, fallback: string) {
  const name = value?.trim();
  return !name || name === id || /^(?:user entered|entered |subject-[a-z]$|syn-)/i.test(name)
    ? fallback
    : name;
}
export function studentOccurrence(item: CalendarOccurrence): CalendarOccurrence {
  return {
    ...item,
    subject: {
      ...item.subject,
      name: displayName(item.subject.name, item.subject.id, 'Subject details unavailable'),
      code: displayName(item.subject.code, item.subject.id, ''),
    },
    teacher: {
      ...item.teacher,
      name: displayName(item.teacher.name, item.teacher.id, 'Instructor to be confirmed'),
    },
    room: {
      ...item.room,
      name: displayName(item.room.name, item.room.id, 'Room to be confirmed'),
      building: displayName(item.room.building, '', ''),
    },
    section: {
      ...item.section,
      name: displayName(item.section.name, item.section.id, 'Section to be confirmed'),
    },
  };
}
export function studentTime(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Manila',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(value));
}
export function timeRange(start: string, end: string) {
  const a = studentTime(start),
    b = studentTime(end);
  return `${a.slice(-2) === b.slice(-2) ? a.slice(0, -3) : a}–${b}`;
}
export function termLabel(calendar?: CalendarData['calendar']) {
  if (!calendar?.academic_year) return '';
  const semester = (
    { first: '1st Semester', second: '2nd Semester', summer: 'Summer' } as Record<string, string>
  )[calendar.semester];
  return `AY ${calendar.academic_year.replace('-', '–')}${semester ? ` · ${semester}` : ''}`;
}
export function nextClass(records: CalendarOccurrence[], now: number) {
  return [...records]
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))
    .find((item) => Date.parse(item.ends_at) > now);
}
