import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Building2, MapPin, Search, X } from 'lucide-react';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { presentationEnabled } from '../lib/presentation-sample';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';
import {
  matchesRoom,
  roomClassPatterns,
  studentRooms,
  type StudentRoom,
} from '../lib/student-rooms';
import { calendarDateLabel } from '../lib/calendar-model';
import { studentOccurrence, timeRange } from '../lib/student-presentation';
import { StudentPageHeader } from '../components/ui/StudentPageHeader';
import { ClassSessionDetails } from '../components/scheduling/ClassSessionDetails';
import { Button } from '../components/ui/Button';
import './student-rooms.css';

export function StudentRooms({ detail = false }: { detail?: boolean }) {
  const w = useScheduleWorkspace('student', false);
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<string | null>(null);
  const category = ['all', 'labs'].includes(params.get('category') ?? '')
    ? params.get('category')!
    : 'my';
  const query = params.get('q') ?? '';
  const ready = !w.loading && !w.error && w.data && w.data.status !== 'not-published';
  const mine = studentRooms(ready ? w.records : []).sort((a, b) => {
    const next = (item: StudentRoom) =>
      item.classes.find((session) => session.date >= w.date)?.starts_at ?? '9999';
    return next(a).localeCompare(next(b)) || a.name.localeCompare(b.name);
  });
  // The owner-supplied catalog is available in preview, never injected into an institutional tenant.
  const directory: StudentRoom[] = presentationEnabled
    ? provisionalCdmRooms.map((room) => ({ ...room, classes: [] }))
    : [];
  const rooms = category === 'my' ? mine : category === 'all' ? directory : [];
  const filtered = rooms.filter((room) => matchesRoom(room, query));
  const room = (params.get('directory') === '1' ? directory : mine).find(
    (item) => item.id === params.get('id'),
  );
  const currentClass = ready ? w.records.find((item) => item.id === selected) : undefined;
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key === 'q' });
  }
  function path(target: string, extra: Record<string, string> = {}) {
    const next = new URLSearchParams(params);
    next.set('date', w.date);
    next.set('period', w.context.period);
    next.set('schedule', '1');
    next.delete('id');
    next.delete('directory');
    Object.entries(extra).forEach(([key, value]) => next.set(key, value));
    return target + '?' + next;
  }
  const schedule =
    '/student/schedule?' + new URLSearchParams({ date: w.date, period: w.context.period });
  const state = w.error ? (
    <div className="student-rooms-state" role="alert">
      <MapPin aria-hidden="true" />
      <h2>
        {[401, 403].includes(w.errorStatus)
          ? 'Your schedule is not accessible'
          : 'Your timetable is unavailable'}
      </h2>
      <p>
        {[401, 403].includes(w.errorStatus)
          ? 'Check your university access to see your assigned rooms.'
          : 'We cannot load your assigned rooms right now. Please try again.'}
      </p>
      <Button onClick={w.retry}>Try again</Button>
    </div>
  ) : w.loading ? (
    <div className="student-rooms-state" role="status" aria-busy="true">
      Loading your rooms…
    </div>
  ) : null;
  function card(item: StudentRoom) {
    const patterns = roomClassPatterns(item.classes);
    return (
      <article className="student-room-card" key={item.id}>
        <div className="student-room-card-heading">
          <span className="student-room-icon">
            <Building2 size={21} aria-hidden="true" />
          </span>
          <div>
            <h2>{item.name}</h2>
            <p>
              {item.building || 'Building details unavailable'}
              {item.location && ` · ${item.location}`}
            </p>
          </div>
        </div>
        {item.alias && (
          <p className="student-room-alias">
            {item.alias}
            {item.aliasUnconfirmed && ' · Unconfirmed'}
          </p>
        )}
        {patterns.length > 0 && (
          <div className="student-rooms-classes">
            {patterns.slice(0, 3).map((pattern, i) => (
              <div key={i}>
                <strong>{pattern.subject}</strong>
                <span>
                  {pattern.days.join(' · ')} · {timeRange(pattern.start, pattern.end)}
                </span>
              </div>
            ))}
          </div>
        )}
        <Link
          className="student-rooms-card-action"
          aria-label={`View ${item.name} details`}
          to={path('/student/rooms/detail', {
            id: item.id,
            ...(category === 'all' ? { directory: '1' } : {}),
          })}
        >
          Room details <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </article>
    );
  }
  return (
    <section className="student-rooms-page" data-published-version={w.data?.version ?? ''}>
      {detail ? (
        <>
          <Link className="student-rooms-back" to={path('/student/rooms')}>
            <ArrowLeft size={16} aria-hidden="true" /> Back to Rooms
          </Link>
          {params.get('directory') !== '1' && state ? (
            <>
              <StudentPageHeader title="Room details" />
              {state}
            </>
          ) : room ? (
            <>
              <StudentPageHeader title={room.name} />
              <div className="student-room-detail-layout">
                <section className="student-room-card student-room-location">
                  <span className="student-room-icon">
                    <Building2 size={28} aria-hidden="true" />
                  </span>
                  <h2>Location</h2>
                  <p>{room.building || 'Building details unavailable'}</p>
                  {room.floor && <p>Floor {room.floor}</p>}
                  {room.location && <p>{room.location}</p>}
                  {room.alias && (
                    <p>
                      {room.alias}
                      {room.aliasUnconfirmed && ' · Unconfirmed'}
                    </p>
                  )}
                  <Link className="student-rooms-card-action" to={schedule}>
                    Back to Schedule <ArrowUpRight size={16} aria-hidden="true" />
                  </Link>
                </section>
                {room.classes.length > 0 ? (
                  <section className="student-room-card">
                    <h2>Your classes here</h2>
                    <p className="student-room-muted">{calendarDateLabel(w.date)}</p>
                    {room.classes
                      .filter((item) => item.date === w.date)
                      .map((item) => (
                        <button
                          className="student-room-class"
                          key={item.id}
                          onClick={() => setSelected(item.id)}
                        >
                          <strong>{item.subject.name}</strong>
                          <span>{timeRange(item.starts_at, item.ends_at)}</span>
                          <span>{item.teacher.name}</span>
                          <ArrowUpRight size={17} aria-hidden="true" />
                        </button>
                      ))}
                    {!room.classes.some((item) => item.date === w.date) && (
                      <p>No classes in this room on this date.</p>
                    )}
                    <details>
                      <summary>Other dates in your schedule</summary>
                      {room.classes
                        .filter((item) => item.date !== w.date)
                        .map((item) => (
                          <button
                            className="student-room-class"
                            key={item.id}
                            onClick={() => setSelected(item.id)}
                          >
                            <strong>{item.subject.name}</strong>
                            <span>
                              {calendarDateLabel(item.date)} ·{' '}
                              {timeRange(item.starts_at, item.ends_at)}
                            </span>
                          </button>
                        ))}
                    </details>
                  </section>
                ) : (
                  <section className="student-room-card">
                    <h2>Room information</h2>
                    <p>
                      This room is in the provisional directory. It is not linked to your current
                      schedule.
                    </p>
                  </section>
                )}
              </div>
              <p className="student-room-source">
                {room.classes.length
                  ? 'Room details are provisional. Physical availability is not confirmed.'
                  : 'Provisional room information. Facilities and physical availability are not confirmed.'}
              </p>
            </>
          ) : (
            <div className="student-rooms-state">
              <MapPin aria-hidden="true" />
              <h1>Room details unavailable</h1>
              <p>This room is not in the selected schedule or accessible directory.</p>
              <Link to={schedule}>Back to Schedule</Link>
            </div>
          )}
        </>
      ) : (
        <>
          <StudentPageHeader title="Rooms" />
          <p className="student-rooms-intro">Find where your classes are held.</p>
          <div className="student-rooms-toolbar">
            <div className="student-rooms-search">
              <Search size={20} aria-hidden="true" />
              <input
                type="search"
                aria-label="Search rooms or buildings"
                placeholder="Search rooms or buildings"
                value={query}
                onChange={(event) => change('q', event.target.value)}
              />
              {query && (
                <button aria-label="Clear search" onClick={() => change('q', '')}>
                  <X size={18} aria-hidden="true" />
                </button>
              )}
            </div>
            <div className="student-room-categories" aria-label="Room categories">
              {[
                ['my', 'My rooms'],
                ['all', 'All rooms'],
                ['labs', 'Labs'],
              ].map(([key, label]) => (
                <button
                  key={key}
                  aria-pressed={category === key}
                  onClick={() => change('category', key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {category === 'my' && state ? (
            state
          ) : category === 'labs' ? (
            <div className="student-rooms-state">
              <Building2 aria-hidden="true" />
              <h2>Lab information is not confirmed</h2>
              <p>The available room information does not include verified lab classifications.</p>
              <Button variant="secondary" onClick={() => change('category', 'all')}>
                Browse all rooms
              </Button>
            </div>
          ) : category === 'all' && !presentationEnabled ? (
            <div className="student-rooms-state">
              <Building2 aria-hidden="true" />
              <h2>Room directory unavailable</h2>
              <p>You can still find rooms assigned in your schedule under My rooms.</p>
            </div>
          ) : (
            <>
              <div className="student-rooms-results" role="status">
                {filtered.length} {filtered.length === 1 ? 'room' : 'rooms'}
                {query && ` matching “${query}”`}
              </div>
              {category === 'all' && (
                <p className="student-room-source">
                  Owner-supplied provisional directory · Room details have not been verified.
                </p>
              )}
              {filtered.length ? (
                <div className="student-rooms-grid">{filtered.map(card)}</div>
              ) : (
                <div className="student-rooms-state">
                  <MapPin aria-hidden="true" />
                  <h2>{query ? 'No matching rooms' : 'No assigned rooms yet'}</h2>
                  <p>
                    {query
                      ? 'Try a different room name or building.'
                      : 'Rooms will appear here when they are assigned in your schedule.'}
                  </p>
                  <Button
                    variant="secondary"
                    onClick={() => (query ? change('q', '') : change('category', 'all'))}
                  >
                    {query ? 'Clear search' : 'Browse all rooms'}
                  </Button>
                </div>
              )}
              {category === 'my' && (
                <p className="student-room-source">
                  Rooms in your selected schedule. Physical availability is not confirmed.
                </p>
              )}
            </>
          )}
          {presentationEnabled && (
            <details className="student-room-preview">
              <summary>Preview tools</summary>
              <Link to="/student/rooms?inventory=demo">Example inventory &amp; filters</Link>
              <Link to="/student/find-room">Schedule-based room search</Link>
            </details>
          )}
        </>
      )}
      {currentClass && (
        <ClassSessionDetails
          session={studentOccurrence(currentClass)}
          role="student"
          sample={w.context.mode !== 'published'}
          presentation={w.context.mode === 'presentation'}
          published={w.context.mode === 'published'}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
