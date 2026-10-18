import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { checkAcademicReadiness, generateAcademicSchedule, listAcademicPeriods, type AcademicReadiness, type AcademicPeriod } from '../lib/academic-api';
import { schedulingSandboxEnabled, type GenerationResult } from '../lib/scheduling-api';
import { SaveDraftPanel } from './SchedulingDraftPages';
import { SchedulingTimetable } from './SchedulingTimetable';
import { WeeklySchedulingPage } from './WeeklySchedulingPage';

export function SchedulingSourcePage() {
  const [search, setSearch] = useSearchParams();
  const source = search.get('source') === 'synthetic' ? 'synthetic' : 'academic';
  return <div className="weekly-scheduler">
    <label>Scheduling source<select value={source} onChange={e => { const next = new URLSearchParams(search); next.set('source', e.target.value); setSearch(next); }}>
      <option value="academic">Saved academic period — user-entered inputs</option>
      <option value="synthetic">Synthetic development test scenario</option>
    </select></label>
    {source === 'synthetic' ? <WeeklySchedulingPage/> : <AcademicGenerationPage key={search.get('period') ?? 'none'}/>}
  </div>;
}

export function ReadinessSummary({ checked }: { checked: AcademicReadiness }) {
  return <section className="workspace-card academic-readiness" aria-label="Academic readiness">
    <h2>Scheduling readiness</h2>
    <StatusBadge tone={checked.ready ? 'success' : 'warning'}>{checked.ready ? 'Ready for generation' : 'Missing required inputs'}</StatusBadge>
    <p>{checked.programs} programs · {checked.sections} sections · {checked.offerings} offerings · {checked.faculty} faculty · {checked.eligible_resources} resources marked operational</p>
    <p>Source revision {checked.period.revision}. Readiness checks input requirements; the solver must still establish feasibility.</p>
    <ul className="scheduler-diagnostics">{checked.issues.map((i, n) => <li key={`${i.code}:${i.record_id}:${n}`}><strong>{i.severity === 'blocking' ? 'Required' : 'Warning'}</strong><p>{i.message}</p></li>)}</ul>
  </section>;
}

function AcademicGenerationPage() {
  const [search, setSearch] = useSearchParams();
  const periodId = search.get('period') ?? '';
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [checked, setChecked] = useState<AcademicReadiness | null>(null);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const active = useRef(false);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    listAcademicPeriods().then(data => { if (!ignore) setPeriods(data.periods); }).catch(e => { if (!ignore) setError(e.message); }).finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [retry]);
  useEffect(() => {
    if (!periodId || !schedulingSandboxEnabled) return;
    let ignore = false;
    checkAcademicReadiness(periodId).then(value => { if (!ignore) setChecked(value); }).catch(e => { if (!ignore) setError(e.message); });
    return () => { ignore = true; };
  }, [periodId, retry]);
  useEffect(() => { if (result) { resultHeading.current?.focus({ preventScroll: true }); resultHeading.current?.scrollIntoView({ block: 'start', behavior: 'instant' }); } }, [result]);
  if (!schedulingSandboxEnabled) return <p>Academic scheduling requires verified Administrator sign-in. The unauthenticated development workflow is unavailable in this build.</p>;
  async function generate() {
    if (!checked?.ready || active.current) return;
    active.current = true; setBusy(true); setError(''); setResult(null);
    try { setResult(await generateAcademicSchedule(checked.period.id, checked.period.revision)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Generation unavailable. Recheck readiness.'); }
    finally { active.current = false; setBusy(false); }
  }
  const success = result && ['feasible', 'optimal'].includes(result.solver_status) && result.validation?.valid;
  return <div className="weekly-scheduler" aria-busy={busy}>
    <p className="scheduling-boundary">Development-entered academic data · Separate from the synthetic test scenario · Saved drafts remain unpublished.</p>
    <section className="workspace-card"><h2>Select academic period</h2>
      <label>Saved academic period<select value={periodId} disabled={busy} onChange={e => { const next = new URLSearchParams(search); next.set('period', e.target.value); setChecked(null); setResult(null); setError(''); setSearch(next); }}>
        <option value="">Choose a period</option>{periods.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
      </select></label>
      {loading && <p role="status">Loading academic periods…</p>}
      {!loading && !periods.length && <p>No saved academic periods. Enter academic data first; no subjects or instructors will be invented.</p>}
      <Link className="text-action" to={`/admin/academic${periodId ? `?period=${encodeURIComponent(periodId)}` : ''}`}>Manage Academic Data</Link>
      <Button variant="secondary" disabled={busy} onClick={() => { setError(''); setChecked(null); setResult(null); setRetry(n => n + 1); }}>Recheck readiness</Button>
    </section>
    {error && <p className="scheduler-error" role="alert">{error}</p>}
    {periodId && !checked && !error && <p role="status">Checking saved academic inputs…</p>}
    {checked && <ReadinessSummary checked={checked}/>}
    <Button disabled={!checked?.ready || busy} onClick={generate}>{busy ? 'Generating weekly schedule…' : 'Generate Weekly Schedule'}</Button>
    <p role="status">{busy ? 'Running the real backend solver on the saved academic batch. Please wait.' : 'Every active offering in this period is required. No automatic publication.'}</p>
    {result && <section className="scheduler-result"><h2 ref={resultHeading} tabIndex={-1}>Review academic schedule result</h2>
      <StatusBadge tone={success ? 'success' : 'warning'}>{result.solver_status === 'infeasible' ? 'Unschedulable — proven infeasible' : result.solver_status.replaceAll('_', ' ')}</StatusBadge>
      <p role="status">{success ? `${result.total_offerings_scheduled}/${result.total_offerings_requested} offerings · ${result.assignments.length} sessions · ${result.hard_conflict_count} hard conflicts · ${result.coverage.reduce((n,c)=>n+c.allocated_minutes,0)}/${result.coverage.reduce((n,c)=>n+c.required_minutes,0)} instructional minutes` : 'No validated timetable was accepted. Review diagnostics and adjust the saved academic inputs.'}</p>
      <ul className="scheduler-diagnostics">{result.diagnostics.map((d,i) => <li key={i}>{d.message}</li>)}</ul>
      {success && checked?.inputs && <><SaveDraftPanel key={`save:${result.run_id}`} result={result} source="academic" defaultTitle={`${checked.period.title} — review draft`}/><SchedulingTimetable key={`timetable:${result.run_id}`} input={checked.inputs} result={result}/></>}
    </section>}
    <Link className="text-action" to="/admin/schedule-manager/drafts?source=academic">Saved academic drafts</Link>
  </div>;
}
