import { appMode } from '../config/runtime-config';
import { env } from '../lib/env';
import {
  UniversitySessionError,
  parseUniversityMembership,
  type UniversitySessionDriver,
} from './university-session';

function identityEndpoint() {
  const base = env.apiBaseUrl;
  if (base.includes('\\')) throw new UniversitySessionError('unavailable');
  if (!base.startsWith('/') && !/^https?:\/\//.test(base))
    throw new UniversitySessionError('unavailable');
  const url = new URL(base, window.location.origin);
  if (base.startsWith('/') && url.origin !== window.location.origin)
    throw new UniversitySessionError('unavailable');
  if (
    base.startsWith('//') ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (url.protocol !== 'https:' &&
      !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)))
  ) {
    throw new UniversitySessionError('unavailable');
  }
  url.pathname = url.pathname.replace(/\/$/, '') + '/auth/me';
  return url.toString();
}

/** Identity-only exception to the still-disabled institutional data API boundary. */
export async function loadUniversitySessionDriver(): Promise<UniversitySessionDriver | null> {
  if (appMode !== 'institutional') return null;
  const endpoint = identityEndpoint();
  const { firebaseApp } = await import('../lib/firebase');
  if (!firebaseApp) return null;
  const { getAuth, onIdTokenChanged, signOut } = await import('firebase/auth');
  const auth = getAuth(firebaseApp);
  return {
    observe: (next, error) => onIdTokenChanged(auth, next, error),
    signOut: () => signOut(auth),
    lookup: async (user, role, signal) => {
      if (!navigator.onLine) throw new UniversitySessionError('offline');
      if (auth.currentUser?.uid !== user.uid) throw new UniversitySessionError('denied');
      const token = await user.getIdToken();
      if (signal.aborted) throw new UniversitySessionError('unavailable');
      if (auth.currentUser?.uid !== user.uid) throw new UniversitySessionError('denied');
      const response = await fetch(endpoint, {
        method: 'GET',
        credentials: 'omit',
        redirect: 'error',
        cache: 'no-store',
        referrerPolicy: 'no-referrer',
        signal,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(role ? { 'X-ClassSync-Role': role } : {}),
        },
      });
      if (!response.headers.get('content-type')?.includes('application/json'))
        throw new UniversitySessionError('unavailable');
      const payload = await response.json();
      if (auth.currentUser?.uid !== user.uid) throw new UniversitySessionError('denied');
      if (!response.ok) {
        if (response.status === 403 && payload?.error?.code === 'role_selection_required')
          throw new UniversitySessionError('role-required');
        throw new UniversitySessionError(
          response.status === 401 || response.status === 403 ? 'denied' : 'unavailable',
        );
      }
      return parseUniversityMembership(payload, user.uid, role);
    },
  };
}
