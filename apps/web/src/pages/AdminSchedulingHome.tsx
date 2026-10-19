import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  checkAcademicReadiness,
  listAcademicPeriods,
  type AcademicReadiness,
} from '../lib/academic-api';
import {
  listSchedulingDrafts,
  schedulingSandboxEnabled,
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
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';

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
    [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!schedulingSandboxEnabled) {
      setLoading(false);
      return;
    }
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
    if (!period || !schedulingSandboxEnabled) return;
    let ignore = false;
    setChecked(undefined);
    setError('');
    setPublished(undefined);
    setPublicationError(false);
    rememberWorkspace('administrator', { ...readWorkspace('administrator'), period });
    checkAcademicReadiness(period)
      .then((v) => {
        if (!ignore) setChecked(v);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    timetableRequest<{ periods: WorkspacePeriod[] }>('sandbox/periods')
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
  const selected = periods.find((p) => p.id === period),
    latest = drafts?.drafts.find((d) => d.period_id === period);
  const currentDraft =
    latest?.data_version === `academic:${period}:revision:${checked?.period.revision}` &&
    latest.validated;
  const action = !period
    ? { label: 'Set up academic data', to: '/admin/academic' }
    : !checked?.ready
      ? {
          label: 'Review Requirements',
          to: `/admin/ai-scheduling?period=${encodeURIComponent(period)}`,
        }
      : currentDraft
        ? {
            label: 'Review Timetable',
            to: `/admin/schedule-manager/drafts/${latest!.id}?source=academic`,
          }
        : {
            label: 'Generate Weekly Schedule',
            to: `/admin/ai-scheduling?period=${encodeURIComponent(period)}`,
          };
  const issues = checked?.issues.filter((i) => i.severity === 'blocking').slice(0, 3) ?? [];
  const publication = published?.find((p) => p.id === period && (p.revision ?? 0) > 0);
  if (!schedulingSandboxEnabled)
    return (
      <section className="workspace-card">
        <h1>Scheduling overview</h1>
        <p>
          The connected scheduling workspace requires verified Administrator access. This preview
          does not grant backend permissions.
        </p>
      </section>
    );
  return (
    <section className="admin-overview">
      <div className="ux-section-heading">
        <h1>Scheduling overview</h1>
        <span className="source-label">Local academic sandbox</span>
      </div>
      <label className="admin-period-selector">
        Academic period
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="">Choose a period</option>
          {periods.map((p) => (
            <option value={p.id} key={p.id}>
              {periodLabel(p)}
            </option>
          ))}
        </select>
      </label>
      {loading && <p role="status">Loading scheduling context…</p>}
      {error && (
        <div role="alert" className="workspace-card">
          <h2>Scheduling status unavailable</h2>
          <p>{error}</p>
          <Button variant="secondary" onClick={() => setRetry((n) => n + 1)}>
            Retry
          </Button>
        </div>
      )}
      <div className="admin-overview-content">
        {!loading && !error && (!period || checked) && (
          <article className="workspace-card admin-next-step">
            <StatusBadge tone={checked?.ready ? 'success' : 'warning'}>
              {checked
                ? checked.ready
                  ? 'Ready to generate'
                  : 'Requirements need attention'
                : 'Setup required'}
            </StatusBadge>
            <h2>{action.label}</h2>
            <p>
              {selected ? periodLabel(selected) : 'Choose or create an academic period to begin.'}
            </p>
            <Link className="button" to={action.to}>
              {action.label}
            </Link>
            {currentDraft && (
              <Link
                className="button button--secondary"
                to={`/admin/ai-scheduling?period=${period}`}
              >
                Generate another candidate
              </Link>
            )}
          </article>
        )}
        {period && !checked && !error && !loading && (
          <p role="status">Checking academic readiness…</p>
        )}
        {issues.length > 0 && (
          <section className="workspace-card admin-attention">
            <h2>Needs attention</h2>
            <ul>
              {issues.map((i, n) => (
                <li key={n}>
                  <p>{i.message}</p>
                  <Link
                    className="button button--secondary"
                    to={`/admin/ai-scheduling?period=${period}#readiness-issues`}
                  >
                    Review requirement
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
        {checked && (
          <section className="workspace-card admin-status">
            <h2>Academic scope</h2>
            <dl className="admin-status-list">
              <div>
                <dt>Active sections</dt>
                <dd>{checked.sections}</dd>
              </div>
              <div>
                <dt>Subject offerings</dt>
                <dd>{checked.offerings}</dd>
              </div>
              <div>
                <dt>Classroom candidates</dt>
                <dd>{checked.eligible_resources}</dd>
              </div>
              <div>
                <dt>{drafts?.has_more ? 'Recent matching drafts' : 'Saved drafts'}</dt>
                <dd>{drafts?.drafts.filter((d) => d.period_id === period).length ?? 0}</dd>
              </div>
            </dl>
            <p className="muted">Room candidates still require per-offering suitability checks.</p>
            <p>
              {publicationError
                ? 'Publication status unavailable'
                : !published
                  ? 'Checking publication…'
                  : publication
                    ? `Published sample revision ${publication.revision}`
                    : 'No published version for this period'}
            </p>
          </section>
        )}
        {drafts && !error && (
          <section className="workspace-card admin-activity">
            <h2>Recent scheduling activity</h2>
            {latest ? (
              <>
                <p className="source-label">Latest saved draft · Unpublished</p>
                <h3>{latest.title}</h3>
                <p>
                  {new Date(latest.created_at).toLocaleString('en', {
                    timeZone: 'Asia/Manila',
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}{' '}
                  · {latest.session_count} sessions
                </p>
                <p>
                  {latest.validated
                    ? `Snapshot validated · ${latest.hard_conflict_count} hard conflicts`
                    : 'Validation unavailable'}
                </p>
                <Link
                  className="button button--secondary"
                  to={`/admin/schedule-manager/drafts/${latest.id}?source=academic`}
                >
                  Open saved draft
                </Link>
              </>
            ) : (
              <p>No saved draft recorded for this selected period.</p>
            )}
          </section>
        )}
      </div>
      <nav className="admin-tool-links" aria-label="Scheduling tools">
        <Link className="button button--secondary" to="/admin/academic">
          Academic Setup
        </Link>
        <Link
          className="button button--secondary"
          to="/admin/schedule-manager/drafts?source=academic"
        >
          Saved Drafts
        </Link>
        <Link className="button button--secondary" to="/admin/calendar">
          Published Timetables
        </Link>
        <Link className="button button--secondary" to="/admin/conflicts">
          Conflict Center
        </Link>
      </nav>
    </section>
  );
}
