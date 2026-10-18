export interface CalendarOccurrence {
  id: string;
  assignment_id: string;
  offering_id: string;
  date: string;
  starts_at: string;
  ends_at: string;
  changed: boolean;
  subject: { id: string; code: string; name: string };
  section: { id: string; name: string };
  teacher: { id: string; name: string };
  room: { id: string; name: string; building: string; floor: string | null };
}
export interface CalendarData {
  version: string | null;
  sequence?: number;
  revision?: number;
  status: string;
  calendar: {
    academic_year: string;
    semester: string;
    timezone: string;
    effective_start: string;
    effective_end: string;
  };
  sections: Array<{
    id: string;
    program_id: string;
    year_level?: number | null;
    section_letter?: string | null;
    custom_label?: string | null;
  }>;
  teachers: Array<{ id: string; name: string }>;
  occurrences: CalendarOccurrence[];
}
export const manilaToday = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Manila',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
export function addDays(value: string, days: number) {
  const d = new Date(value + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
export const calendarDateLabel = (value: string) =>
  new Date(value + 'T00:00:00Z').toLocaleDateString('en', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
export const manilaTime = (value: string) =>
  new Date(value).toLocaleTimeString('en', {
    timeZone: 'Asia/Manila',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
