import { appMode, devServer } from '../config/runtime-config';
import { env } from '../lib/env';
import {
  UniversitySessionError,
  parseUniversityMembership,
  parseAvailableRoles,
  type UniversitySessionDriver,
} from './university-session';

export function identityEndpoint(path = '/auth/me') {
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
  url.pathname = url.pathname.replace(/\/$/, '') + path;
  return url.toString();
}

/** Identity-only exception to the still-disabled institutional data API boundary. */
export async function loadUniversitySessionDriver(): Promise<UniversitySessionDriver | null> {
  if (appMode !== 'institutional') return null;
  let endpoint: string;
  try {
    endpoint = identityEndpoint();
  } catch (error) {
    if (devServer) console.warn('[ClassSync auth] VITE_API_BASE_URL is invalid.');
    throw error;
  }
  const { firebaseApp, firebaseReadiness } = await import('../lib/firebase');
  if (!firebaseApp) {
    if (devServer)
      console.warn(
        '[ClassSync auth] Firebase setup:',
        firebaseReadiness.status,
        firebaseReadiness.missing.map(
          (name) =>
            ({
              apiKey: 'VITE_FIREBASE_API_KEY',
              authDomain: 'VITE_FIREBASE_AUTH_DOMAIN',
              projectId: 'VITE_FIREBASE_PROJECT_ID',
              storageBucket: 'VITE_FIREBASE_STORAGE_BUCKET',
              messagingSenderId: 'VITE_FIREBASE_MESSAGING_SENDER_ID',
              appId: 'VITE_FIREBASE_APP_ID',
            })[name],
        ),
      );
    return null;
  }
  if (devServer) {
    try {
      const response = await fetch(endpoint, {
        credentials: 'omit',
        cache: 'no-store',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
        signal: AbortSignal.timeout(3500),
      });
      if (
        response.status !== 401 ||
        (await response.json())?.error?.code !== 'authentication_required'
      )
        throw new Error('Unexpected auth boundary response');
    } catch {
      console.warn(
        '[ClassSync auth] Gateway auth probe failed. Check the API proxy and Gateway health.',
      );
      return null;
    }
  }
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
          throw new UniversitySessionError(
            'role-required',
            parseAvailableRoles(payload.error.available_roles),
          );
        if (response.status === 403 && payload?.error?.code === 'email_verification_required')
          throw new UniversitySessionError('verification-required');
        if (response.status === 401) throw new UniversitySessionError('expired');
        throw new UniversitySessionError(response.status === 403 ? 'denied' : 'unavailable');
      }
      return parseUniversityMembership(payload, user.uid, role);
    },
  };
}
