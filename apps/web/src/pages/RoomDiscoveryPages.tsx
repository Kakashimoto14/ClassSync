import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { RoomDirectoryCard, ResourceStatusBadge } from '../components/scheduling/RoomDirectoryCard';
import { RoomFilters } from '../components/scheduling/RoomFilters';
import { ScheduleEntry } from '../components/scheduling/ScheduleEntry';
import { EmptyState } from '../components/ui/EmptyState';
import { schedulePreview } from '../data/schedule-preview';
import {
  emptyRoomCriteria,
  filterRooms,
  roomAssignments,
  roomById,
  roomCatalog,
  roomDetailPath,
  roomDirectoryPath,
  roomFacilities,
  type RoomCriteria,
} from '../lib/room-discovery';
import { rolePath, routesByPath, type RouteDefinition } from '../routes/route-config';
import type { UserRole } from '../types/ui';

const rooms = roomCatalog(schedulePreview);

export function RoomDiscoveryPage({ definition }: { definition: RouteDefinition }) {
  const availability = definition.roomMode === 'availability';
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const criteria: RoomCriteria = {
    search: params.get('search') ?? '',
    building: params.get('building') ?? '',
    capacity: params.get('capacity') ?? '',
    type: params.get('type') ?? '',
    facility: params.get('facility') ?? '',
  };
  const results = filterRooms(rooms, criteria);
  function update(key: keyof RoomCriteria, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }
  function reset() {
    const next = new URLSearchParams(params);
    Object.keys(emptyRoomCriteria).forEach((key) => next.delete(key));
    setParams(next, { replace: true });
  }
  return (
    <div className="room-discovery">
      <div className="page-heading">
        <div>
          <h1>{definition.title}</h1>
          <p>Demo inventory · Resource condition is separate from time-based availability.</p>
        </div>
        <Link
          className="text-action"
          to={
            availability
              ? roomDirectoryPath(definition.role)
              : rolePath(
                  definition.role,
                  definition.role === 'student' ? 'find-room' : 'availability',
                )
          }
        >
          {availability ? 'Browse Room Directory' : 'Room Availability'}
        </Link>
      </div>
      {availability && (
        <section className="discovery-availability" aria-labelledby="availability-heading">
          <h2 id="availability-heading">Time-based availability unavailable</h2>
          <p id="availability-limit">
            Filter recorded resources below. Complete schedules and rules are not connected; free
            time and suitability remain unverified.
          </p>
          <details className="discovery-time-criteria">
            <summary>Time criteria · Unavailable</summary>
            <fieldset
              disabled
              aria-label="Requested interval"
              aria-describedby="availability-limit"
            >
              <div className="discovery-time-fields">
                <label>
                  Date
                  <input type="date" />
                </label>
                <label>
                  Start time
                  <input type="time" />
                </label>
                <label>
                  End time
                  <input type="time" />
                </label>
              </div>
            </fieldset>
          </details>
        </section>
      )}
      <RoomFilters rooms={rooms} criteria={criteria} onChange={update} onReset={reset} />
      <div className="discovery-results-heading">
        <h2>{availability ? 'Matching resources' : 'Classrooms'}</h2>
        <p role="status" aria-live="polite">
          {results.length} of {rooms.length} demo rooms
        </p>
      </div>
      <div className="discovery-results">
        {results.map((room) => (
          <RoomDirectoryCard
            key={room.id}
            room={room}
            detailsPath={roomDetailPath(definition.role, room.id)}
            returnTo={location.pathname + location.search}
          />
        ))}
      </div>
      {!results.length && (
        <EmptyState
          title="No matching rooms"
          detail="Clear filters or try another name, building, capacity, type, or facility."
        />
      )}
    </div>
  );
}

export function RoomDetailPage({ role }: { role: UserRole }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const room = params.getAll('id').length === 1 ? roomById(rooms, params.get('id')) : undefined;
  const candidate: unknown = location.state?.returnTo;
  const source =
    typeof candidate === 'string' ? routesByPath.get(candidate.split('?')[0]) : undefined;
  const back =
    source?.role === role && source.kind === 'rooms'
      ? (candidate as string)
      : roomDirectoryPath(role);
  if (!room)
    return (
      <div className="room-discovery">
        <div className="page-heading">
          <h1>Room Details</h1>
        </div>
        <EmptyState
          title={params.has('id') ? 'Room not found' : 'Choose a room'}
          detail="Open a room from the directory to inspect its recorded details."
        />
        <Link className="text-action" to={roomDirectoryPath(role)}>
          Back to Room Directory
        </Link>
      </div>
    );
  const assignments = roomAssignments(schedulePreview, room.id, role);
  return (
    <div className="room-discovery">
      <Link className="text-action" to={back}>
        Back to {source?.roomMode === 'availability' ? 'room search' : 'Room Directory'}
      </Link>
      <div className="page-heading">
        <div>
          <h1>{room.name}</h1>
          <p>
            {room.building}
            {room.floor && ` · ${room.floor}`}
          </p>
        </div>
        <ResourceStatusBadge room={room} />
      </div>
      <div className="discovery-detail-layout">
        <section className="discovery-detail-panel" aria-labelledby="room-resource-heading">
          <h2 id="room-resource-heading">Room information</h2>
          <dl className="discovery-room-facts">
            <div>
              <dt>Room type</dt>
              <dd>{room.resource?.type ?? 'Not recorded'}</dd>
            </div>
            <div>
              <dt>Seating capacity</dt>
              <dd>{room.resource ? `${room.resource.seats} seats` : 'Not recorded'}</dd>
            </div>
            <div>
              <dt>Floor</dt>
              <dd>{room.floor ?? 'Not recorded'}</dd>
            </div>
            <div>
              <dt>Facilities</dt>
              <dd>{roomFacilities(room).join(' · ') || 'Not recorded'}</dd>
            </div>
          </dl>
          {room.resource?.condition === 'maintenance' && (
            <p className="discovery-condition-note">
              This demo resource is marked for maintenance.
            </p>
          )}
          <p className="muted">
            Demo records only. Condition and recorded assignments do not confirm availability or
            suitability.
          </p>
        </section>
        <section className="discovery-assignments" aria-labelledby="room-assignments-heading">
          <h2 id="room-assignments-heading">Recorded demo assignments</h2>
          <p className="muted">
            {role === 'administrator'
              ? 'All recorded publication states.'
              : 'Published records only.'}{' '}
            This is a partial sample, not a complete room timetable.
          </p>
          {assignments.map((item) => (
            <ScheduleEntry key={item.id} occurrence={item} showDate showPublication />
          ))}
          {!assignments.length && (
            <EmptyState
              title="No recorded assignments"
              detail="No assignments are shown for this room. This does not mean the room is free."
            />
          )}
        </section>
      </div>
    </div>
  );
}
