import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RoleScheduleWorkspace as StructuredCalendarPage } from './RoleScheduleWorkspace';
import { timetableRequest } from '../lib/publication-api';
import { addDays, calendarDateLabel, manilaToday } from '../lib/calendar-model';
import { readWorkspace } from '../lib/workspace-context';
vi.mock('../lib/publication-api', () => ({
  timetableRequest: vi.fn(),
  subscribeTimetable: () => () => {},
}));
const date = addDays(manilaToday(), 1);
const event = {
  id: 'class-a',
  assignment_id: 'a',
  offering_id: 'o',
  date,
  starts_at: date + 'T09:00:00+08:00',
  ends_at: date + 'T10:30:00+08:00',
  changed: false,
  subject: { id: 's', code: 'SYN-A', name: 'Synthetic computing' },
  section: { id: 'syn-bsit-3-A', name: 'BSIT 3A' },
  teacher: { id: 'teacher-a', name: 'Sample Instructor A' },
  room: {
    id: 'synthetic-room-1',
    name: 'Synthetic Room 1',
    building: 'Synthetic facility',
    floor: null,
  },
};
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(timetableRequest).mockImplementation(async (path) =>
    path.endsWith('periods')
      ? {
          periods: [
            {
              id: 'period-a',
              title: 'Sample',
              revision: 1,
              calendar: {
                academic_year: '2026-2027',
                semester: 'first',
                effective_start: '2026-01-01',
                effective_end: '2026-12-31',
              },
            },
          ],
        }
      : {
          version: 'version-a',
          sequence: 1,
          status: 'published',
          calendar: { academic_year: '2026-2027', semester: 'first' },
          sections: [
            { id: 'syn-bsit-3-A', program_id: 'bsit', year_level: 3, section_letter: 'A' },
          ],
          teachers: [event.teacher],
          occurrences: [event],
        },
  );
});
afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});
describe('shared role schedule context', () => {
  it('defaults to a published sample identity and retains context from Home to Schedule', async () => {
    render(
      <MemoryRouter initialEntries={['/student/dashboard']}>
        <Routes>
          <Route
            path="/student/dashboard"
            element={<StructuredCalendarPage role="student" dashboard />}
          />
          <Route path="/student/schedule" element={<StructuredCalendarPage role="student" />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: event.subject.name })).toBeInTheDocument();
    expect(screen.getByLabelText('Next class')).toHaveTextContent('Synthetic facility');
    expect(screen.getByLabelText('Next class')).toHaveTextContent('Sample Instructor A');
    expect(screen.getByRole('combobox', { name: 'Academic period' })).not.toBeVisible();
    await waitFor(() => expect(readWorkspace('student').identity).toBe('syn-bsit-3-A'));
    fireEvent.click(screen.getByRole('link', { name: 'Open Schedule' }));
    fireEvent.click(screen.getByRole('button', { name: `${calendarDateLabel(date)}, 1 classes` }));
    const row = within(document.querySelector('.ux-agenda') as HTMLElement).getByRole('button', {
      name: /09:00.*Synthetic computing/,
    });
    fireEvent.click(row);
    expect(screen.getByRole('dialog')).toHaveTextContent('Synthetic Room 1');
    fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(readWorkspace('student').date).toBe(date));
  });
  it('uses the chosen faculty identity and never exposes Administrator controls', async () => {
    render(
      <MemoryRouter>
        <StructuredCalendarPage role="teacher" dashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByLabelText('Next teaching assignment')).toHaveTextContent(
      event.subject.name,
    );
    await waitFor(() => expect(readWorkspace('teacher').identity).toBe('teacher-a'));
    expect(screen.queryByText('Generate Weekly Schedule')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review requests and status' })).toHaveAttribute(
      'href',
      '/teacher/change-requests',
    );
  });
  it('shows a recoverable service failure without an empty agenda or invented classes', async () => {
    vi.mocked(timetableRequest).mockRejectedValue(new Error('Academic service unavailable'));
    render(
      <MemoryRouter>
        <StructuredCalendarPage role="student" dashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Academic service unavailable');
    expect(screen.queryByText('No classes on this date.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Next class')).not.toBeInTheDocument();
  });
  it('never requests a stale entered draft from anonymous review and provides sample recovery', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ data: { drafts: [] } }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetcher);
    render(
      <MemoryRouter initialEntries={['/student/dashboard?review=private-entered-draft']}>
        <StructuredCalendarPage role="student" dashboard />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('saved sample is unavailable');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toContain('/calendar-samples');
    expect(screen.getByRole('button', { name: 'Change sample' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Next class')).not.toBeInTheDocument();
  });
});
