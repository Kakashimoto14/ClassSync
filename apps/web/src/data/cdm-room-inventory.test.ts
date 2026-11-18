// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { CDM_ROOM_INVENTORY_VERSION, provisionalCdmRooms } from './cdm-room-inventory';
import { schedulePreview } from './schedule-preview';
import { emptyRoomCriteria, filterRooms, roomCatalog } from '../lib/room-discovery';

describe('user-supplied provisional CDM inventory', () => {
  it('matches the November 2026 row list and never infers omitted room numbers', () => {
    expect(CDM_ROOM_INVENTORY_VERSION).toBe('2026-11');
    expect(provisionalCdmRooms).toHaveLength(53);
    expect(new Set(provisionalCdmRooms.map((room) => room.id)).size).toBe(53);
    const prrc = provisionalCdmRooms.filter((room) => room.building === 'PRRC');
    expect(prrc).toHaveLength(27);
    expect(prrc.map((room) => Number(room.id.split('-').at(-1)))).toEqual([
      101, 102, 103, 104, 105, 106, 107, 108, 201, 202, 203, 204, 205, 206, 207, 208, 209, 301, 302,
      303, 304, 305, 306, 307, 308, 309, 310,
    ]);
    expect(provisionalCdmRooms.filter((room) => room.building === 'New Building')).toHaveLength(24);
    const newBuildingNumbers = [
      ...Array.from({ length: 7 }, (_, index) => 101 + index),
      ...Array.from({ length: 8 }, (_, index) => 201 + index),
      ...Array.from({ length: 8 }, (_, index) => 301 + index),
    ];
    const expectedIds = [
      ...[
        101, 102, 103, 104, 105, 106, 107, 108, 201, 202, 203, 204, 205, 206, 207, 208, 209, 301,
        302, 303, 304, 305, 306, 307, 308, 309, 310,
      ].map((number) => `cdm-prrc-${number}`),
      ...newBuildingNumbers.map((number) => `cdm-new-${number}`),
      'cdm-new-function-hall',
      'cdm-court',
      'cdm-oval',
    ];
    expect(new Set(provisionalCdmRooms.map((room) => room.id))).toEqual(new Set(expectedIds));
    expect(provisionalCdmRooms.filter((room) => room.schedulable)).toHaveLength(41);
    expect(provisionalCdmRooms.filter((room) => !room.schedulable)).toHaveLength(12);
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-prrc-302')).toMatchObject({
      alias: 'COMLAB1',
      schedulable: true,
      room_type: 'computer_lab',
      allowed_activity_types: ['computer_lab_instruction'],
    });
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-prrc-302')).not.toHaveProperty(
      'capacity',
    );
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-prrc-108')).toMatchObject({
      alias: 'ITE Science Lab',
      schedulable: true,
      allowed_program_ids: ['bsed-sci'],
      allowed_activity_types: ['bse_science_instruction'],
    });
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-new-function-hall')?.floor).toBe(
      'Floor 4',
    );
    expect(provisionalCdmRooms.find((room) => room.id === 'cdm-oval')?.location).toBe('Off campus');
    expect(provisionalCdmRooms.some((room) => room.id === 'cdm-prrc-109')).toBe(false);
    expect(provisionalCdmRooms.every((room) => room.type_verified === false)).toBe(true);
  });
  it('keeps source provenance and excludes unknown resource requirements from matches', () => {
    const rooms = roomCatalog(schedulePreview).filter((room) => room.inventory);
    expect(rooms).toHaveLength(53);
    expect(
      rooms.every(
        (room) => room.inventory?.source === 'user-supplied-provisional' && !room.resource,
      ),
    ).toBe(true);
    expect(
      filterRooms(rooms, { ...emptyRoomCriteria, search: 'comlab1' }).map((room) => room.name),
    ).toEqual(['PRRC 302']);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, capacity: '1' })).toEqual([]);
    expect(filterRooms(rooms, { ...emptyRoomCriteria, facility: 'Projector' })).toEqual([]);
    expect(rooms.filter((room) => room.floor)).toHaveLength(51);
    expect(roomCatalog(schedulePreview).filter((room) => !room.inventory)).toHaveLength(4);
  });
});
