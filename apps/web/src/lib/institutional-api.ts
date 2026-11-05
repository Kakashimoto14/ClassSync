import { appMode } from '../config/runtime-config';
import { env } from './env';
import { firebaseApp } from './firebase';
import type { UserRole } from '../types/ui';

/** Same-origin transport only; every service independently checks current membership. */
export async function institutionalRequest<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
    role?: UserRole;
    timeout?: number;
  } = {},
): Promise<T> {
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
  try {
    const { getAuth } = await Promise.race([import('firebase/auth'), aborted]);
    const user = firebaseApp ? getAuth(firebaseApp).currentUser : null;
    if (!user)
      throw Object.assign(new Error('Sign in to access university services.'), { status: 401 });
    const token = await Promise.race([user.getIdToken(), aborted]);
    if (getAuth(firebaseApp!).currentUser !== user || controller.signal.aborted)
      throw new DOMException('Request cancelled', 'AbortError');
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
      throw new Error('The university service is unavailable. Please retry.');
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
    if (controller.signal.aborted)
      throw new Error('The university request timed out. Please retry.');
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', cancel);
  }
}
