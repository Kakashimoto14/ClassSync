import type { DailyShapeRules } from '../../../../packages/shared-types/src/scheduling';
import type { PatternPolicy } from './commuter-rules';

const policyLabels: Array<[PatternPolicy, string]> = [
  ['single', 'Single block (1 × 180 minutes)'],
  ['split', 'Split (2 × 90 minutes on different days)'],
  ['flexible', 'Flexible (single or split)'],
];

export function PatternPolicySelect({
  label,
  emptyLabel,
  value,
  onChange,
}: {
  label: string;
  emptyLabel: string;
  value: PatternPolicy | null | undefined;
  onChange: (value: PatternPolicy | null) => void;
}) {
  return (
    <label>
      {label}{' '}
      <span className="academic-field-indicator" aria-hidden="true">
        Optional
      </span>
      <select
        aria-label={label}
        value={value ?? ''}
        onChange={(e) => onChange((e.target.value || null) as PatternPolicy | null)}
      >
        <option value="">{emptyLabel}</option>
        {policyLabels.map(([key, text]) => (
          <option key={key} value={key}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Empty fields mean "no preference"; all empty removes the rules entirely. */
export function ShapeRuleFields({
  value,
  onChange,
}: {
  value: DailyShapeRules | null | undefined;
  onChange: (value: DailyShapeRules | null) => void;
}) {
  const field = (
    label: string,
    key: keyof DailyShapeRules,
    min: number,
    max: number,
    scale = 1,
  ) => (
    <label>
      {label}{' '}
      <span className="academic-field-indicator" aria-hidden="true">
        Optional
      </span>
      <input
        aria-label={label}
        type="number"
        min={min}
        max={max}
        step={scale === 1 ? 1 : 0.5}
        placeholder="No preference"
        value={value?.[key] == null ? '' : value[key]! / scale}
        onChange={(e) => {
          const next = e.target.value === '' ? null : Math.round(Number(e.target.value) * scale);
          const rules = { ...value, [key]: next };
          onChange(Object.values(rules).some((item) => item != null) ? rules : null);
        }}
      />
    </label>
  );
  return (
    <fieldset>
      <legend>Commuter-friendly day shape (per section)</legend>
      <div className="academic-field-grid">
        {field('Fewest classes on a class day', 'min_sessions_per_active_day', 1, 6)}
        {field('Most classes on a class day', 'max_sessions_per_day', 1, 10)}
        {field('Longest day, first class to last (hours)', 'max_daily_span_minutes', 1, 24, 60)}
      </div>
      <p className="muted">
        These are preferences. Generation improves the timetable toward them and lists every
        section-day that still misses one; a valid timetable is never rejected because of them.
      </p>
    </fieldset>
  );
}
