import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { CommandBar, CommandField } from '../components/layout/CommandBar';
import { InstituteChips } from '../components/scheduling/InstituteChips';
import { WeekGrid, type WeekEntry } from '../components/scheduling/WeekGrid';
import { ExportIcsButton } from '../components/scheduling/ExportIcsButton';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';
import { addDays, calendarDateLabel, manilaToday, type CalendarOccurrence } from '../lib/calendar-model';
import type { CalendarRange } from '../lib/calendar-ics';
import { facultyDisplayName } from '../lib/presentation-sample';
import './scheduling.css';

// Published meetings carry no activity type, so the accent follows the recorded room type.
const roomTypes = new Map(provisionalCdmRooms.map((room) => [room.id, room.room_type]));
function roomKind(roomId: string): Pick<WeekEntry, 'type' | 'typeLabel'> {
  switch (roomTypes.get(roomId)) {
    case 'computer_lab':
      return { type: 'computer_lab', typeLabel: 'Computer lab' };
    case 'science_lab':
      return { type: 'science_lab', typeLabel: 'Science lab' };
    case 'athletic_space':
      return { type: 'athletic', typeLabel: 'PE / Athletic' };
    case 'lecture_classroom':
      return { type: 'lecture', typeLabel: 'Lecture room' };
    default:
      return { type: 'other', typeLabel: 'Class' };
  }
}

const minutes = (value: string) => Number(value.slice(11, 13)) * 60 + Number(value.slice(14, 16));
const weekday = (date: string) => (new Date(date + 'T00:00:00Z').getUTCDay() + 6) % 7;

/** Administrator view of one published week as a time matrix or agenda list. */
export function PublishedTimetable({
  records,
  date,
  onDate,
  institute,
  onInstitute,
  program,
  programIds,
  onProgram,
  exportable,
  loading,
  onSelect,
}: {
  records: CalendarOccurrence[];
  date: string;
  onDate: (date: string) => void;
  institute: string;
  onInstitute: (value: string) => void;
  program: string;
  programIds: string[];
  onProgram: (value: string) => void;
  exportable: boolean;
  loading: boolean;
  onSelect: (record: CalendarOccurrence) => void;
}) {
  const [range, setRange] = useState<CalendarRange>('week');
  const monday = addDays(date, -weekday(date));
  const week = records.filter((o) => o.date >= monday && o.date < addDays(monday, 7));
  const entries: WeekEntry[] = week.map((o) => ({
    id: o.id,
    day: weekday(o.date),
    start: minutes(o.starts_at),
    end: minutes(o.starts_at) + (Date.parse(o.ends_at) - Date.parse(o.starts_at)) / 60000,
    ...roomKind(o.room.id),
    title: o.subject.name,
    section: o.section.name,
    teacher: facultyDisplayName(o.teacher.name),
    room: o.room.name,
    changed: o.changed,
    onOpen: () => onSelect(o),
  }));
  const dayLabels = Array.from({ length: 7 }, (_, day) => calendarDateLabel(addDays(monday, day)));
  const short = (value: string) =>
    new Date(value + 'T00:00:00Z').toLocaleDateString('en', {
      timeZone: 'UTC',
      month: 'short',
      day: 'numeric',
    });
  return (
    <>
      <CommandBar label="Timetable controls">
        <div className="published-nav">
          <Button variant="secondary" aria-label="Previous week" onClick={() => onDate(addDays(date, -7))}>
            <ChevronLeft size={16} aria-hidden="true" />
          </Button>
          <strong>
            {short(monday)} – {short(addDays(monday, 6))}
          </strong>
          <Button variant="secondary" aria-label="Next week" onClick={() => onDate(addDays(date, 7))}>
            <ChevronRight size={16} aria-hidden="true" />
          </Button>
          <Button variant="secondary" onClick={() => onDate(manilaToday())}>
            Today
          </Button>
        </div>
        <CommandField label="Show week of">
          <input type="date" value={date} onChange={(e) => e.target.value && onDate(e.target.value)} />
        </CommandField>
        <CommandField label="Program">
          <select value={program} onChange={(e) => onProgram(e.target.value)}>
            <option value="all">All programs</option>
            {programIds.map((id) => (
              <option key={id} value={id}>
                {id.toUpperCase()}
              </option>
            ))}
          </select>
        </CommandField>
        <InstituteChips
          value={institute === 'all' ? '' : institute}
          onChange={(code) => onInstitute(code || 'all')}
        />
      </CommandBar>
      <WeekGrid
        label="Published weekly timetable"
        entries={entries}
        dayLabels={dayLabels}
        actions={
          exportable && (
            <div className="published-export">
              <label>
                <span className="visually-hidden">Export range</span>
                <select value={range} onChange={(e) => setRange(e.target.value as CalendarRange)}>
                  <option value="day">Selected day</option>
                  <option value="week">Week</option>
                  <option value="month">Month</option>
                </select>
              </label>
              <ExportIcsButton records={records} role="administrator" view={range} date={date} />
            </div>
          )
        }
      />
      {!loading && !entries.length && <p className="muted">No classes in this week.</p>}
    </>
  );
}
