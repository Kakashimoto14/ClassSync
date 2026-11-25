import { Link } from 'react-router-dom';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { calendarDateLabel } from '../lib/calendar-model';
import { timeRange } from '../lib/student-presentation';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import type { UserRole } from '../types/ui';

export function ConnectedUpdatesPage({ role }: { role: UserRole }) {
  const w = useScheduleWorkspace(role, true);
  const base = role === 'administrator' ? '/admin' : `/${role}`;
  const changes = w.records.filter((item) => item.changed);
  return (
    <section className="workspace-card">
      <h1>Schedule updates</h1>
      <p>Changes shown here come from your current published timetable.</p>
      {w.error ? (
        <div role="alert">
          <p>{w.error}</p>
          <Button onClick={w.retry}>Try again</Button>
        </div>
      ) : w.loading ? (
        <ClassSyncSkeleton layout="rows" label="Loading schedule updates" />
      ) : (
        <>
          <label>
            Academic period
            <select value={w.context.period} onChange={(e) => w.change({ period: e.target.value })}>
              {!w.periods.length && <option value="">No published term</option>}
              {w.periods.map((period) => (
                <option value={period.id} key={period.id}>
                  {period.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Show changes from
            <input
              type="date"
              value={w.date}
              onChange={(e) => w.change({ date: e.target.value })}
            />
          </label>
          {changes.length ? (
            changes.map((item) => (
              <article className="workspace-card" key={item.id}>
                <h2>{item.subject.name}</h2>
                <p>
                  {calendarDateLabel(item.date)} · {timeRange(item.starts_at, item.ends_at)}
                </p>
                <p>
                  Current classroom: {item.room.name} · {item.section.name}
                </p>
                <Link
                  to={`${base}/${role === 'administrator' ? 'calendar' : 'schedule'}?${new URLSearchParams({ period: w.context.period, date: item.date })}`}
                >
                  View updated class
                </Link>
              </article>
            ))
          ) : (
            <p>
              No changed classes in your selected date range. Open your schedule to review all
              current classes.
            </p>
          )}
        </>
      )}
      <Link to={base + '/announcements'}>University announcements</Link>
      <p>ClassSync does not send email or push alerts for these changes.</p>
    </section>
  );
}
