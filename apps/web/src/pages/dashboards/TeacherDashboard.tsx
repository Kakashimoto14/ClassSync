import { Link } from 'react-router-dom';
import {
  previewContext,
  previewProfiles,
  previewViewer,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import {
  formatPreviewDate,
  remainingAfterSummary,
  selectAssignments,
  selectRequests,
  selectUpdates,
  summarizeDay,
} from '../../lib/schedule-preview';
import { NextClassSummary } from '../../components/scheduling/NextClassSummary';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { RequestSummary } from '../../components/scheduling/RequestSummary';
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
  const remaining = remainingAfterSummary(schedule);
  const requests = data ? selectRequests(data, previewProfiles.teacher.id) : [];
  const pending = requests.filter((item) => item.status === 'pending').length;
  return (
    <div className="teacher-dashboard">
      <header className="operations-heading">
        <h1>Your teaching day</h1>
        <p>
          Sample day · {formatPreviewDate(reference)} · {reference.slice(11, 16)}
        </p>
      </header>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <NextClassSummary
            schedule={schedule}
            title="Next teaching assignment"
            showPublication
            action={{ to: rolePath('teacher', 'schedule'), label: 'View teaching schedule' }}
          />
          {remaining.length > 0 && (
            <ScheduleAgenda
              title="Remaining teaching agenda"
              occurrences={remaining}
              emptyMessage="No other teaching assignments today"
            />
          )}
        </div>
        <aside className="dashboard-secondary">
          <section className="dashboard-panel" aria-label="Requests and decisions">
            <div className="section-head">
              <h2>Requests & decisions</h2>
              {data && <span className="muted">{pending} pending</span>}
            </div>
            {!data ? (
              <p>Request data unavailable.</p>
            ) : !requests.length ? (
              <p>No requests in this demo.</p>
            ) : (
              <ul className="request-summary-list">
                {requests.map((request) => (
                  <li key={request.id}>
                    <RequestSummary
                      request={request}
                      assignment={assignments?.find((item) => item.id === request.assignmentId)}
                      role="teacher"
                    />
                  </li>
                ))}
              </ul>
            )}
            <Link className="text-action" to={rolePath('teacher', 'requests')}>
              All requests
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
          <p className="demo-footnote">
            Fixed demo time and sample assignments. Official changes require administrator review.
          </p>
        </aside>
      </div>
    </div>
  );
}
