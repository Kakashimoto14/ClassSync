import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, CalendarDays, MapPin } from 'lucide-react';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { addDays, calendarDateLabel, type CalendarOccurrence } from '../lib/calendar-model';
import { ClassSessionDetails } from '../components/scheduling/ClassSessionDetails';
import { Button } from '../components/ui/Button';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { presentationEnabled } from '../lib/presentation-sample';
import {
  nextClass,
  studentOccurrence,
  studentTime,
  termLabel,
  timeRange,
} from '../lib/student-presentation';
import { StudentPageHeader } from '../components/ui/StudentPageHeader';
import './student-home.css';

export function StudentHome({
  rooms = false,
  roomDetail = false,
  alerts = false,
}: {
  rooms?: boolean;
  roomDetail?: boolean;
  alerts?: boolean;
}) {
  const [params] = useSearchParams();
  const w = useScheduleWorkspace('student', !roomDetail);
  const [selected, setSelected] = useState<CalendarOccurrence | null>(null);
  const [roomQuery, setRoomQuery] = useState('');
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  const records = w.records
    .map(studentOccurrence)
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const currentSelection = selected ? records.find((item) => item.id === selected.id) : undefined;
  const today = records.filter((item) => item.date === w.date);
  const next = nextClass(records, now);
  const weekStart = addDays(w.date, -((new Date(w.date + 'T00:00:00Z').getUTCDay() + 6) % 7));
  const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
  const changes = records.filter((item) => item.changed);
  const knownRooms = [...new Map(records.map((item) => [item.room.id, item.room])).values()];
  const visibleRooms = roomDetail
    ? knownRooms.filter((room) => room.id === params.get('id'))
    : knownRooms.filter((room) =>
        `${room.name} ${room.building}`
          .toLocaleLowerCase()
          .includes(roomQuery.trim().toLocaleLowerCase()),
      );
  const source =
    w.context.mode === 'presentation'
      ? 'Sample schedule'
      : schedulingSandboxEnabled
        ? 'Sample schedule'
        : 'Current schedule';
  const roomsPath = source === 'Sample schedule' ? '/student/rooms?schedule=1' : '/student/rooms';
  const schedulePath = '/student/schedule?period=' + encodeURIComponent(w.context.period);
  function session(item: CalendarOccurrence) {
    return (
      <button
        className={`student-agenda-row ${item.id === next?.id ? 'is-current' : ''}`}
        key={item.id}
        onClick={() => setSelected(item)}
      >
        <span className="student-agenda-time">
          {studentTime(item.starts_at)}
          <small>{studentTime(item.ends_at)}</small>
        </span>
        <span>
          <strong>{item.subject.name}</strong>
          {item.id === next?.id && (
            <small className="student-current-note">
              {Date.parse(item.starts_at) <= now ? 'Ongoing' : 'Up next'}
            </small>
          )}
          <small>{item.room.name}</small>
          <small>{item.teacher.name}</small>
        </span>
        <ArrowRight size={17} aria-hidden="true" />
      </button>
    );
  }
  return (
    <section className="student-home" data-published-version={w.data?.version ?? ''}>
      <StudentPageHeader
        title={rooms ? 'Find your room' : alerts ? 'Schedule updates' : 'Your next class'}
        context={calendarDateLabel(w.date)}
        term={termLabel(w.data?.calendar)}
        action={
          <Link className="button button--secondary" to={`${schedulePath}&date=${w.date}`}>
            <CalendarDays size={18} aria-hidden="true" />
            View full schedule
          </Link>
        }
      />
      {schedulingSandboxEnabled && (
        <details className="student-sample-options">
          <summary>Sample options</summary>
          <p>Local synthetic data only.</p>
          {presentationEnabled && (
            <Button
              variant="secondary"
              onClick={() => w.change({ mode: 'presentation', identity: '', draft: '' })}
            >
              Open read-only presentation
            </Button>
          )}
          <Link className="button button--secondary" to="/student/schedule">
            Choose saved sample
          </Link>
        </details>
      )}
      {w.notice && (
        <p role="status" className="student-notice">
          {w.notice}
        </p>
      )}
      {w.error ? (
        <div className="student-panel" role="alert">
          <h2>
            {[401, 403].includes(w.errorStatus)
              ? 'Your schedule is not accessible'
              : 'Your timetable is unavailable'}
          </h2>
          <p>
            {[401, 403].includes(w.errorStatus)
              ? 'Your current account may not have an assigned schedule or active access. Check your university membership.'
              : 'We cannot reach your timetable right now. Try again in a moment.'}
          </p>
          <Button onClick={w.retry}>Try again</Button>
          <details>
            <summary>Request details</summary>
            <p>{w.error}</p>
          </details>
        </div>
      ) : w.loading && !w.data ? (
        <div className="student-panel student-loading" role="status" aria-busy="true">
          Loading your timetable…
          <div />
          <div />
          <div />
        </div>
      ) : !w.data || w.data.status === 'not-published' ? (
        <div className="student-panel">
          <CalendarDays aria-hidden="true" />
          <h2>No schedule available yet</h2>
          <p>
            Your schedule has not been shared for this term. If you expected classes, ask your
            university to check your enrollment and schedule access.
          </p>
          <Button variant="secondary" onClick={w.retry}>
            Check again
          </Button>
        </div>
      ) : alerts ? (
        <section className="student-panel student-alerts-panel">
          <CalendarDays className="student-alert-symbol" size={28} aria-hidden="true" />
          <h2>Changes to your classes</h2>
          {changes.length ? (
            changes.map(session)
          ) : (
            <p>No changes flagged in your current schedule.</p>
          )}
          <p className="muted">Notifications are not available. Check your schedule for changes.</p>
          {source === 'Sample schedule' && (
            <Link to="/student/announcements">Sample announcements</Link>
          )}
        </section>
      ) : rooms ? (
        <>
          {!roomDetail && (
            <label className="student-room-search">
              Search rooms
              <input
                type="search"
                placeholder="Room name or building"
                value={roomQuery}
                onChange={(e) => setRoomQuery(e.target.value)}
              />
            </label>
          )}
          <p className="muted">Rooms in your schedule · Room details are provisional.</p>
          <div className={`student-room-grid ${roomDetail ? 'is-room-detail' : ''}`}>
            {visibleRooms.map((room) => (
              <article className="student-panel" key={room.id}>
                <MapPin aria-hidden="true" />
                <h2>{room.name}</h2>
                <p>
                  {room.building}
                  {room.floor ? ` · ${room.floor}` : ''}
                </p>
                {!roomDetail && (
                  <Link
                    className="text-action"
                    to={`/student/rooms/detail?id=${encodeURIComponent(room.id)}&date=${w.date}&schedule=1`}
                  >
                    Room details <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                )}
                {roomDetail && (
                  <>
                    <Link to={`${schedulePath}&date=${w.date}`}>Back to schedule</Link>
                    <section className="student-room-classes">
                      <h3>Classes in this room</h3>
                      {records.filter((item) => item.room.id === room.id && item.date === w.date)
                        .length ? (
                        records
                          .filter((item) => item.room.id === room.id && item.date === w.date)
                          .map(session)
                      ) : (
                        <p>No classes listed for this date.</p>
                      )}
                    </section>
                  </>
                )}
              </article>
            ))}
            {!visibleRooms.length && (
              <p>
                {roomDetail
                  ? 'This classroom is not in your available timetable for this date.'
                  : 'No classrooms in the selected timetable range.'}
              </p>
            )}
            {roomDetail && <Link to={roomsPath}>All your classrooms</Link>}
          </div>
        </>
      ) : (
        <div className="student-home-grid">
          <div className="student-home-primary">
            <article className="student-next">
              <div className="student-section-heading">
                <h2>{next && Date.parse(next.starts_at) <= now ? 'In progress' : 'Next class'}</h2>
              </div>
              {next ? (
                <>
                  {next.subject.code && <p className="student-next-code">{next.subject.code}</p>}
                  <h3>
                    <button onClick={() => setSelected(next)}>
                      {next.subject.name}
                      <ArrowRight size={22} aria-hidden="true" />
                    </button>
                  </h3>
                  <p className="student-next-time">
                    {timeRange(next.starts_at, next.ends_at)}
                    <small>
                      {next.date === addDays(w.date, 1) ? 'Tomorrow · ' : ''}
                      {calendarDateLabel(next.date)}
                    </small>
                  </p>
                  <div className="student-next-location">
                    <MapPin size={20} aria-hidden="true" />
                    <div>
                      <strong>{next.room.name}</strong>
                      <span>
                        {next.room.building}
                        {next.room.floor ? ` · ${next.room.floor}` : ''}
                      </span>
                    </div>
                  </div>
                  <p className="student-instructor">
                    {next.teacher.name} · {next.section.name}
                  </p>
                  <Link
                    className="button button--primary student-room-action"
                    to={`/student/rooms/detail?id=${encodeURIComponent(next.room.id)}&date=${next.date}&schedule=1`}
                  >
                    Room details <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                  {next.changed && <p>Schedule changed</p>}
                </>
              ) : (
                <>
                  <h3>You're all caught up.</h3>
                  <p>No upcoming classes in the loaded date range.</p>
                </>
              )}
            </article>
            <section className="student-panel">
              <div className="student-section-heading">
                <h2>Today's classes</h2>
                <span>
                  {today.length} {today.length === 1 ? 'class' : 'classes'}
                </span>
              </div>
              {today.length ? (
                today.map(session)
              ) : (
                <p className="student-empty">No classes today. Your weekly overview is below.</p>
              )}
            </section>
            <section className="student-panel">
              <div className="student-section-heading">
                <h2>This week</h2>
                <Link to={`${schedulePath}&date=${w.date}`}>
                  View full schedule <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </div>
              <nav className="student-week-strip" aria-label="This week's classes">
                {days.map((day) => {
                  const count = records.filter((item) => item.date === day).length;
                  return (
                    <Link
                      key={day}
                      to={`${schedulePath}&date=${day}`}
                      aria-label={`${calendarDateLabel(day)}, ${count} classes`}
                      aria-current={day === w.date ? 'date' : undefined}
                      className={count ? '' : 'student-empty-day'}
                    >
                      <span>
                        {new Date(day + 'T00:00:00Z').toLocaleDateString('en', {
                          weekday: 'short',
                          timeZone: 'UTC',
                        })}
                      </span>
                      <strong>{Number(day.slice(-2))}</strong>
                      <small>
                        {count}
                        <span className="student-class-word">
                          {' '}
                          {count === 1 ? 'class' : 'classes'}
                        </span>
                      </small>
                    </Link>
                  );
                })}
              </nav>
            </section>
          </div>
          <aside className="student-home-secondary">
            <section className="student-panel">
              <h2>Schedule updates</h2>
              {changes.length ? (
                changes.map((item) => (
                  <div className="student-change" key={item.id}>
                    <strong>{item.subject.name} · Schedule changed</strong>
                    <p>
                      {calendarDateLabel(item.date)} · {item.room.name}
                    </p>
                    <button className="text-action" onClick={() => setSelected(item)}>
                      Review class
                    </button>
                  </div>
                ))
              ) : (
                <p>No changes flagged in your current schedule.</p>
              )}
            </section>
            <section className="student-panel student-discovery">
              <MapPin size={24} aria-hidden="true" />
              <h2>Find your room</h2>
              <p>Check room and building details before you head out.</p>
              <Link to={roomsPath}>
                Browse rooms <ArrowRight size={17} aria-hidden="true" />
              </Link>
              <small>Room availability is not confirmed.</small>
            </section>
          </aside>
        </div>
      )}
      {currentSelection && !w.error && w.data && (
        <ClassSessionDetails
          session={currentSelection}
          role="student"
          sample={schedulingSandboxEnabled || w.context.mode !== 'published'}
          presentation={w.context.mode === 'presentation'}
          published={w.context.mode === 'published' && w.data.status !== 'not-published'}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
