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
  compact = false,
}: {
  request: PreviewRequest;
  assignment?: ScheduleOccurrence;
  role: 'teacher' | 'administrator';
  link?: boolean;
  compact?: boolean;
}) {
  const labels = { pending: 'Pending review', approved: 'Approved', declined: 'Declined' };
  return (
    <article
      className={`request-summary${compact ? ' request-summary--compact' : ''}`}
      data-request-id={request.id}
    >
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
      {assignment && !compact && (
        <p>
          {assignment.section.name} · {formatPreviewDate(assignment.startsAt)} ·{' '}
          {formatTimeRange(assignment)}
          <br />
          {assignment.room.name} · {assignment.teacher.name}
        </p>
      )}
      <p>
        {compact && assignment
          ? `${assignment.section.name} · ${assignment.room.name}`
          : request.reason}
      </p>
      {compact && assignment && <p className="request-summary__reason">{request.reason}</p>}
      {!compact && (
        <small>
          Updated {formatPreviewDate(request.updatedAt)} · {request.updatedAt.slice(11, 16)}
        </small>
      )}
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
