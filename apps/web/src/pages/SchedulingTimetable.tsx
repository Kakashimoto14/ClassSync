import { useState } from 'react';
import { sectionLabel } from '../lib/scheduling-labels';
import type { Assignment, GenerationInput, GenerationResult } from '../../../../packages/shared-types/src/scheduling';
const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const time = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
export function SchedulingTimetable({ input, result }: { input: GenerationInput; result: GenerationResult }) {
  const [grouping, setGrouping] = useState('day');
  const [filters, setFilters] = useState({ program: '', section: '', teacher: '', room: '', day: '' });
  const sections = input.sections ?? [];
  const offerings = input.offerings ?? [];
  const filtered = (result?.assignments ?? []).filter((a) => {
    const section = sections.find((s) => s.id === a.section_id);
    return (
      (!filters.program || section?.program_id === filters.program) &&
      (!filters.section || a.section_id === filters.section) &&
      (!filters.teacher || a.teacher_id === filters.teacher) &&
      (!filters.room || a.room_id === filters.room) &&
      (!filters.day || a.day === Number(filters.day))
    );
  });
    return (<>
              <div className="scheduler-filters" aria-label="Timetable filters">
                {(
                  [
                    ['program', 'Program', (input.programs ?? []).map((p) => [p.id, p.acronym])],
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
                Showing {filtered.length} of {result.assignments.length} generated sessions.
                Coverage below always describes the complete run.
              </p>
              <label className="scheduler-grouping">
                Group timetable by
                <select value={grouping} onChange={(e) => setGrouping(e.target.value)}>
                  <option value="day">Day</option>
                  <option value="section">Section</option>
                </select>
              </label>
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
                          />
                        ))}
                      </section>
                    ),
                )}
              </div>
              {!filtered.length && (
                <p>
                  No sessions match these filters. Choose All to recover the complete timetable.
                </p>
              )}
              <section aria-label="Weekly instructional coverage">
                <h3>Instructional coverage — complete run</h3>
                <ul className="scheduler-coverage">
                  {result.coverage.map((c) => (
                    <li key={c.offering_id}>
                      <strong>
                        {offerings.find((o) => o.id === c.offering_id)?.subject_name ??
                          c.offering_id}
                      </strong>
                      <span>
                        {sectionLabel(
                          sections.find(
                            (s) =>
                              s.id === offerings.find((o) => o.id === c.offering_id)?.section_id,
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
              </section>
  </>);
}

function AssignmentCard({
  assignment: a,
  input,
  showDay = false,
}: {
  assignment: Assignment;
  input: GenerationInput;
  showDay?: boolean;
}) {
  const offering = input.offerings?.find((o) => o.id === a.offering_id);
  const room = input.rooms?.find((r) => r.id === a.room_id);
  return (
    <article className="generated-session" data-assignment-id={a.id}>
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
    </article>
  );
}
