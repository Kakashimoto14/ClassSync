import { useEffect, useState, type ReactNode } from 'react';
import { DevelopmentRoleContext } from './development-role-context';
import type { UserRole } from '../types/ui';
import {
  clearPreviewSession,
  previewEnabled,
  previewSessionLifetime,
  readPreviewSessionState,
  writePreviewSession,
} from './preview-session';

export function DevelopmentRoleProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState(readPreviewSessionState);
  const role = session?.role ?? null;
  useEffect(() => {
    if (!session) return;
    const timeout = window.setTimeout(
      () => {
        clearPreviewSession();
        setSession(null);
      },
      Math.max(0, session.startedAt + previewSessionLifetime - Date.now()),
    );
    return () => window.clearTimeout(timeout);
  }, [session]);
  // A history restoration must not revive a preview after Exit in another document
  // in this tab. Ordinary React Router navigation keeps the provider mounted.
  useEffect(() => {
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) setSession(readPreviewSessionState());
    };
    window.addEventListener('pageshow', restore);
    return () => window.removeEventListener('pageshow', restore);
  }, []);
  const startDemo = (selected: UserRole) => {
    if (!previewEnabled) return;
    setSession(writePreviewSession(selected));
  };
  const signOut = () => {
    clearPreviewSession();
    setSession(null);
  };
  return (
    <DevelopmentRoleContext.Provider value={{ role, startDemo, signOut }}>
      {children}
    </DevelopmentRoleContext.Provider>
  );
}
