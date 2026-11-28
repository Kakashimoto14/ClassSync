import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { clockLabel, DAY_NAMES, type SessionType } from '../../lib/scheduling-labels';
import './week-grid.css';

export interface WeekEntry {
  id: string;
  /** 0 = Monday. */
  day: number;
  /** Minutes after midnight. */
  start: number;
  end: number;
  type: SessionType | 'other';
  typeLabel: string;
  title: string;
  section: string;
  teacher: string;
  room: string;
  /** Extra line shown in the agenda list only. */
  note?: string;
  changed?: boolean;
  elementId?: string;
  /** Selecting the entry opens its details. */
  onOpen?: () => void;
  onEdit?: () => void;
  editLabel?: string;
}

export interface WeekGroup {
  id: string;
  label: string;
  entries: WeekEntry[];
}

export type WeekView = 'week' | 'agenda';

/** Phones start on the agenda list; the matrix needs width. */
function defaultWeekView(): WeekView {
  return typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches
    ? 'agenda'
    : 'week';
}

const dayName = (day: number, labels?: string[]) => labels?.[day] ?? DAY_NAMES[day];
const timeRange = (entry: WeekEntry) => `${clockLabel(entry.start)}–${clockLabel(entry.end)}`;
const accessibleName = (entry: WeekEntry, labels?: string[]) =>
  [
    entry.title,
    entry.section,
    `${dayName(entry.day, labels)} ${timeRange(entry)}`,
    entry.room,
    entry.teacher,
    entry.typeLabel,
    entry.changed ? 'Schedule changed' : '',
  ]
    .filter(Boolean)
    .join(', ');

const byTime = (a: WeekEntry, b: WeekEntry) =>
  a.day - b.day || a.start - b.start || a.title.localeCompare(b.title);

function Body({ entry, full, showDay }: { entry: WeekEntry; full: boolean; showDay?: string }) {
  return (
    <>
      <span className="session-type">{entry.typeLabel}</span>
      <time>
        {showDay && `${showDay} · `}
        {timeRange(entry)}
      </time>
      {full ? <h4>{entry.title}</h4> : <span className="session-title">{entry.title}</span>}
      <strong>{entry.section}</strong>
      <span>{entry.room}</span>
      <span className="session-teacher">{entry.teacher}</span>
      {full && entry.note && <small>{entry.note}</small>}
      {entry.changed && <small className="session-changed">Schedule changed</small>}
    </>
  );
}

function Entry({
  entry,
  view,
  tabIndex,
  register,
  showDay,
  labels,
}: {
  entry: WeekEntry;
  view: WeekView;
  /** Roving tab stop in the matrix; undefined keeps the normal order. */
  tabIndex?: number;
  register?: (element: HTMLElement | null) => void;
  showDay?: boolean;
  labels?: string[];
}) {
  const full = view === 'agenda';
  const day = showDay ? dayName(entry.day, labels) : undefined;
  // A matrix entry has exactly one focus target for the arrow keys.
  const articleFocus = !full && !entry.onOpen;
  return (
    <article
      id={entry.elementId}
      ref={articleFocus ? register : undefined}
      tabIndex={articleFocus ? tabIndex : -1}
      aria-label={accessibleName(entry, labels)}
      className="generated-session"
      data-entry={entry.id}
      data-assignment-id={entry.id}
      data-session-type={entry.type}
    >
      {entry.onOpen ? (
        <button
          type="button"
          className="session-open"
          ref={full ? undefined : register}
          tabIndex={tabIndex}
          aria-label={accessibleName(entry, labels)}
          onClick={entry.onOpen}
        >
          <Body entry={entry} full={false} showDay={day} />
        </button>
      ) : (
        <Body entry={entry} full={full} showDay={day} />
      )}
      {entry.onEdit && (
        <button
          type="button"
          className="button button--secondary generated-session__edit"
          aria-label={entry.editLabel}
          tabIndex={tabIndex}
          onClick={entry.onEdit}
        >
          Edit
        </button>
      )}
    </article>
  );
}

const ARROWS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];

function Matrix({
  entries,
  label,
  labels,
}: {
  entries: WeekEntry[];
  label: string;
  labels?: string[];
}) {
  const sorted = [...entries].sort(byTime);
  const [activeId, setActiveId] = useState('');
  const targets = useRef(new Map<string, HTMLElement>());
  const active = sorted.find((entry) => entry.id === activeId) ?? sorted[0];
  // Monday to Saturday always; Sunday only when something is scheduled on it.
  const days = [0, 1, 2, 3, 4, 5, ...(sorted.some((entry) => entry.day === 6) ? [6] : [])];
  const hours = sorted.length
    ? Array.from(
        {
          length:
            Math.max(...sorted.map((e) => Math.floor(e.start / 60))) -
            Math.min(...sorted.map((e) => Math.floor(e.start / 60))) +
            1,
        },
        (_, index) => Math.min(...sorted.map((e) => Math.floor(e.start / 60))) + index,
      )
    : [];

  function move(event: KeyboardEvent<HTMLTableElement>) {
    if (!ARROWS.includes(event.key)) return;
    const id = (event.target as HTMLElement).closest<HTMLElement>('[data-entry]')?.dataset.entry;
    const current = sorted.find((entry) => entry.id === id);
    if (!current) return;
    event.preventDefault();
    const column = sorted.filter((entry) => entry.day === current.day);
    const row = column.indexOf(current);
    let next: WeekEntry | undefined;
    if (event.key === 'ArrowUp') next = column[row - 1];
    else if (event.key === 'ArrowDown') next = column[row + 1];
    else if (event.key === 'Home') next = column[0];
    else if (event.key === 'End') next = column[column.length - 1];
    else {
      const step = event.key === 'ArrowRight' ? 1 : -1;
      for (let day = current.day + step; day >= 0 && day <= 6 && !next; day += step) {
        next = sorted
          .filter((entry) => entry.day === day)
          .sort((a, b) => Math.abs(a.start - current.start) - Math.abs(b.start - current.start))[0];
      }
    }
    if (!next) return;
    setActiveId(next.id);
    targets.current.get(next.id)?.focus();
  }

  return (
    <div className="week-grid">
      <table
        role="grid"
        aria-label={label}
        onKeyDown={move}
        onFocus={(event) => {
          const id = (event.target as HTMLElement).closest<HTMLElement>('[data-entry]')?.dataset
            .entry;
          if (id) setActiveId(id);
        }}
      >
        <thead>
          <tr>
            <th scope="col">Time</th>
            {days.map((day) => (
              <th key={day} scope="col">
                {dayName(day, labels)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hours.map((hour) => (
            <tr key={hour}>
              <th scope="row">
                <time>{clockLabel(hour * 60)}</time>
              </th>
              {days.map((day) => (
                <td key={day}>
                  {sorted
                    .filter((entry) => entry.day === day && Math.floor(entry.start / 60) === hour)
                    .map((entry) => (
                      <Entry
                        key={entry.id}
                        entry={entry}
                        view="week"
                        labels={labels}
                        tabIndex={entry.id === active?.id ? 0 : -1}
                        register={(element) => {
                          if (element) targets.current.set(entry.id, element);
                          else targets.current.delete(entry.id);
                        }}
                      />
                    ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Weekly time matrix with an agenda list alternative. */
export function WeekGrid({
  entries,
  label,
  dayLabels,
  agendaGroups,
  agendaShowsDay = false,
  agendaControls,
  actions,
}: {
  entries: WeekEntry[];
  label: string;
  /** Replaces the weekday names, for example with dates. */
  dayLabels?: string[];
  /** Agenda grouping; days by default. */
  agendaGroups?: WeekGroup[];
  agendaShowsDay?: boolean;
  agendaControls?: ReactNode;
  /** Page actions that sit beside the view toggle, such as export. */
  actions?: ReactNode;
}) {
  const [view, setView] = useState<WeekView>(defaultWeekView);
  const groups =
    agendaGroups ??
    DAY_NAMES.map((_, day) => ({
      id: String(day),
      label: dayName(day, dayLabels),
      entries: entries.filter((entry) => entry.day === day),
    }));
  const types = [...new Map(entries.map((entry) => [entry.type, entry.typeLabel])).entries()];
  return (
    <div className="week-view">
      <div className="week-view__bar">
        <div className="segmented" role="group" aria-label="Timetable view">
          {(['week', 'agenda'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={view === option}
              onClick={() => setView(option)}
            >
              {option === 'week' ? 'Week grid' : 'Agenda list'}
            </button>
          ))}
        </div>
        {view === 'agenda' && agendaControls}
        {view === 'week' && entries.length > 0 && (
          <ul className="week-legend" aria-label="Class types">
            {types.map(([type, text]) => (
              <li key={type} data-session-type={type}>
                {text}
              </li>
            ))}
          </ul>
        )}
        {actions}
      </div>
      {view === 'week' ? (
        entries.length > 0 && <Matrix entries={entries} label={label} labels={dayLabels} />
      ) : (
        <div className="week-agenda">
          {groups.map(
            (group) =>
              group.entries.length > 0 && (
                <section key={group.id} aria-label={`${group.label} timetable`}>
                  <h3>{group.label}</h3>
                  <div>
                    {[...group.entries].sort(byTime).map((entry) => (
                      <Entry
                        key={entry.id}
                        entry={entry}
                        view="agenda"
                        labels={dayLabels}
                        showDay={agendaShowsDay}
                      />
                    ))}
                  </div>
                </section>
              ),
          )}
        </div>
      )}
    </div>
  );
}
