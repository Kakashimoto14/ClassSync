import { describe, expect, it } from 'vitest';
import { previewContext, schedulePreview, type ScheduleOccurrence } from '../data/schedule-preview';
import {
  formatTimeRange,
  selectAssignments,
  selectRequests,
  selectUpdates,
  summarizeAdministration,
  summarizeDay,
  summarizeResources,
} from './schedule-preview';

const student = () => selectAssignments(schedulePreview, { role: 'student', id: 'student-maria' });
const teacher = () => selectAssignments(schedulePreview, { role: 'teacher', id: 'teacher-santos' });
const occurrence = (changes: Partial<ScheduleOccurrence> = {}): ScheduleOccurrence => ({
  ...schedulePreview.occurrences[1],
  ...changes,
});

describe('explicit, deterministic preview assignments', () => {
  it('selects a student across sections by assignment ID, without leaking other records', () => {
    expect(student()?.map((item) => item.id)).toEqual([
      'occ-hci-mon',
      'occ-database-mon',
      'occ-web-mon',
      'occ-database-tue',
    ]);
    expect(new Set(student()?.map((item) => item.section.id)).size).toBe(2);
    expect(student()?.some((item) => item.id === 'occ-networks-mon')).toBe(false);
  });
  it('selects only the teaching assignments and requests owned by the teacher', () => {
    expect(teacher()).toHaveLength(3);
    expect(teacher()?.every((item) => item.teacher.id === 'teacher-santos')).toBe(true);
    expect(selectRequests(schedulePreview, 'teacher-cruz')).toEqual([]);
    expect(selectRequests(schedulePreview, 'teacher-santos')).toHaveLength(2);
  });
  it('treats missing data and broken assignment references as unavailable', () => {
    expect(summarizeDay(null, previewContext.reference).state).toBe('unavailable');
    expect(selectAssignments(schedulePreview, { role: 'student', id: 'unknown' })).toBeNull();
    expect(
      selectAssignments(
        { ...schedulePreview, occurrences: [] },
        { role: 'student', id: 'student-maria' },
      ),
    ).toBeNull();
  });
  it('derives next, today, and remaining from the same records', () => {
    const summary = summarizeDay(student(), previewContext.reference);
    expect(summary.today).toHaveLength(3);
    expect(summary.remaining).toHaveLength(2);
    expect(summary.next?.id).toBe('occ-database-mon');
    expect(summary.remaining[0]).toEqual(summary.next);
    expect(summarizeDay(teacher(), previewContext.reference).today).toHaveLength(2);
  });
  it('uses an end-exclusive boundary and distinguishes in-progress from next', () => {
    const start = summarizeDay(student(), '2026-10-12T10:00');
    expect(start.current.map((item) => item.id)).toEqual(['occ-database-mon']);
    expect(start.next?.id).toBe('occ-web-mon');
    expect(summarizeDay(student(), '2026-10-12T11:30').current).toEqual([]);
  });
  it('distinguishes empty, finished, and unpublished schedules', () => {
    expect(summarizeDay([], previewContext.reference).state).toBe('no-classes');
    const finished = summarizeDay(student(), '2026-10-12T14:30');
    expect(finished.state).toBe('finished');
    expect(finished.next?.id).toBe('occ-database-tue');
    expect(
      summarizeDay([occurrence({ publication: 'draft' })], previewContext.reference).state,
    ).toBe('unpublished');
    expect(
      summarizeDay([occurrence({ publication: 'cancelled' })], previewContext.reference).next,
    ).toBeNull();
  });
  it('does not call tomorrow’s class a class today', () => {
    const result = summarizeDay(student(), '2026-10-11T23:59');
    expect(result.state).toBe('no-classes');
    expect(result.today).toEqual([]);
    expect(result.next?.id).toBe('occ-hci-mon');
  });
  it('includes an overnight occurrence on each day until its exclusive end', () => {
    const item = occurrence({ startsAt: '2026-10-12T23:00', endsAt: '2026-10-13T01:00' });
    expect(summarizeDay([item], '2026-10-13T00:00').current).toHaveLength(1);
    expect(summarizeDay([item], '2026-10-13T01:00').state).toBe('finished');
    expect(
      summarizeDay([occurrence({ endsAt: '2026-10-13T00:00' })], '2026-10-13T00:00').today,
    ).toEqual([]);
    expect(formatTimeRange(item)).toMatch(/Tue,? 13 Oct/);
  });
  it('retains overlapping records and uses a stable tie order without claiming clearance', () => {
    const a = occurrence({ id: 'a' }),
      b = occurrence({ id: 'b' });
    const result = summarizeDay([b, a], '2026-10-12T09:00');
    expect(result.next?.id).toBe('a');
    expect(result.simultaneousNext).toHaveLength(2);
    expect(summarizeDay([b, a], '2026-10-12T10:30').current).toHaveLength(2);
  });
  it('derives administrator counts from actual attention and date-scoped records', () => {
    const admin = summarizeAdministration(schedulePreview, previewContext.reference)!;
    expect(admin.today).toHaveLength(4);
    expect(admin.publishedCount).toBe(3);
    expect(admin.draftCount).toBe(1);
    expect(admin.attentionCount).toBe(admin.conflicts.length + admin.pending.length);
    expect(admin.attentionCount).toBe(2);
    expect(admin.recordCounts).toEqual({ published: 4, draft: 1, conflicts: 1, pending: 1 });
    expect(summarizeAdministration(null, previewContext.reference)).toBeNull();
  });
  it('excludes resolved issues and decisions from actionable counts', () => {
    const data = {
      ...schedulePreview,
      requests: schedulePreview.requests.map((item) => ({ ...item, status: 'approved' as const })),
      conflicts: schedulePreview.conflicts.map((item) => ({
        ...item,
        status: 'resolved' as const,
      })),
    };
    expect(summarizeAdministration(data, previewContext.reference)?.recordCounts).toEqual({
      published: 4,
      draft: 1,
      conflicts: 0,
      pending: 0,
    });
  });
  it('does not expose a request with conflicting teacher ownership', () => {
    const data = {
      ...schedulePreview,
      requests: [{ ...schedulePreview.requests[0], assignmentId: 'occ-hci-mon' }],
    };
    expect(selectRequests(data, 'teacher-santos')).toEqual([]);
  });
  it('distinguishes missing resource data from an empty directory', () => {
    expect(summarizeResources(null)).toBeNull();
    expect(summarizeResources({ ...schedulePreview, resources: undefined })).toBeNull();
    expect(summarizeResources({ ...schedulePreview, resources: [] })).toEqual({
      total: 0,
      active: 0,
      maintenance: [],
    });
  });
  it('keeps all fixture references valid and gives each occurrence a stable unique ID', () => {
    const ids = new Set(schedulePreview.occurrences.map((item) => item.id));
    expect(ids.size).toBe(schedulePreview.occurrences.length);
    for (const request of schedulePreview.requests) {
      expect(
        schedulePreview.occurrences.find((item) => item.id === request.assignmentId)?.teacher.id,
      ).toBe(request.teacherId);
    }
    for (const conflict of schedulePreview.conflicts)
      for (const id of conflict.assignmentIds) expect(ids.has(id)).toBe(true);
    expect(selectUpdates(schedulePreview, teacher()!)).toHaveLength(1);
    expect(selectUpdates(schedulePreview, [])).toEqual([]);
  });
});
