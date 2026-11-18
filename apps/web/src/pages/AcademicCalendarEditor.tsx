import { useState, type FormEvent } from 'react';
import type { AcademicSnapshot } from '../lib/academic-api';
import { Button } from '../components/ui/Button';
import { env } from '../lib/env';
import { liveFetch } from '../config/runtime-config';
import { appMode } from '../config/runtime-config';
import { institutionalRequest } from '../lib/institutional-api';
import { addDays } from '../lib/calendar-model';
export function AcademicCalendarEditor({
  snapshot,
  onSaved,
  open,
}: {
  snapshot: AcademicSnapshot;
  onSaved: (snapshot: AcademicSnapshot) => void;
  open?: boolean;
}) {
  const c = snapshot.period.calendar;
  const [year, setYear] = useState(c?.academic_year ?? '');
  const [semester, setSemester] = useState<'' | 'first' | 'second'>(c?.semester ?? '');
  const [start, setStart] = useState(c?.effective_start ?? '');
  const [end, setEnd] = useState(c?.effective_end ?? '');
  const [midterm, setMidterm] = useState(c?.phases?.find((p) => p.name === 'midterm')?.end ?? '');
  const [days, setDays] = useState(c?.instructional_days ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = {
        expected_revision: snapshot.period.revision,
        calendar: {
          academic_year: year,
          semester: semester as 'first' | 'second',
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
      };
      if (appMode === 'institutional') {
        onSaved(
          await institutionalRequest<AcademicSnapshot>(
            `academic/periods/${snapshot.period.id}/calendar`,
            { method: 'PUT', body, role: 'administrator' },
          ),
        );
        return;
      }
      const r = await liveFetch(
        `${env.apiBaseUrl}/academic/sandbox/periods/${snapshot.period.id}/calendar`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
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
      <details className="workspace-card" open={open ?? !c}>
      <summary>Academic year, semester and instructional calendar</summary>
      <form className="academic-create-period" onSubmit={submit}>
        <p>
          The existing calendar contract uses Asia/Manila. Enter dates and instructional days from
          the approved institutional calendar; blank dates and days are never prefilled. Midterm and
          Final Term are phases inside the semester. Changing these dates versions the academic
          inputs; existing drafts stay intact and require revalidation.
        </p>
        {!c && <p role="note">No academic calendar is saved for this period yet.</p>}
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
            required
            value={semester}
            onChange={(e) => setSemester(e.target.value as '' | 'first' | 'second')}
          >
            <option value="">Choose semester</option>
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
        <fieldset aria-describedby="academic-calendar-days-help">
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
        <p id="academic-calendar-days-help" className="muted">
          Select the actual teaching days, including Saturday/Sunday only if they are approved.
        </p>
        <Button disabled={busy || days.length === 0}>
          {busy ? 'Saving calendar…' : 'Save academic calendar'}
        </Button>
        {error && <p role="alert">{error}</p>}
      </form>
    </details>
  );
}
