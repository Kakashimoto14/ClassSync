import { Link } from 'react-router-dom';
import type { PreviewUpdate } from '../../data/schedule-preview';
import type { UserRole } from '../../types/ui';
import { rolePath } from '../../routes/route-config';

export function ScheduleUpdates({
  updates,
  role,
}: {
  updates: readonly PreviewUpdate[];
  role: UserRole;
}) {
  return (
    <section className="dashboard-section" aria-label="Schedule updates">
      <h2>Schedule updates</h2>
      {updates.length ? (
        <ul className="dashboard-updates">
          {updates.map((item) => (
            <li key={item.id}>
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No updates for these assignments.</p>
      )}
      <Link className="text-action" to={rolePath(role, 'notifications')}>
        All notifications
      </Link>
    </section>
  );
}
