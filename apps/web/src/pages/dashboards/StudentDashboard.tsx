import { Link } from 'react-router-dom';
import {
  previewContext,
  previewViewer,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import {
  formatPreviewDate,
  selectAssignments,
  selectUpdates,
  summarizeDay,
} from '../../lib/schedule-preview';
import { NextClassSummary } from '../../components/scheduling/NextClassSummary';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { rolePath } from '../../routes/route-config';
import { ScheduleUpdates } from './DashboardSupport';

export function StudentDashboard({
  data,
  reference = previewContext.reference,
}: {
  data: SchedulePreviewData | null;
  reference?: string;
}) {
  const assignments = selectAssignments(data, previewViewer('student'));
  const schedule = summarizeDay(assignments, reference);
  // The summary already presents the current/next assignments. Keep every other
  // remaining record, including a simultaneous assignment, visible in the agenda.
  const featured = new Set([...schedule.current.map((item) => item.id), schedule.next?.id]);
  const laterToday = schedule.remaining.filter((item) => !featured.has(item.id));
  return (
    <div className="student-dashboard">
      <header className="student-dashboard__heading">
        <h1>Your day</h1>
        <p>
          Sample day · {formatPreviewDate(reference)} · {reference.slice(11, 16)}
        </p>
      </header>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <NextClassSummary
            schedule={schedule}
            action={{ to: rolePath('student', 'schedule'), label: 'View my schedule' }}
          />
          {laterToday.length > 0 && (
            <ScheduleAgenda
              title="Later today"
              occurrences={laterToday}
              emptyMessage="No other classes today"
            />
          )}
        </div>
        <aside className="dashboard-secondary">
          {data && assignments && (
            <ScheduleUpdates updates={selectUpdates(data, assignments)} role="student" />
          )}
          <section className="dashboard-section">
            <h2>Explore</h2>
            <nav aria-label="Student dashboard actions" className="dashboard-actions">
              <Link className="text-action" to={rolePath('student', 'rooms')}>
                Room directory
              </Link>
              <Link className="text-action" to={rolePath('student', 'calendar')}>
                My calendar
              </Link>
            </nav>
          </section>
          <p className="student-demo-note">
            Fixed demo time. These are sample assignments, not a live schedule.
          </p>
        </aside>
      </div>
    </div>
  );
}
