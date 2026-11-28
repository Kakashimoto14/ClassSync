import { appMode } from '../config/runtime-config';
import { env } from './env';
import { firebaseApp } from './firebase';
import { retryTransientRead, transientFailure } from './transient';
import type { UserRole } from '../types/ui';

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  role?: UserRole;
  timeout?: number;
}

/** Only reads are retried: a repeated mutation could be applied twice. */
export function institutionalRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const read = (options.method ?? 'GET') === 'GET';
  const request = read
    ? retryTransientRead(() => send<T>(path, options), options.signal)
    : send<T>(path, options);
  // fetch rejects with TypeError when the network drops; say what that means for the user.
  return request.catch((error: unknown) => {
    if (!(error instanceof TypeError)) throw error;
    throw new Error(
      read
        ? "Couldn't load from the university service. Check your connection, then retry."
        : 'The university service could not be reached. No change was confirmed.',
    );
  });
}

/** Same-origin transport only; every service independently checks current membership. */
async function send<T>(path: string, options: RequestOptions): Promise<T> {
  if (
    appMode !== 'institutional' ||
    !/^(academic|scheduling|timetables|community)\//.test(path) ||
    path.includes('..') ||
    path.includes('\\') ||
    path.includes('#') ||
    /(^|\/)sandbox(\/|$)/.test(path)
  )
    throw Object.assign(new Error('University service access required.'), { status: 403 });
  const base = new URL(env.apiBaseUrl, window.location.origin);
  if (
    base.origin !== window.location.origin ||
    base.search ||
    base.hash ||
    base.username ||
    base.password
  )
    throw new Error('Use the configured same-origin Gateway for university services.');
  if (options.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
  const controller = new AbortController();
  const cancel = () => controller.abort();
  options.signal?.addEventListener('abort', cancel, { once: true });
  const timer = window.setTimeout(cancel, options.timeout ?? 10000);
  const aborted = new Promise<never>((_, reject) => {
    controller.signal.addEventListener(
      'abort',
      () => reject(new DOMException('Request cancelled', 'AbortError')),
      { once: true },
    );
  });
  let sent = false;
  try {
    const { getAuth } = await Promise.race([import('firebase/auth'), aborted]);
    const user = firebaseApp ? getAuth(firebaseApp).currentUser : null;
    if (!user)
      throw Object.assign(new Error('Sign in to access university services.'), { status: 401 });
    const token = await Promise.race([user.getIdToken(), aborted]);
    if (getAuth(firebaseApp!).currentUser !== user || controller.signal.aborted)
      throw new DOMException('Request cancelled', 'AbortError');
    sent = true;
    const response = await fetch(`${base.href.replace(/\/$/, '')}/${path}`, {
      method: options.method ?? 'GET',
      signal: controller.signal,
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.role ? { 'X-ClassSync-Role': options.role } : {}),
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    });
    if (!response.headers.get('content-type')?.includes('application/json'))
      throw Object.assign(
        new Error(
          (options.method ?? 'GET') === 'GET'
            ? "Couldn't load from the university service. Please retry."
            : 'The university service is unavailable. No change was confirmed.',
        ),
        { status: response.status },
      );
    const payload = await Promise.race([response.json(), aborted]);
    if (getAuth(firebaseApp!).currentUser !== user)
      throw Object.assign(new Error('Session changed.'), { status: 401 });
    if (!response.ok) {
      const detail = payload.error?.message ?? payload.detail?.error?.message ?? payload.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((item: { msg?: string }) => item.msg ?? 'Invalid value').join('; ')
            : 'Your request could not be completed. Check your access and inputs, then retry.';
      throw Object.assign(new Error(message), { status: response.status });
    }
    return payload.data as T;
  } catch (error) {
    if (options.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    if (controller.signal.aborted) {
      const message =
        (options.method ?? 'GET') === 'GET'
          ? "Couldn't load: the university request timed out. Please retry."
          : 'The university request timed out. No change was confirmed. Refresh before retrying.';
      // A stalled sign-in token is not a service cold start; only retry a sent request.
      throw sent ? transientFailure(message) : new Error(message);
    }
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', cancel);
  }
}
