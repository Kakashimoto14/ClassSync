import { SchedulingTimetable } from './SchedulingTimetable';
import { SaveDraftPanel } from './SchedulingDraftPages';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, RefreshCw } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  checkSchedulingInputs,
  generateWeeklySchedule,
  loadSchedulingScenario,
  schedulingSandboxEnabled,
  validateWeeklySchedule,
  type GenerationInput,
  type GenerationResult,
  type ValidationResult,
} from '../lib/scheduling-api';

export function WeeklySchedulingPage() {
  const [input, setInput] = useState<GenerationInput | null>(null);
  const [source, setSource] = useState('feasible');
  const [json, setJson] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [dirty, setDirty] = useState(false);
  const [readiness, setReadiness] = useState<string[]>([]);
  const active = useRef(false);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!result) return;
    resultHeading.current?.focus({ preventScroll: true });
    resultHeading.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [result]);
  const resetResults = () => {
    setResult(null);
    setValidation(null);
  };
  async function load() {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    setInput(null);
    resetResults();
    try {
      const next = await loadSchedulingScenario(source === 'infeasible');
      setInput(next);
      setJson(JSON.stringify(next, null, 2));
      setDirty(false);
      setReadiness([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load scenario.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  async function generate() {
    if (!input || dirty || active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    resetResults();
    try {
      const run = await generateWeeklySchedule(input);
      setResult(run);
      setValidation(run.validation);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed. No timetable accepted.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  async function applyJson() {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    try {
      const value: unknown = JSON.parse(json);
      const checked = await checkSchedulingInputs(value);
      setInput(checked.inputs);
      setJson(JSON.stringify(checked.inputs, null, 2));
      setDirty(false);
      setReadiness(checked.diagnostics.map((d) => d.message));
      resetResults();
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Invalid JSON.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  async function revalidate() {
    if (!input || !result || active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      setValidation(await validateWeeklySchedule(input, result.assignments));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Validation unavailable.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  if (!schedulingSandboxEnabled)
    return (
      <section className="workspace-card">
        <h2>Scheduling sandbox unavailable</h2>
        <p>
          This local synthetic-data workflow is available only in development. Production scheduling
          requires verified Administrator authorization.
        </p>
      </section>
    );
  const offerings = input?.offerings ?? [];
  const sections = input?.sections ?? [];
  const eligible = (input?.rooms ?? []).filter(
    (r) => r.schedulable && r.condition === 'operational',
  );
  const missing = input
    ? [
        !offerings.length && 'Subject offerings',
        !sections.length && 'Sections',
        !input.teachers?.length && 'Teachers',
        !eligible.length && 'Eligible operational classrooms',
        !input.operating_windows?.length && 'Allowed scheduling times',
      ].filter(Boolean)
    : [];
  const success =
    result && ['optimal', 'feasible'].includes(result.solver_status) && validation?.valid;
  return (
    <div className="weekly-scheduler" aria-busy={busy}>
      <p className="scheduling-boundary">
        Development scheduling sandbox · Real CP-SAT solver · Synthetic inputs · Generated previews
        are unpublished. Save a validated result explicitly to keep a draft.
      </p>
      <section className="workspace-card" aria-labelledby="period-step">
        <h2 id="period-step">1. Select academic scenario</h2>
        <div className="scheduler-source">
          <label>
            Academic period / scenario
            <select
              value={source}
              disabled={busy}
              onChange={(e) => {
                setSource(e.target.value);
                setInput(null);
                setJson('');
                resetResults();
                setError('');
              }}
            >
              <option value="feasible">Synthetic week — complete example batch</option>
              <option value="infeasible">Synthetic week — insufficient time</option>
            </select>
          </label>
          <Button variant="secondary" onClick={load} disabled={busy}>
            Load scheduling inputs
          </Button>
        </div>
        <p className="muted">
          No official curriculum, teacher availability, capacity or enrollment dataset has been
          supplied. CDM provisional spaces are kept separate and are not automatically eligible.
        </p>
      </section>
      {input && (
        <section className="workspace-card" aria-labelledby="inputs-step">
          <h2 id="inputs-step">2. Review scheduling inputs</h2>
          <p>
            <strong>{input.period_id}</strong> · Data version {input.data_version}
          </p>
          <p className="muted">{input.scope_description}</p>
          <dl className="scheduler-counts">
            {[
              ['Programs', input.programs?.length ?? 0],
              ['Sections', sections.length],
              ['Offerings', offerings.length],
              ['Teachers', input.teachers?.length ?? 0],
              ['Eligible rooms', eligible.length],
            ].map(([name, count]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
          <p>
            Required weekly instruction:{' '}
            <strong>
              {offerings.reduce((sum, o) => sum + (o.required_weekly_minutes ?? 180), 0)} minutes
            </strong>
            . The 180-minute default is a scenario assumption, not official credit-unit policy.
          </p>
          {missing.length > 0 && (
            <p role="status">
              Missing: {missing.join(', ')}. Submit to receive the backend's detailed readiness
              diagnostics.
            </p>
          )}
          {readiness.length > 0 && (
            <ul className="scheduler-diagnostics" aria-label="Input readiness diagnostics">
              {readiness.map((message, i) => (
                <li key={i}>{message}</li>
              ))}
            </ul>
          )}
          <details>
            <summary>Inspect or edit the complete input batch</summary>
            <p className="muted">
              Edit availability, eligibility, patterns, locks and preferences. All changes are
              revalidated by the backend. Use only synthetic data here.
            </p>
            <label>
              Scheduling input JSON
              <textarea
                rows={12}
                spellCheck={false}
                value={json}
                disabled={busy}
                onChange={(e) => {
                  setJson(e.target.value);
                  setDirty(true);
                  resetResults();
                }}
              />
            </label>
            <Button variant="secondary" onClick={applyJson} disabled={busy}>
              Apply input changes
            </Button>
            {dirty && (
              <p role="status">
                Unapplied input changes. Apply and validate them before generation.
              </p>
            )}
          </details>
        </section>
      )}
      <section className="scheduler-generate" aria-labelledby="generate-step">
        <h2 id="generate-step">3. Generate complete weekly timetable</h2>
        <Button onClick={generate} disabled={!input || busy || dirty}>
          <CalendarDays size={18} aria-hidden="true" />
          {busy ? 'Working…' : 'Generate Weekly Schedule'}
        </Button>
        <p role="status" aria-live="polite">
          {busy
            ? 'Processing the complete batch. Solver generation can take up to 30 seconds; please wait.'
            : 'Every supplied offering is required. No automatic publication.'}
        </p>
      </section>
      {error && (
        <div className="scheduler-error" role="alert">
          <h2>Scheduling request could not complete</h2>
          <p>{error}</p>
          <p>Check the inputs and running Gateway/Scheduling services, then retry.</p>
        </div>
      )}
      {result && (
        <section className="scheduler-result" aria-labelledby="result-step">
          <h2 id="result-step" tabIndex={-1} ref={resultHeading}>
            4. Review generated result
          </h2>
          <StatusBadge tone={success ? 'success' : 'warning'}>
            {result.solver_status === 'infeasible'
              ? 'Unschedulable — proven infeasible'
              : result.solver_status.replaceAll('_', ' ')}
          </StatusBadge>
          <p role="status">
            {success
              ? `${result.total_offerings_scheduled}/${result.total_offerings_requested} offerings scheduled · ${result.assignments.length} sessions · ${result.hard_conflict_count} hard conflicts`
              : 'No successful timetable was accepted. Review diagnostics and correct the input.'}
          </p>
          <ul className="scheduler-diagnostics">
            {result.diagnostics.map((d, i) => (
              <li key={i}>
                <strong>{d.code.replaceAll('_', ' ')}</strong>
                {d.offering_id && ` · ${d.offering_id}`}
                <p>{d.message}</p>
              </li>
            ))}
          </ul>
          {success && input && (
            <>
              <SaveDraftPanel key={`save:${result.run_id}`} result={result}/>
              <SchedulingTimetable key={`timetable:${result.run_id}`} input={input} result={result}/>
              <Button variant="secondary" onClick={revalidate} disabled={busy}>
                <RefreshCw size={16} aria-hidden="true" />
                Run independent validation again
              </Button>
              {validation && (
                <section aria-label="Independent validation">
                  <h3>Independent validation</h3>
                  <p role="status">
                    {validation.valid
                      ? 'Passed: exact minutes, references, availability, eligibility, locks and resource conflicts checked independently.'
                      : `${validation.hard_conflict_count} validation issues found.`}
                  </p>
                  {validation.conflicts.map((c, i) => (
                    <p key={i}>
                      {c.message} · {c.assignment_ids?.join(', ')}
                    </p>
                  ))}
                </section>
              )}
            </>
          )}
          <details>
            <summary>Run provenance</summary>
            <p>Run {result.run_id}</p>
            <p>Input SHA-256: {result.input_hash}</p>
            <p>
              {result.metadata.solver} {result.metadata.solver_version} · seed{' '}
              {result.metadata.seed} · {result.metadata.wall_time_seconds.toFixed(2)}s · objective{' '}
              {result.metadata.objective ?? 'unavailable'} · bound{' '}
              {result.metadata.best_bound ?? 'unavailable'}
            </p>
            <p>
              Original generated candidate. Use Save as Draft to persist it; no publication endpoint exists
              in S1.
            </p>
          </details>
        </section>
      )}
      <Link className="text-action" to="/admin/schedule-manager/drafts">Saved Drafts</Link>
      <Link className="text-action" to="/admin/schedule-manager">
        Back to Schedule Manager
      </Link>
    </div>
  );
}
