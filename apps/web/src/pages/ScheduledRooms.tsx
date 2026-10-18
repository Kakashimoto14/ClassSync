import { Link } from 'react-router-dom';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import type { UserRole } from '../types/ui';
import { Button } from '../components/ui/Button';
export function ScheduledRooms({ role, roomId }: { role: UserRole; roomId?: string }) {
  const w = useScheduleWorkspace(role);
  const rooms = [...new Map(w.records.map((o) => [o.room.id, o.room])).values()];
  const base = role === 'administrator' ? '/admin' : `/${role}`;
  if (roomId) {
    const room = rooms.find((r) => r.id === roomId);
    return (
      <section className="workspace-card">
        <Link className="text-action" to={base + '/schedule'}>
          Back to Schedule
        </Link>
        <h1>{room?.name ?? 'Scheduled room'}</h1>
        {w.loading ? (
          <p role="status">Loading room from your timetable…</p>
        ) : w.error ? (
          <p role="alert">{w.error}</p>
        ) : room ? (
          <>
            <p>
              {room.building}
              {room.floor ? ` · ${room.floor}` : ''}
            </p>
            <p>Sample scheduling resource · Capacity and equipment unverified.</p>
            <Link
              className="text-action"
              to={base + (role === 'student' ? '/find-room' : '/room-availability')}
            >
              Check room availability
            </Link>
          </>
        ) : (
          <p>
            This room is not present in your selected timetable. Choose the same context in Schedule
            or return to the directory.
          </p>
        )}
      </section>
    );
  }
  return (
    <details className="ux-scheduled-rooms">
      <summary>Your scheduled rooms · {w.context.date}</summary>
      {w.error ? (
        <>
          <p>Scheduled rooms unavailable: {w.error}</p>
          <Button variant="ghost" onClick={w.retry}>
            Retry scheduled rooms
          </Button>
        </>
      ) : rooms.length ? (
        <div className="ux-admin-links">
          {rooms.map((r) => (
            <Link
              className="workspace-card"
              key={r.id}
              to={`${base}/rooms/detail?id=${encodeURIComponent(r.id)}`}
            >
              <strong>{r.name}</strong>
              <span>
                {r.building}
                {r.floor ? ` · ${r.floor}` : ''}
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p>
          {w.loading
            ? 'Loading scheduled rooms…'
            : 'No published rooms in this selected context. Room inventory remains available below.'}
        </p>
      )}
    </details>
  );
}
