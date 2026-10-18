import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listAcademicPeriods } from '../lib/academic-api';
import { listSchedulingDrafts, schedulingSandboxEnabled } from '../lib/scheduling-api';
import {
  defaultPeriod,
  periodLabel,
  readWorkspace,
  type WorkspacePeriod,
} from '../lib/workspace-context';
export function AdminSchedulingHome() {
  const [period, setPeriod] = useState<WorkspacePeriod>(),
    [count, setCount] = useState<number>(),
    [error, setError] = useState('');
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    Promise.all([listAcademicPeriods(), listSchedulingDrafts(0, 'academic')])
      .then(([p, d]) => {
        if (!ignore) {
          const id = defaultPeriod(p.periods, readWorkspace('administrator').period);
          setPeriod(p.periods.find((v) => v.id === id));
          setCount(d.drafts.length);
        }
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, []);
  return (
    <section className="ux-admin-home">
      <div>
        <p className="eyebrow">Scheduling workspace</p>
        <h1>Build a better campus week.</h1>
        <p>Choose an academic period, generate a timetable, then review and save a draft.</p>
      </div>
      {error && <p role="alert">{error}</p>}
      <article className="workspace-card ux-admin-primary">
        <span className="ux-update">{period ? periodLabel(period) : 'Academic setup'}</span>
        <h2>Plan the weekly timetable</h2>
        <p>Constraint-based scheduling with OR-Tools. Your hard constraints stay in control.</p>
        <Link
          className="button"
          to={'/admin/ai-scheduling' + (period ? '?period=' + encodeURIComponent(period.id) : '')}
        >
          Generate a schedule
        </Link>
      </article>
      <div className="ux-admin-links">
        <Link className="workspace-card" to="/admin/academic">
          <strong>Academic Setup</strong>
          <span>Periods, programs and teaching requirements</span>
        </Link>
        <Link className="workspace-card" to="/admin/schedule-manager/drafts?source=academic">
          <strong>
            Saved Drafts{count !== undefined ? ` · ${count}${count === 25 ? '+' : ''}` : ''}
          </strong>
          <span>Reopen the exact validated result</span>
        </Link>
        <Link className="workspace-card" to="/admin/calendar">
          <strong>Published Timetables</strong>
          <span>Inspect the current published source</span>
        </Link>
        <Link className="workspace-card" to="/admin/conflicts">
          <strong>Conflict Center</strong>
          <span>Run independent snapshot validation</span>
        </Link>
      </div>
    </section>
  );
}
