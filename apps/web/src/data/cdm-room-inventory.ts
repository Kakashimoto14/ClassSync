import type { ProvisionalRoom } from './schedule-preview';
import type { ActivityType } from '../../../../packages/shared-types/src/scheduling';
import spaces from '../../../../packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json';

// Row-classified November 2026 inventory. Schedulability is source designation only;
// operation, availability, capacity, equipment and room-type verification remain unknown.
export const CDM_ROOM_INVENTORY_VERSION = '2026-11' as const;
export const provisionalCdmRooms: readonly ProvisionalRoom[] = spaces.map(
  (room): ProvisionalRoom => ({
    ...room,
    allowed_activity_types: room.allowed_activity_types as ActivityType[] | null,
    source: 'user-supplied-provisional' as const,
  }),
);
