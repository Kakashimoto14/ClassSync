import { Link } from 'react-router-dom';
import type { SchedulePreviewData } from '../../data/schedule-preview';
import { rolePath } from '../../routes/route-config';

export function ResourceOverview({ data }: { data: SchedulePreviewData | null }) {
  const inventory = data?.inventory ?? [];
  const areaMap = new Map<string, number>();
  for (const room of inventory) {
    areaMap.set(room.building, (areaMap.get(room.building) ?? 0) + 1);
  }
  const areas = [...areaMap.entries()].sort((a, b) => b[1] - a[1]);
  return (
    <section className="dashboard-panel campus-resources" aria-label="Classroom resources">
      <h2>Campus spaces</h2>
      {inventory.length ? <>
        <p className="campus-resources__total"><strong>{inventory.length}</strong> known CDM spaces</p>
        <dl className="campus-resources__areas">
          {areas.map(([name, count]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{count} {count === 1 ? 'space' : 'spaces'}</dd>
            </div>
          ))}
        </dl>
        <p className="muted">Provisional inventory · Condition and time-based availability unverified.</p>
      </> : <p>CDM inventory unavailable.</p>}
      <Link className="text-action" to={rolePath('administrator', 'rooms')}>Open Room Directory</Link>
      <Link className="text-action" to={rolePath('administrator', 'buildings')}>View Buildings &amp; Areas</Link>
    </section>
  );
}
