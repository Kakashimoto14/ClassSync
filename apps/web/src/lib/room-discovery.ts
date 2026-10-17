import type {
  PreviewResource,
  PreviewRoom,
  ProvisionalRoom,
  SchedulePreviewData,
} from '../data/schedule-preview';
import { rolePath } from '../routes/route-config';
import type { UserRole } from '../types/ui';

/** Location identity is usable even when resource metadata has not been supplied. */
export interface RoomRecord extends PreviewRoom {
  inventory?: ProvisionalRoom;
  resource?: PreviewResource;
}
export interface RoomCriteria {
  search: string;
  building: string;
  capacity: string;
  type: string;
  facility: string;
}
export const emptyRoomCriteria: RoomCriteria = {
  search: '',
  building: '',
  capacity: '',
  type: '',
  facility: '',
};

export function roomCatalog(data: SchedulePreviewData): RoomRecord[] {
  const records = new Map<string, RoomRecord>();
  for (const room of data.inventory ?? []) records.set(room.id, { ...room, inventory: room });
  for (const resource of data.resources ?? []) records.set(resource.id, { ...resource, resource });
  for (const occurrence of data.occurrences) {
    if (!records.has(occurrence.room.id)) records.set(occurrence.room.id, { ...occurrence.room });
  }
  return [...records.values()];
}

export function roomById(records: readonly RoomRecord[], id: string | null) {
  return id ? records.find((room) => room.id === id) : undefined;
}

// Adapt existing resource labels here rather than maintaining a second equipment fixture.
export function roomFacilities(room: RoomRecord): string[] {
  return room.resource?.facilities.split(' · ').filter(Boolean) ?? [];
}

export function validMinimumCapacity(value: string): boolean {
  return (
    value === '' ||
    (/^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0)
  );
}

export function filterRooms(records: readonly RoomRecord[], criteria: RoomCriteria): RoomRecord[] {
  if (!validMinimumCapacity(criteria.capacity)) return [];
  const search = criteria.search.trim().toLocaleLowerCase();
  return records.filter(
    (room) =>
      (!search ||
        `${room.name} ${room.id} ${room.inventory?.alias ?? ''}`
          .toLocaleLowerCase()
          .includes(search)) &&
      (!criteria.building || room.building === criteria.building) &&
      (!criteria.capacity ||
        (room.resource !== undefined && room.resource.seats >= Number(criteria.capacity))) &&
      (!criteria.type || room.resource?.type === criteria.type) &&
      (!criteria.facility || roomFacilities(room).includes(criteria.facility)),
  );
}

export function roomDirectoryPath(role: UserRole): string {
  return rolePath(role, role === 'teacher' ? 'find-room' : 'rooms');
}

export function roomDetailPath(role: UserRole, id: string): string {
  return `${rolePath(role, 'room-detail')}?id=${encodeURIComponent(id)}`;
}

export function roomAssignments(data: SchedulePreviewData, id: string, role: UserRole) {
  return data.occurrences
    .filter(
      (item) =>
        item.room.id === id && (role === 'administrator' || item.publication === 'published'),
    )
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt) || a.id.localeCompare(b.id));
}
