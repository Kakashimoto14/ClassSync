import { describe, expect, it } from 'vitest';
import { provisionalCdmRooms } from './cdm-room-inventory';
import { schedulePreview } from './schedule-preview';
import { emptyRoomCriteria, filterRooms, roomCatalog } from '../lib/room-discovery';

describe('user-supplied provisional CDM inventory', () => {
  it('includes exactly the supplied spaces and no inferred PRRC gaps', () => {
    expect(provisionalCdmRooms).toHaveLength(59);
    expect(new Set(provisionalCdmRooms.map((room) => room.id)).size).toBe(59);
    const prrc = provisionalCdmRooms.filter((room) => room.building === 'PRRC');
    expect(prrc).toHaveLength(27);
    expect(prrc.map((room) => Number(room.id.split('-').at(-1)))).toEqual([
      101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 201, 202, 203, 204, 205, 206, 207, 208, 209,
      210, 301, 302, 303, 307, 308, 309, 310,
    ]);
    expect(provisionalCdmRooms.filter((room) => room.building === 'New Building')).toHaveLength(31);
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-prrc-302')).toMatchObject({
      alias: 'VGA Room',
      aliasUnconfirmed: true,
    });
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-new-function-hall')?.floor).toBe(
      '4th floor',
    );
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-court')?.location).toBe(
      'Beside New Building',
    );
  });
  it('keeps source provenance and excludes unknown resource requirements from matches', () => {
    const rooms = roomCatalog(schedulePreview).filter((room) => room.inventory);
    expect(rooms).toHaveLength(59);
    expect(
      rooms.every(
        (room) => room.inventory?.source === 'user-supplied-provisional' && !room.resource,
      ),
    ).toBe(true);
    expect(
      filterRooms(rooms, { ...emptyRoomCriteria, search: 'comlab1' }).map((room) => room.name),
    ).toEqual(['PRRC 301']);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, capacity: '1' })).toEqual([]);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, facility: 'Projector' })).toEqual([]);
    expect(rooms.filter((room) => room.floor)).toHaveLength(58);
    expect(roomCatalog(schedulePreview).filter((room) => !room.inventory)).toHaveLength(4);
  });
});
