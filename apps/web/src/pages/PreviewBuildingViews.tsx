import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { RoomDirectoryCard } from '../components/scheduling/RoomDirectoryCard';
import { EmptyState } from '../components/ui/EmptyState';
import { schedulePreview } from '../data/schedule-preview';
import { roomCatalog, roomDetailPath } from '../lib/room-discovery';
import { rolePath } from '../routes/route-config';

const rooms = roomCatalog(schedulePreview).filter((room) => room.inventory);
const buildings = [...new Set(rooms.map((room) => room.building))].sort();

export function PreviewBuildingDirectory() {
  return (
    <section className="preview-records">
      <p className="muted">
        Provisional CDM buildings and areas · User-supplied spaces, not verified availability.
      </p>
      <div className="discovery-results">
        {buildings.map((building) => {
          const records = rooms.filter((room) => room.building === building);
          return (
            <article className="discovery-room-card" key={building}>
              <h2>{building}</h2>
              <p>
                {records.length} recorded {records.length === 1 ? 'space' : 'spaces'}
              </p>
              <p className="muted">Condition unverified</p>
              <Link
                className="text-action"
                aria-label={`View ${building} rooms`}
                to={`${rolePath('administrator', 'building-detail')}?building=${encodeURIComponent(building)}`}
              >
                View rooms <span aria-hidden="true">→</span>
              </Link>
            </article>
          );
        })}
      </div>
      {!buildings.length && (
        <EmptyState
          title="No recorded buildings"
          detail="Building records have not been supplied."
        />
      )}
    </section>
  );
}

export function PreviewBuildingDetail() {
  const [params] = useSearchParams();
  const location = useLocation();
  const building = params.getAll('building').length === 1 ? params.get('building') : null;
  const records =
    building && buildings.includes(building)
      ? rooms.filter((room) => room.building === building)
      : [];
  return (
    <section className="preview-records">
      <Link className="text-action" to={rolePath('administrator', 'buildings')}>
        Back to buildings
      </Link>
      {records.length ? (
        <>
          <h2>{building} spaces</h2>
          <p className="muted">
            Showing {Math.min(records.length, 6)} of {records.length} provisional spaces. Resource
            details require verification.
          </p>
          <div className="discovery-results">
            {records.slice(0, 6).map((room) => (
              <RoomDirectoryCard
                key={room.id}
                room={room}
                detailsPath={roomDetailPath('administrator', room.id)}
                returnTo={location.pathname + location.search}
              />
            ))}
          </div>
          {records.length > 6 && (
            <Link
              className="text-action"
              to={`${rolePath('administrator', 'rooms')}?building=${encodeURIComponent(building!)}`}
            >
              Browse all {records.length} spaces
            </Link>
          )}
        </>
      ) : (
        <EmptyState
          title={building ? 'Building not found' : 'Choose a building'}
          detail="Open a building from the inventory to inspect its recorded rooms."
        />
      )}
    </section>
  );
}
