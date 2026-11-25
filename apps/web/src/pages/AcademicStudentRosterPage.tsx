import { useEffect, useState, type FormEvent } from 'react';
import { listAcademicPeriods, loadAcademicRoster, createAcademicRosterStudent,
  updateAcademicRosterStudent, deleteAcademicRosterStudent,
  type AcademicPeriod, type AcademicRosterPage, type RosterStudentWrite } from '../lib/academic-api';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { appMode } from '../config/runtime-config';

type StudentForm = Omit<RosterStudentWrite, 'expected_period_revision'>;
const blankStudent = (): StudentForm => ({
  student_id: '', full_name: '', email: '', year_level: 1, section_id: '',
  enrollment_status: 'unverified',
});

export function AcademicStudentRosterPage() {
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [periodId, setPeriodId] = useState('');
  const [page, setPage] = useState<AcademicRosterPage | null>(null);
  const [search, setSearch] = useState('');
  const [year, setYear] = useState('all');
  const [section, setSection] = useState('all');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState('');
  const [form, setForm] = useState<StudentForm>(blankStudent);

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

  const activeSections = (page?.sections ?? []).filter((item) => item.active);
  const sectionsForYear = activeSections.filter((item) => item.year_level === form.year_level);
  function beginCreate() {
    const firstSection = activeSections[0];
    setEditingId('');
    setForm({ ...blankStudent(), ...(firstSection ? {
      year_level: firstSection.year_level, section_id: firstSection.id,
    } : {}) });
    setFormOpen(true);
    setError('');
    setNotice('');
  }
  function beginEdit(item: AcademicRosterPage['items'][number]) {
    setEditingId(item.student_id);
    setForm({
      student_id: item.student_id,
      full_name: item.display_name ?? '',
      email: item.registered_email ?? '',
      year_level: item.year_level,
      section_id: item.section_id,
      enrollment_status: item.enrollment_status,
    });
    setFormOpen(true);
    setError('');
    setNotice('');
  }
  async function reloadRoster(nextOffset: number) {
    const result = await loadAcademicRoster(periodId, {
      limit: 20, offset: nextOffset, search,
      ...(year === 'all' ? {} : { year_level: Number(year) }),
      ...(section === 'all' ? {} : { section_id: section }),
    });
    setPage(result);
    setOffset(nextOffset);
  }
  async function saveStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!page || saving || deletingId) return;
    setSaving(true);
    setError('');
    setNotice('');
    const body: RosterStudentWrite = {
      ...form,
      student_id: form.student_id.trim(),
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      expected_period_revision: page.period_revision,
    };
    try {
      if (editingId) {
        await updateAcademicRosterStudent(periodId, editingId, body);
        await reloadRoster(offset);
        setNotice(`Student ${body.student_id} updated.`);
      } else {
        await createAcademicRosterStudent(periodId, body);
        await reloadRoster(0);
        setNotice(`Student ${body.student_id} added to the roster.`);
      }
      setFormOpen(false);
      setEditingId('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Student record could not be saved.');
    } finally {
      setSaving(false);
    }
  }
  async function removeStudent(item: AcademicRosterPage['items'][number]) {
    if (!page || saving || deletingId) return;
    if (!window.confirm(`Delete ${item.display_name ?? item.student_id} (${item.student_id}) from this roster? This cannot be undone.`)) return;
    setDeletingId(item.student_id);
    setError('');
    setNotice('');
    try {
      const nextOffset = offset > 0 && offset >= page.total - 1 ? Math.max(0, offset - 20) : offset;
      await deleteAcademicRosterStudent(periodId, item.student_id, page.period_revision);
      await reloadRoster(nextOffset);
      setNotice(`Student ${item.student_id} deleted from the roster.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Student record could not be deleted.');
    } finally {
      setDeletingId('');
    }
  }

  return <section className="workspace-card academic-records" aria-labelledby="student-roster-title">
    <div className="student-roster-heading">
      <div><h2 id="student-roster-title">Student roster</h2>
        {page && <p className="academic-record-summary">{page.total} roster records · 20 per page</p>}
      </div>
      <Button type="button" disabled={!page || loading || saving || Boolean(deletingId)} onClick={beginCreate}>+ Add Student</Button>
    </div>
    <div className="academic-list-toolbar">
      <label>Academic period<select value={periodId} onChange={(event) => { setPeriodId(event.target.value); setOffset(0); setFormOpen(false); }}>
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
    {notice && <p role="status" aria-live="polite">{notice}</p>}
    {loading && <ClassSyncSkeleton label="Loading student roster" />}
    {error && <p role="alert" className="scheduler-error">{error}</p>}
    {formOpen && <form className="student-roster-form" aria-label={editingId ? 'Edit student' : 'Add student'} onSubmit={saveStudent}>
      <h3>{editingId ? `Edit ${editingId}` : 'Add student'}</h3>
      <label>Full name<input required maxLength={160} value={form.full_name} placeholder="e.g., Aira Santos" onChange={(event) => setForm({ ...form, full_name: event.target.value })}/><small>Enter the student’s registered full name. Required.</small></label>
      <label>Student ID<input required pattern="[0-9]{2}-[0-9]{5}" maxLength={8} value={form.student_id} placeholder="24-00101" onChange={(event) => setForm({ ...form, student_id: event.target.value })}/><small>Use the student number from the roster. Required.</small></label>
      <label>Email<input required type="email" maxLength={320} value={form.email} placeholder="student@student.pnm.edu.ph" onChange={(event) => setForm({ ...form, email: event.target.value })}/><small>Enter the roster contact email. A changed address is marked unverified. Required.</small></label>
      <label>Year level<select required value={form.year_level} onChange={(event) => {
        const nextYear = Number(event.target.value);
        const nextSection = activeSections.find((item) => item.year_level === nextYear);
        setForm({ ...form, year_level: nextYear, section_id: nextSection?.id ?? '' });
      }}>
        {[1, 2, 3, 4].map((value) => <option key={value} value={value}>{value}{value === 1 ? 'st' : value === 2 ? 'nd' : value === 3 ? 'rd' : 'th'} Year</option>)}
      </select><small>Choose the student’s current year. Required.</small></label>
      <label>Section<select required value={form.section_id} onChange={(event) => setForm({ ...form, section_id: event.target.value })}>
        <option value="">Choose a section</option>{sectionsForYear.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select><small>Only active sections for this year are listed. Required.</small></label>
      <label>Enrollment status<select value={form.enrollment_status} onChange={(event) => setForm({ ...form, enrollment_status: event.target.value as StudentForm['enrollment_status'] })}>
        <option value="active">Active</option><option value="inactive">Inactive</option><option value="unverified">Unverified</option>
      </select><small>Set the roster status. Required.</small></label>
      <div className="draft-actions">
        <Button type="submit" disabled={saving || Boolean(deletingId)} loading={saving}>{editingId ? 'Save Student' : 'Add Student'}</Button>
        <Button type="button" variant="secondary" disabled={saving || Boolean(deletingId)} onClick={() => { setFormOpen(false); setEditingId(''); }}>Cancel</Button>
      </div>
    </form>}
    {!loading && !error && page && !page.items.length && <p>No roster records match these filters.</p>}
    {!loading && page?.items.length ? <>
      <div className="table-wrap"><table>
        <thead><tr><th>Student</th><th>Student ID</th><th>Section</th><th>Email</th><th>Enrollment</th><th>Actions</th></tr></thead>
        <tbody>{page.items.map((item) => <tr key={item.student_id}>
          <td>{item.display_name ?? 'Name not entered'}</td><td>{item.student_id}</td>
          <td>{item.section_label} · Year {item.year_level}</td><td>{item.registered_email ?? 'Email not entered'}</td>
          <td><StatusBadge tone={item.enrollment_status === 'active' ? 'success' : 'warning'}>{item.enrollment_status === 'active' ? 'Active' : item.enrollment_status === 'inactive' ? 'Inactive' : 'Unverified'}</StatusBadge></td>
          <td><div className="student-roster-actions">
            <Button type="button" variant="secondary" disabled={saving || Boolean(deletingId)} onClick={() => beginEdit(item)}>Edit {item.student_id}</Button>
            <Button type="button" variant="danger" loading={deletingId === item.student_id} disabled={saving || Boolean(deletingId)} onClick={() => void removeStudent(item)}>Delete {item.student_id}</Button>
          </div></td>
        </tr>)}</tbody>
      </table></div>
      <div className="draft-actions" aria-label="Roster pagination">
        <Button variant="secondary" disabled={offset === 0 || loading || saving || Boolean(deletingId)} onClick={() => setOffset((value) => Math.max(0, value - 20))}>Previous</Button>
        <span>{offset + 1}–{Math.min(offset + page.items.length, page.total)} of {page.total}</span>
        <Button variant="secondary" disabled={offset + 20 >= page.total || loading || saving || Boolean(deletingId)} onClick={() => setOffset((value) => value + 20)}>Next</Button>
      </div>
    </> : null}
  </section>;
}
