import { useEffect, useState, type ReactNode } from 'react';
import { institutionalRequest } from '../../lib/institutional-api';
import { calendarDateLabel, type CalendarOccurrence } from '../../lib/calendar-model';
import { timeRange } from '../../lib/student-presentation';
import { Button } from '../ui/Button';
import { ClassSyncSkeleton } from '../loading/ClassSyncLoading';

interface Notice {
  id: string;
  title: string;
  body: string;
  audience: string[];
  updated_at: string;
}

const published = (value: string) =>
  new Intl.DateTimeFormat('en-PH', { dateStyle: 'medium', timeZone: 'Asia/Manila' }).format(
    new Date(value),
  );

/**
 * Published class changes and tenant announcements in one list, newest date first. The
 * server scopes both: the timetable to this identity, announcements to tenant and audience.
 */
export function AlertsFeed({
  role,
  changes,
  scheduleReady,
  action,
}: {
  role: 'student' | 'teacher';
  changes: CalendarOccurrence[];
  scheduleReady: boolean;
  action: (item: CalendarOccurrence) => ReactNode;
}) {
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setNotices(null);
    setFailed(false);
    institutionalRequest<{ announcements?: Notice[] }>('community/announcements', {
      role,
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted)
          setNotices((value.announcements ?? []).filter((item) => item.audience.includes(role)));
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [role, reload]);

  const entries = [
    ...changes.map((item) => ({
      key: `change:${item.id}`,
      at: Date.parse(item.starts_at),
      node: (
        <>
          <p className="eyebrow">Class change</p>
          <h3>{item.subject.name}</h3>
          <p>
            {calendarDateLabel(item.date)} · {timeRange(item.starts_at, item.ends_at)}
          </p>
          <p>
            Current classroom: {item.room.name} · {item.section.name}
          </p>
          {action(item)}
        </>
      ),
    })),
    ...(notices ?? []).map((item) => ({
      key: `notice:${item.id}`,
      at: Date.parse(item.updated_at),
      node: (
        <>
          <p className="eyebrow">Announcement</p>
          <h3 style={{ overflowWrap: 'anywhere' }}>{item.title}</h3>
          <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.body}</p>
          <p className="muted">Updated {published(item.updated_at)}</p>
        </>
      ),
    })),
  ].sort((a, b) => b.at - a.at);

  return (
    <section aria-labelledby="alerts-feed-heading">
      <h2 id="alerts-feed-heading">Alerts and announcements</h2>
      {failed && (
        <div role="alert">
          <p>Announcements are unavailable right now.</p>
          <Button variant="secondary" onClick={() => setReload((value) => value + 1)}>
            Retry announcements
          </Button>
        </div>
      )}
      {!notices && !failed && <ClassSyncSkeleton rows={2} label="Loading announcements" />}
      {entries.map((entry) => (
        <article className="workspace-card" key={entry.key}>
          {entry.node}
        </article>
      ))}
      {scheduleReady && !changes.length && <p>No changed classes in your current schedule.</p>}
      {notices?.length === 0 && <p>No current announcements.</p>}
    </section>
  );
}
