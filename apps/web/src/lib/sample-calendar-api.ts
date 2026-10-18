import { env } from './env';
import type { CalendarData } from './calendar-model';

export type CalendarSample = { id: string; title: string; period_id?: string };
async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}/scheduling/sandbox/${path}`, { signal }).catch(
    (error) => {
      if (error.name === 'AbortError') throw error;
      throw new Error('Could not reach the sample timetable service. Start npm run dev and retry.');
    },
  );
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('Sample timetable service unavailable. Check the canonical local startup.');
  const payload = await response.json();
  if (!response.ok)
    throw Object.assign(
      new Error(payload.error?.message ?? payload.detail ?? 'Sample timetable unavailable.'),
      { status: response.status },
    );
  return payload.data as T;
}
export async function listCalendarSamples(signal?: AbortSignal) {
  const samples: CalendarSample[] = [];
  let more = true;
  while (more) {
    const page = await request<{ drafts: CalendarSample[]; has_more: boolean }>(
      `calendar-samples?limit=100&offset=${samples.length}`,
      signal,
    );
    samples.push(...page.drafts);
    more = page.has_more && page.drafts.length > 0;
  }
  return samples;
}
export const loadSampleCalendar = (draft: string, query: string, signal?: AbortSignal) =>
  request<CalendarData>(`calendar/${encodeURIComponent(draft)}?${query}`, signal);
