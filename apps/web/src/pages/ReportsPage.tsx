import { useEffect, useState } from 'react';
import { listAcademicPeriods, type AcademicPeriod } from '../lib/academic-api';
import { loadSchedulingReport, type SchedulingReport } from '../lib/admin-operations-api';
import { downloadCsv, toCsv, type CsvValue } from '../lib/csv';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import './admin-operations.css';

const hours = (minutes: number) => Math.round((minutes / 60) * 10) / 10;
const share = (value: number | null) => (value === null ? 'Not available' : `${value}%`);

function ReportTable({
  title,
  file,
  header,
  rows,
  empty,
}: {
  title: string;
  file: string;
  header: string[];
  rows: CsvValue[][];
  empty: string;
}) {
  return (
    <section className="workspace-card" aria-label={title}>
      <div className="admin-ops__bar">
        <h2>{title}</h2>
        {rows.length > 0 && (
          <Button
            variant="secondary"
            aria-label={`Download ${title} as CSV`}
            onClick={() => downloadCsv(file, toCsv(header, rows))}
          >
            Download CSV
          </Button>
        )}
      </div>
      {rows.length ? (
        <div className="table-wrap admin-ops__scroll" tabIndex={0} role="region" aria-label={`${title} table`}>
          <table>
            <thead>
              <tr>{header.map((name) => <th key={name} scope="col">{name}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>{row.map((cell, column) => <td key={column}>{cell ?? '—'}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

export function ReportsPage({ utilization = false }: { utilization?: boolean }) {
  const [periods, setPeriods] = useState<AcademicPeriod[]>([]);
  const [periodId, setPeriodId] = useState('');
  const [report, setReport] = useState<SchedulingReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let ignore = false;
    listAcademicPeriods(true)
      .then((result) => {
        if (ignore) return;
        setPeriods(result.periods);
        setPeriodId((current) => current || result.periods[0]?.id || '');
        if (!result.periods.length) setLoading(false);
      })
      .catch((cause: unknown) => {
        if (ignore) return;
        setError(cause instanceof Error ? cause.message : 'Periods could not be loaded.');
        setLoading(false);
      });
    return () => { ignore = true; };
  }, [attempt]);

  useEffect(() => {
    if (!periodId) return;
    let ignore = false;
    setLoading(true);
    setError('');
    setReport(null);
    loadSchedulingReport(periodId)
      .then((value) => { if (!ignore) setReport(value); })
      .catch((cause: unknown) => {
        if (!ignore) setError(cause instanceof Error ? cause.message : 'The report could not be loaded.');
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [periodId, attempt]);

  const available = report?.rooms.reduce((sum, room) => sum + room.available_minutes, 0) ?? 0;
  const booked = report?.rooms.reduce((sum, room) => sum + room.booked_minutes, 0) ?? 0;
  const groupRows = (items: SchedulingReport['buildings']) =>
    items.map((item) => [
      item.name,
      item.rooms,
      hours(item.booked_minutes),
      hours(item.available_minutes),
      hours(item.restricted_minutes),
      share(item.utilization),
    ]);
  const groupHeader = ['Rooms', 'Booked hours', 'Available hours', 'Restricted hours', 'Utilization'];
  const slug = report?.period.id.slice(0, 8) ?? 'period';

  return (
    <div className="admin-ops">
      <section className="workspace-card">
        <div className="admin-ops__bar">
          <label>
            Academic period
            <select value={periodId} onChange={(event) => setPeriodId(event.target.value)}>
              {!periods.length && <option value="">No periods saved</option>}
              {periods.map((period) => (
                <option key={period.id} value={period.id}>
                  {period.title}{period.archived_at ? ' (Archived)' : ''}
                </option>
              ))}
            </select>
          </label>
          <Button variant="secondary" disabled={loading} onClick={() => setAttempt((value) => value + 1)}>
            Refresh report
          </Button>
        </div>
        {loading && <ClassSyncSkeleton label="Loading report" />}
        {error && <p role="alert" className="scheduler-error">{error}</p>}
        {report && (
          <>
            <p role="status">
              {report.published
                ? `Published revision ${report.published.revision} of this period.`
                : 'This period has no published timetable, so its faculty loads and class counts are empty.'}
            </p>
            {report.basis ? (
              <p className="muted">
                Utilization covers {report.basis.instructional_dates} instructional dates,{' '}
                {report.basis.effective_start} to {report.basis.effective_end}: published class time
                divided by operating hours less active room restrictions. Rooms are shared, so every
                published timetable dated in this range counts.
              </p>
            ) : (
              <p className="muted">Save a period calendar to calculate room utilization.</p>
            )}
            <dl className="admin-ops__facts">
              <div><dt>Schedulable rooms</dt><dd>{report.rooms.length}</dd></div>
              <div>
                <dt>Overall room utilization</dt>
                <dd>{share(available ? Math.round((booked * 1000) / available) / 10 : null)}</dd>
              </div>
              <div><dt>Instructors</dt><dd>{report.faculty.length}</dd></div>
              <div><dt>Scheduled sections</dt><dd>{report.sections.length}</dd></div>
            </dl>
          </>
        )}
      </section>
      {report && (
        <>
          <ReportTable
            title="Utilization by building"
            file={`utilization-buildings-${slug}.csv`}
            header={['Building', ...groupHeader]}
            rows={groupRows(report.buildings)}
            empty="No rooms to summarize."
          />
          <ReportTable
            title="Utilization by room type"
            file={`utilization-room-types-${slug}.csv`}
            header={['Room type', ...groupHeader]}
            rows={groupRows(report.room_types)}
            empty="No rooms to summarize."
          />
          <ReportTable
            title="Room utilization"
            file={`utilization-rooms-${slug}.csv`}
            header={['Room', 'Building', 'Type', 'Booked hours', 'Available hours', 'Restricted hours', 'Utilization']}
            rows={report.rooms.map((room) => [
              room.name, room.building, room.room_type.replace(/_/g, ' '), hours(room.booked_minutes),
              hours(room.available_minutes), hours(room.restricted_minutes), share(room.utilization),
            ])}
            empty="No rooms to summarize."
          />
          {!utilization && (
            <>
              <ReportTable
                title="Faculty weekly load"
                file={`faculty-load-${slug}.csv`}
                header={['Instructor', 'Status', 'Weekly hours', 'Maximum hours', 'Load', 'Sessions']}
                rows={report.faculty.map((member) => [
                  member.name,
                  member.active ? 'Active' : 'Inactive',
                  hours(member.weekly_minutes),
                  member.max_weekly_minutes === null ? 'Not set' : hours(member.max_weekly_minutes),
                  share(member.load),
                  member.sessions,
                ])}
                empty="No faculty records in this period."
              />
              <ReportTable
                title="Institute distribution"
                file={`institutes-${slug}.csv`}
                header={['Institute', 'Programs', 'Sections', 'Offerings', 'Students', 'Sessions', 'Weekly hours']}
                rows={report.institutes.map((item) => [
                  item.institute, item.programs, item.sections, item.offerings, item.students,
                  item.sessions, hours(item.weekly_minutes),
                ])}
                empty="No sections or offerings in this period."
              />
              <ReportTable
                title="Program distribution"
                file={`programs-${slug}.csv`}
                header={['Program', 'Institute', 'Sections', 'Offerings', 'Students', 'Sessions', 'Weekly hours']}
                rows={report.programs.map((item) => [
                  item.program, item.institute, item.sections, item.offerings, item.students,
                  item.sessions, hours(item.weekly_minutes),
                ])}
                empty="No sections or offerings in this period."
              />
              <ReportTable
                title="Section daily shape"
                file={`section-days-${slug}.csv`}
                header={['Section', 'Program', 'Class days', 'Sessions', 'One-class days', 'Most classes in a day', 'Longest day (hours)', 'Idle hours']}
                rows={report.sections.map((item) => [
                  item.label, item.program, item.active_days, item.sessions, item.one_class_days,
                  item.max_sessions_per_day, hours(item.longest_span_minutes), hours(item.idle_minutes),
                ])}
                empty="Publish a timetable to see section days."
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
