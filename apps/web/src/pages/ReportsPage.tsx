import { useEffect, useState } from 'react';
import { listAcademicPeriods, type AcademicPeriod } from '../lib/academic-api';
import { loadSchedulingReport, type SchedulingReport } from '../lib/admin-operations-api';
import { downloadCsv, toCsv, type CsvValue } from '../lib/csv';
import { Button } from '../components/ui/Button';
import { InlineError } from '../components/ui/InlineError';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { DataTable, type Column } from '../components/ui/DataTable';
import { Meter } from '../components/ui/Meter';
import { PageHeader } from '../components/layout/PageHeader';
import { CommandBar, CommandField } from '../components/layout/CommandBar';
import { KpiStrip } from '../components/layout/KpiStrip';
import { MetaDetails } from '../components/layout/MetaDetails';
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
  const meterColumn = (name: string) => name === 'Utilization' || name === 'Load';
  const columns: Column<CsvValue[]>[] = header.map((name, column) => ({
    header: name,
    numeric: !meterColumn(name) && rows.some((row) => typeof row[column] === 'number'),
    cell: (row) => {
      const value = row[column];
      if (!meterColumn(name)) return <span>{value ?? '—'}</span>;
      // Faculty load is over the limit above 100%; rooms are crowded above 90%.
      return (
        <Meter
          label={`${row[0]} ${name.toLowerCase()}`}
          value={typeof value === 'string' && value.endsWith('%') ? parseFloat(value) : null}
          high={name === 'Load' ? 85 : 70}
          over={name === 'Load' ? 100 : 90}
        />
      );
    },
  }));
  return (
    <section aria-label={title}>
      <div className="section-bar">
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
        <DataTable
          label={title}
          columns={columns}
          rows={rows}
          rowKey={(_, index) => String(index)}
          scroll
        />
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

export function ReportsPage({
  utilization = false,
  title = utilization ? 'Utilization' : 'Reports',
}: {
  utilization?: boolean;
  title?: string;
}) {
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
      <PageHeader
        title={title}
        meta={
          report && (
            <span role="status">
              {report.published
                ? `Published revision ${report.published.revision} of this period.`
                : 'This period has no published timetable, so its faculty loads and class counts are empty.'}
            </span>
          )
        }
      />
      <CommandBar label="Report period">
        <CommandField label="Academic period" wide>
          <select value={periodId} onChange={(event) => setPeriodId(event.target.value)}>
            {!periods.length && <option value="">No periods saved</option>}
            {periods.map((period) => (
              <option key={period.id} value={period.id}>
                {period.title}{period.archived_at ? ' (Archived)' : ''}
              </option>
            ))}
          </select>
        </CommandField>
        <div className="command-bar__end">
          <Button variant="secondary" disabled={loading} onClick={() => setAttempt((value) => value + 1)}>
            Refresh report
          </Button>
        </div>
      </CommandBar>
      {loading && <ClassSyncSkeleton label="Loading report" />}
      {error && (
        <InlineError
          title={periodId ? "Couldn't load the report" : "Couldn't load academic periods"}
          message={error}
          onRetry={() => {
            setError('');
            setAttempt((value) => value + 1);
          }}
        />
      )}
      {report && (
        <>
          <KpiStrip
            label="Report summary"
            items={[
              { label: 'Schedulable rooms', value: report.rooms.length },
              {
                label: 'Overall room utilization',
                value: share(available ? Math.round((booked * 1000) / available) / 10 : null),
              },
              { label: 'Instructors', value: report.faculty.length },
              { label: 'Scheduled sections', value: report.sections.length },
            ]}
          />
          <MetaDetails summary="How utilization is calculated">
            {report.basis ? (
              <p>
                Utilization covers {report.basis.instructional_dates} instructional dates,{' '}
                {report.basis.effective_start} to {report.basis.effective_end}: published class time
                divided by operating hours less active room restrictions. Rooms are shared, so every
                published timetable dated in this range counts.
              </p>
            ) : (
              <p>Save a period calendar to calculate room utilization.</p>
            )}
          </MetaDetails>
        </>
      )}
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
