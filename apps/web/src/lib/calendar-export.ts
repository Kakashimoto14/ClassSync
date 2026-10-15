export interface CalendarExportEvent {
  uid: string;
  summary: string;
  startsAt: Date;
  endsAt: Date;
  location?: string;
  description?: string;
}

export interface CalendarExportOptions {
  calendarName: string;
  createdAt?: Date;
}

const encoder = new TextEncoder();

export function calendarEventUid(assignmentId: string): string {
  const normalizedId = assignmentId.trim();
  if (!normalizedId) throw new Error('Calendar events require a stable assignment identifier.');
  const encodedId = [...encoder.encode(normalizedId)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  return `classsync-${encodedId}@calendar.classsync.invalid`;
}

function assertValidEvent(event: CalendarExportEvent) {
  if (!event.uid.trim() || !event.summary.trim()) throw new Error('Calendar events require a UID and summary.');
  if (Number.isNaN(event.startsAt.getTime()) || Number.isNaN(event.endsAt.getTime()) || event.endsAt <= event.startsAt) {
    throw new Error('Calendar events require valid start and end times.');
  }
}

export function escapeIcsText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\r\n|\r|\n/g, '\\n').replace(/;/g, '\\;').replace(/,/g, '\\,');
}

export function formatIcsUtc(value: Date): string {
  if (Number.isNaN(value.getTime())) throw new Error('Cannot format an invalid calendar timestamp.');
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${value.getUTCFullYear()}${pad(value.getUTCMonth() + 1)}${pad(value.getUTCDate())}T${pad(value.getUTCHours())}${pad(value.getUTCMinutes())}${pad(value.getUTCSeconds())}Z`;
}

export function foldIcsLine(line: string): string {
  let result = '';
  let current = '';
  let currentBytes = 0;
  for (const character of line) {
    const characterBytes = encoder.encode(character).length;
    if (currentBytes + characterBytes > 75) {
      result += `${current}\r\n`;
      current = ` ${character}`;
      currentBytes = 1 + characterBytes;
    } else {
      current += character;
      currentBytes += characterBytes;
    }
  }
  return `${result}${current}`;
}

export function serializeCalendar(events: readonly CalendarExportEvent[], options: CalendarExportOptions): string {
  const createdAt = options.createdAt ?? new Date();
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//ClassSync//Schedule Export//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${escapeIcsText(options.calendarName)}`,
  ];

  for (const event of events) {
    assertValidEvent(event);
    lines.push(
      'BEGIN:VEVENT',
      `UID:${escapeIcsText(event.uid)}`,
      `DTSTAMP:${formatIcsUtc(createdAt)}`,
      `DTSTART:${formatIcsUtc(event.startsAt)}`,
      `DTEND:${formatIcsUtc(event.endsAt)}`,
      `SUMMARY:${escapeIcsText(event.summary)}`,
    );
    if (event.location) lines.push(`LOCATION:${escapeIcsText(event.location)}`);
    if (event.description) lines.push(`DESCRIPTION:${escapeIcsText(event.description)}`);
    lines.push('END:VEVENT');
  }

  lines.push('END:VCALENDAR');
  return `${lines.map(foldIcsLine).join('\r\n')}\r\n`;
}

export function downloadCalendar(filename: string, calendar: string) {
  const safeFilename = filename.endsWith('.ics') ? filename : `${filename}.ics`;
  const blob = new Blob([calendar], { type: 'text/calendar;charset=utf-8' });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = safeFilename;
  anchor.click();
  URL.revokeObjectURL(href);
}
