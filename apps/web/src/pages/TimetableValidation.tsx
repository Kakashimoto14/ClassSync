import { useState } from 'react';
import { Link } from 'react-router-dom';
import { sectionLabel } from '../lib/scheduling-labels';
import { Button } from '../components/ui/Button';
import {
  validateWeeklySchedule,
  type GenerationInput,
  type GenerationResult,
} from '../lib/scheduling-api';
import type { ValidationResult } from '../../../../packages/shared-types/src/scheduling';

export function IndependentValidation({
  input,
  assignments,
}: {
  input: GenerationInput;
  assignments: GenerationResult['assignments'];
}) {
  const [result, setResult] = useState<ValidationResult | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function validate() {
    if (busy) return;
    setBusy(true);
    setResult(null);
    setError('');
    try {
      setResult(await validateWeeklySchedule(input, assignments));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Validation was not confirmed.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card ux-validation">
      <div className="ux-section-heading">
        <h3>Independent conflict check</h3>
        <Button variant="secondary" disabled={busy} onClick={validate}>
          {busy ? 'Checking constraints…' : 'Validate timetable'}
        </Button>
      </div>
      <p className="muted">
        Deterministic backend validation of this exact snapshot. No AI explanation or automatic
        resolution.
      </p>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p role="status">
            {result.valid
              ? `Validated · ${result.hard_conflict_count} hard conflicts`
              : `Validation failed · ${result.hard_conflict_count} hard conflicts`}
          </p>
          <ul>
            {result.conflicts.map((c, i) => (
              <li key={i}>
                <strong>Blocking · {c.code.replaceAll('_', ' ')}</strong>
                <p>{c.message}</p>
                {(c.assignment_ids ?? []).map((id) => {
                  const a = assignments.find((v) => v.id === id);
                  return a ? (
                    <a
                      key={id}
                      href={'#assignment-' + encodeURIComponent(id)}
                      onClick={() => {
                        const target = document.getElementById('assignment-' + id);
                        const details = target?.closest('details');
                        if (details) details.open = true;
                        if (target) {
                          target.tabIndex = -1;
                          target.focus();
                        }
                      }}
                    >
                      {input.offerings?.find((o) => o.id === a.offering_id)?.subject_name} ·{' '}
                      {input.rooms?.find((r) => r.id === a.room_id)?.name} ·{' '}
                      {input.teachers?.find((t) => t.id === a.teacher_id)?.name} ·{' '}
                      {sectionLabel(
                        input.sections?.find((s) => s.id === a.section_id),
                        input,
                      )}
                    </a>
                  ) : null;
                })}
              </li>
            ))}
          </ul>
          {!result.valid && (
            <Link to={'/admin/academic?period=' + encodeURIComponent(input.period_id)}>
              Review source constraints
            </Link>
          )}
        </>
      )}
    </section>
  );
}
