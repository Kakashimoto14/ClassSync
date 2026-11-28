import { roomById, roomCatalog } from './room-discovery';
import { schedulePreview } from '../data/schedule-preview';
import { schedulingSandboxEnabled } from './scheduling-api';
import { presentationEnabled } from './presentation-sample';
import { readWorkspace } from './workspace-context';
import type { UserRole } from '../types/ui';
import { appMode } from '../config/runtime-config';
const inventory = roomCatalog(schedulePreview);
export function sessionRoomPath(
  role: UserRole,
  id: string,
  context?: { period?: string; date?: string },
) {
  const known =
    appMode === 'institutional' ||
    roomById(inventory, id) ||
    ((schedulingSandboxEnabled ||
      (presentationEnabled && readWorkspace(role).mode === 'presentation')) &&
      id.startsWith('synthetic-'));
  return known
    ? `${role === 'administrator' ? '/admin' : '/' + role}/rooms/detail?${new URLSearchParams({ id, ...(context?.period ? { period: context.period } : {}), ...(context?.date ? { date: context.date } : {}) })}`
    : undefined;
}

/** Teacher follow-ups for one published class; both pages preselect it from the query. */
export function teacherClassPath(
  action: 'room-change' | 'issue',
  period: string,
  session: { id: string; date: string },
) {
  const base = action === 'issue' ? '/teacher/report-issue' : '/teacher/change-requests/new';
  return `${base}?${new URLSearchParams({ period, date: session.date, occurrence: session.id })}`;
}
