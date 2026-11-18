import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  checkAcademicReadiness,
  createAcademicPeriod,
  listAcademicPeriods,
  loadAcademicPeriod,
  type AcademicKind,
  type AcademicPeriod,
  type AcademicReadiness,
  type AcademicSnapshot,
} from '../lib/academic-api';
import { academicLabel, academicPath, academicTabs } from '../lib/academic-labels';
import { appMode } from '../config/runtime-config';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { ReadinessSummary } from './AcademicGenerationPage';
import { AcademicFixtureImport } from './AcademicFixtureImport';
import { periodLabel } from '../lib/workspace-context';
import { AcademicCalendarEditor } from './AcademicCalendarEditor';
import { AcademicPeriodSetup } from './AcademicPeriodSetup';
const schedulingSandboxEnabled = appMode !== 'presentation';

export function AcademicManagementPage({
  initialKind = 'programs',
}: {
  initialKind?: AcademicKind;
}) {
  const [search, setSearch] = useSearchParams();
  const periodId = search.get('period') ?? '';
  return (
    <ManagementContent
      key={`${initialKind}:${periodId}`}
      kind={initialKind}
      periodId={periodId}
      onPeriod={(id) => {
        const next = new URLSearchParams(search);
        next.set('period', id);
        setSearch(next);
      }}
    />
  );
}

function ManagementContent({
  kind,
  periodId,
  onPeriod,
}: {
  kind: AcademicKind;
  periodId: string;
  onPeriod: (id: string) => void;
}) {
  const location = useLocation();
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [snapshot, setSnapshot] = useState<AcademicSnapshot | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [includeCatalog, setIncludeCatalog] = useState(true);
  const [recordFilter, setRecordFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [editingKind, setEditingKind] = useState<AcademicKind>(kind);
  const [checked, setChecked] = useState<AcademicReadiness | null>(null);
  const [retry, setRetry] = useState(0);
  const active = useRef(false);
  const feedback = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    Promise.all([
      listAcademicPeriods(),
      periodId ? loadAcademicPeriod(periodId) : Promise.resolve(null),
    ])
      .then(([data, period]) => {
        if (!ignore) {
          setPeriods(data.periods);
          setSnapshot(period);
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
  }, [periodId, retry]);
  useEffect(() => {
    if (notice) feedback.current?.focus({ preventScroll: true });
  }, [notice]);
  if (!schedulingSandboxEnabled)
    return (
      <p>
        Academic data management requires verified Administrator sign-in. The unauthenticated
        development workspace is unavailable in this build.
      </p>
    );
  const current = academicTabs.find((t) => t.kind === kind)!;
  const setupLanding = location.pathname === '/admin/academic';
  async function create(event: FormEvent) {
    event.preventDefault();
    if (active.current || !title.trim()) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      const saved = await createAcademicPeriod({
        title: title.trim(),
        include_cdm_catalog: includeCatalog,
      });
      onPeriod(saved.period.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save academic period.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  async function readiness() {
    if (!snapshot || active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      setChecked(await checkAcademicReadiness(snapshot.period.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Readiness check unavailable.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  const all = snapshot?.records.filter((e) => e.record.kind === kind) ?? [];
  const matching = snapshot
    ? all.filter((e) => {
        const inactive = 'active' in e.record && e.record.active === false;
        return recordFilter === 'all' || (recordFilter === 'inactive' ? inactive : !inactive);
      })
    : [];
  const visible = matching.slice(page * 10, page * 10 + 10);
  const editRecord = snapshot?.records.find(
    (e) => e.record.kind === editingKind && e.record.id === editing,
  );
  const hasSelectedPeriod = Boolean(periodId && periods.some((period) => period.id === periodId));
  return (
    <div className="weekly-scheduler academic-management">
      <p className="academic-workspace-note">
        <strong>
          {appMode === 'institutional' ? 'Institutional workspace' : 'Development sandbox'}
        </strong>
        <span>
          {appMode === 'institutional'
            ? 'Connected academic records · source and revision are shown for each period'
            : 'Server-saved workspace · not verified institutional records'}
        </span>
      </p>
      {snapshot && !setupLanding && (
        <AcademicCalendarEditor
          key={snapshot.period.revision}
          snapshot={snapshot}
          onSaved={(saved) => {
            setSnapshot(saved);
            setChecked(null);
            setNotice('Academic calendar saved. Recheck scheduling readiness before generation.');
          }}
        />
      )}
      <section className="workspace-card">
        {!hasSelectedPeriod && (
          <div className="academic-start">
            <div className="academic-start__intro">
              <p className="academic-setup__eyebrow">Academic setup</p>
              <h2>
                {periods.length
                  ? 'Choose a period to continue'
                  : 'Create your first academic period'}
              </h2>
              <p>
                Academic data is grouped by period so the calendar, curriculum, sections, faculty,
                rooms and scheduling rules stay together. You can save setup in stages.
              </p>
            </div>
            <div className="academic-start__controls">
              <label>
                Academic period
                <select
                  value={periodId}
                  disabled={busy || periods.length === 0}
                  onChange={(e) => onPeriod(e.target.value)}
                >
                  <option value="">
                    {periods.length ? 'Choose a period' : 'No periods saved yet'}
                  </option>
                  {periods.map((p) => (
                    <option value={p.id} key={p.id}>
                      {periodLabel(p)}
                    </option>
                  ))}
                </select>
              </label>
              {periods.length > 0 && (
                <Button disabled={busy} onClick={() => setCreateOpen((v) => !v)}>
                  New academic period
                </Button>
              )}
            </div>
            <section
              className="academic-start__checklist"
              aria-labelledby="academic-start-checklist"
            >
              <h3 id="academic-start-checklist">What you’ll set up in one workspace</h3>
              <ul>
                <li>
                  <strong>Calendar</strong>
                  <span>Approved dates and instructional days</span>
                </li>
                <li>
                  <strong>Programs, subjects and sections</strong>
                  <span>Supplied catalogs and confirmed cohort records</span>
                </li>
                <li>
                  <strong>Faculty and availability</strong>
                  <span>Assigned subjects, windows and workload limits</span>
                </li>
                <li>
                  <strong>Offerings and rooms</strong>
                  <span>Confirmed classes and verified room suitability</span>
                </li>
                <li>
                  <strong>Scheduling rules</strong>
                  <span>Teaching windows, shared scope and fixed commitments</span>
                </li>
              </ul>
              <p>
                Readiness is checked from saved records; this overview does not assume any item is
                complete.
              </p>
            </section>
          </div>
        )}
        {hasSelectedPeriod && (
          <div className="academic-period-controls">
            <label>
              Academic period
              <select value={periodId} disabled={busy} onChange={(e) => onPeriod(e.target.value)}>
                <option value="">Choose a period</option>
                {periods.map((p) => (
                  <option value={p.id} key={p.id}>
                    {periodLabel(p)}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="secondary" disabled={busy} onClick={() => setCreateOpen((v) => !v)}>
              New academic period
            </Button>
          </div>
        )}
        {loading && <p role="status">Loading academic records…</p>}
        {(createOpen || (!loading && !error && !periods.length)) && (
          <form className="academic-create-period" onSubmit={create}>
            <h2>Create academic period</h2>
            <label>
              Academic period title
              <input
                required
                maxLength={160}
                value={title}
                disabled={busy}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="academic-checkbox">
              <input
                type="checkbox"
                checked={includeCatalog}
                disabled={busy}
                onChange={(e) => setIncludeCatalog(e.target.checked)}
              />
              Include the supplied nine-program catalog and 53 row-classified CdM spaces
            </label>
            <p className="muted">
              No subjects, faculty, sections, operating hours or room capacities are invented. A
              catalog entry does not establish availability or curriculum.
            </p>
            <div className="draft-actions">
              <Button type="submit" disabled={busy || !title.trim()}>
                {busy ? 'Creating period…' : 'Create Period'}
              </Button>
              {periods.length > 0 && (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </Button>
              )}
            </div>
          </form>
        )}
      </section>
      {error && (
        <div className="scheduler-error" role="alert">
          <p>{error}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setError('');
              setLoading(true);
              setRetry((n) => n + 1);
            }}
          >
            Reload academic data
          </Button>
        </div>
      )}
      {snapshot && (
        <>
          {!setupLanding && (
            <nav className="academic-tabs" aria-label="Academic data categories">
              <Link to={academicPath('programs', periodId)}>Setup overview</Link>
              {academicTabs.map((t) => (
                <Link
                  key={t.kind}
                  to={academicPath(t.kind, periodId)}
                  aria-current={kind === t.kind ? 'page' : undefined}
                >
                  {t.label}
                </Link>
              ))}
            </nav>
          )}
          <div className="academic-review-actions">
            <p>
              {periodLabel(snapshot.period)} · Source revision {snapshot.period.revision}
            </p>
            <div className="draft-actions">
              <Button variant="secondary" disabled={busy} onClick={readiness}>
                {busy ? 'Checking inputs…' : 'Validate Readiness'}
              </Button>
              <Link
                className="button button--secondary"
                to={`/admin/schedule-manager/create?source=academic&period=${encodeURIComponent(periodId)}`}
              >
                Generate from this period
              </Link>
            </div>
          </div>
          {checked && <ReadinessSummary checked={checked} />}
          {setupLanding ? (
            <AcademicPeriodSetup
              snapshot={snapshot}
              editing={editing}
              editingKind={editingKind}
              onEdit={(nextKind, id) => {
                setEditingKind(nextKind);
                setEditing(id);
                setNotice('');
              }}
              onCancel={() => setEditing(null)}
              onReload={() => {
                setEditing(null);
                setSnapshot(null);
                setLoading(true);
                setError('');
                setRetry((n) => n + 1);
              }}
              onSaved={(next) => {
                setSnapshot(next);
                setEditing(null);
                setChecked(null);
                setNotice('Academic record saved. Existing drafts are unchanged.');
              }}
            />
          ) : editing !== null ? (
            <AcademicRecordEditor
              key={`${periodId}:${editingKind}:${editing}`}
              kind={editingKind}
              snapshot={snapshot}
              existing={editRecord}
              onCancel={() => setEditing(null)}
              onReload={() => {
                setEditing(null);
                setSnapshot(null);
                setLoading(true);
                setError('');
                setRetry((n) => n + 1);
              }}
              onSaved={(next) => {
                setSnapshot(next);
                setEditing(null);
                setChecked(null);
                setNotice('Academic record saved. Existing drafts are unchanged.');
              }}
            />
          ) : (
            <section className="academic-records" aria-label={`${current.label} records`}>
              <div className="academic-list-toolbar">
                <label>
                  Record status
                  <select value={recordFilter} onChange={(e) => { setRecordFilter(e.target.value as typeof recordFilter); setPage(0); }}>
                    <option value="all">All records</option>
                    <option value="active">Active records</option>
                    <option value="inactive">Inactive records</option>
                  </select>
                </label>
                <Button
                  onClick={() => {
                    setEditingKind(kind);
                    setEditing(kind === 'constraints' ? 'rules' : 'new');
                    setNotice('');
                  }}
                >
                  {kind === 'constraints'
                    ? 'Edit Scheduling Constraints'
                    : `Add ${kind === 'faculty' ? 'Faculty' : kind === 'offerings' ? 'Subject Offering' : kind === 'resources' ? 'Resource' : current.label.replace(/s$/, '')}`}
                </Button>
              </div>
              {!matching.length && (
                <p>
                  No {current.label.toLowerCase()}{' '}
                  {recordFilter !== 'all'
                    ? 'match this status.'
                    : 'saved for this period. Add the records required by the intended timetable.'}
                </p>
              )}
              <ul className="academic-record-list">
                {visible.map((e) => (
                  <li key={e.record.id} className="workspace-card academic-record-row">
                    <div>
                      <h2>
                        {academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot)}
                      </h2>
                      {e.record.kind === 'subjects' && (
                        <p>
                          {e.record.required_weekly_minutes ?? 'Missing'} weekly contact minutes ·{' '}
                          {e.record.patterns?.length ?? 0} allowed patterns
                        </p>
                      )}
                      {e.record.kind === 'faculty' && (
                        <p>
                          {e.record.subject_ids?.length ?? 0} eligible subjects ·{' '}
                          {e.record.availability?.length ?? 0} availability windows
                        </p>
                      )}
                      {e.record.kind === 'resources' && (
                        <p>
                          {e.record.condition === 'operational' && e.record.schedulable
                            ? 'Operational metadata entered'
                            : 'Not verified for scheduling'}{' '}
                          ·{' '}
                          {e.record.capacity_verified
                            ? `${e.record.capacity} verified capacity`
                            : 'Capacity unverified'}
                        </p>
                      )}
                      {e.record.kind === 'offerings' && (
                        <p>
                          {e.record.teacher_ids?.length ?? 0} assigned/eligible faculty ·{' '}
                          {e.record.room_ids?.length ?? 0} eligible classrooms
                        </p>
                      )}
                      {e.record.kind === 'constraints' && (
                        <p>{e.record.operating_windows?.length ?? 0} permitted operating windows</p>
                      )}
                    </div>
                    <div className="draft-actions">
                      <StatusBadge
                        tone={
                          'active' in e.record && e.record.active === false ? 'warning' : 'neutral'
                        }
                      >
                        {'active' in e.record && e.record.active === false ? 'Inactive' : 'Saved'}
                      </StatusBadge>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setEditingKind(kind);
                          setEditing(e.record.id!);
                          setNotice('');
                        }}
                        aria-label={`Edit ${academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot)}`}
                      >
                        Edit
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
              {matching.length > 10 && (
                <nav className="draft-actions" aria-label="Academic record pagination">
                  <Button
                    variant="secondary"
                    disabled={!page}
                    onClick={() => setPage((n) => n - 1)}
                  >
                    Previous
                  </Button>
                  <span>
                    {page * 10 + 1}–{Math.min(page * 10 + 10, matching.length)} of {matching.length}
                  </span>
                  <Button
                    variant="secondary"
                    disabled={(page + 1) * 10 >= matching.length}
                    onClick={() => setPage((n) => n + 1)}
                  >
                    Next
                  </Button>
                </nav>
              )}
            </section>
          )}
          <p role="status" tabIndex={-1} ref={feedback}>
            {notice}
          </p>
        </>
      )}
      {setupLanding && appMode === 'sandbox' && (
        <section className="academic-dev-tools" id="sample-scenario" aria-label="Development tools">
          <p className="academic-setup__eyebrow">Development tools</p>
          <AcademicFixtureImport />
        </section>
      )}
    </div>
  );
}
