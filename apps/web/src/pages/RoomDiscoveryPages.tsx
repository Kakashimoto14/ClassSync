import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { useRef } from 'react';
import { Button } from '../components/ui/Button';
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
import { ScheduledRooms } from './ScheduledRooms';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { PublishedRoomAvailability } from './PublishedRoomAvailability';

const rooms = roomCatalog(schedulePreview);

export function RoomDiscoveryPage({ definition }: { definition: RouteDefinition }) {
  const availability = definition.roomMode === 'availability';
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const inventory = params.get('inventory');
  const inventorySource = inventory === 'demo' ? 'demo' : 'cdm';
  const inventoryRooms = rooms.filter((room) =>
    inventorySource === 'cdm' ? !!room.inventory : !room.inventory,
  );
  const criteria: RoomCriteria = {
    search: params.get('search') ?? '',
    building: params.get('building') ?? '',
    capacity: params.get('capacity') ?? '',
    type: params.get('type') ?? '',
    facility: params.get('facility') ?? '',
  };
  const results = filterRooms(inventoryRooms, criteria);
  const pageCount = Math.max(1, Math.ceil(results.length / 12));
  const requestedPage = Number(params.get('page') ?? 1);
  const page =
    Number.isSafeInteger(requestedPage) && requestedPage > 0
      ? Math.min(requestedPage, pageCount)
      : 1;
  const shown = results.slice((page - 1) * 12, page * 12);
  function update(key: keyof RoomCriteria | 'inventory' | 'page', value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next, { replace: true });
  }
  function reset() {
    const next = new URLSearchParams(params);
    Object.keys(emptyRoomCriteria).forEach((key) => next.delete(key));
    next.delete('page');
    setParams(next, { replace: true });
  }
  return (
    <div className="room-discovery">
      <ScheduledRooms role={definition.role} />
      <div className="page-heading">
        <div>
          <h1>{definition.title}</h1>
          <p>
            {inventorySource === 'cdm'
              ? 'CDM inventory · User-supplied and provisional.'
              : 'Demo inventory · Sample resource records.'}
          </p>
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
        <PublishedRoomAvailability
          rooms={inventoryRooms.map((r) => ({ id: r.id, name: r.name }))}
        />
      )}
      {availability && (
        <p className="muted">
          Time-based occupancy is separate from unverified capacity and equipment suitability.
        </p>
      )}
      <RoomFilters
        rooms={inventoryRooms}
        criteria={criteria}
        onChange={update}
        onReset={reset}
        inventorySource={inventorySource}
        onInventoryChange={(value) => update('inventory', value)}
      />
      <div className="discovery-results-heading">
        <h2 ref={resultsHeading} tabIndex={-1}>
          {availability ? 'Matching resources' : 'Rooms & spaces'}
        </h2>
        <p role="status" aria-live="polite">
          {results.length} of {inventoryRooms.length}{' '}
          {inventorySource === 'demo' ? 'demo rooms' : 'spaces'}
        </p>
      </div>
      <div className="discovery-results">
        {shown.map((room) => (
          <RoomDirectoryCard
            key={room.id}
            room={room}
            detailsPath={roomDetailPath(definition.role, room.id)}
            returnTo={location.pathname + location.search}
          />
        ))}
      </div>
      {pageCount > 1 && (
        <nav className="discovery-pagination" aria-label="Room results pages">
          <Button
            variant="secondary"
            disabled={page === 1}
            onClick={() => {
              update('page', String(page - 1));
              resultsHeading.current?.focus({ preventScroll: true });
              window.scrollTo({ top: 0, behavior: 'instant' });
            }}
          >
            Previous
          </Button>
          <span role="status">
            Page {page} of {pageCount}
          </span>
          <Button
            variant="secondary"
            disabled={page === pageCount}
            onClick={() => {
              update('page', String(page + 1));
              resultsHeading.current?.focus({ preventScroll: true });
              window.scrollTo({ top: 0, behavior: 'instant' });
            }}
          >
            Next
          </Button>
        </nav>
      )}
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
  const [query] = useSearchParams();
  if (
    schedulingSandboxEnabled &&
    query.getAll('id').length === 1 &&
    query.get('id')?.startsWith('synthetic-room-')
  )
    return <ScheduledRooms role={role} roomId={query.get('id')!} />;
  return <InventoryRoomDetailPage role={role} />;
}
function InventoryRoomDetailPage({ role }: { role: UserRole }) {
  const [params] = useSearchParams();
  const location = useLocation();
  const room = params.getAll('id').length === 1 ? roomById(rooms, params.get('id')) : undefined;
  const candidate: unknown = location.state?.returnTo;
  const source =
    typeof candidate === 'string' ? routesByPath.get(candidate.split('?')[0]) : undefined;
  const back =
    source?.role === role && (source.kind === 'rooms' || source.kind === 'building-detail')
      ? (candidate as string)
      : roomDirectoryPath(role) + (room && !room.inventory ? '?inventory=demo' : '');
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
  const unknown = room.inventory ? 'Unverified' : 'Not recorded';
  return (
    <div className="room-discovery">
      <Link className="text-action" to={back}>
        Back to{' '}
        {source?.kind === 'building-detail'
          ? 'building'
          : source?.roomMode === 'availability'
            ? 'room search'
            : 'Room Directory'}
      </Link>
      <div className="page-heading">
        <div>
          <h1>{room.name}</h1>
          <p>
            {room.inventory?.location ?? room.building}
            {room.floor && ` · ${room.floor}`}
          </p>
        </div>
        <ResourceStatusBadge room={room} />
      </div>
      {room.inventory && (
        <p className="muted">
          User-supplied provisional CDM inventory.{' '}
          {room.inventory.alias &&
            `${room.inventory.alias}${room.inventory.aliasUnconfirmed ? ' — Unconfirmed label.' : '.'}`}{' '}
          Resource details require verification.
        </p>
      )}
      <div className="discovery-detail-layout">
        <section className="discovery-detail-panel" aria-labelledby="room-resource-heading">
          <h2 id="room-resource-heading">Room information</h2>
          <dl className="discovery-room-facts">
            <div>
              <dt>Room type</dt>
              <dd>{room.resource?.type ?? unknown}</dd>
            </div>
            <div>
              <dt>Seating capacity</dt>
              <dd>{room.resource ? `${room.resource.seats} seats` : unknown}</dd>
            </div>
            <div>
              <dt>Floor</dt>
              <dd>{room.floor ?? unknown}</dd>
            </div>
            <div>
              <dt>Facilities</dt>
              <dd>{roomFacilities(room).join(' · ') || unknown}</dd>
            </div>
          </dl>
          {room.resource?.condition === 'maintenance' && (
            <p className="discovery-condition-note">
              This demo resource is marked for maintenance.
            </p>
          )}
          <p className="muted">
            Condition and recorded assignments do not confirm availability or suitability.
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
