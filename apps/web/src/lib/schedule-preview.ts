import type {
  PreviewRequest,
  ScheduleOccurrence,
  SchedulePreviewData,
  ScheduleViewer,
} from '../data/schedule-preview';

export type ScheduleState = 'ready' | 'no-classes' | 'finished' | 'unpublished' | 'unavailable';
export interface DaySchedule {
  state: ScheduleState;
  reference: string;
  today: ScheduleOccurrence[];
  remaining: ScheduleOccurrence[];
  current: ScheduleOccurrence[];
  next: ScheduleOccurrence | null;
  simultaneousNext: ScheduleOccurrence[];
}

const ordered = (records: readonly ScheduleOccurrence[]) =>
  [...records].sort((a, b) => a.startsAt.localeCompare(b.startsAt) || a.id.localeCompare(b.id));

// Assignment IDs, not section labels, determine the Student preview scope.
export function selectAssignments(
  data: SchedulePreviewData | null,
  viewer: ScheduleViewer,
): ScheduleOccurrence[] | null {
  if (!data) return null;
  if (viewer.role === 'administrator') return ordered(data.occurrences);
  if (viewer.role === 'teacher')
    return ordered(data.occurrences.filter((item) => item.teacher.id === viewer.id));
  const student = data.students.find((item) => item.id === viewer.id);
  if (!student) return null;
  const ids = new Set(student.assignmentIds);
  const records = data.occurrences.filter((item) => ids.has(item.id));
  // A broken reference is missing data, not an empty timetable.
  return records.length === ids.size ? ordered(records) : null;
}

export function onDay(item: ScheduleOccurrence, date: string): boolean {
  return item.startsAt < `${date}T24:00` && item.endsAt > `${date}T00:00`;
}

export function summarizeDay(
  records: readonly ScheduleOccurrence[] | null,
  reference: string,
): DaySchedule {
  const empty: DaySchedule = {
    state: 'unavailable',
    reference,
    today: [],
    remaining: [],
    current: [],
    next: null,
    simultaneousNext: [],
  };
  if (!records) return empty;
  const published = ordered(records.filter((item) => item.publication === 'published'));
  const date = reference.slice(0, 10);
  const today = published.filter((item) => onDay(item, date));
  const remaining = today.filter((item) => item.endsAt > reference);
  const current = remaining.filter((item) => item.startsAt <= reference);
  const upcoming = published.filter((item) => item.startsAt > reference);
  const next = upcoming[0] ?? null;
  const unpublished = !published.length && records.some((item) => item.publication === 'draft');
  return {
    state: unpublished
      ? 'unpublished'
      : !today.length
        ? 'no-classes'
        : !remaining.length
          ? 'finished'
          : 'ready',
    reference,
    today,
    remaining,
    current,
    next,
    simultaneousNext: next ? upcoming.filter((item) => item.startsAt === next.startsAt) : [],
  };
}

export function selectRequests(data: SchedulePreviewData, teacherId?: string): PreviewRequest[] {
  return data.requests
    .filter((item) => {
      if (!teacherId) return true;
      const assignment = data.occurrences.find((record) => record.id === item.assignmentId);
      return item.teacherId === teacherId && (!assignment || assignment.teacher.id === teacherId);
    })
    .sort(
      (a, b) =>
        Number(b.status === 'pending') - Number(a.status === 'pending') ||
        b.updatedAt.localeCompare(a.updatedAt) ||
        a.id.localeCompare(b.id),
    );
}

export function summarizeAdministration(data: SchedulePreviewData | null, reference: string) {
  if (!data) return null;
  const today = ordered(
    data.occurrences.filter(
      (item) => item.publication !== 'cancelled' && onDay(item, reference.slice(0, 10)),
    ),
  );
  const conflicts = data.conflicts.filter((item) => item.status === 'open');
  const pending = selectRequests(data).filter((item) => item.status === 'pending');
  return {
    today,
    conflicts,
    pending,
    publishedCount: today.filter((item) => item.publication === 'published').length,
    draftCount: today.filter((item) => item.publication === 'draft').length,
    attentionCount: conflicts.length + pending.length,
    // These four metrics share the entire supplied preview scope, not today's list.
    recordCounts: {
      published: data.occurrences.filter((item) => item.publication === 'published').length,
      draft: data.occurrences.filter((item) => item.publication === 'draft').length,
      conflicts: conflicts.length,
      pending: pending.length,
    },
  };
}

export function remainingAfterSummary(schedule: DaySchedule): ScheduleOccurrence[] {
  const featured = new Set([...schedule.current.map((item) => item.id), schedule.next?.id]);
  return schedule.remaining.filter((item) => !featured.has(item.id));
}

export function summarizeResources(data: SchedulePreviewData | null) {
  if (!data?.resources) return null;
  return {
    total: data.resources.length,
    active: data.resources.filter((room) => room.condition === 'active').length,
    maintenance: data.resources.filter((room) => room.condition === 'maintenance'),
  };
}

export function selectUpdates(
  data: SchedulePreviewData,
  assignments: readonly ScheduleOccurrence[],
) {
  const ids = new Set(
    assignments.filter((item) => item.publication === 'published').map((item) => item.id),
  );
  return data.updates.filter((item) => ids.has(item.assignmentId));
}

export function formatPreviewDate(date: string): string {
  // UTC is only a deterministic formatting frame for a timezone-free calendar date.
  // It does not establish an institutional timezone or convert an occurrence.
  const [year, month, day] = date.slice(0, 10).split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function formatTimeRange(item: ScheduleOccurrence): string {
  const start = item.startsAt.slice(11, 16),
    end = item.endsAt.slice(11, 16);
  return `${start}–${end}${item.startsAt.slice(0, 10) === item.endsAt.slice(0, 10) ? '' : ` (${formatPreviewDate(item.endsAt)})`}`;
}
