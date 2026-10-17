import { CalendarDays, TriangleAlert, ClipboardList, DoorOpen } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  previewContext,
  type PreviewRequest,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import {
  summarizeAdministration,
  formatPreviewDate,
  formatTimeRange,
} from '../../lib/schedule-preview';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { AttentionQueue, type AttentionItem } from '../../components/scheduling/AttentionQueue';
import { RequestSummary } from '../../components/scheduling/RequestSummary';
import { EmptyState } from '../../components/ui/EmptyState';
import { rolePath } from '../../routes/route-config';
import { ResourceOverview } from './ResourceOverview';

export function AdministratorDashboard({
  data,
  reference = previewContext.reference,
}: {
  data: SchedulePreviewData | null;
  reference?: string;
}) {
  const summary = summarizeAdministration(data, reference);
  const issues: AttentionItem[] =
    summary?.conflicts.map((conflict) => {
      const assignment = data?.occurrences.find((item) => item.id === conflict.assignmentIds[0]);
      return {
        id: conflict.id,
        title: assignment?.room.name ?? 'Room assignment conflict',
        context: assignment
          ? `${assignment.room.building}${assignment.room.floor ? ` · ${assignment.room.floor}` : ''} · ${formatTimeRange(assignment)}`
          : undefined,
        detail: conflict.reason,
        status: 'Blocking conflict',
        href: `${rolePath('administrator', 'conflict-detail')}?id=${encodeURIComponent(conflict.id)}`,
        action: 'Review conflict',
      };
    }) ?? [];
  return (
    <div className="admin-dashboard">
      <header className="operations-heading">
        <h1>Scheduling overview</h1>
        <p>
          Sample day · {formatPreviewDate(reference)} · {reference.slice(11, 16)}
        </p>
      </header>
      {!summary || !data ? (
        <EmptyState
          title="Operational data unavailable"
          detail="Counts and scheduling issues cannot be determined without records."
        />
      ) : (
        <>
          <div className="admin-priorities">
            <AttentionQueue
              title="Scheduling attention"
              items={issues.slice(0, 2)}
              emptyMessage="No open conflicts in the supplied demo records. Pending decisions are listed below; this is not live validation."
            />
            <PendingDecisions requests={summary.pending} data={data} />
          </div>
          <nav className="admin-action-grid" aria-label="Administrator dashboard actions">
            {(
              [
                ['schedule-manager', 'Schedule Manager', CalendarDays],
                ['conflicts', 'Conflict Center', TriangleAlert],
                ['requests', 'Change requests', ClipboardList],
                ['rooms', 'Room Directory', DoorOpen],
              ] as const
            ).map(([kind, label, Icon]) => (
              <Link key={kind} to={rolePath('administrator', kind)}>
                <Icon size={20} aria-hidden="true" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>
          <section className="operations-metrics" aria-label="Demo record summary">
            <div className="section-head">
              <h2>Record summary</h2>
              <span className="muted">All supplied demo records</span>
            </div>
            <dl>
              {[
                ['Published', summary.recordCounts.published],
                ['Draft', summary.recordCounts.draft],
                ['Open conflicts', summary.recordCounts.conflicts],
                ['Pending requests', summary.recordCounts.pending],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </section>
          <div className="admin-workspace">
            <div className="admin-agenda">
              <ScheduleAgenda
                title="Today’s campus schedule"
                occurrences={summary.today.filter((item) => item.endsAt > reference).slice(0, 3)}
                emptyMessage={
                  summary.today.length
                    ? 'No remaining sessions in this demo day'
                    : 'No campus classes in this demo day'
                }
                showPublication
              />
              <Link className="text-action" to={rolePath('administrator', 'schedule-manager')}>
                View full schedule
              </Link>
            </div>
            <div className="admin-resources">
              <ResourceOverview data={data} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function PendingDecisions({
  requests,
  data,
}: {
  requests: readonly PreviewRequest[];
  data: SchedulePreviewData;
}) {
  return (
    <section className="dashboard-panel admin-pending" aria-label="Pending decisions">
      <div className="section-head">
        <h2>Pending decisions</h2>
        <span className="muted">{requests.length} pending</span>
      </div>
      {requests.length ? (
        <ul className="request-summary-list">
          {requests.slice(0, 2).map((request) => (
            <li key={request.id}>
              <RequestSummary
                request={request}
                assignment={data.occurrences.find((item) => item.id === request.assignmentId)}
                role="administrator"
                compact
              />
            </li>
          ))}
        </ul>
      ) : (
        <p>No pending requests in the supplied demo records.</p>
      )}
      {requests.length > 2 && (
        <Link className="text-action" to={rolePath('administrator', 'requests')}>
          All pending requests
        </Link>
      )}
    </section>
  );
}
