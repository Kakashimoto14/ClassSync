import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { institutionalRequest } from '../lib/institutional-api';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { calendarDateLabel } from '../lib/calendar-model';
import { timeRange } from '../lib/student-presentation';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import type { UserRole } from '../types/ui';

type DecidedRequest = {
  id: string;
  status: 'pending' | 'approved' | 'rejected' | 'fulfilled';
  decision_note: string | null;
  updated_at?: string;
  context: {
    class: { date: string; subject: { code: string }; room: { name: string } };
    proposed_room: { name: string };
  };
};
const decisionLabel = {
  approved: 'Approved · awaiting publication',
  fulfilled: 'Approved · new room published',
  rejected: 'Declined',
} as const;

/** Teacher-only: Administrator decisions on this Teacher's own classroom requests. */
function RequestDecisions() {
  const [decided, setDecided] = useState<DecidedRequest[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    institutionalRequest<{ requests: DecidedRequest[] }>('timetables/requests', {
      role: 'teacher',
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setDecided(
          data.requests
            .filter((item) => item.status !== 'pending')
            .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
            .slice(0, 10),
        );
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(failure instanceof Error ? failure.message : 'Request decisions unavailable.');
      });
    return () => controller.abort();
  }, []);
  return (
    <section aria-labelledby="request-decisions-heading">
      <h2 id="request-decisions-heading">Classroom request decisions</h2>
      {error ? (
        <p role="alert">{error}</p>
      ) : !decided ? (
        <ClassSyncSkeleton rows={2} label="Loading request decisions" />
      ) : decided.length ? (
        <ul>
          {decided.map((item) => (
            <li key={item.id}>
              <strong>{decisionLabel[item.status as keyof typeof decisionLabel]}</strong> ·{' '}
              {item.context.class.subject.code} · {calendarDateLabel(item.context.class.date)} ·{' '}
              {item.context.class.room.name} → {item.context.proposed_room.name}
              {item.decision_note && <p className="muted">Note: {item.decision_note}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <p>No decided classroom requests yet.</p>
      )}
      <Link to="/teacher/change-requests">All classroom requests</Link>
    </section>
  );
}

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
      {role === 'teacher' && <RequestDecisions />}
      <Link to={base + '/announcements'}>University announcements</Link>
      <p>
        {role === 'teacher'
          ? 'Published room changes appear here. Classroom request decisions are also emailed to you when email delivery is configured.'
          : 'Published room changes appear here as soon as they take effect.'}
      </p>
    </section>
  );
}
