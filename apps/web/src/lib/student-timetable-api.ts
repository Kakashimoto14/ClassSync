import { appMode } from '../config/runtime-config';
import { env } from './env';
import { firebaseApp } from './firebase';

/** Bounded read-only exception; other institutional clients remain closed. */
export async function studentTimetableRequest<T>(path: string, signal?: AbortSignal): Promise<T> {
  if (appMode !== 'institutional' || !/^(periods|calendar\/[A-Za-z0-9_-]+)(\?[^#]*)?$/.test(path))
    throw Object.assign(new Error('Student timetable access required.'), { status: 403 });
  const base = new URL(env.apiBaseUrl, window.location.origin);
  if (
    base.origin !== window.location.origin ||
    base.search ||
    base.hash ||
    base.username ||
    base.password
  )
    throw new Error('Use the configured same-origin Gateway for Student schedules.');
  if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  const timeout = window.setTimeout(cancel, 10000);
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
    if (!user) throw Object.assign(new Error('Sign in to view your schedule.'), { status: 401 });
    const token = await Promise.race([user.getIdToken(), aborted]);
    if (getAuth(firebaseApp!).currentUser !== user || controller.signal.aborted)
      throw new DOMException('Request cancelled', 'AbortError');
    const response = await fetch(`${base.href.replace(/\/$/, '')}/timetables/${path}`, {
      signal: controller.signal,
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      headers: { Authorization: `Bearer ${token}`, 'X-ClassSync-Role': 'student' },
    });
    if (!response.headers.get('content-type')?.includes('application/json'))
      throw new Error('The timetable service is unavailable.');
    const payload = await Promise.race([response.json(), aborted]);
    if (!response.ok)
      throw Object.assign(new Error('Your timetable could not be retrieved.'), {
        status: response.status,
      });
    if (getAuth(firebaseApp!).currentUser !== user)
      throw Object.assign(new Error('Session changed.'), { status: 401 });
    return payload.data as T;
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    if (controller.signal.aborted)
      throw new Error('The timetable request timed out. Please retry.');
    throw error;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', cancel);
  }
}
