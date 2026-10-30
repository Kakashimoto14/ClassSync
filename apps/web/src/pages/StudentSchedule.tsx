import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import {
  addDays,
  calendarDateLabel,
  manilaToday,
  type CalendarOccurrence,
} from '../lib/calendar-model';
import { studentOccurrence, studentTime, termLabel, timeRange } from '../lib/student-presentation';
import { periodLabel } from '../lib/workspace-context';
import { presentationEnabled, presentationOnlyBuild } from '../lib/presentation-sample';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { ClassSessionDetails } from '../components/scheduling/ClassSessionDetails';
import { Button } from '../components/ui/Button';
import { StudentPageHeader } from '../components/ui/StudentPageHeader';
import './student-schedule.css';

export function StudentSchedule() {
  const w = useScheduleWorkspace('student');
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    if (!params.has('date')) {
      const canonical = new URLSearchParams(params);
      canonical.set('date', w.date);
      setParams(canonical, { replace: true });
    }
  }, [params, setParams, w.date]);
  const [selected, setSelected] = useState<CalendarOccurrence | null>(null);
  const records = w.records
    .map(studentOccurrence)
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const current = selected ? records.find((item) => item.id === selected.id) : undefined;
  const monday = addDays(w.date, -((new Date(w.date + 'T00:00:00Z').getUTCDay() + 6) % 7));
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const week = records.filter((item) => days.includes(item.date));
  const agenda = records.filter((item) => item.date === w.date);
  const view = w.context.view ?? 'week';
  const monthStart = w.date.slice(0, 7) + '-01';
  const monthCount = new Date(
    Date.UTC(Number(w.date.slice(0, 4)), Number(w.date.slice(5, 7)), 0),
  ).getUTCDate();
  function move(direction: number) {
    const date =
      view === 'month'
        ? new Date(
            Date.UTC(Number(w.date.slice(0, 4)), Number(w.date.slice(5, 7)) - 1 + direction, 1),
          )
            .toISOString()
            .slice(0, 10)
        : addDays(w.date, direction * (view === 'day' ? 1 : 7));
    w.change({ date });
  }
  const sample = w.context.mode !== 'published' || schedulingSandboxEnabled;
  const minutes = (value: string) => {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Manila',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(new Date(value));
    return (
      Number(parts.find((part) => part.type === 'hour')?.value) * 60 +
      Number(parts.find((part) => part.type === 'minute')?.value)
    );
  };
  const duration = (item: CalendarOccurrence) =>
    (Date.parse(item.ends_at) - Date.parse(item.starts_at)) / 60000;
  const start = Math.floor(Math.min(480, ...week.map((item) => minutes(item.starts_at))) / 60) * 60;
  const end =
    Math.ceil(
      Math.max(
        week.length ? 0 : 1020,
        ...week.map((item) => minutes(item.starts_at) + duration(item)),
      ) / 60,
    ) * 60;
  const hours = Array.from({ length: (end - start) / 60 }, (_, i) => start + i * 60);
  const event = (item: CalendarOccurrence, grid = false) => (
    <button
      key={item.id}
      className={grid ? 'student-calendar-event' : 'student-agenda-row ux-agenda-row'}
      onClick={() => setSelected(item)}
      style={
        grid
          ? {
              top: `${(minutes(item.starts_at) - start) * 1.5}px`,
              minHeight: Math.min(44, duration(item) * 1.5 - 4),
              height: duration(item) * 1.5 - 4,
            }
          : undefined
      }
    >
      <span className="student-agenda-time">{timeRange(item.starts_at, item.ends_at)}</span>
      <span>
        <strong>{item.subject.name}</strong>
        <small>{item.room.name}</small>
        <small className="student-calendar-instructor">{item.teacher.name}</small>
      </span>
    </button>
  );
  return (
    <section
      className="student-schedule student-home"
      data-published-version={w.data?.version ?? ''}
    >
      <StudentPageHeader title="My Schedule" term={termLabel(w.data?.calendar)} />
      <div className="student-view-tabs" role="group" aria-label="Calendar views">
        {(['day', 'week', 'month'] as const).map((option) => (
          <button
            key={option}
            aria-pressed={view === option}
            onClick={() => w.change({ view: option })}
          >
            {option[0].toUpperCase() + option.slice(1)}
          </button>
        ))}
      </div>
      <div className="student-calendar-toolbar">
        <div>
          <Button
            variant="secondary"
            aria-label={`Previous ${view === 'month' ? 'month' : view === 'day' ? 'day' : 'week'}`}
            onClick={() => move(-1)}
          >
            <ChevronLeft size={18} />
          </Button>
          <strong>
            {view === 'month'
              ? new Date(w.date + 'T00:00:00Z').toLocaleDateString('en', {
                  month: 'long',
                  year: 'numeric',
                  timeZone: 'UTC',
                })
              : view === 'day'
                ? calendarDateLabel(w.date)
                : `${calendarDateLabel(monday)} – ${calendarDateLabel(addDays(monday, 6))}`}
          </strong>
          <Button
            variant="secondary"
            aria-label={`Next ${view === 'month' ? 'month' : view === 'day' ? 'day' : 'week'}`}
            onClick={() => move(1)}
          >
            <ChevronRight size={18} />
          </Button>
        </div>
        <Button variant="secondary" onClick={() => w.change({ date: manilaToday() })}>
          Today
        </Button>
      </div>
      <details className="student-schedule-options">
        <summary>Schedule options</summary>
        <label>
          Academic period
          <select
            value={w.context.period}
            onChange={(e) => w.change({ period: e.target.value, identity: '' })}
          >
            {w.periods.map((period) => (
              <option key={period.id} value={period.id}>
                {periodLabel(period)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Calendar view
          <select
            value={view}
            onChange={(e) => w.change({ view: e.target.value as 'day' | 'week' | 'month' })}
          >
            <option value="week">Week</option>
            <option value="day">Day</option>
            <option value="month">Month</option>
          </select>
        </label>
        {sample && (
          <details className="student-preview-tools">
            <summary>Preview tools</summary>
            {w.data && (
              <label>
                Sample section
                <select
                  value={w.context.identity}
                  onChange={(e) => w.change({ identity: e.target.value })}
                >
                  {w.data.sections.map((section) => (
                    <option key={section.id} value={section.id}>
                      {section.custom_label ??
                        `${section.program_id.toUpperCase()} ${section.year_level ?? ''}${section.section_letter ?? ''}`}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {presentationEnabled && !presentationOnlyBuild && (
              <Button
                variant="secondary"
                onClick={() => w.change({ mode: 'presentation', identity: '', draft: '' })}
              >
                Open sample schedule
              </Button>
            )}
            {schedulingSandboxEnabled && !presentationOnlyBuild && (
              <>
                <Button
                  variant="secondary"
                  onClick={() => w.change({ mode: 'published', identity: '', draft: '' })}
                >
                  Use local published schedule
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => w.change({ mode: 'review', draft: '', identity: '' })}
                >
                  Choose saved sample
                </Button>
                <label>
                  Saved sample
                  <select
                    value={w.context.draft}
                    onChange={(e) => {
                      if (e.target.value !== w.context.draft)
                        w.change({ mode: 'review', draft: e.target.value, identity: '' });
                    }}
                  >
                    <option value="">Choose a sample</option>
                    {w.drafts.map((draft) => (
                      <option key={draft.id} value={draft.id}>
                        {draft.title}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
          </details>
        )}
      </details>
      <nav className="student-week-strip" aria-label="Select a day">
        {days.map((day) => (
          <a
            key={day}
            href={`?period=${encodeURIComponent(w.context.period)}&date=${day}`}
            onClick={(e) => {
              e.preventDefault();
              w.change({ date: day });
            }}
            aria-current={day === w.date ? 'date' : undefined}
            aria-label={calendarDateLabel(day)}
          >
            <span>
              {new Date(day + 'T00:00:00Z').toLocaleDateString('en', {
                weekday: 'short',
                timeZone: 'UTC',
              })}
            </span>
            <strong>{Number(day.slice(-2))}</strong>
            <small>
              {records.filter((item) => item.date === day).length}
              <span className="student-class-word"> classes</span>
            </small>
          </a>
        ))}
      </nav>
      {w.error ? (
        <section className="student-panel" role="alert">
          <h2>
            {[401, 403].includes(w.errorStatus)
              ? 'Your schedule is not accessible'
              : 'Your schedule is unavailable'}
          </h2>
          <p>
            {[401, 403].includes(w.errorStatus)
              ? 'Check your university access and assigned schedule.'
              : 'We cannot reach your schedule. Check your connection and try again.'}
          </p>
          <Button onClick={w.retry}>Try again</Button>
        </section>
      ) : w.loading ? (
        <p role="status" aria-busy="true">
          Loading your schedule…
        </p>
      ) : !w.data || w.data.status === 'not-published' ? (
        <section className="student-panel">
          <h2>No schedule available yet</h2>
          <p>Your schedule has not been shared for this term.</p>
          <Button onClick={w.retry}>Check again</Button>
        </section>
      ) : (
        <>
          {w.notice && <p role="status">{w.notice}</p>}
          {view === 'month' && (
            <nav className="student-month-grid" aria-label="Month dates">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
                <span className="student-month-label" key={day}>
                  {day}
                </span>
              ))}
              {Array.from(
                { length: (new Date(monthStart + 'T00:00:00Z').getUTCDay() + 6) % 7 },
                (_, index) => (
                  <span key={`blank-${index}`} aria-hidden="true" />
                ),
              )}
              {Array.from({ length: monthCount }, (_, index) => addDays(monthStart, index)).map(
                (day) => {
                  const count = records.filter((item) => item.date === day).length;
                  return (
                    <button
                      key={day}
                      aria-label={`${calendarDateLabel(day)}, ${count} classes`}
                      aria-pressed={day === w.date}
                      onClick={() => w.change({ date: day })}
                    >
                      <time dateTime={day}>{Number(day.slice(-2))}</time>
                      {count > 0 && <span className="student-month-dot" aria-hidden="true" />}
                    </button>
                  );
                },
              )}
            </nav>
          )}
          {view === 'week' && (
            <div className="student-calendar-desktop" aria-label="Weekly schedule">
              <div className="student-calendar-head">
                <span>Time</span>
                {days.map((day) => (
                  <button
                    key={day}
                    onClick={() => w.change({ date: day })}
                    aria-current={day === manilaToday() ? 'date' : undefined}
                  >
                    {calendarDateLabel(day)}
                  </button>
                ))}
              </div>
              <div className="student-calendar-grid" style={{ height: (end - start) * 1.5 }}>
                <div className="student-calendar-hours">
                  {hours.map((minute) => (
                    <span key={minute} style={{ top: (minute - start) * 1.5 }}>
                      {studentTime(
                        `2026-10-26T${String(Math.floor(minute / 60)).padStart(2, '0')}:00:00+08:00`,
                      )}
                    </span>
                  ))}
                </div>
                {days.map((day) => (
                  <div className="student-calendar-day" key={day}>
                    {week.filter((item) => item.date === day).map((item) => event(item, true))}
                  </div>
                ))}
              </div>
            </div>
          )}
          <section className="student-panel student-calendar-agenda">
            <h2>
              {calendarDateLabel(w.date)}{' '}
              <span className="muted">
                · {agenda.length} {agenda.length === 1 ? 'class' : 'classes'}
              </span>
            </h2>
            {agenda.length ? agenda.map((item) => event(item)) : <p>No classes on this day.</p>}
          </section>
        </>
      )}
      {current && !w.error && w.data && (
        <ClassSessionDetails
          session={current}
          role="student"
          sample={sample}
          presentation={w.context.mode === 'presentation'}
          published={w.context.mode === 'published'}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
