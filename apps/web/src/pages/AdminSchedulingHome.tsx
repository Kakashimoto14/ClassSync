import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  DoorOpen,
  RefreshCw,
  UsersRound,
} from 'lucide-react';
import {
  checkAcademicReadiness,
  listAcademicPeriods,
  type AcademicReadiness,
} from '../lib/academic-api';
import {
  listSchedulingDrafts,
  type DraftList,
} from '../lib/scheduling-api';
import { timetableRequest } from '../lib/publication-api';
import {
  defaultPeriod,
  periodLabel,
  readWorkspace,
  rememberWorkspace,
  type WorkspacePeriod,
} from '../lib/workspace-context';
import { presentationData, presentationOnlyBuild } from '../lib/presentation-sample';
import { appMode } from '../config/runtime-config';
import { readinessActionForIssue } from '../lib/readiness-navigation';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ClassSyncInlineSpinner, ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';

export function AdminSchedulingHome() {
  return presentationOnlyBuild ? <PresentationOverview /> : <ConnectedOverview />;
}
function PresentationOverview() {
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof presentationData>>>();
  useEffect(() => {
    let ignore = false;
    presentationData().then((p) => {
      if (!ignore) setSummary(p);
    });
    return () => {
      ignore = true;
    };
  }, []);
  return (
    <section className="admin-overview">
      <h1>Scheduling overview</h1>
      <p className="source-label">
        Read-only presentation · {summary?.metadata.version ?? 'Loading sample…'}
      </p>
      <article className="workspace-card admin-next-step">
        <span className="source-label">Sample academic scenario</span>
        <h2>Review the sample campus week</h2>
        <p>AY 2026–2027 · 1st Semester · BSIT 3A</p>
        <Link className="button" to="/admin/calendar">
          Review sample timetable
        </Link>
      </article>
      {summary && (
        <section className="workspace-card">
          <h2>Frozen sample status</h2>
          <dl className="admin-status-list">
            <div>
              <dt>Sections</dt>
              <dd>{summary.calendar.sections.length}</dd>
            </div>
            <div>
              <dt>Subject offerings</dt>
              <dd>{summary.metadata.offerings}</dd>
            </div>
            <div>
              <dt>Weekly sessions</dt>
              <dd>{summary.metadata.sessions_per_week}</dd>
            </div>
            <div>
              <dt>Hard conflicts at export</dt>
              <dd>{summary.metadata.hard_conflicts_at_export}</dd>
            </div>
          </dl>
        </section>
      )}
      <p className="muted">
        No live synchronization or campus metrics. Generation, database writes and publication
        require the connected authorized backend.
      </p>
    </section>
  );
}
function ConnectedOverview() {
  const [periods, setPeriods] = useState<WorkspacePeriod[]>([]),
    [period, setPeriod] = useState(readWorkspace('administrator').period);
  const [drafts, setDrafts] = useState<DraftList>(),
    [checked, setChecked] = useState<AcademicReadiness>();
  const [published, setPublished] = useState<WorkspacePeriod[]>(),
    [publicationError, setPublicationError] = useState(false);
  const [error, setError] = useState(''),
    [loading, setLoading] = useState(true),
    [checking, setChecking] = useState(false),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError('');
    Promise.all([listAcademicPeriods(), listSchedulingDrafts(0, 'academic')])
      .then(([p, d]) => {
        if (!ignore) {
          setPeriods(p.periods);
          setPeriod((old) => defaultPeriod(p.periods, old));
          setDrafts(d);
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
    if (!period) {
      setChecked(undefined);
      setPublished(undefined);
      setChecking(false);
      return;
    }
    let ignore = false;
    setChecking(true);
    setChecked(undefined);
    setError('');
    setPublished(undefined);
    setPublicationError(false);
    rememberWorkspace('administrator', { ...readWorkspace('administrator'), period });
    const readinessRequest = checkAcademicReadiness(period);
    readinessRequest
      .then((v) => {
        if (!ignore) setChecked(v);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      })
      .finally(() => {
        if (!ignore) setChecking(false);
      });
    timetableRequest<{ periods: WorkspacePeriod[] }>(
      appMode === 'sandbox' ? 'sandbox/periods' : 'periods',
    )
      .then((v) => {
        if (!ignore) setPublished(v.periods);
      })
      .catch(() => {
        if (!ignore) setPublicationError(true);
      });
    return () => {
      ignore = true;
    };
  }, [period, retry]);
  const selected = periods.find((p) => p.id === period);
  const currentReadiness = checked?.period.id === period ? checked : undefined;
  const periodDrafts = useMemo(
    () =>
      (drafts?.drafts ?? [])
        .filter((draft) => draft.period_id === period)
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [drafts, period],
  );
  const latest = periodDrafts[0];
  const currentDraft =
    latest?.data_version === `academic:${period}:revision:${currentReadiness?.period.revision}` &&
    latest.validated === true;
  const blockers = currentReadiness?.issues.filter((issue) => issue.severity === 'blocking') ?? [];
  const warnings = currentReadiness?.issues.filter((issue) => issue.severity !== 'blocking') ?? [];
  const shownBlockers = blockers.slice(0, 3);
  const publication = published?.find((item) => item.id === period && (item.revision ?? 0) > 0);
  const periodQuery = period ? `?period=${encodeURIComponent(period)}` : '';
  const action = !period
    ? { label: 'Set up academic period', to: '/admin/academic' }
    : !currentReadiness
      ? null
      : !currentReadiness.ready
        ? blockers[0]
          ? {
              label: 'Resolve next blocker',
              to: readinessActionForIssue(blockers[0], period).to,
            }
          : { label: 'Review scheduling readiness', to: `/admin/ai-scheduling${periodQuery}` }
        : currentDraft
          ? {
              label: 'Review saved draft',
              to: `/admin/schedule-manager/drafts/${encodeURIComponent(latest!.id)}?source=academic`,
            }
          : { label: 'Generate weekly schedule', to: `/admin/ai-scheduling${periodQuery}` };
  const workspaceLabel =
    appMode === 'institutional'
      ? 'Institutional workspace'
      : appMode === 'sandbox'
        ? 'Development sandbox'
        : 'Read-only presentation';
  const setupSteps = [
    {
      title: 'Academic setup',
      to: '/admin/academic',
      done: !!currentReadiness && currentReadiness.programs > 0 && currentReadiness.subjects > 0
        && currentReadiness.sections > 0 && currentReadiness.offerings > 0,
    },
    {
      title: 'Rooms & faculty',
      to: '/admin/academic/resources',
      done: !!currentReadiness && currentReadiness.faculty > 0
        && (currentReadiness.assigned_faculty ?? 0) > 0 && currentReadiness.eligible_resources > 0,
    },
    {
      title: 'Generate schedule',
      to: '/admin/ai-scheduling',
      done: !!currentDraft,
    },
    {
      title: 'Publish & access',
      to: '/admin/calendar',
      done: !!publication,
    },
  ];
  const nextSetupStep = setupSteps.findIndex((step) => !step.done);

  return (
    <section className="admin-overview admin-command-center" aria-labelledby="admin-dashboard-title">
      <header className="admin-command-header">
        <div className="admin-command-title">
          <h1 id="admin-dashboard-title">Scheduling overview</h1>
          <StatusBadge tone={appMode === 'institutional' ? 'success' : 'neutral'}>
            {workspaceLabel}
          </StatusBadge>
        </div>
        <div className="admin-command-controls">
          <label className="admin-period-selector">
            <span className="visually-hidden">Academic period</span>
            <select
              aria-label="Academic period"
              value={period}
              disabled={loading || periods.length === 0}
              onChange={(event) => setPeriod(event.target.value)}
            >
              <option value="">Choose an academic period</option>
              {periods.map((item) => (
                <option value={item.id} key={item.id}>
                  {periodLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="secondary"
            className="admin-refresh-button"
            aria-label="Refresh scheduling readiness"
            title="Refresh scheduling data"
            disabled={loading || checking}
            onClick={() => setRetry((value) => value + 1)}
          >
            <RefreshCw size={16} aria-hidden="true" />
            <span>Refresh</span>
          </Button>
        </div>
      </header>

      <nav className="admin-setup-journey" aria-label="Administrator setup journey">
        {setupSteps.map((step, index) => {
          const state = step.done ? 'Done' : index === nextSetupStep ? 'Next step' : 'Pending';
          return (
            <Link
              className="admin-setup-step"
              data-state={state.toLowerCase().replace(' ', '-')}
              aria-current={index === nextSetupStep ? 'step' : undefined}
              key={step.title}
              to={step.to}
            >
              <span className="admin-setup-step__number">{step.done ? <CheckCircle2 size={15} aria-hidden="true" /> : index + 1}</span>
              <span className="admin-setup-step__copy"><strong>{step.title}</strong><small>{state}</small></span>
            </Link>
          );
        })}
      </nav>

      {loading && <ClassSyncSkeleton layout="kpis" label="Loading scheduling data" />}

      {error && (
        <div role="alert" className="workspace-card admin-command-error">
          <div>
            <h2>Scheduling data is unavailable</h2>
            <p>{error}</p>
          </div>
          <Button variant="secondary" onClick={() => setRetry((value) => value + 1)}>
            Retry
          </Button>
        </div>
      )}

      {!loading && !error && period && currentReadiness && (
        <>
          <nav className="admin-kpi-ribbon" aria-label="Academic period summary">
            <Link className="admin-kpi-card" to={`/admin/sections${periodQuery}`}>
              <span className="admin-kpi-icon"><UsersRound size={18} aria-hidden="true" /></span>
              <span className="admin-kpi-copy"><span>Active sections</span><strong>{currentReadiness.sections}</strong><small>Configured this period</small></span>
            </Link>
            <Link className="admin-kpi-card" to={`/admin/offerings${periodQuery}`}>
              <span className="admin-kpi-icon"><BookOpen size={18} aria-hidden="true" /></span>
              <span className="admin-kpi-copy"><span>Subject offerings</span><strong>{currentReadiness.offerings}</strong><small>{currentReadiness.offerings ? 'Saved for this period' : 'Setup needed'}</small></span>
            </Link>
            <Link className="admin-kpi-card" to={`/admin/academic/resources${periodQuery}`}>
              <span className="admin-kpi-icon"><DoorOpen size={18} aria-hidden="true" /></span>
              <span className="admin-kpi-copy"><span>Schedulable spaces</span><strong>{currentReadiness.eligible_resources}</strong><small>Candidate count · suitability checked per offering</small></span>
            </Link>
            <Link className="admin-kpi-card" to="/admin/schedule-manager/drafts?source=academic">
              <span className="admin-kpi-icon"><ClipboardList size={18} aria-hidden="true" /></span>
              <span className="admin-kpi-copy"><span>Saved drafts</span><strong>{periodDrafts.length}</strong><small>Recent results · open draft list</small></span>
            </Link>
          </nav>

          <div className="admin-command-body">
            <section className="workspace-card admin-readiness-card" aria-labelledby="admin-readiness-title">
              <div className="admin-card-heading">
                <div>
                  <p className="admin-card-eyebrow">{selected ? periodLabel(selected) : 'Selected academic period'}</p>
                  <h2 id="admin-readiness-title">Academic readiness</h2>
                </div>
                <StatusBadge tone={currentReadiness.ready ? 'success' : 'warning'}>
                  {currentReadiness.ready ? 'Ready to generate' : `${blockers.length} ${blockers.length === 1 ? 'blocker' : 'blockers'}`}
                </StatusBadge>
              </div>
              <div className="admin-readiness-summary">
                <p>
                  {currentReadiness.ready
                    ? 'The saved inputs pass current readiness checks. Generation creates a draft for review.'
                    : 'Resolve the blocking items below before generating a schedule.'}
                </p>
                {action && <Link className="button" to={action.to}>{action.label}</Link>}
                {currentDraft && (
                  <Link className="admin-secondary-action" to={`/admin/ai-scheduling${periodQuery}`}>
                    Generate another candidate
                  </Link>
                )}
              </div>

              {blockers.length > 0 ? (
                <div className="admin-readiness-list" aria-label="Blocking readiness issues">
                  {shownBlockers.map((issue, index) => {
                    const destination = readinessActionForIssue(issue, period);
                    return (
                      <div className="admin-readiness-row" key={`${issue.code}-${issue.record_id ?? index}`}>
                        <AlertCircle size={18} aria-hidden="true" />
                        <p>{issue.message}</p>
                        <Link to={destination.to}>{destination.label}<span aria-hidden="true"> →</span></Link>
                      </div>
                    );
                  })}
                  {blockers.length > shownBlockers.length && (
                    <details className="admin-more-issues">
                      <summary>Show {blockers.length - shownBlockers.length} more blockers</summary>
                      {blockers.slice(shownBlockers.length).map((issue, index) => {
                        const destination = readinessActionForIssue(issue, period);
                        return (
                          <div className="admin-readiness-row" key={`${issue.code}-${issue.record_id ?? index}`}>
                            <AlertCircle size={18} aria-hidden="true" />
                            <p>{issue.message}</p>
                            <Link to={destination.to}>{destination.label}<span aria-hidden="true"> →</span></Link>
                          </div>
                        );
                      })}
                    </details>
                  )}
                </div>
              ) : (
                <div className="admin-readiness-complete" role="status">
                  <CheckCircle2 size={19} aria-hidden="true" />
                  <span>No blocking requirements. Review any data notes before generation.</span>
                </div>
              )}
              {warnings.length > 0 && (
                <details className="admin-readiness-warnings">
                  <summary>{warnings.length} {warnings.length === 1 ? 'data note' : 'data notes'}</summary>
                  <ul>{warnings.map((issue, index) => <li key={`${issue.code}-${issue.record_id ?? index}`}>{issue.message}</li>)}</ul>
                </details>
              )}
            </section>

            <aside className="admin-command-aside" aria-label="Publication and draft activity">
              <section className="workspace-card admin-publication-card" aria-labelledby="admin-publication-title">
                <div className="admin-card-heading">
                  <div>
                    <p className="admin-card-eyebrow">Publication</p>
                    <h2 id="admin-publication-title">Published timetable</h2>
                  </div>
                  <StatusBadge tone={publicationError ? 'warning' : publication ? 'success' : 'neutral'}>
                    {publicationError
                      ? 'Unavailable'
                      : !published
                        ? 'Checking'
                        : publication
                          ? `Published · Rev ${publication.revision}`
                          : 'Unpublished'}
                  </StatusBadge>
                </div>
                <p>{selected ? periodLabel(selected) : periodLabel(currentReadiness.period)}</p>
                {publicationError ? (
                  <p className="admin-state-note" role="status">Publication status is unavailable.</p>
                ) : !published ? (
                  <p className="admin-state-note" role="status">Checking publication status…</p>
                ) : !publication ? (
                  <p className="admin-state-note">No published timetable is recorded for this period.</p>
                ) : null}
                <Link className="admin-inline-action" to={`/admin/calendar${periodQuery}`}>View timetable <span aria-hidden="true">→</span></Link>
              </section>

              <section className="workspace-card admin-activity-card" aria-labelledby="admin-activity-title">
                <div className="admin-card-heading">
                  <div>
                    <p className="admin-card-eyebrow">Recent activity</p>
                    <h2 id="admin-activity-title">Latest saved draft</h2>
                  </div>
                  <CalendarClock size={19} aria-hidden="true" />
                </div>
                {checking && !currentReadiness ? (
                  <p className="admin-state-note" role="status">Checking this period…</p>
                ) : latest ? (
                  <>
                    <p className="admin-draft-title">{latest.title}</p>
                    <p className="admin-state-note">
                      {new Date(latest.created_at).toLocaleString('en', { timeZone: 'Asia/Manila', dateStyle: 'medium', timeStyle: 'short' })}
                      {' · '}{latest.session_count} sessions
                    </p>
                    <StatusBadge tone={latest.validated === true ? 'success' : 'warning'}>
                      {latest.validated === true
                        ? `${latest.hard_conflict_count ?? 0} hard conflicts`
                        : 'Validation not confirmed'}
                    </StatusBadge>
                    <Link className="admin-inline-action" to={`/admin/schedule-manager/drafts/${encodeURIComponent(latest.id)}?source=academic`}>Open draft <span aria-hidden="true">→</span></Link>
                  </>
                ) : (
                  <p className="admin-state-note">No saved draft is recorded in the loaded results for this period.</p>
                )}
              </section>
            </aside>
          </div>
          {drafts?.has_more && (
            <p className="admin-data-note">Draft count reflects the recent results loaded here. <Link to="/admin/schedule-manager/drafts?source=academic">Open all drafts</Link>.</p>
          )}
        </>
      )}

      {!loading && !error && !period && (
        <section className="workspace-card admin-period-empty">
          <div>
            <p className="admin-card-eyebrow">Academic setup</p>
            <h2>Choose or create an academic period</h2>
            <p>Once selected, this dashboard will show saved records, readiness, and schedule activity for that period.</p>
          </div>
          <Link className="button" to="/admin/academic">Open Academic Setup</Link>
          {periods.length === 0 && <p className="admin-state-note">No periods are available yet.</p>}
        </section>
      )}

      {!loading && !error && period && !currentReadiness && (
        <div className="admin-checking-state" role="status" aria-live="polite">
          <span className="admin-inline-skeleton" aria-hidden="true" />
          <span><ClassSyncInlineSpinner />Checking academic readiness…</span>
        </div>
      )}
    </section>
  );
}
