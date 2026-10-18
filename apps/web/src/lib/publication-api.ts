import { firebaseApp } from './firebase';
import { env } from './env';

export async function timetableHeaders(): Promise<Record<string, string>> {
  if (!firebaseApp) return {};
  const { getAuth } = await import('firebase/auth');
  const user = getAuth(firebaseApp).currentUser;
  return user ? { Authorization: `Bearer ${await user.getIdToken()}` } : {};
}
export async function timetableRequest<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}/timetables/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(await timetableHeaders()) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal,
  }).catch((error) => {
    if (error.name === 'AbortError') throw error;
    throw new Error(
      'Could not reach the Gateway timetable service. Start npm run dev, then retry. No publication was confirmed.',
    );
  });
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('Timetable service unavailable. No publication was confirmed.');
  const p = await response.json();
  if (!response.ok) {
    const detail = p.error?.message ?? p.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.join('.') ?? ''}: ${d.msg}`).join('; ')
      : typeof detail === 'string'
        ? detail
        : 'Timetable request rejected';
    throw Object.assign(new Error(message), { status: response.status });
  }
  return p.data as T;
}

/** Authenticated fetch streaming; ordered cursor persists across reconnects. */
export function subscribeTimetable(
  path: string,
  onVersion: (sequence: number) => void,
  onConnection: (connected: boolean) => void,
) {
  const controller = new AbortController();
  let cursor = 0;
  let retry = 500;
  const resume = () => onVersion(cursor);
  const visible = () => {
    if (document.visibilityState === 'visible') resume();
  };
  window.addEventListener('online', resume);
  document.addEventListener('visibilitychange', visible);
  async function connect() {
    while (!controller.signal.aborted) {
      try {
        const response = await fetch(`${env.apiBaseUrl}/timetables/${path}&after=${cursor}`, {
          headers: await timetableHeaders(),
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!response.ok || !response.headers.get('content-type')?.includes('text/event-stream'))
          throw new Error('Stream unavailable');
        onConnection(true);
        retry = 500;
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let boundary;
          while ((boundary = buffer.indexOf('\n\n')) >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const data = frame.split('\n').find((line) => line.startsWith('data: '));
            if (data) {
              const event = JSON.parse(data.slice(6));
              if (Number.isSafeInteger(event.sequence) && event.sequence > cursor) {
                cursor = event.sequence;
                onVersion(cursor);
              }
            }
          }
        }
      } catch {
        if (controller.signal.aborted) break;
      }
      onConnection(false);
      await new Promise<void>((resolve) => {
        const finish = () => {
          clearTimeout(id);
          controller.signal.removeEventListener('abort', finish);
          resolve();
        };
        const id = window.setTimeout(finish, retry);
        controller.signal.addEventListener('abort', finish, { once: true });
      });
      retry = Math.min(retry * 2, 15000);
    }
  }
  void connect();
  return () => {
    controller.abort();
    window.removeEventListener('online', resume);
    document.removeEventListener('visibilitychange', visible);
  };
}
