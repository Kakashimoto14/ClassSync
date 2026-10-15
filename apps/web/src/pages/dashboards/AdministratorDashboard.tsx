import { Link } from 'react-router-dom';
import { previewContext, type SchedulePreviewData } from '../../data/schedule-preview';
import { summarizeAdministration, formatTimeRange } from '../../lib/schedule-preview';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { AttentionQueue, type AttentionItem } from '../../components/scheduling/AttentionQueue';
import { EmptyState } from '../../components/ui/EmptyState';
import { rolePath } from '../../routes/route-config';

export function AdministratorDashboard({
  data,
  reference = previewContext.reference,
}: {
  data: SchedulePreviewData | null;
  reference?: string;
}) {
  const summary = summarizeAdministration(data, reference);
  const items: AttentionItem[] =
    !data || !summary
      ? []
      : [
          ...summary.conflicts.map((conflict) => ({
            id: conflict.id,
            title: 'Overlapping room assignments',
            detail: conflict.reason,
            status: 'Blocking conflict' as const,
            href: rolePath('administrator', 'conflicts'),
            action: 'Review conflicts',
          })),
          ...summary.pending.map((request) => {
            const assignment = data.occurrences.find((item) => item.id === request.assignmentId);
            return {
              id: request.id,
              title: assignment
                ? 'Room change · ' + assignment.subject.name
                : 'Room change · assignment unavailable',
              detail: assignment
                ? assignment.teacher.name +
                  ' · ' +
                  formatTimeRange(assignment) +
                  '. ' +
                  request.reason
                : request.reason,
              status: 'Pending decision' as const,
              href: rolePath('administrator', 'requests'),
              action: 'Review requests',
            };
          }),
        ];
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Administrator</p>
          <h1>Scheduling control center</h1>
        </div>
        <Link className="button" to={rolePath('administrator', 'schedule-create')}>
          Create schedule
        </Link>
      </div>
      {!summary ? (
        <EmptyState
          title="Operational data unavailable"
          detail="No counts or conflict-clearance claims can be shown without records."
        />
      ) : (
        <>
          <AttentionQueue items={items} />
          <div className="dashboard-columns dashboard-columns--admin">
            <div className="dashboard-primary">
              <div className="schedule-counts" aria-label="Today’s schedule summary">
                <span>
                  <strong>{summary.publishedCount}</strong> published classes
                </span>
                <span>
                  <strong>{summary.draftCount}</strong> draft{' '}
                  {summary.draftCount === 1 ? 'class' : 'classes'}
                </span>
              </div>
              <ScheduleAgenda
                title="Today’s campus schedule"
                occurrences={summary.today}
                emptyMessage="No campus classes in this demo day"
                showPublication
              />
            </div>
            <aside className="dashboard-secondary">
              <section className="dashboard-section">
                <h2>Scheduling workspace</h2>
                <nav className="dashboard-actions" aria-label="Administrator dashboard actions">
                  <Link className="text-action" to={rolePath('administrator', 'schedule-manager')}>
                    Open Schedule Manager
                  </Link>
                  <Link className="text-action" to={rolePath('administrator', 'availability')}>
                    Find a classroom
                  </Link>
                </nav>
                <p className="muted">
                  Validation, publishing, and room availability require connected services. These
                  attention items are examples, not detected live results.
                </p>
              </section>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
