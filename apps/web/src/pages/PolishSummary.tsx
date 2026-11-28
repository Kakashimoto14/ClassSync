import type {
  GenerationInput,
  PolishReport,
} from '../../../../packages/shared-types/src/scheduling';
import './scheduling.css';

const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const problems = {
  below_min_sessions: 'too few classes',
  over_max_sessions: 'too many classes',
  over_span: 'day too long',
};
const hours = (minutes: number) => `${Number((minutes / 60).toFixed(1))} h`;

function sectionLabel(input: GenerationInput, id: string) {
  const section = input.sections?.find((item) => item.id === id);
  if (!section) return id;
  if (section.custom_label) return section.custom_label;
  const program = input.programs?.find((item) => item.id === section.program_id);
  return `${program?.acronym ?? section.program_id}-${section.year_level}${section.section_letter}`;
}

export function PolishSummary({ report, input }: { report: PolishReport; input: GenerationInput }) {
  const rows = [
    ['One-class section-days', report.before.orphan_section_days, report.after.orphan_section_days],
    [
      'Section-days over the length limit',
      report.before.over_span_section_days,
      report.after.over_span_section_days,
    ],
    [
      'Longest section day',
      hours(report.before.max_span_minutes),
      hours(report.after.max_span_minutes),
    ],
    [
      'Lectures holding specialized rooms',
      report.before.lectures_in_specialized_rooms,
      report.after.lectures_in_specialized_rooms,
    ],
    [
      'Instructor late-then-early days',
      report.before.faculty_clopenings,
      report.after.faculty_clopenings,
    ],
  ];
  return (
    <section className="workspace-card scheduling-page" aria-label="Commuter-friendly polish">
      <h3>Commuter-friendly polish</h3>
      <div className="polish-compare" role="table" aria-label="Polish comparison, before saving">
        <div className="polish-compare__head" role="row">
          <span role="columnheader">Measure</span>
          <span role="columnheader">Solver</span>
          <span role="columnheader">After polish</span>
        </div>
        {rows.map(([label, before, after]) => (
          <div className="polish-card" role="row" key={label}>
            <span role="rowheader">{label}</span>
            <span role="cell" data-label="Solver">
              {before}
            </span>
            <span role="cell" data-label="After polish">
              {after}
            </span>
          </div>
        ))}
      </div>
      {report.unmet.length ? (
        <details>
          <summary>Section-days still outside the preferences: {report.unmet.length}</summary>
          <ul>
            {report.unmet.map((item) => (
              <li key={`${item.section_id}:${item.day}`}>
                {sectionLabel(input, item.section_id)} · {days[item.day]}: {item.sessions} classes
                over {hours(item.span_minutes)} (
                {item.issues.map((issue) => problems[issue]).join(', ')})
              </li>
            ))}
          </ul>
        </details>
      ) : (
        <p>Every section-day meets the configured preferences.</p>
      )}
    </section>
  );
}
