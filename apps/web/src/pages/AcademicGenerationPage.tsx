import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  checkAcademicReadiness,
  generateAcademicSchedule,
  listAcademicPeriods,
  type AcademicReadiness,
  type AcademicPeriod,
} from '../lib/academic-api';
import { schedulingSandboxEnabled, type GenerationResult } from '../lib/scheduling-api';
import {
  defaultPeriod,
  periodLabel,
  readWorkspace,
  rememberWorkspace,
} from '../lib/workspace-context';
import { SaveDraftPanel } from './SchedulingDraftPages';
import { SchedulingTimetable } from './SchedulingTimetable';
import { WeeklySchedulingPage } from './WeeklySchedulingPage';
import { AcademicFixtureImport } from './AcademicFixtureImport';
import { IndependentValidation } from './TimetableValidation';

export function SchedulingSourcePage() {
  const [search] = useSearchParams();
  return (
    <div className="weekly-scheduler ux-generator">
      <p className="ux-engine-note">
        Constraint-based automated scheduling · OR-Tools. Language-model recommendations are
        planned.
      </p>
      {search.get('source') === 'synthetic' ? (
        <>
          <p>Explicit synthetic engine test scenario</p>
          <WeeklySchedulingPage />
        </>
      ) : (
        <AcademicGenerationPage />
      )}
    </div>
  );
}
function fixPath(code: string, period: string) {
  const path = /faculty|teacher|workload/.test(code)
    ? '/admin/teachers'
    : /room|resource/.test(code)
      ? '/admin/academic/resources'
      : /section/.test(code)
        ? '/admin/sections'
        : /operating|scope|constraint/.test(code)
          ? '/admin/scheduling-constraints'
          : '/admin/offerings';
  return path + '?period=' + encodeURIComponent(period);
}
export function ReadinessSummary({ checked }: { checked: AcademicReadiness }) {
  const blocking = checked.issues.filter((i) => i.severity === 'blocking');
  const warnings = checked.issues.filter((i) => i.severity !== 'blocking');
  const groups = [
    {
      name: 'Classroom requirements',
      test: /room|resource/,
      action: 'Review room requirements',
      path: '/admin/offerings',
      reason:
        'Review classroom requirements and eligible resources. Unverified rooms are not assumed suitable.',
    },
    {
      name: 'Faculty availability',
      test: /faculty|teacher|workload/,
      action: 'Review faculty availability',
      path: '/admin/teachers',
      reason: 'Check subject eligibility, availability and workload limits.',
    },
    {
      name: 'Teaching windows',
      test: /operating|placement|distinct_days|weekly_time/,
      action: 'Review teaching windows',
      path: '/admin/scheduling-constraints',
      reason: 'Recorded teaching windows must support every required meeting.',
    },
    {
      name: 'Subject offerings',
      test: /offering|subject|minute|pattern|reference|session|section|program/,
      action: 'Review subject offerings',
      path: '/admin/offerings',
      reason: 'Complete the required academic records and meeting patterns.',
    },
    {
      name: 'Institutional constraints',
      test: /.*/,
      action: 'Review constraints',
      path: '/admin/scheduling-constraints',
      reason: 'Review the recorded scheduling rules before generating.',
    },
  ];
  const remaining = [...blocking];
  const grouped = groups
    .map((g) => {
      const items = remaining.filter((i) => g.test.test(i.code));
      items.forEach((i) => remaining.splice(remaining.indexOf(i), 1));
      return { ...g, items };
    })
    .filter((g) => g.items.length);
  return (
    <section className="ux-readiness" aria-label="Academic readiness">
      <div className="ux-section-heading">
        <h2>Readiness</h2>
        <StatusBadge tone={checked.ready ? 'success' : 'warning'}>
          {checked.ready ? 'Ready for generation' : `${blocking.length} blocking issues`}
        </StatusBadge>
      </div>
      <div className="ux-scope-stats">
        <span>
          <strong>{checked.sections}</strong>Sections
        </span>
        <span>
          <strong>{checked.offerings}</strong>Subject offerings
        </span>
        <span>
          <strong>
            {checked.assigned_faculty ?? checked.inputs?.teachers?.length ?? checked.faculty}
          </strong>
          {checked.assigned_faculty != null || checked.inputs ? 'Teachers' : 'Faculty catalog'}
        </span>
        <span>
          <strong>{checked.eligible_resources}</strong>Classroom candidates
        </span>
      </div>
      {blocking.length > 0 && (
        <section
          className="readiness-issues"
          id="readiness-issues"
          tabIndex={-1}
          aria-label="Requirements to resolve"
        >
          <h3>What needs attention</h3>
          {grouped.map((g) => (
            <article key={g.name} className="readiness-issue-group">
              <div>
                <h4>{g.name}</h4>
                <span>
                  {g.items.length} {g.items.length === 1 ? 'issue' : 'issues'}
                </span>
              </div>
              <p>
                {g.items.every((i) => i.code === 'no_eligible_room')
                  ? `${new Set(g.items.map((i) => i.record_id)).size} offerings need suitable classrooms. No classroom satisfies the recorded requirements.`
                  : g.reason}
              </p>
              <Link
                className="button button--secondary"
                to={g.path + '?period=' + encodeURIComponent(checked.period.id)}
              >
                {g.action}
              </Link>
              <details>
                <summary>Affected records and validation details</summary>
                <ul>
                  {g.items.map((i, n) => (
                    <li key={n}>
                      <p>{i.message}</p>
                      <Link className="text-action" to={fixPath(i.code, checked.period.id)}>
                        Review related academic data
                      </Link>
                    </li>
                  ))}
                </ul>
              </details>
            </article>
          ))}
        </section>
      )}
      {(warnings.length > 0 || checked.ready) && (
        <details className="readiness-notes">
          <summary>
            {warnings.length ? `${warnings.length} data notes` : 'Scope and suitability details'}
          </summary>
          <p>
            Classroom candidates are checked against each offering's requirements. Their count does
            not confirm suitability. The solver determines feasibility; generation does not publish.
          </p>
          <ul>
            {warnings.map((i, n) => (
              <li key={n}>{i.message}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
function AcademicGenerationPage() {
  const [search, setSearch] = useSearchParams();
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]),
    [period, setPeriod] = useState(search.get('period') ?? readWorkspace('administrator').period);
  const [checked, setChecked] = useState<AcademicReadiness | null>(null),
    [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState(''),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [retry, setRetry] = useState(0);
  const active = useRef(false),
    heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    listAcademicPeriods()
      .then((v) => {
        if (!ignore) {
          setPeriods(v.periods);
          setPeriod((p) => defaultPeriod(v.periods, p));
        }
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [retry]);
  useEffect(() => {
    if (!period || !schedulingSandboxEnabled) return;
    let ignore = false;
    setChecked(null);
    checkAcademicReadiness(period)
      .then((v) => {
        if (!ignore) setChecked(v);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    rememberWorkspace('administrator', { ...readWorkspace('administrator'), period });
    return () => {
      ignore = true;
    };
  }, [period, retry]);
  useEffect(() => {
    if (result) heading.current?.focus();
  }, [result]);
  if (!schedulingSandboxEnabled)
    return (
      <p>
        Verified Administrator sign-in is required for academic scheduling. Local preview mutations
        are disabled in this build.
      </p>
    );
  async function generate() {
    if (!checked?.ready || active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      setResult(await generateAcademicSchedule(checked.period.id, checked.period.revision));
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Generation was not confirmed. Recheck readiness and retry.',
      );
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  const success =
    result && ['feasible', 'optimal'].includes(result.solver_status) && result.validation?.valid;
  return (
    <div className="ux-generation-flow" aria-busy={busy}>
      <ol className="ux-steps" aria-label="Scheduling steps">
        <li>Select period</li>
        <li>Generate</li>
        <li>Review</li>
        <li>Save draft</li>
      </ol>
      <section className="workspace-card ux-generation-setup">
        <div className="ux-section-heading">
          <h2>Generate a weekly timetable</h2>
          <span className="muted">
            {checked?.inputs?.synthetic ? 'Sample data' : 'Local academic records'}
          </span>
        </div>
        <label>
          Academic period
          <select
            value={period}
            disabled={busy}
            onChange={(e) => {
              setPeriod(e.target.value);
              setResult(null);
              setError('');
              const next = new URLSearchParams(search);
              next.set('period', e.target.value);
              setSearch(next);
            }}
          >
            <option value="">Choose a period</option>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {periodLabel(p)}
              </option>
            ))}
          </select>
        </label>
        {loading && <p role="status">Loading academic periods…</p>}
        {!loading && !periods.length && !error && (
          <p>No academic periods yet. Set up academic data or explicitly import a sample below.</p>
        )}
        {checked && <ReadinessSummary checked={checked} />}
        <Button
          variant={result ? 'secondary' : 'primary'}
          disabled={!checked?.ready || busy}
          onClick={generate}
        >
          {busy ? 'Generating weekly schedule…' : 'Generate Weekly Schedule'}
        </Button>
        {checked && !checked.ready && (
          <div className="readiness-resolve">
            <p>
              {checked.issues.filter((i) => i.severity === 'blocking').length} blocking issues must
              be resolved before generation.
            </p>
            <Button
              variant="secondary"
              onClick={() => {
                document.getElementById('readiness-issues')?.focus();
                document.getElementById('readiness-issues')?.scrollIntoView({ block: 'start' });
              }}
            >
              Resolve Requirements
            </Button>
          </div>
        )}
        {busy && (
          <p role="status">
            OR-Tools is checking the complete selected scope. You can review only after the server
            returns a validated result.
          </p>
        )}
        <details>
          <summary>Advanced setup and data</summary>
          <p>
            All active offerings are required. Hard constraints stay enforced. Saving does not
            publish.
          </p>
          <div className="draft-actions">
            <Link
              className="button button--secondary"
              to={`/admin/academic${period ? '?period=' + encodeURIComponent(period) : ''}`}
            >
              Manage Academic Data
            </Link>
            <Link
              className="button button--secondary"
              to={'/admin/scheduling-constraints?period=' + encodeURIComponent(period)}
            >
              Teaching windows and solver objectives
            </Link>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                setError('');
                setRetry((n) => n + 1);
              }}
            >
              Recheck readiness
            </Button>
          </div>
        </details>
      </section>
      {error && (
        <div role="alert" className="workspace-card">
          <p>{error}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setError('');
              setRetry((n) => n + 1);
            }}
          >
            Retry loading scheduling data
          </Button>
        </div>
      )}
      {!result && <AcademicFixtureImport />}
      {result && (
        <section className="scheduler-result">
          <h2 ref={heading} tabIndex={-1}>
            Review generated timetable
          </h2>
          <StatusBadge tone={success ? 'success' : 'warning'}>
            {result.solver_status === 'infeasible'
              ? 'Infeasible — no solution satisfies these constraints'
              : result.solver_status === 'unknown'
                ? 'Unknown — no validated solution returned'
                : result.solver_status}
          </StatusBadge>
          <div className="ux-scope-stats">
            <span>
              <strong>
                {result.total_offerings_scheduled}/{result.total_offerings_requested}
              </strong>
              offerings covered
            </span>
            <span>
              <strong>{result.assignments.length}</strong>sessions
            </span>
            <span>
              <strong>
                {result.coverage.reduce((n, c) => n + c.allocated_minutes, 0)}/
                {result.coverage.reduce((n, c) => n + c.required_minutes, 0)}
              </strong>
              assigned / required min
            </span>
            <span>
              <strong>{result.hard_conflict_count ?? 'Not validated'}</strong>hard conflicts
            </span>
          </div>
          {!success && (
            <p>
              Review academic constraints and availability, then generate again. Unknown does not
              prove infeasibility.
            </p>
          )}
          <ul>
            {result.diagnostics.map((d, i) => (
              <li key={i}>{d.message}</li>
            ))}
          </ul>
          {success && checked?.inputs && (
            <>
              <SchedulingTimetable key={result.run_id} input={checked.inputs} result={result} />
              <IndependentValidation input={checked.inputs} assignments={result.assignments} />
              <SaveDraftPanel
                key={'save:' + result.run_id}
                result={result}
                source="academic"
                defaultTitle={`${periodLabel(checked.period)} — Draft`}
              />
            </>
          )}
        </section>
      )}
      <Link className="text-action" to="/admin/schedule-manager/drafts?source=academic">
        Saved Drafts
      </Link>
    </div>
  );
}
