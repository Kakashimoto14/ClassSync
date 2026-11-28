import { useState } from 'react';
import {
  assignmentLabel,
  clockLabel as time,
  DAY_NAMES as days,
  sectionLabel,
  sessionType,
} from '../lib/scheduling-labels';
import type {
  Assignment,
  GenerationInput,
  GenerationResult,
} from '../../../../packages/shared-types/src/scheduling';
import { INSTITUTES, instituteCode } from '../lib/program-scope';
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
  return (
    <>
      <div className="institute-chips" role="group" aria-label="Institute">
        {['', ...INSTITUTES].map((code) => (
          <button
            key={code || 'all'}
            type="button"
            aria-pressed={filters.institute === code}
            // A program or section from another institute would silently empty the grid.
            onClick={() => setFilters({ ...filters, institute: code, program: '', section: '' })}
          >
            {code || 'All'}
          </button>
        ))}
      </div>
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
        <label className="scheduler-grouping">
          Group timetable by
          <select value={grouping} onChange={(e) => setGrouping(e.target.value)}>
            <option value="day">Day</option>
            <option value="section">Section</option>
          </select>
        </label>
      </details>
      <div className="weekly-grid">
        {(grouping === 'day'
          ? days.map((day, index) => ({
              id: String(index),
              label: day,
              values: filtered.filter((a) => a.day === index),
            }))
          : sections.map((section) => ({
              id: section.id,
              label: sectionLabel(section, input),
              values: filtered.filter((a) => a.section_id === section.id),
            }))
        ).map(
          (group) =>
            group.values.length > 0 && (
              <section key={group.id} aria-label={`${group.label} timetable`}>
                <h3>{group.label}</h3>
                {group.values.map((a) => (
                  <AssignmentCard
                    key={a.id}
                    assignment={a}
                    input={input}
                    showDay={grouping === 'section'}
                    onEdit={onEdit}
                  />
                ))}
              </section>
            ),
        )}
      </div>
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

function AssignmentCard({
  assignment: a,
  input,
  showDay = false,
  onEdit,
}: {
  assignment: Assignment;
  input: GenerationInput;
  showDay?: boolean;
  onEdit?: (assignmentId: string) => void;
}) {
  const offering = input.offerings?.find((o) => o.id === a.offering_id);
  const room = input.rooms?.find((r) => r.id === a.room_id);
  const kind = sessionType(offering);
  return (
    <article
      id={'assignment-' + a.id}
      tabIndex={-1}
      className="generated-session"
      data-assignment-id={a.id}
      data-session-type={kind.type}
    >
      <span className="session-type">{kind.label}</span>
      <time>
        {showDay && `${days[a.day]} · `}
        {time(a.start)}–{time(a.end)}
      </time>
      <h4>{offering?.subject_name}</h4>
      <strong>
        {sectionLabel(
          input.sections?.find((s) => s.id === a.section_id),
          input,
        )}
      </strong>
      <p>{input.teachers?.find((t) => t.id === a.teacher_id)?.name}</p>
      <p>
        {room?.name} · {room?.building}
      </p>
      <small>{a.end - a.start} instructional minutes</small>
      {onEdit && (
        <button
          type="button"
          className="button button--secondary generated-session__edit"
          aria-label={`Edit ${assignmentLabel(a, input)}`}
          onClick={() => onEdit(a.id)}
        >
          Edit
        </button>
      )}
    </article>
  );
}
