import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentRooms } from './StudentRooms';
import type { CalendarOccurrence } from '../lib/calendar-model';
const fixture = vi.hoisted(() => ({ workspace: {} as Record<string, unknown>, preview: true }));
vi.mock('../lib/use-schedule-workspace', () => ({ useScheduleWorkspace: () => fixture.workspace }));
vi.mock('../lib/presentation-sample', () => ({
  get presentationEnabled() {
    return fixture.preview;
  },
  facultyDisplayName: (name: string) => name,
}));
const item: CalendarOccurrence = {
  id: 'class-1',
  assignment_id: 'a',
  offering_id: 'o',
  date: '2026-10-30',
  starts_at: '2026-10-30T08:00:00+08:00',
  ends_at: '2026-10-30T09:30:00+08:00',
  changed: false,
  subject: { id: 'subject-1', code: 'ADBMS', name: 'Advanced Database Systems' },
  section: { id: 'section-1', name: 'BSIT 3A' },
  teacher: { id: 'teacher-1', name: 'Example instructor' },
  room: {
    id: 'synthetic-student-room-1',
    name: 'LAB-201',
    building: 'Example IT Complex',
    floor: null,
  },
};
function show(path = '/student/rooms?date=2026-10-30&period=term-1', detail = false) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <StudentRooms detail={detail} />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  fixture.preview = true;
  fixture.workspace = {
    context: { mode: 'presentation', period: 'term-1' },
    records: [
      item,
      {
        ...item,
        id: 'class-2',
        date: '2026-11-06',
        starts_at: '2026-11-06T08:00:00+08:00',
        ends_at: '2026-11-06T09:30:00+08:00',
      },
    ],
    date: '2026-10-30',
    data: { status: 'published', version: 'v' },
    loading: false,
    error: '',
    errorStatus: 0,
    retry: vi.fn(),
  };
});
it('defaults to distinct authorized schedule rooms and retains date/term in details', () => {
  show();
  expect(screen.getByRole('button', { name: 'My rooms' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText('Advanced Database Systems')).toBeVisible();
  expect(screen.queryByText('PRRC 101')).not.toBeInTheDocument();
  const href = screen.getByRole('link', { name: 'View LAB-201 details' }).getAttribute('href')!;
  expect(new URL(href, 'http://localhost').searchParams.get('period')).toBe('term-1');
  expect(new URL(href, 'http://localhost').searchParams.get('date')).toBe('2026-10-30');
});
it('keeps the 59 provisional rooms separate and supports combined alias/building search, reset and labs', () => {
  show();
  fireEvent.click(screen.getByRole('button', { name: 'All rooms' }));
  expect(screen.getAllByRole('article')).toHaveLength(59);
  expect(screen.queryByText('Advanced Database Systems')).not.toBeInTheDocument();
  expect(screen.queryByText('On your schedule')).not.toBeInTheDocument();
  const search = screen.getByRole('searchbox', { name: 'Search rooms or buildings' });
  fireEvent.change(search, { target: { value: 'VGA' } });
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByRole('heading', { name: 'PRRC 302' })).toBeVisible();
  fireEvent.change(search, { target: { value: 'New Building' } });
  expect(screen.getAllByRole('article').length).toBeGreaterThan(1);
  fireEvent.change(search, { target: { value: 'no-such-room' } });
  expect(screen.getByRole('heading', { name: 'No matching rooms' })).toBeVisible();
  fireEvent.click(
    within(screen.getByRole('heading', { name: 'No matching rooms' }).parentElement!).getByRole(
      'button',
      { name: 'Clear search' },
    ),
  );
  expect(search).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: 'Labs' }));
  expect(screen.getByRole('heading', { name: 'Lab information is not confirmed' })).toBeVisible();
  expect(screen.queryByRole('article')).not.toBeInTheDocument();
});
it.each([401, 403, 503])('does not show stale room relationships after HTTP %s', (status) => {
  fixture.workspace.error = 'Rejected';
  fixture.workspace.errorStatus = status;
  show();
  expect(screen.getByRole('alert')).toBeVisible();
  expect(screen.queryByText('LAB-201')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(fixture.workspace.retry).toHaveBeenCalledOnce();
});
it('shows loading instead of stale classes', () => {
  fixture.workspace.loading = true;
  show();
  expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
  expect(screen.queryByText('LAB-201')).not.toBeInTheDocument();
});
it('retains a page heading while room details are loading', () => {
  fixture.workspace.loading = true;
  show('/student/rooms/detail?id=synthetic-student-room-1&schedule=1', true);
  expect(screen.getByRole('heading', { name: 'Room details', level: 1 })).toBeVisible();
  expect(screen.queryByText('Advanced Database Systems')).not.toBeInTheDocument();
});
it('honestly shows no assigned rooms and offers the directory', () => {
  fixture.workspace.records = [];
  show();
  expect(screen.getByRole('heading', { name: 'No assigned rooms yet' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Browse all rooms' }));
  expect(screen.getAllByRole('article')).toHaveLength(59);
});
it('does not inject the local directory into an institutional account', () => {
  fixture.preview = false;
  show('/student/rooms?category=all');
  expect(screen.getByRole('heading', { name: 'Room directory unavailable' })).toBeVisible();
  expect(screen.queryByText('PRRC 101')).not.toBeInTheDocument();
  expect(screen.queryByText('Preview tools')).not.toBeInTheDocument();
});
it('shows related class details and retains schedule context', () => {
  show(
    '/student/rooms/detail?id=synthetic-student-room-1&date=2026-10-30&period=term-1&schedule=1',
    true,
  );
  expect(screen.getByRole('heading', { name: 'LAB-201' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Back to Schedule' })).toHaveAttribute(
    'href',
    '/student/schedule?date=2026-10-30&period=term-1',
  );
  fireEvent.click(screen.getByRole('button', { name: /Advanced Database Systems 8:00/ }));
  expect(screen.getByRole('dialog')).toBeVisible();
});
it('does not reveal a guessed unrelated room or class', () => {
  show('/student/rooms/detail?id=cdm-prrc-101&schedule=1', true);
  expect(screen.getByRole('heading', { name: 'Room details unavailable' })).toBeVisible();
  expect(screen.queryByText('Advanced Database Systems')).not.toBeInTheDocument();
});
