import { useId } from 'react';
import { CalendarDays, MapPin } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { DaySchedule } from '../../lib/schedule-preview';
import { Alert } from '../ui/Alert';
import { EmptyState } from '../ui/EmptyState';
import { ScheduleEntry } from './ScheduleEntry';

export function NextClassSummary({
  schedule,
  title = 'Next class',
  action,
  showPublication = false,
  roomAction,
}: {
  schedule: DaySchedule;
  title?: string;
  action?: { to: string; label: string };
  showPublication?: boolean;
  roomAction?: string;
}) {
  const titleId = useId();
  const unavailable = schedule.state === 'unavailable' || schedule.state === 'unpublished';
  return (
    <section className="next-class" aria-labelledby={titleId}>
      <h2 id={titleId}>{title}</h2>
      {unavailable ? (
        <EmptyState
          title={
            schedule.state === 'unavailable' ? 'Schedule unavailable' : 'Schedule not published'
          }
          detail={
            schedule.state === 'unavailable'
              ? 'Assignment data is missing. No next class can be determined.'
              : 'A draft is not an assigned class. Published assignments will appear here.'
          }
        />
      ) : (
        <>
          {schedule.state === 'no-classes' && (
            <p className="schedule-state">No classes today in this demo.</p>
          )}
          {schedule.state === 'finished' && (
            <p className="schedule-state">All of today’s classes have finished in this demo.</p>
          )}
          {schedule.current.length > 0 && (
            <div className="current-classes">
              <h3>In progress at the demo time</h3>
              {schedule.current.map((item) => (
                <ScheduleEntry
                  key={item.id}
                  occurrence={item}
                  featured
                  showPublication={showPublication}
                />
              ))}
            </div>
          )}
          {schedule.current.length > 1 && (
            <Alert tone="warning" title="Overlapping assignments">
              More than one class is in progress in these records. Review the schedule; no conflict
              resolution has been applied.
            </Alert>
          )}
          {schedule.next ? (
            <ScheduleEntry
              occurrence={schedule.next}
              featured
              showDate={schedule.next.startsAt.slice(0, 10) !== schedule.reference.slice(0, 10)}
              showPublication={showPublication}
            />
          ) : (
            <p className="muted">No upcoming published class in the available records.</p>
          )}
          {schedule.simultaneousNext.length > 1 && (
            <Alert tone="warning" title="Multiple classes start together">
              The next start time has more than one assignment. Check the agenda before choosing a
              classroom.
            </Alert>
          )}
        </>
      )}
      <div className="next-class__actions">
        {action && (
          <Link className="button next-class__action" to={action.to} aria-label={action.label}>
            <CalendarDays size={18} aria-hidden="true" /> Schedule
          </Link>
        )}
        {roomAction && !unavailable && (
          <Link className="button button--secondary" to={roomAction} aria-label="View room details">
            <MapPin size={18} aria-hidden="true" /> Room details
          </Link>
        )}
      </div>
    </section>
  );
}
