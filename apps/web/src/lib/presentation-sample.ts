import type { CalendarData } from './calendar-model';
import type { UserRole } from '../types/ui';

export const presentationEnabled =
  import.meta.env.DEV || import.meta.env.VITE_ENABLE_PRESENTATION_SAMPLE === 'true';
export const presentationOnlyBuild =
  import.meta.env.PROD && import.meta.env.VITE_ENABLE_PRESENTATION_SAMPLE === 'true';
export const presentationVersion = 'classsync-presentation-v1';
export async function presentationData() {
  return structuredClone((await import('../data/presentation-timetable.v1.json')).default);
}
export async function presentationCalendar(
  role: UserRole,
  identity: string,
  start: string,
  end: string,
): Promise<CalendarData> {
  const { calendar } = await presentationData();
  if (
    identity &&
    role !== 'administrator' &&
    !(role === 'student' ? calendar.sections : calendar.teachers).some((v) => v.id === identity)
  )
    throw Object.assign(new Error('Choose an identity included in this presentation sample.'), {
      status: 422,
    });
  return {
    ...calendar,
    occurrences: calendar.occurrences.filter(
      (o) =>
        o.date >= start &&
        o.date <= end &&
        (!identity ||
          role === 'administrator' ||
          (role === 'student' ? o.section.id === identity : o.teacher.id === identity)),
    ),
  };
}
export function facultyDisplayName(name: string) {
  return name.replace(/^Sample Instructor SYN-.*-(\d+)$/i, 'Sample Instructor $1');
}
