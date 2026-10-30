import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { appMode } from '../config/runtime-config';
import type { UserRole } from '../types/ui';
import { createUniversitySession, type UniversitySession } from './university-session';
import { UniversitySessionContext } from './university-session-context';
import { loadUniversitySessionDriver } from './university-session-driver';

function ConnectedSessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<UniversitySession>({ status: 'checking' });
  const [available, setAvailable] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const current = useRef<ReturnType<typeof createUniversitySession> | null>(null);
  useEffect(() => {
    queryClient.clear();
    let closed = false;
    let owned: ReturnType<typeof createUniversitySession> | null = null;
    const revalidate = () => {
      if (navigator.onLine) owned?.online();
      else owned?.offline();
    };
    const offline = () => owned?.offline();
    const visible = () => {
      if (document.visibilityState === 'visible') revalidate();
    };
    void loadUniversitySessionDriver()
      .then((driver) => {
        if (closed) return;
        if (!driver) {
          setAvailable(false);
          setState({ status: 'unavailable' });
          return;
        }
        setAvailable(true);
        owned = createUniversitySession(driver, (next) => {
          if (closed) return;
          if (next.status !== 'authorized') queryClient.clear();
          setState(next);
        });
        current.current = owned;
        if (!navigator.onLine) owned.offline();
        window.addEventListener('focus', revalidate);
        window.addEventListener('pageshow', revalidate);
        window.addEventListener('online', revalidate);
        window.addEventListener('offline', offline);
        document.addEventListener('visibilitychange', visible);
      })
      .catch(() => {
        if (!closed) {
          queryClient.clear();
          setState({ status: 'unavailable' });
        }
      });
    return () => {
      closed = true;
      owned?.dispose();
      if (current.current === owned) current.current = null;
      window.removeEventListener('focus', revalidate);
      window.removeEventListener('pageshow', revalidate);
      window.removeEventListener('online', revalidate);
      window.removeEventListener('offline', offline);
      document.removeEventListener('visibilitychange', visible);
      queryClient.clear();
    };
  }, [attempt, queryClient]);
  const refresh = useCallback((role?: UserRole) => {
    if (current.current) {
      if (navigator.onLine) current.current.online(role);
      else current.current.offline();
    } else {
      setState({ status: 'checking' });
      setAttempt((value) => value + 1);
    }
  }, []);
  const signOut = useCallback(() => {
    void current.current?.signOut();
  }, []);
  const value = useMemo(
    () => ({ available, state, refresh, signOut }),
    [available, state, refresh, signOut],
  );
  return (
    <UniversitySessionContext.Provider value={value}>{children}</UniversitySessionContext.Provider>
  );
}

export function UniversitySessionProvider({ children }: { children: ReactNode }) {
  return appMode === 'institutional' ? (
    <ConnectedSessionProvider>{children}</ConnectedSessionProvider>
  ) : (
    <>{children}</>
  );
}
