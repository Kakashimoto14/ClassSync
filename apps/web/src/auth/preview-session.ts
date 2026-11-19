import type { UserRole } from '../types/ui';
import { appMode, devServer } from '../config/runtime-config';

// This enables sample UI only. It never grants backend permissions.
// Preview identities are usable only in the explicit presentation build or
// local sandbox server. Stale environment flags cannot restore a production session.
export const previewEnabled =
  appMode === 'presentation' ||
  (appMode === 'sandbox' && (devServer || import.meta.env.MODE === 'test'));
export const previewSessionKey = 'classsync.preview.v1';
export const previewSessionLifetime = 8 * 60 * 60 * 1000;
export interface PreviewSession {
  role: UserRole;
  startedAt: number;
}

export function clearPreviewSession() {
  try {
    window.sessionStorage.removeItem(previewSessionKey);
  } catch {
    /* Storage may be blocked. */
  }
}

export function readPreviewSessionState(): PreviewSession | null {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(previewSessionKey) ?? 'null');
    const now = Date.now();
    if (
      previewEnabled &&
      value?.version === 1 &&
      ['student', 'teacher', 'administrator'].includes(value.role) &&
      Number.isFinite(value.startedAt) &&
      value.startedAt <= now &&
      now < value.startedAt + previewSessionLifetime
    )
      return { role: value.role, startedAt: value.startedAt };
  } catch {
    /* Invalid or unavailable storage must not break navigation. */
  }
  clearPreviewSession();
  return null;
}

export function readPreviewSession(): UserRole | null {
  return readPreviewSessionState()?.role ?? null;
}

export function writePreviewSession(role: UserRole) {
  const session: PreviewSession = { role, startedAt: Date.now() };
  try {
    window.sessionStorage.setItem(previewSessionKey, JSON.stringify({ version: 1, ...session }));
  } catch {
    /* Keep an in-memory preview usable when storage is blocked. */
  }
  return session;
}
