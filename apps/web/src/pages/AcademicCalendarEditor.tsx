import { useState, type FormEvent } from 'react';
import type { AcademicSnapshot } from '../lib/academic-api';
import { Button } from '../components/ui/Button';
import { env } from '../lib/env';
import { addDays } from '../lib/calendar-model';
export function AcademicCalendarEditor({
  snapshot,
  onSaved,
}: {
  snapshot: AcademicSnapshot;
  onSaved: (snapshot: AcademicSnapshot) => void;
}) {
  const c = snapshot.period.calendar;
  const [year, setYear] = useState(c?.academic_year ?? '2026-2027');
  const [semester, setSemester] = useState(c?.semester ?? 'first');
  const [start, setStart] = useState(c?.effective_start ?? '2026-10-01');
  const [end, setEnd] = useState(c?.effective_end ?? '2026-12-31');
  const [midterm, setMidterm] = useState(c?.phases?.find((p) => p.name === 'midterm')?.end ?? '');
  const [days, setDays] = useState(c?.instructional_days ?? [0, 1, 2, 3, 4]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const r = await fetch(
        `${env.apiBaseUrl}/academic/sandbox/periods/${snapshot.period.id}/calendar`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_revision: snapshot.period.revision,
            calendar: {
              academic_year: year,
              semester,
              effective_start: start,
              effective_end: end,
              timezone: 'Asia/Manila',
              instructional_days: days,
              phases: midterm
                ? [
                    { name: 'midterm', start, end: midterm },
                    { name: 'final', start: addDays(midterm, 1), end },
                  ]
                : [],
              exceptions: c?.exceptions ?? [],
              published_version: null,
            },
          }),
        },
      );
      const p = await r.json();
      if (!r.ok)
        throw new Error(
          typeof p.error?.message === 'string'
            ? p.error.message
            : JSON.stringify(p.detail ?? p.error),
        );
      onSaved(p.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Calendar save failed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="workspace-card">
      <summary>Academic year, semester and instructional calendar</summary>
      <form className="academic-create-period" onSubmit={submit}>
        <p>
          Asia/Manila. Midterm and Final Term are phases inside the semester. Changing these dates
          versions the academic inputs; existing drafts stay intact and require revalidation.
        </p>
        <label>
          Academic year
          <input
            pattern="[0-9]{4}-[0-9]{4}"
            required
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </label>
        <label>
          Semester
          <select
            value={semester}
            onChange={(e) => setSemester(e.target.value as 'first' | 'second')}
          >
            <option value="first">First semester</option>
            <option value="second">Second semester</option>
          </select>
        </label>
        <label>
          Effective start
          <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          Effective end
          <input required type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>
          Midterm phase ends (optional)
          <input type="date" value={midterm} onChange={(e) => setMidterm(e.target.value)} />
        </label>
        <fieldset>
          <legend>Instructional days</legend>
          {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(
            (name, day) => (
              <label key={day} className="academic-checkbox">
                <input
                  type="checkbox"
                  checked={days.includes(day)}
                  onChange={(e) =>
                    setDays(
                      e.target.checked ? [...days, day].sort() : days.filter((d) => d !== day),
                    )
                  }
                />
                {name}
              </label>
            ),
          )}
        </fieldset>
        <Button disabled={busy}>{busy ? 'Saving calendar…' : 'Save academic calendar'}</Button>
        {error && <p role="alert">{error}</p>}
      </form>
    </details>
  );
}
