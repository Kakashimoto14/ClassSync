import { useState } from 'react';
import {
  assignmentLabel,
  DAY_NAMES as days,
  sectionLabel,
  sessionType,
} from '../lib/scheduling-labels';
import type {
  Assignment,
  GenerationInput,
  GenerationResult,
} from '../../../../packages/shared-types/src/scheduling';
import { instituteCode } from '../lib/program-scope';
import { InstituteChips } from '../components/scheduling/InstituteChips';
import { WeekGrid, type WeekEntry } from '../components/scheduling/WeekGrid';
export function SchedulingTimetable({
  input,
  result,
  onEdit,
}: {
  input: GenerationInput;
  result: GenerationResult;
  onEdit?: (assignmentId: string) => void;
}) {
  const [grouping, setGrouping] = useState('day');
  const [filters, setFilters] = useState({
    institute: '',
    program: '',
    section: '',
    teacher: '',
    room: '',
    day: '',
  });
  const sections = input.sections ?? [];
  const offerings = input.offerings ?? [];
  const programInstitute = new Map((input.programs ?? []).map((p) => [p.id, instituteCode(p.institute)]));
  const filtered = (result?.assignments ?? []).filter((a) => {
    const section = sections.find((s) => s.id === a.section_id);
    return (
      (!filters.institute || programInstitute.get(section?.program_id ?? '') === filters.institute) &&
      (!filters.program || section?.program_id === filters.program) &&
      (!filters.section || a.section_id === filters.section) &&
      (!filters.teacher || a.teacher_id === filters.teacher) &&
      (!filters.room || a.room_id === filters.room) &&
      (!filters.day || a.day === Number(filters.day))
    );
  });
  const entry = (a: Assignment): WeekEntry => {
    const offering = offerings.find((o) => o.id === a.offering_id);
    const room = input.rooms?.find((r) => r.id === a.room_id);
    const kind = sessionType(offering);
    return {
      id: a.id,
      elementId: 'assignment-' + a.id,
      day: a.day,
      start: a.start,
      end: a.end,
      type: kind.type,
      typeLabel: kind.label,
      title: offering?.subject_name ?? 'Unknown subject',
      section: sectionLabel(sections.find((s) => s.id === a.section_id), input),
      teacher: input.teachers?.find((t) => t.id === a.teacher_id)?.name ?? 'Unknown instructor',
      room: room ? `${room.name} · ${room.building}` : 'Unknown room',
      note: `${a.end - a.start} instructional minutes`,
      onEdit: onEdit ? () => onEdit(a.id) : undefined,
      editLabel: `Edit ${assignmentLabel(a, input)}`,
    };
  };
  return (
    <>
      <InstituteChips
        value={filters.institute}
        // A program or section from another institute would silently empty the grid.
        onChange={(code) => setFilters({ ...filters, institute: code, program: '', section: '' })}
      />
      <details className="ux-timetable-filters">
        <summary>Filter timetable · Program, section, teacher, room and day</summary>
        <div className="scheduler-filters" aria-label="Timetable filters">
          {(
            [
              ['program', 'Program', (input.programs ?? [])
                .filter((p) => !filters.institute || programInstitute.get(p.id) === filters.institute)
                .map((p) => [p.id, p.acronym])],
              ['section', 'Section', sections.map((s) => [s.id, sectionLabel(s, input)])],
              ['teacher', 'Teacher', (input.teachers ?? []).map((t) => [t.id, t.name])],
              ['room', 'Room', (input.rooms ?? []).map((r) => [r.id, r.name])],
              ['day', 'Day', days.map((day, i) => [String(i), day])],
            ] as const
          ).map(([key, label, values]) => (
            <label key={key}>
              {label}
              <select
                value={filters[key]}
                onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}
              >
                <option value="">All {label.toLowerCase()}s</option>
                {values.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <p role="status">
          Showing {filtered.length} of {result.assignments.length} generated sessions. Coverage
          below always describes the complete run.
        </p>
      </details>
      <WeekGrid
        label="Weekly timetable"
        entries={filtered.map(entry)}
        agendaShowsDay={grouping === 'section'}
        agendaGroups={
          grouping === 'section'
            ? sections.map((section) => ({
                id: section.id,
                label: sectionLabel(section, input),
                entries: filtered.filter((a) => a.section_id === section.id).map(entry),
              }))
            : undefined
        }
        agendaControls={
          <label>
            Group timetable by
            <select value={grouping} onChange={(e) => setGrouping(e.target.value)}>
              <option value="day">Day</option>
              <option value="section">Section</option>
            </select>
          </label>
        }
      />
      {!filtered.length && (
        <p>No sessions match these filters. Choose All to recover the complete timetable.</p>
      )}
      <details aria-label="Weekly instructional coverage">
        <summary>Weekly instructional coverage</summary>
        <h3>Instructional coverage — complete run</h3>
        <ul className="scheduler-coverage">
          {result.coverage.map((c) => (
            <li key={c.offering_id}>
              <strong>
                {offerings.find((o) => o.id === c.offering_id)?.subject_name ?? 'Unknown subject'}
              </strong>
              <span>
                {sectionLabel(
                  sections.find(
                    (s) => s.id === offerings.find((o) => o.id === c.offering_id)?.section_id,
                  ),
                  input,
                )}
              </span>
              <span>
                {c.allocated_minutes}/{c.required_minutes} min
              </span>
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
