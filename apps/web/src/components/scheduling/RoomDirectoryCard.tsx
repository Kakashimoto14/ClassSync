import { Building2, MapPin, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatusBadge } from '../ui/StatusBadge';

export interface RoomDirectoryRecord {
  id: string;
  building: string;
  floor: string;
  type: string;
  seats: number;
  facilities: string;
  status: string;
}

/** Resource metadata only. A room record cannot establish time-window availability. */
export function RoomDirectoryCard({
  room,
  detailsPath,
  availabilityPreview = false,
}: {
  room: RoomDirectoryRecord;
  detailsPath?: string;
  availabilityPreview?: boolean;
}) {
  return (
    <article className="room-directory-card">
      <div className="room-thumb">
        <Building2 aria-hidden="true" />
      </div>
      <div>
        <StatusBadge tone={room.status === 'Maintenance' ? 'warning' : 'neutral'}>
          {room.status === 'Available' ? 'Resource active' : room.status}
        </StatusBadge>
        <h2>{room.id}</h2>
        <p>
          {room.building} · {room.floor} · {room.type}
        </p>
        <div className="room-meta">
          <span>
            <UsersRound size={16} aria-hidden="true" />
            {room.seats} seats
          </span>
          <span>
            <MapPin size={16} aria-hidden="true" />
            {room.facilities}
          </span>
        </div>
        {availabilityPreview && (
          <small>Time-window availability is not verified in this preview.</small>
        )}
      </div>
      {detailsPath && (
        <Link className="button button--secondary" to={detailsPath}>
          View room details
        </Link>
      )}
    </article>
  );
}
