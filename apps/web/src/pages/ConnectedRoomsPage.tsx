import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { usePublishedRoomDirectory } from '../lib/use-published-room-directory';
import { calendarDateLabel } from '../lib/calendar-model';
import { timeRange } from '../lib/student-presentation';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { ClassSessionDetails } from '../components/scheduling/ClassSessionDetails';
import { RoomSlotChecker } from '../components/rooms/RoomSlotChecker';
import type { UserRole } from '../types/ui';
import './student-rooms.css';

export function ConnectedRoomsPage({ role, detail = false }: { role: UserRole; detail?: boolean }) {
  const w = useScheduleWorkspace(role, false);
  const [params, setParams] = useSearchParams();
  const [selected, select] = useState('');
  const ready = !w.loading && !w.error && w.data?.status !== 'not-published';
  const directory = usePublishedRoomDirectory(
    role,
    w.context.period,
    ready ? w.data?.version : null,
  );
  const base = role === 'administrator' ? '/admin' : `/${role}`;
  const home = base + (role === 'teacher' ? '/find-room' : '/rooms');
  const query = params.get('q') ?? '';
  const path = (target: string, id?: string) =>
    target +
    '?' +
    new URLSearchParams({
      period: w.context.period,
      date: w.date,
      ...(id ? { id } : {}),
    });
  const room = directory.rooms.find((item) => item.id === params.get('id'));
  const sessions = room ? w.records.filter((item) => item.room.id === room.id) : [];
  const current = w.records.find((item) => item.id === selected);
  return (
    <section className="student-rooms-page" aria-busy={w.loading || directory.loading}>
      <h1>{detail ? (room?.name ?? 'Room details') : 'Rooms'}</h1>
      <p>
        Published university room information. Check a time to see which rooms have a published
        class.
      </p>
      <label>
        Academic period
        <select value={w.context.period} onChange={(e) => w.change({ period: e.target.value })}>
          {!w.periods.length && <option value="">No published term</option>}
          {w.periods.map((period) => (
            <option key={period.id} value={period.id}>
              {period.title}
            </option>
          ))}
        </select>
      </label>
      {w.error || directory.error ? (
        <div role="alert" className="workspace-card">
          <h2>Room information unavailable</h2>
          <p>{w.error || directory.error}</p>
          <Button
            onClick={() => {
              w.retry();
              directory.retry();
            }}
          >
            Try again
          </Button>
        </div>
      ) : w.loading || directory.loading ? (
        <ClassSyncSkeleton layout="rows" label="Loading rooms" />
      ) : !w.data || w.data.status === 'not-published' ? (
        <p>No authorized published rooms yet.</p>
      ) : detail ? (
        <>
          <Link to={path(home)}>Back to rooms</Link>
          {room ? (
            <article className="student-room-card">
              <h2>Location and facilities</h2>
              <p>
                {room.building || 'Building unavailable'}
                {room.floor ? ` · Floor ${room.floor}` : ''}
              </p>
              {room.location && <p>{room.location}</p>}
              <p>
                {room.room_type || 'Room type not verified'} ·{' '}
                {room.capacity ? `${room.capacity} seats` : 'Capacity not verified'}
              </p>
              <p>{room.equipment.length ? room.equipment.join(', ') : 'Equipment not verified'}</p>
              <h2>{role === 'teacher' ? 'Your classes here' : 'Published classes here'}</h2>
              <label>
                Show classes from
                <input
                  type="date"
                  value={w.date}
                  onChange={(e) => w.change({ date: e.target.value })}
                />
              </label>
              {sessions.length ? (
                sessions.map((item) => (
                  <button
                    className="student-room-class"
                    key={item.id}
                    onClick={() => select(item.id)}
                  >
                    <strong>
                      {item.subject.name} · {item.section.name}
                    </strong>
                    <span>
                      {calendarDateLabel(item.date)} · {timeRange(item.starts_at, item.ends_at)}
                    </span>
                  </button>
                ))
              ) : (
                <p>No classes in your selected date range.</p>
              )}
            </article>
          ) : (
            <p>This room is not in your permitted current directory.</p>
          )}
        </>
      ) : (
        <>
          <RoomSlotChecker role={role} period={w.context.period} initialDate={w.date} />
          <label>
            Search rooms
            <input
              type="search"
              value={query}
              onChange={(e) => {
                const next = new URLSearchParams(params);
                next.set('q', e.target.value);
                setParams(next, { replace: true });
              }}
            />
          </label>
          <div className="student-rooms-grid">
            {directory.rooms
              .filter((item) =>
                `${item.name} ${item.building}`.toLowerCase().includes(query.trim().toLowerCase()),
              )
              .map((item) => (
                <article className="student-room-card" key={item.id}>
                  <h2>{item.name}</h2>
                  <p>{item.building}</p>
                  <Link to={path(base + '/rooms/detail', item.id)}>
                    Room details for {item.name}
                  </Link>
                </article>
              ))}
          </div>
          {!directory.rooms.some((item) =>
            `${item.name} ${item.building}`.toLowerCase().includes(query.trim().toLowerCase()),
          ) && <p role="status">No matching rooms.</p>}
        </>
      )}
      {current && (
        <ClassSessionDetails
          session={current}
          role={role}
          sample={false}
          published
          period={w.context.period}
          onClose={() => select('')}
        />
      )}
    </section>
  );
}
