import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { env } from '../lib/env';
import { addDays } from '../lib/calendar-model';

export function AcademicFixtureImport() {
  const navigate = useNavigate();
  const [programs, setPrograms] = useState('bsit');
  const [years, setYears] = useState('3');
  const [letters, setLetters] = useState('A');
  const [certificate, setCertificate] = useState('Certificate A');
  const [semester, setSemester] = useState('first');
  const [academicYear, setAcademicYear] = useState('2026-2027');
  const [days, setDays] = useState([0, 1, 2, 3, 4]);
  const [midtermEnd, setMidtermEnd] = useState('');
  const [start, setStart] = useState('2026-10-01');
  const [end, setEnd] = useState('2026-12-31');
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!review) {
      setReview(true);
      return;
    }
    setBusy(true);
    setError('');
    try {
      const values = (value: string) =>
        value
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);
      const response = await fetch(`${env.apiBaseUrl}/academic/sandbox/fixtures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          program_ids: values(programs),
          year_levels: values(years).map(Number),
          section_letters: values(letters),
          certificate_groups: values(certificate),
          calendar: {
            academic_year: academicYear,
            semester,
            effective_start: start,
            effective_end: end,
            timezone: 'Asia/Manila',
            instructional_days: days,
            phases: midtermEnd
              ? [
                  { name: 'midterm', start, end: midtermEnd },
                  { name: 'final', start: addDays(midtermEnd, 1), end },
                ]
              : [],
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error?.message ?? JSON.stringify(payload.detail));
      navigate(`/admin/ai-scheduling?period=${payload.data.period.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="workspace-card">
      <summary>Sample Academic Scenario</summary>
      <form className="academic-create-period" onSubmit={submit}>
        <p>
          Start with BSIT 3A or customize the isolated scenario, using synthetic teachers, subjects
          and four synthetic classroom candidates. No provisional CdM room is made eligible.
        </p>
        <details hidden={review}>
          <summary>Customize sample scenario</summary>
          <label>
            Academic year
            <input
              pattern="[0-9]{4}-[0-9]{4}"
              required
              value={academicYear}
              onChange={(e) => setAcademicYear(e.target.value)}
            />
          </label>
          <p>
            Synthetic curriculum, teachers and mock sections. Original academic records and drafts
            are preserved. Repeating the same import reuses its period without overwriting edits.
          </p>
          <label>
            Program IDs (comma separated)
            <input
              value={programs}
              onChange={(e) => setPrograms(e.target.value)}
              aria-describedby="fixture-programs"
            />
          </label>
          <p id="fixture-programs" className="muted">
            bsit, bscpe, bsed-sci, beed-gen, beed-eced, btled-ict, bsba-hrm, bse, tcp
          </p>
          <label>
            Configured degree years (1–4)
            <input value={years} onChange={(e) => setYears(e.target.value)} />
          </label>
          <label>
            Mock section letters (A–D)
            <input value={letters} onChange={(e) => setLetters(e.target.value)} />
          </label>
          <label>
            Certificate groups (TCP only)
            <input value={certificate} onChange={(e) => setCertificate(e.target.value)} />
          </label>
          <label>
            Semester
            <select value={semester} onChange={(e) => setSemester(e.target.value)}>
              <option value="first">First semester</option>
              <option value="second">Second semester</option>
            </select>
          </label>
          <label>
            Effective start
            <input type="date" required value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label>
            Effective end
            <input type="date" required value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label>
            Midterm phase ends (optional)
            <input type="date" value={midtermEnd} onChange={(e) => setMidtermEnd(e.target.value)} />
          </label>
          <p className="muted">
            Final term starts the following day within this semester. Phases do not duplicate weekly
            teaching hours.
          </p>
          <fieldset>
            <legend>Instructional days</legend>
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(
              (name, day) => (
                <label className="academic-checkbox" key={day}>
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
          <p className="muted">
            Start with BSIT 3A. The import configures sections, not proof of actual CdM enrollment.
            Two 180-minute demonstration subjects per configured section; no capacities or equipment
            are asserted.
          </p>
        </details>
        {review && (
          <section className="sample-setup-review" aria-label="Review sample setup">
            <h3>Review sample setup</h3>
            <p>
              {academicYear} · {semester === 'first' ? '1st' : '2nd'} Semester
            </p>
            <dl>
              <div>
                <dt>Programs</dt>
                <dd>{programs.toUpperCase()}</dd>
              </div>
              <div>
                <dt>Degree years / section labels</dt>
                <dd>
                  {years} / {letters}
                </dd>
              </div>
              <div>
                <dt>Effective dates</dt>
                <dd>
                  {start} to {end}
                </dd>
              </div>
            </dl>
            <p>
              Two demonstration offerings per configured section. Repeating this import reuses its
              period without overwriting edits. Generation and publication are separate actions.
            </p>
            <Button variant="secondary" type="button" onClick={() => setReview(false)}>
              Back to configuration
            </Button>
          </section>
        )}
        <Button disabled={busy}>
          {busy ? 'Importing…' : review ? 'Import sample period' : 'Review sample setup'}
        </Button>
        {error && <p role="alert">{error}</p>}
      </form>
    </details>
  );
}
