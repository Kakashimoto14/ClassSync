import { Link } from 'react-router-dom';
import { previewContext, type SchedulePreviewData } from '../../data/schedule-preview';
import { summarizeAdministration, formatPreviewDate } from '../../lib/schedule-preview';
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
    summary?.conflicts.map((conflict) => ({
      id: conflict.id,
      title: 'Overlapping room assignments',
      detail: conflict.reason,
      status: 'Blocking conflict',
      href: `${rolePath('administrator', 'conflict-detail')}?id=${encodeURIComponent(conflict.id)}`,
      action: 'Review conflict',
    })) ?? [];
  return (
    <div className="admin-dashboard">
      <header className="operations-heading">
        <h1>Scheduling control center</h1>
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
          <AttentionQueue
            title="Scheduling attention"
            items={issues}
            emptyMessage="No open conflicts in the supplied demo records. Pending decisions are listed below; this is not live validation."
          />
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
            <section className="dashboard-panel admin-pending" aria-label="Pending decisions">
              <div className="section-head">
                <h2>Pending decisions</h2>
                <span className="muted">{summary.pending.length} pending</span>
              </div>
              {summary.pending.length ? (
                <ul className="request-summary-list">
                  {summary.pending.map((request) => (
                    <li key={request.id}>
                      <RequestSummary
                        request={request}
                        assignment={data.occurrences.find(
                          (item) => item.id === request.assignmentId,
                        )}
                        role="administrator"
                      />
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No pending requests in the supplied demo records.</p>
              )}
            </section>
            <div className="admin-agenda">
              <ScheduleAgenda
                title="Today’s campus schedule"
                occurrences={summary.today}
                emptyMessage="No campus classes in this demo day"
                showPublication
              />
            </div>
            <div className="admin-resources">
              <ResourceOverview data={data} />
            </div>
          </div>
        </>
      )}
      <nav className="operations-actions" aria-label="Administrator dashboard actions">
        <Link className="text-action" to={rolePath('administrator', 'schedule-manager')}>
          Schedule Manager
        </Link>
        <Link className="text-action" to={rolePath('administrator', 'conflicts')}>
          Conflict Center
        </Link>
        <Link className="text-action" to={rolePath('administrator', 'requests')}>
          Change requests
        </Link>
        <Link className="text-action" to={rolePath('administrator', 'availability')}>
          Room Availability preview
        </Link>
        {!data && (
          <Link className="text-action" to={rolePath('administrator', 'rooms')}>
            Room Directory
          </Link>
        )}
      </nav>
      <p className="demo-footnote">
        Sample records only. No live validation, publication, or availability service is connected.
      </p>
    </div>
  );
}
