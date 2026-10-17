import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DevelopmentRoleProvider } from './DevelopmentRoleProvider';
import { useDevelopmentRole } from './useDevelopmentRole';
import type { DevelopmentRoleContextValue } from './development-role-context';
import {
  previewSessionKey,
  previewSessionLifetime,
  readPreviewSession,
  writePreviewSession,
} from './preview-session';

describe('bounded tab preview storage', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it.each(['student', 'teacher', 'administrator'] as const)(
    'restores %s without extending its lifetime',
    (role) => {
      const now = Date.now();
      vi.spyOn(Date, 'now').mockReturnValue(now);
      writePreviewSession(role);
      expect(readPreviewSession()).toBe(role);
      vi.mocked(Date.now).mockReturnValue(now + previewSessionLifetime);
      expect(readPreviewSession()).toBeNull();
      expect(sessionStorage.getItem(previewSessionKey)).toBeNull();
    },
  );

  it.each([
    'invalid json',
    'null',
    '{}',
    '"student"',
    JSON.stringify({ version: 0, role: 'student', startedAt: Date.now() }),
    JSON.stringify({ version: 1, role: 'superuser', startedAt: Date.now() }),
    JSON.stringify({ version: 1, role: 'teacher', startedAt: Date.now() + 86400000 }),
    JSON.stringify({ version: 1, role: 'student', startedAt: 'today' }),
  ])('discards invalid state: %s', (raw) => {
    sessionStorage.setItem(previewSessionKey, raw);
    expect(readPreviewSession()).toBeNull();
    expect(sessionStorage.getItem(previewSessionKey)).toBeNull();
  });

  it('keeps role selection and exit usable when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    let session: DevelopmentRoleContextValue | undefined;
    function Probe() {
      session = useDevelopmentRole();
      return null;
    }
    render(
      <DevelopmentRoleProvider>
        <Probe />
      </DevelopmentRoleProvider>,
    );
    act(() => session?.startDemo('teacher'));
    expect(session?.role).toBe('teacher');
    act(() => session?.signOut());
    expect(session?.role).toBeNull();
  });

  it('expires a mounted preview without extending it through navigation', () => {
    vi.useFakeTimers();
    try {
      let session: DevelopmentRoleContextValue | undefined;
      function Probe() {
        session = useDevelopmentRole();
        return null;
      }
      const view = render(
        <DevelopmentRoleProvider>
          <Probe />
        </DevelopmentRoleProvider>,
      );
      act(() => session?.startDemo('student'));
      expect(session?.role).toBe('student');
      act(() => vi.advanceTimersByTime(previewSessionLifetime));
      expect(session?.role).toBeNull();
      expect(sessionStorage.getItem(previewSessionKey)).toBeNull();
      view.unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it('disables restoration and role selection in an ordinary production build', async () => {
    vi.resetModules();
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_ENABLE_ROLE_PREVIEW', 'false');
    const disabled = await import('./preview-session');
    writePreviewSession('administrator');
    expect(disabled.previewEnabled).toBe(false);
    expect(disabled.readPreviewSession()).toBeNull();
  });

  it('requires an explicit demo build flag outside development', async () => {
    vi.resetModules();
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_ENABLE_ROLE_PREVIEW', 'true');
    const demo = await import('./preview-session');
    expect(demo.previewEnabled).toBe(true);
    demo.writePreviewSession('student');
    expect(demo.readPreviewSession()).toBe('student');
  });
});
