import { Link } from 'react-router-dom';
import type { PreviewRequest, ScheduleOccurrence } from '../../data/schedule-preview';
import { formatPreviewDate, formatTimeRange } from '../../lib/schedule-preview';
import { rolePath } from '../../routes/route-config';
import { StatusBadge } from '../ui/StatusBadge';

export function RequestSummary({
  request,
  assignment,
  role,
  link = true,
}: {
  request: PreviewRequest;
  assignment?: ScheduleOccurrence;
  role: 'teacher' | 'administrator';
  link?: boolean;
}) {
  const labels = { pending: 'Pending review', approved: 'Approved', declined: 'Declined' };
  return (
    <article className="request-summary" data-request-id={request.id}>
      <StatusBadge
        tone={
          request.status === 'pending'
            ? 'warning'
            : request.status === 'approved'
              ? 'success'
              : 'neutral'
        }
      >
        {labels[request.status]}
      </StatusBadge>
      <h3>{assignment?.subject.name ?? 'Assignment unavailable'}</h3>
      {assignment && (
        <p>
          {assignment.section.name} · {formatPreviewDate(assignment.startsAt)} ·{' '}
          {formatTimeRange(assignment)}
          <br />
          {assignment.room.name} · {assignment.teacher.name}
        </p>
      )}
      <p>{request.reason}</p>
      <small>
        Updated {formatPreviewDate(request.updatedAt)} · {request.updatedAt.slice(11, 16)}
      </small>
      {link && (
        <Link
          className="text-action"
          to={`${rolePath(role, 'request-detail')}?id=${encodeURIComponent(request.id)}`}
          aria-label={`View request: ${assignment?.subject.name ?? request.id}`}
        >
          View request
        </Link>
      )}
    </article>
  );
}
