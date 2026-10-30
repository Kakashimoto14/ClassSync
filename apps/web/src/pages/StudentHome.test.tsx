import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentHome } from './StudentHome';
import type { CalendarOccurrence } from '../lib/calendar-model';
const fixture = vi.hoisted(() => ({ workspace: {} as Record<string, unknown> }));
vi.mock('../lib/use-schedule-workspace', () => ({ useScheduleWorkspace: () => fixture.workspace }));
const event: CalendarOccurrence = {
  id: '1',
  assignment_id: 'a',
  offering_id: 'o',
  date: '2026-10-30',
  starts_at: '2026-10-30T10:00:00+08:00',
  ends_at: '2026-10-30T11:30:00+08:00',
  changed: false,
  subject: { id: 's', code: 'CS101', name: 'Software Engineering' },
  section: { id: 'x', name: 'Section A' },
  teacher: { id: 't', name: 'Synthetic instructor' },
  room: { id: 'r', name: 'Room A', building: 'Synthetic Building', floor: '2' },
};
function show() {
  return render(
    <MemoryRouter>
      <StudentHome />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.useRealTimers();
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-30T09:00:00+08:00'));
  fixture.workspace = {
    context: { mode: 'published', period: 'p' },
    data: { version: 'v1', status: 'published', revision: 1 },
    date: '2026-10-30',
    records: [event],
    periods: [{ id: 'p', title: 'Synthetic term' }],
    loading: false,
    error: '',
    errorStatus: 0,
    notice: '',
    retry: vi.fn(),
    change: vi.fn(),
  };
});
it('prioritizes a sourced next class, chronological agenda, duration and room path', () => {
  show();
  expect(
    within(screen.getByText('Next class').closest('article')!).getByRole('button', {
      name: 'Software Engineering',
    }),
  ).toBeInTheDocument();
  expect(screen.getByText('Synthetic Building · 2')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Fri, Oct 30, 1 classes/ })).toHaveAttribute(
    'href',
    '/student/schedule?period=p&date=2026-10-30',
  );
  expect(screen.getByRole('link', { name: 'Browse rooms' })).toHaveAttribute(
    'href',
    '/student/rooms?schedule=1',
  );
  expect(screen.getByText(/No changes flagged/)).toBeInTheDocument();
});
it.each([401, 403, 503])(
  'hides previously loaded classes during HTTP %s and provides retry',
  (status) => {
    fixture.workspace.error = 'Rejected';
    fixture.workspace.errorStatus = status;
    show();
    expect(screen.queryByText('Software Engineering')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(fixture.workspace.retry).toHaveBeenCalledOnce();
  },
);
it('does not invent classes when no publication is available', () => {
  fixture.workspace.data = null;
  fixture.workspace.records = [];
  show();
  expect(screen.getByRole('heading', { name: 'No schedule available yet' })).toBeInTheDocument();
  expect(screen.queryByText('CS101')).not.toBeInTheDocument();
});
it('keeps IDs and term controls out of the primary Home interface', () => {
  show();
  expect(screen.queryByText('Version v1')).not.toBeInTheDocument();
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
});
it('limits room details to the requested authorized room and handles unknown IDs honestly', () => {
  const view = render(
    <MemoryRouter initialEntries={['/student/rooms/detail?id=unknown']}>
      <StudentHome rooms roomDetail />
    </MemoryRouter>,
  );
  expect(screen.queryByRole('heading', { name: 'Room A' })).not.toBeInTheDocument();
  expect(
    screen.getByText('This classroom is not in your available timetable for this date.'),
  ).toBeInTheDocument();
  view.unmount();
  render(
    <MemoryRouter initialEntries={['/student/rooms/detail?id=r']}>
      <StudentHome rooms roomDetail />
    </MemoryRouter>,
  );
  expect(screen.getByRole('heading', { name: 'Room A' })).toBeInTheDocument();
});
it('removes class details when the selected class leaves the current data scope', () => {
  const view = show();
  fireEvent.click(
    within(screen.getByText('Next class').closest('article')!).getByRole('button', {
      name: 'Software Engineering',
    }),
  );
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(within(screen.getByRole('dialog')).getByText('Sample · Published')).toBeInTheDocument();
  fixture.workspace.records = [];
  view.rerender(
    <MemoryRouter>
      <StudentHome />
    </MemoryRouter>,
  );
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByText('Software Engineering')).not.toBeInTheDocument();
});
it('announces initial loading and provides an honest class-free day', () => {
  fixture.workspace.data = null;
  fixture.workspace.loading = true;
  const view = show();
  expect(screen.getByRole('status')).toHaveTextContent('Loading your timetable');
  fixture.workspace.loading = false;
  fixture.workspace.data = { version: 'v2', status: 'published' };
  fixture.workspace.records = [];
  view.rerender(
    <MemoryRouter>
      <StudentHome />
    </MemoryRouter>,
  );
  expect(screen.getByText(/No classes today/)).toBeInTheDocument();
  expect(screen.queryByText('Software Engineering')).not.toBeInTheDocument();
});

it('opens a flagged schedule change with its current room instead of a sample announcement', () => {
  fixture.workspace.records = [
    { ...event, changed: true, room: { ...event.room, name: 'Room B' } },
  ];
  show();
  const updates = screen.getByRole('heading', { name: 'Schedule updates' }).closest('section')!;
  expect(updates).toHaveTextContent('Software Engineering · Schedule changed');
  expect(updates).toHaveTextContent('Room B');
  expect(
    screen.queryByText('No changes flagged in your current schedule.'),
  ).not.toBeInTheDocument();
  fireEvent.click(within(updates).getByRole('button', { name: 'Review class' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('Room B');
  expect(
    within(screen.getByRole('dialog')).getByRole('link', { name: 'Open Room Details' }),
  ).toHaveAttribute('href', '/student/rooms/detail?id=r&date=2026-10-30&schedule=1');
});
