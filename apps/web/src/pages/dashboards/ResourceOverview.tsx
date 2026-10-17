import { Link } from 'react-router-dom';
import type { SchedulePreviewData } from '../../data/schedule-preview';
import { summarizeResources } from '../../lib/schedule-preview';
import { rolePath } from '../../routes/route-config';
import { StatusBadge } from '../../components/ui/StatusBadge';

export function ResourceOverview({ data }: { data: SchedulePreviewData | null }) {
  const summary = summarizeResources(data);
  return (
    <section className="dashboard-panel" aria-label="Classroom resources">
      <h2>Classroom resources</h2>
      {summary ? (
        <>
          <p className="muted">{summary.total} demo resources with recorded condition</p>
          <dl className="resource-counts">
            <div>
              <dt>Resource active</dt>
              <dd>{summary.active}</dd>
            </div>
            <div>
              <dt>Maintenance</dt>
              <dd>{summary.maintenance.length}</dd>
            </div>
          </dl>
          {summary.maintenance.map((room) => (
            <p key={room.id}>
              <StatusBadge tone="warning">Maintenance</StatusBadge> <strong>{room.name}</strong> ·{' '}
              {room.building}
            </p>
          ))}
          {!summary.total && <p>No resource records in this demo.</p>}
        </>
      ) : (
        <p>Resource condition data unavailable.</p>
      )}
      <p className="muted">
        Time-based availability is unavailable. Capacity and facilities alone do not verify
        suitability.
      </p>
      <Link className="text-action" to={rolePath('administrator', 'rooms')}>
        Open Room Directory
      </Link>
    </section>
  );
}
