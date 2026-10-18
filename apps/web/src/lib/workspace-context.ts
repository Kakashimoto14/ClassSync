import { readPreviewSessionState } from '../auth/preview-session';
import type { UserRole } from '../types/ui';
import { manilaToday } from './calendar-model';

export interface WorkspaceContext {
  period: string;
  identity: string;
  mode: 'published' | 'review';
  draft: string;
  date: string;
  view?: 'day' | 'week' | 'month';
}
const empty = (): WorkspaceContext => ({
  period: '',
  identity: '',
  mode: 'published',
  draft: '',
  date: manilaToday(),
});
export function readWorkspace(role: UserRole): WorkspaceContext {
  try {
    const value = JSON.parse(sessionStorage.getItem(`classsync.workspace.v2.${role}`) ?? 'null');
    if (value?.session !== (readPreviewSessionState()?.startedAt ?? 0)) return empty();
    const c = value.context;
    if (
      !c ||
      !['published', 'review'].includes(c.mode) ||
      ['period', 'identity', 'draft', 'date'].some((k) => typeof c[k] !== 'string')
    )
      return empty();
    return {
      ...c,
      view: ['day', 'week', 'month'].includes(c.view) ? c.view : 'week',
      date:
        /^\d{4}-\d{2}-\d{2}$/.test(c.date) && Number.isFinite(Date.parse(c.date))
          ? c.date
          : manilaToday(),
    };
  } catch {
    return empty();
  }
}
export function rememberWorkspace(role: UserRole, context: WorkspaceContext) {
  try {
    sessionStorage.setItem(
      `classsync.workspace.v2.${role}`,
      JSON.stringify({ session: readPreviewSessionState()?.startedAt ?? 0, context }),
    );
  } catch {
    /* Optional session storage. */
  }
}
export type WorkspacePeriod = {
  id: string;
  title: string;
  revision?: number;
  calendar?: {
    academic_year: string;
    semester: string;
    effective_start: string;
    effective_end: string;
  } | null;
};
export function periodLabel(period: WorkspacePeriod) {
  const c = period.calendar;
  return c
    ? `AY ${c.academic_year} · ${c.semester === 'first' ? '1st' : '2nd'} Semester${/synthetic|sample|s2b|review|cross.client/i.test(period.title) ? ' — Sample' : ''}`
    : period.title.replace(/S2B\s*/gi, '').replace(/entered review period/i, 'Academic period');
}
export function defaultPeriod(periods: WorkspacePeriod[], preferred = '') {
  if (periods.some((p) => p.id === preferred)) return preferred;
  const today = manilaToday();
  return (
    [...periods].sort(
      (a, b) =>
        Number((b.revision ?? 0) > 0) - Number((a.revision ?? 0) > 0) ||
        Number(
          !!b.calendar && b.calendar.effective_start <= today && today <= b.calendar.effective_end,
        ) -
          Number(
            !!a.calendar &&
              a.calendar.effective_start <= today &&
              today <= a.calendar.effective_end,
          ),
    )[0]?.id ?? ''
  );
}
