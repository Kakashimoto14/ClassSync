import { Link } from 'react-router-dom';
import {
  previewContext,
  previewProfiles,
  previewViewer,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import {
  formatPreviewDate,
  selectAssignments,
  selectRequests,
  selectUpdates,
  summarizeDay,
} from '../../lib/schedule-preview';
import { NextClassSummary } from '../../components/scheduling/NextClassSummary';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { rolePath } from '../../routes/route-config';
import { ScheduleUpdates } from './DashboardSupport';

export function TeacherDashboard({
  data,
  reference = previewContext.reference,
}: {
  data: SchedulePreviewData | null;
  reference?: string;
}) {
  const assignments = selectAssignments(data, previewViewer('teacher'));
  const schedule = summarizeDay(assignments, reference);
  const requests = data ? selectRequests(data, previewProfiles.teacher.id) : [];
  const pending = requests.filter((item) => item.status === 'pending').length;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Teacher</p>
          <h1>Your teaching day</h1>
        </div>
        <Link className="text-action" to={rolePath('teacher', 'schedule')}>
          Teaching schedule
        </Link>
      </div>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <NextClassSummary schedule={schedule} title="Next teaching assignment" />
          {schedule.state !== 'unavailable' && schedule.state !== 'unpublished' && (
            <ScheduleAgenda
              title="Today’s teaching agenda"
              occurrences={schedule.today}
              emptyMessage="No teaching assignments today"
            />
          )}
        </div>
        <aside className="dashboard-secondary">
          <section className="dashboard-section" aria-label="Your requests">
            <div className="section-head">
              <h2>Your requests</h2>
              {data && <span className="muted">{pending} pending</span>}
            </div>
            {!data ? (
              <p className="muted">Request data is unavailable.</p>
            ) : !requests.length ? (
              <p className="muted">No requests in this demo.</p>
            ) : (
              <ul className="dashboard-updates">
                {requests.map((request) => {
                  const assignment = assignments?.find((item) => item.id === request.assignmentId);
                  return (
                    <li key={request.id}>
                      <StatusBadge tone={request.status === 'pending' ? 'warning' : 'neutral'}>
                        {request.status === 'pending' ? 'Pending review' : 'Declined'}
                      </StatusBadge>
                      <strong>{assignment?.subject.name ?? 'Assignment unavailable'}</strong>
                      <p>{request.reason}</p>
                      <small>
                        {formatPreviewDate(request.updatedAt)} · {request.updatedAt.slice(11, 16)}
                      </small>
                    </li>
                  );
                })}
              </ul>
            )}
            <Link className="text-action" to={rolePath('teacher', 'requests')}>
              View requests
            </Link>
          </section>
          {data && assignments && (
            <ScheduleUpdates updates={selectUpdates(data, assignments)} role="teacher" />
          )}
          <nav aria-label="Teacher dashboard actions" className="dashboard-actions">
            <Link className="text-action" to={rolePath('teacher', 'request-create')}>
              Request a room change
            </Link>
            <Link className="text-action" to={rolePath('teacher', 'report-issue')}>
              Report an issue
            </Link>
          </nav>
        </aside>
      </div>
    </>
  );
}
