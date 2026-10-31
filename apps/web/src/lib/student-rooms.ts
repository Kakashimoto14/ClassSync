import type { CalendarOccurrence } from './calendar-model';
import { studentOccurrence } from './student-presentation';

export interface StudentRoom {
  id: string;
  name: string;
  building: string;
  floor?: string | null;
  alias?: string;
  aliasUnconfirmed?: boolean;
  location?: string;
  classes: CalendarOccurrence[];
}

// Only stable IDs from the authorized timetable establish a student-room relationship.
// A matching name or provisional inventory alias never establishes enrollment.
export function studentRooms(records: CalendarOccurrence[]): StudentRoom[] {
  const rooms = new Map<string, StudentRoom>();
  for (const record of [...records].sort((a, b) => a.starts_at.localeCompare(b.starts_at))) {
    const item = studentOccurrence(record);
    if (!rooms.has(item.room.id)) rooms.set(item.room.id, { ...item.room, classes: [] });
    rooms.get(item.room.id)!.classes.push(item);
  }
  return [...rooms.values()];
}

export function matchesRoom(room: StudentRoom, query: string) {
  return [room.name, room.building, room.alias, room.location]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase()
    .includes(query.trim().toLocaleLowerCase());
}

export function roomClassPatterns(classes: CalendarOccurrence[]) {
  const patterns = new Map<
    string,
    { subject: string; days: string[]; start: string; end: string }
  >();
  for (const item of classes) {
    const time = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Manila',
      hour: '2-digit',
      minute: '2-digit',
    });
    const key = [
      item.subject.id,
      item.teacher.id,
      time.format(new Date(item.starts_at)),
      time.format(new Date(item.ends_at)),
    ].join(':');
    const day = new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      timeZone: 'Asia/Manila',
    }).format(new Date(item.starts_at));
    if (!patterns.has(key))
      patterns.set(key, {
        subject: item.subject.name,
        days: [],
        start: item.starts_at,
        end: item.ends_at,
      });
    const pattern = patterns.get(key)!;
    if (!pattern.days.includes(day)) pattern.days.push(day);
  }
  const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return [...patterns.values()].map((pattern) => ({
    ...pattern,
    days: pattern.days.sort((a, b) => weekdays.indexOf(a) - weekdays.indexOf(b)),
  }));
}
