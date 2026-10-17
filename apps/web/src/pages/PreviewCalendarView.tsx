import { useState } from 'react';
import { Button } from '../components/ui/Button';
import { ScheduleAgenda } from '../components/scheduling/ScheduleAgenda';
import { previewContext, previewViewer, schedulePreview } from '../data/schedule-preview';
import { formatPreviewDate, onDay, selectAssignments } from '../lib/schedule-preview';
import type { UserRole } from '../types/ui';

/** Date-only browsing of supplied occurrences; no institutional clock or calendar sync. */
export function PreviewCalendarView({ role }: { role: UserRole }) {
  const [selectedDate, setSelectedDate] = useState(previewContext.reference.slice(0, 10));
  const [month, setMonth] = useState(() => new Date(`${selectedDate.slice(0, 7)}-01T00:00:00Z`));
  const records = (selectAssignments(schedulePreview, previewViewer(role)) ?? []).filter(
    (item) => role === 'administrator' || item.publication === 'published',
  );
  const monthLabel = month.toLocaleDateString('en', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const count = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0)).getUTCDate();
  const offset = (month.getUTCDay() + 6) % 7;
  const days: (number | null)[] = [
    ...Array<null>(offset).fill(null),
    ...Array.from({ length: count }, (_, i) => i + 1),
  ];
  function changeMonth(delta: number) {
    const next = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + delta, 1));
    setMonth(next);
    setSelectedDate(next.toISOString().slice(0, 10));
  }
  return (
    <section className="preview-records preview-calendar">
      <p className="muted">
        Supplied demo dates only ·{' '}
        {role === 'administrator' ? 'Includes drafts.' : 'Published assignments.'}
      </p>
      <div className="workspace-card">
        <div className="calendar-head">
          <Button variant="secondary" aria-label="Previous month" onClick={() => changeMonth(-1)}>
            ‹
          </Button>
          <h2 aria-live="polite">{monthLabel}</h2>
          <Button variant="secondary" aria-label="Next month" onClick={() => changeMonth(1)}>
            ›
          </Button>
        </div>
        <div className="preview-calendar__days" role="group" aria-label={monthLabel}>
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
            <span className="calendar-weekday" key={day}>
              {day}
            </span>
          ))}
          {days.map((day, index) => {
            if (!day) return <span key={`blank-${index}`} aria-hidden="true" />;
            const date = `${month.toISOString().slice(0, 7)}-${String(day).padStart(2, '0')}`;
            const classes = records.filter((item) => onDay(item, date)).length;
            return (
              <button
                key={date}
                type="button"
                aria-label={`${formatPreviewDate(date)}, ${classes} recorded ${classes === 1 ? 'class' : 'classes'}`}
                aria-pressed={selectedDate === date}
                onClick={() => setSelectedDate(date)}
              >
                <time dateTime={date}>{day}</time>
                {classes > 0 && (
                  <span className="preview-calendar__count" aria-hidden="true">
                    {classes}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <p className="muted preview-calendar__legend">
          Numbers indicate recorded classes. Select a date to view its agenda.
        </p>
      </div>
      <div aria-live="polite">
        <ScheduleAgenda
          title={formatPreviewDate(selectedDate)}
          occurrences={records.filter((item) => onDay(item, selectedDate))}
          emptyMessage="No recorded classes on this date"
          showPublication
        />
      </div>
    </section>
  );
}
