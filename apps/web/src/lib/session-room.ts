import { roomById, roomCatalog } from './room-discovery';
import { schedulePreview } from '../data/schedule-preview';
import { schedulingSandboxEnabled } from './scheduling-api';
import { presentationEnabled } from './presentation-sample';
import { readWorkspace } from './workspace-context';
import type { UserRole } from '../types/ui';
const inventory = roomCatalog(schedulePreview);
export function sessionRoomPath(role: UserRole, id: string) {
  const known =
    roomById(inventory, id) || ((schedulingSandboxEnabled || (presentationEnabled && readWorkspace(role).mode === 'presentation')) && id.startsWith('synthetic-'));
  return known
    ? `${role === 'administrator' ? '/admin' : '/' + role}/rooms/detail?id=${encodeURIComponent(id)}`
    : undefined;
}
