import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { checkAcademicReadiness, createAcademicPeriod, listAcademicPeriods, loadAcademicPeriod, type AcademicKind, type AcademicPeriod, type AcademicReadiness, type AcademicSnapshot } from '../lib/academic-api';
import { academicLabel, academicPath, academicTabs } from '../lib/academic-labels';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { ReadinessSummary } from './AcademicGenerationPage';

export function AcademicManagementPage({ initialKind = 'programs' }: { initialKind?: AcademicKind }) {
  const [search, setSearch] = useSearchParams();
  const periodId = search.get('period') ?? '';
  return <ManagementContent key={`${initialKind}:${periodId}`} kind={initialKind} periodId={periodId} onPeriod={id => { const next = new URLSearchParams(search); next.set('period', id); setSearch(next); }}/>;
}

function ManagementContent({ kind, periodId, onPeriod }: { kind: AcademicKind; periodId: string; onPeriod: (id: string) => void }) {
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [snapshot, setSnapshot] = useState<AcademicSnapshot | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [includeCatalog, setIncludeCatalog] = useState(true);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [editing, setEditing] = useState<string | null>(null);
  const [checked, setChecked] = useState<AcademicReadiness | null>(null);
  const [retry, setRetry] = useState(0);
  const active = useRef(false);
  const feedback = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    Promise.all([listAcademicPeriods(), periodId ? loadAcademicPeriod(periodId) : Promise.resolve(null)])
      .then(([data, period]) => { if (!ignore) { setPeriods(data.periods); setSnapshot(period); } })
      .catch(e => { if (!ignore) setError(e.message); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [periodId, retry]);
  useEffect(() => { if (notice) feedback.current?.focus({ preventScroll: true }); }, [notice]);
  if (!schedulingSandboxEnabled) return <p>Academic data management requires verified Administrator sign-in. The unauthenticated development workspace is unavailable in this build.</p>;
  const current = academicTabs.find(t => t.kind === kind)!;
  async function create(event: FormEvent) {
    event.preventDefault(); if (active.current || !title.trim()) return;
    active.current = true; setBusy(true); setError('');
    try { const saved = await createAcademicPeriod({ title: title.trim(), include_cdm_catalog: includeCatalog }); onPeriod(saved.period.id); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save academic period.'); }
    finally { active.current = false; setBusy(false); }
  }
  async function readiness() {
    if (!snapshot || active.current) return;
    active.current = true; setBusy(true); setError('');
    try { setChecked(await checkAcademicReadiness(snapshot.period.id)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Readiness check unavailable.'); }
    finally { active.current = false; setBusy(false); }
  }
  const all = snapshot?.records.filter(e => e.record.kind === kind) ?? [];
  const matching = snapshot ? all.filter(e => academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot).toLowerCase().includes(query.toLowerCase())) : [];
  const visible = matching.slice(page * 10, page * 10 + 10);
  const editRecord = all.find(e => e.record.id === editing);
  return <div className="weekly-scheduler academic-management">
    <p className="scheduling-boundary">Development-entered data · Persisted on the server · Not verified institutional records. The synthetic test scenario stays separate.</p>
    <section className="workspace-card"><div className="academic-period-controls"><label>Academic period<select value={periodId} disabled={busy} onChange={e => onPeriod(e.target.value)}><option value="">Choose a period</option>{periods.map(p => <option value={p.id} key={p.id}>{p.title}</option>)}</select></label><Button variant="secondary" disabled={busy} onClick={() => setCreateOpen(v => !v)}>New Academic Period</Button></div>
      {loading && <p role="status">Loading academic records…</p>}
      {(createOpen || (!loading && !error && !periods.length)) && <form className="academic-create-period" onSubmit={create}>
        <h2>Create academic period</h2><label>Academic period title<input required maxLength={160} value={title} disabled={busy} onChange={e => setTitle(e.target.value)}/></label>
        <label className="academic-checkbox"><input type="checkbox" checked={includeCatalog} disabled={busy} onChange={e => setIncludeCatalog(e.target.checked)}/>Include the supplied nine-program catalog and 59 provisional CdM spaces</label>
        <p className="muted">No subjects, faculty, sections, operating hours or room capacities are invented. A catalog entry does not establish availability or curriculum.</p>
        <div className="draft-actions"><Button type="submit" disabled={busy || !title.trim()}>{busy ? 'Creating period…' : 'Create Period'}</Button><Button type="button" variant="secondary" disabled={busy} onClick={() => setCreateOpen(false)}>Cancel</Button></div>
      </form>}
    </section>
    {error && <div className="scheduler-error" role="alert"><p>{error}</p><Button variant="secondary" onClick={() => { setError(''); setLoading(true); setRetry(n => n + 1); }}>Reload academic data</Button></div>}
    {snapshot && <>
      <nav className="academic-tabs" aria-label="Academic data categories">{academicTabs.map(t => <Link key={t.kind} to={academicPath(t.kind, periodId)} aria-current={kind === t.kind ? 'page' : undefined}>{t.label}</Link>)}</nav>
      <div className="academic-review-actions"><p>{snapshot.period.title} · Source revision {snapshot.period.revision}</p><div className="draft-actions"><Button variant="secondary" disabled={busy} onClick={readiness}>{busy ? 'Checking inputs…' : 'Validate Readiness'}</Button><Link className="text-action" to={`/admin/schedule-manager/create?source=academic&period=${encodeURIComponent(periodId)}`}>Generate from this period</Link></div></div>
      {checked && <ReadinessSummary checked={checked}/>}
      {editing !== null ? <AcademicRecordEditor key={`${periodId}:${kind}:${editing}`} kind={kind} snapshot={snapshot} existing={editRecord} onCancel={() => setEditing(null)} onReload={() => { setEditing(null); setSnapshot(null); setLoading(true); setError(''); setRetry(n => n + 1); }} onSaved={next => { setSnapshot(next); setEditing(null); setChecked(null); setNotice('Academic record saved. Existing drafts are unchanged.'); }}/>
        : <section className="academic-records" aria-label={`${current.label} records`}>
          <div className="academic-list-toolbar"><label>Search {current.label.toLowerCase()}<input type="search" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }}/></label><Button onClick={() => { setEditing(kind === 'constraints' ? 'rules' : 'new'); setNotice(''); }}>{kind === 'constraints' ? 'Edit Scheduling Constraints' : `Add ${kind === 'faculty' ? 'Faculty' : kind === 'offerings' ? 'Subject Offering' : kind === 'resources' ? 'Resource' : current.label.replace(/s$/, '')}`}</Button></div>
          {!matching.length && <p>No {current.label.toLowerCase()} {query ? 'match this search.' : 'saved for this period. Add the records required by the intended timetable.'}</p>}
          <ul className="academic-record-list">{visible.map(e => <li key={e.record.id} className="workspace-card academic-record-row"><div><h2>{academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot)}</h2>
            {e.record.kind === 'subjects' && <p>{e.record.required_weekly_minutes ?? 'Missing'} weekly contact minutes · {e.record.patterns?.length ?? 0} allowed patterns</p>}
            {e.record.kind === 'faculty' && <p>{e.record.subject_ids?.length ?? 0} eligible subjects · {e.record.availability?.length ?? 0} availability windows</p>}
            {e.record.kind === 'resources' && <p>{e.record.condition === 'operational' && e.record.schedulable ? 'Operational metadata entered' : 'Not verified for scheduling'} · {e.record.capacity_verified ? `${e.record.capacity} verified capacity` : 'Capacity unverified'}</p>}
            {e.record.kind === 'offerings' && <p>{e.record.teacher_ids?.length ?? 0} assigned/eligible faculty · {e.record.room_ids?.length ?? 0} eligible classrooms</p>}
            {e.record.kind === 'constraints' && <p>{e.record.operating_windows?.length ?? 0} permitted operating windows</p>}
          </div><div className="draft-actions"><StatusBadge tone={'active' in e.record && e.record.active === false ? 'warning' : 'neutral'}>{'active' in e.record && e.record.active === false ? 'Inactive' : 'Saved'}</StatusBadge><Button variant="secondary" onClick={() => { setEditing(e.record.id!); setNotice(''); }} aria-label={`Edit ${academicLabel(e.record as Parameters<typeof academicLabel>[0], snapshot)}`}>Edit</Button></div></li>)}</ul>
          {matching.length > 10 && <nav className="draft-actions" aria-label="Academic record pagination"><Button variant="secondary" disabled={!page} onClick={() => setPage(n => n - 1)}>Previous</Button><span>{page * 10 + 1}–{Math.min(page * 10 + 10, matching.length)} of {matching.length}</span><Button variant="secondary" disabled={(page + 1) * 10 >= matching.length} onClick={() => setPage(n => n + 1)}>Next</Button></nav>}
        </section>}
      <p role="status" tabIndex={-1} ref={feedback}>{notice}</p>
    </>}
  </div>;
}
