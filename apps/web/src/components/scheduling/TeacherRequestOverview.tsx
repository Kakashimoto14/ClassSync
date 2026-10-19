import { Link } from 'react-router-dom';
import { previewProfiles, schedulePreview } from '../../data/schedule-preview';
import { selectRequests } from '../../lib/schedule-preview';
import { RequestSummary } from './RequestSummary';
export function TeacherRequestOverview() {
  const requests = selectRequests(schedulePreview, previewProfiles.teacher.id);
  const pending = requests.filter((r) => r.status === 'pending');
  const decisions = requests.filter((r) => r.status !== 'pending');
  return (
    <section className="ux-request-link">
      <div className="ux-section-heading">
        <h2>Requests and decisions</h2>
        <span className="source-label">Separate demonstration records</span>
      </div>
      {pending.slice(0, 1).map((r) => (
        <RequestSummary
          key={r.id}
          request={r}
          role="teacher"
          compact
          assignment={schedulePreview.occurrences.find((o) => o.id === r.assignmentId)}
        />
      ))}
      <details>
        <summary>Recent demonstration decisions · {decisions.length}</summary>
        {decisions.slice(0, 2).map((r) => (
          <RequestSummary
            key={r.id}
            request={r}
            role="teacher"
            compact
            assignment={schedulePreview.occurrences.find((o) => o.id === r.assignmentId)}
          />
        ))}
      </details>
      <Link className="button button--secondary" to="/teacher/change-requests">
        Review requests and status
      </Link>
      <details>
        <summary>About these request records</summary>
        <p>
          Fixed demonstration, separate from your selected mock faculty timetable. Live submission
          and decisions are not connected.
        </p>
      </details>
    </section>
  );
}
