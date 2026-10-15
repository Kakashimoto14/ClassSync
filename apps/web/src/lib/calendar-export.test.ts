import { describe, expect, it } from 'vitest';
import { calendarEventUid, escapeIcsText, foldIcsLine, serializeCalendar } from './calendar-export';

describe('calendar export serialization', () => {
  it('creates an RFC-style UTC calendar with stable caller-provided UIDs', () => {
    const calendar = serializeCalendar([{
      uid: 'classsync-assignment-42@example.invalid',
      summary: 'Databases, Section A; Lab',
      startsAt: new Date('2026-09-22T02:00:00.000Z'),
      endsAt: new Date('2026-09-22T03:30:00.000Z'),
      location: 'SCI-218, East Wing',
      description: 'Snapshot only. Changes do not synchronize automatically.',
    }], { calendarName: 'Maria Santos — Schedule', createdAt: new Date('2026-09-01T00:00:00.000Z') });

    expect(calendar).toContain('BEGIN:VCALENDAR\r\nVERSION:2.0');
    expect(calendar).toContain('UID:classsync-assignment-42@example.invalid');
    expect(calendar).toContain('DTSTAMP:20260901T000000Z');
    expect(calendar).toContain('DTSTART:20260922T020000Z');
    expect(calendar).toContain('DTEND:20260922T033000Z');
    expect(calendar).toContain('SUMMARY:Databases\\, Section A\\; Lab');
    expect(calendar).toContain('LOCATION:SCI-218\\, East Wing');
    expect(calendar).toContain('END:VEVENT\r\nEND:VCALENDAR\r\n');
  });

  it('derives a stable UID from an authorized assignment identifier', () => {
    expect(calendarEventUid('assignment-42')).toBe(calendarEventUid('assignment-42'));
    expect(calendarEventUid('assignment-42')).not.toBe(calendarEventUid('assignment-43'));
  });

  it('escapes special characters and folds long Unicode lines by UTF-8 bytes', () => {
    expect(escapeIcsText('Line one\\two;three,four\nline five')).toBe('Line one\\\\two\\;three\\,four\\nline five');
    const folded = foldIcsLine(`SUMMARY:${'課'.repeat(40)}`);
    const physicalLines = folded.split('\r\n');
    expect(physicalLines).toHaveLength(2);
    expect(physicalLines.every(line => new TextEncoder().encode(line).length <= 75)).toBe(true);
    expect(physicalLines[1]).toMatch(/^ /);
  });

  it('rejects incomplete or impossible event times', () => {
    expect(() => serializeCalendar([{
      uid: 'missing-times@example.invalid', summary: 'Invalid event',
      startsAt: new Date('2026-09-22T03:30:00.000Z'), endsAt: new Date('2026-09-22T02:00:00.000Z'),
    }], { calendarName: 'Schedule' })).toThrow('valid start and end times');
  });
});
