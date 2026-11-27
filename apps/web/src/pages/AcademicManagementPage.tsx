import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  checkAcademicReadiness,
  createAcademicPeriod,
  deleteAcademicRecord,
  listAcademicPeriods,
  loadAcademicPeriod,
  saveAcademicRecord,
  type AcademicKind,
  type AcademicPeriod,
  type AcademicReadiness,
  type AcademicRecord,
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
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';
import { INSTITUTES, programScope, type ScopedRecord } from '../lib/program-scope';
const schedulingSandboxEnabled = appMode !== 'presentation';

export function AcademicManagementPage({
  initialKind = 'programs',
}: {
  initialKind?: AcademicKind;
}) {
  const [search, setSearch] = useSearchParams();
  const periodId = search.get('period') ?? '';
  const changePeriod = useCallback((id: string) => {
    setSearch((current) => {
      const next = new URLSearchParams(current);
      if (id) next.set('period', id);
      else next.delete('period');
      return next;
    });
  }, [setSearch]);
  return (
    <ManagementContent
      key={initialKind}
      kind={initialKind}
      periodId={periodId}
      onPeriod={changePeriod}
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
  const [title, setTitle] = useState('AY 2026-2027 · 1st Semester');
  const [includeCatalog, setIncludeCatalog] = useState(true);
  const [recordFilter, setRecordFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [recordSearch, setRecordSearch] = useState('');
  const [yearFilter, setYearFilter] = useState<'all' | '1' | '2' | '3' | '4'>('all');
  const [sectionFilter, setSectionFilter] = useState('all');
  const [instituteFilter, setInstituteFilter] = useState('all');
  const [programFilter, setProgramFilter] = useState('all');
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
    setLoading(true);
    setError('');
    const periodsRequest = listAcademicPeriods()
      .then((data) => {
        if (!ignore) {
          setPeriods(data.periods);
          if (periodId && !data.periods.some((period) => period.id === periodId)) {
            onPeriod(data.periods[0]?.id ?? '');
          }
        }
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    const selectedPeriodRequest = periodId
      ? loadAcademicPeriod(periodId)
          .then((period) => {
            if (!ignore) {
              setSnapshot(period);
              setError('');
            }
          })
          .catch((e) => {
            if (!ignore) {
              setSnapshot(null);
              setError(e instanceof Error ? e.message : 'Academic period could not be loaded.');
            }
          })
      : Promise.resolve().then(() => {
          if (!ignore) setSnapshot(null);
        });
    void Promise.all([periodsRequest, selectedPeriodRequest]).finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [periodId, retry, onPeriod]);
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
  const setupLanding = location.pathname === '/admin/academic' || location.pathname === '/admin/dashboard';
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
  async function removeRecord(entry: AcademicSnapshot['records'][number]) {
    if (!snapshot || active.current) return;
    const label = academicLabel(entry.record as AcademicRecord, snapshot);
    if (!window.confirm(`Delete ${label}? Records that still reference it must be updated first.`)) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      setSnapshot(await deleteAcademicRecord(snapshot.period.id, kind, entry.record.id ?? '', entry.revision));
      setChecked(null);
      setNotice(`${label} deleted.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Record could not be deleted.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  const all = snapshot?.records.filter((e) => e.record.kind === kind) ?? [];
  const sections = (snapshot?.records ?? []).flatMap((entry) =>
    entry.record.kind === 'sections' ? [entry.record as AcademicRecord] : [],
  );
  const scope = programScope((snapshot?.records ?? []).map((entry) => entry.record as unknown as ScopedRecord));
  const scopedKinds = ['subjects', 'sections', 'faculty', 'offerings'];
  const programChoices = scope.programs.filter((p) => instituteFilter === 'all' || p.institute === instituteFilter);
  const matching = snapshot
    ? all.filter((e) => {
        const record = e.record;
        if (scopedKinds.includes(kind) && !scope.matches(record as unknown as ScopedRecord, instituteFilter, programFilter)) return false;
        const inactive = 'active' in record && record.active === false;
        if (recordFilter !== 'all' && (recordFilter === 'inactive' ? !inactive : inactive)) return false;
        const searchText = `${academicLabel(record as Parameters<typeof academicLabel>[0], snapshot)} ${JSON.stringify(record)}`.toLowerCase();
        if (recordSearch.trim() && !searchText.includes(recordSearch.trim().toLowerCase())) return false;
        const relatedSection = record.kind === 'offerings'
          ? sections.find((section) => section.kind === 'sections' && section.id === record.section_id)
          : record.kind === 'sections' ? record : undefined;
        const year = record.kind === 'subjects' ? record.year_level : relatedSection?.kind === 'sections' ? relatedSection.year_level : undefined;
        if (yearFilter !== 'all' && year !== Number(yearFilter)) return false;
        if (sectionFilter !== 'all' && (record.kind !== 'offerings' || record.section_id !== sectionFilter)) return false;
        return true;
      })
    : [];
  const schedulableCatalogIds = new Set(provisionalCdmRooms.filter((room) => room.schedulable).map((room) => room.id));
  const excludedCatalogIds = new Set(provisionalCdmRooms.filter((room) => !room.schedulable).map((room) => room.id));
  const schedulableRooms = all.filter((entry) => entry.record.kind === 'resources' && schedulableCatalogIds.has(entry.record.id) && entry.record.schedulable);
  const verifiedRooms = schedulableRooms.filter((entry) => entry.record.kind === 'resources' && entry.record.condition === 'operational' && entry.record.type_verified && entry.record.capacity_verified && entry.record.availability_verified).length;
  const excludedRooms = all.filter((entry) => entry.record.kind === 'resources' && excludedCatalogIds.has(entry.record.id));
  const roomsNeedingVerification = schedulableRooms.filter((entry) => entry.record.kind === 'resources' && entry.record.condition !== 'maintenance' && !(entry.record.condition === 'operational' && entry.record.type_verified && entry.record.capacity_verified && entry.record.availability_verified));
  const visible = matching.slice(page * 20, page * 20 + 20);
  const editRecord = snapshot?.records.find(
    (e) => e.record.kind === editingKind && e.record.id === editing,
  );
  const hasSelectedPeriod = Boolean(periodId && periods.some((period) => period.id === periodId));
  async function verifySchedulableRooms() {
    if (!snapshot || active.current || !roomsNeedingVerification.length) return;
    const summary = `${roomsNeedingVerification.length} schedulable rooms will receive editable capacity and availability defaults. ${excludedRooms.length} excluded spaces will be preserved.`;
    if (!window.confirm(summary)) return;
    active.current = true;
    setBusy(true);
    setError('');
    let currentSnapshot = snapshot;
    try {
      for (const entry of roomsNeedingVerification) {
        if (entry.record.kind !== 'resources' || !entry.record.schedulable) continue;
        const room = entry.record;
        const type = room.room_type ?? (room.allowed_activity_types?.includes('sports') || room.allowed_activity_types?.includes('pahfit') ? 'athletic_space' : room.name.toLowerCase().includes('lab') || room.name.toLowerCase().startsWith('cl-') ? 'computer_lab' : 'lecture_classroom');
        const capacity = type === 'computer_lab' ? 40 : type === 'athletic_space' || type === 'special_activity' ? 60 : 45;
        const next = {
          ...room,
          room_type: type,
          capacity: room.capacity ?? capacity,
          condition: 'operational' as const,
          schedulable: true,
          type_verified: true,
          capacity_verified: true,
          availability: room.availability?.length ? room.availability : [0, 1, 2, 3, 4, 5].map((day) => ({ day, start: 420, end: 1260 })),
          availability_verified: true,
          verification_note: room.verification_note || 'Owner-authorized defense dataset defaults; administrator review remains available.',
        };
        currentSnapshot = await saveAcademicRecord(snapshot.period.id, {
          expected_revision: currentSnapshot.records.find((candidate) => candidate.record.kind === 'resources' && candidate.record.id === room.id)?.revision ?? entry.revision,
          record: next,
        });
        setSnapshot(currentSnapshot);
      }
      setChecked(null);
      const ready = currentSnapshot.records.filter((entry) => entry.record.kind === 'resources' && schedulableCatalogIds.has(entry.record.id) && entry.record.schedulable && entry.record.condition === 'operational' && entry.record.type_verified && entry.record.capacity_verified && entry.record.availability_verified).length;
      setNotice(`${ready}/${schedulableRooms.length} schedulable rooms ready · ${excludedRooms.length} excluded spaces preserved`);
    } catch (e) {
      setSnapshot(currentSnapshot);
      setError(e instanceof Error ? e.message : 'Room verification stopped. Successfully saved changes are shown.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
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
              {!createOpen && !periods.length && !loading && !error && (
                <Button disabled={busy} onClick={() => setCreateOpen(true)}>
                  Create Academic Period
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
        {loading && <ClassSyncSkeleton label="Loading academic records" />}
        {createOpen && (
          <form className="academic-create-period" onSubmit={create}>
            <h2>Create academic period</h2>
            <label>
              Academic period title <span className="academic-field-indicator" aria-hidden="true">Required</span>
              <input
                required
                maxLength={160}
                placeholder="AY 2026-2027 · 1st Semester"
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
              Include the supplied program and room catalog <span className="academic-field-indicator" aria-hidden="true">Optional</span>
            </label>
            <p className="muted">
              No subjects, faculty, sections, operating hours or room capacities are invented. A
              catalog entry does not establish availability or curriculum.
            </p>
            <div className="draft-actions">
              <Button type="submit" disabled={busy || !title.trim()} loading={busy}>
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
              <Button variant="secondary" disabled={busy} loading={busy} onClick={readiness}>
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
              readiness={checked}
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
                  Search records
                  <input type="search" value={recordSearch} placeholder={`Search ${current.label.toLowerCase()}`} onChange={(e) => { setRecordSearch(e.target.value); setPage(0); }} />
                </label>
                {scopedKinds.includes(kind) && <>
                  <label>
                    Institute
                    <select value={instituteFilter} onChange={(e) => { setInstituteFilter(e.target.value); setProgramFilter('all'); setPage(0); }}>
                      <option value="all">All institutes</option>
                      {INSTITUTES.map((code) => <option key={code} value={code}>{code}</option>)}
                    </select>
                  </label>
                  <label>
                    Program
                    <select value={programFilter} onChange={(e) => { setProgramFilter(e.target.value); setPage(0); }}>
                      <option value="all">All programs</option>
                      {programChoices.map((p) => <option key={p.id} value={p.id}>{p.acronym}</option>)}
                    </select>
                  </label>
                </>}
                {['subjects', 'sections', 'offerings'].includes(kind) && (
                  <label>
                    Year level
                    <select value={yearFilter} onChange={(e) => { setYearFilter(e.target.value as typeof yearFilter); setPage(0); }}>
                      <option value="all">All years</option>
                      {[1, 2, 3, 4].map((year) => <option key={year} value={year}>{year}{year === 1 ? 'st' : year === 2 ? 'nd' : year === 3 ? 'rd' : 'th'} Year</option>)}
                    </select>
                  </label>
                )}
                {kind === 'offerings' && (
                  <label>
                    Section
                    <select value={sectionFilter} onChange={(e) => { setSectionFilter(e.target.value); setPage(0); }}>
                      <option value="all">All sections</option>
                      {sections.map((section) => section.kind === 'sections' && <option key={section.id} value={section.id}>{academicLabel(section, snapshot!)}</option>)}
                    </select>
                  </label>
                )}
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
                {kind === 'resources' && <>
                  <p role="status" className="academic-record-summary">{verifiedRooms}/{schedulableRooms.length} schedulable rooms ready · {excludedRooms.length} excluded spaces preserved</p>
                  <Button type="button" variant="secondary" disabled={busy || roomsNeedingVerification.length === 0} loading={busy} onClick={verifySchedulableRooms}>Verify Schedulable Rooms</Button>
                </>}
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
                      <Button
                        variant="danger"
                        disabled={busy}
                        onClick={() => void removeRecord(e)}
                        aria-label={`Delete ${academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot)}`}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
              {matching.length > 20 && (
                <nav className="draft-actions" aria-label="Academic record pagination">
                  <Button
                    variant="secondary"
                    disabled={!page}
                    onClick={() => setPage((n) => n - 1)}
                  >
                    Previous
                  </Button>
                    <span>
                    {page * 20 + 1}–{Math.min(page * 20 + 20, matching.length)} of {matching.length}
                  </span>
                  <Button
                    variant="secondary"
                    disabled={(page + 1) * 20 >= matching.length}
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
