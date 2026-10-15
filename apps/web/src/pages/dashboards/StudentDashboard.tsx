import { Link } from 'react-router-dom';
import {
  previewContext,
  previewViewer,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import { selectAssignments, selectUpdates, summarizeDay } from '../../lib/schedule-preview';
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
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Student</p>
          <h1>Your day</h1>
        </div>
        <Link className="text-action" to={rolePath('student', 'schedule')}>
          My schedule
        </Link>
      </div>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <NextClassSummary schedule={schedule} />
          {schedule.state !== 'unavailable' && schedule.state !== 'unpublished' && (
            <ScheduleAgenda
              title="Today’s remaining classes"
              occurrences={schedule.remaining}
              emptyMessage={
                schedule.state === 'finished'
                  ? 'Your class day is complete'
                  : 'No classes remaining today'
              }
            />
          )}
        </div>
        <aside className="dashboard-secondary">
          {data && assignments && (
            <ScheduleUpdates updates={selectUpdates(data, assignments)} role="student" />
          )}
          <section className="dashboard-section">
            <h2>Useful links</h2>
            <nav aria-label="Student dashboard actions" className="dashboard-actions">
              <Link className="text-action" to={rolePath('student', 'rooms')}>
                Room directory
              </Link>
              <Link className="text-action" to={rolePath('student', 'calendar')}>
                My calendar
              </Link>
            </nav>
          </section>
        </aside>
      </div>
    </>
  );
}
