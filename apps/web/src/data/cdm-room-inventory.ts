import type { ProvisionalRoom } from './schedule-preview';

// Product-owner supplied list. No official inventory or resource condition was supplied.
// IDs use building + room identifier; numbers are not treated as verified floor data.
const range = (start: number, end: number) =>
  Array.from({ length: end - start + 1 }, (_, index) => start + index);
const prrcAliases: Record<number, string> = {
  108: 'ITE Lab',
  301: 'COMLAB1',
  302: 'VGA Room',
  303: 'COMLAB2',
  307: 'COMLAB3',
  308: 'COMLAB4',
};
export const provisionalCdmRooms: readonly ProvisionalRoom[] = [
  ...[...range(101, 110), ...range(201, 210), 301, 302, 303, 307, 308, 309, 310].map((number) => ({
    id: `cdm-prrc-${number}`,
    name: `PRRC ${number}`,
    building: 'PRRC',
    source: 'user-supplied-provisional' as const,
    ...(prrcAliases[number] ? { alias: prrcAliases[number] } : {}),
    ...(number === 302 ? { aliasUnconfirmed: true } : {}),
  })),
  ...[...range(101, 110), ...range(201, 210), ...range(301, 310)].map((number) => ({
    id: `cdm-new-${number}`,
    name: `New Building ${number}`,
    building: 'New Building',
    source: 'user-supplied-provisional' as const,
  })),
  {
    id: 'cdm-new-function-hall',
    name: 'Function Hall',
    building: 'New Building',
    floor: '4th floor',
    source: 'user-supplied-provisional',
  },
  {
    id: 'cdm-court',
    name: 'Court',
    building: 'Court',
    location: 'Beside New Building',
    source: 'user-supplied-provisional',
  },
];
