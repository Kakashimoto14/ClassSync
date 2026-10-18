import type { ProvisionalRoom } from './schedule-preview';
import spaces from '../../../../packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json';

// Canonical 59-space owner-supplied catalog. Floor ranges were explicitly supplied
// in S1; capacities, equipment, operational condition and schedulability remain unknown.
export const provisionalCdmRooms: readonly ProvisionalRoom[] = spaces.map((room) => ({
  ...room,
  ...(room.id === 'cdm-court' ? { location: 'Beside New Building' } : {}),
  source: 'user-supplied-provisional' as const,
}));
