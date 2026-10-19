import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, MapPin } from 'lucide-react';
import { TeacherRequestOverview } from '../components/scheduling/TeacherRequestOverview';
import { Button } from '../components/ui/Button';
import { ClassSessionDetails } from '../components/scheduling/ClassSessionDetails';
import {
  addDays,
  calendarDateLabel,
  manilaTime,
  manilaToday,
  type CalendarOccurrence,
} from '../lib/calendar-model';
import { sessionRoomPath } from '../lib/session-room';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import {
  facultyDisplayName,
  presentationEnabled,
  presentationOnlyBuild,
} from '../lib/presentation-sample';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { periodLabel } from '../lib/workspace-context';
import type { UserRole } from '../types/ui';

export function RoleScheduleWorkspace({
  role,
  dashboard = false,
}: {
  role: UserRole;
  dashboard?: boolean;
}) {
  const w = useScheduleWorkspace(role, dashboard);
  const { context, change, data, records, date, loading, error } = w;
  const [expanded, setExpanded] = useState(false);
  const view = context.view ?? 'week';
  const isPresentation = context.mode === 'presentation';
  const isSample = schedulingSandboxEnabled || isPresentation;
  const settings = useRef<HTMLDetailsElement>(null);
  const [selected, setSelected] = useState<CalendarOccurrence | null>(null);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  const currentSelection = selected ? records.find((o) => o.id === selected.id) : undefined;
  const base = role === 'administrator' ? '/admin' : `/${role}`;
  const next = dashboard ? records.find((o) => Date.parse(o.ends_at) > now) : undefined;
  const agenda = records.filter(
    (o) => o.date === date && (!dashboard || Date.parse(o.ends_at) > now) && o.id !== next?.id,
  );
  const month = date.slice(0, 7),
    first = month + '-01',
    offset = (new Date(first + 'T00:00:00Z').getUTCDay() + 6) % 7;
  const count = new Date(
    Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0),
  ).getUTCDate();
  const week = addDays(date, -((new Date(date + 'T00:00:00Z').getUTCDay() + 6) % 7));
  const weekRecords = records.filter((o) => o.date >= week && o.date < addDays(week, 7));
  const minute = (v: string) => Number(v.slice(11, 13)) * 60 + Number(v.slice(14, 16));
  const begin = Math.floor(Math.min(480, ...weekRecords.map((o) => minute(o.starts_at))) / 60) * 60;
  const finish =
    Math.ceil(
      Math.max(
        1080,
        ...weekRecords.map(
          (o) => minute(o.starts_at) + (Date.parse(o.ends_at) - Date.parse(o.starts_at)) / 60000,
        ),
      ) / 60,
    ) * 60;
  const section = data?.sections.find((s) => s.id === context.identity);
  const scopeLabel =
    role === 'administrator'
      ? 'Campus timetable'
      : role === 'teacher'
        ? facultyDisplayName(
            data?.teachers.find((t) => t.id === context.identity)?.name ?? 'Choose teacher',
          )
        : (section?.custom_label ??
          (section
            ? `${section.program_id.toUpperCase()} ${section.year_level ?? ''}${section.section_letter ?? ''}`
            : 'Choose a sample'));
  function move(delta: number) {
    const d = new Date(first + 'T00:00:00Z');
    d.setUTCMonth(d.getUTCMonth() + delta);
    change({ date: d.toISOString().slice(0, 10) });
  }
  const unpublished = data?.status === 'not-published';
  return (
    <section
      className={`structured-calendar ux-calendar ${dashboard ? 'is-dashboard' : ''}`}
      data-published-version={context.mode === 'published' ? (data?.version ?? '') : ''}
    >
      {dashboard && (
        <div className="ux-day-heading">
          <p className="eyebrow">{calendarDateLabel(manilaToday())}</p>
          <h1>
            {role === 'teacher'
              ? 'Your teaching day'
              : role === 'administrator'
                ? 'Published timetable'
                : 'Your day'}
          </h1>
        </div>
      )}
      <div className="ux-context-bar">
        <span>
          {isPresentation
            ? `Read-only sample · ${scopeLabel ?? 'Loading'} · v1`
            : schedulingSandboxEnabled
              ? context.mode === 'review'
                ? `Sample · ${scopeLabel ?? 'Choose identity'} · Unpublished`
                : `Sample · ${role === 'administrator' ? 'Campus timetable' : (scopeLabel ?? 'Loading identity')}`
              : 'University timetable'}
          {loading ? ' · Loading…' : ''}
        </span>
        <details className="ux-context-settings" ref={settings}>
          <summary>Change context</summary>
          <div className="ux-context-controls">
            {context.mode !== 'review' && (
              <label>
                Academic period
                <select
                  value={context.period}
                  onChange={(e) => change({ period: e.target.value, identity: '' })}
                >
                  <option value="">Choose a period</option>
                  {w.periods.map((p) => (
                    <option key={p.id} value={p.id}>
                      {periodLabel(p)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {isSample && role !== 'administrator' && data && (
              <label>
                {role === 'teacher' ? 'Mock teacher' : 'Mock section'}
                <select
                  value={context.identity}
                  onChange={(e) => change({ identity: e.target.value })}
                >
                  {role === 'teacher'
                    ? data.teachers.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))
                    : data.sections.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.custom_label ??
                            `${s.program_id.toUpperCase()} ${s.year_level ?? ''}${s.section_letter ?? ''}`}
                        </option>
                      ))}
                </select>
              </label>
            )}
            {(schedulingSandboxEnabled || presentationEnabled) && (
              <details>
                <summary>Data source details</summary>
                <p>
                  {isPresentation
                    ? 'Versioned synthetic presentation, October–December 2026. No live synchronization or backend writes.'
                    : 'Local sample identities only. University records require verified identity.'}{' '}
                  Asia/Manila.
                </p>
                <label>
                  Schedule source
                  <select
                    value={context.mode}
                    onChange={(e) =>
                      change({
                        mode: e.target.value as 'published' | 'review' | 'presentation',
                        identity: '',
                        draft: '',
                      })
                    }
                  >
                    {!presentationOnlyBuild && (
                      <option value="published">Published timetables</option>
                    )}
                    {schedulingSandboxEnabled && (
                      <option value="review">Unpublished generated review</option>
                    )}
                    {presentationEnabled && (
                      <option value="presentation">Read-only presentation sample v1</option>
                    )}
                  </select>
                </label>
                {context.mode === 'review' && (
                  <label>
                    Generated calendar review
                    <select
                      value={context.draft}
                      onChange={(e) => change({ draft: e.target.value })}
                    >
                      <option value="">Choose a saved sample</option>
                      {w.drafts.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.title}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </details>
            )}
          </div>
        </details>
      </div>
      {w.notice && (
        <p role="status" className="ux-update">
          {w.notice}
        </p>
      )}
      {!w.connected && data && (
        <p role="status">Updates interrupted. Last confirmed timetable shown; reconnecting.</p>
      )}
      {error && (
        <div role="alert" className="workspace-card">
          <h2>Couldn't load your timetable.</h2>
          <p>
            {w.errorStatus === 403 || w.errorStatus === 401
              ? 'This timetable is not permitted for your current access. Choose an available sample.'
              : w.errorStatus === 404
                ? 'That saved sample is unavailable. Choose another sample.'
                : w.errorStatus === 422
                  ? isPresentation
                    ? 'Choose an identity included in this presentation sample.'
                    : 'This sample needs valid academic calendar dates. Ask the Administrator to review its academic setup.'
                  : 'The timetable service is unavailable. Check the connection, then retry.'}
          </p>
          <Button variant="secondary" onClick={w.retry}>
            Retry
          </Button>
          {isPresentation && (
            <Button variant="secondary" onClick={() => change({ identity: '' })}>
              Reset sample identity
            </Button>
          )}
          {schedulingSandboxEnabled && (
            <Button
              variant="secondary"
              onClick={() => {
                if (settings.current) {
                  settings.current.open = true;
                  settings.current.querySelector('summary')?.focus();
                }
              }}
            >
              Change sample
            </Button>
          )}
          {presentationEnabled && !isPresentation && (
            <Button
              variant="secondary"
              onClick={() => change({ mode: 'presentation', identity: '', draft: '' })}
            >
              Open read-only presentation
            </Button>
          )}
          <details className="ux-error-details">
            <summary>Technical details</summary>
            <p>{error}</p>
          </details>
        </div>
      )}
      {loading && !data && <p role="status">Loading your timetable…</p>}
      {!loading && !error && (unpublished || !data) && (
        <div className="workspace-card ux-empty">
          {presentationEnabled && !isPresentation && (
            <Button
              variant="secondary"
              onClick={() => change({ mode: 'presentation', identity: '', draft: '' })}
            >
              Open read-only presentation
            </Button>
          )}
          <h2>
            {unpublished
              ? 'No timetable published yet'
              : context.mode === 'review'
                ? 'No generated sample yet'
                : 'Choose an available timetable'}
          </h2>
          <p>
            {unpublished
              ? 'Change context to another sample period or open an existing generated sample.'
              : context.mode === 'review'
                ? 'An Administrator can generate and save a sample, or you can return to published timetables.'
                : 'Choose an academic period in Change context. Missing records are never replaced by invented classes.'}
          </p>
          {schedulingSandboxEnabled &&
            (context.mode === 'review' ? (
              <div className="draft-actions">
                <Button variant="secondary" onClick={() => change({ mode: 'published' })}>
                  Choose published timetable
                </Button>
                <Link to="/dev/role-preview?returnTo=/admin/ai-scheduling">Set up a sample</Link>
              </div>
            ) : (
              <Button variant="secondary" onClick={() => change({ mode: 'review' })}>
                Open a sample timetable
              </Button>
            ))}
        </div>
      )}
      {dashboard &&
        data &&
        !unpublished &&
        !error &&
        !loading &&
        !records.some((o) => o.date === date) && (
          <p className="ux-day-empty" role="status">
            No classes today.
          </p>
        )}
      {dashboard && next && !error && (
        <article
          className="ux-next-class"
          aria-label={role === 'teacher' ? 'Next teaching assignment' : 'Next class'}
        >
          <div className="ux-next-caption">
            <strong>
              {Date.parse(next.starts_at) <= now
                ? 'In progress'
                : role === 'teacher'
                  ? 'Teaching next'
                  : 'Next class'}
            </strong>
          </div>
          <h2>
            <button className="ux-subject-action" onClick={() => setSelected(next)}>
              {next.subject.name}
            </button>
          </h2>
          <div className="ux-next-time">
            <strong>
              {manilaTime(next.starts_at)}–{manilaTime(next.ends_at)}
            </strong>
            <span>{calendarDateLabel(next.date)}</span>
          </div>
          <p className="ux-next-room">
            <MapPin size={18} />
            {next.room.name}
          </p>
          <p>
            {next.room.building}
            {next.room.floor ? ` · ${next.room.floor}` : ''}
          </p>
          <p className="muted">
            {role === 'student' ? `${facultyDisplayName(next.teacher.name)} · ` : ''}
            {next.section.name}
          </p>
          {next.changed && <span className="ux-update">Schedule changed</span>}
          <div className="draft-actions">
            <Link className="button" to={base + '/schedule'}>
              Open Schedule
            </Link>
            {sessionRoomPath(role, next.room.id) && (
              <Link className="button button--secondary" to={sessionRoomPath(role, next.room.id)!}>
                Room Details
              </Link>
            )}
          </div>
        </article>
      )}
      {dashboard && data && !unpublished && !next && !loading && !error && (
        <div className="workspace-card ux-empty">
          <h2>
            {records.some((o) => o.date === manilaToday())
              ? 'You’re done for today'
              : 'No upcoming classes in this date range'}
          </h2>
          <p>Browse your schedule for other dates in this academic period.</p>
          <Link className="text-action" to={base + '/schedule'}>
            Open Schedule
          </Link>
        </div>
      )}
      {!dashboard && data && !unpublished && (
        <>
          <div className="calendar-toolbar">
            <Button variant="secondary" aria-label="Previous month" onClick={() => move(-1)}>
              <ChevronLeft size={18} />
            </Button>
            <h2>
              {new Date(first + 'T00:00:00Z').toLocaleDateString('en', {
                month: 'long',
                year: 'numeric',
                timeZone: 'UTC',
              })}
            </h2>
            <Button variant="secondary" aria-label="Next month" onClick={() => move(1)}>
              <ChevronRight size={18} />
            </Button>
            <Button variant="secondary" onClick={() => change({ date: manilaToday() })}>
              Today
            </Button>
          </div>
          <div className="calendar-view-options">
            <Button
              className="calendar-mobile-expand"
              variant="secondary"
              aria-expanded={expanded}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? 'Compact week' : 'Expand month'}
            </Button>
            <label className="calendar-desktop-view">
              View
              <select
                value={view}
                onChange={(e) => change({ view: e.target.value as 'day' | 'week' | 'month' })}
              >
                <option value="day">Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
              </select>
            </label>
          </div>
          <div
            className={`calendar-month ${expanded ? 'is-expanded' : ''} ${view !== 'month' ? 'desktop-week-view' : ''}`}
            role="group"
            aria-label="Select a date"
          >
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
              <span key={d}>{d}</span>
            ))}
            {Array.from({ length: offset }, (_, i) => (
              <span key={'blank' + i} />
            ))}
            {Array.from({ length: count }, (_, i) => {
              const d = `${month}-${String(i + 1).padStart(2, '0')}`,
                n = records.filter((o) => o.date === d).length;
              return (
                <button
                  key={d}
                  aria-pressed={d === date}
                  aria-label={`${calendarDateLabel(d)}, ${n} classes`}
                  onClick={() => change({ date: d })}
                >
                  <time dateTime={d}>{i + 1}</time>
                  {n > 0 && <span className="calendar-dot" />}
                </button>
              );
            })}
          </div>
          <div className="ux-week-navigation">
            <Button
              variant="ghost"
              aria-label="Previous week"
              onClick={() => change({ date: addDays(date, -7) })}
            >
              <ChevronLeft size={16} />
            </Button>
            <div className="calendar-week-strip" role="group" aria-label="Selected week">
              {Array.from({ length: 7 }, (_, i) => {
                const d = addDays(week, i);
                return (
                  <button
                    key={d}
                    aria-label={calendarDateLabel(d)}
                    aria-pressed={d === date}
                    onClick={() => change({ date: d })}
                  >
                    <span>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i]}</span>
                    <strong>{Number(d.slice(-2))}</strong>
                    {records.some((o) => o.date === d) && <span className="calendar-dot" />}
                  </button>
                );
              })}
            </div>
            <Button
              variant="ghost"
              aria-label="Next week"
              onClick={() => change({ date: addDays(date, 7) })}
            >
              <ChevronRight size={16} />
            </Button>
          </div>
          {view === 'week' && (
            <div className="calendar-week-grid" role="region" aria-label="Weekly timetable">
              <div className="calendar-hour-axis" aria-hidden="true">
                <strong>Time</strong>
                <div style={{ height: finish - begin }}>
                  {Array.from({ length: (finish - begin) / 60 + 1 }, (_, i) => (
                    <span key={i} style={{ top: i * 60 }}>
                      {String(begin / 60 + i).padStart(2, '0')}:00
                    </span>
                  ))}
                </div>
              </div>
              {Array.from({ length: 7 }, (_, i) => {
                const d = addDays(week, i);
                return (
                  <div key={d}>
                    <button
                      className="calendar-week-heading"
                      aria-pressed={d === date}
                      onClick={() => change({ date: d })}
                    >
                      {calendarDateLabel(d)}
                    </button>
                    <div className="calendar-time-track" style={{ height: finish - begin }}>
                      {weekRecords
                        .filter((o) => o.date === d)
                        .map((o) => (
                          <button
                            className="calendar-time-block"
                            key={o.id}
                            style={{
                              top: minute(o.starts_at) - begin,
                              height: (Date.parse(o.ends_at) - Date.parse(o.starts_at)) / 60000,
                            }}
                            onClick={() => setSelected(o)}
                          >
                            <span>
                              {manilaTime(o.starts_at)}–{manilaTime(o.ends_at)}
                            </span>
                            <strong>{o.subject.name}</strong>
                            <small>{o.room.name}</small>
                          </button>
                        ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
      {data && !unpublished && !error && (!dashboard || agenda.length > 0) && (
        <section className="ux-agenda" aria-live="polite">
          <div className="ux-section-heading">
            <h2>{dashboard ? 'Remaining today' : calendarDateLabel(date)}</h2>
            {dashboard && <Link to={base + '/schedule'}>Full schedule</Link>}
          </div>
          {loading ? (
            <p role="status">Loading selected day…</p>
          ) : agenda.length ? (
            agenda.map((o) => (
              <button className="ux-agenda-row" key={o.id} onClick={() => setSelected(o)}>
                <span className="ux-agenda-time">
                  {manilaTime(o.starts_at)}
                  <small>{manilaTime(o.ends_at)}</small>
                </span>
                <span>
                  <strong>{o.subject.name}</strong>
                  <span>
                    {o.room.name}
                    {!dashboard ? ` · ${facultyDisplayName(o.teacher.name)}` : ''}
                  </span>
                  {o.changed && <small className="ux-update">Schedule changed</small>}
                </span>
                <ChevronRight size={16} />
              </button>
            ))
          ) : (
            <p className="muted">
              {dashboard
                ? records.some((o) => o.date === date)
                  ? 'Nothing else today.'
                  : 'No classes today.'
                : 'No classes on this date.'}
            </p>
          )}
        </section>
      )}
      {role === 'teacher' && dashboard && <TeacherRequestOverview />}
      {currentSelection && (
        <ClassSessionDetails
          session={currentSelection}
          role={role}
          sample={isSample}
          presentation={isPresentation}
          published={context.mode === 'published'}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
