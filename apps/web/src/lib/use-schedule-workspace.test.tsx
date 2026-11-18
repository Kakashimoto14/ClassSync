import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { useScheduleWorkspace } from './use-schedule-workspace';
import { studentTimetableRequest } from './student-timetable-api';
import { institutionalRequest } from './institutional-api';
vi.mock('./institutional-api', () => ({ institutionalRequest: vi.fn() }));
vi.mock('../config/runtime-config', async () => {
  const { capabilitiesFor } = await import('../config/app-mode');
  return { appMode: 'institutional', capabilities: capabilitiesFor('institutional') };
});
vi.mock('./student-timetable-api', () => ({ studentTimetableRequest: vi.fn() }));
vi.mock('./calendar-model', async (original) => ({
  ...(await original<typeof import('./calendar-model')>()),
  manilaToday: () => '2026-11-01',
}));
beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});
it('retrieves the complete displayed week across a month boundary and clears old records after denial', async () => {
  const occurrence = {
    id: 'previous-month-class',
    starts_at: '2026-10-30T09:00:00+08:00',
    ends_at: '2026-10-30T10:00:00+08:00',
  };
  vi.mocked(studentTimetableRequest).mockImplementation(async (path) =>
    path === 'periods'
      ? ({ periods: [{ id: 'p', title: 'Synthetic term' }] } as never)
      : ({
          status: 'published',
          version: 'v1',
          occurrences: [occurrence],
          sections: [],
          teachers: [],
        } as never),
  );
  const { result, unmount } = renderHook(() => useScheduleWorkspace('student', true), {
    wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter>,
  });
  await waitFor(() => expect(result.current.records).toEqual([occurrence]));
  const paths = vi.mocked(studentTimetableRequest).mock.calls.map(([path]) => path);
  expect(paths.some((path) => path.startsWith('calendar/p?start=2026-10-26&'))).toBe(true);
  expect(paths.some((path) => path.includes('end=2026-12-27'))).toBe(true);
  vi.mocked(studentTimetableRequest).mockRejectedValue(
    Object.assign(new Error('Denied'), { status: 403 }),
  );
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.errorStatus).toBe(403));
  expect(result.current.records).toEqual([]);
  unmount();
});

it('clears teaching assignments when a successful refresh removes all authorized periods', async () => {
  vi.mocked(institutionalRequest).mockImplementation(async (path) =>
    path.endsWith('/periods')
      ? ({ periods: [{ id: 'teaching-period', title: 'Invented teaching period' }] } as never)
      : ({
          status: 'published',
          version: 'v1',
          occurrences: [{ id: 'old-teaching-class' }],
          sections: [],
          teachers: [],
        } as never),
  );
  const { result, unmount } = renderHook(() => useScheduleWorkspace('teacher'), {
    wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter>,
  });
  await waitFor(() => expect(result.current.records).toHaveLength(1));
  vi.mocked(institutionalRequest).mockResolvedValue({ periods: [] });
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.context.period).toBe(''));
  expect(result.current.records).toEqual([]);
  expect(result.current.data).toBeNull();
  unmount();
});
