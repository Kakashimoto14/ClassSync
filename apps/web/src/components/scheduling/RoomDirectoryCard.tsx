import { Link } from 'react-router-dom';
import { roomFacilities, type RoomRecord } from '../../lib/room-discovery';
import { StatusBadge } from '../ui/StatusBadge';

export function ResourceStatusBadge({ room }: { room: RoomRecord }) {
  return (
    <StatusBadge tone={room.resource?.condition === 'maintenance' ? 'warning' : 'neutral'}>
      {room.resource
        ? room.resource.condition === 'maintenance'
          ? 'Maintenance'
          : 'Resource active'
        : 'Condition unrecorded'}
    </StatusBadge>
  );
}

/** Inventory condition only; deliberately makes no claim about availability. */
export function RoomDirectoryCard({
  room,
  detailsPath,
  returnTo,
}: {
  room: RoomRecord;
  detailsPath: string;
  returnTo?: string;
}) {
  return (
    <article className="discovery-room-card">
      <div className="discovery-room-card__heading">
        <h2>{room.name}</h2>
        <ResourceStatusBadge room={room} />
      </div>
      <p>
        {room.building}
        {room.floor && ` · ${room.floor}`}
      </p>
      <p className="discovery-room-card__capacity">
        {room.resource
          ? `${room.resource.type} · ${room.resource.seats} seats`
          : 'Capacity and room type unrecorded'}
      </p>
      <p className="muted">{roomFacilities(room).join(' · ') || 'Facilities unrecorded'}</p>
      <Link
        className="text-action"
        to={detailsPath}
        state={{ returnTo }}
        aria-label={`View ${room.name} details`}
      >
        View details <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
