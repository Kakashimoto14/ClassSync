import { useEffect, useState } from 'react';
import { listAcademicPeriods, loadAcademicRoster, type AcademicPeriod, type AcademicRosterPage } from '../lib/academic-api';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { appMode } from '../config/runtime-config';

export function AcademicStudentRosterPage() {
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [periodId, setPeriodId] = useState('');
  const [page, setPage] = useState<AcademicRosterPage | null>(null);
  const [search, setSearch] = useState('');
  const [year, setYear] = useState('all');
  const [section, setSection] = useState('all');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (appMode !== 'institutional') return;
    let ignore = false;
    listAcademicPeriods().then((result) => {
      if (ignore) return;
      setPeriods(result.periods);
      setPeriodId((current) => current || result.periods[0]?.id || '');
    }).catch((cause: unknown) => {
      if (!ignore) setError(cause instanceof Error ? cause.message : 'Roster periods could not be loaded.');
    }).finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  useEffect(() => {
    if (appMode !== 'institutional' || !periodId) return;
    let ignore = false;
    setLoading(true);
    setError('');
    loadAcademicRoster(periodId, {
      limit: 20, offset, search,
      ...(year === 'all' ? {} : { year_level: Number(year) }),
      ...(section === 'all' ? {} : { section_id: section }),
    }).then((result) => { if (!ignore) setPage(result); })
      .catch((cause: unknown) => { if (!ignore) setError(cause instanceof Error ? cause.message : 'Roster could not be loaded.'); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [periodId, offset, search, year, section]);

  if (appMode !== 'institutional') {
    return <section className="workspace-card">
      <h2>Student roster</h2>
      <p>Roster records are available in the connected institutional workspace.</p>
    </section>;
  }

  return <section className="workspace-card academic-records" aria-labelledby="student-roster-title">
    <h2 id="student-roster-title">Student roster</h2>
    <div className="academic-list-toolbar">
      <label>Academic period<select value={periodId} onChange={(event) => { setPeriodId(event.target.value); setOffset(0); }}>
        <option value="">Choose a period</option>{periods.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select></label>
      <label>Search roster<input type="search" value={search} placeholder="Name, student ID, or email" onChange={(event) => { setSearch(event.target.value); setOffset(0); }}/></label>
      <label>Year level<select value={year} onChange={(event) => { setYear(event.target.value); setOffset(0); }}>
        <option value="all">All years</option>{[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value}{value === 1 ? 'st' : value === 2 ? 'nd' : value === 3 ? 'rd' : 'th'} Year</option>)}
      </select></label>
      <label>Section<select value={section} onChange={(event) => { setSection(event.target.value); setOffset(0); }}>
        <option value="all">All sections</option>{page?.sections.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>
    </div>
    {page && <p role="status" className="academic-record-summary">{page.total} roster records · 20 per page</p>}
    {loading && <ClassSyncSkeleton label="Loading student roster" />}
    {error && <p role="alert" className="scheduler-error">{error}</p>}
    {!loading && !error && page && !page.items.length && <p>No roster records match these filters.</p>}
    {!loading && page?.items.length ? <>
      <div className="table-wrap"><table>
        <thead><tr><th>Student</th><th>Student ID</th><th>Section</th><th>Email</th><th>Enrollment</th></tr></thead>
        <tbody>{page.items.map((item) => <tr key={item.student_id}>
          <td>{item.display_name ?? 'Name not entered'}</td><td>{item.student_id}</td>
          <td>{item.section_label} · Year {item.year_level}</td><td>{item.registered_email ?? 'Email not entered'}</td>
          <td><StatusBadge tone={item.enrollment_status === 'active' ? 'success' : 'warning'}>{item.enrollment_status === 'active' ? 'Active' : item.enrollment_status === 'inactive' ? 'Inactive' : 'Unverified'}</StatusBadge></td>
        </tr>)}</tbody>
      </table></div>
      <div className="draft-actions" aria-label="Roster pagination">
        <Button variant="secondary" disabled={offset === 0 || loading} onClick={() => setOffset((value) => Math.max(0, value - 20))}>Previous</Button>
        <span>{offset + 1}–{Math.min(offset + page.items.length, page.total)} of {page.total}</span>
        <Button variant="secondary" disabled={offset + 20 >= page.total || loading} onClick={() => setOffset((value) => value + 20)}>Next</Button>
      </div>
    </> : null}
  </section>;
}
