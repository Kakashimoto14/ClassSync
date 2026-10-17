import { describe, expect, it } from 'vitest';
import { schedulePreview } from '../data/schedule-preview';
import { demoDestination } from '../auth/access';
import { navigationOwner, routesByPath } from '../routes/route-config';
import {
  emptyRoomCriteria,
  filterRooms,
  roomAssignments,
  roomById,
  roomCatalog,
  roomDetailPath,
  validMinimumCapacity,
} from './room-discovery';

const rooms = roomCatalog(schedulePreview);
describe('room resource discovery', () => {
  it('resolves every assignment identity without fabricating missing metadata', () => {
    expect(new Set(rooms.map((room) => room.id)).size).toBe(rooms.length);
    for (const item of schedulePreview.occurrences) {
      const room = roomById(rooms, item.room.id)!;
      expect(room.name).toBe(item.room.name);
      expect(room.building).toBe(item.room.building);
      expect(room.floor).toBe(item.room.floor);
    }
    expect(roomById(rooms, 'room-nb-405')?.resource).toBeUndefined();
    expect(roomById(rooms, null)).toBeUndefined();
    expect(roomById(rooms, 'SCI-218')).toBeUndefined();
    expect(
      roomCatalog({
        ...schedulePreview,
        inventory: undefined,
        resources: undefined,
        occurrences: [],
      }),
    ).toEqual([]);
  });
  it('combines actual fields and includes the capacity boundary', () => {
    expect(
      filterRooms(rooms, {
        ...emptyRoomCriteria,
        capacity: '42',
        type: 'Computer laboratory',
        facility: 'Projector',
      }).map((room) => room.name),
    ).toEqual(['SCI-218']);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, capacity: '43' })).toEqual([]);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, search: ' eng-204 ' })[0].name).toBe(
      'ENG-204',
    );
    expect(
      filterRooms(rooms, { ...emptyRoomCriteria, building: 'Computing Building' })[0].resource
        ?.condition,
    ).toBe('maintenance');
    for (const capacity of ['-1', '0', '1.5', 'abc', 'Infinity']) {
      expect(validMinimumCapacity(capacity)).toBe(false);
      expect(filterRooms(rooms, { ...emptyRoomCriteria, capacity })).toEqual([]);
    }
  });
  it('orders recorded assignments and restricts draft visibility', () => {
    expect(
      roomAssignments(schedulePreview, 'room-sci-218', 'administrator').map((item) => item.id),
    ).toEqual(['occ-database-mon', 'occ-networks-mon', 'occ-database-tue']);
    for (const role of ['student', 'teacher'] as const)
      expect(
        roomAssignments(schedulePreview, 'room-sci-218', role).every(
          (item) => item.publication === 'published',
        ),
      ).toBe(true);
    expect(roomAssignments(schedulePreview, 'room-lab-04', 'administrator')).toEqual([]);
  });
  it.each(['student', 'teacher', 'administrator'] as const)(
    'registers owned %s details and preserves IDs through demo access',
    (role) => {
      const path = roomDetailPath(role, 'room-eng-204');
      expect(routesByPath.get(path.split('?')[0])?.role).toBe(role);
      expect(navigationOwner(path.split('?')[0])).toBe(
        `${role}.${role === 'teacher' ? 'find-room' : 'rooms'}`,
      );
      expect(demoDestination(role, path)).toBe(path);
      expect(demoDestination(role, 'https://example.com' + path)).not.toBe(path);
      if (role !== 'administrator')
        expect(
          demoDestination(role, roomDetailPath('administrator', 'room-eng-204')),
        ).not.toContain('/admin/');
    },
  );
});
